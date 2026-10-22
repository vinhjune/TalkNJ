"""Qt widgets only; recording, inference and OS integration live outside the view."""

from math import ceil
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QIcon, QInputEvent, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QLabel, QListView, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from talknj.audio import MAX_SECONDS
from talknj.models import CATALOG
from talknj.native import _KEY_VKS, format_hotkey, validate_hotkey


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
QPushButton#toggle, QPushButton#compact { padding: 7px 10px; }
QPushButton#toggle:checked { background: #4c5fd5; color: white; border-color: #4c5fd5; }
QPushButton#toggle:disabled { background: #e2e6ed; color: #69748a; border-color: #e2e6ed; }
QLineEdit { background: #ffffff; border: 1px solid #d8dfeb; border-radius: 7px;
    padding: 9px; min-height: 20px; selection-background-color: #4c5fd5; }
QLineEdit:disabled { color: #9ba4b5; }
QComboBox { background: #ffffff; border: 1px solid #d8dfeb; border-radius: 8px;
    padding: 9px 38px 9px 12px; min-height: 20px; combobox-popup: 0;
    selection-background-color: #4c5fd5; }
QComboBox#dictationLanguage { padding: 7px 28px 7px 8px; }
QComboBox:hover { background: #f8f9ff; border-color: #a5afe0; }
QComboBox:focus, QComboBox:on { border-color: #4c5fd5; background: #f5f7ff; }
QComboBox:disabled { color: #9ba4b5; background: #f3f4f7; border-color: #e2e6ed; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right;
    width: 32px; border: none; }
QComboBox::down-arrow { image: url("__CHEVRON__"); width: 14px; height: 9px; }
QComboBox::down-arrow:disabled { image: url("__CHEVRON_DISABLED__"); }
QComboBox QAbstractItemView { background: #ffffff; color: #202839;
    border: 1px solid #d8dfeb; border-radius: 10px; padding: 6px; outline: 0;
    selection-background-color: #edf0ff; selection-color: #3e50bc; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 5px 10px; border-radius: 6px; }
QComboBox QAbstractItemView::item:hover { background: #f5f7ff; }
QComboBox QAbstractItemView::item:selected { background: #edf0ff; color: #3e50bc; }
QComboBox QAbstractItemView::item:disabled { color: #9ba4b5; }
QMenu { background: #ffffff; border: 1px solid #d8dfeb; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: #edf0ff; color: #3e50bc; }
QMenu::item:disabled { color: #9ba4b5; }
QMenu::separator { height: 1px; background: #e3e6ed; margin: 6px; }
QPlainTextEdit { background: #ffffff; border: 1px solid #e0e5ed; border-radius: 10px;
    padding: 14px; font-size: 16px; selection-background-color: #cbd3ff; }
QProgressBar { border: none; background: #e8ecf4; border-radius: 4px; min-height: 7px;
    max-height: 7px; text-align: center; }
QProgressBar::chunk { background: #6f7ee4; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 3px 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 3px; }
QScrollBar:focus { background: #edf0ff; border-radius: 5px; }
QScrollBar::handle:vertical { background: #c1c9df; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:horizontal { background: #c1c9df; border-radius: 5px; min-width: 28px; }
QScrollBar::handle:hover { background: #8796c7; }
QScrollBar::handle:pressed { background: #6175ca; }
QScrollBar::handle:disabled { background: #e2e6ed; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolTip { background: #202839; color: #ffffff; border: none; padding: 6px; }
""".replace("__CHEVRON__", (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()).replace(
    "__CHEVRON_DISABLED__", (Path(__file__).parent / "assets" / "chevron-down-disabled.svg").as_posix())


def countdown_text(elapsed_seconds: float = 0) -> str:
    """Round remaining time upward so 05:00 lasts until one second elapses."""
    seconds = max(0, min(MAX_SECONDS, ceil(MAX_SECONDS - elapsed_seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def combo_box() -> QComboBox:
    """Use an owned Qt popup/delegate so the stylesheet works on both platforms."""
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(12)
    view = QListView(combo)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    combo.setView(view)
    combo.setItemDelegate(QStyledItemDelegate(combo))
    return combo


def app_icon() -> QIcon:
    assets = Path(__file__).parent / "assets"
    icon = QIcon(str(assets / "talknj.png"))
    for size in (16, 24, 32, 48, 64):
        icon.addFile(str(assets / f"talknj-{size}.png"))
    return icon


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
        Qt.Key.Key_Control: Qt.KeyboardModifier.ControlModifier,
        Qt.Key.Key_Alt: Qt.KeyboardModifier.AltModifier,
        Qt.Key.Key_Shift: Qt.KeyboardModifier.ShiftModifier,
        Qt.Key.Key_Meta: Qt.KeyboardModifier.MetaModifier,
    }
    _TRIGGER_KEYS = {code: token for token, code in _KEY_VKS.items()}

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
        modifier_names = "Control, Option, Shift or Cmd" if sys.platform == "darwin" else "Ctrl, Alt, Shift or Win"
        layout.addWidget(label(
            f"Use two or more of {modifier_names}, or combine a modifier with a letter, "
            "number, punctuation key, Space or F1–F12. "
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
        # Cocoa sends aggregate modifier transitions: the final release may
        # come from the opposite physical side to the initial press.
        aggregate_modifier = sys.platform == "darwin" and key in self._MODIFIER_KEYS
        physical_key = ((key, 0, 0) if aggregate_modifier
                        else (key, event.nativeScanCode(), event.nativeVirtualKey()))
        if kind == QEvent.Type.KeyRelease:
            # QKeyEvent.modifiers() toggles the released modifier's own bit.
            # The base accessor preserves Cocoa's aggregate held-key state.
            if not (aggregate_modifier and QInputEvent.modifiers(event) & self._MODIFIER_KEYS[key]):
                self._down.discard(physical_key)
            if not self._down:
                self.use_shortcut.setEnabled(bool(self.chord))
                if self.chord:
                    self.feedback.setText(
                        "Choose Use shortcut, or press a different chord. It is not active until you apply it.")
                elif self.preview.text() == "Waiting for keys…":
                    self.feedback.setText(
                        "Use two different modifiers, or add a letter, number, punctuation, Space or F1–F12.")
            return True
        if key == Qt.Key.Key_Escape:
            self.reject()
            return True
        if not self._down:
            self.chord = ""
            self.preview.setText("Waiting for keys…")
        self._down.add(physical_key)
        self.use_shortcut.setEnabled(False)
        self.chord = ""
        modifiers = event.modifiers()
        if key in self._MODIFIER_KEYS:
            modifiers = QInputEvent.modifiers(event) | self._MODIFIER_KEYS[key]
        for held, _, _ in self._down:
            if held in self._MODIFIER_KEYS:
                modifiers |= self._MODIFIER_KEYS[held]
        # Qt maps ControlModifier to Command and MetaModifier to Control on macOS.
        names = [name for mask, name in (
            (Qt.KeyboardModifier.ControlModifier, "win" if sys.platform == "darwin" else "ctrl"),
            (Qt.KeyboardModifier.AltModifier, "alt"),
            (Qt.KeyboardModifier.ShiftModifier, "shift"),
            (Qt.KeyboardModifier.MetaModifier, "ctrl" if sys.platform == "darwin" else "win"),
        ) if modifiers & mask]
        # Only Windows virtual keys share the codes expected by its global hook.
        # macOS nativeVirtualKey is a hardware code, not a Windows VK identity.
        triggers = [held for held in self._down if held[0] not in self._MODIFIER_KEYS]
        trigger = ""
        if len(triggers) == 1:
            trigger_key, _, native_vk = triggers[0]
            vk = native_vk if sys.platform == "win32" else 0
            if vk:
                trigger = self._TRIGGER_KEYS.get(vk, "")
            elif 0x21 <= trigger_key <= 0x7E:
                trigger = chr(trigger_key).lower()
            elif trigger_key == Qt.Key.Key_Space:
                trigger = "space"
            elif Qt.Key.Key_F1 <= trigger_key <= Qt.Key.Key_F12:
                trigger = f"f{trigger_key - Qt.Key.Key_F1 + 1}"
        try:
            if modifiers & Qt.KeyboardModifier.GroupSwitchModifier or key == Qt.Key.Key_AltGr:
                raise ValueError("AltGr is not supported. Choose another modifier combination.")
            if len(triggers) > 1:
                raise ValueError("Choose exactly one non-modifier key with your modifiers.")
            if not triggers and len(names) < 2:
                self.feedback.setText("Add another modifier or a letter, number, punctuation, Space or F1–F12.")
                return True
            if triggers and not trigger:
                raise ValueError("Choose a letter, number, punctuation, Space or F1–F12 with your modifiers.")
            self.chord = validate_hotkey("+".join(names + ([trigger] if trigger else [])))
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


class _HotkeyLabel(QLabel):
    """Keep the full accessible chord while fitting narrow settings rows."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width())
        painter.drawText(self.contentsRect(), self.alignment(), text)


class MainWindow(QMainWindow):
    record_requested = Signal()
    copy_requested = Signal()
    download_requested = Signal(str)
    cancel_download_requested = Signal()
    import_requested = Signal()
    storage_requested = Signal()
    refresh_requested = Signal()
    preferences_changed = Signal()
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
        for index, title in enumerate(("Dictation", "Preferences", "About")):
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
        self._preferences_page()
        self._about_page()
        self.navigate(0)

    def navigate(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)

    def _page(self, title: str, subtitle: str) -> QVBoxLayout:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.pages.addWidget(scroll)
        return layout

    def _dictation_page(self) -> None:
        layout = self._page("Dictation", "Local speech-to-text. Your audio stays on this computer.")
        frame, box = card()
        box.setContentsMargins(18, 14, 18, 14)
        heading = QHBoxLayout()
        heading.addWidget(label("VOICE CAPTURE", "eyebrow"))
        heading.addStretch()
        self.status = label("Ready", "status")
        heading.addWidget(self.status)
        box.addLayout(heading)
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
        self.elapsed = label(f"{countdown_text()} remaining", "muted")
        controls.addWidget(self.elapsed)
        controls.addStretch()
        box.addLayout(controls)
        self.delivery_hint = label("Global hotkey: types into your app + copies. Recording button: clipboard preview only.", "muted", True)
        box.addWidget(self.delivery_hint)
        layout.addWidget(frame)
        frame, box = card()
        box.setContentsMargins(14, 14, 14, 14)
        box.setSpacing(10)
        box.addWidget(label("Dictation settings", "section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.push_to_talk = QPushButton("Push to talk")
        self.push_to_talk.setObjectName("toggle")
        self.push_to_talk.setCheckable(True)
        self.push_to_talk.setAccessibleName("Push to talk")
        self.push_to_talk.setToolTip("On: hold to talk. Off: press to start, press again to stop.")
        self.push_to_talk.toggled.connect(self.preferences_changed)
        row.addWidget(self.push_to_talk)
        row.addWidget(label("Language"))
        self.language = combo_box()
        self.language.setObjectName("dictationLanguage")
        self.language.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.language.setMinimumWidth(108)
        self.language.setMaximumWidth(160)
        self.language.addItem("English", "en")
        self.language.addItem("Vietnamese", "vi")
        self.language.setAccessibleName("Dictation language")
        self.language.setToolTip("Vietnamese requires a multilingual model in Preferences.")
        self.language.currentIndexChanged.connect(self.preferences_changed)
        row.addWidget(self.language)
        row.addStretch(1)
        row.addWidget(label("Hotkey"))
        self.hotkey_chord = ""
        self.hotkey = _HotkeyLabel("Choose a shortcut")
        self.hotkey.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.hotkey.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.hotkey.setMinimumWidth(80)
        self.hotkey.setAccessibleName("Global hotkey")
        self.hotkey.setToolTip("Global shortcuts also reach other apps. Choose an unused key combination.")
        row.addWidget(self.hotkey)
        self.choose_hotkey = QPushButton("Edit")
        self.choose_hotkey.setObjectName("compact")
        self.choose_hotkey.setIcon(QIcon(str(Path(__file__).parent / "assets" / "edit.svg")))
        self.choose_hotkey.setAccessibleName("Edit global hotkey")
        self.choose_hotkey.clicked.connect(self.choose_hotkey_requested)
        row.addWidget(self.choose_hotkey)
        box.addLayout(row)
        box.addWidget(label("Hold and release with Push to talk enabled; otherwise, press to start/stop.", "muted", True))
        self.hotkey_status = label("", "muted", True)
        self.hotkey_status.hide()
        box.addWidget(self.hotkey_status)
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

    def _preferences_page(self) -> None:
        layout = self._page("Preferences", "Microphone and local speech models. Changes save automatically.")
        frame, box = card()
        row = QHBoxLayout()
        row.addWidget(label("Microphone", "section"))
        self.microphone = combo_box()
        self.microphone.setAccessibleName("Microphone")
        self.microphone.setPlaceholderText("Choose an available microphone")
        self.microphone.currentIndexChanged.connect(self.preferences_changed)
        row.addWidget(self.microphone, 1)
        refresh = QPushButton("Refresh")
        refresh.setToolTip("Refresh microphones and local models")
        refresh.clicked.connect(self.refresh_requested)
        row.addWidget(refresh)
        box.addLayout(row)
        layout.addWidget(frame)
        frame, box = card()
        box.addWidget(label("Model library", "section"))
        row = QHBoxLayout()
        row.addWidget(label("Active model"))
        self.model = combo_box()
        self.model.setAccessibleName("Active model")
        self.model.currentIndexChanged.connect(self.model_changed)
        row.addWidget(self.model, 1)
        self.import_model = QPushButton("Use existing folder")
        self.import_model.setToolTip(
            "Select a CTranslate2 Whisper, whisper.cpp GGML, or Parakeet ONNX model folder.")
        self.import_model.clicked.connect(self.import_requested)
        row.addWidget(self.import_model)
        box.addLayout(row)
        self.model_detail = label("No model installed", "muted", True)
        box.addWidget(self.model_detail)
        box.addWidget(label("Download once, dictate offline. Vietnamese needs a multilingual model.", "muted", True))
        self.download_buttons = {}
        for spec in CATALOG:
            row = QHBoxLayout()
            details = QVBoxLayout()
            details.setSpacing(2)
            details.addWidget(label(spec.name, wrap=True))
            languages = "English only" if spec.languages == ("en",) else "English + Vietnamese"
            details.addWidget(label(f"{languages} · ~{spec.size_mb} MB", "muted"))
            row.addLayout(details, 1)
            button = QPushButton("Download")
            button.clicked.connect(lambda checked=False, key=spec.id: self.download_requested.emit(key))
            self.download_buttons[spec.id] = button
            row.addWidget(button)
            box.addLayout(row)
        layout.addWidget(frame)
        frame, box = card()
        row = QHBoxLayout()
        row.addWidget(label("Model storage", "section"), 1)
        self.browse_storage = QPushButton("Change folder")
        self.browse_storage.clicked.connect(self.storage_requested)
        row.addWidget(self.browse_storage)
        box.addLayout(row)
        self.storage = label("", "muted", True)
        self.storage.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.storage)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setTextVisible(False)
        self.download_progress.hide()
        box.addWidget(self.download_progress)
        self.download_status = label("Downloads use Hugging Face. Inference stays offline.", "muted", True)
        box.addWidget(self.download_status)
        self.cancel_download = QPushButton("Cancel download")
        self.cancel_download.clicked.connect(self.cancel_download_requested)
        self.cancel_download.hide()
        box.addWidget(self.cancel_download)
        layout.addWidget(frame)
        layout.addWidget(label("Closing the window keeps your hotkey active. Quit from the tray or menu-bar icon. "
                               "Recordings stop at five minutes. If focus changes, recover your text from the clipboard.",
                               "muted", True))
        layout.addStretch()

    def _about_page(self) -> None:
        layout = self._page("About TalkNJ", "Private, offline voice dictation.")
        frame, box = card()
        box.addWidget(label("TalkNJ", "section"))
        box.addWidget(label("Creator: Vinh Hoang"))
        contact = label("Email: hoangthevinh.htv@gmail.com")
        contact.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(contact)
        box.addWidget(label("License: GNU General Public License v3.0 (GPL-3.0)",
                            "muted", True))
        layout.addWidget(frame)
        layout.addStretch()

    def set_hotkey(self, chord: str) -> None:
        self.hotkey_chord = validate_hotkey(chord) if chord else ""
        self.hotkey.setText(format_hotkey(chord) if self.hotkey_chord else "Choose a shortcut")
        self.hotkey.setToolTip(
            f"{self.hotkey.text()}\nGlobal shortcuts also reach other apps. Choose an unused key combination.")

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
        for widget in (self.model, self.language, self.microphone, self.choose_hotkey,
                       self.push_to_talk, self.import_model):
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
