import logging
import threading
import time
from collections import deque
from typing import Callable

import numpy as np
import sounddevice

SAMPLE_RATE = 16000
STALL_SECONDS = 3.0  # an open stream that delivers no audio for this long is dead

log = logging.getLogger("flowvoice.recorder")


def _device_info(device: int | None, query=sounddevice.query_devices) -> dict | None:
    """Info for input device `device` (None = system default), or None when it is gone."""
    try:
        info = query(device, "input") if device is not None else query(kind="input")
        return {"name": str(info["name"]), "hostapi": info.get("hostapi")}
    except Exception:
        return None


def _find_by_name(name: str, hostapi, query=sounddevice.query_devices) -> int | None:
    """Index of the input device called `name` (same host API first), or None."""
    try:
        matches = [(i, d) for i, d in enumerate(query())
                   if d["max_input_channels"] > 0 and str(d["name"]) == name]
    except Exception:
        return None
    for i, d in matches:
        if d.get("hostapi") == hostapi:
            return i
    return matches[0][0] if matches else None


class Recorder:
    """Always-on mic stream with a rolling pre-roll; start()/stop() delimit a take.

    A stream can die without any error reaching us (sleep/resume, a USB mic unplugged, a
    driver reset) and a device index can start to mean another device. `healthy()` notices
    both and `reopen()` rebuilds the stream, falling back to the system default mic.
    """

    def __init__(self, device: int | None = None, preroll_ms: int = 300,
                 min_ms: int = 250, stream_factory=sounddevice.InputStream,
                 query_device: Callable = sounddevice.query_devices,
                 clock: Callable[[], float] = time.monotonic):
        self._device = device
        self._preroll = SAMPLE_RATE * preroll_ms // 1000
        self._min = SAMPLE_RATE * min_ms // 1000
        self._factory = stream_factory
        self._query = query_device
        self._clock = clock
        self._stream = None
        self._stream_lock = threading.Lock()
        self._ring: deque[np.ndarray] = deque()
        self._ring_len = 0
        self._take: list[np.ndarray] = []
        self._recording = False
        self._recorded = 0
        self._last_audio = clock()
        self._wanted: dict | None = None  # name + host API of the chosen mic, kept across reopens
        self._callback_failures = 0
        self.on_level: Callable[[float], None] | None = None

    @property
    def device(self) -> int | None:
        return self._device

    def open(self) -> None:
        with self._stream_lock:
            self._open_locked(self._device)

    def _open_locked(self, device: int | None) -> None:
        stream = self._factory(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                               device=device, callback=self._on_audio)
        stream.start()
        self._stream = stream
        self._device = device
        self._last_audio = self._clock()
        info = _device_info(device, self._query)
        if device is not None and self._wanted is None:
            self._wanted = info
        log.info("mic open device=%s name=%s", device, info and info["name"])

    def close(self) -> None:
        with self._stream_lock:
            self._close_locked()

    def _close_locked(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
        finally:
            stream.close()

    def healthy(self) -> bool:
        """Is the mic stream open, delivering audio, and still the device we opened?"""
        stream = self._stream
        if stream is None:
            return False
        if not getattr(stream, "active", True):
            return False
        if self._clock() - self._last_audio > STALL_SECONDS:
            return False
        if self._device is not None and self._wanted is not None:
            now = _device_info(self._device, self._query)
            if now is not None and now["name"] != self._wanted["name"]:
                return False  # the index now points at a different device
        return True

    def reopen(self) -> str:
        """Rebuild the stream. Returns 'same', 'default' (fell back) or 'failed'. Never raises."""
        with self._stream_lock:
            try:
                self._close_locked()
            except Exception:
                log.exception("mic close failed during reopen")
            candidates: list[tuple[int | None, str]] = []
            if self._wanted is not None:
                # The chosen mic by name: its index may have moved since it was picked.
                found = _find_by_name(self._wanted["name"], self._wanted["hostapi"], self._query)
                if found is not None:
                    candidates.append((found, "same"))
                candidates.append((None, "default"))
            else:
                candidates.append((self._device, "same"))
            for device, outcome in candidates:
                try:
                    self._open_locked(device)
                    return outcome
                except Exception:
                    log.exception("mic reopen failed device=%s", device)
            self._stream = None
            return "failed"

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

    def _report_level(self, mono: np.ndarray) -> None:
        callback = self.on_level
        if callback is None or not len(mono):
            return
        try:
            callback(min(1.0, float(np.sqrt(np.mean(np.square(mono)))) * 10))
        except Exception:
            pass

    def _on_audio(self, indata, frames, time_info, status) -> None:
        """PortAudio callback. An exception here would make PortAudio abort the stream
        silently, so nothing may escape: a bad chunk is dropped and logged once."""
        try:
            self._last_audio = self._clock()
            mono = np.array(indata[:, 0], dtype=np.float32, copy=True)
            if self._recording:
                self._take.append(mono)
                self._recorded += len(mono)
                self._report_level(mono)
                return
            self._ring.append(mono)
            self._ring_len += len(mono)
            while self._ring_len - len(self._ring[0]) >= self._preroll:
                self._ring_len -= len(self._ring.popleft())
        except Exception:
            self._callback_failures += 1
            if self._callback_failures == 1:
                log.exception("audio callback failed (further failures not logged)")
