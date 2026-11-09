import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {studioProxy} from '../plugin/studio-proxy.mjs';

test('native course proxy binds the selected course, enforces mutations and streams real byte ranges',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-native-proxy-'));let selected=root,mutations=0,received;
  const backend=createServer(async(req,res)=>{
    if(req.url==='/api/identity'){res.setHeader('content-type','application/json');return res.end(JSON.stringify({course_root:root}));}
    if(req.url.startsWith('/course-file')){res.writeHead(206,{'content-type':'video/mp4','content-range':'bytes 1-2/5','content-length':2,'accept-ranges':'bytes'});return res.end('bc');}
    if(req.method==='POST'){let body='';for await(const chunk of req)body+=chunk;received={body,origin:req.headers.origin,revision:req.headers['x-base-revision']};mutations++;}
    res.setHeader('content-type','application/json');res.end(JSON.stringify({ok:true,text:'实际课程正文'}));
  });
  await new Promise(resolve=>backend.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+backend.address().port;
  await mkdir(join(root,'project/work'),{recursive:true});await writeFile(join(root,'project/work/workbench-service.json'),JSON.stringify({url:origin}));
  const proxy=studioProxy({resolveCourse:()=>selected,validToken:req=>req.headers['x-kgxc-token']==='current',json:(res,status,value)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(value));}});
  const server=createServer((req,res)=>proxy.serve(req,res,new URL(req.url,'http://localhost')).catch(error=>{res.writeHead(500);res.end(error.message);}));
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
  try{
    await assert.rejects(proxy.open({session_id:'S',course_path:'/another-course'}));
    const access=await proxy.open({session_id:'S',course_path:root});
    assert.equal((await proxy.open({session_id:'S',course_path:root})).resource_base,access.resource_base);
    const path=base+access.resource_base;
    assert.equal((await (await fetch(path+'/api/studio')).json()).text,'实际课程正文');
    assert.equal((await fetch(path+'/api/studio/sections',{method:'POST',body:'{}'})).status,403);assert.equal(mutations,0);
    const body=JSON.stringify({text:'人工新增\n请保留'});
    assert.equal((await fetch(path+'/api/studio/sections',{method:'POST',headers:{'X-KGXC-Token':'current','X-Base-Revision':'8','Content-Type':'application/json'},body})).status,200);
    assert.deepEqual(received,{body,origin,revision:'8'});assert.equal(mutations,1);
    const media=await fetch(path+'/course-file?path=delivery/video.mp4',{headers:{Range:'bytes=1-2'}});
    assert.equal(media.status,206);assert.equal(media.headers.get('content-range'),'bytes 1-2/5');assert.equal(await media.text(),'bc');
    assert.equal((await fetch(path+'/not-exposed')).status,404);
    selected='/new-course';assert.equal((await fetch(path+'/api/studio')).status,403);
  }finally{await new Promise(resolve=>server.close(resolve));await new Promise(resolve=>backend.close(resolve));await rm(root,{recursive:true,force:true});}
});
