# Flow Voice

Free, local, Wispr Flow-style dictation for Windows. Speak, and clean text is pasted at your cursor in any app. All speech runs on your PC (Whisper); nothing is sent to the cloud, and audio is never saved.

## Run
Double-click `run.bat`. The first launch downloads the ~500 MB `small.en` speech model, so the first start takes a while. On the very first run (no config file yet) the main window opens by itself. After that Flow Voice lives in the system tray and a small pill at the bottom center of the screen.

## Dictate
- **Hold to talk:** hold **Right Ctrl**, speak, release. The text is pasted where your cursor is.
- **Hands-free:** double-tap **Right Ctrl** (two quick taps) to latch recording on, or click the pill. Talk as long as you like, up to 5 minutes. Recording ends when you press Right Ctrl again, click the pill again, or stop talking for the set number of seconds (default 4; it only counts after you have started speaking). Speech is judged against your room's background noise, and the first half second of a take is ignored so the thump of the double-tap itself never counts as speech. A hands-free take in which you never spoke is discarded, not transcribed.
- **Esc** cancels the take; nothing is pasted. Pressing any other key while holding Right Ctrl also cancels.
- A single quick tap of Right Ctrl does nothing.

## The pill
A small capsule at the bottom center, always on top, that never takes focus from the app you are typing in.
- **Grey:** idle.
- **Red with a moving waveform:** recording.
- **Amber with animated dots:** transcribing.

Click it to start or stop a hands-free take. You can hide it while idle in Settings (it still appears while recording).

## The main window
Three pages in the sidebar: **Home**, **History**, **Settings**.
- **Home:** live status, your last dictation with a Copy button, and a Start/Stop dictation button.
- Closing the window only hides it to the tray. To quit, right-click the tray icon and choose **Quit**. The tray menu has **Open**, **Start/Stop dictation** and **Quit**; double-click the tray icon to open the window.

## History
Every successful dictation is saved to a local database at `%APPDATA%\FlowVoice\history.db` (the cleaned text, the raw transcript, the time and the app you pasted into). Only text is stored, never audio.
- The History page lists entries newest first. **Search** filters them, **Copy** copies the selected entry, **Delete** removes it, **Clear all** removes everything (it asks first).
- Turn it off with **Save history** in Settings. Nothing new is recorded while it is off, and existing entries stay until you delete them.

## Spoken commands
Say these words and they become punctuation or formatting. Turn the whole feature off with **Spoken commands** in Settings, and edit the phrases in the table there.

**Always converted:**
- Line breaks: "new line", "new paragraph", "bullet point"
- Punctuation: "comma", "semicolon", "full stop", "question mark", "exclamation point" / "exclamation mark", "ellipsis"
- Brackets and quotes: "open quote", "close quote", "open paren", "close paren", "open bracket", "close bracket"
- Symbols: "at sign", "underscore", "ampersand", "percent sign", "dollar sign", "plus sign", "equals sign"

**Guarded** (could be an ordinary word, so they convert only in the right place): "period", "colon", "hyphen", "dash", "em dash", "slash", "dot".

How the guard works, in plain words:
- If the word before is `the, a, an, this, that, time, grace, trial, probation, my, your, his, her, our, their, to`, the guarded word stays a word ("the time period", "a trial period", "a dash of salt").
- "Period" converts only when you set it off (punctuation just before it), when it is the last word, or when it is directly followed by another command. To end a sentence, say **"full stop"**, which always converts: Whisper usually writes a final "period" as "period." with its own dot, and that stays a word.
- "Dot" converts only before a common ending (`com, org, net, edu, gov, io, co, us, ai, dev, app, uk`) or inside an address after "at sign".
- Inside an address, "dash", "hyphen", "slash" and "underscore" always convert, and "dash" gives a plain hyphen.
- Bare "quote" is not a command; use "open quote" and "close quote".

**Line breaks on their own:** "new line" or "new paragraph" at the start of a take starts the text on a new line, and a take that is only "new paragraph" or "new line" pastes just that break.

**Escape:** say **literal** right before a command to type the word itself ("literal comma" types the word comma).

**Capitals:** "all caps" starts typing in capital letters and "end caps" stops. "All caps" is ignored right after words like in, with, using, is, are, the, a, an, my, your, so ordinary sentences are safe.

Examples:
- "hello comma new paragraph how are you question mark" gives "Hello," then a blank line, then "How are you?"
- "john at sign gmail dot com" gives `john@gmail.com`
- "the time period is long" is left alone

## Backtracking and filler words
- **Backtrack:** say "scratch that", "never mind", "nevermind", "forget that", "delete that", "cancel that", "strike that", "ignore that" or "excuse me" and your last sentence is deleted along with the phrase.
- **Fillers:** "um", "uh" and similar are dropped, as are set-off phrases such as "you know," "I mean," "basically," and "well,".
- Order of processing: backtracking, then spoken commands, then filler cleanup. Line breaks you dictate are kept.
- Both phrase lists are editable in Settings.

## Settings
- **Dictation:** push-to-talk key, read-aloud key (click the field, then press the new keys; left and right Ctrl/Shift/Alt are told apart, so pressing Right Ctrl shows "Right Ctrl"), speech model (`tiny.en`, `base.en`, `small.en`, `medium.en`; larger is more accurate but slower), microphone, save history.
- **Hands-free:** double-tap on/off and the stop-after-silence time.
- **Interface:** always show the pill, interface size (scales the window and the pill), start with Windows.
- **Phrases:** spoken commands on/off and the command table (write `\n` for a line break, `\t` for a tab), filler words, backtrack phrases, and a button to reset all of them to the built-in lists.

Changes to the hotkeys, speech model, microphone and start-with-Windows restart the app automatically when you press Save. Everything else applies immediately. The config file is `%APPDATA%\FlowVoice\config.json`.

## Read aloud
Select text in any app and press **Ctrl+Alt+S**. Press it again to stop.

## Known limits
- Apps running as Administrator ignore pasted input from a normal-privilege process.
- The clipboard is restored after each paste, but only for text (images on the clipboard are lost).
- The command guard is a heuristic, and Whisper's own punctuation decides some cases. "Period" converts only when set off; say "full stop" to end a sentence, because Whisper usually writes a last-word "period" as "period." and it stays a word.
- Starting dictation from the **Start dictation** button on Home or in the tray menu makes Flow Voice itself the foreground window, so the text appears only in the Last transcription card and in History. To paste into another app, use the hotkey or click the pill.
- Starting a second copy of Flow Voice is not prevented; run only one.

## Develop
```
.venv\Scripts\python -m pytest -m "not slow"    # fast tests
.venv\Scripts\python -m pytest                  # includes Whisper tests
.venv\Scripts\python scripts/render_previews.py # render UI previews
```
Manual checks that need a person at the keyboard are in `docs/manual-test-checklist.md`.
