"""Floating waveform pill: non-activating, always-on-top status capsule."""
import math
import sys
import time
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

COLORS = {"idle": "#8e8e93", "recording": "#007aff", "processing": "#ff9f0a"}
IDLE_SIZE = (56.0, 16.0)
ACTIVE_SIZE = (220.0, 48.0)
MARGIN = 16.0
SHADOW_LAYERS = 16
BOTTOM_OFFSET = 60.0
BAR_COUNT = 21
FRAME_MS = 33

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


class PillWidget(QWidget):
    """Idle: small dim capsule. Recording: blue with live bars. Processing: amber with dots."""

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
        self._levels: deque[float] = deque([0.0] * BAR_COUNT, maxlen=BAR_COUNT)
        self._shown = [0.0] * BAR_COUNT
        self._start = time.monotonic()
        self._pressed = False
        self._styled = False
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._relayout()

    def set_state(self, state: str) -> None:
        if state not in COLORS:
            raise ValueError(f"unknown pill state: {state}")
        if state == "recording" and self._state != "recording":
            self._levels.extend([0.0] * BAR_COUNT)
            self._shown = [0.0] * BAR_COUNT
        if state != self._state:
            self._start = time.monotonic()
        self._state = state
        self._relayout()

    def set_level(self, level: float) -> None:
        self._levels.append(max(0.0, min(1.0, float(level))))
        self._shown = self._shown[1:] + [self._shown[-1]]
        self._ease()
        if self._state == "recording":
            self.update()

    def apply(self, scale: float, always_visible: bool) -> None:
        self._scale = scale
        self._always_visible = always_visible
        self._relayout()

    def capsule_rect(self) -> QRectF:
        """The capsule's rectangle in widget coordinates (inside the shadow margins)."""
        w, h = ACTIVE_SIZE if self._state != "idle" else IDLE_SIZE
        m = MARGIN * self._scale
        return QRectF(m, m, w * self._scale, h * self._scale)

    def animating(self) -> bool:
        return self._timer.isActive()

    def _relayout(self) -> None:
        rect = self.capsule_rect()
        m = MARGIN * self._scale
        self.setFixedSize(math.ceil(rect.width() + 2 * m), math.ceil(rect.height() + 2 * m))
        self._reposition()
        if self._always_visible or self._state != "idle":
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
        if self._state != "idle" and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _ease(self) -> None:
        for i, target in enumerate(self._levels):
            rate = 0.55 if target > self._shown[i] else 0.22
            self._shown[i] += (target - self._shown[i]) * rate

    def _tick(self) -> None:
        if self._state == "recording":
            self._ease()
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

    def mousePressEvent(self, event) -> None:
        inside = self.capsule_rect().contains(event.position())
        self._pressed = event.button() == Qt.LeftButton and inside
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        inside = self.capsule_rect().contains(event.position())
        if self._pressed and event.button() == Qt.LeftButton and inside:
            self.clicked.emit()
        self._pressed = False
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.capsule_rect()
        self._paint_shadow(painter, rect)
        self._paint_body(painter, rect)
        if self._state == "recording":
            self._paint_bars(painter, rect)
        elif self._state == "processing":
            self._paint_dots(painter, rect)
        painter.end()

    def _paint_shadow(self, painter: QPainter, rect: QRectF) -> None:
        s = self._scale
        spread = (MARGIN - 5) * s
        strength = 0.30 if self._state != "idle" else 0.16
        alpha = max(1, round(strength * 255 / SHADOW_LAYERS))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, alpha))
        base = rect.adjusted(spread * 0.15, 4 * s, -spread * 0.15, 3 * s)
        for i in range(SHADOW_LAYERS):
            grow = spread * (1 - i / SHADOW_LAYERS)
            layer = base.adjusted(-grow, -grow * 0.35, grow, grow * 0.9)
            radius = layer.height() / 2
            painter.drawRoundedRect(layer, radius, radius)

    def _paint_body(self, painter: QPainter, rect: QRectF) -> None:
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        base = QColor(COLORS[self._state])
        alpha = 215 if self._state == "idle" else 250

        fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        top, bottom = QColor(base.lighter(108)), QColor(base.darker(108))
        top.setAlpha(alpha)
        mid = QColor(base)
        mid.setAlpha(alpha)
        bottom.setAlpha(alpha)
        fill.setColorAt(0.0, top)
        fill.setColorAt(0.5, mid)
        fill.setColorAt(1.0, bottom)
        painter.fillPath(path, fill)

        sheen = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.center().y()))
        sheen.setColorAt(0.0, QColor(255, 255, 255, 46))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(path, sheen)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 22), 1.0))
        outer = rect.adjusted(-0.5, -0.5, 0.5, 0.5)
        painter.drawRoundedRect(outer, outer.height() / 2, outer.height() / 2)

        edge = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        edge.setColorAt(0.0, QColor(255, 255, 255, 110))
        edge.setColorAt(1.0, QColor(255, 255, 255, 18))
        inner = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(edge, 1.0))
        painter.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)

    def _paint_bars(self, painter: QPainter, rect: QRectF) -> None:
        pad_x = rect.height() * 0.6
        pad_y = rect.height() * 0.18
        area = rect.adjusted(pad_x, pad_y, -pad_x, -pad_y)
        gap_ratio = 0.75
        width = area.width() / (BAR_COUNT + (BAR_COUNT - 1) * gap_ratio)
        gap = width * gap_ratio
        cy = area.center().y()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 242))
        for i, level in enumerate(self._shown):
            envelope = 0.55 + 0.45 * math.sin(math.pi * (i + 0.5) / BAR_COUNT)
            amount = min(1.0, max(0.0, level) * 1.2) ** 0.7 * envelope
            height = width + (area.height() - width) * amount
            x = area.left() + i * (width + gap)
            bar = QRectF(x, cy - height / 2, width, height)
            painter.drawRoundedRect(bar, width / 2, width / 2)

    def _paint_dots(self, painter: QPainter, rect: QRectF) -> None:
        s = self._scale
        radius = 4.0 * s
        spacing = 13.0 * s
        phase = (time.monotonic() - self._start) * 1.3
        center = rect.center()
        painter.setPen(Qt.NoPen)
        for i in range(3):
            wave = (math.sin(2 * math.pi * (phase - i * 0.16)) + 1) / 2
            painter.setBrush(QColor(255, 255, 255, int(110 + 140 * wave)))
            pos = QPointF(center.x() + (i - 1) * spacing, center.y() - wave * 3.0 * s)
            painter.drawEllipse(pos, radius, radius)
