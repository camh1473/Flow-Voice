"""Home tab: live status, the last transcription with Copy, and Start/Stop."""
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowvoice.history import HistoryEntry

ELLIPSIS = "\u2026"
MIDDLE_DOT = "\u00b7"
STATUS_TEXT = {
    "idle": ("Ready", "Waiting for your voice"),
    "recording": ("Listening" + ELLIPSIS, "Speak naturally; stop when you are done"),
    "processing": ("Transcribing" + ELLIPSIS, "Turning your words into text"),
}
EMPTY_ENTRY = "Nothing yet. Your last dictation will show up here."
COPIED_MS = 1400


def _restyle(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(10)
    return card, layout


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


def format_meta(entry: HistoryEntry) -> str:
    """Meta line for an entry: time, then the app name after a middle dot."""
    try:
        when = datetime.fromisoformat(entry.created_at)
        day = "Today" if when.date() == datetime.now().date() else when.strftime("%b %d")
        stamp = f"{day} {when.strftime('%I:%M %p').lstrip('0')}"
    except ValueError:
        stamp = entry.created_at
    return f"{stamp}  {MIDDLE_DOT}  {entry.app_name}" if entry.app_name else stamp


class HomeView(QWidget):
    """Big status with a colored dot, the last transcription card, Start/Stop and a hint."""

    toggle_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._state = "idle"
        self._text = ""
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.setInterval(COPIED_MS)
        self._copy_timer.timeout.connect(self._reset_copy)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)
        root.addWidget(_label("Home", "PageTitle"))

        status_card, status = _card()
        self.state_dot = QLabel()
        self.state_dot.setObjectName("StateDot")
        self.status_label = _label("", "StatusLabel")
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.addWidget(self.state_dot, 0, Qt.AlignVCenter)
        title_row.addWidget(self.status_label, 1)
        self.detail_label = _label("", "Secondary")
        self.detail_label.setWordWrap(True)
        detail_row = QHBoxLayout()
        detail_row.setSpacing(12)
        indent = QLabel()
        indent.setObjectName("DotIndent")
        detail_row.addWidget(indent)
        detail_row.addWidget(self.detail_label, 1)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addLayout(title_row)
        text_col.addLayout(detail_row)
        self.toggle_button = QPushButton()
        self.toggle_button.setProperty("variant", "primary")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle_clicked)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addLayout(text_col, 1)
        row.addWidget(self.toggle_button, 0, Qt.AlignVCenter)
        status.addLayout(row)
        root.addWidget(status_card)

        entry_card, entry = _card()
        head = QHBoxLayout()
        head.addWidget(_label("LAST TRANSCRIPTION", "Caption"), 1, Qt.AlignVCenter)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy)
        head.addWidget(self.copy_button)
        entry.addLayout(head)
        self.entry_label = _label(EMPTY_ENTRY, "EntryText")
        self.entry_label.setWordWrap(True)
        self.entry_label.setTextFormat(Qt.PlainText)
        self.entry_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        entry.addWidget(self.entry_label)
        self.meta_label = _label("", "Secondary")
        self.meta_label.hide()
        entry.addWidget(self.meta_label)
        root.addWidget(entry_card)

        root.addStretch(1)
        self.hint_label = _label("", "HintLabel")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        self._set_empty(True)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        if state not in STATUS_TEXT:
            raise ValueError(f"unknown state: {state}")
        self._state = state
        title, detail = STATUS_TEXT[state]
        self.status_label.setText(title)
        self.detail_label.setText(detail)
        recording = state == "recording"
        self.toggle_button.setText("Stop dictation" if recording else "Start dictation")
        self.toggle_button.setProperty("active", "true" if recording else "false")
        self.state_dot.setProperty("state", state)
        _restyle(self.toggle_button)
        _restyle(self.state_dot)

    def state(self) -> str:
        return self._state

    def show_entry(self, entry: HistoryEntry) -> None:
        self._text = entry.clean_text
        self.entry_label.setText(entry.clean_text)
        self.meta_label.setText(format_meta(entry))
        self.meta_label.show()
        self._set_empty(False)

    def hint(self, text: str) -> None:
        self.hint_label.setText(text)

    def _set_empty(self, empty: bool) -> None:
        self.entry_label.setProperty("empty", "true" if empty else "false")
        self.copy_button.setEnabled(not empty)
        _restyle(self.entry_label)

    def _copy(self) -> None:
        if not self._text:
            return
        QGuiApplication.clipboard().setText(self._text)
        self.copy_button.setText("Copied")
        self._copy_timer.start()

    def _reset_copy(self) -> None:
        self.copy_button.setText("Copy")
