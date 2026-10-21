"""Local CPU speech inference; native runtimes load only in worker paths."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Protocol

import numpy as np

from talknj.audio import SAMPLE_RATE
from talknj.models import InstalledModel, validate_model


class _Backend(Protocol):
    supported_languages: tuple[str, ...] | list[str]

    def transcribe(self, samples: np.ndarray, language: str) -> str: ...

    def close(self) -> None: ...


class _FasterWhisperBackend:
    def __init__(self, installed: InstalledModel) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            str(installed.path), device="cpu", compute_type="int8",
            local_files_only=True, num_workers=1,
        )
        self.supported_languages = self._model.supported_languages

    def transcribe(self, samples: np.ndarray, language: str) -> str:
        segments, _info = self._model.transcribe(
            samples,
            language=language,
            task="transcribe",
            beam_size=5,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            word_timestamps=False,
        )
        # Work happens in the iterator, not just the transcribe call.
        return " ".join(segment.text.strip() for segment in segments
                        if segment.text.strip()).strip()

    def close(self) -> None:
        self._model = None


class _ParakeetBackend:
    supported_languages = ("en",)

    def __init__(self, installed: InstalledModel) -> None:
        from sherpa_onnx import OfflineRecognizer

        self._recognizer = OfflineRecognizer.from_transducer(
            encoder=str(installed.path / "encoder.int8.onnx"),
            decoder=str(installed.path / "decoder.int8.onnx"),
            joiner=str(installed.path / "joiner.int8.onnx"),
            tokens=str(installed.path / "tokens.txt"),
            model_type="nemo_transducer", provider="cpu", num_threads=4,
            sample_rate=SAMPLE_RATE, feature_dim=128, decoding_method="greedy_search",
        )

    def transcribe(self, samples: np.ndarray, language: str) -> str:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        # Upstream's long-audio flow uses VAD: a single several-minute context
        # can lose speech after long silence. Decode every detected speech span
        # with bounded context, rather than cropping a prefix of the recording.
        spans = get_speech_timestamps(
            samples, VadOptions(max_speech_duration_s=30, min_silence_duration_ms=2000),
        )
        texts = []
        for span in spans:
            stream = self._recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, samples[span["start"]:span["end"]])
            self._recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            if text:
                texts.append(text)
        return " ".join(texts)

    def close(self) -> None:
        self._recognizer = None


def _load_backend(installed: InstalledModel) -> _Backend:
    if installed.backend == "faster-whisper":
        return _FasterWhisperBackend(installed)
    if installed.backend == "sherpa-onnx":
        return _ParakeetBackend(installed)
    if installed.backend == "whisper.cpp":
        from talknj._whispercpp import WhisperCppWorker

        if not installed.model_file:
            raise RuntimeError("The validated model is missing its local GGML file.")
        return WhisperCppWorker(installed.path / installed.model_file)
    raise RuntimeError(f"Unsupported local speech backend: {installed.backend}.")


class Transcriber:
    """Cache exactly one backend and serialize model loading and inference.

    Array input is mono normalized floating-point PCM at 16 kHz. Local files
    are decoded/resampled by bundled PyAV in memory. Inference never downloads
    model files. Native punctuation and casing are preserved without rewriting.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._model: _Backend | None = None
        self._model_path: Path | None = None
        self._backend: str | None = None

    def _release_model(self) -> None:
        model = self._model
        self._model = None
        self._model_path = None
        self._backend = None
        if model is not None:
            model.close()

    def close(self) -> None:
        """Release weights/native workers after active transcription jobs drain."""
        with self._lock:
            self._release_model()

    def transcribe(
        self,
        audio: np.ndarray | str | Path,
        model_path: Path,
        language: str,
    ) -> str:
        if language not in ("en", "vi"):
            raise ValueError("Select English (en) or Vietnamese (vi) for transcription.")
        with self._lock:
            installed = validate_model(model_path)
            if language not in installed.languages:
                raise ValueError("This model is English-only. Select a multilingual model "
                                 "to transcribe Vietnamese.")
            samples = _audio_samples(audio)
            if samples.size == 0 or not np.any(samples):
                return ""
            if (self._model is None or self._model_path != installed.path
                    or self._backend != installed.backend):
                # Close/join the old worker before allocating a new weight set.
                self._release_model()
                try:
                    model = _load_backend(installed)
                except Exception as exc:
                    raise RuntimeError(f"Cannot load the local model at {installed.path} "
                                       f"using {installed.backend}: {exc}. Check that its supported "
                                       "export is complete, the runtime is installed and enough "
                                       "memory is available.") from exc
                if language not in model.supported_languages:
                    model.close()
                    raise RuntimeError("The model weights disagree with the tokenizer's language "
                                       "metadata. Export the model and tokenizer together again.")
                self._model = model
                self._model_path = installed.path
                self._backend = installed.backend
            elif language not in self._model.supported_languages:
                raise RuntimeError("The loaded model does not support the selected language.")
            try:
                return self._model.transcribe(samples, language)
            except Exception as exc:
                # A native worker may have terminated. Discard that instance so
                # the user's next recording can load a fresh engine; never retry
                # this failed recording or return its partial text automatically.
                cleanup = ""
                try:
                    self._release_model()
                except Exception as close_error:
                    cleanup = f" Engine cleanup also failed: {close_error}."
                raise RuntimeError(f"Offline transcription failed ({installed.backend}): {exc}. "
                                   "Try recording again or select a different local model."
                                   + cleanup) from exc


def _audio_samples(audio: np.ndarray | str | Path) -> np.ndarray:
    if isinstance(audio, (str, Path)):
        path = Path(audio).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Audio file does not exist: {path}")
        try:
            from faster_whisper.audio import decode_audio

            samples = decode_audio(str(path), sampling_rate=SAMPLE_RATE)
        except Exception as exc:
            raise RuntimeError(f"Cannot decode the local audio file {path}: {exc}") from exc
    elif isinstance(audio, np.ndarray):
        samples = audio
    else:
        raise TypeError("Audio must be a mono NumPy array or a local audio-file path.")
    if samples.ndim != 1 or not np.issubdtype(samples.dtype, np.floating):
        raise ValueError("Audio must be one-dimensional floating-point mono PCM at 16 kHz.")
    if not np.isfinite(samples).all():
        raise ValueError("Audio contains non-finite samples; record it again.")
    return np.ascontiguousarray(samples, dtype=np.float32)
