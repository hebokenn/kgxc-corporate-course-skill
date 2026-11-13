import {startActivity} from '/activity.js';
const $ = id => document.getElementById(id);
let status, lastRevision = -1, lastStateKey = null, planDirty = false, coursewareDirty = false, directorDirty = false;
let refreshTask = null, refreshTimer = null;
let serviceDisconnected = false;
startActivity(()=>planDirty||coursewareDirty||directorDirty);
const labels = {open:'待确认',confirmed:'已确认',stale:'内容已变，需复核',delivered:'已交付'};
const gateLabel = gate => (gate.delivery||gate.needs_artifact)&&gate.status==='open'?'待生成':labels[gate.status];
const dispositions = {core:'主课',optional:'选学',job_aid:'工作工具',separate:'另成专题',omit:'本课不展开'};
function el(tag, text, cls) {const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function note(text, error=false) {$('notice').textContent=text;$('notice').classList.toggle('error',error);$('notice').hidden=false;}
async function api(path, data) {
 const r=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;
}
function fileLink(path,text){const a=el('a',text,'artifact-link');a.href='/course-file?path='+encodeURIComponent(path);a.target='_blank';a.rel='noopener';return a;}
function empty(list, text){if(!list.length)return [el('p',text,'empty')];return list;}
function route(){for(const key of ['design','decisions','production']){const current=(location.hash||'#design')==='#'+key;$(key+'-view').hidden=!current;$('nav-'+key).setAttribute('aria-current',current?'page':'false');}}
window.addEventListener('hashchange',route);route();
function render() {
 const p=status.plan;
 $('course-title').textContent=p.title||'新课程';document.title=(p.title||'课程')+' · 共创工作台';
 $('connection').textContent='已保存 · r'+status.revision;$('next-action').textContent=status.next_action;
 $('pending-count').textContent=status.pending.filter(p=>p.kind!=='issue').length||'';$('design-status').textContent=p.stage==='script'?'逐字稿阶段':p.stage==='courseware'?'旧版内容稿':'结构草案';
 $('narration-status').textContent=status.narration_status==='not_required'?(status.branch==='courseware'?'课件分支无需配音':'确认后选择交付形式'):status.narration_status==='needs_regeneration'?'讲稿已变更，需更新小样与配音':status.narration_status==='ready'?'已生成完整视频':status.narration_status==='sample_ready'?'有声小样已生成':'尚未配音';
 $('nav-video').hidden=status.workflow_schema===2&&status.branch!=='video';
 $('stages').replaceChildren(...status.gates.map(g=>{const row=el('li');row.append(el('span',g.label),el('small',gateLabel(g)));return row;}));
 $('sources').replaceChildren(...empty((p.sources||[]).map(s=>{const row=el('div',null,'source');row.append(el('strong',s.title));if(s.kind==='file')row.append(fileLink(s.location,'查看保留的原始素材'));else row.append(el('p',s.location,'meta'));return row;}),'建档后将保留原件，并逐步补充来源与缺口。'));
 $('audience').textContent=p.audience?'面向：'+p.audience:'受众将在素材诊断后与你确定。';
 $('performance-task').textContent=p.performance_task||'正在从素材中确定需要解决的工作任务。';
 $('objectives').replaceChildren(...empty((p.objectives||[]).map(o=>{const row=el('div',null,'objective');row.append(el('strong',o.statement),el('p','如何检验：'+o.evidence,'meta'));return row;}),'先确定学员在工作中要完成的动作，再展开章节。'));
 $('units').replaceChildren(...empty((p.units||[]).map(u=>{const row=el('div',null,'unit');row.append(el('h4',u.title+' · '+(dispositions[u.disposition]||u.disposition)),el('p',u.activity));if(u.teaching_method)row.append(el('p','推荐讲法：'+u.teaching_method+'；'+u.teaching_reason));row.append(el('p','呈现：'+u.media+'；'+u.media_reason,'meta'));return row;}),'课程结构尚未形成，后续先提供结构与取舍供你选择。'));
 $('assessments').replaceChildren(...empty((p.assessments||[]).map(a=>{const row=el('div',null,'assessment');row.append(el('h4',a.task),el('p','评价依据：'+a.criteria),el('p','反馈：'+a.feedback,'meta'));return row;}),'关键能力将配套示范、练习与反馈。'));
 if(!planDirty)$('plan-data').value=JSON.stringify(p,null,2);
 renderBranch();renderDecisions();renderReviews();renderProduction();
 $('issues').replaceChildren(...empty((p.issues||[]).map(i=>el('p',(i.state==='open'?'待解决：':'已处理：')+i.detail+(i.resolution?'；'+i.resolution:''))),'当前没有登记的问题。'));
}
function renderDecisions(){
 const active=document.activeElement;
 if(active?.closest('.decision')&&status.revision===lastRevision)return;
 $('decisions').replaceChildren(...empty((status.plan.decisions||[]).map(d=>{
  const pending=status.pending.some(p=>p.id===d.id), box=el('article',null,'decision'+(!pending?' confirmed':''));box.dataset.decision=d.id;
  box.append(el('h3',d.question),el('p',d.finding,'finding'));
  for(const o of d.options){const label=el('label',null,'option'),radio=document.createElement('input');radio.type='radio';radio.name='decision-'+d.id;radio.value=o.id;radio.checked=!pending&&d.selected===o.id;
   const desc=el('span'),strong=el('strong',o.label);if(d.recommended===o.id)strong.append(el('span','推荐','recommended'));desc.append(strong,el('small',o.impact));label.append(radio,desc);box.append(label);}
  if(!pending)box.append(el('p','已保存 '+(d.confirmed_at||'')+'\n'+d.evidence,'receipt'));
  const comments=document.createElement('textarea');comments.setAttribute('aria-label',d.id+' 选择说明');comments.placeholder='可补充意见，也可以直接提交选项';box.append(comments);
  const submit=el('button',pending?'提交选择':'更新选择','primary');submit.onclick=async()=>{
   const radio=box.querySelector('input:checked');if(!radio){note('请先选择一个方案。',true);return;}
   const option=d.options.find(o=>o.id===radio.value);const evidence=d.question+' → '+option.label+(comments.value.trim()?'\n'+comments.value.trim():'');
   try{submit.disabled=true;status=await api('/api/workflow/decision',{id:d.id,selected:radio.value,evidence,baseRevision:status.revision});render();lastRevision=status.revision;note('选择已保存到课程工程，后续制作将读取这条记录。');}
   catch(e){note(e.message,true);}finally{submit.disabled=false;}
  };box.append(submit);return box;
 }),'当前没有待选择的内容。制作过程中发现会影响内容或制作量的事项，会出现在这里。'));
}
function renderReviews(){
 if(document.activeElement?.closest('.review')&&status.revision===lastRevision)return;
 $('reviews').replaceChildren(...status.gates.map(g=>{
  const row=el('article',null,'review');row.append(el('h4',g.label+' · '+gateLabel(g)));
  for(const path of status.artifacts[g.id]||[])row.append(fileLink(path,'查看审阅产物：'+path.split('/').at(-1)));
  if(g.status==='confirmed'||g.status==='delivered')row.append(el('p',g.receipt.at+'\n'+g.receipt.evidence,'receipt'));
  else if(status.workflow_schema===2&&(g.id==='style'||g.delivery)){
   row.append(el('p',g.id==='style'?'在制作与交付页查看三个实际风格并提交选择。':'文件完成后会显示交付记录。','hint'));if(g.id==='style'){const a=el('a','查看导演画面与三个风格');a.href='#production';row.append(a);}
   for(const reason of g.reasons)row.append(el('p',reason,'meta'));
  }
  else{if(g.reasons.length){const list=el('ul');for(const reason of g.reasons)list.append(el('li',reason));row.append(list);}
   const input=document.createElement('textarea');input.rows=2;input.setAttribute('aria-label',g.id+' 阶段确认说明');input.placeholder='记录你对当前版本的确认意见';row.append(input);
   const b=el('button','确认'+g.label);b.disabled=!g.ready;b.onclick=async()=>{try{
    if(!input.value.trim()){note('请填写对当前版本的确认说明。',true);return;}
    status=await api('/api/workflow/confirm',{gate:g.id,evidence:input.value,baseRevision:status.revision});render();lastRevision=status.revision;note('本阶段确认已保存。');
   }catch(e){note(e.message,true);}};row.append(b);
  }return row;
 }));
}
async function refresh(manual=false){
 if(manual)serviceDisconnected=false;
 if(refreshTask)return refreshTask;
 refreshTask=(async()=>{try{
 const next=await api('/api/workflow'), changed=next.state_key!==lastStateKey;status=next;serviceDisconnected=false;
 if(changed||manual){render();lastRevision=next.revision;lastStateKey=next.state_key;const c=await api('/api/script');if(!coursewareDirty)$('courseware').value=c.text;}
 $('connection').textContent='已保存 · r'+status.revision+(status.stage==='complete'?' · 空闲 2 分钟后工作台自动关闭':'');
 }catch(e){serviceDisconnected=true;$('connection').textContent=status?.stage==='complete'?'课程已完成，工作台已断开；再次编辑请从课程目录打开':'连接中断，可重新打开工作台';if(manual)note(e.message,true);}})();
 try{return await refreshTask;}finally{refreshTask=null;}
}
function scheduleRefresh(){
 clearTimeout(refreshTimer);
 if(!document.hidden&&!serviceDisconnected)refreshTimer=setTimeout(async()=>{await refresh();scheduleRefresh();},6000);
}
$('plan-data').oninput=()=>{planDirty=true;};$('courseware').oninput=()=>{coursewareDirty=true;$('courseware-dirty').textContent='有未保存修改';};
$('save-plan').onclick=async()=>{try{status=await api('/api/workflow/design',{plan:JSON.parse($('plan-data').value),baseRevision:status.revision});planDirty=false;render();lastRevision=status.revision;note('课程设计已保存，关联的旧确认会提示复核。');}catch(e){note(e.message,true);}};
$('save-courseware').onclick=async()=>{try{status=await api('/api/workflow/script',{text:$('courseware').value,baseRevision:status.revision});coursewareDirty=false;$('courseware-dirty').textContent='已保存';render();lastRevision=status.revision;note('逐字稿已保存。关联确认会按当前版本重新判断，独立课件仍保留。');}catch(e){note(e.message,true);}};
function renderBranch(){
 const modern=status.workflow_schema===2;$('branch-panel').hidden=!modern;if(!modern)return;
 const approved=status.gates.some(g=>g.id==='script'&&g.status==='confirmed');$('choose-branch').disabled=!approved;
 $('branch-summary').textContent=approved?(status.branch==='courseware'&&status.stage==='complete'?'课件与逐字稿已经交付。以后提出视频需求时，可切换到视频分支，从本稿启动导演。':'逐字稿已确认，请选择本次交付。两个分支独立保存，既有交付文件会保留。'):'先审阅并确认逐字稿，再选择课件或视频。';
 if(!document.activeElement?.closest('#branch-panel')||status.revision!==lastRevision)for(const radio of document.querySelectorAll('input[name="output-branch"]'))radio.checked=status.branch===radio.value;
 const r=status.branch_receipt;$('branch-receipt').textContent=r?r.at+'\n'+r.evidence:'';
}
function mediaPreview(path,container){
 if(path.toLowerCase().endsWith('.mp4')){const video=document.createElement('video');video.controls=true;video.preload='metadata';video.src='/course-file?path='+encodeURIComponent(path);video.setAttribute('aria-label','配音与画面小样播放器');container.append(video);}
 container.append(fileLink(path,'打开文件：'+path.split('/').at(-1)));
}
function renderStoryboard(){
 const enabled=status.planning_workflow==='storyboard-v1';
 let panel=$('storyboard-panel');
 if(!panel){panel=el('section',null,'section');panel.id='storyboard-panel';$('video-production').prepend(panel);}
 panel.hidden=!enabled;
 $('director-beats').closest('section').hidden=enabled;
 $('style-options').closest('section').hidden=enabled;
 $('director-data').closest('details').hidden=enabled;
 if(!enabled)return;
 if(document.activeElement?.closest('#storyboard-panel')&&status.revision===lastRevision)return;
 panel.replaceChildren(el('h3','全课内容演绎与分镜'));
 panel.append(el('p','先比较每个教学片段至少三种表现，确定全课分镜后再抽取三个完整片段生成有声动态小样。','hint'));
 const board=status.storyboard||{}, report=status.storyboard_report||{};
 const v=board.visual_direction||{};
 if(Object.keys(v).length){const art=el('details');art.append(el('summary','共用美术候选'));for(const [key,label] of [['palette','配色'],['typography','字体'],['graphics','图形与材质'],['atmosphere','气质']])if(v[key])art.append(el('p',label+'：'+v[key],'meta'));panel.append(art);}
 panel.append(el('p','逐字稿段落 '+(report.paragraph_count||0)+' · 教学片段 '+(report.segment_count||0)+' · 画面方案 '+(report.option_count||0)+' · 待选择 '+(report.pending||[]).length,'badge'));
 if((board.segments||[]).length)panel.append(fileLink('storyboard.html','打开全课分镜对照表'));
 const list=el('div');
 for(const segment of board.segments||[]){
  const box=el('details',null,'storyboard-segment'),sum=el('summary',segment.id+' · '+segment.teaching_goal+' · '+(segment.selected?'已选 '+segment.selected:'待选择'));
  box.dataset.segment=segment.id;box.append(sum,el('blockquote',segment.script_excerpt),el('p','类型：'+({concept:'概念讲解',scenario:'人物情境',operation:'过程演示',practice:'练习反馈'}[segment.kind]||segment.kind)+'；'+(segment.risk==='high'?'需重点验证':'常规风险'),'meta'));
  const grid=el('div',null,'style-grid');
  for(const option of segment.options||[]){
   const card=el('article',null,'style-card');card.append(el('h4',option.id+' · '+option.method+(segment.recommended===option.id?' · 推荐':'')));
   for(const [key,label] of [['opening','开始'],['action','画面变化'],['result','结果'],['focus','观看焦点'],['difference','方案差异'],['feasibility','实现条件'],['cost','预计成本'],['risk_note','需检查']])card.append(el('p',label+'：'+option[key]));
   if(option.reading_design){const rd=option.reading_design;card.append(el('p','焦点顺序：'+(rd.focus_order||[]).join(' → ')));for(const g of rd.information_groups||[])card.append(el('p','信息组：'+g.screen_text+'；读懂：'+g.read_task+'；动作 '+g.motion_seconds+'秒，完整停稳阅读 '+g.stable_read_seconds+'秒；保留：'+g.retention));if(!(rd.information_groups||[]).length)card.append(el('p',rd.no_new_text_reason||''))}
   card.append(el('p',option.characters?'使用人物':'不使用人物','meta'));
   const choice=el('label',null,'option'),radio=document.createElement('input');radio.type='radio';radio.name='shot-'+segment.id;radio.value=option.id;radio.checked=segment.selected===option.id;
   choice.append(radio,el('span','采用 '+option.id));card.append(choice);grid.append(card);
  }
  box.append(grid,el('p','推荐依据：'+segment.recommendation_reason));
  const noteInput=document.createElement('textarea');noteInput.rows=2;noteInput.setAttribute('aria-label',segment.id+' 分镜选择说明');noteInput.placeholder='可补充选择理由';box.append(noteInput);
  const save=el('button','保存本段选择');save.onclick=async()=>{try{const chosen=box.querySelector('input:checked');if(!chosen){note('请选择本段的画面方案。',true);return;}
   status=await api('/api/workflow/shot',{id:segment.id,option:chosen.value,evidence:segment.id+' 选择 '+chosen.value+(noteInput.value.trim()?'：'+noteInput.value.trim():''),baseRevision:status.revision});render();lastRevision=status.revision;note('本段选择已保存；全部选择后请确认全课分镜。');
  }catch(e){note(e.message,true);}};box.append(save);
  if(segment.selection_receipt)box.append(el('p',segment.selection_receipt.evidence,'receipt'));
  list.append(box);
 }
 panel.append(list);
 const evidence=document.createElement('textarea');evidence.setAttribute('aria-label','全课分镜确认说明');evidence.placeholder='记录对整课分镜与美术方向的意见；也可明确采用全部推荐方案';evidence.id='storyboard-evidence';panel.append(evidence);
 const bulk=el('button','采用全部推荐方案');bulk.disabled=!(board.segments||[]).length;bulk.onclick=async()=>{try{if(!evidence.value.trim()){note('请填写采用推荐方案的说明。',true);return;}status=await api('/api/workflow/shot',{id:'all',option:'recommended',evidence:evidence.value,baseRevision:status.revision});render();lastRevision=status.revision;note('推荐方案已按你的选择保存，仍需确认全课分镜。');}catch(e){note(e.message,true);}};panel.append(bulk);
 const gate=status.gates.find(g=>g.id==='storyboard'),confirm=el('button','确认全课分镜','primary');confirm.disabled=!gate?.ready;confirm.onclick=async()=>{try{if(!evidence.value.trim()){note('请填写对当前全课分镜的确认说明。',true);return;}status=await api('/api/workflow/confirm',{gate:'storyboard',evidence:evidence.value,baseRevision:status.revision});render();lastRevision=status.revision;note('全课分镜已确认，下一步分层抽样。');}catch(e){note(e.message,true);}};panel.append(confirm);
 if(gate?.status==='confirmed')panel.append(el('p',gate.receipt.evidence,'receipt'));
 const sampling=el('section');sampling.append(el('h4','三个样段的抽样计划'));
 const draw=el('button','分层随机抽取三个片段');draw.disabled=gate?.status!=='confirmed'||(!!status.sampling?.selections&&status.sampling.storyboard_sha256===status.storyboard_sha256);draw.onclick=async()=>{try{status=await api('/api/workflow/sample',{baseRevision:status.revision});render();lastRevision=status.revision;note('抽样已保存，制作端将按这三个完整片段生成小样。');}catch(e){note(e.message,true);}};sampling.append(draw);
 for(const item of status.sampling?.selections||[])sampling.append(el('p',item.segment_id+' / '+item.option_id+' · '+item.reason));
 if(status.sampling?.selections&&status.sampling.storyboard_sha256!==status.storyboard_sha256)sampling.append(el('p','以下为旧抽样记录，分镜已改变；本轮须重新抽样。','hint'));
 if(status.sampling?.selections){sampling.append(el('p',status.sampling.scope,'hint'));if(status.sampling.uncovered_kinds?.length)sampling.append(el('p','未抽中表现类型：'+status.sampling.uncovered_kinds.join('、'),'meta'));if(status.sampling.unsampled_high_risk_ids?.length)sampling.append(el('p','未抽中的高风险片段仍需生产验证：'+status.sampling.unsampled_high_risk_ids.join('、'),'meta'));}
 panel.append(sampling);
 const detail=el('details');detail.append(el('summary','制作人员：分镜数据'));
 const data=document.createElement('textarea');data.rows=12;data.setAttribute('aria-label','分镜数据');data.value=JSON.stringify(board,null,2);detail.append(data);
 const importButton=el('button','保存分镜数据');importButton.onclick=async()=>{try{status=await api('/api/workflow/storyboard',{storyboard:JSON.parse(data.value),baseRevision:status.revision});render();lastRevision=status.revision;note('分镜已保存，尚未确认的选择仍待审阅。');}catch(e){note(e.message,true);}};detail.append(importButton);panel.append(detail);
}
function renderProduction(){
 const modern=status.workflow_schema===2,branch=status.branch;
 $('production-title').textContent=branch==='courseware'?'课件制作与交付':branch==='video'?'导演与视频制作':'制作与交付';
 $('branch-badge').textContent=branch==='courseware'?'独立课件':branch==='video'?'视频':'待选择';
 $('production-summary').textContent=status.planning_workflow==='storyboard-v1'&&branch==='video'?'先确定全课内容演绎与分镜，再分层抽取三个完整片段验证动态、配音和字幕，确认后制作整课。':branch==='courseware'?'按已确认逐字稿独立制作课件，供讲授或自行录制。交付课件与逐字稿后，本次制作完成；以后仍可启动视频。':branch==='video'?'导演从已确认逐字稿和原始素材设计视频。先确认三个风格之一，再确认配音与画面小样，随后制作完整视频。':'结构与逐字稿确认后，在待你确认页选择课件或视频。';
 $('production-script').replaceChildren();if(status.plan.script_file)$('production-script').append(fileLink(status.plan.script_file,'查看当前逐字稿'));
 $('video-production').hidden=modern&&branch!=='video';
 const director=status.director||{};
 $('director-beats').replaceChildren(...empty((director.beats||[]).map(b=>{const row=el('div',null,'unit');row.append(el('h4',b.id+' · '+b.script_excerpt),el('p','画面：'+b.picture),el('p','动作：'+b.action));return row;}),'导演方案将在这里展示逐字稿与画面的对应关系。'));
 const activeStyle=status.gates.find(g=>g.id==='style'),validStyle=activeStyle?.status==='confirmed';
 if(!document.activeElement?.closest('#style-options')||status.revision!==lastRevision)$('style-options').replaceChildren(...empty((director.styles||[]).map(s=>{
  const box=el('article',null,'style-card');box.append(el('h4',s.title+(director.recommended===s.id?' · 推荐':'')));
  if(s.preview_file){const src='/course-file?path='+encodeURIComponent(s.preview_file);if(s.preview_file.endsWith('.html')){const frame=document.createElement('iframe');frame.src=src;frame.title=s.title+'预览';frame.setAttribute('sandbox','allow-scripts');box.append(frame);}else{const img=document.createElement('img');img.src=src;img.alt=s.title+'实际画面预览';box.append(img);}box.append(fileLink(s.preview_file,'放大查看画面'));}
  box.append(el('p',s.rationale));
  if(director.style_scope==='visual'){
   for(const [key,label] of [['palette','配色'],['typography','字体'],['graphics','图形与材质'],['atmosphere','画面气质']])box.append(el('p',label+'：'+(s.visual?.[key]||''),'meta'));
  }else if(s.motion)box.append(el('p','原方案动作说明：'+s.motion,'meta'));
  box.append(el('p','制作影响：'+s.production_impact,'meta'));
  const label=el('label',null,'option'),radio=document.createElement('input');radio.type='radio';radio.name='video-style';radio.value=s.id;radio.checked=validStyle&&status.selected_style===s.id;label.append(radio,el('span','选择 '+s.title));box.append(label);return box;
 }),'导演会提供三个可查看的视觉风格。'));
 $('choose-style').disabled=!activeStyle?.ready;
 $('style-receipt').textContent=validStyle?activeStyle.receipt.at+'\n'+activeStyle.receipt.evidence:status.selected_style?'原风格涉及内容变更，请重新查看并确认。':'';
 $('pilot-preview').replaceChildren();for(const path of status.artifacts.pilot||[])mediaPreview(path,$('pilot-preview'));
 if(!(status.artifacts.pilot||[]).length)$('pilot-preview').append(el('p',status.planning_workflow==='storyboard-v1'?'全课分镜确认后生成本次抽中的三个完整有声样段。':'风格确认后生成本课有声画面小样。','empty'));
 if(status.planning_workflow==='storyboard-v1'&&!status.pilot_is_current)$('pilot-preview').replaceChildren(el('p','本轮三个有声样段尚未生成；请先审阅分镜并按抽样计划制作。历史小样继续保留。','empty'));
 renderStoryboard();
 if(!directorDirty)$('director-data').value=JSON.stringify(director,null,2);
 $('deliveries').replaceChildren(...empty((status.deliveries||[]).map(d=>{const box=el('div',null,'unit');box.append(el('h4',(d.branch==='courseware'?'课件与逐字稿':'完整视频')+' · '+d.at),el('p',d.evidence+(d.script_sha256!==status.script_sha256?' · 对应此前版本逐字稿':''),'meta'));for(const f of d.files)box.append(fileLink(f.path,'下载 '+f.path.split('/').at(-1)));return box;}),'交付完成后，文件和记录会显示在这里。'));
 for(const job of status.jobs||[])if(job.status==='complete'&&job.video&&(status.artifacts.final||[]).some(p=>p.endsWith(job.video.split('/').at(-1)))){
  const box=el('div',null,'unit');box.append(el('h4','视频、字幕与可编辑工程'));
  for(const [key,label] of [['video','下载MP4'],['srt','下载SRT字幕'],['package','下载可编辑工程ZIP']])if(job[key]){const link=el('a',label,'artifact-link');link.href=job[key];box.append(link);}
  $('deliveries').append(box);
 }
}
$('choose-branch').onclick=async()=>{try{const selected=document.querySelector('input[name="output-branch"]:checked');if(!selected||!$('branch-evidence').value.trim()){note('请选择交付形式并记录本次需求。',true);return;}status=await api('/api/workflow/branch',{branch:selected.value,evidence:$('branch-evidence').value,baseRevision:status.revision});render();lastRevision=status.revision;note('交付形式已保存，原有逐字稿与交付文件保留。');}catch(e){note(e.message,true);}};
$('choose-style').onclick=async()=>{try{const selected=document.querySelector('input[name="video-style"]:checked');if(!selected||!$('style-evidence').value.trim()){note('请选择视觉风格，并记录确认说明。',true);return;}status=await api('/api/workflow/style',{id:selected.value,evidence:$('style-evidence').value,baseRevision:status.revision});render();lastRevision=status.revision;note('视觉风格已保存，动效继续按各段内容设计。下一步生成有声画面小样。');}catch(e){note(e.message,true);}};
$('director-data').oninput=()=>{directorDirty=true;};
$('save-director').onclick=async()=>{try{status=await api('/api/workflow/director',{director:JSON.parse($('director-data').value),baseRevision:status.revision});directorDirty=false;render();lastRevision=status.revision;note('导演方案已保存，三个风格等待明确选择。');}catch(e){note(e.message,true);}};
$('refresh').onclick=()=>refresh(true).then(scheduleRefresh);
window.addEventListener('beforeunload',e=>{if(planDirty||coursewareDirty||directorDirty){e.preventDefault();e.returnValue='';}});
if(location.protocol==='file:'){note('请从课程目录双击“打开课程工作台.command”，使用实际本地地址打开工作台。');$('connection').textContent='请从课程工程启动';}else{
 document.addEventListener('visibilitychange',async()=>{clearTimeout(refreshTimer);if(!document.hidden){await refresh();scheduleRefresh();}});
 await refresh(true);scheduleRefresh();
}
