from collections import deque

import numpy as np
import sounddevice

SAMPLE_RATE = 16000


class Recorder:
    """Always-on mic stream with a rolling pre-roll; start()/stop() delimit a take."""

    def __init__(self, device: int | None = None, preroll_ms: int = 300,
                 min_ms: int = 250, stream_factory=sounddevice.InputStream):
        self._device = device
        self._preroll = SAMPLE_RATE * preroll_ms // 1000
        self._min = SAMPLE_RATE * min_ms // 1000
        self._factory = stream_factory
        self._stream = None
        self._ring: deque[np.ndarray] = deque()
        self._ring_len = 0
        self._take: list[np.ndarray] = []
        self._recording = False
        self._recorded = 0

    def open(self) -> None:
        self._stream = self._factory(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                     device=self._device, callback=self._on_audio)
        self._stream.start()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def start(self) -> None:
        self._take = list(self._ring)
        self._ring.clear()
        self._ring_len = 0
        self._recorded = 0
        self._recording = True

    def stop(self) -> np.ndarray | None:
        if not self._recording:
            return None
        self._recording = False
        take, self._take = self._take, []
        if self._recorded < self._min:
            return None
        return np.concatenate(take) if take else None

    def _on_audio(self, indata, frames, time, status) -> None:
        mono = np.array(indata[:, 0], dtype=np.float32, copy=True)
        if self._recording:
            self._take.append(mono)
            self._recorded += len(mono)
            return
        self._ring.append(mono)
        self._ring_len += len(mono)
        while self._ring_len - len(self._ring[0]) >= self._preroll:
            self._ring_len -= len(self._ring.popleft())
