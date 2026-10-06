# Flow Voice v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hands-free dictation (double-tap, pill click, silence auto-stop), a local history, spoken punctuation/formatting commands, and replace the tkinter/pystray UI with a PySide6 waveform pill plus a main window (Home, History, Settings).

**Architecture:** Core logic stays UI-agnostic and unit-tested with fakes: a pure `TalkMode` state machine (hold/tap/double-tap/latch), a pure `commands.apply_commands` text transformer, a SQLite `History`, and `App` talking to the UI only through a small `Ui` interface. Qt owns the main thread; worker/hook threads reach widgets only through signals on `QtUi`.

**Tech Stack:** Python 3.12, existing v1 stack (`faster-whisper`, `sounddevice`, `keyboard`, `pyperclip`, `pywin32`), `PySide6` (new; replaces `pystray` and `Pillow`), stdlib `sqlite3`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-05-hands-free-history-ui-design.md` (builds on `2026-10-05-flow-voice-design.md` and the shipped v1 on branch `build`).

## Global Constraints

- Windows only; project at `C:\Users\camh1\dev\flow-voice\`; never write project files to OneDrive. Use `.venv\Scripts\python`. All source files ASCII-only (PowerShell `Set-Content` mangles non-ASCII; use `\u2014` escapes for the em dash).
- Everything local: no cloud, no network except Whisper model download. Audio is never saved.
- Defaults: `hands_free=True`, `silence_stop_seconds=4.0`, `save_history=True`, `pill_always_visible=True`, `ui_scale=1.0` (range 0.8-1.6), `voice_commands=True`.
- Hands-free thresholds: tap < 0.3 s is discarded; double-tap = two taps within 0.5 s latches recording; latched recording stops on another press, pill click, silence (only after speech was heard), or a 5-minute cap; Esc cancels; any non-modifier key while holding cancels (v1).
- History: `%APPDATA%\FlowVoice\history.db`, table `entries(id, created_at, raw_text, clean_text, app_name)`; entry added after each successful paste when `save_history` is on.
- Pill: frameless, translucent, always-on-top, non-activating (never takes focus), bottom-center; idle = small dim capsule, recording = red with live waveform, processing = amber with animated dots; click toggles recording.
- Order of text processing: backtracking -> spoken commands -> filler cleanup.
- "Literal" before a command types the word. Bare "quote" is not a command. "Full stop" always converts. "Period" converts only when set off by punctuation, at the end, or directly followed by another command; other guarded words ("colon", "hyphen", "dash", "slash") convert unless the previous word is one of `the, a, an, this, that, time, grace, trial, probation`. "Dot" converts only before a common TLD (`com, org, net, edu, gov, io, co, us, ai, dev, app, uk`) or inside an address run after `@`.
- Settings apply live except hotkeys, model, microphone, start-with-Windows (those restart the app).
- Non-goals: phone/web, saving audio, cloud sync, extra themes, other languages, LLM rewriting, "press enter" key command.
- Plan decisions beyond the spec (ledger as rulings): `Dictation.submit(audio, tag=None)` carries the foreground-app name captured at record start so history is correct for queued dictations; `on_result(raw, clean, tag)`.

## Review Focus

1. Tap or brush of Right Ctrl never records or pastes (tap discard; no stray transcription). Tested in Task 6.
2. Latched recording must not silence-stop before speech was heard, never silence-stop during a held push-to-talk, and Esc cancels. Tested in Task 6.
3. Line breaks from "new line"/"new paragraph" survive cleanup (no whitespace collapse, no repeated-word merge across lines). Tested in Task 4.
4. "the time period is long", "a trial period", "a dash of salt" and bare "quote" stay words; emails/URLs have no spaces. Tested in Tasks 3 and 4.
5. A failing history write, or `save_history` off, never blocks the paste or kills the worker thread. Tested in Task 9.

---

### Task 1: Config fields and settings_logic

**Files:**
- Create: `src/flowvoice/settings_logic.py`, `src/flowvoice/commands.py` (constants only here: `DEFAULT_COMMANDS: dict[str, str]`), `tests/test_settings_logic.py`
- Modify: `src/flowvoice/config.py`, `tests/test_config.py`; rename `tests/test_settings.py` -> `tests/test_settings_logic.py`
- Test: `tests/test_config.py`, `tests/test_settings_logic.py`

**Interfaces:**
- Produces: `DEFAULT_COMMANDS` (phrase -> output text; breaks use `"\n"`, `"\n\n"`, `"\n- "`; em dash as `"\u2014"`; includes every "always convert" and "guarded" phrase from Global Constraints plus `"full stop"`, `"em dash"`, `"dot"`, `"literal"` is NOT in the table). `Config` gains `voice_commands: bool`, `command_phrases: dict[str, str]` (default copy of `DEFAULT_COMMANDS`), `hands_free: bool`, `silence_stop_seconds: float`, `save_history: bool`, `pill_always_visible: bool`, `ui_scale: float`. `settings_logic.parse_phrases(text) -> list[str]` and `needs_restart(old: Config, new: Config) -> bool` (moved unchanged from `settings.py`, same restart fields).

- [ ] **Step 1: Write failing tests**: defaults for each new field (`silence_stop_seconds == 4.0`, `command_phrases["full stop"] == "."`, `"quote" not in command_phrases`); round-trip with a custom `command_phrases` and `ui_scale=1.3`; `command_phrases` not shared between instances; load with a non-dict `command_phrases` or non-numeric `ui_scale` falls back to defaults; `ui_scale` clamped to 0.8-1.6 on load; the two moved settings_logic tests from the old `test_settings.py` (import from `flowvoice.settings_logic`).
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_config.py tests/test_settings_logic.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the constants and fields; `load_config` validates types per field and falls back to the default for any bad value.
- [ ] **Step 4: Run tests.** Expected: PASS (old `settings.py` still exists and still imports; leave it until Task 15).
- [ ] **Step 5: Commit** `feat: v2 config fields and settings_logic`.

### Task 2: Spoken commands, always-convert set

**Files:**
- Modify: `src/flowvoice/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes: `DEFAULT_COMMANDS` (Task 1).
- Produces: `apply_commands(text: str, mapping: dict[str, str] = DEFAULT_COMMANDS) -> str`. Pure. Spacing roles are keyed by phrase for built-ins (open/close quote, paren, bracket; join: `at sign`, `underscore`, `slash`, `hyphen`, `dash`, `em dash`, `dot`; prefix: `dollar sign`; attach-left: `percent sign` and any output made only of `.,;:!?` or `...`; break: any output containing `\n`); any other (custom) phrase is spaced normally.

- [ ] **Step 1: Write failing table-driven tests** (`test_apply_commands`): `"hello comma how are you question mark"` -> `"hello, how are you?"`; `"Hello, comma, how are you question mark."` -> `"Hello, how are you?"` (Whisper punctuation touching a command is absorbed); `"hello new line world"` -> `"hello\nworld"`; `"hello new paragraph world"` -> `"hello\n\nworld"`; `"bullet point apples bullet point pears"` -> `"- apples\n- pears"` (no leading break at start); `"he said open quote hi there close quote"` -> `'he said "hi there"'`; `"call open paren home close paren now"` -> `"call (home) now"`; `"done full stop next"` -> `"done. next"`; `"john at sign gmail"` -> `"john@gmail"`; `"dollar sign 5"` -> `"$5"`; `"50 percent sign"` -> `"50%"`; `"1 plus sign 1 equals sign 2"` -> `"1 + 1 = 2"`; `"literal comma"` -> `"comma"`; `"literal new line"` -> `"new line"`; longest phrase wins (`"exclamation point"` not split); case-insensitive (`"NEW LINE"`); custom mapping `{"oops sign": "!"}` works and removing a phrase from the mapping leaves the words; empty mapping returns text unchanged; text with no commands is returned unchanged.
- [ ] **Step 2: Run** `pytest tests/test_commands.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `apply_commands`: tokenize into words, then scan left to right matching the longest phrase at each word (case-insensitive, trailing/leading `. , ; ! ?` touching the phrase are consumed); a preceding word `literal` emits the phrase as plain words; build output applying the spacing roles. Do not capitalize here (Task 4's `clean` does).
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: spoken commands (always-convert set)`.

### Task 3: Guarded commands, addresses, all caps

**Files:**
- Modify: `src/flowvoice/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Consumes/Produces: same `apply_commands` signature; extends behavior.

- [ ] **Step 1: Write failing tests**: stays words: `"the time period is long"`, `"a trial period"`, `"a dash of salt"`, `"this colon"`, `"say quote hello"`, `"see you dot"` (dot with no TLD and no `@`); converts: `"I am done period"` -> `"I am done."`, `"Done, period."` -> `"Done."`, `"done period new line next"` -> `"done.\nnext"` (period followed by another command), `"note colon buy milk"` -> `"note: buy milk"`, `"well hyphen known"` -> `"well-known"`, `"wait dash what"` -> `"wait\u2014what"`, `"john at sign gmail dot com"` -> `"john@gmail.com"`, `"example dot com slash pricing"` -> `"example.com/pricing"`, `"my_name"` via `"my underscore name"`, `"all caps hello end caps world"` -> `"HELLO world"`, `"all caps hello world"` -> `"HELLO WORLD"`, `"literal period"` -> `"period"`, `"literal dot"` -> `"dot"`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** the guard rules from Global Constraints inside the scan loop (previous-word guard set; "period" set-off check looks at neighboring punctuation/end/next command; "dot" TLD lookahead or `@`-run lookbehind; address runs join `slash/hyphen/dash/underscore` too); implement `all caps` / `end caps` as a pass over the result uppercasing between the markers (unclosed = to end).
- [ ] **Step 4: Run tests.** Expected: PASS (Task 2 tests still pass).
- [ ] **Step 5: Commit** `feat: guarded commands, addresses, all caps`.

### Task 4: Commands in cleanup, preserve line breaks

**Files:**
- Modify: `src/flowvoice/cleanup.py`
- Test: `tests/test_cleanup.py`

**Interfaces:**
- Consumes: `apply_commands` (Tasks 2-3).
- Produces: `clean(text: str, *, fillers=..., backtracks=..., commands: dict[str, str] | None = None) -> str` (new `commands` argument; `None` = spoken commands off). Order: backtracks, commands, fillers, repeat-collapse, whitespace, capitalization.

- [ ] **Step 1: Write failing tests**: `clean("hello new line world", commands=DEFAULT_COMMANDS) == "Hello\nWorld"`; `"hello new paragraph world"` -> `"Hello\n\nWorld"`; `"yes new line yes"` -> `"Yes\nYes"` (no repeat-merge across a break); `"hello comma how are you question mark"` -> `"Hello, how are you?"`; end-to-end address `clean("john at sign gmail dot com", commands=DEFAULT_COMMANDS) == "john@gmail.com"` (no capitalization of address-like tokens: containing `@`, `/`, or `word.tld`); `"the time period is long"` -> `"The time period is long"`; backtracking first: `"Hi. Send it to Bob comma. Scratch that. Send it to Alice."` -> `"Hi. Send it to Alice."`; `commands=None` leaves `"hello new line world"` as `"Hello new line world"`; all existing v1 cleanup tests still pass.
- [ ] **Step 2: Run** `pytest tests/test_cleanup.py -q`. Expected: FAIL on the new cases.
- [ ] **Step 3: Implement**: whitespace collapse touches only spaces/tabs and trims spaces around `\n`; `_REPEAT` uses `[ \t]+` between repeats; capitalization also fires after `\n` and after a bullet's `- ` is NOT capitalized (`"- apples"` stays); skip address-like tokens.
- [ ] **Step 4: Run all tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: wire spoken commands into cleanup, preserve line breaks`.

### Task 5: History store and foreground app name

**Files:**
- Create: `src/flowvoice/history.py`, `tests/test_history.py`

**Interfaces:**
- Produces: `@dataclass HistoryEntry(id: int | None, created_at: str, raw_text: str, clean_text: str, app_name: str)`; `class History`: `__init__(self, path: Path | None = None)` (default `%APPDATA%\FlowVoice\history.db`; creates dir and table), `add(self, raw: str, clean: str, app_name: str = "") -> HistoryEntry`, `list(self, limit: int = 200, query: str = "") -> list[HistoryEntry]` (newest first; query matches `clean_text` or `raw_text` case-insensitively), `delete(self, entry_id: int) -> None`, `clear(self) -> None`. `active_app_name() -> str` (foreground window's exe name via ctypes `GetForegroundWindow`/`QueryFullProcessImageNameW`; `""` on any failure).

- [ ] **Step 1: Write failing tests** (tmp db): add then list returns it with the app name; newest first; query filters case-insensitively on clean and raw; limit respected; delete removes one; clear removes all; two `History` objects on one file see each other's rows; add from two threads concurrently loses nothing; `active_app_name()` returns a `str` and never raises.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** with a fresh `sqlite3.connect` per call (thread safety); `created_at` ISO local time.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: local history store`.

### Task 6: TalkMode state machine

**Files:**
- Create: `src/flowvoice/talkmode.py`, `tests/test_talkmode.py`

**Interfaces:**
- Produces: `class TalkMode`: `__init__(self, on_start, on_stop, on_cancel, *, clock=time.monotonic, hands_free=True, silence_stop_seconds=4.0, tap_seconds=0.3, double_tap_seconds=0.5, max_seconds=300.0, voice_threshold=0.05)` (callbacks take no args); methods `press()`, `release()`, `other_key(name: str)`, `click()`, `level(value: float)`, `tick()`; read-only `state` -> `"idle" | "held" | "latched"`; mutable attributes `hands_free`, `silence_stop_seconds`. Thread-safe (internal lock). `press` while idle -> `on_start`; release of a hold >= `tap_seconds` -> `on_stop`; release of a shorter press -> latch if `hands_free` and the previous short press ended within `double_tap_seconds` (no callback; recording continues), otherwise `on_cancel` and remember the tap time; `press` while latched -> `on_stop` and ignore the following release; `other_key` while held -> `on_cancel` (release then ignored), `other_key("esc")` while held or latched -> `on_cancel`, other keys while latched ignored; `click` idle -> `on_start` + latched, latched -> `on_stop`, held -> ignored; `level(v)` with `v >= voice_threshold` records `last_voice` and `heard_speech`; `tick` while latched -> `on_stop` if (`heard_speech` and clock - `last_voice` >= `silence_stop_seconds`) or clock - latch start >= `max_seconds`; `tick` never stops a held press.

- [ ] **Step 1: Write failing tests** with a fake clock and recorded callbacks: hold 1.0 s -> `["start","stop"]`; tap 0.1 s -> `["start","cancel"]` and nothing transcribed; double-tap (press, release at +0.1, press at +0.2, release at +0.1) -> `["start","cancel","start"]`, state `"latched"`; third press -> `"stop"` then its release ignored, state `"idle"`; two taps 0.6 s apart -> two cancels, no latch; `hands_free=False` double-tap does not latch; `other_key("c")` while held -> cancel and following release ignored; `other_key("esc")` while latched -> cancel, `other_key("c")` while latched ignored; click idle -> start+latched, click again -> stop, click while held ignored; silence: latched with no `level()` call above threshold, `tick` at +10 s -> no stop; `level(0.5)` at t=0, `tick` at +4.1 -> stop; `level(0.5)` again at +3 then `tick` at +4.1 -> no stop; held press with long silence -> `tick` never stops; max_seconds cap stops a latched take at 300 s; events after a stop-by-silence are handled as idle.
- [ ] **Step 2: Run** `pytest tests/test_talkmode.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `TalkMode` as specified.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: TalkMode hold/tap/double-tap/latch state machine`.

### Task 7: Hotkey layer feeds TalkMode

**Files:**
- Modify: `src/flowvoice/hotkey.py`, `tests/test_hotkey.py`

**Interfaces:**
- Consumes: `TalkMode` method names (Task 6).
- Produces: `PushToTalk(key: str, on_press: Callable[[], None], on_release: Callable[[], None], on_other_key: Callable[[str], None] = lambda name: None, backend=keyboard)` with `enable()`/`disable()`. It dedupes auto-repeat (one `on_press` per physical press), ignores the left Ctrl for `"right ctrl"`, and calls `on_other_key(name)` on any non-modifier key-down (including `"esc"`) regardless of held state. `Toggle` unchanged.

- [ ] **Step 1: Rewrite the PushToTalk tests** (keep Toggle tests): press then release -> `on_press`, `on_release`; auto-repeat downs -> one `on_press`; up without down ignored; left ctrl ignored; other key down -> `on_other_key("c")`; modifier keys never reach `on_other_key`; esc down -> `on_other_key("esc")`; disable stops callbacks.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement**: remove start/stop/cancel semantics (now in TalkMode); keep the `_MODIFIERS` set and name filtering.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `refactor: PushToTalk emits raw press/release/other-key events`.

### Task 8: Recorder levels and Dictation result callback

**Files:**
- Modify: `src/flowvoice/recorder.py`, `src/flowvoice/pipeline.py`, `tests/test_recorder.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces: `Recorder.on_level: Callable[[float], None] | None` (public attribute, default `None`), called from `_on_audio` only while recording with `min(1.0, rms * 10)`. `Dictation.__init__(..., on_done=..., on_result: Callable[[str, str, object], None] = lambda raw, clean, tag: None)`; `submit(self, audio: np.ndarray | None, tag: object = None) -> None`; `on_result(raw_transcript, cleaned_text, tag)` is called after a successful paste only; `paste`, `on_error`, `on_done` semantics unchanged.

- [ ] **Step 1: Write failing tests**: recorder: a 100 ms chunk of constant 0.01 -> level about 0.1 (approx), 0.5 -> 1.0 (clamped), no call when not recording, no error when `on_level` is `None`; pipeline: `on_result` gets `("um hello", "Hello", tag)` after paste; not called for empty transcript or when paste raises; `tag` per submission is preserved in order across 3 queued submissions.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** both.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: recorder level callback and dictation result callback`.

### Task 9: App integration

**Files:**
- Create: `src/flowvoice/ui_api.py` (`Ui` Protocol)
- Modify: `src/flowvoice/app.py`, `tests/test_app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `TalkMode` (6), `History`/`HistoryEntry`/`active_app_name` (5), `Dictation` changes (8), `clean(..., commands=)` (4), `Config` (1).
- Produces: `Ui` Protocol: `set_state(state: Literal["idle","recording","processing"]) -> None`, `set_level(level: float) -> None`, `notify(message: str) -> None`, `add_history(entry: HistoryEntry) -> None`. `App.__init__(self, config: Config, *, engine, recorder, speaker, ui, history: History | None = None, paste=paste_text, copy_selection=copy_selection, active_app=active_app_name, clock=time.monotonic)`. Attributes: `config`, `talk: TalkMode` (callbacks are `on_ptt_start`, `on_ptt_stop`, `on_ptt_cancel`, which keep their v1 behavior), `dictation`. Methods: `press()`, `release()`, `other_key(name)`, `click()`, `tick()` (delegate to `talk`), `on_level(level)` (sets `recorder.on_level` to this in `__init__`; forwards to `ui.set_level` and `talk.level`), `apply_config(cfg: Config)` (replaces `config`, updates `talk.hands_free` and `talk.silence_stop_seconds`), `on_tts_trigger()` unchanged. On `on_ptt_start` the foreground app name is captured and passed as the tag to `submit`; `_on_result(raw, clean, tag)` writes a history entry when `config.save_history` and `history` are set, catching any exception (then `ui.notify("History unavailable")`), and always calls `ui.add_history(HistoryEntry(id=None-or-saved...))` so the Home tab can show the last text (id `None` when not saved). `_clean` passes `commands=config.command_phrases if config.voice_commands else None`.

- [ ] **Step 1: Update existing tests** to the new constructor (`ui=` instead of `tray=`, fake `Ui` with `set_level`/`add_history`, `history=None` by default) and add: `test_double_tap_cycle_pastes_once` (press/release/press/release with fake clock, then `click()`... then audio pasted exactly once); `test_silence_stop_pastes` (latch, `on_level(0.5)`, advance clock 5 s, `tick()` -> pasted); `test_history_entry_written_with_app_name_and_texts`; `test_history_not_written_when_save_history_off`; `test_history_failure_does_not_block_paste_or_kill_worker` (history.add raises; paste still happens; a second dictation also pastes; `ui.notify` called); `test_commands_applied` (`"hello comma new line world"` pastes `"Hello,\nWorld"`); `test_voice_commands_off_leaves_words`; `test_apply_config_updates_silence_and_phrases_live`; `test_on_level_forwards_to_ui_and_talk`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** `ui_api.py` and the `App` changes.
- [ ] **Step 4: Run** `pytest tests -q -m "not slow"`. Expected: PASS (old `tray.py`, `settings.py`, `__main__.py` still exist and are fixed in Task 15; `__main__` is not imported by tests).
- [ ] **Step 5: Commit** `feat: App uses TalkMode, commands, history and Ui interface`.

### Task 10: Qt dependency swap and thread-safe bridge

**Files:**
- Create: `src/flowvoice/ui/__init__.py`, `src/flowvoice/ui/bridge.py`, `tests/conftest.py`, `tests/test_bridge.py`
- Modify: `pyproject.toml`
- Test: `tests/test_bridge.py`

**Interfaces:**
- Produces: `class QtUi(QObject)` implementing `Ui`: signals `state_changed = Signal(str)`, `level_changed = Signal(float)`, `message = Signal(str)`, `entry_added = Signal(object)`; methods `set_state`, `set_level`, `notify`, `add_history` each just emit the matching signal. `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` and provides a session `qapp` fixture (`QApplication.instance() or QApplication([])`).

- [ ] **Step 1: Update dependencies**: in `pyproject.toml` add `PySide6`, remove `pystray` and `Pillow`; `.venv\Scripts\python -m pip install -e ".[dev]"`; expected `import PySide6.QtWidgets` works. (`tray.py` still imports pystray until Task 15; install keeps it resolvable by leaving `pystray` and `Pillow` installed, only removing them from `pyproject.toml`.)
- [ ] **Step 2: Write failing tests**: a connected slot on a `QObject` living in the main thread receives `set_state("recording")`, `set_level(0.5)`, `notify("x")`, `add_history(obj)` emitted from a plain `threading.Thread`, after `QCoreApplication.processEvents()`, and the slot ran on the main thread (`threading.get_ident()` equals the main thread id); `QtUi` satisfies the `Ui` protocol (`isinstance` via `runtime_checkable` or attribute check).
- [ ] **Step 3: Run tests.** Expected: FAIL.
- [ ] **Step 4: Implement** `bridge.py`.
- [ ] **Step 5: Run tests.** Expected: PASS. **Commit** `feat: Qt bridge for cross-thread UI updates`.

### Task 11: Waveform pill

**Files:**
- Create: `src/flowvoice/ui/pill.py`, `tests/test_pill.py`, `scripts/render_previews.py`

**Interfaces:**
- Produces: `class PillWidget(QWidget)`: `__init__(self, scale: float = 1.0, always_visible: bool = True)`; `set_state(self, state: str) -> None` (`"idle"|"recording"|"processing"`); `set_level(self, level: float) -> None` (appends to a fixed-length history that drives the waveform bars); `apply(self, scale: float, always_visible: bool) -> None`; `clicked = Signal()`. Frameless, translucent, always-on-top, tool window, `WindowDoesNotAcceptFocus`, `WA_ShowWithoutActivating`; after first show set `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` through ctypes. Positioned bottom-center of the primary screen, re-centered on state/size change. Colors: idle `#8e8e93` (dim), recording `#ff3b30`, processing `#ff9f0a`. Idle size about 56x16 px, active about 220x48 px, both times `scale`.

- [ ] **Step 1: Write failing tests** (offscreen): constructs in each state and `grab()` returns a non-null image; the pixel at the capsule center is reddish when recording (`r > 200 and g < 100`), amber when processing, grey when idle; two different level sequences render different images while recording; `scale=1.5` is wider than `scale=1.0`; with `always_visible=False` the widget is hidden when idle and visible when recording; a left click (`QTest.mouseClick`) emits `clicked` once; window flags include `WindowDoesNotAcceptFocus`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** with `paintEvent` (antialiased rounded capsule, soft shadow, 21 waveform bars from the level history while recording, three animated dots driven by a `QTimer` while processing, gentle idle look) and a `QTimer` at about 33 ms only while active.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Visual check:** `scripts/render_previews.py` saves `pill_idle.png`, `pill_recording.png` (with a believable level sequence), `pill_processing.png` into `.superpowers/preview/`; read the three PNGs and confirm a rounded capsule, a visible red waveform, amber dots; fix the drawing until they look right.
- [ ] **Step 6: Commit** `feat: waveform pill`.

### Task 12: Theme, main window shell, Home tab

**Files:**
- Create: `src/flowvoice/ui/theme.py`, `src/flowvoice/ui/main_window.py`, `src/flowvoice/ui/home_view.py`, `tests/test_main_window.py`

**Interfaces:**
- Produces: `theme.stylesheet(dark: bool, scale: float) -> str` (rounded cards, `border-radius`, system font stack "Segoe UI Variable, Segoe UI", font sizes scaled); `theme.is_dark(app: QApplication) -> bool` (window color lightness). `HomeView(QWidget)`: `set_state(state: str)`, `show_entry(entry: HistoryEntry)`, `toggle_clicked = Signal()`, `hint(text: str)`. `MainWindow(QMainWindow)`: `__init__(self, config: Config, history: History | None, on_save_config: Callable[[Config], None])`, left sidebar with items `Home`, `History`, `Settings`, `home: HomeView`, `history_view`, `settings_view` (added by Tasks 13 and 14 via placeholders now), `quit_requested = Signal()`, `request_quit()`; closing the window hides it (ignores the close event) unless quit was requested; remembers size/position with `QSettings("FlowVoice", "FlowVoice")`; `apply_scale(scale: float)`.

- [ ] **Step 1: Write failing tests**: sidebar has exactly Home/History/Settings; selecting each shows the matching page; `HomeView.set_state("recording")` changes the status text; `show_entry` displays the clean text and a Copy button puts it on the clipboard; the Start/Stop button emits `toggle_clicked`; close event hides the window without quitting; `request_quit()` emits `quit_requested`; `stylesheet(True, 1.0)` contains `border-radius` and differs from `stylesheet(False, 1.0)`; `stylesheet(False, 1.5)` has larger font sizes than at 1.0.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** (placeholder `QWidget`s for History and Settings pages replaced in Tasks 13-14).
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: main window shell, theme and Home tab`.

### Task 13: History tab

**Files:**
- Create: `src/flowvoice/ui/history_view.py`, `tests/test_history_view.py`
- Modify: `src/flowvoice/ui/main_window.py`

**Interfaces:**
- Consumes: `History` (Task 5).
- Produces: `HistoryView(QWidget)`: `__init__(self, history: History | None, confirm: Callable[[str], bool] = <QMessageBox yes/no>)`; `refresh(self, query: str = "") -> None`; `prepend(self, entry: HistoryEntry) -> None` (ignored when `entry.id is None`); a search box (typing calls `refresh`); each row shows time, app, text; buttons Copy, Delete, Clear all (Clear all calls `confirm` first); `row_count() -> int`; a friendly empty state ("Nothing here yet") and a "History is off" message when `history is None`.

- [ ] **Step 1: Write failing tests** (tmp `History` with 3 entries): `refresh()` shows 3 rows newest first; searching "milk" shows only matching rows; select + Copy puts clean text on the clipboard; Delete removes the row and the DB row; Clear all with `confirm=lambda m: False` keeps everything, with `True` empties both; `prepend` adds a row at the top and ignores `id=None`; `history=None` shows the off message and does not raise.
- [ ] **Step 2: Run tests.** Expected: FAIL. **Step 3: Implement** and mount it in `MainWindow` (replace the placeholder). **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: history tab`.

### Task 14: Settings tab and hotkey capture

**Files:**
- Create: `src/flowvoice/ui/settings_view.py`, `src/flowvoice/ui/hotkey_edit.py`, `tests/test_settings_view.py`
- Modify: `src/flowvoice/settings_logic.py`, `src/flowvoice/ui/main_window.py`, `tests/test_settings_logic.py`

**Interfaces:**
- Produces in `settings_logic`: `escape_text(s: str) -> str` (newline -> `\n`, tab -> `\t`, backslash doubled) and `unescape_text(s: str) -> str` (inverse); `rows_to_commands(rows: list[tuple[str, str]]) -> dict[str, str]` (phrase lowercased/trimmed, blank phrases dropped, outputs unescaped, later rows win). `HotkeyEdit(QLineEdit)`: `hotkey() -> str`, `set_hotkey(text: str)`, `begin_capture()` (background thread runs `keyboard.read_hotkey(suppress=False)` and delivers via signal `captured = Signal(str)`; the field shows "Press keys..." meanwhile; `captured` sets the text). `SettingsView(QWidget)`: `__init__(self, config: Config, mics: list[tuple[str, int | None]], on_save: Callable[[Config], None])`, `to_config(self) -> Config`, `load(self, config: Config)`. Controls: push-to-talk and read-aloud `HotkeyEdit`, model combo (`tiny.en, base.en, small.en, medium.en`), microphone combo, toggles (start with Windows, save history, hands-free double-tap, pill always visible, spoken commands), silence slider (1-10 s), UI size slider (0.8-1.6), filler and backtrack phrase editors (one per line, via `parse_phrases`), command table (`QTableWidget`, two columns phrase/output, add/remove row buttons), a "Clear history" button is NOT here (History tab owns it), Save button.

- [ ] **Step 1: Write failing tests**: logic: `unescape_text(escape_text(s)) == s` for `"\n- "`, `"\u2014"`, a backslash; `rows_to_commands([("New Line", "\\n")]) == {"new line": "\n"}`; blank phrase dropped. View: `SettingsView(Config(ptt_key="f9", ui_scale=1.3), ...).to_config()` equals that config; changing every control then `to_config()` reflects each; the command table round-trips `DEFAULT_COMMANDS` unchanged; adding a table row `("oops sign", "!")` appears in `to_config().command_phrases`; Save calls `on_save` with the same object `to_config()` returns; `HotkeyEdit.set_hotkey("right ctrl")` round-trips; emitting `captured("f9")` sets the field.
- [ ] **Step 2: Run tests.** Expected: FAIL. **Step 3: Implement** and mount in `MainWindow` (replace the placeholder). **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Visual check:** extend `scripts/render_previews.py` to save `home.png`, `history.png`, `settings.png` of the main window (light and dark) into `.superpowers/preview/`; read them and confirm a tidy rounded layout with readable text; fix until it looks right.
- [ ] **Step 6: Commit** `feat: settings tab and hotkey capture`.

### Task 15: Shell, tray and entry-point wiring

**Files:**
- Create: `src/flowvoice/ui/shell.py`, `tests/test_shell.py`
- Modify: `src/flowvoice/__main__.py`
- Delete: `src/flowvoice/tray.py`, `src/flowvoice/settings.py`, and their stale tests (`tests/test_settings.py` if present)

**Interfaces:**
- Consumes: everything above.
- Produces: `Shell.__init__(self, config: Config, history: History | None)`: creates `QApplication`, `QtUi`, `PillWidget`, `MainWindow`, `QSystemTrayIcon` (menu: Open, Start/Stop, Quit; double-click opens; icon drawn with `QPainter`), connects `QtUi` signals to the pill and Home/History views, pill `clicked` and Home `toggle_clicked` to a settable `on_toggle` callback, exposes `ui: QtUi`, `pill`, `window`, `tray`, `on_quit` callback, `apply_config(cfg)` (scale, always_visible, window scale), `run() -> int` (`QApplication.exec()`), and a 200 ms `QTimer` calling a settable `on_tick`. `__main__.main()`: load config, set autostart, build `History` (or `None` when `save_history` is off), build `Shell`; on a worker thread load `Engine`, create `Recorder` (open it), build `App(..., ui=shell.ui, history=history)`, create hotkeys (`PushToTalk(cfg.ptt_key, app.press, app.release, app.other_key)`, `Toggle(cfg.tts_key, read_aloud)`), set `shell.on_toggle = app.click`, `shell.on_tick = app.tick`, notify "Ready"; settings save handler: `save_config(new)`, restart (as in v1) if `needs_restart(old, new)`, else `app.apply_config(new)` + `shell.apply_config(new)` + notify "Settings saved"; quit closes recorder and hotkeys then `QApplication.quit()`.

- [ ] **Step 1: Write failing tests** (offscreen): `Shell(Config(), None)` constructs without error; `shell.ui.set_state("recording")` processed through events turns the pill red; `shell.ui.add_history(entry)` shows the text on Home; calling `shell.on_toggle` via the pill click works; tray menu has Open, Start/Stop, Quit; `apply_config(Config(ui_scale=1.5, pill_always_visible=False))` changes the pill size and hides it while idle.
- [ ] **Step 2: Run tests.** Expected: FAIL. **Step 3: Implement** the shell and the new `__main__`; delete the old tray/settings modules and remove stale imports. **Step 4: Run** `pytest tests -q`. Expected: PASS (no references to `pystray`, `PIL`, `tkinter` remain: verify with a grep).
- [ ] **Step 5: Smoke launch** `Start-Process .venv\Scripts\python.exe -m flowvoice` for 15 s: process alive, no stderr; also confirm the pill does not take focus: record the foreground window handle, show the pill in the recording state, and confirm the handle is unchanged.
- [ ] **Step 6: Commit** `feat: Qt shell and tray wiring; remove tkinter and pystray UI`.

### Task 16: Docs and manual verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**: hands-free (double-tap, pill click, silence stop, Esc), history (location, off switch, clear), spoken commands list with the guard rules and "literal" escape, settings and window, how to quit, known limits (admin apps, text-only clipboard, guard is a heuristic).
- [ ] **Step 2: Run the full suite** `.venv\Scripts\python -m pytest tests -q`. Expected: all pass (record the count).
- [ ] **Step 3: Manual checks with the user** (report each as pass/fail; the agent cannot do these alone): double-tap Right Ctrl latches and a pause ends it with the text pasted; single tap does nothing; pill click starts and stops; pill is red with a moving waveform and never steals focus before a paste into Notepad, a browser box and Word; "hello comma new paragraph how are you question mark" pastes correctly; "the time period is long" stays; "john at sign gmail dot com" -> `john@gmail.com`; History tab lists entries and search/delete/clear work; turning history off stops new entries; Settings changes (phrases live, hotkey restart) apply; UI size slider enlarges the pill and window text.
- [ ] **Step 4: Fix anything that fails** (test first where possible); re-run the suite.
- [ ] **Step 5: Commit** `docs: v2 README and verification notes`.
