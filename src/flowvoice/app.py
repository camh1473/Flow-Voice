import time
from datetime import datetime

from flowvoice.cleanup import clean
from flowvoice.config import Config
from flowvoice.history import History, HistoryEntry, active_app_name
from flowvoice.inject import copy_selection as _copy_selection
from flowvoice.inject import paste_text
from flowvoice.pipeline import Dictation
from flowvoice.talkmode import TalkMode
from flowvoice.ui_api import Ui


class App:
    """Wires key/pill events, the recorder, the dictation pipeline, history and the UI."""

    def __init__(self, config: Config, *, engine, recorder, speaker, ui: Ui,
                 history: History | None = None, paste=paste_text,
                 copy_selection=_copy_selection, active_app=active_app_name,
                 clock=time.monotonic):
        self.config = config
        self.recorder = recorder
        self.speaker = speaker
        self.ui = ui
        self.history = history
        self._copy_selection = copy_selection
        self._paste = paste
        self._active_app = active_app
        self._recording = False
        self._tag = ""
        self.dictation = Dictation(engine.transcribe, self._clean, self._paste_text,
                                   on_error=ui.notify, on_done=self._on_done,
                                   on_result=self._on_result)
        self.talk = TalkMode(self.on_ptt_start, self.on_ptt_stop, self.on_ptt_cancel,
                             clock=clock, hands_free=config.hands_free,
                             silence_stop_seconds=config.silence_stop_seconds)
        recorder.on_level = self.on_level

    def press(self) -> None:
        self.talk.press()

    def release(self) -> None:
        self.talk.release()

    def other_key(self, name: str) -> None:
        self.talk.other_key(name)

    def click(self) -> None:
        self.talk.click()

    def tick(self) -> None:
        self.talk.tick()

    def on_level(self, level: float) -> None:
        """Called from the audio thread: must never raise."""
        try:
            self.ui.set_level(level)
        except Exception:
            pass
        try:
            self.talk.level(level)
        except Exception:
            pass

    def apply_config(self, cfg: Config) -> None:
        self.config = cfg
        self.talk.hands_free = cfg.hands_free
        self.talk.silence_stop_seconds = cfg.silence_stop_seconds

    def on_ptt_start(self) -> None:
        self._recording = True
        self._tag = self._active_app()
        self.ui.set_state("recording")
        self.recorder.start()

    def on_ptt_stop(self) -> None:
        self._recording = False
        audio = self.recorder.stop()
        if audio is None:
            self.ui.set_state("idle")
            return
        self.ui.set_state("processing")
        self.dictation.submit(audio, self._tag)

    def _clean(self, text: str) -> str:
        cfg = self.config
        return clean(text, fillers=cfg.filler_phrases, backtracks=cfg.backtrack_phrases,
                     commands=cfg.command_phrases if cfg.voice_commands else None)

    def on_ptt_cancel(self) -> None:
        self._recording = False
        self.recorder.stop()
        self.ui.set_state("idle")

    def _paste_text(self, text: str) -> None:
        if not self._recording:  # a newer take keeps its recording pill (non-activating)
            self.ui.set_state("idle")  # hide the badge so it can never take focus from the paste
        self._paste(text)

    def _on_result(self, raw: str, clean_text: str, tag) -> None:
        """Runs on the worker after the paste: history trouble must never propagate."""
        app_name = tag or ""
        entry = None
        if self.config.save_history and self.history is not None:
            try:
                entry = self.history.add(raw, clean_text, app_name)
            except Exception:
                try:
                    self.ui.notify("History unavailable")
                except Exception:
                    pass
        if entry is None:
            entry = HistoryEntry(None, datetime.now().isoformat(timespec="seconds"),
                                 raw, clean_text, app_name)
        try:
            self.ui.add_history(entry)
        except Exception:
            pass

    def on_tts_trigger(self) -> None:
        if self.speaker.is_speaking():
            self.speaker.stop()
            return
        self.speaker.speak(self._copy_selection())

    def _on_done(self) -> None:
        self.ui.set_state("recording" if self._recording else "idle")
