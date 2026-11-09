// Fold committed execution events; supervision receives bounded metadata, not source bodies.
import {createHash} from 'node:crypto';
const stages={outline:'大纲',script:'逐字稿',storyboard:'分镜',pilot:'有声小样',final:'整课视频'};
const basename=value=>String(value||'').split(/[\\/]/).at(-1).slice(0,100);
const parse=value=>{try{return typeof value==='string'?JSON.parse(value):value||{};}catch{return {};}};
const textOf=content=>(content||[]).filter(b=>b.type==='text').map(b=>b.text||'').join('\n');
const exitCode=text=>{const match=String(text).match(/(?:\[exit code:\s*|^exit code:\s*|\[status:\s*[^,\]]+,\s*exit code:\s*)(-?\d+)\]?\s*$/im);return match?Number(match[1]):null;};
const compact=text=>{const content=String(text||'').trim(),value=parse(content.split('\n[status:')[0]);if(value.errors?.length)return String(value.errors[0]).slice(0,600);const lines=content.split('\n').filter(Boolean);return (lines.find(line=>/^(?:[\w.]+Error|[\w.]+Exception|StopIteration)(?::|$)/.test(line))||lines.slice(-3).join('\n')).slice(0,600);};
const metadata=text=>({sha256:createHash('sha256').update(text).digest('hex'),bytes:Buffer.byteLength(text,'utf8')});
const identifier=value=>typeof value==='string'&&/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(value);
const pathValue=value=>typeof value==='string'&&value.length<=1024&&!/[\x00-\x1f\x7f<>$`|;?*#]/.test(value)&&!/[A-Za-z][A-Za-z0-9+.-]*:\/\//.test(value)&&!value.split(/[\\/]/).includes('..')&&!/^(?:\.env(?:\..*)?|auth\.json|credentials?(?:\..*)?|id_rsa|id_ed25519|.*\.(?:key|pem))$/i.test(value.split(/[\\/]/).at(-1))&&/^(?:\/?[^\s/][^/]*\/|\.\.?\/|~\/|[A-Za-z]:[\\/]|[^\s/]+\.[A-Za-z0-9]{1,8}$)/.test(value)?value:undefined;
const sha256=value=>typeof value==='string'&&/^[a-fA-F0-9]{64}$/.test(value)?value:undefined;
const finiteInteger=value=>Number.isSafeInteger(value)&&value>=0&&value<=1000000000;
const errorClass=value=>String(value||'').match(/(?:^|\n)([A-Za-z][A-Za-z0-9_.]{0,70}(?:Error|Exception)|StopIteration)(?::|\s|$)/)?.[1]||'tool_execution_failure';
function argumentValue(value,flag){
  if(/token|password|secret|credential|api[-_]?key|auth|cookie|prompt|instruction|text|code|data/i.test(flag||''))return {kind:'opaque',...metadata(value)};
  if(sha256(value)&&/(?:^|[-_])sha(?:256)?$/.test(flag||''))return {kind:'sha256',value};
  if(/^-?\d+(?:\.\d+)?$/.test(value)&&value.length<=20&&Number.isSafeInteger(Number(value))&&Math.abs(Number(value))<=1000000000)return {kind:'number',value:Number(value)};
  if(pathValue(value))return {kind:'path',value};
  if(['script','storyboard','pilot','final','outline','readback','check','verify','validate','true','false','json','metadata','dry-run','apply'].includes(value))return {kind:'enum',value};
  return {kind:'opaque',...metadata(value)};
}
function commandEvidence(command){
  const opaque={type:'opaque',...metadata(command)};
  if(command.length>8192||/[\r\n\\;&|<>$`#?*\[\]{}()!]/.test(command))return opaque;
  const words=[],token=/'([^']*)'|"([^"]*)"|([^\s'"]+)/y;let cursor=0;
  while(cursor<command.length){while(/\s/.test(command[cursor]||'')&&cursor<command.length)cursor++;if(cursor===command.length)break;token.lastIndex=cursor;const match=token.exec(command);if(!match||token.lastIndex<command.length&&!/\s/.test(command[token.lastIndex]))return opaque;words.push(match[1]??match[2]??match[3]);cursor=token.lastIndex;if(words.length>32)return opaque;}
  const interpreter=words.shift();if(!/^(?:python(?:\d+(?:\.\d+)*)?|node(?:js)?)$/.test(basename(interpreter))||interpreter.includes('/')&&!pathValue(interpreter))return opaque;
  const flags=[];while(['-B','-u','-s','-S','-E','-I','--no-warnings','--enable-source-maps'].includes(words[0]))flags.push(words.shift());
  const script=words.shift();if(!pathValue(script)||!(/\.py$/.test(script)&&/^python/.test(basename(interpreter))||/\.(?:[cm]?js)$/.test(script)&&/^node/.test(basename(interpreter))))return opaque;
  const argv=flags.map(value=>({kind:'flag',value}));let flag;
  for(const word of words){const option=word.match(/^(--[a-z][a-z0-9-]{0,62})(?:=(.*))?$/);if(option){flag=option[1];argv.push({kind:'flag',value:flag});if(option[2]!==undefined){argv.push(argumentValue(option[2],flag));flag=undefined;}}else{argv.push(argumentValue(word,flag));flag=undefined;}}
  if(argv.length>32)return opaque;
  return {type:'simple_script',...metadata(command),interpreter,script_path:script,argv};
}
function mutationEvidence(operation,args){
  const claimed=[];let complete=true;
  for(const key of ['file_path','path'])if(Object.hasOwn(args,key)){if(typeof args[key]==='string')claimed.push(args[key]);else complete=false;}
  if(operation==='apply_patch'){
    const patches=['patch','input'].filter(key=>Object.hasOwn(args,key));if(patches.length>1)complete=false;
    for(const key of patches){
      if(typeof args[key]!=='string'){complete=false;continue;}
      const lines=args[key].split(/\r?\n/);if(lines[0]!=='*** Begin Patch'||lines.at(-1)!=='*** End Patch'&&!(lines.at(-1)===''&&lines.at(-2)==='*** End Patch')){complete=false;continue;}
      for(const line of lines){
        const header=line.match(/^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/);
        if(header)claimed.push(header[1]);else if(line.startsWith('*** ')&&!['*** Begin Patch','*** End Patch','*** End of File'].includes(line))complete=false;
      }
    }
  }
  const targets=[...new Set(claimed)],valid=targets.filter(path=>pathValue(path));
  // These are literal requested targets, not resolved paths or proof of a write.
  return {basis:'committed_tool_arguments',scope:'requested_targets',operation,fs_verified:false,paths:valid.slice(0,32),paths_complete:complete&&targets.length>0&&targets.length===valid.length&&targets.length<=32};
}
function callEvidence(name,args,raw){
  const evidence={arguments:metadata(typeof raw==='string'?raw:JSON.stringify(raw??{}))};
  if(['read','read_file'].includes(name)){
    const path=pathValue(args.file_path||args.path),range={};for(const key of ['offset','limit','start_line','end_line','line_start','line_end'])if(finiteInteger(args[key]))range[key]=args[key];
    evidence.read={basis:'committed_tool_arguments',...path?{path}:{},range};
  }
  if(['write','edit','apply_patch'].includes(name))evidence.mutation=mutationEvidence(name,args);
  if(name==='bash')evidence.command=commandEvidence(String(args.command||''));
  return evidence;
}
function resultEvidence(text){
  const result={basis:'committed_tool_result',coverage:'reported_fields_only',...metadata(text),format:'opaque'};
  let value;try{value=JSON.parse(text.replace(/\n\[(?:status:[^\]\n]*|exit code:\s*-?\d+)\]\s*$/,'').trim());}catch{return {result};}
  const type=child=>child===null?'null':Array.isArray(child)?'array':typeof child;
  result.format='json';result.structure={type:type(value)};
  if(Array.isArray(value))result.structure.length=value.length;
  else if(value&&typeof value==='object'){
    const fields=Object.keys(value).filter(identifier);result.structure.fields=fields.slice(0,32).map(name=>({name,type:type(value[name]),...Array.isArray(value[name])?{length:value[name].length}:{}}));result.structure.field_count=fields.length;
    const reported={};
    for(const key of ['ok','completed','all_selected_A','only_process_receipt_written','new_user_confirmation','review_not_triggered','independent_review_passed','baseline_matches'])if(typeof value[key]==='boolean')reported[key]=value[key];
    for(const key of ['workflow_revision','segments','options','backed_up_files','revision'])if(finiteInteger(value[key]))reported[key]=value[key];
    for(const key of fields.filter(key=>key.endsWith('_sha256')).slice(0,32))if(sha256(value[key]))reported[key]=value[key];
    for(const key of ['receipt','receipt_path','output'])if(pathValue(value[key]))reported[key]=value[key];
    if(value.protected_files&&typeof value.protected_files==='object'&&!Array.isArray(value.protected_files))reported.protected_files=Object.fromEntries(Object.entries(value.protected_files).filter(([path,digest])=>pathValue(path)&&sha256(digest)).slice(0,32));
    if(value.checks&&typeof value.checks==='object'&&!Array.isArray(value.checks))reported.checks=Object.fromEntries(Object.entries(value.checks).filter(([key,checked])=>identifier(key)&&typeof checked==='boolean').slice(0,32));
    result.reported=reported;
  }
  return {result};
}

export function initialProduction(){return {operation:null,running:false,status:'idle',last_event_at:0,model_wait_at:null,model_wait_ms:0,last_export:null,items:[],failures:[]};}

export function operationOf(data){
  if(data.source?.kind==='kgxc-producer-work'){
    const line=textOf(data.content).split('\n')[0];if(!line.startsWith('KGXC_OPERATION '))return null;
    const marker=parse(line.slice(15));
    if(!marker||typeof marker!=='object'||Array.isArray(marker)||Object.keys(data.source).length!==1||typeof data.id!=='string'||!data.id||data.id.length>200||Object.keys(marker).sort().join(',')!=='course_path,operation_id,request_id,stage')return null;
    if(!pathValue(marker.course_path)||!marker.course_path.startsWith('/')||!Object.hasOwn(stages,marker.stage)||typeof marker.request_id!=='string'||!marker.request_id||marker.request_id.length>200||/[\x00-\x1f\x7f]/.test(marker.request_id))return null;
    const expected='produce-'+createHash('sha256').update(marker.course_path+'\0'+marker.request_id).digest('hex');
    return marker.operation_id===expected?marker:null;
  }
  if(data.source?.kind!=='kgxc-course-context')return null;
  const text=textOf(data.content),line=text.split('\n').find(line=>line.startsWith('KGXC_OPERATION '));
  const marker=line?parse(line.slice(15)):null;
  if(marker?.course_path&&stages[marker.stage])return {course_path:marker.course_path,stage:marker.stage};
  // Recognize stage handoffs written by 0.5 before the explicit marker existed.
  const old=text.match(/课程工程位于当前会话工作区内：("(?:[^"\\]|\\.)*")。目标阶段=(outline|script|storyboard|pilot|final)/);
  return old?{course_path:parse(old[1]),stage:old[2]}:null;
}

// Facts identify requested reads and simple script argv, plus tool-reported
// typed assertions. They are not independent filesystem verification.
export function productionEventFact(event){
  const data=event.data||{},base={seq:event.seq,time:event.time,type:event.type};
  if(event.type==='request/header'){
    const header=data.header||{},route=header.config||header;
    return {...base,route:{provider:route.provider,model:route.model},tools:(header.tools||[]).map(tool=>tool.name)};
  }
  if(event.type==='tool/call'||event.type==='tool/ptc-dispatch-start'){
    const args=parse(data.arguments),call=describeCall(data.name,args);
    return {...base,call_id:data.callId||data.subCallId,name:call.name,kind:call.kind,label:call.label,evidence:callEvidence(data.name,args,data.arguments)};
  }
  if(event.type==='tool/result'||event.type==='tool/ptc-dispatch'){
    const message=data.message||data,text=textOf(message.content),output=parse(text),code=exitCode(text),evidence=resultEvidence(text);
    const failed=!!(message.isError||data.error||code!==null&&code!==0||output.ok===false||evidence.result.reported?.ok===false);
    return {...base,call_id:message.toolCallId||data.subCallId,failed,exit_code:code,...failed?{error:errorClass(data.error?.message||text)}:{},...output.job?.id?{job_id:output.job.id,job_status:output.job.status}:{},evidence};
  }
  if(event.type==='job/registered')return {...base,job_id:data.jobId,call_id:data.toolCall?.callId};
  if(event.type==='job/settled'){
    const code=exitCode(data.detail),failed=code!==null?code!==0:data.status==='failed';
    return {...base,job_id:data.jobId,status:data.status,failed,exit_code:code,...failed?{error:errorClass(data.detail)}:{}};
  }
  if(event.type==='turn/start'||event.type==='step/start')return {...base,turn:data.turn,step:data.step};
  if(event.type==='turn/end')return {...base,turn:data.turn,status:data.reason?.kind,failed:data.reason?.kind==='error',...data.reason?.error?{error:errorClass(data.reason.error.message)}:{}};
  return null;
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
  else if(name==='kgxc_course_source_coverage'){kind=args.action==='save'?'save':'read';label=args.action==='save'?'保存原件与逐字稿对照':'读取原件与逐字稿对照';subject='';}
  else if(name==='kgxc_course_update'){kind='save';label='保存'+(stages[args.stage]||'课程成果');subject='';}
  else if(name==='kgxc_course_export'){kind='render';label='提交实际视频合成';subject='';}
  else if(/^kgxc_course_/.test(name)){kind='check';label='核对当前课程状态';subject='';}
  return {name,kind,label:String(label).slice(0,100),subject,key:kind+':'+subject,critical:['build','voice','alignment','render','save','execute'].includes(kind)};
}

function trim(items){const active=items.filter(x=>x.status==='running').slice(-8),rest=items.filter(x=>x.status!=='running').slice(-16);return [...active,...rest].sort((a,b)=>a.started_at-b.started_at);}
function progressReceipt(text){
  const outer=parse(String(text).replace(/\n\[(?:status:[^\]\n]*|exit code:\s*-?\d+)\]\s*$/,'').trim());
  const value=outer.result&&typeof outer.result==='object'&&!Array.isArray(outer.result)?outer.result:outer;
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  const result={};for(const key of ['ok','completed'])if(typeof value[key]==='boolean')result[key]=value[key];
  if(outer.ok===false)result.ok=false;
  if(finiteInteger(value.workflow_revision))result.workflow_revision=value.workflow_revision;
  for(const key of ['script_sha256','expected_script_sha256','candidate_sha256'])if(sha256(value[key]))result[key]=value[key];
  return Object.keys(result).length?result:null;
}
function supersede(state,item,time,basis,failure){
  if(failure.superseded_by)return;
  const receipt=item.receipt||{};failure.superseded_by={id:item.id,at:time,basis,
    ...finiteInteger(receipt.workflow_revision)?{workflow_revision:receipt.workflow_revision}:{},
    ...receipt.script_sha256?{script_sha256:receipt.script_sha256}:{},...receipt.candidate_sha256?{candidate_sha256:receipt.candidate_sha256}:{}};
}
function supersedeScriptReceipt(state,item,time){
  const success=item.receipt;
  if(state.operation.stage!=='script'||success?.ok!==true||success.completed!==true||!finiteInteger(success.workflow_revision)||!success.script_sha256||!success.candidate_sha256)return;
  for(const failure of state.failures){
    const failed=failure.receipt;
    if(failure.course_path===state.operation.course_path&&failure.id!==item.id&&failed?.ok===false&&finiteInteger(failed.workflow_revision)
      &&success.workflow_revision>failed.workflow_revision&&success.candidate_sha256===failed.candidate_sha256&&success.script_sha256===failed.expected_script_sha256)
      supersede(state,item,time,'matching-candidate-source-revision',failure);
  }
}
function settle(state,item,status,time,error=''){
  const previous=item.status;Object.assign(item,{status,ended_at:time,error});
  if(status==='failed'&&previous!=='failed'){
    const old=state.failures.filter(x=>x.key===item.key&&x.operation_key===state.operation.key).at(-1);
    state.failures.push({id:item.id,key:item.key,label:item.label,subject:item.subject,count:(old?.count||0)+1,at:time,error,critical:item.critical,
      course_path:state.operation.course_path,operation_key:state.operation.key,operation_id:state.operation.operation_id,stage:state.operation.stage,
      receipt:item.receipt,errors:[{at:time,error}],superseded_by:null});
  }else if(status==='failed'){
    const failure=state.failures.find(x=>x.id===item.id);if(failure){failure.receipt=item.receipt||failure.receipt;if(error&&failure.error!==error){failure.errors.push({at:time,error});failure.error=error;}}
  }else if(status==='complete'&&previous==='running')for(const failure of state.failures)
    if(failure.operation_key===state.operation.key&&failure.key===item.key&&failure.id!==item.id&&item.receipt?.completed!==false
      &&!failure.receipt?.candidate_sha256&&!failure.receipt?.expected_script_sha256)supersede(state,item,time,'same-step-completed',failure);
}

export function applyProduction(previous,event){
  const begin=event.type==='user/message'&&operationOf(event.data);
  if(begin){
    const key=begin.operation_id||'legacy:'+event.seq;
    if(previous.operation?.key===key)return previous;
    return {...initialProduction(),failures:structuredClone(previous.failures||[]),operation:{...begin,key,operation_id:begin.operation_id||null,request_id:begin.request_id||null,
      started_at:event.time,turn:event.data.turn??null},running:true,status:'running',last_event_at:event.time,model_wait_at:event.time};
  }
  if(!previous.operation)return previous;
  if(!['turn/start','turn/end','step/start','tool/call','tool/result','job/registered','job/settled','tool/ptc-dispatch-start','tool/ptc-dispatch'].includes(event.type))return previous;
  const state=structuredClone(previous),data=event.data,time=event.time;state.last_event_at=time;
  if(event.type==='turn/start'){state.running=true;state.status='running';state.operation.turn=data.turn;state.model_wait_at=time;}
  if(event.type==='step/start')state.model_wait_at=time;
  if(event.type==='tool/call'||event.type==='tool/ptc-dispatch-start'){
    if(state.model_wait_at!==null){
      state.model_wait_ms+=Math.max(0,time-state.model_wait_at);
      state.items.push({id:'model-'+event.seq,name:'model',kind:'model',label:'等待模型输出下一步操作',subject:'',key:'model',critical:false,started_at:state.model_wait_at,ended_at:time,status:'complete',error:'',job_id:null,receipt:null});
    }
    const id=data.callId||data.subCallId,desc=describeCall(data.name,parse(data.arguments));
    if(!state.items.some(x=>x.id===id))state.items.push({...desc,id,started_at:time,ended_at:null,status:'running',error:'',job_id:null,receipt:null});
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
      const receipt=progressReceipt(text);if(receipt)item.receipt=receipt;
      const result=message.isError||data.error||code!==null&&code!==0||receipt?.ok===false;
      // A background shell's immediate return is not the completion of its work.
      if(item.status==='running'&&item.job_id&&!result){}
      else settle(state,item,result?'failed':'complete',time,result?compact(data.error?.message||text):'');
      if(item.kind==='wait'&&code!==null){const original=state.items.find(x=>x.job_id===item.subject);if(original)settle(state,original,code?'failed':'complete',original.ended_at||time,code?compact(text):'');}
      const output=parse(text);if(item.name==='kgxc_course_export'&&!result&&output.job?.id)state.last_export={job_id:output.job.id,at:item.started_at};
      if(!result&&item.status==='complete')supersedeScriptReceipt(state,item,time);
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
  const current=state.items.filter(x=>x.status==='running').at(-1),failure=state.failures.filter(x=>x.critical&&x.operation_key===state.operation.key&&!x.superseded_by).at(-1);
  const waiting=!!running&&!current&&state.model_wait_at!==null;
  return {available:true,stage:state.operation.stage,status:running?'running':state.status,started_at:state.operation.started_at,
    updated_at:state.last_event_at,now,current:current||null,waiting_since:waiting?state.model_wait_at:null,model_wait_ms:state.model_wait_ms+(waiting?Math.max(0,now-state.model_wait_at):0),
    operation_id:state.operation.operation_id,request_id:state.operation.request_id,
    issue:failure||null,history:state.failures.filter(x=>x.course_path===course_path&&(x.operation_key!==state.operation.key||x.superseded_by)),last_export:state.last_export,items:state.items.slice(-12)};
}

export function productionProjection(z){
  const receipt=z.object({ok:z.boolean().optional(),completed:z.boolean().optional(),workflow_revision:z.number().optional(),script_sha256:z.string().optional(),expected_script_sha256:z.string().optional(),candidate_sha256:z.string().optional()}).strict().nullable();
  const replacement=z.object({id:z.string(),at:z.number(),basis:z.string(),workflow_revision:z.number().optional(),script_sha256:z.string().optional(),candidate_sha256:z.string().optional()}).strict().nullable();
  const item=z.object({id:z.string(),name:z.string(),kind:z.string(),label:z.string(),subject:z.string(),key:z.string(),critical:z.boolean(),
    started_at:z.number(),ended_at:z.number().nullable(),status:z.string(),error:z.string(),job_id:z.string().nullable(),receipt}).strict();
  const issue=z.object({id:z.string(),key:z.string(),label:z.string(),subject:z.string(),count:z.number(),at:z.number(),error:z.string(),critical:z.boolean(),
    course_path:z.string(),operation_key:z.string(),operation_id:z.string().nullable(),stage:z.string(),receipt,errors:z.array(z.object({at:z.number(),error:z.string()}).strict()),superseded_by:replacement}).strict();
  return {key:'kgxcProduction',stateVersion:4,
    stateSchema:z.object({operation:z.object({course_path:z.string(),stage:z.string(),key:z.string(),operation_id:z.string().nullable(),request_id:z.string().nullable(),started_at:z.number(),turn:z.number().nullable()}).strict().nullable(),
      running:z.boolean(),status:z.string(),last_event_at:z.number(),model_wait_at:z.number().nullable(),model_wait_ms:z.number(),last_export:z.object({job_id:z.string(),at:z.number()}).strict().nullable(),items:z.array(item).max(24),failures:z.array(issue)}).strict(),
    init:initialProduction,apply:applyProduction};
}
