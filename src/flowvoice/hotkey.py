import queue
from typing import Callable

import keyboard

_MODIFIERS = {"ctrl", "left ctrl", "right ctrl", "shift", "left shift", "right shift",
              "alt", "left alt", "right alt", "alt gr", "windows", "left windows",
              "right windows"}

_SIDED = ("ctrl", "shift", "alt", "windows")


def key_matches(configured: str, name: str) -> bool:
    """Does a key event named `name` come from the `configured` key?

    The keyboard library names the LEFT modifier plainly ("ctrl") and the right one
    "right ctrl". So "left ctrl" matches the events "ctrl"/"left ctrl", "right ctrl" only
    "right ctrl", and the side-less "ctrl" (older configs) matches either key.
    """
    if name == configured:
        return True
    for base in _SIDED:
        if configured == f"left {base}":
            return name == base
        if configured == base:
            return name in (f"left {base}", f"right {base}")
    return False


def read_hotkey_by_side(suppress: bool = False, *, hook=keyboard.hook,
                        unhook=keyboard.unhook, get_hotkey_name=keyboard.get_hotkey_name) -> str:
    """Like keyboard.read_hotkey, but a single modifier keeps its side.

    read_hotkey() strips "left"/"right", so pressing Right Ctrl came back as "ctrl", which
    matches the left key. A single key is returned by its own event name (the plain "ctrl"
    event is the left key, so it becomes "left ctrl"); combos use the library's naming.
    """
    events: queue.Queue = queue.Queue()
    handle = hook(events.put)
    pressed: dict = {}
    try:
        while True:
            event = events.get()
            if event.event_type == "down":
                pressed[event.scan_code] = event.name or str(event.scan_code)
            else:
                names = list(pressed.values()) or [event.name]
                break
    finally:
        unhook(handle)
    if len(names) == 1:
        name = names[0]
        return f"left {name}" if name in _SIDED else name
    return get_hotkey_name(names)


class PushToTalk:
    """Raw press/release/other-key events for `key`; TalkMode decides what they mean.

    Callbacks run inside the keyboard hook: keep them fast. Only events from `key` count
    (see key_matches: keyboard's hook_key also matches the left Ctrl for "right ctrl").
    `_held` tracks the physical key only, so auto-repeat never re-fires `on_press`.
    `on_other_key(name)` fires on any non-modifier key-down, whether or not `key` is held.
    """

    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None],
                 on_other_key: Callable[[str], None] = lambda name: None, backend=keyboard):
        self._key, self._on_press, self._on_release = key, on_press, on_release
        self._on_other_key = on_other_key
        self._backend = backend
        self._handles: list = []
        self._held = False

    def enable(self) -> None:
        self._handles = [self._backend.hook_key(self._key, self._on_event),
                         self._backend.hook(self._on_any)]

    def disable(self) -> None:
        for h in self._handles:
            self._backend.unhook(h)
        self._handles = []
        self._held = False

    def _is_ours(self, event) -> bool:
        name = getattr(event, "name", None)
        return name is None or key_matches(self._key, name)

    def _on_event(self, event) -> None:
        if not self._is_ours(event):
            return
        if event.event_type == "down":
            if not self._held:
                self._held = True
                self._on_press()
        elif self._held:
            self._held = False
            self._on_release()

    def _on_any(self, event) -> None:
        name = getattr(event, "name", None)
        if event.event_type == "down" and name is not None \
                and not key_matches(self._key, name) and name not in _MODIFIERS:
            self._on_other_key(name)


class Toggle:
    """Fires `on_trigger` once per press. Single keys ignore auto-repeat; combos use add_hotkey."""

    def __init__(self, key: str, on_trigger: Callable[[], None], backend=keyboard):
        self._key, self._on_trigger = key, on_trigger
        self._backend = backend
        self._handle = None
        self._held = False
        self._combo = "+" in key

    def enable(self) -> None:
        if self._combo:
            self._handle = self._backend.add_hotkey(self._key, self._on_trigger)
        else:
            self._handle = self._backend.hook_key(self._key, self._on_event)

    def disable(self) -> None:
        if self._handle is not None:
            if self._combo:
                self._backend.remove_hotkey(self._handle)
            else:
                self._backend.unhook(self._handle)
            self._handle = None
        self._held = False

    def _on_event(self, event) -> None:
        if event.event_type == "down":
            if not self._held:
                self._held = True
                self._on_trigger()
        else:
            self._held = False
