/* Refresh a restored PWA only after verifying a newer shell is reachable. */
(() => {
  'use strict';
  const release=document.querySelector('meta[name="uno-release"]')?.content;
  if(!release||release==='__UNO_RELEASE__')return;
  let checking=false,reloading=false;
  const safe=()=>document.getElementById('game-shell')?.classList.contains('is-booting')||
    window.UNOLuckCanReload?.()===true;
  async function check(){
    if(checking||reloading||document.hidden||!safe())return;
    checking=true;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),6000);
    try{
      const response=await fetch('/api/ui-version',{cache:'no-store',signal:controller.signal});
      if(!response.ok)return;
      const {release:next}=await response.json();
      if(!/^[a-f0-9]{20}$/.test(next)||next===release)return;
      const url=new URL(location.href);url.searchParams.set('_uno_release',next);
      const shell=await fetch(url,{cache:'no-store',signal:controller.signal});
      if(!shell.ok)return;
      const html=new DOMParser().parseFromString(await shell.text(),'text/html');
      if(html.querySelector('meta[name="uno-release"]')?.content!==next||!safe())return;
      reloading=true;
      location.replace(url.href);
    }catch(_){/* Retain the usable page while offline; retry on foreground/online. */}
    finally{clearTimeout(timer);checking=false;}
  }
  window.addEventListener('pageshow',check);
  window.addEventListener('online',check);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)void check();});
  setInterval(check,60000);
  void check();
})();
