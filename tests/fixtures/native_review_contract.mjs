// Run with installed Electron's ELECTRON_RUN_AS_NODE=1. No network/inference,
// production project, desktop config or installed plugin is touched.
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm,stat,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {isolatedAgentRunner,FIXED_ROUTE,REVIEW_PROTOCOL,SUPERVISION_PROTOCOL} from '../../plugin/isolated-review-agent.mjs';
const base=process.env.KGXC_DSH_NATIVE_ROOT||'/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai/';
const load=async name=>import(base+name+'/lib/index.js');
const {Context}=await load('cordis');
const ctx=new Context(),fibers=[],requests=[],globalCalls=[],idleEvents=[],localRegistrations=[];let localExecutions=0,normalContextVerified=false,navigationContractVerified=false;
const mount=async(plugin,config,parent=ctx)=>{const fiber=parent.plugin(plugin,config);fibers.push(fiber);await fiber.await();return fiber;};
const header={...FIXED_ROUTE,maxTokens:14000};
const syntheticStream=async function*(request){
    requests.push(request);
    assert.deepEqual(request.tools||[],[]);
    assert.equal(request.messages.length,2);
    assert.equal(request.messages[0].role,'system');assert.match(request.messages[0].content[0].text,/独立.*Agent/);
    assert.doesNotMatch(JSON.stringify(request.messages),/SECRET_ORIGINAL|INJECTED_HISTORY|GLOBAL_CONTEXT|PRIVATE_SKILL/);
    const payload=JSON.parse(request.messages[1].content[0].text);
    if(payload.stage==='storyboard'){
      const prompt=request.messages[0].content[0].text;
      assert.ok(payload.input.storyboard.segments[0].id);
      assert.match(prompt,/findings 与 items 中针对普通片段的每条 evidence 都必须有 segment_id.*实际存在的片段 id/);
      assert.match(prompt,/locator 指明该片段内的具体字段，quote 必须逐字连续复制该字段的当前原文/);
      assert.match(prompt,/不能用概述代替 quote，不能用省略号拼接不连续片段/);
      assert.match(prompt,/缺少时间字段时，引用实际存在的 action 或 reading.*在 problem 中明确缺少什么/);
      assert.match(prompt,/beat 和 time 只有实际字段存在.*不估算、不补造/);
      assert.match(prompt,/segment_id:仅分镜片段证据填写实际片段ID.*beat:仅实际存在时填写,time:仅实际存在时填写,sha256:仅已提交实际帧的哈希/);
      assert.match(prompt,/method:"storyboard_read",locator:"input\.storyboard\.navigation\.<实际字段>\[实际索引\]\.\.\.",quote:/);
      assert.match(prompt,/数组索引可写 \[0\] 或 \.0.*紧凑 JSON／默认带空格 JSON 表达/);
      assert.match(prompt,/导航 evidence 只能包含 method、locator、quote 三个键，不得携带 segment_id、option_id、beat、time、sha256 或其他键/);
      assert.match(prompt,/不能引用原件、路径、自由制作说明或未提供的原始 navigation\.basis、timing_budget、source/);
      assert.match(prompt,/缺失字段、未知状态或无法核对的导航证据如实标记“无法验证”/);
      assert.equal(payload.input.storyboard.navigation.toc.sections[0].label,'合成章节');assert.deepEqual(payload.input.storyboard.navigation.actual_timeline.toc_visible,[0,30]);navigationContractVerified=true;
      assert.match(prompt,/只找问题和报告，不修改、不重写、不产出补丁/);
      assert.match(prompt,/连续视听、运动、节奏和音画同步检查必须无法验证/);
    }
    const report=payload.protocol===SUPERVISION_PROTOCOL?{summary:'synthetic real-native supervision',passed:true,findings:[]}:{summary:'synthetic real-native contract',learner:{about:'fixture',what_it_said:'fixture',learned:['fixture'],confusions:[]},findings:[],items:[]};
    yield {type:'text-delta',index:0,text:JSON.stringify(report)};yield {type:'usage',usage:{inputTokens:9,outputTokens:5,totalTokens:14}};yield {type:'finish',reason:{kind:'stop'}};
};
await mount(c=>{
  c.provide('fs',{resolve:async path=>realpath(path),stat:async path=>({type:(await stat(path)).isDirectory()?'directory':'file'}),processPath:path=>path});
  c.provide('subagents',{});
});
for(const name of ['dsh-session','dsh-session-projection','dsh-agent','dsh-llm','dsh-system-prompt','dsh-tools','dsh-agent-loop'])await mount((await load(name)).default);
ctx.llm.registerAdapter([FIXED_ROUTE.provider],{providerInfo:provider=>({id:provider,name:'Synthetic no-network adapter'}),providerRetryPolicy:()=>({mode:'normal',maxRetries:0,retryableCodes:[],initialDelayMs:1,maxDelayMs:1,jitterRatio:0}),
  prepareCall:async(provider,model)=>({model:{id:model,provider,name:model,inputModalities:['text','image']},stream:syntheticStream})});
await mount((await load('dsh-working-directory')).default,{defaultDirectory:tmpdir()});
// Team runtime needs persistence for its own dormant recovery seam; native
// test agents remain ephemeral in the original registry/loop scope.
const teamContext=ctx.isolate('sessionPersistence');
await mount(c=>c.provide('sessionPersistence',{}),undefined,teamContext);
await mount((await load('dsh-experimental-agent-team')).default,undefined,teamContext);
await mount(await load('dsh-experimental-tool-agent-team'));
ctx.on('agent/created',({agent})=>{
  agent.ctx.tools.register({name:'native_late_local',description:'SECRET_ORIGINAL',parameters:{type:'object'},output:{schema:{type:'object'},render:()=>[]},execute:()=>{localExecutions++;throw Error('agent-local execution forbidden');}});
  agent.ctx.systemPrompt.context({name:'native-late-required',order:0,required:true,text:'SECRET_ORIGINAL LATE_REQUIRED_CONTEXT'});
  localRegistrations.push({id:agent.id,tools:agent.ctx.tools.schemas(agent).map(tool=>tool.name)});
});
ctx.on('agent/status',({agent,status})=>{
  if(status!=='idle'||![...agent.session.log].some(event=>event.type==='turn/end'))return;
  assert.equal(agent.status,'idle');assert.equal([...agent.session.log].at(-1).type,'turn/end');idleEvents.push(agent.id);
});
ctx.tools.setExecutor({describe:()=>({schemas:[{name:'unrestricted_exec',description:'private',parameters:{type:'object'}}]}),execute:()=>{throw Error('GLOBAL EXECUTOR MUST NOT RUN');}});
ctx.tools.register({name:'read_file',description:'SECRET_ORIGINAL',parameters:{type:'object'},output:{schema:{type:'object'},render:()=>[]},execute:()=>{throw Error('read original forbidden');}});
ctx.systemPrompt.section({name:'global-private',order:0,text:'PRIVATE_SKILL SECRET_ORIGINAL'});
ctx.systemPrompt.context({name:'global-required',order:0,required:true,text:'GLOBAL_CONTEXT'});
ctx.on('agent/pre-step',async(payload,next)=>{globalCalls.push(payload.agent.id);const value=await next();return {...value,messages:[...value.messages,{id:'injected',role:'user',source:{kind:'fixture'},content:[{type:'text',text:'INJECTED_HISTORY SECRET_ORIGINAL'}]}]};});
const root=await mkdtemp(join(tmpdir(),'kgxc-real-native-contract-'));await mkdir(join(root,'project'),{recursive:true});
const packet={protocol:REVIEW_PROTOCOL,stage:'script',run_id:'native-synthetic',fingerprint:'f',artifact_sha256:'a'.repeat(64),binding:{packet_sha256:'b'.repeat(64)},review_contract:{role:'reviewer',read_only:true},checklist:[],input:{text:'当前独立逐字稿技术夹具'},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:'transcript',kind:'transcript',sha256:'a'.repeat(64)}]};
try{
  const runner=isolatedAgentRunner(ctx),signal=new AbortController().signal;
  const one=await runner({role:'reviewer',packet,course_path:root,selection:header,signal,onCreated:async()=>{
    const normal=await ctx.agents.create({sessionId:'native-normal-context',agentOptions:header,meta:{cwd:root}});
    try{
      const assembly=await ctx.systemPrompt.assemble({scope:normal.agent,agent:normal.agent,modelSelection:header,signal});
      const refreshed=ctx.systemPrompt.refreshContext(assembly,{scope:normal.agent,agent:normal.agent,modelSelection:header,signal});
      assert.ok(refreshed.contexts.some(context=>context.name==='native-late-required'&&context.text.includes('SECRET_ORIGINAL')));
      assert.ok(refreshed.contexts.some(context=>context.name==='team:identity'));
      assert.ok(refreshed.tools.length);normalContextVerified=true;
    }finally{await normal.dispose();}
  }});
  const two=await runner({role:'reviewer',packet,course_path:root,selection:header,signal});
  const storyboard={...packet,stage:'storyboard',input:{storyboard:{navigation:{schema:'course-navigation/1',toc:{sections:[{unit_id:'U',label:'合成章节'}]},actual_timeline:{fps:30,total_frames:180,body:[0,180],toc_visible:[0,30]}},segments:[{id:'s',beats:[{at:0,object:'当前讲解的对象'}]}]}},allowed_artifacts:[{id:'storyboard',kind:'storyboard',sha256:'a'.repeat(64)}]};
  const three=await runner({role:'reviewer',packet:storyboard,course_path:root,selection:header,signal});
  const supervisor=await runner({role:'supervisor',packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:'synthetic'},requirements:[],execution:[{user_instruction:'USER_DIRECTION_SENTINEL'}]},course_path:root,selection:header,signal});
  assert.notEqual(one.audit.id,two.audit.id);assert.equal(globalCalls.length,0,'global instruction injectors must be bypassed');
  assert.equal(new Set([one.audit.id,two.audit.id,three.audit.id,supervisor.audit.id]).size,4);
  assert.equal(requests.length,4);assert.equal(one.usage.totalTokens,14);assert.ok(one.audit.invocation_ids.length);assert.deepEqual(one.audit.accessible_tools,[]);
  assert.deepEqual(one.result.binding,packet.binding);assert.equal(one.audit.binding_host.source,'host-attached-missing');assert.equal(one.audit.request_boundary.boundary_observed,true);
  assert.equal(new Set(idleEvents).size,4,'actual native idle fires with completed turn already committed');
  assert.ok(normalContextVerified,'facade never strips a different normal Agent');
  assert.ok(one.audit.registered_tools.includes('native_late_local'));
  assert.ok(one.audit.registered_tools.includes('spawn_teammate'));
  assert.ok(one.audit.suppressed_runtime_contexts.includes('team:identity'));
  assert.ok(one.audit.suppressed_runtime_contexts.includes('native-late-required'));
  assert.equal(localExecutions,0);
  assert.doesNotMatch(JSON.stringify(requests.slice(0,3)),/USER_DIRECTION_SENTINEL/);assert.match(JSON.stringify(requests[3]),/USER_DIRECTION_SENTINEL/);
  const rogue=ctx.systemPrompt.tools(()=>({schemas:[{name:'leaked_schema',description:'SECRET_ORIGINAL',parameters:{type:'object'}}]}));
  await assert.rejects(runner({role:'reviewer',packet,course_path:root,selection:header,signal}),error=>{
    assert.match(error.message,/未隔离|额外能力/);assert.equal(error.execution_phase,'preflight');assert.equal(error.model_invoked,false);
    assert.deepEqual(error.usage,{});assert.deepEqual(error.agent_audit.invocation_ids,[]);assert.deepEqual(error.agent_audit.request_headers,[]);return true;
  });
  assert.equal(requests.length,4,'direct prompt schema leakage must fail before inference');await rogue();
  const injected=ctx.on('agent/created',({agent})=>agent.inject({id:'rogue-created',role:'user',source:{kind:'fixture'},content:[{type:'text',text:'SECRET_ORIGINAL'}]}));
  await assert.rejects(runner({role:'reviewer',packet,course_path:root,selection:header,signal}),error=>{
    assert.match(error.message,/未授权上下文/);assert.equal(error.execution_phase,'preflight');assert.equal(error.model_invoked,false);assert.deepEqual(error.usage,{});return true;
  });await injected();
  assert.equal(requests.length,4,'creation-time injection must fail before model request');
  for(const [type,role,source] of [
    ['developer/message','developer',{kind:'fixture'}],
    ['system/message','system',{kind:'system-prompt'}],
    ['tool/result','tool',{kind:'tool',callId:'fixture-result'}],
  ]){
    const stop=ctx.on('agent/created',({agent})=>{
      const message={id:'rogue-'+role,role,source,content:[{type:'text',text:'SECRET_ORIGINAL '+role}],...role==='tool'?{toolCallId:'fixture-result'}:{}};
      agent.session.append(type,{turn:0,step:0,message},{surfaceOp:'append'});
      assert.equal(agent.session.deriveMessages().at(-1).role,role);
    });
    try{
      await assert.rejects(runner({role:'reviewer',packet,course_path:root,selection:header,signal}),error=>{
        assert.match(error.message,/历史上下文/);assert.equal(error.execution_phase,'preflight');assert.equal(error.model_invoked,false);return true;
      });
      assert.equal(requests.length,4,role+' history must be rejected before inference');
    }finally{await stop();}
  }
  console.log(JSON.stringify({ok:true,native_api:'installed DSH 0.2.2-rc.1',network_inference_calls:0,synthetic_streams:requests.length,independent_ids:[one.audit.id,two.audit.id,three.audit.id,supervisor.audit.id],global_injectors_executed:globalCalls.length,tools:[],native_idle_events:idleEvents.length,registered_local_tools:one.audit.registered_tools,suppressed_context_names:one.audit.suppressed_runtime_contexts,normal_agent_context_unchanged:normalContextVerified,local_tool_executions:localExecutions,storyboard_navigation_evidence_contract:navigationContractVerified}));
}finally{
  for(const fiber of fibers.reverse())await fiber.dispose?.();
  await rm(root,{recursive:true,force:true});
}
