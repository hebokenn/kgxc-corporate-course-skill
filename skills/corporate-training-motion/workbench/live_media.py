"""Read-only index of explicitly saved course media, not a filesystem crawler.

Producers may atomically save work/live-media.json with {"items": [
 {"path": "media/line-01.wav", "kind": "audio", "label": "第一段配音",
  "segment_id": "S01", "sha256": "optional immutable file digest"}
]}. Files use the same project-relative paths as /course-file. The index also
includes storyboard preview_file, the document's bound narration and registered
video candidates. Availability is NOT approval, a finished render, or QA success.
"""
from pathlib import Path
import hashlib
import json
import time
import os
import uuid
from functools import lru_cache

KINDS={'.png':'image','.jpg':'image','.jpeg':'image','.webp':'image',
       '.wav':'audio','.mp3':'audio','.m4a':'audio','.ogg':'audio',
       '.mp4':'video','.webm':'video'}
MAX_ITEMS=80
MAX_MANIFEST=256*1024

def _read(path,limit=MAX_MANIFEST,root=None):
    try:
        if root is not None and not path.resolve().is_relative_to(Path(root).resolve()):return {}
        if path.stat().st_size>limit:return {}
        value=json.loads(path.read_text());return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def _signature(path):
    with path.open('rb') as file:head=file.read(32)
    suffix=path.suffix.lower()
    if suffix=='.png':return head.startswith(b'\x89PNG\r\n\x1a\n')
    if suffix in ('.jpg','.jpeg'):return head.startswith(b'\xff\xd8\xff')
    if suffix=='.webp':return head[:4]==b'RIFF' and head[8:12]==b'WEBP'
    if suffix=='.wav':return head[:4]==b'RIFF' and head[8:12]==b'WAVE'
    if suffix=='.mp3':return head.startswith(b'ID3') or len(head)>1 and head[0]==255 and head[1]&224==224
    if suffix=='.ogg':return head.startswith(b'OggS')
    if suffix in ('.mp4','.m4a'):return head[4:8]==b'ftyp'
    if suffix=='.webm':return head.startswith(b'\x1a\x45\xdf\xa3')
    return False

@lru_cache(maxsize=256)
def _verified_digest(path,mtime_ns,size,expected):
    # Metadata is part of the cache identity, not merely the pathname.
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file,'sha256').hexdigest()==expected


def index(space,now=None):
    from workflow import Course
    course=Course(space.root);project=course.project
    doc=_read(space.file,4*1024*1024,course.root);board=_read(project/'storyboard.json',root=course.root);state=_read(project/'course-state.json',root=course.root)
    manifest=_read(project/'work/live-media.json',root=course.root)
    requests=[]
    receipts=project/'work/live-media-receipts'
    if receipts.is_dir():
        for receipt in sorted(receipts.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:MAX_ITEMS]:
            entry=_read(receipt,root=course.root)
            if entry.get('path'):requests.append(dict(entry,source='saved_audio_receipt'))
    for item in manifest.get('items',[])[:MAX_ITEMS] if isinstance(manifest.get('items'),list) else []:
        if isinstance(item,dict):requests.append(dict(item,source='producer_manifest'))
    for segment in (board.get('segments') if isinstance(board.get('segments'),list) else [])[:200]:
        if not isinstance(segment,dict):continue
        for option in (segment.get('options') if isinstance(segment.get('options'),list) else [])[:3]:
            if isinstance(option,dict) and option.get('preview_file'):
                requests.append(dict(path=option['preview_file'],kind='image',label=segment.get('title') or '已保存画面',segment_id=segment.get('id'),source='storyboard',current=segment.get('selected')==option.get('id')))
    audio=(doc.get('media') if isinstance(doc.get('media'),dict) else {}).get('audio')
    if audio:requests.append(dict(path=audio,kind='audio',label='当前工程配音',source='document',current=True))
    for key in ['artifacts','candidate_artifacts']:
        for stage,paths in (state.get(key) if isinstance(state.get(key),dict) else {}).items():
            if stage not in ['pilot','final'] or not isinstance(paths,list):continue
            for path in paths[:20]:requests.append(dict(path=path,kind='video',label='已保存'+('小样' if stage=='pilot' else '成片候选'),source=key,current=None))
    exports=project/'work/workbench/exports'
    if exports.is_dir():
        for folder in sorted((f for f in exports.iterdir() if f.is_dir() and len(f.name)==12 and all(c in '0123456789abcdef' for c in f.name)),key=lambda f:f.stat().st_mtime,reverse=True)[:8]:
            preview=folder/'live-preview.jpg'
            if preview.is_file():requests.append(dict(path=str(preview.relative_to(project)),kind='image',label='已保存的合成画面',source='render_preview',current=None,_atomic=True))
    items={};clock=time.time() if now is None else now
    for request in requests:
        name=request.get('path')
        if not isinstance(name,str) or len(name)>1024 or '\x00' in name:continue
        try:
            path=course.relative(name)
            # Deny hidden paths, active temporary files, symlinks out of course,
            # unknown extensions and extension-disguised unrelated documents.
            if any(part.startswith('.') for part in path.relative_to(course.root).parts):continue
            kind=KINDS.get(path.suffix.lower())
            if not kind or request.get('kind',kind)!=kind or not path.is_file():continue
            stat=path.stat()
            if not stat.st_size or (clock-stat.st_mtime<.5 and not request.get('_atomic')) or not _signature(path):continue
            digest=request.get('sha256')
            if digest:
                if not isinstance(digest,str) or len(digest)!=64:continue
                if not _verified_digest(str(path),stat.st_mtime_ns,stat.st_size,digest):continue
            after=path.stat()
            if (stat.st_size,stat.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):continue
            canonical=Path(os.path.relpath(path,project)).as_posix()
            item=dict(id=hashlib.sha256(canonical.encode()).hexdigest()[:16],kind=kind,path=canonical,
                      label=str(request.get('label') or path.name)[:120],mtime=int(stat.st_mtime*1000),bytes=stat.st_size,
                      source=request['source'],status='saved',current=request.get('current'))
            if isinstance(request.get('segment_id'),str):item['segment_id']=request['segment_id'][:80]
            if digest:item['sha256']=digest
            items.setdefault(canonical,item)
        except (OSError,ValueError,TypeError):continue
    result=sorted(items.values(),key=lambda item:item['mtime'],reverse=True)[:MAX_ITEMS]
    return dict(items=result,updated_at=max((item['mtime'] for item in result),default=0),
                scope='saved_course_media',notice='已保存的制作产物，不代表小样完成或审阅通过。')


def publish_render_preview(directory,jpeg):
    """Publish only a fully captured JPEG, by atomic replacement; never a QA claim."""
    if not jpeg or not jpeg.startswith(b'\xff\xd8\xff'):return
    directory=Path(directory);pending=directory/'live-preview.pending'
    pending.write_bytes(jpeg);pending.replace(directory/'live-preview.jpg')


def publish_saved_audio(path,digest=None):
    """Called only after TTS and metadata writes succeed. No generic disk scan.

    Outside a recognized course project this is a no-op. Receipt publication is
    independent of content/listening review and never marks a stage approved.
    """
    path=Path(path).resolve()
    project=next((p for p in list(path.parents)[:8] if (p/'course-state.json').is_file()),None)
    if project is None or path.suffix.lower() not in KINDS or KINDS[path.suffix.lower()]!='audio':return False
    if not path.is_file() or not _signature(path):return False
    with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if digest and actual!=digest:return False
    name=path.relative_to(project).as_posix();directory=project/'work/live-media-receipts'
    if not directory.resolve().is_relative_to(project):return False
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(hashlib.sha256(name.encode()).hexdigest()[:24]+'.json')
    pending=target.with_suffix('.pending-'+uuid.uuid4().hex)
    value=dict(path=name,kind='audio',label=path.stem,sha256=actual,status='saved',current=None)
    try:pending.write_text(json.dumps(value,ensure_ascii=False));pending.replace(target)
    finally:
        if pending.exists():pending.unlink()
    return True
