"""Generate tests/data/hello.wav with the Windows SAPI voice (16 kHz mono)."""
from pathlib import Path
import win32com.client

out = Path(__file__).parent / "data" / "hello.wav"
out.parent.mkdir(exist_ok=True)
stream = win32com.client.Dispatch("SAPI.SpFileStream")
fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
fmt.Type = 18  # SAFT16kHz16BitMono
stream.Format = fmt
stream.Open(str(out), 3)  # SSFMCreateForWrite
voice = win32com.client.Dispatch("SAPI.SpVoice")
voice.AudioOutputStream = stream
voice.Speak("hello world this is a test")
stream.Close()
print(out, out.stat().st_size)
