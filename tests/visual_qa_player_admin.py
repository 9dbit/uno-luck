"""Player/admin separation, fixed Coin total and independently scrolling history."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('artifacts/uno-v1143-player-admin')
OUT.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8080'

with sync_playwright() as pw:
    for engine in ('chromium','webkit'):
        browser=getattr(pw,engine).launch(headless=True)
        context=browser.new_context(viewport={'width':393,'height':852})
        page=context.new_page()
        errors=[];writes=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:writes.append(r.url) if r.method not in ('GET','HEAD') else None)
        page.goto(URL,wait_until='domcontentloaded')
        page.locator('#boot-play').click(timeout=17000)
        page.locator('#game-shell').wait_for(state='visible',timeout=26000)
        assert not page.locator('.balance-readout small').is_visible()
        assert not page.locator('#wallet-rupiah').is_visible()
        assert page.locator('#wallet-balance').is_visible()
        page.locator('#profile-btn').click()
        assert page.locator('.menu-tile').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("aria-label"))') == ['Turnamen','Game Rules','Bet Setting','Profile','Sound On','Rank Info']
        page.get_by_role('button',name='Sound On',exact=True).click()
        assert page.evaluate("localStorage.getItem('uno_orbit_music')")=='off'
        assert page.evaluate("localStorage.getItem('uno_orbit_sfx')")=='off'
        assert not page.evaluate('UNOLuckSoundStudio.isMusicMediaPlaying()||UNOLuckSoundStudio.isMusicWebAudioPlaying()')
        page.get_by_role('button',name='Sound Off',exact=True).click()
        assert page.evaluate("localStorage.getItem('uno_orbit_music')")=='on'
        page.wait_for_function('() => UNOLuckSoundStudio.isMusicMediaPlaying()||UNOLuckSoundStudio.isMusicWebAudioPlaying()')
        page.get_by_role('button',name='Bet Setting',exact=True).click()
        assert page.locator('#modal-title').inner_text()=='Bet Setting'
        page.locator('#modal-close').click()

        page.locator('#profile-btn').click()
        page.get_by_role('button',name='Game Rules',exact=True).click()
        rules_text=page.locator('#modal-content').inner_text()
        assert '%' not in rules_text
        for rank,multiplier in enumerate([200,80,30,10,2],1):
            assert f'RANK {rank}' in rules_text
            assert f'{multiplier}× BET' in rules_text
        # The redesigned Rules guide puts the NO MATCH explanation in
        # Cara Main, not in the initial Rank & Bonus catalog.
        page.get_by_role('tab',name='Cara Main',exact=True).click()
        page.locator('#rg-panel-play summary').filter(has_text='Bagaimana jika tidak ada kombinasi?').click()
        assert 'NO MATCH' in page.locator('#rg-panel-play').inner_text()
        page.screenshot(path=str(OUT/f'{engine}-player-rules.png'))
        page.locator('#modal-close').click()
        page.locator('#turbo-btn').click()
        assert '%' not in page.locator('#game-shell').inner_text()
        page.locator('#turbo-btn').click()

        # Synthetic history affects only this isolated browser response.
        def history(route):
            response=route.fetch();data=response.json()
            data['recent']=[{'id':str(n),'stake':25,'payout':50,'delta':25,
                'combo':'COLOR_MATCH','created_at':1792454400-n*60} for n in range(8)]
            data['account']['daily_available']=False
            data['account']['refill_available']=True
            route.fulfill(response=response,json=data)
        page.route('**/api/orbit/state',history)
        for width,height in [(320,568),(393,852),(852,393),(1440,1000)]:
            page.set_viewport_size({'width':width,'height':height})
            page.locator('#wallet-open').click()
            page.locator('.coin-history-row').nth(7).wait_for()
            assert page.locator('#modal-content button').count()==0
            # Measure scroll stability after the actual opening animation settles.
            page.locator('.modal-card').evaluate('(e)=>Promise.all(e.getAnimations().map(a=>a.finished))')
            top=page.locator('#coin-total').bounding_box()['y']
            page.locator('.coin-history').evaluate('(e)=>e.scrollTop=e.scrollHeight')
            assert abs(page.locator('#coin-total').bounding_box()['y']-top)<1
            assert page.locator('.coin-history').evaluate('(e)=>e.scrollTop>0')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(OUT/f'{engine}-coin-{width}x{height}.png'))
            page.locator('#modal-close').click()
        page.locator('#gift-btn').click()
        assert page.get_by_role('button',name='Klaim +250 harian',exact=True).is_disabled()
        assert page.get_by_role('button',name='Refill gratis +1.000',exact=True).is_enabled()
        page.locator('#modal-close').click()
        assert not writes,writes

        page.goto(URL+'/admin',wait_until='domcontentloaded')
        assert page.locator('h1').inner_text()=='Admin'
        assert page.locator('script[src*="/orbit.js"]').count()==0
        page.locator('#admin-studio').click()
        assert page.locator('details.studio-cue').count()==12
        page.locator('#modal-close').click()
        page.locator('#admin-gallery').click()
        assert page.locator('#modal-content button').count()==5
        page.locator('#modal-content button').nth(4).click()
        page.locator('#celebration-overlay').wait_for(state='visible')
        assert page.locator('#celebration-overlay').get_attribute('data-rank')=='5'
        page.locator('#celebration-continue').click()
        page.screenshot(path=str(OUT/f'{engine}-admin.png'))
        assert not writes,writes
        assert not errors,errors
        context.close();browser.close()
        print('PASS:',engine,'player menu, Coin scrolling, gift isolation, admin controls')
