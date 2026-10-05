import numpy as np
from faster_whisper import WhisperModel


def _pick_device() -> tuple[str, str]:
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


class Engine:
    def __init__(self, model_name: str = "small.en", device: str = "auto"):
        if device == "auto":
            device, compute = _pick_device()
        else:
            compute = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(model_name, device=device, compute_type=compute)

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio.astype(np.float32),
            language="en",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
