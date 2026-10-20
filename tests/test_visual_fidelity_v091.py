"""Regression contracts for the approved standalone UNO LUCK visual fidelity pass."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app'/'static'
HTML=(STATIC/'orbit-index.html').read_text()
JS=(STATIC/'orbit.js').read_text()
STYLE=(STATIC/'art'/'fidelity.css').read_text()
LED=(STATIC/'art'/'ledwheel.js').read_text()


def test_approved_master_assets_unchanged_and_one_logo():
    assert HTML.count('class="uno-logo"')==1
    assert 'art/v1/logo.webp' in HTML
    assert 'art/v2/wheel-dragon.webp' in HTML
    assert HTML.count('id="spin-btn"')==1
    assert HTML.count('id="orbit-ring"')==1
    assert (STATIC/'art'/'v2'/'wheel-dragon.webp').is_file()


def test_real_balance_label_without_changing_coin_binding():
    assert 'class="balance-readout"' in HTML
    assert '<small>Coin</small>' in HTML
    assert HTML.count('id="wallet-balance"')==1
    assert 'balance-chip .balance-readout strong' in STYLE


def test_corner_glyphs_land_in_baked_oval_assets():
    assert 'el.dataset.face=face' in JS
    for color in ['red','yellow','green']:
        assert f".card3d[data-color='{color}'] .small-num:not(.bottom)" in STYLE
        assert f".card3d[data-color='{color}'] .small-num.bottom" in STYLE
    assert "data-color='yellow'" in STYLE
    assert '.card3d[data-face=\'+2\']' in STYLE


def test_metal_betting_bar_has_three_coin_icons_and_dynamic_values():
    assert 'game-shell>.result-bar>div::before' in STYLE
    assert 'id="last-stake"' in HTML
    assert 'id="last-payout"' in HTML
    assert 'id="last-delta"' in HTML
    assert 'window.UNOLuckMotion' in JS


def test_static_led_positions_and_server_selection_preserved():
    assert 'this.displays[i]=this.displays[i-1]' in LED
    assert 'PICKS = 4' in LED
    assert 'wheel.transferTo' in JS
    assert 'await wheel.settle(card,phase)' in JS
    assert 'fetch(' not in LED
    assert '.wheel-led-ring .led-slot' in STYLE
    assert '.wheel-stage .side-action' in STYLE


def test_media_queries_no_new_extra_reels_or_duplicated_crown():
    assert '@media(max-width:350px)' in STYLE
    assert '@media(orientation:landscape) and (max-height:470px)' in STYLE
    assert 'object-fit:contain!important;' in STYLE
    assert '<div class="crown"' not in HTML
    assert HTML.count('class="result-cell"')==3
    assert '/assets/art/fidelity.css?v=91' in HTML


def test_server_ledger_does_not_depend_on_visual_assets():
    source=(ROOT/'app'/'orbit.py').read_text()
    assert 'secrets.randbelow(100) < WIN_PERCENT' in source
    assert "multiplier * row['stake']" in source and 'CELEBRATIONS' in source
    assert 'idempotent' not in STYLE.lower()
