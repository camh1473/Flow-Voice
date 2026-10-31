"""Crash diagnostics: a rolling log file, native-crash tracebacks and a clean-exit marker.

The app runs under pythonw, which has no console: without this a crash leaves no trace at
all. Everything lands in %APPDATA%\\FlowVoice\\:

  flowvoice.log      rolling log (3 x 512 KB): start/stop, unhandled errors, Qt warnings, mic events
  native-crash.log   faulthandler dump if the process dies in native code (Qt, PortAudio, CTranslate2)
  running.marker     exists only while the app runs; still there at the next start means the
                     last run did not exit cleanly (crash, force-kill, power loss)

Dictated text is never written to the log.
"""
import faulthandler
import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path

LOG_NAME = "flowvoice.log"
NATIVE_NAME = "native-crash.log"
MARKER_NAME = "running.marker"
MAX_BYTES = 512 * 1024
BACKUPS = 3

log = logging.getLogger("flowvoice")

_state: dict = {}


def default_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "FlowVoice"


def log_path(directory: Path | None = None) -> Path:
    return (directory or default_dir()) / LOG_NAME


def setup(directory: Path | None = None) -> bool:
    """Start logging and crash capture. Returns True if the previous run ended unexpectedly.

    Never raises: diagnostics must not be the reason the app fails to start.
    """
    directory = Path(directory) if directory else default_dir()
    previous_unclean = False
    try:
        directory.mkdir(parents=True, exist_ok=True)
        teardown()
        marker = directory / MARKER_NAME
        previous_unclean = marker.exists()

        handler = logging.handlers.RotatingFileHandler(
            directory / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False

        native = open(directory / NATIVE_NAME, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=native, all_threads=True)

        _state.update(directory=directory, handler=handler, native=native, marker=marker,
                      excepthook=sys.excepthook, threadhook=threading.excepthook,
                      unraisable=sys.unraisablehook)
        sys.excepthook = _log_exception
        threading.excepthook = _log_thread_exception
        sys.unraisablehook = _log_unraisable
        _install_qt_handler()

        if previous_unclean:
            log.warning("previous run did not exit cleanly (crash, force-kill or power loss)")
        log.info("start pid=%s python=%s", os.getpid(), sys.version.split()[0])
        marker.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass
    return previous_unclean


def mark_clean_exit() -> None:
    """Call when the app is shutting down on purpose; safe to call more than once."""
    marker = _state.pop("marker", None)
    if marker is None:
        return
    try:
        marker.unlink(missing_ok=True)
        log.info("clean exit pid=%s", os.getpid())
    except Exception:
        pass


def teardown() -> None:
    """Undo setup (tests, repeated setup)."""
    handler = _state.pop("handler", None)
    if handler is not None:
        log.removeHandler(handler)
        handler.close()
    native = _state.pop("native", None)
    if native is not None:
        try:
            faulthandler.disable()
            native.close()
        except Exception:
            pass
    for key, restore in (("excepthook", "sys.excepthook"), ("threadhook", "threading.excepthook"),
                         ("unraisable", "sys.unraisablehook")):
        old = _state.pop(key, None)
        if old is not None:
            if restore == "sys.excepthook":
                sys.excepthook = old
            elif restore == "threading.excepthook":
                threading.excepthook = old
            else:
                sys.unraisablehook = old
    _state.pop("directory", None)
    _state.pop("marker", None)


def _log_exception(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        return
    log.critical("unhandled exception", exc_info=(exc_type, exc, tb))


def _log_thread_exception(args) -> None:
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread else "?"
    log.critical("unhandled exception in thread %s", name,
                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def _log_unraisable(args) -> None:
    log.error("unraisable exception: %s", args.err_msg or "",
              exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def _install_qt_handler() -> None:
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        return
    levels = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
              QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
              QtMsgType.QtFatalMsg: logging.CRITICAL}

    def handler(kind, context, message) -> None:
        level = levels.get(kind, logging.WARNING)
        if level >= logging.WARNING:
            log.log(level, "qt: %s", message)

    qInstallMessageHandler(handler)
