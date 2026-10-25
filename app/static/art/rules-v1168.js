/* DEV-02 v1.1.68: one informative guide for Game Rules and Rank Info.
 * All amounts below are labeled examples, never game settlement or wallet writes. */
(() => {
  'use strict';
  if (window.UNOLuckRulesGuide || typeof showRules !== 'function') return;
  const $ = id => document.getElementById(id);
  const node = (tag, cls, text) => panelNode(tag, cls, text);
  const num = value => new Intl.NumberFormat('id-ID').format(value);
  const names = {red:'Merah',blue:'Biru',green:'Hijau',yellow:'Kuning',wild:'Tanpa warna'};
  const titles = {RANK_1:'Dragon King Jackpot',RANK_2:'Imperial Fortune',
    RANK_3:'Phoenix Color Blast',RANK_4:'Golden Match',RANK_5:'Lucky Color Win'};
  const descriptions = {
    RANK_1:'Tiga kartu Wild +4. Warna tidak diperlukan.',
    RANK_2:'Tiga kartu WILD biasa. Campuran WILD dan +4 tidak memenuhi pola ini.',
    RANK_3:'SKIP, REVERSE, dan +2 dengan satu warna yang sama. Urutan kartu bebas.',
    RANK_4:'Tiga angka berurutan dengan satu warna yang sama. Urutan tampil bebas.',
    RANK_5:'Tiga kartu sewarna, setelah pemeriksaan bonus angka dan rank khusus.',
    COLOR_SEQUENCE:'Dua angka berurutan pada kartu berdampingan dengan warna sama. Kartu ketiga berbeda warna.',
    COLOR_PAIR:'Minimal dua kartu berwarna sama, termasuk posisi kiri dan kanan. Tidak menumpuk hadiah lain.'
  };
  function description(item) {
    if (descriptions[item.id]) return descriptions[item.id];
    const triple=item.id.endsWith('_TRIPLE'), draw=item.id.includes('_DRAW_');
    return (triple?'Tiga':'Dua')+' face '+(draw?'+2':'angka')+' sama; '+
      (item.guide_formula==='product'?'ketiga kartu sewarna. Kalikan ketiga nilainya.':
        'warna tidak semuanya sama. Jumlahkan ketiga nilainya.');
  }
  function detail(parent, title, copy) {
    const box=node('details','rg-detail'), head=node('summary','',title);
    box.append(head,node('p','',copy));parent.append(box);return box;
  }
  function button(parent, text, callback) {
    const b=modalButton(parent,text,callback);b.className='rg-button';return b;
  }
  function drawHand(item) {
    const hand=node('div','rg-hand'+(item.group==='rank'?' rules-hand':''));
    hand.setAttribute('role','img');
    hand.setAttribute('aria-label','Contoh: '+item.cards.map(c=>names[c.color]+' '+c.face).join(', '));
    for (const card of item.cards) {
      const image=htmlCard(card,true);image.setAttribute('aria-hidden','true');hand.append(image);
    }
    return hand;
  }
  function exampleLine(item, stake) {
    const payout=Number(item.guide_example)*stake;
    const net=payout-stake;
    return 'BET '+num(stake)+'  \u2192  WIN '+num(payout)+'  \u00b7  NET '+(net>=0?'+':'')+num(net)+' Coin';
  }
  showRules = function() {
    const area=playerPanel('Game Rules');$('modal').dataset.view='rules-guide';
    const rules=ruleset || {};
    const entries=(rules.win_catalog || []).slice().sort((a,b)=>(a.guide_order||99)-(b.guide_order||99));
    if (!entries.length) {
      area.append(node('p','rg-notice','Aturan belum tersedia. Periksa koneksi lalu buka kembali menu ini.'));
      return;
    }
    const options=(rules.stake_options || [25]).filter(x=>Number.isInteger(x)&&x>0);
    let stake=options.includes(STAKES[stakeIndex])?STAKES[stakeIndex]:options[0];
    let filter='all';
    const hero=node('header','rg-hero');
    hero.append(node('span','rg-kicker','DRAGON SPIN / RULES v'+rules.rules_version),
      node('h3','','Kenali kartu. Pahami hadiahnya.'),
      node('p','',entries.length+' pola hadiah dalam satu panduan. Setiap ronde memiliki satu hadiah permainan dasar.'));
    const stats=node('div','rg-stats');
    for (const [value,label] of [[entries.length,'pola'],[3,'kartu / ronde'],[Math.max(...entries.map(e=>e.guide_max))+'\u00d7','batas tertinggi']]) {
      const part=node('div','');part.append(node('strong','',String(value)),node('span','',label));stats.append(part);
    }
    hero.append(stats);area.append(hero);
    const navigation=node('div','rg-nav');navigation.setAttribute('role','tablist');navigation.setAttribute('aria-label','Bagian panduan');
    const panels={},tabs=[];
    function activate(key, focus=false) {
      for (const tab of tabs) {
        const selected=tab.dataset.tab===key;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
        panels[tab.dataset.tab].hidden=!selected;
        if(selected&&focus)tab.focus();
      }
      area.scrollTop=0;
    }
    for (const [key,label] of [['catalog','Rank & Bonus'],['play','Cara Main'],['terms','Ketentuan']]) {
      const tab=button(navigation,label,()=>activate(key));tab.id='rg-tab-'+key;tab.dataset.tab=key;
      tab.setAttribute('role','tab');tab.setAttribute('aria-controls','rg-panel-'+key);
      const panel=node('section','rg-panel');panel.id='rg-panel-'+key;
      panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);panel.tabIndex=0;
      panels[key]=panel;tabs.push(tab);
      tab.addEventListener('keydown',event=>{
        let index=tabs.indexOf(tab);
        if(event.key==='ArrowRight')index=(index+1)%tabs.length;
        else if(event.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;
        else if(event.key==='Home')index=0;
        else if(event.key==='End')index=tabs.length-1;
        else return;
        event.preventDefault();activate(tabs[index].dataset.tab,true);
      });
    }
    area.append(navigation,...Object.values(panels));
    const catalog=panels.catalog;
    const note=node('p','rg-order-note','Urutan 01\u2013'+String(entries.length).padStart(2,'0')+
      ' berdasarkan batas hadiah tertinggi, bukan peluang menang. Bonus variabel dapat membayar lebih kecil. Nomor rank utama tidak berubah.');
    catalog.append(note);
    const controls=node('div','rg-controls'),filters=node('div','rg-filters');
    filters.setAttribute('role','group');filters.setAttribute('aria-label','Filter kombinasi');
    const list=node('div','rg-list rules-paytable');
    const count=node('p','rg-count');count.setAttribute('role','status');
    const rows=[];
    function applyFilter() {
      for (const child of filters.children)child.setAttribute('aria-pressed',String(child.dataset.filter===filter));
      let visible=0;
      for (const row of rows) {row.hidden=filter!=='all'&&row.dataset.group!==filter;if(!row.hidden)visible++;}
      count.textContent=visible+' dari '+entries.length+' pola ditampilkan';
    }
    for (const [key,label] of [['all','Semua'],['rank','Rank utama'],['bonus','Bonus']]) {
      const b=button(filters,label,()=>{filter=key;applyFilter();});b.dataset.filter=key;
    }
    const label=node('label','rg-stake-label','Contoh BET');label.htmlFor='rg-example-stake';
    const select=node('select','rg-select');select.id='rg-example-stake';
    for(const value of options){const option=node('option','',num(value)+' Coin');option.value=String(value);select.append(option);}
    select.value=String(stake);
    label.append(select);controls.append(filters,label);catalog.append(controls,
      node('p','rg-simulation','SIMULASI PERHITUNGAN SAJA. Tidak mengubah BET atau saldo Anda.'),count,list);
    for(const item of entries){
      const row=node('article','rg-entry '+(item.group==='rank'?'rules-tier':'award-tier'));
      row.dataset.award=item.id;row.dataset.order=String(item.guide_order);row.dataset.group=item.group;
      if(item.group==='rank')row.dataset.rank=item.rank;
      row.dataset.active=String(item.sampling_active);
      const heading=node('div','rg-entry-heading');
      const index=node('span','rg-index',String(item.guide_order).padStart(2,'0'));index.setAttribute('aria-label','Urutan '+item.guide_order);
      const text=node('div','rg-title');
      text.append(node('span','rg-family',item.group==='rank'?'RANK '+item.rank:
        item.guide_formula==='product'?'BONUS PERKALIAN':item.guide_formula==='sum'?'BONUS PENJUMLAHAN':'BONUS WARNA'),
        node('h4','',titles[item.id]||item.title));
      const amount=node('strong','rg-multiplier'+(item.group==='rank'?' rules-multiplier':''),
        (item.guide_variable?'Maks. ':'')+num(item.guide_max)+'\u00d7 BET');
      heading.append(index,text,amount);row.append(heading);
      const content=node('div','rg-entry-body'),visual=node('div','rg-visual');
      visual.append(drawHand(item),node('small','rg-illustration','ILUSTRASI KOMBINASI'));
      const info=node('div','rg-info');info.append(node('p','rg-rule',description(item)));
      const status=node('span','rg-state',item.sampling_active?'Aktif pada konfigurasi ini':'Belum aktif sebagai hasil tersendiri');
      info.append(status);
      if(!item.sampling_active)info.append(node('p','rg-inactive-note',
        'Pola didukung aturan, tetapi kategori ini belum diikutkan dalam undian konfigurasi saat ini. Contoh di bawah bukan janji hasil.'));
      const example=node('p','rg-example',exampleLine(item,stake));example.dataset.example=item.id;info.append(example);
      let equation;
      if(item.guide_formula==='fixed')equation=num(item.guide_example)+'\u00d7 BET. Ini hadiah bruto, bukan keuntungan bersih.';
      else{
        const operation=item.guide_formula==='product'?' \u00d7 ':' + ';
        equation=item.cards.map(c=>String(c.face)==='+2'?'2':c.face).join(operation)+' = '+num(item.guide_raw)+
          '. Batas '+num(item.guide_cap)+'\u00d7 BET; contoh memakai '+num(item.guide_example)+'\u00d7 BET.'+(item.id.includes('_DRAW_')?' +2 bernilai 2.':'');
      }
      detail(info,'Cara hitung',equation);
      content.append(visual,info);row.append(content);list.append(row);rows.push(row);
    }
    select.addEventListener('change',()=>{
      stake=Number(select.value);
      for(const item of entries)list.querySelector('[data-example="'+item.id+'"]').textContent=exampleLine(item,stake);
    });
    applyFilter();
    const play=panels.play;
    play.append(node('h3','rg-section-title','Satu BET, tiga kali SPIN'));
    const steps=node('ol','rg-steps');
    for(const [title,copy] of [['Pilih BET','Tentukan BET sebelum ronde baru. Biaya dipotong satu kali, saat SPIN pertama.'],
      ['Buka tiga kartu','SPIN pertama membuka kiri, kedua tengah, ketiga kanan. Tunggu ketiganya selesai.'],
      ['Lihat WIN dan NET','Server menyelesaikan kombinasi dan mengkreditkan hadiah sekali. Contoh di Rules tidak menjalankan SPIN.']]){
      const step=node('li','');step.append(node('strong','',title),node('p','',copy));steps.append(step);
    }
    play.append(steps);
    const metrics=node('dl','rg-metrics');
    for(const [key,value] of [['BET','Biaya ronde. Free Spin menggunakan nominal BET, tanpa debit biaya ronde.'],
      ['WIN','Hadiah bruto dari kombinasi kartu. Bukan saldo akhir.'],
      ['NET','Hadiah permainan + grant promo terpisah - biaya yang benar-benar didebit. Tanpa promo: WIN - BET.']]){
      metrics.append(node('dt','',key),node('dd','',value));
    }
    play.append(metrics);
    detail(play,'Bagaimana kombinasi yang tumpang tindih dihitung?',
      'Server memeriksa bonus angka / Draw Two terlebih dahulu, kemudian rank utama, Color Sequence yang aktif, lalu Twin Color. Satu hadiah dasar saja, tidak dijumlahkan. Urutan pemeriksaan bukan memilih multiplier terbesar. Perkalian nol pada tiga kartu sewarna beralih ke Lucky Color.').open=true;
    detail(play,'Apa arti pasangan warna?',
      'Dua kartu merah, biru, hijau, atau kuning yang sama warna dapat membentuk Twin Color. Posisi kiri-kanan juga dihitung. Color Sequence memerlukan posisi berdampingan dan angka berurutan. WILD dan +4 tidak mempunyai warna.');
    detail(play,'Apakah 2 sama dengan +2?',
      'Tidak untuk face pasangan. Dua +2 membentuk pasangan Draw Two dan masing-masing bernilai 2 saat dihitung. Satu angka 2 bersama satu +2 bukan pasangan face identik. Semua kartu dalam bonus angka harus berupa angka atau +2.');
    detail(play,'Bagaimana jika tidak ada kombinasi?',
      'NO MATCH memiliki WIN permainan 0. Biaya BET tetap berlaku. Grant promosi, bila ada, dicatat terpisah dan tidak mengubah kartu kalah menjadi kartu pemenang.');
    const terms=panels.terms;
    terms.append(node('h3','rg-section-title','AUTO, hadiah & ketentuan'));
    detail(terms,'AUTO dan 10 Free Spins',
      'AUTO berisi maksimal 10 ronde berbayar. Jika promosi tersedia dan sesi diterima server, terdapat 10 ronde gratis tambahan dan 5 grant promosi terpisah. Setiap grant memilih 30, 50, atau 100 persen dari nominal BET batch berbayar. Promosi mengikuti ketersediaan anggaran serta batas sesi, bukan selalu tersedia.').open=true;
    detail(terms,'CONTINUE, TURBO dan mengganti BET',
      'Tiga kartu asli diselesaikan sebelum layar JACKPOT GIFT promosi. Tekan CONTINUE untuk melanjutkan; refresh mempertahankan sesi yang sudah diterima. TURBO hanya mempercepat animasi, bukan mengubah peluang. Pilihan BET saat ronde atau AUTO berlangsung berlaku setelah komitmen tersebut selesai.');
    detail(terms,'Hasil acak dan urutan rank',
      'Hasil ditentukan server secara independen. Rank atau urutan katalog bukan probabilitas dan bukan jadwal kemenangan. Pengurutan berdasarkan batas hadiah tidak berarti setiap bonus membayar maksimum. Konfigurasi baru tidak mengubah kontrak ronde yang sudah dibayar.');
    detail(terms,'Koin virtual dan batas saldo',
      'Coin tidak dapat dibeli, dicairkan, atau ditukar uang maupun hadiah nyata. Tampilan Rp hanyalah ekuivalen virtual. Batas saldo '+num(rules.coin_cap||1000000)+' Coin dapat membatasi kredit aktual. Gambar dan contoh hitung tidak mengubah saldo. Ini bukan aturan UNO resmi.');
    detail(terms,'Cahaya emas dan ticker PAYOUT',
      'Gold edge dan gloss menandai kartu pada kemenangan permainan positif yang sudah dikonfirmasi, bukan grant promo saja. Feed berlabel SIMULASI QA berisi contoh, bukan bukti pemain atau transaksi nyata.');
    area.append(node('p','rg-footer','UNO LUCK \u00b7 DEV-02 v1.1.68 \u00b7 Koin virtual / tanpa nilai uang'));
    activate('catalog');
  };
  window.UNOLuckRulesGuide={version:'1.1.68',open:()=>showRules()};
})();
