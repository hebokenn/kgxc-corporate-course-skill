"""Course craft signals and evidence-bound aesthetic review, never a beauty score."""
import hashlib
import json
from pathlib import Path
import subprocess

CRITERIA=('composition','typography','colorMaterial','imagery','whitespace','visualRhythm')


def policy():
    return dict(schema='course-craft-policy/1',required=True,aestheticReview=True,coverRequired=True,
                voiceRequirements=['natural-training-tone','standard-mandarin','crisp-pacing','consistent-speaker'])


def _shape(node):
    if node.get('role')=='decoration':return None
    kind=node.get('type');result={'type':kind}
    for key in ['x','y','fontSize','scaleX','scaleY','rotation']:
        if isinstance(node.get(key),(int,float)):result[key]=round(node[key]/20)*20 if key in ['x','y'] else node[key]
    if kind!='text':
        for key in ['width','height']:
            if isinstance(node.get(key),(int,float)):result[key]=round(node[key]/20)*20
    children=[v for n in node.get('children',[]) if (v:=_shape(n)) is not None]
    if children:result['children']=children
    return result


def analyze(doc):
    """Flag repeated composition for an actual decision, without forcing novelty."""
    scenes=doc.get('scenes',[]);groups={};signatures=[]
    for scene in scenes:
        shape=[v for n in doc.get('sceneGraph',{}).get('nodes',[]) if n.get('sceneId')==scene['id'] and (v:=_shape(n)) is not None]
        digest=hashlib.sha256(json.dumps(shape,sort_keys=True).encode()).hexdigest() if shape else None
        signatures.append(digest)
        if digest:groups.setdefault(digest,[]).append(scene['id'])
    signals=[];start=0
    while start<len(scenes):
        end=start+1
        while end<len(scenes) and signatures[start] and signatures[end]==signatures[start]:end+=1
        if end-start>=3:signals.append(dict(kind='consecutive-composition',sceneIds=[s['id'] for s in scenes[start:end]],question='这些内容是否需要同一构图？如没有比较或操作连续性的理由，重新设计表现。'))
        start=end
    for ids in groups.values():
        if len(scenes)>=6 and len(ids)/len(scenes)>=.4:signals.append(dict(kind='dominant-composition',sceneIds=ids,question='该版式占整课较高比例；检查是否把不同内容套成同一模板。'))
    return dict(schema='course-craft-signals/1',status='review-required' if signals else 'pass',signals=signals,
                scope='composition similarity only; no automatic aesthetic approval and no action-count quota')


def review(project,doc,video,verify_pixels=True):
    p=Path(project).resolve();video=Path(video).resolve();marker=p/'craft-contract.json'
    required=marker.is_file() or doc.get('qualityPolicy',{}).get('required')
    if not required:return dict(status='legacy-not-opted-in',errors=[])
    from cover_quality import review as cover_review
    cover=cover_review(p,doc,video,verify_pixels=verify_pixels)
    errors=list(cover['errors'])
    if not doc.get('qualityPolicy',{}).get('required'):errors.append('本工程要求课程工艺复核，不能删除 qualityPolicy')
    path=p/'qa/craft-review.json'
    if not path.is_file():return dict(status='pending',errors=errors+['缺少独立审美与配音复核 qa/craft-review.json'])
    try:data=json.loads(path.read_text())
    except (OSError,ValueError):return dict(status='pending',errors=errors+['课程工艺复核不是有效 JSON'])
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    if data.get('schema')!='course-craft-review/1' or data.get('status')!='reviewed':errors.append('课程工艺复核未完成')
    if data.get('videoSha256')!=sha(video) or data.get('documentSha256')!=sha(p/'workbench.json'):errors.append('课程工艺复核绑定的是旧版本')
    if not data.get('reviewer') or not data.get('scope'):errors.append('须说明实际复核者、方法与听看范围')
    notes=data.get('aesthetics',{})
    for key in CRITERIA:
        if not isinstance(notes.get(key),str) or not notes[key].strip():errors.append('缺少独立审美观察 '+key)
    if len({str(notes.get(k,'')) for k in CRITERIA})!=len(CRITERIA):errors.append('不能用同一句自评替代六项实际审美观察')
    voice=data.get('voice',{})
    for key in ['naturalTone','standardMandarin','crispPacing','speakerContinuity','reviewScope']:
        if not isinstance(voice.get(key),str) or not voice[key].strip():errors.append('配音复核须说明实际依据 '+key)
    if data.get('unresolvedIssues'):errors.append('仍有未解决的课程工艺问题')
    decisions=data.get('compositionDecisions',[])
    for signal in analyze(doc)['signals']:
        if not any(set(signal['sceneIds']).issubset(set(d.get('sceneIds',[]))) and str(d.get('reason','')).strip() for d in decisions):
            errors.append('重复构图尚未作内容判断 '+','.join(signal['sceneIds']))
    frames=data.get('evidenceFrames',[]);thirds=set();body_start=doc.get('introFrames',0);body_end=doc.get('bodyEndFrame',doc['sourceDurationFrames'])
    from timeline import display_frame
    from PIL import Image
    for frame in frames:
        name=frame.get('path','');f=(p/name).resolve();source=frame.get('sourceFrame')
        if not name or Path(name).is_absolute() or not f.is_relative_to(p) or not f.is_file() or frame.get('sha256')!=sha(f):
            errors.append('审美证据文件不存在、越界或已变化');continue
        if type(source) is not int or not body_start<=source<body_end:errors.append('审美证据须位于实际课程正文');continue
        thirds.add(min(2,int((source-body_start)*3/max(1,body_end-body_start))))
        if not frame.get('observation'):errors.append('须说明该实际画面的审美观察')
        if frame.get('origin')!='encoded-video':errors.append('审美证据须从当前编码视频抽取')
        if verify_pixels:
            index=display_frame(source,doc.get('holds',[]),doc.get('cuts',[]))
            try:
                raw=subprocess.check_output(['ffmpeg','-v','error','-ss',f'{index/doc["fps"]:.9f}','-i',str(video),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],stderr=subprocess.STDOUT)
                with Image.open(f) as image:actual=image.convert('RGB').tobytes();size=image.size
                if size!=(doc['width'],doc['height']) or raw!=actual:errors.append('画面证据与当前视频真实像素不一致 '+name)
            except (OSError,subprocess.CalledProcessError):errors.append('无法核对编码画面 '+name)
    if thirds!={0,1,2}:errors.append('审美复核须覆盖整课早、中、晚段的实际编码画面')
    return dict(status='pending' if errors else 'pass',errors=errors,cover=cover,
                scope='bound aesthetic observations and voice evidence; no automatic beauty score or fabricated listening acceptance')
