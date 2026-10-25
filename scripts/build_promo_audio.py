#!/usr/bin/env python3
"""Build reproducible local promotional AUDIO assets, not Sound Cloud presets.

The first WAV contains a low cinematic explosion, sustained "Free Spiinnn!"
speech from the offline espeak voice and a victory chord. The second is a
full-length tadaa for Turbo Auto, with no dependence on remote TTS or gesture-
restricted speechSynthesis. These are only visual/promo cues: no RNG effect.
"""
from __future__ import annotations

import argparse
import math
import random
import shutil
import struct
import subprocess
import wave
from pathlib import Path

RATE=22050
TAU=2*math.pi


def tts() -> list[float]:
    exe=shutil.which("espeak")
    if not exe:
        raise SystemExit("espeak required to produce real spoken Free Spiinnn audio")
    data=subprocess.check_output(
        [exe,"-v","en-us+f4","-s","138","-p","84","-a","200",
         "--stdout","Free Spiinnn!"],timeout=20)
    # espeak streaming WAV uses an open-ended data size; use the PCM payload.
    if data[:4]!=b"RIFF" or data[8:12]!=b"WAVE":
        raise SystemExit("Unexpected espeak WAV header")
    found=data.find(b"data")
    if found<0 or found+8>=len(data):
        raise SystemExit("espeak output has no PCM chunk")
    pcm=data[found+8:]
    if len(pcm)%2:pcm=pcm[:-1]
    return [sample/32768 for (sample,) in struct.iter_unpack("<h",pcm)]


def synth(path: Path, *, voice: bool):
    length=3.75 if voice else 2.85
    n=int(length*RATE)
    samples=[0.0]*n
    rng=random.Random(20261024)
    speech=tts() if voice else []
    voice_start=int(.62*RATE)
    for i in range(n):
        t=i/RATE
        if voice:
            # Deep explosion, with a quick low-pass-feeling decay.
            if t<1.28:
                decay=math.exp(-3.9*t)
                freq=170*math.exp(-2.4*t)+43
                boom=(math.sin(TAU*freq*t)*.26+rng.uniform(-1,1)*.15)*decay
                samples[i]+=boom
            vi=i-voice_start
            if 0<=vi<len(speech):
                samples[i]+=speech[vi]*.88
            echo=vi-int(.16*RATE)
            if 0<=echo<len(speech):
                samples[i]+=speech[echo]*.19
        # Sustained colorful fanfare with a long controlled tail.
        music_start=.2 if voice else .05
        local=t-music_start
        if local>=0:
            base=[392.0,493.88,587.33,783.99] if voice else [523.25,659.25,783.99,1046.5]
            for k,hz in enumerate(base):
                offset=k*(.16 if voice else .2)
                x=local-offset
                if x<0:continue
                attack=min(1,x/.055)
                decay=min(1,max(0,(length-.24-t)/.63))
                envelope=attack*decay
                if voice and voice_start/RATE<=t<voice_start/RATE+len(speech)/RATE:
                    envelope*=.23
                elif voice:envelope*=.46
                else:envelope*=.8
                samples[i]+=math.sin(TAU*hz*x)*envelope*(.12 if voice else .15)
        # Gentle sparkling shimmer, low enough not to mask speech.
        if t>2.3 and voice:
            tail=(length-t)/max(.01,length-2.3)
            samples[i]+=math.sin(TAU*1318.5*t)*.042*max(0,tail)
    gain=.88/max(1, max(abs(x) for x in samples))
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h",int(max(-1,min(1,x*gain))*32767)) for x in samples))
    print(f"Audio built: {path}, {length:.2f}s, {path.stat().st_size} bytes")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    audio=args.root/"audio"
    synth(audio/"free-spin-gift.wav",voice=True)
    synth(audio/"auto-tadaa.wav",voice=False)


if __name__=="__main__":
    main()
