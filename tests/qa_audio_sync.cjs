// Run against a local disposable server. Audio fixtures are read-only copies
// of the published manifest and clips; never exercise a live coin ledger.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES?
  process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright':'playwright');
const root=path.resolve(__dirname,'..');
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/audio-sync-manifest.json')));
function tone(seconds){
 const rate=22050,n=Math.ceil(seconds*rate),b=Buffer.alloc(44+n*2);
 b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);
 b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*2,28);
 b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(n*2,40);
 for(let i=0;i<n;i++)b.writeInt16LE(Math.round(Math.sin(i/rate*440*2*Math.PI)*5000),44+i*2);
 return b;
}
const base=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
assert.match(base,/^http:\/\/(localhost|127\.0\.0\.1)(:|\/)/);
(async()=>{
 const server=require('node:child_process').spawn('python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8080'],
  {cwd:root,env:{...process.env,UNO_SPIN_DB_PATH:path.join(root,'fixtures/qa.sqlite3')},stdio:'ignore'});
 for(let i=0;i<50;i++){try{if((await fetch(base+'/health')).ok)break;}catch(_){}await new Promise(r=>setTimeout(r,100));}
 const browser=await chromium.launch({headless:true,executablePath:process.env.UNO_QA_CHROMIUM,
  args:['--autoplay-policy=user-gesture-required']});
 try{
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/sounds/manifest',r=>r.fulfill({json:manifest}));
  await page.route('**/api/sounds/files/*',r=>{
   const key=new URL(r.request().url()).pathname.split('/').pop();
   const fixture=path.join(root,'fixtures',key+'.mp3');
   return fs.existsSync(fixture)?r.fulfill({path:fixture,contentType:'audio/mpeg'}):
     r.fulfill({body:tone(manifest.cues[key].fileDuration),contentType:'audio/wav'});
  });
  await page.addInitScript(()=>{
   window.audioEvents=[];
   const start=AudioBufferSourceNode.prototype.start,stop=AudioBufferSourceNode.prototype.stop;
   AudioBufferSourceNode.prototype.start=function(...args){
    this.qaId=window.audioEvents.length;
    window.audioEvents.push({type:'start',id:this.qaId,at:performance.now(),clock:this.context.currentTime,
      duration:this.buffer?.duration,loop:this.loop,loopStart:this.loopStart,loopEnd:this.loopEnd,args});
    return start.apply(this,args);
   };
   AudioBufferSourceNode.prototype.stop=function(...args){
    window.audioEvents.push({type:'stop',id:this.qaId,at:performance.now(),args});return stop.apply(this,args);
   };
   window.addEventListener('uno:boot-finished',()=>window.audioEvents.push({type:'boot',at:performance.now()}));
  });
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.locator('#boot-play:not([disabled])').waitFor({timeout:25000});
  await page.locator('#boot-play').click();
  await page.waitForFunction(()=>document.querySelector('#boot-overlay').hidden,{timeout:20000});
  await page.waitForFunction(()=>window.UNOLuckSoundStudio.isMusicWebAudioPlaying());
  let events=await page.evaluate(()=>window.audioEvents);
  const splash=events.find(e=>e.type==='start'&&Math.abs(e.duration-46.45)<.2);
  const boot=events.find(e=>e.type==='boot');
  assert(splash,'published splash uses the shared Web Audio mixer');
  assert(Math.abs((boot.at-splash.at)-7000)<100,JSON.stringify({splash,boot}));
  assert.equal(events.filter(e=>e.type==='start'&&Math.abs(e.duration-26.12)<.2).length,1,'one BGM source');
  const levels=await page.evaluate(async()=>{
   const s=window.UNOLuckSound,c=s.channels(),a=c.context.createAnalyser();
   c.music.connect(a);a.fftSize=2048;
   await new Promise(r=>setTimeout(r,250));
   const samples=new Float32Array(a.fftSize);a.getFloatTimeDomainData(samples);a.disconnect();
   return {master:s.masterVolume,music:s.musicVolume,sfx:s.volume,rms:Math.sqrt(samples.reduce((n,v)=>n+v*v,0)/samples.length)};
  });
  assert.deepEqual([levels.master,levels.music,levels.sfx],[.9,.22,.85]);
  assert(levels.rms>.0001,'BGM must produce samples without a second tap');
  console.log('PASS splash/game reveal within 100ms; audible BGM samples; saved mixer',levels);
  let responseDelay=0;
  await page.route('**/api/orbit/pick',async route=>{
    await new Promise(r=>setTimeout(r,responseDelay));await route.continue();
  });
  await page.evaluate(()=>{
   const studio=window.UNOLuckSoundStudio,stop=studio.stopSpin;
   studio.stopSpin=function(){window.audioEvents.push({type:'spin-stop',at:performance.now()});return stop();};
   new MutationObserver(records=>{
    for(const r of records)if(r.attributeName==='data-spin-phase'&&r.target.dataset.spinPhase==='locked')
      window.audioEvents.push({type:'lock',at:performance.now()});
   }).observe(document.body,{attributes:true,subtree:true,attributeFilter:['data-spin-phase']});
  });
  for(const [label,turbo,delay] of [['normal',false,0],['turbo',true,0],['slow-server',false,3500]]){
  responseDelay=delay;
  await page.locator('#spin-btn:not([disabled])').waitFor({timeout:20000});
  if((await page.locator('#turbo-btn').getAttribute('aria-pressed'))!==String(turbo))await page.locator('#turbo-btn').click();
  const offset=await page.evaluate(()=>window.audioEvents.length);
  await page.locator('#spin-btn').click();
  await page.waitForFunction(n=>window.audioEvents.slice(n).some(e=>e.type==='lock'),offset,{timeout:20000});
  events=await page.evaluate(n=>window.audioEvents.slice(n),offset);
  const spin=events.find(e=>e.type==='start'&&Math.abs(e.duration-11.98)<.2);
  const locked=events.find(e=>e.type==='lock');
  const stopped=events.find(e=>e.type==='stop'&&e.id===spin?.id);
  assert(spin?.loop,'spin clip must loop beyond its trim');
  assert.equal(spin.loopEnd,2.5);
  assert(stopped&&Math.abs(stopped.at-locked.at)<50,'stop at visual center lock');
  if(delay)assert(stopped.at-spin.at>3500,'sound outlives the 2.5s clip on slow server');
  assert.equal(await page.evaluate(()=>window.UNOLuckSoundStudio.isSpinPlaying()),false);
  console.log('PASS '+label+' spin', {duration:stopped.at-spin.at,lockDelta:stopped.at-locked.at});
  }
  // Cancel while decoding: stale audio must not start after cancellation.
  const late=await page.evaluate(async()=>{
   const studio=window.UNOLuckSoundStudio,n=window.audioEvents.length;
   const pending=studio.startSpin();studio.stopSpin();await pending;
   return {playing:studio.isSpinPlaying(),starts:window.audioEvents.slice(n).filter(e=>e.type==='start'&&e.loop).length};
  });
  assert.deepEqual(late,{playing:false,starts:0});
  assert.deepEqual(errors,[]);
  console.log('PASS cancelled async start, no runtime errors');
  // Interrupted WebKit retains the native-media route and releases its mute.
  await page.addInitScript(()=>{
    const Native=window.AudioContext;
    window.AudioContext=class extends Native{get state(){return 'interrupted';}resume(){return Promise.resolve();}};
  });
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('#boot-play:not([disabled])').waitFor({timeout:25000});
  await page.locator('#boot-play').click();
  await page.waitForFunction(()=>document.querySelector('#boot-overlay').hidden,{timeout:20000});
  const native=await page.evaluate(()=>{
    const a=document.querySelector('audio[data-uno-music]');
    return {muted:a.muted,paused:a.paused,playing:window.UNOLuckSoundStudio.isMusicMediaPlaying()};
  });
  assert.deepEqual(native,{muted:false,paused:false,playing:true});
  assert.deepEqual(errors,[]);
  console.log('PASS interrupted-context native BGM fallback');
 }finally{await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
