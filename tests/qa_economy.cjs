/* Admin UI against real isolated CI API; optional read-only RDC fixtures. */
const {chromium,webkit}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const URL=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
const engine=process.env.UNO_QA_ENGINE||'chromium';
const OUT=process.env.UNO_QA_OUT||'artifacts/uno-economy';fs.mkdirSync(OUT,{recursive:true});
(async()=>{
 const browser=await ({chromium,webkit}[engine]).launch(engine==='chromium'&&process.env.UNO_QA_CHROME?{channel:'chrome'}:{});
 const context=await browser.newContext({viewport:{width:393,height:852},hasTouch:true});
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 let fixture;
 if(process.env.UNO_QA_ECONOMY_FIXTURE){
  fixture=JSON.parse(fs.readFileSync(process.env.UNO_QA_ECONOMY_FIXTURE));
  for(const [url,body] of Object.entries(fixture.sources))await page.route('**'+url+'*',r=>r.fulfill({body,contentType:url.endsWith('.html')?'text/html':url.includes('.css')?'text/css':'text/javascript'}));
  await page.route(/\/api\/admin\/economy(?:\/.*)?$/,async r=>{
   const req=r.request(),data=req.postDataJSON();
   if(!req.headers()['x-uno-sound-admin'])return r.fulfill({status:403,json:{detail:'Unauthorized'}});
   if(req.url().endsWith('/simulate')){
    const c=data.config,total=Object.values(c.percentages).reduce((a,b)=>a+Number(b),0);
    if(Math.abs(total-100)>.000001||c.multipliers[4]<=Math.max(c.sum_cap,c.product_cap))return r.fulfill({status:422,json:{detail:'Total atau urutan payout tidak valid'}});
    return r.fulfill({json:Number(c.percentages.PAIR_SUM)===6?fixture.changed:fixture.simulation});
   }
   if(req.url().endsWith('/publish'))return r.fulfill({json:{revision:++fixture.revision,new_rounds_only:true}});
   return r.fulfill({json:{revision:fixture.revision,active:null,draft:fixture.config,legacy_rtp_percent:195.36}});
  });
 }
 await page.goto(URL+'/assets/economy-admin.html');
 assert(await page.locator('#editor').isHidden());
 await page.locator('#admin-key').fill(process.env.UNO_SOUND_ADMIN_TOKEN||'qa-fixture-only-key');
 await page.locator('#unlock').click();
 await page.locator('#publish').waitFor();await page.waitForFunction(()=>!document.querySelector('#publish').disabled);
 const initial=await page.locator('#results').innerText();assert(initial.includes('79,025')||initial.includes('79,03'),initial);
 await page.locator('#p-PAIR_SUM').fill('6');
 await page.waitForTimeout(600);assert(await page.locator('#publish').isDisabled());
 await page.locator('#balance-probabilities').click();
 await page.waitForFunction(()=>!document.querySelector('#publish').disabled);
 assert.notEqual(await page.locator('#results').innerText(),initial);
 await page.locator('#m-5').fill('20');await page.waitForTimeout(600);assert(await page.locator('#publish').isDisabled());
 await page.locator('#m-5').fill('25');await page.waitForFunction(()=>!document.querySelector('#publish').disabled);
 for(const [width,height] of [[320,568],[393,852],[852,393],[1440,1000]]){
  await page.setViewportSize({width,height});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(OUT,`${engine}-economy-${width}x${height}.png`),fullPage:true});
 }
 await page.locator('#publish').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('diterapkan'));
 assert(await page.locator('#publish').isDisabled());
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({engine,result:'PASS',fixtures:!!fixture,checks:['auth gate','automatic simulation','invalid total','payout ordering','responsive four sizes','publish revision']}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
