import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
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
  let launchCalls=0,busy=null;
  const updater=createUpdateInstaller({version:'0.9.3',getRelease:async()=>({release}),busyReason:()=>busy,
    helperPath:new URL('../plugin/update-install-helper.py',import.meta.url),platform:'darwin',directory,
    fetcher:async url=>url.endsWith('SUMS')?new Response(sha+'  '+release.asset+'\n'):
      new Response(content,{headers:{'content-length':String(content.length)}}),
    launch:(python,args,options)=>{
      launchCalls++;assert.equal(python,'python3');assert.ok(args[0].startsWith(directory));assert.match(args[0],/install-helper-[a-f0-9-]+\.py$/);
      assert.ok(args.includes(sha));assert.ok(args.includes(release.version));assert.ok(options.detached);
      const process=new EventEmitter();process.unref=()=>{};return process;
    },...opts});
  try{await run({updater,setBusy:value=>busy=value,launchCalls:()=>launchCalls});}finally{await rm(directory,{recursive:true,force:true});}
}

test('downloads and verifies without installing, then awaits normal DSH quit after explicit confirmation',async()=>{
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
    assert.match(state.message,/正常退出/);assert.equal(launchCalls(),1);
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
