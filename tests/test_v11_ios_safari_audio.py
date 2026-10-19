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

def test_uploaded_splash_is_prepared_before_user_activation():
    assert "await studio.prepareSplashMedia()" in BOOT
    assert "soundStart.disabled=true" in BOOT
    assert "const pendingMedia = htmlFallback?studio.playSplashGesture():null;" in BOOT
    assert BOOT.index("const pendingMedia = ") < BOOT.index("const pendingUnlock = ")
    assert BOOT.index("const pendingUnlock = ") < BOOT.index("try {\n        let played=false;")
    assert "if (htmlFallback)" in BOOT
    assert "if(custom&&!played)" in BOOT
    assert "AudioContext belum aktif" not in BOOT
    assert "playSplashGesture()" in STUDIO
    assert "prepareSplashMedia()" in STUDIO
    assert "file=await readFile('soft-tech-splash-screen')" in STUDIO
    assert "URL.createObjectURL(typed)" in STUDIO
    assert "promise=player.play()" in STUDIO
    assert "mediaUnlocked=true" in STUDIO
    assert "media-src 'self' blob:" in HTML
    assert "sound.js?v=1117" in HTML
    assert "sound-studio.js?v=1120" in HTML
    assert "boot.js?v=1119" in HTML

def test_ios_media_fallback_preserves_sound_studio_settings():
    assert "limits(key,duration,{draft:previewMode})" in STUDIO
    assert "const fadeIn=bounds.fadeIn" in STUDIO
    assert "const fadeOut=bounds.fadeOut" in STUDIO
    assert "if(t>=stop-.025)" in STUDIO
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
