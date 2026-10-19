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
        page.locator('#boot-play').click(timeout=17000)
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
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight+2'),(width,height,'vertical overflow')
            assert page.locator('#boot-sound-gate').count()==0
            game=bound(page.locator('#game-shell'))
            area=bound(page.locator('.wheel-area'))
            stage=bound(page.locator('.wheel-stage'))
            assert game['y']>=-1 and game['y']+game['height']<=height+2,(width,height,'PWA viewport')
            assert stage['y']>=area['y']-2,(width,height,'wheel top clipped')
            assert stage['y']+stage['height']<=area['y']+area['height']+2,(width,height,'wheel bottom clipped')
            for selector in ('#turbo-btn','#auto-btn'):
                assert page.locator(selector).evaluate('(el)=>el.scrollWidth <= el.clientWidth+2'),selector
            page.screenshot(path=str(OUTPUT/f'game-{width}x{height}.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.locator('#orbit-ring .led-slot').count()==9
        assert page.locator('#orbit-ring').evaluate("(el)=>el.classList.contains('led-ambient')")
        initial=page.locator('#orbit-ring .led-slot').evaluate_all(
            "(nodes)=>nodes.map(n=>n.dataset.color+':'+n.querySelector('.led-symbol').textContent)")
        before_index=page.locator('#orbit-ring').get_attribute('data-led-frame')
        slots_before=page.locator('#orbit-ring .led-slot').evaluate_all(
            "(nodes)=>nodes.map(n=>{const r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})")
        page.wait_for_timeout(1150)
        after=page.locator('#orbit-ring .led-slot').evaluate_all(
            "(nodes)=>nodes.map(n=>n.dataset.color+':'+n.querySelector('.led-symbol').textContent)")
        after_index=page.locator('#orbit-ring').get_attribute('data-led-frame')
        slots_after=page.locator('#orbit-ring .led-slot').evaluate_all(
            "(nodes)=>nodes.map(n=>{const r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})")
        assert initial==after, 'LED glyphs/colors must remain stationary during idle'
        assert before_index!=after_index, 'Illuminated LED panel must advance clockwise'
        assert page.locator('#orbit-ring .led-illuminated').count()==1
        assert slots_before==slots_after, 'Idle must never rotate the nine metal frames'
        page.locator('#menu-open').click()
        page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
        editor=page.locator('.sound-studio')
        assert editor.locator('details.studio-cue').count()==12
        assert editor.locator('input[type="range"].studio-range').count()==61
        fourth=editor.locator('details.studio-cue').nth(3)
        fourth.locator('summary').click()
        fourth.locator('input[type=file]').set_input_files(str(tone))
        fourth.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        slider=fourth.locator('input[name="push-button-start-slider"]')
        slider.evaluate("""el => {el.value='0.10';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
        assert fourth.locator('input[name="push-button-start"]').input_value()=='0.1'
        fourth.locator('input[name="push-button-duration-slider"]').evaluate(
            """el => {el.value='0.65';el.dispatchEvent(new Event('input',{bubbles:true}));}""")
        assert fourth.locator('input[name="push-button-stop"]').input_value()=='0.75'
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
        # Auto boot never plays sound without a gesture. File remains stored
        # across reload; Sound Studio PREVIEW after a user click can play it.
        splash=editor.locator('details.studio-cue').first
        splash.locator('summary').click()
        splash.locator('input[type=file]').set_input_files(str(tone))
        splash.locator('.studio-status').get_by_text('Audio tersimpan:',exact=False).wait_for(timeout=10000)
        page.reload(wait_until='domcontentloaded')
        page.locator('#boot-play').click(timeout=17000)
        page.locator('#game-shell').wait_for(state='visible',timeout=25000)
        assert page.locator('#boot-start-sound').count()==0
        stored=page.evaluate("window.UNOLuckSoundStudio.profile('push-button')")
        assert stored['start']==0.1 and stored['fileName']=='qa-tone.wav'
        assert page.evaluate("window.UNOLuckSoundStudio.profile('soft-tech-splash-screen').custom")
        page.evaluate("""() => {
            window.__splashStartCount=0;
            const start=AudioBufferSourceNode.prototype.start;
            AudioBufferSourceNode.prototype.start=function(...args){
                window.__splashStartCount++;
                return start.apply(this,args);
            };
        }""")
        assert page.evaluate("window.__splashStartCount")==0, 'Autoplay audio must be blocked'
        page.locator('#menu-open').click()
        page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
        storedSplash=page.locator('.sound-studio details.studio-cue').first
        storedSplash.locator('summary').click()
        storedSplash.locator('button',has_text='PREVIEW').click()
        storedSplash.locator('.studio-status').get_by_text('Preview aktif',exact=False).wait_for(timeout=10000)
        assert page.evaluate("window.__splashStartCount")>0
        storedSplash.locator('button',has_text='STOP').click()
        page.screenshot(path=str(OUTPUT/'auto-splash-reload.png'),full_page=True)
        assert not errors, 'Uncaught browser errors: '+str(errors)
        browser.close()
    print('PASS: responsive Sound Studio, trim/fades, music repeat and auto boot with gesture-only preview')

if __name__=='__main__':
    main()
