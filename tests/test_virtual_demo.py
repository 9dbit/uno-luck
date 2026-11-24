import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import spin, orbit
from app.demo_security import COOKIE, Budget, budget
from app.production_safety import check_production_environment
from app.demo_storage import prepare_demo_storage

ORIGIN = "https://uno.xd-play.com"


@pytest.fixture
def demo(monkeypatch, tmp_path):
    for key, value in {
        "UNO_DEPLOYMENT_TIER": "production", "UNO_RELEASE_MODE": "virtual-demo",
        "UNO_VIRTUAL_DEMO_ENABLED": "1", "GAMEOPS_BRIDGE_ENABLED": "0",
        "UNO_ALLOWED_ORIGINS": ORIGIN,
        "UNO_SPIN_DB_PATH": str(tmp_path / "game.sqlite3"),
        "UNO_SOUND_STORAGE_DIR": str(tmp_path / "sounds"),
    }.items():
        monkeypatch.setenv(key, value)
    budget.entries.clear()
    prepare_demo_storage()
    client = TestClient(app, base_url=ORIGIN)
    state = client.get("/api/orbit/state")
    assert state.status_code == 200
    client.headers.update({"Origin": ORIGIN, "X-UNO-Client": "spin-ui",
                           "X-UNO-CSRF": state.headers["x-uno-csrf"]})
    yield client, state, tmp_path
    client.close()


def test_demo_configuration_is_explicit_and_isolated():
    env = {"UNO_DEPLOYMENT_TIER": "production", "UNO_RELEASE_MODE": "virtual-demo",
           "UNO_SPIN_DB_PATH": "/data/game/demo.sqlite3",
           "UNO_SOUND_STORAGE_DIR": "/data/sounds", "UNO_ALLOWED_ORIGINS": ORIGIN,
           "GAMEOPS_BRIDGE_ENABLED": "0"}
    assert check_production_environment(env) == ()
    for key, value in (("UNO_ALLOWED_ORIGINS", ORIGIN + ",https://staging-uno.xd-play.com"),
                       ("GAMEOPS_BRIDGE_SECRET", "staging-secret"),
                       ("GAMEOPS_BRIDGE_ENABLED", "1"), ("UNO_PUBLIC_ROUNDS_ENABLED", "1")):
        assert check_production_environment({**env, key: value})


def test_cookie_and_session_isolation(demo):
    client, response, _ = demo
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(COOKIE + "=")
    for flag in ("Secure", "HttpOnly", "SameSite=lax", "Path=/"):
        assert flag in cookie
    assert "Domain=" not in cookie
    assert client.get("/api/orbit/state").json()["account"] == response.json()["account"]
    other = TestClient(app, base_url=ORIGIN, cookies={spin.COOKIE: client.cookies[COOKIE]})
    assert other.get("/api/spin/history").status_code == 401


@pytest.mark.parametrize("path", ["/admin", "/admin/", "/assets/admin.html", "/assets/admin.js",
    "/assets/art/sound-studio.js", "/api/sounds/admin/check", "/classic", "/openapi.json", "/studio"])
def test_private_surfaces_unavailable(demo, path):
    response = demo[0].get(path)
    assert response.status_code == 404
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("headers", [
    {"Origin": "https://xd-play.com"}, {"Origin": "https://staging-uno.xd-play.com"},
    {"Origin": "https://evil.example"}, {"Origin": "null"}, {"Origin": ""},
    {"X-UNO-CSRF": ""}, {"X-UNO-CSRF": "bad"}, {"Sec-Fetch-Site": "same-site"},
])
def test_csrf_rejects_cross_origin_and_missing_token(demo, headers):
    r = demo[0].post("/api/orbit/pick", json={"request_id": "csrf-probe-000001", "stake": 25}, headers=headers)
    assert r.status_code == 403
    assert demo[0].get("/api/orbit/state").json()["account"]["balance"] == 1000


def test_only_successful_play_document_can_be_framed(demo):
    c = demo[0]
    doc = c.get("/play/")
    assert doc.status_code == 200
    assert "frame-ancestors https://xd-play.com" in doc.headers["content-security-policy"]
    assert "x-frame-options" not in doc.headers
    assert "/assets/art/public-audio.js" in doc.text
    assert "/assets/art/sound-studio.js" not in doc.text
    for response in (c.get("/"), c.get("/api/orbit/state"), c.get("/play-extra/"), c.post("/play/")):
        assert response.headers["x-frame-options"] == "DENY"
    assert c.get("/play/", headers={"host": "attacker.example"}).status_code == 400


def test_mutation_surface_and_limits(demo):
    c = demo[0]
    assert c.post("/api/spin/place", json={}).status_code == 403
    assert c.patch("/api/sounds/mixer", json={}).status_code == 403
    assert c.post("/api/deposit", json={}).status_code == 403
    assert c.post("/api/withdraw", json={}).status_code == 403
    assert c.post("/api/orbit/pick", content="x").status_code == 415
    assert c.post("/api/orbit/pick", json={"padding": "x" * 17000}).status_code == 413
    b = Budget()
    assert all(b.allow("a", 3, 0) for _ in range(3))
    assert not b.allow("a", 3, 0)
    assert b.allow("a", 3, 60)


def test_lost_reply_refresh_replay_and_restore(demo, monkeypatch):
    c, _, folder = demo
    first = c.post("/api/orbit/pick", json={"request_id": "recover-demo-0001", "stake": 25}).json()
    assert first["round"]["picked"] == 1
    assert c.get("/api/orbit/state").json()["round"] == first["round"]
    retry = c.post("/api/orbit/pick", json={"request_id": "recover-demo-0001", "stake": 25}).json()
    assert retry["replayed"] and retry["account"]["balance"] == 975
    for i in (2, 3):
        result = c.post("/api/orbit/pick", json={"request_id": f"recover-demo-000{i}", "stake": 25}).json()
    assert result["round"]["complete"]
    before = c.get("/api/orbit/state").json()
    for i in (1, 2, 3):
        assert c.post("/api/orbit/pick", json={"request_id": f"recover-demo-000{i}", "stake": 25}).json()["replayed"]
    assert c.get("/api/orbit/state").json() == before
    restored = folder / "restored.sqlite3"
    with sqlite3.connect(spin.database_path()) as src, sqlite3.connect(restored) as dst:
        src.backup(dst)
        assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    monkeypatch.setenv("UNO_SPIN_DB_PATH", str(restored))
    assert c.get("/api/orbit/state").json() == before
    assert c.post("/api/orbit/pick", json={"request_id": "recover-demo-0003", "stake": 25}).json()["replayed"]


def test_snapshot_audio_and_readonly_player(demo):
    c = demo[0]
    manifest = c.get("/api/sounds/manifest").json()
    assert manifest["revision"] == "801acad084900b626931ffa1"
    assert manifest["mixer"] == {"master": .9, "music": .22, "sfx": .85}
    expected = json.loads((Path(__file__).parents[1] / "app/published_audio/manifest.json").read_text())
    for cue, info in manifest["cues"].items():
        response = c.get(info["url"])
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == expected["cues"][cue]["sha256"]
    player = c.get("/assets/art/public-audio.js").text
    assert "X-UNO-Sound-Admin" not in player
    assert "sessionStorage" not in player
    assert "verifyAdminKey" not in player


def test_admission_switch_closes_rounds(demo, monkeypatch):
    monkeypatch.setenv("UNO_VIRTUAL_DEMO_ENABLED", "0")
    assert demo[0].get("/api/orbit/state").status_code == 503
    assert demo[0].post("/api/orbit/pick", json={}).status_code == 503
    assert demo[0].get("/health").json()["launch_enabled"] is False
