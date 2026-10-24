/** Regression for iPhone screenshot 6/0/6 BLUE, PAYOUT 0, NET -25.
 * UI uses only a fixture; no player balance, RNG, sound or DB writes.
 */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8080';

(async()=>{
 for (const engine of ['chromium','webkit']) {
  const browser=await ({chromium,webkit}[engine]).launch();
  const context=await browser.newContext({viewport:{width:393,height:852},
    isMobile:true,hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Version/18.6 Mobile/15E148 Safari/604.1'});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
  // account is assigned before loadState awaits AUTO state; wait for its final
  // paint to finish so a late network response cannot overwrite this fixture.
  await page.waitForFunction(()=>typeof paintRound==='function'&&account!==null &&
    typeof stateLoading==='boolean'&&!stateLoading &&
    typeof window.UNOLuckMotion?.numbers==='function');
  await page.evaluate(()=>{
   // DOM-only assertion fixture: the regular PLAY WITH SOUND splash keeps
   // gameplay visibility:hidden. Expose it without touching player APIs.
   const shell=document.getElementById('game-shell');
   shell.classList.remove('is-booting');
   shell.removeAttribute('aria-hidden');
   document.getElementById('boot-overlay').hidden=true;
   window.__blueRound={stake:25,charged_stake:25,picked:3,complete:true,
     combo:'COLOR_MATCH',payout:625,promo_coin:0,delta:600,
     cards:[6,0,6].map(n=>({color:'blue',face:String(n)})),
     tier:{rank:5,title:'LUCKY COLOR WIN',multiplier:25}};
   paintRound(window.__blueRound);
  });
  assert.equal(await page.locator('#last-stake').innerText(),'25');
  assert.equal(await page.locator('#last-payout').innerText(),'625');
  assert.equal(await page.locator('#last-delta').innerText(),'+600');
  assert.deepEqual(await page.locator('.result-cell .card3d').evaluateAll(nodes=>
   nodes.map(n=>[n.dataset.color,n.dataset.face])),
   [['blue','6'],['blue','0'],['blue','6']]);
  await page.evaluate(()=>paintRound(null));
  assert.equal(await page.locator('#last-payout').innerText(),'—');
  assert.equal(await page.locator('#last-delta').innerText(),'—');
  assert.equal(await page.locator('#spin-step').innerText(),'1 / 3');
  assert.equal(await page.locator('.result-cell .card3d.placeholder').count(),3);
  assert.deepEqual(errors,[]);
  console.log(engine+': PASS Rank5 625 + NET600 and next SPIN1 pending reset');
  await context.close();await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
