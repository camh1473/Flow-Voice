from types import SimpleNamespace

from flowvoice.hotkey import PushToTalk, Toggle


class FakeBackend:
    def __init__(self):
        self.cb = None
        self.unhooked = False

    def hook_key(self, key, callback):
        self.cb = callback
        return "handle"

    def hook(self, callback):
        return "any-handle"

    def unhook(self, handle):
        if handle == "handle":
            self.unhooked = True
            self.cb = None

    def send(self, kind):
        if self.cb:
            self.cb(SimpleNamespace(event_type=kind))


def make(cls=PushToTalk):
    log = []
    b = FakeBackend()
    if cls is PushToTalk:
        h = PushToTalk("f9", lambda: log.append("press"), lambda: log.append("release"), backend=b)
    else:
        h = Toggle("f10", lambda: log.append("fire"), backend=b)
    h.enable()
    return h, b, log


def test_press_then_release_calls_press_then_release():
    _, b, log = make()
    b.send("down"); b.send("up")
    assert log == ["press", "release"]


def test_auto_repeat_down_events_call_press_once():
    _, b, log = make()
    for _ in range(5):
        b.send("down")
    b.send("up")
    assert log == ["press", "release"]


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
    def add_hotkey(self, key, callback, **kw):
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

# --- review fixes ---
class AnyBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.any_cb = None

    def hook(self, callback):
        self.any_cb = callback
        return "any-handle"

    def unhook(self, handle):
        super().unhook(handle)
        if handle == "any-handle":
            self.any_cb = None

    def send_named(self, kind, name):
        ev = SimpleNamespace(event_type=kind, name=name)
        if self.cb and name in ("right ctrl", "left ctrl"):
            self.cb(ev)
        if self.any_cb:
            self.any_cb(ev)


def make_named():
    log = []
    b = AnyBackend()
    h = PushToTalk("right ctrl", lambda: log.append("press"), lambda: log.append("release"),
                   on_other_key=lambda name: log.append(("other", name)), backend=b)
    h.enable()
    return b, log


def test_left_ctrl_does_not_trigger_push_to_talk():
    b, log = make_named()
    b.send_named("down", "left ctrl"); b.send_named("up", "left ctrl")
    assert log == []


def test_other_key_down_reports_name_even_while_held():
    b, log = make_named()
    b.send_named("down", "c")
    b.send_named("down", "right ctrl")
    b.send_named("down", "c")
    b.send_named("up", "right ctrl")
    assert log == [("other", "c"), "press", ("other", "c"), "release"]


def test_esc_down_reports_other_key():
    b, log = make_named()
    b.send_named("down", "esc")
    assert log == [("other", "esc")]


def test_modifier_keys_never_reach_on_other_key():
    b, log = make_named()
    for name in ("ctrl", "left ctrl", "shift", "left shift", "right shift", "alt",
                 "right alt", "alt gr", "windows", "left windows", "right windows"):
        b.send_named("down", name)
        b.send_named("up", name)
    assert log == []


def test_own_key_never_reaches_on_other_key():
    b, log = make_named()
    b.send_named("down", "right ctrl"); b.send_named("up", "right ctrl")
    assert log == ["press", "release"]


def test_other_key_up_is_not_reported():
    b, log = make_named()
    b.send_named("up", "c")
    assert log == []


def test_held_tracks_physical_key_regardless_of_consumer():
    # The consumer (TalkMode) may stop/cancel while the key is still down; repeats must not re-press.
    b, log = make_named()
    b.send_named("down", "right ctrl")
    b.send_named("down", "right ctrl"); b.send_named("down", "right ctrl")
    log.append("consumer-stops")
    b.send_named("down", "right ctrl"); b.send_named("down", "right ctrl")
    b.send_named("up", "right ctrl")
    assert log == ["press", "consumer-stops", "release"]


def test_other_key_does_not_clear_held_state():
    b, log = make_named()
    b.send_named("down", "right ctrl")
    b.send_named("down", "c")
    b.send_named("down", "right ctrl")  # auto-repeat after other key
    b.send_named("up", "right ctrl")
    assert log == ["press", ("other", "c"), "release"]


def test_disable_stops_other_key_callbacks():
    log = []
    b = AnyBackend()
    h = PushToTalk("right ctrl", lambda: None, lambda: None,
                   on_other_key=lambda n: log.append(n), backend=b)
    h.enable()
    h.disable()
    assert b.any_cb is None and b.cb is None


def test_toggle_combo_triggers_on_key_press_not_release():
    # Release-triggered combos depend on the order the user lets go of the keys; copy_selection
    # already waits for the modifiers to come up, so the plain key-down trigger is the reliable one.
    class B(ComboBackend):
        def add_hotkey(self, key, callback, **kw):
            self.kw = kw
            return super().add_hotkey(key, callback)
    b = B()
    Toggle("ctrl+alt+s", lambda: None, backend=b).enable()
    assert not b.kw.get("trigger_on_release")


# --- left/right modifier keys ------------------------------------------------------------
# The keyboard library names the LEFT modifier plainly ("ctrl") and the right one "right ctrl",
# and its own read_hotkey() drops the side entirely. Capturing Right Ctrl therefore saved
# "ctrl", which only matches the left key (manual test 24).

import pytest

from flowvoice.hotkey import key_matches, read_hotkey_by_side


@pytest.mark.parametrize("configured,name,expected", [
    ("right ctrl", "right ctrl", True),
    ("right ctrl", "ctrl", False),
    ("left ctrl", "ctrl", True),
    ("left ctrl", "left ctrl", True),
    ("left ctrl", "right ctrl", False),
    ("ctrl", "ctrl", True),
    ("ctrl", "right ctrl", True),
    ("ctrl", "left ctrl", True),
    ("right shift", "right shift", True),
    ("left shift", "shift", True),
    ("left shift", "right shift", False),
    ("right alt", "right alt", True),
    ("f9", "f9", True),
    ("f9", "f10", False),
    ("right ctrl", "c", False),
])
def test_key_matches_distinguishes_sides(configured, name, expected):
    assert key_matches(configured, name) is expected


def test_push_to_talk_on_left_ctrl_ignores_right_ctrl():
    log = []
    b = AnyBackend()
    h = PushToTalk("left ctrl", lambda: log.append("start"), lambda: log.append("stop"),
                   backend=b)
    h.enable()
    for kind, name in (("down", "right ctrl"), ("up", "right ctrl"),
                       ("down", "ctrl"), ("up", "ctrl")):
        h._on_event(SimpleNamespace(event_type=kind, name=name))
    assert log == ["start", "stop"]


def test_push_to_talk_on_either_ctrl_matches_both():
    log = []
    h = PushToTalk("ctrl", lambda: log.append("start"), lambda: log.append("stop"),
                   backend=AnyBackend())
    for kind, name in (("down", "ctrl"), ("up", "ctrl"), ("down", "right ctrl"),
                       ("up", "right ctrl")):
        h._on_event(SimpleNamespace(event_type=kind, name=name))
    assert log == ["start", "stop", "start", "stop"]


def _capture(*events):
    """Run read_hotkey_by_side against scripted (event_type, name, scan_code) events."""
    delivered = []

    def hook(callback):
        for kind, name, sc in events:
            callback(SimpleNamespace(event_type=kind, name=name, scan_code=sc))
        return "handle"

    return read_hotkey_by_side(hook=hook, unhook=lambda h: delivered.append(h),
                               get_hotkey_name=lambda names: "+".join(sorted(names))), delivered


def test_capture_keeps_right_ctrl_as_right_ctrl():
    result, unhooked = _capture(("down", "right ctrl", 57373), ("up", "right ctrl", 57373))
    assert result == "right ctrl" and unhooked == ["handle"]


def test_capture_names_the_plain_ctrl_event_as_left_ctrl():
    result, _ = _capture(("down", "ctrl", 29), ("up", "ctrl", 29))
    assert result == "left ctrl"


def test_capture_other_single_keys_are_kept_as_is():
    assert _capture(("down", "f9", 67), ("up", "f9", 67))[0] == "f9"
    assert _capture(("down", "esc", 1), ("up", "esc", 1))[0] == "esc"
    assert _capture(("down", "right shift", 54), ("up", "right shift", 54))[0] == "right shift"
    assert _capture(("down", "shift", 42), ("up", "shift", 42))[0] == "left shift"


def test_capture_combos_use_the_libraries_combo_naming():
    result, _ = _capture(("down", "ctrl", 29), ("down", "alt", 56), ("down", "s", 31),
                         ("up", "s", 31))
    assert result == "alt+ctrl+s"  # fake get_hotkey_name sorts; real one orders modifiers first


def test_capture_ignores_auto_repeat_before_release():
    result, _ = _capture(("down", "right ctrl", 57373), ("down", "right ctrl", 57373),
                         ("down", "right ctrl", 57373), ("up", "right ctrl", 57373))
    assert result == "right ctrl"
