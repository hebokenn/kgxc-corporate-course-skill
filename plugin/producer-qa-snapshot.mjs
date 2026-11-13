import {createHash} from 'node:crypto';
import {requireRoute,denyAllExecutor} from './isolated-review-agent.mjs';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const sha=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const messageMeta=message=>({id:message.id,role:message.role,source:message.source?.kind,sha256:sha(message.content)});
const automaticSources=new Set(['runtime-context','time-context','agent-instructions','working-directory','model-selection','tool-registry']);
const executorRestorations=new WeakMap();
// dsh-tool-skill emits this exact replacement when its original skill tool is
// hidden but a catalog was already published. It is not a required context.
const EMPTY_SKILL_UPDATE=['<system-reminder>','The available skill catalog changed. This complete catalog replaces every earlier available-skills list in this session:','','<available_skills>','</available_skills>','','No skills are currently available through the `skill` tool. Do not use names from earlier skill catalogs.',"A user may still invoke a skill directly; its <skill_content> block then appears in this conversation. Follow it, and do not call the `skill` tool for it.",'</system-reminder>'].join('\n');

// Native setExecutor unloading intentionally leaves an unavailable selection.
// Restore the exact previous provider, and only replace a restoration layer
// that this helper itself installed on an earlier QA turn.
export async function producerReadOnlyTools(producer){
  const tools=producer.ctx?.tools;
  if(!tools?.selectExecutor||!tools?.setExecutor)throw Error('原生制作端无法读取及恢复工具执行器，停止只读 QA。');
  const previous=tools.selectExecutor(producer),owned=executorRestorations.get(producer);
  if(owned&&owned.executor!==previous)throw Error('制作端工具执行器已被其他操作改变，不接管当前 QA。');
  if(owned){await owned.dispose();executorRestorations.delete(producer);}
  let dispose;
  try{dispose=tools.setExecutor(denyAllExecutor());}
  catch(error){if(owned)executorRestorations.set(producer,{executor:previous,dispose:tools.setExecutor(previous)});throw error;}
  let restored=false;
  return async()=>{
    if(restored)return;restored=true;await dispose();
    executorRestorations.set(producer,{executor:previous,dispose:tools.setExecutor(previous)});
  };
}

// Only the original registration-bound prepared handle is dispatched. No
// Session surface, durable event, provider registration or model is replaced.
export function producerQASnapshot(producer,{message,packet,signal,onProjection}){
  const selectedRoute=requireRoute(producer.model?.current?.()||producer.options);
  if(!producer?.ctx?.on||!producer.session?.id||message?.source?.kind!=='kgxc-producer-qa'||!packet?.run_id||!['script','storyboard','pilot','final'].includes(packet.stage)||packet.binding?.run_id!==packet.run_id||packet.binding?.stage!==packet.stage)throw Error('制作端 QA 缺少精确身份、当前消息或成果绑定，不能投影请求。');
  const expected=sha(message),sessionId=producer.session.id,disposers=[],fromSeq=[...producer.session.log].at(-1)?.seq??-1,suppressed=[];
  const automatic=input=>['user','developer'].includes(input.role)&&automaticSources.has(input.source?.kind);
  if([...(producer.inbox?.nextStep||[]),...(producer.inbox?.nextTurn||[])].some(input=>input.id!==message.id&&!automatic(input)))throw Error('制作端 QA 前仍有待处理的新对话；输入保留，不启动旧快照。');
  let disposed=false,interrupted=false,used=false,receipt=null,boundaryObserved=false,projectedRequest;
  const assertLive=()=>{signal.throwIfAborted();if(disposed||interrupted)throw Error('制作端 QA 请求投影已结束或收到新输入，不能继续调用。');};
  const interrupt=()=>{interrupted=true;producer.cancel({kind:'user',message:'制作端 QA 收到新的对话或执行输入，停止旧快照。'},{keepInbox:true});};
  disposers.push(producer.ctx.on('agent/inbox/inserted',({agent,message:input})=>{if(agent===producer&&input?.id!==message.id&&!automatic(input))interrupt();}));
  disposers.push(producer.ctx.on('agent/pre-step',async(payload,next)=>{
    if(payload.agent!==producer)return next();assertLive();
    // Inspect claimed input BEFORE the native skill middleware can replace or
    // remove an existing catalog-shaped message.
    if(payload.messages.some(input=>input.id!==message.id&&!automatic(input))){interrupt();throw Error('制作端 QA 收到未授权输入，保留新消息并停止旧快照。');}
    const decision=await next();assertLive();if(decision.kind==='reject')return decision;
    const claimed=new Set(payload.messages.map(input=>input.id)),history=[...producer.session.log];
    const published=history.some(event=>event.type==='user/message'&&event.data.source?.kind==='skill-catalog'&&Array.isArray(event.data.source.entries));
    const managed=typeof producer.ctx.tools?.get==='function'&&producer.ctx.tools.get('skill',producer)===undefined&&published?decision.messages.filter(input=>
      input.role==='user'&&!claimed.has(input.id)&&!history.some(event=>event.type==='user/message'&&event.data.id===input.id)&&
      Object.keys(input.source||{}).sort().join(',')==='entries,form,kind,update'&&input.source.kind==='skill-catalog'&&input.source.form==='catalog'&&input.source.update===true&&Array.isArray(input.source.entries)&&input.source.entries.length===0&&
      input.content?.length===1&&input.content[0].type==='text'&&input.content[0].text===EMPTY_SKILL_UPDATE):[];
    if(managed.length!==1)return decision;
    suppressed.push({...messageMeta(managed[0]),agent_id:producer.id||sessionId,turn:payload.turn,step:payload.step,reason:'native-hidden-skill-tool-empty-update'});
    return {...decision,messages:decision.messages.filter(input=>input!==managed[0])};
  },{prepend:true}));
  disposers.push(producer.ctx.on('llm/stream',(request,next)=>{
    if(request.sessionId!==sessionId)return next();
    assertLive();
    if(request!==projectedRequest)throw Error('制作端 QA 下游请求没有经过本次受控快照，停止调用。');
    if((request.tools||[]).length||request.toolHistory?.tools?.length||request.toolHistory?.updates?.length)throw Error('制作端 QA 下游仍包含工具或工具历史。');
    boundaryObserved=true;receipt.boundary_observed=true;
    const stream=next();
    return (async function*(){await onProjection?.(receipt);for await(const chunk of stream){assertLive();yield chunk;}})();
  },{prepend:true}));
  disposers.push(producer.ctx.on('internal/get',(_reader,name,_error,next)=>{
    const service=next();if(name!=='llm'||!service)return service;
    return new Proxy(service,{get(target,key){
      const native=Reflect.get(target,key,target);
      if(key!=='prepareCall')return native;
      return async(...args)=>{
        // Loop contexts can retain this facade. A later ordinary turn uses
        // the original service after the QA scope has been disposed.
        if(disposed)return Reflect.apply(native,target,args);
        const prepared=await Reflect.apply(native,target,args);
        if(!prepared?.config||typeof prepared.stream!=='function')throw Error('原生模型没有提供 registration-bound prepared stream，不能执行 QA 快照。');
        return Object.freeze({...prepared,stream:request=>{
          if(request.sessionId!==sessionId)return prepared.stream(request);
          assertLive();if(used)throw Error('制作端 QA 快照已经使用，不重复执行或接管后续对话。');
          requireRoute(request,selectedRoute);requireRoute(prepared.config,selectedRoute);
          for(const [key,value] of Object.entries(prepared.config))if(JSON.stringify(request[key])!==JSON.stringify(value))throw Error('制作端 QA 原生调用配置发生变化：'+key);
          if((request.tools||[]).length)throw Error('制作端 QA 原生请求暴露了执行工具。');
          if(!Array.isArray(request.messages)||!request.signal)throw Error('制作端 QA 原生请求缺少完整消息或取消信号。');
          const owned=request.messages.filter(item=>item.id===message.id);
          if(owned.length!==1||sha(owned[0])!==expected)throw Error('制作端 QA 当前消息与完整冻结资料包不一致。');
          const developers=request.messages.filter(item=>item.role==='developer');
          // This installed Runtime drops developer messages when projecting an
          // empty tool history. Do not silently discard current constraints or
          // change their role to make that projection accept them.
          if(developers.some(item=>item.source?.kind!=='tool-registry'))throw Error('原生 Runtime 无法在空工具历史下保留本次 developer 系统约束，制作端 QA 在 dispatch 前停止。');
          const instructions=request.messages.filter(item=>item.role==='system');
          const systems=instructions.filter(item=>item.role==='system');
          if(!systems.length||systems.some(item=>!Array.isArray(item.content)||item.content.some(block=>block.type!=='text')))throw Error('无法完整保留制作端当前原生系统指令。');
          const position=request.messages.indexOf(owned[0]);
          if([...producer.session.log].some(event=>event.seq>fromSeq&&(['tool/call','tool/result','assistant/message'].includes(event.type)||event.type==='user/message'&&event.data.id!==message.id&&!automatic(event.data)))){interrupt();throw Error('制作端 QA 期间收到新的对话或执行结果，停止旧快照。');}
          for(const item of request.messages.slice(position+1))if(!instructions.includes(item)&&!(automaticSources.has(item.source?.kind)&&['user','developer'].includes(item.role)))throw Error('制作端 QA 期间收到新的对话或执行结果，停止旧快照。');
          const messages=Object.freeze([...instructions,owned[0]]),toolHistory=Object.freeze({tools:Object.freeze([]),updates:Object.freeze([])});
          projectedRequest=Object.freeze({...request,messages,tools:Object.freeze([]),toolHistory});
          const excluded=request.messages.filter(item=>!messages.includes(item)),byRole={};
          for(const item of excluded)byRole[item.role]=(byRole[item.role]||0)+1;
          receipt={protocol:'course-producer-qa-snapshot/1',session_id:sessionId,qa_message_id:message.id,stage:packet.stage,run_id:packet.run_id,binding:structuredClone(packet.binding),
            packet_sha256:sha(packet),outbound_image_count:owned[0].content.filter(block=>block.type==='image').length,qa_message_sha256:expected,native_messages_sha256:sha(request.messages),outbound_messages_sha256:sha(messages),
            native_message_count:request.messages.length,outbound_message_count:messages.length,excluded_history_count:excluded.length,excluded_history_by_role:byRole,
            input_messages:messages.filter(item=>item.role==='user').map(messageMeta),system_prompt_hashes:systems.map(item=>sha(item.content)),developer_instruction_hashes:instructions.filter(item=>item.role==='developer').map(item=>sha(item.content)),
            messages:messages.map(messageMeta),config:structuredClone(prepared.config),tools:[],tool_history:{tools:[],updates:[]},
            registration_bound:true,signal_preserved:projectedRequest.signal===request.signal,session_preserved:true,session_history_mutated:false,managed_context_suppressions:[...suppressed]};
          used=true;
          const stream=prepared.stream(projectedRequest);
          if(!boundaryObserved)throw Error('原生 llm/stream 未确认本次 QA 快照，停止调用。');
          return stream;
        }});
      };
    }});
  },{prepend:true}));
  return {get receipt(){return receipt;},assertObserved(){if(!used||!boundaryObserved||!receipt)throw Error('制作端 QA 没有可核对的实际出站快照。');return receipt;},
    async dispose(){disposed=true;for(const dispose of disposers.reverse())await dispose();}};
}
