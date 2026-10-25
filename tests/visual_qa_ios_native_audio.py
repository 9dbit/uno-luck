"""End-to-end iPhone audio audit on isolated CI sound fixtures only.

Exercises WebKit and Chromium with an iPhone user agent, including the case
where WebAudio claims "running" but its audible route is unavailable. We must
start the actual native HTMLMediaElement tracks on the trusted PLAY gesture,
unmute BGM when gameplay starts, and preserve the published Sound Cloud mixer.
"""
from playwright.sync_api import sync_playwright

URL="http://127.0.0.1:8080/"
IOS_UA=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.6 Mobile/15E148 Safari/604.1")
TRACK="""
(() => {
  localStorage.setItem('uno_orbit_music','off');
  localStorage.setItem('uno_orbit_sfx','off');
  window.__nativeAudioPlays=[];
  const oldPlay=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(...args){
    window.__nativeAudioPlays.push({
      src:this.getAttribute('src')||'',muted:this.muted,
      cue:this.dataset.unoCue||'',music:this.dataset.unoMusic==='background-music',
      time:performance.now()});
    return oldPlay.apply(this,args);
  };
})();
"""

with sync_playwright() as p:
  for name in ('chromium','webkit'):
    browser=getattr(p,name).launch(headless=True)
    context=browser.new_context(viewport={'width':393,'height':852},
        device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=IOS_UA)
    context.add_init_script(TRACK)
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto(URL,wait_until='domcontentloaded')
    page.wait_for_function(
       "() => !document.getElementById('boot-play').disabled && "
       "window.UNOLuckSoundStudio?.audioDiagnostics?.().musicPrepared",
       timeout=18000)
    assert page.evaluate('window.UNOLuckSoundStudio.isIOS()')
    assert page.evaluate('window.UNOLuckSoundStudio.cloudStatus().ready')
    # A stale mute preference must be overridden by explicit WITH SOUND.
    assert page.evaluate("localStorage.getItem('uno_orbit_music')")=='off'
    # Simulate a misleading running AudioContext. An iPhone must still use
    # HTMLMediaElement for the published splash and music.
    page.evaluate("""() => Object.defineProperty(window.UNOLuckSound,
      'webAudioState',{configurable:true,get:()=> 'running'})""")
    page.locator('#boot-play').tap(timeout=10000)
    page.wait_for_function("""() =>
      window.__nativeAudioPlays.some(p=>p.src.includes('soft-tech-splash-screen')&&!p.muted)
      && window.__nativeAudioPlays.some(p=>p.music&&p.muted)""",timeout=10000)
    assert page.evaluate("localStorage.getItem('uno_orbit_music')")=='on'
    assert page.evaluate("localStorage.getItem('uno_orbit_sfx')")=='on'
    page.wait_for_function(
      "() => !document.querySelector('#game-shell').classList.contains('is-booting')",
      timeout=30000)
    page.wait_for_function("""() => {
      const s=window.UNOLuckSoundStudio.audioDiagnostics();
      return s.musicPlaying&&!s.musicMuted&&!s.musicPaused;
    }""",timeout=8000)
    pos=page.evaluate("UNOLuckSoundStudio.audioDiagnostics().musicPosition")
    page.wait_for_timeout(500)
    nxt=page.evaluate("UNOLuckSoundStudio.audioDiagnostics().musicPosition")
    assert nxt>pos,(name,'BGM not advancing',pos,nxt)
    # Native button cue must also be called even while WebAudio says running.
    page.locator('#turbo-btn').tap(timeout=8000)
    page.wait_for_function("""() =>
      window.__nativeAudioPlays.some(p=>p.cue==='push-button')""",timeout=5000)
    assert page.evaluate("window.UNOLuckSoundStudio.audioDiagnostics().musicPlaying")
    # Reproduce WKWebView pausing music while unmuting after splash. The
    # recovery pill must call .play() directly in a new trusted gesture.
    page.evaluate("""() => {
      document.querySelector('audio[data-uno-music]').pause();
      refreshAudioRetry();
    }""")
    assert page.locator('#audio-retry').is_visible()
    before=page.evaluate("window.__nativeAudioPlays.filter(p=>p.music).length")
    page.locator('#audio-retry').tap()
    page.wait_for_function("""() =>
      window.UNOLuckSoundStudio.audioDiagnostics().musicPlaying""",timeout=6000)
    after=page.evaluate("window.__nativeAudioPlays.filter(p=>p.music).length")
    assert after>before,(name,'native gesture was not retried')
    assert not errors,(name,errors)
    print(name+': PASS native splash, music, SFX, restore, explicit sound unmute and published mixer')
    context.close()
    browser.close()
