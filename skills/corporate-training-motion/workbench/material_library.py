"""Read-only uploaded-file inventory. Source treatment is not video usage."""
from functools import lru_cache
import math
from pathlib import Path
import re

from workflow import read, sha

IMAGES={'.png','.jpg','.jpeg','.webp','.gif','.tif','.tiff','.bmp'}
DIGEST=re.compile(r'[a-f0-9]{64}')


def objects(value):
    return (v for v in value if isinstance(v,dict)) if isinstance(value,list) else ()


@lru_cache(maxsize=256)
def _hash(path, device, inode, size, mtime, ctime):
    return sha(Path(path))


def owned(course, path):
    try:
        value=course.relative(path)
        if value.is_file():
            info=value.stat()
            return _hash(str(value),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _read_object(path):
    try:
        value=read(path,{})
        return value if isinstance(value,dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def library(course, sources, artifacts, coverage):
    """Display only files already admitted to the course and receipt-backed use."""
    current={}
    for stage in ('pilot','final'):
        for a in objects(artifacts.get(stage)):
            digest=a.get('sha256')
            path=a.get('path')
            if isinstance(path,str) and path.lower().endswith('.mp4') and a.get('available') and isinstance(digest,str) and DIGEST.fullmatch(digest):
                current[(stage,path,digest)] = a.get('duration_seconds')
    report=coverage.get('report') or {}
    points={}
    if coverage.get('current') and isinstance(report,dict):
        for p in objects(report.get('points')):
            sid=p.get('source_id')
            if isinstance(sid,str):
                points.setdefault(sid,[]).append({key:p.get(key) for key in ('id','disposition','locator','reason')})
    inventory=_read_object(course.project/'source_images.json')
    receipt=_read_object(course.project/'material-video-usage.json')
    receipts=list(objects(receipt.get('materials'))) if receipt.get('schema')=='material-video-usage/1' else []
    result=[]
    for src in objects(sources):
        sid=src.get('id')
        path=src.get('location')
        if not isinstance(sid,str) or not isinstance(path,str) or src.get('kind','file')!='file':
            continue
        try:course.relative(path)
        except (OSError,ValueError,TypeError):continue
        digest=owned(course,path)
        image=Path(path).suffix.lower() in IMAGES
        status='unverified';reason='尚未核对实际成片中的使用情况' if image else '原件对照记录的是内容取舍，不代表原文件出现在视频中'
        if not digest:reason='原件文件暂不可读，未验证使用情况'
        placements=[];seen=set();excluded=None
        if digest:
            for row in receipts:
                if row.get('source_id')!=sid or row.get('source_sha256')!=digest:
                    continue
                for r in objects(row.get('placements')):
                    stage,media_path,media_sha=(r.get(k) for k in ('stage','artifact_path','artifact_sha256'))
                    if not all(isinstance(v,str) for v in (stage,media_path,media_sha)):
                        continue
                    duration=current.get((stage,media_path,media_sha))
                    start,end=(r.get(k) for k in ('start_seconds','end_seconds'))
                    if (r.get('method')!='encoded-video-viewing' or not isinstance(r.get('evidence'),str) or not r['evidence'].strip()
                            or type(duration) not in (int,float) or not math.isfinite(duration)
                            or type(start) not in (int,float) or type(end) not in (int,float) or not math.isfinite(start) or not math.isfinite(end)
                            or not 0<=start<end<=duration):
                        continue
                    key=(stage,media_path,media_sha,start,end)
                    if key not in seen:
                        seen.add(key)
                        placements.append(dict(stage=stage,artifact_path=media_path,artifact_sha256=media_sha,start_seconds=start,end_seconds=end,segment_label=(r.get('segment_label') or '').strip()[:120] if isinstance(r.get('segment_label'),str) and r['segment_label'].strip() else Path(media_path).name))
                if row.get('status')=='excluded' and isinstance(row.get('reason'),str) and row['reason'].strip():
                    excluded=row['reason'].strip()
            planned=False
            if image and inventory.get('review_status')=='reviewed':
                for item in objects(inventory.get('images')):
                    asset=item.get('asset_path')
                    if (item.get('source_id')!=sid and asset!=path) or item.get('sha256')!=digest:
                        continue
                    if item.get('decision')=='include' and item.get('scene_ids'):
                        planned=True
                    if item.get('decision')=='exclude' and isinstance(item.get('exclusion_reason'),str) and item['exclusion_reason'].strip():
                        excluded=item['exclusion_reason'].strip()
            if placements:status,reason='used','已按当前视频版本核对实际画面'
            elif excluded:status,reason='unused',excluded
            elif planned:reason='已在分镜登记，尚未核对实际成片'
        title=src.get('title')
        result.append(dict(id=sid,source_id=sid,title=title if isinstance(title,str) and title else Path(path).name,path=path,
                           kind='image' if image else 'file',available=bool(digest),status=status,reason=reason,placements=placements,
                           source_points=points.get(sid,[])))
    return result
