# Flow Voice v2: Hands-free, History, New UI - Design

Date: 2026-10-05. Builds on `2026-10-05-flow-voice-design.md` (v1, shipped on branch `build`).

## Goal
Make Flow Voice nicer to live with: dictate without holding a key, keep a private local history of what was said, and replace the tkinter/pystray interface with a polished Apple-style UI: a floating waveform pill that turns red while recording, and a larger main window (Home, History, Settings). PC only. Phone/web is explicitly out of scope.

## User decisions
- Do hands-free + history + UI together.
- Waveform pill; red (or another high-contrast color) while recording.
- A larger interface is wanted (resizable window, adjustable pill/UI size).

## Non-goals
Phone/web app, saving audio, cloud sync, theming beyond system light/dark, multiple languages, LLM rewriting.

## 1. Hands-free
Three ways to record without holding a key (all on by default):
- **Double-tap push-to-talk key** (default Right Ctrl): tap twice within 0.5 s to latch recording on; tap once more to stop. Holding the key still works as push-to-talk. A press shorter than 0.3 s is a "tap" and is discarded, never transcribed.
- **Click the pill** to start (latched) and click again to stop.
- **Silence auto-stop** while latched: stops after `silence_stop_seconds` (default 4.0) of silence once speech has been heard, and after a hard cap of 5 minutes.
Esc while recording cancels and discards the take (any non-modifier key while holding already cancels, per v1).

Implemented as a pure state machine `talkmode.TalkMode` (injectable clock) with events `press`, `release`, `other_key`, `tick`, `click` and actions `start`, `stop`, `cancel`. It replaces the press/release logic inside `hotkey.PushToTalk`, which keeps only key filtering and passes events through.

## 2. History
- SQLite database at `%APPDATA%\FlowVoice\history.db` (stdlib `sqlite3`). Table `entries(id, created_at, raw_text, clean_text, app_name)`.
- `history.History`: `add(raw, clean, app_name)`, `list(limit=200, query="")`, `delete(id)`, `clear()`. Thread-safe (one connection per call).
- An entry is added after each successful paste. `app_name` is the foreground app's executable name (best effort; empty string if unknown).
- Setting `save_history` (default true). When off, nothing is written. A "Clear history" button deletes everything. Audio is never saved.

## 3. UI (PySide6 / Qt replaces tkinter and pystray)
- **Pill** (`ui/pill.py`): frameless, translucent, always-on-top, non-activating (never takes focus), rounded capsule with soft shadow, bottom-center of the screen. States: idle (small dim capsule), recording (expands, red, live waveform bars driven by mic level), processing (amber, animated dots). Click toggles recording. Scaled by `ui_scale` (0.8-1.6, default 1.0). Setting `pill_always_visible` (default true); when false it only appears while active.
- **Main window** (`ui/main_window.py`): resizable, remembers size/position, left sidebar with Home / History / Settings, rounded cards, system font (Segoe UI Variable), follows system light/dark.
  - Home: big status, the last transcription with Copy, Start/Stop button, hotkey hint.
  - History: search box, list (time, app, text), Copy, Delete, Clear all.
  - Settings: click-to-record hotkey fields, model dropdown, microphone dropdown, toggles (start with Windows, save history, hands-free double-tap, pill always visible), silence timeout slider, UI size slider, the filler and backtrack phrase editors, the spoken-commands switch and phrase table. Replaces `settings.py`.
- **Tray**: `QSystemTrayIcon` with menu Open, Start/Stop, Quit; double-click opens the window. Closing the window hides it to tray.
- Core code talks to the UI only through a small `Ui` interface: `set_state(state)`, `set_level(float)`, `notify(msg)`, `add_history(entry)`. The Qt implementation turns calls from worker/hook threads into signals so widgets are only touched on the Qt main thread.

## 4. Spoken commands (punctuation and formatting)
Say a command and the symbol or break is inserted into the text instead of the words. Pure module `commands.py`: `apply_commands(text, mapping) -> str`, run after backtracking and before filler cleanup.
- **Always convert** (unambiguous; editable in Settings as a phrase -> text table): "new line" -> line break; "new paragraph" -> blank line; "bullet point" -> line break + `- `; "question mark" -> `?`; "exclamation point" / "exclamation mark" -> `!`; "full stop" -> `.`; "comma" -> `,`; "semicolon" -> `;`; "ellipsis" -> `...`; "open quote" / "close quote" -> `"`; "open paren" / "close paren" -> `(` / `)`; "open bracket" / "close bracket" -> `[` / `]`; "at sign" -> `@`; "underscore" -> `_`; "ampersand" -> `&`; "percent sign" -> `%`; "dollar sign" -> `$`; "plus sign" -> `+`; "equals sign" -> `=`. Bare "quote" is not a command, so it stays a word.
- **Guarded** (also ordinary words; see Guard rule): "period" -> `.`; "colon" -> `:`; "hyphen" -> `-`; "dash" / "em dash" -> an em dash; "slash" -> `/`; "dot" -> `.`.
- **Guard rule:** a guarded word does not convert when the word before it is one of `the, a, an, this, that, time, grace, trial, probation` ("a dash of salt"). **"Period" additionally** converts only when it is set off by punctuation, at the end of the text, or directly followed by another command (it is the only guarded word that is common mid-sentence prose). The other guarded words ("colon", "hyphen", "dash", "slash") convert mid-sentence without punctuation, because Whisper rarely punctuates around them and they are seldom ordinary words. "Dot" is handled for addresses: it converts when the next word is a common top-level domain (`com, org, net, edu, gov, io, co, us, ai, dev, app, uk`) or when it follows an `@` within the same run of words. Inside such an address run, "slash", "hyphen", "dash" and "underscore" also convert. This is a heuristic, not a guarantee: Whisper does not always punctuate around spoken commands, and the literal escape is the backup. "Full stop" is the recommended way to say the symbol.
- **All caps:** "all caps" starts uppercasing and "end caps" stops; if "end caps" is never said, it stops at the end of the dictation.
- **Spacing rules:** punctuation attaches to the previous word with no space before it and one space after; a line break or paragraph break replaces the spaces around it; the next word after `.`, `?`, `!`, a line break or a paragraph break is capitalized; open/close quotes, parens and brackets hug their contents; `@`, `_`, `/`, hyphen, em dash and the address `.` join both sides with no spaces; `%` attaches to the previous word, `$` to the next word; `+` and `=` stay spaced.
- **Whisper punctuation is absorbed:** Whisper often writes its own punctuation around spoken commands ("Hello, comma, how are you question mark."). Punctuation characters (`. , ; ! ?`) directly touching a command phrase are consumed so the result is clean ("Hello, how are you?").
- **Literal escape:** saying "literal" before a command types the word instead ("literal period" -> "period"), for the cases where you mean the word.
- **Settings:** master switch `voice_commands` (default on) plus the editable `command_phrases` table. Added or removed phrases apply immediately.
- **Escape and edits:** "literal" before any command types the word instead ("literal period" -> "period"; "literal comma" -> "comma"). Removing or editing a phrase in Settings changes it permanently.
- Pasted line breaks are sent as-is with Ctrl+V; single-line fields may show them as a space or ignore them.

## 5. Other changes
- `Recorder` gets an `on_level(float)` callback (RMS of each chunk, scaled 0..1) feeding the waveform and silence detection.
- `Dictation` gets an `on_result(raw, clean)` callback used to write history.
- `Config` gains: `voice_commands: bool = True`, `command_phrases: dict[str, str]` (defaults above), `hands_free: bool = True`, `silence_stop_seconds: float = 4.0`, `save_history: bool = True`, `pill_always_visible: bool = True`, `ui_scale: float = 1.0`.
- Settings apply live except hotkeys/model/microphone/start-with-Windows, which restart the app as in v1.
- Remove dependencies `pystray` and `Pillow`; add `PySide6`. Remove `tray.py` and `settings.py` (their pure helpers `parse_phrases` and `needs_restart` move to `settings_logic.py`).

## Testing
- Unit: `TalkMode` (hold, tap, double-tap latch, stop-by-tap, cancel, auto-stop on silence, 5-minute cap, injected clock), `History` (tmp db: add/list/search/delete/clear, save_history off), recorder levels, config defaults and round-trip, settings helpers.
- Spoken commands (table-driven): each default command; spacing and capitalization ("hello comma how are you question mark" -> "Hello, how are you?"); absorbed Whisper punctuation ("Hello, comma, how" -> "Hello, how"); "new line" / "new paragraph" produce the right breaks and capitalize the next word; "literal period" types "period"; guard rule ("the time period is long" and "a trial period" stay words, "I am done period" and "done, period." convert, "full stop" always converts); bare "quote" stays a word while "open quote ... close quote" converts; addresses ("john at sign gmail dot com" -> "john@gmail.com", "example dot com slash pricing" -> "example.com/pricing"); "bullet point"; "all caps ... end caps" (closed and unclosed); custom phrase added or removed; master switch off leaves words untouched; interaction with backtracking ("scratch that" still deletes the last sentence including a spoken comma).
- App integration with fakes: double-tap cycle pastes once, silence stop pastes, history entry written after paste, no entry when `save_history` is off.
- Qt smoke tests with `QT_QPA_PLATFORM=offscreen`: pill and main window construct; pill renders each state to a PNG that is visually reviewed; settings form round-trips to `Config`.
- Manual (needs the user): double-tap latch, click-to-toggle pill, silence auto-stop, pill never steals focus before a paste, history entries appear, window size and scale feel right.

## Success criteria
Double-tap Right Ctrl, speak a sentence, pause; it stops by itself and the text appears at the cursor with no key held. The pill is red with a moving waveform while recording and never takes focus from the app being typed into. The History tab lists what was said, can be searched, and can be cleared or turned off. Saying "hello comma new paragraph how are you question mark" pastes "Hello," then a blank line then "How are you?". Existing v1 behavior (hold to dictate, backtracking, read-aloud) is unchanged.

## Risks
- Qt owns the main thread: hook, recorder and pipeline threads must only reach widgets through signals.
- A non-activating click-to-toggle pill depends on Windows window styles; verify it manually.
- PySide6 adds roughly 200 MB to the venv.
- Double-tap needs a short wait (0.5 s) before a single tap is known to be only a tap; a tap does nothing, so there is no visible delay.
