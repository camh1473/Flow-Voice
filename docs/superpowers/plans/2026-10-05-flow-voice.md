# Flow Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A free, local Windows tray app: hold a hotkey, speak, clean text is pasted at the cursor in any app; a second hotkey reads selected text aloud.

**Architecture:** Small single-purpose modules under `src/flowvoice/`, wired together by `app.py`. Every module with OS side effects (clipboard, keyboard, mic, SAPI) takes its side-effecting functions as constructor/function arguments so unit tests use fakes. Transcription runs on a worker thread so the hotkey listener never blocks.

**Tech Stack:** Python 3.12, `faster-whisper`, `sounddevice`, `numpy`, `keyboard`, `pyperclip`, `pywin32` (SAPI), `pystray`, `Pillow`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-05-flow-voice-design.md`

## Global Constraints

- Platform: Windows only for v1. Project lives at `C:\Users\camh1\dev\flow-voice\`, never in OneDrive.
- All speech is local: no Google Cloud, no API keys, no network calls except the one-time Whisper model download.
- STT: `faster-whisper`, default model `small.en`, CUDA if available else CPU int8; model loaded once at startup.
- Audio: 16 kHz mono; ~300 ms pre-roll; taps shorter than ~250 ms are ignored.
- Default push-to-talk key: Right Ctrl, configurable. Second hotkey reads selection aloud; pressing it again stops.
- TTS: Windows built-in SAPI voices.
- Config: JSON at `%APPDATA%\FlowVoice\config.json` with hotkeys, model, mic device, start-with-Windows.
- Clipboard is always restored, including on failure. Empty/silent audio pastes nothing. Errors show as a tray notification, never a crash.
- Python executable: `C:\Users\camh1\AppData\Local\Programs\Python\Python312\python.exe` (the `python` alias is the Store shortcut; use the venv's python after Task 1).
- Non-goals: LLM polish, custom dictionaries, command mode, phone app, installer, streaming partial text.
- One deviation from the spec: TTS uses `pywin32` (`SAPI.SpVoice`, async + purge) instead of `pyttsx3`, because it can be interrupted reliably from another thread. Same SAPI voices.

## Review Focus

1. Silence or noise-only audio: Whisper hallucinates text ("Thank you.") — must paste nothing (VAD filter on, empty result pasted as nothing). Tested in Task 3.
2. Key held down auto-repeats press events: must start recording once, not many times. Tested in Task 6.
3. Tap shorter than 250 ms: ignored, nothing transcribed or pasted. Tested in Task 4.
4. User starts a new dictation while the previous one is still transcribing: must queue/serialize, never run two transcriptions at once or drop the text. Tested in Task 7.
5. Paste raises mid-way (e.g. focused app rejects input): original clipboard still restored. Tested in Task 5.

---

### Task 1: Scaffold and config

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/flowvoice/__init__.py`, `src/flowvoice/config.py`, `tests/test_config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `@dataclass Config(ptt_key: str = "right ctrl", tts_key: str = "ctrl+alt+s", model: str = "small.en", mic_device: int | None = None, start_with_windows: bool = False)`; `default_path() -> Path` (`%APPDATA%\FlowVoice\config.json`); `load_config(path: Path | None = None) -> Config`; `save_config(cfg: Config, path: Path | None = None) -> None`.

- [ ] **Step 1: Scaffold** — `pyproject.toml` (setuptools, `src` layout, runtime deps listed in Tech Stack, `pytest` as dev extra, `pythonpath = ["src"]` for pytest), `.gitignore` (`.venv/`, `__pycache__/`, `*.egg-info/`). Create the venv: `C:\Users\camh1\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`. Expected: install succeeds, `.venv\Scripts\python -c "import faster_whisper, sounddevice, keyboard, pystray, win32com.client"` exits 0.
- [ ] **Step 2: Write failing tests** in `tests/test_config.py`: `test_defaults_when_file_missing` (`load_config(tmp/"x.json") == Config()`), `test_roundtrip` (save then load returns equal Config with `ptt_key="f9"`, `model="base.en"`), `test_corrupt_file_returns_defaults` (garbage JSON -> `Config()`), `test_unknown_keys_ignored`.
- [ ] **Step 3: Run** `.venv\Scripts\python -m pytest tests/test_config.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `config.py` per Interfaces; `save_config` creates parent dirs; `load_config` never raises.
- [ ] **Step 5: Run tests.** Expected: 4 PASS.
- [ ] **Step 6: Commit** `feat: scaffold project and config`.

### Task 2: Cleanup

**Files:**
- Create: `src/flowvoice/cleanup.py`, `tests/test_cleanup.py`

**Interfaces:**
- Produces: `clean(text: str) -> str` (pure).

- [ ] **Step 1: Write failing table-driven test** `test_clean` with `pytest.mark.parametrize`:
  - `"um so uh I think we should go"` -> `"So I think we should go"`
  - `"I I I want the the report"` -> `"I want the report"`
  - `"hello   world ."` -> `"Hello world."`
  - `"the umbrella is here"` -> `"The umbrella is here"` (fillers match whole words only)
  - `"  "` -> `""`
  - `"first sentence. second sentence"` -> `"First sentence. Second sentence"`
  - `"Um, okay"` -> `"Okay"` (filler plus trailing comma removed)
- [ ] **Step 2: Run** `pytest tests/test_cleanup.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `clean` with regexes: drop `um|uh|er|erm|hmm` as whole words (case-insensitive, with an adjacent comma), collapse immediate repeated words (case-insensitive), collapse whitespace, remove space before `.,!?`, capitalize first letter and letters after `. ! ?`.
- [ ] **Step 4: Run tests.** Expected: all PASS.
- [ ] **Step 5: Commit** `feat: add transcript cleanup`.

### Task 3: Whisper engine

**Files:**
- Create: `src/flowvoice/engine.py`, `tests/test_engine.py`, `tests/data/hello.wav` (generate with the Windows SAPI voice: say "hello world this is a test" and save 16 kHz mono; add a `tests/make_test_audio.py` that does it)

**Interfaces:**
- Produces: `class Engine`: `__init__(self, model_name: str = "small.en", device: str = "auto")` (loads model once; `auto` -> `cuda` if `ctranslate2.get_cuda_device_count() > 0` with `float16`, else `cpu` with `int8`); `transcribe(self, audio: np.ndarray) -> str` where audio is float32 mono 16 kHz in [-1, 1]; returns stripped text, `""` if nothing recognized.

- [ ] **Step 1: Generate test audio** with `tests/make_test_audio.py`; verify `tests/data/hello.wav` exists and is about 2 s.
- [ ] **Step 2: Write failing tests** (mark `slow`; model `tiny.en` for speed): `test_transcribes_known_phrase` (result lowercased contains "hello" and "test"), `test_silence_returns_empty` (2 s of zeros -> `""`), `test_low_noise_returns_empty` (2 s of gaussian noise, std 0.005 -> `""`).
- [ ] **Step 3: Run** `pytest tests/test_engine.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** `Engine` with `faster_whisper.WhisperModel`; call `transcribe(audio, language="en", vad_filter=True, beam_size=1, condition_on_previous_text=False)` and join segment text.
- [ ] **Step 5: Run tests.** Expected: 3 PASS (first run downloads `tiny.en`).
- [ ] **Step 6: Commit** `feat: add faster-whisper engine`.

### Task 4: Recorder

**Files:**
- Create: `src/flowvoice/recorder.py`, `tests/test_recorder.py`

**Interfaces:**
- Produces: `class Recorder`: `__init__(self, device: int | None = None, preroll_ms: int = 300, min_ms: int = 250, stream_factory=sounddevice.InputStream)`; `open(self) -> None` (starts the always-on stream feeding a rolling pre-roll buffer); `close(self) -> None`; `start(self) -> None` (begin keeping audio, seeded with pre-roll); `stop(self) -> np.ndarray | None` (float32 mono 16 kHz, or `None` if shorter than `min_ms`). Internal `_on_audio(self, indata: np.ndarray, frames: int, time, status) -> None` is the stream callback.

- [ ] **Step 1: Write failing tests** feeding `_on_audio` directly with 16 kHz chunks of 100 ms: `test_tap_shorter_than_min_returns_none` (start, feed 100 ms, stop -> None), `test_long_recording_returned` (feed 1 s -> array length ~16000+preroll), `test_preroll_included` (feed 300 ms before `start`, then 500 ms after; result length >= 12800 samples), `test_audio_before_start_not_kept_beyond_preroll` (feed 2 s before `start`; after start+0.5 s result length <= 16000*0.8+tolerance).
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** with a `collections.deque` of chunks trimmed to `preroll_ms`; when recording, append to a list; `stop` concatenates and applies the `min_ms` rule on recorded (non-pre-roll) duration.
- [ ] **Step 4: Run tests.** Expected: 4 PASS.
- [ ] **Step 5: Commit** `feat: add recorder with pre-roll`.

### Task 5: Inject

**Files:**
- Create: `src/flowvoice/inject.py`, `tests/test_inject.py`

**Interfaces:**
- Produces: `paste_text(text: str, *, get_clip=pyperclip.paste, set_clip=pyperclip.copy, send=keyboard.send, type_text=keyboard.write, sleep=time.sleep) -> None`. Empty/whitespace `text` does nothing (no clipboard access).

- [ ] **Step 1: Write failing tests** with fake clipboard and recorded `send` calls: `test_pastes_and_restores_clipboard` (clipboard "orig" -> sends `"ctrl+v"` once, clipboard text was `text` at send time, final clipboard "orig"), `test_empty_text_noop`, `test_restores_clipboard_when_send_raises` (send raises RuntimeError; exception re-raised? No: caught, falls back to `type_text(text)`, clipboard still "orig"), `test_restore_happens_after_paste_delay` (sleep called between send and restore).
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** save clipboard, set text, send Ctrl+V, `sleep(0.15)`, restore in a `finally`; on send failure fall back to `type_text`.
- [ ] **Step 4: Run tests.** Expected: 4 PASS.
- [ ] **Step 5: Commit** `feat: add clipboard paste injector`.

### Task 6: Hotkey

**Files:**
- Create: `src/flowvoice/hotkey.py`, `tests/test_hotkey.py`

**Interfaces:**
- Produces: `class PushToTalk`: `__init__(self, key: str, on_start: Callable[[], None], on_stop: Callable[[], None], backend=keyboard)`; `enable(self) -> None`; `disable(self) -> None`. `class Toggle`: `__init__(self, key: str, on_trigger: Callable[[], None], backend=keyboard)`; `enable()`, `disable()`. The backend is anything with `hook_key(key, callback)` and `add_hotkey(...)`/`unhook(...)`; tests use a fake that delivers `KeyboardEvent`-like objects with `.event_type` (`"down"`/`"up"`).

- [ ] **Step 1: Write failing tests** with a fake backend: `test_press_then_release_calls_start_then_stop`, `test_auto_repeat_down_events_call_start_once` (down x5 then up -> `on_start` once, `on_stop` once), `test_up_without_down_ignored`, `test_disable_stops_callbacks`, `test_toggle_fires_once_per_press`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** with a `_held` flag guarding repeats; callbacks run inside the hook so they must be fast (documented in the docstring: do no work there).
- [ ] **Step 4: Run tests.** Expected: 5 PASS.
- [ ] **Step 5: Commit** `feat: add push-to-talk and toggle hotkeys`.

### Task 7: TTS and pipeline

**Files:**
- Create: `src/flowvoice/tts.py`, `src/flowvoice/pipeline.py`, `tests/test_tts.py`, `tests/test_pipeline.py`

**Interfaces:**
- Produces in `tts.py`: `class Speaker`: `__init__(self, voice_factory=lambda: win32com.client.Dispatch("SAPI.SpVoice"))`; `speak(self, text: str) -> None` (async, purges any current speech first; empty text is a no-op); `stop(self) -> None`; `is_speaking(self) -> bool`; `toggle(self, text: str) -> None` (stops if speaking, else speaks).
- Produces in `pipeline.py`: `class Dictation`: `__init__(self, transcribe: Callable[[np.ndarray], str], clean: Callable[[str], str], paste: Callable[[str], None], on_error: Callable[[str], None])`; `submit(self, audio: np.ndarray | None) -> None` (queues work to ONE background worker thread; `None` is ignored); `join(self, timeout: float = 5.0) -> None` (waits for the queue to drain, for tests/shutdown). Failures in any stage call `on_error(message)` and the worker keeps running.

- [ ] **Step 1: Write failing tests** `test_tts.py` with a fake voice: `test_speak_calls_async_with_purge`, `test_empty_text_noop`, `test_toggle_stops_when_speaking`. `test_pipeline.py`: `test_pastes_cleaned_transcript`, `test_empty_transcript_pastes_nothing`, `test_none_audio_ignored`, `test_overlapping_submissions_run_serially_in_order` (fake `transcribe` sleeps 100 ms and records concurrent-call count; submit 3 -> max concurrency 1, pasted order = submit order), `test_transcribe_error_reports_and_continues`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** `Speaker` (SAPI flags `SVSFlagsAsync=1`, `SVSFPurgeBeforeSpeak=2`; `is_speaking` via `voice.WaitUntilDone(0) is False`), and `Dictation` with a `queue.Queue` and a daemon worker thread.
- [ ] **Step 4: Run tests.** Expected: 8 PASS.
- [ ] **Step 5: Commit** `feat: add TTS speaker and serial dictation pipeline`.

### Task 8: Tray, indicator, and app wiring

**Files:**
- Create: `src/flowvoice/tray.py`, `src/flowvoice/app.py`, `src/flowvoice/__main__.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: everything above.
- Produces in `tray.py`: `class Tray`: `__init__(self, on_quit: Callable[[], None])`; `run(self) -> None` (blocks; pystray main loop); `set_state(self, state: Literal["idle","recording","processing"]) -> None` (changes icon color and shows/hides a small always-on-top `tkinter` recording indicator on its own thread); `notify(self, message: str) -> None`.
- Produces in `app.py`: `class App`: `__init__(self, config: Config, *, engine, recorder, speaker, tray, paste=paste_text, copy_selection: Callable[[], str] | None = None)`; `on_ptt_start(self)` (set state recording, `recorder.start()`); `on_ptt_stop(self)` (`audio = recorder.stop()`; state processing if audio else idle; `dictation.submit(audio)`); `on_tts_trigger(self)` (copy selection with Ctrl+C via the clipboard-preserving helper, then `speaker.toggle(text)`); `start(self)`/`shutdown(self)`. `main() -> None` in `__main__.py`: load config, create `Engine` (tray notifies "Loading model…" then "Ready"), wire hotkeys, run tray.

- [ ] **Step 1: Write failing tests** `test_app.py` with fakes: `test_ptt_cycle_pastes_text` (start -> stop with fake audio -> fake engine returns "um hello" -> pasted "Hello"), `test_short_tap_pastes_nothing_and_returns_to_idle` (recorder.stop returns None), `test_tts_trigger_speaks_selection`, `test_state_returns_to_idle_after_paste`, `test_engine_error_notifies_tray`.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement** `tray.py` (pystray with Pillow-generated colored circle icons; menu: Quit), `app.py`, `__main__.py`. Tray and `main()` are not unit tested; `App` is.
- [ ] **Step 4: Run all tests** `pytest -v -m "not slow"`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat: wire app, tray, and entry point`.

### Task 9: Run script and manual verification

**Files:**
- Create: `run.bat` (activates the venv and runs `python -m flowvoice`, no console window variant using `pythonw`), `README.md` (install, run, hotkeys, config path, admin-app limitation, model download size)
- Modify: `src/flowvoice/config.py` only if start-with-Windows is wired here: add `set_autostart(enabled: bool) -> None` writing/removing the `HKCU\...\Run` value, with a test using a fake registry function.

- [ ] **Step 1: Write failing test** `test_set_autostart_writes_and_removes_run_key` with a fake registry; run, expect FAIL; implement; expect PASS.
- [ ] **Step 2: Launch** `run.bat`. Expected: tray icon appears; "Ready" notification after model load.
- [ ] **Step 3: Manual checks** (report each as pass/fail): dictate a sentence into Notepad; into a browser text box; into Word/Outlook; hold-and-silent produces nothing; quick tap produces nothing; clipboard text from before dictation is unchanged afterward; select text and press the TTS hotkey -> it speaks, press again -> stops; first word of a sentence is not clipped; time from key release to text under ~2 s on `small.en`.
- [ ] **Step 4: Fix anything that fails** (add a test first where possible), re-run all tests.
- [ ] **Step 5: Commit** `feat: add run script, autostart, README`.
