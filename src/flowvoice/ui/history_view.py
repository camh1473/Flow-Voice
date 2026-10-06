"""History tab: searchable list of past dictations shown as card rows."""
from typing import Callable

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowvoice.history import History, HistoryEntry
from flowvoice.ui.home_view import format_meta

MSG_OFF = "History is off"
MSG_EMPTY = "Nothing here yet"
MSG_NO_MATCH = "No matches"
MSG_ERROR = "History unavailable"
CLEAR_PROMPT = "Delete all history? This cannot be undone."
ENTRY_ROLE = Qt.UserRole
ROW_GAP = 10  # matches the bottom margin of #HistoryList::item in theme.py
ROW_SIDE_GAP = 4  # right margin of the item, which the widget overlaps


def default_confirm(message: str) -> bool:
    answer = QMessageBox.question(None, "Flow Voice", message, QMessageBox.Yes | QMessageBox.No,
                                  QMessageBox.No)
    return answer == QMessageBox.Yes


def _row_widget(entry: HistoryEntry) -> QFrame:
    row = QFrame()
    row.setObjectName("HistoryRowBody")
    row.setAttribute(Qt.WA_TransparentForMouseEvents)
    layout = QVBoxLayout(row)
    layout.setContentsMargins(16, 12, 16 + ROW_SIDE_GAP, 12)
    layout.setSpacing(4)
    meta = QLabel(format_meta(entry))
    meta.setObjectName("Secondary")
    text = QLabel(entry.clean_text)
    text.setObjectName("EntryText")
    text.setWordWrap(True)
    text.setTextFormat(Qt.PlainText)
    layout.addWidget(meta)
    layout.addWidget(text)
    return row


class HistoryView(QWidget):
    def __init__(self, history: History | None,
                 confirm: Callable[[str], bool] = default_confirm,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._history = history
        self._confirm = confirm
        self._query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 24)
        root.setSpacing(14)
        title = QLabel("History")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        bar.addWidget(self.search, 1)
        self.copy_button = QPushButton("Copy")
        self.delete_button = QPushButton("Delete")
        self.clear_button = QPushButton("Clear all")
        self.clear_button.setProperty("variant", "destructive")
        for button, slot in ((self.copy_button, self._copy), (self.delete_button, self._delete),
                             (self.clear_button, self._clear)):
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(slot)
            bar.addWidget(button)
        root.addLayout(bar)

        self.list = QListWidget()
        self.list.setObjectName("HistoryList")
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.viewport().installEventFilter(self)
        root.addWidget(self.list, 1)

        self.message = QLabel("")
        self.message.setObjectName("Secondary")
        self.message.setAlignment(Qt.AlignCenter)
        root.addWidget(self.message, 1)

        self.refresh()

    def row_count(self) -> int:
        return self.list.count()

    def refresh(self, query: str = "") -> None:
        """Reload rows. Typing in the search box passes the query; no arg reuses it."""
        self._query = query or self.search.text().strip()
        self.list.clear()
        if self._history is None:
            self._show_message(MSG_OFF)
            return
        try:
            entries = self._history.list(query=self._query)
        except Exception:
            self._show_message(MSG_ERROR)
            return
        for entry in entries:
            self._add_row(entry)
        self._show_message("" if entries else (MSG_NO_MATCH if self._query else MSG_EMPTY))

    def prepend(self, entry: HistoryEntry) -> None:
        if entry.id is None or self._history is None or self.message.text() == MSG_ERROR:
            return
        q = self._query.lower()
        if q and q not in entry.clean_text.lower() and q not in entry.raw_text.lower():
            return
        self._add_row(entry, 0)
        self._show_message("")

    def eventFilter(self, watched, event) -> bool:
        if watched is self.list.viewport() and event.type() == QEvent.Resize:
            self._fit_rows()
        return super().eventFilter(watched, event)

    def _add_row(self, entry: HistoryEntry, index: int | None = None) -> None:
        item = QListWidgetItem()
        item.setData(ENTRY_ROLE, entry)
        if index is None:
            self.list.addItem(item)
        else:
            self.list.insertItem(index, item)
        self.list.setItemWidget(item, _row_widget(entry))
        self._fit(item)

    def _fit(self, item: QListWidgetItem) -> None:
        widget = self.list.itemWidget(item)
        if widget is None:
            return
        width = max(1, self.list.viewport().width())
        item.setSizeHint(QSize(width, widget.heightForWidth(width) + ROW_GAP))

    def _fit_rows(self) -> None:
        for i in range(self.list.count()):
            self._fit(self.list.item(i))

    def _show_message(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(bool(text))
        self.list.setVisible(not text)
        self._update_buttons()
        if not text:
            self._fit_rows()

    def _selected(self) -> QListWidgetItem | None:
        items = self.list.selectedItems()
        return items[0] if items else None

    def _update_buttons(self) -> None:
        live = self._history is not None and self.message.text() != MSG_ERROR
        picked = live and self._selected() is not None
        self.search.setEnabled(self._history is not None)
        self.copy_button.setEnabled(picked)
        self.delete_button.setEnabled(picked)
        self.clear_button.setEnabled(live and self.list.count() > 0)

    def _copy(self) -> None:
        item = self._selected()
        if item is not None:
            QGuiApplication.clipboard().setText(item.data(ENTRY_ROLE).clean_text)

    def _delete(self) -> None:
        item = self._selected()
        if item is None or self._history is None:
            return
        try:
            self._history.delete(item.data(ENTRY_ROLE).id)
        except Exception:
            self._show_message(MSG_ERROR)
            return
        self.list.takeItem(self.list.row(item))
        if self.list.count() == 0:
            self._show_message(MSG_NO_MATCH if self._query else MSG_EMPTY)
        self._update_buttons()

    def _clear(self) -> None:
        if self._history is None or not self._confirm(CLEAR_PROMPT):
            return
        try:
            self._history.clear()
        except Exception:
            self._show_message(MSG_ERROR)
            return
        self.refresh()





