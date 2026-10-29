"""DEV-08 exact-branch card-to-BET and emissive-title geometry QA.

This is a read-only visual test. It never starts rounds or mutates wallet values.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("UNO_QA_URL", "http://127.0.0.1:8080")
OUT = Path(os.environ.get("UNO_QA_OUTPUT", "artifacts/uno-dev08-card-kiss"))
OUT.mkdir(parents=True, exist_ok=True)

PORTRAIT = [
    ("iphone15pro", 393, 852),
    ("iphone-small", 320, 568),
    ("iphone-portrait-short", 393, 659),
    ("iphone-large", 430, 932),
]
MEASURE = r"""() => {
  const rect = sel => {
    const e = document.querySelector(sel);
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,
      width:r.width,height:r.height};
  };
  const cards = [...document.querySelectorAll('.result-cell .card3d')];
  const image = document.getElementById('dragon-title-art');
  const bet = document.querySelector('.result-bar');
  const panel = bet.getBoundingClientRect();
  return {
    cards: cards.map(c=>{const r=c.getBoundingClientRect();return {
      left:r.left,top:r.top,right:r.right,bottom:r.bottom,
      width:r.width,height:r.height};}),
    results:rect('.result-area'),
    bet:rect('.result-bar'),
    betFrameTop:panel.top - .1 * panel.height,
    title:rect('.title-area'),
    titleFilter:getComputedStyle(image).filter,
    titleLoaded:image.complete && image.naturalWidth > 0,
    version:document.querySelector('meta[name="uno-development"]')?.content,
    overflow:document.documentElement.scrollWidth-innerWidth,
    controls:['#spin-btn','#turbo-btn','#auto-btn','#bet-open']
      .map(s=>({selector:s,exists:!!document.querySelector(s),
        width:document.querySelector(s)?.getBoundingClientRect().width || 0}))
  };
}"""

with sync_playwright() as pw:
    for browser_name in os.environ.get("UNO_QA_ENGINES", "chromium,webkit").split(","):
        launch = {"headless": True}
        if browser_name == "chromium" and os.environ.get("UNO_QA_SYSTEM_CHROMIUM") == "1":
            launch.update(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        browser = getattr(pw, browser_name).launch(**launch)
        try:
            for name, width, height in PORTRAIT:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    is_mobile=True, has_touch=True, reduced_motion="reduce",
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                try:
                    page.goto(BASE + "/", wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_function(
                        "() => document.querySelectorAll('.result-cell .card3d').length === 3",
                        timeout=20000,
                    )
                    page.evaluate("""() => {
                      const shell=document.getElementById('game-shell');
                      shell.classList.remove('is-booting');
                      shell.removeAttribute('aria-hidden');
                      const boot=document.getElementById('boot-overlay');
                      if(boot) boot.hidden=true;
                    }""")
                    page.wait_for_function(
                        "() => {const a=document.getElementById('dragon-title-art');"
                        "return a && a.complete && a.naturalWidth > 0}",
                        timeout=15000,
                    )
                    now = page.evaluate(MEASURE)
                    assert now["version"] == "DEV-08 v1.1.74r3", now
                    assert now["titleLoaded"] and "brightness(1.34)" in now["titleFilter"], now
                    assert "drop-shadow" in now["titleFilter"], now
                    assert len(now["cards"]) == 3, now
                    assert now["overflow"] <= 3, (browser_name, name, "horizontal-overflow", now)
                    assert all(c["width"] >= 65 and c["height"] > c["width"] for c in now["cards"]), now
                    assert all(c["left"] >= -6 and c["right"] <= width+6 for c in now["cards"]), now
                    assert all(c["bottom"] <= now["bet"]["top"] + 2 for c in now["cards"]), now
                    center = now["cards"][1]
                    gap = now["betFrameTop"] - center["bottom"]
                    assert -3 <= gap <= 8, (browser_name, name, "not-kissing", gap, now)
                    assert all(x["exists"] and x["width"] >= 20 for x in now["controls"]), now
                    # Compare same loaded page without only the latest DEV-08 CSS:
                    # the bottom-aligned card must not be smaller than the baseline.
                    page.evaluate("""() => {
                      document.querySelector('link[href*="dev08-card-spin-layout"]').disabled = true;
                    }""")
                    baseline = page.evaluate(MEASURE)
                    # An old oversized card could protrude through the BET rim.
                    # Compare against the baseline size that could actually fit
                    # above that rim, not its overlapping/hidden area.
                    prior = baseline["cards"][1]
                    prior_overshoot = max(0.0, prior["bottom"] - baseline["betFrameTop"])
                    safe_prior_width = prior["width"] - prior_overshoot * (2 / 3)
                    assert center["width"] >= safe_prior_width - 1, (
                        browser_name, name, "fitted-card-size-regression",
                        center["width"], safe_prior_width, prior_overshoot
                    )
                    page.evaluate("""() => {
                      document.querySelector('link[href*="dev08-card-spin-layout"]').disabled = false;
                    }""")
                    page.screenshot(path=str(OUT / f"{browser_name}-{name}.png"), full_page=True)
                    assert not errors, (browser_name, name, errors)
                    print("PASS", browser_name, name,
                          "centerWidth", round(center["width"], 1),
                          "baselineFitWidth", round(safe_prior_width, 1),
                          "cardToBetFrameGap", round(gap, 1),
                          "titleEmissive", True, flush=True)
                finally:
                    context.close()
        finally:
            browser.close()
