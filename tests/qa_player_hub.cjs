/* UI-only fixtures. Never send a pick, join, gift or sound write to staging. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const pw=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES?process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright':'playwright');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
const OUT=process.env.UNO_QA_OUT||'artifacts/uno-v1148-player-hub';fs.mkdirSync(OUT,{recursive:true});
const sources=process.env.UNO_QA_SOURCES?JSON.parse(fs.readFileSync(process.env.UNO_QA_SOURCES,'utf8')):null;
const sizes=[[320,568],[320,700],[393,659],[393,852],[390,844],[430,932],[852,393],[1440,1000]];
(async()=>{
 for(const engine of (process.env.UNO_QA_ENGINE||'chromium,webkit').split(',')){
  const b=await pw[engine].launch({headless:true,...(process.env.UNO_QA_CHROME?{channel:'chrome'}:{})});
  try{
  const c=await b.newContext({viewport:{width:393,height:852},reducedMotion:'reduce'}),p=await c.newPage();
  const baseline=await(await c.request.get(BASE+'/api/sounds/manifest')).json();
  const state=await(await c.request.get(BASE+'/api/orbit/state')).json();state.round=null;state.recent=[];state.account.balance=1000;
  let joins=0,mode='normal',held=null;const errors=[],unexpected=[];
  const event={event:{id:'2026-10-22',title:'Dragon Daily',ends_at:1792688400,server_time:1792638000,round_limit:10,timezone:'WIB',participants:0},you:null,leaderboard:[]};
  p.on('pageerror',e=>errors.push(e.message));
  await p.route(BASE+'/**',async r=>{
   const u=new URL(r.request().url());
   if(sources&&u.pathname==='/api/ui-version')return r.fulfill({json:{release:'1'.repeat(20)}});
   if(u.pathname==='/api/orbit/state')return r.fulfill({json:state});
   if(u.pathname==='/api/tournament/state'){
    if(mode==='hold'){held=r;return;}
    if(mode==='fail')return r.fulfill({status:503,json:{detail:'Turnamen sedang offline'}});
    return r.fulfill({json:event});
   }
   if(u.pathname==='/api/tournament/join'){
    joins++;event.event.participants=1;event.you={name:'Player',points:0,rounds:0,position:1,is_you:true};event.leaderboard=[event.you];return r.fulfill({json:event});
   }
   if(!['GET','HEAD'].includes(r.request().method())){unexpected.push(u.pathname);return r.abort();}
   if(sources){const key=u.pathname==='/'?'orbit-index.html':u.pathname.replace('/assets/','');
    if(sources[key])return r.fulfill({contentType:key.endsWith('.html')?'text/html':key.endsWith('.css')?'text/css':key.endsWith('.svg')?'image/svg+xml':'application/javascript',body:sources[key].replaceAll('__UNO_RELEASE__','1'.repeat(20))});}
   return r.continue();
  });
  await p.goto(BASE,{waitUntil:'domcontentloaded'});await p.locator('#boot-play').click({timeout:25000});
  await p.locator('#game-shell').waitFor({state:'visible',timeout:25000});
  const close=()=>p.locator('#modal-close').click();
  const menu=async(name)=>{await p.locator('#profile-btn').click();if(name)await p.getByRole('button',{name,exact:true}).click();};
  async function bounds(){
   await p.locator('#modal img').evaluateAll(imgs=>Promise.all(imgs.map(img=>img.decode())));
   assert(await p.locator('#modal img').evaluateAll(imgs=>imgs.every(img=>img.naturalWidth>0)),'panel artwork loaded');
   const dims=await p.evaluate(()=>({page:document.documentElement.scrollWidth<=innerWidth+1,content:document.querySelector('#modal-content').scrollWidth<=document.querySelector('#modal-content').clientWidth+1}));
   assert(dims.page&&dims.content,JSON.stringify(dims));
   for(const sel of ['#modal-close','.panel-primary'])if(await p.locator(sel).count()){
    const box=await p.locator(sel).boundingBox();assert(box&&box.y>=0&&box.y+box.height<=p.viewportSize().height+1,sel+JSON.stringify(box));
   }
  }
  for(const [width,height] of sizes){
   await p.setViewportSize({width,height});await menu();
   assert.deepEqual(await p.locator('.menu-tile').evaluateAll(ns=>ns.map(n=>n.getAttribute('aria-label'))),['Turnamen','Game Rules','Bet Setting','Profile','Sound On']);
   assert(!/Sound Studio|Mixer|Galeri|Gift|%/.test(await p.locator('#modal-content').innerText()));
   await bounds();await p.screenshot({path:path.join(OUT,`${engine}-menu-${width}x${height}.png`)});await close();
   await menu('Bet Setting');assert.equal(await p.locator('[data-bet]').count(),5);await bounds();
   await p.screenshot({path:path.join(OUT,`${engine}-bet-${width}x${height}.png`)});await close();
   await menu('Turnamen');await p.getByRole('button',{name:'GABUNG GRATIS'}).waitFor();await bounds();
   assert.equal(joins,0);await p.screenshot({path:path.join(OUT,`${engine}-tournament-${width}x${height}.png`)});await close();
   for(const name of ['Game Rules','Profile']){await menu(name);await bounds();await p.screenshot({path:path.join(OUT,`${engine}-${name.replaceAll(' ','-')}-${width}x${height}.png`)});await close();}
   for(const [selector,name] of [['#gift-btn','gift'],['#wallet-open','coin'],['#auto-btn','auto']]){
    await p.locator(selector).click();await bounds();
    assert.equal(await p.locator('.hero-art').count(),1,name+' hero');
    if(name==='coin'){const top=(await p.locator('.coin-summary').boundingBox()).y;await p.locator('.coin-history').evaluate(el=>el.scrollTop=el.scrollHeight);assert.equal((await p.locator('.coin-summary').boundingBox()).y,top);}
    await p.screenshot({path:path.join(OUT,`${engine}-${name}-${width}x${height}.png`)});await close();
   }
  }
  await p.setViewportSize({width:393,height:852});await menu('Bet Setting');await p.locator('[data-bet="100"]').click();await close();
  assert.equal(await p.locator('#last-stake').innerText(),'25');
  await menu('Bet Setting');await p.locator('[data-bet="100"]').click();await p.getByRole('button',{name:'GUNAKAN BET',exact:true}).click();
  assert.equal(await p.locator('#last-stake').innerText(),'100');
  await p.locator('#about-btn').click();assert((await p.locator('#modal-content').innerText()).includes('bukan permainan UNO resmi'));
  await p.getByRole('button',{name:'Soft Tech',exact:true}).click();assert((await p.locator('.about-story').innerText()).includes('Dikembangkan oleh Soft Tech'));
  await bounds();await p.screenshot({path:path.join(OUT,`${engine}-soft-tech.png`)});await close();
  await menu('Turnamen');await p.getByRole('button',{name:'GABUNG GRATIS'}).click();await p.getByRole('button',{name:'LANJUT BERMAIN'}).waitFor();assert.equal(joins,1);
  event.you={name:'Player',points:12,rounds:6,position:23,is_you:true};event.leaderboard=Array.from({length:20},(_,i)=>({name:'Player '+i,points:200-i,rounds:10,position:i+1,is_you:false}));
  await p.getByRole('button',{name:'Refresh',exact:true}).click();await p.locator('.leaderboard li').nth(19).waitFor();
  assert((await p.locator('.tournament-stats').innerText()).includes('#23'));await bounds();
  const top=(await p.locator('.panel-primary').boundingBox()).y;await p.locator('#modal-content').evaluate(e=>e.scrollTop=e.scrollHeight);
  assert.equal((await p.locator('.panel-primary').boundingBox()).y,top);await close();
  mode='fail';await menu('Turnamen');await p.getByRole('button',{name:'Coba lagi',exact:true}).waitFor();await close();
  mode='hold';await menu('Turnamen');await p.waitForTimeout(200);await p.locator('#modal-back').click();assert.equal(await p.locator('#modal-title').innerText(),'Menu');
  await held.fulfill({json:event});await p.waitForTimeout(100);assert.equal(await p.locator('#modal-title').innerText(),'Menu');await close();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(await(await c.request.get(BASE+'/api/sounds/manifest')).json(),baseline);
  console.log('PASS '+engine+': 8 viewports; menu; BET cancel/confirm; about; tournament join/scroll/error/stale response; no live writes; audio manifest unchanged');
  }finally{await b.close();}
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
