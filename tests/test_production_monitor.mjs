import test from 'node:test';
import assert from 'node:assert/strict';
import {z} from 'zod';
import {initialProduction,applyProduction,productionSnapshot,productionProjection} from '../plugin/production-monitor.mjs';

const path='/tmp/course-monitor-fixture';
function stream(){let state=initialProduction(),seq=0,time=1000;return {get state(){return state;},event(type,data){state=applyProduction(state,{type,data,time:time+=1000,seq:seq++});productionProjection(z).stateSchema.parse(state);return state;},begin(){this.event('user/message',{source:{kind:'kgxc-course-context'},content:[{type:'text',text:'KGXC_OPERATION '+JSON.stringify({course_path:path,stage:'pilot'})}]});},call(id,name,args){this.event('tool/call',{callId:id,name,arguments:JSON.stringify(args)});},result(id,text,isError=false){this.event('tool/result',{message:{toolCallId:id,isError,content:[{type:'text',text}]}});}};}

test('actual steps, waiting time and stop survive a replay without fabricating percentages',()=>{
  const s=stream();s.begin();s.event('turn/start',{turn:1});s.call('read1','read',{file_path:'/tmp/reference.md'});s.result('read1','read content');s.event('step/start',{turn:1,step:2});
  const p=productionSnapshot(s.state,{course_path:path,running:true,now:9000});assert.equal(p.items.find(x=>x.id==='read1').label,'读取制作资料与接口');assert.equal(p.items.find(x=>x.id==='read1').status,'complete');assert.ok(p.items.some(x=>x.kind==='model'&&x.ended_at>x.started_at));assert.ok(p.waiting_since);assert.ok(p.model_wait_ms>0);assert.equal('progress' in p,false);
  s.event('turn/end',{turn:1,reason:{kind:'aborted'}});assert.equal(productionSnapshot(s.state,{course_path:path,running:false}).status,'stopped');
  assert.equal(productionSnapshot(s.state,{course_path:'/tmp/other',running:true}).available,false);
});

test('nonzero shell exit is a failure even when DSH isError is false; unrelated reads cannot erase it',()=>{
  const s=stream();s.begin();
  for(let i=0;i<2;i++){s.call('b'+i,'bash',{command:'python /tmp/build_pilot.py',description:'Build current pilot'});s.event('job/registered',{jobId:'j'+i,toolCall:{callId:'b'+i}});s.event('job/settled',{jobId:'j'+i,status:'completed',detail:'exit code: 1'});s.result('b'+i,'Traceback\nStopIteration\n[exit code: 1]',false);}
  s.call('r','read',{file_path:'/tmp/backend.py'});s.result('r','some source');
  const p=productionSnapshot(s.state,{course_path:path,running:true});assert.equal(p.issue.count,2);assert.match(p.issue.error,/StopIteration/);assert.equal(p.issue.label,'构建画面与时间轴');
  s.call('fixed','bash',{command:'python /tmp/build_pilot.py'});s.result('fixed','built\n[exit code: 0]');assert.equal(productionSnapshot(s.state,{course_path:path,running:true}).issue,null);
});

test('background generation remains executing until the actual job settles',()=>{
  const s=stream();s.begin();s.call('voice','bash',{command:'python /tmp/tts.py',description:'Generate speech'});s.event('job/registered',{jobId:'job1',toolCall:{callId:'voice'}});s.result('voice','Task running in background: job1');
  assert.equal(productionSnapshot(s.state,{course_path:path,running:true}).current.label,'生成配音');
  s.event('job/settled',{jobId:'job1',status:'completed',detail:'exit code: 0'});assert.equal(productionSnapshot(s.state,{course_path:path,running:true}).current,null);
});

test('old 0.5 handoffs recover and retained activity is bounded and excludes commands and source contents',()=>{
  const s=stream();s.event('user/message',{source:{kind:'kgxc-course-context'},content:[{type:'text',text:'用户在 DSH 课程工作台发起本阶段操作。课程工程位于当前会话工作区内："'+path+'"。目标阶段=pilot。'}]});
  for(let i=0;i<40;i++){s.call('r'+i,'read',{file_path:'/tmp/read'+i+'.md'});s.result('r'+i,'PRIVATE SOURCE CONTENT');}
  assert.ok(s.state.items.length<=24);assert.doesNotMatch(JSON.stringify(s.state),/PRIVATE SOURCE CONTENT/);assert.equal(s.state.operation.stage,'pilot');
});
test('background error details attach to the failing operation and actual export acceptance is recorded separately',()=>{
  const s=stream();s.begin();s.call('check','bash',{command:'python /tmp/check_workbench.py',description:'Validate renderer'});s.event('job/registered',{jobId:'j-check',toolCall:{callId:'check'}});s.event('job/settled',{jobId:'j-check',status:'completed',detail:'exit code: 1'});
  s.call('output','job_output',{job_id:'j-check'});s.result('output','{"ok":false,"errors":["new storyboard format was read as an old array"]}\n[status: completed, exit code: 1]');
  assert.match(s.state.failures.find(x=>x.critical).error,/new storyboard/);assert.equal(s.state.failures.find(x=>x.critical).count,1);
  s.call('export','kgxc_course_export',{purpose:'pilot'});s.result('export','{"ok":true,"job":{"id":"actual-export","status":"rendering"}}');
  assert.equal(s.state.last_export.job_id,'actual-export');assert.ok(s.state.last_export.at>s.state.failures[0].at);
});
