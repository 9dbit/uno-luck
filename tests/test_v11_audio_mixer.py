"""UNO LUCK v1.1 regression checks: sound controls and unchanged virtual payouts."""
from pathlib import Path
from app import orbit

ROOT = Path(__file__).resolve().parents[1] / 'app/static'


def test_virtual_economy_expected_return_is_documented():
    weights = orbit.CELEBRATIONS
    assert orbit.WIN_PERCENT == 80
    assert sum(t['weight'] for t in weights.values()) == orbit.WEIGHT_SCALE
    expected_return = sum(
        t['weight'] * t['multiplier'] for t in weights.values()
    ) * orbit.WIN_PERCENT / (orbit.WEIGHT_SCALE * 100)
    assert expected_return == 1.9536  # 195.36%, deliberately unchanged
    assert orbit.public_rules()['virtual_only']


def test_audio_controls_are_independent_and_guarded():
    sound = (ROOT / 'art/sound.js').read_text()
    ui = (ROOT / 'orbit.js').read_text()
    wheel = (ROOT / 'art/ledwheel.js').read_text()
    for name in ('setMasterVolume', 'setMusicVolume', 'setVolume', 'ledTick', 'lastError'):
        assert name in sound
    for key in ('uno_luck_master_volume', 'uno_luck_music_volume', 'uno_luck_fx_volume'):
        assert key in sound
    for title in ('MASTER', 'MUSIC', 'SFX'):
        assert "'"+title+"'" in ui
    assert 'Audio Mixer' in ui
    assert "window.UNOLuckSound?.ledTick(this.injected)" in wheel
    assert "window.UNOLuckSound?.play('lock')" in wheel
    assert "if(isAuto){cancelAuto=true;updateButtons();" in ui
    assert "src.onended=" in sound
    assert "decodeAudioData" in sound
    assert "ctx.resume()" in sound


def test_color_match_stays_server_authoritative():
    html = (ROOT / 'orbit-index.html').read_text()
    match = (ROOT / 'art/match-announce.js').read_text()
    celebrations = (ROOT / 'art/celebrations.js').read_text()
    assert '<h1 class="motion-title">DRAGON SPIN</h1>' in html
    assert 'id="color-match-burst"' in html
    assert 'aria-hidden="true" hidden' in html
    assert 'result.combo!==\'COLOR_MATCH\'' in match
    assert 'result.cards.length!==3' in match
    assert "if(!preview&&!isWin)return false;" in celebrations
