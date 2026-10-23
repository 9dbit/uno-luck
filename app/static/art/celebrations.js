/* Five server-confirmed virtual tiers. Rank 1 can cover the screen;
   Ranks 2–5 replace only Dragon Spin. Preview never changes coins. */
(() => {
  'use strict';
  const lookup={
    1:{name:'DRAGON KING JACKPOT',multiplier:200,auto:6500},
    2:{name:'IMPERIAL FORTUNE',multiplier:80,auto:5300},
    3:{name:'PHOENIX COLOR BLAST',multiplier:30,auto:4400},
    4:{name:'GOLDEN MATCH',multiplier:10,auto:3450},
    5:{name:'LUCKY COLOR WIN',multiplier:2,auto:2750}
  };
  const $=id=>document.getElementById(id);
  const wheelArea=document.querySelector('.wheel-area');
  const overlay=$('celebration-overlay');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let running=null, generation=0;
  function restore(){
    overlay.classList.remove('shown','scope-wheel','scope-full');
    overlay.hidden=true;
    overlay.removeAttribute('data-scope');
    $('celebration-particles').replaceChildren();
    wheelArea?.classList.remove('has-celebration');
    overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('role','dialog');
    window.UNOLuckMatch?.clear();
  }
  function close(){
    generation++;
    const previous=running;running=null;
    if(previous)clearTimeout(previous.timer);
    window.UNOLuckSound?.stopCelebration?.();
    restore();
    if(previous)previous.finish();
  }
  function sparks(rank){
    const surface=$('celebration-particles');surface.replaceChildren();
    if(reduced)return;
    const colors=rank===1?['#ffd252','#ed3c11','#fff1ac']:rank===2?['#e3be6e','#a33cff','#ff3562']:rank===3?['#f83cac','#fff19e','#ff7134']:rank===4?['#11fc9a','#f4c44a','#f7e986']:['#ff3b29','#ffe753','#ffb283'];
    const count=rank===1?36:rank===2?25:rank===3?22:14;
    const frag=document.createDocumentFragment();
    for(let i=0;i<count;i++){
      const e=document.createElement('span');e.className='celebration-spark';
      const angle=2*Math.PI*i/count;
      e.style.setProperty('--dx',Math.cos(angle)*(60+Math.random()*115)+'px');
      e.style.setProperty('--dy',Math.sin(angle)*(55+Math.random()*125)+'px');
      e.style.setProperty('--r',Math.floor(Math.random()*360)+'deg');
      e.style.setProperty('--spark-color',colors[i%colors.length]);
      e.style.setProperty('--delay',(i%8)*.026+'s');frag.append(e);
    }
    surface.append(frag);
  }
  async function present(result,{preview=false,rank=null}={}){
    if(running)close();
    const isWin=result?.complete&&result.combo==='COLOR_MATCH'&&Number.isInteger(result.tier?.rank);
    if(!preview&&!isWin)return false;
    const selected=preview?rank:result.tier.rank;
    const cfg=lookup[selected];
    if(!Number.isInteger(selected)||!cfg)return false;
    if(!preview && (result.tier.title!==cfg.name || !Number.isInteger(result.tier.multiplier) || result.tier.multiplier<1 || result.tier.multiplier>10000 ||
      !Number.isInteger(result.stake) || result.stake<=0 || !Number.isInteger(result.payout) ||
      result.payout<0 || result.payout>result.stake*result.tier.multiplier || result.delta!==result.payout-result.stake ||
      result.cards?.length!==3 ||
      !result.cards?.every(card=>card.color===result.cards[0].color) ||
      (result.rules_version>=2 && result.tier.pattern!==result.pattern)))return false;
    const token=++generation;
    if(!preview){
      const announced=await window.UNOLuckMatch?.reveal(result);
      if(announced===false||token!==generation)return false;
    }else window.UNOLuckMatch?.clear();
    const local=selected!==1;
    if(local){wheelArea.append(overlay);wheelArea.classList.add('has-celebration');}
    else document.body.append(overlay);
    overlay.classList.toggle('scope-wheel',local);
    overlay.classList.toggle('scope-full',!local);
    overlay.dataset.scope=local?'wheel':'screen';
    overlay.dataset.rank=String(selected);
    overlay.setAttribute('role',local?'region':'dialog');
    overlay.setAttribute('aria-modal',String(!local));
    overlay.setAttribute('aria-label',`${cfg.name} peringkat ${selected}${preview?' preview':''}`);
    $('celebration-art').src=`/assets/art/v3/tier-${selected}.webp`;
    $('celebration-title').textContent=cfg.name;
    const matchedPattern=$('celebration-pattern');
    if(matchedPattern){
      matchedPattern.textContent=preview?'':String(result.tier?.rule||'');
      matchedPattern.hidden=preview||!matchedPattern.textContent;
    }
    const fmt=n=>new Intl.NumberFormat('id-ID').format(n);
    $('celebration-amount').textContent=preview?`${cfg.multiplier}× · PREVIEW TANPA HADIAH`:
      `PAYOUT ${fmt(result.payout)} koin · WIN ${result.delta>=0?'+':''}${fmt(result.delta)}`;
    $('celebration-preview').hidden=!preview;
    overlay.hidden=false;
    overlay.classList.remove('shown');
    sparks(selected);
    requestAnimationFrame(()=>{if(token===generation)overlay.classList.add('shown');});
    const done=new Promise(resolve=>{running={finish:()=>resolve(true),timer:null};});
    // Await the actual configured audio clip, so its START/STOP span drives the
    // celebration lifetime rather than a fixed tier timer.
    let audio={played:false,duration:0};
    try{audio=await window.UNOLuckSound?.celebration(selected)||audio;}
    catch(error){console.warn('[UNO JACKPOT] audio failed',selected,error);}
    if(token!==generation)return done; // CONTINUE or visibility change cancelled pending audio
    const configuredMs=Math.ceil(Math.max(0,Number(audio?.duration)||0)*1000)+100;
    const minimumMs=reduced?1400:cfg.auto;
    running.timer=setTimeout(close,Math.max(minimumMs,configuredMs));
    return done;
  }
  $('celebration-continue')?.addEventListener('click',close);
  overlay?.addEventListener('click',e=>{if(e.target===overlay)close();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&running){e.preventDefault();close();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)close();});
  window.UNOLuckCelebration={present,close,get active(){return Boolean(running);},registry:lookup};
})();
