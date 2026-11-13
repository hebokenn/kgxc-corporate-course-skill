"""Read back current formal files through the actual macOS Finder adapter."""
from pathlib import Path
import hashlib
import os
import stat
import subprocess
import sys

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare_visible(folder,outputs):
    """Only after a real release decision/copy; re-read flags after repairing them."""
    changed=[];hidden=getattr(stat,'UF_HIDDEN',0)
    for path in [Path(folder),*[Path(row['path']) for row in outputs]]:
        if path.name.startswith('.'):raise ValueError('DELIVERY_HIDDEN: formal names cannot begin with a dot')
        flags=getattr(path.stat(),'st_flags',0)
        if hidden and flags&hidden:
            if not hasattr(os,'chflags'):raise ValueError('DELIVERY_HIDDEN: cannot restore visibility')
            os.chflags(path,flags&~hidden)
            if getattr(path.stat(),'st_flags',0)&hidden:raise ValueError('DELIVERY_HIDDEN: flag remains set')
            changed.append(str(path))
    return dict(method='filesystem flags repair and actual stat readback',changed=changed)

def verify_finder_files(folder,outputs):
    """Actual Finder readback, separate from filesystem SHA and browser poster."""
    folder=Path(folder)
    hidden=getattr(stat,'UF_HIDDEN',0)
    if folder.name.startswith('.') or getattr(folder.stat(),'st_flags',0)&hidden:raise ValueError('DELIVERY_HIDDEN: course folder')
    for item in outputs:
        path=Path(item['path'])
        if path.name.startswith('.') or getattr(path.stat(),'st_flags',0)&hidden or not path.is_file() or digest(path)!=item['sha256']:
            raise ValueError('DELIVERY_COPY_MISMATCH: missing, hidden or changed target')
    if sys.platform!='darwin':raise ValueError('FINDER_READBACK_UNVERIFIED: this host has no Finder adapter')
    script='on run argv\nset targetFolder to POSIX file (item 1 of argv) as alias\ntell application "Finder"\nset fileNames to name of every file of targetFolder\nend tell\nset AppleScript\'s text item delimiters to linefeed\nreturn fileNames as text\nend run'
    result=subprocess.run(['osascript','-e',script,str(folder)],capture_output=True,text=True,timeout=30)
    if result.returncode or not {Path(f['path']).name for f in outputs}<=set(result.stdout.strip().splitlines()):
        raise ValueError('FINDER_READBACK_UNVERIFIED: actual Finder file listing unavailable or incomplete')
    return dict(method='Finder AppleScript file listing',folder=str(folder),files=[f['path'] for f in outputs],status='verified')

