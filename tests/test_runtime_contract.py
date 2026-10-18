"""Ensure Railway's domain/runtime port contract stays consistent."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dockerfile_exposes_runtime_port():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "PORT=8080" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert "--port ${PORT:-8080}" in dockerfile

def test_railway_healthcheck_endpoint():
    cfg = json.loads((ROOT / "railway.json").read_text())
    assert cfg["deploy"]["healthcheckPath"] == "/health"
