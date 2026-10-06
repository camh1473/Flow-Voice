from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from flowvoice.ui.pill import PillWidget

STATES = ("idle", "recording", "processing")
SPEECH_A = [0.05, 0.2, 0.6, 0.9, 0.4, 0.1, 0.7, 0.3, 0.8, 0.2, 0.5] * 2
SPEECH_B = [0.9, 0.05, 0.05, 0.3, 0.95, 0.6, 0.02, 0.4, 0.1, 0.85, 0.15] * 2


def make(qapp, state="idle", **kw) -> PillWidget:
    pill = PillWidget(**kw)
    pill.set_state(state)
    return pill


def body_color(pill: PillWidget):
    """Colour of the capsule body: centre row, inside the left end cap (clear of bars/dots)."""
    rect = pill.capsule_rect()
    x = int(rect.left() + rect.height() * 0.3)
    y = int(rect.center().y())
    return pill.grab().toImage().pixelColor(x, y)


def test_grab_is_not_null_in_every_state(qapp):
    for state in STATES:
        pill = make(qapp, state)
        assert not pill.grab().isNull()
        pill.close()


def test_recording_body_is_red(qapp):
    c = body_color(make(qapp, "recording"))
    assert c.red() > 200 and c.green() < 100


def test_processing_body_is_amber(qapp):
    c = body_color(make(qapp, "processing"))
    assert c.red() > 200 and 100 < c.green() < 200 and c.blue() < 80


def test_idle_body_is_grey(qapp):
    c = body_color(make(qapp, "idle"))
    assert abs(c.red() - c.green()) < 20 and abs(c.green() - c.blue()) < 20
    assert 90 < c.red() < 190


def test_level_sequences_change_the_waveform(qapp):
    a, b = make(qapp, "recording"), make(qapp, "recording")
    for level in SPEECH_A:
        a.set_level(level)
    for level in SPEECH_B:
        b.set_level(level)
    assert a.grab().toImage() != b.grab().toImage()


def test_scale_makes_pill_wider(qapp):
    small = make(qapp, "recording", scale=1.0)
    big = make(qapp, "recording", scale=1.5)
    assert big.width() > small.width()
    assert big.capsule_rect().width() > small.capsule_rect().width()


def test_active_pill_is_larger_than_idle(qapp):
    pill = make(qapp, "idle")
    idle_width = pill.capsule_rect().width()
    pill.set_state("recording")
    assert pill.capsule_rect().width() > idle_width


def test_hidden_when_idle_unless_always_visible(qapp):
    pill = make(qapp, "idle", always_visible=False)
    assert not pill.isVisible()
    pill.set_state("recording")
    assert pill.isVisible()
    pill.set_state("idle")
    assert not pill.isVisible()
    pill.apply(1.0, True)
    assert pill.isVisible()


def test_always_visible_shows_idle_pill(qapp):
    assert make(qapp, "idle", always_visible=True).isVisible()


def test_left_click_emits_clicked_once(qapp):
    pill = make(qapp, "recording")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    center = pill.capsule_rect().center().toPoint()
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, center)
    assert hits == [1]


def test_click_outside_capsule_is_ignored(qapp):
    pill = make(qapp, "recording")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, QPoint(1, 1))
    assert hits == []


def test_window_never_takes_focus(qapp):
    pill = make(qapp)
    flags = pill.windowFlags()
    for flag in (Qt.WindowDoesNotAcceptFocus, Qt.FramelessWindowHint,
                 Qt.WindowStaysOnTopHint, Qt.Tool):
        assert flags & flag
    assert pill.testAttribute(Qt.WA_ShowWithoutActivating)
    assert pill.testAttribute(Qt.WA_TranslucentBackground)


def test_animation_timer_runs_only_while_active(qapp):
    pill = make(qapp, "idle")
    assert not pill.animating()
    pill.set_state("recording")
    assert pill.animating()
    pill.set_state("processing")
    assert pill.animating()
    pill.set_state("idle")
    assert not pill.animating()
