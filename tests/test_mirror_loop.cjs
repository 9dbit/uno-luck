/* Deterministic PCM Mirror Loop regression, no external audio or game ledger. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const window={};
vm.runInNewContext(fs.readFileSync('app/static/art/mirror-loop.js','utf8'),
  {window,Blob,Float32Array,ArrayBuffer,DataView,Math,Number,Error});
const engine=window.UNOLuckMirrorLoop;
const context={
  createBuffer(channels,length,sampleRate){
    const channelData=Array.from({length:channels},()=>new Float32Array(length));
    return {
      numberOfChannels:channels,length,sampleRate,duration:length/sampleRate,
      getChannelData(ch){return channelData[ch];}
    };
  }
};
const original=context.createBuffer(2,6000,1000);
for(let i=0;i<6000;i++){
  // 3 whole cycles in trimmed 2 seconds, deliberately not all-zero.
  original.getChannelData(0)[i]=Math.sin(i*.032)*.35;
  original.getChannelData(1)[i]=Math.cos(i*.032)*.25;
}
const out=engine.render(context,original,1,3,120);
assert.equal(out.crossfadeSeconds,.12);
assert.equal(out.buffer.numberOfChannels,2);
assert.equal(out.buffer.length,2*(2000-120));
assert.equal(out.buffer.duration,3.76);
for(let channel=0;channel<2;channel++){
  const arr=out.buffer.getChannelData(channel);
  for(const v of arr)assert.ok(Number.isFinite(v)&&Math.abs(v)<=1);
  // First and last sample of the loop must have a nearly continuous amplitude.
  assert.ok(Math.abs(arr[0]-arr[arr.length-1])<.1,'Loop wrap discontinuity');
  // Reverse traversal: second half follows the source backwards.
  const middle=Math.floor(arr.length/2);
  assert.ok(Math.abs(arr[middle+150]-
    original.getChannelData(channel)[2999-120-150])<.003,'Reverse half must mirror');
}
const plain=engine.render(context,original,1,3,0);
assert.equal(plain.buffer.length,4000);
assert.ok(Math.abs(plain.buffer.getChannelData(0)[0]-original.getChannelData(0)[1000])<1e-6);
assert.throws(()=>engine.render(context,original,1,3,150,1.5),/maksimal/);
(async()=>{
  const wav=engine.wavBlob(out.buffer);
  assert.equal(wav.type,'audio/wav');
  const bytes=new DataView(await wav.arrayBuffer());
  assert.equal(bytes.getUint32(4,true)+8,wav.size);
  assert.equal(bytes.getUint16(22,true),2);
  assert.equal(bytes.getUint32(24,true),1000);
  assert.equal(bytes.getUint32(40,true)+44,wav.size);
  process.stdout.write('PASS: mirrored forward/reverse PCM, crossfade seam, trim, stereo WAV for Safari\n');
})().catch(e=>{console.error(e);process.exitCode=1;});
