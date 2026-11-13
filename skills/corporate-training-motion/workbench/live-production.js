// Read-only display of producer-published files. Presence never constitutes acceptance.
export function createLiveProduction({document,window,fetch,mediaURL}){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const root=el('section',null,'live-workspace'),head=el('div',null,'live-heading'),title=el('h2','制作现场'),status=el('span','正在读取产物','live-status');
  head.append(title,status);root.append(head);
  const layout=el('div',null,'live-layout'),visual=el('div',null,'live-visual'),audioPane=el('aside',null,'live-audio');layout.append(visual,audioPane);root.append(layout);
  const strip=el('div',null,'live-strip');strip.setAttribute('aria-label','已保存的制作产物');root.append(strip);
  let items=[],selected=null,selectedAudio=null,signature='',timer,reading=false,closed=false,started=false,visibleVersion='';
  const key=x=>x.id||x.path;
  function source(x){return mediaURL(x.path)+'&v='+encodeURIComponent(x.sha256||x.mtime||x.bytes||'');}
  function showVisual(item){
    selected=key(item);visibleVersion=JSON.stringify([item.path,item.mtime,item.sha256]);visual.replaceChildren();
    if(item.kind==='image'){const image=el('img');image.src=source(item);image.alt=item.label||'当前已保存画面';visual.append(image);}
    else{const video=el('video');video.controls=true;video.preload='metadata';video.src=source(item);video.setAttribute('aria-label',item.label||'当前已保存样段');visual.append(video);}
    const caption=el('div',null,'live-caption');caption.append(el('strong',item.label||item.path.split('/').at(-1)),el('span',item.current===false?'历史素材 · 非当前版本':item.kind==='image'?'画面已出 · 未验收':'样段已出 · 未验收'));visual.append(caption);
    const media=visual.querySelector('img,video');media.addEventListener('error',()=>{status.textContent='文件暂时无法读取，稍后自动重试';});
  }
  function showAudio(item){selectedAudio=key(item);const player=audioPane.querySelector('audio');player.src=source(item);audioPane.querySelector('.live-audio-title').textContent=item.label||'已保存音轨';}
  function paint(){
    const pictures=items.filter(x=>x.kind==='image'||x.kind==='video'),sounds=items.filter(x=>x.kind==='audio');
    if(!pictures.length){visual.replaceChildren();const empty=el('div',null,'live-empty');empty.append(el('span','◌'),el('h3','画面生成后，会出现在这里'),el('p','不必等整段视频合成完成。'));visual.append(empty);selected=null;}
    else{const item=pictures.find(x=>key(x)===selected)||pictures[0];if(selected!==key(item)||!visual.querySelector('img,video'))showVisual(item);else if(visibleVersion!==JSON.stringify([item.path,item.mtime,item.sha256])&&!visual.querySelector('.live-update')){const update=el('button','此画面有新版本 · 点击查看','live-update');update.onclick=()=>showVisual(item);visual.append(update);}}
    if(!audioPane.querySelector('audio')){audioPane.append(el('h3','配音'),el('p','等待音轨保存','live-audio-title'));const audio=el('audio');audio.controls=true;audio.preload='metadata';audio.setAttribute('aria-label','试听已保存配音');audio.addEventListener('error',()=>{audioPane.querySelector('.live-audio-title').textContent='此音轨暂时无法播放，请查看文件';});audioPane.append(audio,el('div',null,'live-audio-list'));}
    audioPane.querySelector('audio').hidden=!sounds.length;
    const audioList=audioPane.querySelector('.live-audio-list');audioList.replaceChildren();
    for(const item of sounds){const b=el('button',item.label||item.path.split('/').at(-1));b.setAttribute('aria-pressed',String(key(item)===selectedAudio));b.onclick=()=>{showAudio(item);paintAudioSelection();};audioList.append(b);}
    if(sounds.length&&!sounds.some(x=>key(x)===selectedAudio))showAudio(sounds[0]);
    if(!sounds.length)audioPane.querySelector('.live-audio-title').textContent='配音保存后即可试听';
    strip.replaceChildren();for(const item of pictures){const b=el('button',null,'live-thumb');b.setAttribute('aria-label',item.label||'查看已保存画面');b.setAttribute('aria-pressed',String(key(item)===selected));if(item.kind==='image'){const img=el('img');img.src=source(item);img.alt='';b.append(img);}else b.append(el('span','▶','live-video-symbol'));b.append(el('span',item.label||'样段'));b.onclick=()=>{showVisual(item);paint();};strip.append(b);}
    paintAudioSelection();
  }
  function paintAudioSelection(){for(const [i,b] of [...audioPane.querySelectorAll('.live-audio-list button')].entries())b.setAttribute('aria-pressed',String(key(items.filter(x=>x.kind==='audio')[i])===selectedAudio));}
  async function poll(){if(closed||reading)return;reading=true;try{const response=await fetch('/api/studio/live-media');if(!response.ok)throw Error('无法读取');const value=await response.json();const next=Array.isArray(value.items)?value.items:[];const nextSignature=JSON.stringify(next);if(nextSignature!==signature){signature=nextSignature;items=next;paint();}status.textContent=items.length?'已保存 '+items.length+' 项 · 自动更新':'等待制作端保存产物';}catch{status.textContent='产物连接中断 · 正在重试';}finally{reading=false;clearTimeout(timer);if(!closed)timer=setTimeout(poll,3000);}}
  window.addEventListener('pagehide',()=>{closed=true;clearTimeout(timer);});
  return {mount(target){target.append(root);if(!started){started=true;paint();void poll();}},dispose(){closed=true;clearTimeout(timer);}};
}
