"""Sound Studio v1.1 contract tests: all twelve sound events and persisted trim controls."""
from pathlib import Path
import re
from app import orbit
P=Path(__file__).resolve().parents[1]/'app'/'static'
A=(P/'art/sound-studio.js').read_text()
C=(P/'art/sound-studio.css').read_text()
S=(P/'art/sound.js').read_text()
H=(P/'orbit-index.html').read_text()
GAME=(P/'orbit.js').read_text()
BOOT=(P/'boot.js').read_text()

def test_twelve_editable_sounds_registered():
    for sound in ['soft-tech-splash-screen','loading-scene','background-music',
        'push-button','spinning-sound','chosen-card','result-sound']:
        assert sound in A
    assert "'jackpot-'+rank" in A
    assert "1,2,3,4,5" in A
    assert "KEYS.map" in A
    for field in ['start','stop','duration','fadeIn','fadeOut']:
        assert field in A

def test_editing_is_real_and_persistent_without_server_upload():
    for contract in ["indexedDB.open", "createObjectStore('files')",
            "decodeAudioData", "file.arrayBuffer()", "await writeFile(key,file)",
            "await removeFile(key)", "source.loopStart=bounds.start",
            "source.loopEnd=bounds.stop", "source.start(now,bounds.start,bounds.length)",
            "linearRampToValueAtTime", "file.size>MAX_BYTES",
            "if(![start,stop,fi,fo].every(Number.isFinite)"]:
        assert contract in A, contract
    assert "UNO_SPIN_DB_PATH" not in A
    assert "/api/orbit/pick" not in A
    assert "/api/sounds/manifest" in A
    assert "function stopLoop()" in A and "function stopPreview()" in A

def test_real_game_events_and_boot_use_studio_cues():
    assert 'sound-studio.js?v=1120' in H
    assert 'sound-studio.css?v=1120' in H
    assert H.index('sound.js?v=1117') < H.index('sound-studio.js?v=1120') < H.index('orbit.js?v=1119')
    assert "installStudio,channels,playCue,result" in S
    assert "studio?.isCustomized(cue)" in S
    assert "studio?.isCustomized('background-music')" in S
    assert "studio?.isCustomized('result-sound')" in S
    assert "playCue('soft-tech-splash-screen')" in BOOT
    assert "playCue('loading-scene')" in BOOT
    assert "showSoundStudio" in GAME and 'Sound Studio · 12 Custom Sound Effects' in GAME
    assert "last.combo!=='COLOR_MATCH')window.UNOLuckSound?.result(false)" in GAME
    assert "window.UNOLuckSound?.play('lock')" in (P/'art/ledwheel.js').read_text()
    assert "sfx('spin')" in GAME and "sfx('tap')" in GAME

def test_pill_layout_is_wider_without_covering_spin():
    assert "width:29%!important" in C
    assert "width:30%!important" in C
    assert "left:1%!important" in C and "right:1%!important" in C
    assert "overflow:visible!important" in C
    assert "white-space:nowrap!important" in C
    assert "overflow-y:auto!important" in C

def test_coin_engine_unchanged():
    assert orbit.WIN_PERCENT == 80
    assert [orbit.CELEBRATIONS[i]['multiplier'] for i in range(1,6)] == [200,80,30,10,2]
    assert sum(x['weight'] for x in orbit.CELEBRATIONS.values()) == 1_000_000

def test_native_slider_editor_on_every_cue():
    assert "for(const [key,title,defaultSample] of KEYS)" in A
    assert "slider.type='range'" in A
    assert "slider.dataset.field=field" in A
    assert "['start','START'],['stop','STOP'],['duration','DURATION']" in A
    assert "values[field].value=slider.value" in A
    assert "updateSliderView()" in A
    assert "studio-timeline-selection" in A
    assert ".studio-slider-row" in C
    assert "overflow-y:auto!important" in C

def test_music_repeat_off_and_on_end_to_end_wiring():
    assert "function getRepeat(key)" in A
    assert "function setRepeat(key,enabled)" in A
    assert "repeatInput.type='checkbox'" in A
    assert "repeatInput.checked=getDraftRepeat(key)" in A
    assert "setRepeat(key,repeatInput.checked)" in A
    assert "repeat:getDraftRepeat(key)" in A
    assert "const repeat=looping && getRepeat(key)" in A
    assert "source.loop=repeat" in A
    assert "if(repeat)source.start(now,bounds.start)" in A
    assert "else source.start(now,bounds.start,bounds.length)" in A
    assert "musicRequested=Boolean(playIt)" in S
    assert "async function refreshMusic()" in S
    assert "refreshMusic," in S

def test_jackpot_audio_is_exclusive_cancelable_and_server_confirmed():
    celebration=(P/'art/celebrations.js').read_text()
    assert "if(!preview&&!isWin)return false;" in celebration
    assert "if(!customized&&isActive())cinematicImpact(rank)" in S
    assert "const key='jackpot-'+rank" in S
    assert "if(cue&&studio?.isCustomized(cue))return studio.play(cue)" in S
    assert "window.UNOLuckSound?.stopCelebration?.()" in celebration
    assert "window.UNOLuckSound?.celebration(selected)" in celebration
    assert "Math.max(minimumMs,configuredMs)" in celebration
    assert "stopCelebration,segmentDuration" in A
    assert "jackpotToken!==celebrationRequest" in A
    assert "if(isJackpot){item.key=key;celebrationNode=item;}" in A
    assert "if(sfxEnabled && last.combo!=='COLOR_MATCH')" in GAME
    assert [__import__('app.orbit',fromlist=['CELEBRATIONS']).CELEBRATIONS[i]['multiplier']
        for i in range(1,6)] == [200,80,30,10,2]
