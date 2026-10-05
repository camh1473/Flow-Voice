# Flow Voice

Free, local, Wispr Flow-style dictation for Windows. Hold a key, speak, and clean text is pasted at the cursor in any app. All speech runs on your PC (Whisper); nothing is sent to the cloud.

## Run
Double-click `run.bat`. A grey dot appears in the system tray; wait for the "Ready" notification (first launch downloads the ~500 MB `small.en` model).

## Use
- **Dictate:** hold **Right Ctrl**, speak, release. Text is pasted where your cursor is.
- **Read aloud:** select text and press **Ctrl+Alt+S**. Press again to stop.
- A red REC badge shows while recording.
- **Backtrack:** say "scratch that", "never mind", "forget that", "delete that", "cancel that", "strike that", "ignore that" or "excuse me" and your last sentence is deleted along with the phrase.
- Filler words (um, uh) and set-off phrases like "you know," "I mean," "basically," "well," are dropped.

## Settings
Right-click the tray icon -> **Settings...** to change hotkeys, model, microphone, start-with-Windows, and the backtrack/filler phrase lists. Phrase lists apply immediately; other changes restart the app automatically.

Under the hood it is`%APPDATA%\FlowVoice\config.json` (created on first save) - `ptt_key`, `tts_key`, `model` (`tiny.en`, `base.en`, `small.en`, `medium.en`), `mic_device`, `start_with_windows`. Restart the app after editing.

## Known limits
- Apps running as Administrator ignore pasted input from a normal-privilege process.
- The clipboard is restored after each paste, but only for text (images on the clipboard are lost).

## Develop
```
.venv\Scripts\python -m pytest -m "not slow"    # fast tests
.venv\Scripts\python -m pytest                  # includes Whisper tests
```
