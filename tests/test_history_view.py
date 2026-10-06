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
