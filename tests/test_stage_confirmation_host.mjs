import test from 'node:test';
import assert from 'node:assert/strict';
import {createStageConfirmationHost} from '../plugin/stage-confirmation.mjs';

const id='kgxc-confirm-'+ 'a'.repeat(36);
const input={course_path:'/fixture/current',session_id:'current-session',stage:'script',question_id:id};
const question={id,question:'确认当前逐字稿吗？',options:[{label:'确认讲稿及原件对照'},{label:'稍后确认'},{label:'需要修改'}]};
const REQUEST='stage-confirmation-request',STATUS='stage-confirmation-status';
function fixture(){
  const agent={session:{id:input.session_id},status:'idle'};
  const calls=[],asked=[];let path=input.course_path,answer;
  const service={ask:request=>{asked.push(request);return new Promise(resolve=>{answer=resolve;});}};
  const handle=createStageConfirmationHost({get:name=>name==='agents'?new Map([[input.session_id,agent]]):service},{
    review:async(action,args)=>{calls.push({action,args});return action==='stage_confirmation_request'?{ok:true,question}:{ok:true,status:args.selected==='稍后确认'?'deferred':'confirmed'};},
    resolveCourse:()=>path,
  });
  return {handle,asked,calls,agent,reply:result=>answer(result),setPath:newPath=>{path=newPath;}};
}
const idle=()=>new Promise(resolve=>setImmediate(resolve));

test('proactive request sends exactly one native card to the bound root and accepts only a real returned answer',async()=>{
  const f=fixture();
  await Promise.all([f.handle(REQUEST,{...input,selected:'确认讲稿及原件对照'}),f.handle(REQUEST,input)]);
  assert.equal(f.asked.length,1);
  assert.equal(f.asked[0].agent,f.agent);
  assert.deepEqual(f.asked[0].questions,[question]);
  assert.equal(f.calls.length,1);
  f.reply({answers:[{id,selected:['确认讲稿及原件对照']}]});
  await idle();
  assert.equal((await f.handle(STATUS,input)).status,'confirmed');
  assert.equal(f.calls.length,2);
  assert.equal(f.calls[1].args.selected,'确认讲稿及原件对照');
});

test('free text, skip, wrong card, and course switch never apply approval',async()=>{
  for(const answer of [{id,selected:[],custom:'确认'},{id,selected:[]},{id:'stale',selected:['确认讲稿及原件对照']}]){
    const f=fixture();await f.handle(REQUEST,input);f.reply({answers:[answer]});await idle();
    assert.equal((await f.handle(STATUS,input)).status,'skipped');
    assert.equal(f.calls.length,1);
  }
  const f=fixture();await f.handle(REQUEST,input);f.setPath('/fixture/other');
  f.reply({answers:[{id,selected:['确认讲稿及原件对照']}]});await idle();
  assert.equal(f.calls.length,1);
  await assert.rejects(f.handle(STATUS,input),/课程或对话已切换/);
});

test('deferred answer records a non-grant and can reopen from the same right-side channel',async()=>{
  const f=fixture();await f.handle(REQUEST,input);f.reply({answers:[{id,selected:['稍后确认']}]});await idle();
  assert.equal((await f.handle(STATUS,input)).status,'deferred');
  assert.equal(f.calls[1].args.selected,'稍后确认');
  await f.handle(REQUEST,input);
  assert.equal(f.asked.length,2);
  f.reply({answers:[{id,selected:['确认讲稿及原件对照']}]});await idle();
  assert.equal((await f.handle(STATUS,input)).status,'confirmed');
});

test('retracting a displayed stale card never persists a subsequent result',async()=>{
  const f=fixture();await f.handle(REQUEST,input);
  assert.equal((await f.handle('stage-confirmation-cancel',input)).status,'cancelled');
  assert.equal(f.asked[0].signal.aborted,true);
  f.reply({answers:[{id,selected:['确认讲稿及原件对照']}]});await idle();
  assert.equal(f.calls.length,1);
  assert.equal((await f.handle(STATUS,input)).status,'cancelled');
});

test('feedback is saved before explicit dispatch and retry keeps the same feedback ID',async()=>{
  const calls=[],agent={session:{id:input.session_id},status:'running'};
  let durable=false;
  const handle=createStageConfirmationHost({get:()=>new Map([[input.session_id,agent]])},{
    resolveCourse:()=>input.course_path,
    review:async(action,args)=>{
      calls.push(action);
      if(action==='stage_feedback_save')return {ok:true,feedback:{id:args.feedback_id}};
      if(action==='stage_feedback_dispatch_spec')return {ok:true,feedback:{id:args.feedback_id},dispatch_status:durable?'requested':'not_requested'};
      if(action==='stage_feedback_dispatched'){durable=true;return {ok:true};}
      throw Error('unexpected');
    },
    dispatchFeedback:async()=>{calls.push('dispatch');}
  });
  const payload={...input,feedback_id:'a'.repeat(36),text:'修改具体句子'};
  assert.equal((await handle('stage-feedback-submit',payload)).status,'saved');
  assert.deepEqual(calls,['stage_feedback_save','stage_feedback_dispatch_spec']);
  agent.status='idle';
  const results=await Promise.all([handle('stage-feedback-submit',payload),handle('stage-feedback-submit',payload)]);
  assert.deepEqual(results.map(r=>r.status),['requested','requested']);
  assert.equal(calls.filter(c=>c==='dispatch').length,1);
  assert.equal(durable,true);
});
