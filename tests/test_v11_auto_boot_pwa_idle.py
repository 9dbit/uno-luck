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


def test_iphone_play_button_is_the_only_splash_confirmation():
    assert 'id="boot-play"' in HTML
    assert 'id="boot-play-text"' in HTML
    assert 'aria-label="Mulai dengan suara"' in HTML
    for ident in ('boot-sound-gate','boot-start-sound','boot-start-muted',
                  'boot-with-audio','boot-continue','boot-ready-actions'):
        assert f'id="{ident}"' not in HTML,ident
    assert "playButton.addEventListener('click',onPlay)" in BOOT
    assert "await playGate" in BOOT
    assert "studio()?.prepareSplashMedia?.()" in BOOT
    assert "studio()?.playSplashGesture?.()" in BOOT
    assert "trySplashSound(false)" not in BOOT
    assert "window.UNOLuckSound?.unlock?.()" in BOOT
    assert "void runBoot().catch" in BOOT
    assert "game.classList.remove('is-booting')" in BOOT
    assert 'uno:boot-finished' in BOOT
    assert "studio()?.stopSplashAudio?.()" in BOOT


def test_softtech_zoom_loading_height_and_logo_pulse():
    assert 'unoSoftTechZoom' in LAYOUT
    assert 'unoLuckLogoBreathe' in LAYOUT
    assert '5.6dvh' in LAYOUT
    assert 'height:clamp(34px,5.6dvh,52px)!important' in LAYOUT
    assert 'is-zooming' in BOOT
    assert 'boot.js?v=1134' in HTML
    assert "studio()?.armMusicOnSplashGesture?.()" in BOOT
    assert "const musicPromise=Promise.resolve(studio()?.prepareMusicMedia?.())" in BOOT


def test_pwa_uses_visible_iphone_viewport_and_respects_safe_area():
    assert "window.visualViewport" in VIEWPORT
    assert "visualViewport?.addEventListener('resize'" in VIEWPORT
    assert "'--uno-wheel-size'" in VIEWPORT
    assert "rect.height-shift-2" in VIEWPORT
    assert "env(safe-area-inset-top" in LAYOUT
    assert "env(safe-area-inset-bottom" in LAYOUT
    assert 'var(--uno-wheel-size' in LAYOUT
    assert '/assets/art/viewport-v11.css?v=1139' in HTML
    assert '/assets/viewport-v11.js?v=1125' in HTML
    assert 'height:var(--uno-viewport-height,100dvh)!important' in LAYOUT


def test_clockwise_idle_faces_not_ledger_or_metal_frame_geometry():
    assert 'this.illuminate((this.chaseIndex+1)%this.count)' in WHEEL
    assert "this.host.dataset.spinPhase='decelerate'" in WHEEL
    assert 'const smooth=progress*progress*(3-2*progress)' in WHEEL
    assert 'if(this.chaseIndex!==PICKS)' in WHEEL
    assert 'this.idleInterval=480' in WHEEL
    assert "this.host.classList.add('led-idle','led-ambient')" in WHEEL
    assert "this.stopIdle();\n      this.active=true" in WHEEL
    assert "window.UNOLuckSound?.ledTick(Boolean(this.deceleration))" in WHEEL
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


def test_led_previews_show_random_uno_cards_not_nine_ones():
    # Numbers now travel with each clockwise LED pulse; server remains authoritative.
    assert "const WILDS = ['WILD','+4'];" in WHEEL
    assert "const ACTIONS = ['SKIP','REVERSE','+2'];" in WHEEL
    assert "this.displays=previewPack()" in WHEEL
    assert "this.advanceFaces(index)" in WHEEL
    assert "if(node.dataset.face!==face)node.dataset.face=face" in WHEEL
    assert "this.displays[PICKS]={...this.lastSelected}" in WHEEL
    assert "this.displays[PICKS]={...this.ready.card}" in WHEEL
    assert "textContent='1'" not in WHEEL
    assert 'ledwheel.js?v=1139' in HTML
    assert 'ledwheel.css?v=10' in HTML
    assert 'Sembilan panel kartu UNO berwarna' in HTML

def test_iphone15pro_pwa_background_full_bleed_and_safe_area():
    assert "CSS.supports?.('height','100dvh')" in VIEWPORT
    assert "--uno-wheel-drop" in VIEWPORT
    assert 'else update(); // First paint must not wait' in VIEWPORT
    assert 'update(); // Manual/boot refresh is synchronous' in VIEWPORT
    assert "rect.height-shift-2" in VIEWPORT
    assert "height:100lvh" in LAYOUT
    assert "body::before" in LAYOUT
    assert "url('/assets/art/v4/lava-temple.webp')!important" in LAYOUT
    assert "@media (display-mode:standalone)" in LAYOUT
    assert "padding-bottom:max(env(safe-area-inset-bottom,0px),5px)" in LAYOUT

def test_solid_uno_wheel_card_lighting():
    assert "clip-path:none!important" in LAYOUT
    assert "background:#e82032!important" in LAYOUT
    assert "background:#1169e9!important" in LAYOUT
    assert "background:#16ae50!important" in LAYOUT
    assert "background:#f5c916!important" in LAYOUT
    assert "led-dimmed .led-screen" in LAYOUT
    assert "filter:brightness(.37) saturate(.72)!important" in LAYOUT
    assert "led-illuminated .led-screen" in LAYOUT
    assert "filter:brightness(1.35) saturate(1.25)!important" in LAYOUT
