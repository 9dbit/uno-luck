"""Native sound consumption exposes only the public catalog and safe files."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.provider_main import app


def test_native_sound_routes_are_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path))
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN', 'a' * 44)
    audio = Path(__file__).parents[1] / 'app/static/audio/music-loop.mp3'
    name = 'soft-tech-splash-screen-' + 'a' * 24 + '.mp3'
    (tmp_path / 'audio').mkdir()
    (tmp_path / 'audio' / name).write_bytes(audio.read_bytes())
    data = {'revision': 'native-qa', 'cues': {'soft-tech-splash-screen': {
        'source': 'custom', 'storageName': name, 'revision': 'native-qa',
        'fileName': 'music-loop.mp3', 'start': 0, 'stop': 7, 'fileDuration': 14.616,
    }}}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(data))
    before = manifest.read_bytes()
    # No lifespan is needed: these public read routes have no agency DB effect.
    client = TestClient(app)
    response = client.get('/api/sounds/manifest')
    assert response.status_code == 200
    cue = response.json()['cues']['soft-tech-splash-screen']
    assert 'storageName' not in cue
    download = client.get(cue['url'])
    assert download.status_code == 200
    assert download.content == audio.read_bytes()
    assert download.headers['content-type'].startswith('audio/mpeg')
    assert download.headers['x-content-type-options'] == 'nosniff'
    for method, path in [('GET', '/api/sounds/admin/check'),
                         ('PUT', '/api/sounds/cues/soft-tech-splash-screen'),
                         ('PATCH', '/api/sounds/mixer'),
                         ('DELETE', '/api/sounds/cues/soft-tech-splash-screen')]:
        result = client.request(method, path, headers={'X-UNO-Sound-Admin': 'a' * 44})
        assert result.status_code in (404, 405)
    assert manifest.read_bytes() == before
    assert client.get('/api/sounds/files/unknown').status_code == 404


def test_native_sound_rejects_manifest_path_escape(tmp_path, monkeypatch):
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path))
    (tmp_path / 'manifest.json').write_text(json.dumps({'revision': 'bad', 'cues': {
        'soft-tech-splash-screen': {'source': 'custom', 'revision': 'bad',
                                  'storageName': '../../outside.mp3'}}}))
    assert TestClient(app).get('/api/sounds/files/soft-tech-splash-screen').status_code == 503


def test_native_sound_unconfigured_is_a_public_empty_catalog(monkeypatch):
    monkeypatch.delenv('UNO_SOUND_STORAGE_DIR', raising=False)
    result = TestClient(app).get('/api/sounds/manifest')
    assert result.status_code == 200
    assert result.json() == {'ready': False, 'revision': 'initial', 'cues': {}}
