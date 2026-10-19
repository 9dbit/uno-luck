/* UNO LUCK v0.5 splash and user-gesture audio bootstrap. */
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
  const actions = find('boot-ready-actions');
  const game = find('game-shell');
  const soundGate = find('boot-sound-gate');
  const soundStatus = find('boot-sound-status');
  const soundStart = find('boot-start-sound');
  const silentStart = find('boot-start-muted');
  let introStarted = false;
  let introStarting = false;
  let requestedSound = false;
  let released = false;
  let finishTimer = null;
  let current = 0;
  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  function progress(value, message){
    const safe = Math.min(100, Math.max(current, Math.round(value)));
    current = safe;
    fill.style.width = `${safe}%`;
    track.setAttribute('aria-valuenow', String(safe));
    percent.textContent = `${safe}%`;
    if(message) loadingText.textContent = message;
  }
  function preloadImage(element){
    if(element.complete && element.naturalWidth) return Promise.resolve(true);
    const result = new Promise(resolve => {
      element.addEventListener('load', () => resolve(true), {once:true});
      element.addEventListener('error', () => resolve(false), {once:true});
    });
    if(typeof element.decode === 'function') element.decode().catch(() => {});
    return result;
  }
  async function release(activateSound){
    if(released) return;
    released = true;
    clearTimeout(finishTimer);
    // Start music only when the intro finishes; it must not mask the splash cue.
    if(activateSound || requestedSound) {
      window.UNOLuckAudio?.unlock()?.catch?.(error => {
        console.warn('[UNO BOOT] music unlock failed', error);
      });
    }
    banner.classList.add('is-fading');
    cover.classList.add('is-dismissing');
    await wait(reducedMotion ? 150 : 430);
    game.classList.remove('is-booting');
    game.removeAttribute('aria-hidden');
    cover.hidden = true;
    window.dispatchEvent(new Event('uno:boot-finished'));
  }
  find('boot-with-audio').addEventListener('click', () => release(true));
  find('boot-continue').addEventListener('click', () => release(false));

  async function startIntro(withSound) {
    if (introStarted || introStarting) return;
    introStarting = true;
    requestedSound = withSound;
    soundStart.disabled = true;
    silentStart.disabled = true;
    if (withSound) {
      soundStatus.textContent = 'Mengaktifkan suara Soft Tech…';
      const studio = window.UNOLuckSoundStudio;
      const custom = Boolean(studio?.isCustomized('soft-tech-splash-screen'));
      const htmlFallback = Boolean(custom && studio?.isIOS?.());
      // IMPORTANT: Both .play() and AudioContext.resume() are initiated directly
      // in the click callstack. No asynchronous IndexedDB read before HTML play.
      const pendingMedia = htmlFallback?studio.playSplashGesture():null;
      const pendingUnlock = window.UNOLuckSound?.unlock();
      try {
        let played=false;
        if (htmlFallback){
          // Safari may keep the Web Audio context "interrupted" forever.
          // Do not await resume before the already-started HTML5 audio clip.
          played=Boolean(await pendingMedia);
          if (!played){
            const unlocked=Boolean(await pendingUnlock);
            if(unlocked)played=Boolean(await window.UNOLuckSound.playCue('soft-tech-splash-screen'));
          }
        }else{
          const unlocked=Boolean(await pendingUnlock);
          if(unlocked)played=Boolean(await window.UNOLuckSound.playCue('soft-tech-splash-screen'));
        }
        if(custom&&!played){
          const state=window.UNOLuckSound?.webAudioState||'unavailable';
          throw Error('Splash tidak bisa diputar (WebAudio '+state+'). '+
            (studio?.splashError||studio?.lastError||
            'Pastikan file audio tersedia lalu ketuk kembali.'));
        }
        soundStatus.textContent=played?'Soft Tech audio aktif · intro dimulai.':
          'Belum ada audio Soft Tech custom. Intro dilanjutkan.';
      } catch (error) {
        soundStatus.textContent = 'AUDIO GAGAL: ' + String(error?.message || error) +
          ' · Coba lagi atau pilih TANPA SUARA.';
        introStarting = false;
        requestedSound = false;
        soundStart.disabled = false;
        silentStart.disabled = false;
        return;
      }
    }
    introStarted = true;
    soundGate.hidden = true;
    runBoot().catch(error => {
      console.warn('[UNO BOOT] intro failed', error);
      release(false);
    });
  }
  // Safari iPhone needs a gesture on each new page load, including reload.
  soundStart.addEventListener('click', () => { void startIntro(true); });
  silentStart.addEventListener('click', () => { void startIntro(false); });
  const studio=window.UNOLuckSoundStudio;
  soundStart.disabled=true;
  soundStatus.textContent='Sinkronisasi audio desktop → mobile…';
  // Fetch the server-published catalog BEFORE the first iOS sound gesture.
  // Do not block the silent path if network or storage is temporarily down.
  Promise.resolve(studio?.syncCloud?.()).then(async(online)=>{
    if(online!==true)throw Error(studio?.cloudStatus?.()?.error||'Sound Cloud belum siap');
    const published=studio?.publishedProfile?.('soft-tech-splash-screen');
    const local=studio?.profile?.('soft-tech-splash-screen');
    const profile=published?.source==='custom'?published:local;
    if(profile?.custom||profile?.source==='custom'){
      if(studio?.isIOS?.()){
        soundStatus.textContent='Memuat audio Soft Tech dari '+(published?.source==='custom'?'cloud':'perangkat')+'…';
        await studio.prepareSplashMedia();
      }
      soundStatus.textContent='Audio siap: '+(profile.fileName||'Soft Tech')+
        (published?.source==='custom'?' · SINKRON CLOUD':' · LOKAL')+
        ' · ketuk START WITH SOUND.';
    }else{
      soundStatus.textContent='Ketuk START WITH SOUND · Audio publik menunggu konfigurasi.';
    }
  }).catch(error=>{
    console.warn('[UNO BOOT] sound sync',error);
    soundStatus.textContent='Audio cloud tidak tersedia: '+String(error?.message||error)+
      ' · Anda masih dapat masuk dengan suara lokal atau tanpa suara.';
  }).finally(()=>{if(!introStarted)soundStart.disabled=false;});

  async function runBoot(){
    const imgs = [find('boot-softtech-img'), find('boot-banner-img')];
    // Start downloading both brand assets immediately; do not start the intro
    // clock until the Soft Tech logo can be painted.
    await Promise.race([preloadImage(imgs[0]), wait(2500)]);
    await wait(reducedMotion ? 400 : 1350);
    logo.classList.add('is-fading');
    await wait(reducedMotion ? 180 : 570);
    logo.hidden = true;
    await wait(reducedMotion ? 100 : 230); // true black transition frame
    banner.hidden = false;
    if (requestedSound) window.UNOLuckSound?.playCue('loading-scene');
    requestAnimationFrame(() => banner.classList.add('is-visible'));
    progress(7, 'Memuat aset game…');

    // Progress cannot reach 100 until the art and server readiness settle.
    let loaded = false;
    const readyAssets = Promise.all([
      Promise.race([preloadImage(imgs[1]), wait(6500)]),
      Promise.race([
        fetch('/health', {cache:'no-store'}).then(r => r.ok).catch(() => false),
        wait(3500)
      ])
    ]).finally(() => { loaded = true; });
    const start = performance.now();
    while(!released){
      const elapsed = performance.now() - start;
      const target = Math.min(90, 7 + elapsed / 30);
      progress(target, current < 44 ? 'Memuat aset game…' : current < 75 ? 'Menyiapkan efek dan audio…' : 'Menghubungkan permainan…');
      if(loaded && elapsed >= 1750) break;
      if(elapsed > 7800) break; // never lock user out because a request stalled
      await wait(90);
    }
    if(released) return;
    await Promise.race([readyAssets, wait(50)]);
    progress(100, 'loading game system');
    actions.hidden = false;
    find('boot-loading-panel').classList.add('is-ready');
    // Auto-entry preserves the requested flow even without touching the screen;
    // on iPhone the first real gesture (e.g. PLACE) will unlock the audio.
    finishTimer = setTimeout(() => release(false), reducedMotion ? 1200 : 2900);
  }
  // The user selects sound ON or mute before the intro starts.
})();
