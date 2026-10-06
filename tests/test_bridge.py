import threading

from PySide6.QtCore import QCoreApplication, QObject, Slot

from flowvoice.history import HistoryEntry
from flowvoice.ui.bridge import QtUi


def _entry() -> HistoryEntry:
    return HistoryEntry(1, "2026-01-01T00:00:00", "raw", "clean", "app")


def test_set_state_emits(qapp):
    ui = QtUi()
    got = []
    ui.state_changed.connect(got.append)
    ui.set_state("recording")
    assert got == ["recording"]


def test_set_level_emits(qapp):
    ui = QtUi()
    got = []
    ui.level_changed.connect(got.append)
    ui.set_level(0.5)
    assert got == [0.5]


def test_notify_emits_message(qapp):
    ui = QtUi()
    got = []
    ui.message.connect(got.append)
    ui.notify("hello")
    assert got == ["hello"]


def test_add_history_emits_entry(qapp):
    ui = QtUi()
    got = []
    ui.entry_added.connect(got.append)
    entry = _entry()
    ui.add_history(entry)
    assert got == [entry]


def test_emit_from_thread_runs_slot_on_main_thread(qapp):
    class Receiver(QObject):
        def __init__(self):
            super().__init__()
            self.threads = []
            self.values = []

        @Slot(str)
        def on_state(self, value):
            self.threads.append(threading.current_thread())
            self.values.append(value)

    ui = QtUi()
    receiver = Receiver()
    ui.state_changed.connect(receiver.on_state)
    worker = threading.Thread(target=lambda: ui.set_state("processing"))
    worker.start()
    worker.join()
    QCoreApplication.processEvents()
    assert receiver.values == ["processing"]
    assert receiver.threads == [threading.main_thread()]
