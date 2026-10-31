import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from flowvoice import diagnostics
from flowvoice.ai_polish import MISSING, OFF, UNAVAILABLE, WARMING, AiService
from flowvoice.app import App
from flowvoice.autostart import set_autostart
from flowvoice.config import ensure_config_file, load_config, save_config
from flowvoice.history import History
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.paths import relaunch_command
from flowvoice.recorder import Recorder
from flowvoice.settings_logic import mic_choices
from flowvoice.singleinstance import SingleInstance
from flowvoice.tts import Speaker
from flowvoice.ui.hotkey_edit import pretty_key
from flowvoice.ui.shell import (
    HookGroup,
    Shell,
    apply_saved_config,
    restart_process,
    wire_capture,
)


log = logging.getLogger("flowvoice")

RESTART_ENV = "FLOWVOICE_RESTARTED"
RESTART_WAIT_SECONDS = 15.0  # a restarted copy waits for the old one to let go of the lock


def _already_running_notice() -> None:
    """pythonw has no console: say it in a small message box instead of exiting silently."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "Flow Voice is already running. Look for its icon in the system tray.",
            "Flow Voice", 0x40)
    except Exception:
        pass


def _open_history() -> History | None:
    try:
        return History()
    except Exception:
        return None


def _unhook_all() -> None:
    try:
        import keyboard
        keyboard.unhook_all()
    except Exception:
        pass


def ai_toast(prev_status: str, status: str, detail: str, *, enabled: bool) -> str | None:
    """The tray message for an AI status change, or None (only failures, only with AI on)."""
    if not enabled or status == prev_status:
        return None
    if status == UNAVAILABLE:
        return f"AI polish unavailable: {detail}"
    if status == MISSING:
        return f"AI model not installed. Run: {detail}"
    return None


def ai_status_handler(get_ui: Callable[[], object],
                      is_enabled: Callable[[], bool]) -> Callable[[str, str], None]:
    """AiService `on_status`: forward every status, toast a failure once.

    AiService calls this from worker threads with its lock held, so it only emits Qt signals.
    `warming` does not count as a change, so a failed retry does not toast again.
    """
    settled = [OFF]

    def on_status(status: str, detail: str) -> None:
        ui = get_ui()
        ui.set_ai_status(status, detail)
        if status == WARMING:
            return
        message = ai_toast(settled[0], status, detail, enabled=is_enabled())
        settled[0] = status
        if message:
            ui.notify(message)

    return on_status


def make_ai_service(get_ui: Callable[[], object], is_enabled: Callable[[], bool],
                    **kwargs) -> AiService:
    return AiService(on_status=ai_status_handler(get_ui, is_enabled), **kwargs)


def make_on_save(state, apply: Callable[[object, object], str]) -> Callable[[object], None]:
    """Settings save handler; `state.cfg` stays the old config until the save applied live.

    `state.ai_enabled` (read by the AI toast handler) is set before applying, because the AI
    warm-up started by `apply` can report a failure before `apply` returns.
    """

    def on_save(new) -> None:
        state.ai_enabled = new.ai_enabled
        result = apply(state.cfg, new)
        if result == "live":
            state.cfg = new
        elif result == "failed":
            state.ai_enabled = state.cfg.ai_enabled

    return on_save


class AiProbe:
    """What Settings may ask of the AI service: list models and run a test. Never starts Ollama."""

    def __init__(self, ai: AiService) -> None:
        self._ai = ai

    def list_models(self, cfg) -> list[str]:
        return self._ai.list_models(cfg)

    def test(self, cfg) -> str:
        return self._ai.test(cfg)


def selftest() -> int:
    """Check an installed/packaged copy without touching the running app.

    Loads the speech model, transcribes the bundled sample and opens the microphone briefly.
    No keyboard hooks, no window, no single-instance lock: safe next to a running copy.
    Prints one PASS/FAIL line per check and returns 0 only if all pass.
    """
    import wave

    import numpy as np

    from flowvoice.engine import Engine
    from flowvoice.paths import app_dir, bundled_model, frozen

    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            results.append((name, True, str(fn())))
        except Exception as e:
            results.append((name, False, f"{type(e).__name__}: {e}"))

    def sample_path():
        bundle = Path(getattr(sys, "_MEIPASS", app_dir()))  # PyInstaller's _internal folder
        for base in (bundle / "samples", app_dir() / "samples", app_dir() / "tests" / "data"):
            if (base / "hello.wav").is_file():
                return base / "hello.wav"
        raise FileNotFoundError("hello.wav sample not found")

    def speech():
        cfg = load_config()
        engine = Engine(cfg.model, device="cpu")
        with wave.open(str(sample_path()), "rb") as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        text = engine.transcribe(audio)
        if not text:
            raise RuntimeError("model returned no text for the sample")
        where = "bundled" if bundled_model(cfg.model) else "downloaded/cached"
        return f"{where} model {cfg.model!r} heard: {text!r}"

    def microphone():
        r = Recorder(device=load_config().mic_device)
        r.open()
        try:
            import time
            time.sleep(1.0)
            if not r.healthy():
                raise RuntimeError("stream opened but delivered no audio")
            return "stream delivers audio"
        finally:
            r.close()

    def libraries():
        import ctranslate2, keyboard, onnxruntime, pyperclip, sounddevice, win32com.client  # noqa: F401
        from PySide6 import QtWidgets  # noqa: F401
        return f"frozen={frozen()} ctranslate2={ctranslate2.__version__}"

    check("libraries", libraries)
    check("speech", speech)
    check("microphone", microphone)
    lines = [f"{'PASS' if ok else 'FAIL'} {name}: {detail}" for name, ok, detail in results]
    report = "\n".join(lines) + "\n"
    try:  # a windowed .exe has no console, so the report is also written next to the log
        out = diagnostics.default_dir() / "selftest.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
    except Exception:
        pass
    if sys.stdout is not None:
        print(report, end="", flush=True)
    return 0 if all(ok for _, ok, _ in results) else 1


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    restarted = os.environ.pop(RESTART_ENV, "") == "1"
    guard = SingleInstance()
    if not guard.acquire(wait=RESTART_WAIT_SECONDS if restarted else 0.0):
        _already_running_notice()
        return 0
    previous_crashed = diagnostics.setup()
    try:
        code = _run(guard, previous_crashed)
    except BaseException:
        # Logged, and the marker is left behind so the next start reports an unclean exit.
        log.critical("fatal error in main", exc_info=True)
        guard.release()
        raise
    diagnostics.mark_clean_exit()
    guard.release()
    return code


def _run(guard: SingleInstance, previous_crashed: bool) -> int:
    cfg = load_config()
    first_run = ensure_config_file(cfg)
    autostart_error = None
    try:
        set_autostart(cfg.start_with_windows)
    except Exception as e:
        autostart_error = e
    history = _open_history()
    hooks = HookGroup()
    state = SimpleNamespace(cfg=cfg, ai_enabled=cfg.ai_enabled, app=None, recorder=None,
                            lock=threading.Lock())

    # Quitting never stops Ollama (the user may run it for other things); AI threads are daemons.
    ai = make_ai_service(lambda: shell.ui, lambda: state.ai_enabled)
    shell = Shell(cfg, history, mics=mic_choices(), first_run=first_run, ai_probe=AiProbe(ai))
    ai.configure(state.cfg)  # warm up alongside the speech model; a no-op with AI off

    def stop_input() -> None:
        # Runs first on quit and on restart (which exits with os._exit, skipping main's tail):
        # a deliberate stop is recorded as clean and the lock is freed for a restarted copy.
        diagnostics.mark_clean_exit()
        guard.release()
        hooks.close()
        _unhook_all()
        with state.lock:
            recorder, state.recorder = state.recorder, None
        if recorder is not None:
            try:
                recorder.close()
            except Exception:
                pass

    def restart() -> None:
        restart_process(shutdown=shell.shutdown,
                        spawn=lambda: subprocess.Popen(relaunch_command(),
                                                                               env={**os.environ, RESTART_ENV: "1"}),
                        exit=lambda: os._exit(0), notify=shell.ui.notify)

    def apply_settings(old, new) -> str:
        return apply_saved_config(old, new, save=save_config, app=state.app,
                                  apply_ui=shell.apply_config, restart=restart,
                                  notify=shell.ui.notify, ai=ai)

    shell.on_quit = stop_input
    shell.on_save_config = make_on_save(state, apply_settings)
    wire_capture(shell.window, hooks, lambda: state.app)
    if history is None:
        shell.ui.notify("History unavailable")
    if autostart_error is not None:
        shell.ui.notify(f"Start with Windows failed: {autostart_error}")
    if previous_crashed:
        shell.ui.notify("Flow Voice did not close cleanly last time. "
                        f"Details: {diagnostics.log_path()}")

    def setup() -> None:
        from flowvoice.engine import Engine  # slow import: keep it off the GUI thread

        shell.ui.notify("Loading speech model...")
        try:
            engine = Engine(cfg.model)
            recorder = Recorder(device=cfg.mic_device)
            recorder.open()
            with state.lock:
                if hooks.closed:
                    recorder.close()
                    return
                state.recorder = recorder
            app = App(state.cfg, engine=engine, recorder=recorder, speaker=Speaker(on_error=shell.ui.notify),
                      ui=shell.ui, history=history, ai=ai)

            def read_aloud() -> None:
                threading.Thread(target=app.on_tts_trigger, daemon=True).start()

            state.app = app
            hooks.set([PushToTalk(cfg.ptt_key, app.press, app.release, app.other_key),
                       Toggle(cfg.tts_key, read_aloud)])
        except Exception as e:
            log.exception("startup failed")
            shell.on_toggle = lambda: shell.ui.notify("Startup failed - check Settings")
            shell.ui.notify(f"Startup failed: {e}")
            shell.ui.show_window("Settings")
            return
        shell.on_toggle = app.click
        shell.on_tick = app.tick
        key = pretty_key(cfg.ptt_key)
        if state.cfg.hands_free:
            shell.ui.notify(f"Ready - hold {key} to dictate, or double-tap it")
        else:
            shell.ui.notify(f"Ready - hold {key} to dictate")

    threading.Thread(target=setup, daemon=True).start()
    return shell.run()


if __name__ == "__main__":
    sys.exit(main())
