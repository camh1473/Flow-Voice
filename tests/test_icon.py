import struct

import pytest
from PySide6.QtGui import QImage

from flowvoice import paths
from flowvoice.ui.shell import app_icon, tray_icon

ICO = paths.asset_path("flowvoice.ico")
REQUIRED = {16, 20, 24, 32, 48, 64, 128, 256}


def entries():
    data = ICO.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    out = []
    for i in range(count):
        w, h, _, _, planes, bpp, size, offset = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        out.append((w or 256, h or 256, bpp, data[offset:offset + size]))
    return out


def test_ico_has_every_windows_size():
    assert REQUIRED <= {w for w, _, _, _ in entries()}


def test_every_ico_entry_is_a_real_png_of_the_stated_size():
    for w, h, bpp, blob in entries():
        img = QImage()
        assert img.loadFromData(blob, "PNG"), f"{w}px entry is not a PNG"
        assert (img.width(), img.height()) == (w, h) and bpp == 32


@pytest.mark.parametrize("size", [16, 24, 32, 256])
def test_icon_is_the_blue_violet_bubble_with_white_letters(size):
    img = next(QImage.fromData(blob) for w, _, _, blob in entries() if w == size)
    colored = white = 0
    for y in range(size):
        for x in range(size):
            c = img.pixelColor(x, y)
            if c.alpha() < 200:
                continue
            if c.blue() > c.red() and c.blue() > 150 and c.green() < 140:
                colored += 1
            elif min(c.red(), c.green(), c.blue()) > 225:
                white += 1
    assert colored > size * size * 0.25, "the bubble should be blue-violet"
    assert white > size * size * 0.04, "the FV letters should be white"


def test_corners_are_transparent():
    img = QImage.fromData(next(b for w, _, _, b in entries() if w == 256))
    assert img.pixelColor(0, 0).alpha() == 0 and img.pixelColor(255, 0).alpha() == 0


def test_app_icon_loads_with_several_sizes(qapp):
    icon = app_icon()
    assert not icon.isNull()
    assert len(icon.availableSizes()) >= 5


def test_tray_icon_is_the_logo_and_state_adds_a_badge(qapp):
    idle, rec, proc = tray_icon("idle"), tray_icon("recording"), tray_icon("processing")
    for icon in (idle, rec, proc):
        assert not icon.isNull()
    a = rec.pixmap(64, 64).toImage()
    b = proc.pixmap(64, 64).toImage()
    c = idle.pixmap(64, 64).toImage()
    assert a != c and b != c and a != b
    assert a.pixelColor(56, 56).blue() > 180 and b.pixelColor(56, 56).red() > 200  # badge colours
