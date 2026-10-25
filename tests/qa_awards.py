"""DOM-only iPhone awards QA. Fixtures never post game or sound changes."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL=os.getenv('UNO_QA_URL','http://127.0.0.1:8080')
OUT=Path('artifacts/uno-v1167-awards');OUT.mkdir(parents=True,exist_ok=True)
LAYOUTS=[('iphone',393,852),('safari-short',393,659),('small',320,568),('landscape',852,393)]
with sync_playwright() as p:
    for engine in ('chromium','webkit'):
        browser=getattr(p,engine).launch()
        for label,width,height in LAYOUTS:
            context=browser.new_context(viewport={'width':width,'height':height},
                is_mobile=width<height,has_touch=True,reduced_motion='no-preference')
            page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            baseline=context.request.get(URL+'/api/sounds/manifest').json()
            page.goto(URL,wait_until='domcontentloaded')
            page.wait_for_function("() => !!window.UNOLuckAwards && !!account && !stateLoading",timeout=20000)
            page.evaluate("""() => {
                document.getElementById('game-shell').classList.remove('is-booting');
                document.getElementById('game-shell').removeAttribute('aria-hidden');
                document.getElementById('boot-overlay').hidden=true;
                window.__awardRound={complete:true,picked:3,stake:25,charged_stake:25,
                    payout:50,promo_coin:0,delta:25,combo:'COLOR_PAIR',
                    bonus:{kind:'COLOR_PAIR',multiplier:2},
                    cards:[{color:'yellow',face:'1'},{color:'blue',face:'7'},{color:'yellow',face:'9'}],
                    award:{id:'COLOR_PAIR',winning_indices:[0,2],color_indices:[0,2]}};
                paintRound(window.__awardRound);
                say('ZONK · Tidak ada kemenangan permainan.');
            }""")
            page.wait_for_function("""() => [...document.querySelectorAll('.wheel-stage img,.result-area img')]
                .every(img=>img.complete&&img.naturalWidth>0)""",timeout=15000)
            page.wait_for_timeout(900)
            assert page.locator('#spin-caption').text_content()==''
            assert not page.locator('.balance-readout>small').is_visible()
            assert not page.locator('#wallet-rupiah').is_visible()
            assert page.locator('#wallet-balance').is_visible()
            assert page.locator('.result-area .award-winning').count()==2
            assert page.locator('.result-area .award-edge-runner').count()==2
            assert page.locator('.result-area .award-muted').count()==1
            assert page.locator('.result-area .card-back:visible').count()==0
            assert page.locator('.result-area .card-front .number').all_text_contents()==['1','7','9']
            assert page.locator('.result-area .card-front .number:visible').count()==3
            metrics=page.evaluate("""() => {
                const rect=q=>{const r=document.querySelector(q).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};
                return {area:rect('.wheel-area'),stage:rect('.wheel-stage'),
                    viewport:{width:innerWidth,height:innerHeight},
                    animation:getComputedStyle(document.querySelector('.award-edge-runner')).animationName};
            }""")
            assert metrics['animation']=='unoGoldEdge',metrics
            assert metrics['stage']['bottom']<=metrics['area']['bottom']+2,metrics
            assert metrics['stage']['left']>=-2 and metrics['stage']['right']<=width+2,metrics
            if width<height:
                assert metrics['stage']['width']>=min(metrics['area']['height']-11,metrics['area']['width']-6),metrics
            page.screenshot(path=str(OUT/f'{engine}-{label}-gold.png'),full_page=True)
            # Exercise actual user clicks, not just calling the global menu
            # function: the profile/back buttons must use the enhanced handler.
            page.locator('#profile-btn').click()
            page.get_by_role('button',name='Rank Info',exact=True).click()
            assert page.locator('.rules-paytable [data-award]').count()==15
            assert page.locator('.award-tier[data-award="COLOR_PAIR"]').count()==1
            page.locator('.modal-card').wait_for(state='visible')
            page.wait_for_timeout(500)
            page.wait_for_function("""() => [...document.querySelectorAll('#modal img')]
                .every(img=>img.complete&&img.naturalWidth>0)""",timeout=15000)
            assert page.locator('#modal-title').is_visible()
            page.screenshot(path=str(OUT/f'{engine}-{label}-catalog.png'),full_page=True)
            page.locator('.award-tier[data-award="COLOR_PAIR"]').scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            page.screenshot(path=str(OUT/f'{engine}-{label}-twin-color.png'),full_page=True)
            page.locator('#modal-back').click()
            assert page.get_by_role('button',name='Rank Info',exact=True).count()==1
            page.locator('#modal-close').click()
            page.evaluate("""() => {paintRound({...window.__awardRound,
                combo:'NO_MATCH',payout:0,promo_coin:100,regular_payout:0,award:null});}""")
            assert page.locator('.result-area .award-edge').count()==0
            page.evaluate('() => paintRound(window.__awardRound)')
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.award-edge-runner').first.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
            page.evaluate("() => say('Koneksi terputus. Coba lagi.')")
            assert page.locator('#spin-caption.is-actionable').is_visible()
            page.evaluate('() => {say("");paintRound(null);} ')
            assert page.locator('.result-area .award-edge').count()==0
            assert not errors,errors
            assert context.request.get(URL+'/api/sounds/manifest').json()==baseline
            print(engine,label,'PASS: number-only balance, no loss caption, larger intact SPIN, actual Rank Info clicks, 15 catalog entries, front-only gold edges, no false promo win',flush=True)
            context.close()
        browser.close()
