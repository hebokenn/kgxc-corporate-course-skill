import {createHash,randomUUID} from 'node:crypto';
import {requireRoute} from './isolated-review-agent.mjs';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const hash=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const automatic=new Set(['runtime-context','time-context','agent-instructions','working-directory','model-selection','tool-registry','kgxc-course-context']);
const meta=message=>({id:message.id,role:message.role,source:message.source?.kind,sha256:hash(message.content)});
const escapeCatalog=text=>text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function nativeCatalogText(entries,update,incomplete){
  const warning='Some skills could not be checked. Only confirmed skills are listed; a lower-priority definition of the same name may be selected when a preferred source is unavailable. Discovery will be retried on the next request.';
  const direct="A user may also invoke a skill directly; its <skill_content> block then appears in this conversation. Follow it, and do not call the `skill` tool again for that skill.",emptyDirect="A user may still invoke a skill directly; its <skill_content> block then appears in this conversation. Follow it, and do not call the `skill` tool for it.";
  const heading=update?(incomplete?'Skill discovery is incomplete. This catalog of currently available skills replaces every earlier available-skills list in this session:':'The available skill catalog changed. This complete catalog replaces every earlier available-skills list in this session:'):(entries.length?'A skill is a reusable set of task-specific instructions. The following skills are available in this session:':'No skills could be confirmed in this discovery attempt.');
  const instructions=update?(entries.length?["Use only names in this replacement catalog. If the user names a listed skill, or the task clearly matches its description, call the `skill` tool with the exact name before acting.",direct]:[incomplete?"No skills could be confirmed in this discovery attempt. Do not use names from earlier skill catalogs.":"No skills are currently available through the `skill` tool. Do not use names from earlier skill catalogs.",emptyDirect]):[entries.length?"If the user names a skill, or the task clearly matches a skill's description, call the `skill` tool with the exact skill name before taking task actions. Load all applicable skills, then follow their full instructions. This catalog contains summaries only; do not infer or follow a skill's instructions until it has been loaded.":"Wait for an updated catalog before calling the `skill` tool. Do not infer skill instructions from an empty catalog.",direct];
  return ['<system-reminder>',heading,'','<available_skills>',...entries.map(entry=>'- `'+entry.name+'`: '+escapeCatalog(entry.description)),'</available_skills>','',...incomplete?[warning,'']:[],...instructions,'</system-reminder>'].join('\n');
}
const boundSummary=text=>text.length<=120?text:text.slice(0,119)+'…';
const bytes=text=>Buffer.byteLength(text,'utf8');
const head=(text,limit)=>{let data=Buffer.from(text);if(data.length<=limit)return text;data=data.subarray(0,limit);for(;;){try{return new TextDecoder('utf-8',{fatal:true}).decode(data);}catch{data=data.subarray(0,-1);}}};
const gentleRepeat='You are repeating the exact same tool call with identical arguments. Carefully analyze the previous result before calling again: if the task is not complete, try a different approach or different arguments instead of repeating the call.';
const argumentsOf=value=>{try{return typeof value==='string'?JSON.parse(value):value;}catch{return value;}};
const wildcard=pattern=>new RegExp('^'+pattern.replace(/[|\\{}()[\]^$+?.]/g,'\\$&').replaceAll('*','.*')+'$');
// Mirror only the native notice framing, never treat its text as authority.
function jobNoticeTexts(job,read,expectedText){
  const prefix='background job '+job.id,label=job.label.trimStart(),newline=label.indexOf('\n'),detail=' ('+job.kind+': '+boundSummary(newline===-1?label:label.slice(0,newline)+'…')+') finished [status: '+job.status+((job.progress??job.detail)!==undefined?', '+(job.progress??job.detail):'')+']';
  const complete=prefix+detail+'. Read its output with job_output.',limit=job.outputLimitBytes??Infinity,texts=new Set();
  if(bytes(complete)<=limit)texts.add(complete);
  else{
    const omitted='\n[notice truncated]',action='\nDone; job_output.',fixed=prefix+omitted+action;
    if(bytes(fixed)<=limit)texts.add(prefix+head(detail,limit-bytes(fixed))+omitted+action);
    else if(bytes(prefix+action)<=limit)texts.add(prefix+action);
    else{const recovery='background job ended; use job_list for id.';texts.add(bytes(recovery)<=limit?recovery:head('job_list',limit));}
  }
  if(texts.has(expectedText)||!expectedText.startsWith(prefix+detail+'. Output:\n')&&expectedText!==prefix+detail+'. No new output.')return texts;
  read=read();
  if(read&&!read.lossy&&!read.chunks.some(chunk=>chunk.gapBefore)){
    // A previous job_output may have consumed a prefix. All possible unread
    // chunk suffixes are checked against the registry's non-consuming output.
    for(let start=0;start<=read.chunks.length;start++){
      const visible=read.chunks.slice(start).filter(chunk=>chunk.channel!=='log'),out=visible.filter(chunk=>chunk.channel!=='stderr').map(chunk=>chunk.text).join(''),err=visible.filter(chunk=>chunk.channel==='stderr').map(chunk=>chunk.text).join('');
      const output=out+(err?(out&&!out.endsWith('\n')?'\n':'')+'[stderr]\n'+err:''),inline=prefix+detail+(output?'. Output:\n'+output.replace(/\n$/,''):'. No new output.');
      if(bytes(inline)<=limit)texts.add(inline);if(inline===expectedText)break;
    }
  }
  return texts;
}

// This scope changes only explicitly dispatched production requests. Native
// tools, executor, permission policy, durable history and prepared handles stay
// owned by the original producer and Runtime.
export function producerWorkSnapshot(producer,{message,operation_id,request_id,signal,onProjection,onSteering}){
  const selectedRoute=requireRoute(producer.model?.current?.()||producer.options);
  if(!producer?.ctx?.on||!producer.ctx.tools?.guard||!producer.session?.id||message?.source?.kind!=='kgxc-producer-work'||!operation_id||!request_id)throw Error('制作任务快照缺少真实身份、明确指令或操作绑定。');
  const expected=hash(message),sessionId=producer.session.id,disposers=[],requests=new WeakMap(),receipts=[],jobNotices=new Map(),catalogs=new Map(),repeatNotices=new Map(),pendingRepeats=new Set();let disposed=false,steered=false,steeringTask,derivedCatalog,currentDerived;
  const pending=[...(producer.inbox?.nextStep||[]),...(producer.inbox?.nextTurn||[])];
  const staleNotices=new Map();signal.throwIfAborted();
  const live=()=>{signal.throwIfAborted();if(disposed||steered)throw Error('当前制作快照已结束或收到新用户指令，停止旧任务。');};
  const repeatPolicy=()=>{
    const policies=[];for(const runtime of producer.ctx.registry?.values?.()||[])if(runtime.name==='repeat-tool-reminder')for(const fiber of runtime.fibers)if(fiber.state===2)policies.push(fiber.effectiveConfig);
    if(policies.length!==1)return null;const policy=policies[0];
    if(!policy?.thresholds?.length||policy.thresholds.some(count=>!Number.isInteger(count)||count<2)||!Array.isArray(policy.include)||!Array.isArray(policy.exclude)||!Number.isInteger(policy.argumentsPreviewChars)||policy.argumentsPreviewChars<1)return null;
    return {...policy,thresholds:[...policy.thresholds].sort((a,b)=>a-b)};
  };
  const repeatProof=(input,log,call,beforeSeq,policy)=>{
    if(!policy||input.role!=='user'||hash(input.source)!==hash({kind:'repeat-tool-reminder',form:'notice',summary:input.source?.summary})||input.content?.length!==1||input.content[0].type!=='text')return false;
    const tracked=name=>(!policy.include.length||policy.include.some(pattern=>wildcard(pattern).test(name)))&&!policy.exclude.some(pattern=>wildcard(pattern).test(name));
    if(!call||!tracked(call.data.name))return false;
    const single=entry=>log.filter(event=>event.type==='tool/call'&&event.data.turn===entry.data.turn&&event.data.step===entry.data.step).length===1;
    if(!single(call))return false;const args=argumentsOf(call.data.arguments),key=hash([call.data.name,args]);let count=1;
    for(const event of log.filter(event=>event.seq<beforeSeq).reverse()){
      if(event.type==='user/message'&&event.data.source?.kind==='user')break;
      if(event.type!=='tool/result'||event.data.message?.toolCallId===call.data.callId)continue;
      const prior=log.find(entry=>entry.type==='tool/call'&&entry.data.callId===event.data.message?.toolCallId&&entry.seq<event.seq);
      if(!prior)return false;if(!tracked(prior.data.name))continue;if(hash([prior.data.name,argumentsOf(prior.data.arguments)])!==key)break;if(!single(prior))return false;count++;
    }
    if(!policy.thresholds.includes(count)||input.source.summary!==call.data.name+' × '+count)return false;
    const canonicalArgs=JSON.stringify(canonical(args)),cap=policy.argumentsPreviewChars,preview=canonicalArgs.length<=cap?canonicalArgs:canonicalArgs.slice(0,cap)+'… (+'+(canonicalArgs.length-cap)+' more chars)';
    const text=count===policy.thresholds[0]?gentleRepeat:'Repeated tool call detected:\n- tool: '+call.data.name+'\n- consecutive_calls: '+count+'\n- arguments: '+preview+'\nThe repeated calls are not making progress. Do not call this tool with these exact arguments again. Inspect the latest result and choose a different action, different arguments, or finish the task if enough evidence has been gathered.';
    if(input.content[0].text!==text)return false;
    return {message_id:input.id,message_sha256:hash(input),owner:sessionId,tool_call_id:call.data.callId,call_seq:call.seq,turn:call.data.turn,step:call.data.step,tool_name:call.data.name,consecutive_calls:count,arguments_sha256:hash(args),policy_sha256:hash(policy)};
  };
  const verifyRepeat=(input,historical=false)=>{
    if(disposed||steered||signal.aborted||input.source?.kind!=='repeat-tool-reminder')return false;
    const log=[...producer.session.log],insertion=log.findLast(event=>event.type==='agent/inbox/spliced'&&event.data.inserted?.length===1&&event.data.inserted[0].id===input.id),result=log.find(event=>event.seq===insertion?.seq-1),policy=repeatPolicy();
    if(!insertion||hash(insertion.data.inserted[0])!==hash(input)||result?.type!=='tool/result'||log.some(event=>event.type==='user/message'&&event.data.id===input.id))return false;
    const call=log.find(event=>event.type==='tool/call'&&event.data.callId===result.data.message?.toolCallId&&event.seq<result.seq&&event.data.turn===result.data.turn&&event.data.step===result.data.step),proof=repeatProof(input,log,call,result.seq,policy);
    if(!proof)return false;
    if(historical){if(producer.status!=='idle'||!log.some(event=>event.type==='turn/end'&&event.data.turn===proof.turn&&event.seq>result.seq))return false;}
    else {const captured=repeatNotices.get(input.id);if(!captured||captured.origin!=='native-post-execute'||captured.message_sha256!==proof.message_sha256||captured.tool_call_id!==proof.tool_call_id||captured.policy_sha256!==proof.policy_sha256||captured.inbox_seq&&captured.inbox_seq!==insertion.seq)return false;}
    return {...proof,result_seq:result.seq,inbox_seq:insertion.seq,origin:historical?'native-log-pending':'native-post-execute'};
  };
  const verifyJobNotice=(input,historical=false)=>{
    if(disposed||steered||signal.aborted||input.source?.kind!=='tool-jobs'||input.source.form!=='notice'||input.content?.length!==1||input.content[0].type!=='text')return false;
    try{
      const log=[...producer.session.log],owned=log.find(event=>event.type==='user/message'&&event.data.id===message.id);
      const insertion=log.findLast(event=>event.type==='agent/inbox/spliced'&&event.data.inserted?.length===1&&event.data.inserted[0].id===input.id);
      const settled=log.find(event=>event.seq===insertion?.seq-1);
      // Native jobs record settlement immediately before synchronous notice
      // delivery. A notice copied into the inbox later has no such provenance.
      if(!insertion||settled?.type!=='job/settled'||hash(insertion.data.inserted[0])!==hash(input)||!historical&&(!owned||settled.seq<=owned.seq))return false;
      const data=settled.data,registered=log.find(event=>event.type==='job/registered'&&event.data.jobId===data.jobId&&event.seq>(historical?-1:owned.seq)&&event.seq<settled.seq);
      if(!registered||data.owner!==sessionId||registered.data.owner!==sessionId||!data.toolCall?.callId||hash(data.toolCall)!==hash(registered.data.toolCall))return false;
      const start=log.findLast(event=>event.type==='turn/start'&&event.seq<(historical?registered.seq:owned.seq)),turn=start?.data.turn;
      if(!start||historical&&(producer.status!=='idle'||!log.some(event=>event.type==='turn/end'&&event.data.turn===turn&&event.seq>registered.seq)))return false;
      const call=id=>log.find(event=>event.type==='tool/call'&&event.data.callId===id&&event.seq>(historical?start.seq:owned.seq)&&event.seq<registered.seq&&event.data.turn===turn);
      if(!call(data.toolCall.callId)||!call(data.toolCall.rootCallId??data.toolCall.callId)||[...jobNotices.values()].some(notice=>notice.job_id===data.jobId))return false;
      const jobs=producer.ctx.get?.('jobs')||producer.ctx.jobs;if(!jobs?.get||!jobs?.readAt)return false;
      const job=jobs.get(data.jobId,sessionId);
      if(job.owner!==sessionId||job.status!==data.status||!['completed','failed','killed'].includes(job.status)||job.kind!==registered.data.kind||job.label!==registered.data.label||job.startedAt!==registered.data.startedAt||job.finishedAt!==data.finishedAt)return false;
      const status='[status: '+job.status+((job.progress??job.detail)!==undefined?', '+(job.progress??job.detail):'')+']';
      if(input.source.summary!==boundSummary(job.kind+' '+job.label+' '+status)||!jobNoticeTexts(job,()=>jobs.readAt(job.id,0,sessionId),input.content[0].text).has(input.content[0].text))return false;
      return {message_id:input.id,message_sha256:hash(input),job_id:job.id,owner:job.owner,tool_call_id:data.toolCall.callId,root_call_id:data.toolCall.rootCallId??data.toolCall.callId,registered_seq:registered.seq,settled_seq:settled.seq,inbox_seq:insertion.seq};
    }catch{return false;}
  };
  for(const input of pending)if(input.role==='user'&&!automatic.has(input.source?.kind)){
    const repeat=verifyRepeat(input,true);if(repeat){repeatNotices.set(input.id,repeat);pendingRepeats.add(input.id);continue;}
    const proof=verifyJobNotice(input,true);if(!proof)throw Error('制作前仍有未处理用户或无法证明来源的任务通知；保留 inbox，不启动旧任务。');staleNotices.set(input.id,proof);
  }
  const abort=()=>producer.cancel({kind:'user',message:'当前明确制作任务已取消。'},{keepInbox:true});signal.addEventListener('abort',abort,{once:true});disposers.push(()=>signal.removeEventListener('abort',abort));
  const approveJobNotice=input=>{const proof=verifyJobNotice(input);if(!proof)return false;jobNotices.set(input.id,proof);return true;};
  const approvedJobNotice=input=>jobNotices.get(input.id)?.message_sha256===hash(input);
  const approveRepeat=input=>{const proof=verifyRepeat(input);if(!proof)return false;repeatNotices.set(input.id,proof);return true;};
  const approvedRepeat=input=>repeatNotices.get(input.id)?.message_sha256===hash(input);
  const approvedCatalog=input=>catalogs.get(input.id)?.message_sha256===hash(input);
  const catalogView=async()=>{
    const visible=producer.ctx.tools?.get?.('skill',producer),skills=producer.ctx.get?.('skills')||producer.ctx.skills,working=producer.ctx.get?.('workingDirectory')||producer.ctx.workingDirectory;
    if(!visible||!skills?.snapshot||!working?.ensure)throw Error('无法核对当前制作 Agent 的原生技能目录绑定。');
    const limits=new Set();
    for(const runtime of producer.ctx.registry?.values?.()||[])if(runtime.name==='tool-skill')for(const fiber of runtime.fibers)if(fiber.state===2){const limit=fiber.effectiveConfig?.catalogDescriptionMaxLength;if(Number.isSafeInteger(limit)&&limit>=3)limits.add(limit);}
    if(limits.size!==1)throw Error('原生技能目录策略未激活或存在歧义，停止制作。');
    const limit=[...limits][0],cwd=await working.ensure(producer,signal),snapshot=await skills.snapshot({cwd,signal,scope:producer});live();
    const entries=snapshot.skills.filter(skill=>skill.invocation?.modelInvocable===true).map(skill=>{const description=skill.description.replaceAll(/\s+/g,' ').trim();return {name:skill.name,description:description.length<=limit?description:description.slice(0,limit-3)+'...'};});
    return {entries,incomplete:!snapshot.complete,limit,source_sha256:hash({skills:snapshot.skills,complete:snapshot.complete,cwd_sha256:hash(cwd),catalog_description_max_length:limit})};
  };
  const steer=input=>{
    if(steered||disposed)return;steered=true;
    // Preserve queued human input; cancellation must not discard it.
    producer.cancel({kind:'user',message:'收到新的用户指令，停止旧制作快照。'},{keepInbox:true});
    steeringTask=Promise.resolve(onSteering?.(input)).catch(()=>{});
  };
  disposers.push(producer.ctx.on('agent/inbox/inserted',({agent,message:input})=>{
    if(agent===producer&&input?.id!==message.id&&input?.role==='user'&&!automatic.has(input.source?.kind)&&!approveJobNotice(input)&&!approveRepeat(input))steer(input);
  }));
  disposers.push(producer.ctx.on('tools/post-execute',async(exec,_result,next)=>{
    if(exec.agent!==producer)return next();live();const policy=repeatPolicy(),log=[...producer.session.log],call=log.find(event=>event.type==='tool/call'&&event.data.callId===exec.callId),owned=log.find(event=>event.type==='user/message'&&event.data.id===message.id);
    const decision=await next();live();const candidates=(decision.additionalContexts||[]).filter(input=>input.source?.kind==='repeat-tool-reminder');if(!candidates.length)return decision;
    if(candidates.length!==1||!owned||!call||call.seq<=owned.seq||hash(argumentsOf(call.data.arguments))!==hash(exec.arguments)||call.data.name!==exec.name)throw Error('重复工具提醒缺少本制作任务的真实执行绑定。');
    const input=candidates[0],proof=repeatProof(input,log,call,Infinity,policy);
    if(!proof||log.some(event=>event.type==='user/message'&&event.data.id===input.id||event.type==='agent/inbox/spliced'&&event.data.inserted?.some(item=>item.id===input.id)))throw Error('重复工具提醒不是当前原生策略与执行链生成的新上下文。');
    repeatNotices.set(input.id,{...proof,origin:'native-post-execute'});return decision;
  },{prepend:true}));
  disposers.push(producer.ctx.tools.guard(()=>{try{live();}catch(error){return error.message;}}));
  disposers.push(producer.ctx.on('agent/pre-step',async(payload,next)=>{
    if(payload.agent!==producer)return next();live();requireRoute(payload.modelSelection,selectedRoute);
    // Inspect incoming identities before tool-skill can replace an existing
    // catalog-shaped message; a source label never authorizes claimed input.
    for(const input of payload.messages)if(input.id!==message.id&&!automatic.has(input.source?.kind)&&!approvedJobNotice(input)&&!approvedRepeat(input)&&staleNotices.get(input.id)?.message_sha256!==hash(input)){steer(input);live();}
    currentDerived=undefined;const decision=await next();live();if(decision.kind==='reject')return decision;
    const candidates=decision.messages.filter(input=>input.source?.kind==='skill-catalog');
    if(!candidates.length){
      if(!producer.ctx.tools.get('skill',producer))return decision;
      const view=await catalogView(),history=producer.session.deriveMessages(),position=history.findIndex(input=>input.id===message.id);
      // Native tool-skill deliberately omits an unchanged catalog. A prior
      // catalog is not input authority: derive the current view from the live
      // registry/policy, and keep this new context only in the outbound projection.
      if(position!==-1&&history.slice(position).some(input=>approvedCatalog(input)&&catalogs.get(input.id).entries_sha256===hash(view.entries)&&catalogs.get(input.id).incomplete===view.incomplete&&catalogs.get(input.id).catalog_description_max_length===view.limit))return decision;
      const viewHash=hash(view);
      if(derivedCatalog?.view_sha256!==viewHash){
        const input={id:randomUUID(),role:'user',source:{kind:'kgxc-managed-skill-catalog',form:'catalog',entries:view.entries,...view.incomplete?{incomplete:true}:{}},content:[{type:'text',text:nativeCatalogText(view.entries,false,view.incomplete)}]};
        derivedCatalog={view_sha256:viewHash,message:input,audit:{message_id:input.id,message_sha256:hash(input),agent_id:producer.id,entries_sha256:hash(view.entries),entry_count:view.entries.length,incomplete:view.incomplete,catalog_description_max_length:view.limit,origin:'derived-from-current-registry/catalog',source_sha256:view.source_sha256,projection_only:true}};
      }
      currentDerived={...derivedCatalog,turn:payload.turn,step:payload.step};return decision;
    }
    const claimed=new Set(payload.messages.map(input=>input.id)),history=[...producer.session.log],published=history.some(event=>event.type==='user/message'&&event.data.source?.kind==='skill-catalog'&&Array.isArray(event.data.source.entries)),view=await catalogView();
    if(candidates.length!==1)throw Error('同一步出现多个技能目录，不能证明原生目录绑定。');
    const input=candidates[0],source={kind:'skill-catalog',form:'catalog',...published?{update:true}:{},entries:view.entries,...view.incomplete?{incomplete:true}:{}};
    if(input.role!=='user'||claimed.has(input.id)||history.some(event=>event.type==='user/message'&&event.data.id===input.id)||hash(input.source)!==hash(source)||input.content?.length!==1||input.content[0].type!=='text'||input.content[0].text!==nativeCatalogText(view.entries,published,view.incomplete))throw Error('技能目录不是本制作步骤与真实技能注册表一致的原生更新。');
    catalogs.set(input.id,{message_id:input.id,message_sha256:hash(input),agent_id:producer.id,turn:payload.turn,step:payload.step,entries_sha256:hash(view.entries),entry_count:view.entries.length,incomplete:view.incomplete,update:published,catalog_description_max_length:view.limit,origin:'native-pre-step'});
    return decision;
  },{prepend:true}));
  disposers.push(producer.ctx.on('llm/stream',(request,next)=>{
    if(request.sessionId!==sessionId)return next();live();const receipt=requests.get(request);
    if(!receipt)throw Error('制作请求没有经过当前明确任务快照，停止调用。');
    receipt.boundary_observed=true;const stream=next();
    return(async function*(){await onProjection?.(receipt);for await(const chunk of stream){live();yield chunk;}})();
  },{prepend:true}));
  disposers.push(producer.ctx.on('internal/get',(_reader,name,_error,next)=>{
    const service=next();if(name!=='llm'||!service)return service;
    return new Proxy(service,{get(target,key){
      const native=Reflect.get(target,key,target);if(key!=='prepareCall')return native;
      return async(...args)=>{
        if(disposed)return Reflect.apply(native,target,args);
        const prepared=await Reflect.apply(native,target,args);let used=false;
        if(!prepared?.config||typeof prepared.stream!=='function')throw Error('原生制作模型缺少绑定的 prepared stream。');
        return Object.freeze({...prepared,stream:request=>{
          if(request.sessionId!==sessionId)return prepared.stream(request);
          live();if(used)throw Error('制作步骤的 prepared stream 不得重复调用。');requireRoute(request,selectedRoute);requireRoute(prepared.config,selectedRoute);
          for(const [key,value] of Object.entries(prepared.config))if(JSON.stringify(request[key])!==JSON.stringify(value))throw Error('制作快照的原生模型配置发生变化：'+key);
          if(!Array.isArray(request.messages)||!request.signal||!request.toolHistory)throw Error('制作快照缺少完整原生请求或工具历史。');
          const owned=request.messages.filter(item=>item.id===message.id),position=request.messages.findIndex(item=>item.id===message.id);
          if(owned.length!==1||hash(owned[0])!==expected)throw Error('本次明确制作指令不在实际请求中或已被改变。');
          if(request.messages.some(item=>item.role==='developer'&&item.source?.kind!=='tool-registry'))throw Error('原生 Runtime 无法证明完整保留 developer 系统约束，停止制作快照。');
          const systems=request.messages.filter(item=>item.role==='system');
          if(!systems.length||systems.some(item=>item.content?.some(block=>block.type!=='text')))throw Error('制作快照无法完整保留原生系统指令。');
          const tail=request.messages.slice(position).filter(item=>item.role!=='system');
          for(const item of tail)if(item.role==='user'&&item.id!==message.id&&!automatic.has(item.source?.kind)&&!approvedJobNotice(item)&&!approvedCatalog(item)&&!approvedRepeat(item)){steer(item);live();}
          const ownedEvent=producer.session.log.find(event=>event.type==='user/message'&&event.data.id===message.id);
          if(!ownedEvent||producer.session.log.some(event=>event.seq>ownedEvent.seq&&event.type==='turn/end'))throw Error('明确制作任务已结束，不能接管后续普通对话。');
          const step=[...producer.session.log].reverse().find(event=>event.type==='step/start');if(!step)throw Error('制作步骤没有真实原生调用边界。');
          const derived=currentDerived?.turn===step.data.turn&&currentDerived.step===step.data.step?currentDerived:undefined;
          const pendingReminders=request.messages.slice(0,position).filter(item=>pendingRepeats.has(item.id)&&approvedRepeat(item));
          const messages=Object.freeze([...systems,tail[0],...pendingReminders,...derived?[derived.message]:[],...tail.slice(1)]),projected=Object.freeze({...request,messages});
          const excluded=request.messages.filter(item=>!messages.includes(item)),byRole={};for(const item of excluded)byRole[item.role]=(byRole[item.role]||0)+1;
          const receipt={protocol:'course-producer-work-snapshot/1',boundary:'native-prepared-stream',operation_id,request_id,session_id:sessionId,
            invocation_id:sessionId+':step:'+step.seq,turn:step.data.turn,step:step.data.step,
            native_messages_sha256:hash(request.messages),projected_messages_sha256:hash(messages),native_message_count:request.messages.length,projected_message_count:messages.length,
            excluded_history_count:excluded.length,excluded_history_by_role:byRole,retained_native_message_count:request.messages.length-excluded.length,derived_message_count:derived?1:0,messages:messages.map(meta),system_prompt_hashes:systems.map(item=>hash(item.content)),
            tools:(request.tools||[]).map(tool=>tool.name),tools_sha256:hash(request.tools||[]),tool_history_sha256:hash(request.toolHistory),config:structuredClone(prepared.config),
            registration_bound:true,tools_preserved:projected.tools===request.tools,tool_history_preserved:projected.toolHistory===request.toolHistory,
            signal_preserved:projected.signal===request.signal,session_history_mutated:false,verified_job_notices:tail.filter(item=>jobNotices.has(item.id)).map(item=>jobNotices.get(item.id)),excluded_verified_pending_job_notices:excluded.filter(item=>staleNotices.has(item.id)).map(item=>staleNotices.get(item.id)),verified_repeat_tool_notices:messages.filter(item=>repeatNotices.has(item.id)).map(item=>repeatNotices.get(item.id)),retained_pending_repeat_ids:pendingReminders.map(item=>item.id),verified_skill_catalogs:tail.filter(item=>catalogs.has(item.id)).map(item=>catalogs.get(item.id)),derived_skill_catalogs:derived?[{...derived.audit,turn:derived.turn,step:derived.step}]:[]};
          requests.set(projected,receipt);receipts.push(receipt);used=true;
          const stream=prepared.stream(projected);if(!receipt.boundary_observed)throw Error('原生 stream 未确认本制作步骤的实际投影。');return stream;
        }});
      };
    }});
  },{prepend:true}));
  return {get receipts(){return receipts;},get steered(){return steered;},assertObserved(){if(!receipts.length||receipts.some(item=>!item.boundary_observed))throw Error('制作没有可核对的实际原生步骤投影。');return receipts;},
    async dispose(){if(!disposed){disposed=true;for(const dispose of disposers.reverse())await dispose();}await steeringTask;}};
}
