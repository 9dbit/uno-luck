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
    // Start prefetch without waiting on audio or network APIs.
    void window.UNOLuckSoundStudio?.syncCloud?.();
    await Promise.race([preloadImage(soft),wait(2500)]);
    logo.classList.add('is-zooming');
    await wait(reducedMotion?350:1480);
    logo.classList.add('is-fading');
    await wait(reducedMotion?130:450);
    logo.hidden=true;
    await wait(reducedMotion?70:170);
    banner.hidden=false;
    requestAnimationFrame(()=>banner.classList.add('is-visible'));
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
  // Never try to autoplay custom splash / background music on Safari.
  // The first SPIN, TURBO, AUTO, or other trusted tap resumes its AudioContext.
  void runBoot().catch(error=>{
    console.warn('[UNO BOOT] visual boot fallback',error);
    void release();
  });
})();
