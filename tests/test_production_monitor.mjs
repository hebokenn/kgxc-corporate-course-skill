import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {z} from 'zod';
import {initialProduction,applyProduction,productionSnapshot,productionProjection,productionEventFact,operationOf} from '../plugin/production-monitor.mjs';

const path='/tmp/course-monitor-fixture';
function stream(){let state=initialProduction(),seq=0,time=1000;return {get state(){return state;},event(type,data){state=applyProduction(state,{type,data,time:time+=1000,seq:seq++});productionProjection(z).stateSchema.parse(state);return state;},begin(){this.event('user/message',{source:{kind:'kgxc-course-context'},content:[{type:'text',text:'KGXC_OPERATION '+JSON.stringify({course_path:path,stage:'pilot'})}]});},call(id,name,args){this.event('tool/call',{callId:id,name,arguments:JSON.stringify(args)});},result(id,text,isError=false){this.event('tool/result',{message:{toolCallId:id,isError,content:[{type:'text',text}]}});}};}
function workMessage(stage,request_id){return {id:'owned-message-'+request_id,source:{kind:'kgxc-producer-work'},content:[{type:'text',text:'KGXC_OPERATION '+JSON.stringify({course_path:path,stage,operation_id:'produce-'+createHash('sha256').update(path+'\0'+request_id).digest('hex'),request_id})+'\nPRIVATE_TASK_BODY'}]};}

test('source coverage status stays a read while saving is a formal change with no source text leakage',()=>{
  const s=stream();s.begin();
  s.call('coverage-status','kgxc_course_source_coverage',{course_path:path,action:'status'});
  assert.equal(s.state.items.at(-1).kind,'read');assert.equal(s.state.items.at(-1).critical,false);
  s.result('coverage-status',JSON.stringify({ok:true,source_coverage:{private_original:'PRIVATE_SOURCE_TEXT'}}));
  s.call('coverage-save','kgxc_course_source_coverage',{course_path:path,action:'save',report:{source_quote:'PRIVATE_ORIGINAL_QUOTE'},expected_script_sha256:'a'.repeat(64)});
  assert.equal(s.state.items.at(-1).kind,'save');assert.equal(s.state.items.at(-1).critical,true);assert.match(s.state.items.at(-1).label,/原件与逐字稿对照/);
  const fact=productionEventFact({seq:7,time:7000,type:'tool/call',data:{callId:'coverage-save',name:'kgxc_course_source_coverage',arguments:JSON.stringify({action:'save',report:{source_quote:'PRIVATE_ORIGINAL_QUOTE'}})}});
  assert.equal(fact.kind,'save');assert.doesNotMatch(JSON.stringify(fact),/PRIVATE_ORIGINAL_QUOTE|source_quote/);assert.doesNotMatch(JSON.stringify(s.state),/PRIVATE_SOURCE_TEXT|PRIVATE_ORIGINAL_QUOTE/);
});

test('native turn43 owned producer-work resets the current stage and keeps earlier failures as unresolved history',()=>{
  const s=stream();s.begin();s.call('old','bash',{command:'python /tmp/helper121.py'});s.result('old','old failure\n[exit code: 2]');
  const old=structuredClone(s.state.failures[0]),message=workMessage('script','confirmed-sentence-and-covered-timing');
  // Real native shape: user/message source has exactly kind, and the strict
  // four-key marker is the first line (native43 seq3549/time1794118740874).
  s.event('user/message',message);let snapshot=productionSnapshot(s.state,{course_path:path,running:true});
  assert.equal(snapshot.stage,'script');assert.equal(snapshot.status,'running');assert.equal(snapshot.issue,null);assert.equal(snapshot.current,null);assert.ok(snapshot.waiting_since);
  assert.equal(snapshot.history.length,1);assert.deepEqual(snapshot.history[0],old);assert.equal(snapshot.history[0].superseded_by,null);
  assert.equal(snapshot.request_id,'confirmed-sentence-and-covered-timing');assert.doesNotMatch(JSON.stringify(s.state),/PRIVATE_TASK_BODY/);
  const current=structuredClone(s.state);s.event('user/message',message);assert.deepEqual(s.state,current,'same dispatch cannot clear current activity');
  const marker=JSON.parse(message.content[0].text.split('\n')[0].slice(15));
  for(const bad of [{...message,source:{kind:'user'}},{...message,content:[{type:'text',text:'prefix\n'+message.content[0].text}]},
      ...[null,{...marker,stage:'__proto__'},{...marker,request_id:'other'},{...marker,course_path:'/tmp/other-course'},{...marker,extra:'PRIVATE_SOURCE'}].map(value=>({...message,content:[{type:'text',text:'KGXC_OPERATION '+JSON.stringify(value)}]}))]){
    assert.equal(operationOf(bad),null);s.event('user/message',bad);assert.deepEqual(s.state,current);
  }
});

test('actual121 failure and123 flat success retain raw failure and link only the matching saved candidate/source/revision',()=>{
  const s=stream();s.begin();const candidate='a'.repeat(64),expected='b'.repeat(64);
  const failure={ok:false,completed:false,workflow_revision:120,candidate_sha256:candidate,script_sha256:'c'.repeat(64),expected_script_sha256:expected,error_code:'api_current_revision_matches',new_user_confirmation:false,independent_review_passed:false};
  s.call('helper121','bash',{command:'python3 -B /tmp/121-native-submit.py --apply'});s.result('helper121',JSON.stringify(failure),false);
  assert.ok(productionSnapshot(s.state,{course_path:path,running:true}).issue);
  const rawError=s.state.failures[0].error;s.event('user/message',workMessage('script','corrected-helper123'));
  s.call('helper126','bash',{command:'python3 -B /tmp/126-component-timing.py'});s.result('helper126',JSON.stringify({ok:true,completed:true,workflow_revision:122,script_sha256:expected}));
  assert.equal(s.state.failures[0].superseded_by,null,'unrelated timing success cannot resolve script adoption');
  s.call('helper123','bash',{command:'python3 -B /tmp/123-corrected-submit.py --apply'});
  s.result('helper123',JSON.stringify({ok:true,completed:true,workflow_revision:121,candidate_sha256:candidate,script_sha256:expected,expected_script_sha256:expected,new_user_confirmation:false,independent_review_passed:false}));
  const snapshot=productionSnapshot(s.state,{course_path:path,running:true});assert.equal(snapshot.issue,null);assert.equal(snapshot.history.length,1);
  assert.equal(snapshot.history[0].error,rawError);assert.equal(snapshot.history[0].receipt.ok,false);
  assert.deepEqual(snapshot.history[0].superseded_by,{id:'helper123',at:s.state.last_event_at,basis:'matching-candidate-source-revision',workflow_revision:121,script_sha256:expected,candidate_sha256:candidate});
});

test('nested helper receipt cannot use inner api success to hide failure or unknown/incomplete scope',()=>{
  const s=stream();s.event('user/message',workMessage('script','nested-helper'));const candidate='a'.repeat(64),expected='b'.repeat(64);
  s.call('failure','bash',{command:'python /tmp/save.py'});s.result('failure',JSON.stringify({result:{ok:false,completed:false,workflow_revision:120,candidate_sha256:candidate,expected_script_sha256:expected},api:{ok:true}}));
  assert.ok(productionSnapshot(s.state,{course_path:path,running:true}).issue);
  s.call('same-helper-preflight','bash',{command:'python /tmp/save.py'});s.result('same-helper-preflight',JSON.stringify({ok:true,completed:false,workflow_revision:120,candidate_sha256:candidate,script_sha256:expected}));
  assert.equal(s.state.failures[0].superseded_by,null,'a successful preflight of the same helper is not a saved revision');
  s.call('same-helper-other-candidate','bash',{command:'python /tmp/save.py'});s.result('same-helper-other-candidate',JSON.stringify({ok:true,completed:true,workflow_revision:121,candidate_sha256:'d'.repeat(64),script_sha256:expected}));
  assert.equal(s.state.failures[0].superseded_by,null,'the same executable path is not proof of the same candidate');
  for(const [id,result] of [['incomplete',{ok:true,completed:false,workflow_revision:121,candidate_sha256:candidate,script_sha256:expected}],['wrong-target',{ok:true,completed:true,workflow_revision:121,candidate_sha256:'d'.repeat(64),script_sha256:expected}],['old-version',{ok:true,completed:true,workflow_revision:120,candidate_sha256:candidate,script_sha256:expected}]]){
    s.call(id,'bash',{command:'python /tmp/'+id+'.py'});s.result(id,JSON.stringify({result,api:{completed:true}}));assert.equal(s.state.failures[0].superseded_by,null);
  }
  s.call('saved','bash',{command:'python /tmp/saved.py'});s.result('saved',JSON.stringify({result:{ok:true,completed:true,workflow_revision:121,candidate_sha256:candidate,script_sha256:expected,source_text:'PRIVATE_SOURCE'},api:{anything:'PRIVATE_API'}})+'\n[status: completed, exit code: 0]');
  assert.equal(s.state.failures[0].superseded_by.workflow_revision,121);assert.equal(productionSnapshot(s.state,{course_path:path,running:true}).issue,null);assert.doesNotMatch(JSON.stringify(s.state),/PRIVATE_SOURCE|PRIVATE_API/);
});

test('new task does not delete unknown failures and a genuine current failure remains current',()=>{
  const s=stream();s.begin();for(let i=0;i<10;i++){s.call('failed-'+i,'bash',{command:'python /tmp/unknown-'+i+'.py'});s.result('failed-'+i,'unknown execution failure\n[exit code: 1]');}
  s.event('user/message',workMessage('script','fresh-task'));let snapshot=productionSnapshot(s.state,{course_path:path,running:true});assert.equal(snapshot.history.length,10);assert.ok(snapshot.history.every(failure=>failure.superseded_by===null));
  s.call('current-error','bash',{command:'python /tmp/current.py'});s.result('current-error','current real failure\n[exit code: 1]');snapshot=productionSnapshot(s.state,{course_path:path,running:true});assert.equal(snapshot.issue.id,'current-error');assert.equal(snapshot.history.length,10);assert.equal(s.state.failures.length,11);
});

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

const fact=(type,data)=>productionEventFact({seq:17,time:1234,type,data});
const callFact=(name,args)=>fact('tool/call',{callId:'synthetic-call',name,arguments:JSON.stringify(args)});
const resultFact=text=>fact('tool/result',{message:{toolCallId:'synthetic-call',content:[{type:'text',text}]}});
const digest=value=>createHash('sha256').update(value).digest('hex');

test('supervision read evidence retains only actual requested path/range and committed argument hashes',()=>{
  const args={file_path:'/tmp/合成课程/process/readback.py',offset:73,limit:120,body:'PRIVATE_SOURCE_BODY'},value=callFact('read',args);
  assert.equal(value.call_id,'synthetic-call');assert.equal(value.seq,17);assert.equal(value.time,1234);
  assert.deepEqual(value.evidence.read,{basis:'committed_tool_arguments',path:args.file_path,range:{offset:73,limit:120}});assert.equal(value.evidence.arguments.sha256,digest(JSON.stringify(args)));
  assert.doesNotMatch(JSON.stringify(value),/PRIVATE_SOURCE_BODY/);
  assert.deepEqual(callFact('read',{file_path:args.file_path}).evidence.read.range,{},'a read without requested range must not acquire one');
  assert.deepEqual(callFact('read_file',{path:'source/transcript.md',offset:-1,limit:1.2,end_line:1e20}).evidence.read.range,{});
  assert.equal('path' in callFact('read',{file_path:'/tmp/file?token=PRIVATE_CREDENTIAL'}).evidence.read,false);
  for(const file_path of ['/tmp/auth.json','../source/transcript.md','/tmp/.env.production','/tmp/private.pem'])assert.equal('path' in callFact('read',{file_path}).evidence.read,false);
});

test('actual write/edit argument shapes expose requested paths without pretending to resolve or write them',()=>{
  // Shapes verified in native125 write3275 and earlier native edit2244/2249.
  // Paths and bodies below are neutral synthetic fixtures, not course artifacts.
  const target='project/work/synthetic-after-script121/minimal-plan.md';
  for(const [name,args] of [['write',{file_path:target,content:'PRIVATE_FULL_SOURCE_BODY'}],['edit',{file_path:'project/work/synthetic-candidate.json',old_string:'PRIVATE_OLD_BODY',new_string:'PRIVATE_NEW_BODY'}]]){
    const value=callFact(name,args);assert.deepEqual(value.evidence.mutation,{basis:'committed_tool_arguments',scope:'requested_targets',operation:name,fs_verified:false,paths:[args.file_path],paths_complete:true});assert.equal(value.evidence.arguments.sha256,digest(JSON.stringify(args)));assert.doesNotMatch(JSON.stringify(value),/PRIVATE_FULL_SOURCE_BODY|PRIVATE_OLD_BODY|PRIVATE_NEW_BODY/);
  }
  assert.equal(callFact('write',{path:target,content:'PRIVATE_FULL_SOURCE_BODY'}).evidence.mutation.paths[0],target);
  const actualOpaque=resultFact('Synthetic write confirmation text.');assert.equal(actualOpaque.evidence.result.format,'opaque');assert.equal('mutation' in actualOpaque.evidence,false);assert.equal('reported' in actualOpaque.evidence.result,false,'native confirmation text must not become filesystem proof');
});

test('synthetic apply_patch cases expose only recognized header targets and keep unsupported scope unverified',()=>{
  // No native apply_patch call has been observed in the production session.
  const patch='*** Begin Patch\n*** Update File: project/work/old.md\n*** Move to: project/work/new.md\n@@\n-PRIVATE_OLD_BODY\n+PRIVATE_NEW_BODY\n*** Add File: project/work/added.md\n+PRIVATE_FULL_SOURCE_BODY\n*** Delete File: project/work/removed.md\n*** End Patch\n';
  const value=callFact('apply_patch',{patch}).evidence.mutation;assert.deepEqual(value.paths,['project/work/old.md','project/work/new.md','project/work/added.md','project/work/removed.md']);assert.equal(value.paths_complete,true);assert.equal(value.fs_verified,false);assert.doesNotMatch(JSON.stringify(value),/PRIVATE_OLD_BODY|PRIVATE_NEW_BODY|PRIVATE_FULL_SOURCE_BODY/);
  assert.deepEqual(callFact('apply_patch',{input:patch}).evidence.mutation,value);
  for(const args of [{patch:'diff --git a/x b/x\nPRIVATE_FULL_SOURCE_BODY'},{patch:'*** Begin Patch\n*** Update File: ../auth.json\n@@\n+PRIVATE_FULL_SOURCE_BODY\n*** End Patch'},{file_path:'/tmp/auth.json',content:'PRIVATE_CREDENTIAL'},{patch:null},{}]){
    const evidence=callFact('apply_patch',args).evidence.mutation;assert.equal(evidence.paths_complete,false);assert.equal(evidence.fs_verified,false);assert.doesNotMatch(JSON.stringify(evidence),/PRIVATE_FULL_SOURCE_BODY|PRIVATE_CREDENTIAL/);
  }
  const many='*** Begin Patch\n'+Array.from({length:40},(_,i)=>'*** Add File: work/file'+i+'.md\n+PRIVATE_FULL_SOURCE_BODY').join('\n')+'\n*** End Patch';const capped=callFact('apply_patch',{patch:many}).evidence.mutation;assert.equal(capped.paths.length,32);assert.equal(capped.paths_complete,false);
});

test('actual125 baseline stdout retains all four typed values, including false, as reported evidence',()=>{
  const output={backed_up_files:14,output:'/tmp/synthetic-course/project/work/synthetic-after-script121',baseline_matches:true,revision:121};
  const value=resultFact(JSON.stringify(output)+'\n[status: completed, exit code: 0]').evidence.result;assert.deepEqual(value.reported,output);assert.equal(value.basis,'committed_tool_result');assert.equal(value.coverage,'reported_fields_only');
  assert.equal(resultFact(JSON.stringify({...output,baseline_matches:false})).evidence.result.reported.baseline_matches,false);
  const invalid=resultFact(JSON.stringify({backed_up_files:'14',revision:1e10,baseline_matches:'true',output:'https://secret.invalid/token',free_string:'PRIVATE_FULL_SOURCE_BODY'})).evidence.result;assert.deepEqual(invalid.reported,{});assert.doesNotMatch(JSON.stringify(invalid),/PRIVATE_FULL_SOURCE_BODY|secret\.invalid/);
});

test('literal Python and Node script requests expose bounded typed argv without exposing credentials or free text',()=>{
  const value=callFact('bash',{command:"'/tmp/venv/bin/python' -B '/tmp/合成课程/process/readback.py' 118"}),command=value.evidence.command;
  assert.equal(command.type,'simple_script');assert.equal(command.interpreter,'/tmp/venv/bin/python');assert.equal(command.script_path,'/tmp/合成课程/process/readback.py');assert.deepEqual(command.argv,[{kind:'flag',value:'-B'},{kind:'number',value:118}]);
  const node=callFact('bash',{command:"node '/tmp/readback.mjs' --stage storyboard --receipt '/tmp/receipt.json' --expected-sha "+'a'.repeat(64)+" --token PRIVATE_CREDENTIAL --note PRIVATE_SOURCE_BODY"}).evidence.command;
  assert.equal(node.type,'simple_script');assert.ok(node.argv.some(arg=>arg.kind==='enum'&&arg.value==='storyboard'));assert.ok(node.argv.some(arg=>arg.kind==='path'&&arg.value==='/tmp/receipt.json'));assert.ok(node.argv.some(arg=>arg.kind==='sha256'&&arg.value==='a'.repeat(64)));assert.ok(node.argv.filter(arg=>arg.kind==='opaque').length===2);
  assert.doesNotMatch(JSON.stringify(node),/PRIVATE_CREDENTIAL|PRIVATE_SOURCE_BODY/);
  assert.equal(callFact('bash',{command:'python3 -B /tmp/readback.py 118'}).evidence.command.interpreter,'python3');
  assert.equal(callFact('bash',{command:'python /tmp/readback.py 999999999999'}).evidence.command.argv[0].kind,'opaque');
});

test('complex shell, inline code, substitution and oversized commands remain opaque hashes',()=>{
  for(const command of ["python - <<'PY'\nPRIVATE_SOURCE_BODY\nPY",'python -c PRIVATE_SOURCE_BODY','node -e PRIVATE_CREDENTIAL','python /tmp/readback.py && echo PRIVATE_CREDENTIAL','python /tmp/readback.py > /tmp/output','python /tmp/readback.py "$(cat /tmp/PRIVATE_CREDENTIAL)"','python /tmp/readback.py '+'.'.repeat(9000),'python /tmp/readback.py '+Array.from({length:20},(_,i)=>'--arg'+i+'=x').join(' ')]){
    const evidence=callFact('bash',{command}).evidence.command;assert.deepEqual(evidence,{type:'opaque',sha256:digest(command),bytes:Buffer.byteLength(command)});assert.doesNotMatch(JSON.stringify(evidence),/PRIVATE_SOURCE_BODY|PRIVATE_CREDENTIAL/);
  }
});

test('structured stdout preserves actual typed checks, hashes and receipt paths, including false',()=>{
  const output={ok:true,completed:true,workflow_revision:118,segments:16,options:48,all_selected_A:false,only_process_receipt_written:true,new_user_confirmation:false,review_not_triggered:true,independent_review_passed:false,storyboard_sha256:'a'.repeat(64),html_sha256:'b'.repeat(64),script_sha256:'c'.repeat(64),self_script_sha256:'d'.repeat(64),receipt:'/tmp/合成课程/process/readback.receipt.json',protected_files:{'storyboard.json':'a'.repeat(64),'native/main.js':'b'.repeat(64),'source/transcript.md':'c'.repeat(64),'not-a-path':'PRIVATE_CREDENTIAL'},checks:{import_receipt:true,artifact_hashes:false,protected_hashes:true,identity_revision:true,structure:true,unlimited_counts:true,no_replacement_character:true,free_text:'PRIVATE_SOURCE_BODY'},source_text:'PRIVATE_SOURCE_BODY',credential:'PRIVATE_CREDENTIAL',no_writes:true};
  const text=JSON.stringify(output)+'\n[status: completed, exit code: 0]',value=resultFact(text),result=value.evidence.result;
  assert.equal(value.exit_code,0);assert.equal(value.failed,false);assert.equal(result.format,'json');assert.equal(result.sha256,digest(text));assert.equal(result.bytes,Buffer.byteLength(text));assert.equal(result.basis,'committed_tool_result');assert.equal(result.coverage,'reported_fields_only');
  assert.equal(result.reported.all_selected_A,false);assert.equal(result.reported.checks.artifact_hashes,false);assert.equal(result.reported.completed,true);assert.equal(result.reported.workflow_revision,118);assert.equal(result.reported.segments,16);assert.equal(result.reported.options,48);assert.equal(result.reported.self_script_sha256,output.self_script_sha256);assert.equal(result.reported.receipt,output.receipt);
  for(const key of ['only_process_receipt_written','new_user_confirmation','review_not_triggered','independent_review_passed'])assert.equal(result.reported[key],output[key]);
  assert.deepEqual(result.reported.protected_files,{'storyboard.json':'a'.repeat(64),'native/main.js':'b'.repeat(64),'source/transcript.md':'c'.repeat(64)});assert.equal('no_writes' in result.reported,false);assert.equal('free_text' in result.reported.checks,false);assert.doesNotMatch(JSON.stringify(value),/PRIVATE_SOURCE_BODY|PRIVATE_CREDENTIAL/);
  assert.deepEqual(fact('tool/ptc-dispatch',{subCallId:'ptc-call',content:[{type:'text',text}]}).evidence,resultFact(text).evidence);
  assert.equal(fact('tool/result',{message:{toolCallId:'job-output-call',content:[{type:'text',text:'{"ok":false,"completed":false}\n[status: completed, exit code: 0]'}]}}).failed,true);
});

test('evidence is bounded and unknown output or exit-only job status does not become a verification result',()=>{
  const files=Object.fromEntries(Array.from({length:80},(_,i)=>['source/file'+i+'.json','a'.repeat(64)])),checks=Object.fromEntries(Array.from({length:80},(_,i)=>['check_'+i,i%2===0])),value=resultFact(JSON.stringify({protected_files:files,checks,receipt:'https://invalid.example/?token=PRIVATE_CREDENTIAL',storyboard_sha256:'not a digest',segments:-1,options:1.1})).evidence.result;
  assert.equal(Object.keys(value.reported.protected_files).length,32);assert.equal(Object.keys(value.reported.checks).length,32);assert.equal('receipt' in value.reported,false);assert.equal('storyboard_sha256' in value.reported,false);assert.equal('segments' in value.reported,false);
  const raw=resultFact('PRIVATE_SOURCE_BODY\nPRIVATE_CREDENTIAL').evidence.result;assert.equal(raw.format,'opaque');assert.equal('reported' in raw,false);assert.doesNotMatch(JSON.stringify(raw),/PRIVATE_SOURCE_BODY|PRIVATE_CREDENTIAL/);
  const settled=fact('job/settled',{jobId:'synthetic-job',status:'completed',detail:'exit code: 0'});assert.equal(settled.exit_code,0);assert.equal('evidence' in settled,false);
  const failure=resultFact('ValueError: PRIVATE_SOURCE_BODY token=PRIVATE_CREDENTIAL\n[exit code: 1]');assert.equal(failure.error,'ValueError');assert.doesNotMatch(JSON.stringify(failure),/PRIVATE_SOURCE_BODY|PRIVATE_CREDENTIAL/);
});
