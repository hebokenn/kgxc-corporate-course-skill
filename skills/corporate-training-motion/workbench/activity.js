// Only real interactions, unsaved edits and playback hold the local service open.
// Workflow/job polling deliberately does not count as activity.
export function startActivity(isDirty, isPlaying=()=>[...document.querySelectorAll('video')].some(v=>!v.paused&&!v.ended)) {
 if(location.protocol==='file:')return;
 const client=crypto.randomUUID();let last=0,held=false,failures=0;
 async function ping(active=false){
  const dirty=Boolean(isDirty()),playing=Boolean(isPlaying());
  if(!active&&!dirty&&!playing&&!held)return;
  held=dirty||playing;
  try{const r=await fetch('/api/activity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:client,dirty,playing,active})});failures=r.ok?0:failures+1;}
  catch{failures++;}
  if(failures>=2)clearInterval(timer);
 }
 function interaction(){const now=Date.now();if(now-last<10000)return;last=now;void ping(true);}
 for(const name of ['pointerdown','keydown','input'])document.addEventListener(name,interaction);
 const timer=setInterval(()=>{void ping();},30000);
 window.addEventListener('pagehide',()=>{
  clearInterval(timer);
  navigator.sendBeacon('/api/activity',new Blob([JSON.stringify({client_id:client,dirty:false,playing:false,active:false})],{type:'application/json'}));
 });
}
