# Flow Voice manual test checklist

Run `run.bat`, wait for the speech model to load, and check each item. Mark pass or fail.

## Hands-free and the pill
1. [ ] **Double-tap latch.** Click into Notepad. Double-tap Right Ctrl quickly, say "testing one two three", then stay quiet. Expected: recording latches on (pill blue); after about 4 seconds of silence it stops and the text is pasted into Notepad.
2. [ ] **Single tap does nothing.** Tap Right Ctrl once, briefly. Expected: the pill briefly shows blue and then returns to grey; nothing is pasted.
3. [ ] **Hold to talk.** Hold Right Ctrl, say "hold test", release. Expected: text pasted; it does not stop on silence while you hold.
4. [ ] **Pill click.** Click the pill, speak, click it again. Expected: starts then stops; text pasted.
5. [ ] **Pill look and focus.** While recording, the pill is blue with a moving waveform; while transcribing it is amber with animated dots. Check the paste lands correctly, and the pill never takes focus (the caret stays in the target), in each of: Notepad, a text box in a browser, Word.
6. [ ] **No speech first.** Latch recording with a double-tap and say nothing. Expected: it does not stop on silence before speech is heard; press Right Ctrl once to stop; nothing is pasted.
7. [ ] **Esc cancels.** Start a hands-free take, speak, press Esc. Expected: recording ends and nothing is pasted. Also hold Right Ctrl, press another key (for example A): the take is cancelled.

## Spoken commands
8. [ ] Say "hello comma new paragraph how are you question mark". Expected: `Hello,` then a blank line, then `How are you?`.
9. [ ] Say "the time period is long". Expected: stays as words, no period symbol.
10. [ ] Say "john at sign gmail dot com". Expected: `john@gmail.com` with no spaces.
11. [ ] Say "a dash of salt". Expected: stays as words.
12. [ ] Say "literal comma". Expected: the word "comma" is typed (capitalized as "Comma" at the start of a sentence), not a comma symbol.
13. [ ] Say "all caps hello end caps world". Expected: `HELLO world`.

## Backtracking
14. [ ] Say "this is the first sentence. This is wrong scratch that. This is right". Expected: the wrong sentence and "scratch that" are removed.
15. [ ] Say "I will call you today. I will see you tomorrow excuse me". Expected: only "I will call you today." remains.

## History
16. [ ] Open the window (tray icon double-click, or tray menu Open). Go to History. Expected: your earlier dictations are listed newest first, with time and app name.
17. [ ] Search: type part of a dictation in the search box. Expected: the list filters; clearing the box restores it; a nonsense query shows "No matches".
18. [ ] Copy: select an entry, click Copy, paste into Notepad. Expected: the entry text.
19. [ ] Delete: select an entry, click Delete. Expected: it disappears.
20. [ ] Clear all: click it, confirm. Expected: a confirmation prompt, then the list is empty.
21. [ ] A new dictation appears at the top of History without reopening the page, and Home shows it under Last transcription. (If History shows an orange "Saving is off" bar, new dictations only reach Home: click Turn on, or switch Save history on in Settings, then dictate again.)
22. [ ] History off: Settings -> Dictation -> turn Save history off, Save. Dictate. Expected: text still pastes; saving stops: existing entries stay listed, no new rows appear, and the History page shows an orange "Saving is off" bar. Click its Turn on button: the bar disappears and the Settings switch is on again.

## Settings
23. [ ] Live change: edit a phrase in the command table (for example change "comma" output) or the spoken-commands switch, Save. Expected: "Saved"; the app does not restart; the new behavior applies on the next dictation.
24. [ ] Restart change: change the push-to-talk key (click the field, press new keys), Save. Expected: the app restarts and the new key works; the old one no longer does. Left and right modifier keys are captured separately: pressing Right Ctrl shows "Right Ctrl" and only the right key dictates; pressing the left one shows "Left Ctrl".
25. [ ] Hotkey capture does not dictate: click the hotkey field and press Right Ctrl and other keys. Expected: no recording starts while capturing; dictation works again afterwards.
26. [ ] UI size: drag Interface size to the maximum and press Save, then drag it back and press Save. Expected: the size changes only after Save; the window text and controls and the pill scale (range 0.8 to 1.6).
27. [ ] Always show the pill off: Expected: the pill hides while idle and appears while recording.
28. [ ] Hands-free off: turn Double-tap off, Save. Expected: double-tap no longer latches (hold to talk still works). Turn it back on.
29. [ ] Reset phrases to defaults restores the built-in lists and command table.

## Window and tray
30. [ ] Close the window with the X. Expected: it hides; the pill and tray icon remain and dictation still works.
31. [ ] Tray menu shows Open, Start dictation (Stop dictation while recording) and Quit. Start dictation records; Open shows the window.
32. [ ] Quit from the tray. Expected: the tray icon and pill disappear and the process exits (no Flow Voice in Task Manager).
33. [ ] Read aloud: select text in Notepad, press Ctrl+Alt+S. Expected: it speaks; pressing again stops. With nothing selected you get a "Read aloud: select some text first" notice, and if the speech engine fails you get a "Read aloud failed: ..." notice instead of silence.

## Dictionary, snippets, lists and AI
Settings pages: Words, Snippets, Lists and AI. Use Notepad as the target.

34. [ ] **Numbered list by digits.** Say "to reset it, one, unplug it, two, wait thirty seconds, three, plug it back in". Expected: a lead-in line ending in a colon, then `1.` `2.` `3.` lines, each starting with a capital and with no stray commas.
35. [ ] **Numbered list by words.** Say "first, open the lid. Second, press the button. Third, close the lid". Expected: a numbered list of three lines. Also say "number one call Sam number two send the file": two numbered lines.
36. [ ] **Bullet cue.** Say "shopping list: milk, eggs and bread". Expected: `Shopping list:` then `- Milk`, `- Eggs`, `- Bread`. Then say "Shopping list, milk, eggs and bread" (no colon): same result.
37. [ ] **No false list.** Say "I need 1 apple and 2 oranges" and "is it one, two, or three". Expected: both pasted as plain sentences. Turn **Automatic lists** off in Settings, Save, and repeat item 34: it is now plain text. Turn it back on.
38. [ ] **Dictionary term.** Settings > Words: add `Perry Homes` to Dictionary, Save. Say "I work at perry homes". Expected: `Perry Homes` with that casing. (Whisper may also hear it better.)
39. [ ] **Correction.** Add a Corrections row (Heard as `flow voyce`, Write as `Flow Voice`), Save. Say "open flow voyce". Expected: `Flow Voice`. Whole words only: a longer word containing the text is not changed.
40. [ ] **Snippet verbatim.** Settings > Snippets: add trigger `my address`, text `123 Main St\nAustin, TX 78701` (no final period), Save. Say "send it to my address". Expected: the two address lines exactly as typed, with no period added after `78701` and no capitalization changes. Also say "my address." as the last words (Whisper usually adds a dot): still no extra period. Then say "here is my address. call me tomorrow": the address, then a period and "Call me tomorrow" with a capital C.
41. [ ] **Snippet literal escape.** Say "literal my address". Expected: the words `my address` are typed, not the snippet.
42. [ ] **Settings warnings.** Add a snippet whose trigger is `new line`: a warning says it is also a spoken command. Add a trigger `ab`: a warning about 3 characters. Add a row with text but a blank trigger: a warning that it will be ignored. Paste 201 distinct lines into Dictionary or 101 snippet rows: a warning says only the first 200 (or 100) are used. Remove them or close without saving.
43. [ ] **AI enable (Ollama running).** Run `ollama pull qwen3.5:2b-q4_K_M` once, start Ollama, then Settings > Lists and AI: switch AI polish on, Save. Expected: the status goes from "AI: warming up..." to "AI: ready" within about a minute.
44. [ ] **AI polish.** With AI ready, dictate a rambling 40-word note with a quantity, a date, a time, a name and a "not" (for example "okay so for Saturday I need to get two gallons of milk and a dozen eggs and we are not buying bread, call Priya at 3:30 on October 14 about the order"). Expected: pasted within a few seconds, possibly split into paragraphs or lines; every number, the date, the time, the name and "not" are exactly as spoken and no word was added or reworded. A dictation under 20 words is pasted without any AI change.
45. [ ] **Test AI.** Press **Test AI**. Expected: a result line starting "OK in" with a time in seconds (about 1 to 3 s when warm) and the formatted sample.
46. [ ] **AI with Ollama stopped.** Stop Ollama (quit it from the tray), then in Settings turn AI polish off, Save, turn it on, Save. Expected: status goes warming then ready because Flow Voice starts Ollama again (it can start Ollama only on its default address, http://localhost:11434; with a custom ai_url you must start Ollama yourself). To see the unavailable state (Ollama must be running for this step so Flow Voice does not start a second server), set "ai_url" in config.json to an unused port (for example http://localhost:11999) and restart Flow Voice: status shows unavailable (after about 30 seconds) with one notice and dictation still pastes the normal text; pressing Test AI says "Ollama is not running". Restore the URL afterwards.
47. [ ] **Model missing.** Type a model name that is not installed (for example `nosuchmodel:1b`) in AI model, Save. Expected: the status says the model is not installed and shows `ollama pull nosuchmodel:1b`; dictation still pastes normal text. Set the model back to `qwen3.5:2b-q4_K_M`.
48. [ ] **Quit leaves Ollama alone.** With AI ready, quit Flow Voice from the tray. Expected: Ollama keeps running (check its tray icon or Task Manager).
49. [ ] **Disable AI.** Switch AI polish off, Save. Expected: the status shows "AI: off" and dictation pastes the normal text with no delay.
