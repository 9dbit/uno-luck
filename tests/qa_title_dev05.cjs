/** DEV-05 golden title: browser-only visual QA, no transaction writes. */
'use strict';
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const {PNG}=require('pngjs');
const fs=require('node:fs');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
const OUT='artifacts/uno-dev05-title';
fs.mkdirSync(OUT,{recursive:true});
const views=[
  {name:'iphone15pro',w:393,h:852},
  {name:'iphone15pro-safe',w:393,h:852,safe:true},
  {name:'iphone-small',w:320,h:568},
  {name:'safari-short',w:393,h:659},
  {name:'iphone-large',w:430,h:932},
  {name:'landscape',w:852,h:393},
  {name:'desktop',w:1440,h:1000}
];
(async()=>{
 for(const [engine,launcher] of Object.entries({chromium,webkit})){
  const browser=await launcher.launch({headless:true});
  for(const v of views){
   const context=await browser.newContext({
    viewport:{width:v.w,height:v.h},
    hasTouch:true,isMobile:v.w<v.h,
    reducedMotion:'reduce'
   });
   const page=await context.newPage();
   const errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>{
    const art=document.getElementById('dragon-title-art');
    return art&&art.complete&&art.naturalWidth>0&&
      document.querySelector('.title-area')?.dataset.titleAsset==='loaded';
   },null,{timeout:25000});
   await page.evaluate(safe=>{
    const s=document.getElementById('game-shell');
    if(safe){
     s.style.setProperty('padding-top','68px','important');
     s.style.setProperty('padding-bottom','34px','important');
    }
    s.classList.remove('is-booting');s.removeAttribute('aria-hidden');
    document.getElementById('boot-overlay').hidden=true;
   },Boolean(v.safe));
   await page.waitForFunction(()=>{
     const im=document.getElementById('dragon-title-art');
     const h1=document.querySelector('.motion-title');
     return Number(getComputedStyle(im).opacity)>.98 &&
       Number(getComputedStyle(h1).opacity)<.02;
   },null,{timeout:5000});
   // Loaded image/style is not the same as painted artwork. Give WebKit and
   // Chrome two compositor frames plus a small settled-paint interval.
   await page.evaluate(()=>new Promise(resolve=>
     requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   await page.waitForTimeout(320);
   const m=await page.evaluate(()=>{
    const r=sel=>{const a=document.querySelector(sel).getBoundingClientRect();
      return {top:a.top,bottom:a.bottom,left:a.left,right:a.right,width:a.width,height:a.height}};
    const im=document.getElementById('dragon-title-art');
    const wrapper=document.querySelector('.title-area');
    return {
      loaded:wrapper.classList.contains('is-art-ready'),
      asset:im.getAttribute('src'),
      image:{naturalWidth:im.naturalWidth,naturalHeight:im.naturalHeight,
        opacity:Number(getComputedStyle(im).opacity),
        src:im.currentSrc,
        version:im.dataset.titleArtVersion,
        imageFit:getComputedStyle(im).objectFit,
        filter:getComputedStyle(im).filter},
      semanticTitle:document.querySelector('.motion-title').textContent.trim(),
      semanticPromo:document.querySelector('.title-max-visual').textContent.trim(),
      promoTooltip:document.querySelector('.title-max-visual').getAttribute('title'),
      oldOpacity:Number(getComputedStyle(document.querySelector('.motion-title')).opacity),
      goldImage:r('#dragon-title-art'),
      gameHeader:r('.game-header'),
      title:r('.title-area'),cards:r('.result-area'),
      wheel:r('.wheel-area'),bet:r('.result-bar'),drawer:r('#metric-drawer'),
      mask:getComputedStyle(document.querySelector('.title-glint-dev05')).maskImage,
      overflow:document.documentElement.scrollWidth-innerWidth,
      controls:['#spin-btn','#auto-btn','#bet-open','#profile-btn'].map(x=>({
        id:x,present:!!document.querySelector(x),
        width:document.querySelector(x)?.getBoundingClientRect().width
      }))
    };
   });
   assert.equal(m.loaded,true,m);
   assert.equal(m.image.naturalWidth,1600,m);
   assert.equal(m.image.naturalHeight,480,m);
   assert.equal(m.image.version,'1172',m);
   assert(m.image.src.includes('dev06/dragon-spin-x1000-gold-1600.webp'),m);
   assert.equal(m.semanticTitle,'DRAGON SPIN',m);
   assert.equal(m.semanticPromo,'X1000',m);
   assert.match(m.promoTooltip,/tema visual/,m);
   assert(m.image.opacity>.98,m);
   assert(m.oldOpacity<.02,m);
   assert(m.mask!=='none',m);
   if(v.w<v.h)assert(m.image.filter.includes('brightness'),m);
   assert(m.goldImage.width>=Math.min(v.w*.74,130),m);
   const titleMid=(m.title.left+m.title.right)/2;
   const imageMid=(m.goldImage.left+m.goldImage.right)/2;
   assert(Math.abs(titleMid-imageMid)<5,m);
   // Preserve room for glowing bevel without covering the result cards.
   if(v.w<v.h){
     assert(m.goldImage.width>=m.title.width*.94,
       JSON.stringify({engine,viewport:v,issue:'title still too narrow on iPhone',
         image:m.goldImage,title:m.title}));
     assert(m.goldImage.left>=m.title.left-10 && m.goldImage.right<=m.title.right+10,
       JSON.stringify({engine,viewport:v,issue:'title exceeds horizontal bounds',
         image:m.goldImage,title:m.title}));
     assert(m.goldImage.bottom<=m.cards.top+12,
       JSON.stringify({engine,viewport:v,issue:'title overlaps cards',image:m.goldImage,cards:m.cards,title:m.title}));
     assert(m.goldImage.top>=m.gameHeader.bottom-22,
       JSON.stringify({engine,viewport:v,issue:'title overlaps header',image:m.goldImage,header:m.gameHeader,title:m.title}));
   }
   assert(m.overflow<=3,m);
   assert(m.controls.every(x=>x.present&&x.width>=22),m);
   assert(!errors.length,{engine,viewport:v,errors});
   const screenshot=await page.screenshot({path:OUT+'/'+engine+'-'+v.name+'.png',fullPage:false});
   const img=PNG.sync.read(screenshot);
   const sx=Math.max(0,Math.floor(m.title.left)+2);
   const ex=Math.min(img.width,Math.ceil(m.title.right)-2);
   const sy=Math.max(0,Math.floor(m.title.top)+2);
   const ey=Math.min(img.height,Math.ceil(m.title.bottom)+3);
   let goldPixels=0;
   for(let y=sy;y<ey;y++)for(let x=sx;x<ex;x++){
     const k=(y*img.width+x)*4;
     const R=img.data[k],G=img.data[k+1],B=img.data[k+2];
     if(R>165 && G>87 && B<160 && R>G+18)goldPixels++;
   }
   if(v.w<v.h)assert(goldPixels>=500,
     JSON.stringify({engine,viewport:v,issue:'wordmark not painted onscreen',
       goldPixels,region:{sx,ex,sy,ey},image:m.goldImage,title:m.title}));
   console.log(engine+' '+v.name+' PASS: 1600px iPhone title + '+goldPixels+' visible gold pixels, no overlap');
   await context.close();
  }
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1);});
