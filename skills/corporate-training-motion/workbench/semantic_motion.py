"""Check authored narration/object links and suspiciously stretched transitions.

These checks can reject missing links and slow padding. They cannot decide that
an image or metaphor teaches the right thing; that needs actual scene review.
"""
import re

# Defaults flag ordinary UI transitions, not a universal film speed or motion quota.
PACING_LIMITS={'dialogue':1.2,'mask-reveal':1.2,'text-rise':1.2,'blur-in':1.2,'paper-fold':1.5,
    'handoff':2.0,'assemble':2.0,'sort':2.0,'group-collect':2.0,'magnify':1.8,'explode':2.0,
    'swimlane-transfer':2.5,'path-follow':2.5,'evidence-attach':2.0,'parallel-sync':2.0,
    'callout':1.2,'route-progress':2.5,'branch-grow':2.5,'draw-on':2.0,'scan':2.5,'rotate-inspect':2.5}


def compact(s):return re.sub(r'[\s\W_]+','',str(s))


def inspect(doc,nodes):
    required=bool(doc.get('motionPolicy',{}).get('semanticRequired'))
    fps=doc.get('fps',30);limits={**PACING_LIMITS,**doc.get('motionPolicy',{}).get('pacingLimits',{})};errors=[];slow=[]
    exceptions=doc.get('narrationLinks',{}).get('pacingExceptions',{})
    cues={c['id']:c for c in doc.get('captions',[])}
    from timeline import segments
    spans=segments(dict(doc,holds=doc.get('holds',[])))
    def source_ranges(cue):
        result=[]
        for s in spans:
            a=max(cue['startFrame'],s['startFrame']);z=min(cue['endFrame'],s['endFrame'])
            if a<z and s['kind']=='source':result.append((s['sourceFrame']+a-s['startFrame'],s['sourceFrame']+z-s['startFrame']))
        return result
    for n in nodes.values():
        for e in n.get('effects',[]):
            seconds=(e['endFrame']-e['startFrame'])/fps;limit=limits.get(e['type'])
            if limit is None or seconds<=limit:continue
            key=n['id']+':'+str(e['startFrame']);exc=exceptions.get(key,{})
            ids=exc.get('cueIds',[]);frames=exc.get('reviewFrames',[])
            explained=bool(str(exc.get('reason','')).strip() and len(set(ids))>=2 and
                all(cid in cues and any(a<e['endFrame'] and z>e['startFrame'] for a,z in source_ranges(cues[cid])) for cid in ids) and
                isinstance(frames,list) and len(set(frames))>=3 and
                all(type(f) is int and e['startFrame']<=f<e['endFrame'] for f in frames))
            slow.append(dict(nodeId=n['id'],effect=e['type'],seconds=round(seconds,3),defaultLimit=limit,reviewedException=explained))
            if required and not explained:errors.append('单个动作被拉长：'+n['id']+' '+e['type']+' '+str(round(seconds,2))+'秒；按具体讲解事件拆开，动作完成后可停稳读图')
    if not required:return dict(status='legacy-advisory',errors=[],slowTransitions=slow,semanticJudgement='not evaluated')
    links=doc.get('narrationLinks',{})
    if links.get('schema')!='narration-object-events/1':return dict(status='fail',errors=errors+['缺少旁白—对象—变化/结果的实际对应 narrationLinks'],slowTransitions=slow)
    mapped={};beats={b['id']:b for b in doc.get('motionPlan',{}).get('beats',[]) if b.get('kind','action')=='action'}
    for link in links.get('cueLinks',[]):
        cid=link.get('cueId');cue=cues.get(cid)
        if not cue:errors.append('旁白对应引用不存在的字幕 '+str(cid));continue
        if compact(link.get('text'))!=compact(cue['text']):errors.append('旁白对应绑定了旧词句 '+cid)
        if not link.get('purpose') or not link.get('visibleObjectIds'):errors.append('须说明本句要看懂什么及实际在看的对象 '+cid)
        for identifier in link.get('visibleObjectIds',[]):
            n=nodes.get(identifier)
            if n is None or n.get('role')=='decoration':errors.append('本句没有实际教学主体 '+cid+' '+str(identifier))
        mapped[cid]=link
    for cue in cues.values():
        # Narration can explain an already completed state. It need not animate every frame.
        relevant=any(s['kind']=='source' and max(cue['startFrame'],s['startFrame'])<min(cue['endFrame'],s['endFrame']) and
          s['sourceFrame']+max(0,cue['startFrame']-s['startFrame'])<doc.get('bodyEndFrame',doc['sourceDurationFrames']) and
          s['sourceFrame']+min(cue['endFrame'],s['endFrame'])-s['startFrame']>doc.get('introFrames',0) for s in spans)
        if relevant and cue['id'] not in mapped:errors.append('旁白缺少内容与可见状态对应 '+cue['id'])
    for beat in beats.values():
        anchor=beat.get('anchor',{});cue=cues.get(anchor.get('cueId'));phrase=compact(anchor.get('phrase',''));at=anchor.get('atFrame')
        if not cue or not phrase or phrase not in compact(cue['text']) or type(at) is not int:
            errors.append('动作缺少实际口播词句锚点 '+beat['id']);continue
        # Anchors use source frames; edited captions use display frames.
        if not any(a-fps//2<=at<z for a,z in source_ranges(cue)) or abs(beat['startFrame']-at)>fps//2:
            errors.append('动作与所指口播不在同一时刻 '+beat['id'])
        if beat['before']==beat['after']:errors.append('动作没有具体前后状态差异 '+beat['id'])
    return dict(status='fail' if errors else 'pass',errors=errors,slowTransitions=slow,narrationLinks=len(mapped),
                semanticJudgement='structural links and pacing only; actual appropriateness and listening review required')
