/* UNO LUCK v1.1: reliable splash audio on iPhone.
 * PLAY WITH SOUND is the single explicit iOS activation gesture.
 * Custom Sound Cloud trim/fade/repeat/mixer remain authoritative.
 */
(() => {
  'use strict';
  const find=id=>document.getElementById(id);
  const cover=find('boot-overlay'),logo=find('boot-softtech');
  const banner=find('boot-banner'),button=find('boot-play-sound');
  const buttonText=find('boot-play-label'),game=find('game-shell');
  const loadingText=find('boot-loading-label'),track=find('boot-loading-track');
  const fill=find('boot-loading-fill'),percent=find('boot-loading-percent');
  const studio=()=>window.UNOLuckSoundStudio;
  const wantMusic=()=>localStorage.getItem('uno_orbit_music')!=='off';
  const splashConfigured=()=>{
    const p=studio()?.publishedProfile?.('soft-tech-splash-screen')||
      studio()?.profile?.('soft-tech-splash-screen')||{};
    return p.custom===true||p.source==='custom';
  };
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  let released=false,accepted=false,current=0;
  let splashReady=false,bgmReady=false,preparing=null;
  let resolveStart;
  const started=new Promise(resolve=>{resolveStart=resolve;});

  function label(value){buttonText.textContent=value;}
  function progress(value,message){
    current=Math.min(100,Math.max(current,Math.round(value)));
    fill.style.width=current+'%';
    track.setAttribute('aria-valuenow',String(current));
    percent.textContent=current+'%';
    if(message)loadingText.textContent=message;
  }
  function preloadImage(img){
    if(img.complete&&img.naturalWidth)return Promise.resolve(true);
    return new Promise(resolve=>{
      img.addEventListener('load',()=>resolve(true),{once:true});
      img.addEventListener('error',()=>resolve(false),{once:true});
      if(typeof img.decode==='function')img.decode().catch(()=>{});
    });
  }
  async function prepareSound(){
    if(preparing)return preparing;
    button.disabled=true;label('MEMUAT SOUND...');
    preparing=(async()=>{
      // Cloud file is staged into HTML5 Audio BEFORE a user clicks.
      // Do not await inside the click: iOS discards the trusted activation.
      const results=await Promise.allSettled([
        studio()?.prepareSplashMedia?.(),
        wantMusic()?studio()?.prepareMusicMedia?.():Promise.resolve(true)
      ]);
      splashReady=results[0].status==='fulfilled'&&results[0].value===true;
      bgmReady=results[1].status==='fulfilled'&&results[1].value===true;
      // In an empty/staging-demo catalog there may not yet be a custom
      // splash clip. Do not lock game entry forever on a nonexistent file.
      if((splashReady||!splashConfigured())&&bgmReady){
        label('PLAY WITH SOUND');
        button.disabled=false;
        return true;
      }
      label('COBA MUAT SOUND LAGI');
      button.disabled=false;
      console.warn('[UNO BOOT] Audio not ready',results.map(x=>x.status));
      return false;
    })().finally(()=>{preparing=null;});
    return preparing;
  }
  // The only entry action. Both media.play() calls are started synchronously
  // inside this same trusted button click, before any Promise or await.
  button.addEventListener('click',()=>{
    if(accepted||released)return;
    if((!splashReady&&splashConfigured())||(wantMusic()&&!bgmReady)){
      void prepareSound();return;
    }
    accepted=true;
    button.disabled=true;
    button.hidden=true;
    const splash=studio()?.playSplashGesture?.();
    if(splash){
      void Promise.resolve(splash).then(ok=>{
        if(!ok)console.warn('[UNO BOOT] Safari could not play the splash soundtrack');
      }).catch(error=>console.warn('[UNO BOOT] Splash audio',error));
    }
    // Prime both engines in one activation: Web Audio for desktop/modern
    // Safari and muted HTML5 BGM for interrupted WhatsApp/PWA WebKit.
    void window.UNOLuckSound?.unlock?.();
    if(wantMusic()){
      const armed=studio()?.armMusicOnSplashGesture?.();
      if(armed)void Promise.resolve(armed).catch(
        error=>console.warn('[UNO BOOT] Music priming',error));
    }
    resolveStart();
  });

  async function release(){
    if(released)return;
    released=true;
    banner.classList.add('is-fading');
    cover.classList.add('is-dismissing');
    await wait(reducedMotion?110:420);
    game.classList.remove('is-booting');
    game.removeAttribute('aria-hidden');
    cover.hidden=true;
    window.dispatchEvent(new Event('uno:boot-finished'));
  }
  async function runBoot(){
    const soft=find('boot-softtech-img'),bannerImage=find('boot-banner-img');
    // Load real cloud clips, never change profiles or write Sound Cloud data.
    void prepareSound();
    await Promise.race([preloadImage(soft),wait(3000)]);
    // Remain on the Soft Tech splash until the person presses PLAY.
    // This ensures WebKit has the actual audio gesture before entering game.
    await started;
    logo.classList.add('is-zooming');
    await wait(reducedMotion?300:1480);
    logo.classList.add('is-fading');
    await wait(reducedMotion?120:450);
    logo.hidden=true;
    await wait(reducedMotion?50:170);
    banner.hidden=false;
    requestAnimationFrame(()=>banner.classList.add('is-visible'));
    // Do not replace the splash track with LOADING SCENE on the shared
    // Safari HTML5 cue player. The existing splash may still be playing.
    progress(7,'Memuat aset game...');
    let loaded=false;
    const readyAssets=Promise.all([
      Promise.race([preloadImage(bannerImage),wait(5000)]),
      Promise.race([
        fetch('/health',{cache:'no-store'}).then(r=>r.ok).catch(()=>false),
        wait(3000)
      ])
    ]).finally(()=>{loaded=true;});
    const start=performance.now();
    while(!released){
      const elapsed=performance.now()-start;
      progress(Math.min(90,7+elapsed/29),
        current<44?'Memuat aset game…':current<75?
          'Menyiapkan permainan…':'Menghubungkan permainan…');
      if(loaded&&elapsed>=1550)break;
      if(elapsed>7200)break;
      await wait(90);
    }
    if(released)return;
    await Promise.race([readyAssets,wait(75)]);
    progress(100,'loading game system');
    await wait(reducedMotion?160:500);
    await release();
  }
  void runBoot().catch(error=>{
    console.warn('[UNO BOOT] visual fallback',error);
    // Do not bypass the audio gesture with an automatic silent start.
    if(accepted)void release();
    else{button.disabled=false;label('COBA MUAT SOUND LAGI');}
  });
})();
