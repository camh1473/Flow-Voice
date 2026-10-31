"""Only one Flow Voice per Windows session.

Two copies both hook the keyboard, so every dictation was transcribed and pasted twice (and
each holds its own ~600 MB speech model). A named mutex is released by Windows if the process
dies, so a crash never leaves a stale lock behind.
"""
import ctypes
import time
from typing import Callable

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\FlowVoice.SingleInstance"


def _win_create(name: str):
    """CreateMutexW -> (handle, already_existed)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, name)
    return handle, ctypes.get_last_error() == ERROR_ALREADY_EXISTS


def _win_close(handle) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle(handle)


class SingleInstance:
    def __init__(self, name: str = MUTEX_NAME, *, create: Callable = _win_create,
                 close: Callable = _win_close) -> None:
        self._name, self._create, self._close = name, create, close
        self._handle = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self, wait: float = 0.0, *, sleep: Callable[[float], None] = time.sleep,
                clock: Callable[[], float] = time.monotonic) -> bool:
        """True if this process now owns the lock. `wait` retries (a restart waits for the old copy).

        If the mutex cannot be created at all we fail open: a broken lock must not stop dictation.
        """
        deadline = clock() + wait
        while True:
            try:
                handle, existed = self._create(self._name)
            except Exception:
                return True
            if not handle:
                return True
            if not existed:
                self._handle = handle
                return True
            self._close(handle)
            if clock() >= deadline:
                return False
            sleep(0.2)

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                self._close(handle)
            except Exception:
                pass
