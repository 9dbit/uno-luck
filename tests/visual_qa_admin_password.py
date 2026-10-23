"""Short test-password login in both admin surfaces; never publishes data."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = 'http://127.0.0.1:8080'
PASSWORD = os.environ['UNO_QA_ADMIN_PASSWORD']
OUT = Path('artifacts/uno-admin-password')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    for engine in ('chromium', 'webkit'):
        browser = getattr(p, engine).launch(headless=True)
        page = browser.new_page(viewport={'width': 393, 'height': 852})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        before = page.request.get(URL + '/api/sounds/manifest').json()
        page.goto(URL + '/assets/economy-admin.html')
        page.locator('#admin-key').fill(PASSWORD)
        page.locator('#unlock').click()
        page.wait_for_function("!document.querySelector('#publish').disabled")
        assert page.locator('#admin-key').input_value() == ''
        assert page.locator('#editor').is_visible()
        page.goto(URL + '/admin')
        page.locator('#admin-studio').click()
        section = page.locator('.studio-cloud-admin')
        section.locator('summary').click()
        section.locator('input[type=password]').fill(PASSWORD)
        section.get_by_role('button', name='VERIFIKASI KUNCI').click()
        section.locator('.studio-cloud-status').get_by_text('Admin terverifikasi', exact=False).wait_for()
        assert section.locator('input[type=password]').input_value() == ''
        assert page.evaluate("sessionStorage.getItem('uno-sound-admin-key')") is None
        page.screenshot(path=str(OUT / f'{engine}-verified.png'))
        page.reload()
        page.wait_for_function('Boolean(window.UNOLuckSoundStudio)')
        assert page.evaluate('window.UNOLuckSoundStudio.cloudStatus().admin') is False
        assert page.request.get(URL + '/api/sounds/manifest').json() == before
        assert not errors, errors
        browser.close()
        print(f'{engine}: PASS password login, memory-only credentials, audio unchanged')
