"""The small interface App uses to talk to whatever UI is running."""
from typing import Literal, Protocol

from flowvoice.history import HistoryEntry

State = Literal["idle", "recording", "processing"]


class Ui(Protocol):
    def set_state(self, state: State) -> None: ...

    def set_level(self, level: float) -> None: ...

    def notify(self, message: str) -> None: ...

    def add_history(self, entry: HistoryEntry) -> None: ...
