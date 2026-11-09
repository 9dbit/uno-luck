"use strict";
(() => {
 const original=window.fetch.bind(window),pendingKey='softtech_uno_launch';
 const params=new URLSearchParams(location.hash.slice(1)),launch=params.get('softtech_launch');
 if(launch){sessionStorage.setItem(pendingKey,launch);params.delete('softtech_launch');history.replaceState(null,'',location.pathname+location.search+(params.size?'#'+params:''));localStorage.removeItem('uno_orbit_pending_v08');}
 let phase=1,roundId=null;
 const ready=(async()=>{
  const token=sessionStorage.getItem(pendingKey);
  if(token){const r=await original('/api/agency/launch',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-UNO-Client':'spin-ui'},body:JSON.stringify({token})});if(!r.ok)throw Error('Open this game from Soft Tech or your operator.');sessionStorage.removeItem(pendingKey);}
  const r=await original('/api/agency/context',{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error('Provider session missing. Relaunch from Soft Tech.');
  const d=await r.json();const url=d.navigation?.home_url;
  if(url){const a=document.createElement('a');a.href=url;a.textContent='Back to operator';a.rel='noopener';a.setAttribute('aria-label','Return to operator');a.className='provider-return';document.body.append(a);}
 })();
 ready.catch(()=>{});
 window.fetch=async(input,init={})=>{
  const path=typeof input==='string'?input:input.url;
  if(!path.startsWith('/api/orbit'))return original(input,init);
  try{await ready;}catch(e){return new Response(JSON.stringify({detail:e.message}),{status:401,headers:{'Content-Type':'application/json'}});}
  const target=path.replace('/api/orbit','/api/agency'),options={...init};
  if(target.endsWith('/pick')){
   const p=JSON.parse(init.body||'{}');let saved;try{saved=JSON.parse(localStorage.getItem('uno_orbit_pending_v08')||'null');}catch{}
   const expected=saved?.id===p.request_id?saved.expected:phase;
   options.body=JSON.stringify({...p,expected_phase:expected,round_id:expected>1?roundId:null});
  }
  const response=await original(target,options);
  if(response.ok){const d=await response.clone().json();if(d.round&&!d.round.complete){phase=d.round.picked+1;roundId=d.round.id;}else{phase=1;roundId=null;}}
  return response;
 };
 const style=document.createElement('link');style.rel='stylesheet';style.href='/assets/provider.css';document.head.append(style);
})();
