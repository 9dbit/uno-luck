"""Safari iOS regression contracts for the audio boot gate, without account mutations."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'app/static'
BOOT=(ROOT/'boot.js').read_text()
SOUND=(ROOT/'art/sound.js').read_text()
STUDIO=(ROOT/'art/sound-studio.js').read_text()
HTML=(ROOT/'orbit-index.html').read_text()

def test_safari_interrupted_context_is_recoverable():
    assert "ctx.state!=='closed'" in SOUND
    assert "primeOnGesture()" in SOUND
    assert "source.start(0)" in SOUND
    assert "const pending=ctx.resume()" in SOUND
    assert "ctx.state==='suspended'" not in SOUND
    assert "Web Audio '+ctx.state" in SOUND
    assert "get webAudioState()" in SOUND

def test_safari_play_button_activates_published_splash_in_trusted_event():
    assert "void runBoot().catch" in BOOT
    assert "window.UNOLuckSound?.unlock()" not in BOOT
    assert "studio()?.playSplashGesture?.()" in BOOT
    assert "studio()?.armMusicOnSplashGesture?.()" in BOOT
    assert "function activateMusicAtGameplay()" in STUDIO
    assert "bgmElement().muted=true" in STUDIO
    assert "player.muted=false" in STUDIO
    assert "studio?.isMusicMediaPlaying?.()" in SOUND
    assert "playButton.addEventListener('click',onPlay)" in BOOT
    assert "await playGate" in BOOT
    assert 'id="boot-play"' in HTML
    assert "window.UNOLuckSound?.playCue(" not in BOOT
    assert "playSplashGesture()" in STUDIO
    assert "prepareSplashMedia()" in STUDIO
    assert "file=await readFile('soft-tech-splash-screen')" in STUDIO
    assert "URL.createObjectURL(typed)" in STUDIO
    assert "promise=player.play()" in STUDIO
    assert "media-src 'self' blob:" in HTML
    assert "boot.js?v=1161" in HTML
    assert "sound-studio.js?v=1161" in HTML
    assert "const activate=()=>{" in (ROOT/'orbit.js').read_text()


def test_ios_media_fallback_preserves_sound_studio_settings():
    assert "limits(key,duration,{draft:previewMode})" in STUDIO
    assert "const fadeIn=bounds.fadeIn" in STUDIO
    assert "const fadeOut=!sustain&&bounds.fadeOut" in STUDIO
    assert "if(t>=stop-.025&&!mirrorDuration)" in STUDIO
    assert "stopFallback(key)" in STUDIO
    assert "get mediaUnlocked()" in STUDIO
    assert "if(window.UNOLuckSound?.webAudioState!=='running')" in STUDIO
    assert "window.UNOLuckSound?.channels?.()?.context" in STUDIO
    assert "context.decodeAudioData(bytes.slice(0))" in STUDIO
    assert "if(!isActive()){" in SOUND
    assert "return fallback?Boolean(await studio?.play(fallback)):false;" in SOUND
    assert "const key='jackpot-'+rank" in SOUND
    assert "window.UNOLuckSound?.stopCelebration?.()" in (ROOT/'art/celebrations.js').read_text()

def test_coin_ledger_and_probability_unchanged():
    from app import orbit
    assert orbit.WIN_PERCENT==80
    assert [orbit.CELEBRATIONS[i]['multiplier'] for i in range(1,6)]==[200,80,30,10,2]

