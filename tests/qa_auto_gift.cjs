/** First AUTO promo is revealed only after 3 settled cards and user CONTINUE.
 * Isolated CI DB and fake Coin only. No production/staging player mutations.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8083';

(async()=>{
  const browser=await chromium.launch({headless:true});
  const ctx=await browser.newContext({
    viewport:{width:393,height:852},isMobile:true,hasTouch:true,
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Version/18.6 Mobile/15E148 Safari/604.1'
  });
  const page=await ctx.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const audio=await page.request.get(BASE+'/assets/audio/free-spin-gift.wav');
  assert.equal(audio.status(),200);
  assert((await audio.body()).length>90000,'Offline spoken gift is missing/too short');
  const tada=await page.request.get(BASE+'/assets/audio/auto-tadaa.wav');
  assert.equal(tada.status(),200);
  assert((await tada.body()).length>90000,'Full-length Turbo tadaa is missing');
  await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#boot-play').disabled,null,{timeout:30000});
  await page.locator('#boot-play').tap();
  await page.waitForFunction(
    ()=>!document.querySelector('#game-shell').classList.contains('is-booting'),
    null,{timeout:30000}
  );
  await page.locator('#auto-btn').tap();
  await page.locator('.auto-grid button[data-rounds="1"]').tap();
  await page.locator('#auto-start').tap();
  await page.waitForFunction(()=>isAuto&&activeAutoSession!==null,null,{timeout:14000});
  // No promo overlay while the first/second card alone is displayed.
  await page.waitForFunction(()=>currentRound&&currentRound.picked===1,null,{timeout:12000});
  assert.equal(await page.locator('#auto-gift-banner').count(),0,
    'Free Spins may not be shown after first card');
  await page.waitForFunction(()=>currentRound&&currentRound.picked===2,null,{timeout:17000});
  assert.equal(await page.locator('#auto-gift-banner').count(),0,
    'Free Spins may not be shown after second card');
  await page.locator('#auto-gift-banner').waitFor({state:'visible',timeout:35000});
  assert.equal(await page.locator('.auto-gift-card').count(),3);
  const promoTitle=await page.locator('.auto-gift-heading').innerText();
  assert.equal(promoTitle,'10 FREE SPINS!');
  assert((await page.locator('.auto-gift-copy').innerText()).includes(
    'terpisah dari hasil acak'), 'Three jackpot visuals must be disclosed as promotional');
  for(let i=0;i<3;i++)
    assert.equal(await page.locator('#result-'+i+' .card3d.placeholder').count(),0,
      'Gift overlay shown before all three real game cards completed');
  const state=await page.evaluate(async()=>{
    const res=await fetch('/api/auto/state',{cache:'no-store'});
    return (await res.json()).session;
  });
  assert(state.gift_ready&&!state.gift_acknowledged);
  assert.equal(state.completed_rounds,1);
  let btn=page.locator('.auto-gift-continue');
  // Voice plays before CONTINUE. If WebKit rejects delayed autoplay,
  // the player is offered a trusted tap to hear it instead.
  for(let i=0;i<3;i++){
    await page.waitForFunction(()=>!document.querySelector('.auto-gift-continue').disabled,
      null,{timeout:12000});
    const label=await btn.innerText();
    if(label.startsWith('CONTINUE'))break;
    assert(label.includes('PUTAR FREE SPINS'),label);
    await btn.tap();
  }
  assert((await btn.innerText()).startsWith('CONTINUE'));
  await btn.tap();
  await page.locator('#auto-gift-banner').waitFor({state:'detached',timeout:14000});
  const accepted=await page.evaluate(async()=>{
    const res=await fetch('/api/auto/state',{cache:'no-store'});
    return (await res.json()).session;
  });
  assert(accepted===null||accepted.gift_acknowledged);
  if(await page.locator('#auto-btn').getAttribute('aria-pressed')==='true')
    await page.locator('#auto-btn').tap();
  await page.waitForFunction(()=>!isAuto&&!isSpinning,null,{timeout:18000});
  assert.equal(await page.locator('.led-running').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: 3 server cards -> disclosed promo triple -> offline voice -> CONTINUE persisted -> AUTO unlock');
  await ctx.close();await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
