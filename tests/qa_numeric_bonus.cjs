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
   await context.close();console.log(JSON.stringify({engine,fallback,result:'PASS'}));
  }
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1);});
