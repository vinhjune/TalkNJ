"""User-visible device selection remains stable when PortAudio reorders indices."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from talknj import app as desktop
from talknj.settings import Settings


@pytest.fixture
def controller(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    preferences = Settings(model_root=str(tmp_path / "models"), microphone="Chosen mic [WASAPI]")
    monkeypatch.setattr(desktop, "load_settings", lambda: (preferences, ""))
    monkeypatch.setattr(desktop.Controller, "register_hotkey", lambda *args: False)
    devices = [(5, "Other mic [WASAPI]"), (19, "Chosen mic [WASAPI]")]
    monkeypatch.setattr(desktop, "list_input_devices", lambda: devices)
    current = desktop.Controller(application)
    current.pool.waitForDone()
    application.processEvents()
    yield current, devices
    current.pool.waitForDone()
    application.processEvents()
    current.request_quit()
    application.processEvents()


def test_saved_device_follows_identity_after_index_reordering(controller):
    current, devices = controller
    assert current.window.microphone.currentData() == 19
    devices[:] = [(19, "Other mic [WASAPI]"), (2, "Chosen mic [WASAPI]")]
    current.refresh()
    assert current.window.microphone.currentData() == 2
    assert current.settings.microphone == "Chosen mic [WASAPI]"


def test_missing_device_requires_explicit_reselection_even_after_other_preferences_change(controller):
    current, devices = controller
    devices[:] = [(19, "Other mic [WASAPI]")]
    current.refresh()
    assert current.microphone_missing
    assert current.window.microphone.currentIndex() == -1
    current.window.output.setCurrentIndex(current.window.output.findData("type"))
    assert current.microphone_missing
    assert current.settings.microphone == "Chosen mic [WASAPI]"
    current.window.microphone.setCurrentIndex(0)
    assert not current.microphone_missing
    assert current.settings.microphone is None
