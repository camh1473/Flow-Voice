import threading

from flowvoice.app import App
from flowvoice.autostart import set_autostart
from flowvoice.config import load_config
from flowvoice.engine import Engine
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.recorder import Recorder
from flowvoice.tray import Tray
from flowvoice.tts import Speaker


def main() -> None:
    cfg = load_config()
    set_autostart(cfg.start_with_windows)
    hotkeys: list = []
    recorders: list = []

    def quit_app() -> None:
        for h in hotkeys:
            h.disable()
        for r in recorders:
            r.close()

    tray = Tray(on_quit=quit_app)

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
