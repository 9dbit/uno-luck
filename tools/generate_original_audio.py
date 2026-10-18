"""Synthesize original UNO LUCK game audio from oscillators and filtered noise.
No third-party songs or copyrighted sound samples. Output peak constrained to -1.5 dBFS.
"""
from pathlib import Path
import numpy as np, math, subprocess, wave
from scipy.signal import butter,sosfilt
SR=32000
ROOT=Path(__file__).resolve().parents[1] / 'app' / 'static' / 'audio';ROOT.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(241018)

def field(sec): return np.zeros(int(SR*sec),dtype=np.float32)
def add(out,start,duration,freq,vol=.18,kind='brass',to=None,pan=0.0):
 n=min(int(duration*SR),len(out)-int(start*SR)); i=int(start*SR)
 if n<2:return
 t=np.arange(n,dtype=np.float64)/SR
 if to is None:to=freq
 phase=2*np.pi*(freq*t+(.5*(to-freq)/max(duration,.001))*t*t)
 if kind=='brass': sig=np.sin(phase)+.42*np.sin(2*phase)+.21*np.sin(3*phase)+.07*np.sin(4*phase)
 elif kind=='bell':sig=np.sin(phase)+.34*np.sin(phase*2.04)+.13*np.sin(phase*3.93)
 elif kind=='bass':sig=np.sin(phase)+.44*np.sin(phase*2)+.12*np.sin(phase*3)
 elif kind=='arcade':sig=np.sin(phase)+.15*np.sin(phase*5)+.20*np.sin(phase*2)
 else:sig=np.sin(phase)
 attack=max(1,int(SR*(.008 if kind!='bell' else .002)))
 release=max(5,int(SR*min(duration*.38,.22)))
 env=np.ones(n,dtype=np.float64)
 env[:attack]=np.linspace(0,1,attack)
 env*=np.exp(-np.arange(n)/(SR*max(.05,duration*.73)))
 env[-release:]*=np.linspace(1,0,release)
 out[i:i+n]+=(sig*env*vol).astype(np.float32)

def shhhh(out,start,duration,vol=.10,hp=900):
 n=min(int(duration*SR),len(out)-int(start*SR));i=int(start*SR)
 if n<10:return
 sig=rng.standard_normal(n).astype(np.float64)
 sos=butter(2,hp,fs=SR,btype='highpass',output='sos')
 sig=sosfilt(sos,sig)
 env=np.exp(-np.arange(n)/(SR*max(.015,duration*.4)))*np.linspace(1,.3,n)
 out[i:i+n]+(sig*env*vol).astype(np.float32)

def thump(out,t,vol=.25):
 add(out,t,.42,105,vol,'bass',to=46)
 add(out,t+.005,.11,190,vol*.15,'bell',to=110)
 shhhh(out,t,.12,vol*.32,600)

def jingle(out,t,n=6,vol=.12):
 seq=[1318,1661,2093,2637,2093,3136,2637,3520]
 for i in range(n):add(out,t+i*.083,.20,seq[i%len(seq)],vol*(.95-i*.045),'bell')

def stinger(rank):
 durations={1:5.5,2:4.65,3:3.7,4:2.85,5:1.8}
 out=field(durations[rank]); thump(out,.02,.34 if rank==1 else .25)
 notes={1:[261.63,329.63,392,523.25,659.25,783.99,1046.5],2:[293.66,369.99,440,587.33,739.99,880],3:[329.63,392,493.88,659.25,783.99],4:[392,493.88,587.33,783.99],5:[523.25,659.25,783.99,1046.5]}
 tempo={1:.32,2:.27,3:.22,4:.18,5:.16}[rank]
 for i,f in enumerate(notes[rank]):
  tm=.26+i*tempo
  add(out,tm,.56,f,.18 if rank<3 else .14,'brass')
  add(out,tm+.015,.5,f*2,.07,'bell')
  if rank<=3 and i%2==0:add(out,tm,.55,f/2,.09,'bass')
 for t in np.arange(.22,durations[rank]-.16,.72 if rank<3 else 1.02):
  if rank<4:thump(out,float(t),.13 if rank>1 else .19)
 shhhh(out,.14,min(1.5,durations[rank]-.14),.14 if rank<3 else .095,550)
 jingle(out,durations[rank]*.59,8 if rank<=2 else 6,.12 if rank<=2 else .09)
 if rank==1:
  add(out,.08,2.1,79,.19,'bass',to=55)
  add(out,.21,1.55,210,.12,'brass',to=135)
  # Secondary low roar uses band-limited turbulence with resonant harmonics.
  shhhh(out,.15,1.5,.15,260)
  add(out,3.6,1.0,523,.15,'brass',to=784)
  thump(out,3.55,.30)
 elif rank==2:
  add(out,.08,1.45,155,.16,'bass',to=95)
  thump(out,2.8,.18)
 elif rank==3:
  add(out,.26,1.1,700,.10,'arcade',to=1480)
 elif rank==4:
  add(out,.4,.4,988,.09,'bell')
 return out

def gen_spin():
 x=field(.43);thump(x,.006,.25);add(x,.04,.19,310,.11,'arcade',to=880);jingle(x,.18,2,.08);return x

def gen_step():
 x=field(.11);shhhh(x,0,.065,.05,1800);add(x,0,.09,1300,.115,'bell',to=980);return x

def gen_music():
 BPM=132; beat=60/BPM; bars=8; sec=beat*4*bars;x=field(sec)
 # Gentle signature soundtrack in D minor, loop-safe release.
 bass=[146.83,110,130.81,98,146.83,123.47,110,130.81]
 chord=[[293.66,349.23,440],[220,261.63,329.63],[261.63,329.63,392],[196,246.94,293.66]]
 lead=[587.33,659.25,698.46,880,783.99,698.46,659.25,587.33,523.25,587.33,698.46,783.99,880,783.99,659.25,587.33]
 for bar in range(bars):
  st=bar*4*beat; add(x,st,beat*1.9,bass[bar],.065,'bass')
  for f in chord[bar%4]:add(x,st,.8*beat,f,.017,'bell')
  for b in range(4):
   tm=st+b*beat
   if b%2==0:add(x,tm,.13,98,.07,'bass',to=64)
   if b in (1,3):shhhh(x,tm,.11,.025,4000)
   for sub in range(2):
    if (bar+b+sub)%3!=0:
     note=lead[(bar*8+b*2+sub)%len(lead)]
     add(x,tm+sub*beat/2,.20,note,.034,'bell')
 return x

def output(name,arr,kbps=128):
 # soft-clip and normalize peak <= -1.8dBFS, preserving dynamics
 arr=np.tanh(arr*1.15).astype(np.float32)
 pk=max(1e-5,float(np.max(np.abs(arr))))
 arr=np.clip(arr*(0.81/pk),-.83,.83)
 pcm=(arr*32767).astype('<i2').tobytes()
 wav=ROOT/(name+'.wav')
 with wave.open(str(wav),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(pcm)
 mp3=ROOT/(name+'.mp3')
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-codec:a','libmp3lame','-b:a',f'{kbps}k','-ar','32000',str(mp3)],check=True)
 wav.unlink()
 print(name,round(mp3.stat().st_size/1024),'KB','peak',round(float(np.max(np.abs(arr))),3))
for rank in range(1,6):output(f'tier-{rank}',stinger(rank))
output('spin-impact',gen_spin(),96)
output('led-click',gen_step(),80)
output('music-loop',gen_music(),80)
