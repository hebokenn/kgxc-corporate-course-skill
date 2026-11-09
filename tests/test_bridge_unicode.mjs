import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {callReview,callTool,tools} from '../plugin/bridge.mjs';

const payload='x'.repeat(70*1024)+'证据原句：画面应随讲解推进。😀；完整结束。';
const stderrTail='证据中文错误：子进程传输必须保留完整字符。😀';
const digest=text=>createHash('sha256').update(text).digest('hex');
const quote=text=>"'"+text.replaceAll("'","'\\''")+"'";
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

// This executable replaces only the Python executable for this process. The
// real exported callTool/callReview still spawn through bridge.invoke.
async function fakeService(){
  const {writeFile}=await import('node:fs/promises');
  let input='';for await(const chunk of process.stdin)input+=chunk;const request=JSON.parse(input),mode=request.arguments.fixture_mode;
  if(mode.startsWith('ignore-term')){
    const {writeFileSync}=await import('node:fs');
    // Publish PID only after the resistant handler is installed: the parent
    // cannot accidentally test default SIGTERM handling during startup.
    process.on('SIGTERM',()=>{
      writeFileSync(request.arguments.term_file,'SIGTERM');
      if(mode==='ignore-term-late-json')process.stdout.write(JSON.stringify({late:true}));
    });
  }
  if(request.arguments.pid_file)await writeFile(request.arguments.pid_file,String(process.pid));
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const split=async(stream,text)=>{
    const data=Buffer.from(text),position=data.indexOf(Buffer.from('证'));
    for(const [start,end] of [[0,position+1],[position+1,position+2],[position+2,data.length]]){await new Promise(resolve=>stream.write(data.subarray(start,end),resolve));await pause(30);}
  };
  if(mode==='hang'){setInterval(()=>{},1000);return;}
  if(mode.startsWith('ignore-term')){
    if(mode==='ignore-term-oversized')process.stdout.write('x'.repeat(12*1024*1024+1));
    setInterval(()=>{},1000);return;
  }
  if(mode==='oversized'){process.stdout.write('x'.repeat(12*1024*1024+1));return;}
  if(mode==='invalid'){process.stdout.write('not-json');return;}
  if(mode==='stderr'){await split(process.stderr,'前缀'.repeat(3000)+'证据中文错误：子进程传输必须保留完整字符。😀');process.exitCode=1;return;}
  await split(process.stdout,JSON.stringify({name:request.name,route:process.argv.includes('--review-once')?'review':'tool',payload:'x'.repeat(70*1024)+'证据原句：画面应随讲解推进。😀；完整结束。'}));
}

async function awaitPid(path){for(let i=0;i<1000;i++){try{return Number(await readFile(path,'utf8'));}catch{await delay(5);}}throw Error('synthetic bridge child did not start');}
async function assertExited(pid){for(let i=0;i<200;i++){try{process.kill(pid,0);}catch(error){if(error.code==='ESRCH')return;throw error;}await delay(5);}assert.fail('synthetic child did not exit');}
async function cleanupOwnedFixture(pid){
  if(!pid)return;
  try{process.kill(pid,'SIGKILL');}catch(error){if(error.code!=='ESRCH')throw error;}
  await assertExited(pid);
}

test('bridge invoke preserves split UTF-8 and its existing process limits',async t=>{
  const directory=await mkdtemp(join(tmpdir(),'kgxc-bridge-unicode-')),child=join(directory,'service.mjs'),executable=join(directory,'python-fixture'),previous=process.env.KGXC_COURSE_PYTHON;
  await writeFile(child,'('+fakeService.toString()+')().catch(error=>{process.stderr.write(error.message);process.exitCode=1;});\n');
  await writeFile(executable,'#!/bin/sh\nexec '+quote(process.execPath)+' '+quote(child)+' "$@"\n',{mode:0o700});process.env.KGXC_COURSE_PYTHON=executable;
  try{
    for(const [route,call,name] of [['review',callReview,'packet'],['tool',callTool,tools[0].name]])await t.test(route+' stdout JSON crosses 64 KiB and split Chinese bytes',async()=>{
      const value=await call(name,{fixture_mode:'unicode'});assert.equal(value.route,route);assert.equal(value.name,name);assert.equal(value.payload.includes('\uFFFD'),false);assert.equal(digest(value.payload),digest(payload));
    });
    await t.test('stderr split Chinese is preserved inside the existing capped error',async()=>{
      await assert.rejects(callTool(tools[0].name,{fixture_mode:'stderr'}),error=>{assert.equal(error.message.includes('\uFFFD'),false);assert.ok(error.message.endsWith(stderrTail));assert.ok(error.message.length<1600);return true;});
    });
    await t.test('12 MiB response cap remains enforced',async()=>{await assert.rejects(callReview('packet',{fixture_mode:'oversized'}),/制课响应过大/);});
    await t.test('invalid JSON remains rejected',async()=>{await assert.rejects(callReview('packet',{fixture_mode:'invalid'}),/制课服务返回了无效数据/);});
    await t.test('timeout terminates the real child',async()=>{
      const pidFile=join(directory,'timeout.pid'),result=assert.rejects(callReview('packet',{fixture_mode:'hang',pid_file:pidFile},{timeout:3000}),/制课请求超时/),pid=await awaitPid(pidFile);await result;await assertExited(pid);
    });
    await t.test('abort terminates the real child',async()=>{
      const pidFile=join(directory,'abort.pid'),controller=new AbortController(),result=assert.rejects(callTool(tools[0].name,{fixture_mode:'hang',pid_file:pidFile},{signal:controller.signal}),error=>error.name==='AbortError'),pid=await awaitPid(pidFile);controller.abort();await result;await assertExited(pid);
    });
    for(const trigger of ['timeout','abort','oversized'])await t.test(trigger+' reaps a SIGTERM-resistant owned child and preserves its original error',async()=>{
      const pidFile=join(directory,'resistant-'+trigger+'.pid'),termFile=join(directory,'resistant-'+trigger+'.term');
      const controller=new AbortController(),mode=trigger==='oversized'?'ignore-term-oversized':'ignore-term-late-json';
      const options=trigger==='abort'?{signal:controller.signal}:{timeout:3000};
      let pid;
      const result=assert.rejects(callReview('packet',{fixture_mode:mode,pid_file:pidFile,term_file:termFile},options),error=>{
        if(trigger==='abort'){assert.equal(error.name,'AbortError');assert.equal(error.code,'ABORT_ERR');}
        else assert.equal(error.message,trigger==='timeout'?'制课请求超时；请查询实际课程状态后继续':'制课响应过大，请使用摘要查询');
        return true;
      });
      try{
        pid=await awaitPid(pidFile);if(trigger==='abort')controller.abort();
        await result;await assertExited(pid);
        assert.equal(await readFile(termFile,'utf8'),'SIGTERM');
      }finally{await cleanupOwnedFixture(pid);}
    });
  }finally{if(previous===undefined)delete process.env.KGXC_COURSE_PYTHON;else process.env.KGXC_COURSE_PYTHON=previous;await rm(directory,{recursive:true,force:true});}
});
