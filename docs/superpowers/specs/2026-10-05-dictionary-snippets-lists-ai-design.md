# Flow Voice v3: Dictionary, Snippets, Lists, Local AI Polish - Design

Date: 2026-10-05. Builds on the v1 and v2 specs (shipped on branch `build`).

## Goal
Make dictated text come out cleaner and more personal, entirely on this PC:
- a **personal dictionary** (names, jargon, acronyms) that Whisper hears correctly and the app spells correctly;
- **snippets**: say a trigger phrase ("my LinkedIn") and a full text or link is inserted;
- **numbered and bulleted lists** formatted automatically from speech;
- an optional **local AI polish** (Ollama) that restructures longer, rambling dictation into bullets or short paragraphs.

## User decisions and rulings
- Scope is dictionary + snippets + lists + local AI. Not in this spec: context-aware tone, command mode (highlight and rewrite), cloud models.
- AI polish is **off by default**, enabled in Settings; it applies only to dictations of at least **20 words** (adjustable). Ollama is started by the app only when AI is enabled.
- Default model is **`qwen3.5:2b-q4_K_M`** (1.9 GB; the user pulls it themselves with `ollama pull qwen3.5:2b-q4_K_M`). It fits the free video memory on this PC (GTX 1660 Ti, 6 GB, about 2.9 GB free in normal use). The model is a Settings choice (any model Ollama has). The app never downloads models itself and never silently falls back to a different model: if the chosen model is not installed, the AI status says so and shows the pull command.
- Nothing leaves the PC: the AI client talks only to a loopback address.

## What the probes on this PC showed (they shape the design)
- `faster-whisper` 1.2.1 supports `initial_prompt` and `hotwords`.
- Ollama 0.35.1 + `qwen3.5:0.8b` answers over `http://localhost:11434/api/chat`. First call after the server was down took **28 s** (server start + model load); warm calls take **0.2 s**. So the model must be warmed up in the background, never on a dictation.
- With a bare instruction, the 0.8B model returned a **single** bullet and did not split the items. So rule-based lists are the primary mechanism and the AI polish is a bonus that needs few-shot examples and strict output checking. The chosen default is the 2B `qwen3.5` (same family and settings as the 0.8B that was probed); `llama3.2:3b` is an alternative the user can select. Quality of the 2B on real dictation is to be confirmed with the Test AI button and the scripted probe.

## Text pipeline (new order; the existing steps keep their behavior)
```
Whisper (with a glossary prompt from the dictionary)
 -> backtracking                         (existing)
 -> snippet placeholders                 (new: trigger phrase -> one private-use character)
 -> spoken commands                      (existing)
 -> fillers, repeats, whitespace, caps   (existing clean())
 -> dictionary: casing + "heard as" fixes (new)
 -> list formatting                      (new, rules)
 -> AI polish                            (new, optional)
 -> snippet expansion                    (new: placeholders -> verbatim text)
 -> paste
```
A new `postprocess.py` orchestrates the new steps around `clean()`; `App._clean` calls it with the live config. `cleanup.clean`, `commands` and the Whisper engine keep their current interfaces except `Engine.transcribe` gains an optional `initial_prompt`.

## 1. Personal dictionary
- **Terms** (one per line, max 200): names, jargon, acronyms, written exactly as you want them ("TBB", "Perry Homes", "Seiren").
  - They are sent to Whisper as `initial_prompt = "Glossary: a, b, c."` (capped at 400 characters, in list order) so it hears them correctly.
  - After transcription, any whole-word, case-insensitive occurrence of a term is rewritten to the term's exact casing ("tbb" -> "TBB").
- **Fixes** (table "heard as" -> "write as", max 200): for mishearings that repeat ("perry home" -> "Perry Homes"). Whole-phrase, case-insensitive, longest first, applied once (no chaining), output exactly as typed.
- Guard: if the transcript is nothing but the glossary text (Whisper sometimes echoes its prompt on silence), it is discarded as empty.

## 2. Snippets
- A table trigger phrase -> text (max 100). The text may be multi-line (shown escaped as `\n` in Settings like the command table) and is inserted **verbatim**: no capitalization, spacing, or cleanup changes.
- Matching: whole-word, case-insensitive, longest first. Punctuation Whisper puts touching the trigger is absorbed, so "my linkedin." inserts the link without a trailing period. "Literal" before a trigger types the words instead.
- Implementation: the trigger is replaced right after backtracking by a single private-use character (`chr(0xE100 + index)`), which no later step treats as a word, and expanded at the very end. If a later step (the AI) loses a placeholder, the AI result is rejected and the rule-based text is used.
- Snippet text is never re-scanned (no recursion). A trigger that is also a spoken-command phrase is shown with a warning in Settings; the snippet wins.

## 3. Rule-based lists (setting `auto_lists`, default on)
Runs on the cleaned text; skipped if the text already has list markup (a line starting with `- ` or `1.`).
- **Numbered:** markers 1, 2, 3, ... (digits or spoken "one, two, three") in order, starting at 1, at least 2. A marker counts only when set off: digit or word followed by `.` `,` `:` `)`, or preceded by "number" ("number one ..."). "I need 1 apple and 2 oranges" stays untouched. Ordinals ("first, second, third") also make a numbered list (at least 2, starting with "first").
- **Output:** the lead-in text before the first marker, with a colon added if it has none, then one item per line `1. Item`. Items: trimmed, leading/trailing commas and "and"/"then" removed, terminal period removed, first letter capitalized. If the last item ends a sentence and more text follows, that text becomes a new paragraph after the list.
- **Bulleted:** a list cue followed by at least 3 items separated by commas / "and" / "then", each at most 6 words. Cues: "the following", "a list of", "list of", "shopping list", "to-do list" / "to do list" / "todo list", "things to do", "things I need", "agenda", "ingredients", "items". Output `- Item` lines under the lead-in with a colon. Without commas or "and" there is no reliable split, so the text is left alone.
- Examples that become tests:
  - `Going to the store for 1. Apples 2. Bananas 3. Oranges` -> `Going to the store for:\n1. Apples\n2. Bananas\n3. Oranges`
  - `Going to the store for one, apples, two, bananas, three, oranges.` -> same result
  - `number one call Sam number two send the plans` -> `1. Call Sam\n2. Send the plans`
  - `First, wake up. Second, make coffee. Third, ship it.` -> `1. Wake up\n2. Make coffee\n3. Ship it`
  - `Shopping list: apples, bananas, and oranges.` -> `Shopping list:\n- Apples\n- Bananas\n- Oranges`
  - `Please add the following milk, eggs, and bread` -> `Please add the following:\n- Milk\n- Eggs\n- Bread`
  - `Pick up 1. milk 2. eggs. Then call Sam.` -> `Pick up:\n1. Milk\n2. Eggs\n\nThen call Sam.`
  - Unchanged: `I need 1 apple and 2 oranges`; a single marker `1. apples`; `things to do call Sam send the plans` (no separators).

## 4. Local AI polish (setting `ai_enabled`, default off)
- **Client** (`ai.py`, stdlib `urllib`, no new dependencies): `OllamaClient(url, model, timeout)` with `chat(system, user)` (`/api/chat`, `stream=false`, `think=false`, temperature 0, output capped, `keep_alive` 30 min), `list_models()` (`/api/tags`), `ensure_running()`. The URL must be loopback (`localhost`, `127.0.0.1`, `::1`); anything else is refused.
- **Start-up and warm-up:** when AI is enabled (at launch or when switched on), a background thread starts `ollama serve` hidden if it is not running (exe from `PATH` or `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`), waits up to 30 s, then loads the model with a tiny request. Status is `off | warming | ready | missing model | unavailable`, shown in Settings; one toast on failure ("AI polish unavailable: ..."). Dictations never wait for warm-up: while the status is not `ready`, polish is skipped.
- **When it runs:** status `ready`, at least `ai_min_words` words (default 20), no list markup already present. Runs on the dictation worker thread, so the pill shows "processing"; the call has a timeout (`ai_timeout_seconds`, default 6) and any failure falls back to the rule-based text.
- **Prompt:** a system prompt (restructure only: bullets if the speaker lists items, numbered if they counted, otherwise short paragraphs; keep every word's meaning; never add facts or answer questions; keep private-use placeholder characters exactly; output only the text) plus three few-shot examples (list, paragraphs, already fine -> unchanged).
- **Output check** (`ai_acceptable(original, candidate) -> bool`, pure): at least 85% of the original's words appear in the result; at most 15% of the result's words are new; length between 0.7x and 1.5x ignoring list markers and newlines; every placeholder character present exactly as often as before; no preamble ("Sure", "Here is", ...); surrounding quotes and code fences are stripped first. Failing the check means the rule-based text is used and a short note is kept for the Settings "Test AI" panel.
- **History** stores the raw Whisper text and the final text (after the AI and snippet expansion).

## 5. Settings and config
- New Settings cards: **Words** (terms editor, fixes table), **Snippets** (table), **Lists and AI** (auto-lists switch; AI switch, model dropdown listing installed Ollama models with a Refresh button, minimum-words spinner, status line, "Test AI" button that sends a sample and shows the result and latency). All apply live; none needs a restart.
- `Config` gains: `dictionary_terms: list[str]`, `dictionary_fixes: dict[str, str]`, `snippets: dict[str, str]`, `auto_lists: bool = True`, `ai_enabled: bool = False`, `ai_model: str = "qwen3.5:2b-q4_K_M"`, `ai_min_words: int = 20`, `ai_timeout_seconds: float = 6.0`, `ai_url: str = "http://localhost:11434"` (config file only). Loading validates each field and falls back to its default.

## Non-goals
Tone adaptation, command mode, cloud LLMs, streaming output, per-app dictionaries, snippet variables (date, clipboard), importing/exporting the dictionary, other languages, automatically downloading models.

## Testing
- Pure tests, table-driven: every list example above and the unchanged cases; dictionary casing and fixes; snippet placeholder survives `clean()`, expands verbatim, absorbs touching punctuation, `literal` escape; whole-pipeline order tests; `ai_acceptable` cases (dropped words, invented words, lost placeholder, preamble, fences, length).
- `OllamaClient` against a throwaway local HTTP server on a random loopback port: success, HTTP 500, malformed JSON, timeout, non-loopback URL refused; `ensure_running` with injected probe / spawn / sleep (already up, starts and becomes ready, never becomes ready, exe missing).
- App integration with a fake AI: disabled, below the word threshold, status not ready, timeout fallback, rejected output fallback, placeholders preserved; history stores raw and final text.
- `Engine.transcribe(initial_prompt=...)` passes the prompt through (fake model); prompt-echo guard.
- Settings round trips and live apply. One scripted probe against the real Ollama (skipped when it is not installed).
- Manual checklist additions: numbered list by voice, bullet cue, a snippet, a dictionary term and fix, AI on/off, Ollama auto-start, behavior with Ollama missing.

## Success criteria
Saying "Going to the store for one apples two bananas three oranges" pastes a numbered list. A snippet trigger inserts its exact text. A dictionary term is spelled as typed. With AI enabled and the model ready, a rambling 40-word dictation can come back as bullets or paragraphs in about a second or two; with Ollama off or the model slow, the app silently falls back to the normal text and never delays a paste by more than the timeout.

## Risks
- The default 0.8B model is weak: it can ignore structure or drop words. The output check protects the text; quality improves with a larger model.
- Cold start is about 28 s; warm-up must finish before polish is used, and the user is told if it fails.
- List detection can misfire on ordinary speech with set-off numbers; the rules require order, a start at 1, and set-off markers, and `auto_lists` can be turned off.
- `initial_prompt` can bias Whisper toward the listed terms in unrelated speech; the list is capped and editable.
- Snippet triggers can fire by accident if they are common phrases; Settings warns about duplicates and command phrases.
