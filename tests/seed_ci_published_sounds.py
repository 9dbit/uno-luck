"""Create local-only published audio fixtures for browser CI.
Never call a live Sound Cloud API. Files are placed solely in the
ephemeral UNO_SOUND_STORAGE_DIR chosen by the GitHub Actions runner.
"""
import json
import math
import os
import struct
import wave
from pathlib import Path

root=Path(os.environ["UNO_SOUND_STORAGE_DIR"]).resolve()
if not str(root).startswith("/tmp/uno-sound-ci-"):
    raise SystemExit("Refusing to seed any non-CI or persistent audio folder")
(root/"audio").mkdir(parents=True,exist_ok=True)

def cue(name,duration,tone,settings):
    revision="1"*24 if name=="soft-tech-splash-screen" else "2"*24
    filename=f"{name}-{revision}.wav"
    with wave.open(str(root/"audio"/filename),"wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        samples=(struct.pack("<h",int(4300*math.sin(2*math.pi*tone*i/16000))) for i in range(int(duration*16000)))
        handle.writeframes(b"".join(samples))
    return {"source":"custom","storageName":filename,"fileName":filename,
            "contentType":"audio/wav","revision":revision,
            "fileDuration":duration,**settings}

catalog={
 "soft-tech-splash-screen":cue("soft-tech-splash-screen",3.0,330,
    {"start":0,"stop":2.5,"fadeIn":0,"fadeOut":1.0,"repeat":True}),
 "background-music":cue("background-music",4.0,220,
    {"start":0.5,"stop":3.5,"fadeIn":0,"fadeOut":0,"repeat":True,
     "mirror":False,"mirrorCrossfadeMs":140}),
}
(root/"manifest.json").write_text(json.dumps({
 "revision":"ci-fixture-initial","cues":catalog,
 "mixer":{"master":0.9,"music":0.22,"sfx":0.85}
}),encoding="utf-8")
print("CI fixture: 2 local cues; no Sound Cloud requests")
