/* UNO LUCK Audio v1.0: licensed-original synthesized audio, decoded once. */
(() => {
  'use strict';
  const samples = {spin:'spin-impact',tap:'led-click',tick:'led-click',
    'tier-1':'tier-1','tier-2':'tier-2','tier-3':'tier-3','tier-4':'tier-4','tier-5':'tier-5',music:'music-loop'};
  let ctx=null, master=null, compressor=null, fxBus=null, musicBus=null, playingMusic=null;
  let fxLevel=Math.min(1,Math.max(0,Number(localStorage.getItem('uno_luck_fx_volume')??'0.85')))||0;
  let audioEnabled=true;
  const buffers=new Map();
  const pending=new Map();
  const isActive=()=>ctx?.state==='running';
  function makeCtx(){
    if(ctx)return true;
    const AudioCtor=window.AudioContext||window.webkitAudioContext;
    if(!AudioCtor)return false;
    ctx=new AudioCtor({latencyHint:'interactive'});
    master=ctx.createGain(); master.gain.value=.86;
    compressor=ctx.createDynamicsCompressor();
    compressor.threshold.value=-18;compressor.knee.value=18;
    compressor.ratio.value=4.6;compressor.attack.value=.003;compressor.release.value=.24;
    fxBus=ctx.createGain(); fxBus.gain.value=fxLevel;
    musicBus=ctx.createGain(); musicBus.gain.value=.13;
    fxBus.connect(compressor);musicBus.connect(compressor);
    compressor.connect(master);master.connect(ctx.destination);
    return true;
  }
  async function sample(name){
    const nameInFile=samples[name];if(!nameInFile||!ctx)return null;
    if(buffers.has(nameInFile))return buffers.get(nameInFile);
    if(pending.has(nameInFile))return pending.get(nameInFile);
    const promise=fetch(`/assets/audio/${nameInFile}.mp3`,{cache:'force-cache'})
      .then(r=>{if(!r.ok)throw Error(`audio ${r.status}`);return r.arrayBuffer();})
      .then(bytes=>ctx.decodeAudioData(bytes))
      .then(buf=>{buffers.set(nameInFile,buf);return buf;})
      .catch(()=>null).finally(()=>pending.delete(nameInFile));
    pending.set(nameInFile,promise);
    return promise;
  }
  function chime(frequency=910){
    if(!isActive()||!audioEnabled)return;
    const osc=ctx.createOscillator(),env=ctx.createGain(),now=ctx.currentTime;
    osc.type='triangle';osc.frequency.setValueAtTime(frequency,now);
    osc.frequency.exponentialRampToValueAtTime(frequency*.72,now+.15);
    env.gain.setValueAtTime(.001,now);env.gain.exponentialRampToValueAtTime(.12,now+.008);
    env.gain.exponentialRampToValueAtTime(.001,now+.20);
    osc.connect(env).connect(fxBus);osc.start(now);osc.stop(now+.22);
  }
  async function unlock(){
    try{if(!makeCtx())return false;
      if(ctx.state==='suspended')await ctx.resume();
      if(isActive()){sample('spin');sample('tick');sample('tier-5');sample('music');}
      return isActive();
    }catch(_){return false;}
  }
  async function play(name){
    if(!audioEnabled||!isActive()||fxLevel===0)return false;
    if(name==='coin'||name==='win'||name==='lose'){chime(name==='lose'?260:name==='coin'?1750:1080);return true;}
    const sound=await sample(name);
    if(!sound||!isActive()||!audioEnabled)return false;
    const src=ctx.createBufferSource();src.buffer=sound;src.connect(fxBus);src.start();
    return true;
  }
  async function music(playIt){
    if(!playIt){if(playingMusic){try{playingMusic.stop();}catch(_){}playingMusic.disconnect();playingMusic=null;}return;}
    if(playingMusic||!isActive()||document.hidden)return;
    const buffer=await sample('music');
    if(!buffer||!isActive()||playingMusic||document.hidden)return;
    const src=ctx.createBufferSource();src.buffer=buffer;src.loop=true;src.connect(musicBus);src.start();playingMusic=src;
  }
  async function celebration(rank){
    if(!Number.isInteger(rank)||rank<1||rank>5)return;
    if(!isActive())return;
    if(musicBus){musicBus.gain.cancelScheduledValues(ctx.currentTime);
      musicBus.gain.setTargetAtTime(.035,ctx.currentTime,.09);
      musicBus.gain.setTargetAtTime(.13,ctx.currentTime+({1:5.5,2:4.7,3:3.8,4:2.9,5:1.85}[rank]),.4);
    }
    return play(`tier-${rank}`);
  }
  function setVolume(v){fxLevel=Math.max(0,Math.min(1,Number(v)||0));localStorage.setItem('uno_luck_fx_volume',String(fxLevel));if(fxBus&&ctx)fxBus.gain.setTargetAtTime(fxLevel,ctx.currentTime,.04);return fxLevel;}
  function setEnabled(v){audioEnabled=Boolean(v);}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)music(false);});
  window.UNOLuckSound={unlock,play,music,celebration,setVolume,setEnabled,
    get volume(){return fxLevel;},get state(){return ctx?.state||'inactive';}};
})();
