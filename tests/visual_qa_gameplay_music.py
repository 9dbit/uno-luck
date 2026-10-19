"""UNO LUCK iPhone audio lifecycle: preload BGM before intro; reserve it
muted in native splash PLAY gesture and unmute at gameplay entry without
a second user interaction, even if WebAudio stays interrupted.
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
  // navigator.userActivation may be sticky/true in automated Chromium. Use
  // a real pointerdown window to model WebKit's transient audio permission.
  window.__musicGesture=false;
  document.addEventListener('pointerdown',()=>{
    window.__musicGesture=true;
    setTimeout(()=>{window.__musicGesture=false;},0);
  },true);
  const original=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(...args){
    const gesture=Boolean(window.__musicGesture);
    const src=this.getAttribute('src')||'';
    if(src.includes('music-loop.mp3'))
      window.__musicCalls.push({gesture,muted:this.muted,src,at:performance.now()});
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
  page.locator("#boot-play").tap(timeout=17000)
  page.locator("#game-shell").wait_for(state="visible",timeout=26000)
  # A single PLAY click already invoked .play() on the separate background
  # player while it was muted. Gameplay must unmute without another tap.
  page.wait_for_function("""() => window.__musicCalls.some(c=>c.gesture&&c.muted)""",
    timeout=5000)
  assert page.evaluate("window.UNOLuckSoundStudio.getRepeat('background-music')")
  assert page.locator("audio[data-uno-music='background-music']").count()==1
  assert page.evaluate("window.UNOLuckSound.webAudioState")=="interrupted"
  page.wait_for_function("""() => {
    const a=document.querySelector('audio[data-uno-music]');
    return a&&!a.muted&&!a.paused&&!a.ended;
  }""",timeout=8000)
  assert not page.evaluate("window.__musicCalls.some(c=>!c.gesture)"),(
    "Media autoplay was attempted without activation",page.evaluate("window.__musicCalls"))
  page.wait_for_function("""() => window.UNOLuckSoundStudio.isMusicMediaPlaying()""",
    timeout=5000)
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
print("PASS: Safari single PLAY gesture primes muted BGM, instant unmute at gameplay, separate SFX and music mute")
