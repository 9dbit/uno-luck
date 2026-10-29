"""Read-only remote acceptance: DEV-07 Railway pinned audio and splash gesture.

No game/wallet transactions, no Sound Cloud publishes, no admin calls.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright

BASE = os.environ.get(
    "UNO_DEV07_LIVE_URL",
    "https://uno-luck-dev07-audio-qa-staging.up.railway.app"
).rstrip("/")
OUT = Path("artifacts/uno-dev07-audio")
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED = {
    "soft-tech-splash-screen": "13dcd99e2497e6c3a8acd952721bae2b792cf4e5c4648f24d1070a09129d0795",
    "background-music": "24af8960ec23cb1e7e021279fd3cc415f05d118584f7300d66cbda919bb76dee",
}


def read(path):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "UnoLuck-DEV07-QA/1.0", "Accept": "application/json, audio/*"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        assert response.status == 200, (path, response.status)
        return response.read(), response.headers.get_content_type()


health, _ = read("/health")
assert json.loads(health)["ok"] is True
raw, _ = read("/api/sounds/manifest")
manifest = json.loads(raw)
assert manifest.get("ready") is True, manifest
assert manifest.get("mixer") == {"master": .9, "music": .22, "sfx": .85}, manifest.get("mixer")
for cue, digest in EXPECTED.items():
    data = manifest["cues"][cue]
    assert data["source"] == "custom" and data["url"].startswith("/api/sounds/files/"), data
    body, mime = read(data["url"])
    assert mime.startswith("audio/"), (cue, mime)
    assert hashlib.sha256(body).hexdigest() == digest, (cue, len(body))
    print(f"PASS {cue}: SHA-256={digest[:16]}, {len(body)} bytes")

with sync_playwright() as pw:
    for name in ("chromium", "webkit"):
        browser = getattr(pw, name).launch(headless=True)
        context = browser.new_context(
            viewport={"width": 393, "height": 852},
            is_mobile=True, has_touch=True,
        )
        page = context.new_page()
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=35000)
        page.locator("#boot-play").wait_for(state="visible", timeout=25000)
        page.locator("#boot-play").click(timeout=20000)
        page.wait_for_function(
            "() => !document.querySelector('#game-shell').classList.contains('is-booting')",
            timeout=45000,
        )
        assert page.locator("#boot-overlay").is_hidden(), name
        assert not failures, (name, failures)
        page.screenshot(path=str(OUT / (name+"-live-gameplay.png")), full_page=True)
        print(name + ": PASS actual Railway PLAY WITH SOUND -> gameplay")
        context.close()
        browser.close()
print("DEV07 remote Sound Cloud and gameplay acceptance PASS")
