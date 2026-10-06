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
    # Legacy tests feed a single level() call as "speech heard"; the sustained-speech
    # rule (min_speech_seconds) is exercised explicitly by the real_* tests below.
    kw.setdefault("min_speech_seconds", 0.0)
    kw.setdefault("settle_seconds", 0.0)
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
    tm.level(0.5)
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
    tm.level(0.5)
    clock.advance(1.0)
    tm.click()
    assert events == ["start", "stop"]
    assert tm.state == "idle"


def test_latched_press_with_no_speech_cancels():
    tm, clock, events = make()
    latch(tm, clock)
    tm.level(0.01)
    clock.advance(2.0)
    tm.press()
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"
    clock.advance(0.1)
    tm.release()
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_latched_click_with_no_speech_cancels():
    tm, clock, events = make()
    latch(tm, clock)
    clock.advance(2.0)
    tm.click()
    assert events == ["start", "cancel", "start", "cancel"]
    assert tm.state == "idle"


def test_click_latch_then_click_with_no_speech_cancels():
    tm, clock, events = make()
    tm.click()
    clock.advance(1.0)
    tm.click()
    assert events == ["start", "cancel"]


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
    talk(tm, clock, 299.0)  # speech-like levels the whole time: never silent
    assert tm.state == "latched"
    talk(tm, clock, 2.0)
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
                  clock=clock, min_speech_seconds=0.0, settle_seconds=0.0)
    holder["tm"] = tm
    done = threading.Event()

    def run():
        tm.click()
        done.set()

    threading.Thread(target=run, daemon=True).start()
    assert done.wait(2.0)
    assert events == ["start:latched", "stop"]
    assert tm.state == "idle"


def _gated(events, gate, entered, holder):
    def on_start():
        entered.set()
        gate.wait(2.0)
        holder["tm"].level(0.5)  # speech heard, so the next stop is a real stop
        events.append("start")
    return on_start


def _race(second_call):
    """Thread A's click blocks inside on_start; thread B acts meanwhile."""
    events: list[str] = []
    gate, entered = threading.Event(), threading.Event()
    clock = Clock()
    holder: dict = {}
    tm = TalkMode(_gated(events, gate, entered, holder), lambda: events.append("stop"),
                  lambda: events.append("cancel"), clock=clock, min_speech_seconds=0.0, settle_seconds=0.0)
    holder["tm"] = tm
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


# --- silence detection must be relative to the room's noise floor -------------------
# A Razer Seiren Mini sits at a steady 0.054-0.073 on the rms*10 scale, right next to the
# fixed 0.05 voice threshold: noise counted as speech, then a dip below 0.05 for 4 s
# looked like "silence after speech" and stopped a take where nobody had spoken.

def real(**kw):
    return make(min_speech_seconds=0.25, settle_seconds=0.6, **kw)


def feed(tm, clock, level, seconds, step=0.05, tick_every=0.2):
    elapsed = since_tick = 0.0
    while elapsed < seconds - 1e-9:
        tm.level(level)
        clock.advance(step)
        elapsed += step
        since_tick += step
        if since_tick >= tick_every - 1e-9:
            tm.tick()
            since_tick = 0.0


def talk(tm, clock, seconds, loud=0.5, dip=0.12):
    """Speech-like levels: 0.4 s of voice, then a 0.1 s dip between words."""
    elapsed = 0.0
    while elapsed < seconds - 1e-9:
        feed(tm, clock, loud, 0.4)
        feed(tm, clock, dip, 0.1)
        elapsed += 0.5


def test_noise_dipping_below_old_threshold_never_arms_silence_stop():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.065, 3.0)   # steady mic noise above the old 0.05 threshold
    feed(tm, clock, 0.03, 9.0)    # then the room gets quieter than that
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_steady_mic_noise_alone_never_stops_a_latched_take():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.07, 30.0)
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_key_click_spike_is_not_speech():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.04, 0.5)
    tm.level(0.8)                 # one short click/pop
    clock.advance(0.03)
    feed(tm, clock, 0.04, 9.0)
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_real_speech_then_silence_still_stops_with_stop_not_cancel():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.065, 1.0)
    talk(tm, clock, 2.0)
    feed(tm, clock, 0.065, 5.0)   # back to mic noise: 4 s of quiet after speech
    assert events == ["start", "cancel", "start", "stop"]
    assert tm.state == "idle"


def test_speaking_from_the_very_first_chunk_is_detected():
    tm, clock, events = real()
    tm.click()                    # latch by clicking, speak at once
    talk(tm, clock, 3.0)
    feed(tm, clock, 0.065, 5.0)
    assert events == ["start", "stop"]


def test_long_continuous_speech_does_not_silence_stop():
    tm, clock, events = real()
    tm.click()
    talk(tm, clock, 40.0)
    assert tm.state == "latched"
    assert events == ["start"]


def test_quiet_room_below_threshold_still_needs_real_speech():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.01, 15.0)
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_one_glitched_zero_chunk_does_not_let_mic_noise_count_as_voice():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.065, 1.0)
    tm.level(0.0)                 # driver glitch: a single all-zero chunk
    clock.advance(0.05)
    feed(tm, clock, 0.07, 12.0)   # ordinary mic noise afterwards
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]

def test_loud_key_thump_right_after_latching_is_not_speech():
    # A desk-mounted mic hears the Right Ctrl double-tap itself: a 0.45 s burst well above
    # the noise floor. It must not count as speech and arm the silence timer.
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.5, 0.45)    # the thump of the key
    feed(tm, clock, 0.04, 10.0)   # then the user says nothing
    assert tm.state == "latched"
    assert events == ["start", "cancel", "start"]


def test_speech_right_after_the_settle_window_is_still_detected():
    tm, clock, events = real()
    latch(tm, clock)
    feed(tm, clock, 0.04, 0.8)
    talk(tm, clock, 2.0)
    feed(tm, clock, 0.04, 5.0)
    assert events == ["start", "cancel", "start", "stop"]