"""Qt widgets only; recording, inference and OS integration live outside the view."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from talknj.models import CATALOG
from talknj.native import format_hotkey, validate_hotkey


STYLE = """
QWidget { background: #f5f6f8; color: #202839; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow { background: #f5f6f8; }
QFrame#sidebar { background: #ffffff; border-right: 1px solid #e3e6ed; }
QFrame#card { background: #ffffff; border: 1px solid #e0e5ed; border-radius: 14px; }
QLabel { background: transparent; }
QLabel#title { font-size: 29px; font-weight: 700; color: #172137; }
QLabel#section { font-size: 17px; font-weight: 600; }
QLabel#muted { color: #69748a; }
QLabel#eyebrow { color: #5365bd; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QLabel#status { color: #32694e; background: #edf7f0; border-radius: 9px; padding: 6px 12px; }
QLabel#notice { color: #7a4a16; background: #fff2d9; border-radius: 8px; padding: 10px; }
QPushButton { background: #ffffff; border: 1px solid #d8dfeb; border-radius: 8px;
    padding: 9px 15px; font-weight: 600; }
QPushButton:hover { background: #edf0fb; border-color: #a5afe0; }
QPushButton:disabled { color: #9ba4b5; background: #f3f4f7; border-color: #e2e6ed; }
QPushButton#primary { background: #4c5fd5; color: white; border: none; padding: 13px 22px; }
QPushButton#primary:hover { background: #3d4fbd; }
QPushButton#primary:disabled { background: #c1c7e7; color: #f7f8ff; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px 16px; }
QPushButton#nav:checked { color: #3e50bc; background: #edf0ff; }
QComboBox, QLineEdit { background: #ffffff; border: 1px solid #d8dfeb; border-radius: 7px;
    padding: 9px; min-height: 20px; selection-background-color: #4c5fd5; }
QComboBox:disabled, QLineEdit:disabled { color: #9ba4b5; }
QComboBox QAbstractItemView { background: white; selection-background-color: #edf0ff;
    selection-color: #202839; padding: 4px; }
QPlainTextEdit { background: #ffffff; border: 1px solid #e0e5ed; border-radius: 10px;
    padding: 14px; font-size: 16px; selection-background-color: #cbd3ff; }
QProgressBar { border: none; background: #e8ecf4; border-radius: 4px; min-height: 7px;
    max-height: 7px; text-align: center; }
QProgressBar::chunk { background: #6f7ee4; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QToolTip { background: #202839; color: #ffffff; border: none; padding: 6px; }
"""


def app_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#4c5fd5"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 64, 64, 17, 17)
    painter.setBrush(QColor("#ffffff"))
    for x, y, h in ((16, 24, 16), (26, 15, 34), (36, 21, 22), (46, 27, 10)):
        painter.drawRoundedRect(x, y, 5, h, 2.5, 2.5)
    painter.end()
    return QIcon(pix)


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return frame, layout


class ShortcutDialog(QDialog):
    """Consume shortcut events before Qt actions can handle a captured chord."""

    _MODIFIER_KEYS = {
        Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta,
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Choose global shortcut")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.chord = ""
        self._down: set[tuple[int, int, int]] = set()
        self._capturing = True
        layout = QVBoxLayout(self)
        layout.addWidget(label("Press your shortcut", "section"))
        layout.addWidget(label(
            "Hold Ctrl, Alt, Shift or Win, then press a letter, number, Space or F1–F12. "
            "Release all keys, then choose Use shortcut. Escape cancels.", "muted", True))
        self.preview = label("Waiting for keys…", "section")
        layout.addWidget(self.preview)
        self.feedback = label("Your current global shortcut is paused while this dialog is open.", "muted", True)
        layout.addWidget(self.feedback)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.use_shortcut = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.use_shortcut.setText("Use shortcut")
        self.use_shortcut.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def done(self, result: int) -> None:
        # Hiding an accepted dialog can deactivate it before exec() returns.
        self._capturing = False
        super().done(result)

    def eventFilter(self, watched, event) -> bool:
        kind = event.type()
        if watched is self and kind == QEvent.Type.WindowDeactivate and self._capturing:
            self.reject()
        if kind == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if not isinstance(event, QKeyEvent):
            return False
        if event.isAutoRepeat():
            return True
        key = event.key()
        physical_key = (key, event.nativeScanCode(), event.nativeVirtualKey())
        if kind == QEvent.Type.KeyRelease:
            self._down.discard(physical_key)
            if not self._down:
                self.use_shortcut.setEnabled(bool(self.chord))
                if self.chord:
                    self.feedback.setText(
                        "Choose Use shortcut, or press a different chord. It is not active until you apply it.")
                elif self.preview.text() == "Waiting for keys…":
                    self.feedback.setText(
                        "Modifiers alone are not a shortcut. Add a letter, number, Space or F1–F12.")
            return True
        if key == Qt.Key.Key_Escape:
            self.reject()
            return True
        if not self._down:
            self.chord = ""
            self.preview.setText("Waiting for keys…")
        self._down.add(physical_key)
        self.use_shortcut.setEnabled(False)
        if key in self._MODIFIER_KEYS:
            return True
        self.chord = ""
        modifiers = event.modifiers()
        names = [name for mask, name in (
            (Qt.KeyboardModifier.ControlModifier, "ctrl"),
            (Qt.KeyboardModifier.AltModifier, "alt"),
            (Qt.KeyboardModifier.ShiftModifier, "shift"),
            (Qt.KeyboardModifier.MetaModifier, "win"),
        ) if modifiers & mask]
        # Native virtual keys match the global hook even on non-US layouts.
        # Qt-created events have no native code; use logical keys for those.
        vk = event.nativeVirtualKey()
        trigger = ""
        if vk:
            if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
                trigger = chr(vk).lower()
            elif vk == 0x20:
                trigger = "space"
            elif 0x70 <= vk <= 0x7B:
                trigger = f"f{vk - 0x6F}"
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            trigger = chr(key).lower()
        elif key == Qt.Key.Key_Space:
            trigger = "space"
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            trigger = f"f{key - Qt.Key.Key_F1 + 1}"
        try:
            if modifiers & Qt.KeyboardModifier.GroupSwitchModifier or key == Qt.Key.Key_AltGr:
                raise ValueError("AltGr is not supported. Use Ctrl, Alt, Shift or Win instead.")
            if sum(held[0] not in self._MODIFIER_KEYS for held in self._down) != 1:
                raise ValueError("Choose exactly one letter, number, Space or F1–F12 with your modifiers.")
            if not names or not trigger:
                raise ValueError(
                    "Use at least one of Ctrl, Alt, Shift or Win with a letter, number, Space or F1–F12.")
            self.chord = validate_hotkey("+".join([*names, trigger]))
        except ValueError as exc:
            self.preview.setText("Unsupported shortcut")
            self.feedback.setText(str(exc))
        else:
            self.preview.setText(format_hotkey(self.chord))
            self.feedback.setText("Release all keys to use this shortcut.")
        return True

    def capture(self) -> str | None:
        application = QApplication.instance()
        application.installEventFilter(self)
        try:
            return self.chord if self.exec() == QDialog.DialogCode.Accepted and self.chord else None
        finally:
            application.removeEventFilter(self)


class MainWindow(QMainWindow):
    record_requested = Signal()
    copy_requested = Signal()
    download_requested = Signal(str)
    cancel_download_requested = Signal()
    import_requested = Signal()
    storage_requested = Signal()
    refresh_requested = Signal()
    preferences_changed = Signal()
    hotkey_requested = Signal()
    choose_hotkey_requested = Signal()
    model_changed = Signal(int)
    hide_requested = Signal()

    def __init__(self):
        super().__init__()
        self.allow_close = False
        self.setWindowTitle("TalkNJ — local voice dictation")
        self.setWindowIcon(app_icon())
        self.resize(1050, 810)
        self.setMinimumSize(880, 700)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 30, 18, 22)
        brand = label("TalkNJ", "title")
        side.addWidget(brand)
        side.addWidget(label("LOCAL VOICE\nDICTATION", "eyebrow"))
        side.addSpacing(35)
        self.pages = QStackedWidget()
        self.nav = []
        for index, title in enumerate(("Dictation", "Model library", "Preferences")):
            button = QPushButton(title)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.nav.append(button)
        side.addStretch()
        side.addWidget(label("PRIVATE BY DESIGN", "eyebrow"))
        side.addWidget(label("Your audio stays\non this computer.", "muted", True))
        side.addSpacing(12)
        side.addWidget(label("CPU inference · No account", "muted", True))
        outer.addWidget(sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(30, 24, 30, 24)
        content.setSpacing(15)
        self.notice = label("", "notice", True)
        self.notice.hide()
        content.addWidget(self.notice)
        content.addWidget(self.pages, 1)
        outer.addLayout(content, 1)
        self._dictation_page()
        self._models_page()
        self._preferences_page()
        self.navigate(0)

    def navigate(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)

    def _page(self, title: str, subtitle: str) -> QVBoxLayout:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.pages.addWidget(scroll)
        return layout

    def _dictation_page(self) -> None:
        layout = self._page("Speak naturally. Stay local.",
                            "Turn your voice into text, without sending your audio anywhere.")
        frame, box = card()
        heading = QHBoxLayout()
        heading.addWidget(label("VOICE CAPTURE", "eyebrow"))
        heading.addStretch()
        self.status = label("Ready", "status")
        heading.addWidget(self.status)
        box.addLayout(heading)
        self.capture_title = label("Make room for your next thought.", "section")
        box.addWidget(self.capture_title)
        self.capture_hint = label("Download a model to start dictating.", "muted", True)
        box.addWidget(self.capture_hint)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setValue(0)
        self.level.setTextVisible(False)
        box.addWidget(self.level)
        controls = QHBoxLayout()
        self.record = QPushButton("Start recording")
        self.record.setObjectName("primary")
        self.record.setEnabled(False)
        self.record.clicked.connect(self.record_requested)
        controls.addWidget(self.record)
        self.elapsed = label("00:00 / 05:00", "muted")
        controls.addWidget(self.elapsed)
        controls.addStretch()
        box.addLayout(controls)
        self.delivery_hint = label("Clipboard only · Nothing is typed automatically", "muted", True)
        box.addWidget(self.delivery_hint)
        layout.addWidget(frame)
        row = QHBoxLayout()
        row.addWidget(label("Latest transcript", "section"))
        row.addStretch()
        self.copy = QPushButton("Copy text")
        self.copy.clicked.connect(self.copy_requested)
        row.addWidget(self.copy)
        clear = QPushButton("Clear")
        row.addWidget(clear)
        layout.addLayout(row)
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText("Your words will appear here. You can edit them before copying.")
        self.transcript.setMinimumHeight(160)
        clear.clicked.connect(self.transcript.clear)
        layout.addWidget(self.transcript, 1)
        self.result = label("Audio is held in memory only. Transcripts are not saved to disk.", "muted", True)
        layout.addWidget(self.result)

    def _models_page(self) -> None:
        layout = self._page("A model for your machine.",
                            "Download once, dictate offline. Choose a model for your language and machine.")
        frame, box = card()
        box.addWidget(label("Active model", "section"))
        self.model = QComboBox()
        self.model.currentIndexChanged.connect(self.model_changed)
        box.addWidget(self.model)
        self.model_detail = label("No model installed", "muted", True)
        box.addWidget(self.model_detail)
        row = QHBoxLayout()
        self.import_model = QPushButton("Use existing model folder")
        self.import_model.setToolTip(
            "Select a CTranslate2 Whisper, whisper.cpp GGML, or Parakeet ONNX model folder.")
        self.import_model.clicked.connect(self.import_requested)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_requested)
        row.addWidget(self.import_model)
        row.addWidget(refresh)
        row.addStretch()
        box.addLayout(row)
        layout.addWidget(frame)
        self.download_buttons = {}
        for spec in CATALOG:
            frame, box = card()
            row = QHBoxLayout()
            details = QVBoxLayout()
            details.addWidget(label(spec.name, "section"))
            languages = "English only" if spec.languages == ("en",) else "English + Vietnamese"
            details.addWidget(label(f"{languages} · Approx. {spec.size_mb} MB download", "muted"))
            row.addLayout(details, 1)
            button = QPushButton("Download")
            button.clicked.connect(lambda checked=False, key=spec.id: self.download_requested.emit(key))
            self.download_buttons[spec.id] = button
            row.addWidget(button)
            box.addLayout(row)
            layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Model storage", "section"))
        self.storage = label("", "muted", True)
        self.storage.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.storage)
        self.browse_storage = QPushButton("Choose download location")
        self.browse_storage.clicked.connect(self.storage_requested)
        box.addWidget(self.browse_storage)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setTextVisible(False)
        self.download_progress.hide()
        box.addWidget(self.download_progress)
        self.download_status = label("Downloads use Hugging Face. Inference never needs a connection.", "muted", True)
        box.addWidget(self.download_status)
        self.cancel_download = QPushButton("Cancel download")
        self.cancel_download.clicked.connect(self.cancel_download_requested)
        self.cancel_download.hide()
        box.addWidget(self.cancel_download)
        layout.addWidget(frame)
        layout.addStretch()

    def _preferences_page(self) -> None:
        layout = self._page("Make it feel like yours.",
                            "Changes are saved on this machine. No account or sync.")
        frame, box = card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(25)
        grid.setVerticalSpacing(18)
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("Vietnamese — multilingual model required", "vi")
        self.output = QComboBox()
        self.output.addItem("Clipboard only — copy, do not type", "clipboard")
        self.output.addItem("Type into active app + keep clipboard copy", "type")
        self.microphone = QComboBox()
        self.microphone.setPlaceholderText("Choose an available microphone")
        for row, (title, widget) in enumerate((
            ("Dictation language", self.language), ("Text delivery", self.output),
            ("Microphone", self.microphone),
        )):
            grid.addWidget(label(title), row, 0)
            grid.addWidget(widget, row, 1)
            widget.currentIndexChanged.connect(self.preferences_changed)
        box.addLayout(grid)
        refresh = QPushButton("Refresh microphones")
        refresh.clicked.connect(self.refresh_requested)
        box.addWidget(refresh)
        box.addWidget(label("Punctuation is generated by the selected speech model. Recognition and punctuation accuracy depend on the model, microphone and speech. Choose a model that supports Vietnamese for Vietnamese dictation.", "muted", True))
        layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Global shortcut", "section"))
        row = QHBoxLayout()
        self.hotkey_chord = ""
        self._hotkey_pending = False
        self.hotkey = label("No shortcut selected", "section")
        self.hotkey.setAccessibleName("Global shortcut")
        self.choose_hotkey = QPushButton("Choose shortcut…")
        self.choose_hotkey.clicked.connect(self.choose_hotkey_requested)
        self.apply_hotkey = QPushButton("Apply shortcut")
        self.apply_hotkey.clicked.connect(self.hotkey_requested)
        row.addWidget(self.hotkey, 1)
        row.addWidget(self.choose_hotkey)
        row.addWidget(self.apply_hotkey)
        box.addLayout(row)
        self.hotkey_mode = QComboBox()
        self.hotkey_mode.addItem("Hold to talk — release to transcribe", "hold")
        self.hotkey_mode.addItem("Press to start — press again to stop", "toggle")
        self.hotkey_mode.currentIndexChanged.connect(self.preferences_changed)
        box.addWidget(self.hotkey_mode)
        self.hotkey_status = label("", "muted", True)
        box.addWidget(self.hotkey_status)
        box.addWidget(label("Choose shortcut, then press the keys you want. Escape cancels. Apply activates and saves your choice. Windows-reserved or registered shortcuts may be unavailable; other apps can still respond to ordinary key events.", "muted", True))
        layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Background use & privacy", "section"))
        box.addWidget(label("Closing this window keeps TalkNJ in the system tray so your shortcut still works. Use the tray menu to quit. Recording stops automatically at five minutes. Typing never activates another window; if focus changes, recover your text from the clipboard.", "muted", True))
        layout.addWidget(frame)
        layout.addStretch()

    def set_hotkey(self, chord: str, *, pending: bool = False) -> None:
        self.hotkey_chord = validate_hotkey(chord) if chord else ""
        self._hotkey_pending = pending and bool(self.hotkey_chord)
        self.hotkey.setText(format_hotkey(chord) if self.hotkey_chord else "Choose a shortcut")
        self.apply_hotkey.setEnabled(self._hotkey_pending)

    def capture_hotkey(self) -> str | None:
        dialog = ShortcutDialog(self)
        try:
            return dialog.capture()
        finally:
            dialog.deleteLater()

    def show_notice(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def set_busy(self, state: str, available: bool) -> None:
        recording = state == "recording"
        busy = state not in ("idle", "recording")
        self.record.setText("Stop & transcribe" if recording else "Working…" if busy else "Start recording")
        self.record.setEnabled(recording or (available and not busy))
        self.status.setText({"idle": "Ready" if available else "Setup needed", "recording": "Recording",
                             "transcribing": "Transcribing", "delivering": "Delivering"}.get(state, state))
        self.capture_title.setText({"idle": "Make room for your next thought.",
                                   "recording": "Listening. Take your time.",
                                   "transcribing": "Finding the words, locally.",
                                   "delivering": "Your words are on their way."}.get(state, state))
        for widget in (self.model, self.language, self.output, self.microphone, self.choose_hotkey,
                       self.hotkey_mode, self.import_model):
            widget.setEnabled(state == "idle")
        self.apply_hotkey.setEnabled(state == "idle" and self._hotkey_pending)
        if not recording:
            self.level.setValue(0)

    def show_models(self, models, selected: str) -> None:
        self.model.blockSignals(True)
        self.model.clear()
        for model in models:
            self.model.addItem(model.name, str(model.path))
        if not models:
            self.model.addItem("No local model — download one below", "")
        index = self.model.findData(selected)
        self.model.setCurrentIndex(max(0, index))
        self.model.blockSignals(False)

    def set_download_busy(self, busy: bool) -> None:
        for button in self.download_buttons.values():
            button.setEnabled(not busy)
        self.browse_storage.setEnabled(not busy)
        self.download_progress.setVisible(busy)
        self.cancel_download.setVisible(busy)
        self.cancel_download.setEnabled(busy)

    def closeEvent(self, event) -> None:
        if self.allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide_requested.emit()
