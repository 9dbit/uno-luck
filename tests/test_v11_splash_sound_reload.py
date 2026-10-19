"""Guard against regression: custom splash audio must wait for a gesture."""
from pathlib import Path
P=Path(__file__).resolve().parents[1] / 'app' / 'static'
B=(P/'boot.js').read_text()
H=(P/'orbit-index.html').read_text()
C=(P/'art/sound-studio.css').read_text()
S=(P/'art/sound-studio.js').read_text()

def test_splash_has_one_explicit_sound_button_and_custom_cue():
    for identifier in ("boot-sound-gate","boot-start-sound","boot-start-muted",
                       "boot-with-audio","boot-continue"):
        assert f'id="{identifier}"' not in H
    assert 'id="boot-play"' in H
    assert 'boot.js?v=1132' in H
    assert "playButton.addEventListener('click',onPlay)" in B
    assert "await playGate" in B
    assert "studio()?.prepareSplashMedia?.()" in B
    assert "studio()?.playSplashGesture?.()" in B
    assert "studio()?.stopSplashAudio?.()" in B
    assert "window.UNOLuckSound?.unlock()" not in B
    assert "window.dispatchEvent(new Event('uno:boot-finished'))" in B
    assert "game.classList.remove('is-booting')" in B
    assert "progress(100,'loading game system')" in B
    assert 'id="boot-loading-track"' in H


def test_uploaded_splash_persists_across_reload():
    assert "indexedDB.open(DB,1)" in S
    assert "await writeFile(key,file)" in S
    assert "const file=await readFile(key)" in S
    assert "profiles[key]={custom:true" in S
    assert "if(!file)throw Error('File audio lokal tidak ditemukan. Upload ulang dari desktop.')" in S
    assert "const response=await fetch(cfg.url" in S
    assert "await syncCloud()" in S
    assert "source.start(now,bounds.start,bounds.length)" in S
