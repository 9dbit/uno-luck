from fastapi.testclient import TestClient
from app.main import app


def test_admin_page_routes_without_game_boot():
    client=TestClient(app)
    for path in ('/admin','/admin/'):
        response=client.get(path)
        assert response.status_code==200
        assert response.headers['cache-control']=='no-store'
        assert '/assets/admin.js?v=1143' in response.text
        assert '/assets/orbit.js' not in response.text
        assert 'boot-play' not in response.text
