import sys

import pytest

from flowvoice.singleinstance import SingleInstance


class FakeOs:
    """Stands in for the mutex API: `owner` holds the name until it lets go."""

    def __init__(self):
        self.owned = set()
        self.closed = []
        self.next_handle = 1

    def create(self, name):
        handle = self.next_handle
        self.next_handle += 1
        existed = name in self.owned
        self.owned.add(name)
        return handle, existed

    def close(self, handle):
        self.closed.append(handle)


def test_first_instance_gets_the_lock():
    os_ = FakeOs()
    a = SingleInstance("x", create=os_.create, close=os_.close)
    assert a.acquire() is True and a.held


def test_second_instance_is_refused_and_its_handle_closed():
    os_ = FakeOs()
    a = SingleInstance("x", create=os_.create, close=os_.close)
    b = SingleInstance("x", create=os_.create, close=os_.close)
    assert a.acquire() is True
    assert b.acquire() is False and not b.held
    assert os_.closed == [2]


def test_wait_retries_until_the_old_copy_lets_go():
    os_ = FakeOs()
    a = SingleInstance("x", create=os_.create, close=os_.close)
    b = SingleInstance("x", create=os_.create, close=os_.close)
    a.acquire()
    now = [0.0]
    attempts = []

    def sleep(seconds):
        attempts.append(seconds)
        now[0] += seconds
        if len(attempts) == 3:
            os_.owned.discard("x")  # the old copy released it

    assert b.acquire(wait=5.0, sleep=sleep, clock=lambda: now[0]) is True
    assert len(attempts) == 3


def test_wait_gives_up_after_the_deadline():
    os_ = FakeOs()
    SingleInstance("x", create=os_.create, close=os_.close).acquire()
    b = SingleInstance("x", create=os_.create, close=os_.close)
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    assert b.acquire(wait=1.0, sleep=sleep, clock=lambda: now[0]) is False
    assert now[0] >= 1.0


def test_release_is_idempotent():
    os_ = FakeOs()
    a = SingleInstance("x", create=os_.create, close=os_.close)
    a.acquire()
    a.release()
    a.release()
    assert os_.closed == [1] and not a.held


def test_fails_open_when_the_mutex_cannot_be_created():
    def broken(name):
        raise OSError("no kernel32")

    assert SingleInstance("x", create=broken).acquire() is True
    assert SingleInstance("x", create=lambda n: (None, False)).acquire() is True


@pytest.mark.skipif(sys.platform != "win32", reason="named mutexes are Windows only")
def test_real_windows_mutex_blocks_a_second_holder():
    name = "Local\\FlowVoice.Test.SingleInstance.%d" % id(object())
    a, b = SingleInstance(name), SingleInstance(name)
    assert a.acquire() is True
    assert b.acquire() is False
    a.release()
    assert b.acquire() is True
    b.release()
