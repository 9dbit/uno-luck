"""Visual rules, confirmed BET and bounded AUTO using browser-only server fixtures.

All /pick requests are fulfilled in the isolated browser; published audio and
live accounts are never written. Existing server/LED suites cover settlement
and animation separately; this suite exercises the actual player controls.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.orbit import classify_rank

URL='http://127.0.0.1:8080'
OUT=Path('artifacts/uno-v1146-player-panels')
OUT.mkdir(parents=True,exist_ok=True)
SIZES=[(320,568),(320,700),(393,659),(393,852),(390,844),(430,932),(852,393),(1440,1000)]

with sync_playwright() as pw:
    for engine in ('chromium','webkit'):
        browser=getattr(pw,engine).launch()
        context=browser.new_context(viewport={'width':393,'height':852},reduced_motion='reduce')
        baseline=context.request.get(URL+'/api/sounds/manifest').json()
        state=context.request.get(URL+'/api/orbit/state').json()
        state.update(round=None,recent=[])
        state['account']['balance']=1000
        page=context.new_page();errors=[];requests=[];held=[]
        mode={'value':'normal'}
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/orbit/state',lambda r:r.fulfill(json=state))

        auto_holder={'session':None}
        def auto_state(route):
            route.fulfill(json={'session':auto_holder['session']})
        def auto_start(route):
            request=route.request.post_data_json
            if auto_holder['session'] is not None:
                route.fulfill(json={'session':auto_holder['session'], 'created':False, 'resumed':True})
                return
            total=request['paid_rounds']+10
            session={'id':'fixture-auto-session', 'stake':request['stake'],
                'paid_rounds':request['paid_rounds'], 'free_rounds':10,
                'completed_rounds':0, 'rounds_remaining':total, 'free_remaining':10,
                'promotional_rewards':5, 'promo_credited_coin':0}
            auto_holder['session']=session
            route.fulfill(json={'session':session, 'created':True,
                'gift':{'free_spins':10,'voice':'Free Spiinnn!'}})
        page.route('**/api/auto/state',auto_state)
        page.route('**/api/auto/start',auto_start)

        def respond(route):
            data=route.request.post_data_json
            current=state['round']
            session=auto_holder['session'] if data.get('auto_session_id') else None
            if not current:
                charge=0 if session and session['completed_rounds']>=session['paid_rounds'] else data['stake']
                state['account']['balance']-=charge
                current={'id':'fixture-round','stake':data['stake'],'charged_stake':charge,
                         'auto_session_id':session['id'] if session else None,
                         'free_spin':bool(session and charge==0),
                         'picked':0,'cards':[], 'promo_coin':0,
                         'complete':False,'combo':None,'tier':None,'payout':None,'delta':None}
            current['picked']+=1
            current['cards']=[{'color':c,'face':str(i+1)}
                for i,c in enumerate(('red','blue','green')[:current['picked']])]
            if current['picked']==3:
                current.update(complete=True,combo='NO_MATCH',payout=0,
                               delta=-current['charged_stake'])
                if session is not None:
                    session['completed_rounds']+=1
                    session['rounds_remaining']=session['paid_rounds']+10-session['completed_rounds']
                    session['free_remaining']=max(0,session['paid_rounds']+10-session['completed_rounds'])
                    if not session['rounds_remaining']:
                        auto_holder['session']=None
            state['round']=None if current['complete'] else current
            route.fulfill(json={'account':state['account'],'round':current})

        def pick(route):
            requests.append(route.request.post_data_json)
            if mode['value']=='hold':held.append(route)
            elif mode['value']=='fail':route.abort()
            else:respond(route)
        page.route('**/api/orbit/pick',pick)
        page.goto(URL,wait_until='domcontentloaded')
        page.locator('#boot-play').click(timeout=17000)
        page.locator('#game-shell').wait_for(state='visible',timeout=26000)

        def menu(name):
            page.locator('#profile-btn').click()
            page.get_by_role('button',name=name,exact=True).click()
        def close():page.locator('#modal-close').click()
        def bounds():
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert page.locator('#modal-content').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
            box=page.locator('#modal-close').bounding_box()
            assert box['y']>=0 and box['y']+box['height']<=page.viewport_size['height']
            if page.locator('.panel-primary').count():
                action=page.locator('.panel-primary').bounding_box()
                assert action['y']>=0 and action['y']+action['height']<=page.viewport_size['height']
                top=action['y']
                page.locator('#modal-content').evaluate('(e)=>e.scrollTop=e.scrollHeight')
                assert abs(page.locator('.panel-primary').bounding_box()['y']-top)<1
                page.locator('#modal-content').evaluate('(e)=>e.scrollTop=0')
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            menu('Game Rules')
            assert page.locator('.rules-tier').count()==5
            assert page.locator('.rules-hand .card3d').count()==15
            for rank in range(1,6):
                cards=page.locator(f'.rules-tier[data-rank="{rank}"] .card3d').evaluate_all('(nodes)=>nodes.map(n=>({color:n.dataset.color,face:n.dataset.face}))')
                assert classify_rank(cards)==rank
            assert page.locator('.rules-multiplier').all_text_contents()==['200× BET','80× BET','30× BET','10× BET','2× BET']
            assert '%' not in page.locator('#modal-content').text_content()
            top=page.locator('#modal-close').bounding_box()['y']
            page.locator('#modal-content').evaluate('(e)=>e.scrollTop=e.scrollHeight')
            assert abs(page.locator('#modal-close').bounding_box()['y']-top)<1
            page.locator('#modal-content details summary').first.click();bounds()
            page.locator('#modal-content').evaluate('(e)=>e.scrollTop=0')
            page.screenshot(path=str(OUT/f'{engine}-rules-{width}x{height}.png'));close()
            menu('Bet Setting');bounds()
            assert page.locator('[data-bet]').count()==5
            page.screenshot(path=str(OUT/f'{engine}-bet-{width}x{height}.png'));close()
            page.locator('#auto-btn').click();bounds()
            page.locator('[data-rounds="3"]').click()
            assert page.locator('.auto-budget .coin-value-text').nth(1).inner_text()=='75 Coin'
            page.screenshot(path=str(OUT/f'{engine}-auto-{width}x{height}.png'));close()
        assert requests==[],requests
        page.set_viewport_size({'width':393,'height':852})
        menu('Bet Setting');page.locator('[data-bet="250"]').click();close()
        assert page.locator('#last-stake').inner_text()=='25'  # Cancel discards draft.
        menu('Bet Setting');page.locator('[data-bet="250"]').click()
        page.get_by_role('button',name='GUNAKAN BET',exact=True).click()
        assert page.locator('#last-stake').inner_text()=='250'
        page.locator('#auto-btn').click();page.locator('[data-rounds="10"]').click()
        assert page.locator('#auto-start').is_disabled()
        assert page.locator('.auto-budget .coin-value-text').nth(1).inner_text()=='2.500 Coin';close()
        menu('Bet Setting');page.locator('[data-bet="25"]').click()
        page.get_by_role('button',name='GUNAKAN BET',exact=True).click()
        # UI fixtures verify the new contract: paid rounds, ten free rounds,
        # STOP and persistent resume, and deferred next BET. Backend tests
        # independently audit five promo grants and replay-safe settlement.
        page.evaluate('''() => {wheel.begin=()=>{};wheel.settle=async()=>true;
                                wheel.transferTo=async()=>{};}''')
        first=len(requests)
        page.locator('#auto-btn').click()
        page.locator('[data-rounds="1"]').click()
        page.locator('#auto-start').click()
        page.wait_for_function('() => isAuto',timeout=8000)
        page.wait_for_function('() => !isAuto&&!isSpinning',timeout=45000)
        batch=requests[first:]
        assert len(batch)==33,(engine,'paid + 10 free rounds',len(batch))
        assert all(item['stake']==25 for item in batch)
        assert all(item.get('auto_session_id') for item in batch)
        assert auto_holder['session'] is None

        mode['value']='hold';start=len(requests)
        page.locator('#auto-btn').click()
        page.locator('[data-rounds="3"]').click()
        page.locator('#auto-start').click()
        page.wait_for_function('() => isSpinning')
        page.wait_for_timeout(100)
        assert len(held)==1
        page.locator('#auto-btn').click()  # STOP only after current SPIN
        respond(held.pop())
        page.wait_for_function('() => !isAuto&&!isSpinning',timeout=12000)
        assert auto_holder['session'] is not None
        assert len(requests)==start+1

        menu('Bet Setting')
        page.locator('[data-bet="100"]').click()
        page.get_by_role('button',name='GUNAKAN BET',exact=True).click()
        assert page.evaluate('() => currentRound.stake')==25
        mode['value']='normal'
        page.locator('#auto-btn').click()
        assert page.locator('#auto-start').inner_text()=='LANJUTKAN AUTO'
        page.locator('#auto-start').click()
        page.wait_for_function('() => isAuto',timeout=8000)
        page.wait_for_function('() => !isAuto&&!isSpinning',timeout=55000)
        resumed=requests[start:]
        assert len(resumed)==39,(engine,'3 paid + 10 free rounds',len(resumed))
        assert all(item['stake']==25 for item in resumed)
        assert auto_holder['session'] is None
        assert page.evaluate('() => STAKES[stakeIndex]')==100
        assert len({item['request_id'] for item in requests})==len(requests)

        start=len(requests)
        page.locator('#spin-btn').click()
        page.wait_for_function('() => !isSpinning&&currentRound?.picked===1')
        assert requests[-1]['stake']==100
        assert context.request.get(URL+'/api/sounds/manifest').json()==baseline
        assert not errors,errors
        context.close();browser.close()
        print('PASS:',engine,'responsive rules/BET, ten free spins, STOP+RESUME, queued BET, unchanged sound')
