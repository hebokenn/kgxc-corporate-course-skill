import {displayFrame,sourceFrame,totalFrames} from '/renderer.js';
import {segments,rippleCut} from '/timeline.js';
import {startActivity} from '/activity.js';
const $=id=>document.getElementById(id),clone=x=>structuredClone(x);
let doc,revision=0,dirty=false,frame=0,selectedCaption='',selectedScene='',selectedField='',selectedAsset='';
let undo=[],redo=[],wave,renderer,renderPending=null,rendering=false,playing=false,audioKey='',scale=1,dragging=false;
let editSerial=0,saveTask=null,mediaTask=null,loadingRenderer=false,rendererDirty=false;
let cutStart=0,cutEnd=30,previewEnd=null,playRequest=0;
startActivity(()=>dirty,()=>playing);
const audio=$('audio');
const seconds=f=>f/doc.fps;
const source=f=>sourceFrame(f,doc.holds,doc.cuts);
const display=f=>displayFrame(f,doc.holds,doc.cuts);
const soundKey=()=>JSON.stringify([doc.holds,doc.cuts||[],doc.audio.gain]);
function time(f){const cs=Math.floor(f*100/doc.fps);return `${Math.floor(cs/6000).toString().padStart(2,'0')}:${(Math.floor(cs/100)%60).toString().padStart(2,'0')}.${(cs%100).toString().padStart(2,'0')}`}
function toast(text,error=false){$('toast').textContent=text;$('toast').classList.toggle('error',error);$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,error?8000:3500)}
async function api(url,data){const response=await fetch(url,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw Error(value.error||'请求失败');return value}
function status(){ $('save-state').textContent=dirty?'● 有未保存修改':doc.status==='draft'?'草稿 · 待接入内容配音':'已保存';$('revision-label').textContent=`版本 r${revision} · ${doc.captions.length} 条字幕`;$('undo').disabled=!undo.length;$('redo').disabled=!redo.length;$('project-name').textContent=doc.title;}
async function applyRenderer(){if(!renderer)return;rendererDirty=true;if(loadingRenderer)return;loadingRenderer=true;try{while(rendererDirty){rendererDirty=false;await renderer.load(clone(doc));paint(frame)}}catch(e){showError(e.message)}finally{loadingRenderer=false}}
function showError(text){$('preview-error').textContent=text;$('preview-error').hidden=false}
async function paint(f){renderPending=f;if(rendering||!renderer)return;rendering=true;while(renderPending!==null){const target=renderPending;renderPending=null;try{await renderer.drawFrame(target);$('preview-error').hidden=true}catch(e){showError(e.message)}}rendering=false;}
function sceneAt(f){const sf=source(f);return doc.scenes.find(s=>s.sourceStartFrame<=sf&&sf<s.sourceEndFrame)||(sf<doc.scenes[0]?.sourceStartFrame?doc.scenes[0]:doc.scenes.at(-1))}
function cueAt(f){return doc.captions.find(c=>c.startFrame<=f&&f<c.endFrame)}
function seek(f,moveAudio=true){frame=Math.max(0,Math.min(totalFrames(doc)-1,Math.round(f)));$('seek').value=frame;$('timecode').textContent=time(frame);$('playhead').style.left=frame*scale+'px';const s=sceneAt(frame);$('scene-title').textContent=s?.title||'课程预览';const c=cueAt(frame);$('caption-now').textContent=c?.text||'此处没有字幕';if(moveAudio&&audio.readyState>=1)audio.currentTime=Math.min(seconds(frame),audio.duration||seconds(frame));paint(frame);}
function mark(change){undo.push(clone(doc));if(undo.length>100)undo.shift();redo=[];try{change(doc);editSerial++;dirty=true;refresh();applyRenderer()}catch(e){doc=undo.pop();toast(e.message,true);refresh()}}
function refresh(){status();$('scene-count').textContent=doc.scenes.length+' 节';$('total-time').textContent=time(totalFrames(doc));$('seek').max=totalFrames(doc)-1;$('voice-note').textContent=doc.audio.voice+' · 原速';cutStart=Math.min(cutStart,totalFrames(doc)-1);cutEnd=Math.min(cutEnd,totalFrames(doc));renderScenes();renderTimeline();refreshInspector();refreshCut();seek(frame,false);}
function option(value,text){const o=document.createElement('option');o.value=value;o.textContent=text;return o}
function renderScenes(){const list=$('scene-list');list.replaceChildren();let chapter='';for(const s of doc.scenes){if(chapter!==(s.chapter||'')){chapter=s.chapter||'';const h=document.createElement('div');h.className='chapter-title';h.textContent=chapter;list.append(h)}const b=document.createElement('button');b.className='scene-row'+(s.id===selectedScene?' selected':'');b.dataset.sceneId=s.id;b.append(document.createTextNode(s.title||s.id));const times=document.createElement('span');times.textContent=time(display(s.sourceStartFrame))+' — '+time(display(s.sourceEndFrame));b.append(times);b.onclick=()=>selectScene(s.id);list.append(b)}}
function selectScene(id){selectedScene=id;const s=doc.scenes.find(x=>x.id===id);seek(display(s.sourceStartFrame));renderScenes();renderTimeline();refreshInspector();}
function tab(name){for(const b of document.querySelectorAll('[data-tab]'))b.setAttribute('aria-selected',String(b.dataset.tab===name));for(const n of ['captions','visual','assets','cut'])$('pane-'+n).hidden=n!==name;$('cut-selection').hidden=name!=='cut'||cutEnd<=cutStart;}
function selectCaption(id){selectedCaption=id;const c=doc.captions.find(x=>x.id===id);if(!c)return;selectedScene=c.sceneId||selectedScene;tab('captions');seek(c.startFrame);refreshInspector();renderTimeline();renderScenes();$('selection-label').textContent=id+' · '+time(c.startFrame);}
function refreshInspector(){
 $('caption-select').replaceChildren(...doc.captions.map(c=>option(c.id,c.id+' '+c.text.slice(0,22))));if(!doc.captions.some(c=>c.id===selectedCaption))selectedCaption=doc.captions[0]?.id||'';$('caption-select').value=selectedCaption;
 const c=doc.captions.find(x=>x.id===selectedCaption);if(c){$('caption-text').value=c.text;$('caption-start').value=seconds(c.startFrame).toFixed(3);$('caption-end').value=seconds(c.endFrame).toFixed(3)}
 $('caption-size').value=doc.captionStyle.fontSize;$('caption-y').value=doc.captionStyle.y;
 $('visual-scene').replaceChildren(...doc.scenes.map(s=>option(s.id,s.id+' '+(s.title||s.id))));$('visual-scene').value=selectedScene;
 const s=doc.scenes.find(x=>x.id===selectedScene);$('hold-seconds').value=s?seconds(doc.holds.find(h=>h.sceneId===s.id)?.frames||0).toFixed(2):0;
 let fields=doc.fields.filter(f=>!f.sceneId||f.sceneId===selectedScene||f.objectId===selectedScene||f.objectId.startsWith(selectedScene+'-'));
 if(!fields.length)fields=doc.fields;
 if(!fields.some(f=>f.id===selectedField))selectedField=fields[0]?.id||'';
 $('field-select').replaceChildren(...fields.map(f=>option(f.id,f.property==='text'?'文字 · '+String(f.text||f.label).slice(0,28):f.label)));$('field-select').value=selectedField;fillField();
 if(!doc.assets.some(a=>a.id===selectedAsset))selectedAsset=doc.assets[0]?.id||'';
 $('asset-select').replaceChildren(...doc.assets.map(a=>option(a.id,a.label)));$('asset-select').value=selectedAsset;fillAsset();$('asset-count').textContent=doc.assets.length+' 项';
}
function fillField(){const f=doc.fields.find(x=>x.id===selectedField);if(!f)return;$('field-text').value=f.text;$('field-text').disabled=f.property==='position';$('field-x').value=f.dx;$('field-y').value=f.dy;}
function fillAsset(){const a=doc.assets.find(x=>x.id===selectedAsset);if(!a)return;$('asset-image').src='/project/'+a.path;$('asset-path').textContent=a.path;}
function assertCue(c,ignoreId){if(!c.text.trim()||/[\r\n\p{P}]/u.test(c.text))throw Error('字幕须为单行无标点，请先整理文字');if(c.startFrame<0||c.endFrame>totalFrames(doc)||c.startFrame>=c.endFrame)throw Error('字幕起止时间无效');if(doc.captions.some(x=>x.id!==ignoreId&&x.startFrame<c.endFrame&&x.endFrame>c.startFrame))throw Error('字幕与相邻条目重叠，请调整起止时间');}
function renderTimeline(){
 const scroll=$('timeline-scroll'),w=Math.max(500,scroll.clientWidth)*Number($('zoom').value);scale=w/totalFrames(doc);$('timeline-content').style.width=w+'px';
 $('ruler').replaceChildren();const total=seconds(totalFrames(doc)),pxPerSec=scale*doc.fps,step=pxPerSec>50?1:pxPerSec>15?5:pxPerSec>5?15:60;
 for(let t=0;t<=total;t+=step){const tick=document.createElement('span');tick.className='tick';tick.style.left=t*pxPerSec+'px';tick.textContent=time(t*doc.fps);$('ruler').append(tick)}
 $('scene-track').replaceChildren();for(const s of doc.scenes){const a=display(s.sourceStartFrame),b=display(s.sourceEndFrame);if(a===b)continue;const e=clip('scene',s.id,s.title||s.id,a,b);e.classList.toggle('selected',s.id===selectedScene);e.onclick=ev=>{ev.stopPropagation();selectScene(s.id);tab('visual')};$('scene-track').append(e)}
 $('caption-track').replaceChildren();for(const c of doc.captions){const e=clip('subtitle',c.id,c.text,c.startFrame,c.endFrame);e.dataset.captionId=c.id;e.classList.toggle('selected',c.id===selectedCaption);for(const end of ['left','right']){const h=document.createElement('span');h.className='handle '+end;h.dataset.end=end;h.setAttribute('aria-label',end==='left'?'调整字幕起点':'调整字幕终点');e.append(h)}e.addEventListener('pointerdown',ev=>startDrag(ev,c,e));e.onclick=ev=>{ev.stopPropagation();if(!dragging)selectCaption(c.id)};$('caption-track').append(e)}
 $('hold-track').replaceChildren();for(const h of doc.holds){const a=display(h.sourceFrame)-h.frames;const e=clip('hold','hold-'+h.sourceFrame,'停留 '+seconds(h.frames).toFixed(1)+'s',a,a+h.frames);e.onclick=ev=>{ev.stopPropagation();pause();seek(a);setCutRange(a,a+h.frames);tab('cut')};$('hold-track').append(e)}
 drawWave();refreshCutOverlay();$('playhead').style.left=frame*scale+'px';
}
function clip(type,id,text,a,b){const e=document.createElement('div');e.className='clip '+type;e.dataset.id=id;e.style.left=a*scale+'px';e.style.width=Math.max(2,(b-a)*scale)+'px';e.textContent=text;e.title=text+' · '+time(a)+' — '+time(b);return e}
function refreshCutOverlay(){const e=$('cut-selection');e.style.left=cutStart*scale+'px';e.style.width=Math.max(0,(cutEnd-cutStart)*scale)+'px';e.hidden=$('pane-cut').hidden||cutEnd<=cutStart;}
function refreshCut(writeInputs=true){
 if(writeInputs){$('cut-start').value=seconds(cutStart).toFixed(3);$('cut-end').value=seconds(cutEnd).toFixed(3);}
 const valid=Number.isInteger(cutStart)&&Number.isInteger(cutEnd)&&cutStart>=0&&cutStart<cutEnd&&cutEnd<=totalFrames(doc)&&cutEnd-cutStart<totalFrames(doc);
 $('apply-cut').disabled=!valid||doc.status==='draft';$('preview-cut').disabled=!valid||!doc.media.audio;
 const covered=doc.captions.filter(c=>cutStart<=c.startFrame&&c.endFrame<=cutEnd).length;
 $('cut-summary').textContent=valid?`将裁掉 ${seconds(cutEnd-cutStart).toFixed(3)} 秒 · 剩余 ${seconds(totalFrames(doc)-cutEnd+cutStart).toFixed(3)} 秒${covered?' · 移除 '+covered+' 条完全位于选区的字幕':''}`:'请选择有效区间 至少保留一帧课程';
 $('cut-count').textContent=`已裁原片 ${seconds((doc.cuts||[]).reduce((n,c)=>n+c.endFrame-c.startFrame,0)).toFixed(3)} 秒`;
 refreshCutOverlay();
}
function setCutRange(a,b,writeInputs=true){cutStart=a;cutEnd=b;refreshCut(writeInputs);}
function readCutRange(){setCutRange(Math.round(Number($('cut-start').value)*doc.fps),Math.round(Number($('cut-end').value)*doc.fps),false);}
for(const id of ['cut-start','cut-end'])$(id).oninput=readCutRange;
$('cut-in').onclick=()=>setCutRange(frame,cutEnd);
$('cut-out').onclick=()=>setCutRange(cutStart,frame);
$('open-cut').onclick=()=>{pause();if(cutEnd<=cutStart)setCutRange(frame,Math.min(totalFrames(doc),frame+doc.fps));tab('cut');refreshCut()};
$('preview-cut').onclick=async()=>{try{readCutRange();if(cutEnd<=cutStart||cutStart<0||cutEnd>totalFrames(doc))throw Error('请选择有效裁剪区间');pause();seek(cutStart);previewEnd=cutEnd;await play()}catch(e){toast(e.message,true)}};
$('apply-cut').onclick=()=>{try{readCutRange();const a=cutStart,b=cutEnd,next=rippleCut(doc,a,b);pause();mark(d=>Object.assign(d,next));const at=Math.min(a,totalFrames(doc)-1);setCutRange(at,at);seek(at);toast(`已裁掉 ${seconds(b-a).toFixed(3)} 秒 画面配音字幕已同步前移 可撤销`)}catch(e){toast(e.message,true)}};
// Shift-drag across the waveform/ruler selects an interval; ordinary dragging still seeks.
for(const id of ['audio-track','ruler'])$(id).addEventListener('pointerdown',ev=>{
 if(!ev.shiftKey||ev.button!==0)return;ev.preventDefault();ev.stopPropagation();pause();
 const el=ev.currentTarget,toFrame=e=>Math.max(0,Math.min(totalFrames(doc),Math.round((e.clientX-$('timeline-content').getBoundingClientRect().left)/scale))),anchor=toFrame(ev);
 el.setPointerCapture(ev.pointerId);tab('cut');
 const move=e=>{const f=toFrame(e);setCutRange(Math.min(anchor,f),Math.max(anchor,f))};
 const up=e=>{move(e);el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',up);el.removeEventListener('pointercancel',up)};
 el.addEventListener('pointermove',move);el.addEventListener('pointerup',up);el.addEventListener('pointercancel',up);
});
function drawWave(){if(!wave)return;const c=$('waveform'),width=Math.min(24000,Math.ceil(totalFrames(doc)*scale)),height=35;c.width=width;c.height=height;const x=c.getContext('2d');x.fillStyle='#ffffff';x.fillRect(0,0,width,height);x.fillStyle='#888888';const spans=segments(doc);let si=0;for(let i=0;i<width;i+=2){const f=Math.min(totalFrames(doc)-1,Math.floor(i/width*totalFrames(doc)));while(si<spans.length-1&&f>=spans[si].endFrame)si++;const s=spans[si];let peak=0;if(s?.kind==='source'){const t=seconds(s.sourceFrame+f-s.startFrame);peak=wave.peaks[Math.min(wave.peaks.length-1,Math.floor(t/wave.duration*wave.peaks.length))]||0}const h=Math.max(1,peak*30);x.fillRect(i,(35-h)/2,1,h)}}
function startDrag(ev,c,el){if(ev.button!==0)return;ev.preventDefault();const startX=ev.clientX,original=clone(c),end=ev.target.dataset.end;let a=c.startFrame,b=c.endFrame,moved=false;const prev=doc.captions.filter(x=>x.endFrame<=c.startFrame&&x.id!==c.id).at(-1)?.endFrame||0;const next=doc.captions.find(x=>x.startFrame>=c.endFrame&&x.id!==c.id)?.startFrame||totalFrames(doc);el.setPointerCapture(ev.pointerId);
 function move(e){const delta=Math.round((e.clientX-startX)/scale);moved=moved||Math.abs(e.clientX-startX)>3;if(end==='left')a=Math.max(prev,Math.min(original.endFrame-1,original.startFrame+delta));else if(end==='right')b=Math.min(next,Math.max(original.startFrame+1,original.endFrame+delta));else{const d=Math.max(prev-original.startFrame,Math.min(next-original.endFrame,delta));a=original.startFrame+d;b=original.endFrame+d}el.style.left=a*scale+'px';el.style.width=Math.max(2,(b-a)*scale)+'px';$('selection-label').textContent=c.id+' · '+time(a)+' — '+time(b);}
 function up(){el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',up);dragging=moved;if(moved){selectedCaption=c.id;mark(d=>{const cue=d.captions.find(x=>x.id===c.id);cue.startFrame=a;cue.endFrame=b;assertCue(cue,c.id)});seek(a);refreshInspector()}else selectCaption(c.id);setTimeout(()=>dragging=false,30)}
 el.addEventListener('pointermove',move);el.addEventListener('pointerup',up);
}
async function save(){
 if(mediaTask)await mediaTask;
 if(saveTask){await saveTask;if(dirty)return save();return doc}
 if(!dirty)return doc;
 saveTask=(async()=>{while(dirty){const serial=editSerial,snapshot=clone(doc),saved=await api('/api/save',{document:snapshot,baseRevision:revision});revision=saved.revision;
   if(editSerial===serial){doc=saved;dirty=false}else{doc.revision=revision;dirty=true}status();}
   toast('已保存到本地工程 · r'+revision);return doc;
 })();try{return await saveTask}finally{saveTask=null}
}

function restored(value){const currentRevision=revision;doc=clone(value);doc.revision=currentRevision;editSerial++;dirty=true;refresh();applyRenderer();}
async function prepareAudio(){const key=soundKey();if(key!==audioKey){toast('正在准备同步音轨');const result=await api('/api/preview-audio',{document:clone(doc)});if(key!==soundKey())return false;audio.src=result.url;await new Promise((resolve,reject)=>{audio.onloadedmetadata=resolve;audio.onerror=()=>reject(Error('音轨加载失败'));audio.load()});if(key!==soundKey())return false;audioKey=key;}audio.currentTime=seconds(frame);return true;}
async function play(){try{if(playing){pause();return}const request=++playRequest;if(!await prepareAudio()||request!==playRequest)return;await audio.play();if(request!==playRequest){audio.pause();return}playing=true;$('play').textContent='Ⅱ';clock(request)}catch(e){toast(e.message,true)}}
function pause(){playRequest++;playing=false;previewEnd=null;audio.pause();$('play').textContent='▶'}
function clock(request){if(!playing||request!==playRequest)return;seek(Math.round(audio.currentTime*doc.fps),false);const scroll=$('timeline-scroll');const x=frame*scale;if(x>scroll.scrollLeft+scroll.clientWidth-45)scroll.scrollLeft=x-80;if(previewEnd!==null&&frame>=previewEnd){const end=previewEnd;pause();seek(end)}else if(audio.ended||frame>=totalFrames(doc)-1)pause();else requestAnimationFrame(()=>clock(request))}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>tab(b.dataset.tab);
$('toggle-chapters').onclick=()=>document.body.classList.toggle('chapters-open');
$('caption-select').onchange=()=>selectCaption($('caption-select').value);
$('visual-scene').onchange=()=>selectScene($('visual-scene').value);
$('field-select').onchange=()=>{selectedField=$('field-select').value;fillField()};
$('asset-select').onchange=()=>{selectedAsset=$('asset-select').value;fillAsset()};
$('apply-caption').onclick=()=>{const c=doc.captions.find(x=>x.id===selectedCaption);if(!c)return;const edited={...c,text:$('caption-text').value.trim(),startFrame:Math.round(Number($('caption-start').value)*doc.fps),endFrame:Math.round(Number($('caption-end').value)*doc.fps)};try{assertCue(edited,c.id);mark(d=>Object.assign(d.captions.find(x=>x.id===c.id),edited));seek(edited.startFrame);toast('字幕已应用，原录音保持不变')}catch(e){toast(e.message,true)}};
$('clean-caption').onclick=async()=>{try{$('caption-text').value=(await api('/api/clean-caption',{text:$('caption-text').value})).text}catch(e){toast(e.message,true)}};
$('split-caption').onclick=()=>{const c=doc.captions.find(x=>x.id===selectedCaption);if(!c||frame<=c.startFrame||frame>=c.endFrame){toast('先把播放头移到当前字幕中间',true);return}const ratio=(frame-c.startFrame)/(c.endFrame-c.startFrame),text=[...c.text],cut=Math.max(1,Math.min(text.length-1,Math.round(text.length*ratio)));mark(d=>{const i=d.captions.findIndex(x=>x.id===c.id);d.captions.splice(i,1,{...c,endFrame:frame,text:text.slice(0,cut).join('')},{...c,id:c.id+'-'+crypto.randomUUID().slice(0,5),startFrame:frame,text:text.slice(cut).join('')})});toast('已按当前位置拆分，请检查完整语块与听读节奏')};
$('merge-caption').onclick=()=>{const i=doc.captions.findIndex(x=>x.id===selectedCaption);if(i<0||i>=doc.captions.length-1)return;mark(d=>{const a=d.captions[i],b=d.captions[i+1];a.text+=b.text;a.endFrame=b.endFrame;d.captions.splice(i+1,1)});toast('已合并，请检查实际单行宽度')};
$('apply-style').onclick=()=>{const size=Number($('caption-size').value),y=Number($('caption-y').value);if(size<24||size>64||y<940||y>1025){toast('字号24—64，垂直位置940—1025',true);return}mark(d=>Object.assign(d.captionStyle,{fontSize:size,y}))};
$('apply-field').onclick=()=>{const id=selectedField,text=$('field-text').value,dx=Number($('field-x').value),dy=Number($('field-y').value);if(Math.abs(dx)>500||Math.abs(dy)>500){toast('位移范围为±500',true);return}mark(d=>Object.assign(d.fields.find(x=>x.id===id),{text,dx,dy}));toast('画面文字与位置已应用')};
$('apply-hold').onclick=()=>{const s=doc.scenes.find(x=>x.id===selectedScene);if(!s)return;const value=Number($('hold-seconds').value);if(value<0||value>60){toast('单处停留范围为0至60秒',true);return}const existing=doc.holds.find(h=>h.sceneId===s.id);let position=existing?.sourceFrame??s.sourceEndFrame;const boundary=display(position);const crossing=doc.captions.find(c=>c.startFrame<boundary&&c.endFrame>boundary);if(!existing&&crossing)position=source(crossing.endFrame);if(position>=doc.sourceDurationFrames){toast('末尾请使用片尾的稳定停留',true);return}if(value>0&&doc.continuityPolicy?.required){const planned=doc.continuityPlan?.pauses?.find(p=>p.sceneId===s.id&&['practice','observation','brand'].includes(p.kind)&&p.window.startFrame<=position&&position<p.window.endFrame);if(!planned){toast('此位置未安排作答或观察任务；阅读时间请通过保留要点和调整画面编排解决',true);return}if(value>planned.maxSeconds){toast('超出本任务的停顿预算，请先核对作答提示及总静音时长',true);return}}const old=doc.holds.find(h=>h.sourceFrame===position)?.frames||0,newFrames=Math.round(value*doc.fps),begin=display(position)-old,oldEnd=begin+old,delta=newFrames-old;if(!delta)return;
 if(!old&&doc.captions.some(c=>c.startFrame<begin&&c.endFrame>begin)){toast('该位置仍有跨界字幕，请先调整字幕边界',true);return}
 pause();mark(d=>{d.holds=d.holds.filter(h=>h.sourceFrame!==position);if(newFrames)d.holds.push({sourceFrame:position,frames:newFrames,sceneId:s.id});d.holds.sort((a,b)=>a.sourceFrame-b.sourceFrame);for(const c of d.captions){if(c.startFrame>=oldEnd)c.startFrame+=delta;else if(c.startFrame>begin)c.startFrame=begin+newFrames;if(c.endFrame>begin)c.endFrame=Math.max(c.startFrame+1,c.endFrame+delta)}});seek(Math.max(0,begin-1));toast('已更新任务停顿；保存和导出时继续检查实际旁白与总静音时长')};
$('asset-upload').onchange=()=>{const file=$('asset-upload').files[0];if(!file)return;const id=selectedAsset;
 mediaTask=(async()=>{try{toast('正在导入图片');const response=await fetch('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name)},body:file});const result=await response.json();if(!response.ok)throw Error(result.error);mark(d=>d.assets.find(x=>x.id===id).path=result.path);toast('素材已替换，原文件保留')}catch(e){toast(e.message,true);throw e}finally{$('asset-upload').value=''}})();
 const current=mediaTask;current.catch(()=>{}).finally(()=>{if(mediaTask===current)mediaTask=null});
};
$('reset-asset').onclick=()=>{mark(d=>{const a=d.assets.find(x=>x.id===selectedAsset);a.path=a.originalPath})};
$('save').onclick=()=>save().catch(e=>toast(e.message,true));
$('undo').onclick=()=>{if(!undo.length)return;redo.push(clone(doc));restored(undo.pop());};
$('redo').onclick=()=>{if(!redo.length)return;undo.push(clone(doc));restored(redo.pop());};
$('history').onclick=async()=>{try{const list=await api('/api/history');$('history-list').replaceChildren();for(const item of [...list].reverse()){const row=document.createElement('div');row.className='history-row';const label=document.createElement('span');label.textContent='已保存版本 r'+item.revision;const b=document.createElement('button');b.textContent='恢复到草稿';b.onclick=async()=>{try{const past=await api('/api/history/'+item.revision);undo.push(clone(doc));redo=[];restored(past);$('history-dialog').close()}catch(e){toast(e.message,true)}};row.append(label,b);$('history-list').append(row)}if(!list.length)$('history-list').textContent='首次保存后将保留上一版工程。';$('history-dialog').showModal()}catch(e){toast(e.message,true)}};
$('close-history').onclick=()=>$('history-dialog').close();
$('play').onclick=play;$('prev-frame').onclick=()=>{pause();seek(frame-1)};$('next-frame').onclick=()=>{pause();seek(frame+1)};$('seek').oninput=()=>{pause();seek(Number($('seek').value))};
$('caption-now').onclick=()=>{const c=cueAt(frame);if(c)selectCaption(c.id)};
$('current-scene').onclick=()=>{const s=sceneAt(frame);if(s){selectedScene=s.id;renderScenes();refreshInspector();document.querySelector(`[data-scene-id="${s.id}"]`)?.scrollIntoView({block:'nearest'})}};
$('zoom').oninput=renderTimeline;
for(const id of ['ruler','scene-track','audio-track','caption-track','hold-track'])$(id).onclick=e=>{if(e.shiftKey||e.target.closest('.clip'))return;pause();const x=e.clientX-$('timeline-content').getBoundingClientRect().left;seek(x/scale)};
window.addEventListener('resize',()=>{if(doc)renderTimeline()});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
document.addEventListener('keydown',e=>{const input=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName);if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save().catch(x=>toast(x.message,true))}if(!input&&(e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'){e.preventDefault();$(e.shiftKey?'redo':'undo').click()}if(!input&&e.code==='Space'){e.preventDefault();play()}});
$('export').onclick=async()=>{$('export-purpose-label').hidden=true;$('export-purpose').value='';try{const flow=await api('/api/workflow');if(flow.workflow_schema===2){$('export-purpose-label').hidden=false;$('export-purpose').value=flow.gates.some(g=>g.id==='pilot'&&g.status==='confirmed')?'final':'pilot';}}catch{}$('export-dialog').showModal();setExportRange()};
function setExportRange(){const kind=$('export-range').value,s=doc.scenes.find(x=>x.id===selectedScene);if(kind==='all'){$('export-start').value=0;$('export-end').value=seconds(totalFrames(doc)).toFixed(6)}else if(kind==='scene'&&s){$('export-start').value=seconds(display(s.sourceStartFrame)).toFixed(6);$('export-end').value=seconds(display(s.sourceEndFrame)).toFixed(6)}}
$('export-range').onchange=setExportRange;
$('start-export').onclick=async()=>{try{$('start-export').disabled=true;await save();const job=await api('/api/export',{revision,start:Number($('export-start').value),end:Number($('export-end').value),purpose:$('export-purpose').value||null});$('export-dialog').close();$('job-panel').hidden=false;$('job-links').replaceChildren();pollJob(job.id)}catch(e){toast(e.message,true)}finally{$('start-export').disabled=false}};
async function pollJob(id){try{const job=await api('/api/jobs/'+id);$('job-progress').value=job.progress||0;$('job-status').textContent=job.status==='complete'?'导出完成 · 技术检查通过':['failed','missing'].includes(job.status)?'导出失败':'正在导出 '+Math.round((job.progress||0)*100)+'%';if(job.status==='complete'){for(const [key,label]of [['video','视频 MP4'],['srt','字幕 SRT'],['package','可编辑工程 ZIP']]){const a=document.createElement('a');a.href=job[key];a.textContent=label;a.download='';$('job-links').append(a)}toast('视频、字幕与工程包已生成')}else if(['failed','missing'].includes(job.status)){const message=document.createElement('p');message.textContent=job.error;$('job-links').append(message);toast('导出失败，请查看记录',true)}else setTimeout(()=>pollJob(id),700)}catch(e){toast(e.message,true)}}
async function boot(){try{doc=await api('/api/document');revision=doc.revision;if(doc.media.audio)audio.src='/api/audio';$('play').disabled=!doc.media.audio;$('export').disabled=doc.status==='draft';selectedScene=doc.scenes[0]?.id;selectedCaption=doc.captions[0]?.id;audioKey=soundKey();refresh();api('/api/waveform').then(x=>{wave=x;drawWave()}).catch(e=>toast(e.message,true));const view=$('preview');for(let i=0;i<700&&!view.contentWindow.ready;i++)await new Promise(r=>setTimeout(r,30));if(!view.contentWindow.ready)throw Error(view.contentWindow.renderError||'预览引擎未就绪');renderer=view.contentWindow.courseRenderer;await applyRenderer();api('/api/jobs').then(jobs=>{const last=jobs.at(-1);if(last){$('job-panel').hidden=false;pollJob(last.id)}}).catch(()=>{});window.workbench={get document(){return clone(doc)},get frame(){return frame},seek,save,selectScene,selectCaption,tab};status()}catch(e){toast(e.message,true);showError(e.message)}}
boot();
