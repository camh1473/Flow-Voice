from typing import Callable

import win32com.client

_ASYNC = 1
_PURGE = 2


class Speaker:
    def __init__(self, voice_factory: Callable[[], object] = lambda: win32com.client.Dispatch("SAPI.SpVoice")):
        self._factory = voice_factory
        self._voice = None

    def _v(self):
        if self._voice is None:
            self._voice = self._factory()
        return self._voice

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._v().Speak(text, _ASYNC | _PURGE)

    def stop(self) -> None:
        self._v().Speak("", _PURGE)

    def is_speaking(self) -> bool:
        return self._voice is not None and not self._voice.WaitUntilDone(0)

    def toggle(self, text: str) -> None:
        if self.is_speaking():
            self.stop()
        else:
            self.speak(text)
