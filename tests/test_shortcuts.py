"""Shortcut selection and controller behavior without real global hooks or audio."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from talknj import app as desktop
from talknj.settings import load_settings
from talknj.ui import MainWindow, ShortcutDialog


class FakeListener:
    fail_start = False
    instances = []

    def __init__(self, chord, on_press, on_release):
        self.chord = chord
        self.on_press = on_press
        self.on_release = on_release
        self.suspended = False
        self.stopped = False
        self.transitions = []
        self.instances.append(self)

    def suspend(self):
        self.suspended = True
        self.transitions.append("suspend")

    def resume(self):
        self.suspended = False
        self.transitions.append("resume")

    def start(self):
        assert self.suspended
        self.transitions.append("start")
        if self.fail_start:
            raise RuntimeError("Windows reserved this shortcut")

    def stop(self):
        self.stopped = True
        self.transitions.append("stop")
        # The real listener can release an active gesture during shutdown.
        self.on_release()


@pytest.fixture
def application():
    current = QApplication.instance() or QApplication([])
    current.setQuitOnLastWindowClosed(False)
    return current


@pytest.fixture
def controller(application, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(FakeListener, "instances", [])
    monkeypatch.setattr(FakeListener, "fail_start", False)
    monkeypatch.setattr(desktop, "HotkeyListener", FakeListener)
    monkeypatch.setattr(desktop, "foreground_window", lambda: 0xBEEF)
    monkeypatch.setattr(desktop, "list_input_devices", lambda: [])
    current = desktop.Controller(application)
    current.pool.waitForDone()
    application.processEvents()
    yield current
    current.pool.waitForDone()
    application.processEvents()
    current.state = "idle"
    current.request_quit()
    application.processEvents()


def send_key(dialog, key, modifiers=Qt.KeyboardModifier.NoModifier, *, release=False, repeat=False):
    kind = QEvent.Type.KeyRelease if release else QEvent.Type.KeyPress
    event = QKeyEvent(kind, key, modifiers, "", repeat)
    assert dialog.eventFilter(dialog, event)


def enter_ctrl_space(dialog):
    send_key(dialog, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
    send_key(dialog, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    send_key(dialog, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier, release=True)
    send_key(dialog, Qt.Key.Key_Control, release=True)


def test_keys_capture_friendly_chord_and_require_full_release(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)
    send_key(dialog, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
    send_key(dialog, Qt.Key.Key_Alt, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    send_key(dialog, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert dialog.chord == "ctrl+alt+space"
    assert dialog.preview.text() == "Ctrl + Alt + Space"
    assert not dialog.use_shortcut.isEnabled()
    send_key(dialog, Qt.Key.Key_Space, release=True)
    send_key(dialog, Qt.Key.Key_Control, release=True)
    assert not dialog.use_shortcut.isEnabled()
    send_key(dialog, Qt.Key.Key_Alt, release=True)
    assert dialog.use_shortcut.isEnabled()
    parent.close()


def test_native_virtual_key_matches_global_hook_on_non_us_layout(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier, 0, 0x41, 0)
    assert dialog.eventFilter(dialog, event)
    assert dialog.chord == "ctrl+a"
    parent.close()


@pytest.mark.parametrize("key, modifiers, message", [
    (Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier, "Modifiers alone"),
    (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "at least one"),
    (Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier, "F1–F12"),
    (Qt.Key.Key_AltGr, Qt.KeyboardModifier.GroupSwitchModifier, "AltGr"),
])
def test_invalid_choices_are_explained_after_release(application, key, modifiers, message):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)
    send_key(dialog, key, modifiers)
    send_key(dialog, key, release=True)
    assert not dialog.chord
    assert not dialog.use_shortcut.isEnabled()
    assert message in dialog.feedback.text()
    parent.close()


def test_multiple_trigger_keys_rejected_and_new_gesture_can_recover(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)
    send_key(dialog, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    send_key(dialog, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    assert not dialog.chord
    assert "exactly one" in dialog.feedback.text()
    send_key(dialog, Qt.Key.Key_A, release=True)
    send_key(dialog, Qt.Key.Key_B, release=True)
    enter_ctrl_space(dialog)
    assert dialog.chord == "ctrl+space"
    assert dialog.use_shortcut.isEnabled()
    parent.close()


def test_escape_cancels_even_after_valid_choice(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)
    enter_ctrl_space(dialog)
    dialog.setResult(QDialog.DialogCode.Accepted)
    send_key(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected
    parent.close()


def test_capture_filters_qt_actions(application):
    parent = MainWindow()
    action = QAction("Quit", parent)
    action.setShortcut("Ctrl+Q")
    invoked = Mock()
    action.triggered.connect(invoked)
    parent.addAction(action)
    dialog = ShortcutDialog(parent)

    def select():
        for kind, key, modifiers in (
            (QEvent.Type.ShortcutOverride, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier),
            (QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier),
            (QEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier),
            (QEvent.Type.KeyRelease, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier),
            (QEvent.Type.KeyRelease, Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier),
        ):
            QApplication.sendEvent(dialog, QKeyEvent(kind, key, modifiers))
        dialog.use_shortcut.click()

    QTimer.singleShot(0, select)
    QTimer.singleShot(1000, dialog.reject)
    assert dialog.capture() == "ctrl+q"
    invoked.assert_not_called()
    parent.close()


def test_startup_registers_saved_chord(controller):
    assert controller.listener.chord == controller.settings.hotkey
    assert controller.listener.transitions == ["suspend", "start", "resume"]
    assert controller.window.hotkey.text() == "Ctrl + Alt + Space"


def test_capture_suspends_bound_chord_and_invalidates_queued_events(controller, monkeypatch):
    original = controller.listener
    epoch = controller._hotkey_epoch
    controller.start_recording = Mock()

    def capture():
        assert original.suspended
        original.on_press()
        controller.hotkey_pressed((original, epoch, 0xBEEF))
        return "ctrl+space"

    monkeypatch.setattr(controller.window, "capture_hotkey", capture)
    controller.choose_hotkey()
    controller.start_recording.assert_not_called()
    assert not original.suspended
    assert controller.listener is original
    assert controller.settings.hotkey == "ctrl+alt+space"
    assert controller.window.hotkey_chord == "ctrl+space"
    assert controller.window.apply_hotkey.isEnabled()
    controller.hotkey_pressed((original, epoch, 0xBEEF))
    controller.start_recording.assert_not_called()


def test_cancel_restores_listener_and_preserves_previous_selection(controller, monkeypatch):
    original = controller.listener
    monkeypatch.setattr(controller.window, "capture_hotkey", lambda: None)
    controller.choose_hotkey()
    assert not original.suspended
    assert controller.window.hotkey_chord == "ctrl+alt+space"
    assert not controller.window.apply_hotkey.isEnabled()
    assert controller.settings.hotkey == "ctrl+alt+space"


def test_dialog_failure_resumes_previous_listener(controller, monkeypatch):
    original = controller.listener
    monkeypatch.setattr(controller.window, "capture_hotkey", Mock(side_effect=RuntimeError("capture failed")))
    controller.choose_hotkey()
    assert not original.suspended
    assert not controller._choosing_hotkey
    assert "capture failed" in controller.window.notice.text()


def test_failed_registration_retains_working_shortcut_and_saved_preferences(controller, monkeypatch):
    controller.persist()
    original = controller.listener
    controller.window.set_hotkey("ctrl+space", pending=True)
    monkeypatch.setattr(FakeListener, "fail_start", True)
    controller.apply_hotkey()
    assert controller.listener is original
    assert not original.stopped
    assert not original.suspended
    assert FakeListener.instances[-1].stopped
    assert controller.settings.hotkey == "ctrl+alt+space"
    assert load_settings()[0].hotkey == "ctrl+alt+space"
    assert controller.window.apply_hotkey.isEnabled()
    assert "still active" in controller.window.hotkey_status.text()
    assert "Windows reserved" in controller.window.notice.text()
    controller.start_recording = Mock()
    original.on_press()
    controller.start_recording.assert_called_once_with(0xBEEF)


def test_successful_replacement_saves_and_reloads_without_stale_release(controller):
    original = controller.listener
    controller.stop_recording = Mock()
    controller.window.set_hotkey("ctrl+shift+f2", pending=True)
    controller.apply_hotkey()
    assert original.stopped
    assert controller.listener is not original
    assert controller.settings.hotkey == "ctrl+shift+f2"
    assert load_settings()[0].hotkey == "ctrl+shift+f2"
    assert not controller.window.apply_hotkey.isEnabled()
    controller.stop_recording.assert_not_called()
    assert controller.register_hotkey(load_settings()[0].hotkey)
    assert controller.listener.chord == "ctrl+shift+f2"


@pytest.mark.parametrize("mode", ["hold", "toggle"])
def test_global_callbacks_target_foreground_application_in_both_modes(controller, mode):
    controller.settings.hotkey_mode = mode
    starts, stops = [], []

    def start(target):
        starts.append(target)
        controller.state = "recording"

    def stop():
        stops.append(True)
        controller.state = "idle"

    controller.start_recording = start
    controller.stop_recording = stop
    controller.listener.on_press()
    assert starts == [0xBEEF]
    controller.listener.on_release()
    if mode == "toggle":
        assert controller.state == "recording"
        assert not stops
        controller.listener.on_press()
    assert stops == [True]
    assert controller.state == "idle"


def test_release_does_not_stop_button_started_recording_or_replaced_listener(controller):
    controller.state = "recording"
    controller.stop_recording = Mock()
    controller.listener.on_release()
    controller.hotkey_released((object(), controller._hotkey_epoch))
    controller.stop_recording.assert_not_called()


def test_unsupported_persisted_chord_does_not_crash_preferences(controller):
    controller.settings.hotkey = "not+a+supported+shortcut"
    controller.populate_preferences()
    assert controller.window.hotkey.text() == "Choose a shortcut"
    assert not controller.register_hotkey(controller.settings.hotkey)
    assert "still active" in controller.window.hotkey_status.text()


def test_mode_change_is_persisted_with_shortcut(controller):
    controller.window.hotkey_mode.setCurrentIndex(controller.window.hotkey_mode.findData("toggle"))
    saved, warning = load_settings()
    assert not warning
    assert saved.hotkey_mode == "toggle"
    assert saved.hotkey == controller.listener.chord


def test_shutdown_closes_backend_only_after_jobs_drain(controller):
    first, second = object(), object()
    controller.jobs.update((first, second))
    controller.quitting = True
    controller.transcriber.close = Mock()
    controller.job_done(first)
    controller.transcriber.close.assert_not_called()
    controller.job_done(second)
    controller.transcriber.close.assert_called_once_with()
    controller.quitting = False


def test_shutdown_surfaces_backend_cleanup_failure(controller, monkeypatch):
    controller.transcriber.close = Mock(side_effect=RuntimeError("worker did not stop"))
    warning = Mock()
    monkeypatch.setattr(desktop.QMessageBox, "warning", warning)
    controller.close_transcriber()
    warning.assert_called_once()
    assert "worker did not stop" in controller.window.notice.text()
    controller.transcriber.close = Mock()


def test_confirmed_shortcut_survives_window_deactivation_while_closing(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)

    def confirm():
        enter_ctrl_space(dialog)
        dialog.use_shortcut.click()
        QApplication.sendEvent(dialog, QEvent(QEvent.Type.WindowDeactivate))

    QTimer.singleShot(0, confirm)
    QTimer.singleShot(1000, dialog.reject)
    assert dialog.capture() == "ctrl+space"
    parent.close()


def test_both_control_keys_must_be_released_before_accepting_shortcut(application):
    parent = MainWindow()
    dialog = ShortcutDialog(parent)

    def control(scan, release=False):
        kind = QEvent.Type.KeyRelease if release else QEvent.Type.KeyPress
        event = QKeyEvent(kind, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier,
                          scan, 0x11, 0)
        assert dialog.eventFilter(dialog, event)

    control(0x1D)
    control(0xE01D)
    send_key(dialog, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    send_key(dialog, Qt.Key.Key_Space, release=True)
    control(0x1D, release=True)
    assert not dialog.use_shortcut.isEnabled()
    control(0xE01D, release=True)
    assert dialog.use_shortcut.isEnabled()
    parent.close()


def test_recording_shortcut_does_not_invoke_application_quit(controller, application):
    assert controller.register_hotkey("ctrl+q")
    controller.window.activateWindow()
    application.processEvents()
    QTest.keyClick(controller.window, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    application.processEvents()
    assert not controller.quitting
    assert controller.register_hotkey("ctrl+alt+f9")
    QTest.keyClick(controller.window, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    application.processEvents()
    assert controller.quitting


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_stale_model_scan_cannot_replace_selection_or_end_recording(
    controller, monkeypatch, tmp_path, outcome,
):
    from talknj.models import InstalledModel

    pending = []
    monkeypatch.setattr(controller, "run_job", lambda function, result, failure:
                        pending.append((result, failure)))
    old = InstalledModel(tmp_path / "old", "Old", ("en",))
    latest = InstalledModel(tmp_path / "latest", "Latest", ("en", "vi"))
    controller.refresh()
    controller.refresh()
    controller.settings.model_path = str(latest.path)
    controller.update_state("recording")
    pending[1][0]([latest])
    if outcome == "success":
        pending[0][0]([old])
    else:
        pending[0][1]("Storage disconnected")
    assert controller.active_model() == latest
    assert controller.window.model.currentData() == str(latest.path)
    assert controller.state == "recording"
    assert "Storage disconnected" not in controller.window.notice.text()
