import threading

import numpy as np

from flowvoice.app import MIC_CHECK_SECONDS, App
from flowvoice.config import Config


class FakeEngine:
    def transcribe(self, audio, initial_prompt=None):
        return "hello"


class Ui:
    def __init__(self):
        self.notes, self.states = [], []

    def set_state(self, s):
        self.states.append(s)

    def set_level(self, level):
        pass

    def notify(self, m):
        self.notes.append(m)

    def add_history(self, entry):
        pass


class MicRecorder:
    def __init__(self, healthy=True, outcome="same"):
        self._healthy, self.outcome = healthy, outcome
        self.reopened = 0
        self.on_level = None
        self.done = threading.Event()

    def healthy(self):
        return self._healthy

    def reopen(self):
        self.reopened += 1
        if self.outcome == "same":
            self._healthy = True
        self.done.set()
        return self.outcome

    def start(self):
        pass

    def stop(self):
        return None


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Speaker:
    def is_speaking(self):
        return False


def make(recorder):
    clock, ui = Clock(), Ui()
    app = App(Config(), engine=FakeEngine(), recorder=recorder, speaker=Speaker(), ui=ui,
              paste=lambda t: None, copy_selection=lambda: "", active_app=lambda: "x", clock=clock)
    return app, clock, ui


def settle(app):
    for _ in range(200):
        if not app._mic_busy:
            return
        threading.Event().wait(0.01)
    raise AssertionError("mic check never finished")


def run_check(app, clock, recorder):
    clock.t += MIC_CHECK_SECONDS + 0.1
    recorder.done.clear()
    app.tick()
    settle(app)


def test_healthy_mic_is_left_alone():
    rec = MicRecorder(healthy=True)
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    assert rec.reopened == 0 and ui.notes == []


def test_dead_mic_is_reopened_and_user_told_once():
    rec = MicRecorder(healthy=False, outcome="same")
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    assert rec.reopened == 1
    assert ui.notes == ["Microphone stopped - reconnecting...", "Microphone reconnected"]


def test_fallback_to_default_is_announced():
    rec = MicRecorder(healthy=False, outcome="default")
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    assert any("system default" in n for n in ui.notes)


def test_failed_reopen_retries_without_repeating_the_toast():
    rec = MicRecorder(healthy=False, outcome="failed")
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    run_check(app, clock, rec)
    run_check(app, clock, rec)
    assert rec.reopened == 3
    assert ui.notes == ["Microphone stopped - reconnecting..."]


def test_recovery_after_failures_says_so():
    rec = MicRecorder(healthy=False, outcome="failed")
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    rec.outcome = "same"
    run_check(app, clock, rec)
    assert ui.notes[-1] == "Microphone reconnected"


def test_check_is_throttled():
    rec = MicRecorder(healthy=False, outcome="failed")
    app, clock, ui = make(rec)
    clock.t += MIC_CHECK_SECONDS + 0.1
    app.tick()
    settle(app)
    app.tick()  # no time has passed
    settle(app)
    assert rec.reopened == 1


def test_recorder_without_health_api_is_ignored():
    class Plain:
        on_level = None

        def start(self):
            pass

        def stop(self):
            return np.zeros(1, dtype=np.float32)

    app, clock, ui = make(Plain())
    clock.t += 100
    app.tick()
    assert ui.notes == [] and not app._mic_busy


def test_health_check_exception_does_not_wedge_the_watcher():
    class Boom(MicRecorder):
        def healthy(self):
            raise RuntimeError("portaudio exploded")

    rec = Boom()
    app, clock, ui = make(rec)
    run_check(app, clock, rec)
    assert not app._mic_busy
    run_check(app, clock, rec)  # still callable afterwards
