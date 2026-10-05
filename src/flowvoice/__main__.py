import os
import subprocess
import sys
import threading

from flowvoice.app import App
from flowvoice.autostart import set_autostart
from flowvoice.config import load_config
from flowvoice.engine import Engine
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.recorder import Recorder
from flowvoice.settings import needs_restart
from flowvoice.tray import Tray
from flowvoice.tts import Speaker


def main() -> None:
    cfg = load_config()
    set_autostart(cfg.start_with_windows)
    hotkeys: list = []
    recorders: list = []
    apps: list = []

    def quit_app() -> None:
        for h in hotkeys:
            h.disable()
        for r in recorders:
            r.close()

    def restart() -> None:
        quit_app()
        subprocess.Popen([sys.executable, "-m", "flowvoice"])
        os._exit(0)

    def open_settings() -> None:
        def work() -> None:
            subprocess.run([sys.executable, "-m", "flowvoice.settings"])
            new = load_config()
            current = apps[0].config if apps else cfg
            if new == current:
                return
            if needs_restart(current, new):
                tray.notify("Applying settings...")
                restart()
            elif apps:
                apps[0].config = new
                tray.notify("Settings saved")

        threading.Thread(target=work, daemon=True).start()

    tray = Tray(on_quit=quit_app, on_settings=open_settings)

    def setup() -> None:
        tray.notify("Loading speech model...")
        try:
            engine = Engine(cfg.model)
            recorder = Recorder(device=cfg.mic_device)
            recorder.open()
        except Exception as e:
            tray.notify(f"Startup failed: {e}")
            return
        recorders.append(recorder)
        app = App(cfg, engine=engine, recorder=recorder, speaker=Speaker(), tray=tray)
        apps.append(app)

        def read_aloud() -> None:
            threading.Thread(target=app.on_tts_trigger, daemon=True).start()

        hotkeys.extend([PushToTalk(cfg.ptt_key, app.on_ptt_start, app.on_ptt_stop,
                                   on_cancel=app.on_ptt_cancel),
                        Toggle(cfg.tts_key, read_aloud)])
        for h in hotkeys:
            h.enable()
        tray.notify(f"Ready - hold {cfg.ptt_key} to dictate")

    tray.run(setup)


if __name__ == "__main__":
    main()
