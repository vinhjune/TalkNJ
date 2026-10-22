"""Explicit model installation and local-only speech model discovery.

Only download_model accesses the network. Installations are assembled beside the
final directory and renamed only after integrity and offline metadata checks.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
from dataclasses import dataclass
from threading import Event
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from tokenizers import Tokenizer

from talknj._model_formats import PARAKEET_FILES, validate_ggml, validate_parakeet


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    repo: str
    size_mb: int
    languages: tuple[str, ...]
    backend: str = "faster-whisper"


@dataclass(frozen=True)
class InstalledModel:
    path: Path
    name: str
    languages: tuple[str, ...]
    backend: str = "faster-whisper"
    model_file: str | None = None


CATALOG = (
    ModelSpec("whisper.cpp-base", "Whisper Base (whisper.cpp)",
              "ggerganov/whisper.cpp", 148, ("en", "vi"), "whisper.cpp"),
    ModelSpec("parakeet-tdt-0.6b-v2-int8", "Parakeet TDT 0.6B v2 (int8)",
              "csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8", 662, ("en",),
              "sherpa-onnx"),
    ModelSpec("tiny.en", "Tiny English", "Systran/faster-whisper-tiny.en", 78, ("en",)),
    ModelSpec("base.en", "Base English", "Systran/faster-whisper-base.en", 148, ("en",)),
    ModelSpec("small.en", "Small English", "Systran/faster-whisper-small.en", 488, ("en",)),
    ModelSpec("tiny", "Tiny multilingual", "Systran/faster-whisper-tiny", 78, ("en", "vi")),
    ModelSpec("base", "Base multilingual", "Systran/faster-whisper-base", 148, ("en", "vi")),
    ModelSpec("small", "Small multilingual", "Systran/faster-whisper-small", 488, ("en", "vi")),
)


class ModelError(RuntimeError):
    """A model is invalid, inaccessible, or could not be installed."""


class DownloadCancelled(ModelError):
    """A user cancelled an installation; its staging directory was removed."""


_FILES = (
    "config.json", "preprocessor_config.json", "model.bin", "tokenizer.json",
    "vocabulary.json", "vocabulary.txt",
)
_REQUIRED = {"config.json", "model.bin", "tokenizer.json"}
_BACKEND_FILES = {
    "faster-whisper": _FILES,
    "sherpa-onnx": PARAKEET_FILES,
    "whisper.cpp": ("ggml-base.bin",),
}
_CHUNK_BYTES = 256 * 1024
_TIMEOUT_SECONDS = 10
_JSON_LIMIT = 32 * 1024 * 1024


def _json_file(path: Path) -> object:
    if path.stat().st_size > _JSON_LIMIT:
        raise ModelError(f"Model metadata is unexpectedly large: {path.name}.")
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def _binary_vocabulary_size(path: Path) -> int:
    """Check the CT2 tensor index without loading or copying model weights.

    CT2 binary versions 4--6 share this format. Checking every payload boundary
    catches truncated imported/downloaded weights before they reach inference.
    CTranslate2 still performs its own architecture validation when loading.
    """
    size = path.stat().st_size
    with path.open("rb") as source:
        def read_exact(count: int) -> bytes:
            data = source.read(count)
            if len(data) != count:
                raise ModelError("model.bin is incomplete; download or export it again.")
            return data

        def integer(fmt: str) -> int:
            return struct.unpack(fmt, read_exact(struct.calcsize(fmt)))[0]

        def string() -> str:
            length = integer("<H")
            if not 1 <= length <= 4096:
                raise ModelError("model.bin has an invalid CTranslate2 string.")
            data = read_exact(length)
            if data[-1] != 0:
                raise ModelError("model.bin has an invalid CTranslate2 string terminator.")
            return data[:-1].decode("utf-8")

        version = integer("<I")
        if version not in (4, 5, 6):
            raise ModelError("model.bin is not a supported CTranslate2 model (binary versions 4–6).")
        if string() != "WhisperSpec":
            raise ModelError("This CTranslate2 model is not a Whisper speech model.")
        if not 1 <= integer("<I") <= 3:
            raise ModelError("This Whisper model needs an unsupported CTranslate2 specification.")
        count = integer("<I")
        if not 1 <= count <= 100000:
            raise ModelError("model.bin has an invalid tensor index.")
        shapes: dict[str, tuple[int, ...]] = {}
        for _ in range(count):
            name = string()
            rank = integer("<B")
            if rank > 8 or name in shapes:
                raise ModelError("model.bin has an invalid tensor shape or duplicate tensor.")
            shape = tuple(integer("<I") for _ in range(rank))
            dtype = integer("<B")
            byte_count = integer("<I")
            item_sizes = (4, 1, 2, 4, 2, 2)
            if (dtype >= len(item_sizes) or any(dim == 0 for dim in shape)
                    or math.prod(shape) * item_sizes[dtype] != byte_count):
                raise ModelError("model.bin has an invalid tensor payload.")
            if source.tell() + byte_count > size:
                raise ModelError("model.bin is incomplete; download or export it again.")
            shapes[name] = shape
            source.seek(byte_count, os.SEEK_CUR)
        alias_count = integer("<I")
        if alias_count > 100000:
            raise ModelError("model.bin has an invalid tensor alias index.")
        for _ in range(alias_count):
            alias, target = string(), string()
            if target not in shapes or alias in shapes:
                raise ModelError("model.bin has an invalid tensor alias.")
            shapes[alias] = shapes[target]
        if source.tell() != size:
            raise ModelError("model.bin contains unexpected trailing data.")
        embedding = shapes.get("decoder/embeddings/weight", ())
        if len(embedding) != 2 or "encoder/conv1/weight" not in shapes:
            raise ModelError("model.bin is missing required Whisper encoder/decoder weights.")
        return embedding[0]


def validate_model(path: Path) -> InstalledModel:
    """Identify and validate a local model directory, without network access.

    Native weights are never loaded into memory by discovery. Each format
    establishes its supported languages from verified weights/metadata rather
    than directory names. Local CT2 tokenizers remain mandatory.
    """
    path = Path(path).expanduser().resolve()
    try:
        if not path.is_dir():
            raise ModelError(f"Model folder does not exist: {path}")
        entries = tuple(path.iterdir())
        relevant = set(_FILES) | set(PARAKEET_FILES)
        for file in entries:
            if (file.name in relevant or file.suffix == ".bin") and file.is_symlink():
                raise ModelError(f"Model files must be inside the imported folder, not symbolic "
                                 f"links: {file.name}.")
            if (file.name in relevant or file.suffix == ".bin") and file.resolve().parent != path:
                raise ModelError(f"Model file escapes the imported folder: {file.name}.")
        has_parakeet = any((path / name).exists() for name in PARAKEET_FILES)
        ggml = [file for file in entries if file.is_file() and file.suffix == ".bin"
                and file.name != "model.bin"]
        has_ct2 = any((path / name).exists() for name in ("model.bin", "config.json", "tokenizer.json"))
        if sum((has_parakeet, bool(ggml), has_ct2)) > 1:
            raise ModelError("This folder mixes multiple model formats. Import one model per folder.")
        if has_parakeet:
            validate_parakeet(path)
            return InstalledModel(path, path.name, ("en",), "sherpa-onnx")
        if ggml:
            if len(ggml) != 1:
                raise ModelError("Import a folder containing exactly one Whisper Base GGML .bin file.")
            return InstalledModel(path, path.name, validate_ggml(ggml[0]), "whisper.cpp", ggml[0].name)
        missing = sorted(name for name in _REQUIRED if not (path / name).is_file())
        if missing:
            raise ModelError(f"Incomplete model in {path}: missing {', '.join(missing)}.")
        config = _json_file(path / "config.json")
        if not isinstance(config, dict):
            raise ModelError("config.json must contain a CTranslate2 Whisper object.")
        for key in ("lang_ids", "suppress_ids", "suppress_ids_begin"):
            ids = config.get(key)
            if not isinstance(ids, list) or any(type(item) is not int or item < 0 for item in ids):
                raise ModelError(f"config.json is missing valid Whisper {key} metadata.")
        vocab_path = path / "vocabulary.json"
        if vocab_path.is_file():
            vocabulary = _json_file(vocab_path)
        else:
            vocab_path = path / "vocabulary.txt"
            if not vocab_path.is_file():
                raise ModelError("Model is missing vocabulary.json or vocabulary.txt.")
            if vocab_path.stat().st_size > _JSON_LIMIT:
                raise ModelError("Model vocabulary is unexpectedly large.")
            with vocab_path.open("r", encoding="utf-8") as source:
                vocabulary = [line.rstrip("\r\n") for line in source]
        if not isinstance(vocabulary, list) or not all(isinstance(t, str) for t in vocabulary):
            raise ModelError("The CTranslate2 vocabulary must be a list of tokens.")
        vocab_size = _binary_vocabulary_size(path / "model.bin")
        if len(vocabulary) != vocab_size:
            raise ModelError("The model weights and vocabulary have different vocabulary sizes.")
        tokenizer_path = path / "tokenizer.json"
        if tokenizer_path.stat().st_size > _JSON_LIMIT:
            raise ModelError("Model tokenizer is unexpectedly large.")
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer_size = tokenizer.get_vocab_size()
        if tokenizer_size != vocab_size:
            # Official tiny.en: tokenizer 50363, CT2 vocabulary 51864; base:
            # 50364 and 51865. Both end their tokenizer at <|notimestamps|>.
            no_timestamps = tokenizer.token_to_id("<|notimestamps|>")
            if (no_timestamps is None or tokenizer_size != no_timestamps + 1
                    or vocab_size - tokenizer_size != 1501
                    or any(vocabulary[tokenizer_size + index]
                           != f"<|{index * 2 // 100}.{index * 2 % 100:02d}|>"
                           for index in range(1501))):
                raise ModelError("The local tokenizer does not match the model vocabulary size.")
        end = tokenizer.token_to_id("<|endoftext|>")
        start = tokenizer.token_to_id("<|startoftranscript|>")
        if end not in (50256, 50257) or start != end + 1:
            raise ModelError("Cannot safely identify this model's Whisper language metadata.")
        required_tokens = ["<|endoftext|>", "<|startoftranscript|>", "<|notimestamps|>"]
        if end == 50257:
            required_tokens.extend(("<|en|>", "<|vi|>", "<|transcribe|>"))
        for token in required_tokens:
            token_id = tokenizer.token_to_id(token)
            if token_id is None or token_id >= len(vocabulary) or vocabulary[token_id] != token:
                raise ModelError(f"The local tokenizer and vocabulary disagree about {token}.")
        languages = ("en", "vi") if end == 50257 else ("en",)
        preprocessor = path / "preprocessor_config.json"
        if preprocessor.is_file():
            settings = _json_file(preprocessor)
            if not isinstance(settings, dict):
                raise ModelError("preprocessor_config.json must contain an object.")
            if settings.get("sampling_rate", 16000) != 16000:
                raise ModelError("Only Whisper models using 16 kHz audio are supported.")
        return InstalledModel(path, path.name, languages)
    except ModelError:
        raise
    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        raise ModelError(f"Cannot read model in {path}: {exc}") from exc
    except Exception as exc:
        # tokenizers reports malformed JSON/models through its extension exception.
        raise ModelError(f"Invalid local tokenizer or model in {path}: {exc}") from exc


def discover_models(root: Path, imported: list[str]) -> list[InstalledModel]:
    """Find root itself, its immediate model children, and explicit imports.

    Incomplete/invalid folders and stale imports are not offered for inference.
    Explicit validation on import provides the diagnostic to the caller.
    """
    root = Path(root).expanduser()
    candidates = [root]
    try:
        if root.is_dir():
            candidates.extend(sorted((p for p in root.iterdir() if not p.name.startswith(".")),
                                     key=lambda p: p.name.casefold()))
    except OSError as exc:
        raise ModelError(f"Cannot list model folder {root}: {exc}") from exc
    candidates.extend(Path(value).expanduser() for value in imported if value.strip())
    found: list[InstalledModel] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            model = validate_model(candidate)
        except ModelError:
            continue
        identity = os.path.normcase(str(model.path))
        if identity not in seen:
            seen.add(identity)
            found.append(model)
    # Stable sorting keeps managed/imported ordering within each backend while
    # preferring native engines even when their folders have been renamed.
    priority = {"whisper.cpp": 0, "sherpa-onnx": 1}
    found.sort(key=lambda model: priority.get(model.backend, 2))
    return found


def _check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise DownloadCancelled("Model download cancelled. No incomplete model was installed.")


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "TalkNJ/0.1", "Accept-Encoding": "identity"})


def _manifest(spec: ModelSpec, cancel: Event) -> tuple[str, list[tuple[str, int, str | None]]]:
    _check_cancel(cancel)
    with urlopen(_request(f"https://huggingface.co/api/models/{spec.repo}?blobs=true"),
                 timeout=_TIMEOUT_SECONDS) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    _check_cancel(cancel)
    if len(data) > 2 * 1024 * 1024:
        raise ModelError("The model server returned unexpectedly large metadata.")
    metadata = json.loads(data)
    if not isinstance(metadata, dict):
        raise ModelError("The model server returned invalid repository metadata.")
    revision = metadata.get("sha")
    siblings = metadata.get("siblings")
    if not isinstance(revision, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", revision):
        raise ModelError("The model server did not provide a valid pinned revision.")
    if not isinstance(siblings, list):
        raise ModelError("The model server did not provide a file list.")
    allowed = _BACKEND_FILES[spec.backend]
    files: dict[str, tuple[str, int, str | None]] = {}
    for item in siblings:
        if not isinstance(item, dict):
            continue
        name = item.get("rfilename")
        if not isinstance(name, str) or name not in allowed:
            continue
        size = item.get("size", 0)
        if type(size) is not int or size < 0:
            raise ModelError(f"Invalid download size for {name}.")
        lfs = item.get("lfs")
        digest = lfs.get("sha256") if isinstance(lfs, dict) else None
        if digest is not None and (not isinstance(digest, str)
                                   or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
            raise ModelError(f"Invalid checksum metadata for {name}.")
        if name in files:
            raise ModelError(f"The model server returned duplicate metadata for {name}.")
        if spec.backend != "faster-whisper" and name != "tokens.txt" and digest is None:
            raise ModelError(f"The model server did not provide the required SHA256 for {name}.")
        files[name] = (name, size, digest)
    if spec.backend == "faster-whisper":
        complete = (_REQUIRED.issubset(files)
                    and bool({"vocabulary.txt", "vocabulary.json"}.intersection(files)))
        # CT2 prefers JSON. Do not download a redundant legacy vocabulary.
        if "vocabulary.json" in files:
            files.pop("vocabulary.txt", None)
    else:
        complete = set(allowed).issubset(files)
    if not complete:
        raise ModelError("The official repository is missing required offline model files.")
    return revision, [files[name] for name in allowed if name in files]


def download_model(
    spec: ModelSpec,
    root: Path,
    progress: Callable[[int, int, str], None],
    cancel: Event,
) -> Path:
    """Download only catalog files, with byte progress and atomic installation.

    Cancellation is checked between chunks and before the final rename. A
    blocked network read has a ten-second timeout. Existing invalid folders are
    never deleted or overwritten; the user must choose another destination.
    """
    if spec not in CATALOG:
        raise ModelError("Only the official models in the catalog may be downloaded.")
    _check_cancel(cancel)
    root = Path(root).expanduser().resolve()
    target = root / spec.id
    staging: Path | None = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            try:
                installed = validate_model(target)
            except ModelError as exc:
                raise ModelError(f"An incomplete or invalid folder already exists at {target}. "
                                 "Move it aside or choose another model folder before downloading.") from exc
            if installed.languages != spec.languages or installed.backend != spec.backend:
                raise ModelError(f"The existing model at {target} does not match {spec.name}.")
            names = ((installed.model_file,) if installed.model_file
                     else _BACKEND_FILES[spec.backend])
            total = sum((target / name).stat().st_size for name in names if (target / name).is_file())
            progress(total, total, "Already installed")
            _check_cancel(cancel)
            return installed.path
        progress(0, 0, "Reading model file list")
        revision, files = _manifest(spec, cancel)
        total = sum(size for _, size, _ in files) if all(size > 0 for _, size, _ in files) else 0
        staging = Path(tempfile.mkdtemp(prefix=f".{spec.id}.incomplete-", dir=root))
        done = 0
        for name, expected_size, expected_digest in files:
            _check_cancel(cancel)
            progress(done, total, name)
            digest = hashlib.sha256()
            received = 0
            url = f"https://huggingface.co/{spec.repo}/resolve/{revision}/{name}"
            with urlopen(_request(url), timeout=_TIMEOUT_SECONDS) as response:
                with (staging / name).open("xb") as output:
                    while True:
                        _check_cancel(cancel)
                        chunk = response.read(_CHUNK_BYTES)
                        _check_cancel(cancel)
                        if not chunk:
                            break
                        received += len(chunk)
                        if expected_size and received > expected_size:
                            raise ModelError(f"The download of {name} exceeded its declared size.")
                        output.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        progress(done, total, name)
            if expected_size and received != expected_size:
                raise ModelError(f"Incomplete download of {name}: expected {expected_size} bytes, "
                                 f"received {received}.")
            if expected_digest and digest.hexdigest().lower() != expected_digest.lower():
                raise ModelError(f"Checksum mismatch for {name}; the download was not installed.")
        _check_cancel(cancel)
        installed = validate_model(staging)
        if installed.languages != spec.languages or installed.backend != spec.backend:
            raise ModelError("Downloaded model metadata does not match its catalog backend/languages.")
        progress(done, total, "Installing validated model")
        _check_cancel(cancel)
        # Same-filesystem rename never exposes partially downloaded model files.
        # Windows refuses an existing target, avoiding replacement in a race.
        staging.rename(target)
        staging = None
        return target
    except DownloadCancelled:
        raise
    except ModelError:
        raise
    except (OSError, URLError, ValueError) as exc:
        raise ModelError(f"Could not download {spec.name} to {root}: {exc}. "
                         "Check the network connection, free disk space, and folder permissions.") from exc
    finally:
        if staging is not None:
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                raise ModelError(f"Could not remove incomplete download {staging}: {exc}. "
                                 "This hidden folder is not a usable installed model.") from exc
