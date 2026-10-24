/* UNO LUCK v1.2: nine fixed, full-color UNO-inspired LED cards.
   Each LED step moves the entire symbol/color sequence clockwise on the SAME
   animation tick as the illuminated panel, and injects a random UNO card.
   Frames are fixed; the final fifth-panel card comes ONLY from the server.
   This preview animation never draws prizes or changes backend outcome odds. */
(() => {
  'use strict';
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PICKS = 4; // top-center fixed golden pointer
  const COLORS = ['red','blue','yellow','green'];
  const NUMBERS = ['0','1','2','3','4','5','6','7','8','9'];
  const ACTIONS = ['SKIP','REVERSE','+2'];
  const WILDS = ['WILD','+4'];
  const FACES = [...NUMBERS,...ACTIONS,...WILDS];
  const SYMBOL = {SKIP:'⊘',REVERSE:'⇄','+2':'+2','+4':'+4',WILD:'◉'};
  const TRACK_ALL=[0,1,2,3,4,5,6,7,8];
  const TRACK_WITHOUT_CENTER=[0,1,2,3,5,6,7,8];
  const GEOMETRY = [
    {x:14.4,y:64.0,w:13.2,h:19.0,angle:-67},
    {x:19.1,y:51.7,w:13.0,h:19.9,angle:-51},
    {x:28.7,y:42.1,w:13.6,h:20.2,angle:-34},
    {x:39.0,y:36.8,w:13.4,h:20.5,angle:-16},
    {x:50.0,y:35.8,w:12.4,h:20.8,angle:0},
    {x:61.0,y:37.3,w:13.5,h:20.6,angle:16},
    {x:71.8,y:42.6,w:13.6,h:20.2,angle:34},
    {x:80.6,y:52.2,w:12.6,h:19.9,angle:51},
    {x:85.5,y:64.3,w:12.8,h:19.0,angle:67}
  ];
  // These visual-only draws NEVER affect /api/orbit/pick or winning odds.
  const random = array => array[Math.floor(Math.random()*array.length)];
  const shuffle = cards => {
    const items=[...cards];
    for(let i=items.length-1;i>0;i--){
      const j=Math.floor(Math.random()*(i+1));
      [items[i],items[j]]=[items[j],items[i]];
    }
    return items;
  };
  const preview = (face=random(FACES)) => ({
    color:WILDS.includes(face)?'wild':random(COLORS),face
  });
  const previewPack = () => {
    // Nine different card faces per wheel, including a colored action card
    // and a Wild/+4. Avoid nine identical 1s or a fake "winning" display.
    const feature=[random(ACTIONS),random(WILDS)];
    const rest=shuffle(FACES.filter(face=>!feature.includes(face))).slice(0,7);
    return shuffle([...feature,...rest]).map(face=>preview(face));
  };
  const describe = card => `${card.color} ${card.face}`;
  const numeric = card => SYMBOL[card.face] || String(card.face || '?');

  class LEDWheel {
    constructor(host, resultFactory, count=9) {
      if (count!==9) throw Error('v0.9 LED wheel needs nine fixed placeholders');
      this.host=host;
      this.resultFactory=resultFactory;
      this.count=count;
      this.nodes=[];
      this.symbolNodes=[];  // Cache glyph DOM once; no selector queries in hot spin loop.
      this.displays=[];
      this.active=false;
      this.raf=0;
      this.lastTick=0;
      this.startedAt=0;
      this.minimum=0;
      this.turbo=false;
      this.ready=null;
      this.injected=false;
      this.afterInject=0;
      this.ledDraws=0;
      this.tickNo=0;
      this.faceSteps=0;
      this.resolve=null;
      this.pending=null;
      this.lastSelected=null;
      this.cardConfirmed=false;
      this.idleTimer=0;
      this.settleWatchdog=0;
      this.idleEnabled=!REDUCED;
      this.idleInterval=480;
      this.chaseIndex=-1;
    }
    // The metal LED frames NEVER move. Each tick moves their UNO faces one
    // position in the same clockwise direction as the LED chase. In idle,
    // numbers also circulate slowly instead of staying static.
    chaseFace(){
      this.displays=previewPack();
      this.faceSteps=0;
      // After a completed SPIN, the fifth card is a real server result. The
      // animated idle preview may NOT rotate or reroll that center outcome.
      if(!this.active && this.cardConfirmed && this.lastSelected)
        this.displays[PICKS]={...this.lastSelected};
      this.updateAll();
    }
    advanceFaces(index){
      if(!this.displays.length)return;
      const centerLocked=!this.active && this.cardConfirmed && Boolean(this.lastSelected);
      const track=centerLocked?TRACK_WITHOUT_CENTER:TRACK_ALL;
      // O(9) in-place reference rotation. No new array/object clones for every
      // frame, unlike the old map/filter/spread path that stalled iPhone Safari.
      const last=this.displays[track[track.length-1]];
      for(let j=track.length-1;j>0;j--)
        this.displays[track[j]]=this.displays[track[j-1]];
      this.displays[track[0]]=last;
      const current=index===PICKS && centerLocked ? track[3] : index;
      const at=track.indexOf(current);
      const injectAt=track[this.faceSteps%2===0
        ? at : (at+track.length-1)%track.length];
      const prior=this.displays[injectAt]?.face;
      // One random UNO face enters the spinning sequence per LED step.
      // A direct loop avoids temporary Set/filter/map arrays in the hot path.
      let choice=null,available=0;
      for(const face of FACES){
        if(face===prior)continue;
        let used=false;
        for(let j=0;j<this.count;j++){
          if(j!==injectAt&&this.displays[j]?.face===face){used=true;break;}
        }
        if(!used&&Math.random()*++available<1)choice=face;
      }
      if(choice!==null)this.displays[injectAt]=preview(choice);
      // The fifth panel is the previous server result during idle, never
      // overwritten by a decoration or the random presentation sequence.
      if(centerLocked)this.displays[PICKS]=this.lastSelected;
      this.faceSteps++;
      this.updateAll();
      this.host.dataset.faceFrame=String(this.faceSteps);
    }
    illuminate(index){
      // One RAF / one clock tick controls glyphs, LED glow and LED SFX.
      this.advanceFaces(index);
      this.setLight(index);
    }
    setLight(index){
      // Change illumination without advancing faces when locking a server ACK.
      const old=this.chaseIndex;
      this.chaseIndex=index;
      if(old<0){
        for(let i=0;i<this.count;i++){
          this.nodes[i].classList.toggle('led-illuminated',i===index);
          this.nodes[i].classList.toggle('led-dimmed',i!==index);
        }
      }else if(old!==index){
        // Only two sockets change light state. Previously all 9 slots
        // invalidated styles on every 34/48ms tick (18 class toggles).
        this.nodes[old].classList.remove('led-illuminated');
        this.nodes[old].classList.add('led-dimmed');
        this.nodes[index].classList.remove('led-dimmed');
        this.nodes[index].classList.add('led-illuminated');
      }
      this.ledDraws++;
      this.host.dataset.ledFrame=String(index);
    }
    clearIllumination(){
      this.chaseIndex=-1;
      this.nodes.forEach(node=>node.classList.remove('led-illuminated','led-dimmed'));
    }
    stopIdle(){
      if(this.idleTimer)clearTimeout(this.idleTimer);
      this.idleTimer=0;
      this.host.classList.remove('led-ambient');
    }
    startIdle(){
      this.stopIdle();
      if(this.active||document.hidden||!this.nodes.length)return;
      this.host.classList.remove('led-running','led-slowing','led-locked');
      if(!this.idleEnabled){
        this.host.classList.add('led-idle');
        this.setLight(PICKS);
        return;
      }
      this.host.classList.add('led-idle','led-ambient');
      this.chaseFace();
      this.illuminate(0);
      const tick=()=>{
        if(this.active||document.hidden){this.stopIdle();return;}
        this.illuminate((this.chaseIndex+1)%this.count);
        this.idleTimer=setTimeout(tick,this.idleInterval);
      };
      this.idleTimer=setTimeout(tick,this.idleInterval);
    }
    mount(values) {
      this.cancel();
      this.displays=Array.isArray(values)&&values.length===9 ? values.map(c=>({...c})) : Array.from({length:9},preview);
      this.nodes=GEOMETRY.map((position,index)=>{
        const node=document.createElement('div');
        node.className='led-slot';
        node.dataset.index=String(index);
        node.style.setProperty('--x',`${position.x}%`);
        node.style.setProperty('--y',`${position.y}%`);
        node.style.setProperty('--w',`${position.w}%`);
        node.style.setProperty('--h',`${position.h}%`);
        node.style.setProperty('--tilt',`${position.angle}deg`);
        node.innerHTML='<span class="led-screen"><span class="led-symbol"></span><span class="led-sheen"></span></span>';
        return node;
      });
      this.symbolNodes=this.nodes.map(node=>node.querySelector('.led-symbol'));
      this.host.replaceChildren(...this.nodes);
      this.updateAll();
      this.lastSelected=null;
      this.host.classList.add('led-idle');
      this.startIdle();
    }
    resize() { /* All coordinates are percentages of the same square wheel art. */ }
    paint(index,card) {
      const node=this.nodes[index];
      if(!node)return;
      const color=COLORS.includes(card.color)?card.color:'wild';
      const face=String(card.face);
      const glyph=numeric(card),symbol=this.symbolNodes[index];
      // Skip redundant style, accessibility and text mutations. textContent
      // on 9 glyphs at 20-30Hz was causing frequent WebKit layout/paint work.
      if(node.dataset.color!==color)node.dataset.color=color;
      if(node.dataset.face!==face)node.dataset.face=face;
      if(symbol.textContent!==glyph)symbol.textContent=glyph;
      const label=describe(card);
      if(node.getAttribute('aria-label')!==label)node.setAttribute('aria-label',label);
      if(index===PICKS)node.classList.toggle('led-selected',!this.active);
    }
    updateAll() {this.displays.forEach((data,i)=>this.paint(i,data));}
    shift(card,{silent=false}={}) {
      // A traveling LED sequence: the gold frames never move, only their content.
      for(let i=this.count-1;i>0;i--)this.displays[i]=this.displays[i-1];
      this.displays[0]={...card};
      this.updateAll();
      this.host.dataset.ledFrame=String((this.tickNo++)%9);
      if(!silent)window.UNOLuckSound?.ledTick(this.injected);
    }
    begin({turbo=false}={}) {
      if(this.active)throw Error('LED selection already in progress');
      this.stopIdle();
      this.active=true;
      this.startSpinAudio();
      this.turbo=Boolean(turbo);
      this.lastTick=0;
      this.startedAt=performance.now();
      this.minimum=this.startedAt+(this.turbo?390:810);
      this.ready=null;
      this.cardConfirmed=false;
      this.host.classList.remove('led-idle','led-locked','led-ambient');
      this.host.classList.add('led-running');
      this.chaseFace();
      this.illuminate(0);
      this.deceleration=null;
      this.nextChaseAt=this.startedAt;
      this.host.dataset.spinPhase='accelerate';
      this.pending=new Promise(resolve=>{this.resolve=resolve;});
      if(REDUCED)return;
      const tick=now=>{
        if(!this.active)return;
        try {
        // Do not plan an endpoint until the server has acknowledged the card.
        // Once acknowledged, choose a whole number of remaining steps that
        // ends EXACTLY at the fixed fifth LED under the golden pointer.
        if(this.ready&&now>=this.minimum&&!this.deceleration){
          const minimumSteps=10;
          const extra=(PICKS-this.chaseIndex-minimumSteps+this.count*4)%this.count;
          this.deceleration={total:minimumSteps+extra,remaining:minimumSteps+extra};
          this.host.classList.add('led-slowing');
          this.host.dataset.spinPhase='decelerate';
        }
        if(now>=this.nextChaseAt){
          this.lastTick=now;
          this.illuminate((this.chaseIndex+1)%this.count);
          if(this.deceleration){
            const ramp=this.deceleration;
            ramp.remaining--;
            if(ramp.remaining===0){
              // The geometry calculation guarantees the center index.
              if(this.chaseIndex!==PICKS)throw Error('LED end-stop alignment failed');
              this.complete();return;
            }
            const progress=(ramp.total-ramp.remaining)/ramp.total;
            const smooth=progress*progress*(3-2*progress);
            // A continuous ease-out: 48ms -> ~300ms (normal), or
            // 34ms -> ~225ms (turbo). No sudden speed jump at server ACK.
            const quick=this.turbo?34:48,braking=this.turbo?191:252;
            const interval=quick+braking*smooth;
            // Phase-continuous timing with a one-frame catch-up limit keeps
            // numbers and LED pacing even when Safari drops an animation frame.
            this.nextChaseAt=Math.max(now+12,this.nextChaseAt+interval);
          }else{
            const interval=this.turbo?34:48;
            this.nextChaseAt=Math.max(now+12,this.nextChaseAt+interval);
          }
          window.UNOLuckSound?.ledTick(Boolean(this.deceleration));
        }
        this.raf=requestAnimationFrame(tick);
        } catch(error) {
          console.warn('[UNO LED] RAF recovered',error);
          // A thrown animation-frame callback must never strand a paid ACK.
          if(this.ready?.card)this.forceComplete();
          else this.cancel();
        }
      };
      this.raf=requestAnimationFrame(tick);
    }
    forceComplete(){
      if(!this.active||!this.ready?.card)return false;
      // iOS can suppress RAF in low-power mode, standalone PWA, or while
      // transitioning to an overlay. The server card is already confirmed.
      this.setLight(PICKS);
      this.complete();
      return true;
    }
    settle(card,picked) {
      if(!this.active)throw Error('Cannot settle LED wheel before SPIN');
      if(!card||!card.color||!card.face)throw Error('Server choice missing');
      if(!Number.isInteger(picked)||picked<1||picked>3)throw Error('Invalid pick phase');
      this.ready={card:{...card},picked};
      // Capture before complete() clears this.pending. Reduced-motion users must
      // receive the same acknowledged server pick rather than a false failure.
      const acknowledged=this.pending;
      // Stop-gap must run even when requestAnimationFrame is suspended.
      // It only displays the server-confirmed card, never generates one.
      clearTimeout(this.settleWatchdog);
      this.settleWatchdog=setTimeout(()=>this.forceComplete(),4300);
      if(REDUCED){
        this.setLight(PICKS);
        this.complete();
      }
      return acknowledged;
    }
    complete() {
      if(!this.active)return;
      clearTimeout(this.settleWatchdog);this.settleWatchdog=0;
      this.stopSpinAudio();
      cancelAnimationFrame(this.raf);
      this.raf=0;
      this.active=false;
      this.host.dataset.spinPhase='locked';
      this.deceleration=null;
      this.cardConfirmed=true;
      if(!this.ready?.card)throw Error('LED cannot finish without server-selected card');
      this.lastSelected={...this.ready.card};
      this.displays[PICKS]={...this.ready.card};
      this.host.classList.remove('led-running','led-slowing');
      this.host.classList.add('led-locked');
      this.setLight(PICKS);
      // The other eight symbols are already painted. Only the center receives
      // a new server-authorized card during lock-in.
      this.paint(PICKS,this.ready.card);
      window.UNOLuckSound?.play('lock');
      const finish=this.resolve;
      this.resolve=null;
      this.pending=null;
      this.ready=null;
      if(finish)finish(true);
    }
    async transferTo(target) {
      if(!this.lastSelected||!target)return;
      if(REDUCED||document.hidden)return;
      const from=this.nodes[PICKS].getBoundingClientRect();
      const to=target.getBoundingClientRect();
      if(!from.width||!to.width)return;
      const item=document.createElement('div');
      item.className='led-flying-card';
      item.style.cssText=`position:fixed;top:${from.top}px;left:${from.left}px;width:${from.width}px;height:${from.height}px;`;
      item.append(this.resultFactory(this.lastSelected,false));
      document.body.append(item);
      const dx=to.left+to.width/2-(from.left+from.width/2);
      const dy=to.top+to.height/2-(from.top+from.height/2);
      const sx=to.width/from.width;
      const sy=to.height/from.height;
      let effect=null,guard=0;
      try{
        effect=item.animate([
          {transform:'translate3d(0,0,0) scale(.88)',opacity:1,filter:'brightness(2)'},
          {transform:`translate3d(${dx*.47}px,${dy*.47-25}px,0) scale(${(sx+1)/2})`,opacity:1,filter:'brightness(2.2)',offset:.48},
          {transform:`translate3d(${dx}px,${dy}px,0) scale(${sx},${sy})`,opacity:1,filter:'brightness(1)'}
        ],{duration:this.turbo?290:520,easing:'cubic-bezier(.2,.72,.2,1)',fill:'forwards'});
        await Promise.race([
          effect.finished.catch(()=>{}),
          new Promise(resolve=>{guard=setTimeout(resolve,900);})
        ]);
      }catch(_){/* Safari can suspend or reject animation.finished */}
      finally{clearTimeout(guard);try{effect?.cancel();}catch(_){}item.remove();}
    }
    recover(card){
      this.cancel();
      if(!card){this.startIdle();return;}
      this.lastSelected={...card};
      this.displays[PICKS]={...card};
      this.cardConfirmed=true;
      this.updateAll();
      this.host.classList.add('led-locked');
      this.startIdle();
    }
    cancel(){
      clearTimeout(this.settleWatchdog);this.settleWatchdog=0;
      this.stopSpinAudio();
      this.stopIdle();
      this.clearIllumination();
      cancelAnimationFrame(this.raf);this.raf=0;
      this.active=false;this.ready=null;this.injected=false;
      this.deceleration=null;
      this.host.dataset.spinPhase='idle';
      this.host.classList.remove('led-running','led-slowing');
      if(this.resolve)this.resolve(false);
      this.resolve=null;this.pending=null;
    }
    startSpinAudio(){
      const token=this.audioSerial=(this.audioSerial||0)+1;
      void Promise.resolve(window.UNOLuckSound?.unlock?.()).then(ok=>{
        if(ok&&this.active&&token===this.audioSerial&&!document.hidden)
          void window.UNOLuckSound?.startSpin?.();
      });
    }
    stopSpinAudio(){
      this.audioSerial=(this.audioSerial||0)+1;
      window.UNOLuckSound?.stopSpin?.();
    }
  }
  window.UNOLuckLEDWheel=LEDWheel;
})();

