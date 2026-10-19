"""Mobile Safari recovery simulation: WebAudio stuck 'interrupted', HTMLMedia must play
the same persisted custom Soft Tech sound after reload. No coin transactions.
"""
from pathlib import Path
import math
import struct
import wave
from playwright.sync_api import sync_playwright

OUT=Path('artifacts/uno-v11-ios-safari-audio')
OUT.mkdir(parents=True,exist_ok=True)
TONE=OUT/'iphone-splash.wav'
with wave.open(str(TONE),'wb') as file:
    file.setnchannels(1)
    file.setsampwidth(2)
    file.setframerate(22050)
    file.writeframes(b''.join(struct.pack('<h',int(6500*math.sin(
        n*2*math.pi*500/22050))) for n in range(3*22050)))

IOS_UA=('Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) '
        'Version/18.6 Mobile/15E148 Safari/604.1')
BROKEN_AUDIO_CONTEXT="""
  (()=>{
    const NativeAudioContext=window.AudioContext;
    if(!NativeAudioContext)return;
    window.AudioContext=class InterruptedContext extends NativeAudioContext {
      get state(){return 'interrupted';}
      resume(){return Promise.resolve();}
    };
  })();
"""

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(
        viewport={'width':390,'height':844},device_scale_factor=2,
        user_agent=IOS_UA,has_touch=True,is_mobile=True)
    context.add_init_script(BROKEN_AUDIO_CONTEXT)
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
    page.locator('#game-shell').wait_for(state='visible',timeout=25000)
    # Auto-boot must not create an AudioContext. The menu tap below activates
    # our deliberately interrupted WebAudio shim on iOS.
    assert page.evaluate("window.UNOLuckSound.webAudioState")=='inactive'

    # The WAV is decoded and saved even when WebAudio is interrupted.
    page.locator('#menu-open').click()
    page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
    splash=page.locator('details.studio-cue').first
    splash.locator('summary').click()
    splash.locator('input[type=file]').set_input_files(str(TONE))
    splash.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
    splash.locator('input[name="soft-tech-splash-screen-start"]').fill('.40')
    splash.locator('input[name="soft-tech-splash-screen-stop"]').fill('2.50')
    splash.locator('input[name="soft-tech-splash-screen-fadeIn"]').fill('.30')
    splash.locator('input[name="soft-tech-splash-screen-fadeOut"]').fill('.40')
    splash.locator('button',has_text='SAVE').click()
    splash.locator('.studio-status').get_by_text('Setting disimpan',exact=False).wait_for()
    setting=page.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen')")
    assert setting['custom'] and setting['start']==.4 and setting['stop']==2.5,setting
    assert setting['fadeIn']==.3 and setting['fadeOut']==.4

    # iOS autoplay is intentionally disabled. Custom file is still available
    # in IndexedDB after a reload and can be previewed after the user's tap.
    page.reload(wait_until='domcontentloaded')
    page.locator('#game-shell').wait_for(state='visible',timeout=25000)
    assert page.locator('#boot-start-sound').count()==0
    assert page.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen').custom")
    assert page.evaluate("window.UNOLuckSound.webAudioState")=='inactive'
    page.evaluate("""() => {
        window.__iosMediaPlays=0;
        const original=HTMLMediaElement.prototype.play;
        HTMLMediaElement.prototype.play=function(...args){
            window.__iosMediaPlays++;
            return original.apply(this,args);
        };
    }""")
    page.screenshot(path=str(OUT/'iphone-auto-splash.png'),full_page=True)
    assert page.evaluate("window.__iosMediaPlays")==0
    # HTML5 media remains usable after the introductory gesture. Preview
    # must not reject merely because AudioContext.state is interrupted.
    page.locator('#menu-open').click()
    page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
    splash=page.locator('details.studio-cue').first
    splash.locator('summary').click()
    previous=page.evaluate('window.__iosMediaPlays')
    splash.locator('button',has_text='PREVIEW').click()
    splash.locator('.studio-status').get_by_text('Preview aktif',exact=False).wait_for(timeout=12000)
    assert page.evaluate('window.__iosMediaPlays')>previous
    splash.locator('button',has_text='STOP').click()
    assert page.evaluate('window.__iosMediaPlays')>0
    assert not errors,errors
    context.close()
    browser.close()
print('PASS: iPhone interrupted WebAudio, hands-free silent splash, saved custom preview on gesture')

# Keep the dedicated first-tap BGM regression in the existing visual QA job.
# This intentionally uses an isolated iPhone context and Safari policy shim.
from runpy import run_path
run_path('tests/visual_qa_gameplay_music.py',run_name='__main__')
