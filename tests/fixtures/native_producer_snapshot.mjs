// Installed native Agent/LLM services; every adapter response is synthetic.
// No network, account, production course or installed settings are used.
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {mkdtemp,rm,realpath,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {producerQASnapshot,producerReadOnlyTools} from '../../plugin/producer-qa-snapshot.mjs';
import {FIXED_ROUTE,sessionCallAudit} from '../../plugin/isolated-review-agent.mjs';
const base=process.env.KGXC_DSH_NATIVE_ROOT||'/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai/';
const load=async name=>import(base+name+'/lib/index.js');
const {Context}=await load('cordis'),ctx=new Context(),fibers=[],calls=[],signals=new Map();
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const hash=value=>createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const mount=async(plugin,config)=>{const fiber=ctx.plugin(plugin,config);fibers.push(fiber);await fiber.await();};
for(const name of ['dsh-session','dsh-session-projection','dsh-agent','dsh-llm','dsh-system-prompt','dsh-tools','dsh-agent-loop'])await mount((await load(name)).default);
await mount(await load('dsh-time-context'),{refreshIntervalMs:0});
await mount(scope=>scope.provide('fs',{resolve:async path=>realpath(path),stat:async path=>({type:(await stat(path)).isDirectory()?'directory':'file'}),processPath:path=>path}));
await mount((await load('dsh-working-directory')).default,{defaultDirectory:tmpdir()});
await mount((await load('dsh-skill')).default);await mount(await load('dsh-tool-skill'));
ctx.skills.register({name:'synthetic-qa-skill',description:'SYNTHETIC_SKILL_CATALOG_SENTINEL',content:'Synthetic instructions, never loaded during QA.'});
const catalogs=[];
ctx.on('agent/pre-step',async(payload,next)=>{const decision=await next();catalogs.push(...decision.messages.filter(item=>item.source.kind==='skill-catalog'));return decision;},{prepend:true});
let preparations=0;
ctx.llm.registerAdapter([FIXED_ROUTE.provider],{providerInfo:provider=>({id:provider,name:'Synthetic no-network adapter'}),providerRetryPolicy:()=>({mode:'normal',maxRetries:0,retryableCodes:[],initialDelayMs:1,maxDelayMs:1,jitterRatio:0}),
  prepareCall:async(provider,model)=>{const preparedId=++preparations;return {model:{id:model,provider,name:model,inputModalities:['text'],reasoning:{efforts:[{id:'xhigh',name:'Extra High'}],defaultEffort:'xhigh'}},stream:async function*(request){
    calls.push({preparedId,request});assert.equal(request.provider,FIXED_ROUTE.provider);assert.equal(request.model,FIXED_ROUTE.model);
    const qa=request.messages.find(item=>item.source?.kind==='kgxc-producer-qa'),subject=ctx.agents.get(request.sessionId);
    if(qa?.content[0].text.includes('CASE_LATE_USER')){subject.steer({id:'late-qa-user',role:'user',source:{kind:'user'},content:[{type:'text',text:'NEW_QA_USER_INPUT'}]});yield {type:'text-delta',index:0,text:'must not finish old QA'};return;}
    if(qa?.content[0].text.includes('CASE_FAKE_CATALOG')){const copy=structuredClone(catalogs.find(item=>item.source.update===true));assert.ok(copy);copy.id='forged-qa-catalog';subject.inject(copy);yield {type:'text-delta',index:0,text:'must not ignore forged source'};return;}
    if(qa?.content[0].text.includes('CASE_UNKNOWN_INPUT')){subject.inject({id:'unknown-qa-input',role:'user',source:{kind:'unknown-runtime'},content:[{type:'text',text:'UNKNOWN_INPUT'}]});yield {type:'text-delta',index:0,text:'must not ignore unknown source'};return;}
    const text={summary:'synthetic native producer response',items:[],repairs:[]};
    yield {type:'text-delta',index:0,text:JSON.stringify(text)};yield {type:'usage',usage:{inputTokens:12,outputTokens:8,totalTokens:20}};yield {type:'finish',reason:{kind:'stop'}};
  }};}});
ctx.tools.register({name:'ordinary_read',description:'ordinary synthetic capability',parameters:{type:'object'},output:{schema:{type:'object'},render:()=>[]},execute:()=>{throw Error('no execution allowed in fixture');}});
ctx.tools.setExecutor({describe:definitions=>({schemas:definitions.map(({name,description,parameters})=>({name,description,parameters}))}),execute:async()=>{throw Error('no execution allowed in fixture');}});
ctx.on('agent/pre-step',async(payload,next)=>{signals.set(payload.agent.id,payload.signal);return next();});
const root=await mkdtemp(join(tmpdir(),'kgxc-native-producer-snapshot-'));
const native=await ctx.agents.create({sessionId:'native-original-producer-'+randomUUID(),agentOptions:{...FIXED_ROUTE,reasoningEffort:'xhigh',maxTokens:731},meta:{cwd:root},setup:(scope)=>{
  scope.systemPrompt.section({name:'snapshot:system',order:0,complete:true,interpolate:false,text:'PRODUCER_SYSTEM_SENTINEL'});
  scope.on('agent/request',async(_payload,next)=>({...await next(),temperature:.23,stop:['KEEP_STOP']}),{prepend:true});
}});
const producer=native.agent,ordinaryExecutor=producer.ctx.tools.selectExecutor(producer),send=async(agent,text,source='user')=>{agent.followup({id:randomUUID(),role:'user',source:{kind:source},content:[{type:'text',text}]});await agent.whenIdle();};
const disposers=[],extra=[];let snapshot,other;
try{
  await send(producer,'OLD_QA_SENTINEL '+'.'.repeat(4096));
  assert.ok(producer.session.log.some(event=>event.type==='user/message'&&event.data.source.kind==='skill-catalog'&&!event.data.source.update));
  producer.session.append('tool/result',{turn:1,step:1,message:{id:randomUUID(),role:'tool',source:{kind:'tool',callId:'old-render'},toolCallId:'old-render',content:[{type:'text',text:'OLD_RENDER_TOOL_SENTINEL '+'.'.repeat(4096)}]}},{surfaceOp:'append'});
  const prefixLength=producer.session.log.length,prefix=JSON.stringify(producer.session.log),originalSystems=producer.session.deriveMessages().filter(message=>message.role==='system');
  const packet={protocol:'course-producer-qa/1',role:'producer',stage:'storyboard',run_id:'native-run',binding:{stage:'storyboard',run_id:'native-run',packet_sha256:'b'.repeat(64)},input:{text:'CURRENT_QA_PACKET'},native:[{text:'COMPLETE_CURRENT_PACKET'}]};
  const message={id:randomUUID(),role:'user',source:{kind:'kgxc-producer-qa'},content:[{type:'text',text:'PRODUCER_PROMPT_SENTINEL\n\n'+JSON.stringify(packet)}]};
  disposers.push(producer.ctx.tools.restrict({allow:[]}));disposers.push(producer.ctx.tools.guard(()=> 'read only'));disposers.push(await producerReadOnlyTools(producer));
  snapshot=producerQASnapshot(producer,{message,packet,signal:new AbortController().signal});
  other=await ctx.agents.create({sessionId:'native-unaffected-agent-'+randomUUID(),agentOptions:FIXED_ROUTE,meta:{cwd:root}});
  await send(other.agent,'OTHER_AGENT_SENTINEL');
  assert.ok(calls.at(-1).request.tools.some(tool=>tool.name==='ordinary_read'));assert.match(JSON.stringify(calls.at(-1).request.messages),/OTHER_AGENT_SENTINEL/);
  producer.followup(message);await producer.whenIdle();
  const receipt=snapshot.assertObserved(),wire=calls.at(-1).request;
  assert.equal(wire.sessionId,producer.session.id);assert.equal(ctx.agents.get(producer.session.id),producer);assert.equal(wire.signal,signals.get(producer.id));
  assert.deepEqual(Object.fromEntries(['provider','model','reasoningEffort','temperature','maxTokens','stop'].map(key=>[key,wire[key]])),{...FIXED_ROUTE,reasoningEffort:'xhigh',temperature:.23,maxTokens:731,stop:['KEEP_STOP']});
  assert.deepEqual(wire.tools,[]);assert.deepEqual(wire.toolHistory,{tools:[],updates:[]});
  assert.equal(hash(wire.messages),receipt.outbound_messages_sha256,'audit hash describes the actual adapter input');
  assert.equal(wire.messages.filter(item=>item.role==='system')[0],originalSystems[0]);
  assert.deepEqual(wire.messages.map(item=>item.role),['system','user']);
  assert.match(JSON.stringify(wire.messages),/PRODUCER_SYSTEM_SENTINEL/);
  assert.match(JSON.stringify(wire.messages),/COMPLETE_CURRENT_PACKET/);assert.doesNotMatch(JSON.stringify(wire.messages),/OLD_QA_SENTINEL|OLD_RENDER_TOOL_SENTINEL/);
  assert.doesNotMatch(JSON.stringify(wire.messages),/SYNTHETIC_SKILL_CATALOG_SENTINEL|skill-catalog/);assert.equal(receipt.managed_context_suppressions.length,1);assert.equal(receipt.managed_context_suppressions[0].reason,'native-hidden-skill-tool-empty-update');
  assert.ok(catalogs.some(item=>item.source.update===true&&item.source.entries.length===0),'the installed native middleware actually generated the managed empty update');
  assert.equal(producer.session.log.slice(prefixLength).some(event=>event.type==='user/message'&&event.data.source.kind==='skill-catalog'),false,'QA suppression does not rewrite or publish catalog history');
  assert.ok(producer.session.deriveMessages().some(item=>item.source?.kind==='time-context'));assert.equal(wire.messages.some(item=>item.source?.kind==='time-context'),false);
  assert.equal(JSON.stringify(producer.session.log.slice(0,prefixLength)),prefix);
  assert.match(JSON.stringify(producer.session.deriveMessages()),/OLD_QA_SENTINEL/);assert.match(JSON.stringify(producer.session.deriveMessages()),/OLD_RENDER_TOOL_SENTINEL/);
  const audit=sessionCallAudit(producer,FIXED_ROUTE,{fromSeq:prefixLength-1,role:'producer',outbound_projection:receipt}).audit;
  assert.equal(audit.input_scope,'producer-qa-snapshot');assert.equal(audit.input_messages.length,1);assert.equal(audit.input_messages[0].id,message.id);assert.ok(receipt.excluded_history_count>0);
  await snapshot.dispose();snapshot=null;for(const dispose of disposers.reverse())await dispose();disposers.length=0;
  assert.equal(producer.ctx.tools.selectExecutor(producer),ordinaryExecutor);
  ctx.skills.register({name:'synthetic-qa-added',description:'SYNTHETIC_SKILL_REFRESH_SENTINEL',content:'Synthetic updated instructions.'});
  await send(producer,'NORMAL_TURN_AFTER_QA');
  const ordinary=calls.at(-1).request;assert.match(JSON.stringify(ordinary.messages),/OLD_QA_SENTINEL/);assert.match(JSON.stringify(ordinary.messages),/NORMAL_TURN_AFTER_QA/);assert.ok(ordinary.tools.some(tool=>tool.name==='ordinary_read'));
  assert.ok(ordinary.tools.some(tool=>tool.name==='skill'));assert.match(JSON.stringify(ordinary.messages),/SYNTHETIC_SKILL_REFRESH_SENTINEL/);assert.ok(producer.session.log.some(event=>event.type==='user/message'&&event.data.source.kind==='skill-catalog'&&event.data.source.update===true&&event.data.source.entries.length===2));
  const secondMessage={...message,id:randomUUID()};
  disposers.push(producer.ctx.tools.restrict({allow:[]}));disposers.push(producer.ctx.tools.guard(()=> 'read only'));disposers.push(await producerReadOnlyTools(producer));
  await assert.rejects(producer.ctx.tools.selectExecutor(producer).execute({}),/没有工具执行/);
  snapshot=producerQASnapshot(producer,{message:secondMessage,packet,signal:new AbortController().signal});
  producer.followup(secondMessage);await producer.whenIdle();assert.equal(snapshot.assertObserved().managed_context_suppressions.length,1);
  assert.deepEqual(calls.at(-1).request.tools,[]);assert.deepEqual(calls.at(-1).request.toolHistory,{tools:[],updates:[]});
  await snapshot.dispose();snapshot=null;for(const dispose of disposers.reverse())await dispose();disposers.length=0;
  assert.equal(producer.ctx.tools.selectExecutor(producer),ordinaryExecutor);await send(producer,'NORMAL_TURN_AFTER_SECOND_QA');
  assert.ok(calls.at(-1).request.tools.some(tool=>tool.name==='ordinary_read'));
  assert.equal(preparations,calls.length,'one native prepared handle per dispatch, no additional LLM call');
  const create=async()=>{const handle=await ctx.agents.create({sessionId:'native-negative-qa-'+randomUUID(),agentOptions:FIXED_ROUTE,meta:{cwd:root},setup:scope=>{scope.systemPrompt.section({name:'negative:system',order:0,complete:true,interpolate:false,text:'ORIGINAL_NEGATIVE_QA_SYSTEM'});}});extra.push(handle);await send(handle.agent,'seed native skill catalog');return handle.agent;};
  for(const mode of ['CASE_LATE_USER','CASE_FAKE_CATALOG','CASE_UNKNOWN_INPUT']){
    const actor=await create(),input={...message,id:randomUUID(),content:[{type:'text',text:mode+'\n'+message.content[0].text}]},cleanup=[actor.ctx.tools.restrict({allow:[]}),actor.ctx.tools.guard(()=> 'QA readonly'),await producerReadOnlyTools(actor)];
    snapshot=producerQASnapshot(actor,{message:input,packet,signal:new AbortController().signal});actor.followup(input);await actor.whenIdle();
    assert.equal(actor.session.log.filter(event=>event.type==='turn/end').at(-1).data.reason.kind,'aborted');assert.ok(actor.inbox.nextStep.length>0,'real/forged/unknown incoming input remains pending');
    await snapshot.dispose();snapshot=null;for(const dispose of cleanup.reverse())await dispose();
  }
  const pendingActor=await create(),forged=structuredClone(catalogs.find(item=>item.source.update===true));forged.id='pending-forged-catalog';pendingActor.inject(forged);const pendingBefore=JSON.stringify(pendingActor.inbox.nextStep),beforePending=calls.length;
  assert.throws(()=>producerQASnapshot(pendingActor,{message:{...message,id:randomUUID()},packet,signal:new AbortController().signal}),/待处理的新对话/);assert.equal(calls.length,beforePending);assert.equal(JSON.stringify(pendingActor.inbox.nextStep),pendingBefore);
  const executionActor=await create(),executionMessage={...message,id:randomUUID()},cleanup=[executionActor.ctx.tools.restrict({allow:[]}),executionActor.ctx.tools.guard(()=> 'QA readonly'),await producerReadOnlyTools(executionActor)],beforeExecution=calls.length;
  const injectExecution=executionActor.ctx.on('agent/request',async(_payload,next)=>{const config=await next();executionActor.session.append('tool/result',{turn:2,step:1,message:{id:'untrusted-execution',role:'tool',source:{kind:'tool',callId:'untrusted-call'},toolCallId:'untrusted-call',content:[{type:'text',text:'UNKNOWN_EXECUTION_RESULT'}]}},{surfaceOp:'append'});return config;},{prepend:true});
  snapshot=producerQASnapshot(executionActor,{message:executionMessage,packet,signal:new AbortController().signal});executionActor.followup(executionMessage);await executionActor.whenIdle();assert.equal(calls.length,beforeExecution);assert.ok(executionActor.session.log.some(event=>event.type==='tool/result'&&event.data.message.id==='untrusted-execution'));await snapshot.dispose();snapshot=null;await injectExecution();for(const dispose of cleanup.reverse())await dispose();
  producer.session.append('developer/message',{turn:3,step:1,message:{id:randomUUID(),role:'developer',source:{kind:'system-prompt'},content:[{type:'text',text:'CURRENT_DEVELOPER_CONSTRAINT'}]}},{surfaceOp:'append'});
  assert.equal(producer.session.deriveMessages().at(-1).role,'developer');
  const beforeBlocked=calls.length,protectedPrefix=JSON.stringify(producer.session.log),protectedPrefixLength=producer.session.log.length;
  const blockedMessage={...message,id:randomUUID()};
  disposers.push(producer.ctx.tools.restrict({allow:[]}));disposers.push(producer.ctx.tools.guard(()=> 'read only'));disposers.push(await producerReadOnlyTools(producer));
  snapshot=producerQASnapshot(producer,{message:blockedMessage,packet,signal:new AbortController().signal});
  producer.followup(blockedMessage);await producer.whenIdle();
  assert.equal(calls.length,beforeBlocked,'unsupported current developer instructions stop before adapter dispatch');
  assert.match(producer.session.log.filter(event=>event.type==='turn/end').at(-1).data.reason.error.message,/无法.*保留.*developer.*系统约束/);
  assert.equal(snapshot.receipt,null);assert.equal(JSON.stringify(producer.session.log.slice(0,protectedPrefixLength)),protectedPrefix);
  console.log(JSON.stringify({ok:true,network_inference_calls:0,native_dispatches:calls.length,preparations,producer_id:producer.id,qa_session_id:wire.sessionId,preserved_history_prefix_sha256:createHash('sha256').update(prefix).digest('hex'),excluded_history_count:receipt.excluded_history_count,config_preserved:true,signal_preserved:true,system_identity_preserved:true,other_agent_unchanged:true,next_ordinary_turn_restored:true,consecutive_qa_restored:true,automatic_time_context_excluded:true,native_skill_catalog_suppressed:true,native_skill_catalog_restored:true,forged_catalog_rejected:true,pending_input_retained:true,late_user_stopped:true,unknown_execution_rejected:true,current_developer_fail_closed:true,audit_scope:audit.input_scope}));
}finally{await snapshot?.dispose();for(const dispose of disposers.reverse())await dispose();for(const handle of extra.reverse())await handle.dispose();await other?.dispose();await native.dispose();for(const fiber of fibers.reverse())await fiber.dispose?.();await rm(root,{recursive:true,force:true});}
