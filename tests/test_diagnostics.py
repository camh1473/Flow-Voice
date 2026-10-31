import logging
import sys
import threading

import pytest

from flowvoice import diagnostics


@pytest.fixture(autouse=True)
def _clean():
    diagnostics.teardown()
    yield
    diagnostics.teardown()


def read_log(tmp_path):
    for h in logging.getLogger("flowvoice").handlers:
        h.flush()
    return (tmp_path / diagnostics.LOG_NAME).read_text(encoding="utf-8")


def test_first_start_is_not_reported_as_a_crash(tmp_path):
    assert diagnostics.setup(tmp_path) is False
    assert (tmp_path / diagnostics.MARKER_NAME).exists()
    assert "start pid=" in read_log(tmp_path)


def test_clean_exit_removes_marker_so_next_start_is_clean(tmp_path):
    diagnostics.setup(tmp_path)
    diagnostics.mark_clean_exit()
    assert not (tmp_path / diagnostics.MARKER_NAME).exists()
    diagnostics.teardown()
    assert diagnostics.setup(tmp_path) is False


def test_leftover_marker_means_previous_run_ended_unexpectedly(tmp_path):
    diagnostics.setup(tmp_path)
    diagnostics.teardown()  # the process "died": marker never removed
    assert diagnostics.setup(tmp_path) is True
    assert "did not exit cleanly" in read_log(tmp_path)


def test_mark_clean_exit_twice_is_harmless(tmp_path):
    diagnostics.setup(tmp_path)
    diagnostics.mark_clean_exit()
    diagnostics.mark_clean_exit()
    assert read_log(tmp_path).count("clean exit") == 1


def test_mark_clean_exit_before_setup_is_harmless():
    diagnostics.mark_clean_exit()


def test_unhandled_exception_is_logged_with_traceback(tmp_path):
    diagnostics.setup(tmp_path)
    try:
        raise ValueError("kaboom-main")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    text = read_log(tmp_path)
    assert "unhandled exception" in text and "kaboom-main" in text and "Traceback" in text


def test_unhandled_thread_exception_is_logged_with_thread_name(tmp_path):
    diagnostics.setup(tmp_path)

    def boom():
        raise RuntimeError("kaboom-thread")

    t = threading.Thread(target=boom, name="worker-x")
    t.start()
    t.join()
    text = read_log(tmp_path)
    assert "worker-x" in text and "kaboom-thread" in text


def test_hooks_restored_on_teardown(tmp_path):
    before = sys.excepthook, threading.excepthook, sys.unraisablehook
    diagnostics.setup(tmp_path)
    assert sys.excepthook is not before[0]
    diagnostics.teardown()
    assert (sys.excepthook, threading.excepthook, sys.unraisablehook) == before


def test_repeated_setup_does_not_duplicate_log_lines(tmp_path):
    diagnostics.setup(tmp_path)
    diagnostics.setup(tmp_path)
    assert read_log(tmp_path).count("start pid=") == 2  # one per setup, not 1 + 2


def test_setup_never_raises_on_unusable_directory(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert diagnostics.setup(blocker / "sub") is False


def test_native_crash_log_is_created(tmp_path):
    diagnostics.setup(tmp_path)
    assert (tmp_path / diagnostics.NATIVE_NAME).exists()


def test_qt_warning_is_logged(tmp_path, qapp):
    from PySide6.QtCore import QtMsgType, qCritical

    diagnostics.setup(tmp_path)
    qCritical("qt-test-message")
    assert "qt-test-message" in read_log(tmp_path)
    assert QtMsgType.QtCriticalMsg is not None
