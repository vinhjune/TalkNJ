"""Local CPU/int8 Whisper inference; no downloads, rewriting, or audio files."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

from talknj.audio import SAMPLE_RATE
from talknj.models import validate_model


class Transcriber:
    """Cache one model and serialize inference, including lazy segment iteration.

    Array input must be mono normalized floating-point PCM at 16 kHz. File input
    must be a local readable file; bundled PyAV decodes/resamples it in memory.
    Whisper supplies punctuation naturally; its output is not rewritten.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._model: WhisperModel | None = None
        self._model_path: Path | None = None

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
            # Avoid loading Whisper or running VAD for empty/digital-silence input.
            if samples.size == 0 or not np.any(samples):
                return ""
            if self._model is None or self._model_path != installed.path:
                # Release the previous model first rather than retaining two CPU
                # weight sets while switching to a larger model.
                self._model = None
                self._model_path = None
                try:
                    model = WhisperModel(
                        str(installed.path), device="cpu", compute_type="int8",
                        local_files_only=True, num_workers=1,
                    )
                except Exception as exc:
                    raise RuntimeError(f"Cannot load the local model at {installed.path}: {exc}. "
                                       "Check that the CTranslate2 export is complete and that "
                                       "enough memory is available.") from exc
                # Check the loaded weights too: imported tokenizer metadata must
                # never cause faster-whisper to silently switch Vietnamese to en.
                if language not in model.supported_languages:
                    raise RuntimeError("The model weights disagree with the tokenizer's language "
                                       "metadata. Export the model and tokenizer together again.")
                self._model = model
                self._model_path = installed.path
            elif language not in self._model.supported_languages:
                raise RuntimeError("The loaded model does not support the selected language.")
            try:
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
            except Exception as exc:
                raise RuntimeError(f"Offline transcription failed: {exc}. "
                                   "Try recording again or select a different local model.") from exc


def _audio_samples(audio: np.ndarray | str | Path) -> np.ndarray:
    if isinstance(audio, (str, Path)):
        path = Path(audio).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Audio file does not exist: {path}")
        try:
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
