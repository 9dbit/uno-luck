/* DEV-05: presentation only. Never touch game state, bets, RNG, sound or accounts. */
(() => {
  'use strict';
  const area=document.querySelector('.title-area');
  const wordmark=document.getElementById('dragon-title-art');
  if(!area||!wordmark)return;
  const visible=()=>{
    if(wordmark.complete&&wordmark.naturalWidth>0&&wordmark.naturalHeight>0){
      area.classList.add('is-art-ready');
      area.dataset.titleAsset='loaded';
    }
  };
  const fallback=()=>{
    area.classList.remove('is-art-ready');
    area.dataset.titleAsset='fallback-text';
  };
  wordmark.addEventListener('load',visible,{once:true});
  wordmark.addEventListener('error',fallback,{once:true});
  if(wordmark.complete){
    if(wordmark.naturalWidth>0)visible();
    else fallback();
  }
})();
