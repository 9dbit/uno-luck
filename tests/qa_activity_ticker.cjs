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
  assert((await page.locator('.activity-head').innerText()).includes('PAYOUT DEMO'));
  assert((await page.locator('#activity-feed').innerText()).includes('maxw**'));
  const label=await page.locator('#activity-total').getAttribute('title');
  assert(label.includes('SIMULASI'));
  const read=async()=>Number((await page.locator('#activity-total').innerText()).replace(/\./g,''));
  const start=await read();
  assert(start>=889980250);
  await page.waitForTimeout(1300);
  const later=await read();
  assert(later>start,{start,later});
  const layout=await page.evaluate(()=>{
    const e=document.getElementById('activity-board'),h=document.querySelector('.title-area');
    const a=e.getBoundingClientRect(),b=h.getBoundingClientRect();
    return {inside:a.top>=b.top-2&&a.bottom<=b.bottom+2,
      width:a.width,screen:window.innerWidth};
  });
  assert(layout.inside,layout);
  assert(layout.width<=layout.screen,layout);
  console.log('PASS: transparent QA payout demo, censored aliases, monotonic illustrative counter, mobile bounds');
  await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
