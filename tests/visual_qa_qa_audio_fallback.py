"""QA-only recovery: a missing published Sound Cloud never traps iPhone splash.

The trusted PLAY tap is still required; local bundled audio is used only when
the server advertises explicit isolated QA fallback. No ledger or sound writes.
"""
import os
from playwright.sync_api import sync_playwright

BASE=os.environ.get("UNO_QA_URL","http://127.0.0.1:8080")
with sync_playwright() as pw:
    for name in ("chromium","webkit"):
        browser=getattr(pw,name).launch(headless=True)
        context=browser.new_context(
            viewport={"width":393,"height":852},
            is_mobile=True,has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
        )
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.route("**/api/sounds/manifest",lambda route:route.fulfill(
            json={"ready":False,"revision":"qa-offline","cues":{},
                  "sample_fallback_allowed":True,"error":"QA mirror unavailable"}
        ))
        page.goto(BASE+"/",wait_until="domcontentloaded")
        page.wait_for_function(
            "() => window.UNOLuckSoundStudio?.sampleAudioActive && !document.querySelector('#boot-play').disabled",
            timeout=25000
        )
        assert page.locator("#boot-play").is_visible()
        assert "Mode QA" in page.locator("#boot-play-error").inner_text()
        assert page.locator("#game-shell").get_attribute("aria-hidden")=="true"
        page.locator("#boot-play").click()
        page.wait_for_function(
            "() => !document.querySelector('#game-shell').classList.contains('is-booting')",
            timeout=30000
        )
        assert page.locator("#boot-overlay").is_hidden()
        assert not errors,errors
        print(name+": PASS isolated QA sample audio, explicit PLAY, game reachable without Sound Cloud")
        context.close()
        browser.close()
