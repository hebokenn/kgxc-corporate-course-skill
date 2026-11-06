import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {editorHost} from '../plugin/editor-host.mjs';

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
  assert.ok(Object.isFrozen(injected));assert.equal(injected.source.kind,'kgxc-course-context');
  assert.equal(delivered.content[0].text,'请按工作台已确认的大纲生成逐字稿。');
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
