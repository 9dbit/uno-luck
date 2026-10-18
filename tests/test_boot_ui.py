"""Boot splash ordering, bundled reference art, and iOS audio activation contracts."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / 'app' / 'static'
HTML = (STATIC / 'spin-index.html').read_text()
CSS = (STATIC / 'spin.css').read_text()
JS = (STATIC / 'spin.js').read_text()
BOOT = (STATIC / 'boot.js').read_text()


def test_two_reference_images_bundled_with_valid_webp_header():
    for asset in ('boot-softtech.webp', 'boot-uno-banner.webp'):
        data = (STATIC / asset).read_bytes()
        assert data[:4] == b'RIFF'
        assert data[8:12] == b'WEBP'
        assert len(data) > 15_000


def test_splash_sequence_and_auto_entry():
    assert HTML.index('id="boot-softtech"') < HTML.index('id="boot-banner"') < HTML.index('id="game-shell"')
    assert '<main class="game-shell is-booting"' in HTML
    assert 'id="boot-loading-track" role="progressbar"' in HTML
    assert 'id="boot-with-audio"' in HTML
    assert 'id="boot-continue"' in HTML
    assert "logo.classList.add('is-fading')" in BOOT
    assert "banner.hidden = false" in BOOT
    assert "progress(100, 'Siap bermain!')" in BOOT
    assert "finishTimer = setTimeout(() => release(false)" in BOOT
    assert 'game.classList.remove(\'is-booting\')' in BOOT
    assert 'aria-hidden' in BOOT


def test_audio_unlocked_inside_user_gesture_and_no_autoplay_attempt():
    assert "gate.unlock()" in BOOT
    assert "find('boot-with-audio').addEventListener('click'" in BOOT
    assert 'await audioUnlockPending' in JS
    assert "audio.state==='running'" in JS
    assert "window.UNOLuckAudio={unlock:audioReady" in JS
    assert "const audioPromise=audioReady();setBusy(true);startReels();" in JS
    assert "document.addEventListener('pointerdown',unlockOnGesture" in JS
    assert "musicBus.connect(audioMaster)" in JS
    assert "sfxBus.connect(audioMaster)" in JS


def test_boot_remains_viewport_fixed_and_modal_game_unaffected():
    assert '.boot-overlay{position:fixed;inset:0' in CSS
    assert 'height:100dvh' in CSS
    assert '.game-shell.is-booting{visibility:hidden;pointer-events:none}' in CSS
    assert 'max(16px,env(safe-area-inset-bottom))' in CSS
    assert '.boot-overlay[hidden]{display:none!important}' in CSS
    assert 'boot.js?v=5' in HTML


def test_assets_http_and_game_routes():
    with TestClient(app) as c:
        assert c.get('/').status_code == 200
        for asset in ('boot-softtech.webp','boot-uno-banner.webp','boot.js'):
            r=c.get('/assets/'+asset)
            assert r.status_code == 200
        assert c.get('/health').json()['ok'] is True
        assert c.get('/classic').status_code == 200
