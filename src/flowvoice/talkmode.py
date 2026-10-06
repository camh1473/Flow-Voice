import threading
import time
from typing import Callable, Optional

Callback = Callable[[], None]


class TalkMode:
    """Hold / tap / double-tap / latch state machine for the dictation key and pill.

    Pure logic: the caller feeds key, click, mic level and timer events. Callbacks take
    no arguments and run after the internal lock is released, so they may call back in.
    A short tap starts then cancels (never stops), so a brush of the key never
    transcribes. Silence only stops a latched take, and only after speech was heard.
    """

    def __init__(self, on_start: Callback, on_stop: Callback, on_cancel: Callback, *,
                 clock: Callable[[], float] = time.monotonic, hands_free: bool = True,
                 silence_stop_seconds: float = 4.0, tap_seconds: float = 0.3,
                 double_tap_seconds: float = 0.5, max_seconds: float = 300.0,
                 voice_threshold: float = 0.05):
        self._on_start, self._on_stop, self._on_cancel = on_start, on_stop, on_cancel
        self._clock = clock
        self.hands_free = hands_free
        self.silence_stop_seconds = silence_stop_seconds
        self._tap = tap_seconds
        self._double_tap = double_tap_seconds
        self._max = max_seconds
        self._threshold = voice_threshold
        self._lock = threading.Lock()
        self._state = "idle"
        self._press_at = 0.0
        self._latch_at = 0.0
        self._last_tap_end: Optional[float] = None
        self._ignore_release = False
        self._heard_speech = False
        self._last_voice = 0.0

    @property
    def state(self) -> str:
        return self._state

    def _begin(self, now: float, state: str) -> Callback:
        self._state = state
        self._press_at = now
        self._latch_at = now
        self._heard_speech = False
        self._ignore_release = False
        return self._on_start

    def _end(self, cb: Callback, ignore_release: bool = False) -> Callback:
        self._state = "idle"
        self._ignore_release = ignore_release
        return cb

    @staticmethod
    def _fire(cb: Optional[Callback]) -> None:
        if cb is not None:
            cb()

    def press(self) -> None:
        cb = None
        with self._lock:
            now = self._clock()
            if self._state == "idle":
                cb = self._begin(now, "held")
            elif self._state == "latched":
                self._last_tap_end = None
                cb = self._end(self._on_stop, ignore_release=True)
        self._fire(cb)

    def release(self) -> None:
        cb = None
        with self._lock:
            now = self._clock()
            if self._state == "idle":
                self._ignore_release = False
            elif self._state == "held":
                if now - self._press_at >= self._tap:
                    self._last_tap_end = None
                    cb = self._end(self._on_stop)
                elif (self.hands_free and self._last_tap_end is not None
                      and now - self._last_tap_end <= self._double_tap):
                    self._last_tap_end = None
                    self._state = "latched"
                    self._latch_at = self._press_at
                else:
                    self._last_tap_end = now
                    cb = self._end(self._on_cancel)
        self._fire(cb)

    def other_key(self, name: str) -> None:
        cb = None
        with self._lock:
            if self._state == "held":
                self._last_tap_end = None
                cb = self._end(self._on_cancel, ignore_release=True)
            elif self._state == "latched" and name == "esc":
                self._last_tap_end = None
                cb = self._end(self._on_cancel)
        self._fire(cb)

    def click(self) -> None:
        cb = None
        with self._lock:
            now = self._clock()
            if self._state == "idle":
                self._last_tap_end = None
                cb = self._begin(now, "latched")
            elif self._state == "latched":
                cb = self._end(self._on_stop)
        self._fire(cb)

    def level(self, value: float) -> None:
        with self._lock:
            if self._state != "idle" and value >= self._threshold:
                self._last_voice = self._clock()
                self._heard_speech = True

    def tick(self) -> None:
        cb = None
        with self._lock:
            if self._state == "latched":
                now = self._clock()
                silent = (self._heard_speech
                          and now - self._last_voice >= self.silence_stop_seconds)
                if silent or now - self._latch_at >= self._max:
                    cb = self._end(self._on_stop)
        self._fire(cb)
