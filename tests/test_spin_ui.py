"""Ensure the only landing page is Spin and its controls are in normal flow."""
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'app/static'
HTML=(BASE/'spin-index.html').read_text()
CSS=(BASE/'spin.css').read_text()
JS=(BASE/'spin.js').read_text()

def test_three_spin_cards_and_one_primary_place():
    assert HTML.count('class="metal-card card-back"')==3
    assert HTML.count('id="place-btn"')==1
    assert 'SPIN YOUR CARDS' in HTML

def test_ui_buttons_exist_for_spin_auto_turbo_wallet():
    for name in ('wallet-open','place-btn','turbo-btn','auto-btn','stake-minus','stake-plus','gift-btn','menu-open','history-btn','sound-btn'):
        assert 'id="'+name+'"' in HTML

def test_responsive_safe_area_no_absolute_controls():
    assert 'env(safe-area-inset-bottom)' in CSS
    assert 'min-height:100svh' in CSS
    assert '.main-actions{position:relative;display:grid' in CSS
    assert '.spin-summary{position:relative;display:grid' in CSS

def test_browser_controls_are_wired_and_server_is_authoritative():
    assert "api('/place','POST'" in JS
    assert "api('/daily','POST'" in JS
    assert "api('/refill','POST'" in JS
    assert 'autoRemaining=10' in JS
    assert "[10,25,50,100,250]" in JS
