#!/usr/bin/env python3
"""Build distributable artifacts from the bounded publication repository."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from check_readme import ReadmeStructureError, check_readme

ROOT=Path(__file__).resolve().parents[1]
NAME='corporate-training-motion'
PUBLIC_CONFIG={'tools.example.json','voice-model.json','azure.example.json','package.json','package-lock.json'}


def excluded(path):
    rel=path.relative_to(ROOT)
    return (any(part.startswith('.') or part in {'__pycache__','node_modules','inputs','courses','work','logs','reviews','private'} for part in rel.parts)
            or path.suffix in {'.pyc','.pem','.key','.log','.pdf','.docx'}
            or any(parent.is_symlink() for parent in [path,*path.parents] if parent != ROOT and parent.is_relative_to(ROOT)))


def main():
    try:
        check_readme(ROOT/'README.md')
    except (ReadmeStructureError, OSError, UnicodeError) as error:
        print(f'打包已阻止：{ROOT / "README.md"}: {error}',file=sys.stderr)
        return 1
    version=(ROOT/'VERSION').read_text().strip()
    for name in [NAME,'elearning-course-design']:
        skill=ROOT/'skills'/name;manifest=skill/'package-manifest.json'
        files={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(skill.rglob('*')) if p.is_file() and p!=manifest and not excluded(p)}
        manifest.write_text(json.dumps(dict(name=name,version=version if name==NAME else '2.0.6',usage='KGXC course production suite',files=files),ensure_ascii=False,indent=2)+'\n')
        subprocess.run([sys.executable,str(ROOT/'skills'/NAME/'scripts/check_skill_package.py'),str(skill)],check=True)
    out=ROOT/'dist';out.mkdir(exist_ok=True);archive=out/f'kgxc-course-suite-v{version}.zip'
    candidates=[]
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if not p.is_file() or rel.parts[0] not in ['skills','scripts','config','docs'] and len(rel.parts)!=1:continue
        if rel.parts[0] in ['dist','.git','tests'] or excluded(p):continue
        if rel.parts[0]=='config' and (len(rel.parts)!=2 or p.name not in PUBLIC_CONFIG):continue
        if rel.as_posix() in ['scripts/build_plugin.py','scripts/install_plugin.py','scripts/check_codex_plugin.py','scripts/build_native_client.py']:continue
        if len(rel.parts)==1 and p.name not in ['install.sh','VERSION','release.json','README.md','THIRD_PARTY_NOTICES.md','requirements.in','requirements.lock','requirements-voice.in','requirements-voice.lock','安装或更新.command']:continue
        candidates.append(p)
    bundle_manifest=dict(version=version,files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in candidates})
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(candidates):
            entry=zipfile.ZipInfo('kgxc-course-suite/'+str(p.relative_to(ROOT)))
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=(0o100755 if p.suffix in {'.sh','.command'} else 0o100644)<<16
            z.writestr(entry,p.read_bytes())
        entry=zipfile.ZipInfo('kgxc-course-suite/bundle-manifest.json')
        entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
        z.writestr(entry,json.dumps(bundle_manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC failed')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest();(out/'SHA256SUMS').write_text(digest+'  '+archive.name+'\n')
    print(json.dumps(dict(version=version,files=len(candidates)+1,zip=archive.name,bytes=archive.stat().st_size,sha256=digest),indent=2))


if __name__=='__main__':raise SystemExit(main())
