/* UNO LUCK Sound Cloud: sample-accurate ping-pong loop generator.
 * A full forward+reverse period is baked once; native AudioBufferSourceNode
 * looping has no seeks/timers at the seam. The same PCM feeds iOS HTML5 WAV.
 */
(() => {
  'use strict';
  const cap=(v,a,b)=>Math.max(a,Math.min(b,Number.isFinite(Number(v))?Number(v):a));
  function render(context,original,start,stop,crossfadeMs=140,maxSeconds=180){
    const sr=original.sampleRate;
    const begin=Math.floor(cap(start,0,original.duration)*sr);
    const end=Math.min(original.length,Math.ceil(cap(stop,start,original.duration)*sr));
    const n=end-begin;
    if(n<64)throw Error('Mirror Loop butuh minimal 64 sample audio');
    if(n/sr>maxSeconds)throw Error('Mirror Loop maksimal '+maxSeconds+' detik pada perangkat ini. Pendekkan START/STOP.');
    const crossfade=Math.min(Math.floor(cap(crossfadeMs,0,1000)*sr/1000),Math.floor(n/4));
    const length=2*(n-crossfade);
    // 2-channel maximum. Keep channel layout faithful for mono/stereo files.
    const channels=Math.min(original.numberOfChannels,2);
    const result=context.createBuffer(channels,length,sr);
    for(let channel=0;channel<channels;channel++){
      const input=original.getChannelData(channel),out=result.getChannelData(channel);
      let p=0;
      for(let j=crossfade;j<n-crossfade;j++)out[p++]=input[begin+j];
      for(let j=0;j<crossfade;j++){
        const w=(j+1)/(crossfade+1);
        out[p++]=(1-w)*input[begin+n-crossfade+j]+w*input[begin+n-1-j];
      }
      for(let j=crossfade;j<n-crossfade;j++)out[p++]=input[begin+n-1-j];
      for(let j=0;j<crossfade;j++){
        const w=(j+1)/(crossfade+1);
        out[p++]=(1-w)*input[begin+crossfade-1-j]+w*input[begin+j];
      }
      if(p!==length)throw Error('Mirror Loop sample count mismatch');
    }
    return {buffer:result,duration:result.duration,crossfadeSeconds:crossfade/sr};
  }
  function wavBlob(buffer){
    const channels=Math.min(buffer.numberOfChannels,2);
    const bytes=44+buffer.length*channels*2;
    const bytesView=new ArrayBuffer(bytes),v=new DataView(bytesView);
    const str=(index,value)=>{for(let j=0;j<value.length;j++)v.setUint8(index+j,value.charCodeAt(j));};
    str(0,'RIFF');v.setUint32(4,bytes-8,true);str(8,'WAVE');str(12,'fmt ');
    v.setUint32(16,16,true);v.setUint16(20,1,true);
    v.setUint16(22,channels,true);v.setUint32(24,buffer.sampleRate,true);
    v.setUint32(28,buffer.sampleRate*channels*2,true);
    v.setUint16(32,channels*2,true);v.setUint16(34,16,true);
    str(36,'data');v.setUint32(40,bytes-44,true);
    const sources=Array.from({length:channels},(_,i)=>buffer.getChannelData(i));
    let k=44;
    for(let i=0;i<buffer.length;i++)for(let ch=0;ch<channels;ch++){
      const value=cap(sources[ch][i],-1,1);
      v.setInt16(k,value<0?Math.round(value*32768):Math.round(value*32767),true);k+=2;
    }
    return new Blob([bytesView],{type:'audio/wav'});
  }
  window.UNOLuckMirrorLoop={render,wavBlob};
})();
