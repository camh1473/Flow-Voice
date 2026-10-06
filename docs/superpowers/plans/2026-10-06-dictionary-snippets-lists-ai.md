# Flow Voice v3 Implementation Plan (dictionary, snippets, lists, local AI polish)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a personal dictionary, snippets, automatic numbered/bulleted lists, and an optional local-AI (Ollama) polish step to the dictation pipeline.

**Architecture:** Small pure modules (`vocabulary`, `snippets`, `lists`, `ai_polish`, `postprocess`) wrapped around the existing `cleanup.clean`; an `ai` module (stdlib HTTP client for a loopback Ollama) plus an `AiService` that owns status and warm-up; the App calls one `Postprocessor` instead of `clean` directly. Settings gets three new cards that apply live.

**Tech Stack:** Python 3.12, existing stack (faster-whisper 1.2.1, PySide6), stdlib `urllib` / `http.server` (tests), `pytest`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-05-dictionary-snippets-lists-ai-design.md`

## Global Constraints

- Windows only; project at `C:\Users\camh1\dev\flow-voice\` on branch `build`; use `.venv\Scripts\python`. All source and tests ASCII-only (the Write/Edit tools may turn `\u` escapes into literal characters: scan with `Select-String -Pattern '[^\x00-\x7F]'` after every write; the suite's ASCII test enforces it). The Bash tool has no coreutils: use PowerShell. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Pipeline order (spec): Whisper (glossary prompt) -> backtracking -> snippet placeholders -> spoken commands -> fillers/repeats/whitespace/caps (`clean`) -> dictionary -> lists -> AI polish -> snippet expansion -> paste. Raw Whisper text stays the history `raw_text`; the final text is `clean_text`.
- Snippet placeholder = one private-use character `chr(0xE100 + index)` (never a literal in source). Snippet text is inserted verbatim and never re-scanned.
- Limits: 200 dictionary terms, 200 fixes, 100 snippets. Glossary prompt capped at 400 characters.
- AI: off by default; default model `qwen3.5:2b-q4_K_M`; minimum 20 words; timeout 6 s; URL must be loopback (`localhost`, `127.0.0.1`, `::1`) else refused; `/api/chat` with `stream=false`, `think=false`, temperature 0, `keep_alive` 30 min; status values `off | warming | ready | missing model | unavailable`; AI failure or rejection falls back to the rule-based text and must never block or lose a paste; never download models.
- `ai_acceptable`: at least 85% of the original's words present; at most 15% of the result's words new; length 0.7x-1.5x ignoring list markers and newlines; every placeholder present exactly as often as before; no preamble ("sure", "here is", "here's"); strip surrounding quotes and code fences first.
- Defaults: `auto_lists=True`, `ai_enabled=False`, `ai_min_words=20`, `ai_timeout_seconds=6.0`, `ai_url="http://localhost:11434"`.
- Settings changes in this plan apply live (no restart). Settings view never writes files; it calls `on_save`.
- Non-goals: tone adaptation, command mode, cloud models, streaming, per-app dictionaries, snippet variables, import/export, other languages, auto-downloading models.

## Review Focus

1. Snippet text arrives verbatim: the placeholder survives `clean()`, dictionary, lists and the AI, Whisper's touching punctuation is absorbed, `literal` types the words. Tested in Tasks 4, 9 and 10.
2. The AI never changes the user's words and never blocks a paste: rejected / timed-out / missing-model / lost-placeholder output falls back to the rule-based text; a raising client does not kill the worker. Tested in Tasks 8 and 10.
3. List false positives: "I need 1 apple and 2 oranges", "one, two, or three", "3.5 million", a lone "1." are untouched; sequences must start at 1 and every item must be non-empty. Tested in Tasks 5 and 6.
4. Glossary prompt hazards: a transcript that is only the glossary text (Whisper echo on silence) is discarded; the prompt never exceeds 400 characters. Tested in Tasks 2 and 3.
5. Nothing leaves the PC: a non-loopback `ai_url` is refused before any connection; `ensure_running` never starts anything when AI is disabled. Tested in Tasks 7 and 8.

---

### Task 1: Config fields

**Files:**
- Modify: `src/flowvoice/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `Config` gains `dictionary_terms: list[str]`, `dictionary_fixes: dict[str, str]`, `snippets: dict[str, str]`, `auto_lists: bool = True`, `ai_enabled: bool = False`, `ai_model: str = "qwen3.5:2b-q4_K_M"`, `ai_min_words: int = 20`, `ai_timeout_seconds: float = 6.0`, `ai_url: str = "http://localhost:11434"`. Constants `MAX_TERMS = 200`, `MAX_FIXES = 200`, `MAX_SNIPPETS = 100`, `AI_MIN_WORDS_MIN = 5`, `AI_TIMEOUT_RANGE = (1.0, 60.0)`.

- [ ] **Step 1: Write failing tests**: defaults for every new field; round trip with non-default values; bad types (non-list terms, non-dict snippets with a non-str value, `ai_min_words="x"`, `ai_enabled="yes"`) fall back to defaults field by field; `ai_min_words=2` clamps to 5 and a float 20.7 becomes int 20; `ai_timeout_seconds=0.1` clamps to 1.0 and `999` to 60.0; more than 200 terms / 200 fixes / 100 snippets are truncated on load (first N kept); mutable defaults are not shared between instances.
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_config.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** fields, `_valid` rules and the load-time clamps/truncation.
- [ ] **Step 4: Run** the config tests and the full non-slow suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat: v3 config fields`.

### Task 2: Dictionary (pure)

**Files:**
- Create: `src/flowvoice/vocabulary.py`, `tests/test_vocabulary.py`

**Interfaces:**
- Produces: `glossary_prompt(terms: list[str], limit: int = 400) -> str | None` (`"Glossary: A, B, C."`, terms in list order, blank terms skipped, stops before exceeding `limit`, `None` when no usable terms); `apply_dictionary(text: str, terms: list[str], fixes: dict[str, str]) -> str`; `is_glossary_echo(text: str, terms: list[str]) -> bool`.

- [ ] **Step 1: Write failing tests**: prompt format, order, blank/duplicate skipping, cap (many long terms stay <= 400 chars and never cut a term in half), `None` for empty; `apply_dictionary`: term casing (`"we use tbb daily"` with term `TBB` -> `"we use TBB daily"`), whole-word only (`"tbbs"` untouched), multi-word term (`perry homes` -> `Perry Homes`), fixes (`"perry home"` -> `"Perry Homes"`), longest fix first, no chaining (fix A->B and B->C does not make A->C), case-insensitive match with exact write-as output, empty terms/fixes return the text unchanged, regex-special characters in terms (`C++`, `a.b`) are matched literally; `is_glossary_echo`: `"Glossary: TBB, Perry Homes."`, `"TBB, Perry Homes"`, `"tbb"` (exactly the terms and nothing else) are echoes, `"TBB is great"` is not, empty text is not.
- [ ] **Step 2: Run** `pytest tests/test_vocabulary.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three functions (regex with `re.escape`, lookarounds for word edges so terms ending in symbols still match).
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: personal dictionary`.

### Task 3: Whisper glossary prompt and echo guard

**Files:**
- Modify: `src/flowvoice/engine.py`, `tests/test_engine.py`

**Interfaces:**
- Consumes: Task 2 not required here.
- Produces: `Engine.transcribe(self, audio: np.ndarray, initial_prompt: str | None = None) -> str` (passes `initial_prompt` to `WhisperModel.transcribe` only when given; the CUDA-fallback retry passes it too).

- [ ] **Step 1: Write failing tests** with the existing fake model: prompt passed through exactly; not passed (no `initial_prompt` kwarg) when `None`; passed again on the CPU-fallback retry; the existing engine tests unchanged.
- [ ] **Step 2: Run** `pytest tests/test_engine.py -q -k "not slow"`. Expected: FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: engine accepts a glossary prompt`.

### Task 4: Snippets and the clean() hook

**Files:**
- Create: `src/flowvoice/snippets.py`, `tests/test_snippets.py`
- Modify: `src/flowvoice/cleanup.py`, `tests/test_cleanup.py`

**Interfaces:**
- Produces: `PLACEHOLDER_BASE = 0xE100`; `protect_snippets(text: str, snippets: dict[str, str]) -> tuple[str, dict[str, str]]` (returns text with each matched trigger replaced by its placeholder character, and a mapping placeholder -> expansion); `expand_snippets(text: str, mapping: dict[str, str]) -> str`. `cleanup.clean(..., before_commands: Callable[[str], str] | None = None)` calls the hook right after backtracking and before spoken commands.

- [ ] **Step 1: Write failing tests**: trigger matched whole-word and case-insensitively (`"send my LinkedIn please"` -> placeholder in the middle, mapping has the exact snippet text); longest trigger wins (`"my linkedin profile"` over `"my linkedin"`); touching punctuation absorbed (`"my linkedin."`, `"my linkedin,"` -> no `.`/`,` left next to the placeholder, expansion inserted verbatim: `expand_snippets` of that text equals the snippet text with nothing appended); `literal` before a trigger leaves the words and drops `literal`; multi-line and punctuation-heavy snippet text (newlines, `.`, `@`, URL) arrives unchanged after `expand_snippets`; the same snippet twice in one text gets the same placeholder; two triggers get different placeholders; the placeholder survives `clean(text, before_commands=lambda t: protect(...)[0], commands=DEFAULT_COMMANDS)` untouched (not capitalized, not merged with a neighbor, not dropped by repeat-collapse, e.g. `"my link my link"` both expand); unmatched text unchanged; empty snippets dict returns the text unchanged; `clean(..., before_commands=None)` behaves as before and an existing cleanup test still passes; the hook runs after backtracking (a snippet in a sentence deleted by "scratch that" never appears).
- [ ] **Step 2: Run** `pytest tests/test_snippets.py tests/test_cleanup.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Snippets: one regex alternation, longest first, `re.escape`, whole-word edges, absorbing `[.,;!?]` directly touching the trigger on either side. Cleanup: add the hook.
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: snippets and clean() hook`.

### Task 5: Numbered lists

**Files:**
- Create: `src/flowvoice/lists.py`, `tests/test_lists.py`

**Interfaces:**
- Produces: `format_lists(text: str) -> str` (this task: numbered and ordinal lists; Task 6 adds bullets in the same function; returns the text unchanged when no list is found or when it already has list markup: a line starting with `- ` or a digit and `.`).

- [ ] **Step 1: Write failing table-driven tests** (spec examples): `"Going to the store for 1. Apples 2. Bananas 3. Oranges"` -> `"Going to the store for:\n1. Apples\n2. Bananas\n3. Oranges"`; `"Going to the store for one, apples, two, bananas, three, oranges."` -> same; `"number one call Sam number two send the plans"` -> `"1. Call Sam\n2. Send the plans"` (no lead-in, so no colon line); `"First, wake up. Second, make coffee. Third, ship it."` -> `"1. Wake up\n2. Make coffee\n3. Ship it"`; `"Pick up 1. milk 2. eggs. Then call Sam."` -> `"Pick up:\n1. Milk\n2. Eggs\n\nThen call Sam."`; lead-in already ending in `:` gets no second colon; items strip leading/trailing commas and "and"/"then" and the terminal period; first letter of each item capitalized. Unchanged: `"I need 1 apple and 2 oranges"`, `"I want one, two, or three apples"` (empty item), `"It costs 3.5 million"`, `"1. apples"` alone, `"2. apples 3. pears"` (does not start at 1), `"1. milk 3. eggs"` (gap), text already containing `"\n- milk"` or `"\n1. milk"`, empty string.
- [ ] **Step 2: Run** `pytest tests/test_lists.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Find marker candidates with one regex (digit 1-2 digits or word one..ten, followed by `.`/`,`/`:`/`)` then whitespace or end, or preceded by "number "; reject a digit marker followed by another digit); take the longest ascending run starting at 1; items are the text between consecutive markers, each must contain at least one word; ordinals `first`..`fifth` as markers when followed by `,`/`:` or at a sentence start, starting at "first", at least 2; the last item ends at its first sentence-ending punctuation that is followed by more text, the remainder becomes a new paragraph.
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: numbered and ordinal lists`.

### Task 6: Bulleted lists

**Files:**
- Modify: `src/flowvoice/lists.py`, `tests/test_lists.py`

**Interfaces:**
- Consumes/Produces: same `format_lists(text) -> str`; bullet cues added.

- [ ] **Step 1: Write failing tests**: `"Shopping list: apples, bananas, and oranges."` -> `"Shopping list:\n- Apples\n- Bananas\n- Oranges"`; `"Please add the following milk, eggs, and bread"` -> `"Please add the following:\n- Milk\n- Eggs\n- Bread"`; each cue (`the following`, `a list of`, `list of`, `shopping list`, `to-do list`, `to do list`, `todo list`, `things to do`, `things I need`, `agenda`, `ingredients`, `items`) triggers with 3 items; `" then "` and `" and "` separate items (`"things to do: call Sam, send the plans then book the lender"`); a trailing sentence after the items becomes a new paragraph (`"Shopping list: milk, eggs, bread. Then I leave."` -> list plus `\n\nThen I leave.`); 2 items does not trigger; an item longer than 6 words cancels the list (`"the following is a long sentence with many words, b, c"` unchanged); no separators (`"things to do call Sam send the plans"`) unchanged; cue words not followed by a list (`"the agenda is clear"`) unchanged; numbered lists still work and take precedence when both apply; idempotent: `format_lists(format_lists(x)) == format_lists(x)`.
- [ ] **Step 2: Run** `pytest tests/test_lists.py -q`. Expected: FAIL on the new cases.
- [ ] **Step 3: Implement** the cue regex, item splitting, size checks.
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: cue-based bulleted lists`.

### Task 7: Ollama client

**Files:**
- Create: `src/flowvoice/ai.py`, `tests/test_ai.py`

**Interfaces:**
- Produces: `is_loopback(url: str) -> bool`; `class AiError(Exception)`; `class OllamaClient`: `__init__(self, url: str, model: str, timeout: float = 6.0)` raising `AiError` for a non-loopback URL; `chat(self, system: str, user: str, *, examples: list[tuple[str, str]] | None = None, max_tokens: int = 512) -> str` (returns the assistant text; raises `AiError` on HTTP errors, malformed JSON, timeout, empty content); `list_models(self) -> list[str]`; `is_up(self) -> bool`; `has_model(self) -> bool`; `find_ollama_exe() -> str | None` (`shutil.which("ollama")` else `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` if it exists); `ensure_running(client, *, spawn=<hidden subprocess.Popen>, sleep=time.sleep, clock=time.monotonic, exe=find_ollama_exe, wait_seconds=30.0) -> bool` (True if up already or became up; False if the exe is missing or it never came up; never raises).

- [ ] **Step 1: Write failing tests** against a throwaway `http.server` on `127.0.0.1` with a random port, run in a thread: `chat` success (request body has `model`, `stream: false`, `think: false`, `options.temperature == 0`, `keep_alive`, the messages in order system, examples as user/assistant pairs, user); HTTP 500 -> `AiError`; malformed JSON -> `AiError`; empty content -> `AiError`; server that sleeps longer than `timeout` -> `AiError` within about the timeout; `list_models` parses `/api/tags`; `is_up` true/false; `has_model` true only for an exact tag match; `OllamaClient("http://example.com:11434", ...)` and `"http://10.0.0.5:11434"` raise `AiError` before any socket is opened (assert no connection attempt via a patched `socket.create_connection`); `localhost`, `127.0.0.1`, `[::1]` accepted; `ensure_running` with injected fakes: already up -> returns True without calling `spawn`; down then up after two polls -> True and `spawn` called once with `["<exe>", "serve"]`; never up -> False after `wait_seconds` of fake clock; exe missing -> False and `spawn` not called; `spawn` raising -> False.
- [ ] **Step 2: Run** `pytest tests/test_ai.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** with `urllib.request` only; Popen with `creationflags=CREATE_NO_WINDOW`, stdout/stderr to `DEVNULL`.
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: loopback-only Ollama client`.

### Task 8: AI polish and AiService

**Files:**
- Create: `src/flowvoice/ai_polish.py`, `tests/test_ai_polish.py`

**Interfaces:**
- Consumes: `OllamaClient`, `AiError`, `ensure_running` (Task 7), `Config` (Task 1).
- Produces: `ai_acceptable(original: str, candidate: str) -> bool` (pure; rules in Global Constraints); `clean_ai_output(raw: str) -> str` (strips surrounding quotes, code fences, whitespace); `SYSTEM_PROMPT: str`, `EXAMPLES: list[tuple[str, str]]` (three few-shot pairs: a list -> bullets, a numbered sequence -> numbered list, rambling -> two short paragraphs, plus one already-fine text returned unchanged); `has_list_markup(text: str) -> bool`; `class AiService`: `__init__(self, *, client_factory=lambda cfg: OllamaClient(cfg.ai_url, cfg.ai_model, cfg.ai_timeout_seconds), ensure=ensure_running, on_status=lambda status, detail: None, start_thread=<threading.Thread wrapper>)`; attributes `status: str`, `detail: str`, `last_note: str`; `configure(self, cfg: Config) -> None` (disabled -> status `off`, nothing started; enabled and not ready, or the model/url changed -> start one background warm-up: `ensure` -> `is_up` -> `has_model` else status `missing model` with detail `ollama pull <model>` -> tiny `chat` to load the model -> `ready`; any failure -> `unavailable` with the reason; each status change calls `on_status` exactly once); `polish(self, text: str, cfg: Config) -> str | None` (None when disabled, status not ready, fewer than `ai_min_words` words, or list markup present; otherwise `chat`, `clean_ai_output`, return the result only if `ai_acceptable`; any exception or rejection returns None and sets `last_note`); `test(self, cfg: Config) -> str` (synchronous sample run; returns e.g. `"OK in 1.4 s: - apples ..."` or the failure reason; works even when disabled); `list_models(self, cfg: Config) -> list[str]` (never raises, `[]` on failure).

- [ ] **Step 1: Write failing tests** with a fake client: `ai_acceptable` table (identical text; re-bulleted text with the same words; a dropped sentence; two invented sentences; a lost or duplicated placeholder character; preamble "Sure, here is ..."; length 3x; list markers and newlines ignored in the length rule; empty candidate); `clean_ai_output` (quotes, fences); `has_list_markup`; `AiService`: disabled `configure` never calls `ensure` or the client; enable -> status sequence `warming` then `ready` (callbacks once each); model missing -> `missing model` with the pull command; `ensure` False -> `unavailable`; client raising during warm-up -> `unavailable`, the service survives; changing the model name re-warms; `polish` returns None below the word threshold, with list markup, while warming, and when `chat` raises `AiError`; returns the cleaned result when accepted; returns None and sets `last_note` when `ai_acceptable` rejects; a placeholder in the input must be present in the output; `polish` called from several threads at once does not corrupt state; `test` formats success and failure; `list_models` returns `[]` when the client raises.
- [ ] **Step 2: Run** `pytest tests/test_ai_polish.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: AI polish service with output checks`.

### Task 9: Postprocessor

**Files:**
- Create: `src/flowvoice/postprocess.py`, `tests/test_postprocess.py`

**Interfaces:**
- Consumes: `clean` + hook (Task 4), `apply_dictionary` (2), `protect_snippets`/`expand_snippets` (4), `format_lists` (5-6), `AiService` (8), `Config` (1).
- Produces: `class Postprocessor`: `__init__(self, ai: AiService | None = None)`; `process(self, text: str, cfg: Config) -> str` implementing the pipeline order exactly; AI input is the text after lists (with placeholders still in it); the snippet mapping is applied last whatever happened before; `glossary(self, cfg: Config) -> str | None` returning the capped prompt only when there are terms.

- [ ] **Step 1: Write failing tests** (fake AI object with a `polish` method): order test with a recording fake for each stage; `"my linkedin"` snippet expands verbatim after an AI that returns text keeping the placeholder; an AI that drops the placeholder is rejected by the service (simulate with the real `ai_acceptable`) and the snippet still expands; snippet protected before commands (a trigger containing "new line" is not converted); dictionary runs after clean (`"tbb"` -> `"TBB"` even at sentence start); `auto_lists=False` skips lists; `ai=None` and `ai_enabled=False` skip the AI; AI returning None leaves the rule-based text; AI raising never propagates (wrap): result is the rule-based text; whole pipeline examples: `"Going to the store for one apples two bananas three oranges"` is NOT a list (no set-off) while `"... for 1. apples 2. bananas 3. oranges"` is; `"my linkedin."` -> exactly the snippet text; `"scratch that"` after a snippet removes it; commands still work (`"hello comma new line world"` -> `"Hello,\nWorld"`).
- [ ] **Step 2: Run** `pytest tests/test_postprocess.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: postprocessor orchestrating the v3 pipeline`.

### Task 10: App integration

**Files:**
- Modify: `src/flowvoice/app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `Postprocessor` (9), `AiService` (8), `glossary_prompt`/`is_glossary_echo` (2), `Engine.transcribe(initial_prompt=)` (3).
- Produces: `App.__init__(..., ai: AiService | None = None)`; `App._clean` calls `Postprocessor(ai).process`; the transcribe callable handed to `Dictation` is `App._transcribe(audio)` which passes `glossary_prompt(config.dictionary_terms)` and returns `""` when the result `is_glossary_echo`; `App.apply_config` also calls `ai.configure(cfg)` when `ai` is set; the constructor calls `ai.configure(config)` once.

- [ ] **Step 1: Write failing tests** with fakes: the engine fake records the `initial_prompt` it receives (None with no terms, the glossary with terms, updated live after `apply_config`); a glossary-echo transcript pastes nothing; the final text is what is pasted and what history stores as `clean_text`, with the Whisper text as `raw_text`; snippet expands in the pasted text; lists format; an AI fake that raises or times out leaves the paste intact and the worker alive for the next dictation; `apply_config` calls `ai.configure` with the new config and a disabled config never leaves AI work running; the existing App tests all pass unchanged (`ai=None`).
- [ ] **Step 2: Run** `pytest tests/test_app.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** **Step 4: Run** the full non-slow suite. Expected: PASS. **Step 5: Commit** `feat: App uses the postprocessor, glossary and AI service`.

### Task 11: Settings logic for the new tables

**Files:**
- Modify: `src/flowvoice/settings_logic.py`, `tests/test_settings_logic.py`

**Interfaces:**
- Produces: `rows_to_dict(rows: list[tuple[str, str]], *, lower_keys: bool, limit: int) -> dict[str, str]` (trim, drop blank keys, unescape values with the existing `unescape_text`, later rows win, truncate to `limit`); `snippet_warnings(snippets: dict[str, str], command_phrases: dict[str, str]) -> list[str]` (messages for a trigger that equals a spoken-command phrase, a trigger shorter than 3 characters, and an empty snippet text; duplicates are impossible in a dict but rows that collapse are reported by `rows_duplicates(rows) -> list[str]`); `terms_from_text(text: str, limit: int = 200) -> list[str]` (one per line, trimmed, de-duplicated case-insensitively keeping the first spelling, order kept, blank lines dropped).

- [ ] **Step 1: Write failing tests**: each function with the cases listed above; `\n` in a snippet value round-trips through `escape_text`/`rows_to_dict`; case preserved for fixes' write-as values and for terms; `lower_keys=True` lowercases triggers and heard-as phrases only.
- [ ] **Step 2: Run** `pytest tests/test_settings_logic.py -q`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run tests.** Expected: PASS. **Step 5: Commit** `feat: settings helpers for dictionary and snippets`.

### Task 12: Settings cards (Words, Snippets, Lists and AI)

**Files:**
- Modify: `src/flowvoice/ui/settings_view.py`, `src/flowvoice/ui/main_window.py`, `src/flowvoice/ui/theme.py` (only if new styles are needed), `tests/test_settings_view.py`, `tests/test_main_window.py`, `scripts/render_previews.py`

**Interfaces:**
- Consumes: Task 11 helpers, `Config` (1), `AiService.list_models/test` shape (8) through a duck-typed `ai_probe`.
- Produces: `SettingsView.__init__(self, config, mics, on_save, ai_probe=None)`; `ai_probe` has `list_models(cfg) -> list[str]` and `test(cfg) -> str`; new widgets: Words card (`terms_edit: QPlainTextEdit`, `fixes_table: QTableWidget` with add/remove), Snippets card (`snippets_table: QTableWidget` with add/remove, a warnings label fed by `snippet_warnings`), Lists and AI card (`auto_lists_switch`, `ai_switch`, `ai_model_combo` editable and filled by a Refresh button via a worker thread and a Qt signal, `ai_min_words` spin box, `ai_status_label` updated through `set_ai_status(status: str, detail: str)` (slot, thread-safe), `test_ai_button` running `ai_probe.test` in a worker thread and showing the result in `ai_result_label`); `to_config()` / `load()` cover all new fields; `MainWindow.__init__` gains `ai_probe=None` and forwards it; `MainWindow.set_ai_status(status, detail)` forwards to the settings view.

- [ ] **Step 1: Write failing tests** (offscreen): `to_config()` reflects every new control, including a fixes row, a snippet row with a multi-line value, terms with blank lines/duplicates; `load()` repopulates them; defaults round trip (`Config()` -> view -> `to_config() == Config()`); the snippet warnings label shows the command-phrase conflict message; Refresh fills the model combo from a fake probe off the GUI thread (assert the combo updates after the signal, and the UI thread was not blocked: the fake blocks on an Event until released); `test_ai_button` shows the fake probe's result and a failure string; `set_ai_status("missing model", "ollama pull x")` shows both texts; the status label is updated from a plain thread through the slot; `ai_probe=None` disables Refresh/Test with a tooltip instead of crashing; the page still scrolls and the Save bar stays.
- [ ] **Step 2: Run** `pytest tests/test_settings_view.py tests/test_main_window.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse the command-table helpers and the existing card/switch styling.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Visual check:** extend `scripts/render_previews.py` to save `settings_words_light.png`, `settings_words_dark.png` (scrolled to the three new cards) into `.superpowers/preview/`; read them and fix until the cards look consistent with the existing Settings (rounded cards, switches, tables).
- [ ] **Step 6: Commit** `feat: settings cards for words, snippets, lists and AI`.

### Task 13: Shell and entry-point wiring

**Files:**
- Modify: `src/flowvoice/ui/bridge.py`, `src/flowvoice/ui/shell.py`, `src/flowvoice/__main__.py`, `tests/test_bridge.py`, `tests/test_shell.py`

**Interfaces:**
- Consumes: `AiService` (8), `App(ai=)` (10), `MainWindow.set_ai_status` (12).
- Produces: `QtUi.ai_status_changed = Signal(str, str)` and `QtUi.set_ai_status(status, detail)` (not part of the `Ui` protocol); `Shell` connects it to `window.set_ai_status` and passes `ai_probe` to `MainWindow` (constructor argument `ai_probe=None`); `__main__` builds one `AiService(on_status=shell.ui.set_ai_status)`, passes it to `App(..., ai=ai)` and as `ai_probe`; a one-time toast when the status becomes `unavailable` or `missing model` after the user enabled AI (not at launch with AI off); `AiService.configure` is also called when Settings saves (already covered by `App.apply_config`); quitting stops no Ollama process that the user started themselves (the app never kills Ollama).

- [ ] **Step 1: Write failing tests**: the new signal delivers from a plain thread on the main thread; `Shell` forwards status to the settings view; `ai_probe` reaches the window; toast logic as a small pure function (`should_toast(prev_status, new_status, user_enabled) -> bool`) tested table-style; existing shell/bridge tests unchanged.
- [ ] **Step 2: Run** `pytest tests/test_bridge.py tests/test_shell.py -q`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** the full non-slow suite. Expected: PASS.
- [ ] **Step 5: Smoke launch** on the real platform (`python -m flowvoice` for 20 s, alive, empty stderr, then stop it; confirm no stray Ollama process was started when AI is disabled).
- [ ] **Step 6: Commit** `feat: wire AI status and probe into the shell`.

### Task 14: Real-model probe, docs and checklist

**Files:**
- Create: `tests/test_ai_real.py` (marked `slow`, skipped unless Ollama is installed and the configured model is present)
- Modify: `README.md`, `docs/manual-test-checklist.md`

- [ ] **Step 1: Write the probe test:** with the real client against `qwen3.5:2b-q4_K_M` (skipped otherwise): warm-up reaches `ready` within 60 s; three sample dictations (a rambling grocery list, a counted sequence, an already-fine sentence) go through `AiService.polish` and each result is either `None` (rejected) or passes `ai_acceptable`; print latency per call; the test never fails on model quality, only on contract violations (exception, accepted output that fails `ai_acceptable`).
- [ ] **Step 2: Run** `pytest tests/test_ai_real.py -q -s`. Record the printed latencies and the accept/reject outcomes in the task report. If the model is missing, record the skip.
- [ ] **Step 3: README:** new sections for dictionary, snippets, lists (with the spoken examples and the "set-off number" rule), local AI (how to enable, the `ollama pull qwen3.5:2b-q4_K_M` command, warm-up status values, privacy, fallbacks). **Checklist:** add numbered-list-by-voice, bullet cue, a snippet, a dictionary term and a fix, AI enable/disable, AI status with Ollama stopped, model missing message, Test AI button.
- [ ] **Step 4: Run the full suite including slow tests** (`pytest tests -q`) and the ASCII scan; record the count.
- [ ] **Step 5: Commit** `docs: v3 README, checklist and real-model probe`.
