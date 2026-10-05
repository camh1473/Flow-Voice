from typing import Callable

import keyboard

_MODIFIERS = {"ctrl", "left ctrl", "right ctrl", "shift", "left shift", "right shift",
              "alt", "left alt", "right alt", "alt gr", "windows", "left windows",
              "right windows"}


class PushToTalk:
    """Hold `key` to record. Callbacks run inside the keyboard hook: keep them fast.

    Only events whose name equals `key` count (keyboard's hook_key also matches the
    left Ctrl for "right ctrl"). Pressing any non-modifier key while held cancels the
    take, so Right-Ctrl shortcuts (Right Ctrl+C) don't dictate.
    """

    def __init__(self, key: str, on_start: Callable[[], None], on_stop: Callable[[], None],
                 on_cancel: Callable[[], None] = lambda: None, backend=keyboard):
        self._key, self._on_start, self._on_stop = key, on_start, on_stop
        self._on_cancel = on_cancel
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
        return name is None or name == self._key

    def _on_event(self, event) -> None:
        if not self._is_ours(event):
            return
        if event.event_type == "down":
            if not self._held:
                self._held = True
                self._on_start()
        elif self._held:
            self._held = False
            self._on_stop()

    def _on_any(self, event) -> None:
        name = getattr(event, "name", None)
        if self._held and event.event_type == "down" and name is not None \
                and name != self._key and name not in _MODIFIERS:
            self._held = False
            self._on_cancel()


class Toggle:
    """Fires `on_trigger` once per press. Single keys ignore auto-repeat; combos fire on release."""

    def __init__(self, key: str, on_trigger: Callable[[], None], backend=keyboard):
        self._key, self._on_trigger = key, on_trigger
        self._backend = backend
        self._handle = None
        self._held = False
        self._combo = "+" in key

    def enable(self) -> None:
        if self._combo:
            self._handle = self._backend.add_hotkey(self._key, self._on_trigger,
                                                    trigger_on_release=True)
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
