"""Thread-safe bridge from App (any thread) to Qt widgets (GUI thread)."""
from PySide6.QtCore import QObject, Signal

from flowvoice.history import HistoryEntry
from flowvoice.ui_api import State


class QtUi(QObject):
    """Implements the Ui protocol by emitting signals; Qt queues them across threads."""

    state_changed = Signal(str)
    level_changed = Signal(float)
    message = Signal(str)
    entry_added = Signal(object)
    window_requested = Signal(str)
    ai_status_changed = Signal(str, str)

    def set_state(self, state: State) -> None:
        self.state_changed.emit(state)

    def set_level(self, level: float) -> None:
        self.level_changed.emit(level)

    def notify(self, message: str) -> None:
        self.message.emit(message)

    def add_history(self, entry: HistoryEntry) -> None:
        self.entry_added.emit(entry)

    def show_window(self, page: str) -> None:
        """Ask the GUI thread to open the main window on `page` (Home, History, Settings)."""
        self.window_requested.emit(page)

    def set_ai_status(self, status: str, detail: str) -> None:
        """AI service status for Settings; only emits, so AiService may call it under its lock."""
        self.ai_status_changed.emit(status, detail)
