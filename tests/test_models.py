"""Deterministic model/download/inference tests; no network or real weights."""

from __future__ import annotations

import hashlib
import io
import json
import struct
from dataclasses import FrozenInstanceError
from functools import lru_cache
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from urllib.error import URLError

import numpy as np
import pytest

from talknj import models
from talknj import _model_formats
from talknj import transcription

_TINY_EN = next(spec for spec in models.CATALOG if spec.id == "tiny.en")


@lru_cache(maxsize=4)
def _model_files(multilingual: bool = False, include_timestamps: bool = False) -> dict[str, bytes]:
    """Small structurally valid CT2 index and real parseable tokenizer metadata.

    The tensors are intentionally not an inference model. Tests exercise local
    validation and download transactions; integration owns real Whisper weights.
    Like official Systran tiny.en/base exports, CT2 includes 1501 timestamp
    tokens which the local tokenizer normally omits. Their IDs are decoded
    arithmetically by faster-whisper rather than through the tokenizer.
    """
    end = 50257 if multilingual else 50256
    size = 51865 if multilingual else 51864
    tokens = [f"token_{index}" for index in range(size)]
    for token, index in {
        "<|endoftext|>": end,
        "<|startoftranscript|>": end + 1,
        "<|en|>": end + 2,
        "<|vi|>": end + 21,
        "<|transcribe|>": end + 102,
        "<|notimestamps|>": end + 106,
    }.items():
        tokens[index] = token
    timestamp_begin = end + 107
    for index in range(1501):
        hundredths = index * 2
        tokens[timestamp_begin + index] = f"<|{hundredths // 100}.{hundredths % 100:02d}|>"
    tokenizer_tokens = tokens if include_timestamps else tokens[:timestamp_begin]
    tokenizer = {
        "version": "1.0", "truncation": None, "padding": None,
        "added_tokens": [], "normalizer": None, "pre_tokenizer": None,
        "post_processor": None, "decoder": None,
        "model": {"type": "WordLevel", "vocab": {t: i for i, t in enumerate(tokenizer_tokens)},
                  "unk_token": "<|endoftext|>"},
    }

    def string(value: str) -> bytes:
        encoded = value.encode("utf-8") + b"\0"
        return struct.pack("<H", len(encoded)) + encoded

    def tensor(name: str, shape: tuple[int, ...], payload: bytes) -> bytes:
        return (string(name) + struct.pack("<B", len(shape))
                + b"".join(struct.pack("<I", d) for d in shape)
                + struct.pack("<BI", 1, len(payload)) + payload)

    binary = (struct.pack("<I", 6) + string("WhisperSpec") + struct.pack("<II", 3, 2)
              + tensor("decoder/embeddings/weight", (size, 1), b"\0" * size)
              + tensor("encoder/conv1/weight", (1, 1, 1), b"\0")
              + struct.pack("<I", 0))
    return {
        "config.json": json.dumps({"lang_ids": [end + 2, end + 21],
                                   "suppress_ids": [], "suppress_ids_begin": []}).encode(),
        "model.bin": binary,
        "tokenizer.json": json.dumps(tokenizer).encode(),
        "vocabulary.json": json.dumps(tokens).encode(),
    }


def _write_model(path: Path, *, multilingual: bool = False) -> Path:
    path.mkdir(parents=True)
    for name, content in _model_files(multilingual).items():
        (path / name).write_bytes(content)
    return path


def _network(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, bytes],
    *,
    fail_file: str | None = None,
    wrong_checksum: bool = False,
    unknown_sizes: bool = False,
    truncated_file: str | None = None,
    checksum_file: str = "model.bin",
) -> list[str]:
    calls: list[str] = []
    siblings = [
        {"rfilename": name, "size": 0 if unknown_sizes else len(content),
         "lfs": {"sha256": "0" * 64 if wrong_checksum and name == checksum_file
                 else hashlib.sha256(content).hexdigest()}}
        for name, content in files.items()
    ]
    siblings.append({"rfilename": "README.md", "size": 100})
    metadata = json.dumps({"sha": "a" * 40, "siblings": siblings}).encode()

    def open_url(request: object, *, timeout: int) -> io.BytesIO:
        url = request.full_url
        calls.append(url)
        if "/api/models/" in url:
            return io.BytesIO(metadata)
        name = url.rsplit("/", 1)[-1]
        if name == fail_file:
            raise URLError("connection interrupted")
        content = files[name]
        if name == truncated_file:
            content = content[:-1]
        return io.BytesIO(content)

    monkeypatch.setattr(models, "urlopen", open_url)
    return calls


def test_catalog_is_immutable_and_exposes_required_languages() -> None:
    by_id = {spec.id: spec for spec in models.CATALOG}
    assert tuple(by_id) == (
        "whisper.cpp-base", "parakeet-tdt-0.6b-v2-int8",
        "tiny.en", "base.en", "small.en", "tiny", "base", "small",
    )
    assert {"tiny.en", "base.en", "small.en", "base", "small"}.issubset(by_id)
    assert by_id["tiny.en"].languages == ("en",)
    assert by_id["base"].languages == ("en", "vi")
    assert by_id["parakeet-tdt-0.6b-v2-int8"].languages == ("en",)
    assert by_id["parakeet-tdt-0.6b-v2-int8"].backend == "sherpa-onnx"
    assert by_id["whisper.cpp-base"].languages == ("en", "vi")
    assert by_id["whisper.cpp-base"].backend == "whisper.cpp"
    with pytest.raises(FrozenInstanceError):
        by_id["base"].name = "changed"


@pytest.mark.parametrize("multilingual,name,expected", [
    (False, "renamed-multilingual", ("en",)),
    (True, "misleading-tiny.en", ("en", "vi")),
])
def test_language_comes_from_metadata_not_directory_or_language_token_presence(
    tmp_path: Path, multilingual: bool, name: str, expected: tuple[str, ...],
) -> None:
    path = _write_model(tmp_path / name, multilingual=multilingual)
    installed = models.validate_model(path)
    assert installed.path == path.resolve()
    assert installed.languages == expected


def test_legacy_text_vocabulary_is_supported(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "legacy")
    vocabulary = json.loads((path / "vocabulary.json").read_text(encoding="utf-8"))
    (path / "vocabulary.json").unlink()
    (path / "vocabulary.txt").write_text("\n".join(vocabulary) + "\n", encoding="utf-8")
    assert models.validate_model(path).languages == ("en",)


@pytest.mark.parametrize("missing", ["model.bin", "config.json", "tokenizer.json", "vocabulary.json"])
def test_missing_offline_files_are_rejected(tmp_path: Path, missing: str) -> None:
    path = _write_model(tmp_path / "broken")
    (path / missing).unlink()
    with pytest.raises(models.ModelError, match="missing"):
        models.validate_model(path)


def test_truncated_model_is_rejected_before_inference(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "broken")
    (path / "model.bin").write_bytes(_model_files()["model.bin"][:-10])
    with pytest.raises(models.ModelError, match="incomplete"):
        models.validate_model(path)


def test_non_whisper_weights_are_rejected(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "broken")
    binary = _model_files()["model.bin"].replace(b"WhisperSpec", b"NotWhisperX", 1)
    (path / "model.bin").write_bytes(binary)
    with pytest.raises(models.ModelError, match="not a Whisper"):
        models.validate_model(path)


def test_mismatched_tokenizer_and_vocabulary_are_rejected(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "mismatch")
    vocabulary = json.loads((path / "vocabulary.json").read_text(encoding="utf-8"))
    vocabulary[50256] = "wrong-token"
    (path / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
    with pytest.raises(models.ModelError, match="disagree"):
        models.validate_model(path)


@pytest.mark.parametrize("metadata", [[], {"lang_ids": "not IDs"},
                                      {"lang_ids": [True], "suppress_ids": [], "suppress_ids_begin": []}])
def test_invalid_config_reports_a_model_error(tmp_path: Path, metadata: object) -> None:
    path = _write_model(tmp_path / "broken")
    (path / "config.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(models.ModelError, match="config.json"):
        models.validate_model(path)


def test_corrupt_tokenizer_is_rejected(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "broken")
    (path / "tokenizer.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(models.ModelError, match="tokenizer"):
        models.validate_model(path)


def test_discovery_omits_staging_invalid_stale_and_duplicate_paths(tmp_path: Path) -> None:
    root = tmp_path / "models"
    managed = _write_model(root / "english")
    _write_model(root / ".base.incomplete-example", multilingual=True)
    (root / "invalid").mkdir()
    imported = _write_model(tmp_path / "imported", multilingual=True)
    found = models.discover_models(root, [str(imported), str(managed), str(tmp_path / "missing")])
    assert [model.path for model in found] == [managed.resolve(), imported.resolve()]


def test_discovery_accepts_root_that_is_itself_a_model(tmp_path: Path) -> None:
    model = _write_model(tmp_path / "root-model")
    assert [item.path for item in models.discover_models(model, [])] == [model.resolve()]


def test_download_is_atomic_pinned_and_reports_monotonic_byte_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = _model_files()
    calls = _network(monkeypatch, files)
    root = tmp_path / "models"
    observed: list[tuple[int, int, str]] = []

    def progress(done: int, total: int, name: str) -> None:
        observed.append((done, total, name))
        assert models.discover_models(root, []) == []

    path = models.download_model(_TINY_EN, root, progress, Event())
    assert path == (root / "tiny.en").resolve()
    assert models.validate_model(path).languages == ("en",)
    total = sum(map(len, files.values()))
    assert observed[-1][:2] == (total, total)
    assert [done for done, _, _ in observed] == sorted(done for done, _, _ in observed)
    assert len(calls) == len(files) + 1
    assert all("/resolve/" + "a" * 40 + "/" in url for url in calls[1:])
    assert sorted(item.name for item in root.iterdir()) == ["tiny.en"]


def test_unknown_download_sizes_report_zero_total(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _network(monkeypatch, _model_files(), unknown_sizes=True)
    progress: list[tuple[int, int, str]] = []
    models.download_model(_TINY_EN, tmp_path / "models", lambda *args: progress.append(args), Event())
    assert all(total == 0 for _, total, _ in progress)
    assert progress[-1][0] > 0


@pytest.mark.parametrize("failure", ["network", "truncated", "checksum"])
def test_failed_download_never_installs_or_leaves_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    _network(monkeypatch, _model_files(), fail_file="model.bin" if failure == "network" else None,
             truncated_file="model.bin" if failure == "truncated" else None,
             wrong_checksum=failure == "checksum")
    root = tmp_path / "models"
    with pytest.raises(models.ModelError):
        models.download_model(_TINY_EN, root, lambda *_: None, Event())
    assert list(root.iterdir()) == []


def test_cancel_before_download_does_not_contact_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _network(monkeypatch, _model_files())
    cancel = Event()
    cancel.set()
    with pytest.raises(models.DownloadCancelled):
        models.download_model(_TINY_EN, tmp_path / "models", lambda *_: None, cancel)
    assert calls == []
    assert not (tmp_path / "models").exists()


@pytest.mark.parametrize("when", ["during file", "before rename"])
def test_cancel_removes_all_incomplete_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, when: str,
) -> None:
    _network(monkeypatch, _model_files())
    monkeypatch.setattr(models, "_CHUNK_BYTES", 8192)
    root = tmp_path / "models"
    cancel = Event()

    def progress(done: int, _total: int, name: str) -> None:
        if ((when == "during file" and name == "model.bin" and done > 8192)
                or (when == "before rename" and name == "Installing validated model")):
            cancel.set()

    with pytest.raises(models.DownloadCancelled):
        models.download_model(_TINY_EN, root, progress, cancel)
    assert list(root.iterdir()) == []
    assert models.discover_models(root, []) == []


def test_existing_good_model_is_reused_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "models"
    model = _write_model(root / "tiny.en")
    calls = _network(monkeypatch, _model_files())
    assert models.download_model(_TINY_EN, root, lambda *_: None, Event()) == model.resolve()
    assert calls == []


def test_existing_invalid_folder_is_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "models"
    target = root / "tiny.en"
    target.mkdir(parents=True)
    marker = target / "user-file.txt"
    marker.write_text("preserve me", encoding="utf-8")
    calls = _network(monkeypatch, _model_files())
    with pytest.raises(models.ModelError, match="already exists"):
        models.download_model(_TINY_EN, root, lambda *_: None, Event())
    assert marker.read_text(encoding="utf-8") == "preserve me"
    assert calls == []


def test_download_rejects_non_catalog_repositories(tmp_path: Path) -> None:
    custom = models.ModelSpec("../outside", "untrusted", "other/repo", 1, ("en",))
    with pytest.raises(models.ModelError, match="official"):
        models.download_model(custom, tmp_path, lambda *_: None, Event())


def test_download_rejects_catalog_language_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _network(monkeypatch, _model_files(multilingual=True))
    root = tmp_path / "models"
    with pytest.raises(models.ModelError, match="languages"):
        models.download_model(_TINY_EN, root, lambda *_: None, Event())
    assert list(root.iterdir()) == []


def test_transcriber_caches_one_model_and_preserves_whisper_punctuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_model(tmp_path / "english")
    loads: list[tuple[str, dict[str, object]]] = []
    requests: list[dict[str, object]] = []

    class FakeWhisper:
        supported_languages = ["en"]

        def __init__(self, model_path: str, **kwargs: object) -> None:
            loads.append((model_path, kwargs))

        def transcribe(self, samples: np.ndarray, **kwargs: object) -> tuple[object, None]:
            requests.append(kwargs)
            assert samples.dtype == np.float32 and samples.ndim == 1
            return iter([SimpleNamespace(text=" Hello, world! "), SimpleNamespace(text=" It works.")]), None

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisper)
    transcriber = transcription.Transcriber()
    samples = np.ones(1600, dtype=np.float64) * 0.1
    assert transcriber.transcribe(samples, path, "en") == "Hello, world! It works."
    assert transcriber.transcribe(samples, path, "en") == "Hello, world! It works."
    assert len(loads) == 1
    assert loads[0][1]["device"] == "cpu"
    assert loads[0][1]["compute_type"] == "int8"
    assert loads[0][1]["local_files_only"] is True
    assert requests[0]["vad_filter"] is True
    assert requests[0]["task"] == "transcribe"


def test_transcriber_refuses_vietnamese_with_english_weights(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "english")
    with pytest.raises(ValueError, match="English-only"):
        transcription.Transcriber().transcribe(np.ones(10, dtype=np.float32), path, "vi")


@pytest.mark.parametrize("samples", [np.empty(0, dtype=np.float32), np.zeros(1600, dtype=np.float32)])
def test_silence_does_not_load_model_or_hallucinate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, samples: np.ndarray,
) -> None:
    path = _write_model(tmp_path / "english")

    def unexpected_load(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Silent input must not load Whisper")

    monkeypatch.setattr("faster_whisper.WhisperModel", unexpected_load)
    assert transcription.Transcriber().transcribe(samples, path, "en") == ""


@pytest.mark.parametrize("samples", [np.zeros((10, 2), dtype=np.float32),
                                     np.array([1, 2], dtype=np.int16),
                                     np.array([np.nan], dtype=np.float32)])
def test_transcriber_rejects_invalid_audio_boundaries(tmp_path: Path, samples: np.ndarray) -> None:
    path = _write_model(tmp_path / "english")
    with pytest.raises(ValueError, match="Audio"):
        transcription.Transcriber().transcribe(samples, path, "en")


def test_lazy_inference_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_model(tmp_path / "english")

    class FailingWhisper:
        supported_languages = ["en"]

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def transcribe(self, *_args: object, **_kwargs: object) -> tuple[object, None]:
            def segments():
                yield SimpleNamespace(text="Partial output")
                raise RuntimeError("decoder failed")
            return segments(), None

    monkeypatch.setattr("faster_whisper.WhisperModel", FailingWhisper)
    with pytest.raises(RuntimeError, match="Offline transcription failed.*decoder failed"):
        transcription.Transcriber().transcribe(np.ones(100, dtype=np.float32), path, "en")


def test_model_switch_replaces_cached_model_and_supports_vietnamese(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    english = _write_model(tmp_path / "english")
    multilingual = _write_model(tmp_path / "multilingual", multilingual=True)
    loaded: list[str] = []

    class FakeWhisper:
        def __init__(self, path: str, **_kwargs: object) -> None:
            loaded.append(path)
            self.supported_languages = ["en", "vi"] if path == str(multilingual) else ["en"]

        def transcribe(self, _samples: np.ndarray, **kwargs: object) -> tuple[object, None]:
            text = "Xin chào, thế giới!" if kwargs["language"] == "vi" else "Hello!"
            return iter([SimpleNamespace(text=text)]), None

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisper)
    transcriber = transcription.Transcriber()
    samples = np.ones(100, dtype=np.float32) * 0.1
    assert transcriber.transcribe(samples, english, "en") == "Hello!"
    assert transcriber.transcribe(samples, multilingual, "vi") == "Xin chào, thế giới!"
    assert transcriber.transcribe(samples, english, "en") == "Hello!"
    assert loaded == [str(english), str(multilingual), str(english)]


def test_missing_tokenizer_is_rejected_before_whisper_can_download_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_model(tmp_path / "english")
    (path / "tokenizer.json").unlink()

    def unexpected_load(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Missing local tokenizer must be rejected before Whisper construction")

    monkeypatch.setattr("faster_whisper.WhisperModel", unexpected_load)
    with pytest.raises(models.ModelError, match="tokenizer.json"):
        transcription.Transcriber().transcribe(np.ones(100, dtype=np.float32), path, "en")


def test_model_load_failure_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_model(tmp_path / "english")

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("not enough memory")

    monkeypatch.setattr("faster_whisper.WhisperModel", fail)
    with pytest.raises(RuntimeError, match="Cannot load the local model.*not enough memory"):
        transcription.Transcriber().transcribe(np.ones(100, dtype=np.float32), path, "en")


def test_file_decode_failure_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_model(tmp_path / "english")
    invalid_audio = tmp_path / "invalid.wav"
    invalid_audio.write_bytes(b"not an audio file")

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unrecognized media")

    monkeypatch.setattr("faster_whisper.audio.decode_audio", fail)
    with pytest.raises(RuntimeError, match="Cannot decode the local audio file.*unrecognized media"):
        transcription.Transcriber().transcribe(invalid_audio, path, "en")


def test_unsupported_language_fails_before_model_discovery(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="English.*Vietnamese"):
        transcription.Transcriber().transcribe(np.ones(100, dtype=np.float32), tmp_path / "missing", "fr")


@pytest.mark.parametrize("multilingual,tokenizer_size,vocabulary_size", [
    (False, 50363, 51864),
    (True, 50364, 51865),
])
def test_official_layout_accepts_tokenizer_without_arithmetic_timestamp_tokens(
    tmp_path: Path, multilingual: bool, tokenizer_size: int, vocabulary_size: int,
) -> None:
    path = _write_model(tmp_path / "official-layout", multilingual=multilingual)
    # Counts and timestamp IDs match the published Systran tiny.en/base exports.
    tokenizer = models.Tokenizer.from_file(str(path / "tokenizer.json"))
    vocabulary = json.loads((path / "vocabulary.json").read_text(encoding="utf-8"))
    assert tokenizer.get_vocab_size() == tokenizer_size
    assert len(vocabulary) == vocabulary_size
    assert vocabulary[tokenizer_size] == "<|0.00|>"
    assert vocabulary[-1] == "<|30.00|>"
    assert tokenizer.token_to_id("<|0.00|>") is None
    assert models.validate_model(path).languages == (("en", "vi") if multilingual else ("en",))


@pytest.mark.parametrize("multilingual", [False, True])
def test_imported_tokenizer_with_full_timestamp_vocabulary_is_supported(
    tmp_path: Path, multilingual: bool,
) -> None:
    path = _write_model(tmp_path / "full-tokenizer", multilingual=multilingual)
    (path / "tokenizer.json").write_bytes(_model_files(multilingual, True)["tokenizer.json"])
    assert models.validate_model(path).languages == (("en", "vi") if multilingual else ("en",))


def test_missing_non_timestamp_token_is_not_mistaken_for_optional_timestamp_suffix(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "incomplete-tokenizer")
    tokenizer = json.loads((path / "tokenizer.json").read_text(encoding="utf-8"))
    del tokenizer["model"]["vocab"]["<|notimestamps|>"]
    (path / "tokenizer.json").write_text(json.dumps(tokenizer), encoding="utf-8")
    with pytest.raises(models.ModelError, match="vocabulary size"):
        models.validate_model(path)


def test_noncanonical_omitted_timestamp_suffix_is_rejected(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "wrong-timestamps")
    vocabulary = json.loads((path / "vocabulary.json").read_text(encoding="utf-8"))
    vocabulary[50363] = "<|0.01|>"
    (path / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
    with pytest.raises(models.ModelError, match="vocabulary size"):
        models.validate_model(path)


def test_equal_size_language_token_mismatch_is_still_rejected(tmp_path: Path) -> None:
    path = _write_model(tmp_path / "wrong-language-token", multilingual=True)
    vocabulary = json.loads((path / "vocabulary.json").read_text(encoding="utf-8"))
    vocabulary[50278], vocabulary[50279] = vocabulary[50279], vocabulary[50278]
    (path / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
    with pytest.raises(models.ModelError, match="disagree.*vi"):
        models.validate_model(path)


@pytest.fixture
def native_payloads(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, bytes]]:
    # Transaction/validation fixtures are tiny stand-ins, not inference models.
    # Only their expected digests are replaced; the real streaming validator and
    # downloader run unchanged. Integration owns published weights and execution.
    parakeet = {name: (name + " official test payload").encode()
                for name in _model_formats.PARAKEET_FILES}
    digests = {}
    for name, content in parakeet.items():
        digests[name] = (hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                         if name == "tokens.txt" else hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(_model_formats, "_PARAKEET_DIGESTS", digests)
    ggml = {"ggml-base.bin": b"standard multilingual Base test payload"}
    monkeypatch.setattr(_model_formats, "_GGML_DIGEST",
                        hashlib.sha256(ggml["ggml-base.bin"]).hexdigest())
    return {"sherpa-onnx": parakeet, "whisper.cpp": ggml}


def _write_native_model(path: Path, files: dict[str, bytes]) -> Path:
    path.mkdir(parents=True)
    for name, content in files.items():
        (path / name).write_bytes(content)
    return path


def test_discovery_prioritizes_native_backends_even_for_renamed_imports(
    tmp_path: Path, native_payloads: dict[str, dict[str, bytes]],
) -> None:
    root = tmp_path / "models"
    faster_a = _write_model(root / "a-english")
    faster_b = _write_model(root / "b-english")
    parakeet = _write_native_model(root / "z-native", native_payloads["sherpa-onnx"])
    imported_faster = _write_model(tmp_path / "external-english")
    imported_parakeet = _write_native_model(tmp_path / "renamed-onnx", native_payloads["sherpa-onnx"])
    imported_whisper = _write_native_model(tmp_path / "renamed-ggml", native_payloads["whisper.cpp"])
    imported = [str(imported_faster), str(imported_parakeet), str(imported_whisper)]

    found = models.discover_models(root, imported)

    assert [model.path for model in found] == [
        path.resolve() for path in (
            imported_whisper, parakeet, imported_parakeet, faster_a, faster_b, imported_faster,
        )
    ]


@pytest.mark.parametrize("backend", ["sherpa-onnx", "whisper.cpp"])
def test_native_models_download_discover_import_and_reuse_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    native_payloads: dict[str, dict[str, bytes]], backend: str,
) -> None:
    files = native_payloads[backend]
    calls = _network(monkeypatch, files)
    spec = next(spec for spec in models.CATALOG if spec.backend == backend)
    root = tmp_path / "models"
    progress: list[tuple[int, int, str]] = []

    def report(done: int, total: int, name: str) -> None:
        progress.append((done, total, name))
        assert models.discover_models(root, []) == []

    path = models.download_model(spec, root, report, Event())
    installed = models.validate_model(path)
    assert installed.backend == backend
    assert installed.languages == spec.languages
    assert installed.model_file == ("ggml-base.bin" if backend == "whisper.cpp" else None)
    assert progress[-1][:2] == (sum(map(len, files.values())),) * 2
    assert [row[0] for row in progress] == sorted(row[0] for row in progress)
    assert len(calls) == len(files) + 1
    assert all("/resolve/" + "a" * 40 + "/" in url for url in calls[1:])
    assert {url.rsplit("/", 1)[-1] for url in calls[1:]} == set(files)
    calls.clear()
    imported = _write_native_model(tmp_path / "renamed-import", files)
    assert [item.path for item in models.discover_models(root, [str(imported)])] == [path, imported]
    assert models.download_model(spec, root, lambda *_: None, Event()) == path
    assert calls == []


@pytest.mark.parametrize("backend", ["sherpa-onnx", "whisper.cpp"])
@pytest.mark.parametrize("failure", ["network", "truncated", "checksum", "cancel"])
def test_native_download_failures_leave_no_install_or_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    native_payloads: dict[str, dict[str, bytes]], backend: str, failure: str,
) -> None:
    files = native_payloads[backend]
    first = next(iter(files))
    _network(monkeypatch, files, fail_file=first if failure == "network" else None,
             truncated_file=first if failure == "truncated" else None,
             wrong_checksum=failure == "checksum", checksum_file=first)
    spec = next(spec for spec in models.CATALOG if spec.backend == backend)
    cancel = Event()

    def report(done: int, _total: int, _name: str) -> None:
        if failure == "cancel" and done:
            cancel.set()

    with pytest.raises(models.ModelError):
        models.download_model(spec, tmp_path, report, cancel)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("backend", ["sherpa-onnx", "whisper.cpp"])
def test_native_import_checks_all_payloads_and_rechecks_modified_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    native_payloads: dict[str, dict[str, bytes]], backend: str,
) -> None:
    files = native_payloads[backend]
    path = _write_native_model(tmp_path / "model", files)
    original_open = Path.open
    reads: list[str] = []

    def track_open(file: Path, *args, **kwargs):
        reads.append(file.name)
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track_open)
    assert models.validate_model(path).backend == backend
    assert sorted(reads) == sorted(files)
    reads.clear()
    assert models.validate_model(path).backend == backend
    assert reads == []
    first = path / next(iter(files))
    first.write_bytes(b"truncated")
    with pytest.raises(models.ModelError, match="incomplete, corrupt, or incompatible"):
        models.validate_model(path)
    assert models.discover_models(tmp_path, []) == []


@pytest.mark.parametrize("missing", list(_model_formats.PARAKEET_FILES))
def test_parakeet_incomplete_layout_is_not_offered(
    tmp_path: Path, native_payloads: dict[str, dict[str, bytes]], missing: str,
) -> None:
    path = _write_native_model(tmp_path / "model", native_payloads["sherpa-onnx"])
    (path / missing).unlink()
    with pytest.raises(models.ModelError, match="missing"):
        models.validate_model(path)
    assert models.discover_models(tmp_path, []) == []


@pytest.mark.parametrize("backend", ["sherpa-onnx", "whisper.cpp"])
def test_wrong_native_export_reports_exact_supported_import_contract(
    tmp_path: Path, backend: str,
) -> None:
    files = ({name: b"wrong export" for name in _model_formats.PARAKEET_FILES}
             if backend == "sherpa-onnx" else {"ggml-base.bin": b"gguf or English-only or truncated"})
    path = _write_native_model(tmp_path / "model", files)
    with pytest.raises(models.ModelError, match=("csukuangfj/" if backend == "sherpa-onnx"
                                               else "ggerganov/whisper.cpp")):
        models.validate_model(path)


def test_multiple_model_formats_cannot_silently_choose_a_backend(
    tmp_path: Path, native_payloads: dict[str, dict[str, bytes]],
) -> None:
    path = _write_model(tmp_path / "mixed")
    (path / "ggml-base.bin").write_bytes(native_payloads["whisper.cpp"]["ggml-base.bin"])
    with pytest.raises(models.ModelError, match="mixes multiple model formats"):
        models.validate_model(path)


def test_import_cannot_follow_native_weight_symlink_outside_model_folder(
    tmp_path: Path, native_payloads: dict[str, dict[str, bytes]],
) -> None:
    payload = native_payloads["whisper.cpp"]["ggml-base.bin"]
    external = tmp_path / "outside.bin"
    external.write_bytes(payload)
    path = tmp_path / "model"
    path.mkdir()
    try:
        (path / "ggml-base.bin").symlink_to(external)
    except OSError:
        pytest.skip("Creating symbolic links requires Windows Developer Mode or administrator rights")
    with pytest.raises(models.ModelError, match="symbolic links"):
        models.validate_model(path)


def test_missing_native_manifest_checksum_never_starts_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = json.dumps({"sha": "a" * 40,
                           "siblings": [{"rfilename": "ggml-base.bin", "size": 100}]}).encode()
    monkeypatch.setattr(models, "urlopen", lambda *_args, **_kwargs: io.BytesIO(metadata))
    spec = next(spec for spec in models.CATALOG if spec.backend == "whisper.cpp")
    with pytest.raises(models.ModelError, match="required SHA256"):
        models.download_model(spec, tmp_path, lambda *_: None, Event())
    assert list(tmp_path.iterdir()) == []


def test_loaded_ct2_weights_cannot_silently_override_vietnamese_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_model(tmp_path / "multilingual", multilingual=True)

    class EnglishWeights:
        supported_languages = ["en"]

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def transcribe(self, *_args: object, **_kwargs: object) -> None:
            pytest.fail("Weights/metadata disagreement must be rejected before decoding")

    monkeypatch.setattr("faster_whisper.WhisperModel", EnglishWeights)
    with pytest.raises(RuntimeError, match="weights disagree"):
        transcription.Transcriber().transcribe(np.ones(100, dtype=np.float32), path, "vi")


def test_renamed_ggml_payload_is_reused_with_real_byte_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    native_payloads: dict[str, dict[str, bytes]],
) -> None:
    spec = next(spec for spec in models.CATALOG if spec.backend == "whisper.cpp")
    content = native_payloads["whisper.cpp"]["ggml-base.bin"]
    path = _write_native_model(tmp_path / spec.id, {"renamed.bin": content})
    calls = _network(monkeypatch, native_payloads["whisper.cpp"])
    progress: list[tuple[int, int, str]] = []
    assert models.download_model(spec, tmp_path, lambda *args: progress.append(args), Event()) == path
    assert progress == [(len(content), len(content), "Already installed")]
    assert calls == []
