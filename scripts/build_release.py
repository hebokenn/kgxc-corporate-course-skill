#!/usr/bin/env python3
"""Build distributable artifacts from the bounded publication repository."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='corporate-training-motion'


def main():
    skill=ROOT/'skills'/NAME;version=(ROOT/'VERSION').read_text().strip();manifest=skill/'package-manifest.json'
    files={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(skill.rglob('*')) if p.is_file() and p!=manifest}
    manifest.write_text(json.dumps(dict(name=NAME,version=version,usage='KGXC internal training; public distribution authorized',files=files),ensure_ascii=False,indent=2)+'\n')
    subprocess.run([sys.executable,str(skill/'scripts/check_skill_package.py'),str(skill)],check=True)
    out=ROOT/'dist';out.mkdir(exist_ok=True);archive=out/f'{NAME}-v{version}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(skill.rglob('*')):
            if p.is_file():z.write(p,NAME+'/'+str(p.relative_to(skill)))
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC failed')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(digest+'  '+archive.name+'\n')
    print(json.dumps(dict(version=version,files=len(files)+1,zip=archive.name,bytes=archive.stat().st_size,sha256=digest),indent=2))


if __name__=='__main__':main()
