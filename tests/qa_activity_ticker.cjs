/** The demo running text must never masquerade as actual player wins. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8083';

(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:393,height:852},
    isMobile:true,hasTouch:true});
  const res=await page.request.get(BASE+'/api/activity/public');
  assert.equal(res.status(),200);
  const source=await res.json();
  assert.equal(source.mode,'simulation');
  assert.equal(source.demo_start_coin,889980250);
  await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.UNOLuckActivity?.mode==='simulation',null,{timeout:15000});
  // The visual game is intentionally hidden behind PLAY WITH SOUND.
  // Read-only ticker geometry QA may reveal it without bypassing game APIs.
  await page.evaluate(()=>{
    document.querySelector('#game-shell').classList.remove('is-booting');
    document.querySelector('#game-shell').removeAttribute('aria-hidden');
    document.querySelector('#boot-overlay').hidden=true;
  });
  assert.equal(await page.locator('#activity-mode').innerText(),'SIMULASI QA');
  assert.equal(await page.locator('.activity-head').innerText(),'✦ PAYOUT');
  assert(!(await page.locator('#activity-board').innerText()).includes('COIN VIRTUAL'));
  assert(!(await page.locator('#activity-board').innerText()).includes('PAYOUT SIMULASI'));
  assert((await page.locator('#activity-feed').innerText()).includes('sutris**'));
  assert((await page.locator('#activity-total').innerText()).startsWith('Rp'));
  assert((await page.locator('#activity-feed').innerText()).includes('Rp88.000'));
  assert((await page.locator('#activity-feed').innerText()).includes('maxw**'));
  const rail=await page.evaluate(()=>{
    const feed=document.querySelector('#activity-feed');
    const cycles=feed.querySelectorAll('.activity-cycle');
    const clip=document.querySelector('.activity-viewport');
    const style=getComputedStyle(document.querySelector('#activity-board'));
    return {copies:cycles.length,
      width:cycles[0]?.getBoundingClientRect().width||0,
      clipWidth:clip.getBoundingClientRect().width,
      background:style.backgroundColor,
      border:parseFloat(style.borderTopWidth),
      shadow:style.boxShadow,
      animation:getComputedStyle(feed).animationName};
  });
  assert.equal(rail.copies,2);
  assert(rail.width>=rail.clipWidth,['marquee begins blank',rail]);
  assert.equal(rail.background,'rgba(0, 0, 0, 0)');
  assert.equal(rail.border,0);
  assert.equal(rail.shadow,'none');
  assert(rail.animation.includes('unoPayoutSeamless'),rail);
  const label=await page.locator('#activity-total').getAttribute('title');
  assert(label.includes('SIMULASI'));
  const read=async()=>Number((await page.locator('#activity-total').innerText()).replace(/[^0-9]/g,''));
  const start=await read();
  assert(start>=889980250);
  // GitHub runners can throttle browser timers while the heavy WebKit suite
  // runs in parallel. Verify eventual monotonic progress, not an exact 1.3s tick.
  await page.waitForFunction(initial=>{
    const current=Number((document.querySelector('#activity-total')?.textContent||'')
      .replace(/[^0-9]/g,''));
    return Number.isFinite(current)&&current>initial;
  },start,{timeout:6500});
  const later=await read();
  assert(later>start,{start,later});
  const layout=await page.evaluate(()=>{
    const box=selector=>document.querySelector(selector).getBoundingClientRect();
    const a=box('#activity-board'),h=box('.title-area'),
      cards=box('.result-area'),bar=box('.result-bar'),total=box('#total-bet-row'),
      wheel=box('.wheel-area'),
      shell=box('.game-shell');
    const style=getComputedStyle(document.querySelector('#total-bet-row'));
    return {
      totalBelowBet:total.top>=bar.bottom-3,
      totalAboveWheel:total.bottom<=wheel.top+3,
      transparentTotal:style.backgroundColor==='rgba(0, 0, 0, 0)' &&
        style.backgroundImage==='none' &&
        parseFloat(style.borderTopWidth)===0 &&
        style.boxShadow==='none',
      betweenTotalAndWheel:a.top>=total.bottom-3&&a.bottom<=wheel.top+3,
      afterBet:a.top>=bar.bottom+3,
      awayFromTitle:a.top>=h.bottom+3,
      awayFromCards:a.top>=cards.bottom+3,
      inViewport:a.bottom<=shell.bottom+2,
      font:parseFloat(getComputedStyle(document.querySelector('.activity-feed')).fontSize),
      width:a.width,screen:window.innerWidth
    };
  });
  assert(layout.totalBelowBet&&layout.totalAboveWheel&&layout.transparentTotal,
    ['unboxed TOTAL BET placement/background',layout]);
  assert(layout.betweenTotalAndWheel&&layout.afterBet&&layout.awayFromTitle&&
    layout.awayFromCards&&layout.inViewport,layout);
  assert(layout.font>=12,layout);
  assert(layout.width<=layout.screen,layout);
  console.log('PASS: transparent TOTAL BET/PAYOUT, continuous nonblank marquee above wheel, mobile bounds');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
