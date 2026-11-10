"""Compare actual subject structure without wording, color, names or mirroring."""
from collections import Counter
from itertools import combinations
from production_validation import resolve_current_video, Check, load, graph, digest, current_review, path_in, sha, ENCODED

EXCLUDED={'navigation','caption','title','decoration','brand'}


def signature(doc, scene):
    nodes,chains=graph(doc)
    ids=scene.get('node_ids',[])
    chosen={i for i,n in nodes.items() if n.get('role') not in EXCLUDED and
            any(root in chains[i] for root in ids)}
    # Parent groups are composition only. Geometry and parent edges are actual graph data.
    features={i:(nodes[i].get('type','unknown'),bool(nodes[i].get('vectorActor')),bool(nodes[i].get('vectorProp')))
              for i in chosen}
    relation=Counter()
    centers={}
    for i in chosen:
        n=nodes[i];x=sum(nodes[k].get('x',0) for k in chains[i]);y=sum(nodes[k].get('y',0) for k in chains[i])
        centers[i]=(x+n.get('width',0)/2,y+n.get('height',0)/2)
        if len(chains[i])>1 and chains[i][-2] in chosen:
            relation[('parent',features[chains[i][-2]],features[i])]+=1
    xs=[v[0] for v in centers.values()];ys=[v[1] for v in centers.values()]
    w=max(xs,default=1)-min(xs,default=0) or 1;h=max(ys,default=1)-min(ys,default=0) or 1
    geometry=[]
    for a,b in combinations(chosen,2):
        dx=round(abs(centers[a][0]-centers[b][0])/w,1);dy=round(abs(centers[a][1]-centers[b][1])/h,1)
        geometry.append((tuple(sorted([features[a],features[b]])),dx,dy))
    actions=[];reveals=[]
    for i in chosen:
        n=nodes[i]
        for m in n.get('motion',[]):
            if m.get('from')!=m.get('to'):
                actions.append((m.get('startFrame',0),features[i],m.get('property')))
        for e in n.get('effects',[]):
            # Actual operation families, never one new signature per effect name.
            kind=('opacity' if e.get('type') in {'fade-in','blur-in'} else
                  'text-progress' if e.get('type') in {'chars-in','typewriter','text-rise'} else
                  'path-progress' if e.get('type') in {'draw-on','route-progress','branch-grow'} else 'object-transform')
            actions.append((e.get('startFrame',0),features[i],kind))
        actor=n.get('vectorActor') or n.get('acting') or {}
        for walk in actor.get('walks',[]):
            if walk.get('fromX')!=walk.get('toX'):actions.append((walk.get('startFrame',0),features[i],'actor-walk'))
        for key in actor.get('facing',[]):
            actions.append((key.get('frame',0),features[i],'actor-facing'))
        for speech in actor.get('speech',[]):
            actions.append((speech.get('startFrame',0),features[i],'actor-speech'))
        for key in actor.get('keys',[]):
            for prop in sorted(key.get('values',{})):
                actions.append((key.get('frame',0),features[i],'actor-'+prop))
        if n.get('type')=='text':
            reveals.append((n.get('startFrame',0),features[i],len(chains[i])))
    def ordered(rows):
        times={f:j for j,f in enumerate(sorted({r[0] for r in rows}))}
        return sorted((times[r[0]],*r[1:]) for r in rows)
    body=dict(objects=sorted(Counter(features.values()).items()),relations=sorted(relation.items()),
              layout=sorted(geometry),operations=ordered(actions),information_order=ordered(reveals))
    return dict(sha256=digest(body),structure=body)


def inspect(project, doc, video, purpose, contract):
    c=Check('presentation')
    if purpose in {'script','design'}:
        return c.result()
    req=contract.get('requirements',{}).get('direction',{})
    data=load(project,req.get('presentation'))
    scenes=req.get('scenes',[])
    plans={s.get('scene_id'):s for s in data.get('scenes',[])}
    chapter_plans=data.get('chapters',[])
    if not chapter_plans or any(not s.get('teaching_task') or not s.get('primary_structure') for s in chapter_plans):
        c.error('PRESENTATION_PLAN_MISSING','Each chapter needs its real teaching task and principal subject structure')
    signatures={}
    for scene in scenes:
        sid=scene.get('scene_id');plan=plans.get(sid,{})
        if scene.get('kind')=='brand':
            continue
        if not all(plan.get(k) for k in ('spatial_organization','interaction_order','information_order','before','process','after','reading_task')):
            c.error('PRESENTATION_PLAN_MISSING','Subject structure, information sequence and post-action reading task are required',sid)
        sig=signature(doc,scene);signatures[sid]=sig
    duplicates=[]
    for a,b in combinations(signatures,2):
        if signatures[a]['sha256']==signatures[b]['sha256']:
            duplicates.append([a,b]);c.error('DUPLICATE_PRESENTATION','Actual subject relationship/layout/operations repeat despite wording/color/name changes',a,other_scene_id=b)
    c.details.update(signatures=signatures,duplicate_pairs=duplicates,
                     inference_limit='A different structural signature is not proof of visual richness or teaching quality')
    if purpose in ENCODED:
        from motion_quality import audit_encoded
        from timeline import duration
        p=resolve_current_video(project,video)
        if not p or not p.is_file():
            c.error('PRESENTATION_MEDIA_MISSING','Current encoded media is required');return c.result()
        audit=audit_encoded(p,doc,0,duration(dict(doc,holds=doc.get('holds',[]))))
        c.details['encoded_static_audit']=audit
        tasks=data.get('reading_tasks',[])
        for run in audit.get('longStaticRuns',[]):
            a,z=run['start']*doc['fps'],run['end']*doc['fps']
            task=next((r for r in tasks if r.get('scene_id')==run['sceneId'] and
                r.get('display_window',[1,0])[0]<=a<z<=r.get('display_window',[1,0])[1]),None)
            nodes,_=graph(doc)
            if not task or not task.get('object_ids') or any(i not in nodes or nodes[i].get('role') in EXCLUDED for i in task['object_ids']) or not task.get('reason'):
                c.error('STATIC_WITH_NEW_TEACHING','Encoded subject is static without a specific current object-reading task',run['sceneId'],display_window=[a,z])
                continue
            from reading_pacing import Exposure
            group=next((g for g in doc.get('readingPlan',{}).get('groups',[]) if g.get('id')==task.get('reading_group_id')),{})
            if not group or not set(task['object_ids'])<=set(group.get('textIds',[])):
                c.error('STATIC_WITH_NEW_TEACHING','Static reading exception lacks the actual relevant body reading group',run['sceneId'])
            else:
                window=group.get('window',{})
                stable=Exposure(doc).windows(group['textIds'],group['sceneId'],window['startFrame'],window['endFrame'])
                if not any(x<=a<z<=y for x,y,_ in stable):
                    c.error('STATIC_WITH_NEW_TEACHING','Claimed reading objects are not actually stable for this run',run['sceneId'])
            semantic=load(project,req.get('semantic_alignment'))
            from timeline import display_frame
            new=[e.get('id') for e in semantic.get('events',[]) if e.get('new_value_node_ids') and
                 a<display_frame(e.get('trigger_frame',0),doc.get('holds',[]),doc.get('cuts',[]))<z]
            if new:c.error('STATIC_WITH_NEW_TEACHING','Narration introduces new fields while encoded subject remains static',run['sceneId'],semantic_event_ids=new)
            actual=next((s for s in doc.get('scenes',[]) if s['id']==run['sceneId']),{})
            if task.get('source_window')==[actual.get('sourceStartFrame'),actual.get('sourceEndFrame')]:
                c.error('STATIC_WITH_NEW_TEACHING','An entire scene reading waiver cannot replace meaningful subject development',run['sceneId'])
        required=[]
        from timeline import display_frame
        for scene in doc.get('scenes',[]):
            a,z=scene.get('sourceStartFrame',0),scene.get('sourceEndFrame',0)
            if z>a:required += [display_frame(a,doc.get('holds',[]),doc.get('cuts',[])),display_frame((a+z)//2,doc.get('holds',[]),doc.get('cuts',[])),display_frame(z-1,doc.get('holds',[]),doc.get('cuts',[]))]
        current_review(c,project,req.get('review'),doc,video,'PRESENTATION_REVIEW_MISSING',required)
        playback=load(project,req.get('review')).get('continuous_comparisons',[])
        viewings=load(project,req.get('review')).get('chapter_viewings',[])
        for plan in chapter_plans:
            if not any(v.get('chapter_id')==plan.get('chapter_id') and v.get('speed')==1 and
                       v.get('method') and v.get('actual_range') and v.get('observation') for v in viewings):
                c.error('PRESENTATION_COMPARISON_UNVERIFIED','Chapter principal presentation lacks an actual normal-speed viewing record',plan.get('chapter_id'))
        for pair in duplicates:
            if not any(r.get('scene_ids')==pair and r.get('speed')==1 and r.get('observed_difference') for r in playback):
                c.error('PRESENTATION_COMPARISON_UNVERIFIED','Risk pair lacks actual normal-speed comparison',pair[0],other_scene_id=pair[1])
    return c.result()
