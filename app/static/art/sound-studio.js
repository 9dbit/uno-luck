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
let database=null, preview=null, loop=null, loopSerial=0, lastError='';
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
async function getBuffer(key){
  if(bufferCache.has(key))return bufferCache.get(key);
  const entry=known.get(key);if(!entry)throw Error('Sound event tidak dikenal');
  const cfg=profiles[key]||{};
  let bytes;
  if(cfg.custom){
    const file=await readFile(key);
    if(!file)throw Error('File audio lokal tidak ditemukan. Upload ulang.');
    bytes=await file.arrayBuffer();
  }else{
    if(!entry[2])return null; // Two opening scenes intentionally have no default sample.
    const response=await fetch('/assets/audio/'+entry[2]+'.mp3',{cache:'force-cache'});
    if(!response.ok)throw Error('Audio tidak tersedia: '+response.status);
    bytes=await response.arrayBuffer();
  }
  const buffer=await channel().context.decodeAudioData(bytes.slice(0));
  bufferCache.set(key,buffer);
  return buffer;
}
function limits(key,duration){
  const current=profiles[key]||{};
  const start=clamp(current.start??0,0,Math.max(0,duration-.02));
  const stop=clamp(current.stop??duration,start+.01,duration);
  const length=stop-start;
  const fadeIn=clamp(current.fadeIn??0,0,length/2);
  const fadeOut=clamp(current.fadeOut??0,0,length/2);
  return {start,stop,length,fadeIn,fadeOut};
}
function isCustomized(key){
  const p=profiles[key];
  return Boolean(p&&(p.custom||p.edited));
}
function profile(key){return {...(profiles[key]||{})};}
function getRepeat(key){return key==='background-music' && profiles[key]?.repeat!==false;}
function setRepeat(key,enabled){
  if(key!=='background-music')throw Error('Repeat hanya untuk BACKGROUND MUSIC');
  profiles[key]={...profiles[key],repeat:Boolean(enabled),edited:true};
  save();
  window.UNOLuckSound?.refreshMusic?.();
  return getRepeat(key);
}
async function measure(key){const b=await getBuffer(key);return b?.duration||0;}
async function configure(key,settings){
  if(!known.has(key))throw Error('Sound event tidak dikenal');
  const length=await measure(key);
  if(!length)throw Error('Upload file audio terlebih dahulu');
  const start=Number(settings.start),stop=Number(settings.stop);
  const fi=Number(settings.fadeIn),fo=Number(settings.fadeOut);
  if(![start,stop,fi,fo].every(Number.isFinite)||start<0||stop>length+.001||stop-start<.02||
      fi<0||fo<0||fi+fo>stop-start+.001)throw Error('Rentang start/stop atau fade tidak valid');
  profiles[key]={...profiles[key],start:decimals(start),stop:decimals(Math.min(stop,length)),
    fadeIn:decimals(fi),fadeOut:decimals(fo),edited:true};
  save();
  if(key==='background-music')window.UNOLuckSound?.refreshMusic?.();
  return limits(key,length);
}
async function upload(key,file){
  if(!known.has(key))throw Error('Sound event tidak dikenal');
  if(!file||!file.size||file.size>MAX_BYTES)throw Error('Ukuran audio wajib 1 byte sampai 16 MB');
  if(!(/\.(mp3|wav|m4a|aac|ogg|webm)$/i.test(file.name)||file.type.startsWith('audio/')))
    throw Error('Gunakan MP3, WAV, M4A, AAC, OGG atau WebM yang didukung browser');
  const {context}=channel();
  const bytes=await file.arrayBuffer();
  const decoded=await context.decodeAudioData(bytes.slice(0));
  if(!decoded.duration||!Number.isFinite(decoded.duration))throw Error('Durasi audio tidak valid');
  await writeFile(key,file);
  bufferCache.set(key,decoded);
  profiles[key]={custom:true,edited:true,fileName:file.name,fileDuration:decimals(decoded.duration),
    start:0,stop:decimals(decoded.duration),fadeIn:0,fadeOut:0,
    ...(key==='background-music'?{repeat:getRepeat(key)}:{})};
  save();
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
function stopPreview(){stopNode(preview,0.04);preview=null;}
function stopLoop(){
  loopSerial++;
  if(loop){stopNode(loop,loop.bounds.fadeOut);loop=null;}
}
async function play(key,{looping=false,forPreview=false}={}){
  if(!known.has(key))return false;
  if(forPreview)stopPreview();
  if(looping)stopLoop();
  const serial=loopSerial;
  try{
    const {context,fx,music}=channel();
    const buffer=await getBuffer(key);
    if(!buffer)return false;
    if(looping&&serial!==loopSerial)return false;
    const bounds=limits(key,buffer.duration);
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
      if(forPreview){
        preview=item;source.onended=()=>{if(preview===item)preview=null;};
      }
    }
    return true;
  }catch(error){
    lastError=String(error?.message||error);
    console.warn('[UNO SOUND STUDIO]',key,lastError);return false;
  }
}
async function previewCue(key){
  const ok=await window.UNOLuckSound?.unlock();
  if(!ok)throw Error('Browser memblokir audio. Sentuh tombol audio terlebih dahulu.');
  const played=await play(key,{forPreview:true});
  if(!played)throw Error(lastError||'Audio tidak tersedia. Upload file untuk cue ini.');
  return true;
}
async function reset(key){
  stopPreview();if(key==='background-music')stopLoop();
  try{await removeFile(key);}catch(_){/* No DB for bundled-only sound. */}
  delete profiles[key];bufferCache.delete(key);save();
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
    '12 kanal efek. Upload audio pada perangkat ini, atur START / STOP / DURATION / FADE IN / FADE OUT, lalu PREVIEW. Audio tersimpan lokal di browser, bukan di server.'));
  host.append(element('p','studio-note',
    'Safari iPhone hanya mengizinkan suara splash/loading setelah ada interaksi pengguna yang membuka audio.'));
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
      input.setAttribute('aria-label',title+' '+label);
      input.name=key+'-'+field;
      values[field]=input;wrap.append(input);form.append(wrap);
    }
    let actualDuration=0;
    const setStatus=text=>{status.textContent=text;};
    const paint=async()=>{
      setStatus('Membaca audio…');
      const p=profile(key);
      try{
        actualDuration=await measure(key);
        if(!details.isConnected)return;
        if(!actualDuration){setStatus('Belum ada file default. Upload audio untuk cue ini.');return;}
        const r=limits(key,actualDuration);
        for(const name of ['start','stop','fadeIn','fadeOut'])values[name].value=String(decimals(r[name]));
        values.duration.value=String(decimals(r.length));
        setStatus((p.custom?'CUSTOM: '+p.fileName:'DEFAULT: '+(defaultSample||'-'))+' · File '+decimals(actualDuration)+' s');
      }catch(error){setStatus('Audio tidak bisa dibaca: '+String(error.message));}
    };
    let updating=false;
    const sync=(changed)=>{
      if(updating)return;updating=true;
      const s=Number(values.start.value),t=Number(values.stop.value),d=Number(values.duration.value);
      if(changed==='duration')values.stop.value=String(decimals(s+d));
      else values.duration.value=String(decimals(t-s));
      updating=false;
    };
    values.start.addEventListener('input',()=>sync('start'));
    values.stop.addEventListener('input',()=>sync('stop'));
    values.duration.addEventListener('input',()=>sync('duration'));
    const fileInput=element('input');
    fileInput.type='file';fileInput.accept='audio/*,.mp3,.wav,.m4a,.aac,.ogg,.webm';
    fileInput.setAttribute('aria-label','Upload '+title);
    fileInput.addEventListener('change',async()=>{
      if(!fileInput.files?.[0])return;
      setStatus('Memeriksa dan menyimpan audio…');
      try{
        await window.UNOLuckSound?.unlock();
        await upload(key,fileInput.files[0]);
        await paint();setStatus('Audio tersimpan: '+fileInput.files[0].name);
      }catch(error){setStatus('UPLOAD GAGAL: '+error.message);}
    });
    const buttons=element('div','studio-buttons');
    const button=(label,fn)=>{
      const b=element('button','studio-button',label);
      b.type='button';b.addEventListener('click',fn);buttons.append(b);return b;
    };
    button('SAVE',async()=>{
      try{
        const args=Object.fromEntries(['start','stop','fadeIn','fadeOut'].map(k=>[k,values[k].value]));
        await configure(key,args);setStatus('Setting disimpan pada perangkat ini.');
      }catch(error){setStatus('GAGAL: '+error.message);}
    });
    button('▶ PREVIEW',async()=>{
      setStatus('Memutar preview…');
      try{await previewCue(key);setStatus('Preview aktif. STOP untuk menghentikan.');}
      catch(error){setStatus('PREVIEW GAGAL: '+error.message);}
    });
    button('■ STOP',()=>{stopPreview();setStatus('Preview dihentikan.');});
    button('RESET',async()=>{await reset(key);await paint();});
    body.append(status,fileInput,form,buttons);details.append(body);host.append(details);
    details.addEventListener('toggle',()=>{if(details.open)paint();});
  }
}
window.UNOLuckSoundStudio={show,install(){window.UNOLuckSound?.installStudio?.(this);},
  isCustomized,play,stopLoop,stopPreview,profile,measure,configure,upload,reset,previewCue,getRepeat,setRepeat,
  get cues(){return KEYS.map(([key,label])=>({key,label}));},
  get lastError(){return lastError;}};
window.UNOLuckSoundStudio.install();
})();