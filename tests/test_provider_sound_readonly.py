"""Provider playback routes cannot publish audio or touch native game storage."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import agency
from app.provider_main import app

ASSET = Path(__file__).resolve().parents[1] / 'app/static/audio/music-loop.mp3'
CUE = 'soft-tech-splash-screen'


def test_public_catalog_and_actual_audio_preserve_files(tmp_path, monkeypatch):
    root = tmp_path / 'catalog'
    (root / 'audio').mkdir(parents=True)
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(root))
    revision = hashlib.sha256(ASSET.read_bytes()).hexdigest()[:24]
    filename = f'{CUE}-{revision}.mp3'
    (root / 'audio' / filename).write_bytes(ASSET.read_bytes())
    manifest = {'revision': revision, 'cues': {CUE: {
        'source': 'custom', 'revision': revision, 'fileName': 'published.mp3',
        'storageName': filename, 'start': .25, 'stop': 7, 'fadeIn': .1,
        'fadeOut': .25, 'fileDuration': 14.616, 'private_note': 'not-public',
    }, 'unknown-cue': {'source': 'custom', 'revision': 'ignored'}}}
    (root / 'manifest.json').write_text(json.dumps(manifest))
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    # Do not run lifespan: this is the isolated public HTTP read surface.
    client = TestClient(app)
    response = client.get('/api/sounds/manifest')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    data = response.json()
    assert set(data) == {'ready', 'revision', 'cues', 'mixer'}
    assert data['ready'] is True and set(data['cues']) == {CUE}
    cue = data['cues'][CUE]
    assert set(cue) == {'source','revision','fileName','start','stop','fadeIn','fadeOut','fileDuration','url'}
    assert cue['url'] == f'/api/sounds/files/{CUE}?v={revision}'
    audio = client.get(cue['url'])
    assert audio.status_code == 200 and audio.content == ASSET.read_bytes()
    assert audio.headers['content-type'] == 'audio/mpeg'
    assert audio.headers['x-content-type-options'] == 'nosniff'
    bundled = client.get('/assets/audio/music-loop.mp3')
    assert bundled.status_code == 200 and bundled.content == ASSET.read_bytes()
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_empty_and_unconfigured_catalog_are_honest_public_reads(tmp_path, monkeypatch):
    root = tmp_path / 'empty'
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(root))
    monkeypatch.setattr(agency, 'db_open', lambda: pytest.fail('Unexpected native DB access'))
    client = TestClient(app)
    empty = client.get('/api/sounds/manifest')
    assert empty.status_code == 200 and empty.json() == {
        'ready': True, 'revision': 'initial', 'cues': {}, 'mixer': None}
    # The existing storage helper initializes directories; it does not publish.
    assert root.is_dir() and (root / 'audio').is_dir()
    assert not list(root.rglob('*.*'))
    monkeypatch.delenv('UNO_SOUND_STORAGE_DIR')
    response = client.get('/api/sounds/manifest')
    assert response.status_code == 200 and response.json() == {
        'ready': False, 'revision': 'initial', 'cues': {}}


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/sounds/admin/check'), ('GET', '/api/sounds/health'),
    ('PUT', '/api/sounds/cues/soft-tech-splash-screen'),
    ('PATCH', '/api/sounds/cues/soft-tech-splash-screen'),
    ('DELETE', '/api/sounds/cues/soft-tech-splash-screen'),
    ('PATCH', '/api/sounds/mixer'), ('POST', '/api/sounds/manifest'),
    ('PUT', '/api/sounds/files/soft-tech-splash-screen'),
    ('DELETE', '/api/sounds/files/soft-tech-splash-screen'),
])
def test_admin_and_mutation_routes_remain_absent(tmp_path, monkeypatch, method, path):
    root = tmp_path / 'not-created'
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(root))
    token = 'local-test-only-' + 'a' * 40
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN', token)
    monkeypatch.setattr(agency, 'db_open', lambda: pytest.fail('Unexpected native DB access'))
    response = TestClient(app).request(method, path, headers={'X-UNO-Sound-Admin': token}, json={'start': 0})
    assert response.status_code in (404,405)
    assert not root.exists()
    sound_routes = [r for r in app.routes if getattr(r, 'path', '').startswith('/api/sounds/')]
    assert {(r.path, frozenset(r.methods)) for r in sound_routes} == {
        ('/api/sounds/manifest', frozenset({'GET'})),
        ('/api/sounds/files/{cue}', frozenset({'GET'})),
    }


@pytest.mark.parametrize('filename', ['../../outside.mp3','/tmp/outside.mp3','other-cue-'+'a'*24+'.mp3',CUE+'-'+'a'*24+'.html'])
def test_published_file_rejects_unsafe_storage_names(tmp_path, monkeypatch, filename):
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path))
    (tmp_path / 'manifest.json').write_text(json.dumps({'revision':'bad','cues':{
        CUE:{'source':'custom','revision':'bad','storageName':filename}}}))
    response = TestClient(app).get('/api/sounds/files/'+CUE)
    assert response.status_code == 503 and response.json()['detail'] == 'Sound manifest file invalid'


def test_missing_published_audio_is_not_reported_as_success(tmp_path, monkeypatch):
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path))
    (tmp_path / 'manifest.json').write_text(json.dumps({'revision':'missing','cues':{
        CUE:{'source':'custom','revision':'missing','storageName':CUE+'-'+'a'*24+'.mp3'}}}))
    client = TestClient(app)
    assert client.get('/api/sounds/files/'+CUE).status_code == 503
    assert client.get('/api/sounds/files/unknown-cue').status_code == 404


def test_corrupt_catalog_remains_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path))
    (tmp_path / 'manifest.json').write_text('{')
    response = TestClient(app).get('/api/sounds/manifest')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Sound manifest tidak dapat dibaca'
