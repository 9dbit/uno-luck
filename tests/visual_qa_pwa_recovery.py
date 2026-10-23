"""Network handover and restored-page upgrade: real Chromium/WebKit with fault injection."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = os.getenv('UNO_QA_URL', 'http://127.0.0.1:8080')
OUT = Path('artifacts/uno-v1144-pwa-recovery')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    for engine in ('chromium', 'webkit'):
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={'width': 393, 'height': 852}, has_touch=True)
        page = context.new_page()
        errors, writes = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: writes.append(r.url) if r.method not in ('GET', 'HEAD') else None)
        baseline = context.request.get(URL+'/api/sounds/manifest').json()
        # The first fetch never settles until AbortController cancels it, as
        # can happen during a VPN handover. No live configuration is modified.
        page.add_init_script("""() => {
          const original=window.fetch;const stalled=new Set();
          window.fetch=(url,options={})=>{
            if(['/api/sounds/manifest','/api/orbit/state'].includes(String(url))&&!stalled.has(String(url))){
              stalled.add(String(url));
              return new Promise((resolve,reject)=>options.signal?.addEventListener('abort',
                ()=>reject(new DOMException('Network handover timeout','AbortError')),{once:true}));
            }
            return original(url,options);
          };
        }""".replace('() => {', '(() => {', 1) + ')();')
        page.goto(URL, wait_until='domcontentloaded')
        page.locator('#boot-play-error').wait_for(state='visible', timeout=14000)
        assert page.locator('#game-shell').get_attribute('aria-hidden') == 'true'
        page.screenshot(path=str(OUT/f'{engine}-network-retry.png'))
        page.evaluate("window.dispatchEvent(new Event('online'))")
        page.wait_for_function("() => document.getElementById('boot-play-error').hidden && !document.getElementById('boot-play').disabled")
        assert '/api/sounds/files/background-music' in page.locator('audio[data-uno-music]').get_attribute('src')
        page.locator('#boot-play').tap()
        page.locator('#game-shell').wait_for(state='visible', timeout=25000)
        page.wait_for_function("() => document.getElementById('connection-status').textContent==='ONLINE'")
        assert page.locator('#spin-btn').is_enabled()
        page.locator('#profile-btn').tap()
        assert page.locator('.menu-tile').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("aria-label"))') == ['Turnamen','Game Rules','Bet Setting','Profile','Sound On']
        page.locator('#modal-close').tap()
        page.screenshot(path=str(OUT/f'{engine}-recovered.png'))
        assert context.request.get(URL+'/api/sounds/manifest').json() == baseline

        # Simulate a newer deployment. Never reload during a round/pending pick.
        next_release = 'a'*20
        shell = context.request.get(URL).text()
        release = page.locator('meta[name="uno-release"]').get_attribute('content')
        page.route('**/api/ui-version', lambda r: r.fulfill(json={'release': next_release}))
        page.route('**/*_uno_release=*', lambda r: r.fulfill(content_type='text/html', body=shell.replace(release,next_release)))
        page.evaluate("window.__canReload=window.UNOLuckCanReload;window.UNOLuckCanReload=()=>false;window.dispatchEvent(new Event('pageshow'))")
        page.wait_for_timeout(300)
        assert '_uno_release' not in page.url
        page.evaluate("window.UNOLuckCanReload=window.__canReload;window.dispatchEvent(new Event('pageshow'))")
        page.wait_for_url('**/*_uno_release='+next_release, timeout=10000)
        assert page.locator('meta[name="uno-release"]').get_attribute('content') == next_release
        page.locator('#boot-play').wait_for(state='visible')
        before_url = page.url
        page.evaluate("window.dispatchEvent(new Event('pageshow'))")
        page.wait_for_timeout(300)
        assert page.url == before_url
        assert not errors, errors
        assert not writes, writes
        context.close();browser.close()
        print('PASS:', engine, 'network timeout recovery, one PLAY, unchanged sound, safe PWA upgrade')
