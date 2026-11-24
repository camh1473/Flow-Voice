"""Draw the Flow Voice icon at every Windows size and pack it into src/flowvoice/assets/.

Run:  .venv/Scripts/python.exe scripts/make_icon.py

The artwork is a blue-to-violet speech bubble with a forward-leaning "FV" and two sound arcs.
Each size is drawn natively (not scaled down): 32 px and up have the arcs; 24 px and below drop
them and use bigger letters so the mark stays readable. The letters come from Bahnschrift, a
font that ships with Windows; only the finished images are committed, nothing needs the font
at run time.
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "flowvoice" / "assets"

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QImage,  # noqa: E402
                           QLinearGradient, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import QApplication  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
FONT_FILE = "C:/Windows/Fonts/bahnschrift.ttf"
COBALT, VIOLET = QColor("#2b5bff"), QColor("#8a3ffc")
WHITE = QColor("#ffffff")
SHEAR = 0.12  # forward lean: "flow"


def bubble_path() -> QPainterPath:
    """The speech bubble: rounded body (14,24)-(242,184) plus a tail curling down at the lower left."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(14, 24, 228, 160), 66, 66)
    tail = QPainterPath()
    tail.moveTo(58, 170)
    tail.quadTo(60, 216, 38, 232)
    tail.quadTo(92, 226, 114, 172)
    tail.closeSubpath()
    return path.united(tail)


def round_pen(color, width) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def draw_mark(p: QPainter, family: str, small: bool) -> None:
    """The "FV" and, at larger sizes, two sound arcs; centred in the bubble body."""
    font = QFont(family)
    font.setPixelSize(120)
    font.setWeight(QFont.Bold)
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    path.addText(0, 0, font, "FV")
    path = path.simplified()
    box = path.boundingRect()
    arc_k = 0.0 if small else 0.695         # arcs reach this many letter-heights past the V
    height = 104.0 if small else 84.0
    room = 190.0 if small else 172.0         # letters (+ arcs) must stay inside the bubble body
    total = box.width() * height / box.height() + arc_k * height
    if total > room:
        height *= room / total
    scale = height / box.height()
    total = box.width() * scale + arc_k * height
    cx, cy = 128.0, 102.0
    left = cx - total / 2
    p.save()
    p.translate(left - box.left() * scale, cy + height / 2 - box.bottom() * scale)
    p.scale(scale, scale)
    p.shear(-SHEAR, 0)
    p.setPen(Qt.NoPen)
    p.setBrush(WHITE)
    p.drawPath(path)
    p.restore()
    if not small:
        ax = left + box.width() * scale + height * 0.10
        for i, r in enumerate((height * 0.30, height * 0.52)):
            p.setPen(round_pen(QColor(255, 255, 255, 255 if i == 0 else 205), height * 0.15))
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(ax - r, cy - r, 2 * r, 2 * r), int(-36 * 16), int(72 * 16))


def render(size: int, family: str) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(size / 256, size / 256)
    bubble = bubble_path()
    fill = QLinearGradient(14, 24, 242, 214)
    fill.setColorAt(0, COBALT)
    fill.setColorAt(1, VIOLET)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(fill))
    p.drawPath(bubble)
    sheen = QLinearGradient(0, 24, 0, 120)
    sheen.setColorAt(0, QColor(255, 255, 255, 52))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(sheen))
    p.drawPath(bubble)
    if size >= 40:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 40), 2.0))
        p.drawPath(bubble)
    draw_mark(p, family, small=size <= 24)
    p.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(data)


def pack_ico(images: dict[int, QImage]) -> bytes:
    """An .ico whose entries are PNGs (supported since Windows Vista)."""
    blobs = {size: png_bytes(img) for size, img in sorted(images.items())}
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, body = b"", b""
    for size, blob in blobs.items():
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(body))
        body += blob
    return header + entries + body


def main() -> int:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    font_id = QFontDatabase.addApplicationFont(FONT_FILE)
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    if "Bahnschrift" not in families:
        print(f"Bahnschrift not found at {FONT_FILE}; cannot draw the icon.", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    images = {size: render(size, "Bahnschrift") for size in SIZES}
    (OUT / "flowvoice.ico").write_bytes(pack_ico(images))
    images[256].save(str(OUT / "flowvoice.png"))
    print("wrote", OUT / "flowvoice.ico", "sizes", list(images))
    return 0


if __name__ == "__main__":
    sys.exit(main())
