"""Regression checks for approved UNO LUCK UI assets and compositor motion hooks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'app' / 'static' / 'art'


def test_approved_art_is_individually_addressable():
    expected = (
        'logo.webp', 'gift.webp', 'avatar.webp', 'menu.webp',
        'spin.webp', 'turbo.webp', 'auto.webp', 'card-slot-gold.webp',
        'betting-frame-empty.webp', 'dragon-wheel-reference.webp', 'dragon-head-fx.webp',
        'color-match-title.webp',
    )
    for name in expected:
        content = (ART / 'v1' / name).read_bytes()
        assert len(content) > 5000, name
        assert content[:4] == b'RIFF', name
        assert content[8:12] == b'WEBP', name


def test_animated_numbers_have_no_payout_side_effects():
    source = (ART / 'motion.js').read_text()
    assert 'requestAnimationFrame' in source
    assert 'prefers-reduced-motion' in source
    assert "data.combo === 'JACKPOT'" in source
    assert "data.combo === 'COLOR_MATCH'" in source
    assert 'fetch(' not in source
    assert 'Math.random' not in source


def test_fx_keys_transform_only_for_dragon_motion():
    css = (ART / 'motion.css').read_text()
    assert '@keyframes dragonJackpot' in css
    assert '@keyframes dragonNod' in css
    assert '@keyframes candyPress' in css
    assert 'betting-frame-empty.webp' in css
    assert '@media(prefers-reduced-motion:reduce)' in css