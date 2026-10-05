import numpy as np

from flowvoice.app import App
from flowvoice.config import Config


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

    def start(self):
        self.started = True

    def stop(self):
        return self.audio


class FakeTray:
    def __init__(self):
        self.states, self.notes = [], []

    def set_state(self, s):
        self.states.append(s)

    def notify(self, m):
        self.notes.append(m)


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


AUDIO = np.ones(8000, dtype=np.float32)


def make(engine=None, audio=AUDIO, selection="read me"):
    pasted, tray, spk = [], FakeTray(), FakeSpeaker()
    app = App(Config(), engine=engine or FakeEngine(), recorder=FakeRecorder(audio),
              speaker=spk, tray=tray, paste=pasted.append, copy_selection=lambda: selection)
    return app, pasted, tray, spk


def test_ptt_cycle_pastes_text():
    app, pasted, tray, _ = make()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Hello"] and app.recorder.started


def test_short_tap_pastes_nothing_and_returns_to_idle():
    app, pasted, tray, _ = make(audio=None)
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == [] and tray.states[-1] == "idle"


def test_tts_trigger_speaks_selection():
    app, _, _, spk = make(selection="read me")
    app.on_tts_trigger()
    assert spk.said == ["read me"]


def test_state_returns_to_idle_after_paste():
    app, pasted, tray, _ = make()
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert tray.states[:2] == ["recording", "processing"] and tray.states[-1] == "idle"


def test_engine_error_notifies_tray():
    app, pasted, tray, _ = make(engine=FakeEngine(fail=True))
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == [] and any("model broke" in n for n in tray.notes)
    assert tray.states[-1] == "idle"


def test_tts_trigger_while_speaking_stops():
    app, _, _, spk = make()
    spk.speaking = True
    app.on_tts_trigger()
    assert spk.said == ["<stop>"]

def test_ptt_cancel_discards_recording_and_returns_to_idle():
    app, pasted, tray, _ = make()
    app.on_ptt_start(); app.on_ptt_cancel(); app.dictation.join()
    assert pasted == [] and tray.states[-1] == "idle"


def test_indicator_hidden_before_paste():
    seen = []
    tray = FakeTray()
    app = App(Config(), engine=FakeEngine(), recorder=FakeRecorder(AUDIO), speaker=FakeSpeaker(),
              tray=tray, paste=lambda t: seen.append(tray.states[-1]),
              copy_selection=lambda: "")
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert seen == ["idle"]


def test_app_uses_live_phrase_lists_from_config():
    pasted = []
    cfg = Config(backtrack_phrases=["oops"])
    app = App(cfg, engine=FakeEngine(text="Keep this. Drop me. Oops."), recorder=FakeRecorder(AUDIO),
              speaker=FakeSpeaker(), tray=FakeTray(), paste=pasted.append, copy_selection=lambda: "")
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted == ["Keep this."]
    app.config = Config(backtrack_phrases=[])  # settings changed at runtime
    app.on_ptt_start(); app.on_ptt_stop(); app.dictation.join()
    assert pasted[-1] == "Keep this. Drop me. Oops."
