/* Browser-only pick fixtures: no live coin, gift, tournament or audio writes. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const pw=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES?process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright':'playwright');
const base=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
const out=process.env.UNO_QA_OUT||'artifacts/uno-v1149-bet';fs.mkdirSync(out,{recursive:true});
const sources=process.env.UNO_QA_SOURCES?JSON.parse(fs.readFileSync(process.env.UNO_QA_SOURCES,'utf8')):null;
(async()=>{
 for(const engine of (process.env.UNO_QA_ENGINE||'chromium,webkit').split(',')){
  const b=await pw[engine].launch({headless:true,...(process.env.UNO_QA_CHROME?{channel:'chrome'}:{})});
  try{
   const c=await b.newContext({viewport:{width:393,height:852},hasTouch:true,reducedMotion:'reduce'}),p=await c.newPage();
   const sound=await(await c.request.get(base+'/api/sounds/manifest')).json();
   const state=await(await c.request.get(base+'/api/orbit/state')).json();
   state.account.balance=950;state.recent=[];
   state.round={id:'fixture',stake:25,picked:1,cards:[{color:'red',face:'1'}],complete:false};
   const requests=[],errors=[],unexpected=[];let hold=false,held;
   p.on('pageerror',e=>errors.push(e.message));
   function respond(r){
    const data=r.request().postDataJSON();
    const round=state.round||{id:'fixture',stake:data.stake,picked:0,cards:[],complete:false};
    if(!state.round)state.account.balance-=data.stake;
    round.picked++;round.cards.push({color:['red','blue','green'][round.picked-1],face:String(round.picked)});
    if(round.picked===3)Object.assign(round,{complete:true,combo:'NO_MATCH',payout:0,delta:-round.stake});
    state.round=round.complete?null:round;
    return r.fulfill({json:{account:state.account,round}});
   }
   await p.route(base+'/**',async r=>{
    const u=new URL(r.request().url());
    if(u.pathname==='/api/orbit/state')return r.fulfill({json:state});
    if(u.pathname==='/api/orbit/pick'){requests.push(r.request().postDataJSON());if(hold){held=r;return;}return respond(r);}
    if(!['GET','HEAD'].includes(r.request().method())){unexpected.push(u.pathname);return r.abort();}
    if(sources&&u.pathname==='/api/ui-version')return r.fulfill({json:{release:'1'.repeat(20)}});
    if(sources){const key=u.pathname==='/'?'orbit-index.html':u.pathname.replace('/assets/','');if(sources[key])return r.fulfill({contentType:key.endsWith('.html')?'text/html':'application/javascript',body:sources[key].replaceAll('__UNO_RELEASE__','1'.repeat(20))});}
    return r.continue();
   });
   await p.goto(base,{waitUntil:'domcontentloaded'});await p.locator('#boot-play').click({timeout:25000});
   await p.locator('#game-shell').waitFor({state:'visible',timeout:25000});
   await p.evaluate(()=>{wheel.begin=()=>{};wheel.settle=async()=>true;wheel.transferTo=async()=>{};});
   const open=async()=>{await p.locator('#profile-btn').tap();await p.getByRole('button',{name:'Bet Setting',exact:true}).tap();};
   const save=()=>p.getByRole('button',{name:'GUNAKAN BET',exact:true}).tap();
   await open();assert.equal(await p.locator('[data-bet]:disabled').count(),0);
   await p.locator('[data-bet="100"]').tap();assert.equal(await p.locator('.panel-amount').innerText(),'100 Coin');
   await p.locator('#modal-close').tap();await open();assert.equal(await p.locator('[data-bet="25"]').getAttribute('aria-pressed'),'true');
   await p.locator('[data-bet="100"]').tap();await p.screenshot({path:out+'/'+engine+'-next-bet.png'});await save();
   assert.equal(await p.locator('#last-stake').innerText(),'25');
   for(let i=0;i<2;i++){await p.locator('#spin-btn').tap();await p.waitForFunction(()=>!isSpinning);}
   assert.deepEqual(requests.map(r=>r.stake),[25,25]);
   await p.locator('#spin-btn').tap();await p.waitForFunction(()=>!isSpinning);assert.equal(requests.at(-1).stake,100);
   for(let i=0;i<2;i++){await p.locator('#spin-btn').tap();await p.waitForFunction(()=>!isSpinning);}
   hold=true;const start=requests.length;
   await p.locator('#auto-btn').tap();await p.locator('[data-rounds="3"]').tap();await p.locator('#auto-start').tap();
   await p.waitForFunction(()=>isSpinning);await p.waitForTimeout(100);assert(held);
   await open();await p.locator('[data-bet="250"]').tap();await save();
   hold=false;await respond(held);await p.waitForFunction(()=>!isAuto&&!isSpinning,{},{timeout:25000});
   assert.deepEqual(requests.slice(start).map(r=>r.stake),Array(9).fill(100));
   await p.locator('#spin-btn').tap();await p.waitForFunction(()=>!isSpinning);assert.equal(requests.at(-1).stake,250);
   assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
   assert.deepEqual(await(await c.request.get(base+'/api/sounds/manifest')).json(),sound);
   console.log('PASS '+engine+': touch chip selection, cancel, queued BET, paid-round stake preserved, AUTO budget preserved, next request uses new BET, unchanged audio; no live writes');
  }finally{await b.close();}
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
