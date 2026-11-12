import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {request as httpRequest} from 'node:http';
import {existsSync} from 'node:fs';
import {mkdtemp,mkdir,readFile,rm,realpath} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {apply} from '../plugin/dsh.mjs';
import {callWorkspace} from '../plugin/bridge.mjs';

test('DSH registers the shared tools, both skills and an actual environment call', async () => {
  const registered = [], skills = [];
  const ctx = {tools: {register: item => registered.push(item)}, inject: (deps, action) => {
    if (deps.includes('skills')) action({skills: {register: item => skills.push(item)}});
  }};
  apply(ctx);
  assert.equal(registered.length, 10);
  assert.ok(registered.find(tool=>tool.name==='kgxc_course_source_coverage'));
  assert.deepEqual(skills.map(skill => skill.name), ['corporate-training-motion', 'elearning-course-design']);
  for (const skill of skills) { assert.ok(existsSync(skill.path)); assert.ok(skill.content.length > 100); }
  const value = await registered.find(tool => tool.name === 'kgxc_course_environment').execute({});
  assert.equal(value.ok, true);
  assert.equal(value.plugin_version,JSON.parse(await readFile(new URL('../package.json',import.meta.url),'utf8')).version);
  assert.equal(value.core_version,(await readFile(new URL('../VERSION',import.meta.url),'utf8')).trim());
  assert.equal(registered.some(tool => tool.name.includes('confirm')), false);
});

test('DSH local JSON API rejects forged host and missing CSRF token', async () => {
  let handler;
  const ctx = {tools: {register: () => {}}, inject: (deps, action) => {
    if (deps.includes('webServer')) action({effect: fn => fn(), webServer: {getOrigin:()=> 'http://127.0.0.1:12345',register: route => { handler = route.handler; return () => {}; }}});
  }};
  apply(ctx);
  const server = createServer((req, res) => handler(req, res));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  try {
    const meta = await (await fetch(base + '/api/kgxc-course/meta')).json();
    assert.equal(meta.ok, true); assert.equal(meta.token.length, 64);
    assert.equal(meta.version, JSON.parse(await readFile(new URL('../package.json',import.meta.url),'utf8')).version);
    assert.equal(meta.media_origin,'http://127.0.0.1:12345');
    const blocked = await fetch(base + '/api/kgxc-course/call', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: 'kgxc_course_environment'})});
    assert.equal(blocked.status, 403);
    const forged = await new Promise((resolve, reject) => {
      const req = httpRequest(base + '/api/kgxc-course/meta', {headers: {Host: 'untrusted.example'}}, res => { res.resume(); resolve(res.statusCode); });
      req.on('error', reject); req.end();
    });
    assert.equal(forged, 403);
    const result = await (await fetch(base + '/api/kgxc-course/call', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-KGXC-Token': meta.token}, body: JSON.stringify({name: 'kgxc_course_environment', arguments: {}})})).json();
    assert.equal(result.ok, true);
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test('DSH create automatically uses its real session workspace instead of the old global directory',async()=>{
  const folder=await mkdtemp(join(tmpdir(),'kgxc-dsh-workspace-')),workspace=join(folder,'workspace'),config=join(folder,'config');
  await mkdir(workspace);await mkdir(config);const previous=process.env.COURSE_CONFIG_DIR;process.env.COURSE_CONFIG_DIR=config;let course;
  try{
    const registered=[];apply({tools:{register:tool=>registered.push(tool)},inject:()=>{}});
    course=await registered.find(t=>t.name==='kgxc_course_create').execute({title:'DSH工作区技术夹具'},{agent:{session:{id:'session-dsh-workspace-test',header:{cwd:workspace}}}});
    assert.equal(course.ok,true,course.error);assert.ok(course.course_path.startsWith(await realpath(workspace)+'/'));
    const identity=await (await fetch(course.workbench_url+'/api/identity')).json();assert.equal(identity.course_root,course.course_path);
    const health=await callWorkspace('workbench_live',{course_path:course.course_path});
    assert.deepEqual(health,{ok:true,alive:true});
    for(const action of ['cleanup_preview','retention']){
      const result=await callWorkspace(action,{course_path:course.course_path,workspace_path:workspace});
      assert.equal(typeof result.ok,'boolean');assert.notEqual(result.error,'未知工作区操作');
    }
    await assert.rejects(callWorkspace('unrecognized',{course_path:course.course_path}),/未知工作区操作/);
    const association=JSON.parse(await readFile(join(config,'dsh-session-courses.json'),'utf8'));
    assert.equal(association.sessions['session-dsh-workspace-test'].course_path,course.course_path);
  }finally{
    if(course?.ok){const server=JSON.parse(await readFile(join(course.course_path,'project/work/workbench-service.json'),'utf8'));try{process.kill(server.pid,'SIGTERM');}catch{}}
    if(previous===undefined)delete process.env.COURSE_CONFIG_DIR;else process.env.COURSE_CONFIG_DIR=previous;
    await rm(folder,{recursive:true,force:true});
  }
});
test('local update API returns stable metadata without invoking a model or changing courses',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'kgxc-update-api-')),originalFetch=globalThis.fetch,previousCache=process.env.XDG_CACHE_HOME;let handler,calls=0;
 try{
  process.env.XDG_CACHE_HOME=dir;
  globalThis.fetch=async url=>{calls++;assert.equal(url,'https://api.github.com/repos/hebokenn/kgxc-corporate-course-skill/releases/latest');return {ok:true,headers:new Map(),text:async()=>JSON.stringify({tag_name:'v99.0.0',draft:false,prerelease:false,assets:[{name:'kgxc-course-plugin-v99.0.0.zip',state:'uploaded',size:100}]})};};
  apply({tools:{register:()=>{}},inject:(deps,action)=>{if(deps.includes('webServer'))action({effect:fn=>fn(),webServer:{register:route=>{handler=route.handler;return()=>{};}}});}});
  globalThis.fetch=originalFetch;
  let value,status;
  await handler({url:'/api/kgxc-course/updates',method:'GET',headers:{host:'localhost'},socket:{remoteAddress:'127.0.0.1'}},{writeHead:n=>status=n,end:body=>value=JSON.parse(body)});
  assert.equal(status,200);assert.equal(value.update.version,'99.0.0');assert.equal(value.channel,'stable');assert.equal(calls,1);
 }finally{globalThis.fetch=originalFetch;if(previousCache===undefined)delete process.env.XDG_CACHE_HOME;else process.env.XDG_CACHE_HOME=previousCache;await rm(dir,{recursive:true,force:true});}
});
