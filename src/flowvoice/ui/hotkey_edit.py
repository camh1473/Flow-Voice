"""Click-to-record hotkey field: a background thread reads the next hotkey via `keyboard`."""
import threading
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit

CAPTURE_TEXT = "Press keys..."
CAPTURE_TIMEOUT_MS = 15000
CANCEL_KEYS = ("esc", "escape")
START_KEYS = (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)


def pretty_key(key: str) -> str:
    """'right ctrl' -> 'Right Ctrl', 'ctrl+alt+s' -> 'Ctrl+Alt+S'."""
    return "+".join(part.strip().title() for part in key.split("+"))


def _default_reader(suppress: bool = False) -> str:
    from flowvoice.hotkey import read_hotkey_by_side
    return read_hotkey_by_side(suppress=suppress)


class HotkeyEdit(QLineEdit):
    """Read-only field; click (or Enter/Space) to capture the next hotkey.

    `hotkey()` is the stored `keyboard` name ("right ctrl"); the field shows it title-cased.

    The reader thread never touches widgets: it only emits `_finished(token, hotkey)`,
    which Qt queues to the GUI thread. Stale results (after Escape, a timeout or a newer
    capture) carry an old token and are ignored. Escape, a timeout or a reader failure
    restore the previous value. `capture_started` / `capture_finished` bracket every real
    capture exactly once so the app can pause its global hotkeys meanwhile.
    """

    captured = Signal(str)
    capture_started = Signal()  # once per real capture; the app pauses its global hooks
    capture_finished = Signal()  # once per capture on every exit path (success or cancel)
    _finished = Signal(int, str)

    def __init__(self, parent=None, reader: Callable[..., str] | None = None,
                 timeout_ms: int = CAPTURE_TIMEOUT_MS) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click, then press the new key or combination. Esc cancels.")
        self._reader = reader or _default_reader
        self._hotkey = ""
        self._token = 0
        self._capturing = False
        self._armed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(self.cancel_capture)
        self._finished.connect(self._on_finished, Qt.QueuedConnection)
        self.captured.connect(self._on_captured)

    def hotkey(self) -> str:
        return self._hotkey

    def set_hotkey(self, text: str) -> None:
        self._hotkey = text.strip()
        if not self._capturing:
            self.setText(pretty_key(self._hotkey))

    def is_capturing(self) -> bool:
        return self._capturing

    def begin_capture(self) -> None:
        if self._capturing:
            return
        self._token += 1
        self._capturing = True
        self.setProperty("capturing", "true")
        self._restyle()
        self.setText(CAPTURE_TEXT)
        self._timer.start()
        token = self._token
        self.capture_started.emit()
        try:
            threading.Thread(target=self._read, args=(token,), daemon=True,
                             name="hotkey-capture").start()
        except Exception:
            self.cancel_capture()

    def cancel_capture(self) -> None:
        if self._capturing:
            self._end_capture()

    def _read(self, token: int) -> None:
        try:
            result = self._reader(suppress=False) or ""
        except Exception:
            result = ""
        try:
            self._finished.emit(token, result)
        except RuntimeError:
            pass  # widget already deleted

    def _on_finished(self, token: int, hotkey: str) -> None:
        if token != self._token or not self._capturing:
            return
        hotkey = hotkey.strip()
        if not hotkey or hotkey.lower() in CANCEL_KEYS:
            self._end_capture()
            return
        self.captured.emit(hotkey)

    def _on_captured(self, hotkey: str) -> None:
        self._hotkey = hotkey.strip()
        self._end_capture()

    def _end_capture(self) -> None:
        was_capturing = self._capturing
        self._token += 1
        self._capturing = False
        self._timer.stop()
        self.setProperty("capturing", "false")
        self._restyle()
        self.setText(pretty_key(self._hotkey))
        if was_capturing:
            self.capture_finished.emit()

    def _restyle(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.begin_capture()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if self._capturing:
            if key == Qt.Key_Escape:
                self.cancel_capture()
            event.accept()
            return
        if key in START_KEYS:
            self._armed = True
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        # Start on release: the hook returns on the first key-up, which would be this key.
        # Only a press seen while idle arms it, so the release of a captured Enter does not.
        if self._armed and event.key() in START_KEYS and not event.isAutoRepeat():
            self._armed = False
            self.begin_capture()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if event.reason() in (Qt.MouseFocusReason, Qt.TabFocusReason, Qt.BacktabFocusReason):
            self.cancel_capture()
