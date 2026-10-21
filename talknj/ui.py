"""Qt widgets only; recording, inference and OS integration live outside the view."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from talknj.models import CATALOG


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
                            "Download once, dictate offline. Larger models trade speed for accuracy.")
        frame, box = card()
        box.addWidget(label("Active model", "section"))
        self.model = QComboBox()
        self.model.currentIndexChanged.connect(self.model_changed)
        box.addWidget(self.model)
        self.model_detail = label("No model installed", "muted", True)
        box.addWidget(self.model_detail)
        row = QHBoxLayout()
        self.import_model = QPushButton("Use existing model folder")
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
        box.addWidget(label("Punctuation is generated by Whisper. Recognition and punctuation accuracy depend on the model, microphone and speech. Select Small multilingual for better Vietnamese results.", "muted", True))
        layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Global shortcut", "section"))
        row = QHBoxLayout()
        self.hotkey = QLineEdit()
        self.hotkey.setPlaceholderText("ctrl+alt+space")
        self.hotkey.setAccessibleName("Global hotkey chord")
        self.apply_hotkey = QPushButton("Apply shortcut")
        self.apply_hotkey.clicked.connect(self.hotkey_requested)
        row.addWidget(self.hotkey, 1)
        row.addWidget(self.apply_hotkey)
        box.addLayout(row)
        self.hotkey_mode = QComboBox()
        self.hotkey_mode.addItem("Hold to talk — release to transcribe", "hold")
        self.hotkey_mode.addItem("Press to start — press again to stop", "toggle")
        self.hotkey_mode.currentIndexChanged.connect(self.preferences_changed)
        box.addWidget(self.hotkey_mode)
        self.hotkey_status = label("", "muted", True)
        box.addWidget(self.hotkey_status)
        box.addWidget(label("Use ctrl, alt, shift or win with a letter, number, space or F1–F12. Choose a shortcut not used by your other apps; ordinary key events are not suppressed.", "muted", True))
        layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Background use & privacy", "section"))
        box.addWidget(label("Closing this window keeps TalkNJ in the system tray so your shortcut still works. Use the tray menu to quit. Recording stops automatically at five minutes. Typing never activates another window; if focus changes, recover your text from the clipboard.", "muted", True))
        layout.addWidget(frame)
        layout.addStretch()

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
        for widget in (self.model, self.language, self.output, self.microphone, self.hotkey,
                       self.hotkey_mode, self.apply_hotkey, self.import_model):
            widget.setEnabled(state == "idle")
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
