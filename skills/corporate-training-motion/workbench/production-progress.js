const ACTIVE=new Set(['queued','rendering','encoding','packaging']);
export const activeJobs=jobs=>(jobs||[]).some(job=>ACTIVE.has(job.status));

// Keep failed attempts inspectable without presenting them as the current export.
export function productionJobHistory(jobs=[],purpose='final') {
  const list=jobs.filter(job=>job.purpose===purpose);
  const current=list.at(-1)||null;
  const history=list.slice(0,-1).map((job,index)=>{
    const successor=job.status==='failed'?list.slice(index+1).find(next=>next.status==='complete'&&
      (!Number.isFinite(job.revision)||!Number.isFinite(next.revision)||next.revision>=job.revision)):null;
    return {...job,supersededBy:successor?{id:successor.id,revision:successor.revision}:null};
  }).reverse();
  return {current,history};
}

// Derive a recoverable next action only from persisted job facts.
export function exportRecovery(jobs=[],stage='final',busy=false) {
  if(busy||activeJobs(jobs)||!['pilot','final'].includes(stage))return null;
  const {current}=productionJobHistory(jobs,stage);
  if(!current||!['failed','cancelled'].includes(current.status))return null;
  const title=stage==='pilot'?'小样':'成片';
  return {job_id:current.id,stage,label:'继续制作'+title,
    summary:(current.status==='failed'?title+'导出没完成':title+'制作已暂停'),
    detail:'已保存的成果会保留。继续时先检查能复用的文件，再补没做完的部分。'};
}

// Percentages describe a measured export job, never an estimate of AI thinking or remaining time.
export function productionProgress({stage,busy=false,data={},jobs=[],native}) {
  const list=jobs.length?jobs:data.jobs||[],active=list.filter(job=>ACTIVE.has(job.status)).at(-1);
  if(active){
    const value=Number.isFinite(active.progress)?Math.max(0,Math.min(1,active.progress)):null;
    const title=active.purpose==='pilot'?'有声小样':'整课视频';
    return {label:active.status==='queued'?title+'已进入合成队列':title+'正在渲染与编码'+(value===null?'':' · '+Math.floor(value*100)+'%'),value,
      detail:'进度来自实际合成任务，完成后还会校验成品。',tone:'working'};
  }
  const {current:latest}=productionJobHistory(list,stage);
  if(latest?.status==='failed')return {label:'本次合成未完成',value:0,detail:String(latest.error||'').trim().split('\n').filter(Boolean).at(-1)?.slice(0,240)||'请在右侧查看原因，修正后继续制作。',tone:'failed'};
  if(latest?.status==='cancelled')return {label:'本次合成已暂停，过程文件保留',value:null,detail:String(latest.error||'制作或监督暂停了本次任务；解除暂停后重新制作当前版本。'),tone:'waiting'};
  if(data.release_status?.state==='acceptance_blocked')return {label:'候选保留 · 当前验收受阻',value:null,
    detail:(data.release_status.errors||[]).map(e=>(e.code?e.code+'：':'')+e.message).slice(0,5).join('；')||'当前版本必检证据尚未齐备。',tone:'waiting'};
  if(['storyboard','pilot','final'].includes(stage)&&data.production_preferences?.required&&!data.production_preferences.storyboard_current)
    return {label:data.production_preferences.ready?'制作偏好已修改，等待更新对应成果':'待选择课程制作偏好',value:0,detail:'已有视频和历史记录保留；更新相关分镜与音视频后再登记当前结果。',tone:'waiting'};
  if(latest?.status==='complete'&&latest.registration_status==='held')return {label:'候选已生成 · 验收受阻',value:null,detail:'编码完成。当前缺项：'+(latest.contract_pending?.errors||[]).map(e=>e.code||e.message).slice(0,5).join('、')+'。候选可查看，尚未正式交付。',tone:'waiting'};
  const finalGate=data.gates?.find(g=>g.id==='final'),deliveredAt=Date.parse(finalGate?.receipt?.at||'');
  if(finalGate?.status==='delivered'&&Number.isFinite(deliveredAt)&&!busy&&!data.editor?.changed&&list.at(-1)?.status!=='failed'&&(!native?.issue||native.issue.at<deliveredAt))return {label:'整课制作与登记已完成',value:1,detail:'当前成品已通过制作端检查；历史失败保留在折叠记录中，不代表当前制作失败。',tone:'done'};
  const completedAt=latest?.completed_at|| (latest?.id&&native?.last_export?.job_id===latest.id?native.last_export.at:0);
  if(latest?.status==='complete'&&completedAt&&(!native?.issue||native.issue.at<completedAt)&&!data.editor?.changed&&data.gates?.find(g=>g.id===stage)?.status!=='stale')return {label:'候选编码完成 · 待成品审阅',value:null,detail:'当前候选可查看。正式交付与用户验收分别记录。',tone:'waiting'};
  if(native?.available){
    const issue=native.issue,current=native.current;
    if(issue)return {label:issue.label+(issue.count>1?'连续失败 '+issue.count+' 次':'失败')+(native.status==='stopped'?' · 已停止':''),value:0,
      detail:'失败步骤尚未通过，已有成果保留。'+(busy?'AI 仍在执行，请查看下方具体步骤。':'修复后可从当前阶段继续。'),tone:'failed'};
    if(current)return {label:current.label,value:null,detail:(current.subject?current.subject+' · ':'')+'已执行 '+Math.max(0,Math.floor((Date.now()-current.started_at)/1000))+' 秒。',tone:'working'};
    if(busy&&native.waiting_since)return {label:'等待模型安排下一步',value:null,detail:'本次等待 '+Math.max(0,Math.floor((Date.now()-native.waiting_since)/1000))+' 秒；下方保留已完成步骤。',tone:'working'};
    if(native.status==='stopped')return {label:'本轮制作已停止',value:0,detail:'已保存内容保留，可以核对最近步骤后继续。',tone:'waiting'};
  }
  if(busy)return {label:'AI 正在准备课程内容与素材',value:null,detail:latest?.status==='complete'?'视频已合成，AI 正在检查并整理当前结果。':'当前环节没有可准确核算的百分比；合成开始后自动显示实际进度。',tone:'working'};
  const gate=data.gates?.find(g=>g.id===stage);
  if(gate?.status==='stale'||data.editor?.changed&&['script','storyboard','pilot','final'].includes(stage))return {label:'内容已修改，等待更新对应成果',value:0,detail:'保存编辑与确认推进分别处理。',tone:'waiting'};
  if(stage==='sources'&&data.sources?.length)return {label:'已加入 '+data.sources.length+' 份原始资料',value:1,detail:'可核对原件及内容取舍。',tone:'done'};
  if(stage==='outline'&&data.plan?.units?.length)return {label:'已保存 '+data.plan.units.length+' 个章节的大纲',value:1,detail:'生成完成，内容仍由你审阅确认。',tone:'done'};
  if(stage==='script'&&data.editor?.text?.trim())return {label:'分章逐字稿已保存',value:1,detail:'可以手改、选段修改，再确认进入下一步。',tone:'done'};
  if(stage==='storyboard'&&data.storyboard?.segments?.length)return {label:'已保存 '+data.storyboard.segments.length+' 个片段的分镜方案',value:1,detail:gate?.status==='confirmed'?'分镜已确认。':'请选择方案并审阅确认。',tone:'done'};
  if(stage==='pilot'&&gate?.ready)return {label:'三段有声小样已就绪',value:1,detail:gate.status==='confirmed'?'当前小样已确认。':'请播放审阅，确认后再制作整课。',tone:'done'};
  if(stage==='final'&&gate?.status==='delivered')return {label:'整课制作与登记已完成',value:1,detail:'可播放检查并保存当前成品。',tone:'done'};
  if(latest?.status==='complete')return {label:'视频合成已完成 · 100%',value:1,detail:'制作端检查或登记尚待完成，不代表内容已获确认。',tone:'waiting'};
  return {label:'本阶段成果尚未生成',value:0,detail:'前置确认完成后，可以继续制作。',tone:'waiting'};
}
