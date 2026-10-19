/* UNO LUCK v1.1: hands-free visual boot. iOS audio unlock happens on the
 * player's first trusted gameplay interaction, never during autoplay.
 * No dialog, mute confirmation, hidden gate, or stuck audio failure state. */
(() => {
  'use strict';
  const find = id => document.getElementById(id);
  const cover = find('boot-overlay');
  const logo = find('boot-softtech');
  const banner = find('boot-banner');
  const loadingText = find('boot-loading-label');
  const track = find('boot-loading-track');
  const fill = find('boot-loading-fill');
  const percent = find('boot-loading-percent');
  const game = find('game-shell');
  let released = false;
  let splashReady=false, splashPlayed=false, splashAttempted=false;
  let splashPlaying=false,gestureReceived=false;
  const studio=()=>window.UNOLuckSoundStudio;
  // No Sound Studio writes. iOS user activation must reach media.play()
  // synchronously from the trusted pointer/keyboard event.
  function trySplashSound(fromGesture=false){
    if(released||splashPlayed||splashPlaying||!splashReady)return;
    if(!fromGesture&&splashAttempted)return;
    splashAttempted=true;
    splashPlaying=true;
    const result=studio()?.playSplashGesture?.();
    if(!result){splashPlaying=false;return;}
    void Promise.resolve(result).then(played=>{
      splashPlayed=Boolean(played);
      if(!played&&fromGesture)console.warn('[UNO SPLASH] iOS did not start custom audio');
    }).catch(error=>console.warn('[UNO SPLASH] playback blocked',error))
      .finally(()=>{splashPlaying=false;});
  }
  function onSplashGesture(){
    if(released)return;
    gestureReceived=true;
    if(splashReady){
      trySplashSound(true);
    }else{
      // This is a prewarm, not fake playback. The real splash sound still
      // requires a gesture once the network audio file becomes available.
      void window.UNOLuckSound?.unlock?.();
    }
  }
  // Entire visible splash is tappable. No extra SOUND button or message.
  cover.addEventListener('pointerdown',onSplashGesture,{passive:true});
  cover.addEventListener('keydown',event=>{
    if(event.key==='Enter'||event.key===' '){event.preventDefault();onSplashGesture();}
  });

  let current = 0;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  function progress(value,message) {
    const safe = Math.min(100,Math.max(current,Math.round(value)));
    current=safe;
    fill.style.width=safe+'%';
    track.setAttribute('aria-valuenow',String(safe));
    percent.textContent=safe+'%';
    if(message)loadingText.textContent=message;
  }
  function preloadImage(img) {
    if(img.complete&&img.naturalWidth)return Promise.resolve(true);
    const pending=new Promise(resolve=>{
      img.addEventListener('load',()=>resolve(true),{once:true});
      img.addEventListener('error',()=>resolve(false),{once:true});
    });
    if(typeof img.decode==='function')img.decode().catch(()=>{});
    return pending;
  }
  async function release() {
    if(released)return;
    released=true;
    banner.classList.add('is-fading');
    cover.classList.add('is-dismissing');
    await wait(reducedMotion?120:420);
    game.classList.remove('is-booting');
    game.removeAttribute('aria-hidden');
    cover.hidden=true;
    window.dispatchEvent(new Event('uno:boot-finished'));
  }
  async function runBoot() {
    const soft=find('boot-softtech-img'),bannerImage=find('boot-banner-img');
    // Read-only fetch: never change profiles, trim/fade or saved mixer.
    // Prefetch the exact published splash cue while the visual intro starts.
    // Browsers that permit autoplay can hear it immediately. iOS requires
    // the direct splash touch handler above for audible media playback.
    void studio()?.prepareSplashMedia?.().then(ready=>{
      splashReady=Boolean(ready);
      if(splashReady){
        // Desktop/previously allowed browsers may autoplay. iOS generally
        // blocks it; a real screen tap retriggers media.play() synchronously.
        trySplashSound(false);
      }
    }).catch(error=>console.warn('[UNO SPLASH] custom file unavailable',error));
    await Promise.race([preloadImage(soft),wait(2500)]);
    logo.classList.add('is-zooming');
    await wait(reducedMotion?350:1480);
    logo.classList.add('is-fading');
    await wait(reducedMotion?130:450);
    logo.hidden=true;
    await wait(reducedMotion?70:170);
    banner.hidden=false;
    requestAnimationFrame(()=>banner.classList.add('is-visible'));
    // Play the EXISTING custom loading cue only after audio has been unlocked.
    // It is not a new default, does not overwrite cue settings or force
    // forbidden Safari autoplay.
    if(splashPlayed||studio()?.mediaUnlocked){
      void window.UNOLuckSound?.playCue?.('loading-scene');
    }
    progress(7,'Memuat aset game…');
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
    await wait(reducedMotion?180:560);
    await release();
  }
  // A denied autoplay is normal on Safari. The first game interaction still
  // unlocks the existing Sound Studio mixer, without changing its settings.
  void runBoot().catch(error=>{
    console.warn('[UNO BOOT] visual boot fallback',error);
    void release();
  });
})();
