# Flow Voice — Design

Date: 2026-10-05

## Goal
A free, Wispr Flow-style system-wide dictation tool for Windows. Hold a hotkey, speak, and clean text is pasted at the cursor in whatever app has focus. Also reads selected text aloud. Free means no ongoing cost: all speech runs locally (no Google Cloud, no API keys, audio never leaves the PC).

## Decisions made
- STT engine: local Whisper via `faster-whisper` (chosen over Google Cloud, which is only free for ~60 min/month and needs billing).
- TTS: Windows built-in SAPI voices (free, offline).
- Platform: Windows PC only for v1. Phone is a future goal; the `engine` interface is kept reusable for it.
- Stack: Python tray app. Location: `C:\Users\camh1\dev\flow-voice\` (not OneDrive).

## Non-goals (v1)
LLM rewrite/"polish" step, custom dictionaries, command mode, phone app, installer, streaming/live partial text.

## Components
| Unit | Responsibility | Depends on |
|---|---|---|
| `hotkey` | Global push-to-talk (hold to record, release to stop). Default Right Ctrl, configurable. Second hotkey: read selection aloud. | `keyboard` |
| `recorder` | Mic capture, 16 kHz mono, ~300 ms pre-roll so first word is not clipped. Ignores taps shorter than ~250 ms. | `sounddevice` |
| `engine` | `transcribe(audio: np.ndarray) -> str`. `faster-whisper`, default `small.en`, CUDA if available else CPU int8. Model loaded once at startup. | `faster-whisper` |
| `cleanup` | Pure function `clean(text) -> str`: remove fillers (um, uh, er), collapse stutters/repeats, fix spacing, capitalize sentence starts. | none |
| `inject` | Paste text at cursor: save clipboard, set text, send Ctrl+V, restore clipboard. Fallback: typed keystrokes. | `pyperclip`, `keyboard` |
| `tts` | `speak(text)`, `stop()` via SAPI. Hotkey copies the current selection (Ctrl+C), then speaks it. Same hotkey again stops. | `pyttsx3` |
| `tray` | Tray icon (idle/recording/processing states), small always-on-top recording indicator, menu (settings, quit). | `pystray`, `Pillow` |
| `config` | JSON settings in `%APPDATA%\FlowVoice\config.json`: hotkeys, model, mic device, start-with-Windows. | stdlib |

## Data flow
hold hotkey -> `recorder` captures -> release -> `engine.transcribe` -> `cleanup.clean` -> `inject.paste` -> done. Transcription runs on a worker thread so the hotkey listener never blocks.

## Error handling
No mic, model load failure, or empty transcript show a tray notification and leave the clipboard untouched. Clipboard is always restored, including on failure. Empty/silent audio pastes nothing.

## Testing
- Unit tests for `cleanup` (table of inputs/outputs).
- `engine` test transcribing a short bundled WAV and asserting key words.
- `inject` tested against a stub clipboard.
- Manual check: dictate into Notepad, a browser text box, and an Office app; read-aloud of selected text.

## Success criteria
Hold key in any app, speak a sentence, and within ~2 s of release clean text appears at the cursor; no cloud calls; clipboard contents preserved.

## Prerequisites / risks
- Python is not currently installed (the `python` command resolves to the Microsoft Store shortcut). The plan will install Python 3.11+ first (needs the user's OK).
- Some elevated (admin) apps ignore injected input from a non-elevated process; v1 documents this rather than solving it.
- `faster-whisper` downloads the model (~500 MB for `small.en`) on first run.
- Future phone version: reuse `engine` behind a small local HTTP service or a mobile-native Whisper port.
