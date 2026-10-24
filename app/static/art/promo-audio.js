/* Dedicated promo media lanes. No Sound Cloud profile/mixer mutations.
 * The separate speech + explosion and full-length tadaa cannot be cut off
 * by Turbo's LED wheel or by the regular SFX singleton.
 */
(() => {
'use strict';
const $=name=>document.querySelector('audio[data-promo-audio="'+name+'"]');
const MEDIA={
  gift:'/assets/audio/free-spin-gift.wav',
  tadaa:'/assets/audio/auto-tadaa.wav'
};
const durations={gift:3800,tadaa:2950};
const players=new Map();
const tasks=new Map();
let lastError='';
function get(name){
  if(players.has(name))return players.get(name);
  const audio=document.createElement('audio');
  audio.dataset.promoAudio=name;
  audio.setAttribute('playsinline','');
  audio.playsInline=true;
  audio.preload='auto';audio.src=MEDIA[name];
  audio.hidden=true;
  document.body.append(audio);
  players.set(name,audio);
  return audio;
}
function prime(){
  // Called directly from the Auto Start or explicit PLAY WITH SOUND tap.
  // Nothing is overwritten in the shared Sound Cloud mixer.
  for(const name of Object.keys(MEDIA)){
    const audio=get(name);
    audio.load();
    if(audio.readyState>=1)continue;
    audio.muted=true;
    try{
      const p=audio.play();
      void Promise.resolve(p).then(()=>{
        audio.pause();audio.currentTime=0;audio.muted=false;
      }).catch(()=>{audio.muted=false;});
    }catch(_){audio.muted=false;}
  }
}
function stop(name){
  const audio=players.get(name);
  if(audio){audio.pause();try{audio.currentTime=0;}catch(_){}}
  const task=tasks.get(name);
  if(task){task.finish(false);tasks.delete(name);}
}
function play(name,{volume=1}={}){
  if(!MEDIA[name])return Promise.resolve(false);
  const current=tasks.get(name);
  if(current)return current.done;
  const audio=get(name);
  let end;
  const done=new Promise(resolve=>{end=resolve;});
  let timer=0,settled=false;
  const onEnded=()=>finish(true);
  const onError=()=>finish(false);
  const finish=ok=>{
    if(settled)return;
    settled=true;
    clearTimeout(timer);
    audio.removeEventListener('ended',onEnded);
    audio.removeEventListener('error',onError);
    tasks.delete(name);
    end(ok);
  };
  tasks.set(name,{done,finish});
  try{
    // IMPORTANT: .play() is reached synchronously from the user gesture for
    // retry. If delayed Safari autoplay is denied, UI shows a retry CTA.
    audio.muted=false;audio.defaultMuted=false;
    audio.volume=Math.max(0,Math.min(1,Number(volume)||1));
    if(!audio.paused)audio.pause();
    try{audio.currentTime=0;}catch(_){}
    audio.addEventListener('ended',onEnded,{once:true});
    audio.addEventListener('error',onError,{once:true});
    const pending=audio.play();
    void Promise.resolve(pending).then(()=>{
      timer=setTimeout(()=>finish(false),durations[name]+900);
    }).catch(error=>{
      lastError=name+': '+String(error?.name||error?.message||error);
      finish(false);
    });
  }catch(error){
    lastError=name+': '+String(error?.message||error);
    finish(false);
  }
  return done;
}
function playGift(){return play('gift');}
function playTadaa(){return play('tadaa');}
window.UNOLuckPromoAudio={
  prime,playGift,playTadaa,stop,
  get lastError(){return lastError;},
  get status(){return {giftLoaded:get('gift').readyState>=1,
    tadaaLoaded:get('tadaa').readyState>=1,
    active:[...tasks.keys()],lastError};}
};
})();
