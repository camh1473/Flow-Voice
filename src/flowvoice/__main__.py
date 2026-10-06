import os
import subprocess
import sys
import threading
from types import SimpleNamespace

from flowvoice.app import App
from flowvoice.autostart import set_autostart
from flowvoice.config import load_config, save_config
from flowvoice.history import History
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.recorder import Recorder
from flowvoice.settings_logic import mic_choices
from flowvoice.tts import Speaker
from flowvoice.ui.hotkey_edit import pretty_key
from flowvoice.ui.shell import HookGroup, Shell, apply_saved_config, wire_capture


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


def main() -> int:
    cfg = load_config()
    autostart_error = None
    try:
        set_autostart(cfg.start_with_windows)
    except Exception as e:
        autostart_error = e
    history = _open_history()
    hooks = HookGroup()
    state = SimpleNamespace(cfg=cfg, app=None, recorder=None, lock=threading.Lock())

    shell = Shell(cfg, history, mics=mic_choices())

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
        shell.shutdown()
        subprocess.Popen([sys.executable, "-m", "flowvoice"])
        os._exit(0)

    def on_save(new) -> None:
        result = apply_saved_config(state.cfg, new, save=save_config, app=state.app,
                                    apply_ui=shell.apply_config, restart=restart,
                                    notify=shell.ui.notify)
        if result == "live":
            state.cfg = new

    shell.on_quit = stop_input
    shell.on_save_config = on_save
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
            app = App(state.cfg, engine=engine, recorder=recorder, speaker=Speaker(),
                      ui=shell.ui, history=history)

            def read_aloud() -> None:
                threading.Thread(target=app.on_tts_trigger, daemon=True).start()

            state.app = app
            hooks.set([PushToTalk(cfg.ptt_key, app.press, app.release, app.other_key),
                       Toggle(cfg.tts_key, read_aloud)])
        except Exception as e:
            shell.ui.notify(f"Startup failed: {e}")
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
