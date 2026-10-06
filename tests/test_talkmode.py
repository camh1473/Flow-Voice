import threading

from flowvoice.talkmode import TalkMode


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def make(**kw):
    clock = Clock()
    events: list[str] = []
    tm = TalkMode(lambda: events.append("start"), lambda: events.append("stop"),
                  lambda: events.append("cancel"), clock=clock, **kw)
    return tm, clock, events


def tap(tm, clock, dur=0.1):
    tm.press()
    clock.advance(dur)
    tm.release()


def latch(tm, clock):
    tap(tm, clock)
    clock.advance(0.2)
    tap(tm, clock)
    assert tm.state == "latched"


def test_hold_starts_and_stops():
    tm, clock, events = make()
    tm.press()
    assert tm.state == "held"
    clock.advance(1.0)
    tm.release()
    assert events == ["start", "stop"]
    assert tm.state == "idle"


def test_tap_is_cancelled_never_stopped():
    tm, clock, events = make()
    tap(tm, clock, 0.1)
    assert events == ["start", "cancel"]
    assert "stop" not in events
    assert tm.state == "idle"


def test_brush_with_hands_free_off_is_cancelled():
    tm, clock, events = make(hands_free=False)
    tap(tm, clock, 0.05)
    assert events == ["start", "cancel"]


def test_double_tap_latches():
    tm, clock, events = make()
    tap(tm, clock)
    clock.advance(0.2)
    tap(tm, clock)
    assert events == ["start", "cancel", "start"]
    assert tm.state == "latched"


def test_third_press_stops_and_its_release_is_ignored():
    tm, clock, events = make()
    latch(tm, clock)
    clock.advance(2.0)
    tm.press()
    assert events[-1] == "stop"
    assert tm.state == "idle"
    clock.advance(0.1)
    tm.release()
    assert events == ["start", "cancel", "start", "stop"]
    assert tm.state == "idle"


def test_taps_too_far_apart_do_not_latch():
    tm, clock, events = make()
    tap(tm, clock)
    clock.advance(0.6)
    tap(tm, clock)
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_double_tap_without_hands_free_does_not_latch():
    tm, clock, events = make(hands_free=False)
    tap(tm, clock)
    clock.advance(0.2)
    tap(tm, clock)
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_hands_free_toggle_applies_live():
    tm, clock, events = make()
    tm.hands_free = False
    tap(tm, clock)
    clock.advance(0.2)
    tap(tm, clock)
    assert tm.state == "idle"


def test_long_hold_between_taps_breaks_double_tap():
    tm, clock, events = make()
    tap(tm, clock)
    clock.advance(0.1)
    tap(tm, clock, 1.0)
    clock.advance(0.1)
    tap(tm, clock)
    assert events == ["start", "cancel", "start", "stop", "start", "cancel"]
    assert tm.state == "idle"


def test_other_key_while_held_cancels_and_release_ignored():
    tm, clock, events = make()
    tm.press()
    clock.advance(0.5)
    tm.other_key("c")
    assert events == ["start", "cancel"]
    assert tm.state == "idle"
    clock.advance(0.5)
    tm.release()
    assert events == ["start", "cancel"]


def test_esc_while_held_cancels():
    tm, clock, events = make()
    tm.press()
    clock.advance(1.0)
    tm.other_key("esc")
    tm.release()
    assert events == ["start", "cancel"]
    assert tm.state == "idle"


def test_esc_cancels_latched_other_keys_ignored():
    tm, clock, events = make()
    latch(tm, clock)
    tm.other_key("c")
    tm.other_key("space")
    assert tm.state == "latched"
    tm.other_key("esc")
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_other_key_while_idle_ignored():
    tm, clock, events = make()
    tm.other_key("esc")
    tm.other_key("c")
    assert events == []


def test_click_toggles_latched_recording():
    tm, clock, events = make()
    tm.click()
    assert events == ["start"]
    assert tm.state == "latched"
    clock.advance(1.0)
    tm.click()
    assert events == ["start", "stop"]
    assert tm.state == "idle"


def test_click_while_held_ignored():
    tm, clock, events = make()
    tm.press()
    tm.click()
    assert tm.state == "held"
    clock.advance(1.0)
    tm.release()
    assert events == ["start", "stop"]


def test_latched_never_silence_stops_before_speech():
    tm, clock, events = make()
    latch(tm, clock)
    tm.level(0.01)
    clock.advance(10.0)
    tm.tick()
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_silence_after_speech_stops():
    tm, clock, events = make()
    tm.click()
    tm.level(0.5)
    clock.advance(4.1)
    tm.tick()
    assert events == ["start", "stop"]
    assert tm.state == "idle"


def test_silence_measured_from_last_voice():
    tm, clock, events = make()
    tm.click()
    tm.level(0.5)
    clock.advance(3.0)
    tm.level(0.5)
    clock.advance(1.1)
    tm.level(0.01)
    tm.tick()
    assert tm.state == "latched"
    clock.advance(3.0)
    tm.tick()
    assert events == ["start", "stop"]


def test_silence_stop_seconds_applies_live():
    tm, clock, events = make()
    tm.silence_stop_seconds = 1.0
    tm.click()
    tm.level(0.5)
    clock.advance(1.1)
    tm.tick()
    assert events == ["start", "stop"]


def test_held_press_never_silence_stops():
    tm, clock, events = make()
    tm.press()
    tm.level(0.5)
    for _ in range(20):
        clock.advance(30.0)
        tm.tick()
    assert tm.state == "held"
    tm.release()
    assert events == ["start", "stop"]


def test_max_seconds_caps_latched_take():
    tm, clock, events = make()
    tm.click()
    for _ in range(299):
        clock.advance(1.0)
        tm.level(0.5)
        tm.tick()
    assert tm.state == "latched"
    clock.advance(1.0)
    tm.level(0.5)
    tm.tick()
    assert events == ["start", "stop"]


def test_max_seconds_without_speech():
    tm, clock, events = make()
    latch(tm, clock)
    clock.advance(301.0)
    tm.tick()
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_events_after_silence_stop_are_idle():
    tm, clock, events = make()
    tm.click()
    tm.level(0.5)
    clock.advance(5.0)
    tm.tick()
    tm.tick()
    tm.release()
    tm.other_key("esc")
    tm.level(0.9)
    assert events == ["start", "stop"]
    tm.press()
    assert tm.state == "held"
    clock.advance(1.0)
    tm.release()
    assert events == ["start", "stop", "start", "stop"]


def test_level_while_idle_does_not_raise():
    tm, clock, events = make()
    tm.level(0.9)
    tm.tick()
    assert events == []


def test_new_latch_resets_heard_speech():
    tm, clock, events = make()
    tm.click()
    tm.level(0.5)
    clock.advance(1.0)
    tm.click()
    clock.advance(1.0)
    tm.click()
    clock.advance(10.0)
    tm.tick()
    assert tm.state == "latched"


def test_callback_may_reenter_same_thread_without_deadlock():
    # A callback calling back into TalkMode on its own thread must not deadlock.
    clock = Clock()
    events: list[str] = []
    holder: dict = {}

    def on_start():
        tm = holder["tm"]
        tm.level(0.9)
        tm.tick()
        events.append(f"start:{tm.state}")
        tm.click()

    tm = TalkMode(on_start, lambda: events.append("stop"), lambda: events.append("cancel"),
                  clock=clock)
    holder["tm"] = tm
    done = threading.Event()

    def run():
        tm.click()
        done.set()

    threading.Thread(target=run, daemon=True).start()
    assert done.wait(2.0)
    assert events == ["start:latched", "stop"]
    assert tm.state == "idle"


def _gated(events, gate, entered):
    def on_start():
        entered.set()
        gate.wait(2.0)
        events.append("start")
    return on_start


def _race(second_call):
    """Thread A's click blocks inside on_start; thread B acts meanwhile."""
    events: list[str] = []
    gate, entered = threading.Event(), threading.Event()
    clock = Clock()
    tm = TalkMode(_gated(events, gate, entered), lambda: events.append("stop"),
                  lambda: events.append("cancel"), clock=clock)
    a = threading.Thread(target=tm.click, daemon=True)
    a.start()
    assert entered.wait(2.0)
    b = threading.Thread(target=lambda: second_call(tm), daemon=True)
    b.start()
    b.join(0.2)
    blocked = b.is_alive()
    early = list(events)
    gate.set()
    a.join(2.0)
    b.join(2.0)
    return blocked, early, events, tm


def test_cross_thread_click_waits_for_pending_start():
    blocked, early, events, tm = _race(lambda tm: tm.click())
    assert blocked
    assert early == []
    assert events == ["start", "stop"]
    assert tm.state == "idle"


def test_cross_thread_press_waits_for_pending_start():
    blocked, early, events, tm = _race(lambda tm: tm.press())
    assert blocked
    assert early == []
    assert events == ["start", "stop"]
    assert tm.state == "idle"
