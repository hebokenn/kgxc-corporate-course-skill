"""Read current words, objects and timing; plan inspection without selecting a template."""
import hashlib
import json

GUIDES=['references/12-director-teaching.md','references/41-direction-and-performance.md',
        'references/42-content-directed-production.md']


def walk(nodes,scene=None):
    for node in nodes:
        owner=node.get('sceneId',scene)
        yield node,owner
        yield from walk(node.get('children',[]),owner)


def inspect(doc):
    from timeline import segments,display_frame,source_frame
    from craft_quality import analyze
    duration=doc.get('sourceDurationFrames',0);fps=doc.get('fps',30)
    spans=segments(dict(doc,holds=doc.get('holds',[]))) if duration else []
    nodes=list(walk(doc.get('sceneGraph',{}).get('nodes',[])))
    links={v.get('cueId'):v for v in doc.get('narrationLinks',{}).get('cueLinks',[])}
    beats=doc.get('motionPlan',{}).get('beats',[]);rows=[]
    for scene in doc.get('scenes',[]):
        sid=scene['id'];a,z=scene['sourceStartFrame'],scene['sourceEndFrame'];points={}
        def mark(frame,reason):
            if type(frame) is int and a<=frame<min(duration,z+1):points.setdefault(frame,set()).add(reason)
        mark(a,'scene-entry');mark(z-1,'settled-scene');mark(z,'next-scene-residue')
        local=[(n,owner)for n,owner in nodes if owner in [sid,None]]
        for node,_ in local:
            for key in ['startFrame','endFrame']:
                f=node.get(key)
                if type(f) is int:
                    for delta in [-1,0]:mark(f+delta,'visibility:'+node['id'])
            for motion in node.get('motion',[])+node.get('effects',[]):
                x,y=motion.get('startFrame'),motion.get('endFrame')
                if type(x) is int and type(y) is int and x<y:
                    for f in [x,(x+y-1)//2,y-1,y]:mark(f,'transform:'+node['id'])
            for key in node.get('performance',{}).get('keys',[]):mark(key.get('frame'),'performance-key:'+node['id'])
            for blink in node.get('performance',{}).get('blinks',[]):
                for f in blink:mark(f,'performance-blink:'+node['id'])
        camera=doc.get('sceneGraph',{}).get('camera',{})
        for move in camera.get('motion',[]):
            x,y=move.get('startFrame'),move.get('endFrame')
            if type(x) is int and type(y) is int and x<y:
                for f in [x,(x+y-1)//2,y-1,y]:mark(f,'global-camera')
        local_beats=[b for b in beats if b.get('sceneId')==sid]
        for beat in local_beats:
            for f in beat.get('evidenceFrames',[]):mark(f,'declared-action:'+beat['id'])
            for f in beat.get('reviewFrames',[]):mark(f,'producer-peak:'+beat['id'])
        for f in scene.get('reviewFrames',[]):mark(f,'producer-scene-peak')
        for span in spans:
            if span['kind']=='hold':mark(span['sourceFrame'],'retained-read-hold')
        inspected=[]
        for f,reasons in sorted(points.items()):
            display=display_frame(f,doc.get('holds',[]),doc.get('cuts',[]))
            if source_frame(display,doc.get('holds',[]),doc.get('cuts',[]))!=f:continue
            mapped={display}
            for span in spans:
                if span['kind']=='hold' and span['sourceFrame']==f:mapped.update([span['startFrame'],span['endFrame']-1])
            for df in sorted(mapped):inspected.append(dict(sourceFrame=f,displayFrame=df,reasons=sorted(reasons)))
        cues=[]
        for cue in doc.get('captions',[]):
            relevant=any(span['kind']=='source' and max(cue['startFrame'],span['startFrame'])<min(cue['endFrame'],span['endFrame']) and
                span['sourceFrame']+max(0,cue['startFrame']-span['startFrame'])<z and
                span['sourceFrame']+min(cue['endFrame'],span['endFrame'])-span['startFrame']>a for span in spans)
            if relevant:
                link=links.get(cue['id'],{});cues.append(dict(cueId=cue['id'],text=cue['text'],purpose=link.get('purpose'),visibleObjectIds=link.get('visibleObjectIds',[])))
        rows.append(dict(sceneId=sid,title=scene.get('title',''),sourceRange=[a,z],seconds=(z-a)/fps,
            presentation=scene.get('presentation',{}),narration=cues,
            subjectObjectIds=[n['id']for n,_ in local if n.get('role')not in ['decoration','camera'] and n.get('type')!='group'],
            performanceObjectIds=[n['id']for n,_ in local if n.get('performance')],
            actionChoices=[{k:b.get(k)for k in ['id','kind','purpose','before','after','objectIds','anchor','startFrame','endFrame','reason']}for b in local_beats],
            inspectionFrames=inspected))
    signals=analyze(doc)['signals'] if doc.get('scenes') else []
    return dict(schema='course-content-direction-inspection/1',status='inspection-plan' if rows else 'needs-content-design',
        documentSemanticSha256=hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        guides=GUIDES,scenes=rows,compositionSignals=signals,
        scope='actual saved words, objects, states and source/display-frame candidates; no keyword-selected template, semantic judgment, peak-visibility guarantee, aesthetic score or user acceptance')


def continuation(doc):
    report=inspect(doc)
    return dict(schema=report['schema'],status=report['status'],requiredGuides=GUIDES,
        scenes=len(report['scenes']),inspectionFrames=sum(len(s['inspectionFrames'])for s in report['scenes']),
        compositionSignals=report['compositionSignals'],
        command='course_tools.py direction-check --spec PROJECT/workbench.json --out NEW_REVIEW_PLAN.json',
        next='从已确认本课逐字稿决定各段任务、对象变化、观看焦点、镜头理由和动作/结果停留；先做动态分镜。困难或重复段比较可行表现，必要的连续构图保留理由。不得复制示例课的版式、帧号、人物组合或时长。',
        verification='按实际动作和人物关键姿态查看原生画面及最终编码帧，特别复查镜头与标签边界、运动峰值、停稳和下一场；技术计划不能代替正常速度观察或真实用户认可。')
