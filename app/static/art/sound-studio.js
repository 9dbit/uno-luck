/* UNO LUCK Sound Studio v1.1. Custom sound clips stay ON THIS DEVICE,
   in IndexedDB. No coin / result / account / payout interactions. */
(() => {
'use strict';
const KEYS=[
 ['soft-tech-splash-screen','SOFT TECH SPLASH SCREEN',null],
 ['loading-scene','LOADING SCENE',null],
 ['background-music','BACKGROUND MUSIC','music-loop'],
 ['push-button','PUSH BUTTON','led-click'],
 ['spinning-sound','SPINING SOUND','spin-impact'],
 ['chosen-card','CHOOSEN CARD','spin-impact'],
 ['result-sound','RESULT SOUND',null],
 ...[1,2,3,4,5].map(rank=>['jackpot-'+rank,'JACKPOT '+rank,'tier-'+rank])
];
const known=new Map(KEYS.map(x=>[x[0],x]));
const KEY='uno_sound_studio_profiles_v1',DB='uno-luck-custom-sound-v1',MAX_BYTES=16*1024*1024;
const profiles=(()=>{try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch(_){return {};}})();
const bufferCache=new Map();
let cloudProfiles=new Map(), cloudRevision='', cloudReady=false, cloudError='';
let cloudMixer=null, mixerPublishTimer=null;
let cloudFetch=null, adminKey=sessionStorage.getItem('uno-sound-admin-key')||'';
const liveProfile=key=>cloudProfiles.get(key)||profiles[key]||{};
const editProfile=key=>profiles[key]||cloudProfiles.get(key)||{};
async function syncCloud(force=false){
  if(cloudFetch){
    if(!force)return cloudFetch;
    // Serialize forced refreshes; older in-flight manifests must never
    // overwrite a freshly published desktop edit on a different device.
    await cloudFetch;
  }
  cloudFetch=(async()=>{
    const response=await fetch('/api/sounds/manifest',{cache:'no-store'});
    if(!response.ok)throw Error('Cloud catalog HTTP '+response.status);
    const data=await response.json();
    if(data.ready!==true){cloudReady=false;cloudError='Cloud storage belum siap';return false;}
    cloudReady=true;cloudError='';
    if(data.revision!==cloudRevision){
      const oldSplash=cloudProfiles.get('soft-tech-splash-screen')?.revision;
      cloudRevision=data.revision;
      cloudProfiles=new Map(Object.entries(data.cues||{}).filter(([key])=>known.has(key)));
      cloudMixer=data.mixer&&typeof data.mixer==='object'?data.mixer:null;
      if(cloudMixer&&window.UNOLuckSound){
        window.UNOLuckSound.setMasterVolume(cloudMixer.master);
        window.UNOLuckSound.setMusicVolume(cloudMixer.music);
        window.UNOLuckSound.setVolume(cloudMixer.sfx);
      }
      bufferCache.clear();
      if(document.visibilityState==='visible'&&cloudProfiles.has('background-music'))
        void window.UNOLuckSound?.refreshMusic?.();
      if(oldSplash!==cloudProfiles.get('soft-tech-splash-screen')?.revision){
        if(splashUrl?.startsWith('blob:'))URL.revokeObjectURL(splashUrl);
        splashUrl=null;
      }
      window.dispatchEvent(new CustomEvent('uno:sound-cloud-synced',
        {detail:{revision:cloudRevision,cues:cloudProfiles.size}}));
    }
    return true;
  })().catch(error=>{
    cloudReady=false;
    cloudError=String(error?.message||error);
    console.warn('[UNO SOUND CLOUD]',cloudError);
    return false;
  }).finally(()=>{cloudFetch=null;});
  return cloudFetch;
}
function hasAdminKey(){return adminKey.length>=32;}
async function verifyAdminKey(value){
  const entered=String(value||'').trim();
  if(entered.length<32)throw Error('Masukkan kunci admin Sound Studio dari Railway (minimal 32 karakter).');
  const response=await fetch('/api/sounds/admin/check',
    {headers:{'X-UNO-Sound-Admin':entered},cache:'no-store'});
  if(!response.ok)throw Error(response.status===403?
    'Kunci admin salah. Salin dari Railway → Variables → UNO_SOUND_ADMIN_TOKEN.':
    'Verifikasi admin gagal: HTTP '+response.status);
  adminKey=entered;sessionStorage.setItem('uno-sound-admin-key',entered);
  return true;
}
function cloudStatus(){return {ready:cloudReady,revision:cloudRevision,
  online:cloudProfiles.size,error:cloudError,admin:hasAdminKey()};}
async function publishCue(key,{remove=false}={}){
  if(!known.has(key))throw Error('Sound cue tidak dikenal');
  if(!hasAdminKey())throw Error('Kunci admin diperlukan untuk publish sound ke semua perangkat.');
  const headers={'X-UNO-Sound-Admin':adminKey};
  let method='PATCH',body=null,expected=null;
  if(remove){method='DELETE';}
  else{
    const local=profiles[key]||{};
    if(!local.custom&&!local.edited)throw Error('Belum ada perubahan lokal untuk '+key);
    const duration=Number(local.fileDuration)||(await measure(key));
    const meta={
      start:Number(local.start??0),stop:Number(local.stop??duration),
      fadeIn:Number(local.fadeIn??0),fadeOut:Number(local.fadeOut??0),
      fileDuration:duration,repeat:local.repeat!==false,
    };
    expected=meta;
    if(local.custom){
      const file=await readFile(key);
      if(!file)throw Error('File '+key+' tidak ditemukan di desktop. Upload ulang.');
      method='PUT';body=file;
      headers['Content-Type']=file.type||mimeFor(file);
      headers['X-UNO-Sound-Name']=encodeURIComponent(local.fileName||file.name||'sound.mp3');
      headers['X-UNO-Sound-Settings']=JSON.stringify(meta);
    }else{
      headers['Content-Type']='application/json';
      body=JSON.stringify(meta);
    }
  }
  const res=await fetch('/api/sounds/cues/'+encodeURIComponent(key),
    {method,headers,body,cache:'no-store'});
  if(!res.ok){
    let message='HTTP '+res.status;
    try{const error=await res.json();message=error.detail||message;}catch(_){}
    throw Error('Gagal publish '+key+': '+message);
  }
  if(!(await syncCloud(true)))throw Error('Sound tersimpan tetapi cloud belum bisa diverifikasi: '+cloudError);
  const published=cloudProfiles.get(key);
  if(remove){
    if(published)throw Error('Sound reset belum terkonfirmasi oleh server');
  }else{
    if(!published)throw Error('Sound tidak ditemukan pada manifest setelah publish');
    for(const field of ['start','stop','fadeIn','fadeOut','fileDuration']){
      if(Math.abs(Number(published[field])-expected[field])>.011)
        throw Error('Cloud belum memakai '+field+' terbaru. Refresh dan ulangi SAVE.');
    }
    if(Boolean(published.repeat)!==expected.repeat)
      throw Error('Repeat di cloud belum sesuai dengan setting desktop');
  }
  return true;
}
async function publishMixer(){
  if(!hasAdminKey())throw Error('Kunci admin diperlukan untuk publish mixer.');
  const sound=window.UNOLuckSound;
  if(!sound)throw Error('Audio mixer belum aktif');
  const levels={master:sound.masterVolume,music:sound.musicVolume,sfx:sound.volume};
  const response=await fetch('/api/sounds/mixer',{
    method:'PATCH',cache:'no-store',
    headers:{'Content-Type':'application/json','X-UNO-Sound-Admin':adminKey},
    body:JSON.stringify(levels)
  });
  if(!response.ok)throw Error('Gagal publish mixer: HTTP '+response.status);
  await syncCloud(true);
  return true;
}
function schedulePublishMixer(){
  if(!hasAdminKey())return false;
  if(mixerPublishTimer)clearTimeout(mixerPublishTimer);
  mixerPublishTimer=setTimeout(()=>{
    mixerPublishTimer=null;void publishMixer().catch(error=>{
      cloudError=error.message;console.warn('[UNO SOUND CLOUD]',cloudError);
    });
  },650);
  return true;
}
async function publishAll(progress=()=>{}){
  if(!hasAdminKey())throw Error('Masukkan kunci admin sebelum mempublikasikan audio desktop.');
  const entries=KEYS.map(([key])=>key).filter(key=>{
    const p=profiles[key];return Boolean(p&&(p.custom||p.edited));
  });
  if(!entries.length)throw Error('Tidak ada audio lokal untuk dipublikasikan.');
  for(let i=0;i<entries.length;i++){
    progress(i+1,entries.length,entries[i]);
    await publishCue(entries[i]);
  }
  await publishMixer();
  return entries.length;
}
let database=null, preview=null, loop=null, loopSerial=0, lastError='';
let celebrationNode=null, celebrationRequest=0;
// Keep one media element already activated by the splash tap. Reusing the element
// permits subsequent custom cues even in iOS WebViews with interrupted Web Audio.
let fallbackPlayer=null, fallbackKey=null, fallbackPreview=false;
let fallbackTimer=null, fallbackRaf=null, fallbackSerial=0, mediaUnlocked=false;
let splashUrl=null, splashPreparation=null, splashError='',activeTemporaryUrl=null;
const isIOS=()=>/iPhone|iPad|iPod/.test(navigator.userAgent)||
  (navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const mimeFor=file=>{
  if(file.type&&file.type.startsWith('audio/'))return file.type;
  const ext=String(file.name||'').split('.').pop().toLowerCase();
  return ({mp3:'audio/mpeg',m4a:'audio/mp4',aac:'audio/aac',
    wav:'audio/wav',ogg:'audio/ogg',webm:'audio/webm'})[ext]||'audio/mpeg';
};
function mediaPlayer(){
  if(!fallbackPlayer){
    fallbackPlayer=document.createElement('audio');
    fallbackPlayer.preload='auto';
    fallbackPlayer.playsInline=true;
    fallbackPlayer.setAttribute('playsinline','');
    fallbackPlayer.hidden=true;
    document.body.append(fallbackPlayer);
  }
  return fallbackPlayer;
}
function clearFallbackTiming(){
  if(fallbackTimer!==null)clearTimeout(fallbackTimer);
  if(fallbackRaf!==null)cancelAnimationFrame(fallbackRaf);
  fallbackTimer=null;fallbackRaf=null;
}
function stopFallback(key=null){
  if(key&&fallbackKey!==key)return;
  fallbackSerial++;
  clearFallbackTiming();
  if(fallbackPlayer){fallbackPlayer.pause();fallbackPlayer.loop=false;}
  if(activeTemporaryUrl){URL.revokeObjectURL(activeTemporaryUrl);activeTemporaryUrl=null;}
  fallbackKey=null;fallbackPreview=false;
}
function useFallbackSource(key,url){
  const player=mediaPlayer();
  if(player.getAttribute('src')!==url){player.pause();player.src=url;player.load();}
  if(url.startsWith('blob:')&&url!==splashUrl)activeTemporaryUrl=url;
  return player;
}
async function prepareSplashMedia(){
  await syncCloud();
  const cfg=liveProfile('soft-tech-splash-screen');
  if(!cfg.custom&&cfg.source!=='custom')return false;
  if(splashUrl)return true;
  if(splashPreparation)return splashPreparation;
  splashPreparation=(async()=>{
    if(cfg.source==='custom'&&cfg.url){
      splashUrl=cfg.url;
    }else{
      const file=await readFile('soft-tech-splash-screen');
      if(!file)throw Error('File splash lokal tidak ditemukan. Publikasikan dari desktop.');
      const typed=file.type?.startsWith('audio/')?file:new Blob([file],{type:mimeFor(file)});
      splashUrl=URL.createObjectURL(typed);
    }
    useFallbackSource('soft-tech-splash-screen',splashUrl);
    splashError='';
    return true;
  })().catch(error=>{
    splashError=String(error?.message||error);lastError=splashError;
    console.warn('[UNO iOS AUDIO] splash preload',splashError);
    throw error;
  }).finally(()=>{splashPreparation=null;});
  return splashPreparation;
}
function applyMediaBounds(key,player,previewMode=false,looping=false){
  clearFallbackTiming();
  const serial=++fallbackSerial;
  const p=previewMode?editProfile(key):liveProfile(key);
  const duration=Math.max(.05,Number(p.fileDuration)||player.duration||5);
  const bounds=limits(key,duration,{draft:previewMode});
  const start=Math.max(0,bounds.start);
  const stop=Math.max(start+.02,bounds.stop);
  const gain=()=>{
    const mixer=window.UNOLuckSound;
    const level=(mixer?.masterVolume??.9) *
      (key==='background-music'?(mixer?.musicVolume??.22):(mixer?.volume??.85));
    return clamp(level,0,.95);
  };
  const tick=()=>{
    if(serial!==fallbackSerial||player.paused)return;
    const t=player.currentTime;
    if(t>=stop-.025){
      if(looping&&getRepeat(key)){
        try{player.currentTime=start;}catch(_){}
        fallbackRaf=requestAnimationFrame(tick);return;
      }
      stopFallback(key);return;
    }
    const elapsed=Math.max(0,t-start),remaining=Math.max(0,stop-t);
    const fadeIn=bounds.fadeIn>0?Math.min(1,elapsed/bounds.fadeIn):1;
    const fadeOut=bounds.fadeOut>0?Math.min(1,remaining/bounds.fadeOut):1;
    // iOS may ignore element.volume. The trim still works, and the device
    // hardware volume remains the authoritative loudness control.
    try{player.volume=clamp(gain()*Math.min(fadeIn,fadeOut),0,1);}catch(_){}
    fallbackRaf=requestAnimationFrame(tick);
  };
  const seek=()=>{try{player.currentTime=start;}catch(_){}
    if(fallbackRaf===null)fallbackRaf=requestAnimationFrame(tick);};
  if(player.readyState>=1)seek();
  else player.addEventListener('loadedmetadata',seek,{once:true});
  player.loop=false;
  fallbackKey=key;
  fallbackPreview=previewMode;
  return {player,bounds};
}
function playSplashGesture(){
  // Must be invoked *synchronously* in a real user tap. No await/fetch/IDB
  // can appear between the click and this HTMLMediaElement.play call.
  if(!splashUrl)return Promise.resolve(false);
  stopFallback();
  const player=useFallbackSource('soft-tech-splash-screen',splashUrl);
  applyMediaBounds('soft-tech-splash-screen',player);
  let promise;
  try{promise=player.play();}catch(error){
    splashError='HTML5 Audio: '+String(error?.message||error);
    lastError=splashError;return Promise.resolve(false);
  }
  return Promise.resolve(promise).then(()=>{
    mediaUnlocked=true;lastError='';return true;
  }).catch(error=>{
    splashError='HTML5 Audio: '+String(error?.message||error);
    lastError=splashError;console.warn('[UNO iOS AUDIO]',splashError);
    return false;
  });
}
async function playFallback(key,{looping=false,forPreview=false,token=null}={}){
  const entry=known.get(key);if(!entry)return false;
  try{
    if(key==='soft-tech-splash-screen'&&!splashUrl&&!forPreview)await prepareSplashMedia();
    const cfg=forPreview?editProfile(key):liveProfile(key);
    let url;
    if(key==='soft-tech-splash-screen'&&!forPreview)url=splashUrl;
    else if(cfg.source==='custom'&&cfg.url)url=cfg.url;
    else if(cfg.custom){
      const file=await readFile(key);
      if(!file)throw Error('File audio lokal hilang: '+key);
      const typed=file.type?.startsWith('audio/')?file:new Blob([file],{type:mimeFor(file)});
      url=URL.createObjectURL(typed);
    }else{
      if(!entry[2])return false;
      url='/assets/audio/'+entry[2]+'.mp3';
    }
    if(token!==null&&token!==celebrationRequest){
      if(url?.startsWith('blob:')&&url!==splashUrl)URL.revokeObjectURL(url);
      return false;
    }
    stopFallback();
    const player=useFallbackSource(key,url);
    const end=applyMediaBounds(key,player,forPreview,looping);
    // Release temporary URLs once a subsequent cue replaces the source.
    // Keeping the current URL intact is required for seeking/repeating.
    const promise=player.play();
    await Promise.resolve(promise);
    mediaUnlocked=true;
    return Boolean(end.bounds.length>0);
  }catch(error){
    lastError='HTML5 '+key+': '+String(error?.message||error);
    console.warn('[UNO iOS AUDIO]',lastError);return false;
  }
}
const clamp=(v,min,max)=>Math.max(min,Math.min(max,Number.isFinite(Number(v))?Number(v):min));
const decimals=n=>Number(n.toFixed(2));
const save=()=>localStorage.setItem(KEY,JSON.stringify(profiles));
function openDb(){
  if(!('indexedDB' in window))return Promise.reject(Error('IndexedDB tidak tersedia'));
  if(database)return database;
  database=new Promise((resolve,reject)=>{
    const request=indexedDB.open(DB,1);
    request.onupgradeneeded=()=>request.result.createObjectStore('files');
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>{database=null;reject(request.error||Error('Tidak bisa membuka penyimpanan'));};
  });return database;
}
async function readFile(key){
  const db=await openDb();
  return new Promise((resolve,reject)=>{
    const req=db.transaction('files','readonly').objectStore('files').get(key);
    req.onsuccess=()=>resolve(req.result||null);
    req.onerror=()=>reject(req.error);
  });
}
async function writeFile(key,blob){
  const db=await openDb();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction('files','readwrite');
    tx.objectStore('files').put(blob,key);
    tx.oncomplete=()=>resolve(true);
    tx.onerror=()=>reject(tx.error||Error('Penyimpanan audio penuh'));
    tx.onabort=()=>reject(tx.error||Error('Audio gagal disimpan'));
  });
}
async function removeFile(key){
  const db=await openDb();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction('files','readwrite');
    tx.objectStore('files').delete(key);
    tx.oncomplete=()=>resolve(true);tx.onerror=()=>reject(tx.error);
  });
}
function channel(){
  const r=window.UNOLuckSound?.channels?.();
  if(!r?.context||r.context.state!=='running')throw Error('Aktifkan audio melalui tombol game terlebih dahulu');
  return r;
}
async function getBuffer(key,{draft=false}={}){
  const cacheKey=(draft?'draft:':'live:')+key;
  const requestedRevision=cloudRevision;
  if(bufferCache.has(cacheKey))return bufferCache.get(cacheKey);
  const entry=known.get(key);if(!entry)throw Error('Sound event tidak dikenal');
  const cfg=draft?editProfile(key):liveProfile(key);
  let bytes;
  if(cfg.source==='custom'&&cfg.url){
    const response=await fetch(cfg.url,{cache:'force-cache'});
    if(!response.ok)throw Error('Cloud audio '+key+' HTTP '+response.status);
    bytes=await response.arrayBuffer();
  }else if(cfg.custom){
    const file=await readFile(key);
    if(!file)throw Error('File audio lokal tidak ditemukan. Upload ulang dari desktop.');
    bytes=await file.arrayBuffer();
  }else{
    if(!entry[2])return null;
    const response=await fetch('/assets/audio/'+entry[2]+'.mp3',{cache:'force-cache'});
    if(!response.ok)throw Error('Audio tidak tersedia: '+response.status);
    bytes=await response.arrayBuffer();
  }
  // Decoding is legal while a Safari AudioContext is suspended/interrupted.
  // Only source playback (not file editing) needs an active context.
  const context=window.UNOLuckSound?.channels?.()?.context;
  if(!context)throw Error('Audio decoder tidak tersedia. Mulai game lalu coba kembali.');
  const buffer=await context.decodeAudioData(bytes.slice(0));
  // In-flight default decoding must never overwrite a newer uploaded draft;
  // likewise an old cloud response must not repopulate a refreshed catalog.
  if(!draft&&requestedRevision!==cloudRevision)return buffer;
  if(!bufferCache.has(cacheKey))bufferCache.set(cacheKey,buffer);
  return bufferCache.get(cacheKey);
}
function limits(key,duration,{draft=false}={}){
  const current=draft?editProfile(key):liveProfile(key);
  const start=clamp(current.start??0,0,Math.max(0,duration-.02));
  const stop=clamp(current.stop??duration,start+.01,duration);
  const length=stop-start;
  const fadeIn=clamp(current.fadeIn??0,0,length/2);
  const fadeOut=clamp(current.fadeOut??0,0,length/2);
  return {start,stop,length,fadeIn,fadeOut};
}
function isCustomized(key){
  const p=liveProfile(key);
  return Boolean(p&&(p.custom||p.edited||p.source==='custom'||
    (cloudProfiles.has(key)&&known.get(key)?.[2])));
}
function profile(key){return {...editProfile(key)};}
function publishedProfile(key){return {...(cloudProfiles.get(key)||{})};}
function getRepeat(key){return key==='background-music' && liveProfile(key)?.repeat!==false;}
function getDraftRepeat(key){return key==='background-music' && editProfile(key)?.repeat!==false;}
function setRepeat(key,enabled){
  if(key!=='background-music')throw Error('Repeat hanya untuk BACKGROUND MUSIC');
  profiles[key]={...editProfile(key),repeat:Boolean(enabled),edited:true};
  save();
  if(hasAdminKey())void publishCue(key).catch(error=>{
    lastError=error.message;console.warn('[UNO SOUND CLOUD]',lastError);
  });
  window.UNOLuckSound?.refreshMusic?.();
  return getDraftRepeat(key);
}
async function measure(key){const b=await getBuffer(key,{draft:true});return b?.duration||0;}
async function configure(key,settings){
  if(!known.has(key))throw Error('Sound event tidak dikenal');
  const length=await measure(key);
  if(!length)throw Error('Upload file audio terlebih dahulu');
  const start=Number(settings.start),stop=Number(settings.stop);
  const fi=Number(settings.fadeIn),fo=Number(settings.fadeOut);
  if(![start,stop,fi,fo].every(Number.isFinite)||start<0||stop>length+.001||stop-start<.02||
      fi<0||fo<0||fi+fo>stop-start+.001)throw Error('Rentang start/stop atau fade tidak valid');
  profiles[key]={...editProfile(key),start:decimals(start),stop:decimals(Math.min(stop,length)),
    fadeIn:decimals(fi),fadeOut:decimals(fo),edited:true};
  save();bufferCache.delete('draft:'+key);
  if(hasAdminKey())await publishCue(key);
  if(key==='background-music')window.UNOLuckSound?.refreshMusic?.();
  return limits(key,length,{draft:true});
}
async function upload(key,file){
  if(!known.has(key))throw Error('Sound event tidak dikenal');
  if(!file||!file.size||file.size>MAX_BYTES)throw Error('Ukuran audio wajib 1 byte sampai 16 MB');
  if(!(/\.(mp3|wav|m4a|aac|ogg|webm)$/i.test(file.name)||file.type.startsWith('audio/')))
    throw Error('Gunakan MP3, WAV, M4A, AAC, OGG atau WebM yang didukung browser');
  const context=window.UNOLuckSound?.channels?.()?.context;
  if(!context)throw Error('Audio decoder belum tersedia. Pilih START WITH SOUND dahulu.');
  const bytes=await file.arrayBuffer();
  const decoded=await context.decodeAudioData(bytes.slice(0));
  if(!decoded.duration||!Number.isFinite(decoded.duration))throw Error('Durasi audio tidak valid');
  await writeFile(key,file);
  bufferCache.set('draft:'+key,decoded);
  profiles[key]={custom:true,edited:true,fileName:file.name,fileDuration:decimals(decoded.duration),
    start:0,stop:decimals(decoded.duration),fadeIn:0,fadeOut:0,
    ...(key==='background-music'?{repeat:getRepeat(key)}:{})};
  save();
  if(hasAdminKey())await publishCue(key);
  if(key==='soft-tech-splash-screen'&&splashUrl){
    URL.revokeObjectURL(splashUrl);splashUrl=null;
  }
  if(key==='background-music')window.UNOLuckSound?.refreshMusic?.();
  return profile(key);
}
function stopNode(item,fade=0){
  if(!item)return;
  try{
    const {context}=channel(),now=context.currentTime;
    item.envelope.gain.cancelScheduledValues(now);
    item.envelope.gain.setValueAtTime(Math.max(.0001,item.envelope.gain.value),now);
    item.envelope.gain.linearRampToValueAtTime(.0001,now+fade);
    item.source.stop(now+fade+.01);
  }catch(_){try{item.source.stop();}catch(_){}}
}
function stopPreview(){
  stopNode(preview,0.04);preview=null;
  if(fallbackPreview)stopFallback();
}
function stopCelebration(){
  // Invalidate an in-flight IndexedDB/decode request as well as the playing node.
  if(fallbackKey?.startsWith('jackpot-'))stopFallback();
  celebrationRequest++;
  if(celebrationNode){stopNode(celebrationNode,0.065);celebrationNode=null;}
}
async function segmentDuration(key){
  try{
    const buffer=await getBuffer(key);
    return buffer?limits(key,buffer.duration).length:0;
  }catch(error){
    const duration=Number(liveProfile(key)?.fileDuration)||0;
    return duration?limits(key,duration).length:0;
  }
}
function stopLoop(){
  if(fallbackKey==='background-music')stopFallback();
  loopSerial++;
  if(loop){stopNode(loop,loop.bounds.fadeOut);loop=null;}
}
async function play(key,{looping=false,forPreview=false}={}){
  if(!known.has(key))return false;
  if(forPreview)stopPreview();
  if(looping)stopLoop();
  const isJackpot=key.startsWith('jackpot-')&&!forPreview;
  if(isJackpot)stopCelebration();
  const jackpotToken=celebrationRequest;
  const serial=loopSerial;
  try{
    if(window.UNOLuckSound?.webAudioState!=='running'){
      const ok=await playFallback(key,{looping,forPreview,
        token:isJackpot?jackpotToken:null});
      return ok;
    }
    const {context,fx,music}=channel();
    const buffer=await getBuffer(key,{draft:forPreview});
    if(!buffer)return false;
    if(looping&&serial!==loopSerial)return false;
    if(isJackpot&&jackpotToken!==celebrationRequest)return false;
    const bounds=limits(key,buffer.duration,{draft:forPreview});
    const source=context.createBufferSource(),envelope=context.createGain();
    const now=context.currentTime+.012;
    const repeat=looping && getRepeat(key);
    source.buffer=buffer;
    source.loop=repeat;
    if(repeat){source.loopStart=bounds.start;source.loopEnd=bounds.stop;}
    source.connect(envelope).connect(looping||key==='background-music'?music:fx);
    const fadeIn=Math.min(bounds.fadeIn,bounds.length/2);
    envelope.gain.setValueAtTime(fadeIn>0?.0001:1,now);
    if(fadeIn>0)envelope.gain.linearRampToValueAtTime(1,now+fadeIn);
    if(!repeat && bounds.fadeOut>0){
      const startOut=now+bounds.length-bounds.fadeOut;
      envelope.gain.setValueAtTime(1,startOut);
      envelope.gain.linearRampToValueAtTime(.0001,now+bounds.length);
    }
    const item={source,envelope,bounds};
    if(looping){
      if(repeat)source.start(now,bounds.start);
      else source.start(now,bounds.start,bounds.length);
      loop=item;
      source.onended=()=>{if(loop===item)loop=null;};
    }else{
      source.start(now,bounds.start,bounds.length);
      if(forPreview){preview=item;}
      if(isJackpot){item.key=key;celebrationNode=item;}
      source.onended=()=>{
        if(preview===item)preview=null;
        if(celebrationNode===item)celebrationNode=null;
      };
    }
    return true;
  }catch(error){
    lastError=String(error?.message||error);
    console.warn('[UNO SOUND STUDIO]',key,lastError);return false;
  }
}
async function previewCue(key){
  const ok=await window.UNOLuckSound?.unlock();
  if(!ok&&!mediaUnlocked&&!isIOS())
    throw Error('Browser memblokir audio. Sentuh tombol audio terlebih dahulu.');
  const played=await play(key,{forPreview:true});
  if(!played)throw Error(lastError||'Audio tidak tersedia. Upload file untuk cue ini.');
  return true;
}
async function reset(key){
  stopPreview();if(key==='background-music')stopLoop();
  try{await removeFile(key);}catch(_){/* No DB for bundled-only sound. */}
  delete profiles[key];bufferCache.delete('draft:'+key);save();
  if(hasAdminKey())await publishCue(key,{remove:true});
  if(key==='soft-tech-splash-screen'&&splashUrl){
    URL.revokeObjectURL(splashUrl);splashUrl=null;
  }
  if(key==='background-music')window.UNOLuckSound?.refreshMusic?.();
}
const element=(tag,cls,text)=>{
  const node=document.createElement(tag);
  if(cls)node.className=cls;
  if(text!==undefined)node.textContent=text;
  return node;
};
function show(host){
  host.replaceChildren();
  host.classList.add('sound-studio');
  host.append(element('p','studio-note',
    'SOUND CLOUD: Semua perangkat memainkan audio dan pengaturan yang dipublikasikan dari desktop. Upload/edit lokal tetap tersimpan sampai Anda publish.'));
  host.append(element('p','studio-note',
    'Safari iPhone hanya dapat mengeluarkan suara setelah START WITH SOUND disentuh.'));
  const cloudBox=element('section','studio-cloud-panel');
  const cloudHeading=element('strong','studio-cloud-heading','☁ SHARED SOUND CLOUD');
  const cloudInfo=element('p','studio-cloud-status');
  const statusText=()=>{
    const state=cloudStatus();
    const unpublished=KEYS.filter(([key])=>{
      const local=profiles[key];
      return Boolean(local&&(local.custom||local.edited)&&
        (!cloudProfiles.has(key)||local.fileName!==cloudProfiles.get(key)?.fileName));
    }).length;
    const auth=state.admin?' · ADMIN AKTIF':' · READ-ONLY';
    cloudInfo.textContent=state.ready?
      (state.online?
        'TERHUBUNG · '+state.online+' / 12 kanal dipublikasikan'+auth+
        (unpublished?' · '+unpublished+' draft lokal perlu PUBLISH':''):
        'TERHUBUNG · CLOUD MASIH KOSONG (0/12). Audio desktop BELUM dipublikasikan. Verifikasi admin lalu pilih PUBLISH ALL.') :
      ('SOUND CLOUD TIDAK TERHUBUNG · '+(state.error||'menunggu server')+
        '. Setting desktop tidak dapat dipakai di mobile sampai cloud pulih.');
  };
  const syncButton=element('button','studio-cloud-button','↻ REFRESH CLOUD');
  syncButton.type='button';
  syncButton.addEventListener('click',async()=>{
    cloudInfo.textContent='Memperbarui sound semua perangkat…';
    await syncCloud(true);statusText();
  });
  const adminSection=element('details','studio-cloud-admin');
  const adminTitle=element('summary',null,'PUBLISH SOUND DARI DESKTOP · ADMIN');
  const adminGuide=element('p','studio-note',
    'Kunci hanya ada di Railway → uno-luck-web → staging → Variables → UNO_SOUND_ADMIN_TOKEN. Kunci disimpan pada tab ini, tidak dikirim ke perangkat pemain.');
  const keyInput=element('input','studio-admin-key');
  keyInput.type='password';keyInput.autocomplete='off';
  keyInput.placeholder='Masukkan kunci admin (32+ karakter)';
  keyInput.setAttribute('aria-label','Kunci admin Sound Cloud');
  const login=element('button','studio-cloud-button','VERIFIKASI KUNCI');
  login.type='button';
  const publish=element('button','studio-cloud-button','☁ PUBLISH ALL 12 SOUND LIST');
  publish.type='button';
  const publishStatus=element('p','studio-cloud-status');
  login.addEventListener('click',async()=>{
    publishStatus.textContent='Memverifikasi admin…';
    try{await verifyAdminKey(keyInput.value);
      keyInput.value='';publishStatus.textContent='Admin terverifikasi · upload & SAVE akan otomatis publish.';
      statusText();
    }catch(error){publishStatus.textContent='GAGAL: '+error.message;}
  });
  publish.addEventListener('click',async()=>{
    publish.disabled=true;publishStatus.textContent='Menyiapkan file desktop…';
    try{
      const count=await publishAll((n,total,key)=>{
        publishStatus.textContent='Mengirim '+n+' / '+total+' · '+key;
      });
      publishStatus.textContent=count+' sound desktop berhasil dipublikasikan. iPhone memakai versi yang sama setelah refresh.';
      statusText();
    }catch(error){
      publishStatus.textContent='PUBLISH TERHENTI: '+error.message;
    }finally{publish.disabled=false;}
  });
  adminSection.append(adminTitle,adminGuide,keyInput,login,publish,publishStatus);
  cloudBox.append(cloudHeading,cloudInfo,syncButton,adminSection);
  host.append(cloudBox);
  statusText();
  void syncCloud().then(()=>{if(cloudBox.isConnected)statusText();});
  window.addEventListener('uno:sound-cloud-synced',()=>{
    if(cloudBox.isConnected)statusText();
  });
  for(const [key,title,defaultSample] of KEYS){
    const details=element('details','studio-cue');
    const summary=element('summary','studio-title',title);
    details.append(summary);
    const body=element('div','studio-body');
    const status=element('p','studio-status');
    const form=element('div','studio-edit-grid');
    const values={};
    const fields=[
      ['start','START (s)'],['stop','STOP (s)'],['duration','DURATION (s)'],
      ['fadeIn','FADE IN (s)'],['fadeOut','FADE OUT (s)']
    ];
    for(const [field,label] of fields){
      const wrap=element('label','studio-field',label);
      const input=element('input');
      input.type='number';input.step='.05';input.min='0';input.inputMode='decimal';
      // The <details> toggle event fires asynchronously after the user opens
      // a cue. Leave inputs locked from creation until paint() hydrates them.
      input.disabled=true;
      input.setAttribute('aria-label',title+' '+label);
      input.name=key+'-'+field;
      values[field]=input;wrap.append(input);form.append(wrap);
    }

    // Native, accessible sliders complement exact numeric controls on every cue.
    const timeline=element('div','studio-timeline');
    const rail=element('div','studio-timeline-rail');
    const selected=element('div','studio-timeline-selection');
    rail.append(selected);
    const timeReadout=element('div','studio-timeline-label','START 0.00 s  ·  STOP 0.00 s');
    timeline.append(rail,timeReadout);
    const sliderPanel=element('div','studio-slider-panel');
    const sliders={};
    const sliderValues={};
    for(const [field,label] of [
      ['start','START'],['stop','STOP'],['duration','DURATION'],
      ['fadeIn','FADE IN'],['fadeOut','FADE OUT']
    ]){
      const wrap=element('label','studio-slider-row');
      const header=element('span','studio-slider-heading');
      header.append(element('strong',null,label));
      const output=element('output','studio-slider-value','0.00 s');
      header.append(output);
      const slider=element('input','studio-range');
      slider.type='range';slider.step='0.01';slider.min='0';slider.max='1';
      slider.value='0';slider.disabled=true;slider.dataset.field=field;
      slider.name=key+'-'+field+'-slider';
      slider.setAttribute('aria-label',title+' '+label+' slider');
      slider.setAttribute('aria-valuetext','0.00 seconds');
      slider.addEventListener('input',()=>{
        values[field].value=slider.value;
        if(field==='duration'){
          const start=Number(values.start.value)||0;
          values.stop.value=String(decimals(Math.min(actualDuration,start+Number(slider.value))));
        }else if(field==='start'||field==='stop'){
          values.duration.value=String(decimals(Number(values.stop.value)-Number(values.start.value)));
        }
        updateSliderView();
      });
      wrap.append(header,slider);
      sliderPanel.append(wrap);
      sliders[field]=slider;sliderValues[field]=output;
    }
    let repeatInput=null;
    const repeatRow=element('label','studio-repeat-row');
    if(key==='background-music'){
      repeatInput=element('input','studio-repeat-input');
      repeatInput.type='checkbox';repeatInput.name='background-music-repeat';
      repeatInput.disabled=true;
      repeatInput.checked=getDraftRepeat(key);
      repeatInput.setAttribute('aria-label','REPEAT BACKGROUND MUSIC');
      const repeatTitle=element('span','studio-repeat-label','REPEAT BACKGROUND MUSIC');
      const repeatState=element('strong','studio-repeat-state',repeatInput.checked?'ON':'OFF');
      repeatInput.addEventListener('change',()=>{
        setRepeat(key,repeatInput.checked);
        repeatState.textContent=repeatInput.checked?'ON':'OFF';
        status.textContent=repeatInput.checked?'Repeat ON · Musik mengulang bagian START–STOP.':
          'Repeat OFF · Musik dimainkan satu kali sesuai durasi START–STOP.';
      });
      repeatRow.append(repeatInput,repeatTitle,repeatState);
    }
    let actualDuration=0;
    const updateSliderView=()=>{
      const dur=actualDuration, read=name=>Number(values[name].value)||0;
      const start=clamp(read('start'),0,dur);
      const stop=clamp(read('stop'),start,dur);
      const span=Math.max(0,stop-start);
      const fadeIn=clamp(read('fadeIn'),0,span);
      const fadeOut=clamp(read('fadeOut'),0,span);
      const limits={
        start:[0,Math.max(0,stop-.02)],stop:[Math.min(dur,start+.02),dur],
        duration:[.02,Math.max(.02,dur-start)],
        fadeIn:[0,Math.max(0,span-fadeOut)],fadeOut:[0,Math.max(0,span-fadeIn)]
      };
      for(const field of Object.keys(sliders)){
        const slider=sliders[field],value=field==='start'?start:field==='stop'?stop:
          field==='duration'?span:field==='fadeIn'?fadeIn:fadeOut;
        slider.min=String(decimals(limits[field][0]));
        slider.max=String(decimals(Math.max(limits[field][0],limits[field][1])));
        slider.value=String(decimals(value));
        slider.disabled=dur<=0;
        sliderValues[field].textContent=decimals(value).toFixed(2)+' s';
        slider.setAttribute('aria-valuetext',decimals(value).toFixed(2)+' seconds');
      }
      selected.style.left=(dur?100*start/dur:0)+'%';
      selected.style.width=(dur?100*span/dur:0)+'%';
      timeReadout.textContent='START '+start.toFixed(2)+' s   ·   STOP '+
        stop.toFixed(2)+' s   ·   DURATION '+span.toFixed(2)+' s';
    };
    const setStatus=text=>{status.textContent=text;};
    const setEditorBusy=busy=>{
      Object.values(values).forEach(input=>{input.disabled=busy;});
      if(repeatInput)repeatInput.disabled=busy;
    };
    let paintSeq=0;
    const paint=async()=>{
      const seq=++paintSeq;
      setEditorBusy(true);
      setStatus('Membaca audio…');
      const p=profile(key);
      const shared=publishedProfile(key);
      try{
        const measured=await measure(key);
        if(seq!==paintSeq||!details.isConnected)return;
        actualDuration=measured;
        if(!actualDuration){
          updateSliderView();
          setStatus('Belum ada file default. Upload audio untuk cue ini.');
          return;
        }
        const r=limits(key,actualDuration,{draft:true});
        for(const name of ['start','stop','fadeIn','fadeOut'])values[name].value=String(decimals(r[name]));
        values.duration.value=String(decimals(r.length));
        if(repeatInput)repeatInput.checked=getDraftRepeat(key);
        if(repeatInput)repeatRow.querySelector('.studio-repeat-state').textContent=repeatInput.checked?'ON':'OFF';
        updateSliderView();
        setStatus((shared.revision?'☁ SHARED · ':'LOCAL · ')+
          (p.custom||p.source==='custom'?'CUSTOM: '+p.fileName:'DEFAULT: '+(defaultSample||'-'))+
          ' · File '+decimals(actualDuration)+' s');
      }catch(error){if(seq===paintSeq)setStatus('Audio tidak bisa dibaca: '+String(error.message));}
      finally{if(seq===paintSeq)setEditorBusy(actualDuration<=0);}
    };
    let updating=false;
    const sync=(changed)=>{
      if(updating)return;updating=true;
      const s=Number(values.start.value),t=Number(values.stop.value),d=Number(values.duration.value);
      if(changed==='duration')values.stop.value=String(decimals(s+d));
      else values.duration.value=String(decimals(t-s));
      updating=false;
      updateSliderView();
    };
    values.start.addEventListener('input',()=>sync('start'));
    values.stop.addEventListener('input',()=>sync('stop'));
    values.duration.addEventListener('input',()=>sync('duration'));
    values.fadeIn.addEventListener('input',updateSliderView);
    values.fadeOut.addEventListener('input',updateSliderView);
    const fileInput=element('input');
    fileInput.type='file';fileInput.accept='audio/*,.mp3,.wav,.m4a,.aac,.ogg,.webm';
    fileInput.setAttribute('aria-label','Upload '+title);
    fileInput.addEventListener('change',async()=>{
      if(!fileInput.files?.[0])return;
      ++paintSeq; // cancel stale audio measurements from the open-details event
      setEditorBusy(true);
      setStatus('Memeriksa dan menyimpan audio…');
      try{
        await window.UNOLuckSound?.unlock();
        await upload(key,fileInput.files[0]);
        await paint();setStatus('Audio tersimpan: '+fileInput.files[0].name+
          (hasAdminKey()?' · CLOUD PUBLISHED':' · LOKAL, belum dipublikasikan'));
      }catch(error){setEditorBusy(false);setStatus('UPLOAD GAGAL: '+error.message);}
    });
    const buttons=element('div','studio-buttons');
    const button=(label,fn)=>{
      const b=element('button','studio-button',label);
      b.type='button';b.addEventListener('click',fn);buttons.append(b);return b;
    };
    button('SAVE',async()=>{
      try{
        const args=Object.fromEntries(['start','stop','fadeIn','fadeOut'].map(k=>[k,values[k].value]));
        await configure(key,args);setStatus(hasAdminKey()?
          'Setting disimpan di CLOUD · otomatis untuk semua perangkat.':
          'Setting disimpan LOKAL · masukkan kunci admin dan PUBLISH untuk sinkronisasi.');
      }catch(error){setStatus('GAGAL: '+error.message);}
    });
    button('▶ PREVIEW',async()=>{
      setStatus('Memutar preview…');
      try{await previewCue(key);setStatus('Preview aktif. STOP untuk menghentikan.');}
      catch(error){setStatus('PREVIEW GAGAL: '+error.message);}
    });
    button('■ STOP',()=>{stopPreview();setStatus('Preview dihentikan.');});
    button('RESET',async()=>{
      try{await reset(key);await paint();
        setStatus(hasAdminKey()?'RESET di CLOUD selesai.':'Reset lokal saja · sound cloud tetap aktif.');
      }catch(error){setStatus('RESET GAGAL: '+error.message);}
    });
    body.append(status,fileInput,timeline,sliderPanel,form);
    if(repeatInput)body.append(repeatRow);
    body.append(buttons);details.append(body);host.append(details);
    details.addEventListener('toggle',()=>{if(details.open)paint();});
  }
}
window.UNOLuckSoundStudio={show,install(){window.UNOLuckSound?.installStudio?.(this);},
  isCustomized,play,stopLoop,stopPreview,stopCelebration,segmentDuration,
  prepareSplashMedia,playSplashGesture,isIOS,
  syncCloud,cloudStatus,publishedProfile,verifyAdminKey,publishCue,publishAll,
  publishMixer,schedulePublishMixer,hasAdminKey,
  profile,measure,configure,upload,reset,previewCue,getRepeat,setRepeat,
  get cues(){return KEYS.map(([key,label])=>({key,label}));},
  get lastError(){return lastError;},get splashError(){return splashError;},
  get mediaUnlocked(){return mediaUnlocked;},
  get activeCelebrationCue(){
    return celebrationNode?.key||fallbackKey?.startsWith('jackpot-')&&fallbackKey||null;
  }};
window.UNOLuckSoundStudio.install();
void syncCloud();
document.addEventListener('visibilitychange',()=>{
  if(!document.hidden)void syncCloud(true);
});
setInterval(()=>{if(!document.hidden)void syncCloud(true);},45000);
})();