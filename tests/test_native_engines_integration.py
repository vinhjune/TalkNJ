"""Opt-in native regressions using local catalog weights and the public JFK fixture.

Set TALKNJ_NATIVE_MODELS and TALKNJ_NATIVE_SPEECH (whisper.cpp samples/jfk.wav).
The tests never download models/audio or capture the microphone.
"""

from pathlib import Path
import os
import socket

import numpy as np
import pytest

from talknj.audio import MAX_SECONDS, SAMPLE_RATE
from talknj.transcription import Transcriber


@pytest.fixture
def native_assets(monkeypatch):
    root = os.environ.get("TALKNJ_NATIVE_MODELS")
    fixture = os.environ.get("TALKNJ_NATIVE_SPEECH")
    if not root or not fixture:
        pytest.skip("Set TALKNJ_NATIVE_MODELS and TALKNJ_NATIVE_SPEECH for local native regression checks")

    def blocked(*args, **kwargs):
        raise AssertionError("Native integration tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    from faster_whisper.audio import decode_audio

    speech = decode_audio(fixture, sampling_rate=SAMPLE_RATE)
    engine = Transcriber()
    try:
        yield engine, Path(root), speech
    finally:
        engine.close()


def test_parakeet_recognizes_speech_after_several_minutes_of_silence(native_assets):
    engine, models, speech = native_assets
    samples = np.zeros(MAX_SECONDS * SAMPLE_RATE, dtype=np.float32)
    samples[-len(speech):] = speech
    text = engine.transcribe(samples, models / "parakeet-tdt-0.6b-v2-int8", "en").casefold()
    assert "country" in text and "ask" in text, text


def test_whispercpp_reuses_live_worker_for_separate_memory_pcm_requests(native_assets):
    engine, models, speech = native_assets
    first = engine.transcribe(speech, models / "whisper.cpp-base", "en").casefold()
    assert "country" in first and "ask" in first, first
    worker = engine._model
    pid = worker._process.pid
    second = engine.transcribe(speech, models / "whisper.cpp-base", "en").casefold()
    assert "country" in second and "ask" in second, second
    assert engine._model is worker and worker._process.pid == pid and worker._process.is_alive()
