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
let account = null, currentRound=null, last=null, stakeIndex=1, isSpinning=false;
let isTurbo=false, isAuto=false, cancelAuto=false, ringCards=[], wheel=null;
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
  $('gift-btn').disabled=!a.daily_available;
  $('gift-btn').title=a.daily_available?'Hadiah harian tersedia':'Hadiah sudah diklaim';
  updateButtons();
}
function updateButtons(){
  const stake=currentRound?.stake ?? STAKES[stakeIndex];
  $('spin-btn').disabled=isSpinning||isAuto||!account||(!currentRound && account.balance<stake);
  $('turbo-btn').disabled=isSpinning;
  $('turbo-btn').setAttribute('aria-pressed',String(isTurbo));
  $('auto-btn').setAttribute('aria-pressed',String(isAuto));
  $('auto-label').textContent=isAuto?'STOP':'AUTO';
}
async function api(path,method='GET',body){
  const req={method,credentials:'same-origin',headers:{}};
  if(method!=='GET'){req.headers['Content-Type']='application/json';req.headers['X-UNO-Client']='spin-ui';req.body=JSON.stringify(body??{});}
  let response;
  try{response=await fetch('/api/orbit'+path,req);}catch(_){throw Error('Koneksi terputus. Periksa internet dan coba lagi.');}
  let data;try{data=await response.json();}catch(_){throw Error('Server mengirim respons tak valid.');}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`HTTP ${response.status}`);
  return data;
}
async function legacyBonus(endpoint){
  const response=await fetch('/api/spin/'+endpoint,{method:'POST',headers:{'X-UNO-Client':'spin-ui','Content-Type':'application/json'},credentials:'same-origin',body:'{}'});
  const data=await response.json();
  if(!response.ok)throw Error(data.detail||'Gagal mengklaim hadiah');
  return data;
}
function sfx(name){if(sfxEnabled)window.UNOLuckSound?.play(name);}
function startMusic(){if(musicEnabled)window.UNOLuckSound?.music(true);}
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
  unlockAudio().then(ok=>{if(ok){sfx('tap');sfx('spin');}});
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
    sfx('tick');
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
async function autoLoop(){
  if(isAuto){cancelAuto=true;updateButtons();say('AUTO berhenti setelah SPIN saat ini.');return;}
  if(isSpinning||!account)return;
  isAuto=true;cancelAuto=false;updateButtons();
  // Ten full rounds maximum; each round always consists of three manual-equivalent picks.
  for(let rounds=0;rounds<10&&!cancelAuto&&!document.hidden;rounds++){
    for(let k=(currentRound?.picked||0);k<3&&!cancelAuto&&!document.hidden;k++){
      const done=await pickOne();if(!done||cancelAuto)break;
      await wait(isTurbo?130:230);
    }
    if(!cancelAuto)await wait(isTurbo?270:510);
  }
  isAuto=false;updateButtons();
}
function modal(title){$('modal-title').textContent=title;$('modal-content').replaceChildren();if(!$('modal').open)$('modal').showModal();return $('modal-content');}
function paragraph(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);return p;}
function modalButton(parent,text,fn){const b=document.createElement('button');b.textContent=text;b.type='button';b.addEventListener('click',fn);parent.append(b);return b;}
function closeModal(){if($('modal').open)$('modal').close();}
async function claimDaily(){try{const x=await legacyBonus('daily');syncAccount(x.account);sfx('coin');say(`Hadiah +${idMoney(x.credited)} koin virtual`);closeModal();}catch(e){say(e.message);}}
async function claimRefill(){try{const x=await legacyBonus('refill');syncAccount(x.account);sfx('coin');say(`Refill gratis +${idMoney(x.credited)} koin`);closeModal();}catch(e){say(e.message);}}
function showWallet(){const area=modal('Koin Virtual');paragraph(area,`Saldo saat ini ${idMoney(account?.balance||0)} koin.`);paragraph(area,'Tidak ada deposit, penarikan tunai, jual-beli koin, atau hadiah bernilai uang.');modalButton(area,'🎁 Klaim +250 harian',claimDaily).disabled=!account?.daily_available;modalButton(area,'✦ Refill gratis +1.000',claimRefill).disabled=!account?.refill_available;}
async function showHistory(){const area=modal('Riwayat Ronde');try{const x=await api('/state');const list=x.recent||[];if(!list.length)paragraph(area,'Belum ada ronde selesai.');for(const item of list){const row=document.createElement('div');row.className='history-line';row.textContent=`${item.tier?.title||(item.combo==='COLOR_MATCH'?'LUCKY COLOR WIN':'NO MATCH')} · Biaya ${idMoney(item.stake)} · ${item.delta>=0?'+':''}${idMoney(item.delta)} koin`;area.append(row);}}catch(e){paragraph(area,e.message);}}
function showRules(){const area=modal('Aturan UNO LUCK Color Match');paragraph(area,'Satu ronde memiliki tiga SPIN: kartu kiri, tengah, lalu kanan. Kartu yang terpilih adalah kartu tepat di posisi tengah atas carousel saat berhenti.');paragraph(area,'Biaya ronde hanya dipotong sekali pada SPIN pertama. Tiga warna sama memenangkan salah satu bonus 2×, 10×, 30×, 80×, atau 200× setelah SPIN ketiga.');paragraph(area,'Peluang Color Match 80% per ronde, NO MATCH 20%. Dari ronde menang: Rank 1 0,01%; Rank 2 0,09%; Rank 3 0,4%; Rank 4 3%; Rank 5 96,5%. Semua hasil independen dari putaran sebelumnya; tidak ada jaminan jackpot berdasarkan jumlah cycle.');paragraph(area,'Angka kartu, Reverse, Skip dan +2 hanya simbol dalam mode ini. AUTO hingga 10 ronde dan TURBO hanya mengubah kecepatan animasi, bukan peluang menang.');paragraph(area,'Semua koin virtual tidak memiliki nilai uang dan tidak dapat dibeli atau dicairkan. Batas saldo 1.000.000 koin dapat membatasi payout yang benar-benar dikreditkan. Peluang tinggi dan bonus besar berarti ekonomi koin gratis dapat terus bertambah.');}
function showStakeChoices(){const area=modal('Biaya SPIN');paragraph(area,'Pilih biaya satu ronde tiga SPIN. Perubahan hanya dapat dilakukan sebelum ronde dimulai.');for(const [i,cost] of STAKES.entries()){const btn=modalButton(area,`${cost===STAKES[stakeIndex]?'✓ ':''}${idMoney(cost)} koin`,()=>{stakeIndex=i;paintRound(null,true);updateButtons();closeModal();say(`Biaya ronde berikutnya ${idMoney(cost)} koin.`);});btn.disabled=!!currentRound;}}
function showCelebrationGallery(){
  const area=modal('Galeri Celebration · Demo Visual');
  paragraph(area,'Pilih efek untuk melihat animasi dan mendengar suara. Mode demo tidak mengubah hasil kartu, saldo, atau riwayat.');
  for(let rank=1;rank<=5;rank++){
    const item=window.UNOLuckCelebration?.registry[rank];
    if(!item)continue;
    modalButton(area,`PERINGKAT ${rank} · ${item.name} · ${item.multiplier}×`,async()=>{
      closeModal();await unlockAudio();window.UNOLuckCelebration.present(null,{preview:true,rank});
    });
  }
}
async function testSound(){
  closeModal();
  const ok=await unlockAudio();
  if(!ok){say('Audio belum aktif. Sentuh Main dengan Suara lalu coba lagi.');return;}
  const heard=await window.UNOLuckSound?.testSound();
  say(heard?'Tes audio diputar. Pastikan volume media iPhone aktif.':`Audio gagal: ${window.UNOLuckSound?.lastError||'coba sentuh MAIN DENGAN SUARA'}`);
}
function showSoundVolume(){
  const area=modal('Audio Mixer · UNO LUCK');
  paragraph(area,'Master, Musik dan SFX mengikuti pengaturan Sound Cloud yang dipublikasikan. Admin dapat mengubah di desktop dan perubahan akan tersinkron. Volume fisik iPhone tetap mengikuti iOS.');
  for(const [title,property,setter] of [
    ['MASTER','masterVolume','setMasterVolume'],
    ['MUSIC','musicVolume','setMusicVolume'],
    ['SFX','volume','setVolume']]){
    const label=paragraph(area,title+' · '+Math.round((window.UNOLuckSound?.[property]??0)*100)+'%');
    const input=document.createElement('input');
    input.type='range';input.min='0';input.max='100';input.step='5';
    input.value=String(Math.round((window.UNOLuckSound?.[property]??0)*100));
    input.setAttribute('aria-label',title+' Volume');
    input.addEventListener('input',()=>{
      const n=Number(input.value);
      window.UNOLuckSound?.[setter](n/100);
      label.textContent=title+' · '+n+'%';
      if(title==='SFX'&&n>0){sfxEnabled=true;localStorage.setItem(MUTE_EFFECTS,'on');window.UNOLuckSound?.setEnabled(true);}
      window.UNOLuckSoundStudio?.schedulePublishMixer?.();
    });
    area.append(input);
  }
  modalButton(area,'TES AUDIO',async()=>{
    const ok=await unlockAudio();
    if(!ok){say('Audio belum aktif: '+(window.UNOLuckSound?.lastError||'periksa volume perangkat'));return;}
    const heard=await window.UNOLuckSound.testSound();
    say(heard?'Tes fanfare diputar. Jika senyap, naikkan volume media iPhone.':
      'Tes audio gagal: '+(window.UNOLuckSound?.lastError||'periksa status audio'));
  });
}
function showSoundStudio(){
  const area=modal('SOUND STUDIO · CUSTOM EFFECTS');
  if(window.UNOLuckSoundStudio)window.UNOLuckSoundStudio.show(area);
  else paragraph(area,'Sound Studio belum tersedia. Refresh halaman.');
}
function showMenu(){const area=modal('Menu UNO LUCK');modalButton(area,'Aturan & Peluang 80%',showRules);modalButton(area,'Biaya SPIN: '+idMoney(currentRound?.stake??STAKES[stakeIndex]),showStakeChoices);modalButton(area,'Riwayat Ronde',showHistory);modalButton(area,'Galeri 5 Celebration (demo)',showCelebrationGallery);modalButton(area,'Sound Studio · 12 Custom Sound Effects',showSoundStudio);
modalButton(area,'Mixer Master · Musik · SFX',showSoundVolume);modalButton(area,'Tes Suara Meriah',testSound);modalButton(area,'Koin Virtual',showWallet);modalButton(area,musicEnabled?'Matikan musik':'Nyalakan musik',()=>{musicEnabled=!musicEnabled;localStorage.setItem(MUTE_MUSIC,musicEnabled?'on':'off');if(!musicEnabled)stopMusic();else unlockAudio();closeModal();});modalButton(area,sfxEnabled?'Matikan efek suara':'Nyalakan efek suara',()=>{sfxEnabled=!sfxEnabled;localStorage.setItem(MUTE_EFFECTS,sfxEnabled?'on':'off');window.UNOLuckSound?.setEnabled(sfxEnabled);if(sfxEnabled)unlockAudio().then(()=>sfx('tap'));closeModal();});paragraph(area,'UNO LUCK v1.1 · staging · hadiah virtual tanpa nilai tunai.');}
function showProfile(){const area=modal('Profil Pemain');paragraph(area,`Nama saat ini: ${account?.name||'Player'}`);const input=document.createElement('input');input.maxLength=20;input.value=account?.name||'Player';input.setAttribute('aria-label','Nama pemain');area.append(input);modalButton(area,'Simpan nama',async()=>{try{const res=await fetch('/api/spin/profile',{method:'PATCH',credentials:'same-origin',headers:{'Content-Type':'application/json','X-UNO-Client':'spin-ui'},body:JSON.stringify({name:input.value})});const value=await res.json();if(!res.ok)throw Error(value.detail||'Tidak dapat menyimpan nama');syncAccount(value.account);closeModal();say('Nama berhasil disimpan.');}catch(e){paragraph(area,e.message);}});}
async function loadState(quiet=false){
  try{const data=await api('/state');syncAccount(data.account);currentRound=data.round;
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
}
function listeners(){
  $('spin-btn').addEventListener('click',pickOne);
  $('turbo-btn').addEventListener('click',()=>{if(isSpinning)return;isTurbo=!isTurbo;updateButtons();unlockAudio().then(()=>sfx('tap'));say(isTurbo?'Turbo aktif, peluang tetap 80%.':'Turbo nonaktif.');});
  $('auto-btn').addEventListener('click',autoLoop);
  $('wallet-open').addEventListener('click',showWallet);
  $('gift-btn').addEventListener('click',claimDaily);
  $('menu-open').addEventListener('click',showMenu);
  $('profile-btn').addEventListener('click',showProfile);
  $('modal-close').addEventListener('click',closeModal);
  $('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal();});
  addEventListener('resize',layoutRing);
  const activate=()=>{unlockAudio().then(yes=>{if(yes){document.removeEventListener('pointerdown',activate,true);document.removeEventListener('touchend',activate,true);}});};
  document.addEventListener('pointerdown',activate,{passive:true,capture:true});
  document.addEventListener('touchend',activate,{passive:true,capture:true});
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){
      wheel?.stopIdle();
      stopMusic();
      if(isAuto)cancelAuto=true;
    }else{
      if(!isSpinning)wheel?.startIdle();
      startMusic();
    }
  });
}
resetRing();listeners();window.UNOLuckSound?.setEnabled(sfxEnabled);loadState();
