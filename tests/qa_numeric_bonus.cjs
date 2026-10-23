const {chromium,webkit}=require('playwright');
const assert=require('assert/strict'),fs=require('fs');
const URL=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
(async()=>{
 for(const engine of ['chromium','webkit']){
  const browser=await ({chromium,webkit}[engine]).launch(engine==='chromium'&&process.env.UNO_QA_CHROME?{channel:'chrome'}:{});
  for(const fallback of [false,true]){
   const context=await browser.newContext(),page=await context.newPage();
   if(process.env.UNO_QA_SOUND_SOURCE)await page.route('**/assets/art/sound.js*',r=>r.fulfill({body:fs.readFileSync(process.env.UNO_QA_SOUND_SOURCE,'utf8'),contentType:'text/javascript'}));
   await page.addInitScript(fallback=>{
    window.__bonusPlays=0;window.__bonusOscillators=0;
    const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...args){if(this.src.startsWith('blob:'))window.__bonusPlays++;return play.apply(this,args);};
    if(window.OscillatorNode){const start=OscillatorNode.prototype.start;OscillatorNode.prototype.start=function(...args){window.__bonusOscillators++;return start.apply(this,args);};}
    if(fallback&&window.AudioContext){const Native=window.AudioContext;window.AudioContext=class extends Native{get state(){return 'interrupted';}resume(){return Promise.resolve();}};}
   },fallback);
   await page.goto(URL+'/admin');await page.waitForFunction(()=>window.UNOLuckSound);
   assert.equal(await page.evaluate(()=>__bonusPlays+__bonusOscillators),0);
   await page.evaluate(()=>{const b=document.createElement('button');b.id='qa-unlock';b.textContent='Unlock test';b.onclick=()=>UNOLuckSound.unlock();document.body.prepend(b);});
   await page.locator('#qa-unlock').click();await page.waitForTimeout(1600);
   await page.evaluate(()=>{UNOLuckSound.setEnabled(true);UNOLuckSound.setMasterVolume(.9);UNOLuckSound.setVolume(.85);});
   const before=await page.evaluate(()=>({plays:__bonusPlays,osc:__bonusOscillators}));
   assert.equal(await page.evaluate(()=>UNOLuckSound.numericBonus()),true);
   const after=await page.evaluate(()=>({plays:__bonusPlays,osc:__bonusOscillators}));
   if(fallback||await page.evaluate(()=>!window.AudioContext&&!window.webkitAudioContext))assert.equal(after.plays-before.plays,1);else assert.equal(after.osc-before.osc,4);
   await page.evaluate(()=>UNOLuckSound.setEnabled(false));assert.equal(await page.evaluate(()=>UNOLuckSound.numericBonus()),false);
   // Dynamic server payout must retain celebration; numeric bonuses must not.
   await page.evaluate(()=>{
    window.UNOLuckSound.celebration=async()=>({played:false,duration:0});
    window.__prize={complete:true,combo:'COLOR_MATCH',stake:10,payout:250,delta:240,rules_version:2,
      pattern:'COLOR_MATCH',cards:[2,5,9].map(n=>({color:'blue',face:String(n)})),
      tier:{rank:5,title:'LUCKY COLOR WIN',multiplier:25,pattern:'COLOR_MATCH'}};
    window.__present=UNOLuckCelebration.present(__prize);
   });
   await page.locator('#celebration-overlay').waitFor({state:'visible'});
   assert((await page.locator('#celebration-amount').innerText()).includes('250'));
   assert((await page.locator('#celebration-art').getAttribute('src')).endsWith('/festive/trophy.svg'));
   await page.evaluate(()=>{UNOLuckCelebration.close();return __present;});
   assert.equal(await page.evaluate(()=>UNOLuckCelebration.present({...__prize,payout:9999})),false);
   assert.equal(await page.evaluate(()=>UNOLuckCelebration.present({...__prize,combo:'PAIR_PRODUCT',tier:null})),false);
   // Draw Two pair receives the small non-rank Coin celebration and rolling amount.
   await page.goto(URL+'/?qa_draw_two_bonus=1');
   await page.waitForFunction(()=>typeof showNumericBonus==='function'&&window.UNOLuckSound);
   await page.evaluate(()=>showNumericBonus({stake:50,payout:400,delta:350,
    bonus:{kind:'PAIR_SUM',multiplier:8},cards:[
      {color:'blue',face:'+2'},{color:'blue',face:'+2'},{color:'yellow',face:'4'}]}));
   const bonus=page.locator('#numeric-bonus');await bonus.waitFor({state:'visible'});
   assert(await bonus.evaluate(node=>node.classList.contains('is-draw-two')));
   assert.equal(await bonus.locator('.numeric-bonus-title').innerText(),'DRAW TWO MATCH');
   await page.waitForTimeout(950);
   assert.equal(await bonus.locator('.numeric-bonus-amount').innerText(),'+400 Coin');
   assert((await page.locator('#win-particles .win-shard').count())>0||
     await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches));
   await context.close();console.log(JSON.stringify({engine,fallback,result:'PASS'}));
  }
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1);});
