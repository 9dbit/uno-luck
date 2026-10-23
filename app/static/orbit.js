'use strict';
/* UNO LUCK v1.1: server-picked three cards, one GPU wheel with independent transparent card assets. */
const $ = id => document.getElementById(id);
const idMoney = n => new Intl.NumberFormat('id-ID').format(n);
const COLORS = ['red','blue','yellow','green'];
const FACES = ['0','1','2','3','4','5','6','7','8','9','SKIP','REVERSE','+2'];
let STAKES = [10,25,50,100,250];
const RING_COUNT = 9;
const MUTE_MUSIC = 'uno_orbit_music';
const MUTE_EFFECTS = 'uno_orbit_sfx';
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let account = null, currentRound=null, last=null, ruleset=null, stakeIndex=1, isSpinning=false;
let nextBetIndex=null;
let isTurbo=false, isAuto=false, cancelAuto=false, ringCards=[], wheel=null;
const AUTO_ROUNDS=[1,3,5,10];
let autoRounds=10;
let audioContext=null, musicTimer=null, musicEnabled=localStorage.getItem(MUTE_MUSIC)!=='off';
let sfxEnabled=localStorage.getItem(MUTE_EFFECTS)!=='off', nextMusicAt=0, musicStep=0;
const wait = ms => new Promise(r=>setTimeout(r,ms));
const previewCard = () => ({color:COLORS[Math.floor(Math.random()*COLORS.length)],face:FACES[Math.floor(Math.random()*FACES.length)]});
function say(message){$('spin-caption').textContent=message;$('spin-caption').title=message;}
function symbol(face){return ({SKIP:'⊘',REVERSE:'⇄','+2':'+2','+4':'+4',WILD:'◉'})[face]||face;}

function htmlCard(data,small=false,placeholder=false){
  const color = COLORS.includes(data.color) ? data.color : (data.color==='wild'?'wild':'blue');
  const face = String(data.face || '?').slice(0,8);
  const asset = placeholder ? 'card-placeholder' : `card-${color}`;
  const el=document.createElement('div');
  el.className='card3d'+(placeholder?' placeholder':'');
  el.dataset.color=color;el.dataset.small=String(small);el.dataset.face=face;
  el.setAttribute('aria-label',`${color} ${face}`);
  const front=document.createElement('span');front.className='card-face card-front';
  const art=document.createElement('img');art.className='metal-card-art';
  art.src=`/assets/art/v2/${asset}.webp`;art.alt='';art.draggable=false;art.decoding='async';
  const tl=document.createElement('span');tl.className='small-num';tl.textContent=face==='?'?'':symbol(face);
  const num=document.createElement('span');num.className='number';num.textContent=face==='?'?'?':symbol(face);
  const br=document.createElement('span');br.className='small-num bottom';br.textContent=face==='?'?'':symbol(face);
  front.append(art,tl,num,br);
  const back=document.createElement('span');back.className='card-face card-back';
  const backArt=document.createElement('img');backArt.className='metal-card-art';
  backArt.src='/assets/art/v2/card-back.webp';backArt.alt='';backArt.draggable=false;backArt.decoding='async';
  back.append(backArt);el.append(front,back);return el;
}
function resetRing(){
  ringCards=Array.from({length:RING_COUNT},()=>previewCard());
  wheel=new window.UNOLuckLEDWheel($('orbit-ring'),htmlCard,RING_COUNT);
  wheel.mount(ringCards);
}
function layoutRing(){ wheel?.resize(); }
function paintRound(round,preview=false,animateMetrics=false){
  currentRound=round?.complete?null:round;
  const show=round?.cards||[];
  const placeholders=[{color:'blue',face:'6'},{color:'blue',face:'3'},{color:'blue',face:'8'}];
  for(let idx=0;idx<3;idx++){
    const slot=$('result-'+idx);const card=show[idx]||(preview?placeholders[idx]:{color:'blue',face:'?' });
    const element=htmlCard(card,false,idx>=show.length && !preview);
    if(preview)element.classList.add('preview-card');
    slot.replaceChildren(element);
    slot.classList.remove('picked');
  }
  const stake=round?.stake ?? STAKES[stakeIndex];
  const payout=round?.complete?round.payout:null;
  const delta=round?.complete?round.delta:null;
  if(window.UNOLuckMotion) window.UNOLuckMotion.numbers({stake,payout,delta,animate:animateMetrics});
  else {
    $('last-stake').textContent=idMoney(stake);
    $('last-payout').textContent=payout===null?'—':idMoney(payout);
    $('last-delta').textContent=delta===null?'—':`${delta>0?'+':''}${idMoney(delta)}`;
  }
  renderProgress(round?.picked||0);
}
function renderProgress(picked){
  const next=picked===3?0:picked;
  [...$('steps').querySelectorAll('.step')].forEach((item,index)=>{
    item.classList.toggle('done',index<picked);item.classList.toggle('active',index===next);
    [...item.querySelectorAll('.step-slots i')].forEach((dot,j)=>dot.classList.toggle('filled',j<Math.min(picked,index+1)));
  });
  $('spin-step').textContent=`${next+1} / 3`;
  const btn=$('spin-btn');btn.setAttribute('aria-label',`SPIN ${next+1} dari 3`);
}
function virtualRp(n){return 'Rp'+idMoney(n*(ruleset?.virtual_rp_per_coin||40))+' virtual';}
function syncAccount(a){
  if(!a)return;account=a;
  $('wallet-balance').title=virtualRp(a.balance)+' · tidak dapat dicairkan';
  if(window.UNOLuckMotion)window.UNOLuckMotion.balance(a.balance,true);
  else $('wallet-balance').textContent=idMoney(a.balance);
  $('gift-btn').disabled=!a.daily_available&&!a.refill_available;
  $('gift-btn').title='Gift · hadiah harian dan refill';
  const total=$('coin-total');if(total)total.textContent=idMoney(a.balance);
  const denomination=$('coin-rp');if(denomination)denomination.textContent=virtualRp(a.balance)+' · tanpa nilai uang';
  updateButtons();
}
function updateButtons(){
  const stake=currentRound?.stake ?? STAKES[stakeIndex];
  $('spin-btn').disabled=isSpinning||isAuto||!account||(!currentRound && account.balance<stake);
  $('turbo-btn').disabled=isSpinning;
  $('turbo-btn').setAttribute('aria-pressed',String(isTurbo));
  $('auto-btn').setAttribute('aria-pressed',String(isAuto));
  $('auto-btn').disabled=!isAuto&&(isSpinning||!account);
  $('auto-btn').setAttribute('aria-label',isAuto?'Hentikan AUTO':'Pengaturan AUTO');
  $('auto-label').textContent=isAuto?'STOP':'AUTO';
}
async function api(path,method='GET',body){
  const req={method,credentials:'same-origin',headers:{}};
  const controller=method==='GET'?new AbortController():null;
  const timeout=controller?setTimeout(()=>controller.abort(),6000):null;
  if(controller){req.signal=controller.signal;req.cache='no-store';}
  if(method!=='GET'){req.headers['Content-Type']='application/json';req.headers['X-UNO-Client']='spin-ui';req.body=JSON.stringify(body??{});}
  try{
  let response;
  try{response=await fetch('/api/orbit'+path,req);}catch(_){throw Error('Koneksi terputus. Periksa internet dan coba lagi.');}
  let data;try{data=await response.json();}catch(_){throw Error('Server mengirim respons tak valid.');}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`HTTP ${response.status}`);
  return data;
  }finally{if(timeout!==null)clearTimeout(timeout);}
}
async function legacyBonus(endpoint){
  const response=await fetch('/api/spin/'+endpoint,{method:'POST',headers:{'X-UNO-Client':'spin-ui','Content-Type':'application/json'},credentials:'same-origin',body:'{}'});
  const data=await response.json();
  if(!response.ok)throw Error(data.detail||'Gagal mengklaim hadiah');
  return data;
}
function sfx(name){if(sfxEnabled)window.UNOLuckSound?.play(name);}
function startMusic(){
  if(!musicEnabled||document.hidden)return false;
  return window.UNOLuckSound?.music(true);
}
function stopMusic(){window.UNOLuckSound?.music(false);}
async function unlockAudio(){
  const ok=await window.UNOLuckSound?.unlock();
  if(ok){window.UNOLuckSound.setEnabled(sfxEnabled);startMusic();}
  return Boolean(ok);
}
window.UNOLuckAudio={unlock:unlockAudio,preview:()=>sfx('tap'),get state(){return window.UNOLuckSound?.state||'inactive';}};
function winBurst(card){
  const layer=$('win-particles');layer.replaceChildren();
  if(reducedMotion)return;
  const palette={red:'#ff2740',blue:'#0787ff',green:'#21ed6f',yellow:'#ffdc17'};
  for(let i=0;i<36;i++){
    const chip=document.createElement('i');chip.className='win-shard'+(i%5===0?' coin':'');
    const theta=Math.PI*2*i/36,dist=40+Math.random()*130;
    chip.style.setProperty('--dx',Math.cos(theta)*dist+'px');chip.style.setProperty('--dy',Math.sin(theta)*dist+'px');
    chip.style.setProperty('--rot',Math.floor(Math.random()*360)+'deg');
    chip.style.setProperty('--size',(5+Math.floor(Math.random()*9))+'px');
    chip.style.setProperty('--c',palette[card.color]||'#ffce29');layer.append(chip);
  }
  setTimeout(()=>layer.replaceChildren(),1100);
}
function newRequestId(){return typeof crypto.randomUUID==='function'?crypto.randomUUID():(Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)+'_id');}

/* A single SPIN selects one server-issued card. Nine fixed LED screens change
   content from left to right. Only after the pointer stops does a result card fly
   from the wheel to the upper-left, upper-center, or upper-right display. */
const pendingKey='uno_orbit_pending_v08'; // Keep request recovery keys across upgrades.
// The updater may only refresh between completed rounds, never during a pick.
window.UNOLuckCanReload=()=>Boolean(account)&&!isSpinning&&!isAuto&&!currentRound&&
  !pendingInfo()&&!$('modal').open&&$('celebration-overlay').hidden;
function pendingInfo(){
  try{const data=JSON.parse(localStorage.getItem(pendingKey)||'null');
      return data&&typeof data.id==='string'&&Number.isInteger(data.expected)?data:null;
  }catch(_){return null;}
}
async function pickOne(){
  if(isSpinning||!account)return false;
  const stake=currentRound?.stake ?? STAKES[stakeIndex];
  if(!currentRound && account.balance<stake){say('Saldo virtual tidak cukup. Klaim hadiah harian.');return false;}
  const expected=(currentRound?.picked||0)+1;
  let pending=pendingInfo();
  if(!pending||pending.expected!==expected){
    pending={id:newRequestId(),expected};
    localStorage.setItem(pendingKey,JSON.stringify(pending));
  }
  isSpinning=true;updateButtons();
  window.UNOLuckMatch?.clear();
  window.UNOLuckMotion?.beginSpin();
  void unlockAudio();
  say(`SPIN ${expected}/3 · LED kartu bergerak dari kiri ke kanan…`);
  let confirmed=null;
  try {
    wheel.begin({turbo:isTurbo});
    confirmed=await api('/pick','POST',{request_id:pending.id,stake});
    const phase=confirmed.round.picked;
    const card=confirmed.round.cards[phase-1];
    if(!card)throw Error('Server belum memberikan kartu terpilih');
    const aligned=await wheel.settle(card,phase);
    if(!aligned)throw Error('Putaran terhenti, memulihkan hasil server');
    await wheel.transferTo($('result-'+(phase-1)));
    // The server result is painted ONLY after the transfer finishes.
    localStorage.removeItem(pendingKey);
    paintRound(confirmed.round,false,true);
    $('result-'+(phase-1))?.classList.add('picked');
    window.UNOLuckMotion?.pick(phase-1);
    syncAccount(confirmed.account);
    if(confirmed.round.complete){
      last=confirmed.round;
      // A winning round is scored by exactly one tier-specific jackpot cue.
      // Do not overlap RESULT SOUND with the user-selected JACKPOT 1–5 file.
      if(sfxEnabled && last.combo==='NO_MATCH')window.UNOLuckSound?.result(false);
      if(!last.bonus)window.UNOLuckMotion?.result(last);
      if(last.combo==='COLOR_MATCH'){
        const title=last.tier?.title||'LUCKY COLOR WIN';
        say(`${title}! Kembali ${idMoney(last.payout)} · selisih ${last.delta>=0?'+':''}${idMoney(last.delta)} koin`);
        winBurst(last.cards[0]);
        await window.UNOLuckCelebration?.present(last);
      }else if(last.bonus){
        say(`${last.bonus.kind==='PAIR_PRODUCT'?'Bonus perkalian':'Bonus penjumlahan'} · +${idMoney(last.payout)} Coin · ${virtualRp(last.payout)}`);
        showNumericBonus(last);
      }else{say('Belum ada kecocokan warna. Mulai ronde baru!');}
    }else say(`Kartu ${['kiri','tengah','kanan'][phase-1]} terpilih. SPIN ${phase+1}/3 berikutnya.`);
    navigator.vibrate?.(18);
    return true;
  }catch(error){
    wheel.cancel();
    say(`${error.message} · Menyinkronkan hasil server…`);
    try{await loadState(true);}catch(_){/* pending request ID remains for safe retry */}
    if(isAuto)cancelAuto=true;
    return false;
  }finally{
    isSpinning=false;
    applyNextBet();
    window.UNOLuckMotion?.endSpin();
    wheel?.startIdle();
    updateButtons();
  }
}
function canChangeBet(){return !!account&&!isSpinning&&!isAuto&&!currentRound&&!pendingInfo();}
// Only promote a confirmed choice after the paid round, AUTO batch and any
// uncertain request finish. Never change the stake used for an in-flight retry.
function applyNextBet(){
  if(nextBetIndex===null||!canChangeBet())return;
  stakeIndex=nextBetIndex;nextBetIndex=null;
}
let numericBonusTimer;
function showNumericBonus(round){
  document.getElementById('numeric-bonus')?.remove();clearTimeout(numericBonusTimer);
  const toast=panelNode('aside','numeric-bonus');toast.id='numeric-bonus';toast.setAttribute('role','status');
  toast.append(festiveArt('coins'),panelNode('strong','',`+${idMoney(round.payout)} Coin`),panelNode('span','',virtualRp(round.payout)));
  document.body.append(toast);
  if(sfxEnabled&&round.payout>0)window.UNOLuckSound?.numericBonus?.();
  numericBonusTimer=setTimeout(()=>toast.remove(),2400);
}
function autoBudget(rounds){return (rounds-(currentRound?1:0))*(currentRound?.stake??STAKES[stakeIndex]);}
async function autoLoop(roundLimit){
  if(isAuto||isSpinning||!account||pendingInfo()||document.hidden||
      !AUTO_ROUNDS.includes(roundLimit)||account.balance<autoBudget(roundLimit))return;
  // Keep the confirmed setup stake after a restored paid round completes.
  const autoStakeIndex=STAKES.indexOf(currentRound?.stake??STAKES[stakeIndex]);
  if(autoStakeIndex<0){say('BET ronde lama tidak tersedia untuk AUTO. Selesaikan ronde dengan SPIN, lalu pilih BET baru.');return;}
  stakeIndex=autoStakeIndex;
  isAuto=true;cancelAuto=false;updateButtons();
  // The selected limit includes an existing paid partial round. Each card
  // still uses the same server-issued pick and persistent request ID.
  for(let rounds=0;rounds<roundLimit&&!cancelAuto&&!document.hidden;rounds++){
    for(let k=(currentRound?.picked||0);k<3&&!cancelAuto&&!document.hidden;k++){
      const done=await pickOne();if(!done){cancelAuto=true;break;}if(cancelAuto)break;
      await wait(isTurbo?130:230);
    }
    if(!cancelAuto)await wait(isTurbo?270:510);
  }
  isAuto=false;applyNextBet();updateButtons();
}
function modal(title){delete $('modal').dataset.view;$('modal-back').hidden=title==='Menu';$('modal').classList.remove('coin-modal','player-panel');$('modal').querySelector('.panel-actions')?.remove();$('modal-title').textContent=title;$('modal-content').replaceChildren();$('modal-content').scrollTop=0;if(!$('modal').open)$('modal').showModal();return $('modal-content');}
function paragraph(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);return p;}
function modalButton(parent,text,fn){const b=document.createElement('button');b.textContent=text;b.type='button';b.addEventListener('click',fn);parent.append(b);return b;}
function closeModal(){if($('modal').open)$('modal').close();}
function panelNode(tag,klass,text){const el=document.createElement(tag);el.className=klass;if(text!==undefined)el.textContent=text;return el;}
function playerPanel(title){const area=modal(title);$('modal').classList.add('player-panel');return area;}
function festiveArt(kind,klass='hero-art'){
  const img=panelNode('img',klass);img.src=kind==='profile'?'/assets/art/v1/avatar.webp':`/assets/art/festive/${kind}.svg`;
  img.alt='';img.width=240;img.height=240;img.decoding='async';return img;
}
function panelHero(parent,kind,eyebrow,title,copy){
  const hero=panelNode('section','festive-hero');hero.dataset.art=kind;
  const text=panelNode('div','hero-copy');text.append(panelNode('span','panel-eyebrow',eyebrow),panelNode('h3','',title));
  if(copy)text.append(panelNode('p','',copy));hero.append(festiveArt(kind),text);parent.append(hero);return hero;
}
function panelAction(text,fn){const footer=panelNode('div','panel-actions');$('modal').querySelector('.modal-card').append(footer);const btn=modalButton(footer,text,fn);btn.className='panel-primary';return btn;}
async function claimDaily(){try{const x=await legacyBonus('daily');syncAccount(x.account);sfx('coin');say(`Hadiah +${idMoney(x.credited)} koin virtual`);closeModal();}catch(e){say(e.message);}}
async function claimRefill(){try{const x=await legacyBonus('refill');syncAccount(x.account);sfx('coin');say(`Refill gratis +${idMoney(x.credited)} koin`);closeModal();}catch(e){say(e.message);}}
function showGift(){
  const area=playerPanel('Gift');$('modal').dataset.view='gift';
  panelHero(area,'gift','A LITTLE EXTRA JOY','Hadiah untukmu','Kumpulkan Coin virtual dan lanjutkan keseruanmu.');
  const list=panelNode('div','gift-rewards');area.append(list);
  for(const [title,copy,kind,available,fn] of [
    ['Klaim +250 harian','Bonus harian','gift',account?.daily_available,claimDaily],
    ['Refill gratis +1.000','Isi ulang Coin','coins',account?.refill_available,claimRefill]]){
    const btn=menuTile(list,title,available?copy+' · Tersedia':'Belum tersedia',kind,fn);btn.disabled=!available;
  }
  paragraph(area,'Coin bersifat virtual, tidak dapat dibeli atau dicairkan.').className='panel-fine';
}
async function showWallet(){
  const area=playerPanel('Coin');$('modal').classList.add('coin-modal');$('modal').dataset.view='coin';
  const summary=document.createElement('div');summary.className='coin-summary';
  summary.append(festiveArt('coins'));
  paragraph(summary,'Total Coin');
  const total=document.createElement('strong');total.id='coin-total';total.textContent=idMoney(account?.balance||0);
  total.setAttribute('aria-live','polite');summary.append(total);
  const denomination=paragraph(summary,virtualRp(account?.balance||0)+' · tanpa nilai uang');denomination.id='coin-rp';
  const title=document.createElement('h3');title.textContent='History Bet';
  const history=document.createElement('div');history.className='coin-history';history.tabIndex=0;
  history.setAttribute('role','region');history.setAttribute('aria-label','History Bet');
  paragraph(history,'Memuat riwayat bet…');area.append(summary,title,history);
  try{
    const data=await api('/state');
    // A closed/replaced popup must not receive a delayed response.
    if(!history.isConnected||!$('modal').open)return;
    syncAccount(data.account);history.replaceChildren();
    if(!data.recent?.length)paragraph(history,'Belum ada bet selesai.');
    for(const item of data.recent||[]){
      const row=document.createElement('article');row.className='coin-history-row';
      const stamp=new Date(item.created_at*1000);
      const time=document.createElement('time');time.dateTime=stamp.toISOString();
      time.textContent=stamp.toLocaleString('id-ID',{dateStyle:'short',timeStyle:'short'});
      const result=document.createElement('strong');result.textContent=item.tier?.title||(item.combo==='COLOR_MATCH'?'LUCKY COLOR WIN':item.combo==='PAIR_SUM'?'BONUS PENJUMLAHAN':item.combo==='PAIR_PRODUCT'?'BONUS PERKALIAN':'NO MATCH');
      const values=document.createElement('p');values.textContent=`BET ${idMoney(item.stake)} · PAYOUT ${idMoney(item.payout)} · WIN ${item.delta>=0?'+':''}${idMoney(item.delta)}`;
      row.append(time,result,values);history.append(row);
    }
    if(data.recent?.length)paragraph(history,'Menampilkan '+data.recent.length+' bet terakhir.');
  }catch(error){if(history.isConnected){history.replaceChildren();paragraph(history,error.message);}}
}
function showRules(){
  const area=playerPanel('Game Rules');
  panelHero(area,'cards','PLAY YOUR COLORS','Kenali kombinasimu',ruleset?.numeric_bonus?'Lima perayaan dan bonus angka kembar.':'Lima kombinasi. Lima perayaan.');
  area.append(panelNode('p','panel-eyebrow','3 KARTU · 1 RONDE'));
  paragraph(area,'Tekan SPIN tiga kali untuk membuka kartu kiri, tengah, dan kanan. BET dipotong sekali pada SPIN pertama.');
  // Illustration only: these examples never enter the outcome generator.
  const examples={TRIPLE_DRAW_FOUR:['wild',['+4','+4','+4']],TRIPLE_WILD:['wild',['WILD','WILD','WILD']],
    ACTION_TRIO:['red',['SKIP','REVERSE','+2']],COLOR_STRAIGHT:['blue',['3','4','5']],COLOR_MATCH:['green',['2','5','9']]};
  const list=panelNode('div','rules-paytable');area.append(list);
  if(ruleset?.celebrations?.length){
    for(const tier of ruleset.celebrations){
      const row=panelNode('article','rules-tier');row.dataset.rank=tier.rank;
      const heading=panelNode('div','rules-tier-top');
      heading.append(panelNode('span','panel-eyebrow',`RANK ${tier.rank}`),panelNode('strong','rules-multiplier',`${tier.multiplier}× BET`));
      const hand=panelNode('div','rules-hand');hand.setAttribute('aria-label','Contoh kombinasi');
      const example=examples[tier.pattern];
      if(example)for(const face of example[1])hand.append(htmlCard({color:example[0],face},true));
      const description=panelNode('div','rules-description');description.append(panelNode('h3','',tier.title),panelNode('p','',tier.rule));
      row.append(heading,hand,description);list.append(row);
    }
  }else paragraph(area,'Daftar kombinasi sedang disinkronkan dari server. Periksa koneksi sebelum bermain.');
  const details=panelNode('details','rules-details'),summary=panelNode('summary','','Cara bermain & ketentuan');details.append(summary);
  paragraph(details,'Gambar kartu di atas adalah contoh kombinasi. Hasil setiap ronde ditentukan oleh server. Wild dan Wild +4 tidak mempunyai warna; hanya tiga Wild sejenis yang memenuhi Rank 1/2.');
  if(ruleset?.numeric_bonus)paragraph(area,`BONUS ANGKA KEMBAR · Tiga kartu angka dengan minimal dua angka sama: warna berbeda menjumlahkan angka (maks. ${ruleset.numeric_bonus.sum_cap}× BET); semua sewarna mengalikan angka (maks. ${ruleset.numeric_bonus.product_cap}× BET). Hanya satu hadiah per ronde. Angka 0 dapat menghasilkan payout 0. Bonus ini tanpa celebration.`);
  paragraph(area,'NO MATCH · Tidak ada kombinasi yang cocok, tidak ada payout.');
  paragraph(details,'Tidak ada jaminan jackpot atau bonus setelah sejumlah spin.');
  paragraph(details,'AUTO maksimal 10 ronde, TURBO hanya mengubah animasi. Koin tidak mempunyai nilai uang dan tidak dapat dibeli atau dicairkan. Batas saldo 1.000.000 koin dapat menurunkan jumlah yang benar-benar dikreditkan. Ini bukan aturan permainan UNO resmi.');
  area.append(details);
}
function showStakeChoices(){
  const area=playerPanel('Bet Setting');$('modal').dataset.view='bet';let selected=nextBetIndex??stakeIndex;
  const hero=panelNode('section','bet-hero');
  hero.append(festiveArt('coins'));
  hero.append(panelNode('span','panel-eyebrow','YOUR NEXT ROUND'));
  const amount=panelNode('strong','panel-amount',idMoney(STAKES[selected])+' Coin');
  amount.setAttribute('aria-live','polite');hero.append(amount,panelNode('p','','Satu BET. Tiga kartu.'));
  area.append(hero);
  const denomination=panelNode('p','panel-fine',virtualRp(STAKES[selected])+' · 1 Coin = Rp40 virtual, tanpa nilai uang');area.append(denomination);
  const balance=panelNode('div','bet-balance');balance.append(panelNode('span','','Coin tersedia'),coinValue(account?.balance??0,'strong'));area.append(balance);
  area.append(panelNode('p','panel-eyebrow','PILIH CHIP BET'));
  const grid=panelNode('div','bet-grid');grid.setAttribute('role','group');grid.setAttribute('aria-label','Pilihan BET');area.append(grid);
  const preview=panelNode('p','bet-preview');preview.setAttribute('role','status');
  function refresh(){
    const cost=STAKES[selected];amount.textContent=idMoney(cost)+' Coin';denomination.textContent=virtualRp(cost)+' · 1 Coin = Rp40 virtual, tanpa nilai uang';
    for(const item of grid.children)item.setAttribute('aria-pressed',String(Number(item.dataset.bet)===cost));
    preview.textContent=isAuto?`AUTO berjalan tetap ${idMoney(currentRound?.stake??STAKES[stakeIndex])} Coin. Pilihan ini berlaku setelah AUTO dan ronde berjalan selesai.`:
      currentRound?`Ronde berjalan tetap ${idMoney(currentRound.stake)} Coin (${currentRound.picked}/3 kartu). Pilihan ini berlaku mulai ronde berikutnya.`:
      !canChangeBet()?'Pilihan ini disimpan untuk ronde berikutnya setelah SPIN tersinkronkan.':
      (account?.balance??0)<cost?'Coin belum cukup untuk BET ini. Pilihan dapat disimpan.':`Sisa setelah BET pertama: ${idMoney((account?.balance??0)-cost)} Coin`;
  }
  for(const [i,cost] of STAKES.entries()){
    const btn=modalButton(grid,'',()=>{selected=i;refresh();});
    btn.setAttribute('aria-label',idMoney(cost)+' Coin');btn.dataset.bet=String(cost);btn.disabled=!account;
    btn.append(panelNode('span','bet-chip',idMoney(cost)),panelNode('span','bet-chip-label','COIN · Rp'+idMoney(cost*40)),panelNode('span','bet-selected','✓'));
    btn.lastChild.setAttribute('aria-hidden','true');
  }
  area.append(preview,panelNode('p','panel-fine','Pilih chip lalu konfirmasi. Menutup panel membatalkan perubahan.'));
  const save=panelAction('GUNAKAN BET',()=>{
    if(!account)return;
    const ready=canChangeBet();nextBetIndex=selected;applyNextBet();
    if(ready)paintRound(null,true);
    updateButtons();closeModal();
    say(`Bet berikutnya ${idMoney(STAKES[selected])} Coin.${ready?'':' Berlaku setelah ronde / AUTO berjalan selesai.'}`);
  });
  save.disabled=!account;refresh();
}
function coinValue(value,tag='span'){
  const el=panelNode(tag,'coin-value');
  const icon=panelNode('img','coin-value-icon');icon.src='/assets/art/coin-ui.svg';icon.alt='';icon.width=24;icon.height=24;
  el.append(icon,panelNode('span','coin-value-text',idMoney(value)+' Coin'));el.title=virtualRp(value);return el;
}
function showAutoSettings(){
  if(isAuto){cancelAuto=true;updateButtons();say('AUTO berhenti setelah SPIN saat ini.');return;}
  if(isSpinning||!account)return;
  const area=playerPanel('Auto Play');$('modal').dataset.view='auto';let selected=autoRounds;
  panelHero(area,'cards','KEEP THE FUN GOING','Atur ritme bermain','Pilih ronde, lalu biarkan AUTO melanjutkan.');
  area.append(panelNode('p','panel-eyebrow','PILIH JUMLAH RONDE'));
  paragraph(area,'Setiap ronde membuka tiga kartu. AUTO dapat dihentikan setelah SPIN yang sedang berjalan.');
  const grid=panelNode('div','auto-grid');grid.setAttribute('role','group');grid.setAttribute('aria-label','Jumlah ronde AUTO');area.append(grid);
  for(const rounds of AUTO_ROUNDS){
    const btn=modalButton(grid,'',()=>{selected=rounds;refresh();});btn.dataset.rounds=String(rounds);
    btn.setAttribute('aria-label',rounds+' ronde');
    const cards=panelNode('span','auto-card-fan');cards.setAttribute('aria-hidden','true');
    for(const color of ['red','blue','green']){const card=panelNode('img','');card.src=`/assets/art/v2/card-${color}.webp`;card.alt='';cards.append(card);}
    const check=panelNode('span','auto-selected','✓');check.setAttribute('aria-hidden','true');
    btn.append(cards,panelNode('strong','auto-round-count',String(rounds)),panelNode('span','auto-round-label','RONDE'),check);
  }
  const budget=panelNode('dl','auto-budget');
  const total=coinValue(0,'dd'),balance=coinValue(account.balance,'dd');
  budget.append(panelNode('dt','','BET per ronde'),coinValue(currentRound?.stake??STAKES[stakeIndex],'dd'),
    panelNode('dt','','Total kebutuhan'),total,panelNode('dt','','Saldo tersedia'),balance);area.append(budget);
  const message=panelNode('p','panel-note','');message.setAttribute('role','status');area.append(message);
  const virtualBudget=paragraph(area,'');virtualBudget.className='panel-fine';
  if(currentRound)paragraph(area,'Ronde yang sudah dimulai dihitung sebagai ronde pertama. BET ronde tersebut sudah dipotong.');
  else paragraph(area,'Kebutuhan coin dihitung tanpa mengandalkan hadiah dari ronde berikutnya.');
  const start=panelAction('MULAI AUTO',()=>{
    if(isAuto||isSpinning||pendingInfo()||!account||account.balance<autoBudget(selected)){refresh();return;}
    autoRounds=selected;closeModal();void autoLoop(selected);
  });start.id='auto-start';
  function refresh(){
    for(const btn of grid.children)btn.setAttribute('aria-pressed',String(Number(btn.dataset.rounds)===selected));
    const required=autoBudget(selected);virtualBudget.textContent='Kebutuhan '+virtualRp(required)+' · 1 Coin = Rp40 virtual';total.querySelector('.coin-value-text').textContent=idMoney(required)+' Coin';balance.querySelector('.coin-value-text').textContent=idMoney(account?.balance??0)+' Coin';
    const blocked=!!pendingInfo()||isSpinning||isAuto||!account;
    start.disabled=blocked||account.balance<required;
    message.textContent=blocked?'Selesaikan sinkronisasi SPIN sebelum memulai AUTO.':account.balance<required?'Coin belum cukup. Pilih jumlah ronde lebih kecil atau ubah BET.':`${selected} ronde · ${isTurbo?'TURBO aktif':'Kecepatan normal'}`;
  }
  refresh();
}
function hubIcon(kind){
  return festiveArt(({person:'profile',coin:'coins',cup:'trophy'})[kind]||kind,'icon-3d');
}
function menuTile(parent,title,subtitle,icon,fn){
  const btn=modalButton(parent,'',fn);btn.className='menu-tile';btn.setAttribute('aria-label',title);
  const mark=panelNode('span','menu-icon');mark.append(hubIcon(icon));
  const copy=panelNode('span','menu-copy');copy.append(panelNode('strong','',title),panelNode('small','',subtitle));
  btn.append(mark,copy,panelNode('span','menu-chevron','›'));return btn;
}
function showMenu(){
  const area=playerPanel('Menu');$('modal').dataset.view='menu';
  const welcome=panelNode('section','menu-welcome');
  const avatar=panelNode('img','menu-avatar');avatar.src='/assets/art/v1/avatar.webp';avatar.alt='';
  const intro=panelNode('div','');intro.append(panelNode('span','panel-eyebrow','PLAYER LOUNGE'),panelNode('h3','',account?.name||'Player'),panelNode('p','',`Level ${account?.level||1} · ${idMoney(account?.balance??0)} Coin`));
  welcome.append(avatar,intro,festiveArt('cards','lounge-art'));area.append(welcome);
  const tournament=menuTile(area,'Turnamen','Dragon Daily · 10 ronde untuk bersinar','cup',showTournament);tournament.classList.add('tournament-entry');
  const grid=panelNode('div','menu-grid');area.append(grid);
  menuTile(grid,'Game Rules',ruleset?.numeric_bonus?'Kombinasi & bonus angka':'Kenali 5 kombinasi','cards',showRules);
  menuTile(grid,'Bet Setting','Pilih chip favoritmu','coin',showStakeChoices);
  menuTile(grid,'Profile','Nama & identitas bermain','person',showProfile);
  const enabled=()=>musicEnabled||sfxEnabled;
  const sound=menuTile(grid,`Sound ${enabled()?'On':'Off'}`,'Musik & efek suara','sound',()=>{
    const next=!enabled();musicEnabled=next;sfxEnabled=next;
    localStorage.setItem(MUTE_MUSIC,next?'on':'off');localStorage.setItem(MUTE_EFFECTS,next?'on':'off');
    window.UNOLuckSound?.setEnabled(next);
    if(next)void unlockAudio().then(()=>sfx('tap'));else{stopMusic();window.UNOLuckSound?.stopCelebration?.();}
    const label=`Sound ${next?'On':'Off'}`;sound.querySelector('strong').textContent=label;sound.setAttribute('aria-label',label);sound.setAttribute('aria-pressed',String(next));
  });sound.setAttribute('aria-pressed',String(enabled()));
  area.append(panelNode('p','menu-signoff','UNO LUCK · Crafted by Soft Tech'));
}
function showAbout(){
  const area=playerPanel('Tentang UNO LUCK');$('modal').dataset.view='about';
  const hero=panelNode('section','about-hero');const logo=panelNode('img','about-logo');logo.src='/assets/art/v1/logo.webp';logo.alt='UNO LUCK';
  hero.append(logo,panelNode('span','panel-eyebrow','COLOR. CARDS. CELEBRATION.'),panelNode('h3','','Tiga kartu. Satu momen seru.'));area.append(hero);
  const tabs=panelNode('div','about-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','Tentang permainan');area.append(tabs);
  const story=panelNode('section','about-story');story.setAttribute('aria-live','polite');area.append(story);
  const items=[['UNO LUCK',()=>{
    story.append(panelNode('h3','','Apa itu UNO LUCK?'));paragraph(story,'Permainan kasual dengan kartu berwarna, Dragon Spin, dan lima kombinasi perayaan. Buka tiga kartu dalam satu ronde dan lihat kombinasi yang terbentuk.');
    paragraph(story,'UNO adalah permainan kartu yang dikenal dengan warna, angka, dan kartu aksi. UNO LUCK memakai cara bermain sendiri: bukan permainan UNO resmi dan tidak berafiliasi dengan Mattel.');
    paragraph(story,'Semua Coin bersifat virtual, tidak bisa dibeli, ditukar uang, atau dicairkan.');
    menuTile(story,'Game Rules','Lihat kombinasi & cara bermain','cards',showRules);
  }],['Soft Tech',()=>{
    const logo=panelNode('img','about-softtech');logo.src='/assets/boot-softtech.webp';logo.alt='Soft Tech';story.append(logo,panelNode('h3','','Dikembangkan oleh Soft Tech'));
    paragraph(story,'Soft Tech mengembangkan UNO LUCK: pengalaman bermain yang memadukan desain kartu, animasi Dragon Spin, dan audio interaktif.');
    paragraph(story,'Kami terus menyempurnakan pengalaman di mobile, desktop, dan PWA. Selamat bermain!');
  }]];
  for(const [title,render] of items){const btn=modalButton(tabs,title,()=>{for(const b of tabs.children)b.setAttribute('aria-pressed',String(b===btn));story.replaceChildren();render();});btn.setAttribute('aria-pressed','false');}
  tabs.firstChild.click();
}
async function tournamentRequest(path,method='GET'){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
  try{const response=await fetch('/api/tournament/'+path,{method,credentials:'same-origin',cache:'no-store',headers:{'X-UNO-Client':'spin-ui'},signal:controller.signal});
    const data=await response.json();if(!response.ok)throw Error(data.detail||'Turnamen belum dapat dimuat.');return data;
  }finally{clearTimeout(timer);}
}
async function showTournament(){
  const area=playerPanel('Turnamen');$('modal').dataset.view='tournament';
  paragraph(area,'Memuat Dragon Daily…');
  const active=()=>area=== $('modal-content')&&$('modal').open&&$('modal').dataset.view==='tournament'&&area.contains(anchor);
  // Each invocation owns a marker so late responses cannot replace a newer panel.
  const anchor=panelNode('span','');anchor.hidden=true;area.append(anchor);
  function error(message){if(!active())return;area.replaceChildren(anchor);paragraph(area,message);modalButton(area,'Coba lagi',showTournament);}
  function render(data){
    if(!active())return;area.replaceChildren(anchor);$('modal').querySelector('.panel-actions')?.remove();
    const {event,you,leaderboard}=data;
    const hero=panelNode('section','tournament-hero festive-hero');const emblem=panelNode('span','tournament-emblem');emblem.append(festiveArt('trophy'));
    hero.append(emblem,panelNode('span','panel-eyebrow','DAILY TOURNAMENT'),panelNode('h3','',event.title),panelNode('p','','Bawa kombinasi terbaikmu ke papan peringkat.'));
    const meta=panelNode('div','event-meta');meta.append(panelNode('span','','Ikut gratis'),panelNode('span','',`${event.round_limit} ronde`),panelNode('span','','Reset 00.00 WIB'));hero.append(meta);area.append(hero);
    const today=new Date(event.server_time*1000).toLocaleDateString('id-ID',{timeZone:'Asia/Jakarta',day:'numeric',month:'long',year:'numeric'});
    area.append(panelNode('p','event-date',today+' · '+event.participants+' peserta'));
    if(you){
      const stats=panelNode('div','tournament-stats');
      for(const [label,value] of [['PERINGKAT','#'+you.position],['POIN',idMoney(you.points)],['RONDE',you.rounds+'/'+event.round_limit]]){const cell=panelNode('div','');cell.append(panelNode('small','',label),panelNode('strong','',value));stats.append(cell);}
      area.append(stats);const progress=panelNode('progress','tournament-progress');progress.max=event.round_limit;progress.value=you.rounds;progress.setAttribute('aria-label','Ronde turnamen selesai');area.append(progress);
    }
    const heading=panelNode('div','leaderboard-heading');heading.append(panelNode('h3','','Leaderboard'));
    const reload=modalButton(heading,'Refresh',showTournament);reload.className='text-action';area.append(heading);
    if(!leaderboard.length)area.append(panelNode('p','tournament-empty','Panggung masih kosong. Jadilah peserta pertama hari ini.'));
    else{const list=panelNode('ol','leaderboard');list.setAttribute('aria-label','Peringkat turnamen');
      for(const row of leaderboard){const item=panelNode('li',row.is_you?'is-you':'');
        item.append(panelNode('span','rank-badge',String(row.position)),panelNode('span','leader-name',row.name+(row.is_you?' · Kamu':'')),panelNode('strong','leader-score',idMoney(row.points)+' pt'));list.append(item);}
      area.append(list);
    }
    const details=panelNode('details','rules-details'),summary=panelNode('summary','','Cara ikut & perhitungan poin');details.append(summary);
    paragraph(details,'Gabung dahulu, lalu mainkan 10 ronde baru pertama sebelum 00.00 WIB. Ronde yang dimulai sebelum bergabung atau selesai setelah hari berganti tidak dihitung.');
    paragraph(details,'Poin turnamen tetap menurut rank: 200, 80, 30, 10, atau 2. Bonus angka dan NO MATCH mendapat 0 poin. Poin terpisah dari multiplier hadiah Coin. Nominal BET tidak meningkatkan poin; skor sama berbagi peringkat.');
    paragraph(details,'Pendaftaran gratis. Ronde tetap memakai BET biasa. Tidak ada bonus Coin atau hadiah uang dari turnamen. Nama profil terlihat oleh peserta lain setelah bergabung.');area.append(details);
    if(!you){
      paragraph(area,'Dengan bergabung, nama profilmu tampil di leaderboard.');
      const join=panelAction('GABUNG GRATIS',async()=>{join.disabled=true;join.textContent='MENDAFTAR…';try{const joined=await tournamentRequest('join','POST');render(joined);}catch(e){if(active()){join.disabled=false;join.textContent='COBA GABUNG LAGI';paragraph(area,'Pendaftaran belum terkonfirmasi. Tekan lagi untuk memeriksa dengan aman.');}}});
    }else panelAction(you.rounds>=event.round_limit?'SELESAI · KEMBALI KE GAME':'LANJUT BERMAIN',closeModal);
  }
  try{render(await tournamentRequest('state'));}catch(e){error(e.name==='AbortError'?'Koneksi lambat. Coba muat turnamen lagi.':e.message);}
}
function showProfile(){const area=playerPanel('Profil Pemain');panelHero(area,'profile','YOUR PLAYER ID','Panggungmu, gayamu','Nama ini tampil di papan peringkat saat kamu bergabung.');paragraph(area,`Nama saat ini: ${account?.name||'Player'}`);const input=document.createElement('input');input.maxLength=20;input.value=account?.name||'Player';input.setAttribute('aria-label','Nama pemain');area.append(input);modalButton(area,'Simpan nama',async()=>{try{const res=await fetch('/api/spin/profile',{method:'PATCH',credentials:'same-origin',headers:{'Content-Type':'application/json','X-UNO-Client':'spin-ui'},body:JSON.stringify({name:input.value})});const value=await res.json();if(!res.ok)throw Error(value.detail||'Tidak dapat menyimpan nama');syncAccount(value.account);closeModal();say('Nama berhasil disimpan.');}catch(e){paragraph(area,e.message);}});}
let stateLoading=false;
async function loadState(quiet=false){
  if(stateLoading)return;
  stateLoading=true;
  try{const data=await api('/state');ruleset=data.rules||ruleset;
    const payouts=ruleset?.celebrations?.map(t=>t.multiplier).filter(Number.isFinite);
    if(payouts?.length){$('reward-range').textContent=ruleset.numeric_bonus?'≤'+Math.max(...payouts)+'×':Math.min(...payouts)+'×–'+Math.max(...payouts)+'×';$('combination-label').textContent=ruleset.numeric_bonus?'5 rank + bonus':'5 kombinasi';}
    syncAccount(data.account);currentRound=data.round;
    if(Array.isArray(ruleset?.stake_options)&&!isAuto){
      const selected=STAKES[stakeIndex],queued=nextBetIndex===null?null:STAKES[nextBetIndex];
      STAKES=[...ruleset.stake_options];
      stakeIndex=Math.max(0,STAKES.indexOf(selected));
      nextBetIndex=queued!==null&&STAKES.includes(queued)?STAKES.indexOf(queued):null;
    }
    if(data.round){paintRound(data.round);}else if(data.recent?.length){const lastSpin=data.recent[0];last={...lastSpin,complete:true,picked:3};paintRound(last);}else paintRound(null,true);
    const pending=pendingInfo();
    if(pending && ((data.round && data.round.picked>=pending.expected) ||
        (!data.round && pending.expected===3 && data.recent?.length))) {
      localStorage.removeItem(pendingKey);
    }
    if(data.round?.cards?.length)wheel.recover(data.round.cards.at(-1));
    else if(data.recent?.length && data.recent[0].cards?.length)wheel.recover(data.recent[0].cards.at(-1));
    applyNextBet();updateButtons();
    $('connection-status').textContent='ONLINE';
    if(!quiet)say(data.round?`Lanjutkan ronde: SPIN ${data.round.picked+1}/3`:'Sentuh SPIN untuk memilih kartu pertama');
  }catch(e){$('connection-status').textContent='OFFLINE';say(e.message);}
  finally{stateLoading=false;}
}
function recoverInitialConnection(){
  if(!account&&!document.hidden&&!isSpinning)void loadState();
}
window.addEventListener('online',recoverInitialConnection);
document.addEventListener('visibilitychange',recoverInitialConnection);
const initialConnectionTimer=setInterval(()=>{
  if(account){clearInterval(initialConnectionTimer);return;}
  recoverInitialConnection();
},8000);
function listeners(){
  // One delegated activation handles dynamic menus, touch, mouse and keyboard.
  // Capture before handlers disable/remove controls; no sound on scroll or disabled choices.
  document.addEventListener('click',event=>{
    const control=event.target.closest?.('button,summary,[role="button"],input[type="radio"],input[type="checkbox"],select');
    if(!control||control.matches(':disabled,[aria-disabled="true"]'))return;
    control.classList.remove('ui-pressed');
    control.classList.add('ui-pressed');
    setTimeout(()=>control.classList.remove('ui-pressed'),140);
    if(control.id==='boot-play')void Promise.resolve(window.UNOLuckSound?.unlock()).then(()=>sfx('tap')); // splash owns music activation
    else sfx('tap');
  },true);
  $('spin-btn').addEventListener('click',pickOne);
  $('turbo-btn').addEventListener('click',()=>{if(isSpinning)return;isTurbo=!isTurbo;updateButtons();void unlockAudio();say(isTurbo?'Turbo aktif, animasi lebih cepat.':'Turbo nonaktif.');});
  $('auto-btn').addEventListener('click',showAutoSettings);
  $('wallet-open').addEventListener('click',showWallet);
  $('gift-btn').addEventListener('click',showGift);
  $('profile-btn').addEventListener('click',showMenu);
  $('about-btn').addEventListener('click',showAbout);
  $('modal-back').addEventListener('click',showMenu);
  $('modal-close').addEventListener('click',closeModal);
  $('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal();});
  addEventListener('resize',layoutRing);
  // The intro is hands-free. Background Music is requested immediately on
  // entering gameplay, not only on a later touch or visibilitychange.
  window.addEventListener('uno:boot-finished',async()=>{
    if(!musicEnabled)return;
    // Splash PLAY activated a separate music lane inside the user's native
    // gesture. Unmute it immediately here, without Safari-blocked autoplay.
    const reserved=await window.UNOLuckSoundStudio?.activateMusicAtGameplay?.();
    if(reserved){
      void startMusic(); // records requested state; never restarts active media
      return;
    }
    void Promise.resolve(window.UNOLuckSoundStudio?.prepareMusicMedia?.())
      .then(()=>{if(musicEnabled&&!document.hidden)void startMusic();})
      .catch(error=>console.warn('[UNO GAMEPLAY BGM] preload',error));
  });
  const activate=()=>{
    if($('game-shell').classList.contains('is-booting'))return;
    // HTMLMediaElement.play() MUST run in the trusted iOS event before any
    // awaited AudioContext.resume(), otherwise WebKit may reject the request.
    if(musicEnabled&&window.UNOLuckSound?.webAudioState!=='running')
      void window.UNOLuckSoundStudio?.playMusicGesture?.();
    void unlockAudio().then(yes=>{
      const musicReady=!musicEnabled ||
        window.UNOLuckSound?.webAudioState==='running' ||
        window.UNOLuckSoundStudio?.isMusicMediaPlaying?.();
      if(yes&&musicReady){
        document.removeEventListener('pointerdown',activate,true);
        document.removeEventListener('touchend',activate,true);
      }
    });
  };
  document.addEventListener('pointerdown',activate,{passive:true,capture:true});
  document.addEventListener('touchend',activate,{passive:true,capture:true});
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){
      wheel?.stopSpinAudio();
      wheel?.stopIdle();
      stopMusic();
      if(isAuto)cancelAuto=true;
    }else{
      if(wheel?.active)wheel.startSpinAudio();
      if(!isSpinning)wheel?.startIdle();
      if(!$('game-shell').classList.contains('is-booting'))void startMusic();
    }
  });
}
resetRing();listeners();window.UNOLuckSound?.setEnabled(sfxEnabled);loadState();

