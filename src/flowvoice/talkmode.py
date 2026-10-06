import threading
import time
from typing import Callable, Optional

Callback = Callable[[], None]


class TalkMode:
    """Hold / tap / double-tap / latch state machine for the dictation key and pill.

    Pure logic: the caller feeds key, click, mic level and timer events. Callbacks take
    no arguments. Each public call decides under the state lock, then fires its callback
    with only the dispatch RLock held: callbacks run in decision order across threads,
    and a callback may call back in on its own thread. A short tap starts then cancels
    (never stops), so a brush of the key never transcribes. Silence only stops a latched
    take, and only after speech was heard; a latched take with no speech heard is
    cancelled however it ends (press, click or the time cap).
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
        self._dispatch = threading.RLock()
        self._state = "idle"
        self._press_at = 0.0
        self._latch_at = 0.0
        self._last_tap_end: Optional[float] = None
        self._ignore_release = False
        self._heard_speech = False
        self._last_voice = 0.0

    @property
    def state(self) -> str:
        # Lock-free: a single attribute read is atomic.
        return self._state

    def _run(self, decide: Callable[[], Optional[Callback]]) -> None:
        with self._dispatch:
            with self._lock:
                cb = decide()
            if cb is not None:
                cb()

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

    def press(self) -> None:
        self._run(self._decide_press)

    def release(self) -> None:
        self._run(self._decide_release)

    def other_key(self, name: str) -> None:
        self._run(lambda: self._decide_other_key(name))

    def click(self) -> None:
        self._run(self._decide_click)

    def level(self, value: float) -> None:
        with self._lock:
            if self._state != "idle" and value >= self._threshold:
                self._last_voice = self._clock()
                self._heard_speech = True

    def tick(self) -> None:
        self._run(self._decide_tick)

    def _decide_press(self) -> Optional[Callback]:
        now = self._clock()
        if self._state == "idle":
            return self._begin(now, "held")
        if self._state == "latched":
            self._last_tap_end = None
            return self._end(self._latched_finish(), ignore_release=True)
        return None

    def _latched_finish(self) -> Callback:
        """A latched take with no speech heard is cancelled, never transcribed."""
        return self._on_stop if self._heard_speech else self._on_cancel

    def _decide_release(self) -> Optional[Callback]:
        now = self._clock()
        if self._state == "idle":
            self._ignore_release = False
        elif self._state == "held":
            if now - self._press_at >= self._tap:
                self._last_tap_end = None
                return self._end(self._on_stop)
            if (self.hands_free and self._last_tap_end is not None
                    and now - self._last_tap_end <= self._double_tap):
                self._last_tap_end = None
                self._state = "latched"
                self._latch_at = self._press_at
                return None
            self._last_tap_end = now
            return self._end(self._on_cancel)
        return None

    def _decide_other_key(self, name: str) -> Optional[Callback]:
        if self._state == "held":
            self._last_tap_end = None
            return self._end(self._on_cancel, ignore_release=True)
        if self._state == "latched" and name == "esc":
            self._last_tap_end = None
            return self._end(self._on_cancel)
        return None

    def _decide_click(self) -> Optional[Callback]:
        now = self._clock()
        if self._state == "idle":
            self._last_tap_end = None
            return self._begin(now, "latched")
        if self._state == "latched":
            return self._end(self._latched_finish())
        return None

    def _decide_tick(self) -> Optional[Callback]:
        if self._state != "latched":
            return None
        now = self._clock()
        if self._heard_speech and now - self._last_voice >= self.silence_stop_seconds:
            return self._end(self._on_stop)
        if now - self._latch_at >= self._max:
            return self._end(self._latched_finish())
        return None
