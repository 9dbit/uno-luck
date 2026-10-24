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
  await page.waitForFunction(()=>window.UNOLuckActivity?.mode==='simulation',{timeout:15000});
  assert.equal(await page.locator('#activity-mode').innerText(),'SIMULASI QA');
  assert.equal(await page.locator('.activity-head').innerText(),'✦ PAYOUT');
  assert(!(await page.locator('#activity-board').innerText()).includes('COIN VIRTUAL'));
  assert(!(await page.locator('#activity-board').innerText()).includes('PAYOUT SIMULASI'));
  assert((await page.locator('#activity-feed').innerText()).includes('sutris**'));
  assert((await page.locator('#activity-total').innerText()).startsWith('Rp'));
  assert((await page.locator('#activity-feed').innerText()).includes('Rp88.000'));
  assert((await page.locator('#activity-feed').innerText()).includes('maxw**'));
  const label=await page.locator('#activity-total').getAttribute('title');
  assert(label.includes('SIMULASI'));
  const read=async()=>Number((await page.locator('#activity-total').innerText()).replace(/[^0-9]/g,''));
  const start=await read();
  assert(start>=889980250);
  await page.waitForTimeout(1300);
  const later=await read();
  assert(later>start,{start,later});
  const layout=await page.evaluate(()=>{
    const box=selector=>document.querySelector(selector).getBoundingClientRect();
    const a=box('#activity-board'),h=box('.title-area'),
      cards=box('.result-area'),bar=box('.result-bar'),wheel=box('.wheel-area'),
      shell=box('.game-shell');
    return {
      afterWheel:a.top>=wheel.bottom-3,
      afterBet:a.top>=bar.bottom+3,
      awayFromTitle:a.top>=h.bottom+3,
      awayFromCards:a.top>=cards.bottom+3,
      inViewport:a.bottom<=shell.bottom+2,
      font:parseFloat(getComputedStyle(document.querySelector('.activity-feed')).fontSize),
      width:a.width,screen:window.innerWidth
    };
  });
  assert(layout.afterWheel&&layout.afterBet&&layout.awayFromTitle&&
    layout.awayFromCards&&layout.inViewport,layout);
  assert(layout.font>=12,layout);
  assert(layout.width<=layout.screen,layout);
  console.log('PASS: transparent QA payout demo, censored aliases, monotonic illustrative counter, mobile bounds');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
