// The durable backend owns every request, budget, report and approval.
import {sourceCoverageDeclaration} from '/source-coverage.js';
const RUNNING=new Set(['queued','checking','repairing','rendering','rechecking']);
const labels={script:'教学内容与讲稿',storyboard:'全课分镜与画面节奏',pilot:'实际有声小样',final:'最终交付文件'};
const stages=['script','storyboard','pilot','final'];
const pendingDecision=node=>node?.stage==='storyboard'?!node.passed:!node?.user_confirmed;
export const requiresUserAudio=(review,stage)=>['pilot','final'].includes(stage)&&review?.policy?.review_arrangement?.mode==='visual_ai_user_audio';
export const usesProducerAudio=(review,stage)=>['pilot','final'].includes(stage)&&review?.policy?.review_arrangement?.mode==='visual_ai_producer_audio';
function audioBinding(node){
  const audio=node?.user_audio_review,hashes=audio?.artifact_sha256s,artifacts=audio?.artifacts;
  if(!Array.isArray(hashes)||!hashes.length||!Array.isArray(artifacts)||artifacts.length!==hashes.length)return null;
  if(!artifacts.every((item,i)=>/^[a-f0-9]{64}$/.test(hashes[i])&&item.sha256===hashes[i]&&item.start_seconds===0&&Number.isFinite(item.end_seconds)&&item.end_seconds>0))return null;
  return {artifact_sha256s:[...hashes],artifacts:artifacts.map(({sha256,start_seconds,end_seconds})=>({sha256,start_seconds,end_seconds})),coverage:'all_stage_videos'};
}
function el(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
export function createReviewPanel({getData,getStage,host,action,save,refresh,onApproved,onState,readOnly=false,onError,isBusy,mediaURL,openSourceCoverage,document=globalThis.document,window=globalThis.window}){
  let state,timer,reading=false,closed=false,dialog,selected,input,draftTimer,lastFocus,sending=false,audioCheck,audioChoice,arrangementDialog,coverageCheck,coverageChoice;
  const shown=new Set();
  const refreshed=new Set();
  const draftKey=node=>'kgxc-review-input:'+String(state?.course_id||getData().course_path||getData().title)+':'+node.stage+':'+node.run.id;
  function localDraft(node){try{return localStorage.getItem(draftKey(node));}catch{return null;}}
  const launch=el('button','检查记录与问题清单');launch.id='ai-review-open';launch.type='button';launch.disabled=true;
  (document.getElementById('studio-tools-content')||document.querySelector('header')).append(launch);
  const arrangementLaunch=el('button','审阅分工');arrangementLaunch.id='review-arrangement-open';arrangementLaunch.type='button';arrangementLaunch.onclick=openArrangement;
  if(!readOnly)launch.before(arrangementLaunch);
  const progress=el('section',undefined,'ai-review-progress');progress.hidden=true;
  document.getElementById('production-progress').after(progress);
  launch.onclick=()=>{const candidate=choose();if(candidate?.run?.id)open(candidate);else if(!readOnly)void startInitial(candidate).catch(onError);};
  function choose(){return state?.nodes[getStage()]||stages.map(s=>state?.nodes[s]).find(n=>n?.run?.id&&pendingDecision(n))||state?.nodes.script;}
  function audioKey(node){return JSON.stringify([node.stage,node.run.id,node.run.fingerprint,node.fingerprint,state?.policy?.review_arrangement?.mode,audioBinding(node)]);}
  function openArrangement(){
    if(!arrangementDialog){arrangementDialog=el('dialog',undefined,'ai-review-dialog review-arrangement');arrangementDialog.setAttribute('aria-label','审阅分工');document.body.append(arrangementDialog);}
    arrangementDialog.replaceChildren(el('h2','审阅分工'),el('p','分工选择只安排本课审阅职责，不代表任何视频已听审、声音已通过或内容已确认。'));
    const label=el('label','本课审阅安排'),select=el('select');select.setAttribute('aria-label','本课审阅安排');
    for(const [value,text] of [['default_full_av','AI 完整视听审阅（沿用默认能力要求）'],['visual_ai_user_audio','由我听音轨，AI审文字与画面'],['visual_ai_producer_audio','配音免人工审核，由制作端自动技术检查']]){const option=el('option',text);option.value=value;select.append(option);}
    select.value=state?.policy?.review_arrangement?.mode||'default_full_av';label.append(select);arrangementDialog.append(label,el('p','选择用户听审时，需完整播放当前全部视频后声明；选择配音免人工审核时，无需逐句试听或音频审批。自动技术检查不等于完整听审，声音自然度及连续音画配合未验证时继续保留关键未知，内容与画面确认仍按原安排。','meta'));
    const controls=el('div',undefined,'review-actions');controls.append(makeButton('取消，不保存分工',()=>arrangementDialog.close()),makeButton('保存审阅分工',async()=>{
      if(sending||isBusy())throw Error('请等待当前检查、制作或保存结束，再调整审阅分工。');
      sending=true;try{await action('review-arrangement',{mode:select.value,evidence:'用户在工作台明确选择并保存审阅分工：'+select.selectedOptions[0].textContent,source:{kind:'ui',id:crypto.randomUUID()}});state=getData().ai_review;audioChoice=null;arrangementDialog.close();}finally{sending=false;}render();
    },true));arrangementDialog.append(controls);arrangementDialog.showModal();
  }
  function checkList(root,items){
    for(const item of items){const row=el('li');row.append(el('strong',item.verdict+' · '+item.label),el('p',item.reason));if(item.evidence?.length){const detail=el('details');detail.append(el('summary','证据与定位'),el('pre',JSON.stringify(item.evidence,null,2)));row.append(detail);}root.append(row);}
  }
  function render(){
    const node=choose(),active=stages.map(s=>state?.nodes[s]).find(n=>RUNNING.has(n?.status));
    const pending=stages.filter(s=>state?.nodes[s]?.run?.id&&pendingDecision(state.nodes[s]));
    launch.textContent=state?.hold?.held?'检查记录 · 课程已暂停':active?'查看检查进度':'检查记录与问题清单';
    launch.disabled=!node?.run?.id; // Internal review creation belongs to the workflow, not a user toolbar.
    progress.hidden=!active;progress.replaceChildren();
    if(active){progress.append(el('strong',labels[active.stage]+' · '+(active.run.events?.at(-1)?.text||'检查中')),el('p','累计 '+Math.floor(active.elapsed_ms/1000)+' 秒；当前未返回的项目保持检查中。'));
      const details=el('details');details.append(el('summary','查看检查、返修与耗时'),el('p','当前整体验收范围：'+(active.run.checklist||[]).map(c=>c.label).join('、')+'。逐项新结论尚未返回时不标记完成。'),el('pre',(active.run.events||[]).map(e=>e.at+' '+e.text).join('\n')));
      if(active.run.repaired?.length)details.append(el('p','已完成局部修改，正在复核：'+active.run.repaired.map(c=>c.path+' · '+c.reason).join('；')));progress.append(details);}
    if(dialog?.open&&selected){const latest=state.nodes[selected.stage];
      if(latest?.run?.id===selected.run?.id){selected=latest;paintDialog(false);}
      else{
        // A newer automatic round may start while an old summary is open.
        // Retain the old input without overwriting the newer round's draft.
        clearTimeout(draftTimer);const old=selected,text=input?.value||'';
        if(!readOnly)void host('review',{review_action:'draft',stage:old.stage,run_id:old.run.id,text}).catch(onError);
        dialog.close();selected=latest;input=null;
      }
    }
    if(readOnly){onState?.();return;}
    for(const stage of stages){const n=state?.nodes[stage];if(stage==='storyboard'||!n?.run?.id||RUNNING.has(n.status)||n.user_confirmed||n.run.dismissed_at||shown.has(n.run.id))continue;
      if(!dialog?.open){shown.add(n.run.id);open(n);}break;}
  }
  function open(node){
    if(!node?.run?.id){if(!readOnly)void startInitial(node).catch(onError);return;}
    if(!dialog){dialog=el('dialog',undefined,'ai-review-dialog');dialog.setAttribute('aria-labelledby','ai-review-title');document.body.append(dialog);
      dialog.addEventListener('cancel',event=>{event.preventDefault();void dismiss();});}
    selected=node;audioChoice=null;coverageChoice=null;lastFocus=document.activeElement;paintDialog(true);if(!dialog.open)dialog.showModal();
  }
  async function persistDraft(){if(!selected||!input)return;clearTimeout(draftTimer);await host('review',{review_action:'draft',stage:selected.stage,run_id:selected.run.id,text:input.value});}
  async function dismiss(){if(readOnly){dialog.close();lastFocus?.focus?.();return;}if(sending)return;try{await persistDraft();await host('review',{review_action:'dismiss',stage:selected.stage,run_id:selected.run.id});audioChoice=null;dialog.close();lastFocus?.focus?.();}catch(error){onError(error);}}
  function makeButton(label,handler,primary=false){const b=el('button',label,primary?'primary':undefined);b.type='button';b.disabled=sending;b.onclick=()=>void Promise.resolve(handler()).catch(onError);return b;}
  function paintDialog(reset){
    const node=selected,run=node.run,report=run.report||{},draft=reset?(localDraft(node)??node.draft):input?.value??node.draft,userAudio=requiresUserAudio(state,node.stage),producerAudio=usesProducerAudio(state,node.stage),binding=userAudio?audioBinding(node):null;
    const key=userAudio?audioKey(node):null;if(reset||audioChoice?.key!==key)audioChoice={key,checked:false};
    const focused=document.activeElement===input,start=input?.selectionStart,end=input?.selectionEnd;
    dialog.replaceChildren();const head=el('div',undefined,'row');head.append(el('h2',getData().title+' · '+labels[node.stage]));head.firstChild.id='ai-review-title';head.append(makeButton(readOnly?'关闭记录':'关闭，稍后处理',dismiss));dialog.append(head);
    dialog.append(el('p','每阶段当前选定方案仅一次盲审；问题一次汇总，后续集中修复并按固定清单验收。未解决项保持待处理。','meta'));
    dialog.append(el('p','审阅版本 '+run.id.slice(0,8)+' · 本轮输入 '+run.fingerprint.slice(0,12)+(run.fingerprint!==node.fingerprint?' · 当前输入 '+node.fingerprint.slice(0,12):''),'meta'));
    if(state?.hold?.held)dialog.append(el('p','课程审阅已暂停：'+state.hold.reason,'review-blocked'));
    dialog.append(el('p',node.status==='stale'?'内容已修改，待以当前证据核验固定清单；不自动增加盲审':node.stage==='storyboard'&&node.passed?'分镜当前清单验收通过，沿用已有选择与制作委托':node.user_confirmed?(userAudio?'AI文字与画面检查通过；当前全部媒体的用户听审与内容确认已记录，尚未据此宣称正式交付':'AI审阅已通过；用户已确认，尚未据此宣称正式交付'):RUNNING.has(node.status)?'本轮仍在检查或修复，请稍候':node.passed?(userAudio?'AI文字与画面审阅通过 · 待你完整听审并确认':'AI审阅通过 · 待你确认'):'仍有阻塞项 · 待处理', 'review-verdict'));
    if(userAudio){
      const scope=el('section',undefined,'review-audio-scope');scope.append(el('h3','文字与画面由 AI 检查，音轨由你听审'),el('p','AI检查文字、静帧与有时间定位的画面序列；画面序列不等于连续播放。音轨和音画配合需由你完整播放当前全部视频后确认。'));
      scope.append(el('p','用户听审：'+({confirmed:'当前全部视频已实际听审',stale:'先前听审对应旧媒体，当前版本待听审',issues_reported:'已记录声音问题，当前版本未确认',pending:'待完整播放当前全部视频'}[node.user_audio_review?.status]||'待取得当前媒体范围'),'review-verdict'));
      if(binding){const files=el('ul',undefined,'review-media-bindings');binding.artifacts.forEach((item,i)=>{const row=el('li','视频 '+(i+1)+' · '+item.start_seconds+'—'+item.end_seconds+' 秒 · SHA-256 '+item.sha256);const file=getData().artifacts?.[node.stage]?.find(f=>f.sha256===item.sha256&&f.available!==false);if(file&&mediaURL){const link=el('a','打开这一版完整视频');link.href=mediaURL(file.path);link.target='_blank';link.rel='noopener';row.append(' ',link);}files.append(row);});scope.append(files);}else scope.append(el('p','尚未取得当前全部视频的完整 SHA 与时长范围，不能作听审声明。','review-blocked'));
      dialog.append(scope);
    }
    if(producerAudio){
      const scope=el('section',undefined,'review-audio-scope');scope.append(el('h3','配音免人工审核，由制作端自动技术检查'),el('p','无需你逐句试听或审核配音。AI只审当前文字、实际帧及其时间顺序和技术事实；自动技术检查绑定当前视频字节。'));
      scope.append(el('p','未执行连续听审：声音自然度、残音、末句及连续音画配合仍未验证；关键未知继续阻断正式放行，内容与画面确认按原安排。','review-verdict'));
      const media=report.inspection?.media||[];if(media.length){const files=el('ul');for(const item of media)files.append(el('li','视频 SHA-256 '+item.sha256+' · 自动音轨技术检查：'+({passed:'通过（仅技术范围）',failed:'发现技术问题',unverified:'未完成'}[item.audio_technical?.status]||'尚未完成')));scope.append(files);}
      dialog.append(scope);
    }
    if(report.summary)dialog.append(el('p',report.summary));if(node.reason)dialog.append(el('p',node.reason,'review-blocked'));
    if(report.learner){const learner=report.learner;dialog.append(el('h3',node.review_cycle?.producer_only?'首次盲审的理解（修复结果见当前清单）':'独立学员的理解'));
      for(const [label,value] of [['内容是什么',learner.about],['讲了什么',learner.what_it_said],['学到了什么',learner.learned],['仍不明白',learner.confusions]])dialog.append(el('p',label+'：'+(Array.isArray(value)?value.join('；'):value||'尚未返回')));}
    const ledger=node.issue_ledger||run.issue_ledger||[];
    if(ledger.length){dialog.append(el('h3','固定问题清单与当前验收'));const issues=el('ul',undefined,'review-items');
      for(const issue of ledger){const row=el('li');row.append(el('strong',issue.id+' · '+({resolved:'已解决',unresolved:'未解决',open:'待验收',not_applicable:'不适用'}[issue.status]||issue.status||'待验收')+' · '+(issue.label||'')));
        row.append(el('p',issue.learning_impact||''),el('p','验收条件：'+(issue.acceptance_condition||'保留原问题依据，待补齐可观察条件')));
        if(issue.acceptance_reason)row.append(el('p',issue.acceptance_reason));
        if(issue.acceptance_evidence?.length){const detail=el('details');detail.append(el('summary','当前验收证据'),el('pre',JSON.stringify(issue.acceptance_evidence,null,2)));row.append(detail);}issues.append(row);}dialog.append(issues);}
    if(run.repaired?.length){dialog.append(el('h3','本轮已经修复'));const list=el('ul');for(const change of run.repaired)list.append(el('li',change.reason+'（'+change.path+'）'));dialog.append(list);}
    const unresolved=(report.items||[]).filter(i=>!['通过','不适用'].includes(i.verdict)&&!(userAudio&&i.responsibility==='user_audio'&&i.verdict==='待用户听审'));
    dialog.append(el('h3',userAudio?'AI职责范围内剩余问题与无法验证项':'剩余问题与无法验证项'));const list=el('ul',undefined,'review-items');checkList(list,unresolved);if(!unresolved.length)list.append(el('li',node.passed?(userAudio?'AI文字与画面范围内无未解决的必检项；音轨仍按用户听审状态处理。':'无未解决的必检项'):'本轮尚未获得完整有效的审阅结果'));dialog.append(list);
    if(report.findings?.length){if(ledger.length)dialog.append(el('h3','首次盲审发现（当前结果见固定清单）'));const findings=el('ul',undefined,'review-items');for(const item of report.findings){const row=el('li');row.append(el('strong',(item.severity?item.severity+' · ':'')+item.problem));if(item.evidence?.length){const details=el('details');details.append(el('summary','问题定位'),el('pre',JSON.stringify(item.evidence,null,2)));row.append(details);}findings.append(row);}dialog.append(findings);}
    if(report.next_step)dialog.append(el('p','AI建议：'+report.next_step));
    const coverage=getData().source_coverage,coverageRequired=node.stage==='script'&&coverage?.required&&!coverage.confirmed;
    const coverageKey=JSON.stringify([coverage?.report_sha256,coverage?.script_sha256,coverage?.sources_sha256,coverage?.current]);
    if(reset||coverageChoice?.key!==coverageKey)coverageChoice={key:coverageKey,checked:false};coverageCheck=null;
    if(coverageRequired){const section=el('section',undefined,'review-audio-scope');section.append(el('h3','原件取舍与新增内容需要人工确认'),el('p','覆盖率按原始业务要点统计，关键规则单列。请查看原件对照后，在本次逐字稿确认中一并提交；不增加盲审。'));
      if(openSourceCoverage)section.append(makeButton('查看原件与逐字稿对照',openSourceCoverage));
      if(readOnly){section.append(el('p','只读对照。请在右侧问答确认当前范围。','meta'));dialog.append(section);}else{
      const label=el('label',undefined,'review-audio-declaration');coverageCheck=el('input');coverageCheck.type='checkbox';coverageCheck.checked=!!coverageChoice.checked;coverageCheck.disabled=!coverage.current||sending||RUNNING.has(node.status)||!!state?.hold?.held;
      const text='已对照当前原件与讲稿，确认保留、合并、舍弃及新增内容和理由';coverageCheck.setAttribute('aria-label',text);label.append(coverageCheck,el('span',text));section.append(label);
      if(!coverage.current)section.append(el('p','尚无与当前原件和稿件一致的完整对照报告，暂不能确认。','review-blocked'));dialog.append(section);}}
    const usage=node.usage||{},tokens=Number.isFinite(usage.totalTokens)?usage.totalTokens:null;
    const unlimited=(state?.policy?.unlimited_counts??node.policy?.unlimited_counts)===true;
    const counts=unlimited?'本轮调用/返修次数暂不限，累计'+node.calls+'调用/'+node.repairs+'返修':'自动返修 '+node.repairs+'/'+node.policy.max_repairs+' 轮 · 调用预算 '+node.calls+'/'+node.policy.max_calls+' 次';
    dialog.append(el('p','累计耗时 '+Math.floor(node.elapsed_ms/1000)+' 秒 · '+counts+' · '+(tokens===null?'用量尚未返回':tokens.toLocaleString()+' tokens')+'。'+(unlimited?'累计调用次数':'预算次数')+'包含已预留尝试；实际推理与用量以明细为准。账户额度比例与费用未由宿主提供。','meta'));
    const evidence=el('details');evidence.append(el('summary','详细验收清单、检查范围与历史证据'));const all=el('ul',undefined,'review-items');checkList(all,report.items||[]);evidence.append(all,el('p','实际检查方法：'+(report.methods||[]).join('、')),el('pre',(report.limitations||[]).join('\n')));
    if(report.inspection)evidence.append(el('pre',JSON.stringify(report.inspection,null,2)));
    if(run.calls?.length){const calls=el('ul');for(const call of run.calls){const invoked=call.model_invoked===false?'模型未调用':call.model_invoked===true?'模型已调用':'调用状态按原记录核对';calls.append(el('li',(call.role||'历史审阅')+' · '+call.status+' · '+(call.execution_phase||'原记录')+' · '+invoked+' · '+(Number.isFinite(call.usage?.totalTokens)?call.usage.totalTokens+' tokens':'用量未返回')));}evidence.append(el('h3','调用与预留明细'),calls);}
    if(report.agent_audit)evidence.append(el('h3','独立审阅身份与只读范围'),el('pre',JSON.stringify(report.agent_audit,null,2)));
    if(report.producer_qa)evidence.append(el('h3','制作端来源核验'),el('pre',JSON.stringify(report.producer_qa,null,2)));
    if(report.supervision)evidence.append(el('h3','监督侦探报告'),el('pre',JSON.stringify(report.supervision,null,2)));
    if(node.legacy)evidence.append(el('p','此为历史知情审阅，不能作为当前独立盲审通过。'));
    if(run.events?.length)evidence.append(el('pre',run.events.map(e=>e.at+' '+e.text).join('\n')));
    if(run.error_history?.length)evidence.append(el('pre',run.error_history.map(e=>e.at+' · '+e.reason+' · '+(e.resolved_by?'执行已由更新成果恢复（'+e.resolution_scope+' / '+e.resolved_by.slice(0,12)+'）':'尚未恢复')).join('\n')));
    if(node.history.length){const history=el('details');history.append(el('summary','历史审阅与失败记录'),el('pre',node.history.map(h=>h.id.slice(0,8)+' · '+h.status+(h.reason?' · '+h.reason:'')+(h.superseded_by?' · 已由 '+h.superseded_by.slice(0,8)+' 成功版本替代':' · 未标记为已解决')).join('\n')));evidence.append(history);}dialog.append(evidence);
    if(readOnly){if(pendingDecision(node)&&node.passed)dialog.append(el('p','需要你确认时，AI 会在右侧对话发起问答。','meta'));return;}
    const label=el('label','审阅重点或修改意见（自动保存）');input=el('textarea');input.value=draft||'';input.rows=3;input.setAttribute('aria-label','审阅重点或修改意见');input.oninput=()=>{try{localStorage.setItem(draftKey(node),input.value);}catch{}clearTimeout(draftTimer);draftTimer=setTimeout(()=>persistDraft().catch(onError),500);};label.append(input);dialog.append(label);
    audioCheck=null;if(userAudio&&!node.user_confirmed){const declaration=el('label',undefined,'review-audio-declaration');audioCheck=el('input');audioCheck.type='checkbox';audioCheck.checked=!!audioChoice.checked;audioCheck.disabled=!binding||sending||RUNNING.has(node.status)||node.status==='stale'||!!state?.hold?.held;
      const text='已完整播放当前全部'+(node.stage==='pilot'?'小样':'成片')+'，声音与音画配合无问题';audioCheck.setAttribute('aria-label',text);declaration.append(audioCheck,el('span',text));dialog.append(declaration,el('p','仅勾选后主动点击本次确认才记录声明；关闭、刷新、超时和选择分工均不代表听审通过。','meta'));}
    const controls=el('div',undefined,'review-actions');
    const confirm=makeButton(node.passed?(node.stage==='storyboard'?'按既有选择继续制作':'确认并进入下一阶段'):'集中修复并验收',()=>node.passed?approve():request('modify',input.value.trim()||'制作端按当前选定方案的固定问题清单集中修复，保留差异与当前证据，逐项定向验收，不重新盲审。'),true);
    const blocked=sending||RUNNING.has(node.status)||state?.hold?.held;
    const disableConfirm=()=>{confirm.disabled=blocked||node.status==='limit_reached'||(node.passed&&coverageRequired&&(!coverage.current||!coverageCheck?.checked))||(userAudio&&node.passed&&(!binding||node.status==='stale'||node.user_confirmed||!audioCheck?.checked));};disableConfirm();if(audioCheck)audioCheck.onchange=()=>{audioChoice={key,checked:audioCheck.checked};disableConfirm();};if(coverageCheck)coverageCheck.onchange=()=>{coverageChoice={key:coverageKey,checked:coverageCheck.checked};disableConfirm();};controls.append(confirm);
    const continueButton=makeButton(node.review_cycle?.blind_review_completed||node.run.blind_report?'继续清单验收':'开始一次盲审',()=>request('continue',input.value));continueButton.disabled=blocked;controls.append(continueButton);
    const modify=makeButton('按意见修改并验收',()=>{if(!input.value.trim())throw Error('请先填写修改意见。');return request('modify',input.value);});modify.disabled=blocked||node.status==='limit_reached';controls.append(modify);
    if(userAudio){const feedback=makeButton('保存声音问题，不确认',async()=>{if(!input.value.trim())throw Error('请先填写具体的声音或音画配合问题。');if(sending)return;sending=true;try{await persistDraft();await action('feedback',{stage:node.stage,time:0,text:input.value});state=getData().ai_review;audioChoice=null;}finally{sending=false;}paintDialog(false);dialog.append(el('p','声音问题已保存；尚未确认或进入下一阶段。','review-blocked'));});feedback.disabled=blocked;controls.append(feedback);}dialog.append(controls);
    if(node.status==='limit_reached'&&!state?.hold?.held){const extension=el('details');extension.append(el('summary','明确追加返修授权'),el('p','保留成果。只有主动点击下方按钮才追加本节点 1 轮定向返修和 2 次调用，不增加盲审次数；沿用当前模型和计费来源。'),makeButton('追加 1 轮返修与 2 次调用',async()=>{await action('review-extend',{stage:node.stage,repairs:1,calls:2,evidence:'用户在审阅窗口明确点击追加1轮返修与2次调用，仅限当前节点固定清单的定向修复和原有模型通道，不增加盲审次数'});await request('continue',input.value);}));dialog.append(extension);}
    if(focused){input.focus();input.setSelectionRange(start,end);}
  }
  async function request(mode,instruction){
    if(state?.hold?.held)throw Error('课程已暂停，请明确恢复后再审阅。');
    if(sending||isBusy())throw Error('请等待当前检查或制作结束，再开始新一轮。');
    sending=true;const stage=selected.stage;
    try{await save();await persistDraft();await host('review',{review_action:mode,stage,request_id:crypto.randomUUID(),instruction});dialog.close();await sync();}
    finally{sending=false;}
  }
  async function startInitial(node){
    if(sending)return;
    if(state?.hold?.held)throw Error('课程已暂停：'+state.hold.reason);
    await save();if(isBusy())throw Error('请等待当前制作或保存结束。');sending=true;
    try{await host('review',{review_action:'continue',stage:node?.stage||'script',request_id:crypto.randomUUID(),instruction:''});await sync();}
    finally{sending=false;}
  }
  async function approve(){
    if(sending)return;const stage=selected.stage,userAudio=requiresUserAudio(state,stage);let declaration;
    const sourceDeclaration=stage==='script'?sourceCoverageDeclaration(getData().source_coverage,!!coverageCheck?.checked&&!!coverageChoice?.checked):undefined;
    if(userAudio){const binding=audioBinding(selected);if(!binding||!audioCheck?.checked||!audioChoice?.checked||audioChoice.key!==audioKey(selected)||selected.status==='stale')throw Error('请完整播放当前全部视频，并明确勾选当前版本的听审声明。');declaration={...binding,listened_completely:true,audio_and_sync_ok:true,evidence:audioCheck.getAttribute('aria-label'),source:{kind:'ui',id:crypto.randomUUID()}};}
    sending=true;
    try{await save();await persistDraft();await action('review-approve',{stage,run_id:selected.run.id,...(declaration?{audio_declaration:declaration}:{}),...(sourceDeclaration?{source_coverage_declaration:sourceDeclaration}:{})});state=getData().ai_review;
      if(userAudio&&!state?.nodes?.[stage]?.user_confirmed)throw Error('本次未取得当前全部媒体的听审与内容确认，保持当前阶段。');
      audioChoice=null;dialog.close();await refresh();await onApproved(stage);}
    finally{sending=false;}
  }
  async function sync(){
    if(closed||reading||document.hidden)return;reading=true;
    try{const result=await host('review',{review_action:'sync',busy:isBusy()});state=result.review;
      const completed=stages.map(s=>state?.nodes?.[s]).filter(n=>n?.run?.completed_at);
      const completionKey=n=>JSON.stringify([n.run.id,n.run.completed_at,n.fingerprint,n.status,n.passed,n.user_confirmed]);
      if(completed.some(n=>!refreshed.has(completionKey(n)))){
        const didRefresh=await refresh();if(didRefresh!==false)for(const n of completed)refreshed.add(completionKey(n));
      }render();}
    finally{reading=false;clearTimeout(timer);if(!closed)timer=setTimeout(()=>sync().catch(onError),3000);}
  }
  window.addEventListener('pagehide',()=>{closed=true;clearTimeout(timer);clearTimeout(draftTimer);});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)void sync().catch(onError);});
  return {sync,open:()=>open(choose()),get state(){return state;}};
}
