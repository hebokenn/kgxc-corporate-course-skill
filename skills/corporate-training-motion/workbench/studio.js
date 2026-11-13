import {createProductionOverview,materialStatuses,materialRows} from '/production-overview.js';
import {createLiveProduction} from '/live-production.js';
import {paragraphAt,replaceSelection,previewDocument} from '/script-editor-model.js';
import {totalFrames,displayFrame} from '/timeline.js';
import {startActivity} from '/activity.js';
import {productionProgress,activeJobs,productionJobHistory,exportRecovery} from '/production-progress.js';
import {createProductionPreferences,productionPreferenceSummary} from '/production-preferences.js';
import {createReviewPanel,requiresUserAudio} from '/review-panel.js';
import {createSourceCoveragePanel} from '/source-coverage.js';

export function mountStudio({document=globalThis.document,window=globalThis.window,location=globalThis.location,parent=window.parent,fetch=globalThis.fetch,Audio=globalThis.Audio,resourceBase='',native=false}={}){
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const stage=params.get('stage')||'outline',parentOrigin=params.get('parentOrigin');
const finalPhase=stage==='final'?(params.get('phase')==='body'?'body':'post'):null;
const titles={sources:'资料',outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课交付'};
let data,serial=0,savedSerial=0,saveTask,saveTimer,selectedUnit,selectedSegment,selectedSource,sourcePage=1,hostReady=false,aiBusy=false,selection;
let renderer,previewState,previewFrame=0,playing=false,playEpoch=0,previewTimer,pollTimer,closed=false;
let confirmationDisplay;
let progressJobs=[],progressReading=false,progressError='',nativeProduction,lastNativeIssue,computerExportAt=0;
const pending=new Map(),audio=new Audio();
const confirmationStages=new Set(['script','pilot','final']);
const reviews=createReviewPanel({readOnly:true,document,window,getData:()=>data,getStage:()=>stage,host,action,save,refresh,mediaURL:fileURL,
  openSourceCoverage:()=>sourceCoverage.open(),isBusy:()=>aiBusy||serial!==savedSerial||!!saveTask||activeJobs(progressJobs)||activeJobs(data?.jobs),onError:error=>notice(error.message,true),
  onState:()=>{if(data){primaryState();paintProgress();announce();}}});
const sourceCoverage=createSourceCoveragePanel({readOnly:true,document,getData:()=>data,action,host,onError:error=>notice(error.message,true),isBusy:()=>aiBusy||serial!==savedSerial||!!saveTask||activeJobs(progressJobs)||activeJobs(data?.jobs)});
const productionPreferences=createProductionPreferences({document,window,
  getValue:()=>data?.production_preferences,
  saveChoice:args=>action('production-choice',args),
  onError:error=>notice(error.message,true),
  uploadReference:async file=>{if(file.size>25*1024*1024)throw Error('参考图最大25MB。');const response=await fetch('/api/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name)},body:file});const result=await response.json();if(!response.ok||result.error)throw Error(result.error||'参考图上传未完成');return result;},
});
function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(className)node.className=className;return node;}
function notice(text='',bad=false){$('notice').hidden=!text;$('notice').textContent=text;$('notice').setAttribute('role',bad?'alert':'status');}
function button(label,action,className){const b=el('button',label,className);b.onclick=()=>Promise.resolve(action()).catch(e=>notice(e.message,true));return b;}
function link(path,label){const a=el('a',label);a.href=fileURL(path);a.target='_blank';a.rel='noopener';return a;}
function resourceURL(path){return resourceBase+path;}
function fileURL(path){return resourceURL('/course-file?path=')+encodeURIComponent(path);}
function stamp(seconds){return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(Math.floor(seconds%60)).padStart(2,'0');}
function fullText(sections=data.sections){return sections.some(s=>s.body?.trim())?sections.map((s,i)=>'## '+(i+1)+'. '+s.title+'\n\n'+s.body.trim()).join('\n\n').trim():'';}
function section(){return data.sections.find(s=>s.unit_id===selectedUnit)||data.sections[0];}
function draftKey(){return 'kgxc-studio-draft:'+data.course_id+':'+stage;}
async function api(path,value,headers={}){const response=await fetch(path,value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(value)});const result=await response.json();if(!response.ok||result.error||result.ok===false)throw Error(result.error||'操作未完成');return result;}
function host(action,args={}){if(!hostReady)throw Error('请从 DSH 课程工作台内使用 AI。');const id=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('AI 连接尚未响应，请查看右侧对话。'));},120000);pending.set(id,{resolve,reject,timer});parent.postMessage({type:'kgxc-editor-request',id,action,course_path:data.course_path,...args},parentOrigin);});}
function announce(){if(parent===window||!parentOrigin)return;parent.postMessage({type:'kgxc-editor-ready'},parentOrigin);const waiting_decisions=(data.plan.decisions||[]).filter(d=>(d.gate||'outline')===(stage==='sources'?'outline':stage)&&!['confirmed','delegated'].includes(d.status)).map(d=>({id:d.id,question:d.question,options:d.options}));parent.postMessage({type:'kgxc-studio-state',course_path:data.course_path,stage,phase:finalPhase,revision:data.revision,gates:data.gates,ai_review:{nodes:Object.fromEntries(Object.entries((reviews.state||data.ai_review)?.nodes||{}).map(([key,value])=>[key,{passed:value.passed,user_confirmed:value.user_confirmed,status:value.status}]))},waiting_decisions,pending_confirmations:data.pending_confirmations||[],unsaved_edits:serial!==savedSerial,has_sources:!!data.sources.length,has_outline:!!data.plan.units.length,has_script:!!data.editor.text,has_storyboard:!!data.storyboard?.segments?.length,has_pilot:!!data.artifacts.pilot?.length,has_final:!!data.artifacts.final?.length,dirty:data.editor.changed,producing:activeJobs(progressJobs)||activeJobs(data.jobs)},parentOrigin);}
window.addEventListener('message',async event=>{
  if(event.source!==parent||event.origin!==parentOrigin)return;
  const message=event.data;
  if(message?.type==='kgxc-editor-confirmation'){
    if(data&&message.course_path&&message.course_path!==data.course_path)return;
    confirmationDisplay=message.question_id||message.editing_feedback?{question_id:message.question_id,stage:message.stage,status:message.status,course_path:message.course_path,editing_feedback:message.editing_feedback===true}:null;
    if(data)paintProgress();
    return;
  }
  if(message?.type==='kgxc-editor-production'&&message.course_path===data?.course_path){nativeProduction=message.production;paintProgress();return;}
  if(message?.type==='kgxc-editor-host'){hostReady=true;aiBusy=!!message.running;if(data){primaryState();paintProgress();schedulePoll();void reviews.sync().catch(e=>notice(e.message,true));}return;}
  if(message?.type==='kgxc-editor-busy'){aiBusy=!!message.running;if(data){primaryState();paintProgress();schedulePoll();}return;}
  if(message?.type==='kgxc-editor-refresh'){if(serial===savedSerial&&!saveTask)await refresh();return;}
  if(message?.type==='kgxc-editor-leave'){
    try{await save();parent.postMessage({type:'kgxc-editor-leave-result',id:message.id},parentOrigin);}catch(e){parent.postMessage({type:'kgxc-editor-leave-result',id:message.id,error:e.message},parentOrigin);}return;
  }
  if(message?.type==='kgxc-editor-result'&&pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);clearTimeout(item.timer);if(message.result?.executor==='computer'&&message.result.job){computerExportAt=Date.now();progressJobs=[...progressJobs.filter(j=>j.id!==message.result.job.id),message.result.job];paintProgress();primaryState();announce();schedulePoll();}message.error?item.reject(Error(message.error)):item.resolve(message.result);}
});
function planFields(){return {audience:data.plan.audience,performance_task:data.plan.performance_task,objectives:data.plan.objectives};}
function changed(){serial++;$('save-status').textContent='正在保存…';announce();try{localStorage.setItem(draftKey(),JSON.stringify({baseRevision:data.revision,units:stage==='outline'?data.plan.units:undefined,plan_fields:stage==='outline'?planFields():undefined,sections:stage==='script'?data.sections:undefined}));}catch{}clearTimeout(saveTimer);saveTimer=setTimeout(()=>save().catch(e=>notice(e.message,true)),650);}
async function save(){
  if(saveTask){await saveTask;if(serial!==savedSerial)return save();return;}
  if(serial===savedSerial)return;
  const checkpoint=serial,kind=stage==='outline'?'outline':'sections',payload=stage==='outline'?{units:structuredClone(data.plan.units),plan_fields:structuredClone(planFields())}:{sections:structuredClone(data.sections),baseEditorRevision:data.editor.revision};
  saveTask=api('/api/studio/'+kind,{...payload,baseRevision:data.revision}).then(value=>{
    const localUnits=data.plan.units,localSections=data.sections,localFields=planFields();data=value;savedSerial=checkpoint;
    if(stage==='outline'){data.plan.units=localUnits;Object.assign(data.plan,localFields);}else data.sections=localSections;
    if(serial===checkpoint){try{localStorage.removeItem(draftKey());}catch{}}
    $('save-status').textContent=serial===savedSerial?'已保存':'正在保存…';announce();
  });
  try{await saveTask;}finally{saveTask=null;}
  if(serial!==savedSerial)return save();
}
async function action(name,args={}){await save();data=await api('/api/studio/'+name,{...args,baseRevision:data.revision});serial=savedSerial=0;render();announce();return data;}
async function refresh(){if(closed)return false;const value=await api('/api/studio');if(serial!==savedSerial||saveTask)return false;data=value;render();announce();schedulePoll();return true;}
function paintProgress(){if(!data)return;const native=nativeProduction?.updated_at>=computerExportAt?nativeProduction:undefined;const body=finalPhase==='body'?finalBodyState(data):null,recovery=!body?recoveryState():null,state=recovery?{label:recovery.summary,value:null,detail:recovery.detail,recovery:true,tone:'failed'}:body?{label:body.title,value:null,detail:body.detail,tone:'waiting'}:productionProgress({stage,busy:aiBusy,data,jobs:progressJobs,native});overview.update({...data,ai_review:reviews.state||data.ai_review,confirmation_display:confirmationDisplay},stage,{...state,phase:finalPhase});$('production-progress').dataset.state=state.tone;$('production-progress').dataset.indeterminate=String(state.value===null||!!progressError);$('production-label').textContent=progressError||state.label;$('production-owner').textContent=progressError?'连接异常 · 正在重试':state.tone==='working'?'AI 正在执行 · 无需手动操作':state.tone==='done'?'成果已保存':'制作状态 · 查看当前说明';$('production-detail').textContent=progressError?'当前数据暂未读到，将自动重新连接。':state.detail;$('production-bar').setAttribute('aria-valuetext',progressError||state.label);if(state.value===null||progressError)$('production-bar').removeAttribute('value');else $('production-bar').value=state.value;paintProductionSteps(finalPhase==='body'?undefined:native,state.tone==='done');}
function paintProductionSteps(native,historical=false){
  const panel=$('production-steps'),list=$('production-step-list'),issue=native?.issue,historyOpen=!!list.querySelector('[data-production-history]')?.open,
    openedErrors=new Set([...list.querySelectorAll('details[data-failure-id][open]')].map(node=>node.dataset.failureId));panel.hidden=!native?.available;list.replaceChildren();
  if(!native?.available)return;
  const task={outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课视频'}[native.stage];
  panel.dataset.historical=String(historical);panel.querySelector('summary').textContent=historical?'查看制作步骤与历史记录':(task?'当前'+task+' · ':'')+'查看具体制作步骤与耗时';
  const signature=issue&&issue.key+':'+issue.at;if(signature&&signature!==lastNativeIssue){panel.open=!historical;lastNativeIssue=signature;}
  $('production-issue').hidden=!issue;$('production-issue').setAttribute('role',historical?'status':'alert');$('production-issue').textContent=issue?(historical?'先前检查记录（非当前合成状态）：':'')+(issue.subject?issue.subject+'：':'')+issue.error:'';
  for(const item of (native.items||[]).slice(-6)){
    const row=el('li',null,'production-step'),label=el('span',item.label+(item.subject?' · '+item.subject:'')),status=({running:'执行中',complete:'已完成',failed:'失败',stopped:'已停止'})[item.status]||item.status;
    const seconds=Math.max(0,((item.ended_at||Date.now())-item.started_at)/1000);
    row.dataset.status=item.status;row.append(label,el('span',status+' · '+(seconds<1?seconds.toFixed(1):Math.floor(seconds))+' 秒','meta'));list.append(row);
  }
  if(native.history?.length){
    const container=el('li'),history=el('details',null,'job-history');history.dataset.productionHistory='true';history.open=historyOpen;
    history.append(el('summary','历史失败记录（'+native.history.length+'）'));container.append(history);list.append(container);
    for(const failure of native.history){
      const entry=el('div',null,'job'),replacement=failure.superseded_by;
      entry.append(el('p',(failure.label||'制作步骤')+(failure.subject?' · '+failure.subject:'')),
        el('p',replacement?(Number.isFinite(replacement.workflow_revision)?'已被修订 '+replacement.workflow_revision+' 的成功步骤替代':'已被后续同一步骤的成功执行替代'):'旧任务的未解决记录；不代表当前任务失败','meta'));
      if(replacement)entry.append(el('p','成功步骤：'+replacement.id+(replacement.script_sha256?' · 稿件 SHA '+replacement.script_sha256:''),'meta'));
      const detail=el('details',null,'job-diagnostics');detail.dataset.failureId=failure.id||failure.key;detail.open=openedErrors.has(detail.dataset.failureId);
      detail.append(el('summary','查看保留的错误与时间'),el('pre',(failure.errors?.length?failure.errors:[{at:failure.at,error:failure.error}]).map(value=>new Date(value.at).toLocaleString()+'\n'+value.error).join('\n\n')));
      entry.append(detail);history.append(entry);
    }
  }
}
async function pollProgress(){if(closed||document.hidden||progressReading)return;progressReading=true;const wasActive=activeJobs(progressJobs);try{progressJobs=await api('/api/jobs');progressError='';paintProgress();primaryState();if(wasActive&&!activeJobs(progressJobs)){if(serial===savedSerial&&!playing)await refresh();else{notice('新制作结果已返回。');$('notice').append(button('查看新结果',async()=>{await save();pause();await refresh();}));}announce();}}catch(e){progressError='制作进度连接暂时中断';paintProgress();}finally{progressReading=false;schedulePoll();}}
function schedulePoll(){clearTimeout(pollTimer);if(!closed&&!document.hidden&&(aiBusy||activeJobs(progressJobs)||activeJobs(data?.jobs)))pollTimer=setTimeout(pollProgress,3000);}
new ResizeObserver(()=>document.documentElement.style.setProperty('--studio-header-height',document.querySelector('header').getBoundingClientRect().height+'px')).observe(document.querySelector('header'));
function pendingPanel(root){const relevant=(data.plan.decisions||[]).filter(d=>(d.gate||'outline')===(stage==='sources'?'outline':stage));const waiting=relevant.filter(d=>!['confirmed','delegated'].includes(d.status));const accepted=relevant.filter(d=>['confirmed','delegated'].includes(d.status));if(accepted.length){const summary=el('section',null,'card pending');summary.append(el('h3','已记录的选择'));for(const item of accepted)summary.append(el('p',item.question+'：'+(item.options.find(o=>o.id===item.selected)?.label||item.options.find(o=>o.id===item.selected)?.title||item.selected)));if(stage==='outline')summary.append(button('按已选方案更新大纲建议',()=>host('stage',{target_stage:'outline',instruction:'按已经记录的真实选择复核并更新大纲。保留人工修改，变更先展示建议，不自动确认。'})));root.append(summary);}if(!waiting.length)return;const card=el('section',null,'card pending');card.append(el('h3','本阶段还有待选择事项'));const list=el('ul');for(const item of waiting)list.append(el('li',item.question));card.append(list,el('p','AI 会在右侧对话主动发起问答。','meta'));root.append(card);}
function impactPanel(root){if(!data.impact?.reason)return;const gate=data.gates.find(g=>g.id===stage);if(gate?.status!=='stale'&&!data.editor.changed&&(gate?.ready||['confirmed','delivered'].includes(gate?.status)))return;const box=el('p',data.impact.reason+(data.impact.segment_ids?.length?'；关联 '+data.impact.segment_ids.length+' 个教学片段。':''),'impact');root.append(box);}
function inputField(label,value,onChange,multi=false){const wrap=el('label',label),control=el(multi?'textarea':'input');control.value=value||'';control.oninput=()=>{onChange(control.value);changed();};wrap.append(control);return wrap;}

function materialLibrary(root){
  const rows=materialRows(data.material_library,data.sources);
  const card=el('section',null,'material-library card');
  const title=el('h2','素材库');
  title.id='material-library-title';card.setAttribute('aria-labelledby',title.id);
  card.append(title,el('p','按文件查看用没用、用在哪、为什么。只有核实到当前视频的位置才提供播放定位。','meta'));
  if(!rows.length){card.append(el('p','尚未入库素材。上传资料或实拍图后，可以在这里逐个核对。','material-library-empty'));root.append(card);return;}
  const totals=el('ul',null,'material-library-totals');
  for(const status of Object.keys(materialStatuses)){const total=rows.filter(item=>item.status===status).length;if(total)totals.append(el('li',materialStatuses[status].title+' '+total));}
  card.append(totals);
  const list=el('ul',null,'material-library-list');
  for(const item of rows){
    const row=el('li',null,'material-library-row'),header=el('div',null,'material-library-item-head'),identity=el('div',null,'material-library-identity');
    row.dataset.status=item.status;
    if(item.kind==='image'&&item.path&&item.available===true){const thumb=el('img');thumb.alt='';thumb.loading='lazy';thumb.src=fileURL(item.path);thumb.addEventListener('error',()=>{thumb.hidden=true;},{once:true});header.append(thumb);}
    identity.append(el('h3',item.title||item.path?.split('/').at(-1)||'未命名素材'),el('span',item.kind==='image'?'图片':'文件','meta'));header.append(identity,el('span',materialStatuses[item.status].title,'material-library-badge'));
    row.append(header,el('p',item.reason||materialStatuses[item.status].description,'material-library-reason'));
    if(item.path&&item.available===true)row.append(link(item.path,'查看原文件'));
    if(item.placements.length){
      const uses=el('ul',null,'material-library-placements');
      for(const p of item.placements){
        const label=({pilot:'有声小样',final:'整课成片',body:'主体视频'})[p.stage]+(p.segment_label?' · '+p.segment_label:'');
        const jump=el('a',label+' '+stamp(p.start_seconds)+'–'+stamp(p.end_seconds));
        jump.href=fileURL(p.artifact_path)+'#t='+p.start_seconds+','+p.end_seconds;
        jump.target='_blank';jump.rel='noopener';const place=el('li');place.append(jump);uses.append(place);
      }
      row.append(uses);
    }else if(item.status==='used')row.append(el('p','已登记使用，但暂无可播放的时间定位。','meta'));
    if(item.source_points.length){
      const details=el('details',null,'material-library-points'),points=el('ul');
      details.append(el('summary','原件内容取舍 · '+item.source_points.length+' 项'));
      const labels={retained:'保留',merged:'合并',omitted:'舍弃'};
      for(const p of item.source_points){
        const point=el('li');
        point.append(el('strong',[labels[p.disposition],p.locator].filter(Boolean).join(' · ')||'原件要点'));
        if(p.reason)point.append(el('p',p.reason));points.append(point);
      }
      details.append(points);row.append(details);
    }
    list.append(row);
  }
  card.append(list);root.append(card);
}

function sourcesView(root){
  root.append(el('p','加入原始资料，核对原件摘要、缺口与每项内容的课程去处。','intro'));
  const upload=el('input');upload.type='file';upload.multiple=true;upload.accept='.pdf,.docx,.pptx,.xlsx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp';upload.hidden=true;
  upload.onchange=async()=>{try{for(const file of upload.files){if(file.size>25*1024*1024)throw Error('单个资料文件最大 25 MB。');const response=await fetch('/api/studio/source',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name),'X-Base-Revision':String(data.revision)},body:file});const result=await response.json();if(!response.ok||result.error)throw Error(result.error);data=result;}render();announce();}catch(e){notice(e.message,true);}finally{upload.value='';}};
  root.append(button('上传原始资料',()=>upload.click()),upload);
  materialLibrary(root);
  if(!data.sources.length){root.append(empty('尚未加入原件','也可以在右侧对话中描述主题，或选择资料文件夹，让 AI 建立课程。'));return;}
  const grid=el('div',null,'source-grid'),list=el('div',null,'source-list'),preview=el('section',null,'source-preview');
  selectedSource=data.sources.find(s=>s.id===selectedSource)?.id||data.sources[0].id;
  for(const source of data.sources){const b=button(source.title,()=>{selectedSource=source.id;sourcePage=1;render();});b.setAttribute('aria-pressed',String(source.id===selectedSource));list.append(b);}
  const source=data.sources.find(s=>s.id===selectedSource);
  if(!source.available)preview.append(el('p','原件已不在工程中；请补充资料。','card'));
  else if(/\.(txt|md|csv)$/i.test(source.location)){const pre=el('pre','正在读取原件…');preview.append(pre);fetch(fileURL(source.location)).then(r=>r.text()).then(text=>pre.textContent=text).catch(e=>pre.textContent=e.message);}
  else if(/\.(png|jpe?g|webp)$/i.test(source.location)){const image=el('img');image.src=fileURL(source.location);image.alt=source.title;preview.append(image);}
  else if(/\.pdf$/i.test(source.location)){if(source.pdf_preview_available){const controls=el('div',null,'pdf-controls'),prev=button('上一页',()=>{sourcePage--;render();}),next=button('下一页',()=>{sourcePage++;render();});prev.disabled=sourcePage<=1;next.disabled=sourcePage>=source.pages;controls.append(prev,el('span','第 '+sourcePage+' / '+source.pages+' 页'),next);const image=el('img');image.src=resourceURL('/api/studio/source-preview?id=')+encodeURIComponent(source.id)+'&page='+sourcePage;image.alt=source.title+' 第'+sourcePage+'页原件';image.onerror=()=>notice('此页预览未能显示，请使用“查看原件文件”打开原件。',true);preview.append(controls,image);}else preview.append(el('p','本机暂未提供 PDF 页预览，可直接打开完整原件。','card'),link(source.location,'打开 PDF 原件'));}
  else preview.append(el('p','此格式保留完整原件，可下载后查看。','card'),link(source.location,'打开 '+source.title));
  list.append(link(source.location,'查看原件文件'));grid.append(list,preview);root.append(grid);
  const ledger=el('section',null,'ledger');ledger.append(el('h2','原件内容怎样进入课程'));
  for(const item of data.plan.source_items||[]){const row=el('div',null,'ledger-item');const refs=(item.source_refs||[]).map(ref=>(data.sources.find(s=>s.id===ref.source_id)?.title||ref.source_id)+(ref.locator?' · '+ref.locator:''));const destinations=(item.unit_ids||[]).map(id=>{const index=data.plan.units.findIndex(u=>u.id===id);return index<0?id:'第'+(index+1)+'章 '+data.plan.units[index].title;});row.append(el('h3',item.title||item.summary||item.id),el('p',item.summary||item.content||(item.key_points||[]).join('\n')),el('p','处理：'+(({core:'纳入主课',reference:'作为参考',appendix:'附录',omit:'本课不采用',omitted:'本课不采用',excluded:'本课不采用',merge:'合并讲解',partial:'采用相关内容',merged:'合并讲解',deferred:'移至后续课程'})[item.disposition]||item.disposition||item.treatment||'待分析'),'meta'));if(refs.length)row.append(el('p','原件位置：'+refs.join('；'),'meta'));if(destinations.length)row.append(el('p','课程去处：'+destinations.join('；'),'meta'));if(item.reason||item.rationale)row.append(el('p','理由：'+(item.reason||item.rationale),'meta'));ledger.append(row);}
  if(!(data.plan.source_items||[]).length)ledger.append(el('p','AI 完成素材诊断后，这里显示采用、删减或移至其他章节的内容与理由。','muted'));
  for(const issue of data.plan.issues||[])ledger.append(el('p','待补充：'+(issue.detail||issue.title||issue.id),'impact'));
  root.append(ledger,el('p','工程位置：'+data.course_path,'file-path'));
}

function outlineView(root){
  root.append(el('p','按章节卡片修改内容。拖动卡片或使用上移、下移；保存会同步关联的讲稿次序，并标出后续需要更新的部分。','intro'));impactPanel(root);
  if(!data.plan.units.length){root.append(empty('大纲尚未生成','点击上方“生成大纲”，AI 会先分析资料并给出可审阅结构。'));return;}
  const intro=el('section',null,'card fields');intro.append(inputField('学习对象',data.plan.audience,value=>data.plan.audience=value),inputField('学习后要完成的工作',data.plan.performance_task,value=>data.plan.performance_task=value));
  const goals=el('details',null,'full');goals.append(el('summary','查看与修改全课学习目标'));for(const objective of data.plan.objectives||[])goals.append(inputField(objective.id,objective.statement,value=>objective.statement=value,true));intro.append(goals);root.append(intro);
  const units=el('div');let dragged;
  data.plan.units.forEach((unit,index)=>{
    const card=el('article',null,'card unit');card.draggable=true;card.dataset.unit=unit.id;
    const head=el('div',null,'unit-head'),handle=el('span','⠿','handle'),title=el('input');handle.title='拖动调整章节顺序';title.className='title';title.setAttribute('aria-label','第'+(index+1)+'章标题');title.value=unit.title;title.oninput=()=>{unit.title=title.value;changed();};head.append(handle,el('strong','第 '+(index+1)+' 章'),title);card.append(head);
    const fields=el('div',null,'fields');fields.append(inputField('核心内容（每行一项）',Array.isArray(unit.content_points)?unit.content_points.join('\n'):unit.content_points||unit.summary,value=>unit.content_points=value.split('\n').map(s=>s.trim()).filter(Boolean),true),inputField('学习活动',unit.activity,value=>unit.activity=value,true),inputField('推荐讲法',unit.teaching_method,value=>unit.teaching_method=value,true),inputField('为什么这样讲',unit.teaching_reason,value=>unit.teaching_reason=value,true));
    const duration=inputField('预计时长（分钟）',unit.duration_minutes??unit.estimated_minutes??'',value=>unit.duration_minutes=value);duration.lastChild.placeholder='尚未估算';fields.append(duration);card.append(fields);
    const objectives=(unit.objective_ids||[]).map(id=>data.plan.objectives.find(o=>o.id===id)?.statement||id);if(objectives.length)card.append(el('p','学习目标：'+objectives.join('；'),'meta'));
    const refs=unit.source_refs?.length?unit.source_refs:(unit.source_ids||[]).map(id=>({source_id:id}));if(refs.length)card.append(el('p','来源：'+refs.map(ref=>(data.sources.find(s=>s.id===ref.source_id)?.title||ref.source_id)+(ref.locator?' · '+ref.locator:'')).join('；'),'meta'));
    const controls=el('div',null,'unit-actions');
    for(const [label,name] of [['在后面加一章','add'],['拆分这一章','split'],['与下一章合并','merge'],['删除这一章','remove']])controls.append(button(label,()=>action(name,{unit_id:unit.id})));
    const move=async offset=>{await save();const order=data.plan.units.map(u=>u.id),a=order.indexOf(unit.id),b=a+offset;if(b<0||b>=order.length)return;[order[a],order[b]]=[order[b],order[a]];await action('reorder',{order});};controls.append(button('上移',()=>move(-1)),button('下移',()=>move(1)));const editMenu=el('details',null,'chapter-tools');editMenu.append(el('summary','调整章节结构'),controls);card.append(editMenu);
    card.ondragstart=event=>{if(event.target.closest('input,textarea,button')){event.preventDefault();return;}dragged=unit.id;event.dataTransfer.setData('text/plain',unit.id);};card.ondragover=event=>{event.preventDefault();card.classList.add('drop');};card.ondragleave=()=>card.classList.remove('drop');card.ondrop=async event=>{event.preventDefault();card.classList.remove('drop');try{await save();const id=dragged||event.dataTransfer.getData('text/plain'),order=data.plan.units.map(u=>u.id);if(!order.includes(id)||id===unit.id)return;order.splice(order.indexOf(id),1);order.splice(order.indexOf(unit.id),0,id);await action('reorder',{order});}catch(e){notice(e.message,true);}};
    units.append(card);
  });root.append(units);
}

function scriptView(root){
  impactPanel(root);
  if(data.editor.text&&!data.mapped){const box=el('section',null,'card');box.append(el('h2','已有讲稿尚未绑定章节'),el('p','原稿完整保留。先让 AI 给出章节绑定建议，审阅后采用；避免按标题猜配。'),el('pre',data.editor.text),button('让 AI 按大纲绑定当前原稿',()=>host('stage',{target_stage:'script',instruction:'保留现有原稿全文，提出按稳定章节身份绑定的分章建议，不删内容，先展示差异。'})));root.append(box);return;}
  if(!data.sections.length){root.append(empty('先确定课程大纲','有了章节后，可以在这里逐章编辑讲稿。'));return;}
  selectedUnit=data.sections.find(s=>s.unit_id===selectedUnit)?.unit_id||data.sections[0].unit_id;
  const grid=el('div',null,'script-grid'),form=el('section',null,'script-form'),preview=el('section');
  const choose=el('select');choose.setAttribute('aria-label','选择讲稿章节');data.sections.forEach((s,i)=>{const option=el('option',(i+1)+'. '+s.title);option.value=s.unit_id;option.selected=s.unit_id===selectedUnit;choose.append(option);});choose.onchange=async()=>{try{await save();selectedUnit=choose.value;pause();render();}catch(e){notice(e.message,true);}};
  const area=el('textarea');area.className='chapter-text';area.id='chapter-script';area.setAttribute('aria-label','当前章节逐字稿');area.value=section().body;area.placeholder='这一章的口播、练习引导与反馈';
  const counts=el('div',null,'counts'),words=el('span'),estimate=el('span');counts.append(words,estimate);
  const count=()=>{const n=[...area.value.replace(/\s/g,'')].length;words.textContent=n+' 字';estimate.textContent='估时约 '+Math.ceil(n/230)+' 分钟（配音后校准）';};count();
  area.oninput=()=>{section().body=area.value;changed();count();pause();clearTimeout(previewTimer);previewTimer=setTimeout(updatePreview,160);};area.onclick=()=>updatePreview();
  const tools=el('div',null,'row');tools.append(button('选择当前段落',()=>{const p=paragraphAt(area.value,area.selectionStart);if(p){area.focus();area.setSelectionRange(p.start,p.end);}}),button('让 AI 修改选中文字',()=>openRewrite(area)));
  form.append(choose,tools,area,counts);const screen=el('div',null,'screen'),waiting=el('div',null,'placeholder');waiting.id='waiting';waiting.append(el('span','逐字稿预览','meta'),el('h2',section().title),el('p',section().body||'开始输入这一章的讲稿。'),el('small','课程动态画面尚未制作'));
  const frame=el('iframe');frame.id='real-preview';frame.title='当前章节实际画面';frame.hidden=true;screen.append(frame,waiting);preview.append(screen,el('p',native?'修改后的实际画面与声音在有声小样阶段检查。':'文字改动即时预览；配音和视频在对应制作阶段更新。','preview-meta'));
  const controls=el('div',null,'playback'),play=button('播放预览',()=>togglePlay());play.id='play';play.disabled=true;const seek=el('input');seek.type='range';seek.min=0;seek.max=1;seek.value=0;seek.id='seek';seek.setAttribute('aria-label','课程预览进度');seek.oninput=()=>{pause();previewFrame=Number(seek.value);paint();};const clock=el('span','00:00');clock.id='preview-time';controls.append(play,seek,clock);preview.append(controls);grid.append(form,preview);root.append(grid);loadPreview().catch(e=>notice(e.message,true));
}
async function openRewrite(area){let start=area.selectionStart,end=area.selectionEnd;if(start===end){const p=paragraphAt(area.value,start);if(!p)return;start=p.start;end=p.end;}selection={snapshot:area.value,text:area.value.slice(start,end),start,end,unit_id:selectedUnit};$('rewrite-selection').textContent=selection.text;$('rewrite-instruction').value='';$('rewrite-result').hidden=true;$('rewrite-accept').disabled=true;$('rewrite-status').textContent='';$('rewrite').showModal();}
$('rewrite-generate').onclick=async()=>{if(!selection)return;try{$('rewrite-generate').disabled=true;$('rewrite-status').textContent='AI 正在生成修改建议…';const result=await host('rewrite',{requestId:crypto.randomUUID(),text:selection.text,instruction:$('rewrite-instruction').value.trim()||'更清楚自然，保留事实和关键步骤',before:selection.snapshot.slice(Math.max(0,selection.start-1200),selection.start),after:selection.snapshot.slice(selection.end,selection.end+1200)});$('rewrite-suggestion').value=result.text;$('rewrite-result').hidden=false;$('rewrite-accept').disabled=false;$('rewrite-status').textContent='核对后采用，只替换选中范围。';}catch(e){$('rewrite-status').textContent=e.message;}finally{$('rewrite-generate').disabled=false;}};
$('rewrite-accept').onclick=()=>{try{const area=$('chapter-script');if(!area||selectedUnit!==selection.unit_id)throw Error('当前章节已切换，请重新选择文字。');area.value=replaceSelection(area.value,selection,$('rewrite-suggestion').value);area.dispatchEvent(new Event('input'));$('rewrite').close();}catch(e){$('rewrite-status').textContent=e.message;}};

async function loadPreview(){if(native)return;renderer=null;previewState=await api('/api/editor');const frame=$('real-preview');if(!frame||!previewState.has_scenes)return;frame.src='/renderer.html?revision='+previewState.document.revision+'&studio='+Date.now();frame.hidden=false;$('waiting').hidden=true;await new Promise((resolve,reject)=>{const end=Date.now()+25000;const check=()=>{if(closed||!frame.isConnected)return resolve();if(frame.contentWindow.ready)return resolve();if(frame.contentWindow.renderError)return reject(Error(frame.contentWindow.renderError));if(Date.now()>end)return reject(Error('画面预览尚未就绪'));setTimeout(check,80);};check();});if(!frame.isConnected)return;renderer=frame.contentWindow.courseRenderer;audio.src='/api/audio?revision='+previewState.document.revision;$('play').disabled=false;await updatePreview();}
async function updatePreview(){const current=section(),area=$('chapter-script');if(!current||!area)return;const waiting=$('waiting');if(waiting){waiting.querySelector('h2').textContent=current.title;waiting.querySelector('p').textContent=paragraphAt(area.value,area.selectionStart)?.text||area.value||'开始输入这一章的讲稿。';}if(!renderer||!previewState)return;const text=fullText(),prefix=data.sections.slice(0,data.sections.findIndex(s=>s.unit_id===selectedUnit)).map((s,i)=>'## '+(i+1)+'. '+s.title+'\n\n'+s.body.trim()).join('\n\n');const caret=(prefix?prefix.length+2:0)+('## '+(data.sections.findIndex(s=>s.unit_id===selectedUnit)+1)+'. '+current.title+'\n\n').length+area.selectionStart;const result=previewDocument(previewState.document,previewState.base_text,text,caret);if(result.scene)previewFrame=displayFrame(result.scene.sourceStartFrame,result.document.holds,result.document.cuts);previewState.currentDoc=result.document;await renderer.load(result.document);audio.muted=text!==previewState.base_text;$('seek').max=totalFrames(result.document)-1;await paint();}
async function paint(){if(!renderer||!previewState?.currentDoc)return;await renderer.drawFrame(previewFrame);if($('seek'))$('seek').value=previewFrame;if($('preview-time'))$('preview-time').textContent=stamp(previewFrame/previewState.currentDoc.fps);}
function pause(){playing=false;audio.pause();if($('play'))$('play').textContent='播放预览';}
function togglePlay(){if(playing){pause();return;}if(!renderer)return;playing=true;playEpoch=performance.now()-previewFrame/previewState.currentDoc.fps*1000;if(!audio.muted){audio.currentTime=previewFrame/previewState.currentDoc.fps;audio.play().catch(()=>{});}$('play').textContent='暂停预览';tick();}
async function tick(){if(!playing||closed)return;previewFrame=Math.min(totalFrames(previewState.currentDoc)-1,Math.floor((performance.now()-playEpoch)/1000*previewState.currentDoc.fps));await paint();if(previewFrame>=totalFrames(previewState.currentDoc)-1)pause();else requestAnimationFrame(tick);}

function storyboardView(root){
  root.append(el('p','每个教学片段比较不同画面表现；静态关键帧只作示意，实际动态画面以小样为准。','intro'));impactPanel(root);
  const segments=data.storyboard?.segments||[];if(!segments.length){root.append(empty('全课分镜尚未生成','确认逐字稿后，AI 将覆盖整课内容，为每段提出至少三种表现方案。'));return;}
  selectedSegment=segments.find(s=>s.id===selectedSegment)?.id||segments[0].id;
  root.append(button('采用全部推荐方案',()=>action('choice',{id:'all',option:'recommended'})));
  const grid=el('div',null,'board-grid'),list=el('nav',null,'segment-list'),detail=el('section');list.setAttribute('aria-label','章节与教学片段');
  segments.forEach((s,i)=>{const unit=data.plan.units.find(u=>u.id===s.unit_id);const b=button((i+1)+'. '+(unit?.title||'')+' · '+s.teaching_goal,()=>{selectedSegment=s.id;render();});b.setAttribute('aria-current',String(s.id===selectedSegment));list.append(b);});
  const current=segments.find(s=>s.id===selectedSegment);detail.append(el('h2',current.teaching_goal),el('blockquote',current.script_excerpt,'segment-copy'));
  const alternatives=el('div',null,'alternatives');for(const option of current.options){const card=el('article',null,'card alternative');card.setAttribute('aria-selected',String(current.selected===option.id));card.append(el('h3',option.method+(current.recommended===option.id?' · 推荐':'')));
    for(const [key,label] of [['opening','开始画面'],['action','画面动作'],['result','最终结果'],['focus','观看焦点'],['feasibility','实现条件'],['cost','制作量'],['risk_note','需检查']])if(option[key])card.append(el('p',label+'：'+option[key],'detail'));
    const keyframe=el('div',null,'keyframe');keyframe.append(el('p','静态画面示意','meta'));if(option.preview_file){if(/\.(png|jpe?g|webp|svg)$/i.test(option.preview_file)){const img=el('img');img.src=fileURL(option.preview_file);img.alt=option.method+'关键帧示意';keyframe.append(img);}else keyframe.append(link(option.preview_file,'查看画面示意'));}else keyframe.append(el('p','尚未生成关键帧；上方为已写入分镜的画面方案。','muted'));card.append(keyframe,button(current.selected===option.id?'已采用这一方案':'采用这一方案',()=>action('choice',{id:current.id,option:option.id}),current.selected===option.id?'primary':undefined));alternatives.append(card);}
  detail.append(alternatives);const refine=el('section',null,'card feedback'),instruction=el('textarea');instruction.placeholder='例如：改成顾客与私教对话，保留本段教学目的';refine.append(el('h3','调整本段画面或视觉风格'),instruction,button('让 AI 给出本段修改建议',()=>host('stage',{target_stage:'storyboard',segment_id:current.id,instruction:instruction.value,user_instruction:instruction.value})));detail.append(refine);grid.append(list,detail);root.append(grid);
}
function timestampFeedback(stageName,segmentId,video,file,interval){
  if(!video||!file?.sha256||!parentOrigin||parent===window)return null;
  return button('这里要改',()=>{
    video.pause();
    const start=interval?.playback_start??0;
    const stop=interval?.playback_end??(Number.isFinite(file.duration_seconds)?file.duration_seconds:video.duration);
    const time=Math.max(start,Math.min(Number.isFinite(stop)?stop:Number.MAX_SAFE_INTEGER,Number(video.currentTime)||start));
    parent.postMessage({type:'kgxc-editor-feedback',course_path:data.course_path,stage:stageName,
      segment_id:segmentId,time:Number(time.toFixed(3)),artifact_path:file.path,artifact_sha256:file.sha256},parentOrigin);
  });
}
function feedbackForm(stageName,segmentId,video,file){
  const history=el('div',null,'feedback-history');
  for(const item of (data.feedback||[]).filter(f=>f.stage===stageName&&f.segment_id===segmentId).slice(-5)){
    const same=!!video&&item.artifact_sha256===file?.sha256;const entry=el('div',null,'card');
    entry.append(el('p',item.text),el('p',item.artifact_sha256?'视频内 '+stamp(item.time)+(same?' · 当前视频':' · 先前视频版本'):'已记录的制作要求','meta'));
    if(same)entry.append(button('定位这条反馈',()=>{video.currentTime=item.time;}));history.append(entry);
  }
  return history;
}
function samplePlayer(file,binding,index){const video=el('video');video.controls=true;video.preload='metadata';video.src=fileURL(file.path)+'#t='+binding.playback_start+','+binding.playback_end;video.setAttribute('aria-label','有声样段 '+(index+1));const start=binding.playback_start,end=binding.playback_end;video.addEventListener('loadedmetadata',()=>video.currentTime=start);video.addEventListener('play',()=>{if(video.currentTime<start||video.currentTime>=end-.04)video.currentTime=start;});video.addEventListener('seeking',()=>{if(video.currentTime<start-.05)video.currentTime=start;else if(video.currentTime>end+.05)video.currentTime=end;});video.addEventListener('timeupdate',()=>{if(!video.paused&&video.currentTime>=end-.035){video.pause();video.currentTime=end;}});return video;}
function mediaReviewScope(root,stageName){
  const review=reviews.state||data.ai_review;if(!requiresUserAudio(review,stageName))return;
  const audio=review.nodes?.[stageName]?.user_audio_review,scope=el('section',null,'card review-audio-scope');scope.append(el('h2','AI审文字与画面，你听音轨'),el('p','AI的静帧和画面序列检查不代表连续播放。请完整播放当前全部'+(stageName==='pilot'?'小样':'成片')+'，在原确认窗口中同时声明声音、音画配合和内容均可接受。'));
  scope.append(el('p','当前听审状态：'+({confirmed:'当前全部视频已实际听审',stale:'媒体已变化，先前声明失效',issues_reported:'已记录声音问题，未确认',pending:'待用户完整听审'}[audio?.status]||'尚未取得完整媒体范围'),'review-verdict'));
  const hashes=audio?.artifact_sha256s||[],ranges=audio?.artifacts||[];
  if(!hashes.length)scope.append(el('p','当前尚无可绑定的完整媒体范围，不能确认听审。','review-blocked'));
  hashes.forEach((sha,index)=>{const range=ranges[index],file=(data.artifacts[stageName]||[]).find(f=>f.sha256===sha&&f.available);const row=el('article',null,'review-media-binding');row.append(el('h3','完整视频 '+(index+1)),el('p','SHA-256 '+sha,'file-path'),el('p',range?.sha256===sha&&Number.isFinite(range.end_seconds)?'完整范围 '+range.start_seconds+'—'+range.end_seconds+' 秒':'时长尚未核对，不能作听审声明。','meta'));
    if(file){row.append(link(file.path,'打开当前完整视频'));if(stageName==='pilot'){const video=el('video');video.controls=true;video.preload='metadata';video.src=fileURL(file.path);video.className='delivery-video';video.setAttribute('aria-label','完整听审小样 '+(index+1));row.append(video);}}else row.append(el('p','这一版本的视频尚不可访问，请刷新核对。','review-blocked'));scope.append(row);});
  root.append(scope);
}
let liveProduction;
const overview=createProductionOverview({document,onCoverage:()=>sourceCoverage.open()});
function liveWorkspace(root){if(!liveProduction)liveProduction=createLiveProduction({document,window,fetch,mediaURL:fileURL});liveProduction.mount(root);}
function samplesView(root){
  const previewRoot=root,inspection=el('details',null,'sample-inspection');inspection.append(el('summary','查看抽样依据、听审范围和制作记录'));root=inspection;
  impactPanel(root);mediaReviewScope(root,'pilot');
  if(data.artifacts.pilot?.some(file=>file.available&&file.current_storyboard)){
    const retry=button('重新合成当前小样',async()=>{retry.disabled=true;try{await host('stage',{target_stage:'pilot'});notice('已提交当前小样制作请求。');}finally{retry.disabled=aiBusy||activeJobs(progressJobs)||activeJobs(data.jobs);}});retry.disabled=aiBusy||activeJobs(progressJobs)||activeJobs(data.jobs);root.append(retry);
  }
  const sampling=data.sampling||{},selections=sampling.selections||[];
  if(!selections.length){previewRoot.append(empty('有声小样还没生成','完成分镜后，会在这里看到三段小样。'));liveWorkspace(previewRoot);previewRoot.append(inspection);return;}
  const overview=el('section',null,'card');overview.append(el('h2','本轮抽样范围'),el('p',sampling.scope||''));if(sampling.uncovered_kinds?.length)overview.append(el('p','尚未覆盖的表现类型：'+sampling.uncovered_kinds.map(k=>({concept:'概念讲解',scenario:'人物情境',operation:'操作演示',practice:'练习与反馈'})[k]||k).join('、'),'impact'));if(sampling.unsampled_high_risk_ids?.length)overview.append(el('p','仍需另行检查 '+sampling.unsampled_high_risk_ids.length+' 个高风险片段。','meta'));root.append(overview);
  const grid=el('div',null,'sample-grid');selections.forEach((selected,index)=>{const segment=data.storyboard.segments.find(s=>s.id===selected.segment_id),card=el('article',null,'card');card.append(el('h2','样段 '+(index+1)+' · '+(segment?.teaching_goal||selected.segment_id)));
    const segmentDetails=el('details',null,'sample-inspection');segmentDetails.append(el('summary','查看本段讲稿与定位反馈'),el('p','抽样原因：'+selected.reason,'meta'));if(segment)segmentDetails.append(el('p',segment.script_excerpt),el('p','画面方案：'+(segment.options.find(o=>o.id===selected.option_id)?.method||selected.option_id),'meta'));
    const file=(data.artifacts.pilot||[]).find(item=>item.available&&item.current_storyboard&&item.bindings?.some(b=>b.segment_id===selected.segment_id&&b.option_id===selected.option_id&&b.playback_complete));const binding=file?.bindings.find(b=>b.segment_id===selected.segment_id);let video;
    if(file){video=samplePlayer(file,binding,index);card.append(video);const note=timestampFeedback('pilot',selected.segment_id,video,file,binding);if(note)card.append(note);card.append(el('p','本段位置 '+stamp(binding.playback_start)+'—'+stamp(binding.playback_end)+'；完整片段 '+(binding.playback_end-binding.playback_start).toFixed(1)+' 秒。','meta'));}else card.append(el('p','本段有声视频尚未生成，或尚未核对与当前分镜的完整对应关系。','impact'));
    segmentDetails.append(el('p','音色与语速：'+(file?.audio_settings?.summary||'暂无单独记录'),'meta'),feedbackForm('pilot',selected.segment_id,video,file,binding));card.append(segmentDetails);grid.append(card);});previewRoot.append(grid);
  if((data.artifacts.pilot||[]).some(file=>file.available&&/\.mp4$/i.test(file.path)&&!file.bindings?.length)){const extra=el('section',null,'card');extra.append(el('h3','已生成、尚待核对对应关系的视频'));for(const file of data.artifacts.pilot.filter(f=>f.available&&/\.mp4$/i.test(f.path)&&!f.bindings?.length)){const video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';extra.append(video);}previewRoot.append(extra);}
  liveWorkspace(previewRoot);previewRoot.append(inspection);
}
function finalBodyState(model){
  const pilot=model.gates?.find(g=>g.id==='pilot');
  const evidence=(model.artifacts?.body||[]).filter(file=>file.available===true&&/\.mp4$/i.test(file.path||''));
  if(evidence.length)return {title:'主体视频已登记',detail:'可播放当前主体视频。',files:evidence};
  if(pilot?.status!=='confirmed')return {title:'等待当前小样确认',detail:'三段有声小样确认后，才开始整课主体制作。',files:[]};
  return {title:'主体进度尚未单独登记',detail:'主体视频完成后会在这里显示。',files:[]};
}
function finalBodyView(root){
  const phase=el('section',null,'final-phase card');
  phase.append(el('span','整课制作 · 第一步','final-phase-index'),el('h2','画面与配音'),el('p','在这里查看整课画面、旁白和主体视频。'));
  const model=finalBodyState(data);
  phase.append(el('p',model.title,'final-phase-evidence'),el('p',model.detail,'meta'));
  for(const file of model.files){const video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';phase.append(video,link(file.path,'查看主体文件'));}
  root.append(phase);
  liveWorkspace(root);
}
function finalView(root){
  if(finalPhase==='body'){finalBodyView(root);return;}
  const phase=el('section',null,'final-phase card');
  phase.append(el('span','整课制作 · 第二步','final-phase-index'),el('h2','后期与成片'),el('p','加入花字和音效后，完整视频会出现在这里。'));
  const files=(data.artifacts.final||[]).filter(f=>f.available);
  root.append(phase);
  impactPanel(root);
  if(!files.length)root.append(empty('成片还没生成','完成后可在这里播放。'));
  for(const file of files){const card=el('section',null,'card');let video;if(/\.mp4$/i.test(file.path)){video=el('video');video.controls=true;video.src=fileURL(file.path);video.className='delivery-video';card.append(video);const note=timestampFeedback('final',undefined,video,file);if(note)card.append(note);if(file.chapters?.length){const jumps=el('div',null,'unit-actions');for(const chapter of file.chapters)jumps.append(button(chapter.title,()=>{video.currentTime=Math.min(chapter.start,Math.max(0,(video.duration||Infinity)-.1));}));card.append(jumps);}else card.append(el('p','此文件没有经过核对的章节定位，仍可直接播放。','meta'));}card.append(link(file.path,'下载当前文件'));if(video){const feedback=el('details',null,'sample-inspection');feedback.append(el('summary','定位反馈'),feedbackForm('final',undefined,video,file));card.append(feedback);}root.append(card);}
  for(const delivery of data.deliveries||[])if(delivery.path||delivery.paths)root.append(el('p','已登记交付：'+(delivery.path||delivery.paths.join('、')),'file-path'));
  const diagnostics=el('details',null,'sample-inspection');diagnostics.append(el('summary','查看成片检查与制作记录'));
  mediaReviewScope(diagnostics,'final');
  const {current,history}=productionJobHistory(progressJobs.length?progressJobs:data.jobs,'final');
  if(current)diagnostics.append(exportJobCard(current,false));
  if(history.length){const archive=el('details',null,'job-history'),failed=history.filter(job=>job.status==='failed').length;archive.append(el('summary','历史制作记录 · '+history.length+' 次'+(failed?'，其中 '+failed+' 次当时未通过':'')));archive.append(el('p','历史文件和错误均保留；下列记录不代表当前任务状态。','meta'));for(const job of history)archive.append(exportJobCard(job,true));diagnostics.append(archive);}
  root.append(diagnostics);
}
function exportJobCard(job,historical){
  const row=el('section',null,'job'),heading=el('div',null,'job-heading');row.dataset.status=job.status;
  let label=({queued:'排队中',rendering:'制作中',encoding:'编码中',packaging:'整理交付',complete:'合成已完成',failed:'本次未通过校验'})[job.status]||job.status;
  if(job.status==='complete'&&job.registration_status==='held')label='候选已生成 · 验收受阻';
  if(historical)label=job.status==='failed'?'历史失败记录':label;
  heading.append(el('strong',(historical?'':'当前任务 · ')+label,'job-label'),el('span',(Number.isFinite(job.revision)?'R'+job.revision+' · ':'')+(job.id||''),'meta'));row.append(heading);
  if(job.status==='complete')row.append(el('p',job.registration_status==='held'?'渲染与编码检查已完成；制作候选尚未登记，需补齐当前制作检查。':'已完成渲染与编码检查。','meta'));
  if(job.registration_status==='held'&&job.contract_pending?.errors?.length){const pending=el('details',null,'job-diagnostics');pending.append(el('summary','当前缺项 · '+job.contract_pending.errors.length+' 项'));for(const issue of job.contract_pending.errors)pending.append(el('p',(issue.code?issue.code+'：':'')+issue.message));row.append(pending);}
  if(!historical&&activeJobs([job])&&typeof job.progress==='number'){const line=el('div',null,'job-progress'),bar=el('progress');bar.max=1;bar.value=Math.max(0,Math.min(1,job.progress));line.append(bar,el('span',Math.floor(bar.value*100)+'%'));row.append(line);}
  if(job.supersededBy)row.append(el('p','后续 '+(Number.isFinite(job.supersededBy.revision)?'R'+job.supersededBy.revision+' ':'')+'导出已通过；本条保留为历史诊断。','meta'));
  if(job.error){const diagnostic=el('details',null,'job-diagnostics');diagnostic.append(el('summary',historical?'查看当时的错误详情':'查看本次错误详情'),el('pre',String(job.error)));row.append(diagnostic);}
  return row;
}
function empty(title,copy){const box=el('section',null,'empty');box.append(el('h2',title),el('p',copy));return box;}
function renderProposals(){const items=(data.proposals||[]).filter(p=>p.status==='open'),root=$('proposals');root.hidden=!items.length;root.replaceChildren();for(const proposal of items){const details=el('details',null,'card');details.append(el('summary','AI 提交了'+(titles[proposal.stage]||proposal.stage)+'修改建议，尚未替换人工内容'));const diff=el('div',null,'diff');const before=proposal.stage==='script'?data.editor.text:readable(data[proposal.stage]||data.plan);const after=proposal.stage==='script'?(proposal.candidate.sections||[]).map(s=>s.body).join('\n\n'):readable(proposal.candidate);diff.append(el('pre','当前内容\n\n'+before),el('pre','AI 建议\n\n'+after));details.append(diff,button('采用这份建议',()=>action('adopt',{id:proposal.id})));root.append(details);}}
function readable(value){if(Array.isArray(value))return value.map(readable).join('\n\n');if(value&&typeof value==='object')return ['title','audience','performance_task','statement','teaching_goal','activity','teaching_method','method','opening','action','result','focus','script_excerpt'].map(k=>value[k]||'').filter(Boolean).join('\n')+'\n'+['content_points','objectives','units','segments','options'].filter(k=>value[k]).map(k=>readable(value[k])).join('\n');return String(value||'');}
function needsGeneration(){return stage==='script'&&!data.editor.text?.trim()||stage==='storyboard'&&!data.storyboard?.segments?.length||stage==='pilot'&&!data.gates.find(g=>g.id==='pilot')?.ready;}
function stageReview(){return reviews.state||data.ai_review;}
function stageConfirmed(id){
  const review=stageReview();
  if(review?.enabled)return review.nodes?.[id]?.user_confirmed===true;
  return data.gates?.some(g=>g.id===id&&['confirmed','delivered'].includes(g.status));
}
function atConfirmationGate(){
  if(!confirmationStages.has(stage))return false;
  if(stageConfirmed(stage))return false;
  if((data.pending_confirmations||[]).some(item=>item.stage===stage))return true;
  const g=data.gates.find(g=>g.id===stage);
  const review=stageReview()?.nodes?.[stage];
  if(g?.status==='stale'||review?.status==='stale')return false;
  return stage==='script'?!!data.editor.text?.trim():!!g?.ready;
}
function recoveryState(){return exportRecovery(progressJobs.length?progressJobs:data.jobs,stage,aiBusy);}
function primaryState(){
  const primary=$('primary'),review=stageReview()?.nodes?.[stage];
  const labels={sources:'生成大纲',outline:data.plan.units.length?'确认大纲，生成逐字稿':'生成大纲',
    script:stageConfirmed('script')?'制作分镜':'生成逐字稿',storyboard:needsGeneration()?'生成全课分镜':'制作三段有声小样',
    pilot:stageConfirmed('pilot')?'制作整课':'继续制作三段有声小样',
    final:stageConfirmed('final')?'保存成片到桌面':'开始制作成片'};
  const rendering=activeJobs(progressJobs)||activeJobs(data.jobs);
  primary.hidden=finalPhase==='body'||atConfirmationGate()||aiBusy||rendering;
  primary.textContent=recoveryState()?.label||(rendering?'视频正在合成…':aiBusy?'AI 正在制作…':labels[stage]);
  primary.disabled=aiBusy||rendering||primary.hidden;
  $('production-preferences').disabled=aiBusy||rendering;
  const prerequisite={script:'outline',storyboard:'script',pilot:'storyboard',final:'pilot'}[stage];
  if(prerequisite&&!data.gates.some(g=>g.id===prerequisite&&g.status==='confirmed'))primary.disabled=true;
  if(stage==='script'&&data.editor.text?.trim()&&!data.mapped)primary.disabled=true;
  if(stage==='storyboard'&&!needsGeneration()&&!data.gates.find(g=>g.id===stage)?.ready)primary.disabled=true;
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.required&&(!data.production_preferences.ready||!data.production_preferences.storyboard_current)){primary.textContent='按制作偏好更新分镜';primary.disabled=primary.hidden||aiBusy||rendering||!data.gates.some(g=>g.id==='script'&&g.status==='confirmed');}
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.choices?.customer==='new'&&!data.production_preferences.new_customer_ready){primary.textContent='设计新增顾客并更新分镜';primary.disabled=primary.hidden||aiBusy||rendering||!data.gates.some(g=>g.id==='script'&&g.status==='confirmed');}
  if(data.ai_review?.enabled&&stage==='storyboard'&&!needsGeneration()&&!review?.passed){primary.textContent='分镜检查由 AI 推进';primary.disabled=true;}
}
function render(){
  if(data.review_context==='qa-simulation')notice('独立验证课程：当前操作记录为技术模拟，不代表正式业务课内容验收。');
  pause();$('course-title').textContent=data.title;$('stage-kicker').textContent=finalPhase==='body'?'画面与配音':finalPhase==='post'?'后期与成片':titles[stage]||'课程工作台';$('save-status').textContent=serial===savedSerial?'已保存':'正在保存…';$('undo').disabled=!data.undo_available;renderProposals();
  const root=$('content');root.replaceChildren();overview.mount(root);({sources:sourcesView,outline:outlineView,script:scriptView,storyboard:storyboardView,pilot:samplesView,final:finalView}[stage]||outlineView)(root);pendingPanel(root);overview.mountHistory(root);
  primaryState();paintProgress();sourceCoverage.sync();
}
$('undo').onclick=()=>action('undo').catch(e=>notice(e.message,true));
$('production-preferences').onclick=()=>productionPreferences.open();
async function runPrimary(){try{
  $('primary').disabled=true;await save();
  const review=stageReview()?.nodes?.[stage],recovery=recoveryState();
  if(finalPhase==='body')return;
  if(atConfirmationGate()){notice('等 AI 在右侧对话发起本节点的确认。');return;}
  if(data.ai_review?.enabled&&stage==='storyboard'&&!needsGeneration()&&!review?.passed)return;
  if(stage==='final'&&stageConfirmed('final')){notice('正在校验并保存成品，过程文件保留…');await host('deliver');return;}
  let target;
  if(stage==='sources'||stage==='outline'&&!data.plan.units.length)target='outline';
  else if(stage==='final'||needsGeneration()||confirmationStages.has(stage)&&!stageConfirmed(stage))target=stage;
  else target={outline:'script',script:'storyboard',storyboard:'pilot',pilot:'final'}[stage];
  if(['storyboard','pilot','final'].includes(target)&&productionPreferences.pending){productionPreferences.open({continueWith:runPrimary});return;}
  if(data.production_preferences?.required&&!data.production_preferences.storyboard_current&&['pilot','final'].includes(target))target='storyboard';
  if(data.production_preferences?.choices?.customer==='new'&&!data.production_preferences.new_customer_ready&&['pilot','final'].includes(target))target='storyboard';
  if(target!==stage&&stage==='outline'&&!needsGeneration()&&data.plan.units.length)await action('confirm',{stage});
  const result=await host('stage',{target_stage:target,context_stage:stage,instruction:(recovery?'恢复当前阶段上次未完成的制作任务 '+recovery.job_id+'。先核对已保存的当前版讲稿、配音、画面和缓存，沿用有效文件，从失败环节继续，不重复生成或重开审阅。':'')+'仅完成本次目标阶段并保存实际成果，随后停在对应审阅页。沿用本会话已核对的原件、环境与有效选择，避免重复建课或重复读取无变化的资料；本机工作台使用插件工具读取，无需互联网网页获取。制作偏好：'+productionPreferenceSummary(data.production_preferences)+'。必须读取production-preferences.json；新增顾客按本课设计不同发型与衣服的同风格多部件vectorActor，先展示实际设计供采用，不能用整张PNG或断手占位；启用花字/音效后检查真实编码并按production_handoff的implementation_review登记，不以计划代替接入。若本课标注为验证课，沿用其技术模拟范围，不代表正式课验收。'});
  notice(result.executor==='computer'?'已复用当前成果提交实际合成任务。':'已交给当前课程的 AI，完成后在对应阶段展示。');
}catch(e){notice(e.message,true);}finally{if($('primary'))primaryState();}}
$('primary').onclick=runPrimary;
window.addEventListener('beforeunload',event=>{if(serial!==savedSerial){event.preventDefault();event.returnValue='';}});
window.addEventListener('pagehide',()=>{closed=true;pause();clearTimeout(pollTimer);clearTimeout(saveTimer);clearTimeout(previewTimer);});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();else if(data)schedulePoll();});
startActivity(()=>serial!==savedSerial||pending.size>0||aiBusy||activeJobs(progressJobs)||activeJobs(data?.jobs),()=>playing,{document,window,fetch,location});
async function boot(){try{data=await api('/api/studio');const recovery=JSON.parse(localStorage.getItem(draftKey())||'null');if(recovery){if(recovery.baseRevision===data.revision){notice('已恢复离开前未保存的编辑，请核对后继续。');if(recovery.units&&stage==='outline'){data.plan.units=recovery.units;Object.assign(data.plan,recovery.plan_fields||{});}if(recovery.sections&&stage==='script')data.sections=recovery.sections;serial=1;}else{notice('发现离开前的编辑；课程已有其他更新。原输入仍保留，请核对后选择恢复。');$('notice').append(button('恢复离开前的编辑',()=>{if(recovery.units){data.plan.units=recovery.units;Object.assign(data.plan,recovery.plan_fields||{});}if(recovery.sections)data.sections=recovery.sections;serial=1;render();}));}}render();announce();schedulePoll();}catch(e){notice(e.message,true);}}
const ready=boot().then(()=>{if(data?.production_preferences?.required&&productionPreferences.pending&&['storyboard','pilot','final'].includes(stage)&&finalPhase!=='body'&&!aiBusy)productionPreferences.open();});

return {ready,dispose(){window.dispatchEvent(new Event('pagehide'));}};
}
if(globalThis.document?.getElementById('course-title'))mountStudio();
