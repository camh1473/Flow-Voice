from types import SimpleNamespace

from flowvoice.hotkey import PushToTalk, Toggle


class FakeBackend:
    def __init__(self):
        self.cb = None
        self.unhooked = False

    def hook_key(self, key, callback):
        self.cb = callback
        return "handle"

    def unhook(self, handle):
        self.unhooked = True
        self.cb = None

    def send(self, kind):
        if self.cb:
            self.cb(SimpleNamespace(event_type=kind))


def make(cls=PushToTalk):
    log = []
    b = FakeBackend()
    if cls is PushToTalk:
        h = PushToTalk("f9", lambda: log.append("start"), lambda: log.append("stop"), backend=b)
    else:
        h = Toggle("f10", lambda: log.append("fire"), backend=b)
    h.enable()
    return h, b, log


def test_press_then_release_calls_start_then_stop():
    _, b, log = make()
    b.send("down"); b.send("up")
    assert log == ["start", "stop"]


def test_auto_repeat_down_events_call_start_once():
    _, b, log = make()
    for _ in range(5):
        b.send("down")
    b.send("up")
    assert log == ["start", "stop"]


def test_up_without_down_ignored():
    _, b, log = make()
    b.send("up")
    assert log == []


def test_disable_stops_callbacks():
    h, b, log = make()
    h.disable()
    b.send("down")
    assert log == [] and b.unhooked


def test_toggle_fires_once_per_press():
    _, b, log = make(Toggle)
    b.send("down"); b.send("down"); b.send("up")
    b.send("down"); b.send("up")
    assert log == ["fire", "fire"]

class ComboBackend(FakeBackend):
    def add_hotkey(self, key, callback):
        self.combo = (key, callback)
        return "combo-handle"

    def remove_hotkey(self, handle):
        self.combo = None


def test_toggle_combo_uses_add_hotkey():
    b = ComboBackend()
    log = []
    t = Toggle("ctrl+alt+s", lambda: log.append("fire"), backend=b)
    t.enable()
    key, cb = b.combo
    cb()
    assert key == "ctrl+alt+s" and log == ["fire"]
    t.disable()
    assert b.combo is None
