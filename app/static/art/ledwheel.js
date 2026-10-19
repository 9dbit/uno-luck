/* UNO LUCK v1.2: nine fixed, full-color UNO-inspired LED cards.
   Preview symbols/colors change independently inside the fixed panels; only
   the LED highlight runs clockwise and decelerates at card five.
   Backend /api/orbit/pick alone chooses the settled card, credit and payout. */
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
      this.tickNo=0;
      this.resolve=null;
      this.pending=null;
      this.lastSelected=null;
      this.cardConfirmed=false;
      this.idleTimer=0;
      this.idleEnabled=!REDUCED;
      this.idleInterval=480;
      this.chaseIndex=-1;
    }
    // LED Chase: metal frames never move. When idle, nine assorted UNO card
    // faces stand still and only the LED light advances. On SPIN, each newly
    // lit panel can flicker to another colored UNO card without shifting slots.
    chaseFace(){
      this.displays=previewPack();
      // The center card is the real server result after a finished SPIN.
      // Never replace that card with a decorative preview during idle/reload.
      if(!this.active && this.cardConfirmed && this.lastSelected)
        this.displays[PICKS]={...this.lastSelected};
      this.updateAll();
    }
    flashPreview(index){
      if(!this.active)return;
      const shown=new Set(this.displays
        .filter((_,i)=>i!==index).map(card=>card.face));
      const prior=this.displays[index]?.face;
      // Keep all nine symbols varied, and make the lit preview change on each
      // pass. Math.random here is ONLY presentation, not game result RNG.
      const candidates=FACES.filter(face=>face!==prior&&!shown.has(face));
      if(!candidates.length)return;
      const card=preview(random(candidates));
      this.displays[index]=card;
      this.paint(index,card);
    }
    illuminate(index){
      if(this.active)this.flashPreview(index);
      this.chaseIndex=index;
      this.nodes.forEach((node,i)=>{
        node.classList.toggle('led-illuminated',i===index);
        node.classList.toggle('led-dimmed',i!==index);
      });
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
      if(this.active||!this.idleEnabled||document.hidden||!this.nodes.length)return;
      this.host.classList.remove('led-running','led-slowing');
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
      node.dataset.color=color;
      node.dataset.face=String(card.face);
      node.querySelector('.led-symbol').textContent=numeric(card);
      node.setAttribute('aria-label',describe(card));
      node.classList.toggle('led-selected',!this.active&&index===PICKS);
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
            this.nextChaseAt=now+quick+braking*smooth;
          }else{
            this.nextChaseAt=now+(this.turbo?34:48);
          }
          window.UNOLuckSound?.ledTick(Boolean(this.deceleration));
        }
        this.raf=requestAnimationFrame(tick);
      };
      this.raf=requestAnimationFrame(tick);
    }
    settle(card,picked) {
      if(!this.active)throw Error('Cannot settle LED wheel before SPIN');
      if(!card||!card.color||!card.face)throw Error('Server choice missing');
      if(!Number.isInteger(picked)||picked<1||picked>3)throw Error('Invalid pick phase');
      this.ready={card:{...card},picked};
      // Capture before complete() clears this.pending. Reduced-motion users must
      // receive the same acknowledged server pick rather than a false failure.
      const acknowledged=this.pending;
      if(REDUCED){
        this.illuminate(PICKS);
        this.complete();
      }
      return acknowledged;
    }
    complete() {
      if(!this.active)return;
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
      this.clearIllumination();
      this.updateAll();
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
      try{
        await item.animate([
          {transform:'translate3d(0,0,0) scale(.88)',opacity:1,filter:'brightness(2)'},
          {transform:`translate3d(${dx*.47}px,${dy*.47-25}px,0) scale(${(sx+1)/2})`,opacity:1,filter:'brightness(2.2)',offset:.48},
          {transform:`translate3d(${dx}px,${dy}px,0) scale(${sx},${sy})`,opacity:1,filter:'brightness(1)'}
        ],{duration:this.turbo?290:520,easing:'cubic-bezier(.2,.72,.2,1)',fill:'forwards'}).finished;
      }catch(_){/* DOM can be removed by navigation/reduced-motion */}
      finally{item.remove();}
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
  }
  window.UNOLuckLEDWheel=LEDWheel;
})();
