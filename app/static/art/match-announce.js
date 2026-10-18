/* Conditional celebration title, never a static game heading.
   Only a completed server-confirmed COLOR_MATCH may show the asset. */
(() => {
  'use strict';
  const area=document.querySelector('.title-area');
  const art=document.getElementById('color-match-burst');
  const live=document.getElementById('match-live');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let generation=0;
  function clear(){
    generation++;
    area?.classList.remove('match-active');
    if(art)art.hidden=true;
    if(live)live.textContent='';
  }
  async function reveal(result){
    if(!result?.complete || result.combo!=='COLOR_MATCH' ||
       !result.tier?.rank || !result.cards || result.cards.length!==3 ||
       !(result.cards.every(card=>card.color===result.cards[0].color)))return false;
    clear();
    const marker=generation;
    art.hidden=false;
    area?.classList.add('match-active');
    if(live)live.textContent='COLOR MATCH!';
    if(!reduced)await new Promise(resolve=>setTimeout(resolve,580));
    return marker===generation;
  }
  window.UNOLuckMatch={reveal,clear,get visible(){return Boolean(art&&!art.hidden);}};
})();
