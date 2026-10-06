import queue
import threading
from typing import Callable

_ASYNC = 1
_PURGE = 2


def _sapi_voice():
    import win32com.client
    return win32com.client.Dispatch("SAPI.SpVoice")


def _co_init() -> None:
    import pythoncom
    pythoncom.CoInitialize()


def _co_uninit() -> None:
    import pythoncom
    pythoncom.CoUninitialize()


class Speaker:
    """Windows SAPI text-to-speech, owned by one dedicated worker thread.

    SAPI is a COM object: COM must be initialised on the thread that creates and uses it.
    The app asks for speech from short-lived threads (hotkey callbacks), where creating the
    voice failed with "CoInitialize has not been called", so every call is forwarded to a
    single long-lived worker that initialises COM once and owns the voice. Failures are
    reported through `on_error` instead of disappearing inside a daemon thread.
    """

    def __init__(self, voice_factory: Callable[[], object] = _sapi_voice, *,
                 init_com: Callable[[], None] = _co_init,
                 uninit_com: Callable[[], None] = _co_uninit,
                 on_error: Callable[[str], None] | None = None,
                 ask_timeout: float = 1.0):
        self._factory = voice_factory
        self._init_com, self._uninit_com = init_com, uninit_com
        self._on_error = on_error
        self._ask_timeout = ask_timeout
        self._voice = None
        self._jobs: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()

    # ----- public API (safe to call from any thread) -----

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._submit(lambda: self._v().Speak(text, _ASYNC | _PURGE))

    def stop(self) -> None:
        self._submit(lambda: self._v().Speak("", _PURGE))

    def is_speaking(self) -> bool:
        def check() -> bool:
            return self._voice is not None and not self._voice.WaitUntilDone(0)
        return bool(self._ask(check, default=False))

    def toggle(self, text: str) -> None:
        if self.is_speaking():
            self.stop()
        else:
            self.speak(text)

    def flush(self, timeout: float = 5.0) -> None:
        """Wait until everything submitted so far has run (tests, orderly shutdown)."""
        self._ask(lambda: None, default=None, timeout=timeout)

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._jobs.put(None)
        thread.join(2.0)
        self._thread = None

    # ----- worker -----

    def _v(self):
        if self._voice is None:
            self._voice = self._factory()
        return self._voice

    def _ensure_worker(self) -> None:
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="flowvoice-tts",
                                                daemon=True)
                self._thread.start()

    def _submit(self, job: Callable[[], object]) -> None:
        self._ensure_worker()
        self._jobs.put((job, None))

    def _ask(self, job: Callable[[], object], default, timeout: float | None = None):
        self._ensure_worker()
        box: queue.Queue = queue.Queue(maxsize=1)
        self._jobs.put((job, box))
        try:
            ok, value = box.get(timeout=self._ask_timeout if timeout is None else timeout)
        except queue.Empty:
            return default
        return value if ok else default

    def _run(self) -> None:
        try:
            self._init_com()
        except Exception as e:
            self._report(e)
        try:
            while True:
                item = self._jobs.get()
                if item is None:
                    break
                job, box = item
                try:
                    value = job()
                    result = (True, value)
                except Exception as e:
                    self._report(e)
                    result = (False, None)
                if box is not None:
                    box.put(result)
        finally:
            try:
                self._uninit_com()
            except Exception:
                pass

    def _report(self, error: Exception) -> None:
        if self._on_error is None:
            return
        try:
            self._on_error(f"Read aloud failed: {error}")
        except Exception:
            pass
