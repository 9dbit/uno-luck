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
      faceFrame:document.querySelector('#orbit-ring').dataset.faceFrame,
      content:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>n.querySelector('.led-symbol').textContent),
      rects:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>{let r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];})
    })""")
    # Visuals are UNO-like: 9 distinct numbers/actions/Wilds rather than nine "1".
    assert first["content"] != ["1"]*9,first
    assert len(set(first["content"]))==9,first
    assert all(x in ("0","1","2","3","4","5","6","7","8","9","⊘","⇄","+2","+4","◉")
               for x in first["content"]),first
    assert ring.locator(".led-illuminated").count()==1
    page.wait_for_timeout(1050)
    second=page.evaluate("""() => ({
      index:document.querySelector('#orbit-ring').dataset.ledFrame,
      faceFrame:document.querySelector('#orbit-ring').dataset.faceFrame,
      content:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>n.querySelector('.led-symbol').textContent),
      rects:Array.from(document.querySelectorAll('#orbit-ring .led-slot')).map(n=>{let r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];})
    })""")
    assert first["content"]!=second["content"],"UNO numbers must rotate during the idle LED chase"
    assert sum(a!=b for a,b in zip(first["content"],second["content"]))>=6,(first,second)
    assert int(second["faceFrame"])>int(first["faceFrame"]),"Number frame must advance with LED"
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
            face:w.nodes[index]?.dataset.face,color:w.nodes[index]?.dataset.color,
            faces:w.nodes.map(node=>node.dataset.face),
            faceFrame:Number(el.dataset.faceFrame),
            lit:w.nodes.filter(n=>n.classList.contains('led-illuminated')).length});
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
      const idleBefore=w.nodes.map(n=>n.dataset.face);
      await new Promise(resolve=>setTimeout(resolve,1030));
      const idleAfter=w.nodes.map(n=>n.dataset.face);
      const idleCenterHeld=idleAfter[4]==='1';
      const idleOthersMove=idleAfter.some((face,i)=>i!==4&&face!==idleBefore[i]);
      const syncedSteps=timeline.slice(1).map((row,i)=>{
        const prev=timeline[i];
        return {
          ledMoves:row.index===(prev.index+1)%9,
          faceMoves:row.faceFrame===prev.faceFrame+1,
          matches:row.faces.reduce((n,face,slot)=>n+(face===prev.faces[(slot+8)%9]?1:0),0),
          changed:row.faces.filter((face,slot)=>face!==prev.faces[slot]).length,
          lit:row.lit
        };
      });
      const intervals=timeline.slice(1).map((row,i)=>({
        ms:row.t-timeline[i].t,phase:row.phase,index:row.index
      }));
      const cruise=intervals.filter(x=>x.phase==='accelerate').map(x=>x.ms);
      const brake=intervals.filter(x=>x.phase==='decelerate').map(x=>x.ms);
      const finalStep=timeline.length?timeline[timeline.length-1].index:-1;
      w.cancel();el.remove();
      return {finished,choice,center,centerAfterIdle,variedAfterIdle,previewVariety,
        idleCenterHeld,idleOthersMove,syncedSteps,lit,unchanged,finalStep,
        cruise:cruise.slice(0,8),brake:brake.slice(-6)};

    }""")
    assert state["finished"] is True,state
    assert state["choice"]=={"color":"red","face":"1"},state
    assert state["center"]=="1",state
    assert state["centerAfterIdle"]=="1","Idle must preserve exact server-picked fifth card"
    assert state["variedAfterIdle"]>=8,state
    assert state["idleCenterHeld"],"Actual server result must remain visible during idle"
    assert state["idleOthersMove"],"Non-winning LED faces must continue moving during idle"
    assert state["previewVariety"]>=4,"Spinning must visibly randomize the UNO card faces"
    assert len(state["syncedSteps"])>=12,state
    # Final LED frame receives the server card and remains the sole bright card.
    assert all(
        row["ledMoves"] and row["faceMoves"] and row["changed"]>=7 and
        row["matches"] >= (7 if i==len(state["syncedSteps"])-1 else 8) and
        row["lit"] == 1
        for i,row in enumerate(state["syncedSteps"])
    ), "All number frames must follow the LED step; last frame is server-authoritative"
    assert state["lit"]==1,state
    assert state["unchanged"],"Visual-only LED test must never change balance"
    assert state["finalStep"]==4,state
    assert state["cruise"] and len(state["brake"])>=4,state
    early=sum(state["cruise"])/len(state["cruise"])
    last=sum(state["brake"][-3:])/3
    assert last>early*1.8,(early,last,state)

    assert not errors,errors
    browser.close()
print("PASS: idle+spin numbers rotate with each LED step, random UNO cards, fixed frames, slow-motion finish, fifth server card stays pinned")
