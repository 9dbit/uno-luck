from fastapi.testclient import TestClient
from app.main import app, UI_RELEASE


def test_shell_and_release_cannot_be_reused_without_network():
    client = TestClient(app)
    for path in ('/', '/?_uno_release=old', '/admin', '/classic', '/spin-legacy'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
    shell = client.get('/')
    assert f'name="uno-release" content="{UI_RELEASE}"' in shell.text
    assert '__UNO_RELEASE__' not in shell.text
    version = client.get('/api/ui-version')
    assert version.json() == {'release': UI_RELEASE}
    assert version.headers['cache-control'] == 'no-store'


def test_old_and_new_asset_urls_revalidate_without_deleting_player_data():
    client = TestClient(app)
    for path in ('/assets/orbit.js?v=1142', '/assets/orbit.js?v=1144',
                 '/assets/pwa-update.js?v=1144', '/assets/spin-manifest.webmanifest'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-cache, must-revalidate'
    source = client.get('/assets/pwa-update.js').text
    assert 'localStorage.clear' not in source and 'indexedDB.deleteDatabase' not in source
