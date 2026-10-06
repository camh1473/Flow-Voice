import pytest
from PySide6.QtGui import QGuiApplication

from flowvoice.history import History, HistoryEntry
from flowvoice.ui.history_view import HistoryView


@pytest.fixture
def hist(tmp_path):
    h = History(tmp_path / "h.db")
    h.add("buy milk raw", "Buy milk.", "notepad.exe")
    h.add("call sam raw", "Call Sam.", "outlook.exe")
    h.add("send floor plans", "Send the floor plans.", "chrome.exe")
    return h


def _view(hist, confirm=lambda m: True):
    return HistoryView(hist, confirm=confirm)


def _texts(view):
    return [view.list.item(i).data(256).clean_text for i in range(view.row_count())]


def test_refresh_shows_rows_newest_first(qapp, hist):
    view = _view(hist)
    assert view.row_count() == 3
    assert _texts(view)[0] == "Send the floor plans."


def test_search_filters_rows(qapp, hist):
    view = _view(hist)
    view.search.setText("milk")
    assert _texts(view) == ["Buy milk."]


def test_copy_puts_clean_text_on_clipboard(qapp, hist):
    view = _view(hist)
    view.list.setCurrentRow(1)
    view.copy_button.click()
    assert QGuiApplication.clipboard().text() == "Call Sam."


def test_delete_removes_row_and_db_entry(qapp, hist):
    view = _view(hist)
    view.list.setCurrentRow(0)
    view.delete_button.click()
    assert view.row_count() == 2
    assert len(hist.list()) == 2
    assert "Send the floor plans." not in [e.clean_text for e in hist.list()]


def test_clear_all_respects_confirm(qapp, hist):
    view = _view(hist, confirm=lambda m: False)
    view.clear_button.click()
    assert view.row_count() == 3 and len(hist.list()) == 3
    view = _view(hist, confirm=lambda m: True)
    view.clear_button.click()
    assert view.row_count() == 0 and hist.list() == []
    assert view.message.text() == "Nothing here yet"


def test_prepend_adds_on_top_and_ignores_unsaved(qapp, hist):
    view = _view(hist)
    view.prepend(HistoryEntry(None, "2026-10-05T10:00:00", "x", "Unsaved", ""))
    assert view.row_count() == 3
    view.prepend(HistoryEntry(99, "2026-10-05T10:00:00", "x", "Fresh one.", "a.exe"))
    assert view.row_count() == 4 and _texts(view)[0] == "Fresh one."


def test_prepend_respects_active_query(qapp, hist):
    view = _view(hist)
    view.search.setText("milk")
    view.prepend(HistoryEntry(98, "2026-10-05T10:00:00", "x", "Unrelated.", ""))
    assert view.row_count() == 1
    view.prepend(HistoryEntry(99, "2026-10-05T10:00:00", "x", "More milk.", ""))
    assert _texts(view)[0] == "More milk."


def test_history_none_shows_off_state(qapp):
    view = HistoryView(None)
    assert view.message.text() == "History is off"
    assert not view.clear_button.isEnabled() and not view.search.isEnabled()
    view.refresh()
    view.prepend(HistoryEntry(1, "2026-10-05T10:00:00", "x", "y", ""))
    assert view.row_count() == 0


def test_empty_history_shows_friendly_state(qapp, tmp_path):
    view = _view(History(tmp_path / "e.db"))
    assert view.message.text() == "Nothing here yet"


def test_db_error_shows_inline_message(qapp, hist):
    view = _view(hist)

    def boom(**kwargs):
        raise RuntimeError("db locked")

    hist.list = boom
    view.refresh()
    assert view.message.text() == "History unavailable"
    assert view.row_count() == 0


def _long_view(hist):
    hist.add("long", "word " * 80, "x.exe")
    view = _view(hist)
    view.resize(520, 600)
    view.show()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    return view


@pytest.mark.parametrize("scale", [1.0, 1.5])
def test_set_scale_reserves_scaled_gap(qapp, hist, scale):
    from flowvoice.ui import theme
    view = _long_view(hist)
    view.set_scale(scale)
    item = view.list.item(0)
    body = view.list.itemWidget(item)
    width = view.list.viewport().width()
    bottom, _side = theme.history_gaps(scale)
    assert item.sizeHint().height() >= body.heightForWidth(width) + bottom
    assert view.gaps == theme.history_gaps(scale)


def test_main_window_scale_propagates_to_history(qapp, tmp_path):
    from flowvoice.config import Config
    from flowvoice.ui import theme
    from flowvoice.ui.main_window import MainWindow
    from PySide6.QtCore import QSettings
    win = MainWindow(Config(), History(tmp_path / "w.db"), lambda c: None,
                     settings=QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat), dark=False)
    win.apply_scale(1.5)
    assert win.history_view.gaps == theme.history_gaps(1.5)
    win.request_quit()
    win.close()


# --- "Saving is off" banner: a new dictation never reaches History while saving is off ---

def test_banner_hidden_while_saving_is_on(qapp, hist):
    view = _view(hist)
    view.set_saving(True)
    assert not view.banner.isVisibleTo(view)


def test_banner_shown_when_saving_is_off(qapp, hist):
    view = _view(hist)
    view.set_saving(False)
    assert view.banner.isVisibleTo(view)
    assert "off" in view.banner_text.text().lower()
    view.set_saving(True)
    assert not view.banner.isVisibleTo(view)


def test_banner_never_shown_when_history_itself_is_unavailable(qapp):
    view = HistoryView(None)
    view.set_saving(False)
    assert not view.banner.isVisibleTo(view)


def test_turn_on_button_emits_enable_saving_requested_once(qapp, hist):
    view = _view(hist)
    view.set_saving(False)
    got = []
    view.enable_saving_requested.connect(lambda: got.append(1))
    view.turn_on_button.click()
    assert got == [1]
