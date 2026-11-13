import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {createUpdateInstaller} from '../plugin/update-install.mjs';

const release={version:'0.9.4',tag:'v6.9.3',asset:'kgxc-course-plugin-v0.9.4.zip'};
const content=Buffer.from('test package');
const sha=createHash('sha256').update(content).digest('hex');
const settle=async updater=>{
  for(let i=0;i<100;i++){
    const state=await updater();
    if(state.phase!=='downloading')return state;
    await new Promise(resolve=>setTimeout(resolve,5));
  }
  throw Error('not settled');
};
async function fixture(run,opts={}){
  const directory=await mkdtemp(join(tmpdir(),'kgxc-updater-'));
  let launchCalls=0,busy=null,receipt;
  const updater=createUpdateInstaller({version:'0.9.3',getRelease:async()=>({release}),busyReason:()=>busy,
    helperPath:new URL('../plugin/update-install-helper.py',import.meta.url),platform:'darwin',directory,
    fetcher:async url=>url.endsWith('SUMS')?new Response(sha+'  '+release.asset+'\n'):
      new Response(content,{headers:{'content-length':String(content.length)}}),
    launch:(python,args,options)=>{
      launchCalls++;assert.equal(python,'python3');assert.ok(args[0].startsWith(directory));assert.match(args[0],/install-helper-[a-f0-9-]+\.py$/);
      assert.ok(args.includes('--request-restart'));receipt=args[args.indexOf('--status')+1];assert.ok(args.includes(sha));assert.ok(args.includes(release.version));assert.ok(options.detached);
      const process=new EventEmitter();process.unref=()=>{};return process;
    },...opts});
  try{await run({updater,directory,report:(status,message)=>writeFile(receipt,JSON.stringify({status,message,version:release.version})),setBusy:value=>busy=value,launchCalls:()=>launchCalls});}finally{await rm(directory,{recursive:true,force:true});}
}

test('downloads and verifies without installing, then requests DSH restart after explicit confirmation',async()=>{
  await fixture(async({updater,setBusy,launchCalls})=>{
    assert.equal((await updater()).phase,'idle');
    assert.equal((await updater('install')).ok,false);
    await updater('download');
    const ready=await settle(updater);assert.equal(ready.phase,'ready');
    assert.equal(ready.received,content.length);assert.equal(launchCalls(),0);
    setBusy('渲染中');assert.equal((await updater()).busy,'渲染中');
    assert.equal((await updater('install')).ok,false);assert.equal(launchCalls(),0);
    setBusy(null);
    const state=await updater('install');assert.equal(state.phase,'installing');
    assert.match(state.message,/重启 DeepSeek Harness/);assert.doesNotMatch(state.message,/Codex/);assert.equal(launchCalls(),1);
    assert.equal((await updater('install')).ok,false);assert.equal(launchCalls(),1);
  });
});
test('rejects different bytes and never arms helper',async()=>{
  await fixture(async({updater,launchCalls})=>{
    await updater('download');assert.match((await settle(updater)).error,/下载校验失败/);
    assert.equal((await updater('install')).ok,false);assert.equal(launchCalls(),0);
  },{fetcher:async url=>url.endsWith('SUMS')?new Response(sha+'  '+release.asset+'\n'):new Response('wrong')});
});
test('rejects CDN redirects to non GitHub destinations',async()=>{
  let called=0;
  await fixture(async({updater})=>{
    await updater('download');assert.match((await settle(updater)).error,/不是官方 GitHub/);assert.equal(called,1);
  },{fetcher:async()=>{called++;return new Response(null,{status:302,headers:{location:'https://other.example/archive'}});}});
});

test('an installed receipt clears an active update and stale persisted downloads are ignored on next launch',async()=>{
  await fixture(async({updater,report,directory,launchCalls})=>{
    await updater('download');await settle(updater);
    await updater('install',release.version);
    await report('installed','插件已更新。');
    assert.deepEqual(await updater(),{ok:true,phase:'idle',installedVersion:release.version});
    assert.deepEqual(await updater('download',release.version),{ok:true,phase:'idle',installedVersion:release.version});
    assert.equal((await updater('install',release.version)).ok,false);
    assert.equal(launchCalls(),1);
    const reopened=createUpdateInstaller({version:release.version,platform:'darwin',directory});
    assert.deepEqual(await reopened(),{ok:true,phase:'idle'});
  });
});

test('deferred restart retains verified package across remount and can restart explicitly again',async()=>{
  await fixture(async({updater,directory,report,launchCalls})=>{
    await updater('download');await settle(updater);
    await updater('install',release.version);
    await report('deferred','请保存未完成工作后重试。');
    const deferred=await updater();
    assert.equal(deferred.phase,'ready');
    assert.equal(deferred.deferred,true);
    assert.match(deferred.message,/请保存未完成工作/);
    const pending=JSON.parse(await readFile(join(directory,'pending.json'),'utf8'));
    assert.equal(pending.sha,sha);
    const reopened=createUpdateInstaller({version:'0.9.3',platform:'darwin',directory});
    assert.equal((await reopened()).phase,'ready');
    assert.equal(launchCalls(),1);
    assert.equal((await updater('install',release.version)).phase,'installing');
    assert.equal(launchCalls(),2);
  });
});
