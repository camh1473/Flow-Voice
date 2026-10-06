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


def speak(app, clock, seconds=1.5, level=0.5, step=0.05):
    """Sustained speech-like input: TalkMode ignores the first 0.6 s of a take (key thump)
    and needs ~0.25 s of voice after that to count speech as heard."""
    for _ in range(int(round(seconds / step))):
        app.on_level(level)
        clock.t += step

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


def test_tts_trigger_with_nothing_selected_says_so_instead_of_staying_silent():
    app, _, ui, spk = make(selection="   ")
    app.on_tts_trigger()
    assert spk.said == []
    assert any("select" in n.lower() for n in ui.notes)


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
    speak(app, clock)
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
    speak(app, clock)
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


def test_history_unavailable_notified_once_per_failure_streak():
    hist = FakeHistory(fail=True)
    app, pasted, ui, _ = make(history=hist)

    def take():
        app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()

    take(); take(); take()
    assert ui.notes.count("History unavailable") == 1
    hist.fail = False
    take()
    hist.fail = True
    take(); take()
    assert ui.notes.count("History unavailable") == 2


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
    speak(app, clock)
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
    speak(app, clock)
    assert ui.levels and set(ui.levels) == {0.5}  # every chunk reaches the UI
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


class PromptEngine:
    """Records the initial_prompt of every transcribe call."""

    def __init__(self, text="um hello"):
        self.text = text
        self.prompts = []

    def transcribe(self, audio, initial_prompt=None):
        self.prompts.append(initial_prompt)
        return self.text


class FakeAi:
    def __init__(self, result=None, error=None, status="off"):
        self.result, self.error, self.status = result, error, status
        self.configured, self.calls = [], []

    def configure(self, cfg):
        self.configured.append(cfg)

    def polish(self, text, cfg):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.result


def make_ai(engine=None, ai=None, config=None, history=None, clock=None):
    pasted, ui = [], FakeUi()
    kwargs = {"clock": clock} if clock is not None else {}
    app = App(config or Config(), engine=engine or PromptEngine(), recorder=FakeRecorder(AUDIO),
              speaker=FakeSpeaker(), ui=ui, history=history, paste=pasted.append,
              copy_selection=lambda: "", active_app=lambda: "notepad.exe", ai=ai, **kwargs)
    return app, pasted, ui


def take(app):
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()


def test_no_terms_calls_engine_without_prompt():
    engine = PromptEngine()
    app, pasted, _ = make_ai(engine=engine)
    take(app)
    assert engine.prompts == [None] and pasted == ["Hello"]


def test_old_engine_without_prompt_kwarg_still_works():
    app, pasted, ui, _ = make(engine=FakeEngine(), config=Config(dictionary_terms=[]))
    take(app)
    assert pasted == ["Hello"] and ui.notes == []


def test_glossary_passed_live_and_updated_after_apply_config():
    engine = PromptEngine()
    app, pasted, _ = make_ai(engine=engine, config=Config(dictionary_terms=["TBB", "Perry"]))
    take(app)
    app.apply_config(Config(dictionary_terms=["Ollama"]))
    take(app)
    app.apply_config(Config())
    take(app)
    assert engine.prompts == ["Glossary: TBB, Perry.", "Glossary: Ollama.", None]
    assert pasted == ["Hello"] * 3


def test_glossary_echo_pastes_nothing():
    hist = FakeHistory()
    engine = PromptEngine(text="Glossary: TBB, Perry.")
    app, pasted, ui = make_ai(engine=engine, config=Config(dictionary_terms=["TBB", "Perry"]),
                              history=hist)
    take(app)
    assert pasted == [] and hist.added == [] and ui.entries == [] and ui.states[-1] == "idle"
    engine.text = "TBB"  # a single term said alone is real dictation
    take(app)
    assert pasted == ["TBB"]


def test_snippet_expands_in_pasted_text_and_history_keeps_raw():
    hist = FakeHistory()
    cfg = Config(snippets={"my email": "cam@example.com"})
    app, pasted, ui = make_ai(engine=PromptEngine(text="um send it to my email."), config=cfg,
                              history=hist)
    take(app)
    assert pasted == ["Send it to cam@example.com"]
    assert hist.added == [("um send it to my email.", "Send it to cam@example.com", "notepad.exe")]
    assert ui.entries[-1].raw_text == "um send it to my email."
    assert ui.entries[-1].clean_text == "Send it to cam@example.com"


def test_lists_dictionary_and_commands_in_pasted_text():
    engine = PromptEngine(text="tbb needs 1. milk 2. eggs 3. bread")
    app, pasted, _ = make_ai(engine=engine, config=Config(dictionary_terms=["TBB"]))
    take(app)
    assert pasted == ["TBB needs:\n1. Milk\n2. Eggs\n3. Bread"]
    app.apply_config(Config(dictionary_terms=["TBB"], auto_lists=False))
    take(app)
    assert pasted[-1] == "TBB needs 1. Milk 2. Eggs 3. Bread"  # lists off: one line
    engine.text = "hello comma new line world"
    take(app)
    assert pasted[-1] == "Hello,\nWorld"


def test_ai_polish_result_pasted_when_returned():
    hist = FakeHistory()
    ai = FakeAi(result="Polished text")
    app, pasted, _ = make_ai(ai=ai, config=Config(ai_enabled=True), history=hist)
    take(app)
    assert ai.calls == ["Hello"] and pasted == ["Polished text"]
    assert hist.added == [("um hello", "Polished text", "notepad.exe")]


def test_ai_none_keeps_rule_text():
    ai = FakeAi(result=None)
    app, pasted, _ = make_ai(ai=ai, config=Config(ai_enabled=True))
    take(app)
    assert ai.calls == ["Hello"] and pasted == ["Hello"]


def test_ai_raising_keeps_paste_and_worker_alive():
    ai = FakeAi(error=RuntimeError("model crashed"))
    app, pasted, ui = make_ai(ai=ai, config=Config(ai_enabled=True))
    take(app); take(app)
    assert pasted == ["Hello", "Hello"] and len(ai.calls) == 2
    assert ui.states[-1] == "idle" and ui.notes == []


def test_ai_disabled_never_polishes():
    ai = FakeAi(result="Polished text")
    app, pasted, _ = make_ai(ai=ai, config=Config(ai_enabled=False))
    take(app)
    assert ai.calls == [] and pasted == ["Hello"]


def test_ai_configured_at_construction_and_on_apply_config():
    ai = FakeAi()
    first = Config()
    app, _, _ = make_ai(ai=ai, config=first)
    assert len(ai.configured) == 1 and ai.configured[0] is first
    new = Config(ai_enabled=True)
    app.apply_config(new)
    assert len(ai.configured) == 2 and ai.configured[1] is new and app.config is new


def test_disabled_ai_never_retries_configure():
    clock = Clock()
    ai = FakeAi(status="unavailable")
    app, pasted, _ = make_ai(ai=ai, config=Config(ai_enabled=False), clock=clock)
    clock.t += 120.0
    take(app)
    clock.t += 120.0
    take(app)
    assert len(ai.configured) == 1 and pasted == ["Hello", "Hello"]


def test_unavailable_ai_retries_configure_at_most_every_60_seconds():
    clock = Clock()
    ai = FakeAi(status="unavailable")
    cfg = Config(ai_enabled=True)
    app, pasted, _ = make_ai(ai=ai, config=cfg, clock=clock)
    assert len(ai.configured) == 1
    take(app)  # the constructor just attempted
    assert len(ai.configured) == 1
    clock.t += 61.0
    take(app)
    assert len(ai.configured) == 2 and ai.configured[-1] is cfg
    clock.t += 30.0
    take(app)
    assert len(ai.configured) == 2
    ai.status = "missing model"
    clock.t += 31.0
    take(app)
    assert len(ai.configured) == 3
    assert pasted == ["Hello"] * 4


def test_ready_or_warming_ai_never_retries():
    clock = Clock()
    ai = FakeAi(status="ready")
    app, _, _ = make_ai(ai=ai, config=Config(ai_enabled=True), clock=clock)
    clock.t += 120.0
    take(app)
    ai.status = "warming"
    clock.t += 120.0
    take(app)
    assert len(ai.configured) == 1


def test_retry_configure_raising_does_not_break_paste():
    clock = Clock()
    ai = FakeAi(status="unavailable")
    app, pasted, ui = make_ai(ai=ai, config=Config(ai_enabled=True), clock=clock)

    def boom(cfg):
        raise RuntimeError("thread start failed")

    ai.configure = boom
    clock.t += 61.0
    take(app); take(app)
    assert pasted == ["Hello", "Hello"] and ui.notes == []
