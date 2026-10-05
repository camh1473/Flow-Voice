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


class _FakeSegment:
    text = " ok "


class _FakeModel:
    def __init__(self, name, device, compute_type):
        self.device = device

    def transcribe(self, audio, **kw):
        if self.device == "cuda":
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
        return [_FakeSegment()], None


def test_cuda_failure_falls_back_to_cpu(monkeypatch):
    import flowvoice.engine as eng
    monkeypatch.setattr(eng, "_pick_device", lambda: ("cuda", "float16"))
    e = eng.Engine("tiny.en", model_factory=_FakeModel)
    assert e.transcribe(np.zeros(100, dtype=np.float32)) == "ok"
    assert e.device == "cpu"
