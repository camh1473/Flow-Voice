import wave
from pathlib import Path

import numpy as np
import pytest

from flowvoice.engine import Engine

pytestmark = pytest.mark.slow
DATA = Path(__file__).parent / "data" / "hello.wav"


@pytest.fixture(scope="module")
def engine():
    return Engine("tiny.en", device="cpu")


def _load(path):
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def test_transcribes_known_phrase(engine):
    text = engine.transcribe(_load(DATA)).lower()
    assert "hello" in text and "test" in text


def test_silence_returns_empty(engine):
    assert engine.transcribe(np.zeros(32000, dtype=np.float32)) == ""


def test_low_noise_returns_empty(engine):
    rng = np.random.default_rng(0)
    noise = (rng.standard_normal(32000) * 0.005).astype(np.float32)
    assert engine.transcribe(noise) == ""
