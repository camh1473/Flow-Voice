import re

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from flowvoice.config import Config
from flowvoice.history import HistoryEntry
from flowvoice.ui import theme
from flowvoice.ui.home_view import HomeView
from flowvoice.ui.main_window import MainWindow


@pytest.fixture
def window(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "window.ini"), QSettings.IniFormat)
    saved = []
    win = MainWindow(Config(), None, saved.append, settings=settings)
    yield win
    win.request_quit()
    win.close()


def _entry(text: str = "Hello there, world.") -> HistoryEntry:
    return HistoryEntry(1, "2026-10-05T09:30:00", "hello there world", text, "notepad.exe")


def _font_sizes(css: str) -> list[float]:
    return [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css)]


def test_sidebar_has_exactly_home_history_settings(window):
    items = [window.sidebar.item(i).text() for i in range(window.sidebar.count())]
    assert items == ["Home", "History", "Settings"]


def test_selecting_sidebar_item_shows_matching_page(window):
    for row, page in enumerate([window.home, window.history_view, window.settings_view]):
        window.sidebar.setCurrentRow(row)
        assert window.pages.currentWidget() is page


def test_set_history_view_replaces_page(window):
    new = QWidget()
    window.set_history_view(new)
    assert window.history_view is new
    window.sidebar.setCurrentRow(1)
    assert window.pages.currentWidget() is new


def test_set_settings_view_replaces_page(window):
    new = QWidget()
    window.set_settings_view(new)
    window.sidebar.setCurrentRow(2)
    assert window.pages.currentWidget() is new


def test_set_state_changes_status_text(qapp):
    home = HomeView()
    idle = home.status_label.text()
    home.set_state("recording")
    assert home.status_label.text() != idle
    assert "listening" in home.status_label.text().lower()


def test_set_state_rejects_unknown(qapp):
    with pytest.raises(ValueError):
        HomeView().set_state("bogus")


def test_show_entry_displays_text_and_copy_puts_it_on_clipboard(qapp):
    home = HomeView()
    home.show_entry(_entry("Copy me, please."))
    assert home.entry_label.text() == "Copy me, please."
    QGuiApplication.clipboard().setText("")
    home.copy_button.click()
    assert QGuiApplication.clipboard().text() == "Copy me, please."


def test_copy_disabled_before_any_entry(qapp):
    assert not HomeView().copy_button.isEnabled()


def test_toggle_button_emits_toggle_clicked(qapp):
    home = HomeView()
    hits = []
    home.toggle_clicked.connect(lambda: hits.append(1))
    home.toggle_button.click()
    assert hits == [1]


def test_toggle_button_label_follows_state(qapp):
    home = HomeView()
    assert "Start" in home.toggle_button.text()
    home.set_state("recording")
    assert "Stop" in home.toggle_button.text()


def test_hint_sets_hint_text(qapp):
    home = HomeView()
    home.hint("Hold F9 to talk")
    assert home.hint_label.text() == "Hold F9 to talk"


def test_close_event_hides_without_quitting(window):
    quits = []
    window.quit_requested.connect(lambda: quits.append(1))
    window.show()
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert not window.isVisible()
    assert quits == []


def test_request_quit_emits_and_allows_close(window):
    quits = []
    window.quit_requested.connect(lambda: quits.append(1))
    window.request_quit()
    assert quits == [1]
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_geometry_saved_to_given_settings(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "geo.ini"), QSettings.IniFormat)
    win = MainWindow(Config(), None, lambda c: None, settings=settings)
    win.resize(700, 500)
    win.closeEvent(QCloseEvent())
    assert settings.value("geometry") is not None
    again = MainWindow(Config(), None, lambda c: None, settings=settings)
    assert (again.width(), again.height()) == (700, 500)


def test_close_flushes_geometry_to_disk(qapp, tmp_path):
    path = tmp_path / "flush.ini"
    settings = QSettings(str(path), QSettings.IniFormat)
    win = MainWindow(Config(), None, lambda c: None, settings=settings)
    win.show()
    win.close()  # hides; a restart then os._exit()s without Qt's lazy flush
    assert path.exists() and "geometry" in path.read_text(encoding="latin-1")


def test_mics_stored(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "m.ini"), QSettings.IniFormat)
    mics = [("Default", None), ("USB Mic", 3)]
    win = MainWindow(Config(), None, lambda c: None, settings=settings, mics=mics)
    assert win.mics == mics


def test_stylesheet_has_radius_and_dark_differs():
    dark = theme.stylesheet(True, 1.0)
    assert "border-radius" in dark
    assert dark != theme.stylesheet(False, 1.0)


def test_stylesheet_scale_enlarges_fonts():
    small = _font_sizes(theme.stylesheet(False, 1.0))
    big = _font_sizes(theme.stylesheet(False, 1.5))
    assert small and len(small) == len(big)
    assert all(b > s for s, b in zip(small, big))


def test_apply_scale_restyles_window(window):
    before = window.styleSheet()
    window.apply_scale(1.4)
    assert window.styleSheet() != before
    assert max(_font_sizes(window.styleSheet())) > max(_font_sizes(before))


def test_is_dark_reads_palette(qapp):
    assert isinstance(theme.is_dark(qapp), bool)


def test_hint_mentions_ptt_key(window):
    assert "Right Ctrl" in window.home.hint_label.text()


def test_placeholder_pages_have_labels(window):
    assert window.history_view.findChild(QLabel) is not None
