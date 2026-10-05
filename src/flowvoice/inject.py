import time

import keyboard
import pyperclip


def paste_text(text: str, *, get_clip=pyperclip.paste, set_clip=pyperclip.copy,
               send=keyboard.send, type_text=keyboard.write, sleep=time.sleep) -> None:
    if not text.strip():
        return
    original = get_clip()
    try:
        set_clip(text)
        try:
            send("ctrl+v")
            sleep(0.15)
        except Exception:
            type_text(text)
    finally:
        set_clip(original)


def copy_selection(*, get_clip=pyperclip.paste, set_clip=pyperclip.copy,
                   send=keyboard.send, sleep=time.sleep) -> str:
    """Return the currently selected text (via Ctrl+C), restoring the clipboard."""
    original = get_clip()
    try:
        set_clip("")
        send("ctrl+c")
        sleep(0.15)
        return get_clip()
    finally:
        set_clip(original)
