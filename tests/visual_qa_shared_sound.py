"""Cross-device Sound Cloud QA: desktop imports local drafts, mobile plays published audio.

Two isolated browser contexts share no localStorage/IndexedDB. The published
audio and trim metadata must be identical on both. No spin or wallet actions.
"""
from pathlib import Path
import math
import os
import struct
import wave

from playwright.sync_api import sync_playwright

ARTIFACTS=Path("artifacts/uno-v11-shared-sound")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ADMIN=os.environ.get("UNO_SOUND_ADMIN_TOKEN", "")
assert len(ADMIN)>=32, "CI requires a test-only sound cloud admin token"

FILE=ARTIFACTS/"shared-desktop-sfx.wav"
with wave.open(str(FILE),"wb") as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050)
    w.writeframes(b"".join(struct.pack("<h",int(7000*math.sin(
        2*math.pi*420*n/22050))) for n in range(22050*3)))

URL="http://127.0.0.1:8080/"
IOS_UA=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.6 Mobile/15E148 Safari/604.1")


def open_studio(page):
    page.locator("#menu-open").click()
    page.get_by_role("button",name="Sound Studio · 12 Custom Sound Effects").click()
    return page.locator(".sound-studio")


with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    desktop=browser.new_context(viewport={"width":1200,"height":900})
    d=desktop.new_page()
    errors=[]
    d.on("pageerror",lambda err:errors.append(str(err)))
    d.goto(URL,wait_until="domcontentloaded")
    d.locator("#boot-start-sound").click()
    d.locator("#game-shell").wait_for(state="visible",timeout=26000)

    studio=open_studio(d)
    for index,key in [(0,"soft-tech-splash-screen"),(2,"background-music"),(9,"jackpot-3")]:
        cue=studio.locator("details.studio-cue").nth(index)
        cue.locator("summary").click()
        cue.locator("input[type=file]").set_input_files(str(FILE))
        cue.locator(".studio-status").get_by_text("Audio tersimpan:",exact=False).wait_for(timeout=12000)
        cue.locator(f'input[name="{key}-start"]').fill("0.35")
        cue.locator(f'input[name="{key}-stop"]').fill("2.40")
        cue.locator(f'input[name="{key}-fadeIn"]').fill("0.30")
        cue.locator(f'input[name="{key}-fadeOut"]').fill("0.40")
        cue.locator("button",has_text="SAVE").click()
        cue.locator(".studio-status").get_by_text("Setting disimpan",exact=False).wait_for(timeout=12000)
        if key=="background-music":
            cue.locator('input[name="background-music-repeat"]').uncheck()
        cue.locator("summary").click()

    admin=studio.locator(".studio-cloud-admin")
    admin.locator("summary").click()
    admin.locator('input[type="password"]').fill(ADMIN)
    admin.get_by_role("button",name="VERIFIKASI KUNCI").click()
    admin.locator(".studio-cloud-status").get_by_text("Admin terverifikasi",exact=False).wait_for(timeout=15000)
    admin.get_by_role("button",name="☁ PUBLISH ALL 12 SOUND LIST").click()
    admin.locator(".studio-cloud-status").get_by_text(
        "3 sound desktop berhasil dipublikasikan",exact=False).wait_for(timeout=35000)
    server_manifest=d.request.get(URL+"api/sounds/manifest").json()
    assert server_manifest["ready"] and len(server_manifest["cues"])==3
    assert server_manifest["cues"]["background-music"]["repeat"] is False
    assert server_manifest["mixer"]["master"]>=0
    for key in ["soft-tech-splash-screen","background-music","jackpot-3"]:
        item=server_manifest["cues"][key]
        assert abs(item["start"]-.35)<.01 and abs(item["stop"]-2.4)<.01
        assert item["fadeIn"]==.3 and item["fadeOut"]==.4
        remote=d.request.get(URL+item["url"].lstrip("/"))
        assert remote.ok and remote.body()==FILE.read_bytes()

    # Mobile is a completely different browser context: no desktop uploads
    # exist in this context. Only server manifest + files can supply audio.
    mobile=browser.new_context(
        viewport={"width":390,"height":844},device_scale_factor=2,
        is_mobile=True,has_touch=True,user_agent=IOS_UA)
    m=mobile.new_page()
    m.on("pageerror",lambda err:errors.append(str(err)))
    m.goto(URL,wait_until="domcontentloaded")
    for _ in range(100):
        if m.locator("#boot-start-sound").is_enabled():break
        m.wait_for_timeout(100)
    assert m.locator("#boot-start-sound").is_enabled()
    assert "SINKRON CLOUD" in m.locator("#boot-sound-status").inner_text()
    assert m.evaluate("window.UNOLuckSoundStudio.publishedProfile('soft-tech-splash-screen').source")=="custom"
    assert m.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen').stop")==2.4
    assert m.locator('audio[src*="/api/sounds/files/soft-tech-splash-screen"]').count()==1
    m.screenshot(path=str(ARTIFACTS/"iphone-shared-softtech-ready.png"),full_page=True)
    m.locator("#boot-start-sound").click()
    m.locator("#boot-sound-gate").wait_for(state="hidden",timeout=16000)
    m.locator("#game-shell").wait_for(state="visible",timeout=26000)
    assert m.evaluate("window.UNOLuckSoundStudio.mediaUnlocked")
    assert m.evaluate("window.UNOLuckSoundStudio.getRepeat('background-music')") is False

    # Publish a new desktop trim and ensure an already-open iPhone receives it.
    d.locator("#modal").evaluate("(el)=>el.close()")
    studio=open_studio(d)
    splash=studio.locator("details.studio-cue").first
    splash.locator("summary").click()
    splash.locator('input[name="soft-tech-splash-screen-stop"]').fill("2.10")
    capture=[]
    d.on("request",lambda req: capture.append({
      "method":req.method,
      "settings":req.headers.get("x-uno-sound-settings"),
      "url":req.url.split("/")[-1],
    }) if "/api/sounds/cues/soft-tech-splash-screen" in req.url else None)
    assert splash.locator('input[name="soft-tech-splash-screen-stop"]').input_value()=="2.10"
    splash.locator("button",has_text="SAVE").click()
    splash.locator(".studio-status").get_by_text("Setting disimpan di CLOUD",exact=False).wait_for(timeout=16000)
    local=d.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen')")
    from_server=d.request.get(URL+"api/sounds/manifest").json()["cues"]["soft-tech-splash-screen"]
    assert from_server["stop"]==2.1, ("Desktop publish did not reach server",
        {"local":local,"requests":capture,"server":from_server})
    assert m.evaluate("window.UNOLuckSoundStudio.publishedProfile('soft-tech-splash-screen').stop")==2.4
    assert m.evaluate("window.UNOLuckSoundStudio.syncCloud(true)")
    fresh=m.evaluate("window.UNOLuckSoundStudio.publishedProfile('soft-tech-splash-screen')")
    assert fresh["stop"]==2.1, ("Mobile failed to refresh shared sound",fresh,from_server)
    assert m.evaluate("window.UNOLuckSoundStudio.profile('jackpot-3').fadeOut")==.4
    assert m.evaluate("window.UNOLuckSoundStudio.cloudStatus().online")==3
    m.screenshot(path=str(ARTIFACTS/"iphone-shared-audio-after-update.png"),full_page=True)

    assert not errors,errors
    browser.close()
print("PASS: desktop local drafts publish all; mobile has exact file, trim, fade, repeat and mixer; live refresh works")
