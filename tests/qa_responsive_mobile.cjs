/** UNO LUCK: source-backed responsive iPhone 15 Pro / small iPhone /
 * landscape / desktop layout assertions, with an optional fixture screenshot.
 * Read-only DOM display. No mutations of API, user wallets or Sound Cloud.
 */
'use strict';
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const BASE=process.env.UNO_QA_URL||'http://127.0.0.1:8080';
const OUT='artifacts/uno-v1164-responsive';
fs.mkdirSync(OUT,{recursive:true});
const layouts=[
  {name:'iphone15pro',width:393,height:852},
  {name:'iphone15pro-safe',width:393,height:852,safe:true},
  {name:'iphone-small',width:320,height:568},
  {name:'iphone-medium',width:390,height:844},
  {name:'iphone-large',width:430,height:932},
  {name:'safari-viewport',width:393,height:659},
  {name:'landscape',width:852,height:393},
  {name:'desktop',width:1440,height:1000}
];

(async()=>{
 for(const engine of ['chromium','webkit']){
  const browser=await ({chromium,webkit}[engine]).launch({headless:true});
  for(const layout of layouts){
   const context=await browser.newContext({
     viewport:{width:layout.width,height:layout.height},hasTouch:true,
     isMobile:layout.width<layout.height,
     reducedMotion:'reduce',
     userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1'
   });
   const page=await context.newPage();
   const errors=[];
   page.on('pageerror',error=>errors.push(String(error)));
   await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.UNOLuckActivity &&
     ['live','simulation'].includes(window.UNOLuckActivity.mode) &&
     typeof window.UNOLuckMotion?.numbers==='function' &&
     typeof account!=='undefined' && Boolean(account) && !stateLoading,
     null,{timeout:18000});
   await page.evaluate(safe=>{
     const g=document.getElementById('game-shell');
     if(safe){
       g.style.setProperty('padding-top','68px','important');
       g.style.setProperty('padding-bottom','34px','important');
     }
     g.classList.remove('is-booting');g.removeAttribute('aria-hidden');
     document.getElementById('boot-overlay').hidden=true;
     window.UNOLuckMotion.numbers({stake:25,payout:0,delta:0,animate:false});
     // These three blue cards are an illustration only. Show an actual
     // Rank-5 payout, never a "zero WIN" on a same-color triple.
     if(typeof paintRound==='function'){
       paintRound({
         stake:25,charged_stake:25,picked:3,complete:true,
         cards:[6,3,8].map(n=>({color:'blue',face:String(n)})),
         combo:'COLOR_MATCH',payout:625,promo_coin:0,delta:600,
         tier:{rank:5,title:'LUCKY COLOR WIN',multiplier:25}
       });
     }
   },Boolean(layout.safe));
   await page.waitForTimeout(140);
   const measured=await page.evaluate(()=>{
     const get=q=>document.querySelector(q);
     const rect=q=>{
       const r=get(q).getBoundingClientRect();
       return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,
         width:r.width,height:r.height};
     };
     const totalStyle=getComputedStyle(get('#total-bet-row'));
     const payoutStyle=getComputedStyle(get('#activity-board'));
     const drawerStyle=getComputedStyle(get('#metric-drawer'));
     const titleStyle=getComputedStyle(get('.title-area .motion-title'));
     const rail=get('#activity-feed');
     const cycle=get('.activity-cycle');
     const tickerClip=get('.activity-viewport');
     const hud=[...get('.result-bar').querySelectorAll(':scope>div')].map(
       c=>({label:c.querySelector('small').textContent,
         direction:getComputedStyle(c).flexDirection,
         labelMidY:(c.querySelector('small').getBoundingClientRect().top+
           c.querySelector('small').getBoundingClientRect().bottom)/2,
         valueMidY:(c.querySelector('strong').getBoundingClientRect().top+
           c.querySelector('strong').getBoundingClientRect().bottom)/2,
         labelFont:parseFloat(getComputedStyle(c.querySelector('small')).fontSize),
         valueFont:parseFloat(getComputedStyle(c.querySelector('strong')).fontSize),
         minX:c.getBoundingClientRect().left,maxX:c.getBoundingClientRect().right}));
     return {
       header:rect('.game-header'),title:rect('.title-area'),
       cards:rect('.result-area'),bet:rect('.game-shell>.result-bar'),
       wheel:rect('.wheel-area'),stage:rect('.wheel-stage'),
       ticker:rect('#activity-board'),totalBet:rect('#total-bet-row'),
       drawer:rect('#metric-drawer'),maxTag:rect('.title-max-visual'),
       titleText:get('.title-area .motion-title').textContent,
       visibleTitle:get('.title-area').innerText,
       maxTagText:get('.title-max-visual').textContent,
       maxTagHint:get('.title-max-visual').getAttribute('title'),
       titleMetal:{background:titleStyle.backgroundImage,
         stroke:titleStyle.webkitTextStrokeWidth,
         sheen:getComputedStyle(get('.title-area .motion-title'),'::after').animationName},
       drawerStyle:{background:drawerStyle.backgroundImage,
         radius:drawerStyle.borderBottomLeftRadius,
         border:parseFloat(drawerStyle.borderLeftWidth)},
       simulationLine:get('#total-bet-row').textContent,
       modeInPayout:get('#activity-board').contains(get('#activity-mode')),
       titleCenter:(get('.title-area .motion-title').getBoundingClientRect().left+
         get('.title-area .motion-title').getBoundingClientRect().right)/2,
       totalVisual:{background:totalStyle.backgroundColor,image:totalStyle.backgroundImage,
         border:parseFloat(totalStyle.borderTopWidth),shadow:totalStyle.boxShadow},
       payoutVisual:{background:payoutStyle.backgroundColor,image:payoutStyle.backgroundImage,
         border:parseFloat(payoutStyle.borderTopWidth),shadow:payoutStyle.boxShadow},
       tickerCycleWidth:cycle?.getBoundingClientRect().width||0,
       tickerVisibleWidth:tickerClip.getBoundingClientRect().width,
       tickerCopies:rail.querySelectorAll('.activity-cycle').length,
       tickerAnimation:getComputedStyle(rail).animationName,
       shell:rect('#game-shell'),
       hud,headline:get('.activity-head').textContent,
       tickerText:get('#activity-board').textContent,
       total:get('#activity-total').textContent,
       mode:get('#activity-mode').textContent,
       label:get('.activity-total-label').textContent,
       cardFaces:[...get('.result-area').querySelectorAll('.result-cell .card3d .number')]
         .map(x=>x.textContent),
       cardNumberFont:parseFloat(getComputedStyle(
         get('.result-cell .card3d .number')).fontSize),
       payoutLabel:get('.result-bar').children[1].querySelector('small').textContent,
       fontTicker:parseFloat(getComputedStyle(get('.activity-feed')).fontSize),
       digits:get('#last-payout').textContent,
       scrollW:document.documentElement.scrollWidth,
       scrollH:document.documentElement.scrollHeight,
       screenW:innerWidth,screenH:innerHeight,
       controls:['#spin-btn','#turbo-btn','#auto-btn'].map(rect)
     };
   });
   assert.deepEqual(measured.hud.map(x=>x.label),['BET','WIN','NET'],
     [engine,layout.name,measured.hud]);
   assert(measured.titleText==='DRAGON SPIN' &&
     measured.maxTagText==='X1000' &&
     !/3 kartu|15 pola|300[×x]/i.test(measured.visibleTitle),
     [engine,layout.name,'old title line still displayed',measured.visibleTitle]);
   assert(measured.maxTagHint.includes('tema visual') &&
     measured.titleMetal.background.includes('linear-gradient') &&
     parseFloat(measured.titleMetal.stroke)>0,
     [engine,layout.name,'3D gold title or explicit visual-only hint missing',measured.titleMetal]);
   assert(Math.abs((measured.drawer.left+measured.drawer.right)/2 -
     (measured.bet.left+measured.bet.right)/2)<4 &&
     measured.drawer.top>=measured.bet.bottom-9 &&
     measured.drawer.top<=measured.bet.bottom+8,
     [engine,layout.name,'drawer not centered and hanging from BET',measured]);
   assert(measured.drawerStyle.background.includes('linear-gradient') &&
     parseFloat(measured.drawerStyle.radius)>0 && measured.drawerStyle.border>0,
     [engine,layout.name,'metal drawer skin missing',measured.drawerStyle]);
   assert(!measured.simulationLine.includes('SIMULASI QA') &&
     measured.modeInPayout &&
     measured.mode==='SIMULASI QA',
     [engine,layout.name,'QA marker must be with PAYOUT not TOTAL BET',measured]);
   assert(measured.headline.includes('PAYOUT'),
     [engine,layout.name,measured.headline]);
   assert(!measured.tickerText.includes('PAYOUT DEMO') &&
     !measured.tickerText.includes('PAYOUT SIMULASI') &&
     !measured.tickerText.includes('COIN VIRTUAL'),
     [engine,layout.name,measured.tickerText]);
   // Portrait stacks HUD -> TOTAL BET -> wheel; landscape shares a row
   // with the wheel in a separate right-side column.
   const totalPlaced=measured.totalBet.top>=measured.bet.bottom-3 &&
     (layout.width>layout.height && layout.height<=470
       ? measured.totalBet.right<=measured.wheel.left+3
       : measured.totalBet.bottom<=measured.wheel.top+3);
   assert(totalPlaced,
     [engine,layout.name,'unboxed TOTAL BET location',
       JSON.stringify({bet:measured.bet,total:measured.totalBet,wheel:measured.wheel})]);
   assert(measured.totalVisual.background==='rgba(0, 0, 0, 0)' &&
     measured.totalVisual.image==='none' &&
     measured.totalVisual.border===0 &&
     measured.totalVisual.shadow==='none',
     [engine,layout.name,'TOTAL BET has a background/frame/shadow',measured.totalVisual]);
   // Reserve caption clearance: wheel grows to row height minus 26px,
   // instead of the previous 31px gap, without clipping the dragon.
   assert(measured.stage.width>=Math.min(measured.wheel.width,measured.wheel.height)-32,
     [engine,layout.name,'Dragon SPIN panel too small for its safe row',measured]);
   assert(measured.total.startsWith('Rp'),
     [engine,layout.name,'No Rupiah prefix',measured.total]);
   assert(measured.digits==='625',[engine,layout.name,measured.digits]);
   assert.deepEqual(measured.cardFaces,['6','3','8'],
     [engine,layout.name,'approved mockup card faces',measured.cardFaces]);
   assert(measured.payoutLabel==='WIN',
     [engine,layout.name,'PAYOUT text must be WIN',measured.payoutLabel]);
   assert(measured.scrollW<=measured.screenW+2,
     [engine,layout.name,'horizontal overflow',measured]);
   assert(measured.scrollH<=measured.screenH+2,
     [engine,layout.name,'vertical overflow',measured]);
   for(const key of ['header','title','cards','bet','drawer','totalBet','maxTag','wheel','ticker']){
     assert(measured[key].left>=-3&&measured[key].right<=measured.screenW+3,
       [engine,layout.name,key,'horizontal clip',measured]);
   }
   const shortLandscape=layout.width>layout.height && layout.height<=470;
   assert(measured.ticker.top>=measured.totalBet.bottom-3 &&
     measured.ticker.bottom<=measured.drawer.bottom+3 &&
     measured.totalBet.top>=measured.drawer.top-3,
     [engine,layout.name,'PAYOUT/TOTAL BET outside single drawer',measured]);
   if(shortLandscape){
     assert(measured.ticker.top>=measured.wheel.bottom-3,
       [engine,layout.name,'landscape ticker overlaps wheel',measured]);
   }else{
     assert(measured.ticker.bottom<=measured.wheel.top+3,
       [engine,layout.name,'PAYOUT should appear above Dragon Spin',measured]);
   }
   assert(measured.payoutVisual.background==='rgba(0, 0, 0, 0)' &&
     measured.payoutVisual.image==='none' &&
     measured.payoutVisual.border===0 &&
     measured.payoutVisual.shadow==='none',
     [engine,layout.name,'PAYOUT has a background/pillshape',measured.payoutVisual]);
   assert(measured.tickerCopies===2 &&
     measured.tickerCycleWidth>=measured.tickerVisibleWidth,
     [engine,layout.name,'PAYOUT rail has a blank gap',measured]);
   assert(measured.ticker.top>=measured.bet.bottom+3,
     [engine,layout.name,'ticker/bet overlap',measured]);
   assert(measured.ticker.bottom<=measured.shell.bottom+2,
     [engine,layout.name,'ticker below viewport',measured]);
   assert(measured.ticker.top>=measured.cards.bottom+3 &&
     measured.ticker.top>=measured.title.bottom+3,
     [engine,layout.name,'ticker covers cards/title',measured]);
   for(const r of measured.controls)
     assert(r.left>=-3&&r.right<=measured.screenW+3&&
       r.top>=-3&&r.bottom<=measured.screenH+3,
       [engine,layout.name,'control clipped',r]);
   if(layout.width<layout.height){
     assert(measured.hud.every(x=>x.direction==='row' &&
       Math.abs(x.labelMidY-x.valueMidY)<7),
       [engine,layout.name,'BET/WIN/NET must align horizontally',measured.hud]);
     if(layout.width>=390&&layout.height>=659){
       assert(measured.hud.every(x=>x.labelFont>=11&&x.valueFont>=17),
         [engine,layout.name,'HUD still too small',measured.hud]);
       assert(measured.fontTicker>=12,
         [engine,layout.name,'ticker still too small',measured.fontTicker]);
     }
     if(layout.width>=390&&layout.height>=660){
       assert(measured.hud.every(x=>x.labelFont>=13&&x.valueFont>=21),
         [engine,layout.name,'approved mobile HUD should be 2x legible',measured.hud]);
       assert(measured.cardNumberFont>=50,
         [engine,layout.name,'card numbers should dominate result',measured.cardNumberFont]);
       assert(measured.fontTicker>=13,
         [engine,layout.name,'ticker font below approved mobile minimum',measured.fontTicker]);
     }
     assert(measured.header.bottom<=measured.title.top+3,
       [engine,layout.name,'header/title overlap',measured]);
     assert(measured.title.bottom<=measured.cards.top+3,
       [engine,layout.name,'title/cards overlap',measured]);
     assert(measured.cards.bottom<=measured.bet.top+3,
       [engine,layout.name,'cards/bet overlap',measured]);
     assert(measured.bet.bottom<=measured.totalBet.top+3 &&
       measured.ticker.bottom<=measured.wheel.top+3,
       [engine,layout.name,'HUD/TOTAL BET/PAYOUT/wheel overlap',measured]);
   }
   await page.screenshot({path:path.join(OUT,engine+'-'+layout.name+'.png')});
   assert.deepEqual(errors,[],[engine,layout.name,errors]);
   console.log(engine+' '+layout.name+': PASS gold 3D title, X1000-only label, centered hanging drawer, ticker and wheel');
   await context.close();
  }
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exit(1);});
