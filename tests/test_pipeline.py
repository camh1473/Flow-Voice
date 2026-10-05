import threading
import time

import numpy as np

from flowvoice.pipeline import Dictation


def make(transcribe, pasted, errors, clean=lambda t: t.strip()):
    return Dictation(transcribe, clean, pasted.append, errors.append)


def test_pastes_cleaned_transcript():
    out, err = [], []
    d = make(lambda a: " um hello ", out, err, clean=lambda t: "Hello")
    d.submit(np.ones(10, dtype=np.float32)); d.join()
    assert out == ["Hello"] and err == []


def test_empty_transcript_pastes_nothing():
    out, err = [], []
    d = make(lambda a: "   ", out, err)
    d.submit(np.ones(10, dtype=np.float32)); d.join()
    assert out == []


def test_none_audio_ignored():
    out, err = [], []
    called = []
    d = make(lambda a: called.append(1) or "x", out, err)
    d.submit(None); d.join()
    assert out == [] and called == []


def test_overlapping_submissions_run_serially_in_order():
    out, err = [], []
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def slow(audio):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.1)
        with lock:
            state["now"] -= 1
        return str(int(audio[0]))

    d = make(slow, out, err)
    for i in range(3):
        d.submit(np.array([i], dtype=np.float32))
    d.join()
    assert state["max"] == 1 and out == ["0", "1", "2"]


def test_transcribe_error_reports_and_continues():
    out, err = [], []

    def flaky(audio):
        if audio[0] == 0:
            raise RuntimeError("boom")
        return "ok"

    d = make(flaky, out, err)
    d.submit(np.array([0], dtype=np.float32))
    d.submit(np.array([1], dtype=np.float32))
    d.join()
    assert out == ["ok"] and len(err) == 1 and "boom" in err[0]
