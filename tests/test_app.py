import threading

import numpy as np

from flowvoice.app import App
from flowvoice.config import Config
from flowvoice.history import HistoryEntry


class FakeEngine:
    def __init__(self, text="um hello", fail=False):
        self.text, self.fail = text, fail

    def transcribe(self, audio):
        if self.fail:
            raise RuntimeError("model broke")
        return self.text


class FakeRecorder:
    def __init__(self, audio):
        self.audio = audio
        self.started = False
        self.on_level = None

    def start(self):
        self.started = True

    def stop(self):
        return self.audio


class FakeUi:
    def __init__(self):
        self.states, self.notes, self.levels, self.entries = [], [], [], []

    def set_state(self, s):
        self.states.append(s)

    def set_level(self, level):
        self.levels.append(level)

    def notify(self, m):
        self.notes.append(m)

    def add_history(self, entry):
        self.entries.append(entry)


class FakeSpeaker:
    def __init__(self):
        self.said = []

    speaking = False

    def speak(self, text):
        self.said.append(text)

    def stop(self):
        self.said.append("<stop>")

    def is_speaking(self):
        return self.speaking


class FakeHistory:
    def __init__(self, fail=False):
        self.fail = fail
        self.added = []

    def add(self, raw, clean, app_name=""):
        if self.fail:
            raise OSError("disk full")
        self.added.append((raw, clean, app_name))
        return HistoryEntry(len(self.added), "2026-10-05T12:00:00", raw, clean, app_name)


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


AUDIO = np.ones(8000, dtype=np.float32)


def make(engine=None, audio=AUDIO, selection="read me", config=None, history=None,
         clock=None, app_name="notepad.exe"):
    pasted, ui, spk = [], FakeUi(), FakeSpeaker()
    kwargs = {"clock": clock} if clock is not None else {}
    app = App(config or Config(), engine=engine or FakeEngine(), recorder=FakeRecorder(audio),
              speaker=spk, ui=ui, history=history, paste=pasted.append,
              copy_selection=lambda: selection, active_app=lambda: app_name, **kwargs)
    return app, pasted, ui, spk


def test_ptt_cycle_pastes_text():
    app, pasted, ui, _ = make()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello"] and app.recorder.started


def test_short_tap_pastes_nothing_and_returns_to_idle():
    app, pasted, ui, _ = make(audio=None)
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == [] and ui.states[-1] == "idle"


def test_tts_trigger_speaks_selection():
    app, _, _, spk = make(selection="read me")
    app.on_tts_trigger()
    assert spk.said == ["read me"]


def test_state_returns_to_idle_after_paste():
    app, pasted, ui, _ = make()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert ui.states[:2] == ["recording", "processing"] and ui.states[-1] == "idle"


def test_engine_error_notifies_ui():
    app, pasted, ui, _ = make(engine=FakeEngine(fail=True))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == [] and any("model broke" in n for n in ui.notes)
    assert ui.states[-1] == "idle"


def test_tts_trigger_while_speaking_stops():
    app, _, _, spk = make()
    spk.speaking = True
    app.on_tts_trigger()
    assert spk.said == ["<stop>"]


def test_ptt_cancel_discards_recording_and_returns_to_idle():
    app, pasted, ui, _ = make()
    app.on_ptt_start(); app.on_ptt_cancel(); app.dictation.join()
    assert pasted == [] and ui.states[-1] == "idle"


def test_indicator_hidden_before_paste():
    seen = []
    ui = FakeUi()
    app = App(Config(), engine=FakeEngine(), recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              ui=ui, paste=lambda t: seen.append(ui.states[-1]),
              copy_selection=lambda: "", active_app=lambda: "")
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert seen == ["idle"]


def test_app_uses_live_phrase_lists_from_config():
    cfg = Config(backtrack_phrases=["oops"])
    app, pasted, _, _ = make(engine=FakeEngine(text="Keep this. Drop me. Oops."), config=cfg)
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Keep this."]
    app.config = Config(backtrack_phrases=[])  # settings changed at runtime
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted[-1] == "Keep this. Drop me. Oops."


def test_hold_press_release_pastes():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.press(); clock.t += 1.0; app.release(); app.dictation.join()
    assert pasted == ["Hello"]


def test_quick_tap_never_pastes():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.press(); clock.t += 0.1; app.release(); app.dictation.join()
    assert pasted == [] and ui.states[-1] == "idle"


def test_double_tap_cycle_pastes_once():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.press(); clock.t += 0.1; app.release()
    clock.t += 0.2
    app.press(); clock.t += 0.1; app.release()
    assert app.talk.state == "latched" and ui.states[-1] == "recording"
    app.on_level(0.5)
    clock.t += 3.0
    app.click(); app.dictation.join()
    assert pasted == ["Hello"]
    assert app.talk.state == "idle" and ui.states[-1] == "idle"


def test_latched_take_with_no_speech_is_cancelled_not_transcribed():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.click()
    clock.t += 3.0
    app.click(); app.dictation.join()
    assert pasted == [] and app.talk.state == "idle" and ui.states[-1] == "idle"
    assert "processing" not in ui.states


def test_silence_stop_pastes():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.click()
    app.on_level(0.5)
    clock.t += 5.0
    app.tick(); app.dictation.join()
    assert pasted == ["Hello"] and app.talk.state == "idle"


def test_history_entry_written_with_app_name_and_texts():
    hist = FakeHistory()
    app, pasted, ui, _ = make(history=hist, app_name="outlook.exe")
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello"]
    assert hist.added == [("um hello", "Hello", "outlook.exe")]
    assert len(ui.entries) == 1 and ui.entries[0].id == 1
    assert ui.entries[0].clean_text == "Hello" and ui.entries[0].app_name == "outlook.exe"


def test_history_not_written_when_save_history_off():
    hist = FakeHistory()
    app, pasted, ui, _ = make(history=hist, config=Config(save_history=False))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello"] and hist.added == []
    assert len(ui.entries) == 1 and ui.entries[0].id is None
    assert ui.entries[0].raw_text == "um hello" and ui.entries[0].clean_text == "Hello"
    assert ui.entries[0].app_name == "notepad.exe" and ui.entries[0].created_at


def test_history_none_still_shows_last_text():
    app, pasted, ui, _ = make(history=None)
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello"] and len(ui.entries) == 1 and ui.entries[0].id is None


def test_history_failure_does_not_block_paste_or_kill_worker():
    hist = FakeHistory(fail=True)
    app, pasted, ui, _ = make(history=hist)
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello", "Hello"]
    assert "History unavailable" in ui.notes
    assert len(ui.entries) == 2 and all(e.id is None for e in ui.entries)
    assert ui.states[-1] == "idle"


def test_add_history_failure_does_not_kill_worker():
    app, pasted, ui, _ = make()

    def boom(entry):
        raise RuntimeError("ui gone")

    ui.add_history = boom
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello", "Hello"]


def test_commands_applied():
    app, pasted, _, _ = make(engine=FakeEngine(text="hello comma new line world"))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello,\nWorld"]


def test_break_only_take_pastes_the_break():
    app, pasted, ui, _ = make(engine=FakeEngine(text="New paragraph."))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["\n\n"] and ui.entries[-1].clean_text == "\n\n"


def test_voice_commands_off_leaves_words():
    app, pasted, _, _ = make(engine=FakeEngine(text="hello comma new line world"),
                             config=Config(voice_commands=False))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello comma new line world"]


def test_apply_config_updates_silence_and_phrases_live():
    clock = Clock()
    app, pasted, _, _ = make(engine=FakeEngine(text="Keep this. Drop me. Oops."), clock=clock)
    new = Config(silence_stop_seconds=1.0, backtrack_phrases=["oops"], hands_free=False)
    app.apply_config(new)
    assert app.config is new
    assert app.talk.silence_stop_seconds == 1.0 and app.talk.hands_free is False
    app.click()
    app.on_level(0.5)
    clock.t += 1.5
    app.tick(); app.dictation.join()
    assert pasted == ["Keep this."]


def test_on_level_forwards_to_ui_and_talk():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    assert app.recorder.on_level == app.on_level
    app.click()
    clock.t += 5.0
    app.tick()
    assert app.talk.state == "latched"  # no speech heard yet: never silence-stops
    app.on_level(0.5)
    assert ui.levels == [0.5]
    clock.t += 5.0
    app.tick(); app.dictation.join()
    assert app.talk.state == "idle" and pasted == ["Hello"]


class GatedEngine:
    def __init__(self, text="um hello"):
        self.text = text
        self.gate = threading.Event()
        self.entered = threading.Event()

    def transcribe(self, audio):
        self.entered.set()
        self.gate.wait(5)
        return self.text


def test_paste_during_new_recording_keeps_recording_state():
    engine = GatedEngine()
    app, pasted, ui, _ = make(engine=engine)
    app.on_ptt_start(); app.on_ptt_stop()  # dictation A queued
    assert engine.entered.wait(5)
    app.on_ptt_start()  # recording B starts while A is processing
    mark = len(ui.states)
    engine.gate.set(); app.dictation.join()
    assert pasted == ["Hello"]
    assert "idle" not in ui.states[mark:]
    assert ui.states[-1] == "recording"


def test_pill_stays_processing_while_queued_dictation_remains():
    engine = GatedEngine()
    ui = FakeUi()
    at_paste = []
    app = App(Config(), engine=engine, recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              ui=ui, paste=lambda t: at_paste.append(ui.states[-1]),
              copy_selection=lambda: "", active_app=lambda: "")
    app.on_ptt_start(); app.on_ptt_stop()  # A in flight
    assert engine.entered.wait(5)
    app.on_ptt_start(); app.on_ptt_stop()  # B queued behind A
    mark = len(ui.states)
    engine.gate.set(); app.dictation.join()
    assert at_paste == ["processing", "idle"]  # idle only once the queue drains
    assert ui.states[mark:] == ["processing", "idle", "idle"]


def test_paste_when_not_recording_goes_idle_before_paste():
    events = []
    ui = FakeUi()
    orig = ui.set_state
    ui.set_state = lambda s: (events.append(("state", s)), orig(s))
    app = App(Config(), engine=FakeEngine(), recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              ui=ui, paste=lambda t: events.append(("paste", t)),
              copy_selection=lambda: "", active_app=lambda: "")
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    paste_at = events.index(("paste", "Hello"))
    assert ("state", "idle") in events[:paste_at]
    assert ui.states[-1] == "idle"


def test_injected_paste_keys_do_not_cancel_held_next_take():
    clock = Clock()
    engine = GatedEngine()
    pasted, ui = [], FakeUi()
    holder = {}

    def paste(text):
        holder["app"].other_key("v")  # the injected Ctrl+V reaches the global hook
        pasted.append(text)

    app = App(Config(), engine=engine, recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              ui=ui, paste=paste, copy_selection=lambda: "", active_app=lambda: "",
              clock=clock)
    holder["app"] = app
    app.press(); clock.t += 1.0; app.release()  # take A queued
    assert engine.entered.wait(5)
    app.press()  # take B held while A pastes
    engine.gate.set(); app.dictation.join()
    assert pasted == ["Hello"] and app.talk.state == "held"
    clock.t += 1.0
    app.release(); app.dictation.join()
    assert pasted == ["Hello", "Hello"] and app.talk.state == "idle"


def test_injected_copy_keys_do_not_cancel_held_take():
    clock = Clock()
    holder = {}

    def copy():
        holder["app"].other_key("c")
        return "read me"

    ui, spk = FakeUi(), FakeSpeaker()
    app = App(Config(), engine=FakeEngine(), recorder=FakeRecorder(AUDIO), speaker=spk, ui=ui,
              paste=lambda t: None, copy_selection=copy, active_app=lambda: "", clock=clock)
    holder["app"] = app
    app.press()
    app.on_tts_trigger()
    assert spk.said == ["read me"] and app.talk.state == "held"


def test_real_other_key_still_cancels_held_take():
    clock = Clock()
    app, pasted, ui, _ = make(clock=clock)
    app.press()
    app.other_key("x")
    assert app.talk.state == "idle" and ui.states[-1] == "idle"


def test_injection_flag_cleared_when_paste_raises():
    clock = Clock()
    ui = FakeUi()

    def bad_paste(text):
        raise RuntimeError("no clipboard")

    app = App(Config(), engine=FakeEngine(), recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              ui=ui, paste=bad_paste, copy_selection=lambda: "", active_app=lambda: "",
              clock=clock)
    app.press(); clock.t += 1.0; app.release(); app.dictation.join()
    app.press()
    app.other_key("x")
    assert app.talk.state == "idle"


def test_on_level_never_raises_into_audio_thread():
    app, _, ui, _ = make()

    def boom(level):
        raise RuntimeError("widget gone")

    ui.set_level = boom
    app.on_level(0.5)
