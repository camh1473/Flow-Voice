import queue
import threading
from typing import Callable

import numpy as np


class Dictation:
    """Serial background pipeline: audio -> transcribe -> clean -> paste."""

    def __init__(self, transcribe: Callable[[np.ndarray], str], clean: Callable[[str], str],
                 paste: Callable[[str], None], on_error: Callable[[str], None],
                 on_done: Callable[[], None] = lambda: None,
                 on_result: Callable[[str, str, object], None] = lambda raw, clean, tag: None):
        self._transcribe, self._clean = transcribe, clean
        self._paste, self._on_error, self._on_done = paste, on_error, on_done
        self._on_result = on_result
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, audio: np.ndarray | None, tag: object = None) -> None:
        if audio is not None:
            self._q.put((audio, tag))

    def join(self, timeout: float = 5.0) -> None:
        done = threading.Event()
        self._q.put(done)
        done.wait(timeout)

    def _notify_result(self, raw: str, text: str, tag: object) -> None:
        try:
            self._on_result(raw, text, tag)
        except Exception as e:
            try:
                self._on_error(f"Result handler failed: {e}")
            except Exception:
                pass

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if isinstance(item, threading.Event):
                item.set()
                continue
            audio, tag = item
            try:
                raw = self._transcribe(audio)
                text = self._clean(raw)
                if text.strip():
                    self._paste(text)
                    self._notify_result(raw, text, tag)
            except Exception as e:
                self._on_error(f"Dictation failed: {e}")
            finally:
                self._on_done()
