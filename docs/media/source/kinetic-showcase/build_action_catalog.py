#!/usr/bin/env python3
"""Package an audited, offline action index without accessing other files."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--atlas-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
root=a.atlas_root.resolve()
proof=(root/'manifest.json').read_bytes()
data=json.loads(proof)
actions=data['actions']
assert data['status']=='complete' and len(actions)==data['actualRuntimeCount']==100
assert len({x['id'] for x in actions})==100 and len({x['sha256'] for x in actions})==100
assert [x['ordinal'] for x in actions]==list(range(1,101))
bundle={'index.html':Path(__file__).with_name('action-catalog.html').read_bytes(),
        'manifest.json':proof,'打开方式.txt':'完整解压，然后在浏览器打开 index.html。无需联网。\n'.encode()}
short=[]
for x in actions:
    assert re.fullmatch(r'[a-z][a-z\d-]*',x['id'])
    path=f"actions/{x['id']}.jpg"
    assert x['path']==path and x['distinctReducedFrames']>1 and x['activeRuntimeReceipts']>0
    item=(root/path).read_bytes()
    assert hashlib.sha256(item).hexdigest()==x['sha256'] and item[:2]==b'\xff\xd8'
    bundle[path]=item
    short.append({k:x[k] for k in ('id','title','task','observe','ordinal','category','path')})
bundle['catalog-data.js']=('window.kgxcCatalog = '+json.dumps(short,ensure_ascii=False,separators=(',',':'))+';\n').encode()
a.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,value in sorted(bundle.items()):
        entry=zipfile.ZipInfo('kgxc-motion-actions/'+name)
        entry.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(entry,value)
with zipfile.ZipFile(a.output) as z:
    assert len(z.namelist())==104 and not z.testzip()
print('100/100 verified motion atlases and offline viewer:',a.output)
