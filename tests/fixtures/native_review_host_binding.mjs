// Installed native Agent + registration-bound LLM services. Synthetic adapters
// only: no production project, account, configuration, network or model calls.
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {mkdtemp,mkdir,writeFile,readFile,readdir,rm,realpath,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {readFileSync} from 'node:fs';
import {isolatedAgentRunner,FIXED_ROUTE,SUPERVISION_PROTOCOL} from '../../plugin/isolated-review-agent.mjs';
const base=process.env.KGXC_DSH_NATIVE_ROOT||'/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai/';
const load=async name=>import(base+name+'/lib/index.js');
const {Context}=await load('cordis'),ctx=new Context(),fibers=[],calls=[];
const mount=async(plugin,config)=>{const fiber=ctx.plugin(plugin,config);fibers.push(fiber);await fiber.await();};
for(const name of ['dsh-session','dsh-session-projection','dsh-agent','dsh-llm','dsh-system-prompt','dsh-tools','dsh-agent-loop'])await mount((await load(name)).default);
await mount(scope=>{
  scope.provide('fs',{resolve:async path=>realpath(path),stat:async path=>({type:(await stat(path)).isDirectory()?'directory':'file'}),processPath:path=>path});
  scope.provide('attachments',{saveImage:async({data,mediaType,name})=>({attachmentId:'sha256:'+createHash('sha256').update(data).digest('hex'),mediaType,name,bytes:data.length,width:1,height:1})});
});
await mount((await load('dsh-working-directory')).default,{defaultDirectory:tmpdir()});
let mode='missing',afterDispatch;
ctx.llm.registerAdapter([FIXED_ROUTE.provider],{providerInfo:provider=>({id:provider,name:'Synthetic no-network adapter'}),providerRetryPolicy:()=>({mode:'normal',maxRetries:0,retryableCodes:[],initialDelayMs:1,maxDelayMs:1,jitterRatio:0}),
  prepareCall:async(provider,model)=>({model:{id:model,provider,name:model,inputModalities:['text','image']},stream:async function*(request){
    calls.push(request);const owned=request.messages.find(message=>message.source?.kind?.startsWith('kgxc-isolated-'));
    if(!owned){yield {type:'text-delta',index:0,text:'ordinary synthetic response'};yield {type:'finish',reason:{kind:'stop'}};return;}
    const payload=JSON.parse(owned.content[0].text),body={summary:'synthetic native body',...payload.protocol===SUPERVISION_PROTOCOL?{passed:true,findings:[]}:{learner:{about:'synthetic',what_it_said:'synthetic',learned:[],confusions:[]},findings:[],items:[]}};
    if(mode==='correct')body.binding=payload.binding;
    if(mode==='wrong')body.binding={...payload.binding,operation_id:'wrong-operation'};
    if(mode==='null')body.binding=null;if(mode==='false')body.binding=false;
    await afterDispatch?.(request);
    yield {type:'text-delta',index:0,text:JSON.stringify(body)};yield {type:'usage',usage:{inputTokens:3,outputTokens:2,totalTokens:5}};yield {type:'finish',reason:{kind:'stop'}};
  }})});
ctx.tools.register({name:'normal_fixture_tool',description:'ordinary agent tool',parameters:{type:'object'},output:{schema:{type:'object'},render:()=>[]},execute:()=>{throw Error('fixture never executes tools');}});
ctx.tools.setExecutor({describe:definitions=>({schemas:definitions.map(({name,description,parameters})=>({name,description,parameters}))}),execute:()=>{throw Error('fixture never executes tools');}});
const root=await mkdtemp(join(tmpdir(),'kgxc-native-host-binding-'));await mkdir(join(root,'project'),{recursive:true});
const operation='produce-'+randomUUID(),packet={protocol:SUPERVISION_PROTOCOL,binding:{protocol:SUPERVISION_PROTOCOL,operation_id:operation,execution_sha256:'a'.repeat(64)},requirements:[],execution:[]};
const runner=isolatedAgentRunner(ctx),signal=new AbortController().signal;
const run=(extra={})=>runner({role:'supervisor',packet,course_path:root,selection:FIXED_ROUTE,signal,...extra});
let other;
try{
  if(process.argv.includes('--external-fixture-packet')){
    const external=JSON.parse(readFileSync(0,'utf8'));
    const value=await run({packet:external});
    console.log(JSON.stringify({...value,network_inference_calls:0}));
  }else{
  const first=await run();assert.deepEqual(first.result.binding,packet.binding);assert.equal(first.audit.binding_host.source,'host-attached-missing');
  assert.equal(first.audit.request_boundary.boundary_observed,true);assert.equal(first.audit.request_boundary.request_rewritten,false);
  const directory=join(root,'project/qa/ai-review/supervision',operation),raw=JSON.parse(await readFile(join(directory,first.audit.session_id+'.model.json'),'utf8'));
  const envelope=JSON.parse(await readFile(join(directory,first.audit.session_id+'.agent.json'),'utf8'));
  assert.equal(Object.hasOwn(raw.body,'binding'),false);assert.equal(JSON.parse(raw.text).summary,first.result.summary);assert.deepEqual(envelope.result.binding,packet.binding);
  mode='correct';assert.equal((await run()).audit.binding_host.source,'model-present-verified');
  for(mode of ['wrong','null','false']){
    await assert.rejects(run(),/错误的成果绑定/);
  }
  const logs=await readdir(directory),rejected=[];
  for(const file of logs.filter(name=>name.endsWith('.failure.json'))){const failure=JSON.parse(await readFile(join(directory,file),'utf8'));rejected.push(failure);const raw=JSON.parse(await readFile(join(directory,file.replace('.failure.json','.model.json')),'utf8'));assert.ok(Object.hasOwn(JSON.parse(raw.text),'binding'));}
  assert.equal(rejected.length,3);const rejectedPrefix=JSON.stringify(rejected);
  mode='missing';
  let beforeTamper=calls.length;
  let stop=ctx.on('agent/created',({agent})=>{
    agent.ctx.on('internal/get',(_reader,name,_error,next)=>{
      const service=next();if(name!=='llm')return service;
      return new Proxy(service,{get(target,key){const native=Reflect.get(target,key,target);if(key!=='prepareCall')return native;return async(...args)=>{const prepared=await Reflect.apply(native,target,args);return {...prepared,stream:request=>prepared.stream({...request,messages:request.messages.map(message=>message.role==='user'?{...message,content:[{type:'text',text:'TAMPERED_OWNED_PACKET'}]}:message)})};};}});
    },{prepend:true});
  });
  await assert.rejects(run(),/实际原生输入.*不一致/);await stop();assert.equal(calls.length,beforeTamper);
  afterDispatch=request=>ctx.agents.get(request.sessionId).session.append('tool/result',{turn:0,step:0,message:{id:randomUUID(),role:'tool',source:{kind:'tool',callId:'injected-execution'},toolCallId:'injected-execution',content:[{type:'text',text:'UNAUTHORIZED_EXECUTION_AFTER_DISPATCH'}]}},{surfaceOp:'append'});
  await assert.rejects(run(),/额外步骤、工具或历史上下文/);afterDispatch=undefined;
  assert.equal(calls.length,beforeTamper+1,'late native evidence is rejected after one real synthetic dispatch');beforeTamper=calls.length;
  stop=ctx.on('agent/created',({agent})=>agent.ctx.on('internal/get',(_reader,name,_error,next)=>{
    const service=next();if(name!=='llm')return service;
    return new Proxy(service,{get(target,key){const native=Reflect.get(target,key,target);if(key!=='prepareCall')return native;return async(...args)=>{
      const prepared=await Reflect.apply(native,target,args);return {...prepared,stream:request=>prepared.stream({...request})};
    };}});
  }));
  await assert.rejects(run(),/下游请求.*篡改/);await stop();assert.equal(calls.length,beforeTamper);
  stop=ctx.on('agent/created',({agent})=>agent.ctx.on('agent/request',async(payload,next)=>{
    const config=await next();agent.session.append('developer/message',{turn:0,step:0,message:{id:randomUUID(),role:'developer',source:{kind:'fixture-extra'},content:[{type:'text',text:'EXTRA_PRIVATE_CONTEXT'}]}},{surfaceOp:'append'});return config;
  },{prepend:true}));
  await assert.rejects(run(),/实际原生输入.*不一致/);await stop();assert.equal(calls.length,beforeTamper);
  // A changed caller object after creation must not replace the actual sent
  // frozen binding. Backend version checks are tested separately on real Review.
  const caller=structuredClone(packet),frozenBinding=structuredClone(caller.binding);
  const frozen=await run({packet:caller,onCreated:()=>{caller.binding.operation_id='late-caller-change';}});
  assert.deepEqual(frozen.result.binding,frozenBinding);
  // Native image refs are compared exactly; no normalization or extra text is
  // admitted. Bytes are synthetic and only prove the application input scope.
  const frameData=Buffer.from('synthetic image byte fixture'),frameSHA=createHash('sha256').update(frameData).digest('hex'),runId='native-image-'+randomUUID();
  const frameDir=join(root,'project/qa/ai-review',runId);await mkdir(frameDir,{recursive:true});await writeFile(join(frameDir,'frame.jpg'),frameData);
  const imagePacket={protocol:'course-blind-review/1',stage:'pilot',run_id:runId,fingerprint:'f',artifact_sha256:'b'.repeat(64),binding:{stage:'pilot',run_id:runId,packet_sha256:'c'.repeat(64)},review_contract:{},checklist:[],input:{},evidence:{frames:[],media:[],limitations:[]},allowed_artifacts:[{id:'frame',kind:'frame',sha256:frameSHA,path:'qa/ai-review/'+runId+'/frame.jpg'}]};
  const image=await run({role:'reviewer',packet:imagePacket});const actual=calls.at(-1).messages[1].content;
  assert.equal(actual.length,3);assert.equal(actual[2].type,'image');assert.equal(actual[2].attachment.attachmentId,'sha256:'+frameSHA);assert.deepEqual(image.audit.artifact_ids,['frame']);
  stop=ctx.on('agent/created',({agent})=>agent.ctx.on('internal/get',(_reader,name,_error,next)=>{
    const service=next();if(name!=='llm')return service;
    return new Proxy(service,{get(target,key){const native=Reflect.get(target,key,target);if(key!=='prepareCall')return native;return async(...args)=>{const prepared=await Reflect.apply(native,target,args);return {...prepared,stream:request=>prepared.stream({...request,messages:request.messages.map(message=>message.role==='user'?{...message,content:message.content.map(block=>block.type==='image'?{...block,attachment:{...block.attachment,name:'PRIVATE_EXTRA_TEXT'}}:block)}:message)})};};}});
  },{prepend:true}));
  const beforeImageTamper=calls.length;await assert.rejects(run({role:'reviewer',packet:imagePacket}),/实际原生输入.*不一致/);await stop();assert.equal(calls.length,beforeImageTamper);
  other=await ctx.agents.create({sessionId:'ordinary-'+randomUUID(),agentOptions:FIXED_ROUTE,meta:{cwd:root}});
  other.agent.followup({id:randomUUID(),role:'user',source:{kind:'user'},content:[{type:'text',text:'ORDINARY_AGENT_SENTINEL'}]});await other.agent.whenIdle();
  assert.ok(calls.at(-1).tools.some(tool=>tool.name==='normal_fixture_tool'));assert.match(JSON.stringify(calls.at(-1).messages),/ORDINARY_AGENT_SENTINEL/);
  assert.equal(JSON.stringify(rejected),rejectedPrefix,'historical rejected results were never rewritten');
  console.log(JSON.stringify({ok:true,network_inference_calls:0,synthetic_native_dispatches:calls.length,missing_binding_attached:true,wrong_and_null_rejected:true,native_input_tamper_rejected:true,downstream_request_tamper_rejected:true,raw_and_envelope_separate:true,durable_image_refs_exact:true,other_agent_unchanged:true,frozen_binding_not_late_current:true}));
  }
}finally{await other?.dispose();for(const fiber of fibers.reverse())await fiber.dispose?.();await rm(root,{recursive:true,force:true});}
