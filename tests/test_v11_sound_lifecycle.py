"""UNO LUCK music lifecycle does not rewrite Sound Studio audio profiles."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'app'/'static'
SOUND=(ROOT/'art/sound.js').read_text()
STUDIO=(ROOT/'art/sound-studio.js').read_text()
GAME=(ROOT/'orbit.js').read_text()
BOOT=(ROOT/'boot.js').read_text()
HTML=(ROOT/'orbit-index.html').read_text()

def test_gameplay_entry_requests_music_before_any_joystick_or_spin_touch():
    assert "window.addEventListener('uno:boot-finished'" in GAME
    assert "window.dispatchEvent(new Event('uno:boot-finished'))" in BOOT
    assert "window.UNOLuckSoundStudio?.prepareMusicMedia?.()" in GAME
    assert "if(musicEnabled&&!document.hidden)void startMusic()" in GAME
    assert "window.UNOLuckSound?.music(true)" in GAME
    assert "window.UNOLuckSoundStudio?.playMusicGesture?.()" in GAME
    assert "window.UNOLuckSound?.webAudioState!=='running'" in GAME
    assert "if(!$('game-shell').classList.contains('is-booting'))void startMusic()" in GAME

def test_explicit_splash_play_click_triggers_preloaded_custom_cue():
    assert 'id="boot-play"' in HTML
    assert "studio()?.prepareSplashMedia?.()" in BOOT
    assert "studio()?.prepareMusicMedia?.()" in BOOT
    assert "playButton.addEventListener('click',onPlay)" in BOOT
    assert "await playGate" in BOOT
    assert "studio()?.playSplashGesture?.()" in BOOT
    assert "studio()?.armMusicOnSplashGesture?.()" in BOOT
    assert "window.UNOLuckSoundStudio?.activateMusicAtGameplay?.()" in GAME
    assert "window.UNOLuckSound?.unlock?.()" in BOOT
    assert "studio()?.stopSplashAudio?.()" in BOOT
    assert "if(!playButton&&studio()?.mediaUnlocked)" in BOOT



def test_music_has_dedicated_preloaded_fallback_with_no_sfx_interference():
    assert "function bgmElement()" in STUDIO
    assert "function prepareMusicMedia()" in STUDIO
    assert "function playMusicGesture()" in STUDIO
    assert "return playMusicMedia(); // synchronously invokes player.play()" in STUDIO
    assert "function isMusicMediaPlaying()" in STUDIO
    assert "function isMusicWebAudioPlaying()" in STUDIO
    assert "function stopMusicMedia(" in STUDIO
    assert "stopMusicMedia();" in STUDIO
    assert "if(key==='background-music'&&looping&&!forPreview)" in STUDIO
    assert "let fallbackPlayer=null" in STUDIO
    assert "let bgmPlayer=null" in STUDIO
    assert "bgmPlayer.playsInline=true" in STUDIO
    assert "if(cfg.mirror===true&&getRepeat('background-music'))" in STUDIO
    assert "limits('background-music',duration)" in STUDIO
    assert "window.UNOLuckSound?.musicVolume??.22" in STUDIO
    assert "window.UNOLuckSound?.masterVolume??.9" in STUDIO
    assert "function getRepeat(key)" in STUDIO
    assert "function mirrorConfig(" in STUDIO

def test_bgm_independent_from_sfx_mute_and_no_unnecessary_restart():
    assert "function prepareContext(){return makeCtx()?ctx:null;}" in SOUND
    assert "if(studio?.isMusicMediaPlaying?.())return true" in SOUND
    assert "if(studio?.isMusicWebAudioPlaying?.())return true" in SOUND
    assert "if(!audioEnabled||document.hidden)return false" not in SOUND
    assert "function setEnabled(v){audioEnabled=Boolean(v);if(!audioEnabled){stopSpin();bonusMedia?.pause();}}" in SOUND
    assert "const MUTE_MUSIC = 'uno_orbit_music'" in GAME
    assert "const MUTE_EFFECTS = 'uno_orbit_sfx'" in GAME
    assert "if(!musicEnabled||document.hidden)return false" in GAME

def test_only_asset_versions_changed_not_cloud_settings():
    assert "sound.js?v=1152" in HTML
    assert "sound-studio.js?v=1155" in HTML
    assert "orbit.js?v=1155" in HTML
    assert "boot.js?v=1144" in HTML
    assert "const KEY='uno_sound_studio_profiles_v1'" in STUDIO
    assert "await publishCue(key)" in STUDIO
    assert "function liveProfile" not in STUDIO # existing liveProfile arrow remains intact

