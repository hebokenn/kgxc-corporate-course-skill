import {randomUUID,createHash} from 'node:crypto';
import {mkdir,writeFile,readFile,realpath} from 'node:fs/promises';
import {join,resolve,sep} from 'node:path';
import {callReview,callTool} from './bridge.mjs';
import {isolatedAgentRunner,parseAgentJSON,requireRoute,sessionCallAudit,failedInvocationState} from './isolated-review-agent.mjs';
import {productionEventFact} from './production-monitor.mjs';
import {producerQASnapshot,producerReadOnlyTools} from './producer-qa-snapshot.mjs';
import {producerWorkSnapshot} from './producer-work-snapshot.mjs';
import {freezeReviewInput,reviewResultEnvelope} from './review-input-boundary.mjs';
import {probeReviewer} from './review-preflight.mjs';

const STAGES=['script','storyboard','pilot','final'];
const RUNNING=['queued','checking','repairing','rendering','rechecking'];
const FORMAL_TOOLS=new Set(['kgxc_course_update','kgxc_course_export','kgxc_course_source_coverage','write','edit','apply_patch']);
const formalFact=fact=>FORMAL_TOOLS.has(fact.name)&&(fact.name!=='kgxc_course_source_coverage'||fact.kind==='save');
const coverageToolAllowed=async(operation,name,args,allowSave=true)=>{
  if(name.startsWith('kgxc_course_')){
    if(args.course_path!==operation.course_path)return false;
    return name==='kgxc_course_source_coverage'&&(!args.action||args.action==='status'||allowSave&&args.action==='save')||name==='kgxc_course_status'||name==='kgxc_course_editor'&&(!args.action||args.action==='read');
  }
  const path=args.file_path||args.path;
  if(!['read','read_file','glob','grep','search'].includes(name)||typeof path!=='string'||!path.startsWith('/')||!resolve(path).startsWith(resolve(operation.course_path)+sep))return false;
  try{
    const [courseRoot,target]=await Promise.all([realpath(operation.course_path),realpath(path)]);
    return target.startsWith(courseRoot+sep);
  }catch{return false;}
};
const CALL_FACTS=new Set(['tool/call','tool/ptc-dispatch-start']),RESULT_FACTS=new Set(['tool/result','tool/ptc-dispatch']);
const textOf=message=>(message?.content||[]).filter(block=>block.type==='text').map(block=>block.text||'').join('\n');
const done=(stage,node)=>stage==='storyboard'?node?.passed:node?.user_confirmed;
export const PRODUCER_PROMPT=`你是本课绑定的制作 Agent，现在接收独立盲审发现与制作端专用核对包。独立审阅者只找问题，修复职责属于你。依据原件、要求、已有用户确认与当前实际成果核对本次冻结 checklist；盲审意见不是原件事实。只对当前选定方案负责，不评价未选方案，也不扩展画风、媒介或教学范围。保留人工修改与已确认范围。每阶段当前选定方案只盲审一次，全部问题合并为固定清单，一次集中修复。此阶段只返回核对报告和精确局部 repairs，不写文件或运行命令；宿主以你的实际身份，通过版本比较、累计预算和备份后应用一批修改，再由制作端对当前成果作一次定向验收，不再启动新盲审。无权限、缺证据或超限如实报告，不能修改标准、伪造用户确认或完整听审；保留失败和用量。script/storyboard/pilot/final 是四个独立审阅节点，分镜检查讲述与对象/信息/焦点推进以及起态、过程、结果和阅读停稳。
定向验收契约：packet.acceptance_mode 为 targeted 时，只核对 packet.issue_ledger 与冻结 checklist 中的既有问题是否闭环及改动是否引入直接回归；不得重新开放选题、增加风格偏好或产生新的开放式要求，默认不再提交 repairs。只有 packet.targeted_repair_authorized===true 才表示用户另行明确恢复集中修复，可对固定清单提出本次一批 repairs，之后仍只验收一次；不能自行生成授权。未解决项给出当前证据与卡点并停止，不能为凑通过而抹去旧问题。首次集中核对必须一次列全本阶段已见问题，合并重复症状并说明根因。
逐字稿质量契约：重点核对口语是否自然、每段是否增加可用信息、情境与判断依据是否具体、示例及操作与结果是否连贯；识别重复结论、车轱辘话、套话和空泛鼓励。制作端另行核对原件事实、当前方案和已确认的开场品牌问候，保留“酷果星创”问候语；不能把品牌核对答案透露给盲审者。
证据契约：script_read 或 source_and_script 的通过项，evidence 中至少一条 quote 必须逐字完整地存在于当前 packet.input.text，且是连续原文。不能用概述代替 quote，不能用省略号（……或...）拼接不连续片段；多个不连续片段必须拆开为多条 evidence，各自逐字引用。source-accuracy 还必须在对应 evidence 中同时给出 source_id、准确的 locator 和逐字 source_quote；source_id 必须对应 packet.evidence.sources 中的实际来源，source_quote 必须逐字完整地存在该来源的 text 中。只声称页码或给出解释不能代替原件引文。找不到所需引文时保持“无法验证”，不得伪造、补写或改写引文来获得通过。
返修 ID 契约：repairs.issue_id 只能取当前 blind_report 中未解决项的规范 ID，必须逐字使用 packet.blind_report.items[].id，且该项当前 verdict 为“需修改”或“无法验证”，例如 finding:F01；不能取 packet.blind_report.findings[].id 的裸编号 F01。也可使用 packet.checklist 中本轮由你实际判为“需修改”或“无法验证”的精确现有 ID，例如 teaching-continuity。不能仅凭裸编号机械添加 finding: 前缀，必须确认该规范 ID 确实存在于当前未解决 items；禁止 history:Fxx 或临时新造编号。无对应项就报告具体缺项，不得修改验收清单来适配补丁。
分镜返修边界：storyboard.json 顶层除 segments 外所有字段（包括 navigation）必须原样保留，不得改变、增加或删除；片段数量、顺序及每个 segment 的 id、unit_id、source_paragraph_ids、script_excerpt、selected、selection_receipt 也必须不变。局部说明或覆盖状态应放在相应已有 options 的 action、reading_design、safety 等允许内容字段中，只能说明和服从已有导航，调整本片段对象显隐与阅读窗；不得通过更名或挪字段改变既定全局规则，不能把顶层增补当作例外。确需改变上述禁改字段时，只报告需要另行制作，不提交非法 repair。
逐项回应契约：核对每条 packet.blind_report.findings，在现有 root_cause 或 next_step 字符串内逐一说明对应规范 ID 的“提出修复／证据不匹配／待核验”及依据。证据不匹配或待核验项不强迫编造补丁，也不得据此改成通过；如实保留未证实与待核验状态。
只输出核对正文 JSON，不复制 binding 或 agent_audit；宿主仅在核对本次实际原生输入与调用边界后填写绑定和调用审计：{summary,items:[{id,verdict,reason,evidence:[{method,quote,source_id,source_quote,locator}]}],repairs:[{issue_id,path,before_sha256,find,replace,reason}],root_cause,next_step}。`;

export const AUTHORING_PREFLIGHT_PROMPT=`制作前先把输入质量做足：沿用当前选定的教学方案、媒介、人物和用户已确认要求；只用已核实来源区分事实与假设，不补造制度或产品信息。先明确学员在真实工作中要完成的任务，再让每段贡献一个可用判断或操作：按适合主题的具体情境、例子或示范，讲清如何做、为什么这样做、会出现什么结果和如何检查/反馈；不机械要求每段套齐固定结构。逐字稿采用能自然说出口的中文，删去重复结论、同义改写、车轱辘话、空泛套话和没有行动价值的鼓励，保留必要解释与过渡。开场必须保留当前品牌约定的酷果星创问候语；无用户要求不自报总部部门。进入盲审前由制作端先核对内容完整、信息量、原件一致性和当前方案边界，带着高质量初稿进入唯一一次独立盲审。独立盲审后合并问题，一批集中修复、一次定向验收；未解决则保留卡点并停止，不自动重启盲审或循环返修。`;

export const SOURCE_COVERAGE_PROMPT=`原件与逐字稿对照是本课制作交付的一部分，由当前制作 Agent 在同一制作任务内完成，不新增预审 Agent 或审阅循环。首次唯一盲审前，先逐份实际读取原件，按独立业务要点建立对照；逐字稿定稿前及每次改稿后更新。按业务信息点计算覆盖率，不按字数、词频或篇幅估算，不删除遗漏项来缩小分母。每条原件信息保留稳定 id、来源、页码或定位和原文引句，列明 retained（保留）、merged（合并）或 omitted（舍弃）；保留/合并项逐条关联当前稿件实际原句，舍弃项写明舍弃理由，关键 critical 项单列，不能以总覆盖率掩盖关键遗漏。原件漏读、图片表格未辨认或来源信息不全时，source_inventory 的 fully_read 如实填 false，在 read_scope 与 unreadable 中说明实际范围及缺项；不能冒称满覆盖，已登记要点覆盖率不等于原件完整性已获验证。
新增内容逐项登记稿件原句、位置、增加理由和依据：basis_kind=explanation 表示教学解释，example 表示明确标为虚构的教学例子，external 表示有可核查来源的外部事实。外部事实依据提供真实来源引用或链接，找不到依据就保留待核验；解释、虚构例子或外部事实均不能自动变成内部制度、考核要求或承诺，内部规则必须能回到原件依据。
对照保存工具：先读取 kgxc_course_source_coverage(action='status', course_path=当前课程路径)，对照当前稿件的精确 SHA-256；原件正文使用同一工具的 status 加 source_id、offset、limit 分页只读获取 source_excerpt，按 next_offset 继续，核对 source_sha256、read_scope 与 limitations；status=unknown 或正文提取不含图片图表时如实保留未辨认范围，取完文本页不等于核对了全部图片图表；有实际新稿或修改时调用 kgxc_course_source_coverage(action='save', course_path=当前课程路径, expected_script_sha256=当前稿件SHA, report=完整对照)。report 严格使用 {schema:'source-coverage/1',source_inventory:[{source_id,sha256,read_scope,fully_read,unreadable:[]}],points:[{id,source_id,locator,source_quote,critical,disposition:'retained'|'merged'|'omitted',script_quotes:[],reason}],additions:[{id,script_quote,location,reason,basis_kind:'example'|'explanation'|'external',basis}]}。引句必须匹配当前原件或稿件，不补造引文；保存回执不是人工确认。若本阶段不改逐字稿，先核对现有对照是否仍绑定当前稿/原件，沿用有效报告，不为刷新制造重复保存或新模型调用。
人工对照确认必须由用户在工作台真实点击，绑定当前稿件、全部原件和对照报告 SHA；模型工具只支持 status/save，不能调用或伪造 confirm。人工作出信息取舍确认前明确展示覆盖率、关键项、舍弃及新增理由；关闭、预选、沉默、委托制作均不是确认。对照账与原件只属于制作端和人工工作台，不得加入盲审资料包；盲审继续只看当前选定作品，次数仍为一次。`;

export async function producerInputContent({packet,course_path,attachments}){
  const content=[{type:'text',text:PRODUCER_PROMPT+'\n\n'+JSON.stringify(packet)}],frames=packet.evidence?.frames||[];
  if(!frames.length)return {content,frames:[]};
  if(!['pilot','final'].includes(packet.stage)||!attachments?.saveImage)throw Error('当前媒体制作端验收缺少实际图片输入能力，停止调用；不能仅凭JSON帧清单验收。');
  const project=await realpath(resolve(course_path,'project')),boundary=resolve(project,'qa','ai-review',packet.run_id),media=new Set((packet.evidence?.media||[]).map(item=>item.sha256));
  const verified=await Promise.all(frames.map(async(frame,index)=>{
    if(typeof frame.path!=='string'||!media.has(frame.media_sha256)||!/^[a-f0-9]{64}$/.test(frame.sha256)||!Number.isFinite(frame.time)||frame.time<0)throw Error('当前制作端帧证据缺少实际媒体绑定或准确定位。');
    const file=await realpath(resolve(project,frame.path));
    if(!file.startsWith(project+sep)||!file.startsWith(boundary+sep))throw Error('当前制作端帧证据超出本轮冻结目录。');
    const data=await readFile(file);if(createHash('sha256').update(data).digest('hex')!==frame.sha256)throw Error('当前制作端帧字节已改变，停止验收。');
    return {data,id:'producer-frame-'+String(index).padStart(3,'0'),sha256:frame.sha256,media_sha256:frame.media_sha256,time:frame.time};
  }));
  for(const frame of verified){
    const attachment=await attachments.saveImage({data:frame.data,mediaType:'image/jpeg',name:frame.id+'.jpg'});
    content.push({type:'text',text:'当前制作端编码抽帧 '+JSON.stringify({id:frame.id,sha256:frame.sha256,media_sha256:frame.media_sha256,time:frame.time})},{type:'image',attachment});
  }
  return {content,frames:verified.map(({data,...frame})=>frame)};
}

export function reviewHost(ctx,{invoke=callReview,tool=callTool,bindings=new Map(),runIsolated,pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}){
  const owner=randomUUID(),tasks=new Map(),workTasks=new Map(),productions=new Map(),idleTasks=new Map(),blockedProducers=new Map(),directions=new WeakMap();let disposed=false;
  const get=name=>ctx.get?.(name),independent=runIsolated||isolatedAgentRunner(ctx);
  const runCall=async(action,args)=>{const value=await invoke(action,args);if(value.ok===false)throw Error(value.error);return value;};
  const identity=agent=>({id:agent.id||agent.session.id,session_id:agent.session.id,role:'producer'});
  const producerFor=args=>{
    const agents=get('agents'),agent=agents?.get(args.session_id)||bindings.get(args.course_path);
    if(!agent||agents?.get(agent.session.id)!==agent)throw Error('当前课程没有绑定真实制作 Agent，不能冒充制作人。');return agent;
  };
  async function stop(operation,reason){
    if(operation.stopped)return;operation.stopped=true;operation.controller.abort(Error(reason));
    blockedProducers.set(operation.producer,reason);
    operation.producer.cancel({kind:'user',message:reason},{keepInbox:Boolean(operation.steered)});
    await runCall('hold',{course_path:operation.course_path,held:true,reason}).catch(()=>{});
    if(operation.job_id){
      let state;
      for(let attempt=0;attempt<20;attempt++){
        const value=await tool('kgxc_course_job',{course_path:operation.course_path,job_id:operation.job_id}).catch(error=>({ok:false,error:error.message}));
        state=value.job||{status:'unknown',error:value.error};
        if(['cancelled','failed','complete','missing'].includes(state.status))break;
        await pause(500);
      }
      operation.stop_result={job_id:operation.job_id,status:state?.status||'unknown',stop_pending:!['cancelled','failed','complete','missing'].includes(state?.status)};
    }
  }
  async function independentCall(args,packet,role,key,selection,signal){
    signal.throwIfAborted();requireRoute(selection);
    const reserved=await runCall('reserve',{...args,key,role,route:{provider:selection.provider,model:selection.model}});
    if(!reserved.reserved)throw Error('独立 Agent 调用已登记，不重复执行。');
    const controller=new AbortController(),abort=()=>controller.abort(signal.reason);
    signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
    const timer=setTimeout(()=>controller.abort(Error('独立 Agent 达到十分钟时限；成果、调用与用量保留。')),600000);
    try{
      const value=await independent({role,packet,course_path:args.course_path,selection,signal:controller.signal});
      const sent_frames=(packet.allowed_artifacts||[]).filter(artifact=>artifact.kind==='frame'&&value.audit?.artifact_ids?.includes(artifact.id)).map(artifact=>artifact.sha256);
      await runCall('call_result',{...args,key,usage:value.usage,agent_audit:value.audit,sent_frames,execution_phase:'model',model_invoked:true});return value.result;
    }catch(error){
      const execution_phase=error.execution_phase||'unknown',model_invoked=error.model_invoked??null;
      const agent_audit=error.agent_audit?.invocation_ids?.length||execution_phase==='preflight'&&model_invoked===false?error.agent_audit:undefined;
      try{await runCall('call_result',{...args,key,usage:error.usage||{},agent_audit,error:error.message,execution_phase,model_invoked});}
      catch(accountingError){error.message+='；调用结算未写回：'+accountingError.message;}
      throw error;
    }finally{clearTimeout(timer);signal.removeEventListener('abort',abort);}
  }
  async function producerCall(args,packet,key,selection,signal,producer){
    signal.throwIfAborted();requireRoute(producer.model?.current?.()||producer.options);
    packet=freezeReviewInput(packet);
    const input=await producerInputContent({packet,course_path:args.course_path,attachments:get('attachments')});
    signal.throwIfAborted();
    const timeoutMs=Object.hasOwn(packet,'producer_qa_timeout_ms')?packet.producer_qa_timeout_ms:600000;
    if(!Number.isSafeInteger(timeoutMs)||timeoutMs<30000||timeoutMs>3600000)throw Error('制作端 QA 总等待必须是 30000–3600000 的整数毫秒。');
    if(producer.status==='running')throw Error('制作 Agent 正在执行其他工作，本轮不抢占人工操作。');
    const reserved=await runCall('reserve',{...args,key,role:'producer',route:{provider:selection.provider,model:selection.model}});
    if(!reserved.reserved)throw Error('制作端核对调用已登记，不重复执行。');
    const fromSeq=[...producer.session.log].at(-1)?.seq||0,disposers=[],started=performance.now(),startedAt=new Date().toISOString();let watchdogTriggered=false;
    const abort=()=>producer.cancel({kind:'user',message:String(signal.reason?.message||'制作端核对停止')});
    signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
    const timer=setTimeout(()=>{watchdogTriggered=true;producer.cancel({kind:'user',message:'制作端核对达到已登记的 '+timeoutMs+' 毫秒总等待时限'});},timeoutMs);let observation,snapshot,modelText,modelBody,hostResult,resultError,envelopeReturned=false;
    const observe=state=>{
      const sent=snapshot?.receipt?.boundary_observed===true?input.frames:[];
      const value=sessionCallAudit(producer,selection,{fromSeq,role:'producer',artifact_ids:sent.map(frame=>frame.id),outbound_projection:snapshot?.receipt});
      value.audit.capabilities=sent.length?['text','images']:['text'];value.audit.producer_frame_evidence=structuredClone(sent);
      value.audit.producer_qa_wait={effective_timeout_ms:timeoutMs,started_at:startedAt,elapsed_ms:Math.round(performance.now()-started),watchdog_triggered:watchdogTriggered,
        termination:watchdogTriggered?'total_timeout':signal.aborted?'cancelled':state,authorization_source:packet.producer_qa_timeout_authorization?.source||'default'};
      return value;
    };
    try{
      if(!producer.ctx?.tools?.guard||!producer.ctx?.tools?.restrict||!producer.ctx?.tools?.setExecutor||!producer.ctx?.on)throw Error('制作 Agent 缺少版本受控的只读核对能力。');
      disposers.push(producer.ctx.tools.restrict({allow:[]}));
      disposers.push(producer.ctx.tools.guard(()=> '制作端核对禁止直接写入；宿主检查版本和预算后再修复。'));
      disposers.push(await producerReadOnlyTools(producer));
      disposers.push(producer.ctx.on('agent/pre-step',async(payload,next)=>{
        requireRoute(payload.modelSelection);signal.throwIfAborted();if(payload.step>1)throw Error('制作端核对不允许工具循环。');return next();
      },{prepend:true}));
      const message=Object.freeze({id:randomUUID(),role:'user',source:{kind:'kgxc-producer-qa'},content:input.content});
      snapshot=producerQASnapshot(producer,{message,packet,signal,onProjection:async projection=>{
        const directory=join(args.course_path,'project','qa','ai-review',args.run_id,'calls');await mkdir(directory,{recursive:true});
        await writeFile(join(directory,encodeURIComponent(key)+'.projection.json'),JSON.stringify({at:Date.now(),key,projection},null,2),{mode:0o600});
      }});
      producer.followup(message);
      await producer.whenIdle();observation=observe('completed');
      modelText=textOf(observation.events.filter(event=>event.type==='assistant/message').at(-1)?.data.message);
      if(watchdogTriggered)throw Error('制作端核对达到已登记总等待时限，调用与未知用量保留。');
      const end=observation.events.filter(event=>event.type==='turn/end').at(-1);
      if(end?.data.reason?.kind!=='completed')throw Error(end?.data.reason?.error?.message||'制作 Agent 未完整返回核对报告。');
      if(!observation.audit.invocation_ids.length)throw Error('制作端核对没有真实调用记录。');signal.throwIfAborted();
      const receipt=snapshot.assertObserved();
      modelBody=parseAgentJSON(modelText);
      if(observation.headers.some(header=>(header.tools||[]).length))throw Error('制作端核对实际请求暴露了执行工具。');
      hostResult=reviewResultEnvelope(modelBody,{binding:packet.binding,receipt,audit:observation.audit});observation.audit=hostResult.agent_audit;
      await runCall('call_result',{...args,key,usage:observation.usage,agent_audit:observation.audit,sent_frames:input.frames.map(frame=>frame.sha256),execution_phase:'model',model_invoked:true});envelopeReturned=true;return hostResult;
    }catch(error){
      resultError=error.message;
      observation=observe('failed');
      modelText=textOf(observation.events.filter(event=>event.type==='assistant/message').at(-1)?.data.message);
      const phase=failedInvocationState(observation);
      const agent_audit=observation.audit.invocation_ids.length||phase.model_invoked===false?observation.audit:undefined;
      try{await runCall('call_result',{...args,key,usage:observation.usage,agent_audit,sent_frames:observation.audit.producer_frame_evidence.map(frame=>frame.sha256),error:error.message,...phase});}
      catch(accountingError){error.message+='；制作端调用结算未写回：'+accountingError.message;}
      throw error;
    }finally{
      clearTimeout(timer);signal.removeEventListener('abort',abort);await snapshot?.dispose();for(const dispose of disposers.reverse())await dispose();
      if(observation){
        try{
          const directory=join(args.course_path,'project','qa','ai-review',args.run_id,'calls');await mkdir(directory,{recursive:true});
          if(modelText!==undefined)await writeFile(join(directory,encodeURIComponent(key)+'.model.json'),JSON.stringify({text:modelText,...modelBody===undefined?{}:{body:modelBody}},null,2),{mode:0o600});
          await writeFile(join(directory,encodeURIComponent(key)+'.host.json'),JSON.stringify({envelope_returned:envelopeReturned,result:hostResult||null,error:resultError||null,agent_audit:observation.audit},null,2),{mode:0o600});
          await writeFile(join(directory,encodeURIComponent(key)+'.wait.json'),JSON.stringify({key,agent_id:producer.id,session_id:producer.session.id,...observation.audit.producer_qa_wait},null,2),{mode:0o600});
        }catch{ctx.logger?.warn?.('制作端等待元数据附档未写入；实际调用结算保留。');}
      }
    }
  }
  async function supervise(args,selection,signal,key){
    const {packet}=await runCall('supervisor_packet',args);
    const result=await independentCall(args,packet,'supervisor',key,selection,signal);
    const value=await runCall('supervisor_submit',{...args,result});
    return {...value,passed:result.passed,blocked:result.passed===false};
  }
  async function finish(args,options,producer,signal){
    const value=await runCall('finish',{...args,...options}),grant=value.continuation;
    if(!grant?.authorized||grant.stage!=='pilot'||grant.requires_user_confirmation!==false)return value;
    signal.throwIfAborted();
    if(producer.status==='running')throw Error('分镜已通过，制作 Agent 有新任务，保留既有继续授权但不覆盖当前对话。');
    const instruction='当前分镜已完成唯一一次独立盲审、制作端核对/问题验收和独立监督，工作台依据真实既有委托完成了分镜制作预检。继续授权记录='+JSON.stringify(grant)+'。这是依据已有委托继续制作，不是新增用户点击或用户确认。先读取 kgxc_course_status(full=true) 与 kgxc_course_editor，沿用当前正式分镜和实际选择，制作并登记本课三个完整真实有声小样，之后停在独立小样审阅与原有人审节点。不得跳过小样或直接制作整课。';
    await produce({course_path:args.course_path,session_id:producer.session.id,stage:'pilot',request_id:'storyboard-pilot:'+args.run_id+':'+grant.fingerprint,instruction},args.run_id);
    return value;
  }
  async function produce(args,continuationRun){
    if(disposed)throw Error('插件已停止，不能启动制作。');
    const producer=producerFor(args),selection=requireRoute(get('agentDefaultModel')?.currentSelection());requireRoute(producer.model?.current?.()||producer.options);
    if(!STAGES.includes(args.stage)||typeof args.instruction!=='string'||!args.instruction.trim()||args.instruction.length>8000||typeof args.request_id!=='string'||!args.request_id.trim()||args.request_id.length>2000)throw Error('明确制作任务需要有效阶段、完整指令和稳定 request_id。');
    const operation_id='produce-'+createHash('sha256').update(args.course_path+'\0'+args.request_id).digest('hex'),existing=workTasks.get(args.course_path);
    if(existing){if(existing.operation_id===operation_id&&existing.instruction===args.instruction&&existing.stage===args.stage)return {ok:true,started:false,operation_id,request_id:args.request_id};throw Error('当前课程已有受控制作任务，不能并行重放。');}
    if(args.busy||producer.status==='running'||[...tasks.values()].some(task=>task.args.course_path===args.course_path&&task.args.run_id!==continuationRun))throw Error('制作 Agent 或课程正在执行其他工作，本次不抢占。');
    const ready=Promise.withResolvers(),task={operation_id,instruction:args.instruction,stage:args.stage,promise:null};workTasks.set(args.course_path,task);
    task.promise=(async()=>{
      let snapshot,operation,observation,fromSeq=[...producer.session.log].at(-1)?.seq||0,started=false;
      try{
        const dispatch=await runCall('production_dispatch',{course_path:args.course_path,stage:args.stage,task_id:operation_id});
        const llm=get('llm');
        if(!llm?.prepareCall)throw Error('REVIEW_CAPABILITY_MISSING: composed route preparation unavailable');
        const prepared=await llm.prepareCall({...selection,maxTokens:14000},new AbortController().signal);requireRoute(prepared.config);
        const requirements=await runCall('capability_requirements',{course_path:args.course_path,stage:args.stage});
        dispatch.capability_preflight=await probeReviewer({get,selection,prepared,packet:{run_id:operation_id,checklist:requirements.checklist},course_path:args.course_path,strict:false});
        const claim=await handle.production({course_path:args.course_path,producer,stage:args.stage,operation_id,phase:'start',user_instruction:args.instruction,
          execution:[{type:'production/request',operation:'controlled-produce',call_id:args.request_id,agent_id:producer.id,stage:args.stage}]});
        if(claim.started!==true){ready.resolve({ok:true,started:false,operation_id,request_id:args.request_id});return;}
        operation=productions.get(args.course_path);started=true;operation.managed=true;
        if(producer.status==='running'||producer.session.log.some(event=>event.seq>fromSeq&&(event.type==='user/message'&&event.data.source?.kind==='user'||event.type==='agent/inbox/spliced'&&event.data.inserted?.some(input=>input.source?.kind==='user')))){
          operation.steered=true;throw Error('制作派发期间收到新的用户任务，停止旧请求并保留新输入。');
        }
        const message=Object.freeze({id:randomUUID(),role:'user',source:{kind:'kgxc-producer-work'},content:[{type:'text',text:'KGXC_OPERATION '+JSON.stringify({course_path:args.course_path,stage:args.stage,operation_id,request_id:args.request_id})+'\n实际派工与原句、对象、输入哈希、负责/禁改范围、必检动作及交回文件：'+JSON.stringify(dispatch)+'\n完成前通过给出的 return_command 提交真实结果映射与证据，不能只口头声称完成。\n当前课程路径：'+args.course_path+'。依据现有权限和已有确认读取当前实际文件及相关记录后完成以下明确任务；保留过程文件、旧版本和真实失败，不代用户确认。\n'+AUTHORING_PREFLIGHT_PROMPT+'\n\n'+SOURCE_COVERAGE_PROMPT+'\n\n'+args.instruction}]});
        snapshot=producerWorkSnapshot(producer,{message,operation_id,request_id:args.request_id,signal:operation.controller.signal,
          onProjection:async receipt=>{
            const directory=join(args.course_path,'project','qa','ai-supervision',operation_id,'steps');await mkdir(directory,{recursive:true});
            await writeFile(join(directory,encodeURIComponent(receipt.invocation_id)+'.projection.json'),JSON.stringify(receipt,null,2),{mode:0o600});
          },onSteering:async input=>{
            operation.steered=true;
            await runCall('production_event',{course_path:args.course_path,stage:args.stage,operation_id,producer:identity(producer),phase:'failure',execution:[{type:'production/user-direction',status:'steered',user_instruction:textOf(input).slice(0,8000),agent_id:producer.id}]});
            await stop(operation,'收到新的用户指令，停止旧制作快照；新输入与已完成文件保留。');
          }});
        producer.followup(message);ready.resolve({ok:true,started:true,operation_id,request_id:args.request_id});
        await producer.whenIdle();snapshot.assertObserved();
        observation=sessionCallAudit(producer,selection,{fromSeq,role:'producer'});
        await snapshot.dispose();
        const end=observation.events.filter(event=>event.type==='turn/end').at(-1);
        if(end?.data.reason?.kind!=='completed')throw Error(end?.data.reason?.error?.message||'明确制作任务已停止，保留实际文件及用量。');
        await operation.tail;
        if(!operation.finished&&!operation.stopped)await handle.production({course_path:args.course_path,producer,stage:args.stage,phase:'end',execution:[{type:'production/settled',status:'completed',agent_id:producer.id}]});
      }catch(error){
        ready.reject(error);
        if(started&&operation&&!operation.stopped){
          await handle.production({course_path:args.course_path,producer,stage:args.stage,phase:'failure',execution:[{type:'production/settled',status:'failed',failed:true,error:String(error.message).slice(0,2000),agent_id:producer.id}]}).catch(()=>{});
          await stop(operation,'明确制作任务失败，实际文件、历史和用量保留。');
        }
      }finally{
        await snapshot?.dispose();
        if(started){
          observation??=sessionCallAudit(producer,selection,{fromSeq,role:'producer'});
          const audit=observation.audit;
          audit.native_log_input_messages=audit.input_messages;audit.native_log_system_prompt_hashes=audit.system_prompt_hashes;
          audit.input_scope='producer-work-snapshot';audit.outbound_steps=snapshot?.receipts||[];
          audit.input_messages=audit.outbound_steps.flatMap(step=>step.messages.filter(item=>item.role==='user'));audit.system_prompt_hashes=audit.outbound_steps.flatMap(step=>step.system_prompt_hashes);
          try{
            const directory=join(args.course_path,'project','qa','ai-supervision',operation_id);await mkdir(directory,{recursive:true});
            await writeFile(join(directory,'producer-dispatch.json'),JSON.stringify({operation_id,request_id:args.request_id,agent_audit:audit,usage:observation.usage,execution_state:failedInvocationState(observation)},null,2),{mode:0o600});
          }catch{ctx.logger?.warn?.('制作步骤元数据附档未写入，原生日志及实际成果保留。');}
        }
        if(workTasks.get(args.course_path)===task)workTasks.delete(args.course_path);
        if(operation?.finished&&!operation.stopped)void handle.onIdle(producer).catch(()=>{});
      }
    })();
    return ready.promise;
  }
  async function execute(args,selection,signal,producer,resume){
    try{
      let pendingResume=resume,producerOnly=Boolean(resume);
      for(let round=0,iteration=resume?.iteration??0;round<2;round++,iteration++){
        signal.throwIfAborted();const sourceOnly=pendingResume;pendingResume=null;
        if(!producerOnly){
          const {packet}=await runCall('packet',args);
          await runCall('progress',{...args,text:'全新独立 Agent 正在只读审阅当前'+({script:'逐字稿',storyboard:'分镜',pilot:'实际小样',final:'实际完整成片'}[args.stage])+'，制作 Agent 负责核对及修复。'});
          const report=await independentCall(args,packet,'reviewer','check-'+iteration,selection,signal);
          await runCall('submit',{...args,result:report});
        }else await runCall('progress',{...args,text:round?'集中修复已完成，制作端正在按固定问题清单进行一次定向验收；不再启动盲审。':'沿用已接受的唯一盲审报告，仅恢复制作端核验；保留旧失败、问题清单及累计用量。'});
        const {packet:producerPacket}=await runCall('producer_packet',args);
        const sourceReport=await producerCall(args,producerPacket,sourceOnly?.producer_key||'producer-'+iteration,selection,signal,producer);
        const verdict=await runCall('producer_submit',{...args,result:sourceReport});
        const supervision=await supervise(args,selection,signal,sourceOnly?.supervisor_key||'supervisor-'+iteration);
        if(supervision.blocked||supervision.passed===false){
          const operation=productions.get(args.course_path);if(operation)await stop(operation,'独立监督发现执行问题，课程已暂停。');
          else{blockedProducers.set(producer,'独立监督发现执行问题，课程已暂停。');producer.cancel({kind:'user',message:'独立监督发现执行问题，课程已暂停。'});await runCall('hold',{course_path:args.course_path,held:true,reason:'独立监督发现执行问题，课程已暂停。'});}
          await runCall('finish',{...args,error:'独立监督发现执行问题，保留报告与成果，不能放行。'});return;
        }
        if(!verdict.can_repair){await finish(args,{limit:verdict.limit_reached},producer,signal);return;}
        if(round||producerPacket.acceptance_mode==='targeted'&&producerPacket.targeted_repair_authorized!==true){await finish(args,{error:'一次集中修复后的定向验收仍有未解决项，保留问题与证据，停止自动返修；不再启动盲审。'},producer,signal);return;}
        try{
          const repaired=await runCall('repair',{...args,repairs:verdict.repairs,producer_id:identity(producer).id});
          if(repaired.rerender){
            const {job}=await runCall('render',args);let state=job;
            const operation=productions.get(args.course_path);if(operation)operation.job_id=job.id;
            while(['queued','rendering','encoding','packaging'].includes(state.status)){
              signal.throwIfAborted();await pause(1500);const response=await tool('kgxc_course_job',{course_path:args.course_path,job_id:job.id});
              if(response.ok===false)throw Error(response.error);state=response.job;
            }
            if(state.status!=='complete')throw Error('制作端返修导出未完成：'+(state.error||state.status));
            await runCall('render_result',{...args,fingerprint:repaired.fingerprint});
          }
          producerOnly=true;
        }catch(error){
          await runCall('repair_error',{...args,error:error.message}).catch(recordError=>{error.message+='；返修错误未写回：'+recordError.message;});
          throw error;
        }
      }
      throw Error('一次集中修复及定向验收已结束，未解决项、成果与用量保留。');
    }catch(error){await runCall('finish',{...args,error:error.message,limit:/预算|上限/.test(error.message)}).catch(()=>{});}
  }
  function launch(runArgs,selection,producer,resume){
    const taskKey=runArgs.course_path+'\n'+runArgs.stage,controller=new AbortController();
    if(disposed)controller.abort(Error('插件已停止，本轮不再调用模型。'));
    const task={controller,args:runArgs,promise:null,resume_request_id:resume?.request_id};tasks.set(taskKey,task);
    task.promise=execute(runArgs,selection,controller.signal,producer,resume).finally(()=>{
      if(tasks.get(taskKey)===task){tasks.delete(taskKey);void handle.onIdle(producer).catch(error=>ctx.logger?.warn?.('审阅完成后的自动衔接未启动：'+error.message));}
    });
  }
  async function start(args){
    if(disposed)throw Error('插件已停止，请重新打开后明确继续。');
    const producer=producerFor(args),selection=requireRoute(get('agentDefaultModel')?.currentSelection());
    requireRoute(producer.model?.current?.()||producer.options);const operation=productions.get(args.course_path);
    const value=await runCall('begin',{...args,route:{provider:selection.provider,model:selection.model},owner,producer:identity(producer),supervision_operation_id:operation?.id});
    if(value.started)launch({course_path:args.course_path,stage:args.stage,run_id:value.run.id},selection,producer,value.producer_only?{...value,producer_only:true}:undefined);
    return value;
  }
  async function handle(action,args){
    if(action==='produce')return produce(args);
    if(action==='sync'){
      await runCall('enable',{course_path:args.course_path});const {review}=await runCall('recover',{course_path:args.course_path,owner});
      for(const task of tasks.values())if(task.args.course_path===args.course_path&&(review.hold?.held||review.nodes[task.args.stage]?.status==='stale')){
        task.controller.abort(Error(review.hold?.held?'课程已暂停，成果与用量保留。':'审阅期间有人工修改，停止旧版本。'));
        await runCall('finish',{...task.args,error:'审阅暂停或出现新修改，停止旧版本调用。'});
      }
      const agent=get('agents')?.get(args.session_id);
      if(productions.get(args.course_path)?.auto_review===false)return runCall('status',{course_path:args.course_path});
      if(!review.hold?.held&&!workTasks.has(args.course_path)&&!args.busy&&agent?.status!=='running'&&!Object.values(review.nodes).some(node=>RUNNING.includes(node.run?.status))){
        for(const stage of STAGES){
          const node=review.nodes[stage];if(!node)break;if(done(stage,node))continue;if(RUNNING.includes(node.status))break;
          const previous=STAGES[STAGES.indexOf(stage)-1];if(previous&&!done(previous,review.nodes[previous]))break;
          try{await start({...args,stage,mode:'auto',request_id:'auto:'+stage+':'+node.fingerprint});}
          catch(error){if(!/尚无本阶段|人工草稿尚在编辑|实际媒体尚未更新/.test(error.message))throw error;}break;
        }
      }return runCall('status',{course_path:args.course_path});
    }
    if(action==='continue'||action==='modify'){
      if(args.busy||get('agents')?.get(args.session_id)?.status==='running')throw Error('当前课程正在制作，请等待结束后再审阅。');
      return start({...args,mode:action,request_id:args.request_id||randomUUID()});
    }
    if(action==='resume_producer'){
      if(disposed)throw Error('插件已停止，请重新打开后明确恢复制作端核验。');
      const producer=producerFor(args),selection=requireRoute(get('agentDefaultModel')?.currentSelection()),request_id=args.request_id||randomUUID();
      requireRoute(producer.model?.current?.()||producer.options);
      const active=[...tasks.values()].find(task=>task.args.course_path===args.course_path);
      if((active&&active.resume_request_id!==request_id)||(!active&&(args.busy||producer.status==='running')))throw Error('当前课程正在制作或审阅，不能并行恢复制作端核验。');
      const value=await runCall('resume_producer',{...args,request_id,producer:identity(producer),route:{provider:selection.provider,model:selection.model},owner});
      if(value.started){
        if(!value.producer_key||!value.supervisor_key||!value.attempt_id||value.run?.id!==args.run_id||!Number.isSafeInteger(value.iteration))throw Error('制作端恢复响应缺少唯一调用、原任务及轮次绑定，未执行模型。');
        launch({course_path:args.course_path,stage:args.stage,run_id:value.run.id},selection,producer,{...value,request_id});
      }
      return value;
    }
    if(['status','review_arrangement','user_audio_review'].includes(action))return runCall(action,args);
    if(action==='supervision_status'){
      const value=await runCall('status',args),operation=productions.get(args.course_path);
      return {ok:true,supervision:value.review?.supervision||null,runtime:operation?{operation_id:operation.id,stopped:operation.stopped,finished:operation.finished,stop_result:operation.stop_result||null}:null};
    }
    if(action==='hold'){
      const value=await runCall('hold',args);
      if(args.held){
        for(const task of tasks.values())if(task.args.course_path===args.course_path)task.controller.abort(Error(args.reason||'课程审阅已暂停。'));
        const operation=productions.get(args.course_path);if(operation)await stop(operation,args.reason||'用户暂停本课制作。');
      }else{
        const operation=productions.get(args.course_path);if(operation?.stopped)productions.delete(args.course_path);
        const producer=operation?.producer||bindings.get(args.course_path);if(producer)blockedProducers.delete(producer);
      }
      return value;
    }
    if(action==='draft'||action==='dismiss')return runCall('ui',{...args,action});
    throw Error('未知正式审阅操作');
  }
  handle.production=async({course_path,producer,stage,phase='start',execution=[],operation_id,user_instruction,auto_review=true,scope}={})=>{
    if(disposed)throw Error('插件已停止，不能启动制作。');
    if(!producer||get('agents')?.get(producer.session.id)!==producer)throw Error('监督缺少真实绑定制作 Agent。');
    const selection=requireRoute(get('agentDefaultModel')?.currentSelection());requireRoute(producer.model?.current?.()||producer.options);
    let operation=productions.get(course_path);
    if(phase==='start'){
      if(operation&&!operation.finished&&!operation.stopped)throw Error('当前课程已有受监督制作任务。');
      operation={id:operation_id||randomUUID(),course_path,producer,stage,auto_review:auto_review!==false,scope,user_direction_id:directions.get(producer)?.id,controller:new AbortController(),tail:Promise.resolve(),finished:false,stopped:false,events:0,progress_events:0,calls:new Map()};productions.set(course_path,operation);
      const direction=user_instruction||directions.get(producer)?.text;
      if(direction)execution=[...execution,{type:'production/dispatch',operation:user_instruction?'workbench-stage':'conversation',user_instruction:String(direction).slice(0,8000),agent_id:identity(producer).id,stage}];
    }
    if(!operation||operation.producer!==producer||operation.stopped)throw Error('制作监督身份或生命周期已失效。');
    const perform=async()=>{
      const args={course_path,stage,operation_id:operation.id};
      let correlationError;
      execution=execution.map(fact=>{
        if(CALL_FACTS.has(fact.type)&&fact.call_id){
          if(!operation.calls.has(fact.call_id)&&operation.calls.size>=128)correlationError=Error('监督中未结算工具超过128项，保留事实并停止，不能丢失正式变更关联。');
          else operation.calls.set(fact.call_id,{name:fact.name,kind:fact.kind});
        }
        if(RESULT_FACTS.has(fact.type)){
          const call=operation.calls.get(fact.call_id);operation.calls.delete(fact.call_id);
          if(call)return {...fact,...call};
        }
        return fact;
      });
      const exportEvent=execution.find(event=>event.type?.startsWith('export/')&&event.job_id);if(exportEvent)operation.job_id=exportEvent.job_id;
      const recorded=await runCall('production_event',{...args,producer:identity(producer),phase,execution});
      if(phase==='start'&&recorded.started===false){operation.finished=true;return {ok:true,started:false,operation_id:operation.id};}
      if(phase==='start'&&execution.some(event=>event.type==='production/request')&&recorded.started!==true)throw Error('制作任务缺少已持久登记的原子首次启动回执。');
      for(const fact of execution)if(fact.route)requireRoute(fact.route);
      if(correlationError)throw correlationError;
      operation.progress_events+=execution.length;
      const checkpoint=phase==='progress'&&(operation.progress_events>=32||execution.some(fact=>fact.type==='production/user-direction'||fact.type?.startsWith('export/')||(CALL_FACTS.has(fact.type)||RESULT_FACTS.has(fact.type))&&formalFact(fact)||RESULT_FACTS.has(fact.type)&&!fact.name));
      if(['start','failure','end'].includes(phase)||checkpoint){
        const result=await supervise(args,selection,operation.controller.signal,'supervision-'+phase+'-'+operation.events++);
        if(result.blocked||result.passed===false){await stop(operation,'独立监督发现执行不符合要求，已停止制作。');throw Error('独立监督已阻止本次执行。');}
        operation.progress_events=0;
      }
      if(phase==='end'){
        operation.finished=true;
        if(operation.auto_review)void handle.onIdle(producer).catch(error=>ctx.logger?.warn?.('课程自动独立审阅未启动：'+error.message));
      }
      return {ok:true,started:phase==='start'?true:undefined,operation_id:operation.id};
    };
    operation.tail=operation.tail.then(perform).catch(async error=>{await stop(operation,'监督执行失败：'+error.message);throw error;});return operation.tail;
  };
  handle.observe=async(producer,event)=>{
    let direction;
    if(event.type==='user/message'&&event.data?.source?.kind==='user'){
      const text=textOf(event.data).slice(0,8000);
      if(text){direction={text,id:event.data.id,seq:event.seq,time:event.time};directions.set(producer,direction);}
    }
    const operation=[...productions.values()].find(item=>item.producer===producer&&!item.finished&&!item.stopped);if(!operation)return;
    if(direction)return handle.production({course_path:operation.course_path,producer,stage:operation.stage,phase:'progress',execution:[{type:'production/user-direction',operation:'conversation-update',user_instruction:direction.text,agent_id:identity(producer).id,seq:direction.seq,time:direction.time}]});
    const fact=productionEventFact(event);if(!fact)return;
    if(event.type==='turn/end'&&fact.status==='aborted'){
      await runCall('production_event',{course_path:operation.course_path,stage:operation.stage,operation_id:operation.id,producer:identity(producer),phase:'end',execution:[fact]});
      await stop(operation,'制作 Agent 已中止，课程及自动审阅已暂停；成果与用量保留。');operation.finished=true;return;
    }
    // Only a real KGXC export result exposes job_status. DSH shell job IDs are
    // a separate service and must not be polled as video export identifiers.
    if(fact.job_id&&fact.job_status){
      handle.trackExport({course_path:operation.course_path,producer,stage:operation.stage,job:{id:fact.job_id,status:fact.job_status}});
    }
    const ending=event.type==='turn/end'&&!operation.exportTask;
    return handle.production({course_path:operation.course_path,producer,stage:operation.stage,phase:fact.failed?'failure':ending?'end':'progress',execution:[fact]});
  };
  handle.trackExport=({course_path,producer,stage,job})=>{
    const operation=productions.get(course_path);if(!operation||operation.producer!==producer||operation.stopped||operation.exportTask)return;
    operation.job_id=job.id;
    operation.exportTask=(async()=>{
      await handle.production({course_path,producer,stage,phase:'progress',execution:[{type:'export/registered',job_id:job.id,status:job.status}]});
      let current=job;
      while(['queued','rendering','encoding','packaging'].includes(current.status)&&!operation.stopped&&!disposed){
        await pause(1500);const value=await tool('kgxc_course_job',{course_path,job_id:job.id});if(value.ok===false)throw Error(value.error);current=value.job;
      }
      if(!operation.stopped&&!disposed){
        await handle.production({course_path,producer,stage,phase:current.status==='complete'?'end':'failure',execution:[{type:'export/settled',job_id:job.id,status:current.status,failed:current.status!=='complete',error:current.error}]});
        if(current.status==='complete')void handle.onIdle(producer).catch(error=>ctx.logger?.warn?.('导出后的独立审阅未启动：'+error.message));
      }
    })().catch(async error=>{await stop(operation,'真实导出监督失败：'+error.message);});
  };
  handle.blockReason=producer=>{
    if(blockedProducers.has(producer))return blockedProducers.get(producer);
    const operation=[...productions.values()].find(item=>item.producer===producer&&item.stopped);
    return operation?'独立监督已停止本课执行；不得继续调用制作工具或自动重放。':undefined;
  };
  // Native producer idle/real export completion, not browser polling, owns the
  // automatic handoff. The backend's stable auto request id handles refreshes.
  handle.onIdle=producer=>{
    if(disposed||producer?.status==='running'||handle.blockReason(producer))return Promise.resolve();
    const paths=[...bindings].filter(([,agent])=>agent===producer).map(([path])=>path);
    return Promise.all(paths.map(path=>{
      if(idleTasks.has(path))return idleTasks.get(path);
      const operation=productions.get(path);
      if(operation&&(!operation.finished||operation.auto_review===false))return Promise.resolve();
      if(workTasks.has(path))return Promise.resolve();
      if([...tasks.values()].some(task=>task.args.course_path===path))return Promise.resolve();
      const pending=Promise.resolve().then(()=>handle('sync',{course_path:path,session_id:producer.session.id})).finally(()=>{if(idleTasks.get(path)===pending)idleTasks.delete(path);});
      idleTasks.set(path,pending);return pending;
    }));
  };
  handle.beforeTool=async(producer,name,args={})=>{
    if(!producer)return;
    const reason=handle.blockReason(producer);if(reason)throw Error(reason);
    let operation=[...productions.values()].find(item=>item.producer===producer&&!item.finished);
    const completedCoverage=[...productions.values()].find(item=>item.producer===producer&&item.finished&&item.scope==='source-coverage'&&(!args.course_path||args.course_path===item.course_path));
    if(!operation&&completedCoverage&&directions.get(producer)?.id===completedCoverage.user_direction_id){
      if(await coverageToolAllowed(completedCoverage,name,args,false))return;
      throw Error('本次原件对照任务已经结束；须有新的明确用户制作指令，不能自动修改稿件或制作后续阶段。');
    }
    if(operation){
      await operation.tail;if(operation.stopped)throw Error(handle.blockReason(producer));
      if(operation.scope==='source-coverage'){
        if(!await coverageToolAllowed(operation,name,args))throw Error('本次仅生成原件与当前稿件对照，禁止修改稿件、方案、确认、运行命令或制作后续阶段。');
      }
      return;
    }
    if(!['bash','write','edit','apply_patch','kgxc_course_update','kgxc_course_export'].includes(name)&&!(name==='kgxc_course_source_coverage'&&args.action==='save'))return;
    const path=args.course_path||[...bindings].find(([,agent])=>agent===producer)?.[0];if(!path)return;
    let stage=args.stage||args.purpose;
    if(!STAGES.includes(stage)&&stage!=='outline'){
      const value=await tool('kgxc_course_status',{course_path:path});
      stage=value.workflow?.gates?.find(gate=>gate.status!=='confirmed')?.id||'final';
    }
    if(stage==='questions')return;
    const coverageOnly=name==='kgxc_course_source_coverage';
    await handle.production({course_path:path,producer,stage,phase:'start',...coverageOnly?{scope:'source-coverage',auto_review:false}:{},execution:[{type:'production/request',operation:coverageOnly?'source-coverage':'conversation-tool',call_id:randomUUID(),agent_id:identity(producer).id,stage}]});
  };
  handle.active=()=>tasks.size+workTasks.size;
  handle.whenIdle=async()=>{
    for(let boundary=0;boundary<64;boundary++){
      await Promise.allSettled([...idleTasks.values()]);await Promise.all([...tasks.values(),...workTasks.values()].map(task=>task.promise));
      await Promise.allSettled([...productions.values()].flatMap(item=>[item.tail,item.exportTask].filter(Boolean)));
      if(!tasks.size&&!workTasks.size&&!idleTasks.size)return;
    }
    throw Error('自动审阅等待超过边界保护，保留全部调用和成果。');
  };
  handle.dispose=async()=>{
    disposed=true;for(const task of tasks.values())task.controller.abort(Error('插件已停止，成果与用量保留，不自动重放。'));
    for(const item of productions.values())if(!item.finished&&!item.stopped)await stop(item,'插件已停止，制作和监督中断，不自动重放。');await handle.whenIdle();
  };
  ctx.effect?.(()=>()=>{void handle.dispose();},'kgxc-course: cancel independent review and supervision on unload');return handle;
}
