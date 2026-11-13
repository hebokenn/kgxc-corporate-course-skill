import {readFile,mkdir,writeFile,rename} from 'node:fs/promises';
import {homedir} from 'node:os';
import {dirname,join} from 'node:path';
import {randomUUID} from 'node:crypto';

const REPOSITORY='hebokenn/kgxc-corporate-course-skill';
export const RELEASE_API=`https://api.github.com/repos/${REPOSITORY}/releases/latest`;
export const RELEASE_WEB=`https://github.com/${REPOSITORY}/releases/latest`;
export const CACHE_MS=15*60*1000;
export const RETRY_MS=2*60*1000;
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
const requestOptions=()=>({redirect:'manual',signal:AbortSignal.timeout(4000)});
const header=(response,name)=>response.headers?.get?.(name);
const isRedirect=response=>[301,302,303,307,308].includes(response.status);
const limited=response=>response.status===429||(response.status===403&&(
 header(response,'x-ratelimit-remaining')==='0'||Boolean(header(response,'retry-after'))));
async function boundedText(response,max){
 if(Number(header(response,'content-length'))>max)throw Error('Release metadata too large');
 const body=await response.text();
 if(body.length>max)throw Error('Release metadata too large');
 return body;
}
function redirectUrl(response,base){
 const target=header(response,'location');
 if(!target)return null;
 const url=new URL(target,base);
 return url.protocol==='https:'&&!url.username&&!url.password&&!url.port?url:null;
}
async function webStableRelease(fetcher){
 const latest=await fetcher(RELEASE_WEB,requestOptions());
 const url=isRedirect(latest)&&redirectUrl(latest,RELEASE_WEB);
 const prefix=`/${REPOSITORY}/releases/tag/`;
 if(!url||url.hostname!=='github.com'||url.search||url.hash||!url.pathname.startsWith(prefix))return null;
 const tag=url.pathname.slice(prefix.length);
 if(!/^v\d+\.\d+\.\d+$/.test(tag)||!parseVersion(tag.slice(1)))return null;
 const checksumUrl=`https://github.com/${REPOSITORY}/releases/download/${tag}/PLUGIN-SHA256SUMS`;
 let checksums=await fetcher(checksumUrl,requestOptions());
 if(isRedirect(checksums)){
  const download=redirectUrl(checksums,checksumUrl);
  if(!download||!['release-assets.githubusercontent.com','objects.githubusercontent.com'].includes(download.hostname))return null;
  checksums=await fetcher(download.href,requestOptions());
 }
 if(!checksums.ok)return null;
 const entries=(await boundedText(checksums,64*1024)).split(/\r?\n/).flatMap(line=>{
  const match=/^([a-f0-9]{64}) [ *](kgxc-course-plugin-v(\d+\.\d+\.\d+)\.zip)$/i.exec(line);
  return match&&match[2]===`kgxc-course-plugin-v${match[3]}.zip`&&parseVersion(match[3])?[match]:[];
 });
 if(entries.length!==1)return null;
 const [,,asset,version]=entries[0];
 return {version,tag,asset};
}
export async function getStableRelease({fetcher=globalThis.fetch}={}){
 const unavailable=reason=>({status:'unavailable',release:null,source:null,reason});
 try{
  // Public metadata only. No tokens, course data, model selection or user IDs.
  const response=await fetcher(RELEASE_API,{headers:{Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},redirect:'error',signal:AbortSignal.timeout(4000)});
  if(limited(response)){
   try{
    const release=await webStableRelease(fetcher);
    if(release)return {status:'checked',release,source:'github-web',reason:null};
   }catch{/* An unavailable fallback does not establish a release. */}
   return unavailable('github_anonymous_rate_limit');
  }
  if(!response.ok)return unavailable('github_http_error');
  try{
   const release=stableRelease(JSON.parse(await boundedText(response,1024*1024)));
   return release?{status:'checked',release,source:'github-api',reason:null}:unavailable('invalid_stable_release');
  }catch{return unavailable('invalid_stable_release');}
 }catch{return unavailable('network_unavailable');}
}
export function updateChecker({version,fetcher=globalThis.fetch,now=Date.now,cachePath=join(process.env.XDG_CACHE_HOME||join(homedir(),'.cache'),'kgxc-course','stable-release.json')}={}){
 let loaded=false,cache=null,pending;
 const result=()=>{
  const release=cache?.status==='checked'?cachedRelease(cache.release):null,available=release&&newer(release.version,version);
  return {ok:true,current_version:version,channel:'stable',status:cache?.status||'unavailable',checked_at:cache?.checked_at||null,
   reason:cache?.reason||null,
   update:available?{version:release.version,release_url:`https://github.com/${REPOSITORY}/releases/tag/${encodeURIComponent(release.tag)}`} :null};
 };
 return async({force=false}={})=>{
  if(pending)return pending;
  pending=(async()=>{
   if(!loaded){loaded=true;try{cache=JSON.parse(await readFile(cachePath,'utf8'));}catch{}}
   const age=now()-cache?.checked_at;
   if(!force&&cache?.schema===1&&['checked','unavailable'].includes(cache.status)&&Number.isFinite(age)&&age>=0&&age<(cache.status==='checked'?CACHE_MS:RETRY_MS))return result();
   const live=await getStableRelease({fetcher});
   cache={schema:1,checked_at:now(),...live};
   try{await mkdir(dirname(cachePath),{recursive:true});const temp=cachePath+'.'+randomUUID()+'.tmp';await writeFile(temp,JSON.stringify(cache),{mode:0o600});await rename(temp,cachePath);}catch{/* In-memory cache still limits checks when disk cache is unavailable. */}
   return result();
  })();
  try{return await pending;}finally{pending=null;}
 };
}
