"""Special emphasis means an executable relationship, not a font/ID/count."""
from production_validation import Check, load, graph, changed, current_review, path_in, sha, digest, resolve_current_video, ENCODED
from reading_pacing import Exposure, estimate


def inspect(project, doc, video, purpose, contract):
    c = Check('emphasis')
    req = contract.get('requirements', {}).get('emphasis', {})
    if contract.get('choices', {}).get('flower_text') == 'off':
        return c.result()
    if req.get('required') is False:
        c.error('EMPHASIS_UNIMPLEMENTED','Enabled emphasis choice cannot be disabled by a local required flag')
    if purpose in {'script', 'design'}:
        return c.result()
    events = req.get('events', [])
    if not events:
        c.error('EMPHASIS_UNIMPLEMENTED', 'Emphasis enabled but no dedicated events exist')
    nodes, chains = graph(doc)
    exposure = Exposure(doc)
    groups = doc.get('readingPlan', {}).get('groups', [])
    required = []
    runtime=load(project,req.get('runtime_reading'))
    runtime_report=load(project,runtime.get('report_path',runtime.get('report')))
    if purpose in ENCODED and (runtime.get('document_sha256')!=digest(doc) or runtime.get('video_sha256')!=sha(resolve_current_video(project,video)) or runtime_report.get('status')!='pass'):
        c.error('EMPHASIS_RUNTIME_READING_MISSING','Current same-render reading receipt is required; planned windows alone do not prove clipping/occlusion')
    for e in events:
        eid = e.get('id'); texts = e.get('text_node_ids', []); markers = e.get('marker_node_ids', [])
        targets = e.get('target_node_ids', [])
        if not all(e.get(k) for k in ('requirement_id','quote','purpose','emphasis_text','visual_treatment','semantic_anchor','sound_or_silence_reason')):
            c.error('EMPHASIS_BINDING_INVALID', 'Dedicated emphasis meaning/treatment/word/sound decision is incomplete', eid)
        ids = texts+markers+targets
        if not texts or not targets or any(i not in nodes for i in ids):
            c.error('EMPHASIS_BINDING_INVALID', 'Emphasis must reference actual text, visual targets and treatment objects', eid)
            continue
        if any(nodes[i].get('type') != 'text' or nodes[i].get('role') in {'caption','navigation','title','decoration'} for i in texts):
            c.error('EMPHASIS_UNIMPLEMENTED', 'Captions/navigation/renamed decorations cannot impersonate special emphasis', eid)
        a,z,land = e.get('animation_start'),e.get('animation_end'),e.get('landing_frame')
        if not all(type(v) is int for v in (a,z,land)) or not a <= z <= land:
            c.error('EMPHASIS_BINDING_INVALID', 'Animation and landing ranges are invalid', eid)
            continue
        # Typography alone, opacity alone and a name alone never establish treatment.
        def real_action(n):
            return any(m.get('property') != 'opacity' and m.get('from') != m.get('to') for m in n.get('motion', [])) or any(e.get('type') in {'draw-on','underline','check-draw','cross-draw','brace-draw','magnify','assemble','evidence-attach','callout','paper-fold','compare-wipe','correct-replace'} and e.get('endFrame',0)>e.get('startFrame',0) for e in n.get('effects',[]))
        if not markers or not any(real_action(nodes[i]) for i in texts+markers):
            c.error('EMPHASIS_UNIMPLEMENTED', 'Dedicated graphical/subject action is absent; font names alone are insufficient', eid)
        window = e.get('reading_window', [])
        if len(window) != 2 or not all(type(v) is int for v in window) or not land <= window[0] < window[1]:
            c.error('EMPHASIS_BINDING_INVALID', 'Stable continuous reading window must begin after actual landing', eid)
            continue
        matching = [g for g in groups if set(texts) <= set(g.get('textIds', [])) and
            g.get('window',{}).get('startFrame',999999) <= window[0] and g.get('window',{}).get('endFrame',-1) >= window[1]]
        if not matching:
            c.error('EMPHASIS_BINDING_INVALID', 'Emphasis text lacks a real body reading group', eid)
            continue
        g = matching[0]; minimum = max(g.get('minimumStableSeconds',0), estimate([nodes[i].get('text','') for i in texts]))
        windows = exposure.windows(texts, g['sceneId'], *window)
        longest = max((y-x for x,y,_ in windows), default=0)/doc['fps']
        if purpose in ENCODED:
            row=next((r for r in runtime_report.get('groups',[]) if r.get('id')==g['id']),{})
            actual=row.get('actualStableWindow') or []
            mapped=exposure.map_range(*window)
            actual_longest=max((max(0,min(actual[1],y)-max(actual[0],x))/doc['fps'] for x,y in mapped),default=0) if len(actual)==2 else 0
            if actual_longest<minimum or row.get('missingRetentionFrames',0):
                c.error('EMPHASIS_RUNTIME_READING_SHORT','Actual continuous complete/unoccluded runtime exposure does not cover the emphasis window',eid,actual_seconds=actual_longest,required_seconds=minimum)
        if longest < minimum:
            c.error('EMPHASIS_READING_SHORT', 'Continuous actual stable exposure is below both budget and engineering floor', eid,
                    actual_seconds=longest, required_seconds=minimum, missing_seconds=minimum-longest)
        # Protect negation/condition/permission as explicitly identified by authoring.
        automatic=[token for token in ('不能','不得','不应','未经','仅限','必须','先','才','如果','除非')
                   if token in e.get('quote','') and e.get('quote','').replace(token,'').strip()==e.get('emphasis_text','').strip()]
        for token in set(e.get('protected_tokens', []))|set(automatic):
            if token in e.get('quote','') and token not in e.get('emphasis_text',''):
                c.error('EMPHASIS_SEMANTIC_CHANGED', 'Required condition/negation/permission was removed from emphasis', eid, token=token)
        required += [max(0,a-1),a,(a+z)//2,land,window[1]-1]
    if purpose in ENCODED:
        current_review(c, project, req.get('review'), doc, video, 'EMPHASIS_REVIEW_MISSING', required)
    c.details['implemented_count'] = len(events) if not c.errors else None
    return c.result()
