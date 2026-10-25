"""Separate COLOR MATCH asset and actual, server-confirmed celebration gate."""
from pathlib import Path
from app import orbit

SRC = Path(__file__).resolve().parents[1] / 'app' / 'static'
HTML = (SRC / 'orbit-index.html').read_text()
MATCH = (SRC / 'art' / 'match-announce.js').read_text()
CELEBRATIONS = (SRC / 'art' / 'celebrations.js').read_text()
STYLE = (SRC / 'art' / 'v11.css').read_text()


def test_color_match_is_a_standalone_transparent_asset():
    webp = SRC / 'art/v4/color-match.webp'
    assert webp.stat().st_size > 20_000
    assert webp.read_bytes()[:4] == b'RIFF'
    assert b'WEBP' in webp.read_bytes()[8:16]
    assert 'src="/assets/art/v4/color-match.webp"' in HTML
    assert 'id="color-match-burst"' in HTML
    assert 'aria-hidden="true" hidden' in HTML
    assert 'DRAGON SPIN</h1>' in HTML
    assert '<h1 class="motion-title">COLOR MATCH' not in HTML


def test_only_real_matching_server_round_can_trigger_it():
    for check in ("result?.complete", "result.combo!=='COLOR_MATCH'", "result.tier?.rank", "result.cards.length!==3", "result.cards.every("):
        assert check in MATCH
    assert "if(!preview){" in CELEBRATIONS
    assert "window.UNOLuckMatch?.reveal(result)" in CELEBRATIONS
    assert "else window.UNOLuckMatch?.clear()" in CELEBRATIONS
    assert 'window.UNOLuckMatch?.clear()' in (SRC/'orbit.js').read_text()
    assert 'window.UNOLuckMatch?.clear()' in CELEBRATIONS
    assert 'overlay.dataset.scope' in CELEBRATIONS


def test_first_rank_is_fullscreen_but_other_four_replace_wheel():
    assert 'const local=selected!==1;' in CELEBRATIONS
    assert 'wheelArea.append(overlay)' in CELEBRATIONS
    assert 'document.body.append(overlay)' in CELEBRATIONS
    assert 'wheelArea.classList.add(\'has-celebration\')' in CELEBRATIONS
    assert 'celebration-overlay.scope-wheel' in STYLE
    assert 'celebration-overlay.scope-full' in STYLE
    assert 'conic-gradient(' not in STYLE  # no hard-edged wedges in the new v1.1 layers


def test_exact_bet_labels_and_original_tier_policy():
    for label in ('<small>BET</small>', '<small>WIN</small>', '<small>NET</small>'):
        assert HTML.count(label) == 1
    assert sum(x['weight'] for x in orbit.CELEBRATIONS.values()) == 1_000_000
    assert orbit.WIN_PERCENT == 80
    assert orbit.CELEBRATIONS[1]['multiplier'] == 200
    assert orbit.CELEBRATIONS[5]['multiplier'] == 2


def test_background_and_accessible_audio_self_test_are_bundled():
    background = SRC / 'art/v4/lava-temple.webp'
    assert background.read_bytes()[:4] == b'RIFF'
    assert background.stat().st_size > 80_000
    assert "url('/assets/art/v4/lava-temple.webp')" in STYLE
    assert 'match-sr-only' in STYLE
    assert 'id="match-live"' in HTML
    assert 'testSound' in (SRC/'art/sound.js').read_text()
    assert 'Tes Suara Meriah' in (SRC/'admin.html').read_text()
    assert "testSound(){" in (SRC/'art/sound.js').read_text()


def test_reduced_motion_cannot_discard_acknowledged_spin_result():
    """The JS engine must return the Promise saved before complete() resets it."""
    wheel = (SRC / 'art/ledwheel.js').read_text()
    assert 'const acknowledged=this.pending;' in wheel
    assert 'return acknowledged;' in wheel
    assert wheel.index('const acknowledged=this.pending;') < wheel.index('this.complete();', wheel.index('const acknowledged=this.pending;'))
