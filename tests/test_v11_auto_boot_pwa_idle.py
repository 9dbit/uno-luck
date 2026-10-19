"""UNO LUCK v1.1 auto boot, idle LED and iPhone PWA viewport contracts."""
from pathlib import Path
from app import orbit
BASE=Path(__file__).resolve().parents[1]/'app'/'static'
HTML=(BASE/'orbit-index.html').read_text()
BOOT=(BASE/'boot.js').read_text()
WHEEL=(BASE/'art/ledwheel.js').read_text()
GAME=(BASE/'orbit.js').read_text()
LAYOUT=(BASE/'art/viewport-v11.css').read_text()
VIEWPORT=(BASE/'viewport-v11.js').read_text()


def test_auto_boot_removes_sound_confirmation_card_and_buttons():
    for ident in ('boot-sound-gate','boot-sound-status','boot-start-sound',
                  'boot-start-muted','boot-with-audio','boot-continue','boot-ready-actions'):
        assert f'id="{ident}"' not in HTML,ident
    assert "void runBoot().catch" in BOOT
    assert "window.UNOLuckSound?.unlock()" not in BOOT
    assert "window.UNOLuckSound?.playCue(" not in BOOT
    assert 'game.classList.remove(\'is-booting\')' in BOOT
    assert 'uno:boot-finished' in BOOT
    assert "studio()?.prepareSplashMedia?.()" in BOOT
    assert "trySplashSound(false)" in BOOT
    assert "logo.addEventListener('pointerdown'" in BOOT
    assert "void window.UNOLuckSound?.unlock?.()" in BOOT


def test_softtech_zoom_loading_height_and_logo_pulse():
    assert 'unoSoftTechZoom' in LAYOUT
    assert 'unoLuckLogoBreathe' in LAYOUT
    assert '5.6dvh' in LAYOUT
    assert 'height:clamp(34px,5.6dvh,52px)!important' in LAYOUT
    assert 'is-zooming' in BOOT
    assert 'boot.js?v=1124' in HTML


def test_pwa_uses_visible_iphone_viewport_and_respects_safe_area():
    assert "window.visualViewport" in VIEWPORT
    assert "visualViewport?.addEventListener('resize'" in VIEWPORT
    assert "'--uno-wheel-size'" in VIEWPORT
    assert "rect.height*.965" in VIEWPORT
    assert "env(safe-area-inset-top" in LAYOUT
    assert "env(safe-area-inset-bottom" in LAYOUT
    assert 'var(--uno-wheel-size' in LAYOUT
    assert '/assets/art/viewport-v11.css?v=1124' in HTML
    assert '/assets/viewport-v11.js?v=1124' in HTML
    assert 'height:var(--uno-viewport-height,100dvh)!important' in LAYOUT


def test_clockwise_idle_faces_not_ledger_or_metal_frame_geometry():
    assert 'this.illuminate((this.chaseIndex+1)%this.count)' in WHEEL
    assert 'this.idleInterval=480' in WHEEL
    assert "this.host.classList.add('led-idle','led-ambient')" in WHEEL
    assert "this.stopIdle();\n      this.active=true" in WHEEL
    assert "window.UNOLuckSound?.ledTick(slowed)" in WHEEL
    assert "wheel?.startIdle()" in GAME
    assert "wheel?.stopIdle()" in GAME
    assert 'led-illuminated' in LAYOUT
    assert 'unoLedIdleGlide' not in LAYOUT
    assert 'width:min(56vw,441px)!important' in LAYOUT
    assert "url('/assets/art/v4/lava-temple.webp')" in LAYOUT
    assert 'this.host.replaceChildren(...this.nodes)' in WHEEL
    assert 'const PICKS = 4' in WHEEL
    assert 'fetch(' not in WHEEL
    assert 'const RING_COUNT = 9' in GAME
    assert orbit.WIN_PERCENT==80
    assert [orbit.CELEBRATIONS[i]['multiplier'] for i in range(1,6)]==[200,80,30,10,2]
