'use strict';
/* UNO LUCK v1.1: server-picked three cards, one GPU wheel with independent transparent card assets. */
const $ = id => document.getElementById(id);
const idMoney = n => new Intl.NumberFormat('id-ID').format(n);
const COLORS = ['red','blue','yellow','green'];
const FACES = ['0','1','2','3','4','5','6','7','8','9','SKIP','REVERSE','+2'];
const STAKES = [10,25,50,100,250];
const RING_COUNT = 9;
const MUTE_MUSIC = 'uno_orbit_music';
const MUTE_EFFECTS = 'uno_orbit_sfx';
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let account = null, currentRound=null, last=null, ruleset=null, stakeIndex=1, isSpinning=false;
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
function syncAccount(a){
  if(!a)return;account=a;
  if(window.UNOLuckMotion)window.UNOLuckMotion.balance(a.balance,true);
  else $('wallet-balance').textContent=idMoney(a.balance);
  $('gift-btn').disabled=!a.daily_available&&!a.refill_available;
  $('gift-btn').title='Gift · hadiah harian dan refill';
  const total=$('coin-total');if(total)total.textContent=idMoney(a.balance);
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
  unlockAudio().then(ok=>{if(ok&&wheel?.active)sfx('tap');});
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
      if(sfxEnabled && last.combo!=='COLOR_MATCH')window.UNOLuckSound?.result(false);
      window.UNOLuckMotion?.result(last);
      if(last.combo==='COLOR_MATCH'){
        const title=last.tier?.title||'LUCKY COLOR WIN';
        say(`${title}! Kembali ${idMoney(last.payout)} · selisih ${last.delta>=0?'+':''}${idMoney(last.delta)} koin`);
        winBurst(last.cards[0]);
        await window.UNOLuckCelebration?.present(last);
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
    window.UNOLuckMotion?.endSpin();
    wheel?.startIdle();
    updateButtons();
  }
}
function canChangeBet(){return !!account&&!isSpinning&&!isAuto&&!currentRound&&!pendingInfo();}
function autoBudget(rounds){return (rounds-(currentRound?1:0))*(currentRound?.stake??STAKES[stakeIndex]);}
async function autoLoop(roundLimit){
  if(isAuto||isSpinning||!account||pendingInfo()||document.hidden||
      !AUTO_ROUNDS.includes(roundLimit)||account.balance<autoBudget(roundLimit))return;
  // Keep the confirmed setup stake after a restored paid round completes.
  const autoStakeIndex=STAKES.indexOf(currentRound?.stake??STAKES[stakeIndex]);
  if(autoStakeIndex<0)return;
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
  isAuto=false;updateButtons();
}
function modal(title){$('modal').classList.remove('coin-modal','player-panel');$('modal').querySelector('.panel-actions')?.remove();$('modal-title').textContent=title;$('modal-content').replaceChildren();$('modal-content').scrollTop=0;if(!$('modal').open)$('modal').showModal();return $('modal-content');}
function paragraph(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);return p;}
function modalButton(parent,text,fn){const b=document.createElement('button');b.textContent=text;b.type='button';b.addEventListener('click',fn);parent.append(b);return b;}
function closeModal(){if($('modal').open)$('modal').close();}
function panelNode(tag,klass,text){const el=document.createElement(tag);el.className=klass;if(text!==undefined)el.textContent=text;return el;}
function playerPanel(title){const area=modal(title);$('modal').classList.add('player-panel');return area;}
function panelAction(text,fn){const footer=panelNode('div','panel-actions');$('modal').querySelector('.modal-card').append(footer);const btn=modalButton(footer,text,fn);btn.className='panel-primary';return btn;}
async function claimDaily(){try{const x=await legacyBonus('daily');syncAccount(x.account);sfx('coin');say(`Hadiah +${idMoney(x.credited)} koin virtual`);closeModal();}catch(e){say(e.message);}}
async function claimRefill(){try{const x=await legacyBonus('refill');syncAccount(x.account);sfx('coin');say(`Refill gratis +${idMoney(x.credited)} koin`);closeModal();}catch(e){say(e.message);}}
function showGift(){
  const area=modal('Gift');
  paragraph(area,'Hadiah koin virtual untuk bermain.');
  modalButton(area,'Klaim +250 harian',claimDaily).disabled=!account?.daily_available;
  modalButton(area,'Refill gratis +1.000',claimRefill).disabled=!account?.refill_available;
}
async function showWallet(){
  const area=modal('Coin');$('modal').classList.add('coin-modal');
  const summary=document.createElement('div');summary.className='coin-summary';
  paragraph(summary,'Total Coin');
  const total=document.createElement('strong');total.id='coin-total';total.textContent=idMoney(account?.balance||0);
  total.setAttribute('aria-live','polite');summary.append(total);
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
      const result=document.createElement('strong');result.textContent=item.tier?.title||(item.combo==='COLOR_MATCH'?'LUCKY COLOR WIN':'NO MATCH');
      const values=document.createElement('p');values.textContent=`BET ${idMoney(item.stake)} · PAYOUT ${idMoney(item.payout)} · WIN ${item.delta>=0?'+':''}${idMoney(item.delta)}`;
      row.append(time,result,values);history.append(row);
    }
    if(data.recent?.length)paragraph(history,'Menampilkan '+data.recent.length+' bet terakhir.');
  }catch(error){if(history.isConnected){history.replaceChildren();paragraph(history,error.message);}}
}
function showRules(){
  const area=playerPanel('Game Rules');
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
  paragraph(area,'NO MATCH · Tidak ada kombinasi yang cocok, tidak ada payout.');
  paragraph(details,'Tidak ada jaminan jackpot atau bonus setelah sejumlah spin.');
  paragraph(details,'AUTO maksimal 10 ronde, TURBO hanya mengubah animasi. Koin tidak mempunyai nilai uang dan tidak dapat dibeli atau dicairkan. Batas saldo 1.000.000 koin dapat menurunkan jumlah yang benar-benar dikreditkan. Ini bukan aturan permainan UNO resmi.');
  area.append(details);
}
function showStakeChoices(){
  const area=playerPanel('Bet Setting');let selected=stakeIndex;
  area.append(panelNode('p','panel-eyebrow','BET PER RONDE'));
  const amount=panelNode('strong','panel-amount',idMoney(currentRound?.stake??STAKES[selected])+' Coin');area.append(amount);
  paragraph(area,'Satu BET untuk tiga SPIN. Pilih nominal, lalu simpan untuk ronde berikutnya.');
  const grid=panelNode('div','bet-grid');grid.setAttribute('role','group');grid.setAttribute('aria-label','Pilihan BET');area.append(grid);
  for(const [i,cost] of STAKES.entries()){
    const btn=modalButton(grid,idMoney(cost)+' Coin',()=>{
      if(!canChangeBet())return;selected=i;amount.textContent=idMoney(cost)+' Coin';
      for(const item of grid.children)item.setAttribute('aria-pressed',String(item===btn));
    });
    btn.dataset.bet=String(cost);btn.setAttribute('aria-pressed',String(cost===(currentRound?.stake??STAKES[selected])));btn.disabled=!canChangeBet();
  }
  if(!canChangeBet())paragraph(area,'BET terkunci selama ronde, SPIN, atau AUTO aktif. Selesaikan ronde sebelum mengubahnya.');
  const save=panelAction('GUNAKAN BET',()=>{if(!canChangeBet())return;stakeIndex=selected;paintRound(null,true);updateButtons();closeModal();say(`Bet berikutnya ${idMoney(STAKES[selected])} Coin.`);});
  save.disabled=!canChangeBet();
}
function showAutoSettings(){
  if(isAuto){cancelAuto=true;updateButtons();say('AUTO berhenti setelah SPIN saat ini.');return;}
  if(isSpinning||!account)return;
  const area=playerPanel('Auto Play');let selected=autoRounds;
  area.append(panelNode('p','panel-eyebrow','PILIH JUMLAH RONDE'));
  paragraph(area,'Setiap ronde membuka tiga kartu. AUTO dapat dihentikan setelah SPIN yang sedang berjalan.');
  const grid=panelNode('div','auto-grid');grid.setAttribute('role','group');grid.setAttribute('aria-label','Jumlah ronde AUTO');area.append(grid);
  for(const rounds of AUTO_ROUNDS){
    const btn=modalButton(grid,rounds+' ronde',()=>{selected=rounds;refresh();});btn.dataset.rounds=String(rounds);
  }
  const budget=panelNode('dl','auto-budget');
  const total=panelNode('dd','',''),balance=panelNode('dd','',idMoney(account.balance)+' Coin');
  budget.append(panelNode('dt','','BET per ronde'),panelNode('dd','',idMoney(currentRound?.stake??STAKES[stakeIndex])+' Coin'),
    panelNode('dt','','Total kebutuhan'),total,panelNode('dt','','Saldo tersedia'),balance);area.append(budget);
  const message=panelNode('p','panel-note','');message.setAttribute('role','status');area.append(message);
  if(currentRound)paragraph(area,'Ronde yang sudah dimulai dihitung sebagai ronde pertama. BET ronde tersebut sudah dipotong.');
  else paragraph(area,'Kebutuhan coin dihitung tanpa mengandalkan hadiah dari ronde berikutnya.');
  const start=panelAction('MULAI AUTO',()=>{
    if(isAuto||isSpinning||pendingInfo()||!account||account.balance<autoBudget(selected)){refresh();return;}
    autoRounds=selected;closeModal();void autoLoop(selected);
  });start.id='auto-start';
  function refresh(){
    for(const btn of grid.children)btn.setAttribute('aria-pressed',String(Number(btn.dataset.rounds)===selected));
    const required=autoBudget(selected);total.textContent=idMoney(required)+' Coin';balance.textContent=idMoney(account?.balance??0)+' Coin';
    const blocked=!!pendingInfo()||isSpinning||isAuto||!account;
    start.disabled=blocked||account.balance<required;
    message.textContent=blocked?'Selesaikan sinkronisasi SPIN sebelum memulai AUTO.':account.balance<required?'Coin belum cukup. Pilih jumlah ronde lebih kecil atau ubah BET.':`${selected} ronde · ${isTurbo?'TURBO aktif':'Kecepatan normal'}`;
  }
  refresh();
}
function showMenu(){
  const area=modal('Menu');
  modalButton(area,'Game Rules',showRules);
  modalButton(area,'Profile',showProfile);
  const sound=modalButton(area,`Sound ${musicEnabled||sfxEnabled?'On':'Off'}`,()=>{
    const enabled=!(musicEnabled||sfxEnabled);musicEnabled=enabled;sfxEnabled=enabled;
    localStorage.setItem(MUTE_MUSIC,enabled?'on':'off');localStorage.setItem(MUTE_EFFECTS,enabled?'on':'off');
    window.UNOLuckSound?.setEnabled(enabled);
    if(enabled)void unlockAudio();else{stopMusic();window.UNOLuckSound?.stopCelebration?.();}
    sound.textContent=`Sound ${enabled?'On':'Off'}`;sound.setAttribute('aria-pressed',String(enabled));
  });
  sound.setAttribute('aria-pressed',String(musicEnabled||sfxEnabled));
  modalButton(area,'Bet Setting',showStakeChoices);
}
function showProfile(){const area=modal('Profil Pemain');paragraph(area,`Nama saat ini: ${account?.name||'Player'}`);const input=document.createElement('input');input.maxLength=20;input.value=account?.name||'Player';input.setAttribute('aria-label','Nama pemain');area.append(input);modalButton(area,'Simpan nama',async()=>{try{const res=await fetch('/api/spin/profile',{method:'PATCH',credentials:'same-origin',headers:{'Content-Type':'application/json','X-UNO-Client':'spin-ui'},body:JSON.stringify({name:input.value})});const value=await res.json();if(!res.ok)throw Error(value.detail||'Tidak dapat menyimpan nama');syncAccount(value.account);closeModal();say('Nama berhasil disimpan.');}catch(e){paragraph(area,e.message);}});}
let stateLoading=false;
async function loadState(quiet=false){
  if(stateLoading)return;
  stateLoading=true;
  try{const data=await api('/state');ruleset=data.rules||ruleset;syncAccount(data.account);currentRound=data.round;
    if(data.round){paintRound(data.round);}else if(data.recent?.length){const lastSpin=data.recent[0];last={...lastSpin,complete:true,picked:3};paintRound(last);}else paintRound(null,true);
    const pending=pendingInfo();
    if(pending && ((data.round && data.round.picked>=pending.expected) ||
        (!data.round && pending.expected===3 && data.recent?.length))) {
      localStorage.removeItem(pendingKey);
    }
    if(data.round?.cards?.length)wheel.recover(data.round.cards.at(-1));
    else if(data.recent?.length && data.recent[0].cards?.length)wheel.recover(data.recent[0].cards.at(-1));
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
  $('spin-btn').addEventListener('click',pickOne);
  $('turbo-btn').addEventListener('click',()=>{if(isSpinning)return;isTurbo=!isTurbo;updateButtons();unlockAudio().then(()=>sfx('tap'));say(isTurbo?'Turbo aktif, animasi lebih cepat.':'Turbo nonaktif.');});
  $('auto-btn').addEventListener('click',showAutoSettings);
  $('wallet-open').addEventListener('click',showWallet);
  $('gift-btn').addEventListener('click',showGift);
  $('profile-btn').addEventListener('click',showMenu);
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

