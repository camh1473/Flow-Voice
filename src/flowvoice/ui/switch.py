"""iOS-style on/off switch with QCheckBox semantics (isChecked / setChecked / toggled)."""
from PySide6.QtCore import Property, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox

TRACK = (42, 24)
KNOB_MARGIN = 3
ANIM_MS = 140


class Switch(QCheckBox):
    """A rounded track with a sliding knob; colors come from QSS qproperty-* rules."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._scale = 1.0
        self._pos = 0.0
        self._on = QColor("#007aff")
        self._off = QColor("#d1d1d6")
        self._knob = QColor("#ffffff")
        self._ring = QColor("#007aff")
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(ANIM_MS)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._on_toggled)
        self.set_scale(1.0)

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.setFixedSize(self.sizeHint())
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(round(TRACK[0] * self._scale), round(TRACK[1] * self._scale))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def knob_x(self) -> float:
        """Left edge of the knob in px (0 = fully off position)."""
        return self._pos * (self.width() - self.height())

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        self._anim.stop()
        if not self.isVisible():
            self._set_pos(target)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def _set_pos(self, value) -> None:
        self._pos = float(value)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        track = QRectF(0.5, 0.5, w - 1, h - 1)
        color = QColor(self._off)
        on = QColor(self._on)
        t = self._pos
        color.setRgbF(color.redF() + (on.redF() - color.redF()) * t,
                      color.greenF() + (on.greenF() - color.greenF()) * t,
                      color.blueF() + (on.blueF() - color.blueF()) * t, 1.0)
        if not self.isEnabled():
            color.setAlphaF(0.45)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        if self.hasFocus():
            ring = QColor(self._ring)
            ring.setAlphaF(0.55)
            p.setPen(QPen(ring, max(1.5, 2 * self._scale)))
            p.setBrush(Qt.NoBrush)
            inner = track.adjusted(1, 1, -1, -1)
            p.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)
        margin = KNOB_MARGIN * self._scale
        d = h - 2 * margin
        center = QPointF(margin + d / 2 + self.knob_x(), h / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(center + QPointF(0, 0.8 * self._scale), d / 2 + 0.5, d / 2 + 0.5)
        p.setBrush(self._knob)
        p.drawEllipse(center, d / 2, d / 2)
        p.end()

    def _get_on(self) -> QColor:
        return self._on

    def _put_on(self, c: QColor) -> None:
        self._on = QColor(c)
        self.update()

    def _get_off(self) -> QColor:
        return self._off

    def _put_off(self, c: QColor) -> None:
        self._off = QColor(c)
        self.update()

    def _get_knob(self) -> QColor:
        return self._knob

    def _put_knob(self, c: QColor) -> None:
        self._knob = QColor(c)
        self.update()

    def _get_ring(self) -> QColor:
        return self._ring

    def _put_ring(self, c: QColor) -> None:
        self._ring = QColor(c)
        self.update()

    onColor = Property(QColor, _get_on, _put_on)
    offColor = Property(QColor, _get_off, _put_off)
    knobColor = Property(QColor, _get_knob, _put_knob)
    ringColor = Property(QColor, _get_ring, _put_ring)
