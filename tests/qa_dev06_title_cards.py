"""DEV-06 isolated browser geometry validation. No user balances modified."""
import os, json, pathlib, sys
from playwright.sync_api import sync_playwright
BASE=os.environ.get('UNO_QA_URL','http://127.0.0.1:8099')
OUT=pathlib.Path(os.environ.get('UNO_QA_OUTPUT','/mnt/data/uno-dev06-local/qa'))
OUT.mkdir(exist_ok=True,parents=True)
CASES=[('iphone15pro',393,852,False),('iphone15pro-safe',393,852,True),('iphone-small',320,568,False),('iphone-large',430,932,False),('landscape',852,393,False),('desktop',1440,900,False)]
EVAL=r'''() => {
 const box=(sel)=>{const e=document.querySelector(sel);if(!e)return null;const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
 const im=document.getElementById('dragon-title-art'), st=getComputedStyle(im),
   glow=document.querySelector('.title-glint-dev05'), glowSt=getComputedStyle(glow);
 const nat=im.naturalWidth/im.naturalHeight;
 const paintedH=Math.min(im.clientHeight,im.clientWidth/nat);
 const paintedW=paintedH*nat;
 return {title:box('.title-area'),art:box('#dragon-title-art'),paintedH,paintedW,
   cards:box('.result-area'),card:box('.result-cell:nth-child(2) .card3d'),
   bet:box('.result-bar'),drawer:box('#metric-drawer'),wheel:box('.wheel-area'),
   header:box('.game-header'),glowDisplay:glowSt.display,
   glowAnimation:getComputedStyle(im).animationName,shadow:st.filter,
   imgSrc:im.getAttribute('src'),ready:document.querySelector('.title-area').classList.contains('is-art-ready'),
   errors:document.documentElement.scrollWidth-innerWidth};
}'''
with sync_playwright() as playwright:
 for engine in os.environ.get('UNO_QA_ENGINES','chromium,webkit').split(','):
  launch={'headless':True}
  if engine=='chromium' and os.environ.get('UNO_QA_SYSTEM_CHROMIUM')=='1': launch['executable_path']='/usr/bin/chromium'
  browser=getattr(playwright,engine).launch(**launch)
  for name,w,h,safe in CASES:
   page=browser.new_page(viewport={'width':w,'height':h},is_mobile=w<h,has_touch=True,reduced_motion='reduce')
   try:
    page.goto(BASE+'/',wait_until='domcontentloaded',timeout=20000)
    page.wait_for_function("() => {const a=document.querySelector('#dragon-title-art');return a && a.complete && a.naturalWidth>0 && document.querySelector('.title-area').classList.contains('is-art-ready')}",timeout=15000)
    page.evaluate('''safe => {const s=document.getElementById('game-shell');
        if(safe){s.style.setProperty('padding-top','68px','important');s.style.setProperty('padding-bottom','34px','important')}
        s.classList.remove('is-booting');s.removeAttribute('aria-hidden');document.getElementById('boot-overlay').hidden=true;
    }''',safe)
    m=page.evaluate(EVAL)
    assert m['ready'] and 'dev06/dragon-spin' in m['imgSrc'],(engine,name,'not new art')
    assert m['glowDisplay']=='none' and m['glowAnimation']=='none',(engine,name,'glow still on',m)
    assert 'drop-shadow(' in m['shadow'] and '#13' not in m['shadow'],(engine,name,'drop shadow',m['shadow'])
    assert m['errors']<=3,(engine,name,'overflow',m['errors'])
    assert m['card'] and m['card']['width']>45,(engine,name,'card geometry',m)
    # Compare visual geometry of precisely the same page with DEV-06 CSS disabled.
    page.evaluate("document.querySelector('link[href*=\"dev06-title-cards\"]').disabled=true")
    page.wait_for_timeout(75)
    old=page.evaluate(EVAL)
    page.evaluate("document.querySelector('link[href*=\"dev06-title-cards\"]').disabled=false")
    page.wait_for_timeout(75)
    now=page.evaluate(EVAL)
    if w<h:
      ratio=now['paintedW']/old['paintedW']
      assert .76<=ratio<=.89,(engine,name,'title not ~20% smaller',ratio,old['paintedW'],now['paintedW'])
      assert now['cards']['height']>old['cards']['height']+5,(engine,name,'card panel not enlarged',old['cards']['height'],now['cards']['height'])
      assert now['card']['height']>=old['card']['height']-2,(engine,name,'cards shrunk',old['card']['height'],now['card']['height'])
      assert abs(now['bet']['top']-old['bet']['top'])<3,(engine,name,'approved BET moved',old['bet']['top'],now['bet']['top'])
      assert abs(now['drawer']['top']-old['drawer']['top'])<3,(engine,name,'drawer moved')
      assert abs(now['wheel']['top']-old['wheel']['top'])<3,(engine,name,'wheel moved')
      assert now['card']['bottom'] <= now['bet']['top']+7,(engine,name,'cards overlap BET')
    assert now['art']['right']<=w+3,(engine,name,'art cropped')
    page.screenshot(path=str(OUT/f'{engine}-{name}.png'),full_page=True)
    print('PASS',engine,name,'title',round(now['paintedW']), 'previous',round(old['paintedW']),'card',round(old['card']['height']),'>',round(now['card']['height']))
   finally:
    page.close()
  browser.close()