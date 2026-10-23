from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app'/'static'
HTML=(STATIC/'orbit-index.html').read_text()
ORBIT=(STATIC/'orbit.js').read_text()
WHEEL=(STATIC/'art'/'ledwheel.js').read_text()
CSS=(STATIC/'art'/'ledwheel.css').read_text()
SERVER=(ROOT/'app'/'orbit.py').read_text()


def test_single_approved_static_wheel_with_nine_led_placeholders():
    assert HTML.count('id="orbit-ring"')==1
    assert HTML.count('id="spin-btn"')==1
    assert HTML.count('wheel-dragon.webp')==1
    assert 'wheel360.js?v=8' not in HTML
    assert '/assets/art/ledwheel.js?v=1139' in HTML
    assert '/assets/art/ledwheel.css?v=10' in HTML
    assert 'const RING_COUNT = 9' in ORBIT
    assert 'GEOMETRY = [' in WHEEL
    assert 'this.count=count;' in WHEEL
    assert 'this.illuminate((this.chaseIndex+1)%this.count)' in WHEEL
    assert "node.querySelector('.led-symbol').textContent='1'" not in WHEEL
    assert "this.displays=previewPack()" in WHEEL
    assert "this.advanceFaces(index)" in WHEEL
    assert "const WILDS = ['WILD','+4'];" in WHEEL
    assert "const ACTIONS = ['SKIP','REVERSE','+2'];" in WHEEL
    assert 'this.displays[track[j]]=this.displays[track[j-1]]' in WHEEL
    assert 'this.host.dataset.faceFrame=String(this.faceSteps)' in WHEEL
    assert 'Math.sin(' not in WHEEL and 'Math.cos(' not in WHEEL
    assert 'animation:ambientMove' in CSS
    assert 'object-fit:contain!important' in CSS


def test_betting_above_wheel_and_result_cards_are_three_separate_cells():
    assert HTML.index('id="result-2"') < HTML.index('id="last-stake"')
    assert HTML.index('id="last-delta"') < HTML.index('class="wheel-area"')
    assert HTML.count('class="result-cell"') == 3
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))' in CSS
    assert 'height:100dvh' in CSS
    assert 'env(safe-area-inset' in (STATIC/'orbit.css').read_text()


def test_server_selected_card_moves_from_led_pointer_to_next_result():
    assert "confirmed=await api('/pick','POST'" in ORBIT
    assert "const card=confirmed.round.cards[phase-1]" in ORBIT
    assert 'await wheel.settle(card,phase)' in ORBIT
    assert "await wheel.transferTo($('result-'+(phase-1)))" in ORBIT
    assert 'paintRound(confirmed.round,false,true)' in ORBIT
    assert ORBIT.index('await wheel.transferTo')<ORBIT.index('paintRound(confirmed.round,false,true)')
    assert 'if(this.chaseIndex!==PICKS)' in WHEEL
    assert 'this.deceleration={total:minimumSteps+extra,remaining:minimumSteps+extra}' in WHEEL
    assert "if(!this.ready?.card)throw Error" in WHEEL
    assert 'this.displays[PICKS]={...this.ready.card}' in WHEEL
    assert 'this.lastSelected={...this.ready.card}' in WHEEL
    assert 'this.host.replaceChildren(...this.nodes)' in WHEEL


def test_ledger_probability_and_request_deduplication_unchanged():
    assert 'secrets.randbelow(100) < WIN_PERCENT' in SERVER
    assert 'def choose_cards()' in SERVER
    assert "db.execute('SELECT round_id,selected_count FROM orbit_requests" in SERVER
    assert 'charged_stake = payload.stake' in SERVER
    assert "new_balance=acct['balance']-charged_stake" in SERVER
    assert "autoplay.round_terms(promotion)" in SERVER
    assert "multiplier * row['stake']" in SERVER and 'CELEBRATIONS' in SERVER
    assert 'fetch(' not in WHEEL
