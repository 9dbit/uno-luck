/* UNO LUCK PWA viewport: size from the visible iOS screen, not an optimistic
 * 100vh. Keep the gold pointer, all nine LED cards and actions inside the
 * actual wheel row without scrolling the body. */
(() => {
  'use strict';
  const root=document.documentElement;
  let raf=0;
  function update(){
    raf=0;
    const visual=window.visualViewport;
    const height=Math.max(260,Math.floor(Math.min(
      window.innerHeight||visual?.height||window.screen.height,
      visual?.height||window.innerHeight||window.screen.height
    )));
    root.style.setProperty('--uno-viewport-height',height+'px');
    const game=document.getElementById('game-shell');
    const area=game?.querySelector('.wheel-area');
    if(!area)return;
    const rect=area.getBoundingClientRect();
    if(rect.height>0&&rect.width>0){
      const limit=Math.floor(Math.min(rect.width*.985,rect.height*.965));
      game.style.setProperty('--uno-wheel-size',Math.max(1,limit)+'px');
    }
  }
  const schedule=()=>{
    if(raf)return;
    raf=requestAnimationFrame(update);
  };
  window.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('orientationchange',schedule,{passive:true});
  window.visualViewport?.addEventListener('resize',schedule,{passive:true});
  window.visualViewport?.addEventListener('scroll',schedule,{passive:true});
  window.addEventListener('pageshow',schedule);
  window.addEventListener('uno:boot-finished',schedule);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule,{once:true});
  else schedule();
  window.UNOLuckViewport={refresh:schedule};
})();