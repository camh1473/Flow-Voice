import queue
import threading
from typing import Callable

import numpy as np


class Dictation:
    """Serial background pipeline: audio -> transcribe -> clean -> paste."""

    def __init__(self, transcribe: Callable[[np.ndarray], str], clean: Callable[[str], str],
                 paste: Callable[[str], None], on_error: Callable[[str], None]):
        self._transcribe, self._clean = transcribe, clean
        self._paste, self._on_error = paste, on_error
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, audio: np.ndarray | None) -> None:
        if audio is not None:
            self._q.put(audio)

    def join(self, timeout: float = 5.0) -> None:
        done = threading.Event()
        self._q.put(done)
        done.wait(timeout)

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if isinstance(item, threading.Event):
                item.set()
                continue
            try:
                text = self._clean(self._transcribe(item))
                if text.strip():
                    self._paste(text)
            except Exception as e:
                self._on_error(f"Dictation failed: {e}")
