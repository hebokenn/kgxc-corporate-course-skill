import {createHash} from 'node:crypto';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
export const reviewInputSHA=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const equal=(a,b)=>a===undefined||b===undefined?a===b:reviewInputSHA(a)===reviewInputSHA(b);
export function freezeReviewInput(value){
  const freeze=item=>{if(item&&typeof item==='object'){for(const child of Object.values(item))freeze(child);Object.freeze(item);}return item;};
  return freeze(structuredClone(value));
}

// A model body is kept separately. Only genuinely absent binding is filled;
// present invalid values (including null/false) must never be repaired here.
export function reviewResultEnvelope(body,{binding,receipt,audit}){
  if(receipt?.registration_bound!==true||receipt.boundary_observed!==true||!equal(receipt.binding,binding))throw Error('审阅缺少本次冻结输入的原生调用边界，不能附加成果绑定。');
  if(Object.hasOwn(body,'binding')&&!equal(body.binding,binding))throw Error('审阅正文返回了错误的成果绑定；宿主不能覆盖或追认。');
  const result=structuredClone(body);
  if(!Object.hasOwn(body,'binding'))result.binding=structuredClone(binding);
  result.agent_audit={...audit,binding_host:{protocol:'course-review-host-binding/1',
    source:Object.hasOwn(body,'binding')?'model-present-verified':'host-attached-missing',binding_sha256:reviewInputSHA(binding),
    request_boundary_protocol:receipt.protocol,request_boundary_sha256:reviewInputSHA(receipt),
    observation_scope:'registration-bound native llm/stream application boundary; not final HTTP bytes'}};
  return result;
}

// Validate without rewriting the native request, provider or session surface.
// The owned content includes native durable image refs exactly as created;
// adapter image conversion happens later and is not claimed by this receipt.
export function isolatedReviewBoundary(agentCtx,agent,{message,packet,prompt,role,signal,requireRoute}){
  if(!agentCtx?.on||!agent?.session?.id||!['reviewer','supervisor'].includes(role)||message?.source?.kind!=='kgxc-isolated-'+role)throw Error('独立审阅缺少精确原生输入身份。');
  const owned=freezeReviewInput(message),frozenPacket=freezeReviewInput(packet),sessionId=agent.session.id,disposers=[];
  if(owned.content?.[0]?.type!=='text'||owned.content[0].text!==JSON.stringify(frozenPacket)||!frozenPacket.binding)throw Error('独立审阅输入与冻结资料包不一致。');
  let disposed=false,used=false,requestAtEntry,entrySHA,receipt=null;
  const live=()=>{signal.throwIfAborted();if(disposed)throw Error('独立审阅调用边界已结束。');};
  const check=(request,config)=>{
    live();requireRoute(request);requireRoute(config);
    if(request.sessionId!==sessionId||!request.signal)throw Error('独立审阅原生调用身份或取消信号改变。');
    for(const [key,value] of Object.entries(config))if(!equal(request[key],value))throw Error('独立审阅原生调用配置改变：'+key);
    if((request.tools||[]).length||request.toolHistory?.tools?.length||request.toolHistory?.updates?.length)throw Error('独立审阅原生请求包含工具或工具历史。');
    const messages=request.messages;
    if(!Array.isArray(messages)||messages.length!==2||messages[0].role!=='system'||messages[0].source?.kind!=='system-prompt'
        ||!equal(messages[0].content,[{type:'text',text:prompt}])||!equal(messages[1],owned))throw Error('独立审阅实际原生输入或角色提示与冻结内容不一致。');
  };
  disposers.push(agentCtx.on('llm/stream',(request,next)=>{
    if(request.sessionId!==sessionId)return next();
    if(request!==requestAtEntry||reviewInputSHA(request.messages)!==entrySHA)throw Error('独立审阅下游请求未通过本次冻结输入边界或已被篡改。');
    check(request,receipt.config);
    receipt=freezeReviewInput({...receipt,boundary_observed:true});
    return next();
  },{prepend:true}));
  disposers.push(agentCtx.on('internal/get',(_reader,name,_error,next)=>{
    const service=next();if(name!=='llm'||!service)return service;
    return new Proxy(service,{get(target,key){
      const native=Reflect.get(target,key,target);if(key!=='prepareCall')return native;
      return async(...args)=>{
        const prepared=await Reflect.apply(native,target,args);
        if(disposed)return prepared;
        if(!prepared?.config||typeof prepared.stream!=='function')throw Error('独立审阅没有 registration-bound prepared stream。');
        return Object.freeze({...prepared,stream:request=>{
          if(request.sessionId!==sessionId)return prepared.stream(request);
          live();if(used)throw Error('独立审阅冻结输入只能调用一次。');
          check(request,prepared.config);requestAtEntry=request;entrySHA=reviewInputSHA(request.messages);used=true;
          receipt={protocol:'course-isolated-review-input/1',session_id:sessionId,owned_message_id:owned.id,
            binding:structuredClone(frozenPacket.binding),packet_sha256:reviewInputSHA(frozenPacket),
            owned_message_sha256:reviewInputSHA(owned),native_messages_sha256:entrySHA,
            system_prompt_sha256:reviewInputSHA(request.messages[0].content),config:structuredClone(prepared.config),
            registration_bound:true,boundary_observed:false,request_rewritten:false,session_history_mutated:false,
            tools:[],tool_history:{tools:[],updates:[]},
            observation_scope:'native prepared.stream -> llm/stream application boundary before adapter conversion; not final HTTP bytes'};
          const stream=prepared.stream(request);
          if(!receipt.boundary_observed)throw Error('独立审阅 llm/stream 未观察本次原生请求，不能附加绑定。');
          return stream;
        }});
      };
    }});
  },{prepend:true}));
  return {get receipt(){return receipt;},assertObserved(events){
    live();if(!used||!receipt?.boundary_observed)throw Error('独立审阅没有可核对的本次原生请求边界。');
    if(events.some(event=>['tool/call','tool/result','developer/message','forked','session/end-seed'].includes(event.type))
        ||events.filter(event=>event.type==='step/start').length!==1)throw Error('独立审阅实际调用含有额外步骤、工具或历史上下文。');
    const systems=events.filter(event=>event.type==='system/message');
    if(systems.length!==1||!equal(systems[0].data.message?.content,[{type:'text',text:prompt}]))throw Error('独立审阅实际角色提示记录与冻结内容不一致。');
    const users=events.filter(event=>event.type==='user/message');
    if(users.length!==1||users[0].data.id!==owned.id||!equal(users[0].data.content,owned.content)||!equal(users[0].data.source,owned.source))throw Error('独立审阅实际原生记录与冻结输入不一致。');
    return receipt;
  },async dispose(){disposed=true;for(const dispose of disposers.reverse())await dispose();}};
}
