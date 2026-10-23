"""Block unimplemented actions and uncovered narration; audit the encoded subject.

This is evidence for director review, not an automated aesthetic score. Intentional
reading/thinking is represented explicitly. Existing frozen documents opt in only
when the user requests a visual revision; installing a Skill never rewrites them.
"""
import hashlib
import json
from pathlib import Path
import subprocess

SCHEMA='course-motion-plan/1'


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n.get('children',[]))


def library_digest(root=None):
    root=Path(root) if root else Path(__file__).resolve().parent
    h=hashlib.sha256()
    for name in ['motion/effects.js','motion/teaching-effects.js','motion/retail-effects.js','motion/surface-materials.js','motion/m1-mesh.js','teaching_modules.py','motion_catalog.py','starter/scene-engine.js']:
        h.update(name.encode());h.update((root/name).read_bytes())
    return h.hexdigest()


def policy():
    return dict(schema='course-motion-policy/1',required=True,librarySha256=library_digest(),
                longStaticWarningSeconds=8,semanticRequired=True,acceptance='technical evidence plus continuous visual review; user acceptance separate')


def runtime_digest(project,doc):
    """Bind approval to loaded motion code, rather than a user-editable label."""
    p=Path(project);files=doc.get('motionPolicy',{}).get('implementationFiles')
    if files is None:files=['native/scene-engine.js']+[str(f.relative_to(p)) for f in sorted((p/'native/motion').rglob('*.js'))]
    h=hashlib.sha256()
    for name in files:
        f=(p/name).resolve()
        if Path(name).is_absolute() or not f.is_relative_to(p.resolve()) or not f.is_file():raise ValueError('动效基准源码缺失或越界 '+name)
        h.update(name.encode());h.update(f.read_bytes())
    if not files:raise ValueError('动效基准不能只有风格名称，须绑定实际实现文件')
    return h.hexdigest()


def intervals_subtract(interval,covered):
    pieces=[interval]
    for x,y in sorted(covered):
        next_pieces=[]
        for a,b in pieces:
            if y<=a or x>=b:next_pieces.append((a,b));continue
            if a<x:next_pieces.append((a,x))
            if y<b:next_pieces.append((y,b))
        pieces=next_pieces
    return pieces


def preflight(doc):
    enabled=bool(doc.get('motionPolicy',{}).get('required'))
    plan=doc.get('motionPlan',{});errors=[]
    if not enabled and not plan:return dict(status='legacy-not-opted-in',errors=[],scope='frozen course left unchanged')
    if plan.get('schema')!=SCHEMA:return dict(status='fail',errors=['缺少逐段动作计划 motionPlan；不能用效果名称或短小样代替整课编排'])
    if not plan.get('language'):errors.append('缺少本课动作编排标识；它不限制可组合的动作类型')
    nodes={n['id']:n for n in walk(doc.get('sceneGraph',{}).get('nodes',[]))}
    scenes={s['id']:s for s in doc.get('scenes',[])};beats=plan.get('beats',[]);ids=set();coverage=[];actions=[]
    native=doc.get('rendering',{}).get('route')=='native-canvas'
    for b in beats:
        bid=b.get('id');a,z=b.get('startFrame'),b.get('endFrame');scene=scenes.get(b.get('sceneId'))
        if not bid or bid in ids:errors.append('动作节拍ID缺失或重复');continue
        ids.add(bid)
        if not scene or type(a) is not int or type(z) is not int or not scene['sourceStartFrame']<=a<z<=scene['sourceEndFrame']:
            errors.append('节拍越界或缺少真实场景 '+str(bid));continue
        kind=b.get('kind','action')
        if kind in ['read','think','observe']:
            if not str(b.get('reason','')).strip():errors.append('静止停留须说明学员需要看或想什么 '+bid)
            coverage.append((a,z));continue
        if kind!='action':errors.append('未知节拍类型 '+str(kind));continue
        if not all(str(b.get(k,'')).strip() for k in ['purpose','before','after']):errors.append('动作须说明用途、起态与结果 '+bid)
        objects=b.get('objectIds',[])
        if not objects:errors.append('动作没有绑定实际对象 '+bid)
        effect_intervals=[]
        for object_id in objects:
            n=nodes.get(object_id)
            if n is None:
                if not native:errors.append('动作引用不存在的实际对象 '+str(object_id))
                continue
            if n.get('role')=='decoration':errors.append('标题/装饰不能充当教学主体动作 '+bid)
            for e in n.get('effects',[]):
                if max(a,e['startFrame'])<min(z,e['endFrame']):effect_intervals.append((e['startFrame'],e['endFrame']))
            for e in n.get('motion',[]):
                if e.get('from')!=e.get('to') and max(a,e['startFrame'])<min(z,e['endFrame']):effect_intervals.append((e['startFrame'],e['endFrame']))
        if native:
            proof=b.get('implementation',{})
            if not proof.get('source') or not proof.get('function'):errors.append('原生路线须登记真实源码/函数及运行回执 '+bid)
            else:effect_intervals.append((a,z))
        if not effect_intervals:errors.append('只声明动作但没有实际运动实现 '+bid)
        uncovered=intervals_subtract((a,z),effect_intervals)
        if any(y-x>1 for x,y in uncovered):errors.append('动作窗口长于实际动作；请补齐过程或明确读图停留 '+bid)
        actions.append(b);coverage.extend((max(a,x),min(z,y)) for x,y in effect_intervals if max(a,x)<min(z,y))
    if not actions:errors.append('没有实际教学主体动作')
    for cue in ([] if doc.get('motionPolicy',{}).get('semanticRequired') else doc.get('captions',[])):
        from timeline import segments
        spans=segments(dict(doc,holds=doc.get('holds',[])))
        source_ranges=[]
        for span in spans:
            a=max(cue['startFrame'],span['startFrame']);z=min(cue['endFrame'],span['endFrame'])
            if a>=z or span['kind']=='hold':continue
            x=span['sourceFrame']+a-span['startFrame'];y=x+z-a
            if y<=doc.get('introFrames',0) or x>=doc.get('bodyEndFrame',doc['sourceDurationFrames']):continue
            source_ranges.append((x,y))
        missing=[piece for span in source_ranges for piece in intervals_subtract(span,coverage)]
        if any(z-a>1 for a,z in missing):errors.append('旁白缺少对应动作或有理由的停留 '+cue['id'])
    protected=set(plan.get('protectedEffects',[]));actual={e['type'] for n in nodes.values() for e in n.get('effects',[])}
    if protected-actual:errors.append('明确保留的核心动作在整课中缺失 '+', '.join(sorted(protected-actual)))
    from semantic_motion import inspect as inspect_semantics
    semantic=inspect_semantics(doc,nodes);errors.extend(semantic['errors'])
    from craft_quality import analyze
    return dict(status='fail' if errors else 'pass',errors=errors,actions=len(actions),beats=len(beats),semantic=semantic,craft=analyze(doc),
                actualEffects=sorted(actual),librarySha256=doc.get('motionPolicy',{}).get('librarySha256'),
                scope='implementation and narration coverage; encoded motion and visual review still required')


def require(doc,project=None):
    if project and (Path(project)/'craft-contract.json').is_file() and not doc.get('qualityPolicy',{}).get('required'):
        raise ValueError('本工程要求独立审美与声音复核，不能删除 qualityPolicy')
    if project and (Path(project)/'motion-contract.json').is_file() and not doc.get('motionPolicy',{}).get('required'):
        raise ValueError('本工程要求逐段动效检查；不能删除 motionPolicy 绕过检查')
    if project and (Path(project)/'motion-contract.json').is_file():
        marker=json.loads((Path(project)/'motion-contract.json').read_text())
        if marker.get('semanticRequired') and not doc.get('motionPolicy',{}).get('semanticRequired'):
            raise ValueError('本工程要求口播与对象状态对应；不能删除 semanticRequired 绕过检查')
    report=preflight(doc)
    if report['status']=='fail':raise ValueError('整课动效检查未通过：'+'; '.join(report['errors'][:16]))
    return report


def director_review(project,doc,video):
    """A generated MP4 is a candidate until a bound per-section review exists."""
    p=Path(project);video=Path(video)
    if (p/'motion-contract.json').is_file() and not doc.get('motionPolicy',{}).get('required'):
        return dict(status='pending',errors=['本工程缺少必需的逐段动效策略，不能登记为旧工程完成'])
    if not doc.get('motionPolicy',{}).get('required'):return dict(status='legacy-not-opted-in',errors=[])
    try:require(doc,p)
    except ValueError as exc:return dict(status='pending',errors=[str(exc)])
    f=p/'qa/director-review.json'
    if not f.is_file():return dict(status='pending',errors=['缺少绑定当前成片的逐段导演复核 qa/director-review.json'])
    review=json.loads(f.read_text());errors=[]
    sha=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
    if review.get('schema')!='course-director-review/1' or review.get('status')!='reviewed':errors.append('导演复核未完成')
    if review.get('videoSha256')!=sha(video) or review.get('documentSha256')!=sha(p/'workbench.json'):errors.append('导演复核绑定的是旧版本')
    if not review.get('reviewer') or not review.get('scope'):errors.append('未说明真实复核者与检查范围')
    if not str(review.get('pilotComparison','')).strip():errors.append('缺少批准小样与全片的画面、动作和节奏比较')
    if doc.get('motionPolicy',{}).get('semanticRequired'):
        playback=review.get('continuousPlayback',{})
        if playback.get('speed')!=1 or not playback.get('reviewedRanges') or not playback.get('method'):
            errors.append('缺少正常速度连续复看的实际范围与方法；关键帧和技术计数不能代替连续检查')
    sections={s.get('sceneId'):s for s in review.get('sections',[])}
    for s in doc['scenes']:
        item=sections.get(s['id'])
        if not item:errors.append('未逐段复核 '+s['id']);continue
        if item.get('status')!='reviewed' or item.get('unresolvedIssues') or not all(item.get(k) for k in ['observedAction','narrationAlignment','visualContinuity']):errors.append('导演复核仍有未解决项 '+s['id'])
        if doc.get('motionPolicy',{}).get('semanticRequired') and not all(item.get(k) for k in ['semanticFit','pacingObservation','resultOrFeedback']):
            errors.append('须复核动作用途是否合适、正常速度节奏、结果或反馈 '+s['id'])
        frames=item.get('evidenceFrames',[])
        if not frames:errors.append('缺少本段实际编码画面证据 '+s['id'])
        for frame in frames:
            name=frame.get('path','');path=(p/name).resolve()
            if not name or Path(name).is_absolute() or not path.is_relative_to(p.resolve()) or not path.is_file() or frame.get('sha256')!=sha(path):errors.append('复核画面缺失或过期 '+s['id'])
            if type(frame.get('sourceFrame')) is not int or not s['sourceStartFrame']<=frame['sourceFrame']<s['sourceEndFrame']:errors.append('复核画面不属于当前场景 '+s['id'])
    from craft_quality import review as craft_review
    craft=craft_review(p,doc,video);errors.extend(craft['errors'])
    return dict(status='pass' if not errors else 'pending',errors=errors,craft=craft,scope='bound director evidence; human listening and user acceptance separate')


def audit_encoded(video,doc,first,last):
    """Decode actual delivered pixels, excluding headers, captions and cross-cuts."""
    import numpy as np
    if not doc.get('motionPolicy',{}).get('required') and not doc.get('motionPlan'):
        return dict(status='legacy-not-opted-in')
    fps=doc.get('fps',30);w,h=424,160;duration=(last-first)/fps
    cmd=['ffmpeg','-v','error','-ss',str(first/fps),'-i',str(video),'-t',str(duration),
         '-vf',f'fps=2,crop=1696:640:112:270,scale={w}:{h},format=gray','-f','rawvideo','-']
    # Exported video begins at zero, independently of the source timeline.
    cmd[4]='0'
    raw=subprocess.check_output(cmd);frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w)
    times=first/fps+(np.arange(len(frames))+.5)/2
    from timeline import source_frame,segments
    source_times=np.array([source_frame(round(t*fps),doc.get('holds',[]),doc.get('cuts',[]))/fps for t in times])
    changes=[]
    for i in range(1,len(frames)):
        delta=np.abs(frames[i].astype(np.int16)-frames[i-1].astype(np.int16))
        changes.append(bool((delta>12).mean()>.00035 and delta.mean()>.025))
    scenes=doc.get('scenes',[])
    def scene_at(t):return next((s['id'] for s in scenes if s['sourceStartFrame']/fps<=t<s['sourceEndFrame']/fps),None)
    static=[];start=None;warn=doc.get('motionPolicy',{}).get('longStaticWarningSeconds',8)
    for i in range(1,len(frames)):
        same=scene_at(source_times[i])==scene_at(source_times[i-1]) and scene_at(source_times[i]) is not None and source_times[i]-source_times[i-1]<=.75
        if same and not changes[i-1]:
            if start is None:start=i-1
        elif start is not None:
            if times[i-1]-times[start]>=warn:static.append(dict(start=round(float(times[start]),3),end=round(float(times[i-1]),3),sceneId=scene_at(source_times[start])))
            start=None
    if start is not None and times[-1]-times[start]>=warn:static.append(dict(start=round(float(times[start]),3),end=round(float(times[-1]),3),sceneId=scene_at(source_times[start])))
    beats=doc['motionPlan']['beats']
    from motion_samples import action_phase_audit
    proofs,failures=action_phase_audit(video,doc,first,last)
    unresolved=[]
    for run in static:
        holds=[s for s in segments(dict(doc,holds=doc.get('holds',[]))) if s['kind']=='hold']
        readings=[(b['startFrame'],b['endFrame']) for b in beats if b.get('kind') in ['read','think','observe'] and b.get('reason')]
        unaccounted=0
        for t,src in zip(times,source_times):
            if run['start']<=t<=run['end'] and not any(s['startFrame']<=t*fps<s['endFrame'] for s in holds) and not any(a<=src*fps<z for a,z in readings):unaccounted+=1
        run['intentional']=unaccounted<=2
        if not run['intentional']:unresolved.append(run)
    return dict(schema='course-encoded-motion-audit/1',status='fail' if failures else 'review-required' if unresolved else 'pass',
                failures=failures,actionProofs=proofs,longStaticRuns=static,unresolvedStaticRuns=unresolved,
                sampleFps=2,subjectROI=[112,270,1696,640],motionQuota=None,
                scope='actual encoded subject pixels; low-change flags need review, not a universal motion-rate target')
