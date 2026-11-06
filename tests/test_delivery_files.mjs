import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdtemp,mkdir,writeFile,rm,realpath,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {serveDelivery} from '../plugin/delivery-files.mjs';

test('delivered media supports exact seek ranges and refuses changed or unlisted files',async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'kgxc-delivery-range-'))),id='b'.repeat(32),media=join(root,'desktop/final.mp4'),bytes=Buffer.from('0123456789abcdef');
  await mkdir(join(root,'deliveries'));await mkdir(join(root,'desktop'));await writeFile(media,bytes);
  await writeFile(join(root,'deliveries',id+'.json'),JSON.stringify({delivery_root:join(root,'desktop'),files:[{path:media,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}]}));
  const server=createServer((req,res)=>serveDelivery(req,res,new URL(req.url,'http://localhost'),root).catch(error=>{res.writeHead(400);res.end(error.message);}));
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port+'/?course_id='+id+'&index=0';
  try{
    const part=await fetch(base,{headers:{Range:'bytes=3-6'}});assert.equal(part.status,206);assert.equal(part.headers.get('content-range'),'bytes 3-6/16');assert.equal(await part.text(),'3456');
    const suffix=await fetch(base,{headers:{Range:'bytes=-4'}});assert.equal(await suffix.text(),'cdef');
    // Case-insensitive APFS keeps the directory's original case in realpath().
    try{
      await stat(join(root,'DESKTOP/final.mp4'));
      await writeFile(join(root,'deliveries',id+'.json'),JSON.stringify({delivery_root:join(root,'DESKTOP'),files:[{path:join(root,'DESKTOP/final.mp4'),bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}]}));
      const canonical=await fetch(base,{headers:{Range:'bytes=3-6'}});assert.equal(canonical.status,206);assert.equal(await canonical.text(),'3456');
    }catch(error){if(error.code!=='ENOENT')throw error;}
    assert.equal((await fetch(base,{headers:{Range:'bytes=99-100'}})).status,416);
    assert.equal((await fetch(base.replace('index=0','index=1'))).status,400);
    await writeFile(media,Buffer.from('X123456789abcdef'));
    const changed=await fetch(base);assert.equal(changed.status,400);assert.match(await changed.text(),/字节已变化/);
  }finally{await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});}
});
