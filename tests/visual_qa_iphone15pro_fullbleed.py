"""Read-only iPhone 15 Pro Safari + full-screen PWA-like viewport QA.

Playwright WebKit is a browser-engine approximation, NOT a physical iPhone.
Game controls are exposed without invoking splash audio or placing game bets.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.environ.get("UNO_QA_URL","http://127.0.0.1:8080/")
OUT=Path("artifacts/uno-v12-iphone15pro-fullbleed")
OUT.mkdir(parents=True,exist_ok=True)

MODES=[
    ("safari-visible",393,659),
    ("pwa-fullscreen",393,852),
    ("portrait-small",320,700),
    ("portrait-short",320,568),
    ("portrait-large",430,932),
    ("landscape",852,393),
]

def inspect(page):
    return page.evaluate("""() => {
      const bounds=e=>{const b=e.getBoundingClientRect();
        return {top:b.top,bottom:b.bottom,left:b.left,right:b.right,
                width:b.width,height:b.height};};
      const game=document.getElementById('game-shell');
      const area=game.querySelector('.wheel-area');
      const stage=game.querySelector('.wheel-stage');
      const caption=game.querySelector('.spin-caption');
      const controls=['spin-btn','turbo-btn','auto-btn'].map(
        id=>({id,...bounds(document.getElementById(id))}));
      const html=getComputedStyle(document.documentElement);
      const bg=getComputedStyle(document.body,'::before');
      return {
        innerHeight:window.innerHeight,
        outerHeight:window.outerHeight,
        visualHeight:window.visualViewport?.height,
        cssDvh:CSS.supports('height','100dvh'),
        cssLvh:CSS.supports('height','100lvh'),
        viewportVar:html.getPropertyValue('--uno-viewport-height').trim(),
        wheelSize:game.style.getPropertyValue('--uno-wheel-size'),
        wheelDrop:game.style.getPropertyValue('--uno-wheel-drop'),
        htmlBackground:html.backgroundImage,
        pseudoBackground:bg.backgroundImage,
        pseudoHeight:parseFloat(bg.height),
        safeTop:parseFloat(getComputedStyle(game).paddingTop),
        safeBottom:parseFloat(getComputedStyle(game).paddingBottom),
        screenHeight:document.documentElement.clientHeight,
        scrollHeight:document.documentElement.scrollHeight,
        scrollWidth:document.documentElement.scrollWidth,
        game:bounds(game),area:bounds(area),stage:bounds(stage),
        caption:bounds(caption),controls
      };
    }""")

with sync_playwright() as p:
    engine=p.webkit
    browser=engine.launch(headless=True)
    device={k:v for k,v in p.devices['iPhone 15 Pro'].items()
            if k!='default_browser_type'}
    for name,width,height in MODES:
        args={**device,'viewport':{'width':width,'height':height}}
        context=browser.new_context(**args)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE,wait_until='domcontentloaded',timeout=25000)
        page.wait_for_function("() => !!window.UNOLuckViewport && !!window.UNOLuckLEDWheel",
                               timeout=16000)
        # The audio gate is tested separately. This is geometry-only QA.
        page.evaluate("""() => {
            const g=document.getElementById('game-shell');
            g.classList.remove('is-booting');g.removeAttribute('aria-hidden');
            document.getElementById('boot-overlay').hidden=true;
            window.UNOLuckViewport.refresh();
        }""")
        page.wait_for_timeout(220)
        data=inspect(page)
        print("IPHONE15PRO_LAYOUT",name,json.dumps(data,sort_keys=True),flush=True)
        assert data['cssDvh'],"Modern Safari/WebKit must support dynamic height"
        assert data['game']['top']>=-1,(name,data)
        assert data['game']['bottom']>=data['innerHeight']-2,(name,data)
        assert data['pseudoHeight']>=data['innerHeight']-2,(name,data)
        assert "lava-temple.webp" in data['htmlBackground'],(name,data)
        assert "lava-temple.webp" in data['pseudoBackground'],(name,data)
        assert data['safeBottom']>=3,(name,data)
        assert data['scrollWidth']<=width+2,(name,data)
        assert data['scrollHeight']<=data['innerHeight']+2,(name,data)
        assert data['caption']['bottom']<=data['game']['bottom']+2,(name,data)
        assert data['stage']['bottom']<=data['area']['bottom']+2,(name,'wheel artwork clipped',data)
        if width<height:
            assert 5<=float(data['wheelDrop'].replace('px',''))<=19,(name,data)
            assert data['stage']['top']>=data['area']['top']+4,(name,data)
            assert data['area']['bottom']>=data['innerHeight']-data['safeBottom']-2,(name,data)
        for item in data['controls']:
            assert item['left']>=-2 and item['right']<=width+2,(name,item)
            assert item['top']>=-2 and item['bottom']<=data['innerHeight']+2,(name,item)
        assert not errors,(name,errors)
        page.screenshot(path=str(OUT/f"iphone15pro-{name}.png"),full_page=True)
        context.close()
    browser.close()
print("PASS: WebKit iPhone15Pro portrait/Safari/PWA-size/landscape: lava background to bottom, full game viewport, safe action controls")
