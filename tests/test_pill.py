import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from flowvoice.ui import pill as pill_mod
from flowvoice.ui.pill import PillWidget

STATES = ("idle", "recording", "processing")
SPEECH_A = [0.05, 0.2, 0.6, 0.9, 0.4, 0.1, 0.7, 0.3, 0.8, 0.2, 0.5] * 2
SPEECH_B = [0.9, 0.05, 0.05, 0.3, 0.95, 0.6, 0.02, 0.4, 0.1, 0.85, 0.15] * 2


def make(qapp, state="idle", **kw) -> PillWidget:
    pill = PillWidget(**kw)
    pill.set_state(state)
    pill.settle()
    return pill


def pixels(pill):
    img = pill.grab().toImage()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() > 25:
                yield x, y, c


def blue_count(pill) -> int:
    return sum(1 for _, _, c in pixels(pill) if c.blue() > c.red() + 60)


def amber_count(pill) -> int:
    return sum(1 for _, _, c in pixels(pill) if c.red() > c.blue() + 90 and c.green() > 90)


def height(pill) -> int:
    ys = [y for _, y, _ in pixels(pill)]
    return max(ys) - min(ys) if ys else 0


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(pill_mod.time, "monotonic", c)
    return c


def run(pill, clock, seconds, step=0.033):
    for _ in range(int(seconds / step)):
        clock.t += step
        pill._tick()


def test_grab_is_not_null_in_every_state(qapp):
    for state in STATES:
        pill = make(qapp, state)
        assert not pill.grab().isNull()
        pill.close()


def test_idle_is_a_small_round_mic_icon(qapp):
    pill = make(qapp, "idle")
    rect = pill.capsule_rect()
    assert rect.width() == rect.height()
    x, y = int(rect.left() + rect.width() * 0.12), int(rect.center().y())
    c = pill.grab().toImage().pixelColor(x, y)
    assert c.alpha() > 150 and abs(c.red() - c.green()) < 20 and abs(c.green() - c.blue()) < 20
    assert c.red() < 120  # dark disc
    assert blue_count(pill) == 0 and amber_count(pill) == 0


def test_recording_threads_are_blue(qapp):
    pill = make(qapp, "recording")
    for level in SPEECH_A:
        pill.set_level(level)
    assert blue_count(pill) > 200 and amber_count(pill) == 0


def test_processing_threads_are_amber(qapp):
    pill = make(qapp, "processing")
    assert amber_count(pill) > 100 and blue_count(pill) == 0


def test_level_sequences_change_the_threads(qapp):
    a, b = make(qapp, "recording"), make(qapp, "recording")
    for level in SPEECH_A:
        a.set_level(level)
    for level in SPEECH_B:
        b.set_level(level)
    assert a.grab().toImage() != b.grab().toImage()


def test_loud_voice_makes_taller_threads_than_silence(qapp):
    quiet, loud = make(qapp, "recording"), make(qapp, "recording")
    for _ in range(40):
        loud.set_level(1.0)
    assert height(loud) > height(quiet) + 20


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
    pill.settle()
    assert not pill.isVisible()
    pill.apply(1.0, True)
    assert pill.isVisible()


def test_always_visible_shows_idle_pill(qapp):
    assert make(qapp, "idle", always_visible=True).isVisible()


def test_going_idle_fades_instead_of_snapping(qapp, clock):
    pill = make(qapp, "recording", always_visible=False)
    pill.set_state("idle")
    assert pill.isVisible() and pill._act == 1.0  # still fully drawn the moment you stop
    run(pill, clock, 0.3)
    assert 0.0 < pill._act < 0.8 and pill.isVisible()
    run(pill, clock, 3.0)
    assert pill._act == 0.0 and not pill.isVisible()


def test_voice_glow_lets_go_slowly_when_audio_stops(qapp, clock):
    pill = make(qapp, "recording")
    for _ in range(30):
        pill.set_level(1.0)
    loud = pill._lv
    assert loud > 0.8
    run(pill, clock, 0.4)
    assert 0.05 < pill._lv < loud * 0.7  # fading, not gone
    run(pill, clock, 4.0)
    assert pill._lv < 0.01


def test_left_click_emits_clicked_once(qapp):
    pill = make(qapp, "recording")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    center = pill.capsule_rect().center().toPoint()
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, center)
    assert hits == [1]


def test_idle_icon_is_clickable(qapp):
    pill = make(qapp, "idle")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, pill.capsule_rect().center().toPoint())
    assert hits == [1]


def test_click_outside_pill_is_ignored(qapp):
    pill = make(qapp, "recording")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, QPoint(1, 1))
    assert hits == []


def test_click_on_the_far_thread_tips_is_ignored(qapp):
    pill = make(qapp, "recording")
    hits = []
    pill.clicked.connect(lambda: hits.append(1))
    rect = pill.capsule_rect()
    QTest.mouseClick(pill, Qt.LeftButton, Qt.NoModifier, QPoint(int(rect.left()) + 4, int(rect.center().y())))
    assert hits == []


def test_window_never_takes_focus(qapp):
    pill = make(qapp)
    flags = pill.windowFlags()
    for flag in (Qt.WindowDoesNotAcceptFocus, Qt.FramelessWindowHint,
                 Qt.WindowStaysOnTopHint, Qt.Tool):
        assert flags & flag
    assert pill.testAttribute(Qt.WA_ShowWithoutActivating)
    assert pill.testAttribute(Qt.WA_TranslucentBackground)


def test_animation_timer_runs_only_while_needed(qapp, clock):
    pill = make(qapp, "idle")
    assert not pill.animating()
    pill.set_state("recording")
    assert pill.animating()
    pill.set_state("processing")
    assert pill.animating()
    run(pill, clock, 0.5)  # fully faded in
    pill.set_state("idle")
    assert pill.animating()  # still fading out
    run(pill, clock, 3.0)
    assert not pill.animating()


def test_unknown_state_is_rejected(qapp):
    with pytest.raises(ValueError):
        make(qapp).set_state("sleeping")
