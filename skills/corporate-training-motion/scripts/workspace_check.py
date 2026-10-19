#!/usr/bin/env python3
"""Read-only checks for separated course folders; never deletes files."""
from pathlib import Path
import argparse,hashlib,json,re

def check(root):
 root=Path(root).expanduser().resolve();errors=[]
 try:w=json.loads((root/'workspace.json').read_text())
 except (OSError,ValueError) as e:return {'ok':False,'errors':['workspace.json: '+str(e)]}
 expected={'README.md','workspace.json','inputs','project','delivery','packages'}
 errors += ['Unexpected course-root entry: '+p.name for p in root.iterdir() if p.name not in expected and p.name!='.DS_Store']
 for d in ['inputs','project','delivery','packages']:
  if not (root/d).is_dir():errors.append('Missing directory: '+d)
 for p in root.rglob('*'):
  if p.is_symlink() and (not p.exists() or not p.resolve().is_relative_to(root)):errors.append('Broken or escaping symlink: '+str(p.relative_to(root)))
  if p.is_dir() and p.parent==root and re.search(r'(?:^|[-_])v\d+',p.name):errors.append('Historical version folder: '+p.name)
 artifacts=w.get('retain_artifacts',[])
 for a in artifacts:
  name=a.get('path','');p=(root/name).resolve()
  if not name or Path(name).is_absolute() or not p.is_relative_to(root):errors.append('Unsafe artifact path: '+name);continue
  if not p.is_file():errors.append('Missing retained artifact: '+name)
  elif hashlib.sha256(p.read_bytes()).hexdigest()!=a.get('sha256'):errors.append('Retained hash mismatch: '+name)
 videos=list((root/'delivery').glob('*.mp4'));packages=list((root/'packages').glob('*.zip'))
 if len(videos)>1:errors.append('More than one current course MP4')
 if len(packages)>1:errors.append('More than one current editable ZIP')
 return {'ok':not errors,'errors':errors,'frozen_artifacts_checked':len(artifacts),'current_videos':len(videos),'current_packages':len(packages),'layout_version':w.get('layout_version'),'stage':'template' if not videos else 'delivery'}
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('course',type=Path);r=check(a.parse_args().course);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(not r['ok'])
