# Flow Voice v2 manual test checklist

Run `run.bat`, wait for the speech model to load, and check each item. Mark pass or fail.

## Hands-free and the pill
1. [ ] **Double-tap latch.** Click into Notepad. Double-tap Right Ctrl quickly, say "testing one two three", then stay quiet. Expected: recording latches on (pill red); after about 4 seconds of silence it stops and the text is pasted into Notepad.
2. [ ] **Single tap does nothing.** Tap Right Ctrl once, briefly. Expected: nothing records, nothing is pasted, the pill stays grey.
3. [ ] **Hold to talk.** Hold Right Ctrl, say "hold test", release. Expected: text pasted; it does not stop on silence while you hold.
4. [ ] **Pill click.** Click the pill, speak, click it again. Expected: starts then stops; text pasted.
5. [ ] **Pill look and focus.** While recording, the pill is red with a moving waveform; while transcribing it is amber with animated dots. Check the paste lands correctly, and the pill never takes focus (the caret stays in the target), in each of: Notepad, a text box in a browser, Word.
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
21. [ ] A new dictation appears at the top of History without reopening the page, and Home shows it under Last transcription.
22. [ ] History off: Settings -> Dictation -> turn Save history off, Save. Dictate. Expected: text still pastes; History shows no new entry and says it is off. Turn it back on afterwards.

## Settings
23. [ ] Live change: edit a phrase in the command table (for example change "comma" output) or the spoken-commands switch, Save. Expected: "Saved"; the app does not restart; the new behavior applies on the next dictation.
24. [ ] Restart change: change the push-to-talk key (click the field, press new keys), Save. Expected: the app restarts and the new key works; the old one no longer does.
25. [ ] Hotkey capture does not dictate: click the hotkey field and press Right Ctrl and other keys. Expected: no recording starts while capturing; dictation works again afterwards.
26. [ ] UI size: drag Interface size to the maximum, then back. Expected: the window text and controls and the pill scale (range 0.8 to 1.6).
27. [ ] Always show the pill off: Expected: the pill hides while idle and appears while recording.
28. [ ] Hands-free off: turn Double-tap off, Save. Expected: double-tap no longer latches (hold to talk still works). Turn it back on.
29. [ ] Reset phrases to defaults restores the built-in lists and command table.

## Window and tray
30. [ ] Close the window with the X. Expected: it hides; the pill and tray icon remain and dictation still works.
31. [ ] Tray menu shows Open, Start dictation (Stop dictation while recording) and Quit. Start dictation records; Open shows the window.
32. [ ] Quit from the tray. Expected: the tray icon and pill disappear and the process exits (no Flow Voice in Task Manager).
33. [ ] Read aloud: select text in Notepad, press Ctrl+Alt+S. Expected: it speaks; pressing again stops.
