import {randomBytes} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';

export function studioProxy({resolveCourse,validToken,json}){
  const grants=new Map();
  async function open(args){
    const course=resolveCourse(args.session_id);
    if(!course||course!==args.course_path)throw Error('课程已切换，请重新打开当前课程');
    const record=JSON.parse(readFileSync(join(course,'project/work/workbench-service.json'),'utf8'));
    const url=new URL(record.url);
    if(url.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.username||url.password||url.pathname!=='/')throw Error('课程后台地址无效');
    const identity=await (await fetch(url.origin+'/api/identity')).json();
    if(identity.course_root!==course)throw Error('课程后台版本或归属不一致');
    let key=[...grants].find(([,g])=>g.session_id===args.session_id&&g.course===course&&g.origin===url.origin)?.[0];
    if(!key){key=randomBytes(20).toString('hex');grants.set(key,{session_id:args.session_id,course,origin:url.origin});}
    return {ok:true,resource_base:'/api/kgxc-course/content/'+key};
  }
  async function serve(req,res,url){
    const match=/^\/api\/kgxc-course\/content\/([a-f0-9]{40})(\/.*)$/.exec(url.pathname),grant=match&&grants.get(match[1]);
    if(!grant||resolveCourse(grant.session_id)!==grant.course)return json(res,403,{ok:false,error:'课程已切换或本次资源授权已失效'});
    if(!['GET','HEAD','POST'].includes(req.method))return json(res,405,{ok:false,error:'未知课程请求'});
    if(req.method==='POST'&&!validToken(req))return json(res,403,{ok:false,error:'请重新连接课程工作台'});
    const path=match[2];
    if(!/^\/(?:api\/|course-file(?:\?|$)|native\/|project\/|download\/)/.test(path))return json(res,404,{ok:false,error:'未开放的课程资源'});
    const headers={origin:grant.origin};
    for(const name of ['content-type','range','x-filename','x-base-revision'])if(req.headers[name])headers[name]=req.headers[name];
    let body;
    if(req.method==='POST'){
      const chunks=[];let size=0;
      for await(const chunk of req){size+=chunk.length;if(size>25*1024*1024)return json(res,413,{ok:false,error:'课程文件超过25MB'});chunks.push(chunk);}
      body=Buffer.concat(chunks);
    }
    const controller=new AbortController();res.once('close',()=>controller.abort());
    const response=await fetch(grant.origin+path+url.search,{method:req.method,headers,body,redirect:'error',signal:controller.signal});
    const outgoing={};
    for(const name of ['content-type','content-length','content-range','accept-ranges','content-disposition'])if(response.headers.has(name))outgoing[name]=response.headers.get(name);
    outgoing['cache-control']='no-store';res.writeHead(response.status,outgoing);
    if(response.body&&req.method!=='HEAD')await pipeline(Readable.fromWeb(response.body),res);else res.end();
  }
  return {open,serve};
}
