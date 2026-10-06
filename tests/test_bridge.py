import inspect
import threading

from PySide6.QtCore import QCoreApplication, QObject, Slot
import pytest

from flowvoice.history import HistoryEntry
from flowvoice.ui.bridge import QtUi
from flowvoice.ui_api import Ui


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


def test_qtui_satisfies_ui_protocol(qapp):
    ui = QtUi()
    assert isinstance(ui, Ui)
    for name, params in [
        ("set_state", ["state"]),
        ("set_level", ["level"]),
        ("notify", ["message"]),
        ("add_history", ["entry"]),
    ]:
        assert list(inspect.signature(getattr(ui, name)).parameters) == params


class _Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.calls = []

    @Slot(str)
    def on_str(self, value):
        self.calls.append((threading.current_thread(), value))

    @Slot(float)
    def on_float(self, value):
        self.calls.append((threading.current_thread(), value))

    @Slot(object)
    def on_obj(self, value):
        self.calls.append((threading.current_thread(), value))


_ENTRY = _entry()


@pytest.mark.parametrize(
    "method, signal, slot, arg",
    [
        ("set_state", "state_changed", "on_str", "recording"),
        ("set_level", "level_changed", "on_float", 0.5),
        ("notify", "message", "on_str", "x"),
        ("add_history", "entry_added", "on_obj", _ENTRY),
    ],
)
def test_emit_from_thread_is_queued_to_main_thread(qapp, method, signal, slot, arg):
    ui = QtUi()
    receiver = _Receiver()
    getattr(ui, signal).connect(getattr(receiver, slot))
    worker = threading.Thread(target=lambda: getattr(ui, method)(arg))
    worker.start()
    worker.join()
    assert receiver.calls == []
    QCoreApplication.processEvents()
    assert len(receiver.calls) == 1
    thread, value = receiver.calls[0]
    assert thread is threading.main_thread()
    assert value is arg if method == "add_history" else value == arg


def test_set_ai_status_emits(qapp):
    ui = QtUi()
    got = []
    ui.ai_status_changed.connect(lambda status, detail: got.append((status, detail)))
    ui.set_ai_status("missing model", "ollama pull x")
    assert got == [("missing model", "ollama pull x")]


class _PairReceiver(QObject):
    def __init__(self):
        super().__init__()
        self.calls = []

    @Slot(str, str)
    def on_pair(self, status, detail):
        self.calls.append((threading.current_thread(), status, detail))


def test_set_ai_status_from_thread_is_queued_to_main_thread(qapp):
    ui = QtUi()
    receiver = _PairReceiver()
    ui.ai_status_changed.connect(receiver.on_pair)
    worker = threading.Thread(target=lambda: ui.set_ai_status("ready", ""))
    worker.start()
    worker.join()
    assert receiver.calls == []
    QCoreApplication.processEvents()
    assert receiver.calls == [(threading.main_thread(), "ready", "")]
