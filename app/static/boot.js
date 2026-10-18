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
    if(activateSound){
      // Must be invoked synchronously during the user's click. Safari will
      // otherwise keep its AudioContext suspended.
      const gate = window.UNOLuckAudio;
      if(gate) {
        const ready = gate.unlock();
        Promise.resolve(ready).then(ok => {
          if(ok) gate.preview();
        }).catch(()=>{});
      }
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
    progress(100, 'Siap bermain!');
    actions.hidden = false;
    // Auto-entry preserves the requested flow even without touching the screen;
    // on iPhone the first real gesture (e.g. PLACE) will unlock the audio.
    finishTimer = setTimeout(() => release(false), reducedMotion ? 1200 : 2900);
  }
  runBoot().catch(() => release(false));
})();
