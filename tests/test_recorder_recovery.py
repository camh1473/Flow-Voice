import numpy as np

from flowvoice import recorder as rec_mod
from flowvoice.recorder import STALL_SECONDS, Recorder

SR = 16000


class FakeStream:
    def __init__(self, fail_start=False):
        self.active = True
        self.started = self.stopped = self.closed = False
        self.fail_start = fail_start

    def start(self):
        if self.fail_start:
            raise OSError("device unavailable")
        self.started = True

    def stop(self):
        self.stopped = True
        self.active = False

    def close(self):
        self.closed = True


class Devices:
    """A mutable fake of sounddevice.query_devices."""

    def __init__(self, devices):
        self.devices = list(devices)  # (name, inputs, hostapi); a copy, tests mutate it

    def info(self, i):
        name, inputs, hostapi = self.devices[i]
        return {"name": name, "max_input_channels": inputs, "hostapi": hostapi}

    def __call__(self, device=None, kind=None):
        if device is None and kind is None:
            return [self.info(i) for i in range(len(self.devices))]
        if device is None:
            for i, d in enumerate(self.devices):
                if d[1] > 0:
                    return self.info(i)
            raise ValueError("no default")
        if device >= len(self.devices) or self.devices[device][1] == 0:
            raise ValueError("bad device")
        return self.info(device)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(devices, device=1, fail=None):
    """Recorder whose factory hands out FakeStreams; `fail` = set of device ids that cannot open."""
    clock = Clock()
    streams = []
    fail = fail if fail is not None else set()

    def factory(**kw):
        s = FakeStream(fail_start=kw["device"] in fail)
        s.device = kw["device"]
        streams.append(s)
        return s

    r = Recorder(device=device, stream_factory=factory, query_device=Devices(devices), clock=clock)
    return r, streams, clock


MICS = [("Sound Mapper", 2, 0), ("Razer Mic", 1, 0), ("Steam Mic", 8, 0), ("Speakers", 0, 0)]


def feed(r, ms=100):
    r._on_audio(np.full((SR * ms // 1000, 1), 0.1, dtype=np.float32), 0, None, None)


def test_fresh_stream_is_healthy():
    r, _, _ = make(MICS)
    r.open()
    assert r.healthy()


def test_not_open_is_not_healthy():
    r, _, _ = make(MICS)
    assert not r.healthy()


def test_stream_that_stopped_is_unhealthy():
    r, streams, _ = make(MICS)
    r.open()
    streams[0].active = False
    assert not r.healthy()


def test_stream_that_stops_delivering_audio_is_unhealthy_until_audio_returns():
    r, _, clock = make(MICS)
    r.open()
    clock.t += STALL_SECONDS + 1
    assert not r.healthy()
    feed(r)
    assert r.healthy()


def test_index_that_now_means_a_different_mic_is_unhealthy():
    devices = list(MICS)
    r, _, _ = make(devices)
    r.open()
    cfg = r._query
    cfg.devices[1] = ("Some Other Mic", 1, 0)
    assert not r.healthy()


def test_default_device_is_not_name_checked():
    r, _, _ = make(MICS, device=None)
    r.open()
    r._query.devices[0] = ("Renamed Default", 2, 0)
    assert r.healthy()


def test_reopen_same_index_when_the_mic_is_still_there():
    r, streams, _ = make(MICS)
    r.open()
    assert r.reopen() == "same"
    assert streams[0].closed and streams[1].device == 1 and r.healthy()


def test_reopen_follows_the_mic_to_its_new_index():
    r, streams, _ = make(MICS)
    r.open()
    r._query.devices.insert(1, ("New Device", 1, 0))  # Razer Mic is now index 2
    assert r.reopen() == "same"
    assert streams[-1].device == 2


def test_reopen_falls_back_to_default_when_the_mic_is_gone():
    r, streams, _ = make(MICS)
    r.open()
    r._query.devices[1] = ("Unplugged", 0, 0)
    assert r.reopen() == "default"
    assert streams[-1].device is None and r.device is None
    assert r.healthy()


def test_reopen_falls_back_when_opening_the_found_mic_fails():
    r, streams, _ = make(MICS)
    r.open()
    original = r._factory

    def factory(**kw):
        if kw["device"] == 1:
            raise OSError("busy")
        return original(**kw)

    r._factory = factory
    assert r.reopen() == "default"


def test_reopen_reports_failed_and_never_raises():
    r, _, _ = make(MICS, fail={1, None})
    r._device = 1
    r._wanted = {"name": "Razer Mic", "hostapi": 0}
    assert r.reopen() == "failed"
    assert not r.healthy()


def test_close_error_does_not_stop_reopen():
    r, streams, _ = make(MICS)
    r.open()

    def bad_stop():
        raise OSError("already gone")

    streams[0].stop = bad_stop
    assert r.reopen() == "same"


def test_reopen_keeps_a_take_in_progress():
    r, _, _ = make(MICS)
    r.open()
    r.start()
    feed(r, 400)
    r.reopen()
    feed(r, 400)
    audio = r.stop()
    assert audio is not None and len(audio) >= SR * 800 // 1000


def test_audio_callback_never_raises_and_keeps_working():
    r, _, _ = make(MICS)
    r.start()
    r._on_audio(None, 0, None, None)  # garbage chunk
    r._on_audio(np.zeros((0, 0), dtype=np.float32), 0, None, None)
    feed(r, 400)
    assert r.stop() is not None
    assert r._callback_failures >= 1


def test_find_by_name_prefers_same_host_api():
    q = Devices([("Mic", 1, 0), ("Mic", 1, 1), ("Other", 1, 1)])
    assert rec_mod._find_by_name("Mic", 1, q) == 1
    assert rec_mod._find_by_name("Mic", 5, q) == 0
    assert rec_mod._find_by_name("Nope", 0, q) is None
