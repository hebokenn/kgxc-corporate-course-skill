// Fold DSH's committed execution events. No model estimates, source text or raw commands are retained.
const stages={outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课视频'};
const basename=value=>String(value||'').split(/[\\/]/).at(-1).slice(0,100);
const parse=value=>{try{return typeof value==='string'?JSON.parse(value):value||{};}catch{return {};}};
const textOf=content=>(content||[]).filter(b=>b.type==='text').map(b=>b.text||'').join('\n');
const exitCode=text=>{const match=String(text).match(/(?:\[exit code:\s*|^exit code:\s*|\[status:\s*[^,\]]+,\s*exit code:\s*)(-?\d+)\]?\s*$/im);return match?Number(match[1]):null;};
const compact=text=>{const content=String(text||'').trim(),value=parse(content.split('\n[status:')[0]);if(value.errors?.length)return String(value.errors[0]).slice(0,600);const lines=content.split('\n').filter(Boolean);return (lines.find(line=>/^(?:[\w.]+Error|[\w.]+Exception|StopIteration)(?::|$)/.test(line))||lines.slice(-3).join('\n')).slice(0,600);};

export function initialProduction(){return {operation:null,running:false,status:'idle',last_event_at:0,model_wait_at:null,model_wait_ms:0,last_export:null,items:[],failures:[]};}

function operationOf(data){
  if(data.source?.kind!=='kgxc-course-context')return null;
  const text=textOf(data.content),line=text.split('\n').find(line=>line.startsWith('KGXC_OPERATION '));
  const marker=line?parse(line.slice(15)):null;
  if(marker?.course_path&&stages[marker.stage])return {course_path:marker.course_path,stage:marker.stage};
  // Recognize stage handoffs written by 0.5 before the explicit marker existed.
  const old=text.match(/课程工程位于当前会话工作区内：("(?:[^"\\]|\\.)*")。目标阶段=(outline|script|storyboard|pilot|final)/);
  return old?{course_path:parse(old[1]),stage:old[2]}:null;
}

export function describeCall(name,args){
  const file=basename(args.file_path||args.path||''),command=String(args.command||'');
  let kind='tool',label=args.description||name,subject=file;
  if(name==='bash'){
    const scripts=[...command.matchAll(/(?:^|[\s/"'])(([\w-]+)\.py)(?=[\s"']|$)/g)].map(m=>m[1]);subject=scripts[0]||'';
    if(/qwen|generate[_-]?(?:voice|speech)|tts\.py/i.test(command+' '+args.description)){kind='voice';label='生成配音';}
    else if(/transcrib|whisper|(?:^|[^a-z])asr(?:[^a-z]|$)/i.test(command+' '+args.description)){kind='alignment';label='核对配音内容与字幕时间';}
    else if(scripts.some(s=>/^build_/.test(s))){kind='build';label='构建画面与时间轴';}
    else if(/ffprobe/.test(command)){kind='check';label='核对媒体时长与格式';subject='媒体参数';}
    else if(/(?:workbench|workflow)\.py["']?\s+export\b|render_worker\.py/.test(command)||/^(?:Render|Export)\b/i.test(args.description||'')){kind='render';label='导出视频';}
    else {kind='execute';label='执行制作步骤';subject=String(args.description||subject).slice(0,140);}
  }else if(['read','read_file'].includes(name)){kind='read';label='读取制作资料与接口';}
  else if(['glob','grep','search'].includes(name)){kind='read';label='查找制作接口';subject=String(args.pattern||args.glob||'').slice(0,100);}
  else if(['write','edit','apply_patch'].includes(name)){kind='edit';label=/\.py$/.test(file)?'编排或修正画面脚本':'保存课程内容';}
  else if(['task_read','job_output'].includes(name)){kind='wait';label='读取后台制作结果';subject=String(args.job_id||args.task_id||args.id||'').slice(0,100);}
  else if(name==='ask_user_question'){kind='question';label='等待你的选择';subject='';}
  else if(name==='kgxc_course_update'){kind='save';label='保存'+(stages[args.stage]||'课程成果');subject='';}
  else if(name==='kgxc_course_export'){kind='render';label='提交实际视频合成';subject='';}
  else if(/^kgxc_course_/.test(name)){kind='check';label='核对当前课程状态';subject='';}
  return {name,kind,label:String(label).slice(0,100),subject,key:kind+':'+subject,critical:['build','voice','alignment','render','save','execute'].includes(kind)};
}

function trim(items){const active=items.filter(x=>x.status==='running').slice(-8),rest=items.filter(x=>x.status!=='running').slice(-16);return [...active,...rest].sort((a,b)=>a.started_at-b.started_at);}
function settle(state,item,status,time,error=''){
  const previous=item.status;Object.assign(item,{status,ended_at:time,error});
  if(status==='failed'&&previous!=='failed'){
    const old=state.failures.find(x=>x.key===item.key);
    state.failures=state.failures.filter(x=>x.key!==item.key);
    state.failures.push({key:item.key,label:item.label,subject:item.subject,count:(old?.count||0)+1,at:time,error,critical:item.critical});
    state.failures=state.failures.slice(-8);
  }else if(status==='failed'){
    const failure=state.failures.find(x=>x.key===item.key);if(failure&&error)failure.error=error;
  }else if(status==='complete'&&previous==='running')state.failures=state.failures.filter(x=>x.key!==item.key);
}

export function applyProduction(previous,event){
  const begin=event.type==='user/message'&&operationOf(event.data);
  if(begin)return {...initialProduction(),operation:{...begin,started_at:event.time,turn:event.data.turn||null},running:true,status:'running',last_event_at:event.time,model_wait_at:event.time};
  if(!previous.operation)return previous;
  if(!['turn/start','turn/end','step/start','tool/call','tool/result','job/registered','job/settled','tool/ptc-dispatch-start','tool/ptc-dispatch'].includes(event.type))return previous;
  const state=structuredClone(previous),data=event.data,time=event.time;state.last_event_at=time;
  if(event.type==='turn/start'){state.running=true;state.status='running';state.operation.turn=data.turn;state.model_wait_at=time;}
  if(event.type==='step/start')state.model_wait_at=time;
  if(event.type==='tool/call'||event.type==='tool/ptc-dispatch-start'){
    if(state.model_wait_at!==null){
      state.model_wait_ms+=Math.max(0,time-state.model_wait_at);
      state.items.push({id:'model-'+event.seq,name:'model',kind:'model',label:'等待模型输出下一步操作',subject:'',key:'model',critical:false,started_at:state.model_wait_at,ended_at:time,status:'complete',error:'',job_id:null});
    }
    const id=data.callId||data.subCallId,desc=describeCall(data.name,parse(data.arguments));
    if(!state.items.some(x=>x.id===id))state.items.push({...desc,id,started_at:time,ended_at:null,status:'running',error:'',job_id:null});
    state.model_wait_at=null;
  }
  if(event.type==='job/registered'){
    const item=state.items.find(x=>x.id===data.toolCall?.callId);if(item)item.job_id=data.jobId;
  }
  if(event.type==='job/settled'){
    const item=state.items.find(x=>x.job_id===data.jobId||x.id===data.toolCall?.callId);
    if(item){const code=exitCode(data.detail),failed=code!==null?code!==0:data.status==='failed';settle(state,item,failed?'failed':data.status==='cancelled'?'stopped':'complete',data.finishedAt||time,failed?compact(data.detail):'');}
  }
  if(event.type==='tool/result'||event.type==='tool/ptc-dispatch'){
    const message=data.message||data,id=message.toolCallId||data.subCallId,item=state.items.find(x=>x.id===id);
    if(item){
      const text=textOf(message.content),code=['bash','task_read','job_output'].includes(item.name)?exitCode(text):null;
      const result=message.isError||data.error||code!==null&&code!==0||parse(text)?.ok===false;
      // A background shell's immediate return is not the completion of its work.
      if(item.status==='running'&&item.job_id&&!result){}
      else settle(state,item,result?'failed':'complete',time,result?compact(data.error?.message||text):'');
      if(item.kind==='wait'&&code!==null){const original=state.items.find(x=>x.job_id===item.subject);if(original)settle(state,original,code?'failed':'complete',original.ended_at||time,code?compact(text):'');}
      const output=parse(text);if(item.name==='kgxc_course_export'&&!result&&output.job?.id)state.last_export={job_id:output.job.id,at:item.started_at};
    }
    state.model_wait_at=time;
  }
  if(event.type==='turn/end'){
    if(state.model_wait_at!==null)state.model_wait_ms+=Math.max(0,time-state.model_wait_at);
    state.running=false;state.status=data.reason?.kind==='aborted'?'stopped':data.reason?.kind==='error'?'failed':'complete';state.model_wait_at=null;
    for(const item of state.items)if(item.status==='running'&&!item.job_id)settle(state,item,'stopped',time,'此步骤没有收到完成结果，需核对后继续。');
  }
  state.items=trim(state.items);return state;
}

export function productionSnapshot(state,{course_path,running,now=Date.now()}={}){
  if(!state?.operation||state.operation.course_path!==course_path)return {available:false};
  const current=state.items.filter(x=>x.status==='running').at(-1),failure=state.failures.filter(x=>x.critical).at(-1);
  const waiting=!!running&&!current&&state.model_wait_at!==null;
  return {available:true,stage:state.operation.stage,status:running?'running':state.status,started_at:state.operation.started_at,
    updated_at:state.last_event_at,now,current:current||null,waiting_since:waiting?state.model_wait_at:null,model_wait_ms:state.model_wait_ms+(waiting?Math.max(0,now-state.model_wait_at):0),
    issue:failure||null,last_export:state.last_export,items:state.items.slice(-12)};
}

export function productionProjection(z){
  const item=z.object({id:z.string(),name:z.string(),kind:z.string(),label:z.string(),subject:z.string(),key:z.string(),critical:z.boolean(),
    started_at:z.number(),ended_at:z.number().nullable(),status:z.string(),error:z.string(),job_id:z.string().nullable()}).strict();
  const issue=z.object({key:z.string(),label:z.string(),subject:z.string(),count:z.number(),at:z.number(),error:z.string(),critical:z.boolean()}).strict();
  return {key:'kgxcProduction',stateVersion:3,
    stateSchema:z.object({operation:z.object({course_path:z.string(),stage:z.string(),started_at:z.number(),turn:z.number().nullable()}).strict().nullable(),
      running:z.boolean(),status:z.string(),last_event_at:z.number(),model_wait_at:z.number().nullable(),model_wait_ms:z.number(),last_export:z.object({job_id:z.string(),at:z.number()}).strict().nullable(),items:z.array(item).max(24),failures:z.array(issue).max(8)}).strict(),
    init:initialProduction,apply:applyProduction};
}
