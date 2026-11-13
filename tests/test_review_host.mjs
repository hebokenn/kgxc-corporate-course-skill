import {FIXED_ROUTE} from './fixtures/model-route.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID,createHash} from 'node:crypto';
import {mkdtemp,readFile,rm,readdir,mkdir,writeFile,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
import {reviewHost,PRODUCER_PROMPT,AUTHORING_PREFLIGHT_PROMPT,SOURCE_COVERAGE_PROMPT,producerInputContent} from '../plugin/review-host.mjs';
import {callReview} from '../plugin/bridge.mjs';
import {REVIEW_PROTOCOL,SUPERVISION_PROTOCOL,SUPERVISOR_PROMPT,REVIEWER_PROMPT,blindPayload,assertReadOnlyReport} from '../plugin/isolated-review-agent.mjs';

const repository=resolve(import.meta.dirname,'..');
test('blind host rejects unselected storyboard alternatives instead of exposing them to a reviewer',()=>{
  const packet={protocol:REVIEW_PROTOCOL,stage:'storyboard',binding:{packet_sha256:'b'.repeat(64)},input:{storyboard:{segments:[{id:'S1',selected:'A',options:[{id:'A',action:'当前方案'},{id:'B',action:'未选方案'}]}]}},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[]};
  assert.throws(()=>blindPayload(packet),/当前选定方案/);
  packet.input.storyboard.segments[0].options=[{id:'B',action:'未选方案'}];assert.throws(()=>blindPayload(packet),/当前选定方案/);
  packet.input.storyboard.segments[0].options=[{id:'A',action:'当前方案'}];assert.equal(blindPayload(packet).input.storyboard.segments[0].options.length,1);
});

test('authoring, blind review and targeted acceptance have distinct bounded responsibilities',()=>{
  assert.match(AUTHORING_PREFLIGHT_PROMPT,/来源.*事实与假设/);
  assert.match(AUTHORING_PREFLIGHT_PROMPT,/情境、例子或示范.*为什么.*结果.*检查\/反馈/);
  assert.match(AUTHORING_PREFLIGHT_PROMPT,/车轱辘话.*套话/);assert.match(AUTHORING_PREFLIGHT_PROMPT,/酷果星创问候语/);
  assert.match(REVIEWER_PROMPT,/唯一一次盲审/);assert.match(REVIEWER_PROMPT,/不评价未选候选/);
  assert.match(PRODUCER_PROMPT,/acceptance_mode.*targeted.*issue_ledger/);assert.match(PRODUCER_PROMPT,/不再提交 repairs/);
  assert.doesNotMatch(PRODUCER_PROMPT,/交全新独立 Agent 复审/);
});

test('source comparison instructions bind business points and additions to the current draft without widening blind inputs',()=>{
  assert.match(SOURCE_COVERAGE_PROMPT,/唯一盲审前.*按独立业务要点/);assert.match(SOURCE_COVERAGE_PROMPT,/不按字数、词频/);
  assert.match(SOURCE_COVERAGE_PROMPT,/omitted.*舍弃.*关键 critical 项单列/);assert.match(SOURCE_COVERAGE_PROMPT,/fully_read.*false.*不能冒称满覆盖/);
  assert.match(SOURCE_COVERAGE_PROMPT,/basis_kind=explanation.*example.*external/);assert.match(SOURCE_COVERAGE_PROMPT,/不能自动变成内部制度/);
  assert.match(SOURCE_COVERAGE_PROMPT,/kgxc_course_source_coverage\(action='save'.*expected_script_sha256/);assert.match(SOURCE_COVERAGE_PROMPT,/source-coverage\/1/);
  assert.match(SOURCE_COVERAGE_PROMPT,/用户在工作台真实点击/);assert.match(SOURCE_COVERAGE_PROMPT,/模型工具只支持 status\/save.*不能调用或伪造 confirm/);
  assert.match(SOURCE_COVERAGE_PROMPT,/不得加入盲审资料包.*只看当前选定作品.*一次/);
  const packet={protocol:REVIEW_PROTOCOL,stage:'script',binding:{packet_sha256:'b'.repeat(64)},input:{text:'仅当前学员稿件'},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[]};
  assert.throws(()=>blindPayload({...packet,source_coverage:{schema:'source-coverage/1',source_inventory:[{source_id:'PRIVATE_ORIGINAL'}]}}),/未授权上下文/);
  assert.doesNotMatch(JSON.stringify(blindPayload(packet)),/source_inventory|PRIVATE_ORIGINAL|source_coverage/);
});

test('supervisor prompt distinguishes lawful content blocking from actual execution violations',()=>{
  assert.match(SUPERVISOR_PROMPT,/passed 只表示当前执行监督是否合规，不表示课程内容通过或用户批准/);
  assert.match(SUPERVISOR_PROMPT,/producer_result\.passed=false.*本身不等于执行违规/);
  assert.match(SUPERVISOR_PROMPT,/按照 next_action 合法返修或停留.*不得仅因制作端未通过就报告执行违规/);
  assert.match(SUPERVISOR_PROMPT,/实际忽略阻断而放行、越权继续或虚假宣称成功.*必须依据可定位的执行事实返回阻断发现/);
  assert.match(SUPERVISOR_PROMPT,/当前 packet\.stage、phase 和 next_action.*不要求尚未开始的未来阶段已经完成/);
  assert.match(SUPERVISOR_PROMPT,/监督不代替制作端 source QA.*不要求取得原件.*有界验证元数据/);
  assert.match(SUPERVISOR_PROMPT,/真正关键的运行证据仍无法核实，保留“无法验证”的问题并明确缺项/);
});
async function fixture(){
  const root=await mkdtemp(join(tmpdir(),'kgxc-review-host-'));
  execFileSync('python3',['-B','-c',`import sys
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=[sys.argv[1]+'/skills/corporate-training-motion/workbench',sys.argv[1]+'/skills/corporate-training-motion/scripts']
from workflow import Course,atomic
from studio import Studio
from test_branch_workflow import design
r=Path(sys.argv[2]).resolve();p=r/'project';atomic(p/'workbench.json',dict(title='独立审阅控制器夹具',scenes=[],media={}))
c=Course(r);c.init('独立审阅控制器夹具');design(c);c.confirm('outline',c.status()['revision'],'QA结构')
Studio(SimpleNamespace(root=r,project=p,file=p/'workbench.json')).save_sections([dict(unit_id='U',body='先核对订单，再核对商品编码。示例：订单A的编码为P12，实物也是P12，核对后填写一致再交接。若不同就暂停并记录。')],c.status()['revision'],official=True)
`,repository,root]);return root;
}
async function registerProductionObligations(root){
  execFileSync('python3',['-B','-c',`import sys,json
from pathlib import Path
sys.path[:0]=[sys.argv[1]+'/skills/corporate-training-motion/workbench']
from execution_requirements import update
from workflow import atomic,read
p=Path(sys.argv[2])/'project'
(p/'messages').mkdir(parents=True,exist_ok=True);(p/'messages/synthetic-production.txt').write_text('Read the synthetic handoff and return its current structured artifact.')
d=read(p/'workbench.json',{});d.update(sourceDurationFrames=10,fps=25,sceneGraph=dict(nodes=[dict(id='synthetic-work-object',type='rect',startFrame=0,endFrame=10,width=10,height=10)]));atomic(p/'workbench.json',d)
r=dict(id='synthetic-work-return',source_type='user_current',source_ref='messages/synthetic-production.txt',original_quote='Read the synthetic handoff and return its current structured artifact.',stage='storyboard',scope=dict(scenes=['synthetic']),required_behavior='Return readable current work output and check evidence without claiming course approval',acceptance_checks=['synthetic-artifact-readable'],implementation_refs=[],evidence_refs=[],status='not_started',changes=[])
result=update(p,[r]);assert result['ready'],result
`,repository,root]);
}
async function returnProductionResult(root,message){
  const line=message.content[0].text.split('\n').find(x=>x.startsWith('实际派工与原句、对象、输入哈希、负责/禁改范围、必检动作及交回文件：'));
  const dispatch=JSON.parse(line.slice(line.indexOf('：')+1));assert.ok(dispatch.task?.task_id,'producer receives the actual backend dispatch');
  execFileSync('python3',['-B','-c',`import sys,json
from pathlib import Path
sys.path[:0]=[sys.argv[1]+'/skills/corporate-training-motion/workbench']
from workflow import read,atomic
from handoff_contract import submit
from evidence_versions import file_ref
p=Path(sys.argv[2])/'project';task=read(p/'work/handoffs'/(sys.argv[3]+'.json'))
for name in task['return_files']:
 value=read(p/name,{}) if name=='workbench.json' else {}
 value.update(synthetic_output=True,task_id=task['task_id'],note='Readable bounded work artifact; not a valid final course or user approval')
 atomic(p/name,value)
evidence='work/handoffs/'+task['task_id']+'-artifact-check.json'
outputs=[file_ref(p,name)for name in task['return_files']]
atomic(p/evidence,dict(method='current-output-json-readback',output_paths=outputs,readable=all(isinstance(read(p/name),dict)for name in task['return_files']),course_approved=False))
r=dict(task_id=task['task_id'],requirement_ids=task['requirement_ids'],output_paths=outputs,object_bindings=[dict(event_id='synthetic-object-event',quote=next(iter(task['quotes'].values())),object_ids=['synthetic-work-object'],allowed_types=['rect'],frame_range=[0,10])],checks_run=[dict(id=k,status='passed',evidence_ref=evidence)for k in task['required_checks']],evidence_refs=[file_ref(p,evidence)],unresolved_items=[],issue_ids=task['issue_ids'])
result=submit(p,r,read(p/'workbench.json'));assert result['ready'],result
`,repository,root,dispatch.task.task_id]);
}
function producer(root,{repair=true,failCalls=0}={}){
  let seq=0,pending=Promise.resolve();const log=[],capabilities={restrict:0,guard:0,executor:0},hooks=[];
  const emit=(type,data)=>{const event={type,data,seq:++seq,time:Date.now()};log.push(event);fake.onEvent?.(event);};
  const baseExecutor={},dispatch=(name,args,terminal)=>{const listeners=hooks.filter(hook=>hook.name===name);let index=0;const next=()=>listeners[index++]?.fn(...args,next)??terminal();return next();};let selected=baseExecutor;
  const fake={id:'producer-'+randomUUID(),session:{id:'producer-session-'+randomUUID(),log},status:'idle',options:FIXED_ROUTE,model:{current:()=>FIXED_ROUTE},cancel:()=>{fake.cancelled=true;fake.onCancel?.();},inject:()=>{},
    ctx:{tools:{restrict:()=>{capabilities.restrict++;return ()=>{capabilities.restrict--;};},guard:()=>{capabilities.guard++;return ()=>{capabilities.guard--;};},selectExecutor:()=>selected,setExecutor:executor=>{selected=executor;if(executor!==baseExecutor)capabilities.executor++;return ()=>{selected=undefined;if(executor!==baseExecutor)capabilities.executor--;};}},on:(name,fn,options)=>{const hook={name,fn};options?.prepend?hooks.unshift(hook):hooks.push(hook);return ()=>{hooks.splice(hooks.indexOf(hook),1);};}},
    followup:message=>{
      fake.status='running';pending=(async()=>{
        if(message.source?.kind==='kgxc-producer-work'){
          fake.workCalls=(fake.workCalls||0)+1;fake.lastWorkMessage=message;assert.deepEqual(capabilities,{restrict:0,guard:1,executor:0});
          emit('user/message',message);emit('turn/start',{turn:2});emit('step/start',{turn:2,step:1});emit('request/header',{header:{config:FIXED_ROUTE,tools:[{name:'work_tool'}]}});
          const service={prepareCall:async config=>({config,stream:request=>dispatch('llm/stream',[request],()=> (async function*(){
            assert.equal(request.tools.length,1);assert.equal(request.messages.some(item=>item.id==='old-work-history'),false);await fake.beforeWork?.();
            yield {content:[{type:'text',text:'synthetic current production completed'}]};
          })())})};
          const facade=dispatch('internal/get',[fake.ctx,'llm',undefined],()=>service),prepared=await facade.prepareCall(FIXED_ROUTE);
          try{
            for await(const response of prepared.stream({...FIXED_ROUTE,sessionId:fake.session.id,signal:new AbortController().signal,tools:[{name:'work_tool'}],toolHistory:{tools:[{name:'work_tool'}],updates:[]},messages:[{id:'system',role:'system',source:{kind:'system-prompt'},content:[{type:'text',text:'ORIGINAL_WORK_SYSTEM'}]},{id:'old-work-history',role:'user',source:{kind:'user'},content:[{type:'text',text:'OLD_WORK_HISTORY'}]},message]}))emit('assistant/message',{message:{...response,source:FIXED_ROUTE},usage:{totalTokens:23}});
            await fake.completeWork?.(message);
            emit('turn/end',{reason:{kind:'completed'}});
          }catch(error){emit('turn/end',{reason:fake.cancelled?{kind:'aborted'}:{kind:'error',error:{message:error.message}}});}
          fake.status='idle';return;
        }
        assert.equal(capabilities.restrict,1);assert.equal(capabilities.guard,1);assert.equal(capabilities.executor,1,'producer source QA cannot execute an inherited transport');
        const text=message.content[0].text,packet=JSON.parse(text.slice(text.lastIndexOf('\n\n{')+2));
        fake.lastPrompt=text.slice(0,text.lastIndexOf('\n\n{'));
        assert.equal(packet.role,'producer');assert.ok(packet.evidence.sources.length,'only producer receives original source');
        fake.lastPacket=packet;
        emit('user/message',message);emit('turn/start',{turn:1});emit('step/start',{turn:1,step:1});emit('request/header',{header:{config:FIXED_ROUTE}});
        const needs=repair&&packet.input.text.includes('先核对订单，');
        const source=packet.evidence.sources.find(source=>source.text)||{};
        const result={summary:'制作端核对实际原件与当前正文',items:packet.checklist.map(check=>({id:check.id,verdict:needs&&check.id==='teaching-continuity'?'需修改':'通过',reason:'实际来源与当前正文核对',evidence:[{method:check.required_method,quote:packet.input.text,source_id:source.id,source_quote:source.text,locator:'正文'}]})),repairs:needs?[{issue_id:'teaching-continuity',path:'source/transcript.md',before_sha256:packet.editable_files[0].sha256,find:'先核对订单',replace:'先核对订单日期',reason:'制作 Agent 接收盲审问题后补足对象'}]:[]};
        const service={prepareCall:async config=>({config,stream:request=>dispatch('llm/stream',[request],()=> (async function*(){
          assert.deepEqual(request.messages.map(item=>item.role),['system','user']);assert.deepEqual(request.tools,[]);assert.deepEqual(request.toolHistory,{tools:[],updates:[]});
          await fake.beforeResponse?.(packet,result);
          if(failCalls-->0)throw Error('synthetic provider quiet timeout');yield result;
        })())})};
        const facade=dispatch('internal/get',[fake.ctx,'llm',undefined],()=>service),prepared=await facade.prepareCall(FIXED_ROUTE);
        const request={...FIXED_ROUTE,sessionId:fake.session.id,signal:new AbortController().signal,tools:[],toolHistory:{tools:[{name:'old_render_tool'}],updates:[]},messages:[{id:'system',role:'system',source:{kind:'system-prompt'},content:[{type:'text',text:'ORIGINAL_SYSTEM_INSTRUCTION'}]},{id:'old-history',role:'user',source:{kind:'user'},content:[{type:'text',text:'OLD_PRODUCER_HISTORY_SENTINEL'}]},message,{id:'current-time',role:'user',source:{kind:'time-context'},content:[{type:'text',text:'CURRENT_TIME_SENTINEL'}]}]};
        try{for await(const response of prepared.stream(request))emit('assistant/message',{message:{content:[{type:'text',text:JSON.stringify(response)}],source:FIXED_ROUTE},usage:{totalTokens:80}});emit('turn/end',{reason:{kind:'completed'}});}
        catch(error){emit('turn/end',{reason:{kind:'error',error:{message:error.message}}});}
        fake.status='idle';
      })();
    },whenIdle:()=>pending,capabilities};return fake;
}
function isolatedCalls({supervisorPass=true,onCall}={}){
  const calls=[];
  const run=async options=>{
    const {role,packet,signal}=options;signal.throwIfAborted();calls.push({role,packet});await onCall?.(options);
    const audit={id:randomUUID(),session_id:randomUUID(),role,isolated:true,read_only:true,artifact_ids:role==='reviewer'?packet.allowed_artifacts.filter(item=>['transcript','storyboard'].includes(item.kind)).map(item=>item.id):[],route:FIXED_ROUTE,invocation_ids:[randomUUID()],capabilities:['text','images'],accessible_tools:[],inherited_events:0};
    let result;
    if(role==='reviewer'){
      assert.equal(packet.protocol,REVIEW_PROTOCOL);const input=blindPayload(packet);assert.doesNotMatch(JSON.stringify(input),/editable_files|source_quote|source_fusion|previous_round|SECRET_ORIGINAL/);
      const needs=packet.input?.text?.includes('先核对订单，');
      result={binding:packet.binding,summary:'独立学员实际理解',learner:{about:'交接核对',what_it_said:'核对订单和编码后记录',learned:['核对并记录'],confusions:needs?['未说明订单核对项目']:[]},findings:needs?[{id:'teaching-continuity',problem:'订单核对对象不清楚',evidence:[{method:'script_read',quote:packet.input.text,locator:'当前正文'}]}]:[],items:packet.checklist.map(check=>({id:check.id,verdict:needs&&check.id==='teaching-continuity'?'需修改':'通过',reason:'当前正文依据',evidence:[{method:check.required_method,quote:packet.input?.text||JSON.stringify(packet.input?.storyboard),locator:'当前成果'}]}))};
    }else{
      assert.equal(packet.protocol,SUPERVISION_PROTOCOL);result={binding:packet.binding,summary:supervisorPass?'已核对独立职责和真实执行':'实际执行违反只读职责',passed:supervisorPass,findings:supervisorPass?[]:[{id:'role',problem:'越权执行',evidence:[]}]};
    }
    result.agent_audit=audit;return {result,audit,usage:{totalTokens:40}};
  };return {run,calls};
}
function host(root,agent,independent,overrides={}){
  const {attachments,...options}=overrides,services={attachments,llm:{prepareCall:async config=>({config})},agents:{get:id=>id===agent.session.id?agent:undefined},agentDefaultModel:{currentSelection:()=>{throw Error('Must use the course session, not the global model default');}}};
  return reviewHost({get:name=>services[name]}, {bindings:new Map([[root,agent]]),runIsolated:independent.run,...options});
}
function supervisionFixture({allow=()=>true,onCall,bind=false}={}){
  const root='/tmp/kgxc-supervision-batch-'+randomUUID(),agent=producer(root,{repair:false}),journal=[],actions=[],independent=isolatedCalls({onCall});let seq=0,toolPolls=0;
  const native=independent.run;independent.run=async options=>{const value=await native(options);if(!allow(options.packet)){value.result.passed=false;value.result.findings=[{id:'execution',problem:'synthetic blocking execution finding',evidence:[]}];}return value;};
  const invoke=async(action,args)=>{
    actions.push({action,args});
    if(action==='production_event'){journal.push(...structuredClone(args.execution||[]));return {ok:true,started:args.phase==='start'?true:undefined};}
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:args.operation_id,execution_count:journal.length},execution:structuredClone(journal),requirements:[]}};
    if(action==='reserve')return {ok:true,reserved:true};if(action==='recover')return {ok:true,review:{hold:{held:false},nodes:{}}};return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,bindings:bind?new Map([[root,agent]]):new Map(),tool:async()=>{toolPolls++;return {ok:true,job:{status:'cancelled'}};},pause:async()=>{}});
  return {root,agent,handle,journal,actions,independent,get toolPolls(){return toolPolls;},start:execution=>handle.production({course_path:root,producer:agent,stage:'script',execution:execution||[]}),emit:(type,data)=>handle.observe(agent,{seq:++seq,time:seq,type,data})};
}

test('user review arrangement and listening controls forward without a model or production dispatch',async()=>{
  const actions=[],independent=isolatedCalls(),agent=producer('/tmp/user-review-controls',{repair:false});
  const handle=host('/tmp/user-review-controls',agent,independent,{invoke:async(action,args)=>{actions.push({action,args});return {ok:true,recorded:action};}});
  try{
    const arrangement={course_path:'/tmp/user-review-controls',mode:'visual_ai_user_audio',evidence:'用户实际选择由我听音轨，AI审文字与画面',actor:'user-chat-confirmation',source:{kind:'chat',id:'actual-question-reply'}};
    assert.equal((await handle('review_arrangement',arrangement)).recorded,'review_arrangement');
    const declaration={course_path:arrangement.course_path,stage:'pilot',artifact_sha256s:['a'.repeat(64)],artifacts:[{sha256:'a'.repeat(64),start_seconds:0,end_seconds:3.25}],coverage:'all_stage_videos',listened_completely:false,audio_and_sync_ok:false,evidence:'只播放了一部分，声音有问题',actor:'user-chat-confirmation',source:{kind:'chat',id:'actual-listening-reply'},feedback:'末句不完整'};
    assert.equal((await handle('user_audio_review',declaration)).recorded,'user_audio_review');
    assert.deepEqual(actions,[{action:'review_arrangement',args:arrangement},{action:'user_audio_review',args:declaration}]);
    assert.equal(independent.calls.length,0);assert.equal(agent.workCalls,undefined);assert.equal(handle.active(),0);
    await assert.rejects(handle('approve',declaration),/未知正式审阅操作/);
    await assert.rejects(handle('confirm',declaration),/未知正式审阅操作/);
  }finally{await handle.dispose();}
});

test('one blind review and one repair batch stop after targeted acceptance even if producer proposes another batch',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-single-review-host-')),agent=producer(root),independent=isolatedCalls(),actions=[];
  const binding={stage:'script',run_id:'single-review-run',packet_sha256:'b'.repeat(64)};let producerPackets=0;
  const invoke=async(action,args)=>{
    actions.push({action,args});
    if(['production_dispatch','capability_requirements'].includes(action))return callReview(action,args);
    if(action==='production_event'&&args.operation_id?.startsWith('produce-'))return callReview(action,args);
    if(action==='begin')return {ok:true,started:true,run:{id:binding.run_id}};
    if(action==='reserve')return {ok:true,reserved:true};
    if(action==='packet')return {ok:true,packet:{protocol:REVIEW_PROTOCOL,stage:'script',run_id:binding.run_id,fingerprint:'f',artifact_sha256:'a'.repeat(64),binding,review_contract:{},checklist:[],input:{text:'先核对订单，再核对商品编码。'},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:'transcript',kind:'transcript',sha256:'a'.repeat(64)}]}};
    if(action==='producer_packet')return {ok:true,packet:{protocol:'course-producer-qa/1',role:'producer',stage:'script',run_id:binding.run_id,binding,input:{text:'先核对订单，再核对商品编码。'},acceptance_mode:producerPackets++?'targeted':'initial',issue_ledger:[{id:'teaching-continuity'}],checklist:[{id:'teaching-continuity',required_method:'script_read'}],evidence:{sources:[{id:'S',text:'合成来源'}]},editable_files:[{sha256:'a'.repeat(64)}]}};
    if(action==='producer_submit')return {ok:true,can_repair:true,repairs:args.result.repairs};
    if(action==='repair')return {ok:true,rerender:false};
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding,requirements:[],execution:[]}};
    return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,bindings:new Map()});
  try{
    await handle('continue',{course_path:root,session_id:agent.session.id,stage:'script'});await handle.whenIdle();
    assert.equal(actions.filter(call=>call.action==='packet').length,1);assert.equal(independent.calls.filter(call=>call.role==='reviewer').length,1);
    assert.equal(actions.filter(call=>call.action==='producer_submit').length,2);assert.equal(actions.filter(call=>call.action==='repair').length,1);
    assert.match(actions.findLast(call=>call.action==='finish').args.error,/停止自动返修/);
    assert.deepEqual(agent.capabilities,{restrict:0,guard:0,executor:0});
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('a changed-artifact continuation obeys backend producer-only reuse and never asks for another blind packet',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-review-reuse-host-')),agent=producer(root,{repair:false}),independent=isolatedCalls(),actions=[];
  const binding={stage:'script',run_id:'reused-review-run',packet_sha256:'b'.repeat(64)};
  const invoke=async(action,args)=>{
    actions.push({action,args});
    if(action==='begin')return {ok:true,started:true,producer_only:true,iteration:7,run:{id:binding.run_id}};
    if(action==='packet')throw Error('continuation attempted a second blind packet');
    if(action==='reserve')return {ok:true,reserved:true};
    if(action==='producer_packet')return {ok:true,packet:{protocol:'course-producer-qa/1',role:'producer',stage:'script',run_id:binding.run_id,binding,acceptance_mode:'targeted',input:{text:'当前修复版本'},checklist:[],evidence:{sources:[{id:'S',text:'合成来源'}]},editable_files:[]}};
    if(action==='producer_submit')return {ok:true,can_repair:false};
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding,requirements:[],execution:[]}};
    return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,bindings:new Map()});
  try{
    await handle('continue',{course_path:root,session_id:agent.session.id,stage:'script'});await handle.whenIdle();
    assert.equal(actions.some(call=>call.action==='packet'),false);assert.deepEqual(independent.calls.map(call=>call.role),['supervisor']);
    assert.ok(actions.some(call=>call.action==='reserve'&&call.args.key==='producer-7'));assert.equal(actions.some(call=>call.action==='repair'),false);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('producer targeted acceptance attaches current frame bytes and binds only actually sent current hashes',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-producer-frames-')),agent=producer(root,{repair:false}),independent=isolatedCalls(),actions=[],saved=[];
  const run_id='current-media-run',directory=join(root,'project/qa/ai-review',run_id,'producer-current');await mkdir(directory,{recursive:true});
  const bytes=Buffer.from([255,216,255,217]),sha256=createHash('sha256').update(bytes).digest('hex'),media_sha256='c'.repeat(64),frame={path:'qa/ai-review/'+run_id+'/producer-current/frame.jpg',sha256,media_sha256,time:1.25};await writeFile(join(directory,'frame.jpg'),bytes);
  const binding={stage:'pilot',run_id,packet_sha256:'b'.repeat(64)},attachments={saveImage:async value=>{saved.push(value);return {id:'native-current-image'};}};
  const packet={protocol:'course-producer-qa/1',role:'producer',stage:'pilot',run_id,binding,acceptance_mode:'targeted',input:{text:'当前媒体制作端核验'},checklist:[],evidence:{sources:[{id:'S',text:'合成来源'}],media:[{sha256:media_sha256}],frames:[frame]},editable_files:[]};
  const invoke=async(action,args)=>{
    actions.push({action,args});if(action==='begin')return {ok:true,started:true,producer_only:true,iteration:1,run:{id:run_id}};
    if(action==='reserve')return {ok:true,reserved:true};if(action==='producer_packet')return {ok:true,packet};if(action==='producer_submit')return {ok:true,can_repair:false};
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding,requirements:[],execution:[]}};return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,bindings:new Map(),attachments});
  try{
    const built=await producerInputContent({packet,course_path:root,attachments});assert.equal(built.content.filter(block=>block.type==='image').length,1);assert.deepEqual(saved[0].data,bytes);
    await handle('continue',{course_path:root,session_id:agent.session.id,stage:'pilot'});await handle.whenIdle();
    const result=actions.find(call=>call.action==='call_result'&&call.args.key==='producer-1');assert.deepEqual(result.args.sent_frames,[sha256]);assert.deepEqual(result.args.agent_audit.capabilities,['text','images']);
    assert.equal(result.args.agent_audit.outbound_projection.outbound_image_count,1);assert.deepEqual(result.args.agent_audit.producer_frame_evidence,[{id:'producer-frame-000',sha256,media_sha256,time:1.25}]);assert.deepEqual(independent.calls.map(call=>call.role),['supervisor']);
    await assert.rejects(producerInputContent({packet,course_path:root}),/缺少实际图片输入能力/);
    await assert.rejects(producerInputContent({packet:{...packet,evidence:{...packet.evidence,frames:[{...frame,media_sha256:'d'.repeat(64)}]}},course_path:root,attachments}),/媒体绑定/);
    await writeFile(join(directory,'frame.jpg'),Buffer.from('changed'));await assert.rejects(producerInputContent({packet,course_path:root,attachments}),/帧字节已改变/);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('source coverage status neither starts production nor creates formal checkpoints, while save is supervised on both sides',async()=>{
  const s=supervisionFixture();
  try{
    await s.handle.beforeTool(s.agent,'kgxc_course_source_coverage',{course_path:s.root,action:'status'});assert.equal(s.independent.calls.length,0);assert.equal(s.actions.length,0);
    await s.handle.beforeTool(s.agent,'kgxc_course_source_coverage',{course_path:s.root,action:'save'});assert.equal(s.independent.calls.length,1);
    await s.emit('tool/call',{callId:'read-coverage',name:'kgxc_course_source_coverage',arguments:JSON.stringify({action:'status'})});
    await s.emit('tool/result',{message:{toolCallId:'read-coverage',content:[{type:'text',text:'{"ok":true}'}]}});assert.equal(s.independent.calls.length,1,'read status is ordinary progress only');
    await s.emit('tool/call',{callId:'save-coverage',name:'kgxc_course_source_coverage',arguments:JSON.stringify({action:'save',report:{source_quote:'PRIVATE_COVERAGE_SOURCE'}})});assert.equal(s.independent.calls.length,2,'save awaits the formal precheck');
    await s.emit('tool/result',{message:{toolCallId:'save-coverage',content:[{type:'text',text:'{"ok":true}'}]}});assert.equal(s.independent.calls.length,3,'save result is correlated as a formal save');
    assert.equal(s.journal.at(-1).name,'kgxc_course_source_coverage');assert.equal(s.journal.at(-1).kind,'save');assert.doesNotMatch(JSON.stringify(s.journal),/PRIVATE_COVERAGE_SOURCE|source_quote/);
  }finally{await s.handle.dispose();}
});

test('comparison-only production blocks course mutations and idle or refresh cannot trigger blind review',async()=>{
  const s=supervisionFixture({bind:true});
  await mkdir(join(s.root,'source'),{recursive:true});await writeFile(join(s.root,'source/current-original.md'),'当前课程原件');
  // The fixture keeps this same real host handle and producer identity.
  const agent=s.agent,independent=s.independent,actions=s.actions;
  try{
    await s.handle.production({course_path:s.root,producer:agent,stage:'script',phase:'start',scope:'source-coverage',auto_review:false});
    for(const [name,args] of [['kgxc_course_source_coverage',{course_path:s.root,action:'status'}],['kgxc_course_source_coverage',{course_path:s.root,action:'save'}],['kgxc_course_editor',{course_path:s.root,action:'read'}],['read',{path:join(s.root,'source/current-original.md')}]])await s.handle.beforeTool(agent,name,args);
    for(const [name,args] of [['kgxc_course_update',{stage:'script'}],['kgxc_course_export',{}],['kgxc_course_editor',{action:'save'}],['write',{}],['edit',{}],['apply_patch',{}],['bash',{}],['read',{path:'/tmp/another-course/private.md'}],['kgxc_course_source_coverage',{course_path:'/tmp/other-course',action:'save'}]])await assert.rejects(s.handle.beforeTool(agent,name,args),/本次仅生成原件/);
    await s.handle.production({course_path:s.root,producer:agent,stage:'script',phase:'end'});await s.handle.onIdle(agent);await s.handle('sync',{course_path:s.root,session_id:agent.session.id});await s.handle.whenIdle();
    await assert.rejects(s.handle.beforeTool(agent,'kgxc_course_update',{course_path:s.root,stage:'script'}),/须有新的明确用户制作指令/);
    assert.equal(independent.calls.every(call=>call.role==='supervisor'),true);assert.equal(actions.some(call=>['begin','packet','producer_packet'].includes(call.action)),false);
    await s.emit('user/message',{id:'new-explicit-creation-message',source:{kind:'user'},content:[{type:'text',text:'现在请按既定方案继续逐字稿制作。'}]});
    await s.handle.beforeTool(agent,'kgxc_course_update',{course_path:s.root,stage:'script'});
    assert.ok(actions.some(call=>call.action==='production_event'&&call.args.phase==='start'&&call.args.execution.some(fact=>fact.type==='production/request'&&fact.operation==='conversation-tool')),'new real user direction may start a new production task');
  }finally{await s.handle.dispose();await rm(s.root,{recursive:true,force:true});}
});

test('comparison-only reads resolve file links and linked parents before allowing current-course access',async()=>{
  const s=supervisionFixture({bind:true}),outside=await mkdtemp(join(tmpdir(),'kgxc-outside-coverage-'));
  const source=join(s.root,'source'),current=join(source,'current.md'),other=join(outside,'outside.md');
  await mkdir(source,{recursive:true});await writeFile(current,'本课当前原件');await writeFile(other,'本课范围之外');
  await symlink(other,join(source,'outside-link.md'));await symlink(outside,join(source,'outside-parent'));await symlink(current,join(source,'current-link.md'));
  const escaped=[join(source,'outside-link.md'),join(source,'outside-parent/outside.md')];
  try{
    await s.handle.production({course_path:s.root,producer:s.agent,stage:'script',phase:'start',scope:'source-coverage',auto_review:false});
    for(const path of [current,join(source,'current-link.md')])await s.handle.beforeTool(s.agent,'read',{path});
    for(const path of escaped)await assert.rejects(s.handle.beforeTool(s.agent,'read',{path}),/本次仅生成原件/);
    await assert.rejects(s.handle.beforeTool(s.agent,'read_file',{file_path:escaped[0]}),/本次仅生成原件/);
    await s.handle.production({course_path:s.root,producer:s.agent,stage:'script',phase:'end'});
    await s.handle.beforeTool(s.agent,'read',{path:current});
    for(const path of escaped)await assert.rejects(s.handle.beforeTool(s.agent,'read',{path}),/须有新的明确用户制作指令/);
    assert.equal(s.independent.calls.every(call=>call.role==='supervisor'),true);
  }finally{await s.handle.dispose();await rm(s.root,{recursive:true,force:true});await rm(outside,{recursive:true,force:true});}
});

test('producer host fills only absent binding after its native snapshot and archives raw body separately',async()=>{
  for(const mode of ['missing','correct','null','false','wrong']){
    const root=await mkdtemp(join(tmpdir(),'kgxc-producer-binding-')),agent=producer(root,{repair:false}),independent=isolatedCalls(),actions=[];
    const binding={stage:'script',run_id:'synthetic-binding-run',packet_sha256:'b'.repeat(64)};
    agent.beforeResponse=(packet,result)=>{if(mode!=='missing')result.binding=mode==='correct'?packet.binding:mode==='null'?null:mode==='false'?false:{...packet.binding,run_id:'wrong-run'};};
    const invoke=async(action,args)=>{
      actions.push({action,args});
      if(action==='begin')return {ok:true,started:true,run:{id:binding.run_id}};
      if(action==='reserve')return {ok:true,reserved:true};
      if(action==='packet')return {ok:true,packet:{protocol:REVIEW_PROTOCOL,stage:'script',run_id:binding.run_id,fingerprint:'f',artifact_sha256:'a'.repeat(64),binding,review_contract:{},checklist:[],input:{text:'synthetic current body'},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:'transcript',kind:'transcript',sha256:'a'.repeat(64)}]}};
      if(action==='producer_packet')return {ok:true,packet:{protocol:'course-producer-qa/1',role:'producer',stage:'script',run_id:binding.run_id,binding,input:{text:'synthetic current body'},checklist:[],evidence:{sources:[{id:'S',text:'synthetic source'}]},editable_files:[]}};
      if(action==='producer_submit')return {ok:true,can_repair:false};
      if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding,requirements:[],execution:[]}};
      return {ok:true};
    };
    const handle=host(root,agent,independent,{invoke,bindings:new Map()});
    try{
      await handle('continue',{course_path:root,session_id:agent.session.id,stage:'script'});await handle.whenIdle();
      assert.match(agent.lastPrompt,/不复制 binding 或 agent_audit/);assert.doesNotMatch(agent.lastPrompt,/binding:本轮原样绑定/);
      const submitted=actions.filter(call=>call.action==='producer_submit'),directory=join(root,'project/qa/ai-review',binding.run_id,'calls');
      const raw=JSON.parse(await readFile(join(directory,'producer-0.model.json'),'utf8')),envelope=JSON.parse(await readFile(join(directory,'producer-0.host.json'),'utf8'));
      assert.equal(Object.hasOwn(raw.body,'binding'),mode!=='missing');
      if(['missing','correct'].includes(mode)){
        assert.equal(submitted.length,1);assert.deepEqual(submitted[0].args.result.binding,binding);
        assert.equal(submitted[0].args.result.agent_audit.binding_host.source,mode==='missing'?'host-attached-missing':'model-present-verified');
        assert.equal(envelope.envelope_returned,true);assert.deepEqual(envelope.result.binding,binding);
      }else{
        assert.equal(submitted.length,0);assert.equal(envelope.envelope_returned,false);assert.equal(envelope.result,null);
        assert.match(actions.findLast(call=>call.action==='finish').args.error,/错误的成果绑定/);
        assert.equal(actions.some(call=>call.action==='call_result'&&call.args.error&&call.args.model_invoked===true),true);
      }
      assert.deepEqual(agent.capabilities,{restrict:0,guard:0,executor:0});
    }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
  }
});

test('native idle routes one blind review to a CAS repair batch then producer targeted acceptance and supervision',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls(),handle=host(root,agent,independent);
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const node=(await handle('status',{course_path:root})).review.nodes.script;
    assert.equal(node.passed,true,node.reason);assert.equal(node.user_confirmed,false);assert.equal(node.repairs,1);assert.equal(node.calls,5);assert.equal(node.usage.totalTokens,280);
    assert.deepEqual(independent.calls.map(call=>call.role),['reviewer','supervisor','supervisor']);
    const [oldPacket]=independent.calls;
    assert.ok(oldPacket.packet.input.text.includes('先核对订单，'));assert.ok(agent.lastPacket.input.text.includes('先核对订单日期'));
    assert.equal(agent.lastPacket.acceptance_mode,'targeted');assert.ok(agent.lastPacket.issue_ledger.length);
    assert.equal(node.run.blind_report.binding.artifact_sha256,oldPacket.packet.artifact_sha256,'baseline report remains bound to the original reviewed bytes');
    assert.match(JSON.parse(await readFile(join(root,'project/script-editor.json'),'utf8')).text,/先核对订单日期/);
    assert.ok((await readdir(join(root,'project/qa/ai-review',node.run.id,'repair-1'))).includes('changes.diff'));
    const ids=node.run.calls.filter(call=>call.agent_audit?.role==='reviewer').map(call=>call.agent_audit.id);assert.equal(new Set(ids).size,1);
    assert.ok(node.run.calls.some(call=>call.agent_audit?.id===agent.id&&call.role==='producer'));
    assert.ok(node.run.calls.filter(call=>call.role==='producer').every(call=>call.agent_audit.producer_qa_wait.effective_timeout_ms===600000));
    await handle('sync',{course_path:root,session_id:agent.session.id});await handle.whenIdle();assert.equal(independent.calls.length,3,'refresh does not replay the repaired input');
    assert.deepEqual(agent.capabilities,{restrict:0,guard:0,executor:0});
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('a failing independent supervisor holds the course and blocks every repair, render and future production tool',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls({supervisorPass:false});let repairCalls=0;
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{if(action==='repair')repairCalls++;return callReview(action,args);}});
  try{
    await handle('sync',{course_path:root,session_id:agent.session.id});await handle.whenIdle();
    const value=(await callReview('status',{course_path:root})).review;
    assert.equal(repairCalls,0);assert.equal(value.hold.held,true);assert.equal(value.nodes.script.passed,false);
    assert.match(JSON.parse(await readFile(join(root,'project/script-editor.json'),'utf8')).text,/先核对订单，再/);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('explicit production is supervised through real backend and persists request idempotency across host replacement',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls(),options={bindings:new Map()};await registerProductionObligations(root);agent.completeWork=message=>returnProductionResult(root,message);let handle=host(root,agent,independent,options);
  const observes=[];agent.onEvent=event=>{const pending=handle.observe(agent,event).catch(()=>{});observes.push(pending);};
  try{
    await callReview('enable',{course_path:root});let release;const gate=new Promise(resolve=>{release=resolve;});agent.beforeWork=()=>gate;
    const args={course_path:root,session_id:agent.session.id,stage:'storyboard',instruction:'PRODUCE_DIRECTION_SENTINEL：读取当前合成文件并修复分镜。',request_id:'synthetic-controlled-production'};
    const first=await handle('produce',args);assert.equal(first.started,true);
    assert.equal((await handle('produce',args)).started,false);release();await handle.whenIdle();await Promise.all(observes);
    assert.equal(agent.workCalls,1);assert.equal(independent.calls.every(call=>call.role==='supervisor'),true);assert.equal(independent.calls.length,2,'short ordinary progress is persisted between start/end checks');
    const state=(await callReview('status',{course_path:root})).review,operation=state.supervision.operations.find(item=>item.operation_id===first.operation_id);
    const capability=JSON.parse(await readFile(join(root,'project/qa/review-capabilities',first.operation_id+'.json'),'utf8'));
    assert.equal(capability.inference_performed,false);assert.equal(capability.course_blind_review,false);assert.deepEqual(capability.route,{provider:FIXED_ROUTE.provider,model:FIXED_ROUTE.model});
    assert.equal(capability.capabilities.includes('audio_listening'),false,'route preflight cannot invent continuous hearing');
    assert.equal(operation.phase,'end');assert.match(JSON.stringify(operation.events),/PRODUCE_DIRECTION_SENTINEL/);assert.ok(operation.events.some(event=>event.phase==='progress'));
    const summary=JSON.parse(await readFile(join(root,'project/qa/ai-supervision',first.operation_id,'producer-dispatch.json'),'utf8'));
    assert.equal(summary.agent_audit.id,agent.id);assert.equal(summary.agent_audit.input_scope,'producer-work-snapshot');assert.equal(summary.agent_audit.outbound_steps.length,1);
    assert.deepEqual(summary.agent_audit.outbound_steps[0].tools,['work_tool']);assert.equal(summary.usage.totalTokens,23);assert.match(agent.lastWorkMessage.content[0].text,/PRODUCE_DIRECTION_SENTINEL/);
    await handle.dispose();handle=host(root,agent,independent,options);const before=independent.calls.length;
    const replay=await handle('produce',args);await handle.whenIdle();assert.equal(replay.started,false);assert.equal(replay.operation_id,first.operation_id);assert.equal(agent.workCalls,1);assert.equal(independent.calls.length,before);
    await assert.rejects(handle('produce',{...args,instruction:'DIFFERENT_TASK_SAME_REQUEST'}),/绑定不同|覆盖|重启/);assert.equal(agent.workCalls,1);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('course hold blocks a new production claim and interrupts an active managed producer without replay',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls();await registerProductionObligations(root);agent.completeWork=message=>returnProductionResult(root,message);const handle=host(root,agent,independent,{bindings:new Map()});
  const observes=[];agent.onEvent=event=>observes.push(handle.observe(agent,event).catch(()=>{}));
  try{
    await callReview('enable',{course_path:root});await handle('hold',{course_path:root,held:true,reason:'synthetic held'});
    const args={course_path:root,session_id:agent.session.id,stage:'storyboard',instruction:'读取合成文件后继续当前任务',request_id:'synthetic-production-hold'};
    await assert.rejects(handle('produce',args),/暂停/);assert.equal(agent.workCalls,undefined);assert.equal(independent.calls.length,0);
    await handle('hold',{course_path:root,held:false});agent.cancelled=false;
    let entered;const ready=new Promise(resolve=>{entered=resolve;});agent.beforeWork=()=>new Promise((_,reject)=>{agent.onCancel=()=>reject(Error('synthetic native stop'));entered();});
    const first=await handle('produce',{...args,request_id:'synthetic-active-production'});assert.equal(first.started,true);await ready;
    await handle('hold',{course_path:root,held:true,reason:'explicit synthetic stop'});await handle.whenIdle();await Promise.all(observes);
    assert.equal(agent.cancelled,true);assert.equal(agent.workCalls,1);assert.equal((await callReview('status',{course_path:root})).review.hold.held,true);
    const summary=JSON.parse(await readFile(join(root,'project/qa/ai-supervision',first.operation_id,'producer-dispatch.json'),'utf8'));
    assert.equal(summary.execution_state.model_invoked,null);assert.deepEqual(summary.usage,{});assert.equal(agent.capabilities.guard,0);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('an authorized storyboard pass dispatches pilot production through the same managed snapshot without a new approval',async()=>{
  const root=await fixture(),agent=producer(root,{repair:false}),independent=isolatedCalls(),actions=[],operations=new Set();await registerProductionObligations(root);agent.completeWork=message=>returnProductionResult(root,message);
  const binding={stage:'storyboard',run_id:'synthetic-board-run',packet_sha256:'b'.repeat(64)};
  const invoke=async(action,args)=>{
    actions.push({action,args});
    if(['production_dispatch','capability_requirements'].includes(action))return callReview(action,args);
    if(action==='production_event'&&args.operation_id?.startsWith('produce-'))return callReview(action,args);
    if(action==='begin')return {ok:true,started:true,run:{id:binding.run_id}};
    if(action==='packet')return {ok:true,packet:{protocol:REVIEW_PROTOCOL,stage:'storyboard',run_id:binding.run_id,fingerprint:'f',artifact_sha256:'a'.repeat(64),binding,review_contract:{},checklist:[],input:{storyboard:{segments:[{id:'S1',action:'当前对象变化'}]}},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:'storyboard',kind:'storyboard',sha256:'a'.repeat(64)}]}};
    if(action==='producer_packet')return {ok:true,packet:{protocol:'course-producer-qa/1',stage:'storyboard',run_id:binding.run_id,role:'producer',binding,input:{text:'当前逐字稿'},checklist:[],evidence:{sources:[{id:'source',text:'合成原件'}]},editable_files:[]}};
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:args.operation_id?{operation_id:args.operation_id}:binding,execution:[],requirements:[]}};
    if(action==='reserve')return {ok:true,reserved:true};
    if(action==='producer_submit')return {ok:true,can_repair:false};
    if(action==='production_event'){const started=!operations.has(args.operation_id);operations.add(args.operation_id);return {ok:true,started};}
    if(action==='finish')return {ok:true,continuation:{authorized:true,stage:'pilot',requires_user_confirmation:false,review_run_id:binding.run_id,fingerprint:'current-board-fp',actor:'ai-production-preflight'}};
    return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,bindings:new Map()});agent.onEvent=event=>{void handle.observe(agent,event).catch(()=>{});};
  try{
    await handle('continue',{course_path:root,session_id:agent.session.id,stage:'storyboard',request_id:'synthetic-board-pass'});await handle.whenIdle();
    assert.equal(agent.workCalls,1);assert.equal(agent.lastWorkMessage.source.kind,'kgxc-producer-work');assert.ok(agent.lastWorkMessage.content[0].text.includes(AUTHORING_PREFLIGHT_PROMPT));assert.ok(agent.lastWorkMessage.content[0].text.includes(SOURCE_COVERAGE_PROMPT));assert.match(agent.lastWorkMessage.content[0].text,/三个完整真实有声小样/);
    const initial=actions.find(call=>call.action==='production_event'&&call.args.phase==='start');assert.equal(initial.args.stage,'pilot');assert.match(initial.args.operation_id,/^produce-/);
    assert.equal(actions.some(call=>['approve','confirm'].includes(call.action)),false);assert.ok(independent.calls.filter(call=>call.role==='supervisor').length>=3);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('producer-only retry retains the accepted blind report and unknown failure through repair and targeted acceptance',async()=>{
  const root=await fixture(),agent=producer(root,{failCalls:1}),independent=isolatedCalls(),actions=[];
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{actions.push({action,args});return callReview(action,args);}});
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const failed=(await callReview('status',{course_path:root})).review.nodes.script;
    assert.equal(failed.run.status,'failed');assert.equal(failed.run.blind_report.passed,false,'an accepted problem report need not pass to resume source QA');
    const oldFailure=structuredClone(failed.run.calls.find(call=>call.role==='producer'));
    assert.equal(oldFailure.usage_status,'unknown');assert.deepEqual(oldFailure.usage,{});assert.equal(oldFailure.model_invoked,null);
    let release;const gate=new Promise(resolve=>{release=resolve;});agent.beforeResponse=()=>gate;
    const args={course_path:root,session_id:agent.session.id,stage:'script',run_id:failed.run.id,binding:independent.calls[0].packet.binding,request_id:'synthetic-same-artifact-producer-retry'};
    const resumed=await handle('resume_producer',args);assert.equal(resumed.started,true);assert.match(resumed.producer_key,/^producer-retry-/);
    const duplicate=await handle('resume_producer',args);assert.equal(duplicate.started,false);assert.equal(duplicate.attempt_id,resumed.attempt_id);
    release();await handle.whenIdle();
    const node=(await callReview('status',{course_path:root})).review.nodes.script;
    assert.equal(node.passed,true,node.reason);assert.equal(node.repairs,1);assert.equal(node.calls,6);
    assert.deepEqual(node.run.calls.find(call=>call.key===oldFailure.key),oldFailure,'old failure and unknown usage remain exact');
    assert.deepEqual(independent.calls.map(call=>call.role),['reviewer','supervisor','supervisor']);
    assert.equal(actions.filter(call=>call.action==='packet').length,1,'resume and post-repair acceptance never issue another blind packet');
    const retryCall=node.run.calls.find(call=>call.key===resumed.producer_key);assert.equal(retryCall.agent_audit.id,agent.id);assert.equal(retryCall.agent_audit.input_scope,'producer-qa-snapshot');
    assert.ok(node.run.calls.some(call=>call.key===resumed.supervisor_key&&call.role==='supervisor'));
    const projection=JSON.parse(await readFile(join(root,'project/qa/ai-review',node.run.id,'calls',resumed.producer_key+'.projection.json'),'utf8'));
    assert.deepEqual(projection.projection.binding,args.binding);assert.equal(projection.projection.outbound_message_count,2);assert.ok(projection.projection.excluded_history_count>0);
    assert.equal(retryCall.agent_audit.input_messages.length,1);assert.ok(retryCall.agent_audit.native_log_input_messages.length>=1);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('a real CAS rejection stops an initial host run even when the backend has remaining retry budget',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls(),actions=[];let repairRecovery;
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{actions.push({action,args});const value=await callReview(action,args);if(action==='repair_error')repairRecovery=value;return value;}});
  try{
    const before=await readFile(join(root,'project/script-editor.json'),'utf8');agent.beforeResponse=(_packet,result)=>{result.repairs[0].before_sha256='0'.repeat(64);};
    await handle.onIdle(agent);await handle.whenIdle();const node=(await callReview('status',{course_path:root})).review.nodes.script;
    assert.equal(repairRecovery.retry,true,'available budget never authorizes rereview of a rejected transaction');assert.equal(node.run.status,'failed');assert.match(node.run.reason,/文件已被人工或其他任务修改/);assert.equal(node.run.last_error,node.run.reason);
    assert.equal(node.calls,3);assert.equal(node.repairs,1);assert.deepEqual(independent.calls.map(call=>call.role),['reviewer','supervisor']);assert.equal(actions.filter(call=>call.action==='reserve'&&call.args.role==='reviewer').length,1);assert.equal(actions.filter(call=>call.action==='packet').length,1);assert.equal(actions.filter(call=>call.action==='repair').length,1);
    assert.equal(node.run.iterations.length,1);assert.ok(node.run.blind_report);assert.ok(node.run.producer_report);assert.equal(node.run.supervisor_report.passed,true);assert.equal(node.run.iterations[0].proposed_repairs.length,1);assert.equal(await readFile(join(root,'project/script-editor.json'),'utf8'),before);
    await handle.onIdle(agent);await handle.whenIdle();assert.equal(independent.calls.filter(call=>call.role==='reviewer').length,1);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('a real CAS repair rejection preserves accepted reports and earlier unknown usage after producer-only resume',async()=>{
  const root=await fixture(),agent=producer(root,{failCalls:1}),independent=isolatedCalls(),actions=[];
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{actions.push({action,args});return callReview(action,args);}});
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const first=(await callReview('status',{course_path:root})).review.nodes.script,oldFailure=structuredClone(first.run.calls.find(call=>call.role==='producer')),acceptedBlind=structuredClone(first.run.blind_report);
    assert.equal(oldFailure.usage_status,'unknown');assert.deepEqual(oldFailure.usage,{});
    const before=await readFile(join(root,'project/script-editor.json'),'utf8');
    agent.beforeResponse=(_packet,result)=>{result.repairs[0].before_sha256='0'.repeat(64);};
    const resumed=await handle('resume_producer',{course_path:root,session_id:agent.session.id,stage:'script',run_id:first.run.id,binding:independent.calls[0].packet.binding,request_id:'synthetic-repair-cas-rejection'});assert.equal(resumed.started,true);await handle.whenIdle();
    const node=(await callReview('status',{course_path:root})).review.nodes.script,run=node.run;
    assert.equal(run.status,'failed');assert.match(run.reason,/文件已被人工或其他任务修改/);assert.equal(run.last_error,run.reason);assert.equal(run.error_history.length,1);assert.equal(run.error_history[0].reason,run.reason);
    assert.equal(node.calls,4);assert.equal(node.repairs,1);assert.equal(node.usage.totalTokens,160);assert.deepEqual(run.calls.find(call=>call.key===oldFailure.key),oldFailure);assert.deepEqual(run.blind_report,acceptedBlind);
    assert.equal(run.producer_report.agent_audit.id,agent.id);assert.equal(run.supervisor_report.passed,true);assert.equal(run.iterations.length,1);assert.equal(run.iterations[0].proposed_repairs[0].before_sha256,'0'.repeat(64));assert.equal(run.iterations[0].repair_attempted,true);
    assert.deepEqual(independent.calls.map(call=>call.role),['reviewer','supervisor']);assert.equal(actions.filter(call=>call.action==='reserve'&&call.args.role==='reviewer').length,1);assert.equal(actions.filter(call=>call.action==='packet').length,1);assert.equal(actions.filter(call=>call.action==='repair').length,1);assert.equal(actions.filter(call=>call.action==='repair_error').length,1);
    assert.equal(await readFile(join(root,'project/script-editor.json'),'utf8'),before);
    await handle.onIdle(agent);await handle.whenIdle();assert.equal(independent.calls.filter(call=>call.role==='reviewer').length,1,'native idle must not reopen unchanged failed input');assert.equal(actions.filter(call=>call.action==='reserve'&&call.args.role==='reviewer').length,1);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('no native isolated-agent capability fails explicitly and never falls back to direct LLM review',async()=>{
  const root=await fixture(),agent=producer(root);let direct=0;
  const services={agents:{get:id=>id===agent.session.id?agent:undefined},llm:{prepareCall:()=>{direct++;throw Error('fallback forbidden');}},agentDefaultModel:{currentSelection:()=>{throw Error('Must use the course session, not the global model default');}}};
  const handle=reviewHost({get:name=>services[name]},{bindings:new Map([[root,agent]])});
  try{
    await handle('sync',{course_path:root,session_id:agent.session.id});await handle.whenIdle();
    const node=(await handle('status',{course_path:root})).review.nodes.script;
    assert.equal(direct,0);assert.equal(node.passed,false);assert.match(node.reason,/可隔离|原生 Agent/);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('actual lifecycle supervises start, committed progress and failure, cancels producer and reports export cancellation readback',async()=>{
  const root='/tmp/kgxc-supervision-synthetic',agent=producer(root,{repair:false}),calls=[],independent=isolatedCalls(),journal=[];let phase='start',blocked=false,polls=0;
  const invoke=async(action,args)=>{
    calls.push({action,args});
    if(action==='production_event'){phase=args.phase;journal.push(...args.execution);return {ok:true};}
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:args.operation_id,execution_sha256:randomUUID()},execution:structuredClone(journal),requirements:[]}};
    if(action==='reserve')return {ok:true,reserved:true};
    if(action==='supervisor_submit'){if(phase==='failure'){blocked=true;return {ok:true,report:{passed:false}};}return {ok:true};}
    return {ok:true};
  };
  independent.run=async options=>{const entry=await isolatedCalls({supervisorPass:phase!=='failure'}).run(options);independent.calls.push({role:options.role,packet:options.packet});return entry;};
  const handle=host(root,agent,independent,{invoke,tool:async()=>({ok:true,job:{status:++polls>1?'cancelled':'rendering'}}),pause:async()=>{}});
  try{
    await handle.production({course_path:root,producer:agent,stage:'pilot',user_instruction:'USER_DIRECTION_SENTINEL'});
    assert.match(JSON.stringify(independent.calls[0].packet.execution),/USER_DIRECTION_SENTINEL/);
    await handle.observe(agent,{seq:1,time:1,type:'request/header',data:{header:{config:FIXED_ROUTE,tools:[{name:'bash'}]}}});
    assert.equal(independent.calls.length,1,'a correct route header is persisted without another model call');
    await handle.production({course_path:root,producer:agent,stage:'pilot',phase:'progress',execution:[{type:'export/registered',job_id:'owned-export',status:'rendering'}]});
    assert.equal(independent.calls.length,2,'actual export lifecycle remains an immediate checkpoint');
    await assert.rejects(handle.observe(agent,{seq:2,time:2,type:'tool/result',data:{message:{toolCallId:'bad',isError:true,content:[{type:'text',text:'actual renderer failure'}]}}}),/阻止/);
    assert.equal(blocked,true);assert.equal(agent.cancelled,true);assert.ok(handle.blockReason(agent));
    await assert.rejects(handle.beforeTool(agent,'bash',{}),/停止/);assert.ok(calls.some(call=>call.action==='hold'));
    const status=await handle('supervision_status',{course_path:root});assert.equal(polls,2);assert.deepEqual(status.runtime.stop_result,{job_id:'owned-export',status:'cancelled',stop_pending:false});
  }finally{await handle.dispose();}
});

test('ordinary supervision batches exactly 32 facts and end flushes every persisted fact',async()=>{
  const s=supervisionFixture();
  try{
    await s.start();await s.emit('request/header',{header:{config:FIXED_ROUTE,tools:[{name:'read'}]}});
    for(let i=0;i<30;i++)await s.emit('step/start',{turn:1,step:i+1});
    assert.equal(s.journal.length,31);assert.equal(s.independent.calls.length,1);
    await s.emit('step/start',{turn:1,step:31});assert.equal(s.independent.calls.length,2);assert.equal(s.independent.calls[1].packet.execution.length,32);
    await s.emit('step/start',{turn:1,step:32});await s.emit('turn/end',{turn:1,reason:{kind:'completed'}});
    assert.equal(s.independent.calls.length,3);assert.equal(s.journal.length,34);assert.deepEqual(s.independent.calls.at(-1).packet.execution,s.journal);
  }finally{await s.handle.dispose();}
});

test('ordinary shell jobs are persisted without immediate checks, while their failure still blocks promptly',async()=>{
  const s=supervisionFixture({allow:packet=>!packet.execution.some(fact=>fact.failed)});
  try{
    await s.start();await s.emit('tool/call',{callId:'shell',name:'bash',arguments:'{"command":"python /tmp/synthetic.py"}'});
    await s.emit('job/registered',{jobId:'shell-job',toolCall:{callId:'shell'}});await s.emit('job/settled',{jobId:'shell-job',status:'completed',detail:'exit code: 0'});
    await s.emit('tool/result',{message:{toolCallId:'shell',content:[{type:'text',text:'{}'}]}});
    assert.equal(s.journal.length,4);assert.equal(s.independent.calls.length,1);assert.equal(s.toolPolls,0,'a shell job is never polled as a course export');
    await assert.rejects(s.emit('job/settled',{jobId:'failed-shell',status:'failed',detail:'exit code: 1'}),/阻止/);
    assert.equal(s.independent.calls.length,2);assert.equal(s.journal.at(-1).failed,true);assert.equal(s.agent.cancelled,true);assert.ok(s.handle.blockReason(s.agent));
  }finally{await s.handle.dispose();}
});

test('formal mutation checks really await before execution and correlate results before the next tool',async()=>{
  let enterBefore,enterAfter,releaseBefore,releaseAfter;
  const beforeEntered=new Promise(resolve=>{enterBefore=resolve;}),afterEntered=new Promise(resolve=>{enterAfter=resolve;}),beforeGate=new Promise(resolve=>{releaseBefore=resolve;}),afterGate=new Promise(resolve=>{releaseAfter=resolve;});
  const s=supervisionFixture({onCall:async({packet})=>{const fact=packet.execution.at(-1);if(fact?.call_id!=='formal-update')return;if(fact.type==='tool/call'){enterBefore();await beforeGate;}if(fact.type==='tool/result'){enterAfter();await afterGate;}}});
  try{
    await s.start();const observed=s.emit('tool/call',{callId:'formal-update',name:'kgxc_course_update',arguments:JSON.stringify({body:'PRIVATE_ARGUMENT_BODY'})});await beforeEntered;
    let wrote=false;const dispatch=s.handle.beforeTool(s.agent,'kgxc_course_update',{}).then(()=>{wrote=true;});await Promise.resolve();assert.equal(wrote,false);
    releaseBefore();await Promise.all([observed,dispatch]);assert.equal(wrote,true);
    const settled=s.emit('tool/result',{message:{toolCallId:'formal-update',content:[{type:'text',text:'{"completed":true}'}]}});await afterEntered;
    let nextRan=false;const next=s.handle.beforeTool(s.agent,'read',{}).then(()=>{nextRan=true;});await Promise.resolve();assert.equal(nextRan,false);
    releaseAfter();await Promise.all([settled,next]);assert.equal(nextRan,true);assert.equal(s.independent.calls.length,3);
    assert.equal(s.journal.at(-1).name,'kgxc_course_update');assert.equal(s.journal.at(-1).kind,'save');assert.doesNotMatch(JSON.stringify(s.journal),/PRIVATE_ARGUMENT_BODY/);
    for(const name of ['write','edit','apply_patch','kgxc_course_export']){
      const before=s.independent.calls.length;await s.emit('tool/call',{callId:name,name,arguments:'{}'});await s.emit('tool/result',{message:{toolCallId:name,content:[{type:'text',text:'{}'}]}});assert.equal(s.independent.calls.length,before+2,name+' retains both checks');assert.equal(s.journal.at(-1).name,name);
    }
    const beforeExport=s.independent.calls.length;await s.handle.production({course_path:s.root,producer:s.agent,stage:'script',phase:'progress',execution:[{type:'export/registered',job_id:'actual-export',status:'rendering'}]});await s.handle.production({course_path:s.root,producer:s.agent,stage:'script',phase:'end',execution:[{type:'export/settled',job_id:'actual-export',status:'complete'}]});assert.equal(s.independent.calls.length,beforeExport+2);
  }finally{releaseBefore?.();releaseAfter?.();await s.handle.dispose();}
});

test('a blocking formal precheck never dispatches its mutation and a wrong actual route never calls another model',async()=>{
  const s=supervisionFixture({allow:packet=>packet.execution.at(-1)?.name!=='write'});
  try{
    await s.start();const observed=s.emit('tool/call',{callId:'blocked-write',name:'write',arguments:'{}'});let wrote=false;
    const dispatch=s.handle.beforeTool(s.agent,'write',{}).then(()=>{wrote=true;});await assert.rejects(observed,/阻止/);await assert.rejects(dispatch,/阻止|停止/);assert.equal(wrote,false);assert.equal(s.agent.cancelled,true);
  }finally{await s.handle.dispose();}
  const route=supervisionFixture();
  try{
    await route.start();await assert.rejects(route.emit('request/header',{header:{config:{provider:'unexpected-provider',model:FIXED_ROUTE.model}}}),/通道|codex-chatgpt/);
    assert.equal(route.independent.calls.length,1);assert.equal(route.journal.at(-1).route.provider,'unexpected-provider');assert.equal(route.agent.cancelled,true);assert.ok(route.handle.blockReason(route.agent));
  }finally{await route.handle.dispose();}
});

test('tool correlation retains only bounded identities and refuses overflow after persisting its fact',async()=>{
  const s=supervisionFixture();
  try{
    await s.start();for(let i=0;i<129;i++){await s.emit('tool/call',{callId:'settled-'+i,name:'read',arguments:'{}'});await s.emit('tool/result',{message:{toolCallId:'settled-'+i,content:[]}});}
    assert.equal(s.handle.blockReason(s.agent),undefined,'the bound is not a limit on completed calls');
    for(let i=0;i<128;i++)await s.emit('tool/call',{callId:'pending-'+i,name:'read',arguments:JSON.stringify({ignored:'PRIVATE_BODY_'+i})});
    await assert.rejects(s.emit('tool/call',{callId:'overflow',name:'read',arguments:'{}'}),/128/);assert.equal(s.journal.length,387);assert.equal(s.journal.at(-1).call_id,'overflow');assert.equal(s.agent.cancelled,true);assert.doesNotMatch(JSON.stringify(s.journal),/PRIVATE_BODY_/);
  }finally{await s.handle.dispose();}
});

test('the real 117-fact metadata snapshot replays 19 old checks as 6 conservative checks without network',async()=>{
  // Event order/name/call association from snapshot SHA0821c669b69c213ff9aa9dfac388183adc2095db58f48ec6847319a7b6dff608.
  // IDs, times and arguments are synthetic; no user instruction, course path or body is copied.
  const trace='T S H +skill - S +kgxc_course_status - S +kgxc_course_editor - S +read - S +skill - S +todo_write - S +bash J j - S +read - S +read - S +read - S +grep - S +read - S +read - S +glob - S +read - S +read - S +glob - S +grep - S +read - S +grep - S +glob - S +read - S +grep - S +glob - S +write - S +bash J j - S +kgxc_course_status - S +read - S +kgxc_course_editor - S +read - S +read - S +read - S +todo_write - S +read - S +read - S +read - S'.split(' ');
  const s=supervisionFixture();let callId,callCount=0,step=0,oldCount=1,pending=0;
  try{
    await s.start([{type:'production/request'},{type:'production/dispatch'}]);
    for(const token of trace){
      let type,data;
      if(token.startsWith('+')){type='tool/call';data={callId:callId='synthetic-call-'+(++callCount),name:token.slice(1),arguments:'{}'};}
      else if(token==='-'){type='tool/result';data={message:{toolCallId:callId,content:[{type:'text',text:'{}'}]}};}
      else if(token==='T'){type='turn/start';data={turn:1};}
      else if(token==='S'){type='step/start';data={turn:1,step:++step};}
      else if(token==='H'){type='request/header';data={header:{config:FIXED_ROUTE}};}
      else if(token==='J'){type='job/registered';data={jobId:'job-'+callId,toolCall:{callId}};}
      else {type='job/settled';data={jobId:'job-'+callId,status:'completed',detail:'exit code: 0'};}
      pending++;if(pending>=8||token==='H'||token==='J'||token==='j'){oldCount++;pending=0;}await s.emit(type,data);
    }
    assert.equal(callCount,36);assert.equal(s.journal.length,117);assert.equal(oldCount,19);assert.equal(s.independent.calls.length,6);assert.equal(s.actions.filter(call=>call.action==='reserve').length,6);assert.equal(s.independent.calls.at(-1).packet.execution.length,113,'last four facts are persisted for the next key boundary');
    assert.equal(s.journal.filter(fact=>fact.type==='tool/result'&&fact.name==='write').length,1);
  }finally{await s.handle.dispose();}
});

test('blind payload accepts only current storyboard and rejects source/history/repair fields',()=>{
  const packet={protocol:REVIEW_PROTOCOL,stage:'storyboard',artifact_sha256:'a'.repeat(64),run_id:'r',fingerprint:'f',binding:{packet_sha256:'b'.repeat(64)},review_contract:{},checklist:[],input:{storyboard:{segments:[{id:'s',beats:[{at:0,object:'当前讲述对象'}]}]}},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:'storyboard',kind:'storyboard',sha256:'a'.repeat(64)}]};
  assert.deepEqual(blindPayload(packet).input,packet.input);
  assert.throws(()=>blindPayload({...packet,plan:{expected:'secret'}}),/未授权上下文/);
  assert.throws(()=>blindPayload({...packet,input:{...packet.input,text:'source script'}}),/当前分镜/);
  assert.throws(()=>assertReadOnlyReport({findings:[],repairs:[]}),/修改载荷/);
  assert.throws(()=>assertReadOnlyReport({items:[{write:'payload'}]}),/修改载荷/);
});

test('native idle handoff automatically reviews all four current stages without a UI request, preserves holds and deduplicates replay',async()=>{
  const root='/tmp/kgxc-idle-four-stage-fixture',agent=producer(root,{repair:false}),independent=isolatedCalls(),stages=['script','storyboard','pilot','final'];
  const nodes=Object.fromEntries(stages.map(stage=>[stage,{fingerprint:stage+'-current',status:'ready',passed:false,user_confirmed:false}]));
  const review={hold:{held:true},policy:{unlimited_counts:true},nodes},seen=new Set(),begins=[],packets=new Map(),waitAudits=[];
  const invoke=async(action,args)=>{
    if(action==='enable'||action==='recover'||action==='status')return {ok:true,review};
    if(action==='begin'){
      begins.push(args.stage);const token=args.request_id;if(seen.has(token))return {ok:true,started:false};seen.add(token);
      const run={id:args.stage+'-run'};packets.set(run.id,args.stage);return {ok:true,started:true,run};
    }
    if(action==='packet'){
      const stage=packets.get(args.run_id),text='先核对订单日期，再核对商品编码。';
      return {ok:true,packet:{protocol:REVIEW_PROTOCOL,stage,run_id:args.run_id,fingerprint:'f',artifact_sha256:'a'.repeat(64),binding:{packet_sha256:'b'.repeat(64)},review_contract:{},checklist:[],...stage==='script'?{input:{text}}:stage==='storyboard'?{input:{storyboard:{segments:[{id:'s',beat:'当前对象变化'}]}}}:{},evidence:{media:[],frames:[],limitations:[]},allowed_artifacts:[{id:stage,kind:stage==='script'?'transcript':stage==='storyboard'?'storyboard':'video',sha256:'a'.repeat(64)}]}};
    }
    if(action==='producer_packet')return {ok:true,packet:{protocol:'course-producer-qa/1',stage:args.stage,run_id:args.run_id,role:'producer',...args.stage==='storyboard'?{producer_qa_timeout_ms:1200000,producer_qa_timeout_authorization:{source:'course-explicit'}}:{},binding:{stage:args.stage,run_id:args.run_id,packet_sha256:'b'.repeat(64)},input:{text:'先核对订单日期。'},checklist:[],evidence:{sources:[{id:'S',text:'PRIVATE_ORIGINAL_ONLY_FOR_PRODUCER'}]},editable_files:[]}};
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{packet_sha256:'b'.repeat(64)},execution:[],requirements:[]}};
    if(action==='reserve')return {ok:true,reserved:true};
    if(action==='producer_submit')return {ok:true,can_repair:false};
    if(action==='call_result'&&args.agent_audit?.role==='producer')waitAudits.push({stage:args.stage,...args.agent_audit.producer_qa_wait});
    if(action==='finish'){
      nodes[args.stage].passed=true;
      if(args.stage==='script')nodes.script.user_confirmed=true; // pre-existing exact-content receipt becomes reusable after pass
      return {ok:true};
    }
    return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke});
  try{
    await handle.onIdle(agent);await handle.whenIdle();assert.equal(independent.calls.length,0,'hold forbids automatic inference');
    review.hold.held=false;
    await handle.onIdle(agent);await handle.whenIdle();
    assert.deepEqual(independent.calls.filter(call=>call.role==='reviewer').map(call=>call.packet.stage),['script','storyboard','pilot'],'after-review idle recheck reuses exact-content script receipt without browser polling');
    assert.equal(nodes.storyboard.passed,true);assert.equal(nodes.storyboard.user_confirmed,false);assert.equal(nodes.pilot.passed,true,'storyboard AI pass needs no extra user approval');
    await handle.onIdle(agent);await handle.whenIdle();assert.equal(independent.calls.filter(call=>call.role==='reviewer').length,3,'same actual stage/request does not replay');
    nodes.pilot.user_confirmed=true; // synthetic fixture's explicit existing receipt
    await handle.onIdle(agent);await handle.whenIdle();
    assert.deepEqual(independent.calls.filter(call=>call.role==='reviewer').map(call=>call.packet.stage),stages);
    assert.deepEqual(waitAudits.map(entry=>[entry.stage,entry.effective_timeout_ms]),[['script',600000],['storyboard',1200000],['pilot',600000],['final',600000]],'unlimited counts do not choose or remove the watchdog');
    assert.equal(waitAudits[1].authorization_source,'course-explicit');assert.ok(waitAudits.every(entry=>entry.elapsed_ms>=0&&!entry.watchdog_triggered));
    assert.match(agent.lastPrompt,/script_read 或 source_and_script.*至少一条 quote 必须逐字完整地存在于当前 packet\.input\.text/);
    assert.match(agent.lastPrompt,/不连续片段必须拆开为多条 evidence/);
    assert.match(agent.lastPrompt,/source-accuracy.*source_id、准确的 locator 和逐字 source_quote/);
    assert.match(agent.lastPrompt,/source_quote 必须逐字完整地存在该来源的 text 中/);
    assert.match(agent.lastPrompt,/找不到所需引文时保持“无法验证”，不得伪造、补写或改写引文/);
    assert.match(agent.lastPrompt,/repairs\.issue_id 只能取当前 blind_report.*禁止 history:Fxx.*不得修改验收清单/);
    assert.match(agent.lastPrompt,/顶层除 segments 外所有字段（包括 navigation）必须原样保留，不得改变、增加或删除/);
    assert.match(agent.lastPrompt,/片段数量、顺序及每个 segment 的 id、unit_id、source_paragraph_ids、script_excerpt、selected、selection_receipt 也必须不变/);
    assert.match(agent.lastPrompt,/相应已有 options 的 action、reading_design、safety 等允许内容字段/);
    assert.match(agent.lastPrompt,/只能说明和服从已有导航，调整本片段对象显隐与阅读窗；不得通过更名或挪字段改变既定全局规则/);
    assert.match(agent.lastPrompt,/需要另行制作，不提交非法 repair/);
    assert.equal(nodes.final.user_confirmed,false);assert.ok(begins.includes('final'));
  }finally{await handle.dispose();}
});

test('an invalid producer QA timeout is rejected before producer reservation or inference',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls(),calls=[];
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{
    calls.push({action,args});const value=await callReview(action,args);
    if(action==='producer_packet')value.packet.producer_qa_timeout_ms='1200000';
    return value;
  }});
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const node=(await callReview('status',{course_path:root})).review.nodes.script;
    assert.match(node.reason,/整数毫秒/);assert.equal(agent.lastPrompt,undefined);assert.equal(node.calls,1);
    assert.equal(calls.some(call=>call.action==='reserve'&&call.args.role==='producer'),false);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('the configured producer total watchdog cancels the actual bound producer and records the timeout without changing counts or usage',async()=>{
  const root=await fixture(),agent=producer(root),independent=isolatedCalls(),nativeSetTimeout=globalThis.setTimeout;let watchdog;
  globalThis.setTimeout=(callback,ms,...args)=>{if(ms===1200000)watchdog=callback;return nativeSetTimeout(callback,ms,...args);};
  agent.beforeResponse=async()=>{assert.equal(typeof watchdog,'function');watchdog();throw Error('synthetic native turn cancelled by total watchdog');};
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{
    const value=await callReview(action,args);if(action==='producer_packet')value.packet.producer_qa_timeout_ms=1200000;return value;
  }});
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const node=(await callReview('status',{course_path:root})).review.nodes.script,call=node.run.calls.find(call=>call.role==='producer');
    assert.equal(agent.cancelled,true);assert.equal(node.calls,2);assert.equal(node.repairs,0);assert.equal(call.status,'failed');
    assert.equal(call.agent_audit.producer_qa_wait.effective_timeout_ms,1200000);assert.equal(call.agent_audit.producer_qa_wait.watchdog_triggered,true);assert.equal(call.agent_audit.producer_qa_wait.termination,'total_timeout');
    assert.equal(call.usage_status,'unknown');assert.deepEqual(call.usage,{});assert.equal(call.model_invoked,null);
    const meta=JSON.parse(await readFile(join(root,'project/qa/ai-review',node.run.id,'calls','producer-0.wait.json'),'utf8'));
    assert.equal(meta.agent_id,agent.id);assert.equal(meta.termination,'total_timeout');assert.equal(independent.calls.filter(call=>call.role==='reviewer').length,1);
  }finally{globalThis.setTimeout=nativeSetTimeout;await handle.dispose();await rm(root,{recursive:true,force:true});}
});

test('natural conversation instructions reach real production supervision and never become reviewer inputs',async()=>{
  const root='/tmp/kgxc-natural-direction-fixture',agent=producer(root),independent=isolatedCalls(),journal=[];
  const invoke=async(action,args)=>{
    if(action==='production_event'){journal.push(...args.execution);return {ok:true,started:args.phase==='start'?true:undefined};}
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:args.operation_id},requirements:[],execution:journal}};
    if(action==='reserve')return {ok:true,reserved:true};return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke,tool:async()=>({ok:true,workflow:{gates:[{id:'storyboard',status:'open'}]}})});
  try{
    await handle.observe(agent,{seq:1,time:1,type:'user/message',data:{id:'actual-user-message',source:{kind:'user'},content:[{type:'text',text:'请继续当前分镜，NATURAL_DIRECTION_SENTINEL，要让讲述带动画面对象变化。'}]}});
    await handle.beforeTool(agent,'bash',{command:'python build_storyboard.py'});
    assert.equal(independent.calls.length,1);assert.equal(independent.calls[0].role,'supervisor');
    assert.match(JSON.stringify(independent.calls[0].packet.execution),/NATURAL_DIRECTION_SENTINEL/);
    assert.equal(journal.find(fact=>fact.type==='production/dispatch').operation,'conversation');assert.equal(journal.find(fact=>fact.type==='production/request').operation,'conversation-tool');assert.doesNotMatch(JSON.stringify(journal),/build_storyboard\.py/);
  }finally{await handle.dispose();}
});

test('a genuine mid-operation steering instruction is independently supervised before the next production tool',async()=>{
  const root='/tmp/kgxc-steer-direction-fixture',agent=producer(root),independent=isolatedCalls(),journal=[];
  const invoke=async(action,args)=>{
    if(action==='production_event'){journal.push(...args.execution);return {ok:true};}
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:args.operation_id},requirements:[],execution:structuredClone(journal)}};
    if(action==='reserve')return {ok:true,reserved:true};return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke});
  try{
    await handle.production({course_path:root,producer:agent,stage:'storyboard',user_instruction:'原始制作要求'});
    await handle.observe(agent,{seq:5,time:5,type:'user/message',data:{id:'genuine-steer',source:{kind:'user'},content:[{type:'text',text:'追加 STEER_DIRECTION_SENTINEL：人物要面向受话人。'}]}});
    await handle.beforeTool(agent,'write',{path:'synthetic.json'});
    assert.equal(independent.calls.length,2);assert.equal(independent.calls[1].role,'supervisor');
    assert.match(JSON.stringify(independent.calls[1].packet.execution),/STEER_DIRECTION_SENTINEL/);
    assert.equal(journal.at(-1).type,'production/user-direction');assert.equal(journal.at(-1).seq,5);
  }finally{await handle.dispose();}
});

test('a native producer stop holds the course and cannot be converted into an automatic review restart',async()=>{
  const root='/tmp/kgxc-native-stop-fixture',agent=producer(root),independent=isolatedCalls(),calls=[];
  const invoke=async(action,args)=>{
    calls.push({action,args});
    if(action==='supervisor_packet')return {ok:true,packet:{protocol:SUPERVISION_PROTOCOL,binding:{operation_id:args.operation_id},requirements:[],execution:[]}};
    if(action==='reserve')return {ok:true,reserved:true};return {ok:true};
  };
  const handle=host(root,agent,independent,{invoke});
  try{
    await handle.production({course_path:root,producer:agent,stage:'storyboard'});
    await handle.observe(agent,{seq:10,time:10,type:'turn/end',data:{reason:{kind:'aborted'}}});
    await handle.onIdle(agent);await handle.whenIdle();
    assert.equal(independent.calls.length,1);assert.ok(handle.blockReason(agent));assert.ok(calls.some(call=>call.action==='hold'&&call.args.held));
    assert.equal(calls.some(call=>call.action==='begin'),false);
  }finally{await handle.dispose();}
});

test('a proven native preflight failure settles its reservation without inventing invocation IDs or zero token usage',async()=>{
  const root=await fixture(),agent=producer(root),calls=[];
  const independent={run:async()=>{
    const error=Error('合成原生隔离预检阻止调用');error.usage={};error.execution_phase='preflight';error.model_invoked=false;
    error.agent_audit={id:randomUUID(),session_id:randomUUID(),role:'reviewer',read_only:true,isolated:true,route:FIXED_ROUTE,invocation_ids:[],request_headers:[]};throw error;
  }};
  const handle=host(root,agent,independent,{invoke:async(action,args)=>{calls.push({action,args});return callReview(action,args);}});
  try{
    await handle.onIdle(agent);await handle.whenIdle();
    const node=(await callReview('status',{course_path:root})).review.nodes.script;
    assert.equal(node.calls,1);assert.equal(node.passed,false);
    const call=node.run.calls[0];assert.equal(call.status,'failed');assert.equal(call.failure_kind,'preflight');assert.equal(call.usage_status,'not_invoked');
    assert.deepEqual(call.usage,{});assert.deepEqual(call.agent_audit.invocation_ids,[]);
    const settled=calls.find(call=>call.action==='call_result');assert.equal(settled.args.execution_phase,'preflight');assert.equal(settled.args.model_invoked,false);
    assert.equal('totalTokens' in settled.args.usage,false);
  }finally{await handle.dispose();await rm(root,{recursive:true,force:true});}
});
