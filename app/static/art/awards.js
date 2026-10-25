/* UNO LUCK awards presentation v1167. Server settlement is authoritative.
 * No wallet writes, payout calculation, RNG calls or Sound Cloud changes. */
(() => {
  'use strict';
  if (window.UNOLuckAwards || typeof paintRound !== 'function') return;
  const $ = id => document.getElementById(id);
  const ns = 'http://www.w3.org/2000/svg';
  const supported = new Set(['COLOR_MATCH','PAIR_SUM','PAIR_PRODUCT','COLOR_PAIR','COLOR_SEQUENCE']);
  const catalog = () => Array.isArray(ruleset?.win_catalog) ? ruleset.win_catalog : [];

  function edge(card) {
    const front = card.querySelector('.card-front') || card;
    const svg = document.createElementNS(ns, 'svg');
    svg.classList.add('award-edge');
    svg.setAttribute('viewBox', '0 0 200 300');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    for (const name of ['award-edge-base', 'award-edge-runner']) {
      const rect = document.createElementNS(ns, 'rect');
      for (const [key,value] of Object.entries({x:7,y:7,width:186,height:286,rx:22,pathLength:100,fill:'none'}))
        rect.setAttribute(key, String(value));
      rect.setAttribute('class', name);
      svg.append(rect);
    }
    const veil = document.createElement('span');
    veil.className = 'award-veil';
    veil.setAttribute('aria-hidden', 'true');
    const sheen = document.createElement('span');
    sheen.className = 'award-sheen';
    veil.append(sheen);
    front.append(veil,svg);
  }

  function decorate(round) {
    const cards = [...document.querySelectorAll('.result-area .result-cell .card3d')];
    for (const card of cards) {
      card.classList.remove('award-winning','award-muted');
      card.querySelectorAll('.award-edge,.award-veil').forEach(node => node.remove());
    }
    const frame = $('result-frame');
    if (frame) delete frame.dataset.award;
    // History includes a separate promo grant. It must not trigger a card win.
    const payout = Number(round?.regular_payout ?? round?.payout ?? 0);
    if (!round?.complete || payout <= 0 || !supported.has(round.combo) || round.cards?.length !== 3) return;
    const values = round.cards;
    let indices = Array.isArray(round.award?.color_indices) ? round.award.color_indices : [];
    if (indices.length < 2) {
      indices = values.flatMap((card,i) => ['red','blue','green','yellow'].includes(card.color) &&
        values.filter(other => other.color === card.color).length >= 2 ? [i] : []);
    }
    if (indices.length < 2) {
      indices = Array.isArray(round.award?.winning_indices) ? round.award.winning_indices :
        values.flatMap((card,i) => values.filter(other => String(other.face) === String(card.face)).length >= 2 ? [i] : []);
    }
    indices = [...new Set(indices)].filter(i => Number.isInteger(i) && i >= 0 && i < 3);
    if (indices.length < 2) return;
    if (frame) frame.dataset.award = round.award?.id || round.combo;
    cards.forEach((card,i) => {
      if (indices.includes(i)) { card.classList.add('award-winning'); edge(card); }
      else card.classList.add('award-muted');
    });
  }

  const previousPaint = paintRound;
  paintRound = function(round, ...options) {
    const result = previousPaint(round, ...options);
    decorate(round);
    return result;
  };

  const previousSay = say;
  say = function(message) {
    let text = String(message || '');
    if (/\bzon[kg]\b|tidak ada kemenangan|payout permainan 0/i.test(text)) text = '';
    previousSay(text);
    $('spin-caption')?.classList.toggle('is-actionable',
      !!text && /koneksi|timeout|gagal|tidak cukup|tidak valid|sinkron|coba lagi|belum terkonfirmasi/i.test(text));
  };

  const previousRules = showRules;
  showRules = function() {
    previousRules();
    const entries = catalog();
    if (!entries.length) return;
    const area = $('modal-content');
    const list = area.querySelector('.rules-paytable');
    if (!list) return;
    const heroTitle = area.querySelector('.hero-copy h3');
    if (heroTitle) heroTitle.textContent = 'Rank & Kemenangan';
    const copy = area.querySelector('.hero-copy p');
    if (copy) copy.textContent = entries.length + ' pola hadiah, dari Twin Color hingga Dragon King.';
    for (const row of list.querySelectorAll('.rules-tier')) row.dataset.award = 'RANK_' + row.dataset.rank;
    let bonus = 0;
    for (const entry of entries.filter(item => item.group === 'bonus')) {
      const row = panelNode('article', 'award-tier');
      row.dataset.award = entry.id;
      row.classList.toggle('is-inactive', !entry.enabled);
      const top = panelNode('div', 'rules-tier-top');
      top.append(panelNode('span','panel-eyebrow','BONUS ' + String(++bonus).padStart(2,'0')),
        panelNode('strong','rules-multiplier',entry.payout_text));
      const hand = panelNode('div','rules-hand');
      hand.setAttribute('aria-label','Ilustrasi kombinasi, bukan hasil putaran');
      for (const card of entry.cards || []) hand.append(htmlCard(card,true));
      const description = panelNode('div','rules-description');
      description.append(panelNode('h3','',entry.title),panelNode('p','',entry.rule));
      if (!entry.enabled) description.append(panelNode('small','award-status','Belum aktif pada konfigurasi ini'));
      row.append(top,hand,description);list.append(row);
    }
    for (const p of [...area.children]) {
      if (p.tagName === 'P' && /^(COLOR PAIR|COLOR SEQUENCE)/.test(p.textContent)) p.remove();
    }
    const note = panelNode('p','panel-fine',
      'Rank 1–5 tetap peringkat utama. Bonus 01–10 adalah jenis kombinasi, bukan urutan nilai hadiah tetap. Nilai bonus angka mengikuti angka kartu dan batasnya. Satu hadiah permainan per ronde; bonus promosi dicatat terpisah. Koin virtual tidak dapat dibeli atau dicairkan.');
    area.append(note);
  };

  const previousMenu = showMenu;
  showMenu = function() {
    previousMenu();
    const grid = $('modal-content').querySelector('.menu-grid');
    if (grid) menuTile(grid,'Rank Info',catalog().length + ' pola kemenangan','cards',showRules);
  };
  // orbit.js registered the original function object before this module ran.
  // Rebind both entry points, not just the global, without duplicating handlers.
  for (const id of ['profile-btn','modal-back']) {
    const button = $(id);
    if (!button) continue;
    button.removeEventListener('click',previousMenu);
    button.addEventListener('click',showMenu);
  }

  function updateLabel() {
    const node = $('combination-label');
    const entries = catalog();
    if (!node || !entries.length) return;
    const text = entries.length + ' pola hadiah';
    if (node.textContent !== text) node.textContent = text;
  }
  const label = $('combination-label');
  if (label) new MutationObserver(updateLabel).observe(label,{childList:true,characterData:true,subtree:true});
  updateLabel();
  if (typeof last !== 'undefined' && last) decorate(last);
  if (/zon[kg]|tidak ada kemenangan/i.test($('spin-caption')?.textContent || '')) say('');
  document.addEventListener('visibilitychange',() => {
    document.documentElement.classList.toggle('award-paused',document.hidden);
  });
  window.UNOLuckAwards = {catalog, decorate};
})();
