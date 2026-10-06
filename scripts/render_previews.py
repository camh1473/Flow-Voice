"""Render the pill states and the Home window to PNGs for visual review (.superpowers/preview/)."""
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from flowvoice.config import Config  # noqa: E402
from flowvoice.history import HistoryEntry  # noqa: E402
from flowvoice.ui.main_window import MainWindow  # noqa: E402
from flowvoice.ui.pill import PillWidget  # noqa: E402

OUT = ROOT / ".superpowers" / "preview"
BACKDROPS = (QColor("#e5e5ea"), QColor("#1c1c1e"))
SCALES = (1.0, 2.0)
PAD = 24


def speech_levels(count: int = 60) -> list[float]:
    """A believable syllable-like level sequence: bursts with pauses and jitter."""
    levels = []
    for i in range(count):
        syllable = abs(math.sin(i * 0.9)) * (0.55 + 0.45 * math.sin(i * 0.23))
        jitter = 0.12 * math.sin(i * 2.7 + 1.3)
        levels.append(max(0.02, min(1.0, syllable + jitter)))
    return levels


def grab(state: str, scale: float) -> QImage:
    pill = PillWidget(scale=scale)
    pill.set_state(state)
    if state == "recording":
        for level in speech_levels():
            pill.set_level(level)
    image = pill.grab().toImage()
    pill.close()
    return image


def compose(state: str) -> QImage:
    shots = [grab(state, s) for s in SCALES]
    width = max(i.width() for i in shots) + 2 * PAD
    cell_h = sum(i.height() for i in shots) + PAD * (len(shots) + 1)
    sheet = QImage(width * len(BACKDROPS), cell_h, QImage.Format_ARGB32_Premultiplied)
    painter = QPainter(sheet)
    for col, color in enumerate(BACKDROPS):
        x0 = col * width
        painter.fillRect(x0, 0, width, cell_h, color)
        y = PAD
        for shot in shots:
            painter.drawImage(QPoint(x0 + (width - shot.width()) // 2, y), shot)
            y += shot.height() + PAD
    painter.end()
    return sheet


def render_home(dark: bool, state: str = "idle") -> QImage:
    """The main window on the Home tab with a sample transcription."""
    settings = QSettings(str(Path(tempfile.gettempdir()) / "flowvoice-preview.ini"),
                         QSettings.IniFormat)
    win = MainWindow(Config(), None, lambda cfg: None, settings=settings, dark=dark)
    win.resize(880, 620)
    win.home.set_state(state)
    win.home.show_entry(HistoryEntry(
        1, datetime.now().replace(hour=9, minute=41).isoformat(timespec="seconds"),
        "", "Hey Sam, just confirming we are still on for Thursday at 2. "
        "I will bring the floor plans and the updated price sheet.", "OUTLOOK.EXE"))
    win.show()
    QApplication.processEvents()
    image = win.grab().toImage()
    win.request_quit()
    win.close()
    return image


def main() -> None:
    app = QApplication.instance() or QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    for state in ("idle", "recording", "processing"):
        path = OUT / f"pill_{state}.png"
        compose(state).save(str(path))
        print(path)
    for name, dark in (("light", False), ("dark", True)):
        path = OUT / f"home_{name}.png"
        render_home(dark).save(str(path))
        print(path)
    path = OUT / "home_recording.png"
    render_home(False, "recording").save(str(path))
    print(path)
    del app


if __name__ == "__main__":
    main()
