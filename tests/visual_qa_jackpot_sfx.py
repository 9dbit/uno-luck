"""UI-only jackpot sound regression: custom tier mapping, trim/fades and cancellation.
Uses gallery preview to avoid touching the server ledger or user coins.
"""
from pathlib import Path
import math
import struct
import wave
from playwright.sync_api import sync_playwright

ROOT=Path('artifacts/uno-v11-jackpot-audio')
ROOT.mkdir(parents=True,exist_ok=True)
SOUND={rank:ROOT/f'custom-jackpot-{rank}.wav' for rank in range(1,6)}
for rank,filename in SOUND.items():
    duration=6.0 if rank==5 else 1.5+rank*.16
    with wave.open(str(filename),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
        out.writeframes(b''.join(struct.pack('<h',int(3800*math.sin(
            2*math.pi*(190+rank*65)*n/16000))) for n in range(int(duration*16000))))

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':390,'height':844})
    errs=[]
    page.on('pageerror',lambda e:errs.append(str(e)))
    page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
    page.locator('#boot-play').click(timeout=17000)
    page.locator('#game-shell').wait_for(state='visible',timeout=25000)
    page.goto('http://127.0.0.1:8080/admin',wait_until='domcontentloaded')
    page.get_by_role('button',name='Sound Studio · 12 Custom Sound Effects').click()
    editor=page.locator('.sound-studio')
    for rank in range(1,6):
        row=editor.locator('details.studio-cue').nth(6+rank)
        row.locator('summary').click()
        row.locator('input[type=file]').set_input_files(str(SOUND[rank]))
        for _ in range(100):
            if page.evaluate('(k)=>Boolean(window.UNOLuckSoundStudio.profile(k).custom)',f'jackpot-{rank}'):
                break
            page.wait_for_timeout(100)
        assert page.evaluate('(k)=>Boolean(window.UNOLuckSoundStudio.profile(k).custom)',f'jackpot-{rank}'), (
            rank,row.locator('.studio-status').inner_text())
        start=.20
        stop=4.9 if rank==5 else 1.12
        row.locator(f'input[name="jackpot-{rank}-start"]').fill(str(start))
        row.locator(f'input[name="jackpot-{rank}-stop"]').fill(str(stop))
        row.locator(f'input[name="jackpot-{rank}-fadeIn"]').fill('.12')
        row.locator(f'input[name="jackpot-{rank}-fadeOut"]').fill('.18')
        row.locator('button',has_text='SAVE').click()
        row.locator('.studio-status').get_by_text('Setting disimpan',exact=False).wait_for()
        saved=page.evaluate('(key)=>window.UNOLuckSoundStudio.profile(key)',f'jackpot-{rank}')
        assert saved['custom'] and abs(saved['start']-.2)<.02
        assert abs(saved['stop']-stop)<.02 and saved['fadeIn']==.12 and saved['fadeOut']==.18
        row.locator('summary').click()
    page.locator('#modal').evaluate('(el)=>el.close()')

    # Settings must survive a real reload. Safari still needs a new sound gesture.
    page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
    page.locator('#boot-play').click(timeout=17000)
    page.locator('#game-shell').wait_for(state='visible',timeout=25000)
    page.locator('#profile-btn').click()
    page.locator('#modal-close').click()
    page.locator('#game-shell').wait_for(state='visible',timeout=25000)
    page.evaluate("""() => {
      window.__jackpotStarts=[]; window.__jackpotStops=0;window.__synthCount=0;
      const begin=AudioBufferSourceNode.prototype.start;
      AudioBufferSourceNode.prototype.start=function(...args){
        window.__jackpotStarts.push({duration:this.buffer?.duration,offset:args[1],clip:args[2]});
        return begin.apply(this,args);
      };
      const stop=AudioBufferSourceNode.prototype.stop;
      AudioBufferSourceNode.prototype.stop=function(...args){
        window.__jackpotStops++;return stop.apply(this,args);
      };
      const osc=OscillatorNode.prototype.start;
      OscillatorNode.prototype.start=function(...args){
        window.__synthCount++;return osc.apply(this,args);
      };
    }""")

    for rank in range(1,6):
        key=f'jackpot-{rank}'
        assert page.evaluate('(k)=>window.UNOLuckSoundStudio.profile(k).custom',key)
        prior=page.evaluate('window.__jackpotStarts.length')
        synth=page.evaluate('window.__synthCount')
        page.evaluate('(n)=>{window.UNOLuckCelebration.present(null,{preview:true,rank:n});}',rank)
        for _ in range(90):
            if page.evaluate('window.UNOLuckSoundStudio.activeCelebrationCue')==key:
                break
            page.wait_for_timeout(100)
        assert page.evaluate('window.UNOLuckSoundStudio.activeCelebrationCue')==key, (
            rank,page.evaluate('window.UNOLuckSoundStudio.lastError'))
        events=page.evaluate('(offset)=>window.__jackpotStarts.slice(offset)',prior)
        matches=[x for x in events if x['offset'] is not None and abs(x['offset']-.2)<.025]
        assert len(matches)==1,(rank,events)
        current=matches[0]
        assert abs(current['duration']-(6.0 if rank==5 else 1.5+rank*.16))<.06,(rank,current)
        assert abs(current['clip']-(4.7 if rank==5 else .92))<.025,(rank,current)
        assert page.evaluate('window.__synthCount')==synth, 'Custom JACKPOT must not add cinematicImpact oscillators'
        assert page.locator('#celebration-overlay').get_attribute('data-rank')==str(rank)
        if rank==5:
            page.wait_for_timeout(3100)
            assert page.evaluate('window.UNOLuckCelebration.active'), 'Long custom jackpot must outlive short default rank timer'
        stops=page.evaluate('window.__jackpotStops')
        page.locator('#celebration-continue').click()
        assert not page.evaluate('window.UNOLuckCelebration.active')
        assert page.evaluate('window.__jackpotStops')>stops, 'CONTINUE must stop custom JACKPOT audio'
        assert page.evaluate('window.UNOLuckSoundStudio.activeCelebrationCue') is None
    page.screenshot(path=str(ROOT/'all-five-jackpot-audio-verified.png'),full_page=True)
    assert not errs,errs
    browser.close()
print('PASS: 5 distinct uploaded jackpot cues; persisted trim/fades; no synthetic layering; long audio lifecycle; CONTINUE stops source')
