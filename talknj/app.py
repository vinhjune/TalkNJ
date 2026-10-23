"""Desktop orchestration. Blocking downloads, inference and delivery run off the UI thread."""

from pathlib import Path
import sys
import threading
import time

from PySide6.QtCore import (
    QLockFile, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMenu, QMessageBox, QSystemTrayIcon

from talknj.audio import AudioRecorder, list_input_devices
from talknj.models import CATALOG, discover_models, download_model, validate_model
from talknj.native import (
    HotkeyListener, copy_text, foreground_window, format_hotkey, type_text, validate_hotkey,
)
from talknj.settings import data_directory, load_settings, save_settings
from talknj.transcription import Transcriber
from talknj.ui import MainWindow, app_icon, countdown_text


class JobSignals(QObject):
    result = Signal(object)
    failed = Signal(str)
    done = Signal()


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = JobSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            self.signals.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.done.emit()


class Bridge(QObject):
    pressed = Signal(object)
    released = Signal(object)
    download_progress = Signal(int, int, str)


class Controller(QObject):
    def __init__(self, application: QApplication):
        super().__init__()
        self.application = application
        self.settings, warning = load_settings()
        self.window = MainWindow()
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.jobs = set()
        self.state = "idle"
        self.models = []
        self._scan_epoch = 0
        self.listener = None
        self._hotkey_epoch = 0
        self._choosing_hotkey = False
        self._hotkey_holding = False
        self.download_cancel = None
        self.quitting = False
        self.target = 0
        self.started = 0.0
        self.session = None
        self.bridge = Bridge(self)
        self.bridge.pressed.connect(self.hotkey_pressed)
        self.bridge.released.connect(self.hotkey_released)
        self.bridge.download_progress.connect(self.update_download)
        self.indicator = QLabel()
        self.indicator.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                                      Qt.WindowType.WindowStaysOnTopHint |
                                      Qt.WindowType.WindowDoesNotAcceptFocus |
                                      Qt.WindowType.WindowTransparentForInput)
        self.indicator.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator.setStyleSheet("background: #253053; color: white; border-radius: 14px; "
                                     "padding: 14px 24px; font: 14px 'Segoe UI';")
        self.indicator.setFixedSize(330, 54)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.tick)
        self.window.record_requested.connect(self.record_clicked)
        self.window.copy_requested.connect(self.copy_transcript)
        self.window.preferences_changed.connect(self.preferences_changed)
        self.window.choose_hotkey_requested.connect(self.choose_hotkey)
        self.window.model_changed.connect(self.select_model)
        self.window.download_requested.connect(self.start_download)
        self.window.cancel_download_requested.connect(self.cancel_download)
        self.window.import_requested.connect(self.import_model)
        self.window.storage_requested.connect(self.choose_storage)
        self.window.refresh_requested.connect(self.refresh)
        self.window.hide_requested.connect(self.hide_window)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("TalkNJ · Local dictation")
        menu = QMenu(self.window)
        show = menu.addAction("Open TalkNJ")
        show.triggered.connect(self.show_window)
        menu.addSeparator()
        self.hotkey_action = menu.addAction("")
        self.hotkey_action.setEnabled(False)
        self.push_to_talk_action = menu.addAction("Push to talk")
        self.push_to_talk_action.setCheckable(True)
        self.push_to_talk_action.triggered.connect(self.tray_push_to_talk)
        menu.addSeparator()
        quit_action = menu.addAction("Quit TalkNJ")
        quit_action.triggered.connect(self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.quit_action = QAction("Quit TalkNJ", self.window)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.request_quit)
        self.window.addAction(self.quit_action)
        self.populate_preferences()
        self.refresh()
        self.register_hotkey(self.settings.hotkey)
        if warning:
            self.window.show_notice(warning)
        self.window.show()

    def run_job(self, function, result, failure):
        job = Job(function)
        self.jobs.add(job)
        queued = Qt.ConnectionType.QueuedConnection
        job.signals.result.connect(result, queued)
        job.signals.failed.connect(failure, queued)
        job.signals.done.connect(lambda current=job: self.job_done(current), queued)
        self.pool.start(job)

    def job_done(self, job):
        self.jobs.discard(job)
        if self.quitting and not self.jobs:
            self.close_transcriber()
            self.application.quit()

    def close_transcriber(self):
        try:
            self.transcriber.close()
        except Exception as exc:
            message = f"Could not close the local speech engine: {exc}"
            self.window.show_notice(message)
            QMessageBox.warning(self.window, "Shutdown warning", message)

    def persist(self):
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.window.show_notice(f"Preferences could not be saved: {exc}")

    def populate_preferences(self):
        self.window.language.blockSignals(True)
        self.window.language.setCurrentIndex(max(0, self.window.language.findData(self.settings.language)))
        self.window.language.blockSignals(False)
        self.window.push_to_talk.blockSignals(True)
        holding = self.settings.hotkey_mode == "hold"
        self.window.push_to_talk.setChecked(holding)
        self.window.push_to_talk.blockSignals(False)
        try:
            self.window.set_hotkey(self.settings.hotkey)
        except (TypeError, ValueError):
            self.window.set_hotkey("")
        self.update_hints()

    def refresh(self):
        if self.quitting:
            return
        if self.state == "idle":
            self.refresh_microphones()
        self.update_state(self.state)
        self._scan_epoch += 1
        epoch = self._scan_epoch
        root = Path(self.settings.model_root)
        imported = tuple(self.settings.imported_models)
        self.window.model_detail.setText("Checking local models…")
        self.run_job(lambda: discover_models(root, imported),
                     lambda models: self.models_scanned(epoch, models),
                     lambda error: self.models_scanned(epoch, [], error))

    def models_scanned(self, epoch, models, error=""):
        if self.quitting or epoch != self._scan_epoch:
            return
        self.models = models
        if error:
            self.window.show_notice(f"Could not scan models: {error}")
        self.window.show_models(self.models, self.settings.model_path)
        selected = self.window.model.currentData() or ""
        self.settings.model_path = selected
        self.update_model_details()
        self.window.storage.setText(self.settings.model_root)
        self.update_state(self.state)

    def refresh_microphones(self):
        self.window.microphone.blockSignals(True)
        self.window.microphone.clear()
        self.window.microphone.addItem("System default microphone", None)
        try:
            for device, name in list_input_devices():
                self.window.microphone.addItem(name, device)
        except Exception as exc:
            self.window.show_notice(f"Microphone discovery failed: {exc}")
        saved_mic = self.settings.microphone
        matches = [i for i in range(1, self.window.microphone.count())
                   if self.window.microphone.itemText(i) == saved_mic]
        index = matches[0] if len(matches) == 1 else -1 if saved_mic else 0
        self.window.microphone.setCurrentIndex(index)
        if saved_mic and not matches:
            self.window.show_notice("Your selected microphone is unavailable. Select an input in Preferences before recording.")
        elif len(matches) > 1:
            self.window.show_notice("Multiple microphones have the saved device name. Select an input in Preferences before recording.")
        self.microphone_missing = bool(saved_mic and len(matches) != 1)
        self.window.microphone.blockSignals(False)

    def active_model(self):
        return next((m for m in self.models if str(m.path) == self.settings.model_path), None)

    def update_model_details(self):
        model = self.active_model()
        self.window.model_detail.setText(str(model.path) if model else "Download a speech model or choose a supported local model folder.")
        vi = self.window.language.model().item(1)
        vi.setEnabled(bool(model and "vi" in model.languages))
        if model and self.settings.language not in model.languages:
            self.settings.language = "en"
            self.populate_preferences()
            self.window.show_notice("This model does not support the selected language. Language switched to English; choose a Vietnamese-capable model for Vietnamese.")
        self.update_hints()

    @Slot(int)
    def select_model(self, index):
        if self.state != "idle":
            return
        self.settings.model_path = self.window.model.currentData() or ""
        self.update_model_details()
        self.persist()
        self.update_state("idle")

    @Slot()
    def preferences_changed(self):
        if self.state != "idle":
            return
        self.settings.language = self.window.language.currentData() or "en"
        self.settings.hotkey_mode = "hold" if self.window.push_to_talk.isChecked() else "toggle"
        if self.window.microphone.currentIndex() >= 0:
            self.settings.microphone = (self.window.microphone.currentText()
                                        if self.window.microphone.currentData() is not None else None)
            self.microphone_missing = False
        self.update_hints()
        self.persist()

    def update_hints(self):
        holding = self.settings.hotkey_mode == "hold"
        gesture = "Hold" if holding else "Press"
        try:
            shortcut = format_hotkey(self.settings.hotkey)
        except (TypeError, ValueError):
            shortcut = "a configured shortcut"
        self.window.capture_hint.setText(
            f"{gesture} {shortcut} anywhere, or use the recording button. Five-minute limit.")
        self.hotkey_action.setText(f"Hotkey: {shortcut} ({'hold' if holding else 'press'})")
        self.push_to_talk_action.setChecked(holding)

    def register_hotkey(self, chord):
        listener = None
        try:
            canonical = validate_hotkey(chord)
            listener = HotkeyListener(
                canonical,
                lambda: self.bridge.pressed.emit((listener, self._hotkey_epoch, foreground_window())),
                lambda: self.bridge.released.emit((listener, self._hotkey_epoch)),
            )
            # A candidate never fires while the OS is checking/installing it.
            listener.suspend()
            listener.start()
        except Exception as exc:
            cleanup_warning = ""
            if listener is not None:
                try:
                    listener.stop()
                except RuntimeError as cleanup_error:
                    cleanup_warning = f" Candidate cleanup reported: {cleanup_error}"
            retained = (f" {format_hotkey(self.listener.chord)} is still active."
                        if self.listener else " The recording button still works.")
            self.window.hotkey_status.setText(f"Shortcut unavailable: {exc}.{retained}{cleanup_warning}")
            self.window.hotkey_status.show()
            self.window.show_notice(f"Global shortcut could not start: {exc}.{retained}{cleanup_warning}")
            return False
        old = self.listener
        if old:
            old.suspend()
        self._hotkey_epoch += 1
        self._hotkey_holding = False
        self.listener = listener
        cleanup_warning = ""
        if old:
            try:
                old.stop()
            except RuntimeError as exc:
                cleanup_warning = f" Previous listener cleanup reported: {exc}"
        listener.resume()
        self.settings.hotkey = canonical
        quit_chord = "win+q" if sys.platform == "darwin" else "ctrl+q"
        self.quit_action.setShortcut("" if canonical == quit_chord else "Ctrl+Q")
        self.window.set_hotkey(canonical)
        self.window.hotkey_status.setText(cleanup_warning.strip())
        self.window.hotkey_status.setVisible(bool(cleanup_warning))
        self.update_hints()
        return True

    @Slot()
    def choose_hotkey(self):
        if self.state != "idle" or self.quitting or self._choosing_hotkey:
            return
        self._choosing_hotkey = True
        self._hotkey_epoch += 1
        self._hotkey_holding = False
        listener = self.listener
        if listener:
            listener.suspend()
        try:
            chord = self.window.capture_hotkey()
            if chord and self.register_hotkey(chord):
                self.window.show_notice("")
                self.persist()
        except Exception as exc:
            self.window.show_notice(f"Could not choose a shortcut: {exc}")
        finally:
            self._hotkey_epoch += 1
            if listener and listener is self.listener and not self.quitting:
                listener.resume()
            self._choosing_hotkey = False


    @Slot(object)
    def hotkey_pressed(self, event):
        source, epoch, target = event
        if (self.quitting or self._choosing_hotkey or source is not self.listener
                or epoch != self._hotkey_epoch):
            return
        if self.state == "idle":
            self.start_recording(target)
            self._hotkey_holding = self.state == "recording" and self.settings.hotkey_mode == "hold"
        elif self.state == "recording" and self.settings.hotkey_mode == "toggle":
            self.stop_recording()

    @Slot(object)
    def hotkey_released(self, event):
        source, epoch = event
        if (self.quitting or self._choosing_hotkey or source is not self.listener
                or epoch != self._hotkey_epoch):
            return
        if self._hotkey_holding:
            self._hotkey_holding = False
            if self.state == "recording" and self.settings.hotkey_mode == "hold":
                self.stop_recording()

    @Slot()
    def record_clicked(self):
        if self.state == "recording":
            self.stop_recording()
        elif self.state == "idle":
            # Clicking the app itself is a preview workflow, not a request to type elsewhere.
            self.start_recording(0)

    def update_state(self, state):
        self.state = state
        self.window.set_busy(state, self.active_model() is not None)
        self.tray.setToolTip(f"TalkNJ · {state.capitalize()} · {self.window.hotkey.text()}")
        self.push_to_talk_action.setEnabled(state == "idle")
        if state == "recording":
            self.update_countdown()
        if state == "idle":
            self.indicator.hide()
        elif not self.window.isActiveWindow():
            screen = self.application.primaryScreen().availableGeometry()
            self.indicator.move(screen.center().x() - 165, screen.bottom() - 90)
            if state != "recording":
                self.indicator.setText(f"{state.capitalize()} locally…")
            self.indicator.show()

    def start_recording(self, target):
        model = self.active_model()
        if not model:
            self.window.show_notice("Download or select a model in Preferences before recording.")
            self.tray.showMessage("TalkNJ needs a model", "Open Preferences and download a local speech model.")
            return
        if self.microphone_missing:
            self.window.show_notice("Select an available microphone in Preferences before recording.")
            return
        self.window.show_notice("")
        try:
            self.recorder.start(self.window.microphone.currentData())
        except Exception as exc:
            self.window.show_notice(f"Could not start microphone: {exc}")
            self.tray.showMessage("Microphone unavailable", str(exc))
            return
        self.target = target
        self.session = (Path(model.path), self.settings.language, target)
        self.started = time.monotonic()
        self.update_state("recording")
        self.timer.start()

    def update_countdown(self):
        remaining = countdown_text(time.monotonic() - self.started)
        self.window.elapsed.setText(f"{remaining} remaining")
        self.indicator.setText(f"Listening · {remaining} remaining")

    @Slot()
    def tick(self):
        if self.state != "recording":
            return
        self.update_countdown()
        self.window.level.setValue(int(self.recorder.level * 100))
        if self.recorder.error or self.recorder.limit_reached:
            self.stop_recording()

    def stop_recording(self):
        self._hotkey_holding = False
        self.timer.stop()
        try:
            audio = self.recorder.stop()
        except Exception as exc:
            self.operation_failed(f"Recording failed: {exc}")
            return
        model, language, target = self.session
        self.update_state("transcribing")
        self.run_job(lambda: self.transcriber.transcribe(audio, model, language),
                     lambda text: self.transcribed(text, target), self.operation_failed)

    def transcribed(self, text, target):
        if self.quitting:
            return
        if not text.strip():
            self.window.result.setText("No speech detected. Nothing was copied or typed.")
            self.update_state("idle")
            return
        self.window.transcript.setPlainText(text)
        self.update_state("delivering")

        def deliver():
            copy_text(text)
            if target:
                try:
                    type_text(target, text)
                except Exception as exc:
                    return f"Text copied, but not fully typed: {exc} Recover the complete text from the clipboard."
                return "Typed into the original application. A copy is also on the clipboard."
            return "Preview recording: copied to clipboard. Use the global hotkey from another app for automatic typing."

        self.run_job(deliver, self.delivered, self.operation_failed)

    def delivered(self, message):
        self.window.result.setText(message)
        if "not fully typed" in message:
            self.window.show_notice(message)
            self.tray.showMessage("Transcript kept in clipboard", message)
        self.update_state("idle")

    def operation_failed(self, message):
        self.window.show_notice(message)
        self.window.result.setText("Your latest transcript is still available. Recording audio is not saved.")
        self.update_state("idle")
        if not self.window.isVisible():
            self.tray.showMessage("TalkNJ", message)

    @Slot()
    def copy_transcript(self):
        text = self.window.transcript.toPlainText()
        if not text:
            return
        try:
            copy_text(text)
            self.window.result.setText("Edited transcript copied to clipboard.")
        except Exception as exc:
            self.window.show_notice(f"Could not copy transcript: {exc}")

    @Slot(str)
    def start_download(self, model_id):
        if self.download_cancel is not None or self.quitting:
            return
        spec = next(s for s in CATALOG if s.id == model_id)
        root = Path(self.settings.model_root)
        cancel = threading.Event()
        self.download_cancel = cancel
        self.window.set_download_busy(True)
        self.window.download_status.setText(f"Starting {spec.name} download…")
        self.window.download_progress.setRange(0, 0)
        self.run_job(lambda: download_model(spec, root, self.bridge.download_progress.emit, cancel),
                     self.download_finished, self.download_failed)

    @Slot(int, int, str)
    def update_download(self, done, total, filename):
        if total:
            self.window.download_progress.setRange(0, 100)
            self.window.download_progress.setValue(min(100, int(done * 100 / total)))
        else:
            self.window.download_progress.setRange(0, 0)
        self.window.download_status.setText(f"{filename} · {done / 1_000_000:.1f} MB" +
                                            (f" / {total / 1_000_000:.1f} MB" if total else ""))

    def end_download(self):
        self.download_cancel = None
        self.window.set_download_busy(False)

    def download_finished(self, path):
        self.end_download()
        self.window.download_status.setText(f"Ready offline: {Path(path).name}")
        if self.state == "idle":
            self.settings.model_path = str(Path(path).resolve())
            self.refresh()
            self.persist()
        else:
            self.window.download_status.setText("Download complete. Click Refresh when dictation finishes to select it.")

    def download_failed(self, message):
        self.end_download()
        self.window.download_status.setText(message)
        if not self.quitting:
            self.window.show_notice(f"Model download: {message}")

    @Slot()
    def cancel_download(self):
        if self.download_cancel is not None:
            self.download_cancel.set()
            self.window.cancel_download.setEnabled(False)
            self.window.download_status.setText("Cancelling download…")

    @Slot()
    def choose_storage(self):
        if self.download_cancel is not None or self.state != "idle" or self.quitting:
            return
        path = QFileDialog.getExistingDirectory(self.window, "Choose model download folder", self.settings.model_root)
        if path:
            # Keep references to installed models when moving the download destination.
            self.settings.imported_models = list(dict.fromkeys(
                self.settings.imported_models + [str(m.path) for m in self.models]))
            self.settings.model_root = path
            self.refresh()
            self.persist()

    @Slot()
    def import_model(self):
        if self.state != "idle" or self.quitting:
            return
        path = QFileDialog.getExistingDirectory(self.window, "Select a supported speech model folder")
        if not path:
            return
        self.run_job(lambda: validate_model(Path(path)), self.model_imported,
                     lambda error: self.window.show_notice(f"Cannot use this model: {error}"))

    def model_imported(self, model):
        if self.quitting:
            return
        self.settings.imported_models = list(dict.fromkeys(self.settings.imported_models + [str(model.path)]))
        self.settings.model_path = str(model.path)
        self.refresh()
        self.persist()

    @Slot()
    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_window()

    @Slot(bool)
    def tray_push_to_talk(self, checked):
        self.window.push_to_talk.setChecked(checked)

    @Slot()
    def hide_window(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.window.hide()
        else:
            self.window.showMinimized()

    @Slot()
    def request_quit(self):
        if self.quitting:
            return
        if self.state == "recording":
            answer = QMessageBox.question(self.window, "Discard current recording?",
                                          "Quitting discards the current recording without transcribing it.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.quitting = True
        self.timer.stop()
        cleanup_errors = []
        try:
            self.recorder.cancel()
        except RuntimeError as exc:
            cleanup_errors.append(str(exc))
        if self.listener:
            try:
                self.listener.stop()
            except RuntimeError as exc:
                cleanup_errors.append(str(exc))
        if cleanup_errors:
            QMessageBox.warning(self.window, "Shutdown warning", "\n".join(cleanup_errors))
        self.cancel_download()
        self.indicator.hide()
        self.tray.hide()
        if self.jobs:
            # Keep the event loop alive until in-flight native inference releases resources.
            self.window.show_notice("Finishing the current local operation before quitting…")
            self.window.setEnabled(False)
            self.window.show()
        else:
            self.close_transcriber()
            self.window.allow_close = True
            self.window.close()
            self.application.quit()


def main() -> int:
    if sys.platform not in ("win32", "darwin"):
        print("TalkNJ requires Windows or macOS.", file=sys.stderr)
        return 1
    application = QApplication(sys.argv)
    application.setApplicationName("TalkNJ")
    application.setOrganizationName("TalkNJ")
    application.setWindowIcon(app_icon())
    application.setQuitOnLastWindowClosed(False)
    data_directory().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_directory() / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "TalkNJ is already running", "Open TalkNJ using its tray or menu-bar icon.")
        return 0
    controller = Controller(application)

    def report_exception(kind, value, traceback):
        sys.__excepthook__(kind, value, traceback)
        controller.window.show_notice(f"Unexpected error: {value}")

    sys.excepthook = report_exception
    try:
        return application.exec()
    finally:
        controller.timer.stop()
        try:
            controller.recorder.cancel()
        finally:
            try:
                if controller.listener:
                    controller.listener.stop()
            finally:
                try:
                    controller.pool.waitForDone()
                    controller.close_transcriber()
                finally:
                    lock.unlock()
