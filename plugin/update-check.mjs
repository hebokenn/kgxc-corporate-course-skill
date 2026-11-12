import {readFile,mkdir,writeFile,rename} from 'node:fs/promises';
import {homedir} from 'node:os';
import {dirname,join} from 'node:path';
import {randomUUID} from 'node:crypto';

const REPOSITORY='hebokenn/kgxc-corporate-course-skill';
export const RELEASE_API=`https://api.github.com/repos/${REPOSITORY}/releases/latest`;
export const CACHE_MS=24*60*60*1000;
const SEMVER=/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
export function parseVersion(value){
 if(typeof value!=='string'||value.length>100)return null;
 const match=SEMVER.exec(value);if(!match)return null;
 const numbers=match.slice(1,4).map(Number);if(numbers.some(n=>!Number.isSafeInteger(n)))return null;
 const pre=match[4]?.split('.')||[];if(pre.some(x=>/^\d+$/.test(x)&&x.length>1&&x[0]==='0'))return null;
 return {numbers,pre};
}
export function newer(candidate,current){
 const a=parseVersion(candidate),b=parseVersion(current);if(!a||!b)return false;
 for(let i=0;i<3;i++)if(a.numbers[i]!==b.numbers[i])return a.numbers[i]>b.numbers[i];
 if(!a.pre.length||!b.pre.length)return !a.pre.length&&Boolean(b.pre.length);
 for(let i=0;i<Math.max(a.pre.length,b.pre.length);i++){
  if(a.pre[i]===undefined)return false;if(b.pre[i]===undefined)return true;
  if(a.pre[i]===b.pre[i])continue;
  const numeric=x=>/^\d+$/.test(x);
  if(numeric(a.pre[i])&&numeric(b.pre[i]))return BigInt(a.pre[i])>BigInt(b.pre[i]);
  if(numeric(a.pre[i])!==numeric(b.pre[i]))return !numeric(a.pre[i]);
  return a.pre[i]>b.pre[i];
 }
 return false;
}
export function stableRelease(value){
 if(!value||value.draft!==false||value.prerelease!==false||!Array.isArray(value.assets))return null;
 const tag=value.tag_name,core=typeof tag==='string'&&tag.startsWith('v')?parseVersion(tag.slice(1)):null;
 if(!core||core.pre.length)return null;
 const candidates=value.assets.flatMap(asset=>{
  if(asset.state!=='uploaded'||!Number.isSafeInteger(asset.size)||asset.size<=0)return [];
  const name=asset.name,match=typeof name==='string'&&/^kgxc-course-plugin-v(.+)\.zip$/.exec(name),version=match?.[1],parsed=parseVersion(version);
  return parsed&&!parsed.pre.length?[{version,tag,asset:name}]:[];
 });
 return candidates.length===1?candidates[0]:null;
}
function cachedRelease(value){
 if(!value)return null;
 return stableRelease({draft:false,prerelease:false,tag_name:value.tag,assets:[{name:value.asset,size:1,state:'uploaded'}]});
}
export function updateChecker({version,fetcher=globalThis.fetch,now=Date.now,cachePath=join(process.env.XDG_CACHE_HOME||join(homedir(),'.cache'),'kgxc-course','stable-release.json')}={}){
 let loaded=false,cache=null,pending;
 const result=()=>{
  const release=cachedRelease(cache?.release),available=release&&newer(release.version,version);
  return {ok:true,current_version:version,channel:'stable',status:cache?.status||'unavailable',checked_at:cache?.checked_at||null,
   update:available?{version:release.version,release_url:`https://github.com/${REPOSITORY}/releases/tag/${encodeURIComponent(release.tag)}`} :null};
 };
 return async()=>{
  if(pending)return pending;
  pending=(async()=>{
   if(!loaded){loaded=true;try{cache=JSON.parse(await readFile(cachePath,'utf8'));}catch{}}
   const age=now()-cache?.checked_at;
   if(cache?.schema===1&&['checked','unavailable'].includes(cache.status)&&Number.isFinite(age)&&age>=0&&age<CACHE_MS)return result();
   let release=null,status='unavailable';
   try{
    // Public metadata only. No tokens, course data, model selection or user IDs.
    const response=await fetcher(RELEASE_API,{headers:{Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},redirect:'error',signal:AbortSignal.timeout(4000)});
    if(response.ok){
     const length=Number(response.headers?.get?.('content-length'));if(length>1024*1024)throw Error('Release metadata too large');
     const text=await response.text();if(text.length>1024*1024)throw Error('Release metadata too large');
     release=stableRelease(JSON.parse(text));status=release?'checked':'unavailable';
    }
   }catch{/* Offline, rate-limited or malformed metadata never blocks authoring. */}
   cache={schema:1,checked_at:now(),status,release};
   try{await mkdir(dirname(cachePath),{recursive:true});const temp=cachePath+'.'+randomUUID()+'.tmp';await writeFile(temp,JSON.stringify(cache),{mode:0o600});await rename(temp,cachePath);}catch{/* In-memory cache still limits checks when disk cache is unavailable. */}
   return result();
  })();
  try{return await pending;}finally{pending=null;}
 };
}
