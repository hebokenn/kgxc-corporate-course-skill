"""Non-destructive source cuts and retained holds, in integer 30 fps frames."""
import copy


def display_frame(frame, holds, cuts=()):
    removed=sum(max(0,min(frame,c['endFrame'])-c['startFrame']) for c in cuts)
    return frame-removed+sum(h['frames'] for h in holds if h['sourceFrame']<=frame)


def duration(doc):
    return doc['sourceDurationFrames']-sum(c['endFrame']-c['startFrame'] for c in doc.get('cuts',[]))+sum(h['frames'] for h in doc['holds'])


def segments(doc):
    """Return retained source and silent hold segments in edited playback order."""
    cuts=doc.get('cuts',[]);holds={h['sourceFrame']:h for h in doc['holds']}
    points=sorted({0,doc['sourceDurationFrames'],*holds,*[c[k] for c in cuts for k in ['startFrame','endFrame']]})
    result=[];cursor=0;cut_index=0
    for i,a in enumerate(points):
        h=holds.get(a)
        if h and h['frames']:
            result.append(dict(kind='hold',startFrame=cursor,endFrame=cursor+h['frames'],sourceFrame=max(0,a-1),holdFrame=a,sceneId=h.get('sceneId','')));cursor+=h['frames']
        if i==len(points)-1:break
        b=points[i+1]
        while cut_index<len(cuts) and cuts[cut_index]['endFrame']<=a:cut_index+=1
        if cut_index<len(cuts) and cuts[cut_index]['startFrame']<=a<cuts[cut_index]['endFrame']:continue
        result.append(dict(kind='source',startFrame=cursor,endFrame=cursor+b-a,sourceFrame=a));cursor+=b-a
    return result


def source_frame(frame, holds, cuts=()):
    # The final source span is unbounded for the legacy two-argument helper.
    end=max([frame+1+sum(c['endFrame']-c['startFrame'] for c in cuts),*[h['sourceFrame']+1 for h in holds],*[c['endFrame']+1 for c in cuts]])
    for s in segments(dict(sourceDurationFrames=end,holds=holds,cuts=cuts)):
        if s['startFrame']<=frame<s['endFrame']:
            return s['sourceFrame']+(frame-s['startFrame'] if s['kind']=='source' else 0)
    return end-1


def ripple_cut(doc, start, end):
    """Remove an edited interval, retiming every cue without modifying originals."""
    if type(start) is not int or type(end) is not int or not 0<=start<end<=duration(doc) or end-start>=duration(doc):
        raise ValueError('请选择有效裁剪区间，并至少保留一帧课程')
    result=copy.deepcopy(doc);removed_holds={};cuts=copy.deepcopy(doc.get('cuts',[]))
    for s in segments(doc):
        a=max(start,s['startFrame']);b=min(end,s['endFrame'])
        if a>=b:continue
        if s['kind']=='hold':removed_holds[s['holdFrame']]=b-a
        else:cuts.append(dict(startFrame=s['sourceFrame']+a-s['startFrame'],endFrame=s['sourceFrame']+b-s['startFrame']))
    merged=[]
    for c in sorted(cuts,key=lambda c:c['startFrame']):
        if merged and c['startFrame']<=merged[-1]['endFrame']:merged[-1]['endFrame']=max(merged[-1]['endFrame'],c['endFrame'])
        else:merged.append(c)
    result['cuts']=merged
    result['holds']=[dict(h,frames=h['frames']-removed_holds.get(h['sourceFrame'],0)) for h in doc['holds'] if h['frames']>removed_holds.get(h['sourceFrame'],0)]
    def move(t):return t if t<=start else t-(end-start) if t>=end else start
    result['captions']=[dict(c,startFrame=move(c['startFrame']),endFrame=move(c['endFrame'])) for c in doc['captions'] if move(c['endFrame'])>move(c['startFrame'])]
    return result
