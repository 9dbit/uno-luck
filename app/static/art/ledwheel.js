/* UNO LUCK v0.9: fixed 9-position LED marquee. Only the face data moves.
   Backend /api/orbit/pick is the exclusive authority for cards, credit, payout.
   No second spin wheel or frontend prize generation. */
(() => {
  'use strict';
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PICKS = 4; // top-center fixed golden pointer
  const COLORS = ['red','blue','yellow','green'];
  const FACES = ['0','1','2','3','4','5','6','7','8','9','SKIP','REVERSE','+2'];
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
  const random = array => array[Math.floor(Math.random()*array.length)];
  const preview = () => ({color:random(COLORS),face:random(FACES)});
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
    }
    resize() { /* All coordinates are percentages of the same square wheel art. */ }
    paint(index,card) {
      const node=this.nodes[index];
      if(!node)return;
      const color=COLORS.includes(card.color)?card.color:'wild';
      node.dataset.color=color;
      node.querySelector('.led-symbol').textContent=numeric(card);
      node.setAttribute('aria-label',describe(card));
      node.classList.toggle('led-selected',!this.active&&index===PICKS);
    }
    updateAll() {this.displays.forEach((data,i)=>this.paint(i,data));}
    shift(card) {
      // A traveling LED sequence: the gold frames never move, only their content.
      for(let i=this.count-1;i>0;i--)this.displays[i]=this.displays[i-1];
      this.displays[0]={...card};
      this.updateAll();
      this.host.dataset.ledFrame=String((this.tickNo++)%9);
    }
    begin({turbo=false}={}) {
      if(this.active)throw Error('LED selection already in progress');
      this.active=true;
      this.turbo=Boolean(turbo);
      this.lastTick=0;
      this.startedAt=performance.now();
      this.minimum=this.startedAt+(this.turbo?390:810);
      this.ready=null;
      this.injected=false;
      this.afterInject=0;
      this.cardConfirmed=false;
      this.host.classList.remove('led-idle','led-locked');
      this.host.classList.add('led-running');
      this.pending=new Promise(resolve=>{this.resolve=resolve;});
      if(REDUCED) return;
      const tick=now=>{
        if(!this.active)return;
        const dt=now-this.startedAt;
        const interval=this.injected ? (this.turbo?63:116) : (this.turbo?48:Math.min(98,54+Math.floor(dt/200)*8));
        if(now-this.lastTick>=interval){
          this.lastTick=now;
          if(this.ready && !this.injected && now>=this.minimum){
            // Feed the authoritative server-selected card in on the far left.
            this.shift(this.ready.card);
            this.injected=true;
            this.afterInject=0;
            this.host.classList.add('led-slowing');
          }else if(this.injected){
            this.shift(preview());
            this.afterInject++;
            if(this.afterInject===PICKS){this.complete();return;}
          }else this.shift(preview());
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
        this.displays[PICKS]={...card};
        this.updateAll();
        this.complete();
      }
      return acknowledged;
    }
    complete() {
      if(!this.active)return;
      cancelAnimationFrame(this.raf);
      this.raf=0;
      this.active=false;
      this.cardConfirmed=true;
      this.lastSelected=this.ready?.card||this.displays[PICKS];
      this.host.classList.remove('led-running','led-slowing');
      this.host.classList.add('led-locked');
      this.updateAll();
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
      if(!card)return;
      this.lastSelected={...card};
      this.displays[PICKS]={...card};
      this.cardConfirmed=true;
      this.updateAll();
      this.host.classList.add('led-locked');
    }
    cancel(){
      cancelAnimationFrame(this.raf);this.raf=0;
      this.active=false;this.ready=null;this.injected=false;
      this.host.classList.remove('led-running','led-slowing');
      if(this.resolve)this.resolve(false);
      this.resolve=null;this.pending=null;
    }
  }
  window.UNOLuckLEDWheel=LEDWheel;
})();
