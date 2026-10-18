"""Guard against regression: custom splash audio must wait for a gesture."""
from pathlib import Path
P=Path(__file__).resolve().parents[1] / 'app' / 'static'
B=(P/'boot.js').read_text()
H=(P/'orbit-index.html').read_text()
C=(P/'art/sound-studio.css').read_text()
S=(P/'art/sound-studio.js').read_text()

def test_splash_has_audio_choice_and_no_autoplay_skip():
    for fragment in ("id=\"boot-sound-gate\"","id=\"boot-start-sound\"",
                     "id=\"boot-start-muted\"","id=\"boot-sound-status\""):
        assert fragment in H
    assert "boot.js?v=1119" in H
    assert "sound-studio.css?v=1119" in H
    assert "runBoot().catch(() => release(false))" not in B
    assert "soundStart.addEventListener('click'" in B
    assert "silentStart.addEventListener('click'" in B
    assert "const pendingUnlock = window.UNOLuckSound?.unlock()" in B
    assert "await window.UNOLuckSound.playCue('soft-tech-splash-screen')" in B
    assert "if(custom&&!played)" in B
    assert "AUDIO GAGAL:" in B
    assert "if (requestedSound) window.UNOLuckSound?.playCue('loading-scene')" in B
    assert "soundGate.hidden = true" in B
    assert ".boot-sound-gate[hidden]{display:none!important}" in C

def test_uploaded_splash_persists_across_reload():
    assert "indexedDB.open(DB,1)" in S
    assert "await writeFile(key,file)" in S
    assert "const file=await readFile(key)" in S
    assert "profiles[key]={custom:true" in S
    assert "if(!file)throw Error('File audio lokal tidak ditemukan. Upload ulang dari desktop.')" in S
    assert "const response=await fetch(cfg.url" in S
    assert "await syncCloud()" in S
    assert "source.start(now,bounds.start,bounds.length)" in S
