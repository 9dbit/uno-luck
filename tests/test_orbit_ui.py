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
    assert 'layoutRing' in JS and 'animateRing' in JS
    assert 'AudioContext' in JS and 'unlockAudio' in JS
    assert 'navigator.vibrate' in JS


def test_bundled_visual_assets():
    for name in ('orbit-logo.webp','boot-softtech.webp','boot-uno-banner.webp'):
        assert (P/name).is_file()


def test_approved_motion_and_metal_panel_placement():
    assert '/assets/art/motion.css?v=7' in HTML
    assert '/assets/art/motion.js?v=7' in HTML
    assert HTML.index('id="last-stake"') > HTML.index('id="spin-btn"')
    assert '/assets/art/v1/dragon-head-fx.webp' in HTML
    assert 'window.UNOLuckMotion?.result(last)' in JS
    assert 'window.UNOLuckMotion?.beginSpin()' in JS
