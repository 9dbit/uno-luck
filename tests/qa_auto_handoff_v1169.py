"""DEV-03: actual AUTO click works after a paid manual SPIN; no real account writes.
All game and AUTO POSTs are fulfilled by deterministic browser fixtures.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL=os.getenv('UNO_QA_URL','http://127.0.0.1:8080')
OUT=Path('artifacts/uno-dev03-auto');OUT.mkdir(parents=True,exist_ok=True)
CASES=(('manual',393,852),('pending',320,700))

with sync_playwright() as pw:
    for engine in ('chromium','webkit'):
        browser=getattr(pw,engine).launch()
        for scenario,width,height in CASES:
            context=browser.new_context(viewport={'width':width,'height':height},
                                        has_touch=True,reduced_motion='reduce')
            state=context.request.get(URL+'/api/orbit/state').json()
            state['account']['balance']=1000
            state['round']=None
            state['recent']=[]
            holder={'session':None}
            requests=[];events=[];errors=[];seen={}

            def auto_state(route):
                route.fulfill(json={'session':holder['session']})

            def auto_start(route):
                info=route.request.post_data_json
                events.append('auto-start')
                if holder['session'] is not None:
                    route.fulfill(json={'session':holder['session'],'created':False,'resumed':True})
                    return
                holder['session']={'id':'isolated-auto-qa','stake':info['stake'],
                    'paid_rounds':info['paid_rounds'],'free_rounds':10,
                    'completed_rounds':0,'rounds_remaining':info['paid_rounds']+10,
                    'gift_ready':False,'gift_acknowledged':False,
                    'promotional_rewards':5,'promo_credited_coin':0}
                route.fulfill(json={'session':holder['session'],'created':True})

            def gift_continue(route):
                info=route.request.post_data_json
                assert info['session_id']==holder['session']['id']
                holder['session']['gift_acknowledged']=True
                holder['session']['gift_ready']=False
                events.append('gift-ack')
                route.fulfill(json={'session':holder['session'],'acknowledged':True})

            def pick(route):
                info=route.request.post_data_json
                requests.append(info)
                if info['request_id'] in seen:
                    old=seen[info['request_id']]
                    route.fulfill(json={**old,'replayed':True})
                    return
                session=holder['session'] if info.get('auto_session_id') else None
                if info.get('auto_session_id'):
                    assert session and session['id']==info['auto_session_id']
                current=state['round']
                if current is None:
                    cost=0 if session and session['completed_rounds']>=session['paid_rounds'] else info['stake']
                    state['account']['balance']-=cost
                    current={'id':'qa-round','stake':info['stake'],'charged_stake':cost,
                        'auto_session_id':session['id'] if session else None,
                        'free_spin':bool(session and cost==0),
                        'picked':0,'cards':[],'complete':False,'promo_coin':0,
                        'payout':None,'delta':None,'combo':None,'tier':None}
                current['picked']+=1
                current['cards'].append({'color':('red','blue','green')[current['picked']-1],
                                         'face':('1','4','8')[current['picked']-1]})
                if current['picked']==3:
                    current.update(complete=True,payout=0,combo='NO_MATCH',
                                   delta=-current['charged_stake'])
                    if session:
                        session['completed_rounds']+=1
                        session['rounds_remaining']=session['paid_rounds']+10-session['completed_rounds']
                        if session['completed_rounds']>=1 and not session['gift_acknowledged']:
                            session['gift_ready']=True
                        if not session['rounds_remaining']:
                            holder['session']=None
                    state['recent']=[dict(current)]
                state['round']=None if current['complete'] else current
                events.append(('auto-' if session else 'manual-')+str(current['picked']))
                result={'round':dict(current),'account':dict(state['account']),'replayed':False}
                seen[info['request_id']]=result
                route.fulfill(json=result)

            page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/api/orbit/state',lambda route:route.fulfill(json=state))
            page.route('**/api/auto/state',auto_state)
            page.route('**/api/auto/start',auto_start)
            page.route('**/api/auto/gift/continue',gift_continue)
            page.route('**/api/orbit/pick',pick)
            baseline=context.request.get(URL+'/api/sounds/manifest').json()
            page.goto(URL,wait_until='domcontentloaded')
            page.wait_for_function('() => !!account && !stateLoading',timeout=26000)
            page.locator('#boot-play').click(timeout=18000)
            page.locator('#game-shell').wait_for(state='visible',timeout=26000)
            page.evaluate("""() => {
                wheel.begin=()=>{}; wheel.settle=async()=>true; wheel.transferTo=async()=>{};
                if(window.UNOLuckCelebration)window.UNOLuckCelebration.present=async()=>true;
                if(window.UNOLuckPromoAudio)window.UNOLuckPromoAudio.playGift=async()=>true;
            }""")
            if scenario=='manual':
                page.locator('#spin-btn').click()
                page.wait_for_function('() => !isSpinning && currentRound?.picked===1',timeout=22000)
                assert page.evaluate('() => account.balance')==975
            else:
                page.evaluate("""() => localStorage.setItem('uno_orbit_pending_v08',
                    JSON.stringify({id:'pending-safe-retry-v1169',expected:1}))""")
            page.locator('#auto-btn').click()
            page.locator('[data-rounds="1"]').click()
            assert page.locator('#auto-start').inner_text()=='SELESAIKAN & MULAI AUTO'
            assert page.locator('#auto-start').is_enabled(), 'AUTO unexpectedly locked with enough Coin'
            assert '25 Coin' in page.locator('.auto-budget').inner_text()
            page.screenshot(path=str(OUT/f'{engine}-{scenario}-ready.png'))
            page.locator('#auto-start').click()
            page.wait_for_function('() => isAuto && !!activeAutoSession',timeout=26000)
            assert events.index('auto-start')>events.index('manual-3'),events
            assert requests[0]['auto_session_id'] is None
            assert all(r['auto_session_id'] is None for r in requests[:3])
            if scenario=='manual':
                # One already-paid manual round plus a separate AUTO paid round.
                assert len(requests)>=4
                page.locator('#auto-gift-banner').wait_for(state='visible',timeout=25000)
                page.wait_for_function("""() => {
                    const b=document.querySelector('.auto-gift-continue');
                    return b && !b.disabled && b.textContent.startsWith('CONTINUE');
                }""",timeout=16000)
                page.screenshot(path=str(OUT/f'{engine}-{scenario}-gift.png'))
                page.locator('.auto-gift-continue').click()
                page.wait_for_function('() => !isAuto && !isSpinning',timeout=100000)
                assert holder['session'] is None
                assert len(requests)==36,(engine,len(requests))
                assert all(r['auto_session_id']=='isolated-auto-qa' for r in requests[3:])
                assert state['account']['balance']==950
                assert events.count('gift-ack')==1
                assert page.evaluate('() => !pendingInfo() && !currentRound')
            else:
                # STOP must preserve a single resumable session without a double debit.
                # Overlay can appear after the visible check while Safari
                # is waiting to click AUTO. Retry STOP via its own overlay
                # control instead of timing out under the backdrop.
                if page.locator('#auto-gift-banner').is_visible():
                    page.locator('.auto-gift-stop').click()
                else:
                    try:
                        page.locator('#auto-btn').click(timeout=3500)
                    except Exception:
                        if not page.locator('#auto-gift-banner').is_visible():
                            raise
                        page.locator('.auto-gift-stop').click()
                page.wait_for_function('() => !isAuto && !isSpinning',timeout=26000)
                assert all(r['auto_session_id'] is None for r in requests[:3])
                assert requests[0]['request_id']=='pending-safe-retry-v1169'
                assert holder['session'] is not None
                assert state['account']['balance'] in (950,975)
                assert page.evaluate('() => !pendingInfo()')
            assert not errors,errors
            assert context.request.get(URL+'/api/sounds/manifest').json()==baseline
            print(engine,scenario,'PASS: AUTO enabled, manual handoff, pending ID safe, real clicks, original sound unchanged',flush=True)
            context.close()
        browser.close()
