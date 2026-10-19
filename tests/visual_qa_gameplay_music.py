"""UNO LUCK iPhone audio lifecycle: auto BGM request at gameplay entry,
then synchronous media.play from the first trusted tap if Safari blocks it.
No wallet or SPIN requests. The Sound Studio settings are not modified.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path("artifacts/uno-v11-gameplay-music")
OUT.mkdir(parents=True,exist_ok=True)
IOS_UA=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
  "AppleWebKit/605.1.15 (KHTML, like Gecko) "
  "Version/18.6 Mobile/15E148 Safari/604.1")
INTERCEPT="""
(() => {
  const NativeContext=window.AudioContext;
  if(NativeContext){
    window.AudioContext=class InterruptedContext extends NativeContext {
      get state(){return 'interrupted';}
      resume(){return Promise.resolve();}
    };
  }
  window.__musicCalls=[];
  const original=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(...args){
    const gesture=Boolean(navigator.userActivation?.isActive);
    const src=this.getAttribute('src')||'';
    if(src.includes('music-loop.mp3'))
      window.__musicCalls.push({gesture,src,at:performance.now()});
    if(!gesture)
      return Promise.reject(new DOMException('iPhone requires user activation','NotAllowedError'));
    return original.apply(this,args);
  };
})();
"""

with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  context=browser.new_context(viewport={"width":390,"height":844},
    device_scale_factor=2,is_mobile=True,has_touch=True,user_agent=IOS_UA)
  context.add_init_script(INTERCEPT)
  page=context.new_page()
  errors=[]
  page.on("pageerror",lambda error:errors.append(str(error)))
  page.goto("http://127.0.0.1:8080/",wait_until="domcontentloaded")
  page.locator("#game-shell").wait_for(state="visible",timeout=26000)
  # Expose an actionable trace if the initial BGM request never reaches
  # HTMLMediaElement.play (e.g., a cloud-preload/start race).
  page.wait_for_timeout(450)
  diagnosis=page.evaluate("""() => ({
    calls:window.__musicCalls,
    audio:[...document.querySelectorAll('audio')].map(a=>({
      src:a.getAttribute('src'),paused:a.paused,ready:a.readyState
    })),
    cloud:window.UNOLuckSoundStudio.cloudStatus(),
    error:window.UNOLuckSoundStudio.lastError,
    music:window.UNOLuckSound.webAudioState,
    musicEnabled:localStorage.getItem('uno_orbit_music'),
    booting:document.querySelector('#game-shell').classList.contains('is-booting'),
    hidden:document.hidden
  })""")
  print("BGM_ENTER_DIAGNOSTIC",diagnosis,flush=True)
  page.wait_for_function("""() => window.__musicCalls.some(c=>!c.gesture)""",timeout=14000)
  assert page.evaluate("window.UNOLuckSoundStudio.getRepeat('background-music')")
  assert page.locator("audio[data-uno-music='background-music']").count()==1
  assert page.evaluate("window.UNOLuckSound.webAudioState")=="inactive"
  # No iOS autoplay bypass: the app tried immediately and Safari blocked it.
  assert not page.evaluate("""() => [...document.querySelectorAll('audio[data-uno-music]')]
     .some(a=>!a.paused)""")
  # The first real click must use the already prepared media element while the
  # browser is still in user activation, despite interrupted WebAudio.
  page.locator("#menu-open").click()
  page.wait_for_function("""() => window.__musicCalls.some(c=>c.gesture)""",timeout=12000)
  page.wait_for_function("""() => window.UNOLuckSoundStudio.isMusicMediaPlaying()""",
    timeout=12000)
  assert page.evaluate("window.UNOLuckSound.webAudioState")=="interrupted"
  start=page.evaluate("""() => document.querySelector('audio[data-uno-music]').currentTime""")
  page.wait_for_timeout(330)
  end=page.evaluate("""() => document.querySelector('audio[data-uno-music]').currentTime""")
  assert end>start,{"start":start,"end":end}
  # SFX fallback must not steal the BGM player's source or stop the music.
  page.evaluate("window.UNOLuckSoundStudio.play('push-button')")
  assert page.evaluate("window.UNOLuckSoundStudio.isMusicMediaPlaying()")
  assert page.evaluate("""() => document.querySelector('audio[data-uno-music]')
    .getAttribute('src').includes('music-loop.mp3')""")
  # Muting SFX is distinct from muting music; preserve the user's saved mixer.
  page.evaluate("window.UNOLuckSound.setEnabled(false)")
  assert page.evaluate("window.UNOLuckSoundStudio.isMusicMediaPlaying()")
  page.evaluate("window.UNOLuckSound.music(false)")
  page.wait_for_function("""() => !window.UNOLuckSoundStudio.isMusicMediaPlaying()""")
  page.screenshot(path=str(OUT/"iphone-gameplay-music-gesture.png"),full_page=True)
  assert not errors,errors
  context.close()
  browser.close()
print("PASS: immediate BGM request, Safari autoplay refusal, trusted tap recovery, independent SFX and music mute")
