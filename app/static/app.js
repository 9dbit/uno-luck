'use strict';
const $ = s => document.querySelector(s);
const COLORS = {red:'#de3026',yellow:'#ffc61a',green:'#0dac58',blue:'#007cd9',wild:'#151515'};
const LABELS = {red:'MERAH',yellow:'KUNING',green:'HIJAU',blue:'BIRU'};
const savedName = localStorage.getItem('ul_nickname') || '';
let socket = null, activeSession = null, snapshot = null, playerId = null, roomCode = null;
let reconnectTimer = null, wasManuallyClosed = false, hasWelcomed = false, reconnectAttempts = 0;
let pendingChallengeKey = '', lastLogLine = '', muted = localStorage.getItem('ul_sound') === 'off';
let toastTimer = null, audioContext = null;
$('#player-name').value = savedName;
$('#sound-toggle').textContent = muted ? '♩' : '♪';
try { const queryRoom = new URLSearchParams(location.search).get('room'); if (queryRoom) { $('#room-input').value = queryRoom.toUpperCase().slice(0,6); $('#join-row').classList.remove('hidden'); } } catch(e) {}

function screen(name) {
  ['lobby','waiting','game'].forEach(n=>$('#'+n+'-screen').classList.toggle('hidden',name!==n));
}
function status(text, mode='') {
  const el=$('#status-pill'); el.className='status-pill '+mode; el.lastChild.textContent=' '+text;
}
function toast(message) {
  $('#toast').textContent=message;
  $('#toast').classList.add('show');
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),3200);
}
function textElement(tag,cls,text) { const e=document.createElement(tag); if(cls)e.className=cls; e.textContent=String(text); return e; }
function playSound(kind='tap') {
  if (muted) return;
  try {
    const AC=window.AudioContext||window.webkitAudioContext;
    if(!AC) return;
    audioContext ||= new AC();
    if(audioContext.state==='suspended') audioContext.resume();
    const now=audioContext.currentTime;
    const freqs=kind==='win'?[523,659,784,1047]:kind==='card'?[370,554]:kind==='uno'?[587,784,1175]:[450];
    freqs.forEach((freq,i)=>{
      const osc=audioContext.createOscillator(),gain=audioContext.createGain();
      osc.type='sine'; osc.frequency.setValueAtTime(freq,now+i*.09);
      gain.gain.setValueAtTime(.00001,now+i*.09);gain.gain.exponentialRampToValueAtTime(.085,now+i*.09+.018);gain.gain.exponentialRampToValueAtTime(.00001,now+i*.09+.15);
      osc.connect(gain);gain.connect(audioContext.destination);osc.start(now+i*.09);osc.stop(now+i*.09+.16);
    });
  }catch(e){}
}
function openModal(title,desc,buttons,{mandatory=false}={}) {
  const dlg=$('#modal');const box=$('#modal-content'),actions=$('#modal-actions');
  box.replaceChildren();actions.replaceChildren();
  box.append(textElement('h2','',title));
  if(desc)box.append(textElement('p','',desc));
  buttons.forEach(({label,fn,cls='secondary'})=>{
    let btn=textElement('button',cls,label); btn.type='button';btn.addEventListener('click',()=>{dlg.close();fn&&fn();});actions.append(btn);
  });
  dlg.dataset.mandatory=mandatory?'true':'false';
  if(dlg.open)dlg.close();
  dlg.showModal();
}
$('#modal').addEventListener('cancel',e=>{if($('#modal').dataset.mandatory==='true')e.preventDefault();});
function closeModal(){if($('#modal').open)$('#modal').close();}
function showHelp(){
  openModal('Cara Main UNO LUCK',
    'Classic: cocokan warna, angka, atau simbol. Skip melewati satu pemain; Reverse membalik arah; +2 membuat berikutnya ambil 2 dan lewat giliran. Wild memilih warna. +4 bisa ditantang bila pemberi kartu masih memiliki warna yang aktif. Tidak ada stacking dalam mode ini. Ketika tersisa 2 kartu, tekan UNO! sebelum memainkan kartu menjadi satu. Jika lupa, lawan dapat memberi penalti +2. Pemenang ronde mendapat poin dari kartu tersisa milik lawan (angka sesuai nilai; aksi 20; Wild 50). Ini adalah prototipe sosial, tanpa deposit, taruhan, dan withdrawal.',
    [{label:'Mengerti',cls:'cta'}]);
}
$('#help-button').onclick=showHelp;
$('#sound-toggle').onclick=()=>{muted=!muted;localStorage.setItem('ul_sound',muted?'off':'on');$('#sound-toggle').textContent=muted?'♩':'♪';playSound();};

function beginConnect(kind, extras={}) {
  clearTimeout(reconnectTimer);
  wasManuallyClosed=false;
  if(kind!=='resume') reconnectAttempts=0;
  const old=socket;
  if(old){ socket=null; try{old.close();}catch(e){} }
  const nickname=(extras.name||$('#player-name').value).trim();
  if(kind!=='resume'){
    if(!nickname||nickname.length>20){toast('Isi nama pemain (maksimal 20 karakter)');return;}
    localStorage.setItem('ul_nickname',nickname);
  }
  status('Menghubungkan…');
  const protocol=location.protocol==='https:'?'wss:':'ws:';
  const sock=new WebSocket(protocol+'//'+location.host+'/ws');
  socket=sock;hasWelcomed=false;
  let initialError=false;
  sock.onopen=()=>{
    const intro={type:kind};
    if(kind==='resume'){intro.room=extras.room;intro.token=extras.token;}
    else if(kind==='join'){intro.room=extras.room;intro.name=nickname;}
    else intro.name=nickname;
    sock.send(JSON.stringify(intro));
  };
  sock.onmessage=evt=>{
    if(socket!==sock)return;
    let msg;try{msg=JSON.parse(evt.data);}catch(e){return;}
    if(msg.type==='welcome'){
      hasWelcomed=true;reconnectAttempts=0;roomCode=msg.room;playerId=msg.player_id;
      activeSession={room:msg.room,token:msg.token,playerId:msg.player_id,name:msg.name};
      localStorage.setItem('ul_session_v02',JSON.stringify(activeSession));
      history.replaceState(null,'','/?room='+encodeURIComponent(roomCode));
      status('Terhubung','online');playSound('win');
      return;
    }
    if(msg.type==='state'){
      snapshot=msg;render();
      if(msg.game?.logs?.length){const newest=msg.game.logs.at(-1);if(newest!==lastLogLine){if(lastLogLine)playSound(newest.includes('wins')?'win':'card');lastLogLine=newest;}}
      return;
    }
    if(msg.type==='error'){
      toast(msg.message||'Action failed');
      if(!hasWelcomed){initialError=true;localStorage.removeItem('ul_session_v02');screen('lobby');status('Ready');}
      return;
    }
  };
  sock.onerror=()=>{if(socket===sock)status('Koneksi bermasalah','offline');};
  sock.onclose=()=>{
    if(socket!==sock)return;
    socket=null;
    status('Terputus','offline');
    if(!wasManuallyClosed && activeSession && !initialError && (hasWelcomed || kind==='resume')){
      reconnectAttempts+=1;
      const wait=Math.min(15000, 1200*Math.pow(2,Math.min(reconnectAttempts-1,4)));
      toast('Koneksi terputus. Mencoba tersambung ulang…');
      reconnectTimer=setTimeout(()=>beginConnect('resume',activeSession),wait);
    }
    else if(!hasWelcomed && !initialError)toast('Tidak dapat terhubung. Pastikan server berjalan.');
  };
}
function leaveRoom(){
  wasManuallyClosed=true;clearTimeout(reconnectTimer);
  if(socket){const old=socket;socket=null;old.close();}
  localStorage.removeItem('ul_session_v02');
  activeSession=null;snapshot=null;playerId=null;roomCode=null;pendingChallengeKey='';lastLogLine='';
  closeModal();status('Ready');screen('lobby');history.replaceState(null,'','/');
}
function action(name,other={}){
  if(!socket || socket.readyState!==1){toast('Menunggu koneksi server');return;}
  socket.send(JSON.stringify({type:'action',action:name,...other}));playSound(name==='uno'?'uno':'tap');
}
$('#create-room').onclick=()=>beginConnect('create');
$('#join-room').onclick=()=>$('#join-row').classList.toggle('hidden');
$('#confirm-join').onclick=()=>beginConnect('join',{room:$('#room-input').value.toUpperCase().trim()});
$('#room-input').addEventListener('keydown',e=>{if(e.key==='Enter')$('#confirm-join').click();});
$('#start-match').onclick=()=>action('start');
$('#copy-link').onclick=async()=>{
  const invite=location.origin+'/?room='+encodeURIComponent(roomCode||'');
  try{await navigator.clipboard.writeText(invite);toast('Link undangan disalin');}
  catch(e){openModal('Link Undangan',invite,[{label:'Tutup',cls:'cta'}]);}
};
$('#leave-waiting').onclick=leaveRoom;
$('#leave-game').onclick=()=>openModal('Keluar dari room?','Progres room tetap ada untuk sementara di server. Kamu bisa bergabung kembali selama room belum kedaluwarsa.',[{label:'Batal'},{label:'Keluar',cls:'cta',fn:leaveRoom}]);
$('#game-logs').onclick=()=>{
  const g=snapshot?.game;if(!g)return;
  const dlg=$('#modal'),area=$('#modal-content'),actions=$('#modal-actions');area.replaceChildren();actions.replaceChildren();
  area.append(textElement('h2','','Riwayat Ronde'));
  const list=textElement('ol','log-list',''); g.logs.slice().reverse().forEach(l=>list.append(textElement('li','',l)));area.append(list);
  let close=textElement('button','cta','Tutup');close.onclick=()=>dlg.close();actions.append(close);dlg.dataset.mandatory='false';if(dlg.open)dlg.close();dlg.showModal();
};
$('#new-round').onclick=()=>action('next_round');
$('#call-uno').onclick=()=>action('uno');
$('#draw-action').onclick=()=>action('draw');
$('#keep-action').onclick=()=>action('keep');
$('#catch-action').onclick=()=>action('catch');
$('#deck-button').onclick=()=>action('draw');

function render(){
  if(!snapshot)return;
  $('#room-display').textContent=snapshot.room;
  $('#game-room-code').textContent=snapshot.room;
  if(!snapshot.game_running){renderWaiting();screen('waiting');}
  else{screen('game');renderGame(snapshot.game);}
}
function renderWaiting(){
  const list=$('#waiting-members');list.replaceChildren();
  snapshot.members.forEach((p,i)=>{
    const row=textElement('div','waiting-member','');
    row.append(textElement('strong','',`${i+1}. ${p.name}${p.id===snapshot.host?' 👑':''}`));
    row.append(textElement('small','',p.online?'● Online':'○ Reconnecting'));
    list.append(row);
  });
  const host=playerId===snapshot.host;
  $('#start-match').classList.toggle('hidden',!host);
  $('#waiting-note').textContent=host?'Kursi yang kosong otomatis diisi bot saat kamu menekan Mulai.':'Menunggu host memulai permainan…';
}
function cardSymbol(kind){
  if(kind==='skip')return '⊘';if(kind==='reverse')return '⇄';return kind;
}
function makeCard(card,{active=false,onClick=null}={}){
  const btn=document.createElement('button');btn.type='button';
  btn.className='card '+(card.color==='wild'?'wild ':'')+(active?'legal':'inactive');
  btn.style.setProperty('--cardcolor',COLORS[card.color]||COLORS.wild);
  btn.setAttribute('aria-label',(card.color==='wild'?'Wild':(LABELS[card.color]||card.color))+' '+card.kind);
  const face=textElement('div','face','');
  const upper=textElement('span','corner',cardSymbol(card.kind));
  const lower=textElement('span','corner bottom',cardSymbol(card.kind));
  if(card.color==='wild'){
    face.append(textElement('div','wild-mark',''));
    face.append(textElement('span','number',card.kind==='+4'?'+4':'WILD'));
  }else face.append(textElement('span','number',cardSymbol(card.kind)));
  face.append(upper,lower);btn.append(face);
  btn.disabled=!active;
  if(active && onClick)btn.addEventListener('click',onClick);
  return btn;
}
function openColor(card){
  const dlg=$('#modal'),box=$('#modal-content'),actions=$('#modal-actions');
  box.replaceChildren();actions.replaceChildren();
  box.append(textElement('h2','','Pilih warna berikutnya'));
  box.append(textElement('p','','Wild mengubah warna aktif meja.'));
  const grid=textElement('div','color-grid','');
  for(const [col,label] of Object.entries(LABELS)){
    const btn=textElement('button','',label);btn.style.background=COLORS[col];btn.onclick=()=>{dlg.close();action('play',{card_id:card.id,color:col});};grid.append(btn);
  }
  box.append(grid);let cancel=textElement('button','secondary','Batal');cancel.onclick=()=>dlg.close();actions.append(cancel);
  dlg.dataset.mandatory='false';if(dlg.open)dlg.close();dlg.showModal();
}
function renderGame(g){
  const me=g.players.find(p=>p.id===playerId);
  if(!me)return;
  const turnIsMine=g.turn===playerId;
  const myTurn=turnIsMine && (g.phase==='turn'||g.phase==='after_draw');
  const challengeMine=turnIsMine && g.phase==='challenge';
  const chosenColor=g.active_color;
  $('#my-name').textContent=me.name;
  $('#my-stats').textContent=`Skor ${me.score} / 500`;
  $('#count-badge').textContent=g.hand.length+' KARTU';
  $('#direction-badge').textContent=g.direction===1?'↻':'↺';
  $('#turn-banner').textContent=g.phase==='round_over'?'RONDE SELESAI':myTurn?'GILIRANMU!':challengeMine?'TANTANGAN +4':`GILIRAN ${g.players.find(p=>p.id===g.turn)?.name||'...'}`;
  const opponents=$('#opponents');opponents.replaceChildren();
  g.players.filter(p=>p.id!==playerId).forEach((p,i)=>{
    const div=textElement('div','seat'+(g.turn===p.id?' active':''),'');
    const avatar=textElement('div','avatar',(p.name?.[0]||'?').toUpperCase());
    const details=textElement('div','seat-text','');details.append(textElement('strong','',p.name));details.append(textElement('small','',`${p.count} cards • ${p.score} pts`));div.append(avatar,details);
    if(p.uno_warning)div.append(textElement('span','uno-flag','UNO?'));
    opponents.append(div);
  });
  const discard=$('#discard-card');discard.replaceChildren();discard.append(makeCard(g.top));
  $('#color-dot').style.background=COLORS[chosenColor];$('#active-color').textContent=LABELS[chosenColor];
  const legal=new Set(g.legal_ids||[]);
  const hand=$('#hand-row');hand.replaceChildren();
  g.hand.forEach(card=>{
    const enabled=myTurn&&legal.has(card.id);
    const node=makeCard(card,{active:enabled,onClick:()=>card.color==='wild'?openColor(card):action('play',{card_id:card.id})});
    if(g.drawn_id===card.id)node.style.outline='3px solid #84fc9b';
    hand.append(node);
  });
  $('#call-uno').disabled=!(myTurn && g.hand.length===2) && g.uno_candidate!==playerId;
  $('#call-uno').classList.toggle('armed',g.uno_armed);
  $('#call-uno').textContent=g.uno_armed?'UNO ✓':'UNO!';
  $('#draw-action').disabled=!(myTurn&&g.phase==='turn');
  $('#deck-button').disabled=!(myTurn&&g.phase==='turn');
  $('#keep-action').classList.toggle('hidden',!(myTurn&&g.phase==='after_draw'));
  const canCatch=g.uno_candidate!==null && g.uno_candidate!==playerId && g.phase!=='round_over';
  $('#catch-action').classList.toggle('hidden',!canCatch);
  $('#hint-text').textContent=g.phase==='round_over'?'':challengeMine?'Putuskan apakah +4 sah.':myTurn?(g.phase==='after_draw'?'Mainkan hanya kartu yang baru diambil, atau Simpan Kartu.':(g.hand.length===2?'Tekan UNO! sebelum mengeluarkan satu kartu.':'Tap kartu yang menyala, atau ambil kartu.')):'Lihat kartu dan tunggu giliran berikutnya.';
  $('#round-event').textContent=g.logs.at(-1)||'';
  const res=$('#result-banner');res.classList.toggle('hidden',g.phase!=='round_over');
  if(g.phase==='round_over'){
    const winner=g.players.find(p=>p.id===g.winner);
    $('#result-title').textContent=g.winner===playerId?'KAMU MENANG! 🏆':`${winner?.name||'Pemain'} MENANG!`;
    $('#result-copy').textContent=`Bonus skor ronde: ${g.award}. Total ${winner?.score||0} poin menuju target 500.`;
    $('#new-round').classList.toggle('hidden',snapshot.host!==playerId);
  }
  if(challengeMine && g.challenge){
    const key=g.challenge.offender+':'+g.challenge.target;
    if(key!==pendingChallengeKey){
      pendingChallengeKey=key;
      const offender=g.players.find(p=>p.id===g.challenge.offender);
      openModal('Wild +4: Terima atau Tantang?',`${offender?.name||'Pemain'} mengeluarkan +4. Jika warna sebelumnya masih ada di tangannya, tantangan berhasil dan dia mengambil 4 kartu. Jika tidak, kamu mengambil 6 kartu dan giliranmu dilewati.`,[
        {label:'Terima +4',cls:'secondary',fn:()=>action('accept')},
        {label:'Tantang!',cls:'cta',fn:()=>action('challenge')}
      ],{mandatory:true});
    }
  }else if(g.phase!=='challenge'){
    if(pendingChallengeKey){pendingChallengeKey='';closeModal();}
  }
}

// Auto-resume the last guest session on refresh. Credentials never appear in invite links.
try{
  const s=JSON.parse(localStorage.getItem('ul_session_v02')||'null');
  if(s?.room && s?.token){
    const linkRoom=new URLSearchParams(location.search).get('room');
    if(!linkRoom || linkRoom.toUpperCase()===s.room.toUpperCase()){
      activeSession=s;beginConnect('resume',s);
    }else{screen('lobby');status('Ready');}
  }
}catch(e){localStorage.removeItem('ul_session_v02');}
