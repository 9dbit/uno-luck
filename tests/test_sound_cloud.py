"""Shared sound catalog: cross-device, durable, protected and ledger-independent."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app

API = "/api/sounds"
TOKEN = "t" * 44
WAV = (b"RIFF" + (48).to_bytes(4, "little") + b"WAVEfmt " +
       b"\x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00" +
       b"data" + (16).to_bytes(4, "little") + b"\x00" * 16)


@pytest.fixture()
def sound_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("UNO_SOUND_STORAGE_DIR", str(tmp_path / "cloud-audio"))
    monkeypatch.setenv("UNO_SOUND_ADMIN_TOKEN", TOKEN)
    return tmp_path / "cloud-audio"


def headers(name="desktop.wav", start=0.2, stop=0.8):
    import json
    return {
        "X-UNO-Sound-Admin": TOKEN,
        "X-UNO-Sound-Name": name,
        "X-UNO-Sound-Settings": json.dumps({
            "start": start, "stop": stop, "fadeIn": 0.1, "fadeOut": 0.2,
            "repeat": False, "fileDuration": 1.0,
        }),
        "Content-Type": "audio/wav",
    }


def test_cloud_empty_and_unconfigured(monkeypatch, sound_storage):
    with TestClient(app) as browser:
        empty = browser.get(API + "/manifest")
        assert empty.status_code == 200
        assert empty.json()["ready"] is True
        assert empty.json()["cues"] == {}
        assert empty.headers["cache-control"] == "no-store"
        monkeypatch.delenv("UNO_SOUND_STORAGE_DIR")
        missing = browser.get(API + "/manifest").json()
        assert missing["ready"] is False
        assert missing["cues"] == {}


def test_admin_only_can_publish(sound_storage, monkeypatch):
    with TestClient(app) as browser:
        endpoint = API + "/cues/jackpot-1"
        assert browser.put(endpoint, content=WAV, headers={
            k: v for k, v in headers().items() if k != "X-UNO-Sound-Admin"
        }).status_code == 403
        wrong = headers()
        wrong["X-UNO-Sound-Admin"] = "not-valid"
        assert browser.put(endpoint, content=WAV, headers=wrong).status_code == 403
        assert browser.get(API + "/admin/check").status_code == 403
        assert browser.get(API + "/admin/check", headers={"X-UNO-Sound-Admin": TOKEN}).json()["ok"]
        evil = headers()
        evil["Origin"] = "https://evil.example"
        assert browser.put(endpoint, content=WAV, headers=evil).status_code == 403
        assert browser.put(API + "/cues/../accounts", content=WAV, headers=headers()).status_code != 200
        monkeypatch.delenv("UNO_SOUND_ADMIN_TOKEN")
        assert browser.put(endpoint, content=WAV, headers=headers()).status_code == 503


def test_upload_synchronizes_desktop_and_mobile_manifest(sound_storage):
    with TestClient(app) as desktop:
        publish = desktop.put(API + "/cues/soft-tech-splash-screen",
                              content=WAV, headers=headers())
        assert publish.status_code == 200, publish.text
        revision = publish.json()["revision"]
        assert (sound_storage / "manifest.json").exists()
        assert len(list((sound_storage / "audio").glob("*.wav"))) == 1

    # Independent browser, with no IndexedDB and no admin credentials.
    with TestClient(app) as iphone:
        response = iphone.get(API + "/manifest")
        cue = response.json()["cues"]["soft-tech-splash-screen"]
        assert cue["source"] == "custom"
        assert cue["revision"] == revision
        assert cue["fileName"] == "desktop.wav"
        assert cue["start"] == 0.2 and cue["stop"] == 0.8
        assert cue["fadeIn"] == 0.1 and cue["fadeOut"] == 0.2
        assert cue["repeat"] is False
        result = iphone.get(cue["url"])
        assert result.status_code == 200 and result.content == WAV
        assert result.headers["content-type"].startswith("audio/wav")
        assert result.headers["x-content-type-options"] == "nosniff"


def test_settings_repeat_update_persists_without_reupload(sound_storage):
    with TestClient(app) as desktop:
        assert desktop.put(API + "/cues/background-music",
                           content=WAV, headers=headers()).status_code == 200
        old = desktop.get(API + "/manifest").json()["cues"]["background-music"]
        resp = desktop.patch(API + "/cues/background-music",
            json={"start": .1, "stop": .7, "fadeIn": .1, "fadeOut": .1,
                  "fileDuration": 1.0, "repeat": True},
            headers={"X-UNO-Sound-Admin": TOKEN})
        assert resp.status_code == 200, resp.text
        changed = desktop.get(API + "/manifest").json()["cues"]["background-music"]
        assert changed["repeat"] is True
        assert changed["stop"] == .7
        assert changed["revision"] != old["revision"]
        assert desktop.get(changed["url"]).content == WAV
        # Reset is also protected.
        assert desktop.delete(API + "/cues/background-music").status_code == 403
        assert desktop.delete(API + "/cues/background-music",
                              headers={"X-UNO-Sound-Admin": TOKEN}).status_code == 200
        assert "background-music" not in desktop.get(API + "/manifest").json()["cues"]


def test_invalid_duration_and_upload_rejected(sound_storage):
    with TestClient(app) as client:
        assert client.put(API + "/cues/jackpot-3",content=b"<script>alert(1)</script>"+b"x"*36,
                          headers=headers()).status_code == 415
        assert client.put(API + "/cues/jackpot-3",content=WAV,
                          headers=headers(name="escape.html")).status_code == 415
        assert client.put(API + "/cues/jackpot-3",content=WAV,
                          headers=headers(start=.8,stop=.6)).status_code == 422
        assert client.put(API + "/cues/jackpot-3",content=WAV*(300000),
                          headers=headers()).status_code == 413
        assert not list((sound_storage / "audio").glob("*"))


def test_publish_data_separate_from_coin_database(sound_storage, monkeypatch):
    from app import orbit
    assert orbit.WIN_PERCENT == 80
    assert [orbit.CELEBRATIONS[i]["multiplier"] for i in range(1, 6)] == [200,80,30,10,2]
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get(API + "/manifest").status_code == 200
    assert not list(Path(sound_storage.parent).glob("*.db"))


def test_bounded_staging_sound_history(sound_storage):
    with TestClient(app) as browser:
        for i in range(3):
            result = browser.put(API + "/cues/jackpot-5", content=WAV,
                                 headers=headers(name=f"jackpot-{i}.wav"))
            assert result.status_code == 200
        paths = list((sound_storage / "audio").glob("jackpot-5-*.wav"))
        assert len(paths) == 2, paths
        latest = browser.get(API + "/manifest").json()["cues"]["jackpot-5"]
        assert browser.get(latest["url"]).content == WAV

def test_sound_health_verifies_persistent_storage(sound_storage, monkeypatch):
    with TestClient(app) as client:
        response = client.get("/api/sounds/health")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "ready": True, "published_cues": 0, "revision": "initial",
        }
        assert response.headers["cache-control"] == "no-store"
        assert list(sound_storage.glob(".uno-sound-health-*")) == []
        assert list((sound_storage / "audio").glob(".uno-sound-health-*")) == []
        monkeypatch.delenv("UNO_SOUND_STORAGE_DIR")
        assert client.get("/api/sounds/health").status_code == 503


def test_sound_cloud_health_does_not_change_virtual_coin_health(sound_storage):
    with TestClient(app) as client:
        assert client.get("/api/sounds/health").json()["ready"]
        assert client.get("/health").json()["money_enabled"] is False


def test_music_mirror_is_validated_published_and_only_applies_to_music(sound_storage):
    with TestClient(app) as browser:
        response = browser.put(API + "/cues/background-music", content=WAV,
            headers={
                **headers(),
                "X-UNO-Sound-Settings": __import__("json").dumps({
                    "start": 0.1, "stop": 0.8, "fadeIn": 0.1, "fadeOut": 0.1,
                    "repeat": True, "mirror": True, "mirrorCrossfadeMs": 180,
                    "fileDuration": 1.0,
                }),
            })
        assert response.status_code == 200, response.text
        cue = browser.get(API + "/manifest").json()["cues"]["background-music"]
        assert cue["mirror"] is True
        assert cue["mirrorCrossfadeMs"] == 180
        assert cue["repeat"] is True
        patch = browser.patch(API + "/cues/background-music",
            headers={"X-UNO-Sound-Admin": TOKEN},
            json={"start": 0.1, "stop": 0.8, "fadeIn": 0, "fadeOut": 0,
                  "repeat": False, "mirror": False, "mirrorCrossfadeMs": 0,
                  "fileDuration": 1.0})
        assert patch.status_code == 200, patch.text
        next_cue = browser.get(API + "/manifest").json()["cues"]["background-music"]
        assert next_cue["mirror"] is False
        assert next_cue["mirrorCrossfadeMs"] == 0
        assert browser.get(next_cue["url"]).content == WAV
        for invalid in (-1, 1001, "200", float("nan")):
            bad = browser.patch(API + "/cues/background-music",
                headers={"X-UNO-Sound-Admin": TOKEN},
                json={"start": 0.1, "stop": 0.8, "fadeIn": 0, "fadeOut": 0,
                      "repeat": True, "mirror": True, "mirrorCrossfadeMs": invalid,
                      "fileDuration": 1.0})
            assert bad.status_code == 422, (invalid, bad.text)
        assert browser.put(API + "/cues/jackpot-1", content=WAV,
            headers={**headers(), "X-UNO-Sound-Settings": __import__("json").dumps({
                "start": 0.1, "stop": 0.8, "fadeIn": 0, "fadeOut": 0,
                "fileDuration": 1.0, "mirror": True, "mirrorCrossfadeMs": 140
            })}).status_code == 200
        jackpot = browser.get(API + "/manifest").json()["cues"]["jackpot-1"]
        assert "mirror" not in jackpot and "mirrorCrossfadeMs" not in jackpot
