/* UNO LUCK Audio v1.1: licensed-original synthesized audio, decoded once. */
(() => {
  'use strict';
  const samples = {spin:'spin-impact',tap:'led-click',tick:'led-click',
    'tier-1':'tier-1','tier-2':'tier-2','tier-3':'tier-3','tier-4':'tier-4','tier-5':'tier-5',music:'music-loop'};
  let ctx=null, master=null, compressor=null, fxBus=null, musicBus=null, playingMusic=null, musicRequested=false;
  const clamp=v=>Math.min(1,Math.max(0,Number.isFinite(Number(v))?Number(v):0));
  let fxLevel=clamp(localStorage.getItem('uno_luck_fx_volume')??'0.85');
  let masterLevel=clamp(localStorage.getItem('uno_luck_master_volume')??'0.90');
  let musicLevel=clamp(localStorage.getItem('uno_luck_music_volume')??'0.22');
  let audioEnabled=true, lastError='', lastLedTick=0, fanfareSource=null, studio=null, jackpotSeq=0;
  const cueMap={tap:'push-button',spin:'spinning-sound',lock:'chosen-card',
    'tier-1':'jackpot-1','tier-2':'jackpot-2','tier-3':'jackpot-3',
    'tier-4':'jackpot-4','tier-5':'jackpot-5'};
  function installStudio(adapter){studio=adapter;}
  function channels(){return {context:ctx,fx:fxBus,music:musicBus};}
  function playCue(name){return studio?.play(name)??Promise.resolve(false);}
  const audioAvailable=()=>isActive()||Boolean(studio?.mediaUnlocked);
  function result(winning){
    if(!audioEnabled||fxLevel===0)return false;
    if(studio?.isCustomized('result-sound'))return studio.play('result-sound');
    if(!isActive())return studio?.play('push-button')??false;
    chime(winning?1080:260);return true;
  }
  const buffers=new Map();
  const pending=new Map();
  const isActive=()=>ctx?.state==='running';
  function makeCtx(){
    if(ctx)return true;
    const AudioCtor=window.AudioContext||window.webkitAudioContext;
    if(!AudioCtor)return false;
    ctx=new AudioCtor({latencyHint:'interactive'});
    master=ctx.createGain(); master.gain.value=masterLevel;
    compressor=ctx.createDynamicsCompressor();
    compressor.threshold.value=-18;compressor.knee.value=18;
    compressor.ratio.value=4.6;compressor.attack.value=.003;compressor.release.value=.24;
    fxBus=ctx.createGain(); fxBus.gain.value=fxLevel;
    musicBus=ctx.createGain(); musicBus.gain.value=musicLevel;
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
      .catch(error=>{lastError='MP3 '+nameInFile+': '+String(error?.message||error);
        console.warn('[UNO LUCK AUDIO]',lastError);return null;})
      .finally(()=>pending.delete(nameInFile));
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
  // Called directly from a trusted click/touch. Prime a source before
  // awaiting any promise. WebKit can be "interrupted", not only "suspended".
  function primeOnGesture(){
    if(!ctx||ctx.state==='closed')return;
    try{
      const silent=ctx.createBuffer(1,1,ctx.sampleRate||44100);
      const source=ctx.createBufferSource();
      source.buffer=silent;
      source.connect(master);
      source.start(0);
    }catch(error){console.warn('[UNO AUDIO] Safari prime:',error);}
  }
  // Creating a suspended decoder before a gesture is safe. Never resume or
  // start sound here: Safari's actual unlock remains bound to a trusted event.
  function prepareContext(){return makeCtx()?ctx:null;}
  async function unlock(){
    try{
      if(!makeCtx()){
        lastError='Web Audio API tidak tersedia';
        return Boolean(studio?.mediaUnlocked);
      }
      if(!isActive()&&ctx.state!=='closed'){
        primeOnGesture();
        // Invoke resume while still in the trusted gesture, even if interrupted.
        const pending=ctx.resume();
        await Promise.race([pending,new Promise(resolve=>setTimeout(resolve,1100))]);
      }
      if(isActive()){
        lastError='';
        sample('spin');sample('tick');sample('tier-5');sample('music');
        return true;
      }
      lastError='Web Audio '+ctx.state+' · memakai HTML5 Audio jika tersedia';
      console.warn('[UNO AUDIO]',lastError);
      return Boolean(studio?.mediaUnlocked);
    }catch(error){
      lastError='Web Audio '+(ctx?.state||'unavailable')+': '+String(error?.message||error);
      console.warn('[UNO AUDIO]',lastError);
      return Boolean(studio?.mediaUnlocked);
    }
  }
  function ledTick(slowing=false){
    if(!isActive()||!audioEnabled||fxLevel===0)return false;
    const now=ctx.currentTime;
    if(now-lastLedTick<(slowing?.078:.065))return false;
    lastLedTick=now;
    const osc=ctx.createOscillator(),env=ctx.createGain();
    osc.type='triangle';osc.frequency.setValueAtTime(slowing?1140:1420,now);
    osc.frequency.exponentialRampToValueAtTime(slowing?810:1060,now+.038);
    env.gain.setValueAtTime(.0001,now);
    env.gain.exponentialRampToValueAtTime(slowing?.055:.034,now+.003);
    env.gain.exponentialRampToValueAtTime(.0001,now+.045);
    osc.connect(env).connect(fxBus);osc.start(now);osc.stop(now+.05);
    return true;
  }
  async function play(name){
    if(!audioEnabled||fxLevel===0)return false;
    if(!isActive()){
      const fallback=cueMap[name]||(name==='tick'?'push-button':
        name==='coin'||name==='win'||name==='lose'?'result-sound':null);
      return fallback?Boolean(await studio?.play(fallback)):false;
    }
    if(name==='coin'||name==='win'||name==='lose'){chime(name==='lose'?260:name==='coin'?1750:1080);return true;}
    const cue=cueMap[name];
    // When a user provides a custom JACKPOT clip, no bundled sample is layered over it.
    if(cue&&studio?.isCustomized(cue))return studio.play(cue);
    const playSeq=jackpotSeq;
    const sound=await sample(name==='lock'?'spin':name);
    if(name.startsWith('tier-')&&playSeq!==jackpotSeq)return false;
    if(!sound||!isActive()||!audioEnabled){
      // A decoded MP3 failure must never turn every game action completely silent.
      chime(name.startsWith('tier-')?1020:name==='lock'?530:820);
      return isActive();
    }
    if(name.startsWith('tier-')&&fanfareSource){
      try{fanfareSource.stop();}catch(_){} fanfareSource.disconnect();fanfareSource=null;
    }
    const src=ctx.createBufferSource();src.buffer=sound;
    if(name==='lock'){const gain=ctx.createGain();gain.gain.value=.66;
      src.playbackRate.value=1.23;src.connect(gain).connect(fxBus);}
    else src.connect(fxBus);
    if(name.startsWith('tier-')){
      fanfareSource=src;
      src.onended=()=>{if(fanfareSource===src)fanfareSource=null;};
    }
    src.start();return true;
  }
  async function music(playIt){
    musicRequested=Boolean(playIt);
    if(!playIt)studio?.stopLoop();
    // A separately pre-activated HTML5 lane must remain the sole BGM source.
    // Its trim/repeat/mixer follow the published Sound Cloud profile; WebAudio
    // running does NOT mean we should stop and replace music at game entry.
    if(playIt&&studio?.isMusicMediaPlaying?.())return true;
    if(!isActive()){
      if(!playIt)return false;
      // Music has its own mute preference. SFX OFF must not mute music.
      if(document.hidden)return false;
      // An iPhone gesture may already have started the dedicated music
      // element while Web Audio remains "interrupted". Never stop it and
      // restart asynchronously outside the user's activation window.
      if(studio?.isMusicMediaPlaying?.())return true;
      return Boolean(await studio?.play('background-music',{looping:true}));
    }
    if(playIt&&studio?.isCustomized('background-music')){
      if(!isActive()||document.hidden)return false;
      if(studio?.isMusicWebAudioPlaying?.())return true;
      if(playingMusic){try{playingMusic.stop();}catch(_){}playingMusic.disconnect();playingMusic=null;}
      return studio.play('background-music',{looping:true});
    }
    if(!playIt){if(playingMusic){try{playingMusic.stop();}catch(_){}playingMusic.disconnect();playingMusic=null;}return;}
    if(playingMusic||!isActive()||document.hidden)return;
    // Default bundled sample must not overlap an HTML5 music lane that was
    // started while Safari Web Audio was interrupted.
    studio?.stopLoop?.();
    const buffer=await sample('music');
    if(!buffer||!isActive()||playingMusic||document.hidden)return;
    const src=ctx.createBufferSource();src.buffer=buffer;src.loop=true;src.connect(musicBus);src.start();playingMusic=src;
  }
  async function refreshMusic(){
    if(!musicRequested || !audioAvailable() || document.hidden)return false;
    await music(false);
    return music(true);
  }
  function cinematicImpact(rank=5){
    if(!isActive()||!audioEnabled||fxLevel<=0)return false;
    const now=ctx.currentTime;
    const intensity=rank===1?1:rank===2?.85:rank===3?.7:rank===4?.6:.49;
    for(const [freq,shape,amount] of [[180,'sine',.22],[330,'triangle',.075]]){
      const osc=ctx.createOscillator();const env=ctx.createGain();
      osc.type=shape;
      osc.frequency.setValueAtTime(freq*1.4,now);
      osc.frequency.exponentialRampToValueAtTime(freq*.58,now+.30);
      env.gain.setValueAtTime(.001,now);
      env.gain.exponentialRampToValueAtTime(amount*intensity,now+.012);
      env.gain.exponentialRampToValueAtTime(.001,now+.42);
      osc.connect(env).connect(fxBus);osc.start(now);osc.stop(now+.46);
    }
    return true;
  }
  async function testSound(){
    if(!isActive())return false;
    cinematicImpact(3);
    const impact=await play('spin');
    const fanfare=await play('tier-5');
    return Boolean(impact&&fanfare);
  }
  function stopCelebration(){
    jackpotSeq++; // prevents late decoded bundled samples from starting
    studio?.stopCelebration?.();
    if(fanfareSource){
      try{fanfareSource.stop();}catch(_){} fanfareSource.disconnect();fanfareSource=null;
    }
    if(musicBus&&ctx?.state==='running'){
      musicBus.gain.cancelScheduledValues(ctx.currentTime);
      musicBus.gain.setTargetAtTime(musicLevel,ctx.currentTime,.12);
    }
  }
  async function celebration(rank){
    if(!Number.isInteger(rank)||rank<1||rank>5)return {played:false,duration:0};
    if(!audioEnabled||fxLevel===0)return {played:false,duration:0};
    stopCelebration();
    const token=jackpotSeq;
    const key='jackpot-'+rank;
    const customized=Boolean(studio?.isCustomized(key));
    // The selected file alone wins: no synthetic hit, generic stinger or other tier.
    if(!customized&&isActive())cinematicImpact(rank);
    if(isActive()&&musicBus){
      musicBus.gain.cancelScheduledValues(ctx.currentTime);
      musicBus.gain.setTargetAtTime(musicLevel*.17,ctx.currentTime,.09);
    }
    const played=await play(`tier-${rank}`);
    if(token!==jackpotSeq)return {played:false,duration:0};
    let duration=0;
    if(played){
      try{duration=customized?await studio.segmentDuration(key):
        (await sample(`tier-${rank}`))?.duration||0;}
      catch(error){lastError='Jackpot '+rank+' duration: '+String(error?.message||error);}
    }
    if(token!==jackpotSeq)return {played:false,duration:0};
    return {played:Boolean(played),duration:Number(duration)||0,cue:key,customized};
  }
  function setVolume(v){fxLevel=clamp(v);localStorage.setItem('uno_luck_fx_volume',String(fxLevel));if(fxBus&&ctx)fxBus.gain.setTargetAtTime(fxLevel,ctx.currentTime,.04);return fxLevel;}
  function setMasterVolume(v){masterLevel=clamp(v);localStorage.setItem('uno_luck_master_volume',String(masterLevel));
    if(master&&ctx)master.gain.setTargetAtTime(masterLevel,ctx.currentTime,.04);return masterLevel;}
  function setMusicVolume(v){musicLevel=clamp(v);localStorage.setItem('uno_luck_music_volume',String(musicLevel));
    if(musicBus&&ctx)musicBus.gain.setTargetAtTime(musicLevel,ctx.currentTime,.05);return musicLevel;}
  function setEnabled(v){audioEnabled=Boolean(v);}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)music(false);});
  window.UNOLuckSound={unlock,play,music,celebration,testSound,ledTick,setVolume,setMasterVolume,setMusicVolume,setEnabled,
    installStudio,channels,prepareContext,playCue,result,refreshMusic,stopCelebration,
    get volume(){return fxLevel;},get masterVolume(){return masterLevel;},
    get musicVolume(){return musicLevel;},get lastError(){return lastError;},
    get state(){return isActive()?'running':studio?.mediaUnlocked?'media-fallback':
      ctx?.state||'inactive';},get webAudioState(){return ctx?.state||'inactive';}};
})();
