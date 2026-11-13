#!/usr/bin/env python3
"""Offline package integrity/references check; no installation or global changes."""
import argparse,hashlib,json,re
from pathlib import Path

def check(root):
    root=Path(root).resolve();errors=[];files=[p for p in root.rglob('*') if p.is_file()]
    for p in files:
        rel=p.relative_to(root)
        if p.is_symlink():errors.append('Symlink: '+str(rel))
        if any(x in {'__pycache__','node_modules','.git','inputs','logs','work','.aws','.codex'} for x in rel.parts) or p.suffix in {'.pyc','.pdf','.docx','.key','.pem','.log'} or p.name in {'.env','.DS_Store'}:errors.append('Excluded private/cache item: '+str(rel))
        if p.suffix in {'.md','.py','.json','.js','.tsx','.yaml'}:
            text=p.read_text()
            if re.search(r'/Users/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\[A-Za-z0-9_.-]+\\',text):errors.append('Machine absolute path: '+str(rel))
            if re.search(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',text):errors.append('Credential-like value: '+str(rel))
        if p.suffix=='.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
                if '://' in target or target.startswith('#'):continue
                target=target.split('#')[0]
                if target and not (p.parent/target).exists():errors.append('Broken link: '+str(rel)+' -> '+target)
    manifest=root/'package-manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text());listed=data['files']
        actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p!=manifest}
        if listed!=actual:errors.append('Package manifest file set or hashes differ')
    else:errors.append('Package manifest missing')
    for p in root.glob('assets/profiles/*/profile.json'):
        data=json.loads(p.read_text())
        for a in data['assets'].values():
            f=p.parent/a['path']
            if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=a['sha256']:errors.append('Profile asset missing/changed: '+a['path'])
    return {'ok':not errors,'files':len(files),'errors':errors,'scope':'offline integrity, references and bounded credential-pattern scan; no blanket legal or secret certification'}

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('root',type=Path);args=a.parse_args();r=check(args.root);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(not r['ok'])
