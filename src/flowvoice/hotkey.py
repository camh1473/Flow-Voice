from typing import Callable

import keyboard


class PushToTalk:
    """Hold `key` to record. Callbacks run inside the keyboard hook: keep them fast."""

    def __init__(self, key: str, on_start: Callable[[], None],
                 on_stop: Callable[[], None], backend=keyboard):
        self._key, self._on_start, self._on_stop = key, on_start, on_stop
        self._backend = backend
        self._handle = None
        self._held = False

    def enable(self) -> None:
        self._handle = self._backend.hook_key(self._key, self._on_event)

    def disable(self) -> None:
        if self._handle is not None:
            self._backend.unhook(self._handle)
            self._handle = None
        self._held = False

    def _on_event(self, event) -> None:
        if event.event_type == "down":
            if not self._held:
                self._held = True
                self._on_start()
        elif self._held:
            self._held = False
            self._on_stop()


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
