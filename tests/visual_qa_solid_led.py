"""Computed-style regression for one opaque emissive card in every phase.

Read-only against staging: no gameplay or Sound Cloud mutation requests.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get('UNO_QA_URL', 'http://127.0.0.1:8080/')
OUT = Path('artifacts/uno-v13-solid-led')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    for engine in os.environ.get('UNO_QA_ENGINES', 'chromium,webkit').split(','):
        browser = getattr(p, engine).launch(headless=True)
        page = browser.new_page(viewport={'width':393,'height':852})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(BASE, wait_until='domcontentloaded')
        page.wait_for_function('() => !!window.UNOLuckLEDWheel')
        result = page.evaluate('''async () => {
          const host=document.createElement('div');
          host.className='wheel-led-ring';
          host.style.cssText='position:fixed;top:0;left:0;width:390px;height:390px;z-index:99999';
          document.body.append(host);
          const w=new UNOLuckLEDWheel(host,()=>document.createElement('div'));
          w.mount(Array.from({length:9},(_,i)=>({color:'red',face:String(i)})));
          const read=()=>w.nodes.map(n=>{
            const s=getComputedStyle(n.querySelector('.led-screen'));
            const b=n.getBoundingClientRect();
            return {opacity:s.opacity,filter:s.filter,background:s.backgroundColor,
              image:s.backgroundImage,shadow:s.boxShadow,face:n.dataset.face,
              rect:[b.x,b.y,b.width,b.height]};
          });
          const idle=read();
          w.begin({turbo:true});
          const spin=read();
          await w.settle({color:'yellow',face:'+2'},1);
          const locked=read();
          const finalIndex=Number(host.dataset.ledFrame);
          w.startIdle();
          const resumed=read();
          w.stopIdle();
          const center=w.nodes[4].dataset.face;
          window.__solidWheel=w;
          return {idle,spin,locked,resumed,finalIndex,center};
        }''')
        (OUT / f'{engine}-states.json').write_text(json.dumps(result, indent=2))
        page.screenshot(path=str(OUT / f'{engine}-idle-after-result.png'))
        for phase in ('idle','spin','locked','resumed'):
            cards = result[phase]
            bright = [i for i,c in enumerate(cards) if 'brightness(1.35)' in c['filter']]
            dim = [c for c in cards if 'brightness(0.37)' in c['filter']]
            assert len(bright)==1 and len(dim)==8, (engine,phase,bright,cards)
            assert all(c['opacity']=='1' for c in cards), (engine,phase,cards)
            assert all(c['background']!='rgba(0, 0, 0, 0)' or 'conic-gradient' in c['image'] for c in cards)
            assert all('255, 194, 46' not in c['shadow'] for c in dim), (engine,phase)
            assert [c['rect'] for c in cards]==[c['rect'] for c in result['idle']]
        assert result['finalIndex']==4 and result['center']=='+2', result
        assert not errors, errors
        browser.close()
        print(f'PASS {engine}: opaque cards, one bright/eight dark in idle/spin/lock/resume, fixed frames, server fifth card')
