import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {test} from 'node:test';
import {inflateSync} from 'node:zlib';
import {probeReviewer} from '../plugin/review-preflight.mjs';

function crc32(bytes) {
  let crc=0xffffffff;
  for(const byte of bytes){
    crc^=byte;
    for(let bit=0;bit<8;bit++) crc=(crc>>>1) ^ ((crc&1)?0xedb88320:0);
  }
  return (crc^0xffffffff)>>>0;
}

test('real attachment probe is a decodable PNG with valid chunk CRCs',async()=>{
  const root=await mkdtemp(join(tmpdir(),'kgxc-preflight-test-'));
  const config={provider:'fixture',model:'fixture'};
  try {
    const receipt=await probeReviewer({get:()=>({saveImage:async({data,mediaType})=>{
      assert.equal(mediaType,'image/png');
      assert.equal(data.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
      const chunks=[];
      for(let i=8;i<data.length;){
        const n=data.readUInt32BE(i),name=data.toString('ascii',i+4,i+8),end=i+8+n;
        assert.equal(data.readUInt32BE(end),crc32(data.subarray(i+4,end)),name);
        chunks.push([name,data.subarray(i+8,end)]);i=end+4;
      }
      assert.deepEqual(chunks.map(c=>c[0]),['IHDR','IDAT','IEND']);
      assert.deepEqual([...inflateSync(chunks[1][1])],[0,32,88,160,255]);
      return 'fixture';
    }}),selection:config,prepared:{config},packet:{run_id:'test',checklist:[{id:'frames',required_method:'frames',critical:true}]},course_path:root});
    assert.equal(receipt.ready,true);
  } finally {await rm(root,{recursive:true,force:true});}
});
