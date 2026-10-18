/* UNO LUCK v0.8: GPU-composited single-wheel carousel.
   Purely presentation. Server picks all three cards and owns stakes/payouts.
   Only this wheel rotates. The three result cells never become slot reels. */
(() => {
  'use strict';
  const PI2 = Math.PI * 2;
  const ease = t => 1 - Math.pow(1 - t, 4);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const normalize = angle => ((angle % PI2) + PI2) % PI2;

  class Wheel360 {
    constructor(host, factory, count = 13) {
      this.host = host;
      this.factory = factory;
      this.count = count;
      this.angle = 0;
      this.cards = [];
      this.nodes = [];
      this.geometry = null;
      this.raf = 0;
      this.active = false;
      this.pending = null;
      this.ready = null;
      this.deceleration = null;
      this.targetIndex = 0;
      this.lastFrame = null;
      this.minimum = 0;
      this.started = 0;
      this.turbo = false;
    }

    mount(cards) {
      this.cancel();
      if (!Array.isArray(cards) || cards.length !== this.count) throw Error('Wheel requires one card per position');
      this.cards = cards.map(c => ({...c}));
      this.nodes = cards.map((card, index) => {
        const holder = document.createElement('div');
        holder.className = 'orbit-card wheel-slot';
        holder.dataset.index = String(index);
        holder.append(this.factory(card, true));
        return holder;
      });
      this.host.replaceChildren(...this.nodes);
      this.geometry = null;
      this.angle = 0;
      this.targetIndex = 0;
      this.layout();
    }

    cacheGeometry() {
      if (this.geometry) return;
      const width = this.host.clientWidth;
      const height = this.host.clientHeight;
      if (!width || !height) return;
      // The opaque wheel illustration stays still. The card faces travel on a
      // 360-degree orbit, and only the upper semicircle is visible.
      this.geometry = {x: width * .405, y: height * .35};
    }

    resize() {
      this.geometry = null;
      this.layout();
    }

    setCard(index, card) {
      if (!this.nodes[index]) return;
      this.cards[index] = {...card};
      this.nodes[index].replaceChildren(this.factory(card, true));
    }

    layout() {
      this.cacheGeometry();
      if (!this.geometry || !this.nodes.length) return;
      const {x, y} = this.geometry;
      for (let i = 0; i < this.nodes.length; i++) {
        const theta = (PI2 * i / this.count) + this.angle;
        const cs = Math.cos(theta), sn = Math.sin(theta);
        const front = Math.max(0, Math.min(1, (cs + .16) * 4));
        const scale = .76 + Math.max(0, cs) * .20;
        const tilt = sn * 37;
        const node = this.nodes[i];
        node.style.transform = `translate3d(calc(-50% + ${(sn*x).toFixed(2)}px),calc(-50% - ${(cs*y).toFixed(2)}px),0) rotateZ(${tilt.toFixed(2)}deg) scale(${scale.toFixed(3)})`;
        node.style.opacity = String(front);
        node.style.zIndex = String(Math.round((cs+1)*12)+2);
        node.classList.toggle('wheel-chosen', !this.active && i === this.targetIndex);
        node.style.pointerEvents = 'none';
      }
    }

    begin({turbo = false} = {}) {
      if (this.active) throw Error('Spin already in progress');
      this.active = true;
      this.turbo = Boolean(turbo);
      this.started = performance.now();
      this.lastFrame = null;
      this.minimum = this.turbo ? 440 : 970;
      this.ready = null;
      this.deceleration = null;
      this.host.classList.add('wheel-running');
      this.pending = new Promise(resolve => {this.resolve = resolve;});
      if (reduce) return;
      const tick = now => {
        if (!this.active) return;
        const delta = Math.min(45, now - (this.lastFrame ?? now));
        this.lastFrame = now;
        if (!this.deceleration && this.ready && now-this.started >= this.minimum) {
          const {index, card} = this.ready;
          this.setCard(index, card);
          this.nodes[index].classList.remove('card-flip');
          // Re-rendered 3D face shows its reverse side for the half turn.
          void this.nodes[index].offsetWidth;
          this.nodes[index].classList.add('card-flip');
          setTimeout(()=>this.nodes[index]?.classList.remove('card-flip'),790);
          const reference = -PI2*index/this.count;
          const revolutions = Math.max(1, Math.ceil((this.angle-reference)/PI2));
          const destination = reference + PI2*(revolutions + (this.turbo?1:2));
          this.deceleration = {from:this.angle,to:destination,start:now,duration:this.turbo?340:630};
        }
        if (this.deceleration) {
          const d = this.deceleration;
          const progress = Math.min(1, (now-d.start)/d.duration);
          this.angle = d.from + (d.to - d.from)*ease(progress);
          this.layout();
          if (progress === 1) {this.complete();return;}
        } else {
          // All geometry is cached: the animation loop updates only composited
          // transforms and opacity, avoiding synchronous reflow on every frame.
          this.angle += Math.min(delta,45) * (this.turbo ? .026 : .017);
          this.layout();
        }
        this.raf = requestAnimationFrame(tick);
      };
      this.raf = requestAnimationFrame(tick);
    }

    settle(card, pickCount) {
      if (!this.active) throw Error('Cannot settle a wheel that is not spinning');
      if (!card || !card.face || !card.color) throw Error('Missing server-confirmed card');
      if (!Number.isInteger(pickCount) || pickCount < 1 || pickCount > 3) throw Error('Invalid pick phase');
      const index = (pickCount * 4 + 1) % this.count;
      this.targetIndex = index;
      this.ready = {card, index};
      if (reduce) {
        this.setCard(index, card);
        this.angle = normalize(-PI2*index/this.count);
        this.layout();
        this.complete();
      }
      return this.pending;
    }

    complete() {
      if (!this.active) return;
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.active = false;
      this.host.classList.remove('wheel-running');
      this.layout();
      const done = this.resolve;
      this.resolve = null;
      this.pending = null;
      this.ready = null;
      this.deceleration = null;
      if (done) done(true);
    }

    recover(card) {
      if (!card) return;
      const index = this.targetIndex;
      this.setCard(index,card);
      this.angle = normalize(-PI2*index/this.count);
      this.layout();
    }

    cancel() {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.active = false;
      this.lastFrame = null;
      this.ready = null;
      this.deceleration = null;
      this.host.classList.remove('wheel-running');
      if (this.resolve) this.resolve(false);
      this.resolve = null;
      this.pending = null;
      this.layout();
    }
  }
  window.UNOLuckWheel360 = Wheel360;
})();
