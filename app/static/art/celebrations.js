/* Five server-authoritative ranks. Preview mode never changes cards or credits. */
(() => {
  'use strict';
  const lookup = {
    1:{name:'DRAGON KING JACKPOT',multiplier:200,auto:6500},
    2:{name:'IMPERIAL FORTUNE',multiplier:80,auto:5300},
    3:{name:'PHOENIX COLOR BLAST',multiplier:30,auto:4400},
    4:{name:'GOLDEN MATCH',multiplier:10,auto:3450},
    5:{name:'LUCKY COLOR WIN',multiplier:2,auto:2750}
  };
  const $ = id=>document.getElementById(id);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let running=null;
  function close(){
    if(!running)return;
    const active=running;running=null;
    clearTimeout(active.timer);
    const overlay=$('celebration-overlay');overlay.classList.remove('shown');overlay.hidden=true;
    $('celebration-particles').replaceChildren();
    active.finish();
  }
  function sparks(rank){
    const surface=$('celebration-particles');surface.replaceChildren();
    if(reduced)return;
    const colors=rank===1?['#ffd252','#ed3c11','#fff1ac']:rank===2?['#e3be6e','#a33cff','#ff3562']:rank===3?['#f83cac','#fff19e','#ff7134']:rank===4?['#11fc9a','#f4c44a','#f7e986']:['#ff3b29','#ffe753','#ffb283'];
    const count=rank<=2?36:rank===3?26:18;
    const frag=document.createDocumentFragment();
    for(let i=0;i<count;i++){
      const e=document.createElement('span');e.className='celebration-spark';
      const angle=2*Math.PI*i/count;
      e.style.setProperty('--dx',Math.cos(angle)*(90+Math.random()*165)+'px');
      e.style.setProperty('--dy',Math.sin(angle)*(80+Math.random()*190)+'px');
      e.style.setProperty('--r',Math.floor(Math.random()*360)+'deg');
      e.style.setProperty('--spark-color',colors[i%colors.length]);
      e.style.setProperty('--delay',(i%9)*.028+'s');frag.append(e);
    }
    surface.append(frag);
  }
  function present(result,{preview=false,rank=null}={}){
    if(running)close();
    const isWin=result?.complete&&result.combo==='COLOR_MATCH'&&result.tier?.rank>=1;
    if(!preview&&!isWin)return Promise.resolve(false);
    const selected=preview?rank:result.tier.rank;
    if(!Number.isInteger(selected)||!lookup[selected])return Promise.resolve(false);
    const cfg=lookup[selected];
    if(!preview && (result.tier.title!==cfg.name||result.tier.multiplier!==cfg.multiplier))return Promise.resolve(false);
    const fmt=n=>new Intl.NumberFormat('id-ID').format(n);
    const overlay=$('celebration-overlay');
    overlay.dataset.rank=String(selected);
    overlay.setAttribute('aria-label',`${cfg.name} peringkat ${selected}${preview?' preview':''}`);
    $('celebration-art').src=`/assets/art/v3/tier-${selected}.webp`;
    $('celebration-title').textContent=cfg.name;
    $('celebration-amount').textContent=preview?`${cfg.multiplier}× · PREVIEW TANPA HADIAH`:
      `Kembali ${fmt(result.payout)} koin · Selisih ${result.delta>=0?'+':''}${fmt(result.delta)}`;
    $('celebration-preview').hidden=!preview;
    overlay.hidden=false;
    overlay.classList.remove('shown');
    sparks(selected);
    window.UNOLuckSound?.celebration(selected);
    requestAnimationFrame(()=>overlay.classList.add('shown'));
    return new Promise(resolve=>{
      running={finish:()=>resolve(true),timer:setTimeout(close,reduced?1350:cfg.auto)};
    });
  }
  $('celebration-continue')?.addEventListener('click',close);
  $('celebration-overlay')?.addEventListener('click',e=>{if(e.target.id==='celebration-overlay')close();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&running){e.preventDefault();close();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)close();});
  window.UNOLuckCelebration={present,close,get active(){return !!running;},registry:lookup};
})();
