"""Password login preserves token auth, origin checks and published data."""
import pytest
from fastapi.testclient import TestClient
from app import admin_auth, orbit, spin
from app.main import app

PASSWORD = 'qa-only-admin-password'
TOKEN = 'qa-existing-api-token-' + 'x' * 32


@pytest.fixture
def browser(monkeypatch, tmp_path):
    monkeypatch.setenv('UNO_ADMIN_PASSWORD_HASH', admin_auth.hash_password(PASSWORD))
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN', TOKEN)
    monkeypatch.setenv('UNO_SOUND_STORAGE_DIR', str(tmp_path / 'sounds'))
    monkeypatch.setenv('UNO_SPIN_DB_PATH', str(tmp_path / 'game.sqlite'))
    admin_auth._attempts.clear()
    spin.INITIALIZED.clear(); orbit._initialized.clear()
    with TestClient(app) as client:
        yield client
    admin_auth._attempts.clear()


def auth(value=PASSWORD):
    return {'x-uno-sound-admin': value}


def test_password_and_existing_token_share_authorization_without_writes(browser):
    audio = browser.get('/api/sounds/manifest').json()
    state = browser.get('/api/orbit/state').json()
    for credential in (PASSWORD, TOKEN):
        assert browser.get('/api/sounds/admin/check', headers=auth(credential)).json()['ok']
        data = browser.get('/api/admin/economy', headers=auth(credential)).json()
        assert data['revision'] == 0 and data['active'] is None
    assert browser.get('/api/sounds/manifest').json() == audio
    assert browser.get('/api/orbit/state').json() == state


def test_password_rejects_missing_wrong_and_cross_origin(browser):
    for credential in ('', 'incorrect-password', 'non-ascii-\u00e9-password'):
        headers = {'x-uno-sound-admin': credential.encode('utf-8')}
        assert browser.get('/api/sounds/admin/check', headers=headers).status_code == 403
    for credential in (PASSWORD, TOKEN):
        assert browser.get('/api/sounds/admin/check', headers=auth(credential) | {
            'origin': 'https://untrusted.example'}).status_code == 403


def test_password_hash_only_and_malformed_hash_fail_closed(browser, monkeypatch):
    monkeypatch.delenv('UNO_SOUND_ADMIN_TOKEN')
    assert browser.get('/api/sounds/admin/check', headers=auth()).status_code == 200
    monkeypatch.setenv('UNO_ADMIN_PASSWORD_HASH', 'not-a-valid-password-hash')
    assert browser.get('/api/sounds/admin/check', headers=auth()).status_code == 503
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN', TOKEN)
    assert browser.get('/api/sounds/admin/check', headers=auth(TOKEN)).status_code == 200
    monkeypatch.delenv('UNO_ADMIN_PASSWORD_HASH')
    monkeypatch.setenv('UNO_SOUND_ADMIN_TOKEN', 'short-token')
    assert browser.get('/api/sounds/admin/check', headers=auth('short-token')).status_code == 503


def test_password_attempt_limit_expires_without_blocking_api_token(browser, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(admin_auth.time, 'monotonic', lambda: now[0])
    for _ in range(admin_auth.ATTEMPTS):
        assert browser.get('/api/sounds/admin/check', headers=auth('wrong-password')).status_code == 403
    limited = browser.get('/api/sounds/admin/check', headers=auth())
    assert limited.status_code == 429 and limited.headers['retry-after'] == '60'
    assert browser.get('/api/sounds/admin/check', headers=auth(TOKEN)).status_code == 200
    now[0] += 61
    assert browser.get('/api/sounds/admin/check', headers=auth()).status_code == 200
    assert not admin_auth._attempts


def test_hash_has_random_salt_and_bounded_parameters():
    first, second = admin_auth.hash_password(PASSWORD), admin_auth.hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    assert admin_auth._decode(first)
    assert admin_auth._decode(first.replace('$600000$', '$999999999$')) is None
    with pytest.raises(ValueError):
        admin_auth.hash_password('short')
