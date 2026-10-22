"""Bounded, in-memory mono microphone capture with no Qt or disk coupling."""

from __future__ import annotations

import math
import sys
from threading import Lock

import av
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
MAX_SECONDS = 300
_MAX_DEVICE_RATE = 192000
_MICROPHONE_PERMISSIONS = (
    "macOS System Settings > Privacy & Security > Microphone"
    if sys.platform == "darwin" else
    "Windows Settings > Privacy & security > Microphone (including desktop apps)"
)


def list_input_devices() -> list[tuple[int, str]]:
    """Return PortAudio indices and names, including host API to disambiguate."""
    try:
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()
        return [
            (index, f"{device['name']} [{host_apis[device['hostapi']]['name']}]")
            for index, device in enumerate(devices)
            if device["max_input_channels"] > 0
        ]
    except (sd.PortAudioError, OSError) as exc:
        raise RuntimeError("Cannot enumerate microphones. Check microphone privacy permissions in "
                           f"{_MICROPHONE_PERMISSIONS} and your audio drivers: {exc}") from exc


class AudioRecorder:
    """Capture at 16 kHz, falling back to the microphone's native sample rate.

    The callback copies into a fixed-capacity array and never invokes UI code.
    stop() closes PortAudio before resampling and returns float32 mono at 16 kHz.
    A capture error/overflow raises rather than silently transcribing damaged
    audio. A normal duration limit returns the capped recording. start/stop/
    cancel are serialized; properties can be read from the UI thread.
    """

    def __init__(self) -> None:
        self._control = Lock()
        self._state = Lock()
        self._stream: sd.InputStream | None = None
        self._buffer: np.ndarray | None = None
        self._frames = 0
        self._rate = SAMPLE_RATE
        self._level = 0.0
        self._error: str | None = None
        self._limit_reached = False
        self._stopping = False

    @property
    def level(self) -> float:
        with self._state:
            return self._level

    @property
    def error(self) -> str | None:
        with self._state:
            return self._error

    @property
    def limit_reached(self) -> bool:
        with self._state:
            return self._limit_reached

    def start(self, device: int | None = None) -> None:
        if device is not None and (type(device) is not int or device < 0):
            raise ValueError("Microphone device must be a nonnegative PortAudio index or None.")
        with self._control:
            if self._stream is not None:
                raise RuntimeError("Recording is already started. Stop it before starting again.")
            with self._state:
                self._frames = 0
                self._level = 0.0
                self._error = None
                self._limit_reached = False
                self._stopping = False
            stream = None
            try:
                info = sd.query_devices(device, "input")
                if info["max_input_channels"] < 1:
                    raise RuntimeError("The selected audio device has no microphone input channels.")
                rate = SAMPLE_RATE
                try:
                    sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=rate)
                except sd.PortAudioError:
                    native_rate = float(info["default_samplerate"])
                    if not math.isfinite(native_rate) or not 8000 <= native_rate <= _MAX_DEVICE_RATE:
                        raise RuntimeError("The microphone reports an unsupported native sample rate.")
                    rate = round(native_rate)
                    sd.check_input_settings(device=device, channels=1, dtype="float32", samplerate=rate)
                with self._state:
                    self._rate = rate
                    self._buffer = np.empty(rate * MAX_SECONDS, dtype=np.float32)
                stream = sd.InputStream(
                    device=device, channels=1, samplerate=rate, dtype="float32",
                    blocksize=0, callback=self._callback, finished_callback=self._finished,
                )
                self._stream = stream
                stream.start()
            except Exception as exc:
                cleanup_error = None
                if stream is not None:
                    with self._state:
                        self._stopping = True
                    try:
                        stream.close(ignore_errors=False)
                    except Exception as close_exc:
                        cleanup_error = str(close_exc)
                self._stream = None
                message = ("Cannot start microphone recording. Check the selected device, "
                           f"{_MICROPHONE_PERMISSIONS}, "
                           f"and whether another application is using it exclusively: {exc}")
                if cleanup_error:
                    message += f" Closing the failed audio stream also failed: {cleanup_error}"
                with self._state:
                    self._buffer = None
                    self._error = message
                    self._level = 0.0
                raise RuntimeError(message) from exc

    def _callback(self, indata: np.ndarray, frames: int, _time: object, status: object) -> None:
        with self._state:
            if self._stopping or self._buffer is None:
                raise sd.CallbackStop
            if status:
                self._error = ("Microphone capture lost audio or reported a stream problem "
                               f"({status}). Try another device or close CPU-heavy applications.")
                self._level = 0.0
                raise sd.CallbackAbort
            if indata.ndim != 2 or indata.shape != (frames, 1) or not np.isfinite(indata).all():
                self._error = "The microphone returned invalid audio samples. Try another input device."
                self._level = 0.0
                raise sd.CallbackAbort
            count = min(frames, len(self._buffer) - self._frames)
            if count:
                samples = indata[:count, 0]
                self._buffer[self._frames:self._frames + count] = samples
                self._frames += count
                self._level = min(1.0, float(np.max(np.abs(samples))))
            if self._frames >= len(self._buffer):
                self._limit_reached = True
                self._level = 0.0
                raise sd.CallbackStop

    def _finished(self) -> None:
        with self._state:
            self._level = 0.0
            if not self._stopping and not self._limit_reached and self._error is None:
                self._error = ("The microphone stopped unexpectedly. Check the device connection "
                               "and microphone permissions, then record again.")

    def _close_stream(self, *, discard: bool) -> str | None:
        stream = self._stream
        if stream is None:
            return None
        with self._state:
            self._stopping = True
        problems: list[str] = []
        try:
            if discard:
                stream.abort(ignore_errors=False)
            else:
                stream.stop(ignore_errors=False)
        except Exception as exc:
            problems.append(str(exc))
        finally:
            try:
                stream.close(ignore_errors=False)
            except Exception as exc:
                problems.append(str(exc))
            self._stream = None
        if problems:
            message = "Could not stop/close the microphone stream: " + "; ".join(problems)
            with self._state:
                self._error = f"{self._error} {message}" if self._error else message
            return message
        return None

    def stop(self) -> np.ndarray:
        """Return captured audio, or raise for any capture or shutdown failure."""
        with self._control:
            self._close_stream(discard=False)
            with self._state:
                buffer, self._buffer = self._buffer, None
                count = self._frames
                rate = self._rate
                self._frames = 0
                self._level = 0.0
                error = self._error
            if error:
                raise RuntimeError(error)
            if buffer is None or count == 0:
                return np.empty(0, dtype=np.float32)
            audio = buffer[:count].copy()
            if rate == SAMPLE_RATE:
                return audio
            try:
                return _resample(audio, rate)
            except Exception as exc:
                message = f"Could not convert microphone audio from {rate} Hz to 16 kHz: {exc}"
                with self._state:
                    self._error = message
                raise RuntimeError(message) from exc

    def cancel(self) -> None:
        """Stop and discard the recording without retaining or writing audio."""
        with self._control:
            shutdown_error = self._close_stream(discard=True)
            with self._state:
                self._buffer = None
                self._frames = 0
                self._level = 0.0
            if shutdown_error:
                raise RuntimeError(shutdown_error)


def _resample(audio: np.ndarray, rate: int) -> np.ndarray:
    """Use bundled FFmpeg's anti-aliased resampler; no system FFmpeg required."""
    resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    # One-second frames keep intermediate resampler allocations bounded.
    for offset in range(0, len(audio), rate):
        frame = av.AudioFrame.from_ndarray(audio[offset:offset + rate][None, :],
                                          format="flt", layout="mono")
        frame.sample_rate = rate
        for converted in resampler.resample(frame):
            chunks.append(converted.to_ndarray().reshape(-1))
    for converted in resampler.resample(None):
        chunks.append(converted.to_ndarray().reshape(-1))
    if not chunks:
        return np.empty(0, dtype=np.float32)
    return np.concatenate(chunks)[:SAMPLE_RATE * MAX_SECONDS].astype(np.float32, copy=False)
