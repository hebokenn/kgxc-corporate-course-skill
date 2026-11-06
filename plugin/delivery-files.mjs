import {createReadStream} from 'node:fs';
import {readFile,realpath,lstat,stat} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join,resolve,sep,basename,extname} from 'node:path';
import {createHash} from 'node:crypto';

const verified=new Map();

export async function serveDelivery(req,res,url,directory=process.env.COURSE_CONFIG_DIR||join(process.env.XDG_CONFIG_HOME||join(homedir(),'.config'),'corporate-training-motion')) {
  const id=url.searchParams.get('course_id'),index=Number(url.searchParams.get('index'));
  if(!/^[a-f0-9]{32}$/.test(id||'')||!Number.isInteger(index)||index<0)throw Error('交付文件标识无效');
  const receipt=JSON.parse(await readFile(join(directory,'deliveries',id+'.json'),'utf8'));
  const file=receipt.files[index];if(!file)throw Error('交付文件不存在');
  const requestedRoot=resolve(receipt.delivery_root),requested=resolve(file.path);
  const root=await realpath(requestedRoot),path=await realpath(requested);
  // APFS may preserve "AI" while the saved user path says "ai". Compare
  // canonical containment, retaining the regular-file and exact-byte guards.
  if(!requested.startsWith(requestedRoot+sep)||!path.startsWith(root+sep)||(await lstat(requested)).isSymbolicLink())throw Error('交付文件位置已变化');
  const info=await stat(path);if(!info.isFile()||info.size!==file.bytes)throw Error('交付文件已变化，请重新核对');
  const key=path+':'+info.size+':'+info.mtimeMs+':'+info.ctimeMs+':'+info.ino;
  if(verified.get(key)!==file.sha256){const hash=createHash('sha256');for await(const chunk of createReadStream(path))hash.update(chunk);if(hash.digest('hex')!==file.sha256)throw Error('交付文件字节已变化，请重新核对');if(verified.size>=24)verified.clear();verified.set(key,file.sha256);}
  const range=req.headers.range;let first=0,last=info.size-1,status=200;
  if(range){const match=/^bytes=(\d*)-(\d*)$/.exec(range);if(!match||!match[1]&&!match[2]){res.writeHead(416,{'content-range':'bytes */'+info.size});res.end();return;}
    first=match[1]?Number(match[1]):Math.max(0,info.size-Number(match[2]));last=match[1]&&match[2]?Math.min(Number(match[2]),last):last;
    if(first>last||first>=info.size){res.writeHead(416,{'content-range':'bytes */'+info.size});res.end();return;}status=206;
  }
  const headers={'content-type':({'.mp4':'video/mp4','.srt':'application/x-subrip','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'})[extname(path).toLowerCase()]||'application/octet-stream',
    'content-length':last-first+1,'accept-ranges':'bytes','cache-control':'private, no-cache','x-content-type-options':'nosniff'};
  if(status===206)headers['content-range']=`bytes ${first}-${last}/${info.size}`;
  if(url.searchParams.get('download')==='1')headers['content-disposition']="attachment; filename*=UTF-8''"+encodeURIComponent(basename(path));
  res.writeHead(status,headers);
  const stream=createReadStream(path,{start:first,end:last});stream.on('error',()=>res.destroy());res.on('close',()=>stream.destroy());stream.pipe(res);
}
