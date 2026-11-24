"""Fail-closed production hardening tests: no production HTTP/WS game writes."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.production_safety import (
    allowed_https_origins, check_production_environment, data_volume_path,
    is_production, public_request_block, require_safe_production_configuration,
)

SAFE = {
    "RAILWAY_ENVIRONMENT_NAME": "production",
    "UNO_SPIN_DB_PATH": "/data/uno-luck/game.sqlite3",
    "UNO_SOUND_STORAGE_DIR": "/data/uno-luck-sounds",
    "UNO_ALLOWED_ORIGINS": "https://uno.example.com",
}


def test_staging_unmodified():
    assert not is_production({"RAILWAY_ENVIRONMENT_NAME": "staging"})
    assert check_production_environment({"RAILWAY_ENVIRONMENT_NAME": "staging"}) == ()
    for method, path in (("GET", "/admin"), ("POST", "/api/orbit/pick"),
                         ("PATCH", "/api/sounds/mixer")):
        assert public_request_block(method, path, {"RAILWAY_ENVIRONMENT_NAME": "staging"}) is None


def test_startup_fails_closed_on_current_web_shape():
    current = {"RAILWAY_ENVIRONMENT_NAME": "production",
               "UNO_SOUND_STORAGE_DIR": "/data/uno-luck-audio"}
    issues = check_production_environment(current)
    assert any("UNO_SPIN_DB_PATH" in x for x in issues)
    assert any("UNO_ALLOWED_ORIGINS" in x for x in issues)
    with pytest.raises(RuntimeError, match="production startup blocked"):
        require_safe_production_configuration(current)


@pytest.mark.parametrize("key,value", [
    ("UNO_SPIN_DB_PATH", "/tmp/guest.sqlite3"),
    ("UNO_SPIN_DB_PATH", "/data/../tmp/guest.sqlite3"),
    ("UNO_SOUND_STORAGE_DIR", "relative/sounds"),
    ("UNO_ALLOWED_ORIGINS", "*"),
    ("UNO_ALLOWED_ORIGINS", "http://localhost:8080"),
    ("UNO_ALLOWED_ORIGINS", "https://uno.example.com,https://uno.example.com"),
    ("UNO_SOUND_ADMIN_TOKEN", "do-not-use-shared-admin-credential"),
    ("GAMEOPS_WALLET_COMMANDS_ENABLED", "1"),
    ("UNO_PUBLIC_ROUNDS_ENABLED", "1"),
    ("UNO_QA_ACTIVITY_DEMO", "1"),
    ("UNO_DEMO_GAME", "true"),
])
def test_production_rejects_unsafe_configuration(key, value):
    assert check_production_environment({**SAFE, key: value}), key


def test_safe_config_does_not_claim_certification():
    # This checks configuration shape, NOT production security assurance.
    assert check_production_environment(SAFE) == ()
    assert data_volume_path("/data/uno-luck/game.sqlite3")
    assert not data_volume_path("/tmp/uno.sqlite3")
    assert allowed_https_origins("https://uno.example.com")
    assert not allowed_https_origins("https://*.example.com")


def test_editor_publication_and_guest_rounds_are_closed():
    for path in ("/admin", "/admin/", "/assets/admin.html",
                 "/assets/admin.js", "/assets/admin.css",
                 "/api/sounds/admin/check"):
        assert public_request_block("GET", path, SAFE) == "private_editor"
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert public_request_block(method, "/api/sounds/cues/jackpot-1", SAFE) == "sound_publish"
    assert public_request_block("PATCH", "/api/sounds/mixer", SAFE) == "sound_publish"
    for path in ("/api/spin/state", "/api/spin/place", "/api/orbit/pick", "/api/orbit/state"):
        assert public_request_block("GET", path, SAFE) == "rounds_closed"
    assert public_request_block("GET", "/api/sounds/manifest", SAFE) is None
    assert public_request_block("GET", "/health", SAFE) is None


def test_production_http_requires_no_private_editor_token(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    # Avoid app startup: the test is scoped to route-level guarantees. Startup
    # config failures are explicitly exercised in independent tests above.
    client = TestClient(app)
    assert client.get("/admin").status_code == 404
    assert client.get("/assets/admin.html").status_code == 404
    assert client.get("/api/sounds/admin/check").status_code == 404
    assert client.patch("/api/sounds/mixer", json={"master": 1}).status_code == 403
    assert client.get("/api/orbit/state").status_code == 503
    assert client.post("/api/orbit/pick", json={}).status_code == 503
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert homepage.headers["x-content-type-options"] == "nosniff"
    assert homepage.headers["referrer-policy"] == "no-referrer"


def test_production_websocket_refused(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    client = TestClient(app)
    with pytest.raises(Exception) as exc:
        with client.websocket_connect("/ws", headers={"origin": "https://uno.example.com"}):
            pass
    assert "1008" in str(exc.value) or "WebSocketDisconnect" in type(exc.value).__name__
