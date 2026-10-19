#!/usr/bin/env python3
"""Read-only approval receipt/hash check. Never grants approval or starts work."""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = {
    'script': ['source'],
    'visual': ['source', 'content'],
    'pilot': ['source', 'content', 'visual', 'voice'],
    'full': ['source', 'content', 'visual', 'voice', 'pilot'],
    'release': ['source', 'content', 'visual', 'voice', 'pilot', 'final'],
}

def check(folder, next_step):
    folder = Path(folder).resolve()
    errors = []
    boundary = folder.parent if (folder.parent/'workspace.json').is_file() and folder.name=='project' else folder
    try:
        records = json.loads((folder / 'approval_records.json').read_text())
        if not isinstance(records, dict):
            raise ValueError('approval records must be an object')
    except (OSError, ValueError) as exc:
        return [f'APPROVAL_RECORDS: {exc}']
    for stage in REQUIRED[next_step]:
        item = records.get(stage)
        if not isinstance(item, dict) or item.get('status') != 'approved':
            errors.append(f'APPROVAL_MISSING: {stage}')
            continue
        for key in ('reviewer', 'confirmed_at', 'user_confirmation'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f'APPROVAL_EVIDENCE: {stage}.{key}')
        artifacts = item.get('artifacts')
        if not isinstance(artifacts, dict) or not artifacts:
            errors.append(f'APPROVAL_ARTIFACTS: {stage}')
            continue
        for name, expected in artifacts.items():
            target = (folder / name).resolve()
            if Path(name).is_absolute() or not target.is_relative_to(boundary):
                errors.append(f'APPROVAL_PATH: {stage}/{name}')
                continue
            if not target.is_file():
                errors.append(f'APPROVAL_FILE: {stage}/{name}')
            elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                errors.append(f'APPROVAL_STALE: {stage}/{name}')
    return errors

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder', type=Path)
    ap.add_argument('--next', required=True, choices=REQUIRED)
    args = ap.parse_args()
    errors = check(args.folder, args.next)
    print(json.dumps({'ok': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
