"""Actual menu clicks in isolated browsers. Guide interactions are read-only."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL=os.getenv('UNO_QA_URL','http://127.0.0.1:8080')
OUT=Path('artifacts/uno-dev02-rules');OUT.mkdir(parents=True,exist_ok=True)
SIZES=[('small',320,568),('iphone15pro',393,852),('safari-short',393,659),
       ('landscape',852,393),('desktop',1440,1000)]
report=[]
with sync_playwright() as pw:
    for engine in ('chromium','webkit'):
        browser=getattr(pw,engine).launch()
        context=browser.new_context(viewport={'width':393,'height':852},reduced_motion='reduce')
        page=context.new_page();errors=[];writes=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.on('request',lambda req:writes.append(req.url) if req.method not in ('GET','HEAD') else None)
        baseline=context.request.get(URL+'/api/sounds/manifest').json()
        page.goto(URL,wait_until='domcontentloaded')
        page.wait_for_function('() => !!window.UNOLuckRulesGuide && !!account && !stateLoading',timeout=25000)
        page.locator('#boot-play').click(timeout=17000)
        page.locator('#game-shell').wait_for(state='visible',timeout=26000)
        before=page.evaluate('() => ({stake:stakeIndex,balance:account.balance})')
        for label,width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            page.locator('#profile-btn').click()
            page.get_by_role('button',name='Game Rules',exact=True).click()
            page.locator('#rg-panel-catalog').wait_for(state='visible')
            page.locator('.modal-card').evaluate('(e)=>Promise.all(e.getAnimations().map(a=>a.finished))')
            assert page.locator('.rg-entry').count()==15
            assert page.locator('.rules-tier').count()==5
            assert page.locator('.award-tier').count()==10
            assert page.locator('.rg-hand .card3d').count()==45
            assert page.locator('.rg-entry').evaluate_all('(nodes)=>nodes.map(e=>Number(e.dataset.order))')==list(range(1,16))
            assert 'Belum aktif' in page.locator('[data-award="COLOR_PAIR"] .rg-state').inner_text()
            assert page.locator('[data-award="PAIR_PRODUCT_DRAW_TRIPLE"] .rg-multiplier').inner_text()=='8\u00d7 BET'
            assert page.locator('[data-award="PAIR_SUM_DRAW_TRIPLE"] .rg-multiplier').inner_text()=='6\u00d7 BET'
            page.locator('#rg-example-stake').select_option('25')
            triple=page.locator('[data-award="PAIR_PRODUCT_NUMBER_TRIPLE"]')
            assert 'WIN 500' in triple.locator('.rg-example').inner_text()
            assert 'NET +475' in triple.locator('.rg-example').inner_text()
            page.locator('#rg-example-stake').select_option('10')
            assert 'WIN 200' in triple.locator('.rg-example').inner_text()
            assert page.evaluate('() => ({stake:stakeIndex,balance:account.balance})')==before
            page.get_by_role('button',name='Rank utama',exact=True).click()
            assert page.locator('.rg-entry:visible').count()==5
            page.get_by_role('button',name='Bonus',exact=True).click()
            assert page.locator('.rg-entry:visible').count()==10
            page.get_by_role('button',name='Semua',exact=True).click()
            page.locator('#rg-example-stake').select_option('25')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert page.locator('#modal-content').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
            close=page.locator('#modal-close').bounding_box()
            assert close and close['y']>=0 and close['y']+close['height']<=height
            assert page.locator('.rg-hand .card-back:visible').count()==0
            page.locator('#modal-content').evaluate('(e)=>e.scrollTop=0')
            page.screenshot(path=str(OUT/f'{engine}-{label}-rules.png'))
            triple.scroll_into_view_if_needed()
            triple.locator('summary').click()
            page.screenshot(path=str(OUT/f'{engine}-{label}-calculation.png'))
            page.get_by_role('tab',name='Cara Main',exact=True).click()
            assert page.locator('#rg-panel-play').is_visible()
            assert not page.locator('#rg-panel-catalog').is_visible()
            page.screenshot(path=str(OUT/f'{engine}-{label}-how-to.png'))
            page.get_by_role('tab',name='Cara Main',exact=True).focus()
            page.keyboard.press('ArrowRight')
            assert page.get_by_role('tab',name='Ketentuan',exact=True).get_attribute('aria-selected')=='true'
            page.screenshot(path=str(OUT/f'{engine}-{label}-terms.png'))
            page.locator('#modal-back').click()
            page.get_by_role('button',name='Rank Info',exact=True).click()
            assert page.locator('#rg-panel-catalog').is_visible()
            assert page.locator('.rg-entry').count()==15
            page.locator('#modal-close').click()
            report.append({'engine':engine,'viewport':label,'status':'PASS','patterns':15})
            print(engine,label,'PASS: 15 ordered patterns, honest inactive lanes, responsive examples, no stake/wallet writes',flush=True)
        assert not errors,errors
        assert not writes,writes
        assert context.request.get(URL+'/api/sounds/manifest').json()==baseline
        context.close();browser.close()
(OUT/'report.json').write_text(json.dumps(report,indent=2))
