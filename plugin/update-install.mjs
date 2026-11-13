import {createHash,randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {chmod,mkdir,mkdtemp,open,readFile,realpath,rename,rm,stat,writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {newer,parseVersion} from './update-check.mjs';

const origin='https://github.com';
const repository='/hebokenn/kgxc-corporate-course-skill';
const trustedAssets=new Set(['release-assets.githubusercontent.com','objects.githubusercontent.com']);
const sizeLimit=350*1024*1024;
const validStable=s=>typeof s==='string'&&/^\d+\.\d+\.\d+$/.test(s)&&Boolean(parseVersion(s));
function assetURL(tag,name){
  if(!validStable(tag?.slice(1))||tag[0]!=='v'||!/^[a-zA-Z0-9.\-]+$/.test(name))throw Error('更新版本无效。');
  return origin+repository+'/releases/download/'+tag+'/'+name;
}

async function publicAsset(fetcher,url,timeout){
  const signal=AbortSignal.timeout(timeout);
  let current=new URL(url);
  for(let i=0;i<4;i++){
    if(current.protocol!=='https:'||current.username||current.password||current.port||
       !(i===0?current.origin===origin&&current.pathname.startsWith(repository+'/releases/download/'):trustedAssets.has(current.hostname)))
      throw Error('更新下载地址不是官方 GitHub 文件。');
    const r=await fetcher(current.href,{signal,redirect:'manual'});
    if(r.ok)return r;
    if(![301,302,303,307,308].includes(r.status))throw Error('GitHub 下载失败（'+r.status+'）。');
    const next=r.headers.get('location');
    await r.body?.cancel?.();
    if(!next)throw Error('GitHub 未提供下载地址。');
    current=new URL(next,current);
  }
  throw Error('GitHub 下载跳转过多。');
}
async function readBounded(response,max){
  if(!response.body)throw Error('下载内容为空。');
  let bytes=0;const chunks=[];
  for await(const chunk of response.body){
    bytes+=chunk.byteLength;if(bytes>max)throw Error('更新校验文件超过大小限制。');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8');
}
function archiveHash(text,asset){
  const hits=text.split(/\r?\n/).map(line=>/^([0-9a-f]{64})\s+\*?([\w.\-]+)\s*$/i.exec(line)).filter(row=>row?.[2]===asset);
  if(hits.length!==1)throw Error('官方校验文件没有唯一匹配的安装包。');
  return hits[0][1].toLowerCase();
}

export function createUpdateInstaller({version,getRelease,busyReason,helperPath,python='python3',
   fetcher=globalThis.fetch,launch=spawn,platform=process.platform,
   directory=join(process.env.XDG_DATA_HOME||join(homedir(),'.local/share'),'kgxc-course','updates')}={}){
  let state={phase:'idle'},candidate=null,operation=null,receipt=null;
  const statePath=join(directory,'pending.json');
  async function save(data){
    await mkdir(directory,{recursive:true,mode:0o700});await chmod(directory,0o700);
    const tmp=join(directory,randomUUID()+'.tmp');
    await writeFile(tmp,JSON.stringify(data),{mode:0o600});await rename(tmp,statePath);
  }
  async function restore(){
    if(operation||state.phase!=='idle')return;
    try{
      const previous=JSON.parse(await readFile(statePath,'utf8'));
      if(!validStable(previous.version)||!newer(previous.version,version))return;
      if(typeof previous.folder!=='string'||!/^bundle-[a-zA-Z0-9]+$/.test(previous.folder)||!/^[0-9a-f]{64}$/.test(previous.sha))return;
      const folder=await realpath(join(directory,previous.folder)),archive=join(folder,'plugin.zip');
      if(!(await stat(archive)).isFile())return;
      candidate={...previous,archive,folder};
      receipt=join(folder,'result.json');
      state={phase:'ready',version:previous.version,total:previous.total,received:previous.total};
    }catch{}
  }
  const boot=restore();
  async function view(){
    await boot;
    if(receipt){
      try{
        const r=JSON.parse(await readFile(receipt,'utf8'));
        if(r.version===state.version){
          if(r.status==='failed')state={...state,phase:'failed',error:r.message||'安装失败，旧版未自动覆盖。'};
          if(r.status==='waiting'||r.status==='installing')state={...state,phase:'installing'};
        }
      }catch{}
    }
    const busy=state.phase==='ready'?await busyReason?.():null;
    return {ok:true,...state,...(busy?{busy}:{}),...(state.phase==='installing'?{message:'请正常退出 DeepSeek Harness。更新完成后会自动重开；不用退出 Codex。'}:{})};
  }
  async function download(expected){
    let folder;
    try{
      const {release}=await getRelease();
      if(expected&&release?.version!==expected)throw Error('可用更新已变化，请重新检查。');
      if(!release||!validStable(release.version)||!newer(release.version,version)||release.asset!=='kgxc-course-plugin-v'+release.version+'.zip')throw Error('没有可下载的较新稳定版。');
      state={phase:'downloading',version:release.version,received:0,total:release.size||0};
      await mkdir(directory,{recursive:true,mode:0o700});await chmod(directory,0o700);
      folder=await realpath(await mkdtemp(join(directory,'bundle-')));
      const sha=archiveHash(await readBounded(await publicAsset(fetcher,assetURL(release.tag,'PLUGIN-SHA256SUMS'),15000),16384),release.asset);
      const response=await publicAsset(fetcher,assetURL(release.tag,release.asset),10*60*1000);
      const length=Number(response.headers.get('content-length'));
      if(!response.body||length>sizeLimit||release.size>sizeLimit)throw Error('安装包为空或超过大小限制。');
      state={...state,total:release.size||length||0};
      const partial=join(folder,'plugin.partial'),archive=join(folder,'plugin.zip');
      const file=await open(partial,'wx',0o600),hash=createHash('sha256');
      try{
        for await(const chunk of response.body){
          state.received+=chunk.byteLength;
          if(state.received>sizeLimit)throw Error('安装包超过大小限制。');
          hash.update(chunk);
          let offset=0;while(offset<chunk.byteLength){const {bytesWritten}=await file.write(chunk,offset,chunk.byteLength-offset);if(!bytesWritten)throw Error('安装包写入失败。');offset+=bytesWritten;}
        }
        if(!state.received||state.total&&state.received!==state.total||hash.digest('hex')!==sha)throw Error('下载校验失败，未安装。');
        await file.sync();
      }finally{await file.close();}
      await rename(partial,archive);
      const record={version:release.version,sha,total:state.received,folder:folder.split('/').at(-1)};
      await save(record);candidate={...record,archive,folder};receipt=join(folder,'result.json');
      state={...state,phase:'ready',total:state.received};
    }catch(error){
      if(folder)await rm(folder,{recursive:true,force:true}).catch(()=>{});
      state={...state,phase:'failed',error:error.message||'无法下载更新。'};
    }
  }
  return async(action,expected)=>{
    await boot;
    if(!action)return view();
    if(platform!=='darwin')return {ok:false,error:'应用内安装仅支持 macOS 桌面版。'};
    if(action==='download'){
      if(!operation&&!['ready','installing'].includes(state.phase)){
        receipt=null;candidate=null;state={phase:'downloading',received:0,total:0};
        operation=download(expected).finally(()=>{operation=null;});
      }
      return view();
    }
    if(action==='install'){
      if(state.phase!=='ready'||!candidate||operation||expected&&expected!==candidate.version)return {ok:false,error:'请先下载并校验更新。'};
      const busy=await busyReason?.();
      if(busy)return {ok:false,code:'install_busy',error:busy};
      if(state.phase!=='ready')return view();
      state={...state,phase:'installing'};
      try{
        const detachedHelper=join(candidate.folder,'install-helper-'+randomUUID()+'.py');
        await writeFile(detachedHelper,await readFile(helperPath),{flag:'wx',mode:0o600});
        const child=launch(python,[detachedHelper,'--archive',candidate.archive,'--version',candidate.version,'--sha256',candidate.sha,'--status',receipt,'--wait-pid',String(process.pid)],{detached:true,stdio:'ignore'});
        child.once('error',()=>{state={...state,phase:'failed',error:'未能启动安装助手，旧版未改动。'};});
        child.unref();
      }catch{state={...state,phase:'failed',error:'未能启动安装助手，旧版未改动。'};}
      return view();
    }
    return {ok:false,error:'未知更新操作。'};
  };
}
