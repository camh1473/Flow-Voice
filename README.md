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

## Dictionary
**Settings > Words.** Two lists:
- **Dictionary:** names and terms, one per line (up to 200). Flow Voice gives them to Whisper as a short glossary (at most 400 characters) so it listens for them, then fixes the casing and spelling of any match ("acme homes" becomes "Acme Homes"). If Whisper only echoes the glossary back (it does this on silence), the take is discarded, not pasted.
- **Corrections:** "Heard as" and "Write as" pairs (up to 200) for words Whisper keeps getting wrong. Whole words only, case-insensitive, and a correction never chains into another.

The glossary helps recognition but cannot force Whisper to hear a word. Terms past the 400-character glossary are still used for casing and spelling, just not for listening.

## Snippets
**Settings > Snippets.** A trigger phrase and the text it types (up to 100). Say the phrase and the text is inserted exactly as written, including line breaks (`\n`) and tabs (`\t`).
- The text goes in verbatim and last: nothing in it is cleaned, capitalized, turned into a list or sent to the AI.
- Punctuation Whisper glues to the phrase is absorbed when it is a comma or semicolon, or a period, question mark or exclamation mark at the very end of what you said ("my address." as the last words), so a snippet without a final period stays without one. A period, question mark or exclamation mark with more speech after it is kept, so "Here is my address. Call me" pastes the address, a period, then "Call me".
- Say **literal** right before a trigger to type the words themselves ("literal my address").
- Settings warns about a trigger that is also a spoken command (the snippet wins), a trigger shorter than 3 characters, an empty snippet, a row with text but no trigger, and rows past the limit (those are ignored).

## Automatic lists
Switch: **Settings > Lists and AI > Automatic lists** (on by default). Lists are made by fixed rules, with no AI.

**Numbered lists** start from a "set-off" number: a digit or a number word (one to ten) followed by a period, comma, colon or parenthesis; or `number one`; or the ordinals first, second, third (also firstly...) at the start of a clause and followed by a comma or colon ("First, ..." or "Okay, first, ..."; a plain "First floor is..." or "Safety first, quality second" is left alone). The numbers must run 1, 2, 3 in order. A list that uses only commas needs at least 3 markers; other styles need 2.
- "To reset the router, first, unplug it, second, wait thirty seconds, third, plug it back in" becomes a lead-in line followed by `1.` `2.` `3.` lines.
- "Steps: 1. open the lid 2. press the button" and "number one call Sam number two send the file" work too.

**Bulleted lists** start from a cue followed by 3 or more short items (at most 6 words each) split by commas and "and": "shopping list: milk, eggs and bread", "ingredients: flour, sugar, butter". Whisper often drops the colon, so "Shopping list, milk, eggs and bread." at the start of a sentence also works, and so does "I need the following milk, eggs and bread". Cues: the following, a list of, shopping list, to-do list, things to do, things I need, agenda, ingredients, items.

**Left unchanged:** "I need 1 apple and 2 oranges", "one, two, or three", "3.5 million", a lone "1.", a sequence that does not start at 1, an empty item, text that already has list lines, and ordinary sentences that merely contain a cue word.

## Local AI polish
Optional and **off by default**. A small model running in Ollama on this PC splits a long dictation into paragraphs and spoken lists into lines. It only restructures; it does not rewrite. Dictations shorter than 20 words (adjustable in Settings) skip it.

To enable it:
1. Install Ollama (ollama.com).
2. In a terminal run `ollama pull qwen3.5:2b-q4_K_M` (about 2 GB). Flow Voice never downloads models itself.
3. **Settings > Lists and AI:** switch on **AI polish**, choose the model, press Save.

With AI on, Flow Voice starts Ollama if it is not running, then loads the model. It starts Ollama only on its default address (http://localhost:11434); if you set a custom `ai_url` in config.json, you must start Ollama on that address yourself. The status line shows `off`, `warming up`, `ready`, `model not installed` (with the pull command to run) or `unavailable` (with the reason, for example Ollama could not be started). A cold load can take about 30 seconds; dictations during that time paste the normal text. Each dictation waits at most 6 seconds for the AI. **Test AI** sends a sample and shows the result and how long it took.

Safety: the AI only restructures. It may drop connector words like "and", "then", "or" and ordinals such as "first"/"second" when it turns your speech into a list; numbers, names, negations and the order of your words are checked and anything suspicious falls back to the normal text. In detail, its output is compared with what you said; if it replaced, added or reordered a word, dropped any word other than a list connector (and, then, or, also, next, first, second, third...), changed or swapped a number, date or negation, dropped a name, added formatting, repeated a sentence, lost or moved a snippet or timed out, the normal text is pasted instead. Dictations over 300 words skip the AI, because the model must finish within the timeout. Any AI failure falls back to the normal text and never blocks a paste.

Privacy: Flow Voice only talks to an address on this PC (localhost, 127.0.0.1 or ::1) and refuses any other, so your text never leaves it. Quitting Flow Voice never stops Ollama; quit it from its own tray icon to free the memory.

## Settings
- **Dictation:** push-to-talk key, read-aloud key (click the field, then press the new keys; left and right Ctrl/Shift/Alt are told apart, so pressing Right Ctrl shows "Right Ctrl"), speech model (`tiny.en`, `base.en`, `small.en`, `medium.en`; larger is more accurate but slower), microphone, save history.
- **Hands-free:** double-tap on/off and the stop-after-silence time.
- **Interface:** always show the pill, interface size (scales the window and the pill), start with Windows.
- **Words:** the dictionary and corrections (see Dictionary).
- **Snippets:** trigger phrases and their text (see Snippets).
- **Lists and AI:** automatic lists on/off, AI polish on/off, AI model (with Refresh), minimum words, the status line and the Test AI button (see Local AI polish).
- **Phrases:** spoken commands on/off and the command table (write `\n` for a line break, `\t` for a tab), filler words, backtrack phrases, and a button to reset all of them to the built-in lists.

Changes to the hotkeys, speech model, microphone and start-with-Windows restart the app automatically when you press Save. Everything else applies immediately. The config file is `%APPDATA%\FlowVoice\config.json`.

## Read aloud
Select text in any app and press **Ctrl+Alt+S**. Press it again to stop.

## Troubleshooting

Flow Voice runs without a console window, so it keeps its own record in `%APPDATA%\FlowVoice\`:

| File | What it holds |
| --- | --- |
| `flowvoice.log` | Start and stop times, unhandled errors with tracebacks, Qt warnings, microphone events. Rolls over at 512 KB, three backups. Your dictated text is never written to it. |
| `native-crash.log` | A stack dump if the process dies inside native code (Qt, PortAudio, the speech engine). Normally empty. |
| `running.marker` | Exists only while the app runs. If it is still there at the next start, the last run ended unexpectedly and a tray message says so. |

- **Only one copy runs.** Starting a second one (for example `run.bat` while the start-with-Windows copy is already running) shows "already running" and exits. Two copies would both hook the keyboard and paste every dictation twice.
- **The microphone recovers by itself.** If the mic stream stops delivering audio (sleep and wake, an unplugged USB mic, a driver reset) or its device number starts to mean a different device, Flow Voice rebuilds the stream within about 8 seconds, following your chosen mic by name. If that mic is gone it switches to the system default and tells you.
- **To see what happened after a crash,** open `flowvoice.log` and look at the last lines before the `start pid=` entry of the next run.

## Known limits
- Apps running as Administrator ignore pasted input from a normal-privilege process.
- The clipboard is restored after each paste, but only for text (images on the clipboard are lost).
- The command guard is a heuristic, and Whisper's own punctuation decides some cases. "Period" converts only when set off; say "full stop" to end a sentence, because Whisper usually writes a last-word "period" as "period." and it stays a word.
- Starting dictation from the **Start dictation** button on Home or in the tray menu makes Flow Voice itself the foreground window, so the text appears only in the Last transcription card and in History. To paste into another app, use the hotkey or click the pill.
- Lists are rule-based: unusual phrasing can be missed or, rarely, formatted when you did not mean a list. Turn **Automatic lists** off if that bothers you.
- The AI is a small model: slow on a cold start and useful only for long dictations. Suspicious output is thrown away, so some dictations stay unformatted on purpose.
- Flow Voice can start Ollama only on its default address (http://localhost:11434). With a custom `ai_url`, start Ollama yourself; if Ollama is stopped, Flow Voice may start a second, default-address server that it then cannot reach.
- Limits: 200 dictionary terms, 200 corrections, 100 snippets; extra rows are ignored.
- Starting a second copy of Flow Voice is not prevented; run only one.

## Develop
```
.venv\Scripts\python -m pytest -m "not slow"    # fast tests
.venv\Scripts\python -m pytest                  # includes Whisper tests
.venv\Scripts\python scripts/render_previews.py # render UI previews
```
Manual checks that need a person at the keyboard are in `docs/manual-test-checklist.md`.
