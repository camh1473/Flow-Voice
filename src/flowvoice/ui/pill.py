"""Floating status pill: a round mic icon when idle, glowing "fan" threads while you talk.

Non-activating and always on top. Idle is a small circular mic. Recording fades into nine fine
threads that swell with your voice and taper away at both ends; processing turns them amber
with a soft glow sweeping along them. Everything fades in and out; nothing snaps.
"""
import math
import sys
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

COLORS = {"idle": "#8e8e93", "recording": "#007aff", "processing": "#ff9f0a"}  # tray icon, Home dot
IDLE_DIAMETER = 48.0
ACTIVE_SIZE = (340.0, 96.0)
HIT_SIZE = (220.0, 60.0)  # clickable middle of the active area; the rest is just glow
MARGIN = 18.0
BOTTOM_OFFSET = 60.0
FRAME_MS = 33
THREADS = 9

ATTACK_SECONDS = 0.05   # the glow follows a rising voice quickly...
RELEASE_SECONDS = 0.45  # ...and lets go slowly, so it fades out naturally
FADE_SECONDS = 0.20     # idle <-> active
SETTLED = 0.004

GRAPHITE = QColor(44, 44, 46)
BLUE, TEAL, INDIGO = QColor("#0a84ff"), QColor("#18a8e8"), QColor("#5e5ce6")
AMBER_DEEP = QColor("#f28c00")  # a touch deeper than the tray amber so it reads on a light desktop

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _rgba(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(_lerp(a.red(), b.red(), t)), int(_lerp(a.green(), b.green(), t)),
                  int(_lerp(a.blue(), b.blue(), t)))


def _edge(u: float) -> float:
    """1 in the middle, easing to 0 at both ends: every thread tapers away."""
    return _ease(min(u / 0.22, (1 - u) / 0.22, 1.0))


def _glow(p: QPainter, c: QPointF, rx: float, ry: float, color: QColor, alpha: float) -> None:
    """A soft glow with a gaussian falloff to fully transparent: no visible edge."""
    if rx <= 0 or ry <= 0 or alpha <= 0.004:
        return
    p.save()
    p.translate(c)
    p.scale(1.0, ry / rx)
    g = QRadialGradient(QPointF(0, 0), rx)
    for k in range(11):
        g.setColorAt(k / 10, _rgba(color, alpha * math.exp(-((k / 10 * 2.4) ** 2)) if k < 10 else 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(0, 0), rx, rx)
    p.restore()


def draw_mic(p: QPainter, c: QPointF, size: float, color: QColor) -> None:
    """A microphone glyph (the same one as the tray icon), centred on `c`."""
    p.save()
    p.translate(c)
    k = size / 64
    p.scale(k, k)
    p.translate(-32, -32)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(24, 12, 16, 26), 8, 8)
    pen = QPen(color, 4.0)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(17, 18, 30, 26), 180 * 16, 180 * 16)
    p.drawLine(QPointF(32, 44), QPointF(32, 52))
    p.drawLine(QPointF(24, 52), QPointF(40, 52))
    p.restore()


class PillWidget(QWidget):
    """Idle: round mic icon. Recording: blue fan of threads. Processing: amber threads, glow sweeping."""

    clicked = Signal()

    def __init__(self, scale: float = 1.0, always_visible: bool = True) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._scale = scale
        self._always_visible = always_visible
        self._state = "idle"
        self._act = 0.0    # 0 idle .. 1 active
        self._proc = 0.0   # 0 .. 1 thinking
        self._lv = 0.0     # smoothed voice level
        self._raw = 0.0
        self._raw_at = 0.0
        self._t = 0.0
        self._last = time.monotonic()
        self._wide_now = False
        self._pressed = False
        self._styled = False
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._relayout()

    # ----- public API

    def set_state(self, state: str) -> None:
        if state not in COLORS:
            raise ValueError(f"unknown pill state: {state}")
        if state == "recording" and self._state != "recording":
            self._lv = self._raw = 0.0
        self._state = state
        self._relayout()

    def set_level(self, level: float) -> None:
        now = time.monotonic()
        self._raw = max(0.0, min(1.0, float(level)))
        self._raw_at = now
        self._follow(self._raw, 0.02)
        if self._state == "recording":
            self.update()

    def apply(self, scale: float, always_visible: bool) -> None:
        self._scale = scale
        self._always_visible = always_visible
        self._relayout()

    def settle(self) -> None:
        """Jump the fade to where the current state is heading (tests, screenshots)."""
        active = self._state != "idle"
        self._act = 1.0 if active else 0.0
        self._proc = 1.0 if self._state == "processing" else 0.0
        if self._state != "recording":
            self._lv = 0.0
        self._relayout()

    def capsule_rect(self) -> QRectF:
        """The drawn area in widget coordinates (inside the glow margins)."""
        m = MARGIN * self._scale
        if self._wide():
            w, h = ACTIVE_SIZE
        else:
            w = h = IDLE_DIAMETER
        return QRectF(m, m, w * self._scale, h * self._scale)

    def hit_rect(self) -> QRectF:
        """Where a click counts: the icon when idle, the middle of the threads when active."""
        rect = self.capsule_rect()
        if not self._wide():
            return rect
        w, h = HIT_SIZE[0] * self._scale, HIT_SIZE[1] * self._scale
        return QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h)

    def animating(self) -> bool:
        return self._timer.isActive()

    # ----- layout and timing

    def _wide(self) -> bool:
        return self._state != "idle" or self._act > SETTLED

    def _relayout(self) -> None:
        rect = self.capsule_rect()
        m = MARGIN * self._scale
        self.setFixedSize(math.ceil(rect.width() + 2 * m), math.ceil(rect.height() + 2 * m))
        self._reposition()
        if self._always_visible or self._wide():
            if not self.isVisible():
                self.show()
        elif self.isVisible():
            self.hide()
        self._sync_timer()
        self.update()

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        center_y = geo.bottom() - (BOTTOM_OFFSET + ACTIVE_SIZE[1] / 2) * self._scale
        self.move(
            int(geo.center().x() - self.width() / 2),
            int(center_y - self.height() / 2),
        )

    def _sync_timer(self) -> None:
        if self.isVisible() and (self._state != "idle" or self._act > 0.0):
            if not self._timer.isActive():
                self._last = time.monotonic()
                self._timer.start()
        else:
            self._timer.stop()

    def _follow(self, target: float, dt: float) -> None:
        tau = ATTACK_SECONDS if target > self._lv else RELEASE_SECONDS
        self._lv += (target - self._lv) * (1 - math.exp(-dt / tau))

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(now - self._last, 0.1)
        self._last = now
        self._t += dt
        if now - self._raw_at > 0.12:  # no fresh audio: the voice level lets go
            self._raw = 0.0
        self._follow(self._raw if self._state == "recording" else 0.0, dt)
        active = self._state != "idle"
        self._act += ((1.0 if active else 0.0) - self._act) * (1 - math.exp(-dt / FADE_SECONDS))
        self._proc += ((1.0 if self._state == "processing" else 0.0) - self._proc) * (
            1 - math.exp(-dt / 0.15))
        if not active and self._act < SETTLED and self._lv < 0.01:
            self._act, self._lv = 0.0, 0.0
            if self._wide_now:
                self._relayout()
        elif active and not self._wide_now:
            self._relayout()
        self._wide_now = self._wide()
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._styled:
            self._styled = True
            self._apply_noactivate()
        self._sync_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_timer()

    def _apply_noactivate(self) -> None:
        if sys.platform != "win32" or QGuiApplication.platformName() != "windows":
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except Exception:
            pass

    # ----- mouse

    def mousePressEvent(self, event) -> None:
        inside = self.hit_rect().contains(event.position())
        self._pressed = event.button() == Qt.LeftButton and inside
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        inside = self.hit_rect().contains(event.position())
        if self._pressed and event.button() == Qt.LeftButton and inside:
            self.clicked.emit()
        self._pressed = False
        event.accept()

    # ----- painting

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.capsule_rect().center()
        idle_alpha = 1 - _ease(self._act * 1.6)
        if idle_alpha > 0.01:
            self._paint_idle(painter, center, idle_alpha)
        if self._act > 0.01:
            self._paint_threads(painter, center)
        painter.end()

    def _paint_idle(self, p: QPainter, c: QPointF, alpha: float) -> None:
        s = self._scale
        r = IDLE_DIAMETER / 2 * s
        p.setOpacity(alpha)
        _glow(p, QPointF(c.x(), c.y() + 5 * s), r + 16 * s, r + 16 * s, QColor(0, 0, 0), 0.40)
        g = QLinearGradient(c.x(), c.y() - r, c.x(), c.y() + r)
        g.setColorAt(0, _rgba(GRAPHITE.lighter(118), 0.94))
        g.setColorAt(1, _rgba(GRAPHITE.darker(112), 0.94))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1.4 * s))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r - 0.8 * s, r - 0.8 * s)
        draw_mic(p, c, r * 1.55, QColor(255, 255, 255, 235))
        p.setOpacity(1.0)

    def _paint_threads(self, p: QPainter, c: QPointF) -> None:
        s, act, proc, t = self._scale, self._act, self._proc, self._t
        width = _lerp(70.0, ACTIVE_SIZE[0], _ease(act)) * s
        amp = (3 + 40 * self._lv * (1 - proc) + (9 + 3 * math.sin(t * 3)) * proc) * s
        dim = (1 - proc) * (0.45 + 0.55 * min(1.0, self._lv * 2.5)) + proc * 0.9
        # A faint dark underglow keeps the threads readable over a light desktop.
        _glow(p, c, width * 0.5, 30 * s + 22 * s * self._lv, QColor(0, 0, 0), 0.11 * act)
        p.setBrush(Qt.NoBrush)
        n = 110
        for k in range(-(THREADS // 2), THREADS // 2 + 1):
            color = _mix(INDIGO, BLUE, (k + 4) / 4) if k < 0 else _mix(BLUE, TEAL, k / 4)
            color = _mix(color, AMBER_DEEP, proc)
            scale = 1.0 - 0.06 * abs(k)
            speed = 2.2 + 0.12 * k
            path = QPainterPath()
            for i in range(n + 1):
                u = i / n
                x = c.x() - width / 2 + u * width
                y = c.y() + amp * scale * math.sin(math.pi * u) ** 1.4 * math.sin(
                    1.25 * 2 * math.pi * u + 0.34 * k + t * speed)
                if i:
                    path.lineTo(x, y)
                else:
                    path.moveTo(x, y)
            alpha = dim * (1.0 - 0.05 * abs(k)) * act
            pen = QPen(self._brush(c, width, color, alpha), (1.3 + 1.1 * proc) * s)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawPath(path)

    def _brush(self, c: QPointF, width: float, color: QColor, alpha: float) -> QBrush:
        """Fades out at both ends; while thinking a soft bright spot sweeps along the thread."""
        g = QLinearGradient(c.x() - width / 2, 0, c.x() + width / 2, 0)
        sweep = (self._t * 0.55) % 1.5 - 0.25
        for i in range(25):
            u = i / 24
            spot = 0.45 + 0.55 * math.exp(-(((u - sweep) / 0.13) ** 2))
            g.setColorAt(u, _rgba(color, alpha * _edge(u) * ((1 - self._proc) + self._proc * spot)))
        return QBrush(g)
