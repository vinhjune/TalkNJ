"""Recorder behavior with a deterministic PortAudio double, never a microphone."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from talknj import audio


class FakeStream:
    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs
        self.callback = kwargs["callback"]
        self.finished_callback = kwargs["finished_callback"]
        self.started = False
        self.stopped = False
        self.aborted = False
        self.closed = False
        self.stop_error: Exception | None = None
        self.close_error: Exception | None = None
        self.start_error: Exception | None = None

    def start(self) -> None:
        if self.start_error:
            raise self.start_error
        self.started = True

    def stop(self, ignore_errors: bool = True) -> None:
        self.stopped = True
        self.started = False
        self.finished_callback()
        if self.stop_error and not ignore_errors:
            raise self.stop_error

    def abort(self, ignore_errors: bool = True) -> None:
        self.aborted = True
        self.started = False
        self.finished_callback()
        if self.stop_error and not ignore_errors:
            raise self.stop_error

    def close(self, ignore_errors: bool = True) -> None:
        self.closed = True
        if self.close_error and not ignore_errors:
            raise self.close_error

    def feed(self, samples: np.ndarray, status: object = None) -> None:
        assert self.started
        block = np.asarray(samples, dtype=np.float32)
        if block.ndim == 1:
            block = block[:, None]
        try:
            self.callback(block, len(block), None, status)
        except (audio.sd.CallbackStop, audio.sd.CallbackAbort):
            self.started = False
            self.finished_callback()


@pytest.fixture
def portaudio(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    streams: list[FakeStream] = []
    devices = [
        {"name": "Speakers", "max_input_channels": 0, "hostapi": 0, "default_samplerate": 48000},
        {"name": "Microphone", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 48000},
        {"name": "Microphone", "max_input_channels": 2, "hostapi": 1, "default_samplerate": 44100},
    ]

    def query_devices(device: int | None = None, kind: str | None = None):
        if kind == "input":
            return devices[1 if device is None else device]
        return devices

    def input_stream(**kwargs: object) -> FakeStream:
        stream = FakeStream(**kwargs)
        streams.append(stream)
        return stream

    monkeypatch.setattr(audio, "MAX_SECONDS", 1)
    monkeypatch.setattr(audio.sd, "query_devices", query_devices)
    monkeypatch.setattr(audio.sd, "query_hostapis", lambda: [{"name": "MME"}, {"name": "WASAPI"}])
    monkeypatch.setattr(audio.sd, "check_input_settings", lambda **_kwargs: None)
    monkeypatch.setattr(audio.sd, "InputStream", input_stream)
    return SimpleNamespace(streams=streams, devices=devices)


def test_device_enumeration_excludes_outputs_and_disambiguates_host_apis(portaudio: SimpleNamespace) -> None:
    assert audio.list_input_devices() == [(1, "Microphone [MME]"), (2, "Microphone [WASAPI]")]


def test_device_enumeration_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail():
        raise audio.sd.PortAudioError("driver unavailable")

    monkeypatch.setattr(audio.sd, "query_devices", fail)
    with pytest.raises(RuntimeError, match="privacy.*driver unavailable"):
        audio.list_input_devices()


def test_stop_without_start_returns_empty_float32_audio() -> None:
    recorder = audio.AudioRecorder()
    samples = recorder.stop()
    assert samples.shape == (0,)
    assert samples.dtype == np.float32
    assert recorder.level == 0.0
    assert recorder.error is None
    recorder.cancel()


def test_capture_returns_exact_mono_samples_and_closes_stream(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start(device=2)
    stream = portaudio.streams[-1]
    assert stream.options["device"] == 2
    assert stream.options["channels"] == 1
    assert stream.options["samplerate"] == 16000
    stream.feed(np.array([0.0, -0.2, 0.5], dtype=np.float32))
    assert recorder.level == pytest.approx(0.5)
    stream.feed(np.array([0.7, -0.3], dtype=np.float32))
    samples = recorder.stop()
    np.testing.assert_array_equal(samples, np.array([0.0, -0.2, 0.5, 0.7, -0.3], dtype=np.float32))
    assert samples.dtype == np.float32 and samples.ndim == 1
    assert stream.stopped and stream.closed
    assert recorder.error is None
    assert recorder.level == 0.0
    assert recorder.stop().size == 0


def test_recording_stops_exactly_at_boundary_inside_callback_block(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    stream = portaudio.streams[-1]
    stream.feed(np.full(15995, 0.25, dtype=np.float32))
    stream.feed(np.arange(10, dtype=np.float32) / 10)
    assert recorder.limit_reached is True
    assert recorder.error is None
    assert not stream.started
    samples = recorder.stop()
    assert len(samples) == 16000
    np.testing.assert_array_equal(samples[-5:], np.arange(5, dtype=np.float32) / 10)


def test_exactly_full_block_marks_limit_without_another_callback(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].feed(np.zeros(16000, dtype=np.float32))
    assert recorder.limit_reached
    assert recorder.stop().shape == (16000,)


def test_cancel_discards_audio_and_allows_restart(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    first = portaudio.streams[-1]
    first.feed(np.full(100, 0.2, dtype=np.float32))
    recorder.cancel()
    assert first.aborted and first.closed
    assert recorder.stop().size == 0
    recorder.start()
    second = portaudio.streams[-1]
    second.feed(np.array([0.8], dtype=np.float32))
    np.testing.assert_array_equal(recorder.stop(), np.array([0.8], dtype=np.float32))


def test_overflow_aborts_and_is_not_silently_transcribed(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    stream = portaudio.streams[-1]
    stream.feed(np.ones(10, dtype=np.float32) * 0.1)
    stream.feed(np.ones(10, dtype=np.float32), status="input overflow")
    assert "input overflow" in recorder.error
    assert not stream.started
    with pytest.raises(RuntimeError, match="lost audio.*input overflow"):
        recorder.stop()
    assert stream.closed
    recorder.start()
    assert recorder.error is None
    assert recorder.limit_reached is False
    recorder.cancel()


def test_cancel_after_capture_failure_discards_without_raising_capture_error(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].feed(np.zeros(10, dtype=np.float32), status="input overflow")
    recorder.cancel()
    assert "input overflow" in recorder.error
    assert portaudio.streams[-1].closed


@pytest.mark.parametrize("samples", [np.array([np.nan]), np.array([np.inf]), np.ones((10, 2))])
def test_invalid_callback_audio_sets_error(portaudio: SimpleNamespace, samples: np.ndarray) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].feed(samples)
    assert "invalid audio" in recorder.error
    with pytest.raises(RuntimeError, match="invalid audio"):
        recorder.stop()


def test_level_is_clamped_even_when_device_supplies_clipped_audio(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].feed(np.array([-2.0, 3.0], dtype=np.float32))
    assert recorder.level == 1.0
    recorder.cancel()


def test_unexpected_device_stop_is_reported(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].finished_callback()
    assert "stopped unexpectedly" in recorder.error
    with pytest.raises(RuntimeError, match="stopped unexpectedly"):
        recorder.stop()


def test_double_start_does_not_open_a_second_stream(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    with pytest.raises(RuntimeError, match="already started"):
        recorder.start()
    assert len(portaudio.streams) == 1
    recorder.cancel()


@pytest.mark.parametrize("device", [-1, True, "1", 1.5])
def test_invalid_device_index_is_rejected_before_portaudio(portaudio: SimpleNamespace, device: object) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        audio.AudioRecorder().start(device)
    assert not portaudio.streams


def test_open_failure_sets_error_and_releases_stream(
    portaudio: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def input_stream(**kwargs: object) -> FakeStream:
        stream = FakeStream(**kwargs)
        stream.start_error = audio.sd.PortAudioError("device is busy")
        portaudio.streams.append(stream)
        return stream

    monkeypatch.setattr(audio.sd, "InputStream", input_stream)
    recorder = audio.AudioRecorder()
    with pytest.raises(RuntimeError, match="Windows.*device is busy"):
        recorder.start()
    assert "device is busy" in recorder.error
    assert portaudio.streams[-1].closed
    assert recorder.level == 0.0


def test_output_only_device_fails_with_actionable_error(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    with pytest.raises(RuntimeError, match="no microphone input"):
        recorder.start(device=0)
    assert not portaudio.streams


def test_stop_failure_still_closes_device_and_reports_error(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    stream = portaudio.streams[-1]
    stream.stop_error = audio.sd.PortAudioError("stop failed")
    with pytest.raises(RuntimeError, match="stop failed"):
        recorder.stop()
    assert stream.closed
    assert "stop failed" in recorder.error


def test_cancel_reports_close_failure_but_discards_audio(portaudio: SimpleNamespace) -> None:
    recorder = audio.AudioRecorder()
    recorder.start()
    stream = portaudio.streams[-1]
    stream.close_error = audio.sd.PortAudioError("close failed")
    with pytest.raises(RuntimeError, match="close failed"):
        recorder.cancel()
    assert stream.closed
    assert recorder.level == 0.0


def test_native_rate_fallback_resamples_to_float32_mono_16k(
    portaudio: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked: list[int] = []

    def check_input_settings(**kwargs: object) -> None:
        rate = kwargs["samplerate"]
        checked.append(rate)
        if rate == 16000:
            raise audio.sd.PortAudioError("unsupported sample rate")

    monkeypatch.setattr(audio.sd, "check_input_settings", check_input_settings)
    recorder = audio.AudioRecorder()
    recorder.start(device=1)
    stream = portaudio.streams[-1]
    assert checked == [16000, 48000]
    assert stream.options["samplerate"] == 48000
    time = np.arange(48000, dtype=np.float32) / 48000
    stream.feed((0.25 * np.sin(2 * np.pi * 440 * time)).astype(np.float32))
    samples = recorder.stop()
    assert samples.shape == (16000,)
    assert samples.dtype == np.float32
    assert np.isfinite(samples).all()
    assert np.max(np.abs(samples)) == pytest.approx(0.25, abs=0.01)
    assert recorder.limit_reached is True


def test_resampling_failure_is_actionable_and_device_already_closed(
    portaudio: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def check(**kwargs: object) -> None:
        if kwargs["samplerate"] == 16000:
            raise audio.sd.PortAudioError("unsupported sample rate")

    def fail(_samples: np.ndarray, _rate: int) -> np.ndarray:
        raise RuntimeError("resampler failed")

    monkeypatch.setattr(audio.sd, "check_input_settings", check)
    monkeypatch.setattr(audio, "_resample", fail)
    recorder = audio.AudioRecorder()
    recorder.start()
    portaudio.streams[-1].feed(np.ones(480, dtype=np.float32) * 0.1)
    with pytest.raises(RuntimeError, match="convert microphone audio.*resampler failed"):
        recorder.stop()
    assert portaudio.streams[-1].closed
    assert "resampler failed" in recorder.error
