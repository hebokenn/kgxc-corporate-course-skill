import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {SessionCourses,courseFromLog} from '../plugin/session-courses.mjs';

function result(name,path,{ok=true,id='call1'}={}) {
  return [{type:'assistant/message',data:{message:{content:[{type:'tool-call',id,name,arguments:{}}]}}},
    {type:'tool/result',data:{message:{source:{callId:id},content:[{type:'text',text:JSON.stringify({ok,course_path:path})}]}}}];
}
test('new sessions stay blank; selection persists per session without changing old course files',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'kgxc-session-'));
  try{
    const old=join(dir,'old');await mkdir(old);const draft=join(old,'draft.md');await writeFile(draft,'人工逐字稿');
    const contexts=new SessionCourses(dir);contexts.set('old-session',old);
    assert.equal(contexts.resolve('new-session',{log:[]}).course_path,null);
    contexts.set('new-session',join(dir,'new'));
    const reopened=new SessionCourses(dir);
    assert.equal(reopened.resolve('old-session').course_path,old);
    assert.equal(reopened.resolve('new-session').course_path,join(dir,'new'));
    assert.equal(await readFile(draft,'utf8'),'人工逐字稿');
    assert.equal(reopened.resolve('other-session').ready,false);
  }finally{await rm(dir,{recursive:true,force:true});}
});
test('legacy migration follows successful course tools and ignores injected old context, quotations and failures',()=>{
  const log=[{type:'user/message',data:{source:{kind:'kgxc-course-context'},content:[{type:'text',text:'课程 /tmp/old'}]}},
    ...result('kgxc_course_create','/tmp/new'),...result('kgxc_course_status','/tmp/old',{id:'status'}),
    ...result('kgxc_course_resume','/tmp/broken',{id:'fail',ok:false})];
  assert.equal(courseFromLog(log),'/tmp/new');
  assert.equal(courseFromLog(log.slice(0,1)),null);
  assert.equal(courseFromLog(result('unrelated_tool','/tmp/unrelated')),null);
  assert.equal(courseFromLog([...log,...result('kgxc_course_resume','/tmp/explicit',{id:'resume'})]),'/tmp/explicit');
});
test('late activity in another session cannot switch the current session or replace its explicit selection',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'kgxc-session-'));
  try{
    const contexts=new SessionCourses(dir),agent=id=>({session:{id}});
    contexts.record('kgxc_course_create',{ok:true,course_path:'/tmp/course-a'},agent('session-a'));
    contexts.record('kgxc_course_create',{ok:true,course_path:'/tmp/course-b'},agent('session-b'));
    contexts.record('kgxc_course_status',{ok:true,course_path:'/tmp/course-a'},agent('session-b'));
    assert.equal(contexts.resolve('session-b').course_path,'/tmp/course-b');
    contexts.record('kgxc_course_resume',{ok:true,course_path:'/tmp/course-c'},agent('session-a'));
    assert.equal(contexts.resolve('session-b').course_path,'/tmp/course-b');
    contexts.set('session-b',null);
    assert.equal(contexts.resolve('session-b',{log:result('kgxc_course_create','/tmp/stale')}).course_path,null);
  }finally{await rm(dir,{recursive:true,force:true});}
});
