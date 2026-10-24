/* UNO LUCK PAYOUT ticker. Live = settlement data only.
 * QA simulation is ALWAYS labeled "SIMULASI" and never impersonates winners.
 */
(() => {
'use strict';
const modeEl=document.getElementById('activity-mode');
const feedEl=document.getElementById('activity-feed');
const betEl=document.getElementById('activity-total');
const board=document.getElementById('activity-board');
if(!modeEl||!feedEl||!betEl||!board)return;
const money=n=>new Intl.NumberFormat('id-ID').format(n);
const aliases=['adit**','rizk**','sutr**','maxw**','zom**','bayu**',
    'faja**','putr**','dima**','wahy**','bima**','nugg**','arif**',
    'fitr**','rani**','agus**','bagu**','hend**'];
const sample=[{name:'maxw**',payout_coin:88000},
 {name:'sutr**',payout_coin:242250},{name:'zom**',payout_coin:74000}];
let state=null,cycle=0,fetching=false,liveTimer=null,simTimer=null;
const deterministic=n=>{
  let x=(n+0x6d2b79f5)|0;
  x=Math.imul(x^(x>>>15),1|x);
  x^=x+Math.imul(x^(x>>>7),61|x);
  return ((x^(x>>>14))>>>0)/4294967296;
};
function makeItems(data){
  const recent=Array.isArray(data.recent)?data.recent.slice(0,12):[];
  return recent.map(item=>{
    const span=document.createElement('span');span.className='activity-win';
    const name=document.createElement('b');name.textContent=String(item.name||'Pemain**').slice(0,24);
    const value=document.createElement('strong');
    value.textContent=money(Math.max(0,Number(item.payout_coin)||0));
    span.append(name,value);
    return span;
  });
}
function render(data){
  state=data;
  const simulated=data.mode==='simulation';
  board.dataset.mode=simulated?'simulation':'live';
  modeEl.textContent=simulated?'SIMULASI QA':'TERCATAT';
  const head=board.querySelector('.activity-head');
  if(head)head.textContent=simulated?'✦ PAYOUT DEMO':'✦ PAYOUT LIVE';
  modeEl.title=simulated?'Contoh visual dengan nama dan jumlah acak, bukan aktivitas nyata':
    'Kemenangan dari ronde berbayar yang sudah dicatat pada server';
  const items=makeItems(data);
  feedEl.replaceChildren();
  const label=document.createElement('b');label.textContent=simulated?
    'PAYOUT SIMULASI':'PAYOUT COIN';
  label.className='activity-feed-label';feedEl.append(label);
  if(items.length){
    for(let pass=0;pass<2;pass++)
      items.forEach(item=>feedEl.append(item.cloneNode(true)));
  }else{
    const empty=document.createElement('span');empty.textContent='Belum ada payout pemain tercatat';
    empty.className='activity-win';feedEl.append(empty);
  }
  feedEl.classList.toggle('is-empty',items.length===0);
  updateCount();
}
function updateCount(){
  if(!state)return;
  if(state.mode==='simulation'){
    const elapsed=Math.max(0,Math.floor(Date.now()/1000-Number(state.epoch_unix||0)));
    // Guaranteed nondecreasing demonstration counter with small per-second
    // pseudo-random variation, not a fabricated transaction metric.
    const value=Math.max(0,Number(state.demo_start_coin)||0)+
      elapsed*111 + Math.floor(elapsed/4)*125 +
      Math.floor(deterministic(elapsed)*48);
    betEl.textContent=money(value);
    betEl.title='SIMULASI QA · bertambah otomatis setiap detik · bukan total BET riil';
  }else{
    betEl.textContent=money(Math.max(0,Number(state.total_bet_coin)||0));
    betEl.title='Total BET Coin virtual dari ronde berbayar yang selesai dan tercatat';
  }
}
async function refresh(){
  if(fetching||document.hidden)return;
  fetching=true;
  try{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),6500);
    let response;
    try{response=await fetch('/api/activity/public',{cache:'no-store',signal:controller.signal});}
    finally{clearTimeout(timer);}
    if(!response.ok)throw Error('Activity HTTP '+response.status);
    const payload=await response.json();
    if(!['live','simulation'].includes(payload.mode))throw Error('Unknown activity mode');
    if(payload.mode==='simulation'){
      cycle++;
      const n=cycle;
      // Demo names and awards are random-looking for design evaluation only,
      // while three opening examples stay stable per the original brief.
      if(n>0){
        const seed=Date.now()>>>8;
        const examples=sample.map(x=>({...x}));
        for(let i=0;i<3;i++){
          const idx=Math.floor(deterministic(seed+i)*aliases.length);
          const amount=25*(Math.floor(deterministic(seed+i+13)*13500)+200);
          examples.push({name:aliases[idx],payout_coin:amount});
        }
        payload.recent=examples;
      }
    }
    render(payload);
  }catch(error){
    if(!state){
      modeEl.textContent='BELUM TERHUBUNG';
      feedEl.textContent='Menunggu data PAYOUT virtual…';
      betEl.textContent='—';
    }
  }finally{fetching=false;}
}
void refresh();
liveTimer=setInterval(()=>{if(!document.hidden)void refresh();},12000);
simTimer=setInterval(updateCount,1000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refresh();});
window.UNOLuckActivity={refresh,get mode(){return state?.mode||'loading';}};
})();
