"""UNO LUCK: iPhone HUD / continuous Soft Tech splash / smooth LED regression.

Ephemeral Playwright browser against the GitHub Actions local app. Read-only
visual inspection, with no POST to game API or Sound Cloud mutation endpoints.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.environ.get("UNO_QA_URL","http://127.0.0.1:8080/")
OUT=Path("artifacts/uno-v12-performance-hud")
OUT.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
    page=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1)
    errors=[]
    page.on("pageerror",lambda exc:errors.append(str(exc)))
    page.goto(BASE,wait_until="domcontentloaded")
    splash=page.locator("#boot-softtech-img")
    page.locator("#boot-softtech").wait_for(state="visible",timeout=15000)
    def zoom_state():
        return splash.evaluate("""img => {
          const css=getComputedStyle(img),matrix=new DOMMatrixReadOnly(css.transform);
          return {name:css.animationName,count:css.animationIterationCount,
                  scale:matrix.a,visible:!img.hidden,button:!!document.getElementById('boot-play')};
        }""")
    before=zoom_state()
    page.wait_for_timeout(820)
    during=zoom_state()
    assert before["visible"] and during["visible"] and before["button"]
    assert before["name"]=="unoSoftTechIdleZoom" and during["name"]==before["name"],(before,during)
    assert before["count"]=="infinite" and during["count"]=="infinite",(before,during)
    assert abs(during["scale"]-before["scale"])>=.04,(before,during)
    page.screenshot(path=str(OUT/"splash-loop-390x844.png"))
    assert page.locator("#game-shell").is_hidden(),"Must wait for the PLAY gesture"
    page.locator("#boot-play").click(timeout=24000)
    page.wait_for_function(
        "()=>document.getElementById('boot-softtech').classList.contains('is-zooming')",
        timeout=12000)
    outro=zoom_state()
    assert outro["name"]=="unoSoftTechZoom" and outro["count"]=="1",outro
    page.locator("#game-shell").wait_for(state="visible",timeout=29000)

    layouts=[(320,700),(390,844),(430,932),(844,390)]
    for width,height in layouts:
        page.set_viewport_size({"width":width,"height":height})
        page.wait_for_timeout(170)
        view=page.evaluate("""() => {
          const bar=document.querySelector('.game-shell > .result-bar');
          const rect=e=>{const b=e.getBoundingClientRect();
            return {x:b.x,y:b.y,left:b.left,right:b.right,
                    top:b.top,bottom:b.bottom,width:b.width,height:b.height,
                    centerY:(b.top+b.bottom)/2}};
          return {
            bar:rect(bar),
            items:Array.from(bar.children).map(cell=>({
              parent:rect(cell),label:rect(cell.querySelector('small')),
              amount:rect(cell.querySelector('strong')),
              display:getComputedStyle(cell).display,
              direction:getComputedStyle(cell).flexDirection,
              whiteSpace:getComputedStyle(cell).whiteSpace,
              labelText:cell.querySelector('small').textContent
            })),
            overflow:document.documentElement.scrollWidth>innerWidth+2
          };
        }""")
        assert not view["overflow"],(width,height,view)
        assert len(view["items"])==3
        assert [item["labelText"] for item in view["items"]]==["BET","PAYOUT","WIN"]
        for item in view["items"]:
            assert item["display"]=="flex" and item["direction"]=="row",(width,height,item)
            assert item["whiteSpace"]=="nowrap",(width,height,item)
            assert abs(item["label"]["centerY"]-item["amount"]["centerY"])<=3.5,(width,height,item)
            assert item["label"]["right"]<=item["amount"]["left"]+1.5,(width,height,item)
            assert item["label"]["left"]>=item["parent"]["left"]-1.5,(width,height,item)
            assert item["amount"]["right"]<=item["parent"]["right"]+1.5,(width,height,item)
        page.screenshot(path=str(OUT/f"hud-{width}x{height}.png"))

    # No DOM queries needed for the 9 symbols on every animation tick.
    metrics=page.evaluate("""async () => {
      const host=document.createElement('div');
      host.className='wheel-led-ring';
      host.style.cssText='position:fixed;width:320px;height:320px;top:0;left:0';
      document.body.append(host);
      const w=new UNOLuckLEDWheel(host,()=>document.createElement('div'),9);
      w.mount(Array.from({length:9},(_,i)=>({color:'red',face:String(i)})));
      const before=w.nodes.map(n=>{const r=n.getBoundingClientRect();
        return [r.x,r.y,r.width,r.height];});
      let queries=0;
      const orig=Element.prototype.querySelector;
      Element.prototype.querySelector=function(selector){
        if(selector==='.led-symbol' && this.classList?.contains('led-slot'))queries++;
        return orig.call(this,selector);
      };
      let accepted=false,draws=0,fromServer=null,after=null;
      try{
        w.begin({turbo:false});
        accepted=await Promise.race([w.settle({color:'yellow',face:'7'},1),
                       new Promise(resolve=>setTimeout(()=>resolve(false),7000))]);
        draws=w.ledDraws;
        fromServer=w.nodes[4].dataset.face;
        after=w.nodes.map(n=>{const r=n.getBoundingClientRect();
          return [r.x,r.y,r.width,r.height];});
      }finally{
        Element.prototype.querySelector=orig;
        w.cancel();host.remove();
      }
      return {accepted,draws,queries,fromServer,geometryFixed:
              JSON.stringify(before)===JSON.stringify(after)};
    }""")
    assert metrics["accepted"] is True,metrics
    assert metrics["draws"]>=15,metrics
    assert metrics["queries"]==0,("Glyph DOM must be cached before animation",metrics)
    assert metrics["fromServer"]=="7" and metrics["geometryFixed"],metrics
    assert not errors,errors
    browser.close()
print("PASS: looping Soft Tech before PLAY, inline HUD at 320/390/430/landscape, zero hot-loop glyph selectors, server fifth-card lock")
