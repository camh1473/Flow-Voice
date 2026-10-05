"""Settings window (run as `python -m flowvoice.settings`) and its pure helpers."""
import tkinter as tk
from tkinter import ttk

from flowvoice.config import Config, load_config, save_config

MODELS = ["tiny.en", "base.en", "small.en", "medium.en"]
_RESTART_FIELDS = ("ptt_key", "tts_key", "model", "mic_device", "start_with_windows")


def parse_phrases(text: str) -> list[str]:
    """One phrase per line; trimmed, lowercased, de-duplicated, blanks dropped."""
    seen: list[str] = []
    for line in text.splitlines():
        p = line.strip().lower()
        if p and p not in seen:
            seen.append(p)
    return seen


def needs_restart(old: Config, new: Config) -> bool:
    return any(getattr(old, f) != getattr(new, f) for f in _RESTART_FIELDS)


def _mic_choices() -> list[tuple[str, int | None]]:
    choices: list[tuple[str, int | None]] = [("System default", None)]
    try:
        import sounddevice
        for i, d in enumerate(sounddevice.query_devices()):
            if d["max_input_channels"] > 0:
                choices.append((f"{i}: {d['name']}", i))
    except Exception:
        pass
    return choices


def run(selftest: bool = False) -> None:
    cfg = load_config()
    root = tk.Tk()
    root.title("Flow Voice Settings")
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=14)
    frm.grid()

    ptt = tk.StringVar(value=cfg.ptt_key)
    tts = tk.StringVar(value=cfg.tts_key)
    model = tk.StringVar(value=cfg.model)
    auto = tk.BooleanVar(value=cfg.start_with_windows)
    mics = _mic_choices()
    mic_labels = [m[0] for m in mics]
    current = next((m[0] for m in mics if m[1] == cfg.mic_device), mic_labels[0])
    mic = tk.StringVar(value=current)

    rows = [("Push-to-talk key", ttk.Entry(frm, textvariable=ptt, width=24)),
            ("Read-aloud key", ttk.Entry(frm, textvariable=tts, width=24)),
            ("Model", ttk.Combobox(frm, textvariable=model, values=MODELS, state="readonly", width=22)),
            ("Microphone", ttk.Combobox(frm, textvariable=mic, values=mic_labels, state="readonly", width=40))]
    for r, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
        widget.grid(row=r, column=1, sticky="w", pady=3)
    ttk.Checkbutton(frm, text="Start with Windows", variable=auto).grid(row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Backtrack phrases (one per line)\nDeletes your last sentence").grid(
        row=5, column=0, sticky="nw", pady=(10, 3))
    back = tk.Text(frm, width=30, height=8)
    back.insert("1.0", "\n".join(cfg.backtrack_phrases))
    back.grid(row=5, column=1, sticky="w", pady=(10, 3))
    ttk.Label(frm, text="Filler phrases (one per line)\nRemoved when set off by commas").grid(
        row=6, column=0, sticky="nw", pady=3)
    fill = tk.Text(frm, width=30, height=6)
    fill.insert("1.0", "\n".join(cfg.filler_phrases))
    fill.grid(row=6, column=1, sticky="w", pady=3)

    note = ttk.Label(frm, text="Phrase lists apply immediately. Other changes restart the app.",
                     foreground="#666")
    note.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def save() -> None:
        new = Config(ptt_key=ptt.get().strip() or cfg.ptt_key,
                     tts_key=tts.get().strip() or cfg.tts_key,
                     model=model.get(),
                     mic_device=dict(mics).get(mic.get()),
                     start_with_windows=auto.get(),
                     filler_phrases=parse_phrases(fill.get("1.0", "end")),
                     backtrack_phrases=parse_phrases(back.get("1.0", "end")))
        save_config(new)
        root.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=root.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")
    if selftest:
        root.after(800, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    import sys
    run(selftest="--selftest" in sys.argv)
