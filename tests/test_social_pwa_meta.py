"""Social sharing + installable PWA contract for the Dragon Spin homepage."""
from __future__ import annotations
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
import pytest
from app.main import app

BASE = Path(__file__).resolve().parents[1] / "app" / "static"
DOMAIN = "https://uno-luck-web-staging.up.railway.app"
ASSET = "/assets/branding/uno-luck-og-1200x630.jpg"


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.link = {}, {}
    def handle_starttag(self, tag, attrs):
        p = dict(attrs)
        if tag == "meta":
            self.meta[p.get("property", p.get("name", p.get("charset", "")))] = p.get("content", "")
        if tag == "link":
            self.link.setdefault(p.get("rel"), []).append(p)


def test_telegram_instagram_open_graph_preview_is_absolute_and_valid():
    doc = Head()
    doc.feed((BASE / "orbit-index.html").read_text())
    assert doc.meta["og:type"] == "website"
    assert doc.meta["og:title"].startswith("UNO LUCK")
    assert doc.meta["og:site_name"] == "UNO LUCK"
    assert doc.meta["og:url"] == DOMAIN + "/"
    assert doc.meta["og:image"] == doc.meta["og:image:secure_url"]
    assert doc.meta["og:image"].startswith(DOMAIN + ASSET + "?v=")
    assert doc.meta["og:image:type"] == "image/jpeg"
    assert doc.meta["og:image:width"] == "1200"
    assert doc.meta["og:image:height"] == "630"
    assert doc.meta["twitter:card"] == "summary_large_image"
    assert doc.meta["twitter:image"] == doc.meta["og:image"]
    assert "instagram" not in doc.meta  # Instagram shares Open Graph, not a separate tag.
    assert any(x.get("href") == DOMAIN + "/" for x in doc.link["canonical"])


def test_android_and_iphone_receive_real_touch_icons():
    doc = Head()
    doc.feed((BASE / "orbit-index.html").read_text())
    assert any("spin-manifest.webmanifest" in x.get("href", "")
               for x in doc.link["manifest"])
    assert any("uno-luck-icon-180.png" in x.get("href", "")
               for x in doc.link["apple-touch-icon"])
    data = json.loads((BASE / "spin-manifest.webmanifest").read_text())
    assert data["start_url"] == "/" and data["scope"] == "/"
    assert data["display"] == "standalone"
    assert data["theme_color"] == "#160002"
    # Binary media is generated during the Railway Docker image build.
    # GitHub's source-only pytest job intentionally does not ship Pillow.
    script = (BASE.parents[1] / "scripts" / "build_social_assets.py").read_text()
    for icon in ("512", "192", "180", "48", "32"):
        assert icon in script
    assert "1200" in script and "630" in script
    assert "uno-luck-icon-512-maskable.png" in script
    assert any("512-maskable" in entry["src"] and entry["purpose"] == "maskable"
               for entry in data["icons"])


def test_social_assets_and_pwa_manifest_are_http_served():
    # A standalone source checkout has no compiled binary assets, whereas
    # Railway generates them inside the Docker build before app startup.
    if not (BASE / "branding" / "uno-luck-og-1200x630.jpg").exists():
        pytest.skip("Image assets are built inside the Railway Docker image")
    with TestClient(app) as browser:
        response = browser.get("/")
        assert response.status_code == 200
        assert "og:image" in response.text
        assert "apple-touch-icon" in response.text
        for url, content_type in [
            (ASSET, "image/jpeg"),
            ("/assets/branding/uno-luck-icon-180.png", "image/png"),
            ("/assets/branding/uno-luck-icon-512-maskable.png", "image/png"),
            ("/assets/spin-manifest.webmanifest", "application/manifest+json"),
        ]:
            result = browser.get(url)
            assert result.status_code == 200, (url, result.text[:300])
            if "webmanifest" in url:
                assert result.json()["short_name"] == "UNO LUCK"
            else:
                assert result.headers["content-type"].startswith(content_type), url
                assert len(result.content) > 1500, url
