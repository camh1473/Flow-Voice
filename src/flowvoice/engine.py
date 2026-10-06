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
    """Local Whisper. Uses CUDA when it works, otherwise falls back to CPU automatically."""

    def __init__(self, model_name: str = "small.en", device: str = "auto",
                 model_factory=WhisperModel):
        if device == "auto":
            device, compute = _pick_device()
        else:
            compute = "float16" if device == "cuda" else "int8"
        self._name = model_name
        self._factory = model_factory
        self.device = device
        try:
            self._model = self._factory(self._name, device=device, compute_type=compute)
        except Exception:
            if device != "cuda":
                raise
            self._fall_back_to_cpu()

    def _fall_back_to_cpu(self) -> None:
        self.device = "cpu"
        self._model = self._factory(self._name, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        audio = audio.astype(np.float32)
        try:
            return self._run(audio, initial_prompt)
        except RuntimeError:
            if self.device != "cuda":
                raise
            self._fall_back_to_cpu()
            return self._run(audio, initial_prompt)

    def _run(self, audio: np.ndarray, initial_prompt: str | None) -> str:
        options = {}
        if initial_prompt:
            options["initial_prompt"] = initial_prompt
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
            **options,
        )
        return " ".join(s.text.strip() for s in segments).strip()
