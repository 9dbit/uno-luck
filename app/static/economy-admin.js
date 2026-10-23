'use strict';
(()=>{
const $=id=>document.getElementById(id),fmt=n=>new Intl.NumberFormat('id-ID',{maximumFractionDigits:4}).format(n),rp=n=>'Rp'+fmt(n*40)+' virtual';
const names={NO_MATCH:'ZONK / NO MATCH',COLOR_PAIR:'Color Pair · 2 kartu sewarna',COLOR_SEQUENCE:'Color Sequence · warna & angka berurutan',PAIR_SUM:'Angka kembar · jumlah',PAIR_PRODUCT:'Angka kembar · perkalian',RANK_5:'Lucky Color Win',RANK_4:'Golden Match',RANK_3:'Phoenix Color Blast',RANK_2:'Imperial Fortune',RANK_1:'Dragon King Jackpot'};
let key='',revision=0,timer,sequence=0,validDraft=null;
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
async function api(path,body){const r=await fetch('/api/admin/economy'+path,{method:body?'POST':'GET',cache:'no-store',headers:{'X-UNO-Sound-Admin':key,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:Array.isArray(d.detail)?d.detail.map(e=>e.msg).join('\n'):'Gagal memuat konfigurasi');return d;}
async function loadPromoPolicy(){
  const display=$('promo-policy-status');
  try{
    const d=await api('/promo-policy');
    $('promo-policy-enabled').checked=Boolean(d.enabled);
    $('promo-policy-budget').value=d.daily_budget_coin;
    $('promo-policy-account-limit').value=d.max_sessions_per_account_day;
    display.textContent=`Hari WIB ${d.budget_day_wib}: ${fmt(d.sessions_today)} sesi · ${fmt(d.booked_coin)} Coin dialokasikan · ${fmt(d.remaining_coin)} Coin tersisa. ${d.enabled?'Gift AUTO aktif':'Gift AUTO belum diaktifkan'}. ${d.note}`;
    display.classList.remove('error');
  }catch(e){display.textContent='Gagal mengambil status Gift: '+e.message;display.classList.add('error');}
}
async function savePromoPolicy(){
  const display=$('promo-policy-status'),button=$('promo-policy-save');
  button.disabled=true;display.textContent='Menyimpan batas promosi server…';
  try{
    const budget=Number($('promo-policy-budget').value),
      limit=Number($('promo-policy-account-limit').value);
    if(!Number.isSafeInteger(budget)||budget<0||!Number.isSafeInteger(limit)||limit<1)
      throw Error('Budget dan batas sesi harus bilangan bulat.');
    const d=await api('/promo-policy',{
      enabled:$('promo-policy-enabled').checked,daily_budget_coin:budget,
      max_sessions_per_account_day:limit});
    display.textContent=`Policy tersimpan. ${d.enabled?'Gift AUTO aktif':'Gift AUTO nonaktif'} · ${fmt(d.remaining_coin)} Coin tersedia pada ${d.budget_day_wib}. Sesi yang sudah diterima tetap berlaku.`;
    display.classList.remove('error');
  }catch(e){display.textContent=e.message;display.classList.add('error');}
  finally{button.disabled=false;}
}
function field(parent,id,label,value){const l=document.createElement('label');l.textContent=label;const input=document.createElement('input');input.type='number';input.min='0';input.step='0.0001';input.id=id;input.value=value;l.append(input);$(parent).append(l);}
function read(){const stakes=$('stakes').value.split(',').map(x=>Number(x.trim())/40);if(stakes.some(x=>!Number.isInteger(x)))throw Error('Tahapan BET harus kelipatan Rp40 virtual.');return {stake_options:stakes,percentages:Object.fromEntries(Object.keys(names).map(k=>[k,$('p-'+k).value])),sum_cap:Number($('sum-cap').value),product_cap:Number($('product-cap').value),color_pair_multiplier:Number($('color-pair-multiplier').value),color_sequence_multiplier:Number($('color-sequence-multiplier').value),multipliers:[1,2,3,4,5].map(r=>Number($('m-'+r).value))};}
async function load(){clearTimeout(timer);sequence++;validDraft=null;$('publish').disabled=true;const d=await api('');revision=d.revision;const c=d.draft;$('probabilities').replaceChildren();$('multipliers').replaceChildren();for(const [k,n] of Object.entries(names))field('probabilities','p-'+k,n+' (%)',c.percentages[k]??0);for(let r=1;r<=5;r++){field('multipliers','m-'+r,names['RANK_'+r]+' (×)',c.multipliers[r-1]);$('m-'+r).step='1';}$('stakes').value=c.stake_options.map(n=>n*40).join(', ');$('sum-cap').value=c.sum_cap;$('product-cap').value=c.product_cap;$('color-pair-multiplier').value=c.color_pair_multiplier??2;$('color-sequence-multiplier').value=c.color_sequence_multiplier??4;$('editor').hidden=false;$('access').hidden=true;status(d.active?`Konfigurasi aktif revisi ${revision}. Engine ${d.engine_model}; perubahan berikut adalah draft sampai diterapkan.`:`Aturan lama masih aktif (RTP teoretis ${fmt(d.legacy_rtp_percent)}%). Draft fixed-RNG baru belum diterapkan.`);schedule();void loadPerformance();void loadPromoPolicy();}
function schedule(){const token=++sequence;clearTimeout(timer);validDraft=null;$('publish').disabled=true;$('results').textContent='Menghitung draft terbaru…';$('chart').hidden=true;timer=setTimeout(()=>update(token),350);}
async function update(token){try{const config=read();const total=Object.values(config.percentages).reduce((a,b)=>a+Number(b),0);$('total').textContent='Total peluang: '+fmt(total)+'%';const previous=Number($('sim-stake').value);$('sim-stake').replaceChildren(...config.stake_options.filter(Number.isInteger).map(n=>{const o=document.createElement('option');o.value=n;o.textContent=rp(n);return o;}));if(config.stake_options.includes(previous))$('sim-stake').value=previous;const balance=Number($('sim-balance').value)/40;if(!Number.isInteger(balance))throw Error('Saldo simulasi harus kelipatan Rp40 virtual.');const result=await api('/simulate',{config,stake:Number($('sim-stake').value),balance,rounds:Number($('sim-rounds').value),seed:Number($('sim-seed').value),turnover_rp:Number($('turnover').value),costs_rp:Number($('costs').value),auto_sessions:Number($('promo-sessions').value),auto_paid_rounds:Number($('promo-paid-rounds').value)});if(token!==sequence)return;validDraft=config;$('publish').disabled=false;render(result);}catch(e){if(token!==sequence)return;$('results').textContent=e.message;$('chart').hidden=true;$('distribution').replaceChildren();}}
function render(d){renderPool(d);const results=$('results');results.replaceChildren();for(const [label,value] of [['RTP teoretis',fmt(d.rtp_percent)+'%'],['Margin operator (sebelum biaya)',fmt(100-d.rtp_percent)+'%'],['Total BET proyeksi','Rp'+fmt(d.projection?.turnover_rp??Number($('turnover').value))+' virtual'],['Payout proyeksi','Rp'+fmt(d.projection?.expected_payout_rp??0)+' virtual'],['Hasil bruto operator','Rp'+fmt(d.projection?.gross_result_rp??0)+' virtual'],['Hasil neto periode setelah semua bonus','Rp'+fmt(d.projection?.net_result_rp??0)+' virtual'],['Peluang payout > 0',fmt(d.payout_probability_percent)+'%'],['Rata-rata ronde / payout positif',fmt(d.average_rounds_per_positive_payout??0)],['Peluang untung bersih',fmt(d.profit_probability_percent)+'%'],['Rata-rata payout / ronde',rp(d.expected_gross)],['Ekspektasi bersih / ronde',rp(d.expected_net)],['Sesi terhenti karena saldo',fmt(d.stopped_percent)+'%'],['Saldo akhir median',rp(d.median_balance)],['Saldo akhir P10 – P90',rp(d.p10_balance)+' – '+rp(d.p90_balance)],['Ronde rata-rata dimainkan',fmt(d.average_rounds)]]){const cell=document.createElement('article');cell.textContent=label;const v=document.createElement('strong');v.textContent=value;cell.append(v);results.append(cell);}const note=document.createElement('p');note.textContent=d.warning+(d.inflation_warning?' RTP di atas 100%: saldo cenderung bertambah sebelum pembatasan.':'');note.className=d.inflation_warning?'warning':'';results.append(note);const table=document.createElement('table');const head=document.createElement('tr');for(const name of ['Payout × BET','Peluang per ronde']){const th=document.createElement('th');th.textContent=name;head.append(th);}table.append(head);for(const row of d.distribution){const tr=document.createElement('tr');for(const v of [row.multiplier+'×',fmt(row.percent)+'%']){const td=document.createElement('td');td.textContent=v;tr.append(td);}table.append(tr);}$('distribution').replaceChildren(table);const canvas=$('chart');canvas.hidden=false;const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);const max=Math.max(1,...d.trace);ctx.strokeStyle='#ffd574';ctx.lineWidth=3;ctx.beginPath();d.trace.forEach((n,i)=>{const x=20+i/Math.max(1,d.trace.length-1)*(w-40),y=h-25-n/max*(h-50);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();$('chart-caption').textContent=`Contoh satu sesi: ${d.trace.length-1} ronde, saldo ${rp(d.trace[0])} → ${rp(d.trace.at(-1))}. Ringkasan di atas memakai ${d.sessions} sesi.`;}
function renderPool(d){
  const p=d.projection||{},out=$('period-pool-summary');
  out.replaceChildren();out.className='performance-grid';
  const items=[
    ['BET periode (virtual)',p.turnover_rp],
    ['Payout permainan dasar (virtual)',p.expected_payout_rp],
    ['Bonus AUTO total · terendah',p.auto_bonus_min_rp],
    ['Bonus AUTO total · rata-rata',p.auto_bonus_expected_rp],
    ['Bonus AUTO total · tertinggi',p.auto_bonus_max_rp],
    ['Perkiraan payout 10 free spins',p.free_spin_expected_payout_rp],
    ['Total biaya promosi · rata-rata',p.promotional_cost_expected_rp],
    ['Proyeksi hasil pool periode',p.period_expected_surplus_rp],
    ['Stres uji hadiah maksimum',p.period_worst_case_surplus_rp],
    ['Estimasi BET minimum untuk impas',p.break_even_turnover_rp]
  ];
  for(const [name,value] of items){
    const num=Number(value),label=value==null?'Tidak tercapai':'Rp'+fmt(num)+' virtual';
    const kind=name==='Proyeksi hasil pool periode'||name==='Stres uji hadiah maksimum'?
      (num>=0?'positive':'negative'):'';
    out.append(performanceCard(name,label,kind));
  }
  out.append(
    performanceCard('Batas sesi AUTO · margin ekspektasi',fmt(p.max_auto_sessions_expected??0)+' sesi'),
    performanceCard('Batas sesi AUTO · hadiah maksimum',fmt(p.max_auto_sessions_high_gift??0)+' sesi'),
    performanceCard('Kapasitas sesi tambahan',fmt(p.available_extra_auto_sessions_expected??0)+' sesi'),
    performanceCard('Status simulasi periode',
      p.planned_auto_exceeds_paid_turnover?'Jumlah AUTO melebihi total BET periode':
      p.feasible_expected_pool?'SURPLUS DIPROYEKSIKAN':'DEFISIT DIPROYEKSIKAN',
      p.feasible_expected_pool?'positive':'negative')
  );
  const note=document.createElement('p');note.className='wide';
  note.textContent='Batas sesi adalah rekomendasi berdasarkan RTP dan turnover yang diinput, BUKAN pembatas runtime atau jaminan untung. Sesuaikan jumlah promosi/turnover; tidak ada perubahan RNG menurut pemain, saldo, atau target pool.';
  out.append(note);
}
function performanceCard(label,value,kind=''){const cell=document.createElement('article');if(kind)cell.classList.add(kind);cell.append(panelText('span',label),panelText('strong',value));return cell;}
function panelText(tag,text){const node=document.createElement(tag);node.textContent=text;return node;}
async function loadPerformance(){const out=$('performance-results');out.textContent='Memuat data aktual…';try{const d=await api('/performance?days='+$('performance-days').value);const actual=d.actual_rtp_percent===null?'Belum ada ronde':fmt(d.actual_rtp_percent)+'%';out.replaceChildren(performanceCard('Pemain unik',fmt(d.players)),performanceCard('Ronde selesai',fmt(d.rounds)),performanceCard('RTP aktual',actual),performanceCard('Total BET',fmt(d.turnover_coin)+' Coin · Rp'+fmt(d.turnover_rp)+' virtual'),performanceCard('Total payout',fmt(d.payout_coin)+' Coin · Rp'+fmt(d.payout_rp)+' virtual'),performanceCard('Hasil bruto',`${d.gross_coin>=0?'+':''}${fmt(d.gross_coin)} Coin · Rp${fmt(d.gross_rp)} virtual`,d.gross_coin>=0?'positive':'negative'),performanceCard('Pembanding teoretis',fmt(d.theoretical_rtp_percent)+'% · revisi '+d.active_revision,'wide'));out.append(
    performanceCard('Free Spins selesai',fmt(d.free_rounds??0)),
    performanceCard('Payout free spins','Rp'+fmt(d.free_spin_payout_rp??0)+' virtual'),
    performanceCard('Bonus PROMO dikreditkan','Rp'+fmt(d.promotional_payout_rp??0)+' virtual'),
    performanceCard('Sisa bonus PROMO terjadwal','Rp'+fmt(d.pending_bonus_liability_rp??0)+' virtual'),
    performanceCard('Pool setelah bonus terjadwal','Rp'+fmt(d.result_after_reserved_rp??d.gross_rp??0)+' virtual',
      (d.result_after_reserved_coin??d.gross_coin??0)>=0?'positive':'negative'),
    performanceCard('RTP permainan & PROMO',actual)
  );
  $('performance-note').textContent=d.note;}catch(e){out.textContent=e.message;}}
$('unlock').onclick=async()=>{key=$('admin-key').value;$('admin-key').value='';try{await load();}catch(e){status(e.message,true);}};
$('reload').onclick=async()=>{try{await load();}catch(e){status(e.message,true);}};
function syncTarget(fromAmount=false){
 const turnover=Number($('turnover').value);
 if(fromAmount){if(turnover>0)$('target-margin').value=(Number($('target-profit').value)/turnover*100).toFixed(4);}
 else $('target-profit').value=(turnover*Number($('target-margin').value)/100).toFixed(2);
}
$('editor').addEventListener('input',e=>{if(['turnover','costs','target-margin','target-profit'].includes(e.target.id))syncTarget(e.target.id==='target-profit');$('target-status').textContent='Draft berubah. Simulasi menunjukkan margin aktual; target baru diterapkan ke draft setelah tombol Sesuaikan ditekan.';schedule();});
$('fit-target').onclick=async()=>{
 clearTimeout(timer);const token=++sequence;validDraft=null;$('publish').disabled=true;$('fit-target').disabled=true;
 try{const d=await api('/target',{config:read(),margin_percent:$('target-margin').value,
    turnover_rp:Number($('turnover').value),costs_rp:Number($('costs').value),
    auto_sessions:Number($('promo-sessions').value),auto_paid_rounds:Number($('promo-paid-rounds').value),
    stake:Number($('sim-stake').value)});if(token!==sequence)return;
 for(const [k,v] of Object.entries(d.config.percentages))$('p-'+k).value=v;
 $('target-status').textContent=`Target periode ${fmt(d.requested_margin_percent)}% → proyeksi margin periode ${fmt(d.actual_period_margin_percent??d.actual_margin_percent)}% (RTP dasar margin ${fmt(d.actual_margin_percent)}%). Selisih ${fmt(d.rounding_difference_percent)} poin. ${d.note}`;schedule();
 }catch(e){if(token===sequence){$('target-status').textContent=e.message;$('results').textContent='Penyesuaian gagal. Perbaiki input atau ubah target untuk menghitung ulang.';}}
 finally{$('fit-target').disabled=false;}
};$('sim-stake').addEventListener('change',schedule);$('performance-days').addEventListener('change',loadPerformance);$('refresh-performance').addEventListener('click',loadPerformance);
$('suggest-color-probabilities').onclick=()=>{
  const pair=$('p-COLOR_PAIR'),sequence=$('p-COLOR_SEQUENCE');
  const delta=(1-Number(pair.value))+(.25-Number(sequence.value));
  const noMatch=$('p-NO_MATCH');
  if(Number(noMatch.value)<delta){status('Sisa peluang ZONK terlalu kecil untuk contoh bonus warna.',true);return;}
  noMatch.value=(Number(noMatch.value)-delta).toFixed(4);
  pair.value='1.0000';sequence.value='.2500';
  status('Draft contoh diisi, belum aktif. Tinjau RTP, simulasi, lalu terbitkan secara eksplisit.');
  schedule();
};
$('pool-period').onchange=()=>{
  $('performance-days').value=$('pool-period').value;
  void loadPerformance();
};
$('promo-paid-rounds').onchange=schedule;
$('balance-probabilities').onclick=()=>{const other=Object.keys(names).filter(k=>k!=='NO_MATCH').reduce((sum,k)=>sum+Number($('p-'+k).value),0);$('p-NO_MATCH').value=(100-other).toFixed(4);schedule();};
$('promo-policy-save').addEventListener('click',savePromoPolicy);
$('publish').onclick=async()=>{if(!validDraft)return;const token=sequence,config=validDraft;$('publish').disabled=true;try{const d=await api('/publish',{config,expected_revision:revision});revision=d.revision;status(`Revisi ${revision} diterapkan untuk ronde baru · RTP ${fmt(d.rtp_percent)}%. Saldo dan ronde berjalan tetap utuh.`);if(token===sequence)validDraft=null;void loadPerformance();}catch(e){status(e.message,true);if(token===sequence)$('publish').disabled=false;}};
})();
