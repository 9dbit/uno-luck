/* UNO LUCK v1.1 splash: one visible PLAY button is the iOS audio
 * activation gesture. No mute confirmation, no Sound Studio mutation.
 * The classic game (which does not mount #boot-play) retains auto boot. */
(() => {
  'use strict';
  const find=id=>document.getElementById(id);
  const cover=find('boot-overlay');
  const logo=find('boot-softtech');
  const banner=find('boot-banner');
  const loadingText=find('boot-loading-label');
  const track=find('boot-loading-track');
  const fill=find('boot-loading-fill');
  const percent=find('boot-loading-percent');
  const game=find('game-shell');
  const playButton=find('boot-play');
  const playText=find('boot-play-text');
  const studio=()=>window.UNOLuckSoundStudio;
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let released=false,started=false,splashReady=false,splashPlayed=false;
  let splashStartAt=null,current=0;
  let releaseGate=()=>{};
  const playGate=new Promise(resolve=>{releaseGate=resolve;});

  function progress(value,message){
    const safe=Math.min(100,Math.max(current,Math.round(value)));
    current=safe;
    fill.style.width=safe+'%';
    track.setAttribute('aria-valuenow',String(safe));
    percent.textContent=safe+'%';
    if(message)loadingText.textContent=message;
  }
  function preloadImage(img){
    if(img.complete&&img.naturalWidth)return Promise.resolve(true);
    const pending=new Promise(resolve=>{
      img.addEventListener('load',()=>resolve(true),{once:true});
      img.addEventListener('error',()=>resolve(false),{once:true});
    });
    if(typeof img.decode==='function')void img.decode().catch(()=>{});
    return pending;
  }
  function onPlay(){
    if(released||started||!playButton||playButton.disabled)return;
    started=true;splashStartAt=performance.now();
    // Critical: HTML5 media.play() and WebAudio resume() must be called
    // DIRECTLY in the native click event, before awaiting any promises.
    // The published file is preloaded before enabling the PLAY button.
    try{
      const result=splashReady?studio()?.playSplashGesture?.():null;
      if(result)void Promise.resolve(result).then(playing=>{
        splashPlayed=Boolean(playing);
        if(!playing)console.warn('[UNO SPLASH] sound blocked by browser');
      }).catch(error=>console.warn('[UNO SPLASH] sound',error));
    }catch(error){console.warn('[UNO SPLASH] sound',error);}
    try{void window.UNOLuckSound?.unlock?.();}
    catch(error){console.warn('[UNO SPLASH] audio unlock',error);}
    playButton.hidden=true;
    releaseGate();
  }
  if(playButton)playButton.addEventListener('click',onPlay);

  async function release(){
    if(released)return;
    released=true;
    banner.classList.add('is-fading');
    cover.classList.add('is-dismissing');
    await wait(reducedMotion?120:420);
    game.classList.remove('is-booting');
    game.removeAttribute('aria-hidden');
    cover.hidden=true;
    // The splash media player is not the background-music player. Finish
    // its selected trim here to avoid overlap with the gameplay BGM.
    studio()?.stopSplashAudio?.();
    window.dispatchEvent(new Event('uno:boot-finished'));
  }
  async function runBoot(){
    const soft=find('boot-softtech-img'),bannerImage=find('boot-banner-img');
    // Fetch the user's published Sound Cloud files, never create/edit a cue.
    // The first iPhone tap should not be spent on network/IndexedDB work.
    const splashPromise=Promise.resolve(studio()?.prepareSplashMedia?.())
      .then(Boolean)
      .catch(error=>{console.warn('[UNO SPLASH] preload',error);return false;});
    void studio()?.prepareMusicMedia?.();
    await Promise.race([preloadImage(soft),wait(2500)]);
    if(playButton){
      // Do not skip the only trusted Safari sound gesture. Avoid leaving
      // people stuck forever if the cloud is temporarily unavailable.
      splashReady=await Promise.race([splashPromise,wait(8500).then(()=>false)]);
      if(!splashReady){
        playButton.title='Sound belum siap. PLAY tetap dapat memulai game.';
        console.warn('[UNO SPLASH] custom audio unavailable at activation');
      }
      playButton.disabled=false;
      if(playText)playText.textContent=splashReady?'PLAY WITH SOUND':'PLAY';
      await playGate;
    }else{
      // Classic's legacy page has no PLAY button and retains auto entry.
      splashReady=await Promise.race([splashPromise,wait(500).then(()=>false)]);
    }
    logo.classList.add('is-zooming');
    await wait(reducedMotion?350:1480);
    logo.classList.add('is-fading');
    await wait(reducedMotion?130:450);
    logo.hidden=true;
    await wait(reducedMotion?70:170);
    banner.hidden=false;
    requestAnimationFrame(()=>banner.classList.add('is-visible'));
    // Do not interrupt the user-selected 7-second Soft Tech clip with
    // the Loading Scene fallback on iOS. No sound configuration changes.
    if(!playButton&&studio()?.mediaUnlocked)
      void window.UNOLuckSound?.playCue?.('loading-scene');
    progress(7,'Memuat aset game…');
    let loaded=false;
    const readyAssets=Promise.all([
      Promise.race([preloadImage(bannerImage),wait(5000)]),
      Promise.race([
        fetch('/health',{cache:'no-store'}).then(r=>r.ok).catch(()=>false),
        wait(3000)
      ])
    ]).finally(()=>{loaded=true;});
    const began=performance.now();
    while(!released){
      const elapsed=performance.now()-began;
      progress(Math.min(90,7+elapsed/29),
        current<44?'Memuat aset game…':current<75?
          'Menyiapkan permainan…':'Menghubungkan permainan…');
      if(loaded&&elapsed>=1550)break;
      if(elapsed>7200)break;
      await wait(90);
    }
    if(released)return;
    await Promise.race([readyAssets,wait(75)]);
    // Respect custom START/STOP of the splash clip so its fade-out can
    // actually finish before the gameplay BGM begins. Bound to 8.5 sec.
    if(playButton&&splashPlayed&&splashStartAt!==null){
      const cfg=studio()?.publishedProfile?.('soft-tech-splash-screen')||
        studio()?.profile?.('soft-tech-splash-screen');
      const duration=Number(cfg?.stop)-Number(cfg?.start);
      if(Number.isFinite(duration)&&duration>0){
        const target=Math.min(8500,duration*1000);
        const pending=Math.max(0,target-(performance.now()-splashStartAt));
        if(pending>0)await wait(pending);
      }
    }
    progress(100,'loading game system');
    await wait(reducedMotion?180:560);
    await release();
  }
  void runBoot().catch(error=>{
    console.warn('[UNO BOOT] fallback',error);
    // Do not bypass the explicit PLAY gate on the UNO LUCK PWA.
    if(playButton&&!started){
      playButton.disabled=false;
      if(playText)playText.textContent='PLAY';
      void playGate.then(release);
    }else void release();
  });
})();
