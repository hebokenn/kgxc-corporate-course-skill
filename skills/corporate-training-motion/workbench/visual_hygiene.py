"""Bind per-scene alignment, connector and residue review to encoded pictures."""
import hashlib
import json
from pathlib import Path
import subprocess


def review(project,doc,video,verify_pixels=True):
    p=Path(project).resolve();video=Path(video).resolve();path=p/'qa/visual-hygiene-review.json'
    marker=p/'craft-contract.json'
    try:contract=json.loads(marker.read_text()) if marker.is_file() else {};marked=contract.get('visualHygieneRequired');spatial=bool(contract.get('spatialReviewRequired') or doc.get('qualityPolicy',{}).get('spatialReviewRequired'))
    except (OSError,ValueError):return dict(status='pending',errors=['视觉复核契约不是有效JSON'])
    if not (doc.get('qualityPolicy',{}).get('visualHygieneRequired') or marked):
        return dict(status='legacy-not-opted-in',errors=[])
    errors=[]
    if marked and not doc.get('qualityPolicy',{}).get('visualHygieneRequired'):
        errors.append('本工程要求逐场视觉检查，不能删除 visualHygieneRequired')
    if contract.get('spatialReviewRequired') and not doc.get('qualityPolicy',{}).get('spatialReviewRequired'):errors.append('本工程要求支撑关系和文字避让检查，不能删除 spatialReviewRequired')
    if not path.is_file():return dict(status='pending',errors=['缺少逐场视觉检查 qa/visual-hygiene-review.json'])
    try:data=json.loads(path.read_text())
    except (OSError,ValueError):return dict(status='pending',errors=['逐场视觉检查不是有效 JSON'])
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    if data.get('schema')!='course-visual-hygiene-review/1' or data.get('status')!='reviewed':errors.append('逐场视觉检查未完成')
    if data.get('videoSha256')!=sha(video) or data.get('documentSha256')!=sha(p/'workbench.json'):errors.append('逐场视觉检查绑定的是旧视频或旧工程')
    if not data.get('reviewer') or not data.get('scope'):errors.append('须说明实际复核方法与覆盖范围')
    if data.get('unresolvedIssues'):errors.append('仍有未解决的对齐、连接或动画残留问题')
    scenes={s['id'] for s in doc.get('scenes',[])};rows=data.get('sceneReviews',[])
    if not isinstance(rows,list):rows=[];errors.append('sceneReviews须为逐场列表')
    identifiers=[r.get('sceneId') for r in rows if isinstance(r,dict)]
    if len(identifiers)!=len(set(identifiers)) or set(identifiers)!=scenes:errors.append('逐场视觉检查须覆盖当前全部场景且不能重复或混入其他场景')
    from PIL import Image
    for row in rows:
        if not isinstance(row,dict):errors.append('场景检查条目无效');continue
        scene=row.get('sceneId','')
        for key in ['alignment','connectors','animationResidue']+(['physicalSupport','typography'] if spatial else []):
            if not isinstance(row.get(key),str) or not row[key].strip():errors.append('缺少实际观察 '+scene+' '+key)
        frames=row.get('evidenceFrames',[])
        if not isinstance(frames,list) or not frames:errors.append('缺少当前编码画面 '+scene);continue
        for frame in frames:
            name=frame.get('path','');f=(p/name).resolve();index=frame.get('encodedFrame')
            if not name or Path(name).is_absolute() or not f.is_relative_to(p) or not f.is_file() or frame.get('sha256')!=sha(f):
                errors.append('逐场画面证据不存在、越界或已改变 '+scene);continue
            if type(index) is not int or index<0 or frame.get('origin')!='encoded-video' or not frame.get('observation'):
                errors.append('逐场证据须有真实编码帧号、来源和观察 '+scene);continue
            if verify_pixels:
                try:
                    # Seek just before the requested CFR frame to avoid decimal rounding skipping it.
                    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',f'{max(0,(index-.1)/doc["fps"]):.9f}',
                        '-i',str(video),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],stderr=subprocess.STDOUT)
                    with Image.open(f) as image:actual=image.convert('RGB').tobytes();size=image.size
                    if size!=(doc['width'],doc['height']) or raw!=actual:errors.append('逐场证据与当前视频真实像素不一致 '+scene)
                except (OSError,subprocess.CalledProcessError):errors.append('无法核对编码画面 '+scene)
    return dict(status='pending' if errors else 'pass',errors=errors,scenes=len(scenes),
        scope='Per-scene evidence completeness and current pixels, not automatic aesthetic judgment or user acceptance')
