/* UNO LUCK v1.2: exact iPhone 15 Pro / Safari / standalone viewport.
 * CSS 100dvh is authoritative for Safari; 100lvh is used in standalone PWA
 * to paint behind the home-indicator. A visualViewport toolbar/scroll height
 * must never clamp the game into a short rectangle and expose a black stripe.
 * Keep wheel sizing independent of scroll/animation so WebKit paints smoothly.
 */
(() => {
  'use strict';
  const root=document.documentElement;
  const modernHeight=typeof CSS!=='undefined'&&CSS.supports?.('height','100dvh');
  let raf=0,lastHeight=-1,lastWheel=-1,lastShift=-1;
  const setPx=(target,name,value,last)=>{
    if(Math.abs(value-last)<1)return last;
    target.style.setProperty(name,Math.round(value)+'px');
    return Math.round(value);
  };
  function update(){
    raf=0;
    // CSS viewport units are more reliable than Math.min(innerHeight,
    // visualViewport.height) on iOS. Visual viewport can be 40-90px shorter
    // during toolbar animation even after it has stopped moving.
    if(modernHeight){
      if(root.style.getPropertyValue('--uno-viewport-height'))
        root.style.removeProperty('--uno-viewport-height');
    }else{
      const height=Math.max(260,Math.floor(
        window.innerHeight||root.clientHeight||window.visualViewport?.height||window.screen.height
      ));
      lastHeight=setPx(root,'--uno-viewport-height',height,lastHeight);
    }
    const game=document.getElementById('game-shell');
    const area=game?.querySelector('.wheel-area');
    if(!area)return;
    const rect=area.getBoundingClientRect();
    if(rect.height<=0||rect.width<=0)return;
    // Reserve a small, consistent downward offset. The upper cards and HUD
    // stay in place while the wheel fills the bottom section more naturally.
    // Side controls remain above the iPhone home-indicator safe area.
    const shift=Math.min(18,Math.max(6,rect.height*.029));
    // Contain the artwork inside the wheel row on short Safari heights
    // (e.g. iPhone viewport 393x659 or older 320x568). Oversizing by even
    // 8px cuts the dragon's bottom and the lower action buttons.
    // The caption is absolutely positioned over the bottom of this row.
    // Reserve its actual height so its dark backing never hides the dragon's
    // lower curve even when the complete square technically fits the row.
    const captionHeight=area.querySelector('.spin-caption')?.getBoundingClientRect().height||0;
    const size=Math.min(rect.width*.99,rect.height-shift-captionHeight-4);
    lastWheel=setPx(game,'--uno-wheel-size',Math.max(1,size),lastWheel);
    lastShift=setPx(game,'--uno-wheel-drop',shift,lastShift);
  }
  const schedule=()=>{
    if(raf)return;
    raf=requestAnimationFrame(update);
  };
  window.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('orientationchange',schedule,{passive:true});
  window.visualViewport?.addEventListener('resize',schedule,{passive:true});
  window.addEventListener('pageshow',schedule);
  window.addEventListener('uno:boot-finished',schedule);
  if(document.readyState==='loading')
    document.addEventListener('DOMContentLoaded',update,{once:true});
  else update(); // First paint must not wait for a Safari/WebKit animation frame.
  window.UNOLuckViewport={
    refresh(){
      if(raf){cancelAnimationFrame(raf);raf=0;}
      update(); // Manual/boot refresh is synchronous even in a throttled PWA.
    }
  };
})();
