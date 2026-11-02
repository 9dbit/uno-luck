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
  const playError=find('boot-play-error');
  const studio=()=>window.UNOLuckSoundStudio;
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let released=false,started=false,splashReady=false,splashPlayed=false,musicReady=false;
  let retrying=false,attemptSerial=0;
  let preloadSettled=false;
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
  // One visible PLAY button is the only Safari activation and retry control.
  // Errors are explanatory text, not another confirmation card or button.
  function reportAudioError(reason){
    const message=String(reason||'Audio belum dapat diputar.').slice(0,220);
    if(playError){playError.textContent=message+' Ketuk PLAY WITH SOUND untuk mencoba lagi.';playError.hidden=false;}
    if(playButton){playButton.disabled=false;playButton.hidden=false;playButton.title=message;}
    if(playText)playText.textContent='PLAY WITH SOUND';
  }
  function clearAudioError(){
    if(playError){playError.hidden=true;playError.textContent='';}
    if(playButton)playButton.removeAttribute('title');
  }
  function prepareAgain(){
    if(retrying||started||released)return;
    retrying=true;playButton.disabled=true;
    // Read-only refresh. Never publish, reset, or overwrite saved Sound Cloud.
    void Promise.resolve(studio()?.syncCloud?.(true)).then(()=>Promise.all([
      studio()?.prepareSplashMedia?.(),
      localStorage.getItem('uno_orbit_music')==='off'?true:studio()?.prepareMusicMedia?.()
    ])).then(([s,m])=>{
      splashReady=Boolean(s);musicReady=Boolean(m);
      if(!splashReady)reportAudioError(studio()?.splashError||
        'File Soft Tech Splash belum tersedia di Sound Cloud.');
      else if(localStorage.getItem('uno_orbit_music')!=='off'&&!musicReady)
        reportAudioError(studio()?.lastError||'Background Music belum siap diputar.');
      else clearAudioError();
    }).catch(error=>reportAudioError('Gagal memuat audio: '+String(error?.message||error)))
      .finally(()=>{retrying=false;playButton.disabled=false;});
  }
  // Network handovers (including VPN changes) must not require a page reset.
  const recoverAudio=()=>{
    if(playButton&&preloadSettled&&!document.hidden&&!started&&!released&&
       (!splashReady||(localStorage.getItem('uno_orbit_music')!=='off'&&!musicReady)))prepareAgain();
  };
  window.addEventListener('online',recoverAudio);
  window.addEventListener('pageshow',recoverAudio);
  document.addEventListener('visibilitychange',recoverAudio);
  const recoveryTimer=setInterval(()=>{
    if(started||released){clearInterval(recoveryTimer);return;}
    recoverAudio();
  },8000);
  function onPlay(){
    if(released||started||retrying||!playButton||playButton.disabled)return;
    const musicWanted=localStorage.getItem('uno_orbit_music')!=='off';
    if(!splashReady||(musicWanted&&!musicReady)){
      reportAudioError(!splashReady?
        (studio()?.splashError||'File custom splash belum selesai dimuat.'):
        (studio()?.lastError||'Background Music belum selesai dimuat.'));
      prepareAgain();
      return;
    }
    clearAudioError();
    const activationAt=performance.now();
    // DO NOT await anything before either HTMLMediaElement.play() call.
    // Both elements are prepared before the trusted native click on Safari.
    let splashPromise,musicPromise=true;
    try{splashPromise=studio()?.playSplashGesture?.();}
    catch(error){reportAudioError('Soft Tech Splash: '+String(error?.message||error));return;}
    if(!splashPromise){reportAudioError('File custom Soft Tech Splash tidak tersedia.');return;}
    try{
      if(musicWanted)musicPromise=studio()?.armMusicOnSplashGesture?.();
    }catch(error){musicPromise=false;console.warn('[UNO SPLASH] BGM gesture',error);}
    try{void window.UNOLuckSound?.unlock?.();}
    catch(error){console.warn('[UNO SPLASH] audio context unlock',error);}
    const serial=++attemptSerial;
    playButton.disabled=true;
    // Never enter gameplay on an unconfirmed / rejected splash playback.
    void Promise.race([
      Promise.all([Promise.resolve(splashPromise),Promise.resolve(musicPromise)]),
      wait(8000).then(()=>[false,false])
    ]).then(([splashOk,musicOk])=>{
      if(serial!==attemptSerial||released)return;
      if(!splashOk||(musicWanted&&!musicOk)){
        studio()?.stopSplashAudio?.();
        if(musicWanted)studio()?.stopLoop?.();
        const reason=!splashOk?
          (studio()?.splashError||studio()?.lastError||'Safari menolak suara splash (NotAllowedError).'):
          (studio()?.lastError||'Safari belum mengaktifkan Background Music.');
        reportAudioError(reason);
        return;
      }
      splashPlayed=true;started=true;splashStartAt=activationAt;
      playButton.hidden=true;
      releaseGate();
    }).catch(error=>{
      if(serial!==attemptSerial)return;
      studio()?.stopSplashAudio?.();
      if(musicWanted)studio()?.stopLoop?.();
      reportAudioError('Playback gagal: '+String(error?.message||error));
    });
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
      .then(ok=>{
        splashReady=Boolean(ok);
        if(splashReady&&(localStorage.getItem('uno_orbit_music')==='off'||musicReady))clearAudioError();
        return splashReady;
      })
      .catch(error=>{console.warn('[UNO SPLASH] preload',error);return false;});
    const musicPromise=Promise.resolve(studio()?.prepareMusicMedia?.())
      .then(ok=>{musicReady=Boolean(ok);if(musicReady&&splashReady)clearAudioError();return musicReady;})
      .catch(error=>{console.warn('[UNO SPLASH] BGM preload',error);return false;});
    await Promise.race([preloadImage(soft),wait(2500)]);
    if(playButton){
      // Do not skip the only trusted Safari sound gesture. Avoid leaving
      // people stuck forever if the cloud is temporarily unavailable.
      splashReady=await Promise.race([splashPromise,wait(8500).then(()=>false)]);
      // Prefer ready BGM before enabling PLAY, without blocking forever if
      // a third-party browser delays its audio metadata.
      await Promise.race([musicPromise,wait(1400)]);
      preloadSettled=true;
      if(!splashReady){
        reportAudioError(studio()?.splashError||'Custom Soft Tech Splash belum tersedia.');
        console.warn('[UNO SPLASH] custom audio unavailable at activation');
      }
      playButton.disabled=false;
      if(playText)playText.textContent='PLAY WITH SOUND';
      if(splashReady&&localStorage.getItem('uno_orbit_music')!=='off'&&!musicReady)
        reportAudioError(studio()?.lastError||'Background Music belum siap.');
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
      if(playText)playText.textContent='PLAY WITH SOUND';
      reportAudioError('Terjadi kegagalan memuat intro. Audio harus aktif sebelum bermain.');
      void playGate.then(release);
    }else void release();
  });
})();
