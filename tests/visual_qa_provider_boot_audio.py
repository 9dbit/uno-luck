"""Real Chromium boot/audio checks with tracked media and the unchanged Play gate.

The loopback fixture isolates the audio/splash UI, not gameplay or wallet state.
Actual Genesis/native engine conformance is a separate source-verified suite.
No media play result, browser audio policy, or boot DOM state is mocked.
"""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit, unquote

from playwright.sync_api import sync_playwright

STATIC = Path(__file__).resolve().parents[1] / 'app/static'
OUT = Path(os.environ.get('UNO_BOOT_AUDIO_OUT', 'artifacts/provider-boot-audio'))
OUT.mkdir(parents=True, exist_ok=True)
ASSET = STATIC / 'audio/music-loop.mp3'
ASSET_SHA = hashlib.sha256(ASSET.read_bytes()).hexdigest()
CUE = 'soft-tech-splash-screen'
BUNDLED = '/assets/audio/music-loop.mp3'
PUBLISHED = '/api/sounds/files/' + CUE
CASES = ('empty', 'unconfigured', 'catalog_outage', 'published',
         'broken_custom', 'missing_local_draft', 'music_off', 'missing_bundled')
HTML = b'''<!doctype html><html><meta charset="utf-8"><title>UNO boot audio qualification</title>
<style>[hidden]{display:none!important}.is-booting{visibility:hidden}body{background:#151322;color:#fff;font:18px sans-serif;text-align:center}img{max-width:250px}button{font-size:24px;padding:20px}#boot-loading-track{width:280px;margin:auto}#boot-loading-fill{height:12px;background:#7bf}</style>
<div id="boot-overlay"><section id="boot-softtech"><img id="boot-softtech-img" src="/assets/boot-softtech.webp" alt="Soft Tech"><p><button id="boot-play" disabled><span id="boot-play-text">PLAY WITH SOUND</span></button></p><p id="boot-play-error" role="alert" hidden></p></section>
<section id="boot-banner" hidden><img id="boot-banner-img" src="/assets/boot-uno-banner.webp" alt="UNO LUCK"><div id="boot-loading-track"><div id="boot-loading-fill"></div><span id="boot-loading-label"></span></div><strong id="boot-loading-percent"></strong></section></div>
<main id="game-shell" class="is-booting" aria-hidden="true">Boot completed with confirmed audio playback</main>
<script src="/assets/art/sound.js" defer></script><script src="/assets/art/mirror-loop.js" defer></script><script src="/assets/art/sound-studio.js" defer></script><script src="/assets/boot.js" defer></script>
<script>window.addEventListener('uno:boot-finished',()=>window.UNOLuckSoundStudio.activateMusicAtGameplay());</script></html>'''


def manifest(case):
    cue = {'source':'custom','revision':'published-test','fileName':'tracked-music-loop.mp3',
           'url':PUBLISHED,'fileDuration':14.616,'start':.25,'stop':2,'fadeIn':.1,'fadeOut':.25}
    if case == 'broken_custom':
        # A broken long custom clip must not impose its trim on the short fallback.
        cue.update(fileDuration=120,start=88,stop=110)
    return {'ready':case != 'unconfigured','revision':case,'mixer':None,
            'cues':{CUE:cue} if case in ('published','broken_custom') else {}}


@contextmanager
def fixture(case):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            requests.append({'method':'GET','path':path})
            if path == '/':
                return self.respond(200, HTML, 'text/html')
            if path == '/favicon.ico':
                return self.respond(204, b'', 'image/x-icon')
            if path == '/health':
                return self.respond(200, b'{"ok":true}', 'application/json')
            if path == '/api/sounds/manifest':
                if case == 'catalog_outage':
                    return self.respond(503, b'{"detail":"injected optional catalog outage"}', 'application/json')
                return self.respond(200, json.dumps(manifest(case)).encode(), 'application/json')
            if path == PUBLISHED:
                if case == 'broken_custom':
                    return self.respond(503, b'Published audio file missing', 'text/plain')
                return self.respond(200, ASSET.read_bytes(), 'audio/mpeg')
            if path.startswith('/assets/'):
                target = (STATIC / path.removeprefix('/assets/')).resolve()
                if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
                    return self.respond(404, b'missing asset', 'text/plain')
                if path == BUNDLED and case == 'missing_bundled':
                    return self.respond(503, b'injected bundled audio failure', 'text/plain')
                return self.respond(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
            self.respond(404, b'unknown path', 'text/plain')

        def do_POST(self):
            requests.append({'method':'POST','path':urlsplit(self.path).path})
            self.respond(405,b'read-only fixture','text/plain')

        def respond(self, status, data, kind):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port), requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


OBSERVE = '''() => ({boot_hidden:document.getElementById('boot-overlay').hidden,
  play_visible:!document.getElementById('boot-play').hidden,
  error:document.getElementById('boot-play-error').textContent,
  media_unlocked:window.UNOLuckSoundStudio.mediaUnlocked,
  profile:localStorage.getItem('uno_sound_studio_profiles_v1'),
  media:[...document.querySelectorAll('audio')].map(a=>({path:new URL(a.currentSrc||a.src,location.href).pathname,
    paused:a.paused,muted:a.muted,current_time:a.currentTime,
    duration:Number.isFinite(a.duration)?a.duration:null,ready_state:a.readyState})),
  plays:window.__bootAudioPlays})'''


def run_case(browser, case):
    with fixture(case) as (origin, requests):
        context = browser.new_context(viewport={'width':390,'height':844},has_touch=True,
                                      is_mobile=True,reduced_motion='reduce')
        errors, console_errors, external = [], [], []
        context.route('**/*',lambda route: route.continue_() if urlsplit(route.request.url).netloc == urlsplit(origin).netloc
                      else (external.append(route.request.url),route.abort())[-1])
        # Observe and return the real play() result. No media behavior is replaced.
        context.add_init_script('''window.__bootAudioPlays=[];
          const original=HTMLMediaElement.prototype.play;
          HTMLMediaElement.prototype.play=function(...args){
            const item={path:new URL(this.currentSrc||this.src,location.href).pathname,
              muted:this.muted,trusted_click:window.event?.type==='click'&&window.event.isTrusted,
              active_gesture:navigator.userActivation.isActive,result:'pending'};
            window.__bootAudioPlays.push(item);
            try{return Promise.resolve(original.apply(this,args)).then(v=>{item.result='resolved';return v;},
              e=>{item.result='rejected';item.error=e.name;throw e;});}
            catch(e){item.result='rejected';item.error=e.name;throw e;}
          };''')
        saved_profile = json.dumps({CUE:{'custom':True,'fileName':'kept-local-draft.wav',
                                        'fileDuration':120,'start':88,'stop':110}}) if case == 'missing_local_draft' else None
        if saved_profile:
            context.add_init_script('localStorage.setItem("uno_sound_studio_profiles_v1",'+json.dumps(saved_profile)+');')
        if case == 'music_off':
            context.add_init_script('localStorage.setItem("uno_orbit_music","off");')
        page = context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:console_errors.append({'text':m.text,'url':m.location.get('url','')}) if m.type=='error' else None)
        try:
            page.goto(origin,wait_until='domcontentloaded')
            page.wait_for_function('!document.getElementById("boot-play").disabled',timeout=15000)
            before = page.evaluate(OBSERVE)
            assert before['plays'] == [] and not before['boot_hidden'], (case,before)
            page.screenshot(path=str(OUT/(case+'-before.png')))
            page.locator('#boot-play').click()
            failed_attempt = None
            if case in ('broken_custom','missing_bundled'):
                page.locator('#boot-play-error').wait_for(state='visible',timeout=12000)
                page.wait_for_timeout(200)
                failed_attempt = page.evaluate(OBSERVE)
                assert not failed_attempt['boot_hidden'] and failed_attempt['play_visible'], failed_attempt
                assert any(p['result']=='rejected' and not p['muted'] for p in failed_attempt['plays']), failed_attempt
                assert not any(p['path']==BUNDLED and not p['muted'] and p['result']=='resolved'
                               for p in failed_attempt['plays']), 'Fallback played without another click'
                page.screenshot(path=str(OUT/(case+'-rejected.png')))
                if case == 'broken_custom':
                    page.locator('#boot-play').click()
                else:
                    after = page.evaluate(OBSERVE)
                    return {'case':case,'status':'PASS_EXPECTED_BOOT_BLOCK','before':before,
                            'after':after,'requests':requests,'console_errors':console_errors,
                            'page_errors':errors,'blocked_external':external}
            page.wait_for_function('window.__bootAudioPlays.some(p=>!p.muted&&p.result==="resolved")',timeout=10000)
            playing = page.evaluate(OBSERVE)
            expected_path = PUBLISHED if case == 'published' else BUNDLED
            assert any(p['path']==expected_path and p['result']=='resolved' and not p['muted']
                       and p['trusted_click'] and p['active_gesture'] for p in playing['plays']), playing
            audio = next(a for a in playing['media'] if a['path']==expected_path and not a['muted'])
            assert not audio['paused'] and audio['ready_state'] >= 2 and 14 < audio['duration'] < 15, audio
            if case in ('broken_custom','missing_local_draft'):
                assert 0 <= audio['current_time'] < 7, 'Custom trim leaked into bundled playback'
            page.locator('#boot-overlay').wait_for(state='hidden',timeout=18000)
            after = page.evaluate(OBSERVE)
            assert after['boot_hidden'] and after['media_unlocked'] and after['profile'] == saved_profile
            if case == 'music_off':
                assert all(a['paused'] for a in after['media'])
                assert all(not p['muted'] for p in after['plays']), 'Disabled music was activated'
            else:
                assert any(a['path']==BUNDLED and not a['paused'] and not a['muted'] for a in after['media']), 'Prepared music did not continue after boot'
            assert not errors and not external, (errors,external)
            allowed = {'catalog_outage':'/api/sounds/manifest','broken_custom':PUBLISHED}.get(case)
            assert all(urlsplit(e['url']).path==allowed and '503' in e['text'] for e in console_errors), console_errors
            assert all(r['method']=='GET' and not r['path'].startswith(('/api/sounds/admin','/api/sounds/cues','/api/sounds/mixer')) for r in requests)
            page.screenshot(path=str(OUT/(case+'-after.png')))
            return {'case':case,'status':'PASS','before':before,'failed_attempt':failed_attempt,
                    'playing':playing,'after':after,'requests':requests,'console_errors':console_errors,
                    'page_errors':errors,'blocked_external':external}
        except BaseException:
            page.screenshot(path=str(OUT/(case+'-failure.png')))
            (OUT/(case+'-failure.json')).write_text(json.dumps({'state':page.evaluate(OBSERVE),'requests':requests,'errors':errors,'console_errors':console_errors},indent=2,allow_nan=False))
            raise
        finally:
            context.close()


def main():
    results = []
    with sync_playwright() as p:
        executable = os.environ.get('UNO_BOOT_CHROMIUM_EXECUTABLE')
        browser = p.chromium.launch(headless=True, **({'executable_path':executable} if executable else {}))
        try:
            for case in CASES:
                result = run_case(browser,case)
                assert not result['page_errors'] and not result['blocked_external']
                results.append(result)
                print('PASS',case,flush=True)
            report = {'status':'PASS','scope':'Real Chromium audio/splash component fixture; not native gameplay or physical speaker/Safari acceptance',
                      'browser':browser.version,'browser_executable':executable or 'playwright-managed','asset_sha256':ASSET_SHA,
                      'source_sha256':{str(f.relative_to(STATIC)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                                       [STATIC/'boot.js',STATIC/'art/sound.js',STATIC/'art/sound-studio.js',STATIC/'art/mirror-loop.js']},
                      'cases':results,'autoplay_policy_override':False,'play_results_mocked':False}
            (OUT/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
