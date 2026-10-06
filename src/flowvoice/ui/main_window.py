"""Main window: sidebar (Home / History / Settings) over a stack of pages."""
import dataclasses
from typing import Callable

from PySide6.QtCore import QRect, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flowvoice.config import Config
from flowvoice.history import History
from flowvoice.settings_logic import mic_choices
from flowvoice.ui import theme
from flowvoice.ui.history_view import HistoryView
from flowvoice.ui.home_view import HomeView
from flowvoice.ui.hotkey_edit import pretty_key
from flowvoice.ui.settings_view import SettingsView

PAGES = ("Home", "History", "Settings")
GLYPHS = {"Home": "\ue80f", "History": "\ue81c", "Settings": "\ue713"}
ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
DEFAULT_SIZE = (880, 620)
MIN_SIZE = (640, 460)
SIDEBAR_WIDTH = 200
ICON_PX = 18


def hint_text(config: Config) -> str:
    key = pretty_key(config.ptt_key)
    if config.hands_free:
        return f"Hold {key} to talk, or double-tap it to go hands-free."
    return f"Hold {key} to talk."


def _icon_font() -> str | None:
    families = set(QFontDatabase.families())
    return next((f for f in ICON_FONTS if f in families), None)


def _glyph_pixmap(family: str, glyph: str, color: str, px: int, ratio: float) -> QPixmap:
    pix = QPixmap(round(px * ratio), round(px * ratio))
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = QFont(family)
    font.setPixelSize(round(px * 0.9))
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(QRect(0, 0, px, px), Qt.AlignCenter, glyph)
    painter.end()
    return pix


class MainWindow(QMainWindow):
    """Closing hides the window; only request_quit() lets it really close.

    Page seam: `set_history_view(widget)` and `set_settings_view(widget)` swap a page in the
    stack, update the matching attribute and pass the UI scale to the page's `set_scale`;
    a new settings page also gets the last `set_ai_status`.
    `capture_started` / `capture_finished` forward the current settings page's hotkey
    capture lifecycle (the app pauses its global hotkeys in between).
    """

    quit_requested = Signal()
    capture_started = Signal()
    capture_finished = Signal()

    def __init__(
        self,
        config: Config,
        history: History | None,
        on_save_config: Callable[[Config], None],
        settings: QSettings | None = None,
        mics: list[tuple[str, int | None]] | None = None,
        dark: bool | None = None,
        ai_probe=None,
    ) -> None:
        super().__init__()
        self.config = config
        self.history = history
        self.on_save_config = on_save_config
        self.mics = mics
        self._settings = settings if settings is not None else QSettings("FlowVoice", "FlowVoice")
        self._quitting = False
        self._ai_status = ("off", "")
        self._follow_system = dark is None
        app = QApplication.instance()
        self._dark = theme.is_dark(app) if dark is None else dark
        self._scale = config.ui_scale
        self.setWindowTitle("Flow Voice")

        content = QWidget()
        content.setObjectName("Content")
        row = QHBoxLayout(content)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("Sidebar")
        side = QVBoxLayout(self.sidebar_frame)
        side.setContentsMargins(12, 22, 12, 16)
        side.setSpacing(0)
        title = QLabel("Flow Voice")
        title.setObjectName("SidebarTitle")
        side.addWidget(title)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("SidebarList")
        self.sidebar.setFocusPolicy(Qt.NoFocus)
        self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for name in PAGES:
            QListWidgetItem(name, self.sidebar)
        side.addWidget(self.sidebar, 1)
        row.addWidget(self.sidebar_frame)

        self.pages = QStackedWidget()
        self.home = HomeView()
        self.home.hint(hint_text(config))
        self.history_view: QWidget = HistoryView(history)
        self._link_history(self.history_view)
        self._set_saving(config.save_history)
        self.settings_view: QWidget = SettingsView(config, self.mics or mic_choices(), on_save_config,
                                                   ai_probe=ai_probe)
        self._link_capture(self.settings_view, True)
        for page in (self.home, self.history_view, self.settings_view):
            self.pages.addWidget(page)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(content)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        hints = QGuiApplication.styleHints()
        if self._follow_system and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_scheme_changed)

        self.apply_scale(self._scale)
        self._restore_geometry()

    def _link_history(self, page: QWidget) -> None:
        signal = getattr(page, "enable_saving_requested", None)
        if signal is not None:
            signal.connect(self._enable_saving)

    def _set_saving(self, enabled: bool) -> None:
        setter = getattr(self.history_view, "set_saving", None)
        if setter is not None:
            setter(enabled)

    def _enable_saving(self) -> None:
        """The banner's Turn on button: save the current config with history enabled."""
        self.on_save_config(dataclasses.replace(self.config, save_history=True))

    def update_saving(self, config: Config) -> None:
        """Follow a live config change: banner state and the Settings page switch."""
        self.config = config
        self._set_saving(config.save_history)
        loader = getattr(self.settings_view, "load", None)
        if loader is not None:
            loader(config)

    def apply_scale(self, scale: float) -> None:
        self._scale = scale
        self.setStyleSheet(theme.stylesheet(self._dark, scale))
        self.setMinimumSize(round(MIN_SIZE[0] * scale), round(MIN_SIZE[1] * scale))
        self.sidebar_frame.setFixedWidth(round(SIDEBAR_WIDTH * scale))
        self.sidebar.setIconSize(QSize(round(ICON_PX * scale), round(ICON_PX * scale)))
        self._refresh_icons()
        self._scale_pages()

    def _scale_pages(self) -> None:
        for page in (self.history_view, self.settings_view):
            setter = getattr(page, "set_scale", None)
            if setter is not None:
                setter(self._scale)

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.apply_scale(self._scale)

    def is_dark(self) -> bool:
        return self._dark

    def set_history_view(self, widget: QWidget) -> None:
        self._replace_page(self.history_view, widget)
        self.history_view = widget
        self._link_history(widget)
        self._set_saving(self.config.save_history)
        self._scale_pages()

    def set_settings_view(self, widget: QWidget) -> None:
        if widget is not self.settings_view:
            self._link_capture(self.settings_view, False)
            self._link_capture(widget, True)
        self._replace_page(self.settings_view, widget)
        self.settings_view = widget
        self._scale_pages()
        self._forward_ai_status()

    def set_ai_status(self, status: str, detail: str) -> None:
        """Show the AI status on the Settings page; safe to call from any thread."""
        self._ai_status = (status, detail)
        self._forward_ai_status()

    def _forward_ai_status(self) -> None:
        setter = getattr(self.settings_view, "set_ai_status", None)
        if setter is not None:
            setter(*self._ai_status)

    def _link_capture(self, page: QWidget, connect: bool) -> None:
        for name in ("capture_started", "capture_finished"):
            source = getattr(page, name, None)
            if source is None:
                continue
            if connect:
                source.connect(getattr(self, name))
            else:
                source.disconnect(getattr(self, name))

    def show_page(self, name: str) -> None:
        self.sidebar.setCurrentRow(PAGES.index(name))

    def request_quit(self) -> None:
        self._quitting = True
        self.quit_requested.emit()

    def closeEvent(self, event) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.sync()  # restart os._exit()s, skipping Qt's lazy flush
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

    def _replace_page(self, old: QWidget, new: QWidget) -> None:
        if new is old:
            return
        index = self.pages.indexOf(old)
        current = self.pages.currentIndex() == index
        self.pages.removeWidget(old)
        self.pages.insertWidget(index, new)
        if current:
            self.pages.setCurrentIndex(index)
        old.deleteLater()

    def _restore_geometry(self) -> None:
        saved = self._settings.value("geometry")
        if saved is None or not self.restoreGeometry(saved):
            self.resize(*DEFAULT_SIZE)

    def _on_scheme_changed(self, *_) -> None:
        self.set_dark(theme.is_dark(QApplication.instance()))

    def _refresh_icons(self) -> None:
        family = _icon_font()
        if family is None:
            return
        colors = theme.tokens(self._dark)
        px = round(ICON_PX * self._scale)
        ratio = self.devicePixelRatioF() or 1.0
        for i, name in enumerate(PAGES):
            icon = QIcon()
            icon.addPixmap(_glyph_pixmap(family, GLYPHS[name], colors["accent"], px, ratio), QIcon.Normal)
            icon.addPixmap(_glyph_pixmap(family, GLYPHS[name], "#ffffff", px, ratio), QIcon.Selected)
            self.sidebar.item(i).setIcon(icon)

