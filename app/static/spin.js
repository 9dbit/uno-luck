'use strict';
/* UNO LUCK SPIN v0.4 | free, non-redeemable virtual coins; all outcomes server-authoritative. */
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('id-ID').format(value);
const costOptions = [10,25,50,100,250];
const COLORS = ['red','blue','yellow','green'];
const LABELS = {red:'MERAH',blue:'BIRU',yellow:'KUNING',green:'HIJAU',wild:'WILD'};
const PREVIEW_FACES = ['0','1','3','4','6','7','8','9','SKIP','REVERSE','+2'];
const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let account=null, rules=null, last=null, stakeIndex=1;
let spinning=false, turbo=false, auto=false, abortAuto=false, autoRemaining=0, busy=false;
let toastTimer=null, balanceAnimation=null;
let musicEnabled=localStorage.getItem('ul_spin_music')!=='off';
let sfxEnabled=localStorage.getItem('ul_spin_sfx')!=='off';
let audio=null, musicTimer=null, musicStep=0, nextMusicAt=0;
let reelAnimations=[];
function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
function toast(text){
  // Inline announcer instead of a floating overlay that hides mobile controls.
  const el=$('spin-announcement');const previous=el.textContent;
  el.textContent=text;el.title=text;
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>{if(el.textContent===text){el.textContent=previous;el.title='';}},2800);
}
function note(text){$('connection-status').textContent=text;}
function audioReady(){
  try {
    if(!audio)audio=new (window.AudioContext||window.webkitAudioContext)();
    if(audio.state==='suspended')audio.resume().catch(()=>{});
    startMusic();
  }catch(_){audio=null;}
}
function tone(freq,when,length=0.12,volume=0.035,wave='triangle'){
  if(!audio||audio.state==='closed')return;
  const osc=audio.createOscillator(),gain=audio.createGain();
  osc.type=wave;osc.frequency.setValueAtTime(Math.max(25,freq),when);
  gain.gain.setValueAtTime(0.0001,when);
  gain.gain.exponentialRampToValueAtTime(Math.max(.0002,volume),when+0.006);
  gain.gain.exponentialRampToValueAtTime(0.0001,when+length);
  osc.connect(gain).connect(audio.destination);osc.start(when);osc.stop(when+length+.012);
}
function musicStepSchedule(step,when){
  const scale=[523.25,587.33,659.26,783.99,880,783.99,659.26,587.33,659.26,783.99,987.77,880,783.99,659.26,587.33,523.25];
  if(step%2===0)tone(scale[step],when,.155,.017,'triangle');
  if(step%4===0)tone([130.81,164.81,196,164.81][Math.floor(step/4)],when,.29,.023,'sine');
  if(step%4===2)tone(940,when,.035,.008,'square');
  if(step===7||step===15)tone(scale[step]/2,when,.12,.012,'sine');
}
function startMusic(){
  if(!musicEnabled||!audio||document.hidden||musicTimer)return;
  nextMusicAt=audio.currentTime+.05;musicStep=0;
  musicTimer=setInterval(()=>{
    if(!audio||!musicEnabled||document.hidden)return;
    const stepSeconds=60/124/2;
    while(nextMusicAt<audio.currentTime+.16){musicStepSchedule(musicStep%16,nextMusicAt);nextMusicAt+=stepSeconds;musicStep++;}
  },80);
}
function stopMusic(){if(musicTimer){clearInterval(musicTimer);musicTimer=null;}}
function sound(type,index=0){
  if(!sfxEnabled||!audio)return;
  const t=audio.currentTime+.007;
  if(type==='tap'){tone(420,t,.062,.055,'triangle');tone(580,t+.045,.085,.048,'sine');}
  else if(type==='start'){tone(280,t,.10,.055,'sawtooth');tone(510,t+.085,.14,.055,'triangle');}
  else if(type==='tick'){tone(310+index*90,t,.09,.075,'square');tone(740+index*140,t+.028,.12,.04,'triangle');}
  else if(type==='win'){
    [659.26,880,1046.5,1318.5].forEach((f,i)=>tone(f,t+i*.095,.32,.072-i*.009,'triangle'));
    for(let i=0;i<6;i++)tone(1150+i*135,t+.25+i*.037,.16,.035,'sine');
  }else if(type==='coin'){
    [1480,1975,2469].forEach((f,i)=>tone(f,t+i*.055,.16,.03,'sine'));
  }else if(type==='lose')tone(190,t,.17,.026,'triangle');
}
function syncAudioControls(){
  const music=$('music-btn'),sfx=$('sfx-btn');
  music.setAttribute('aria-pressed',String(musicEnabled));
  music.querySelector('small').textContent=musicEnabled?'MUSIK':'MUTE';
  sfx.setAttribute('aria-pressed',String(sfxEnabled));
  sfx.querySelector('small').textContent=sfxEnabled?'EFEK':'MUTE';
}
function toggleMusic(){musicEnabled=!musicEnabled;localStorage.setItem('ul_spin_music',musicEnabled?'on':'off');audioReady();if(musicEnabled)startMusic();else stopMusic();syncAudioControls();}
function toggleSfx(){sfxEnabled=!sfxEnabled;localStorage.setItem('ul_spin_sfx',sfxEnabled?'on':'off');audioReady();syncAudioControls();if(sfxEnabled)sound('tap');}
async function api(path,method='GET',payload){
  const cfg={method,credentials:'same-origin',headers:{}};
  if(method!=='GET'){
    cfg.headers['Content-Type']='application/json';cfg.headers['X-UNO-Client']='spin-ui';
    if(payload!==undefined)cfg.body=JSON.stringify(payload);
  }
  let response;
  try{response=await fetch('/api/spin'+path,cfg);}catch(_){throw Error('Koneksi ke server terputus. Periksa internet.');}
  let data;try{data=await response.json();}catch(_){throw Error('Server mengirim respons yang tidak valid.');}
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`Server error ${response.status}`);
  return data;
}
function syncAccount(next,{animate=false,from=null}={}){
  if(!next)return;
  const previous=from===null?(account?.balance ?? next.balance):from;
  account=next;$('profile-label').textContent=next.name;
  $('level-number').textContent=next.level;
  const gift=$('gift-btn');gift.disabled=!next.daily_available;
  gift.title=next.daily_available?'Hadiah harian +250':'Hadiah harian sudah diklaim';
  if(!animate||previous===next.balance||reducedMotion){$('wallet-balance').textContent=money(next.balance);}
  else animateBalance(previous,next.balance);
  renderCost();
}
function animateBalance(from,to){
  if(balanceAnimation)cancelAnimationFrame(balanceAnimation);
  const start=performance.now(),duration=620;
  const step=now=>{
    const p=Math.min(1,(now-start)/duration),ease=1-Math.pow(1-p,3);
    $('wallet-balance').textContent=money(Math.round(from+(to-from)*ease));
    if(p<1)balanceAnimation=requestAnimationFrame(step);else balanceAnimation=null;
  };
  balanceAnimation=requestAnimationFrame(step);
}
function renderCost(){
  const stake=costOptions[stakeIndex];
  $('stake-value').textContent='✦ '+money(stake);
  $('stake-minus').disabled=spinning||auto||stakeIndex===0;
  $('stake-plus').disabled=spinning||auto||stakeIndex===costOptions.length-1;
  $('place-btn').disabled=spinning||auto||!account||account.balance<stake;
  $('place-btn').classList.toggle('ready',!spinning&&!auto&&!!account&&account.balance>=stake);
  $('last-stake').textContent=money(last?last.stake:stake);
}
function setBusy(flag){
  spinning=flag;$('turbo-btn').disabled=flag;
  $('place-btn').querySelector('span').textContent=flag?'SPIN!':'PLACE';
  $('place-btn').querySelector('small').textContent=flag?'REELS BERPUTAR':'TAP TO SPIN';
  renderCost();
}
function cardElement(card,winning=false){
  const el=document.createElement('div');el.className='metal-card'+(winning?' match':'');
  el.dataset.color=card.color;
  el.setAttribute('aria-label',`${LABELS[card.color]||card.color} ${card.face}`);
  const inner=document.createElement('div');inner.className='card-inner';
  for(const edge of ['top','bottom']){const corner=document.createElement('span');corner.className='face-corner'+(edge==='bottom'?' bottom':'');corner.textContent=card.face;inner.append(corner);}
  const symbol=document.createElement('span');symbol.className='face-symbol';symbol.textContent=({SKIP:'⊘',REVERSE:'⇄','+2':'+2'})[card.face]||card.face;
  inner.append(symbol);el.append(inner);return el;
}
function backCard(){const el=document.createElement('div');el.className='metal-card card-back';const inner=document.createElement('div');inner.className='card-inner';const label=document.createElement('span');label.className='card-back-mark';label.innerHTML='UNO<small>LUCK</small>';inner.append(label);el.append(inner);return el;}
function slotTile(card,winning=false){const tile=document.createElement('div');tile.className='slot-tile';tile.append(card?cardElement(card,winning):backCard());return tile;}
function windows(){return [...document.querySelectorAll('.slot-window')];}
function layoutReels(){for(const win of windows()){win.style.setProperty('--reel-height',`${Math.max(1,win.getBoundingClientRect().height)}px`);}}
function paintCards(cards,winning=false){
  layoutReels();windows().forEach((win,index)=>{
    win.classList.remove('rolling','is-stopped');
    const track=win.querySelector('.slot-track');track.getAnimations().forEach(a=>a.cancel());
    track.style.transform='translateY(0)';track.replaceChildren(slotTile(cards?.[index]||null,winning));
  });
}
function randomPreview(){return {color:COLORS[Math.floor(Math.random()*4)],face:PREVIEW_FACES[Math.floor(Math.random()*PREVIEW_FACES.length)]};}
function startReels(){
  $('win-burst').replaceChildren();$('reel-stage').classList.remove('is-win','win-pulse');
  layoutReels();reelAnimations.forEach(a=>a.cancel());reelAnimations=[];
  windows().forEach((win,index)=>{
    win.classList.remove('is-stopped');win.classList.add('rolling');
    const track=win.querySelector('.slot-track');track.replaceChildren(...Array.from({length:14},()=>slotTile(randomPreview())));
    const h=win.getBoundingClientRect().height;
    const duration=turbo?460:640;
    if(!reducedMotion)reelAnimations.push(track.animate([
      {transform:`translateY(-${2*h}px)`},{transform:`translateY(-${10*h}px)`}
    ],{duration:duration+index*47,easing:'linear',iterations:Infinity}));
    else track.style.transform=`translateY(-${3*h}px)`;
  });
}
async function stopReel(index,finalCard,winning){
  const win=windows()[index],track=win.querySelector('.slot-track');
  track.getAnimations().forEach(a=>a.cancel());win.classList.remove('rolling');
  win.style.setProperty('--reel-height',`${win.getBoundingClientRect().height}px`);
  if(reducedMotion){track.style.transform='translateY(0)';track.replaceChildren(slotTile(finalCard,winning));sound('tick',index);return;}
  const seq=Array.from({length:8},()=>slotTile(randomPreview()));seq.push(slotTile(finalCard,winning));
  track.replaceChildren(...seq);track.style.transform='translateY(0)';
  const height=win.getBoundingClientRect().height;
  const duration=turbo?300:440;
  const a=track.animate([
    {transform:'translateY(0)',filter:'blur(2px)'},
    {offset:.68,transform:`translateY(-${height*7.2}px)`,filter:'blur(1.5px)'},
    {transform:`translateY(-${height*8}px)`,filter:'blur(0)'}
  ],{duration,easing:'cubic-bezier(.16,.77,.22,1)',fill:'forwards'});
  try{await a.finished;}catch(_){}
  a.cancel();track.style.transform=`translateY(-${height*8}px)`;
  win.classList.add('is-stopped');sound('tick',index);
}
async function settleReels(cards,win){
  reelAnimations.forEach(a=>a.cancel());reelAnimations=[];
  for(let i=0;i<3;i++){await stopReel(i,cards[i],win);if(i<2)await sleep(turbo?42:95);}
}
function paintSummary(result){
  last=result;$('last-stake').textContent=money(result.stake);
  $('last-payout').textContent=money(result.payout);
  const delta=$('last-delta');delta.textContent=(result.delta>0?'+':'')+money(result.delta);
  delta.className=result.delta>0?'positive':result.delta<0?'negative':'';
  const matched=result.combo==='COLOR_MATCH';
  const msg=$('spin-announcement');
  msg.textContent=matched?`COLOR MATCH! Kembali ${money(result.payout)} · +${money(result.delta)} bersih`:'Belum match. Putar lagi!';
  msg.className='spin-announcement'+(matched?' win':'');
}
function winEffect(cards){
  const burst=$('win-burst');burst.replaceChildren();
  const rainbow=cards.some(c=>c.color==='wild'||c.face==='WILD');
  const colorMap={red:'#ff193b',blue:'#0872ff',yellow:'#ffdc00',green:'#06d56b'};
  const palette=rainbow?Object.values(colorMap):[colorMap[cards[0].color]||'#fff000','#fff000','#fff',colorMap[cards[0].color]||'#ffe100'];
  for(let i=0;i<46;i++){
    const chip=document.createElement('i');chip.className='win-shard'+(i%6===0?' coin':'');
    const r=i/46*Math.PI*2+Math.random()*.3;
    const dist=40+Math.random()*170;
    chip.style.setProperty('--x',`${48+(Math.random()-.5)*35}%`);
    chip.style.setProperty('--y',`${44+(Math.random()-.5)*35}%`);
    chip.style.setProperty('--dx',`${Math.cos(r)*dist}px`);
    chip.style.setProperty('--dy',`${Math.sin(r)*dist}px`);
    chip.style.setProperty('--particle',palette[i%palette.length]);
    chip.style.setProperty('--rotation',`${Math.floor(Math.random()*360)}deg`);
    chip.style.setProperty('--duration',`${650+Math.floor(Math.random()*450)}ms`);
    chip.style.setProperty('--size',`${5+Math.floor(Math.random()*9)}px`);
    burst.append(chip);
  }
  const stage=$('reel-stage');stage.classList.add('is-win');
  if(!reducedMotion){stage.classList.remove('win-pulse');void stage.offsetWidth;stage.classList.add('win-pulse');}
  setTimeout(()=>{burst.replaceChildren();stage.classList.remove('win-pulse');},1350);
}
async function boot({quiet=false}={}){
  if(!quiet)note('Menghubungkan…');
  try{
    const result=await api('/state');rules=result.rules;syncAccount(result.account);
    const current=result.last?.[0];
    if(current&&!spinning){paintCards(current.cards,current.combo==='COLOR_MATCH');paintSummary(current);}
    else if(!spinning){paintCards(null,false);}
    note('ONLINE · SPIN READY');document.querySelector('.notice-line .dot').classList.add('live');
  }catch(e){note('Koneksi gagal');if(!quiet)toast(e.message);}
}
function stopAuto(showToast=false){auto=false;abortAuto=true;autoRemaining=0;$('auto-btn').setAttribute('aria-pressed','false');$('auto-btn').querySelector('small').textContent='AUTO';renderCost();if(showToast)toast('Auto Spin dihentikan.');}
async function spin(){
  if(spinning||!account)return false;
  const stake=costOptions[stakeIndex];
  if(account.balance<stake){toast('Saldo demo tidak cukup. Klaim hadiah/refill.');stopAuto();return false;}
  audioReady();sound('tap');setBusy(true);startReels();
  $('spin-announcement').textContent='REELS BERPUTAR…';$('spin-announcement').className='spin-announcement';
  let ok=false;
  try{
    const id=crypto.randomUUID?crypto.randomUUID():Date.now()+'_'+Math.random().toString(36).slice(2);
    const started=performance.now();
    sound('start');
    const result=await api('/place','POST',{stake,request_id:id});
    await sleep(Math.max(0,(turbo?320:650)-(performance.now()-started)));
    const matched=result.combo==='COLOR_MATCH';
    await settleReels(result.cards,matched);
    paintSummary(result);
    const before=account.balance;syncAccount(result.account,{animate:true,from:before});
    if(matched){winEffect(result.cards);sound('win');setTimeout(()=>sound('coin'),270);toast(`COLOR MATCH! +${money(result.delta)} koin virtual`);}
    else sound('lose');
    note('ONLINE · SPIN READY');ok=true;
  }catch(e){
    reelAnimations.forEach(a=>a.cancel());reelAnimations=[];
    if(last?.cards)paintCards(last.cards,last.combo==='COLOR_MATCH');else paintCards(null,false);
    $('spin-announcement').textContent='Koneksi bermasalah. Periksa riwayat sebelum PLACE lagi.';
    note('Periksa koneksi');toast(e.message);stopAuto();await boot({quiet:true});
  }finally{setBusy(false);}
  return ok;
}
async function place(){if(spinning||auto)return;await spin();}
async function autoLoop(){
  if(auto){stopAuto(true);return;}
  if(spinning||!account)return;
  audioReady();sound('tap');auto=true;abortAuto=false;autoRemaining=10;
  $('auto-btn').setAttribute('aria-pressed','true');$('auto-btn').querySelector('small').textContent='STOP';renderCost();
  toast('AUTO maksimal 10 putaran. Tap STOP kapan saja.');
  while(autoRemaining>0&&!abortAuto&&!document.hidden){
    const done=await spin();if(!done||abortAuto)break;
    autoRemaining--;
    if(account.balance<costOptions[stakeIndex])break;
    if(autoRemaining>0)await sleep(turbo?270:560);
  }
  if(auto)stopAuto();
}
async function daily(){if(busy||!account?.daily_available)return;busy=true;audioReady();try{const r=await api('/daily','POST',{});syncAccount(r.account,{animate:true,from:account.balance});sound('coin');toast('Hadiah harian +'+money(r.credited)+' koin virtual');}catch(e){toast(e.message);}finally{busy=false;}}
async function freeRefill(){if(busy)return;busy=true;audioReady();try{const r=await api('/refill','POST',{});syncAccount(r.account,{animate:true,from:account.balance});sound('coin');toast('Refill gratis +'+money(r.credited)+' koin virtual');closeModal();}catch(e){toast(e.message);}finally{busy=false;}}
function showModal(title){$('modal-title').textContent=title;$('modal-content').replaceChildren();const modal=$('modal');if(!modal.open)modal.showModal();}
function closeModal(){const modal=$('modal');if(modal.open)modal.close();}
function node(tag,klass,text){const el=document.createElement(tag);if(klass)el.className=klass;if(text!==undefined)el.textContent=text;return el;}
function block(text){const p=node('p','',text);$('modal-content').append(p);return p;}
function panel(){const p=node('div','pane');$('modal-content').append(p);return p;}
function openWallet(){
  showModal('✦ Koin Virtual');const p=panel();p.append(node('strong','',`Saldo: ${money(account?.balance||0)} koin`));
  block('Semua koin hanya untuk game demo. Tidak ada pembelian, nilai uang, transfer, penukaran, penarikan, ataupun hadiah bernilai uang.');
  block('Hadiah harian: +250 koin, satu kali per tanggal WIB. Refill gratis: +1.000 koin, satu kali per tanggal WIB.');
  const actions=node('div','button-stack');$('modal-content').append(actions);
  const d=node('button','',account?.daily_available?'🎁 Klaim harian +250':'✓ Hadiah sudah diklaim');d.disabled=!account?.daily_available;d.onclick=async()=>{await daily();openWallet();};actions.append(d);
  const r=node('button','',account?.refill_available?'✦ Refill +1.000 gratis':'✓ Refill sudah diklaim');r.disabled=!account?.refill_available;r.onclick=freeRefill;actions.append(r);
  block('Saldo disimpan di server staging. Jika cookie browser hilang, akun tamu mungkin tidak dapat dipulihkan.');
}
function openMenu(){
  showModal('Menu UNO LUCK');panel().append(node('strong','',`Pemain ${account?.name||'Player'} · Level ${account?.level||1}`));
  const actions=node('div','button-stack');$('modal-content').append(actions);
  for(const [label,fn] of [['✦ Koin Virtual',openWallet],['▤ Riwayat PLACE',openHistory],['🎯 Aturan & Peluang',openRules],['👤 Profil Pemain',openProfile]]){
    const b=node('button','',label);b.addEventListener('click',fn);actions.append(b);
  }
  block('UNO LUCK Spin v0.4 · Demo tanpa nilai uang.');
}
function openProfile(){
  showModal('Profil Pemain');block('Ganti nama akun tamu di staging.');const input=node('input');
  input.value=account?.name||'Player';input.type='text';input.maxLength=20;input.autocomplete='nickname';$('modal-content').append(input);
  const actions=node('div','button-stack');$('modal-content').append(actions);const save=node('button','','Simpan Nama');actions.append(save);
  save.onclick=async()=>{save.disabled=true;try{const r=await api('/profile','PATCH',{name:input.value});syncAccount(r.account);toast('Nama berhasil disimpan.');closeModal();}catch(e){toast(e.message);save.disabled=false;}};
}
async function openHistory(){
  showModal('Riwayat Spin');block('Menampilkan maksimal 30 spin terbaru. Hasil dan saldo ditentukan server.');
  try{const r=await api('/history');if(!r.items.length){block('Belum ada putaran. Tekan PLACE untuk bermain.');return;}
    for(const result of r.items){const row=node('div','record'),l=node('div'),rhs=node('div');l.append(node('strong','',result.combo==='COLOR_MATCH'?'✦ COLOR MATCH!':'PLACE'));
      l.append(node('small','',new Date(result.created_at*1000).toLocaleString('id-ID',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Jakarta'})));
      rhs.append(node('em',result.delta<0?'loss':'',(result.delta>0?'+':'')+money(result.delta)+' koin'));row.append(l,rhs);$('modal-content').append(row);
    }
  }catch(e){block(e.message);}
}
function openRules(){
  showModal('Aturan Color Match');panel().append(node('strong','','3 WARNA SAMA = 2× BIAYA PLACE'));
  block('Reel menampilkan tiga kartu dengan warna primer merah, biru, kuning, dan hijau. Bila semuanya berwarna sama, saldo mendapat pengembalian 2× biaya PLACE. Jika tidak, pengembalian nol. Angka dan simbol tidak memengaruhi hadiah.');
  block('Peluang Color Match = 1/16 (6,25%) per spin. Warna dipilih independen di server. Hasil tidak dijamin dan ini bukan tabel hadiah resmi UNO.');
  block('Biaya PLACE: 10, 25, 50, 100, atau 250 koin virtual. Turbo hanya mempercepat animasi, Auto maksimal 10 putaran dan dapat dihentikan; peluang tidak berubah.');
  block('Animasi slot dan efek pecah-pecah hanya visual. Hasil selalu dihitung server dan hanya Color Match mendapat burst. Wild tidak termasuk dalam ruleset Color Match v1.');
  panel().append(node('strong','','Game demo saja: koin tidak dapat dibeli, dipindahtangankan, atau diuangkan.'));
}
function listeners(){
  $('place-btn').addEventListener('click',place);
  $('turbo-btn').addEventListener('click',()=>{if(spinning)return;turbo=!turbo;$('turbo-btn').setAttribute('aria-pressed',String(turbo));audioReady();sound('tap');toast(turbo?'Turbo aktif, peluang tidak berubah.':'Turbo nonaktif.');});
  $('auto-btn').addEventListener('click',autoLoop);
  $('stake-minus').addEventListener('click',()=>{if(spinning||auto)return;stakeIndex=Math.max(0,stakeIndex-1);audioReady();sound('tap');renderCost();});
  $('stake-plus').addEventListener('click',()=>{if(spinning||auto)return;stakeIndex=Math.min(costOptions.length-1,stakeIndex+1);audioReady();sound('tap');renderCost();});
  $('wallet-open').addEventListener('click',openWallet);$('menu-open').addEventListener('click',openMenu);$('profile-btn').addEventListener('click',openProfile);
  $('gift-btn').addEventListener('click',daily);$('history-btn').addEventListener('click',openHistory);
  $('music-btn').addEventListener('click',toggleMusic);$('sfx-btn').addEventListener('click',toggleSfx);
  $('modal-close').addEventListener('click',closeModal);$('modal').addEventListener('click',event=>{if(event.target===$('modal'))closeModal();});
  document.addEventListener('pointerdown',()=>audioReady(),{once:true,passive:true});
  document.addEventListener('keydown',()=>audioReady(),{once:true});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){stopMusic();if(auto)stopAuto();}else startMusic();});
  window.addEventListener('pagehide',()=>{stopMusic();if(auto)stopAuto();});
  window.addEventListener('resize',()=>{if(!spinning){layoutReels();if(last?.cards)paintCards(last.cards,last.combo==='COLOR_MATCH');else paintCards(null,false);}});
}
syncAudioControls();listeners();boot();
