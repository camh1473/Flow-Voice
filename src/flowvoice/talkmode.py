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
                 voice_threshold: float = 0.05, min_speech_seconds: float = 0.25,
                 floor_margin: float = 2.5, floor_rise_seconds: float = 10.0,
                 settle_seconds: float = 0.6):
        self._on_start, self._on_stop, self._on_cancel = on_start, on_stop, on_cancel
        self._clock = clock
        self.hands_free = hands_free
        self.silence_stop_seconds = silence_stop_seconds
        self._tap = tap_seconds
        self._double_tap = double_tap_seconds
        self._max = max_seconds
        self._threshold = voice_threshold
        self._min_speech = min_speech_seconds
        self._floor_margin = floor_margin
        self._floor_rise = floor_rise_seconds
        self._settle = settle_seconds
        self._floor = voice_threshold
        self._voice_time = 0.0
        self._last_level_at: Optional[float] = None
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
        self._floor = self._threshold
        self._voice_time = 0.0
        self._last_level_at = None
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
        """Feed one mic level (0..1). Speech is judged against the room's noise floor.

        A fixed threshold fails on mics whose idle noise hovers near it: noise counted as
        speech, and a dip below the line then looked like silence after speech. So the
        floor is tracked (falls at once to any quieter chunk, rises slowly), a chunk is
        voice only when it clearly exceeds that floor, and speech counts as heard only
        after `min_speech_seconds` of voice. The first `settle_seconds` of a take are
        ignored: a desk-mounted mic hears the double-tap itself as a loud burst.
        """
        with self._lock:
            if self._state == "idle":
                return
            now = self._clock()
            dt = 0.0 if self._last_level_at is None else min(now - self._last_level_at, 0.1)
            self._last_level_at = now
            if value < self._floor:
                # Never below 80% of the base threshold: one glitched all-zero chunk
                # must not collapse the floor and let ordinary mic noise count as voice.
                self._floor = max(value, self._threshold * 0.8)
            elif self._floor_rise > 0:
                self._floor += (value - self._floor) * min(1.0, dt / self._floor_rise)
            if now - self._press_at < self._settle:
                return  # the thump of the key / click that started the take
            if value < min(0.9, max(self._threshold, self._floor * self._floor_margin)):
                return
            self._last_voice = now
            self._voice_time += dt
            if self._voice_time >= self._min_speech:
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
