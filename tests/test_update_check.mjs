import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {updateChecker,newer,stableRelease,CACHE_MS,RELEASE_API} from '../plugin/update-check.mjs';
const release=(version='0.9.0',tag='v6.9.0')=>({tag_name:tag,draft:false,prerelease:false,assets:[{name:`kgxc-course-plugin-v${version}.zip`,state:'uploaded',size:12345}]});
const response=value=>({ok:true,headers:new Map(),text:async()=>JSON.stringify(value)});
test('version comparisons handle stable, preview and numeric ordering without downgrades',()=>{
 for(const [a,b,expected] of [['0.9.0','0.9.0-rc.2',true],['0.8.99','0.9.0-rc.2',false],['0.9.1','0.9.0',true],['0.9.0','0.9.0',false],['0.9.0-rc.10','0.9.0-rc.2',true],['0.9.0-rc.2','0.9.0',false],['bad','0.9.0',false],['0.09.0','0.9.0',false]])assert.equal(newer(a,b),expected);
});
test('stable release requires an uploaded plugin archive, not merely a new core or prerelease',()=>{
 assert.deepEqual(stableRelease(release()),{version:'0.9.0',tag:'v6.9.0',asset:'kgxc-course-plugin-v0.9.0.zip'});
 for(const value of [{...release(),draft:true},{...release(),prerelease:true},release('0.9.1-rc.1'),release('0.9.1','v6.9.1-rc.1'),{...release(),assets:[]},{...release(),assets:[...release().assets,...release().assets]},release('0.9.0','../../other')])assert.equal(stableRelease(value),null);
});
test('checks fixed public metadata, shares in-flight calls and caches for 24 hours across restarts',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'kgxc-update-test-')),cachePath=join(dir,'cache.json');let clock=10000,calls=0,finish;
 const fetcher=(url,options)=>{calls++;assert.equal(url,RELEASE_API);assert.equal(options.redirect,'error');assert.equal(options.headers.Authorization,undefined);assert.equal(Object.keys(options).sort().join(','),'headers,redirect,signal');return new Promise(resolve=>finish=()=>resolve(response(release())));};
 try{
  const check=updateChecker({version:'0.9.0-rc.2',fetcher,now:()=>clock,cachePath});
  const a=check(),b=check();while(!finish)await new Promise(resolve=>setImmediate(resolve));finish();
  const [one,two]=await Promise.all([a,b]);assert.deepEqual(one,two);assert.equal(calls,1);assert.equal(one.update.version,'0.9.0');assert.equal(one.update.release_url,'https://github.com/hebokenn/kgxc-corporate-course-skill/releases/tag/v6.9.0');
  await check();assert.equal(calls,1);
  const reopened=updateChecker({version:'0.9.0-rc.2',fetcher,now:()=>clock,cachePath});await reopened();assert.equal(calls,1);
  clock+=CACHE_MS;finish=null;const next=reopened();while(!finish)await new Promise(resolve=>setImmediate(resolve));finish();await next;assert.equal(calls,2);
  const installed=updateChecker({version:'0.9.0',fetcher,now:()=>clock,cachePath});assert.equal((await installed()).update,null);assert.equal(calls,2);
  assert.equal(JSON.parse(await readFile(cachePath)).schema,1);
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('offline, rate limits, malformed releases and unwritable cache do not fail authoring or trigger loops',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'kgxc-update-test-'));
 try{
  for(const [index,fetcher] of [async()=>{throw Error('offline');},async()=>({ok:false,status:403}),async()=>({ok:true,text:async()=>'{invalid'}),async()=>response(release('0.9.1-rc.1'))].entries()){
   let calls=0;const check=updateChecker({version:'0.9.0',cachePath:join(dir,String(index)),fetcher:async(...args)=>{calls++;return fetcher(...args);}});
   const value=await check();assert.equal(value.ok,true);assert.equal(value.update,null);assert.equal(value.status,'unavailable');await check();assert.equal(calls,1);
  }
  const file=join(dir,'not-a-directory');await writeFile(file,'x');const check=updateChecker({version:'0.8.0',cachePath:join(file,'cache'),fetcher:async()=>response(release())});assert.equal((await check()).update.version,'0.9.0');
 }finally{await rm(dir,{recursive:true,force:true});}
});
