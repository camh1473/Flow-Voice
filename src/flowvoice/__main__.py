from flowvoice.app import App
from flowvoice.config import load_config
from flowvoice.engine import Engine
from flowvoice.hotkey import PushToTalk, Toggle
from flowvoice.recorder import Recorder
from flowvoice.tray import Tray
from flowvoice.tts import Speaker


def main() -> None:
    cfg = load_config()
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
        hotkeys.extend([PushToTalk(cfg.ptt_key, app.on_ptt_start, app.on_ptt_stop),
                        Toggle(cfg.tts_key, app.on_tts_trigger)])
        for h in hotkeys:
            h.enable()
        tray.notify(f"Ready - hold {cfg.ptt_key} to dictate")

    tray.run(setup)


if __name__ == "__main__":
    main()
