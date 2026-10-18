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
        browser=playwright.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
        page.locator('#boot-start-sound').click()
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
        assert editor.locator('input[type="range"].studio-range').count()==48
        fourth=editor.locator('details.studio-cue').nth(3)
        fourth.locator('summary').click()
        fourth.locator('input[type=file]').set_input_files(str(tone))
        fourth.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        slider=fourth.locator('input[name="push-button-start-slider"]')
        slider.evaluate("""el => {el.value='0.10';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
        assert fourth.locator('input[name="push-button-start"]').input_value()=='0.1'
        assert 'START' in fourth.locator('.studio-timeline-label').inner_text()
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
        music=editor.locator('details.studio-cue').nth(2)
        music.locator('summary').click()
        music.locator('input[type=file]').set_input_files(str(tone))
        music.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        repeat=music.locator('input[name="background-music-repeat"]')
        assert repeat.is_checked(), 'Repeat default must be ON'
        repeat.uncheck()
        assert page.evaluate("window.UNOLuckSoundStudio.profile('background-music').repeat") is False
        music.locator('input[name="background-music-stop-slider"]').evaluate(
            """el => {el.value='0.45';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
        assert music.locator('input[name="background-music-stop"]').input_value()=='0.45'
        music.locator('button',has_text='SAVE').click()
        music.locator('.studio-status').get_by_text('Setting disimpan',exact=False).wait_for()
        page.evaluate("""() => {
            window.__bgmSources=[];
            const old=AudioBufferSourceNode.prototype.start;
            AudioBufferSourceNode.prototype.start=function(...args){
                window.__bgmSources.push({loop:this.loop,startArgs:args});
                return old.apply(this,args);
            };
        }""")
        assert page.evaluate("window.UNOLuckSoundStudio.play('background-music',{looping:true})")
        off=page.evaluate('window.__bgmSources[window.__bgmSources.length-1]')
        assert not off['loop'] and abs(off['startArgs'][2]-.45)<.02, off
        repeat.check()
        assert page.evaluate("window.UNOLuckSoundStudio.profile('background-music').repeat") is True
        assert page.evaluate("window.UNOLuckSoundStudio.play('background-music',{looping:true})")
        on=page.evaluate('window.__bgmSources[window.__bgmSources.length-1]')
        assert on['loop'] and len(on['startArgs'])==2, on
        page.evaluate('window.UNOLuckSoundStudio.stopLoop()')
        page.screenshot(path=str(OUTPUT/'settings-390x844.png'),full_page=True)
        # Regression: custom splash must persist in IndexedDB and actually
        # call AudioBufferSourceNode.start after a new user gesture on reload.
        splash=editor.locator('details.studio-cue').first
        splash.locator('summary').click()
        splash.locator('input[type=file]').set_input_files(str(tone))
        splash.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        page.reload(wait_until='domcontentloaded')
        stored=page.evaluate("window.UNOLuckSoundStudio.profile('push-button')")
        assert stored['start']==0.1 and stored['fileName']=='qa-tone.wav'
        bgm=page.evaluate("window.UNOLuckSoundStudio.profile('background-music')")
        assert bgm['repeat'] is True and abs(bgm['stop']-.45)<.02, bgm
        assert page.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen').custom")
        assert page.locator('#boot-sound-status').inner_text().find('qa-tone.wav')!=-1
        page.evaluate("""() => {
            window.__splashStartCount=0;
            const start=AudioBufferSourceNode.prototype.start;
            AudioBufferSourceNode.prototype.start=function(...args){
                window.__splashStartCount++;
                return start.apply(this,args);
            };
        }""")
        page.screenshot(path=str(OUTPUT/'splash-audio-gate-after-reload.png'),full_page=True)
        page.locator('#boot-start-sound').click()
        for _ in range(80):
            if page.evaluate('window.__splashStartCount || 0') > 0:
                break
            page.wait_for_timeout(125)
        assert page.evaluate('window.__splashStartCount || 0') > 0, (
            'Uploaded splash file never started AudioBufferSourceNode after tap: '
            +page.locator('#boot-sound-status').inner_text())
        page.locator('#boot-sound-gate').wait_for(state='hidden')
        page.locator('#game-shell').wait_for(state='visible',timeout=25000)
        assert not errors, 'Uncaught browser errors: '+str(errors)
        browser.close()
    print('PASS: 48 sliders, trim/fades, BGM repeat OFF/ON real source looping, persistence and splash reload')

if __name__=='__main__':
    main()
