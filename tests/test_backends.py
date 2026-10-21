"""Backend boundaries without speech-model weights, spawned processes or network."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from talknj import _whispercpp, models, transcription


def _installed(tmp_path: Path, backend: str) -> models.InstalledModel:
    path = (tmp_path / backend).resolve()
    return models.InstalledModel(path, backend,
                                 ("en",) if backend == "sherpa-onnx" else ("en", "vi"),
                                 backend, "ggml-base.bin" if backend == "whisper.cpp" else None)


def test_parakeet_rejects_vietnamese_before_importing_its_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _installed(tmp_path, "sherpa-onnx")
    monkeypatch.setattr(transcription, "validate_model", lambda _path: installed)
    monkeypatch.setitem(sys.modules, "sherpa_onnx", None)
    with pytest.raises(ValueError, match="English-only"):
        transcription.Transcriber().transcribe(np.ones(10, dtype=np.float32), installed.path, "vi")


@pytest.mark.parametrize("backend,module", [("sherpa-onnx", "sherpa_onnx"),
                                            ("faster-whisper", "faster_whisper")])
def test_missing_native_runtime_is_a_job_error_not_an_import_time_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, module: str,
) -> None:
    installed = _installed(tmp_path, backend)
    monkeypatch.setattr(transcription, "validate_model", lambda _path: installed)
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(RuntimeError, match=f"Cannot load the local model.*{backend}"):
        transcription.Transcriber().transcribe(np.ones(10, dtype=np.float32), installed.path, "en")


def test_backend_switch_closes_previous_weights_before_next_load_and_close_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = [_installed(tmp_path, backend)
                 for backend in ("faster-whisper", "sherpa-onnx", "whisper.cpp")]
    by_path = {model.path: model for model in installed}
    events: list[tuple[str, str]] = []

    def load(model: models.InstalledModel) -> object:
        events.append(("load", model.backend))
        return SimpleNamespace(
            supported_languages=model.languages,
            transcribe=lambda _samples, _language: "Recognized!",
            close=lambda: events.append(("close", model.backend)),
        )

    monkeypatch.setattr(transcription, "validate_model", lambda path: by_path[path])
    monkeypatch.setattr(transcription, "_load_backend", load)
    transcriber = transcription.Transcriber()
    for model in installed:
        transcriber.transcribe(np.ones(10, dtype=np.float32), model.path, "en")
        transcriber.transcribe(np.ones(10, dtype=np.float32), model.path, "en")
    transcriber.close()
    transcriber.close()
    assert events == [(action, model.backend) for model in installed for action in ("load", "close")]


def test_parakeet_native_decode_exception_is_an_actionable_job_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _installed(tmp_path, "sherpa-onnx")
    monkeypatch.setattr("faster_whisper.vad.get_speech_timestamps", lambda samples, _options:
                        [{"start": 0, "end": len(samples)}])

    def fail(_stream: object) -> None:
        raise RuntimeError("encoder allocation failed")

    recognizer = SimpleNamespace(
        create_stream=lambda: SimpleNamespace(accept_waveform=lambda *_: None), decode_stream=fail,
    )
    monkeypatch.setitem(sys.modules, "sherpa_onnx", SimpleNamespace(
        OfflineRecognizer=SimpleNamespace(from_transducer=lambda **_: recognizer),
    ))
    monkeypatch.setattr(transcription, "validate_model", lambda _path: installed)
    with pytest.raises(RuntimeError, match="Offline transcription failed.*encoder allocation failed"):
        transcription.Transcriber().transcribe(np.ones(10, dtype=np.float32), installed.path, "en")


def test_parakeet_silence_does_not_produce_a_transcript_or_decode_noise() -> None:
    backend = object.__new__(transcription._ParakeetBackend)
    # No recognizer is needed: genuine silence must be rejected by local VAD
    # rather than sent to the speech model and potentially hallucinated.
    backend._recognizer = None
    assert backend.transcribe(np.zeros(3 * 16000, dtype=np.float32), "en") == ""


@pytest.mark.parametrize("middle,expected", [
    (" Another thought. ", "First thought. Another thought. A later thought!"),
    ("   ", "First thought. A later thought!"),
])
def test_parakeet_keeps_all_speech_spans_in_order_without_empty_text_gaps(
    monkeypatch: pytest.MonkeyPatch, middle: str, expected: str,
) -> None:
    samples = np.zeros(80, dtype=np.float32)
    spans = [{"start": 8, "end": 24}, {"start": 32, "end": 48}, {"start": 56, "end": 72}]
    for span, marker in zip(spans, (.25, .5, .75)):
        samples[span["start"]:span["end"]] = marker
    monkeypatch.setattr("faster_whisper.vad.get_speech_timestamps",
                        lambda _samples, _options: spans)
    phrases = {.25: " First thought. ", .5: middle, .75: " A later thought! "}

    class Stream:
        def accept_waveform(self, _rate: int, audio: np.ndarray) -> None:
            self.audio = audio

    def decode(stream: Stream) -> None:
        # Each span represents a different utterance, so omitting/reordering a
        # span or decoding the whole recording cannot preserve the transcript.
        stream.result = SimpleNamespace(text=phrases[float(stream.audio[0])])

    backend = object.__new__(transcription._ParakeetBackend)
    backend._recognizer = SimpleNamespace(create_stream=Stream, decode_stream=decode)
    assert backend.transcribe(samples, "en") == expected


def test_next_explicit_recording_reloads_a_failed_native_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = _installed(tmp_path, "whisper.cpp")
    monkeypatch.setattr(transcription, "validate_model", lambda _path: installed)
    attempts = []
    closed = []

    def load(_installed):
        attempt = len(attempts)
        attempts.append(attempt)

        def recognize(_samples, _language):
            if attempt == 0:
                raise RuntimeError("native worker disconnected")
            return "A fresh recording succeeded."

        return SimpleNamespace(supported_languages=("en", "vi"), transcribe=recognize,
                               close=lambda: closed.append(attempt))

    monkeypatch.setattr(transcription, "_load_backend", load)
    transcriber = transcription.Transcriber()
    samples = np.ones(10, dtype=np.float32)
    with pytest.raises(RuntimeError, match="native worker disconnected"):
        transcriber.transcribe(samples, installed.path, "en")
    assert attempts == [0] and closed == [0]
    assert transcriber.transcribe(samples, installed.path, "en") == "A fresh recording succeeded."
    assert attempts == [0, 1]
    transcriber.close()
    assert closed == [0, 1]


class _Connection:
    def __init__(self, incoming: list[object] | None = None) -> None:
        self.incoming = incoming or []
        self.sent: list[object] = []
        self.closed = False

    def poll(self, _timeout: float = 0) -> bool:
        return bool(self.incoming)

    def recv(self) -> object:
        if not self.incoming:
            raise EOFError
        return self.incoming.pop(0)

    def send(self, message: object) -> None:
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True


class _Process:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.alive = False
        self.exitcode = 0
        self.closed = False
        self.terminated = False

    def start(self) -> None:
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float | None = None) -> None:
        self.alive = False

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def close(self) -> None:
        self.closed = True


def _worker_context(monkeypatch: pytest.MonkeyPatch, incoming: list[object]):
    parent, child = _Connection(incoming), _Connection()
    process = _Process()

    def create(**kwargs: object) -> _Process:
        process.kwargs = kwargs
        return process

    def context(method: str) -> object:
        assert method == "spawn"
        return SimpleNamespace(Pipe=lambda: (parent, child), Process=create)

    monkeypatch.setattr(_whispercpp.multiprocessing, "get_context", context)
    return parent, child, process


def test_whispercpp_close_is_idempotent_and_stops_its_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent, child, process = _worker_context(monkeypatch, [("ready", ("en", "vi"))])
    worker = _whispercpp.WhisperCppWorker(tmp_path / "ggml-base.bin")
    worker.close()
    worker.close()
    assert parent.sent == [None]
    assert child.closed and parent.closed and process.closed


@pytest.mark.parametrize("failure", ["native-exit", "exception", "invalid-message"])
def test_whispercpp_worker_failure_is_fatal_and_never_retries_or_returns_partial_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    parent, _child, process = _worker_context(monkeypatch, [("ready", ("en", "vi"))])
    worker = _whispercpp.WhisperCppWorker(tmp_path / "ggml-base.bin")
    if failure == "native-exit":
        process.alive = False
        process.exitcode = -1073741819
    else:
        parent.incoming.append(("error", "decoder failed") if failure == "exception" else "invalid")
    with pytest.raises(RuntimeError, match="whisper.cpp offline transcription failed"):
        worker.transcribe(np.ones(10, dtype=np.float32), "en")
    assert process.closed and parent.closed
    with pytest.raises(RuntimeError, match="worker has stopped"):
        worker.transcribe(np.ones(10, dtype=np.float32), "en")


def test_whispercpp_child_missing_file_cannot_trigger_implicit_download(tmp_path: Path) -> None:
    connection = _Connection()
    _whispercpp._worker_main(connection, str((tmp_path / "missing.bin").resolve()))
    assert connection.closed
    assert connection.sent[0][0] == "error"
    assert "local GGML model file is missing" in connection.sent[0][1]


@pytest.mark.parametrize("status", [0, -7])
def test_whispercpp_child_forces_cpu_language_and_checks_native_decode_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int,
) -> None:
    model_file = tmp_path / "ggml-base.bin"
    model_file.write_bytes(b"unit test model")
    samples = np.ones(32000, dtype=np.float32)
    connection = _Connection([(samples, "vi"), None])
    loads: list[tuple[str, dict[str, object]]] = []
    requests: list[dict[str, object]] = []
    decodes: list[np.ndarray] = []

    class BindingModel:
        def __init__(self, path: str, **params: object) -> None:
            self._ctx = object()
            self._params = object()
            loads.append((path, params))

        def transcribe(self, audio: np.ndarray, **params: object):
            requests.append(params)
            return self._transcribe(audio)

        @staticmethod
        def _get_segments(*_args: object):
            assert status == 0, "Failed decode must not extract partial/stale native segments"
            return [SimpleNamespace(text=" Xin chào! ")]

    def decode(_ctx: object, _params: object, audio: np.ndarray, count: int) -> int:
        assert count == samples.size and audio is samples
        decodes.append(audio)
        return status

    monkeypatch.setitem(sys.modules, "pywhispercpp.model", SimpleNamespace(Model=BindingModel))
    monkeypatch.setitem(sys.modules, "_pywhispercpp", SimpleNamespace(
        whisper_full=decode, whisper_full_n_segments=lambda _ctx: 1,
        whisper_is_multilingual=lambda _ctx: True,
    ))
    _whispercpp._worker_main(connection, str(model_file.resolve()))
    assert loads[0][0] == str(model_file.resolve())
    assert loads[0][1]["context_params"] == {"use_gpu": False}
    assert loads[0][1]["print_realtime"] is False
    assert loads[0][1]["print_progress"] is False
    assert requests[0] == {"language": "vi", "translate": False,
                           "detect_language": False, "no_context": True}
    assert len(decodes) == 1
    assert connection.sent[0] == ("ready", ("en", "vi"))
    if status == 0:
        assert connection.sent[1] == ("result", "Xin chào!")
    else:
        assert connection.sent[1][0] == "error"
        assert "native status -7" in connection.sent[1][1]
    assert connection.closed




def test_importing_transcription_does_not_import_native_inference_runtimes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins
    import importlib

    original_import = builtins.__import__
    native_imports: list[str] = []

    def track_import(name: str, *args, **kwargs):
        if name.split(".")[0] in ("faster_whisper", "sherpa_onnx", "pywhispercpp", "_pywhispercpp"):
            native_imports.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", track_import)
    importlib.reload(transcription)
    assert native_imports == []
