/* UNO LUCK approved-art motion controller v0.7.
   This module draws visual feedback only. Server auth/RNG/payout remain in orbit.js. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const format = (n) => new Intl.NumberFormat('id-ID', {maximumFractionDigits: 0}).format(Math.round(n));
  const running = new WeakMap();
  const valueState = new WeakMap();
  let dragonReset = null;
  let uiReset = null;

  function renderNumber(id, next, {sign = false, animate = false, color = true} = {}) {
    const el = $(id);
    if (!el) return;
    const last = valueState.get(el);
    const previous = typeof last === 'number' ? last : 0;
    const oldAnim = running.get(el);
    if (oldAnim) cancelAnimationFrame(oldAnim);
    running.delete(el);
    el.classList.remove('positive', 'negative');
    if (next === null || next === undefined || !Number.isFinite(Number(next))) {
      el.textContent = '—';
      valueState.delete(el);
      el.removeAttribute('data-number');
      return;
    }
    const target = Math.round(Number(next));
    const positive = sign && target > 0;
    const negative = sign && target < 0;
    if (color) el.classList.toggle('positive', positive);
    if (color) el.classList.toggle('negative', negative);
    el.dataset.number = String(target);
    const paint = (n) => { el.textContent = `${sign && n > 0 ? '+' : ''}${format(n)}`; };
    valueState.set(el, target);
    if (reduced || !animate || target === previous) {
      paint(target);
      return;
    }
    const start = performance.now();
    const duration = sign ? 750 : 460;
    const easeOut = (p) => 1 - Math.pow(1 - p, 3);
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const current = Math.round(previous + (target - previous) * easeOut(progress));
      paint(current);
      if (progress < 1 && !document.hidden) running.set(el, requestAnimationFrame(tick));
      else { paint(target); running.delete(el); }
    };
    running.set(el, requestAnimationFrame(tick));
    el.classList.remove('number-pop');
    void el.offsetWidth;
    el.classList.add('number-pop');
  }

  function numbers({stake, payout = null, delta = null, animate = false} = {}) {
    renderNumber('last-stake', stake, {animate});
    renderNumber('last-payout', payout, {animate});
    renderNumber('last-delta', delta, {sign: true, animate});
  }

  function balance(next, animate = false) {
    renderNumber('wallet-balance', next, {animate});
  }

  function press(node) {
    if (!node || node.disabled) return;
    node.classList.remove('fx-press');
    // Toggle deliberately; WAAPI would stack transforms with the disabled pulsing keyframes.
    void node.offsetWidth;
    node.classList.add('fx-press');
    setTimeout(() => node.classList.remove('fx-press'), 260);
  }

  function beginSpin() {
    document.querySelector('.wheel-area')?.classList.add('fx-spinning');
    press($('spin-btn'));
  }

  function endSpin() {
    document.querySelector('.wheel-area')?.classList.remove('fx-spinning');
  }

  function pick(cardIndex) {
    const cell = $('result-' + cardIndex);
    if (!cell || reduced) return;
    cell.classList.remove('fx-metal-flash');
    void cell.offsetWidth;
    cell.classList.add('fx-metal-flash');
    setTimeout(() => cell.classList.remove('fx-metal-flash'), 700);
  }

  function result(data) {
    const wheel = document.querySelector('.wheel-area');
    const title = document.querySelector('.title-area');
    const bar = document.querySelector('.result-bar');
    if (!wheel || !title || !bar || !data?.complete) return;
    const confirmed = data.combo === 'COLOR_MATCH';
    // No separate jackpot outcome exists in v0.6. Only an explicit future server
    // result with a jackpot flag may trigger the dramatic jackpot choreography.
    const jackpot = data.combo === 'JACKPOT' || data.jackpot === true;
    clearTimeout(dragonReset);
    clearTimeout(uiReset);
    wheel.classList.remove('fx-color-match', 'fx-jackpot', 'fx-no-match');
    title.classList.remove('fx-color-match', 'fx-jackpot', 'fx-no-match');
    bar.classList.remove('fx-color-match', 'fx-jackpot', 'fx-no-match');
    void wheel.offsetWidth;
    const cls = jackpot ? 'fx-jackpot' : confirmed ? 'fx-color-match' : 'fx-no-match';
    for (const item of [wheel, title, bar]) item.classList.add(cls);
    const duration = jackpot ? 2200 : confirmed ? 1450 : 500;
    dragonReset = setTimeout(() => wheel.classList.remove(cls), duration + 300);
    uiReset = setTimeout(() => { title.classList.remove(cls); bar.classList.remove(cls); }, duration + 300);
  }

  function cancelVisibleAnimations() {
    document.querySelector('.wheel-area')?.classList.remove('fx-spinning');
    for (const id of ['last-stake','last-payout','last-delta','wallet-balance']) {
      const el = $(id);
      const anim = el && running.get(el);
      if (anim) cancelAnimationFrame(anim);
      if (el && valueState.has(el)) {
        const n = valueState.get(el);
        el.textContent = `${id === 'last-delta' && n > 0 ? '+' : ''}${format(n)}`;
      }
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelVisibleAnimations();
  });
  window.UNOLuckMotion = {numbers, balance, press, beginSpin, endSpin, pick, result};
})();