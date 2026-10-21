"""Bounded-memory integrity checks for the supported native model exports."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path


# Published LFS digests from the sherpa-onnx export repository, revision
# 1ab9323565ddb038682214b292f588070a538ce2. Exact integrity also establishes
# architecture, English-only language and matching token IDs without loading
# ONNX graphs/weights during discovery or trusting a directory name.
PARAKEET_FILES = (
    "encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt",
)
_PARAKEET_DIGESTS = {
    "encoder.int8.onnx": "a32b12d17bbbc309d0686fbbcc2987b5e9b8333a7da83fa6b089f0a2acd651ab",
    "decoder.int8.onnx": "b6bb64963457237b900e496ee9994b59294526439fbcc1fecf705b31a15c6b4e",
    "joiner.int8.onnx": "7946164367946e7f9f29a122407c3252b680dbae9a51343eb2488d057c3c43d2",
    # tokens.txt is a regular Git blob, not an LFS object.
    "tokens.txt": "f0742785f6073e80b911964c455b05f3609bf23b",
}
# ggerganov/whisper.cpp, revision 5359861c739e955e79d9a303bcbc70fb988958b1:
# the standard multilingual Base F16 GGML file, not GGUF or a quantized variant.
_GGML_DIGEST = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"


@lru_cache(maxsize=32)
def _check_published_file(
    path: Path, expected: str, fingerprint: tuple[int, int, int, int], description: str,
) -> None:
    """Cache only successful checks of unchanged files; retain at most 32 keys."""
    size = fingerprint[1]
    is_git_blob = len(expected) == 40
    digest = hashlib.sha1() if is_git_blob else hashlib.sha256()
    if is_git_blob:
        digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as source:
        while chunk := source.read(256 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError(f"{path.name} is incomplete, corrupt, or incompatible. {description}")
    after = path.stat()
    if (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint:
        raise ValueError(f"{path.name} changed during validation; try importing it again.")


def _validate_file(path: Path, digest: str, description: str) -> None:
    if path.is_symlink() or path.resolve().parent != path.parent:
        raise ValueError(f"Model files must be inside the imported folder, not links: {path.name}.")
    stat = path.stat()
    _check_published_file(path, digest,
                          (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns), description)


def validate_parakeet(path: Path) -> None:
    """Accept the exact supported int8 export using chunked, cached hashing."""
    missing = [name for name in PARAKEET_FILES if not (path / name).is_file()]
    if missing:
        raise ValueError(f"Incomplete Parakeet model: missing {', '.join(missing)}.")
    description = (
        "Import encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx and tokens.txt from "
        "csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8 together, "
        "or download Parakeet TDT 0.6B v2 from the catalog."
    )
    for name in PARAKEET_FILES:
        _validate_file(path / name, _PARAKEET_DIGESTS[name], description)


def validate_ggml(path: Path) -> tuple[str, ...]:
    """Accept standard multilingual Whisper Base without parsing/loading weights."""
    _validate_file(path, _GGML_DIGEST,
                   "Import the standard multilingual ggml-base.bin from ggerganov/whisper.cpp "
                   "in its own folder, or download Whisper Base (whisper.cpp) from the catalog. "
                   "English-only, quantized and GGUF variants are not this supported export.")
    return ("en", "vi")
