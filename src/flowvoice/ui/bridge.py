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

    def set_state(self, state: State) -> None:
        self.state_changed.emit(state)

    def set_level(self, level: float) -> None:
        self.level_changed.emit(level)

    def notify(self, message: str) -> None:
        self.message.emit(message)

    def add_history(self, entry: HistoryEntry) -> None:
        self.entry_added.emit(entry)
