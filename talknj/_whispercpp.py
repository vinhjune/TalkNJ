"""Persistent, spawn-safe whisper.cpp CPU worker for pywhispercpp 1.5.1.

The pinned binding wraps a NULL native context as a Python object and discards
whisper_full's status. A separate process keeps native failures out of the UI;
only in-memory PCM and text cross the pipe. No models/audio are downloaded or
written here. Imports of the native binding happen inside the child only.
"""

from __future__ import annotations

import multiprocessing
from multiprocessing.connection import Connection
from pathlib import Path

import numpy as np


def _worker_main(connection: Connection, model_file: str) -> None:
    try:
        # Always pass an existing absolute file, never a built-in model name:
        # pywhispercpp otherwise tries its own implicit model downloader.
        path = Path(model_file)
        if not path.is_absolute() or not path.is_file():
            raise RuntimeError(f"The local GGML model file is missing: {path}")
        from pywhispercpp.model import Model
        import _pywhispercpp as native

        class CheckedModel(Model):
            def _transcribe(self, audio, n_processors=None, extract_probability=False):
                # 1.5.1's public transcribe handles parameters/callbacks, but its
                # private implementation ignores this status. Keep that API and
                # fail before extracting partial/stale segments on native errors.
                status = native.whisper_full(self._ctx, self._params, audio, audio.size)
                if status != 0:
                    raise RuntimeError(f"whisper.cpp decoding failed with native status {status}.")
                count = native.whisper_full_n_segments(self._ctx)
                return self._get_segments(self._ctx, 0, count, extract_probability)

        model = CheckedModel(
            str(path), context_params={"use_gpu": False},
            params_sampling_strategy=1, beam_search={"beam_size": 5, "patience": -1.0},
            print_realtime=False, print_progress=False, print_timestamps=False,
            no_context=True, translate=False, detect_language=False, temperature=0.0,
        )
        # This also probes the opaque context before reporting ready. If the
        # binding returned a wrapper around NULL, only this child can crash.
        multilingual = bool(native.whisper_is_multilingual(model._ctx))
        connection.send(("ready", ("en", "vi") if multilingual else ("en",)))
        while True:
            request = connection.recv()
            if request is None:
                return
            samples, language = request
            try:
                segments = model.transcribe(samples, language=language, translate=False,
                                            detect_language=False, no_context=True)
                text = " ".join(segment.text.strip() for segment in segments
                                if segment.text.strip()).strip()
                connection.send(("result", text))
            except Exception as exc:
                connection.send(("error", f"{type(exc).__name__}: {exc}"))
                return
    except (EOFError, BrokenPipeError):
        # The parent closed the worker during shutdown or a model switch.
        return
    except Exception as exc:
        try:
            connection.send(("error", f"{type(exc).__name__}: {exc}"))
        except (EOFError, OSError):
            pass  # The parent already closed its endpoint; there is no receiver.
    finally:
        connection.close()


class WhisperCppWorker:
    """Own exactly one native model; failed workers are never retried implicitly."""

    def __init__(self, model_file: Path) -> None:
        context = multiprocessing.get_context("spawn")
        self._connection, child = context.Pipe()
        self._process = context.Process(target=_worker_main, args=(child, str(model_file)),
                                        name="TalkNJ-whisper.cpp", daemon=True)
        self._closed = False
        try:
            self._process.start()
        except Exception:
            child.close()
            self._connection.close()
            self._closed = True
            raise
        child.close()
        try:
            kind, languages = self._receive()
            if kind != "ready" or languages not in (("en",), ("en", "vi")):
                raise RuntimeError(f"whisper.cpp could not initialize its CPU model: {languages}")
            self.supported_languages = languages
        except Exception:
            self.close()
            raise

    def _receive(self) -> tuple[str, object]:
        while not self._connection.poll(0.1):
            if not self._process.is_alive():
                if self._connection.poll():
                    break
                raise RuntimeError(
                    f"The whisper.cpp native worker exited unexpectedly "
                    f"(exit code {self._process.exitcode}). The GGML model could not be "
                    "loaded/decoded. Check the model files, CPU compatibility and available memory."
                )
        try:
            message = self._connection.recv()
        except (EOFError, OSError) as exc:
            raise RuntimeError("The whisper.cpp native worker disconnected. Check the GGML "
                               "model, CPU compatibility and available memory.") from exc
        if (not isinstance(message, tuple) or len(message) != 2
                or message[0] not in ("ready", "result", "error")):
            raise RuntimeError("The whisper.cpp worker returned an invalid response.")
        if message[0] == "error":
            raise RuntimeError(f"whisper.cpp native worker failed: {message[1]}")
        return message

    def transcribe(self, samples: np.ndarray, language: str) -> str:
        if self._closed:
            raise RuntimeError("The whisper.cpp worker has stopped; select the model again.")
        try:
            self._connection.send((samples, language))
            kind, text = self._receive()
            if kind != "result" or not isinstance(text, str):
                raise RuntimeError("The whisper.cpp worker returned an invalid transcript.")
            return text
        except Exception as exc:
            self.close()
            raise RuntimeError(f"whisper.cpp offline transcription failed: {exc}") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._process.is_alive():
                try:
                    self._connection.send(None)
                except (EOFError, OSError):
                    pass  # An exited child cannot receive shutdown; join it below.
            self._connection.close()
        finally:
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join()
            self._process.close()
