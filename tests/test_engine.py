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

def test_construction_failure_on_cuda_falls_back_to_cpu(monkeypatch):
    import flowvoice.engine as eng
    monkeypatch.setattr(eng, "_pick_device", lambda: ("cuda", "float16"))

    def factory(name, device, compute_type):
        if device == "cuda":
            raise RuntimeError("cudnn missing")
        return _FakeModel(name, device, compute_type)

    e = eng.Engine("tiny.en", model_factory=factory)
    assert e.device == "cpu" and e.transcribe(np.zeros(10, dtype=np.float32)) == "ok"


class _RecordingModel:
    """Fake model recording the kwargs of every transcribe call."""
    calls: list = []

    def __init__(self, name, device, compute_type):
        self.device = device

    def transcribe(self, audio, **kw):
        _RecordingModel.calls.append((self.device, kw))
        if self.device == "cuda":
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
        return [_FakeSegment()], None


def _recording_engine(monkeypatch, device="cpu"):
    import flowvoice.engine as eng
    _RecordingModel.calls = []
    monkeypatch.setattr(eng, "_pick_device", lambda: (device, "float16"))
    return eng.Engine("tiny.en", model_factory=_RecordingModel)


def test_initial_prompt_is_passed_through(monkeypatch):
    e = _recording_engine(monkeypatch)
    assert e.transcribe(np.zeros(100, dtype=np.float32), initial_prompt="Perry Homes, Kubota") == "ok"
    kw = _RecordingModel.calls[-1][1]
    assert kw["initial_prompt"] == "Perry Homes, Kubota"
    assert kw["condition_on_previous_text"] is False


@pytest.mark.parametrize("prompt", [None, ""])
def test_no_initial_prompt_kwarg_when_none_or_empty(monkeypatch, prompt):
    e = _recording_engine(monkeypatch)
    e.transcribe(np.zeros(100, dtype=np.float32), initial_prompt=prompt)
    assert "initial_prompt" not in _RecordingModel.calls[-1][1]
    e.transcribe(np.zeros(100, dtype=np.float32))
    assert "initial_prompt" not in _RecordingModel.calls[-1][1]


def test_initial_prompt_passed_again_on_cpu_fallback(monkeypatch):
    e = _recording_engine(monkeypatch, device="cuda")
    assert e.transcribe(np.zeros(100, dtype=np.float32), initial_prompt="Perry Homes") == "ok"
    assert e.device == "cpu"
    assert [c[0] for c in _RecordingModel.calls] == ["cuda", "cpu"]
    assert all(c[1]["initial_prompt"] == "Perry Homes" for c in _RecordingModel.calls)
