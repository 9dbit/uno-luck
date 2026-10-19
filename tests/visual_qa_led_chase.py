"""Deterministic LED Chase QA: nine fixed frames, authoritative center lock.
No requests to gameplay endpoints and no virtual-coin mutations.
"""
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=os.environ.get("UNO_QA_URL","http://127.0.0.1:8080/")
OUT=Path("artifacts/uno-v11-led-chase")
OUT.mkdir(parents=True,exist_ok=True)
errors=[]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
    page=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1)
    page.on("pageerror",lambda exc:errors.append(str(exc)))
    page.goto(BASE,wait_until="domcontentloaded")
    page.locator("#boot-play").click(timeout=17000)
    page.locator("#game-shell").wait_for(state="visible",timeout=28000)
    ring=page.locator("#orbit-ring")
    assert ring.locator(".led-slot").count()==9
    first=page.evaluate("""() => ({
      index:document.querySelector('#orbit-ring').dataset.ledFrame,
      content:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>n.querySelector('.led-symbol').textContent),
      rects:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>{let r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];})
    })""")
    # Visuals are UNO-like: 9 distinct numbers/actions/Wilds rather than nine "1".
    assert first["content"] != ["1"]*9,first
    assert len(set(first["content"]))==9,first
    assert any(x in first["content"] for x in ("⊘","⇄","+2")),first
    assert any(x in first["content"] for x in ("◉","+4")),first
    assert ring.locator(".led-illuminated").count()==1
    page.wait_for_timeout(1050)
    second=page.evaluate("""() => ({
      index:document.querySelector('#orbit-ring').dataset.ledFrame,
      content:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>n.querySelector('.led-symbol').textContent),
      rects:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>{let r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];})
    })""")
    assert first["content"]==second["content"],"Letters/digits must stay in place during idle"
    assert first["rects"]==second["rects"],"Gold LED frames must stay in place"
    assert first["index"]!=second["index"],"LED light must advance clockwise"
    assert ring.locator(".led-illuminated").count()==1
    page.screenshot(path=str(OUT/"iphone-led-chase-idle.png"))

    # The injected choice represents a server ACK without actually POSTing
    # /api/orbit/pick or affecting a player's coins.
    state=page.evaluate("""async () => {
      const el=document.createElement('div');
      el.className='wheel-led-ring';
      el.style.cssText='position:absolute;width:320px;height:320px;top:0;left:0';
      document.body.append(el);
      const w=new window.UNOLuckLEDWheel(el,()=>document.createElement('div'),9);
      const base=Array.from({length:9},(_,i)=>({color:'blue',face:String(i)}));
      w.mount(base);
      const coin=document.getElementById('wallet-balance').textContent;
      const timeline=[];
      let previous=-1;
      const observer=new MutationObserver(()=>{
        const index=Number(el.dataset.ledFrame);
        if(index!==previous){
          previous=index;
          timeline.push({t:performance.now(),index,phase:el.dataset.spinPhase,
            face:w.nodes[index]?.dataset.face,color:w.nodes[index]?.dataset.color});
        }
      });
      observer.observe(el,{attributes:true,attributeFilter:['data-led-frame']});
      w.begin({turbo:false});
      const ack=w.settle({color:'red',face:'1'},1);
      const finished=await Promise.race([ack,new Promise(resolve=>setTimeout(()=>resolve('timeout'),6500))]);
      observer.disconnect();
      const choice=w.lastSelected;
      const center=w.nodes[4].querySelector('.led-symbol').textContent;
      const lit=Array.from(w.nodes).filter(n=>n.classList.contains('led-illuminated')).length;
      const unchanged=document.getElementById('wallet-balance').textContent===coin;
      const previewVariety=new Set(timeline.map(row=>row.face).filter(Boolean)).size;
      w.startIdle();
      const centerAfterIdle=w.nodes[4].querySelector('.led-symbol').textContent;
      const variedAfterIdle=new Set(w.nodes.map(n=>n.dataset.face)).size;
      const intervals=timeline.slice(1).map((row,i)=>({
        ms:row.t-timeline[i].t,phase:row.phase,index:row.index
      }));
      const cruise=intervals.filter(x=>x.phase==='accelerate').map(x=>x.ms);
      const brake=intervals.filter(x=>x.phase==='decelerate').map(x=>x.ms);
      const finalStep=timeline.length?timeline[timeline.length-1].index:-1;
      w.cancel();el.remove();
      return {finished,choice,center,centerAfterIdle,variedAfterIdle,previewVariety,lit,unchanged,finalStep,
        cruise:cruise.slice(0,8),brake:brake.slice(-6)};

    }""")
    assert state["finished"] is True,state
    assert state["choice"]=={"color":"red","face":"1"},state
    assert state["center"]=="1",state
    assert state["centerAfterIdle"]=="1","Idle must preserve exact server-picked fifth card"
    assert state["variedAfterIdle"]>=8,state
    assert state["previewVariety"]>=4,"Spinning must visibly randomize the UNO card faces"
    assert state["lit"]==0,state
    assert state["unchanged"],"Visual-only LED test must never change balance"
    assert state["finalStep"]==4,state
    assert state["cruise"] and len(state["brake"])>=4,state
    early=sum(state["cruise"])/len(state["cruise"])
    last=sum(state["brake"][-3:])/3
    assert last>early*1.8,(early,last,state)

    assert not errors,errors
    browser.close()
print("PASS: diverse UNO card faces, stationary panels, random spin previews, fast-to-slow light and fifth-card server lock")
