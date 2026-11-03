"""Ensure Railway's domain/runtime port contract stays consistent."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dockerfile_exposes_runtime_port():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "PORT=8080" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    startup = (ROOT / "deploy" / "start-web.sh").read_text()
    assert '--port "${PORT:-8080}"' in startup
    assert "runuser -u runner -- uvicorn" in startup
    assert "install -d -o runner -g runner" in startup

def test_railway_healthcheck_endpoint():
    cfg = json.loads((ROOT / "railway.json").read_text())
    assert cfg["deploy"]["healthcheckPath"] == "/health"
