import test from 'node:test';
import assert from 'node:assert/strict';
import {productionProgress,productionJobHistory} from '../skills/corporate-training-motion/workbench/production-progress.js';

test('unmeasurable AI preparation is indeterminate, without an invented percentage',()=>{
  const state=productionProgress({stage:'pilot',busy:true});assert.equal(state.value,null);assert.doesNotMatch(state.label,/%/);
});
test('an actual export is visible across tabs and uses its reported progress',()=>{
  const state=productionProgress({stage:'outline',busy:true,jobs:[{purpose:'final',status:'rendering',progress:.427}]});
  assert.equal(state.value,.427);assert.match(state.label,/整课视频.*42%/);
});
test('a real automatic seam test is shown without an invented percentage or confirmation',()=>{
  const state=productionProgress({stage:'pilot',jobs:[{purpose:'pilot',status:'rendering',phase:'seam_preflight',progress:0}]});
  assert.match(state.label,/试拼片头、正文与片尾/);assert.match(state.detail,/无需确认/);
  assert.equal(state.value,null);assert.equal(state.tone,'working');
});
test('saved alternatives finish generation while choices remain explicitly pending',()=>{
  const state=productionProgress({stage:'storyboard',data:{storyboard:{segments:[{},{}]},gates:[{id:'storyboard',status:'open',ready:false}]}});
  assert.equal(state.value,1);assert.match(state.detail,/请选择方案/);
});
test('an old pilot export cannot masquerade as a completed final video',()=>{
  const state=productionProgress({stage:'final',jobs:[{purpose:'pilot',status:'complete',progress:1}]});assert.equal(state.value,0);
});
test('failed export reports the actual reason and changed content is not shown as complete',()=>{
  const state=productionProgress({stage:'pilot',busy:true,jobs:[{purpose:'pilot',status:'failed',error:'旁白连贯性检查未通过'}]});assert.equal(state.tone,'failed');assert.match(state.detail,/旁白连贯性/);
  assert.match(productionProgress({stage:'pilot',jobs:[{purpose:'pilot',status:'failed',error:'\n'}]}).detail,/查看原因/);
  assert.equal(productionProgress({stage:'script',data:{editor:{text:'已保存的旧稿',changed:true}}}).value,0);
});
test('a real preparation failure remains visible even while the model is making another call',()=>{
  const state=productionProgress({stage:'pilot',busy:true,native:{available:true,status:'running',issue:{label:'构建画面与时间轴',count:3}}});
  assert.equal(state.tone,'failed');assert.match(state.label,/连续失败 3 次/);assert.equal(state.value,0);
  const stopped=productionProgress({stage:'pilot',native:{available:true,status:'stopped'}});assert.match(stopped.label,/已停止/);
});
test('completed actual export takes precedence over an earlier separate checker error, but not a new failure',()=>{
  const native={available:true,last_export:{job_id:'real-job',at:20},issue:{label:'独立检查',count:1,at:10}};
  const input={stage:'pilot',jobs:[{id:'real-job',purpose:'pilot',status:'complete',progress:1}],native};
  assert.equal(productionProgress(input).value,null);native.issue.at=30;assert.equal(productionProgress(input).tone,'failed');
});
test('delivered course suppresses old preparation errors across tabs and retains later failures',()=>{
  const at=Date.parse('2026-11-05T19:44:44+08:00');
  const input={stage:'sources',data:{gates:[{id:'final',status:'delivered',receipt:{at:new Date(at).toISOString()}}]},native:{available:true,issue:{label:'旧检查',at:at-1000}}};
  assert.equal(productionProgress(input).tone,'done');
  input.native.issue.at=at+1000;assert.equal(productionProgress(input).tone,'failed');
  input.native.issue.at=at-1000;input.jobs=[{purpose:'final',status:'failed',error:'新的实际合成失败'}];assert.notEqual(productionProgress(input).tone,'done');
});
test('current final export is separate from retained failed attempts and pilot jobs',()=>{
  const jobs=[{id:'pilot',purpose:'pilot',status:'failed',revision:1},
    {id:'bad',purpose:'final',status:'failed',revision:10,error:'old traceback',progress:1},
    {id:'good',purpose:'final',status:'complete',revision:14,completed_at:200}];
  const result=productionJobHistory(jobs,'final');
  assert.equal(result.current.id,'good');assert.equal(result.history.length,1);
  assert.equal(result.history[0].status,'failed');assert.equal(result.history[0].error,'old traceback');
  assert.deepEqual(result.history[0].supersededBy,{id:'good',revision:14});
  assert.equal(productionProgress({stage:'final',jobs,native:{available:true,issue:{label:'old checker',at:100}}}).tone,'waiting');
});
test('new failed attempt remains current despite an earlier successful video',()=>{
  const jobs=[{id:'old-good',purpose:'final',status:'complete',revision:14},
    {id:'new-bad',purpose:'final',status:'failed',revision:15,progress:1,error:'new real failure'}];
  const result=productionJobHistory(jobs,'final');assert.equal(result.current.id,'new-bad');
  assert.equal(productionProgress({stage:'final',jobs}).tone,'failed');
  assert.match(productionProgress({stage:'final',jobs}).detail,/new real failure/);
});


test('changed production preferences cannot show an older complete export as the current result',()=>{
 const state=productionProgress({stage:'final',jobs:[{id:'old',purpose:'final',status:'complete',completed_at:20}],data:{production_preferences:{required:true,ready:true,storyboard_current:false}}});
 assert.equal(state.value,0);assert.match(state.label,/制作偏好已修改/);
});

test('supervision-cancelled current export remains paused despite old delivered media',()=>{
 const state=productionProgress({stage:'final',jobs:[{id:'held',purpose:'final',status:'cancelled',progress:.8,error:'监督发现执行越界；当前文件保留'}],data:{gates:[{id:'final',status:'delivered',receipt:{at:new Date().toISOString()}}]}});
 assert.equal(state.tone,'waiting');assert.equal(state.value,null);assert.match(state.label,/暂停/);assert.match(state.detail,/监督/);
});

test('a technically complete held candidate is not an old delivered course or a failed render',()=>{
 const state=productionProgress({stage:'final',jobs:[{id:'candidate',purpose:'final',status:'complete',registration_status:'held',stage_registered:false,completed_at:20}],data:{gates:[{id:'final',status:'delivered',receipt:{at:new Date().toISOString()}}]}});
 assert.equal(state.value,null);assert.equal(state.tone,'waiting');assert.match(state.label,/验收受阻/);assert.match(state.detail,/尚未正式交付/);
});

test('recovery offers only the failed current phase, not history or a running export',async()=>{
  const {exportRecovery}=await import('../skills/corporate-training-motion/workbench/production-progress.js');
  const old={id:'a',purpose:'pilot',status:'failed'};
  const final={id:'b',purpose:'final',status:'cancelled'};
  assert.equal(exportRecovery([old,final],'final').job_id,'b');
  assert.equal(exportRecovery([old,final],'pilot').label,'继续制作小样');
  assert.equal(exportRecovery([old,{...old,id:'c',status:'complete'}],'pilot'),null);
  assert.equal(exportRecovery([old,{...final,status:'rendering'}],'pilot'),null);
  assert.equal(exportRecovery([old],'pilot',true),null);
});
