"""Spin v0.4 visual and frontend behavior contracts."""
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'app/static'
HTML=(BASE/'spin-index.html').read_text()
CSS=(BASE/'spin.css').read_text()
JS=(BASE/'spin.js').read_text()

def test_three_reel_slots_and_place_cta():
    assert HTML.count('class="slot-window"') == 3
    assert HTML.count('id="place-btn"') == 1
    assert 'SPIN YOUR CARDS' in HTML

def test_all_controls_in_dom():
    for key in ('wallet-open','place-btn','turbo-btn','auto-btn','stake-minus','stake-plus','gift-btn','menu-open','history-btn','music-btn','sfx-btn'):
        assert f'id="{key}"' in HTML

def test_single_viewport_and_safe_area():
    assert 'height:100dvh' in CSS
    assert 'overflow:hidden' in CSS
    assert 'env(safe-area-inset-bottom)' in CSS
    assert 'grid-template-rows:' in CSS
    assert '.win-burst' in CSS
    assert '.slot-window' in CSS
    assert 'card-reels' in HTML

def test_server_authoritative_and_no_client_generated_payout():
    assert "api('/place','POST'" in JS
    assert "api('/daily','POST'" in JS
    assert "api('/refill','POST'" in JS
    assert "result.combo==='COLOR_MATCH'" in JS
    assert 'paintSummary(result)' in JS
    assert 'winEffect(result.cards)' in JS
    assert 'autoRemaining=10' in JS
    assert '[10,25,50,100,250]' in JS

def test_slot_wins_not_mixed_into_rng():
    assert 'randomPreview()' in JS
    assert 'stopReel(index,finalCard,winning)' in JS
    assert "result.cards" in JS

def test_independent_audio_controls():
    assert 'ul_spin_music' in JS
    assert 'ul_spin_sfx' in JS
    assert 'startMusic()' in JS
    assert "sound('tick',index)" in JS
