import threading
import time

from flowvoice.tts import Speaker


class FakeVoice:
    """Records which thread touched it, like SAPI, which needs COM on the calling thread."""

    def __init__(self):
        self.calls = []
        self.threads = set()
        self.busy = False

    def Speak(self, text, flags):
        self.threads.add(threading.get_ident())
        self.calls.append((text, flags))
        self.busy = bool(text)

    def WaitUntilDone(self, ms):
        self.threads.add(threading.get_ident())
        return not self.busy


def make(voice=None, **kw):
    v = voice or FakeVoice()
    com = []
    s = Speaker(lambda: v, init_com=lambda: com.append(("init", threading.get_ident())),
                uninit_com=lambda: com.append(("uninit", threading.get_ident())), **kw)
    return s, v, com


def test_speak_calls_async_with_purge():
    s, v, _ = make()
    s.speak("hi")
    s.flush()
    assert v.calls == [("hi", 1 | 2)]
    s.close()


def test_empty_text_noop():
    s, v, _ = make()
    s.speak("  ")
    s.flush()
    assert v.calls == []
    s.close()


def test_toggle_stops_when_speaking():
    s, v, _ = make()
    s.toggle("hello")
    s.flush()
    assert s.is_speaking()
    s.toggle("hello")
    s.flush()
    assert v.calls[-1] == ("", 2)
    assert not s.is_speaking()
    s.close()


def test_voice_is_only_touched_on_one_com_initialised_worker_thread():
    # Manual test 33: SAPI.SpVoice was created on a fresh thread per hotkey press and failed
    # with "CoInitialize has not been called". Whichever thread asks, one dedicated worker
    # that initialised COM must own the voice.
    s, v, com = make()
    callers = []

    def ask():
        callers.append(threading.get_ident())
        s.speak("from a plain thread")
        s.flush()
        s.is_speaking()

    for _ in range(3):
        t = threading.Thread(target=ask)
        t.start()
        t.join()
    s.speak("from the main thread")
    s.flush()
    assert len(v.threads) == 1
    worker = next(iter(v.threads))
    assert worker != threading.get_ident() and worker not in callers
    assert ("init", worker) in com
    s.close()
    assert ("uninit", worker) in com


def test_a_voice_factory_failure_is_reported_and_the_next_call_still_works():
    v = FakeVoice()
    attempts = []
    errors = []

    def factory():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("no speech engine")
        return v

    s = Speaker(factory, init_com=lambda: None, uninit_com=lambda: None, on_error=errors.append)
    s.speak("first")
    s.flush()
    assert len(errors) == 1 and "no speech engine" in errors[0] and "Read aloud" in errors[0]
    s.speak("second")
    s.flush()
    assert v.calls == [("second", 1 | 2)]
    s.close()


def test_is_speaking_is_false_before_any_speech_and_never_hangs():
    gate = threading.Event()

    def stuck_factory():
        gate.wait(5)
        return FakeVoice()

    s = Speaker(stuck_factory, init_com=lambda: None, uninit_com=lambda: None, ask_timeout=0.1)
    s.speak("blocks the worker")
    started = time.monotonic()
    assert s.is_speaking() is False
    assert time.monotonic() - started < 1.0
    gate.set()
    s.close()


def test_close_stops_the_worker_thread():
    s, v, com = make()
    s.speak("x")
    s.flush()
    s.close()
    assert not any(t.name == "flowvoice-tts" and t.is_alive() for t in threading.enumerate())
