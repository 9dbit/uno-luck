from pathlib import Path
P=Path(__file__).resolve().parents[1]/'app'/'static'
HTML=(P/'orbit-index.html').read_text()
CSS=(P/'orbit.css').read_text()
JS=(P/'orbit.js').read_text()

def test_design_lock():
    assert '/assets/art/v1/logo.webp' in HTML
    assert HTML.count('uno-logo')==1
    assert 'COLOR MATCH!' in HTML
    assert 'result-0' in HTML and 'result-1' in HTML and 'result-2' in HTML
    assert 'orbit-ring' in HTML and 'spin-btn' in HTML
    assert 'PLACE' not in HTML


def test_no_vertical_scroll_design_constraints():
    assert 'height:100dvh' in CSS and 'overflow:hidden' in CSS
    assert 'safe-area-inset' in CSS
    assert 'grid-template-rows:' in CSS
    assert 'boot-loading-track' in CSS


def test_three_spin_card_binding_and_audio():
    assert "api('/pick','POST'" in JS
    assert "currentRound?.picked" in JS
    assert 'layoutRing' in JS and 'wheel.settle(card,phase)' in JS
    assert 'AudioContext' in JS and 'unlockAudio' in JS
    assert 'navigator.vibrate' in JS


def test_bundled_visual_assets():
    for name in ('orbit-logo.webp','boot-softtech.webp','boot-uno-banner.webp'):
        assert (P/name).is_file()


def test_fixed_nine_led_placeholders_and_approved_result_layout():
    engine = (P/'art'/'ledwheel.js').read_text()
    style = (P/'art'/'ledwheel.css').read_text()
    assert HTML.count('id="orbit-ring"') == 1
    assert HTML.count('class="wheel-area"') == 1
    assert HTML.count('id="spin-btn"') == 1
    assert HTML.index('id="last-stake"') < HTML.index('id="spin-btn"')
    assert 'window.UNOLuckLEDWheel' in engine
    assert 'GEOMETRY = [' in engine
    assert 'this.displays[i]=this.displays[i-1]' in engine
    assert 'requestAnimationFrame(tick)' in engine
    assert 'flyTo' not in engine and 'transferTo(target)' in engine
    assert 'wheel-static-v09' in HTML
    assert 'wheel-dragon.webp' in HTML
    assert 'object-fit:contain!important' in style
    assert 'led-screen' in style
    for name in ('wheel-dragon','card-placeholder','card-red','card-blue','card-green','card-yellow','card-wild','card-back'):
        assert (P/'art'/'v2'/(name+'.webp')).is_file()


def test_auditable_authoritative_payout_only():
    motion=(P/'art'/'ledwheel.js').read_text()
    assert "api('/pick','POST'" in JS
    assert 'confirmed.round.cards[phase-1]' in JS
    assert 'await wheel.settle(card,phase)' in JS
    assert 'await wheel.transferTo(' in JS
    assert 'pendingKey' in JS
    assert 'api(' not in motion and 'request_id' not in motion
    assert 'window.UNOLuckWheel360' not in JS
