"""Qt shell: application, pill, main window and tray, plus the entry point's wiring helpers."""
import sys
import threading
from typing import Callable

from PySide6.QtCore import QObject, QRectF, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from flowvoice.config import Config
from flowvoice.history import History, HistoryEntry
from flowvoice.settings_logic import needs_restart
from flowvoice.ui.bridge import QtUi
from flowvoice.ui.main_window import MainWindow, hint_text
from flowvoice.ui.pill import COLORS, PillWidget

TICK_MS = 200
ICON_PX = 64
TITLE = "Flow Voice"


def _quit_qt() -> None:
    QApplication.quit()


def tray_icon(state: str = "idle") -> QIcon:
    """A round badge in the pill's state colour with a white microphone, drawn with QPainter."""
    pix = QPixmap(ICON_PX, ICON_PX)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(COLORS.get(state, COLORS["idle"])))
    p.drawEllipse(QRectF(2, 2, ICON_PX - 4, ICON_PX - 4))
    white = QColor("#ffffff")
    p.setBrush(white)
    p.drawRoundedRect(QRectF(24, 12, 16, 26), 8, 8)
    pen = p.pen()
    pen.setColor(white)
    pen.setWidthF(4.0)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(17, 18, 30, 26), 180 * 16, 180 * 16)
    p.drawLine(32, 44, 32, 52)
    p.drawLine(24, 52, 40, 52)
    p.end()
    return QIcon(pix)


class Shell(QObject):
    """Owns the Qt main thread. Worker threads talk to it only through `ui` (QtUi signals).

    Settable callbacks: `on_toggle` (pill click, Home Start/Stop, tray Start/Stop),
    `on_tick` (every 200 ms), `on_quit` (runs first on quit), `on_save_config` (Settings).
    Until the app sets `on_toggle`, a toggle says the model is still loading.
    """

    def __init__(self, config: Config, history: History | None, *,
                 settings: QSettings | None = None,
                 mics: list[tuple[str, int | None]] | None = None,
                 dark: bool | None = None, first_run: bool = False) -> None:
        self.qapp = QApplication.instance() or QApplication(sys.argv[:1])
        QApplication.setStyle("Fusion")
        self.qapp.setQuitOnLastWindowClosed(False)
        super().__init__()
        self.config = config
        self.on_toggle: Callable[[], None] | None = self._not_ready
        self.on_tick: Callable[[], None] | None = None
        self.on_quit: Callable[[], None] | None = None
        self.on_save_config: Callable[[Config], None] | None = None
        self._down = False

        self.ui = QtUi()
        self.pill = PillWidget(config.ui_scale, config.pill_always_visible)
        self.window = MainWindow(config, history, self._save_config, settings=settings,
                                 mics=mics, dark=dark)

        self._menu = QMenu()
        self.open_action = QAction("Open", self._menu)
        self.start_stop_action = QAction("Start dictation", self._menu)
        self.quit_action = QAction("Quit", self._menu)
        self._menu.addAction(self.open_action)
        self._menu.addAction(self.start_stop_action)
        self._menu.addSeparator()
        self._menu.addAction(self.quit_action)
        self.tray = QSystemTrayIcon(tray_icon("idle"))
        self.tray.setToolTip(TITLE)
        self.tray.setContextMenu(self._menu)

        self.ui.state_changed.connect(self._on_state)
        self.ui.level_changed.connect(self.pill.set_level)
        self.ui.message.connect(self.notify)
        self.ui.entry_added.connect(self._on_entry)
        self.ui.window_requested.connect(self.show_page)
        self.pill.clicked.connect(self._toggle)
        self.window.home.toggle_clicked.connect(self._toggle)
        self.start_stop_action.triggered.connect(self._toggle)
        self.open_action.triggered.connect(self.open_window)
        self.quit_action.triggered.connect(self.quit)
        self.tray.activated.connect(self._on_tray_activated)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(TICK_MS)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start()

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        if first_run:
            self.open_window()

    def run(self) -> int:
        return self.qapp.exec()

    def apply_config(self, cfg: Config) -> None:
        self.config = cfg
        self.pill.apply(cfg.ui_scale, cfg.pill_always_visible)
        self.window.config = cfg
        self.window.apply_scale(cfg.ui_scale)
        self.window.home.hint(hint_text(cfg))

    @Slot(str)
    def notify(self, message: str) -> None:
        if self.tray.isVisible():
            self.tray.showMessage(TITLE, message, QSystemTrayIcon.Information, 3000)

    def open_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    @Slot(str)
    def show_page(self, page: str) -> None:
        self.window.show_page(page)
        self.open_window()

    def _not_ready(self) -> None:
        self.ui.notify("Still loading the speech model...")

    def shutdown(self) -> None:
        """Stop callbacks, run `on_quit`, save the window geometry and hide everything. Idempotent."""
        if self._down:
            return
        self._down = True
        self.tick_timer.stop()
        self.on_toggle = self.on_tick = None
        if self.on_quit is not None:
            try:
                self.on_quit()
            except Exception:
                pass
        self.window.request_quit()
        self.window.close()
        self.pill.hide()
        self.tray.hide()

    @Slot()
    def quit(self) -> None:
        self.shutdown()
        _quit_qt()

    @Slot(str)
    def _on_state(self, state: str) -> None:
        self.pill.set_state(state)
        self.window.home.set_state(state)
        recording = state == "recording"
        self.start_stop_action.setText("Stop dictation" if recording else "Start dictation")
        self.tray.setIcon(tray_icon(state))

    @Slot(object)
    def _on_entry(self, entry: HistoryEntry) -> None:
        self.window.home.show_entry(entry)
        prepend = getattr(self.window.history_view, "prepend", None)
        if prepend is not None:
            prepend(entry)

    @Slot()
    def _toggle(self) -> None:
        if self.on_toggle is not None:
            self.on_toggle()

    @Slot()
    def _tick(self) -> None:
        if self.on_tick is not None:
            self.on_tick()

    def _save_config(self, cfg: Config) -> None:
        if self.on_save_config is not None:
            self.on_save_config(cfg)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_window()


class HookGroup:
    """The global keyboard hooks, switched on and off together; thread safe.

    `pause`/`resume` bracket a Settings hotkey capture; `close` is final (quit/restart).
    Hooks handed to `set` while paused are enabled on `resume`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hooks: list = []
        self._paused = False
        self._closed = False
        self._on = False

    @property
    def closed(self) -> bool:
        return self._closed

    def set(self, hooks: list) -> None:
        with self._lock:
            if self._closed:
                return
            self._switch(False)
            self._hooks = list(hooks)
            self._sync()

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            self._sync()

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self._sync()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._sync()

    def _sync(self) -> None:
        self._switch(not self._paused and not self._closed)

    def _switch(self, on: bool) -> None:
        if on == self._on:
            return
        if not on:
            for h in self._hooks:
                h.disable()
            self._on = False
            return
        done = []
        try:
            for h in self._hooks:
                h.enable()
                done.append(h)
        except Exception:
            for h in done:
                h.disable()
            raise
        self._on = True


def wire_capture(window: MainWindow, hooks: HookGroup, get_app: Callable[[], object]) -> None:
    """Pause the hooks while Settings captures a hotkey, cancelling any take in progress."""

    def started() -> None:
        app = get_app()
        if app is not None and app.talk.state != "idle":
            app.other_key("esc")
        hooks.pause()

    window.capture_started.connect(started)
    window.capture_finished.connect(hooks.resume)


def restart_process(*, shutdown: Callable[[], None], spawn: Callable[[], None],
                    exit: Callable[[], None], notify: Callable[[str], None]) -> None:
    """Shut down, start the replacement process, then always exit (even if a step fails).

    A failed shutdown skips the spawn so two instances never hook the keyboard at once.
    """
    try:
        shutdown()
        spawn()
    except Exception as e:
        try:
            notify(f"Restart failed: {e}")
        except Exception:
            pass
    finally:
        exit()


def apply_saved_config(old: Config, new: Config, *, save: Callable[[Config], None], app,
                       apply_ui: Callable[[Config], None], restart: Callable[[], None],
                       notify: Callable[[str], None]) -> str:
    """Settings save: persist, then restart or apply live. Returns 'restart', 'live' or 'failed'."""
    try:
        save(new)
    except Exception as e:
        notify(f"Could not save settings: {e}")
        return "failed"
    if needs_restart(old, new):
        notify("Applying settings...")
        restart()
        return "restart"
    if app is not None:
        app.apply_config(new)
    apply_ui(new)
    notify("Settings saved")
    return "live"
