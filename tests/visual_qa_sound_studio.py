"""Automated Chromium responsive smoke QA for UNO LUCK v1.1 Sound Studio.
Only GETs the test server. No betting transactions or wallet mutation.
"""
from pathlib import Path
import math
import struct
import wave
from playwright.sync_api import sync_playwright

OUTPUT=Path('artifacts/uno-v11-sound-studio')
OUTPUT.mkdir(parents=True,exist_ok=True)
SIZES=[(320,568),(390,844),(430,932),(768,1024),(844,390)]

def bound(locator):
    r=locator.bounding_box()
    assert r is not None, 'Element missing bounding rectangle'
    return r

def main():
    tone=OUTPUT/'qa-tone.wav'
    with wave.open(str(tone),'wb') as dst:
        dst.setnchannels(1);dst.setsampwidth(2);dst.setframerate(22050)
        samples=(int(8000*math.sin(2*math.pi*523.25*n/22050)) for n in range(22050))
        dst.writeframes(b''.join(struct.pack('<h',n) for n in samples))
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
        page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
        page.locator('#game-shell').wait_for(state='visible',timeout=25000)
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(110)
            left=bound(page.locator('#turbo-btn'))
            right=bound(page.locator('#auto-btn'))
            spin=bound(page.locator('#spin-btn'))
            for item in (left,right,spin):
                assert item['width']>20 and item['height']>20, (width,height,item)
                assert item['x']>=-1 and item['x']+item['width']<=width+1,(width,height,item)
            assert left['x']+left['width'] < spin['x'],(width,height,'TURBO overlaps SPIN')
            assert spin['x']+spin['width'] < right['x'],(width,height,'SPIN overlaps AUTO')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),(width,height,'horizontal overflow')
            for selector in ('#turbo-btn','#auto-btn'):
                assert page.locator(selector).evaluate('(el)=>el.scrollWidth <= el.clientWidth+2'),selector
            page.screenshot(path=str(OUTPUT/f'game-{width}x{height}.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.locator('#menu-open').click()
        page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
        editor=page.locator('.sound-studio')
        assert editor.locator('details.studio-cue').count()==12
        fourth=editor.locator('details.studio-cue').nth(3)
        fourth.locator('summary').click()
        fourth.locator('input[type=file]').set_input_files(str(tone))
        fourth.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        fourth.locator('input[name="push-button-start"]').fill('0.10')
        fourth.locator('input[name="push-button-stop"]').fill('0.75')
        fourth.locator('input[name="push-button-fadeIn"]').fill('0.05')
        fourth.locator('input[name="push-button-fadeOut"]').fill('0.15')
        fourth.locator('button',has_text='SAVE').click()
        fourth.locator('.studio-status').get_by_text('Setting disimpan',exact=False).wait_for()
        values=page.evaluate("window.UNOLuckSoundStudio.profile('push-button')")
        assert values['custom'] and values['start']==0.1 and values['stop']==0.75
        assert values['fadeIn']==0.05 and values['fadeOut']==0.15
        fourth.locator('button',has_text='PREVIEW').click()
        fourth.locator('.studio-status').get_by_text('Preview aktif',exact=False).wait_for(timeout=10000)
        fourth.locator('button',has_text='STOP').click()
        page.screenshot(path=str(OUTPUT/'settings-390x844.png'),full_page=True)
        page.reload(wait_until='domcontentloaded')
        stored=page.evaluate("window.UNOLuckSoundStudio.profile('push-button')")
        assert stored['start']==0.1 and stored['fileName']=='qa-tone.wav'
        assert not errors, 'Uncaught browser errors: '+str(errors)
        browser.close()
    print('PASS: responsive layouts, pill gaps, audio file import, trim/fades, preview and reload persistence')

if __name__=='__main__':
    main()
