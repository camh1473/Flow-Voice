import numpy as np
import pytest

from flowvoice.recorder import Recorder

SR = 16000


def chunk(ms):
    return np.full((SR * ms // 1000, 1), 0.1, dtype=np.float32)


def feed(rec, total_ms, step=100):
    for _ in range(total_ms // step):
        rec._on_audio(chunk(step), SR * step // 1000, None, None)


def test_tap_shorter_than_min_returns_none():
    r = Recorder()
    r.start()
    feed(r, 100)
    assert r.stop() is None


def test_long_recording_returned():
    r = Recorder()
    r.start()
    feed(r, 1000)
    audio = r.stop()
    assert audio.dtype == np.float32 and audio.ndim == 1
    assert len(audio) >= SR


def test_preroll_included():
    r = Recorder()
    feed(r, 300)
    r.start()
    feed(r, 500)
    assert len(r.stop()) >= 12800


def test_audio_before_start_not_kept_beyond_preroll():
    r = Recorder()
    feed(r, 2000)
    r.start()
    feed(r, 500)
    assert len(r.stop()) <= 12800 + 1600


def test_audio_ignored_when_not_recording_and_stop_without_start():
    r = Recorder()
    assert r.stop() is None


def level_chunk(value, ms=100):
    return np.full((SR * ms // 1000, 1), value, dtype=np.float32)


def test_level_reported_while_recording():
    levels = []
    r = Recorder()
    r.on_level = levels.append
    r.start()
    r._on_audio(level_chunk(0.01), 1600, None, None)
    assert levels == [pytest.approx(0.1, abs=1e-3)]


def test_level_clamped_to_one():
    levels = []
    r = Recorder()
    r.on_level = levels.append
    r.start()
    r._on_audio(level_chunk(0.5), 1600, None, None)
    assert levels == [1.0]


def test_no_level_when_not_recording():
    levels = []
    r = Recorder()
    r.on_level = levels.append
    r._on_audio(level_chunk(0.5), 1600, None, None)
    assert levels == []


def test_on_level_none_is_fine():
    r = Recorder()
    assert r.on_level is None
    r.start()
    feed(r, 300)
    assert r.stop() is not None


def test_on_level_exception_does_not_break_recording():
    def boom(level):
        raise RuntimeError("ui gone")

    r = Recorder()
    r.on_level = boom
    r.start()
    feed(r, 1000)
    assert len(r.stop()) >= SR
