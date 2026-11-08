"""Ensure Railway's domain/runtime port contract stays consistent."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dockerfile_exposes_runtime_port():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "PORT=8080" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert 'CMD ["python", "-m", "app.start"]' in dockerfile

def test_railway_healthcheck_endpoint():
    cfg = json.loads((ROOT / "railway.json").read_text())
    assert cfg["deploy"]["healthcheckPath"] == "/health"


def test_container_drops_privileges_before_binding_configured_port(monkeypatch):
    from app import start
    import uvicorn
    monkeypatch.delenv('AGENCY_WALLET_MODE', raising=False)
    monkeypatch.setenv('PORT', '8123')
    uid = [0]
    calls = []
    monkeypatch.setattr(start.os, 'geteuid', lambda: uid[0])
    monkeypatch.setattr(start.os, 'setgroups', lambda groups: calls.append(('groups', groups)))
    monkeypatch.setattr(start.os, 'setgid', lambda gid: calls.append(('gid', gid)))
    def setuid(value):
        uid[0] = value
        calls.append(('uid', value))
    monkeypatch.setattr(start.os, 'setuid', setuid)
    def run(app, **kw):
        assert uid[0] == 10001
        assert calls == [('groups', []), ('gid', 10001), ('uid', 10001)]
        assert kw['host'] == '0.0.0.0' and kw['port'] == 8123
        assert kw['workers'] == 1
    monkeypatch.setattr(uvicorn, 'run', run)
    start.main()
