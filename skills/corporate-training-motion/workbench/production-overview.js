const confirmationStages=['script','pilot','final'];
const confirmationNames={script:'逐字稿',pilot:'有声小样',final:'成片'};
const running=new Set(['queued','checking','repairing','rendering','rechecking','running']);
export function confirmationStageStatus(data={},stage){
  const gate=(data.gates||[]).find(g=>g.id===stage),node=data.ai_review?.nodes?.[stage];
  if(gate?.status==='delivered')return {id:'delivered',text:'已交付'};
  if(node?.status==='stale'||gate?.status==='stale')return {id:'stale',text:'版本已变更'};
  if(node?.user_confirmed||!data.ai_review?.enabled&&gate?.status==='confirmed')return {id:'confirmed',text:'已确认'};
  if(data.ai_review?.hold?.held)return {id:'blocked',text:'已暂停'};
  const pending=(data.pending_confirmations||[]).find(x=>x.stage===stage);
  const display=data.confirmation_display;
  const current=pending&&display?.stage===stage&&display?.question_id===pending.id&&(!display.course_path||display.course_path===data.course_path)?display.status:null;
  if(current==='visible')return {id:'waiting',text:'请在右侧确认'};
  if(current==='failed'||current==='error')return {id:'retry',text:'问答未打开，可在右侧重试'};
  if(current==='deferred'||current==='skipped'||pending?.decision_status==='deferred')return {id:'paused',text:'已暂缓，可在右侧继续'};
  if(current==='changes_requested'||pending?.decision_status==='changes_requested')return {id:'changes',text:'已要求修改，可在右侧补充'};
  if(pending)return {id:'queued',text:'正在准备右侧问答'};
  if(running.has(node?.status))return {id:'checking',text:'AI 正在检查'};
  if(['limit_reached','failed'].includes(node?.status)||node?.run?.id&&node.status==='awaiting_confirmation'&&!node.passed||gate?.status==='blocked')return {id:'blocked',text:'待 AI 处理'};
  const hasCandidate=stage==='script'?!!data.editor?.text?.trim():!!data.artifacts?.[stage]?.some(file=>file.available===true&&/\.mp4$/i.test(file.path||''));
  if(gate?.ready||node?.passed||hasCandidate)return {id:'blocked',text:'已生成 · 尚未达到确认条件'};
  return {id:'pending',text:'未到确认节点'};
}
function compact(value,limit=240){
  return typeof value==='string'?value.trim().slice(0,limit):'';
}
export function confirmationHistory(data={},stage){
  const explicit=Array.isArray(data.confirmation_records)?data.confirmation_records.filter(x=>x?.stage===stage&&x.id):[];
  if(explicit.length)return explicit.map(x=>({...x,label:compact(x.label)||confirmationNames[stage],evidence:compact(x.evidence)}));
  // Legacy, version-bound receipts only. Never treat a review pass or the existence of a video as consent.
  const receipt=data.ai_review?.nodes?.[stage]?.confirmation;
  if(!receipt||(!receipt.run_id&&!receipt.sha256)||!receipt.actor||(!receipt.artifact_hashes?.length&&!receipt.sha256))return [];
  return [{stage,id:receipt.run_id||receipt.sha256,status:'confirmed',at:receipt.at||receipt.confirmed_at||'',label:confirmationNames[stage],evidence:compact(receipt.evidence)||'已保留与对应内容版本绑定的确认记录'}];
}
// Read-only projection: never infer acceptance or source usage from file presence.
export function overviewModel(data={},stage='pilot',state={}) {
  const gates=(data.gates||[]).map(g=>({id:g.id,status:g.status||'unknown'}));
  const review=data.ai_review?.nodes?.[stage];
  const evidence=review?.passed?'检查已通过':review?.status==='running'?'正在检查':'尚无通过记录';
  const points=data.source_coverage?.report?.points||[];
  return {gates,evidence,activity:state.label||'正在读取制作状态',
    materials:points.map(p=>({label:p.source_quote||p.id,status:({retained:'保留',merged:'合并使用',omitted:'未使用'})[p.disposition]||'待核对',reason:p.reason||'尚未登记理由'})),
    issue:data.release_status?.state==='acceptance_blocked'?(data.release_status.errors||[]).map(e=>e.message).join('；'):null};
}
export function nextAction(data={},stage,state={}){
  const text={script:'查看当前讲稿',pilot:'完整看完三段有声小样',final:'查看当前成片'};
  if(data.confirmation_display?.editing_feedback)return {title:'正在填写修改意见',detail:'在右侧写清楚要改什么，再提交给 AI。',tone:'action',kicker:'当前'};
  const visible=data.confirmation_display?.stage;
  if(text[visible]&&confirmationStageStatus(data,visible).id==='waiting'){
    const tab={script:'逐字稿',pilot:'有声小样',final:'后期与成片'}[visible];
    const onPreview=visible===stage&&(visible!=='final'||state.phase!=='body');
    return {title:onPreview?'看完后确认':text[visible],detail:onPreview?'看完当前内容后，在右侧确认或提出修改。':'先到顶部「'+tab+'」查看，看完后在右侧确认。',tone:'action'};
  }
  const target=(data.pending_confirmations||[]).some(item=>item.stage===visible&&item.id===data.confirmation_display?.question_id)?visible:stage,status=confirmationStageStatus(data,target);
  if(['retry','paused','changes'].includes(status.id))return {title:status.text,detail:'已有成果会保留，不会自动确认。',tone:'waiting'};
  if(status.id==='queued')return {title:'正在准备右侧问答',detail:'现在不需要操作，问答打开后再查看。',tone:'waiting'};
  if(state.tone==='working')return {title:state.label||'AI 正在制作',detail:'现在不需要你操作。',tone:'working'};
  if(status.id==='checking')return {title:'AI 正在检查'+(confirmationNames[stage]||'当前成果'),detail:'检查通过后会打开右侧问答。',tone:'working'};
  if(state.recovery)return {title:state.label,detail:state.detail,tone:'waiting'};
  if(state.tone==='failed'||status.id==='blocked')return {title:'当前成果还不能确认',detail:state.detail||'查看下方作品；右侧问答尚未开启。',tone:'waiting'};
  if(stage==='sources')return {title:'加入制作资料',detail:'上传原文件或实拍照片，再查看素材的去向。',tone:'waiting'};
  return {title:state.label||'查看当前作品',detail:state.detail||'',tone:state.tone||'waiting'};
}
export function createProductionOverview({document,onCoverage}) {
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  const root=el('section',null,'production-overview');root.setAttribute('aria-label','制作提示');
  const head=el('div',null,'overview-now'),title=el('h2'),detail=el('p',null,'overview-next-detail'),kicker=el('span','状态','overview-next-kicker');head.append(kicker,title,detail);root.append(head);
  const archive=el('details',null,'overview-history');
  archive.append(el('summary','确认历史与检查记录'));
  const confirmations=el('section',null,'confirmation-strip');confirmations.setAttribute('aria-label','人工确认状态');
  const confirmationGrid=el('div',null,'confirmation-grid');confirmations.append(confirmationGrid);archive.append(confirmations);
  const details=el('details',null,'overview-details');details.append(el('summary','查看原件取舍及检查问题'));const records=el('div');details.append(records);archive.append(details);
  const views=new Map();
  for(const stage of confirmationStages){
    const card=el('section',null,'confirmation-card'),header=el('div',null,'confirmation-card-head');
    header.append(el('strong',confirmationNames[stage]));const badge=el('span',null,'confirmation-status');header.append(badge);card.append(header);
    const recordWrap=el('div',null,'confirmation-record-wrap'),recordToggle=el('button',null,'confirmation-record-toggle'),recordPanel=el('div',null,'confirmation-record-panel');
    const panelId='confirmation-record-'+stage;recordToggle.type='button';recordToggle.setAttribute('aria-controls',panelId);recordToggle.setAttribute('aria-expanded','false');recordToggle.setAttribute('aria-pressed','false');
    recordPanel.id=panelId;recordPanel.hidden=true;recordWrap.append(recordToggle,recordPanel);card.append(recordWrap);confirmationGrid.append(card);
    let hover=false,focused=false,pinned=false,suppressPreview=false;
    const paint=()=>{
      const shown=pinned||(!suppressPreview&&(hover||focused));
      recordPanel.hidden=!shown;recordToggle.setAttribute('aria-expanded',String(shown));recordToggle.setAttribute('aria-pressed',String(pinned));
    };
    recordWrap.addEventListener('pointerenter',()=>{hover=true;suppressPreview=false;paint();});
    recordWrap.addEventListener('pointerleave',()=>{hover=false;if(!focused)suppressPreview=false;paint();});
    recordWrap.addEventListener('focusin',()=>{focused=true;paint();});
    recordWrap.addEventListener('focusout',event=>{if(!recordWrap.contains(event.relatedTarget)){focused=false;if(!hover)suppressPreview=false;paint();}});
    recordToggle.addEventListener('click',()=>{pinned=!pinned;suppressPreview=!pinned;paint();});
    recordWrap.addEventListener('keydown',event=>{if(event.key==='Escape'){pinned=false;suppressPreview=true;paint();event.stopPropagation();}});
    views.set(stage,{card,badge,recordToggle,recordPanel});
  }
  function updateConfirmations(data){
    for(const [stage,{card,badge,recordToggle,recordPanel}] of views){
      const status=confirmationStageStatus(data,stage),history=confirmationHistory(data,stage);
      card.dataset.state=status.id;badge.textContent=status.text;recordToggle.textContent='确认记录'+(history.length?' · '+history.length:'');
      recordToggle.setAttribute('aria-label',confirmationNames[stage]+'确认记录，点击固定或取消固定');
      const rows=el('ul');
      for(const record of history){
        const state=({confirmed:'已确认',approved:'已确认',declined:'暂不确认',deferred:'稍后确认',changes_requested:'要求修改',revoked:'已失效',stale:'对应旧版本'})[record.status]||'已登记';
        const row=el('li');row.append(el('strong',state));
        const at=record.at?new Date(record.at):null;if(at&&!Number.isNaN(at.valueOf())){const t=el('time',at.toLocaleString());t.dateTime=at.toISOString();row.append(t);}
        const current=data.ai_review?.nodes?.[stage]?.fingerprint;
        if(/^[a-f0-9]{12,}$/i.test(record.fingerprint||'')){
          const historical=current&&current!==record.fingerprint;
          row.append(el('p',(historical?'旧版本 ':'版本 ')+record.fingerprint.slice(0,12)));
        }
        if(record.evidence)row.append(el('p',record.evidence));rows.append(row);
      }
      recordPanel.replaceChildren(history.length?rows:el('p','还没有可核实的确认记录。'));
    }
  }
  function update(data,stage,state){const m=overviewModel(data,stage,state),next=nextAction(data,stage,state);
    root.dataset.tone=next.tone;kicker.textContent=next.kicker||(next.tone==='action'?'下一步':'状态');title.textContent=next.title;detail.textContent=next.detail;
    updateConfirmations(data);
    records.replaceChildren();if(m.issue)records.append(el('p','待处理：'+m.issue,'overview-issue'));
    if(!m.materials.length)records.append(el('p','原件取舍尚未登记。'));
    for(const p of m.materials){const row=el('p');row.append(el('strong',p.status+' · '),el('span',p.label),el('small',p.reason));records.append(row);}
    const b=el('button','查看完整原件对照');b.onclick=onCoverage;records.append(b);
  }
  return {mount:container=>container.append(root),mountHistory:container=>container.append(archive),update};
}

export const materialStatuses={
  used:{title:'已出现在视频',description:'已在当前视频中找到这个素材。'},
  unused:{title:'未入片',description:'已记录未放入视频。'},
  reference:{title:'已供讲稿参考',description:'已核对讲稿引用，是否入片尚未核实。'},
  unverified:{title:'还没核对',description:'已入库，尚未核实是否入片。'},
};
function relativeMaterialPath(path){
  if(typeof path!=='string'||!path||path.startsWith('/')||/^[a-z]+:/i.test(path)||path.includes('\\'))return false;
  const clean=path.replace(/^\.\.\/(?:inputs|delivery)\//,'');
  return clean.split('/').every(part=>part&&part!=='.'&&part!=='..');
}
export function materialRows(library,sources=[]){
  const provided=Array.isArray(library)?library:[];
  const found=new Set(provided.map(item=>item?.source_id).filter(Boolean));
  const fallback=sources.filter(item=>item?.id&&!found.has(item.id)).map(item=>({id:item.id,source_id:item.id,title:item.title,path:item.location,available:item.available,kind:/\.(png|jpe?g|webp|gif|heic|avif|tiff?)$/i.test(item.location||'')?'image':'file'}));
  return [...provided,...fallback].filter(item=>item?.id).map(item=>{
    const source_points=Array.isArray(item.source_points)?item.source_points.filter(p=>p&&typeof p==='object'):[];
    const status=item.status==='unverified'&&item.kind==='file'&&source_points.some(p=>['retained','merged'].includes(p.disposition))?'reference':Object.hasOwn(materialStatuses,item.status)?item.status:'unverified';
    const placements=(Array.isArray(item.placements)?item.placements:[]).filter(p=>status==='used'&&['pilot','final','body'].includes(p?.stage)&&relativeMaterialPath(p.artifact_path)&&/^[a-f0-9]{64}$/i.test(p.artifact_sha256||'')&&Number.isFinite(p.start_seconds)&&p.start_seconds>=0&&Number.isFinite(p.end_seconds)&&p.end_seconds>p.start_seconds);
    return {...item,status,placements,path:relativeMaterialPath(item.path)?item.path:null,source_points};
  });
}
