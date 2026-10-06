import os
import subprocess
import sys
import threading
from types import SimpleNamespace
from typing import Callable

from flowvoice.ai_polish import MISSING, OFF, UNAVAILABLE, WARMING, AiService
from flowvoice.app import App
from flowvoice.autostart import set_autostart
from flowvoice.config import ensure_config_file, load_config, save_config
from flowvoice.history import History
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.recorder import Recorder
from flowvoice.settings_logic import mic_choices
from flowvoice.tts import Speaker
from flowvoice.ui.hotkey_edit import pretty_key
from flowvoice.ui.shell import (
    HookGroup,
    Shell,
    apply_saved_config,
    restart_process,
    wire_capture,
)


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


def main() -> int:
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
                        spawn=lambda: subprocess.Popen([sys.executable, "-m", "flowvoice"]),
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
