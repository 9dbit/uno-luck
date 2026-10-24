/** iPhone WebKit RAF stall regression; no ledger or account mutations. */
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8080';

(async()=>{
  for(const engine of ['chromium','webkit']){
    const browser=await ({chromium,webkit}[engine]).launch({headless:true});
    const ctx=await browser.newContext({viewport:{width:393,height:852},
      isMobile:true,hasTouch:true,
      userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Version/18.6 Mobile/15E148 Safari/604.1'});
    const page=await ctx.newPage();
    const errors=[];
    page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>Boolean(window.UNOLuckLEDWheel));
    const state=await page.evaluate(async()=>{
      const originalRAF=window.requestAnimationFrame;
      const host=document.createElement('div');host.className='wheel-led-ring';
      const area=document.createElement('div');area.style.cssText='width:300px;height:200px;position:fixed;top:0;left:0';
      area.append(host);document.body.append(area);
      const make=card=>{const el=document.createElement('div');el.textContent=card.face;return el;};
      const wheel=new UNOLuckLEDWheel(host,make,9);
      const cards=Array.from({length:9},(_,i)=>({color:'blue',face:String(i)}));
      wheel.mount(cards);
      const oldAudio=window.UNOLuckSound;
      window.UNOLuckSound={...oldAudio,unlock:()=>Promise.resolve(false),
        startSpin:()=>false,stopSpin:()=>{},ledTick:()=>false,play:()=>false};
      window.requestAnimationFrame=()=>0; // simulate full iOS RAF suspension
      let stopped=false,selected=false,elapsed=0;
      try{
        wheel.begin({turbo:true});
        const began=performance.now();
        selected=await wheel.settle({color:'green',face:'8'},3);
        elapsed=performance.now()-began;
        stopped=!wheel.active&&host.dataset.spinPhase==='locked' &&
          wheel.lastSelected?.face==='8' && wheel.chaseIndex===4;
        const target=document.createElement('div');
        target.style.cssText='width:100px;height:150px;position:fixed;left:280px;top:200px';
        document.body.append(target);
        const anim=Element.prototype.animate;
        Element.prototype.animate=function(){return {finished:new Promise(()=>{}),cancel(){}}};
        const beganTransfer=performance.now();
        await wheel.transferTo(target); // animation.finished never resolves
        const transferMs=performance.now()-beganTransfer;
        Element.prototype.animate=anim;
        target.remove();
        wheel.cancel();
        return {selected,stopped,elapsed,transferMs,orphan:!!document.querySelector('.led-flying-card')};
      }finally{
        window.requestAnimationFrame=originalRAF;
        window.UNOLuckSound=oldAudio;
        wheel.cancel();area.remove();
      }
    });
    assert(state.selected,state);
    assert(state.stopped,state);
    assert(state.elapsed>=3900&&state.elapsed<7000,state);
    assert(state.transferMs<1600,state);
    assert(!state.orphan,state);
    assert.deepEqual(errors,[]);
    console.log(engine+': PASS 3rd LED forced confirmed-center settlement and orphan-free transfer timeout');
    await ctx.close();await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1});
