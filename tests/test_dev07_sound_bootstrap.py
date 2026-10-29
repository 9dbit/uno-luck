"""QA-only pinned Sound Cloud bootstrap; never mutate a published source."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import dev02_sound_snapshot as snapshot
from app.main import app

PIN = "308c674c7b29f4231f2ef40f95a1965b4e525619913d0e5fc4c9607046338499"
ORIGIN = "https://uno-luck-render-staging.onrender.com"


def test_qa_health_rejects_empty_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("UNO_SOUND_STORAGE_DIR", str(tmp_path / "sound"))
    monkeypatch.setenv("UNO_DEV02_SOUND_SHA256", PIN)
    # Probe the health endpoint directly without lifespan (empty source).
    with pytest.raises(ValueError, match="non-isolated"):
        snapshot.validate_pinned_local(tmp_path / "sound", PIN)
    from app.sound_cloud import sound_health
    with pytest.raises(HTTPException) as error:
        sound_health()
    assert error.value.status_code == 503


def test_unpinned_startup_never_fetches_snapshot(monkeypatch):
    monkeypatch.delenv("UNO_DEV02_SOUND_SHA256", raising=False)
    monkeypatch.delenv("UNO_SOUND_STORAGE_DIR", raising=False)
    monkeypatch.setattr(snapshot, "capture",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("No unpinned fetch")))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_qa_startup_rejects_invalid_source_hash(monkeypatch):
    monkeypatch.setenv("UNO_DEV02_SOUND_SHA256", PIN)
    monkeypatch.setenv("UNO_SOUND_STORAGE_DIR", "/tmp/uno-dev02/sound")
    monkeypatch.setenv("UNO_DEV02_SOUND_SOURCE", ORIGIN)
    calls = []
    monkeypatch.setattr(snapshot, "validate_pinned_local",
                        lambda *_: (_ for _ in ()).throw(ValueError("empty")))
    def fail_capture(origin, root, expected):
        calls.append((origin, root, expected))
        raise ValueError("approved source unavailable")
    monkeypatch.setattr(snapshot, "capture", fail_capture)
    with pytest.raises(RuntimeError, match="abort"):
        with TestClient(app):
            pass
    assert calls
    assert all(root == "/tmp/uno-dev02/sound" and expected == PIN for _, root, expected in calls)
    assert {origin for origin, _, _ in calls} == snapshot.ORIGINS


def test_valid_local_pinned_copy_skips_network(monkeypatch):
    monkeypatch.setenv("UNO_DEV02_SOUND_SHA256", PIN)
    monkeypatch.setenv("UNO_SOUND_STORAGE_DIR", "/tmp/uno-dev02/sound")
    monkeypatch.setattr(snapshot, "validate_pinned_local",
                        lambda root, expected: {"ready": True, "sha": expected})
    monkeypatch.setattr(snapshot, "capture",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not import again")))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_pin_cannot_write_outside_ephemeral_qa_directory(monkeypatch):
    monkeypatch.setenv("UNO_DEV02_SOUND_SHA256", PIN)
    monkeypatch.setenv("UNO_SOUND_STORAGE_DIR", "/app/shared")
    monkeypatch.setattr(snapshot, "capture",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(RuntimeError, match="Refusing"):
        snapshot.ensure_pinned_qa_snapshot()
