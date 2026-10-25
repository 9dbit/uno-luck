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
    // On iOS the WebAudio graph may say "running" while the hardware
    // audio route is silent. Prefer a native media cue in that case.
    if(studio?.isIOS?.()||!isActive())return studio?.play('push-button')??false;
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
    // Effects must not pump/duck the music through a shared compressor.
    fxBus.connect(compressor);musicBus.connect(master);
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
    primeNumericBonus();
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
    if(studio?.isSpinPlaying?.())return false;
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
    // The iPhone's custom Sound Cloud files and bundled backup cues must
    // all use HTMLMediaElement rather than an apparently-running but silent
    // AudioContext. Keep the published selection, trim and mixer unchanged.
    if(studio?.isIOS?.()){
      const nativeCue=cueMap[name]||(name==='tick'?'push-button':
        name==='coin'||name==='win'||name==='lose'?
          (studio?.isCustomized('result-sound')?'result-sound':'push-button'):null);
      return nativeCue?Boolean(await studio.play(nativeCue)):false;
    }
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
  function startSpin(){
    if(!audioEnabled||fxLevel===0||document.hidden)return false;
    return studio?.startSpin?.()??false;
  }
  function stopSpin(){studio?.stopSpin?.();}
  async function music(playIt){
    musicRequested=Boolean(playIt);
    if(!playIt)studio?.stopLoop();
    // The music lane was preactivated on splash PLAY and is already playing
    // when gameplay opens. Do not start another AudioBufferSource on top.
    if(playIt&&studio?.isMusicMediaPlaying?.())return true;
    if(playIt&&studio?.isIOS?.()){
      if(document.hidden)return false;
      return Boolean(await studio?.play('background-music',{looping:true}));
    }
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
  let bonusMedia=null,bonusPrimed=false;
  function primeNumericBonus(){
    if(bonusPrimed)return;
    // An original bundled-in-code MP3 fanfare also works in Safari's native media lane.
    // Prime silently during the same trusted gesture used for the other audio.
    if(!bonusMedia){
      const pcm='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MMS5lxczSNczEuhYeZgiXM0eWsPLYYnlrB8zA+oGm3IhSXYeyiVWSTUnCeS8o7jRKFhkQEE4uFkQYSWUWZcXDvG5U0aUUfFkatbLP///84LEMB56IbAWSYbtMjVrJUcjVrZZf+5katZKhkatbLLLLYZGrKCBRByUrVVVVXKqDEqQNVi//TTUslCaKllv/6qq4aoMSphq//rBNNQ5YJoqv/0qoiVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zgsQ7AAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
      const bytes=Uint8Array.from(atob(pcm),c=>c.charCodeAt(0));
      bonusMedia=new Audio(URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'})));
      bonusMedia.preload='auto';
    }
    bonusMedia.muted=true;
    bonusMedia.play().then(()=>{bonusMedia.pause();bonusMedia.currentTime=0;bonusPrimed=true;}).catch(()=>{});
  }
  function numericBonus(){
    if(!audioEnabled||fxLevel===0||masterLevel===0)return false;
    if(studio?.isIOS?.()||!isActive()){
      if(!bonusPrimed||!bonusMedia)return false;
      bonusMedia.currentTime=0;bonusMedia.muted=false;bonusMedia.volume=fxLevel*masterLevel;
      void bonusMedia.play().catch(()=>{});return true;
    }
    // Short distinct tadaa through the existing SFX/master bus; never stops BGM.
    [523.25,659.25,783.99,1046.5].forEach((hz,i)=>{
      const start=ctx.currentTime+i*.07,osc=ctx.createOscillator(),gain=ctx.createGain();
      osc.type='sine';osc.frequency.value=hz;
      gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(.13,start+.015);
      gain.gain.exponentialRampToValueAtTime(.001,start+.38);
      osc.connect(gain).connect(fxBus);osc.start(start);osc.stop(start+.4);
      osc.onended=()=>{osc.disconnect();gain.disconnect();};
    });return true;
  }
  function setVolume(v){fxLevel=clamp(v);localStorage.setItem('uno_luck_fx_volume',String(fxLevel));if(fxBus&&ctx)fxBus.gain.setTargetAtTime(fxLevel,ctx.currentTime,.04);return fxLevel;}
  function setMasterVolume(v){masterLevel=clamp(v);localStorage.setItem('uno_luck_master_volume',String(masterLevel));
    if(master&&ctx)master.gain.setTargetAtTime(masterLevel,ctx.currentTime,.04);return masterLevel;}
  function setMusicVolume(v){musicLevel=clamp(v);localStorage.setItem('uno_luck_music_volume',String(musicLevel));
    if(musicBus&&ctx)musicBus.gain.setTargetAtTime(musicLevel,ctx.currentTime,.05);return musicLevel;}
  function setEnabled(v){audioEnabled=Boolean(v);if(!audioEnabled){stopSpin();bonusMedia?.pause();}}
  document.addEventListener('visibilitychange',()=>{if(document.hidden){music(false);stopSpin();bonusMedia?.pause();}});
  window.UNOLuckSound={numericBonus,unlock,play,music,celebration,testSound,ledTick,setVolume,setMasterVolume,setMusicVolume,setEnabled,
    installStudio,channels,prepareContext,playCue,result,refreshMusic,stopCelebration,startSpin,stopSpin,
    get volume(){return fxLevel;},get masterVolume(){return masterLevel;},
    get musicVolume(){return musicLevel;},get lastError(){return lastError;},
    get state(){return isActive()?'running':studio?.mediaUnlocked?'media-fallback':
      ctx?.state||'inactive';},get webAudioState(){return ctx?.state||'inactive';}};
})();

