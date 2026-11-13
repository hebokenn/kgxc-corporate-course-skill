import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {editorHost} from '../plugin/editor-host.mjs';
import {AUTHORING_PREFLIGHT_PROMPT,SOURCE_COVERAGE_PROMPT} from '../plugin/review-host.mjs';
import {fastProductionPrompt} from '../plugin/fast-production.mjs';

test('the controlled producer gets the same fast workflow by stage with no new authorization',()=>{
  assert.match(fastProductionPrompt('storyboard'),/逐字稿真实确认后.*两线并行/);
  assert.match(fastProductionPrompt('pilot'),/自动接缝短试，无需另开审阅或用户确认/);
  assert.match(fastProductionPrompt('final'),/主体，再独立加入并检查花字和音效/);
  assert.match(fastProductionPrompt('final'),/incremental_production\.py/);
  assert.equal(fastProductionPrompt('questions'),'');
});

test('inline rewriting uses the host model once, records its input, returns a suggestion without saving text',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-editor-host-'));const calls=[];
  const llm={prepareCall:async config=>({config,stream:async function*(){yield {type:'reasoning-delta',text:'hidden'};yield {type:'text-delta',text:'先暂停交接，再记录差异。'};yield {type:'finish',reason:{kind:'stop'}};}})};
  const services={llm,agentDefaultModel:{currentSelection:()=>({provider:'fixture',model:'fixture-model'})}};
  const invoke=async(name,args)=>{calls.push({name,args});return {ok:true,editor:{course_path:root}};};
  try{const handle=editorHost({get:name=>services[name]},new Map(),invoke);const value=await handle('rewrite',{course_path:root,requestId:'r1',text:'暂停交接，记录差异。',instruction:'更口语化',before:'',after:''});
    assert.equal(value.text,'先暂停交接，再记录差异。');assert.equal(calls.length,1);assert.equal(calls[0].args.action,'read');
    assert.equal((await readdir(join(root,'project/work/editor-ai'))).length,2);
  }finally{await rm(root,{recursive:true,force:true});}
});
test('render delivery uses an identified immutable user message, never auto-confirms a missing plan',async()=>{
  let delivered,injected;const requests=[];const path='/tmp/kgxc-render-host-fixture';
  const agent={session:{id:'fixture-session',log:[]},inject:message=>{injected=message;},followup:message=>{delivered=message;},whenIdle:()=>new Promise(()=>{})};
  const handle=editorHost({get:name=>name==='agents'?{get:()=>agent,roots:()=>[agent]}:undefined},new Map([[path,agent]]),async(name,args)=>{requests.push(args);return {ok:true,editor:{course_path:path,render_request:{id:'ab1234567890',text:'冻结稿件',sha256:'fixture-hash',status:'preparing'}}};});
  assert.equal((await handle('render',{course_path:path,requestId:'ab1234567890'})).ok,true);
  assert.equal(delivered.role,'user');assert.match(delivered.id,/^[a-f0-9-]{36}$/);assert.ok(Object.isFrozen(delivered));
  assert.match(injected.content[0].text,/不得补填其他未确认/);assert.match(delivered.content[0].text,/在工作台点击渲染时的稿件/);assert.doesNotMatch(delivered.content[0].text,/course_path|render_request_id/);assert.equal(requests.length,1);
});

test('opening the dock binds course context without starting a model turn or overwriting chat input',async()=>{
  const injected=[];const agent={session:{id:'s1'},inject:value=>injected.push(value),followup:()=>{throw Error('unexpected model turn');}};
  const bindings=new Map();const path='/tmp/kgxc-chat-binding-fixture';
  const handle=editorHost({get:name=>name==='agents'?{get:id=>id==='s1'?agent:undefined}:undefined},bindings,async()=>({ok:true,editor:{course_path:path}}));
  await handle('bind',{course_path:path,session_id:'s1'});await handle('bind',{course_path:path,session_id:'s1'});
  assert.equal(injected.length,1);assert.equal(bindings.get(path),agent);assert.equal(injected[0].role,'user');
  assert.match(injected[0].content[0].text,/不是生成、渲染或批准请求/);
  await assert.rejects(handle('bind',{course_path:path,session_id:'missing'}),/对话正在连接/);
});

test('stage handoff requires the real prior confirmation and preserves identified messages and stable section instructions',async()=>{
  let allowed=false,delivered,injected;const path='/tmp/kgxc-stage-fixture';
  const agent={session:{id:'stage-session'},inject:message=>{injected=message;},followup:message=>{delivered=message;}};
  const handle=editorHost({get:name=>name==='agents'?{get:()=>agent}:undefined},new Map([[path,agent]]),async name=>name==='kgxc_course_editor'?{ok:true,editor:{course_path:path}}:{ok:true,workflow:{gates:[{id:'outline',status:allowed?'confirmed':'open'}]}});
  await assert.rejects(handle('stage',{course_path:path,session_id:'stage-session',target_stage:'script'}),/先在课程工作台确认大纲/);
  assert.equal(delivered,undefined);allowed=true;
  const result=await handle('stage',{course_path:path,session_id:'stage-session',target_stage:'script'});
  assert.equal(result.target_stage,'script');assert.equal(delivered.role,'user');assert.ok(Object.isFrozen(delivered));
  assert.match(injected.content[0].text,/data\.sections/);assert.match(injected.content[0].text,/不覆盖人工稿/);
  assert.match(injected.content[0].text,/不要因本次按钮操作代填其他阶段确认/);
  assert.ok(injected.content[0].text.includes(AUTHORING_PREFLIGHT_PROMPT));assert.ok(injected.content[0].text.includes(SOURCE_COVERAGE_PROMPT));
  assert.match(injected.content[0].text,/唯一一次独立只读盲审/);assert.match(injected.content[0].text,/定向验收一次/);assert.doesNotMatch(injected.content[0].text,/再交新 Agent 审阅|修复后.*新 Agent.*审阅/);
  assert.ok(Object.isFrozen(injected));assert.equal(injected.source.kind,'kgxc-course-context');
  assert.equal(delivered.content[0].text,'请按工作台已确认的大纲生成逐字稿。');
});

test('source coverage button dispatches only comparison under the current producer supervision and never calls a stage or confirmation tool',async()=>{
  const path='/tmp/kgxc-source-coverage-action',order=[],requests=[];let injected,delivered,operation;
  const agent={session:{id:'coverage-agent'},status:'idle',inject:message=>{injected=message;order.push('context');},followup:message=>{delivered=message;order.push('dispatch');}};
  const supervision={production:async value=>{operation=value;order.push('supervision');}};
  const handle=editorHost({get:name=>name==='agents'?{get:id=>id===agent.session.id?agent:undefined}:undefined},new Map([[path,agent]]),async(name,args)=>{requests.push({name,args});return {ok:true,editor:{course_path:path}};},{supervision});
  const result=await handle('source-coverage',{course_path:path,session_id:agent.session.id});
  assert.equal(result.action,'source-coverage');assert.match(result.operation_id,/^source-coverage-/);assert.deepEqual(order,['supervision','context','dispatch']);
  assert.equal(operation.producer,agent);assert.equal(operation.scope,'source-coverage');assert.equal(operation.auto_review,false);assert.equal(operation.stage,'script');
  assert.ok(injected.content[0].text.includes(SOURCE_COVERAGE_PROMPT));assert.match(injected.content[0].text,/不得修改当前逐字稿、大纲、分镜/);assert.match(injected.content[0].text,/不启动、重开或调用盲审/);assert.match(injected.content[0].text,/保存对照后立即结束/);
  assert.match(delivered.content[0].text,/只生成\/更新.*等我在工作台确认/);assert.deepEqual(requests.map(call=>call.name),['kgxc_course_editor']);
  agent.status='running';await assert.rejects(handle('source-coverage',{course_path:path,session_id:agent.session.id}),/正在执行其他任务/);assert.equal(order.length,3);
  const unmonitored=editorHost({get:name=>name==='agents'?{get:()=>agent}:undefined},new Map([[path,agent]]),async()=>({ok:true,editor:{course_path:path}}));agent.status='idle';await assert.rejects(unmonitored('source-coverage',{course_path:path}),/缺少制作执行监督/);
});

test('a prepared and currently bound timeline exports by computer without another model turn',async()=>{
  const path='/tmp/kgxc-prepared-fixture',calls=[];let dirty=false;
  const handle=editorHost({get:()=>undefined},new Map(),async(name,args)=>{
    calls.push({name,args});
    if(name==='kgxc_course_editor')return {ok:true,editor:{course_path:path,prepared_exports:{pilot:true,final:false},changed:dirty}};
    if(name==='kgxc_course_status')return {ok:true,workflow:{revision:17,gates:[{id:'storyboard',status:'confirmed'},{id:'pilot',status:'confirmed'}]}};
    return {ok:true,job:{id:'actual-job',status:'queued',progress:0}};
  });
  const result=await handle('stage',{course_path:path,session_id:'s1',target_stage:'pilot'});
  assert.equal(result.executor,'computer');assert.equal(result.job.id,'actual-job');assert.equal(calls.at(-1).name,'kgxc_course_export');assert.equal(calls.at(-1).args.base_revision,17);
  dirty=true;await assert.rejects(handle('stage',{course_path:path,session_id:'s1',target_stage:'pilot'}),/对话尚未连接/);
  dirty=false;await assert.rejects(handle('stage',{course_path:path,session_id:'s1',target_stage:'final'}),/对话尚未连接/);
  await assert.rejects(handle('stage',{course_path:path,session_id:'s1',target_stage:'pilot',user_instruction:'调整这段画面'}),/对话尚未连接/);
  assert.equal(calls.filter(x=>x.name==='kgxc_course_export').length,1);
});

test('a real stage dispatch awaits independent supervision and passes current user instructions only to producer and supervisor',async()=>{
  const path='/tmp/kgxc-stage-supervision-fixture',order=[],instructions=[];
  const agent={session:{id:'supervised-producer'},inject:message=>{order.push('producer-context');instructions.push(message.content[0].text);},followup:()=>order.push('producer-start')};
  const supervision={production:async request=>{order.push('supervisor-start');assert.match(request.user_instruction,/USER_DIRECTION_SENTINEL/);},onIdle:async()=>{}};
  const invoke=async name=>name==='kgxc_course_editor'?{ok:true,editor:{course_path:path}}:{ok:true,workflow:{gates:[{id:'script',status:'confirmed'}]}};
  const handle=editorHost({get:name=>name==='agents'?{get:()=>agent}:undefined},new Map([[path,agent]]),invoke,{supervision});
  await handle('stage',{course_path:path,session_id:agent.session.id,target_stage:'storyboard',instruction:'USER_DIRECTION_SENTINEL'});
  assert.deepEqual(order,['supervisor-start','producer-context','producer-start']);
  assert.match(instructions[0],/USER_DIRECTION_SENTINEL/);assert.match(instructions[0],/四个节点/);assert.match(instructions[0],/不新增用户点击/);assert.match(instructions[0],/起态、过程、结果/);
  supervision.production=async()=>{throw Error('独立监督阻止执行');};order.length=0;
  await assert.rejects(handle('stage',{course_path:path,session_id:agent.session.id,target_stage:'storyboard'}),/阻止/);assert.deepEqual(order,[]);
});

test('restoring a bound idle producer schedules automatic independent review without waking production',async()=>{
  const path='/tmp/kgxc-bind-idle-fixture';let idle=0;
  const agent={session:{id:'bound-idle'},inject:()=>{},followup:()=>{throw Error('binding cannot wake production');}};
  const handle=editorHost({get:name=>name==='agents'?{get:()=>agent}:undefined},new Map(),async()=>({ok:true,editor:{course_path:path}}),{supervision:{onIdle:async target=>{assert.equal(target,agent);idle++;}}});
  await handle('bind',{course_path:path,session_id:agent.session.id});assert.equal(idle,1);
});
