from flowvoice.cleanup import clean
from flowvoice.config import Config
from flowvoice.inject import copy_selection as _copy_selection
from flowvoice.inject import paste_text
from flowvoice.pipeline import Dictation


class App:
    def __init__(self, config: Config, *, engine, recorder, speaker, tray,
                 paste=paste_text, copy_selection=_copy_selection):
        self.config = config
        self.recorder = recorder
        self.speaker = speaker
        self.tray = tray
        self._copy_selection = copy_selection
        self._paste = paste
        self._recording = False
        self.dictation = Dictation(engine.transcribe, self._clean, self._paste_text,
                                   on_error=tray.notify, on_done=self._on_done)

    def on_ptt_start(self) -> None:
        self._recording = True
        self.tray.set_state("recording")
        self.recorder.start()

    def on_ptt_stop(self) -> None:
        self._recording = False
        audio = self.recorder.stop()
        if audio is None:
            self.tray.set_state("idle")
            return
        self.tray.set_state("processing")
        self.dictation.submit(audio)

    def _clean(self, text: str) -> str:
        return clean(text, fillers=self.config.filler_phrases,
                     backtracks=self.config.backtrack_phrases)

    def on_ptt_cancel(self) -> None:
        self._recording = False
        self.recorder.stop()
        self.tray.set_state("idle")

    def _paste_text(self, text: str) -> None:
        self.tray.set_state("idle")  # hide the badge so it can never take focus from the paste
        self._paste(text)

    def on_tts_trigger(self) -> None:
        if self.speaker.is_speaking():
            self.speaker.stop()
            return
        self.speaker.speak(self._copy_selection())

    def _on_done(self) -> None:
        if not self._recording:
            self.tray.set_state("idle")
