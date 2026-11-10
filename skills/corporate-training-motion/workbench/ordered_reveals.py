"""Declared numbered lists: exact sentence anchors, cumulative order and encoded probes.

This verifies presence in specified regions, not glyph OCR, meaning or continuous AV.
"""
import hashlib
import json
import math
import subprocess
from production_validation import Check, load, graph, first_readable, visible, path_in, sha, resolve_current_video, ENCODED, digest
from semantic_alignment import resolve

GENERIC = {'这节课', '本课', '接下来', '然后', '我们来看', '这一节'}


def resolve_row(mapping, event):
    row = next((s for s in mapping.get('segments', []) if s.get('id') == event.get('segment_id')), None)
    if not row or not row.get('paragraph_id') or row['paragraph_id'] != event.get('paragraph_id'):
        raise ValueError('Explicit current segment and paragraph identity required')
    text = row.get('narration', '')
    span = event.get('sentence_span', [])
    if (len(span) != 2 or any(type(x) is not int for x in span) or
            not 0 <= span[0] < span[1] <= len(text) or text[span[0]:span[1]] != event.get('sentence')):
        raise ValueError('Exact concrete sentence and raw sentence span required')
    quote = event.get('quote', '')
    if quote.strip(' ，。！？；：') in GENERIC:
        raise ValueError('Generic transition phrase cannot trigger a numbered teaching item')
    aligned = resolve(mapping, event)
    a, z = aligned['raw_span']
    if not span[0] <= a < z <= span[1]:
        raise ValueError('Selected occurrence is outside its concrete sentence')
    return aligned


def plan(mapping, groups, events):
    """Never sort timestamps, clamp them, or estimate missing triggers."""
    byid = {e['id']: e for e in events}
    if len(byid) != len(events):
        raise ValueError('Duplicate semantic event identity')
    result, identities = [], set()
    for g in groups:
        gid = g.get('id')
        if not gid or gid in identities or g.get('mode') not in {'sequential', 'simultaneous'}:
            raise ValueError('Unique list identity and explicit sequential/simultaneous mode required')
        identities.add(gid)
        rows = g.get('rows', [])
        if not rows or any(type(r.get('number'))is not int for r in rows) or len({r.get('node_id')for r in rows})!=len(rows) or [r.get('number') for r in rows] != list(range(1, len(rows)+1)):
            raise ValueError('Layout rows must retain consecutive declared numbers; do not sort by time')
        resolved = []
        for row in rows:
            e = byid.get(row.get('event_id'))
            if e is None or not row.get('node_id'):
                raise ValueError('Every actual row needs its own semantic event and node')
            aligned = resolve_row(mapping, e)
            f = e.get('trigger_frame')
            if type(f) is not int or not math.isfinite(aligned['start']) or not math.isfinite(aligned['end']) or abs(f-aligned['start']) > .5:
                raise ValueError('Trigger differs from its actual word; no proportional or max-clamp fallback')
            stable = row.get('stable_frame')
            if type(stable) is not int or stable < f:
                raise ValueError('Explicit stable frame required after appearance')
            resolved.append(dict(row, trigger_frame=f, stable_frame=stable))
        times = [r['trigger_frame'] for r in resolved]
        if g['mode'] == 'sequential' and any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError('Number/layout order differs from narration order; revise the layout or narration')
        end = g.get('end_frame')
        if type(end) is not int or end <= max(r['stable_frame'] for r in resolved):
            raise ValueError('Actual list end must retain the last stable row')
        result.append(dict(g, rows=resolved))
    return result


def checkpoints(groups):
    return sorted({f for g in groups for r in g['rows'] for f in
                   [max(0,r['trigger_frame']-1),r['trigger_frame'],r['stable_frame']]})


def encoded_presence(video, groups, source_to_display=lambda f:f):
    """One from-head, non-reinitializing decode; observations bind exact main bytes."""
    import numpy as np
    from media_frames import main_video
    stream = main_video(video); w,h = stream['width'],stream['height']
    indices = sorted({source_to_display(f) for f in checkpoints(groups)})
    probes = []
    for g in groups:
        axis=1 if g.get('layout','vertical')=='vertical'else 0
        positions=[r.get('probe',{}).get('region',[])[axis]for r in g['rows']if len(r.get('probe',{}).get('region',[]))==4]
        if len(positions)==len(g['rows']) and any(a>=b for a,b in zip(positions,positions[1:])):raise ValueError('Actual probe layout disagrees with numbered order')
        for row in g['rows']:
            p = row.get('probe', {}); box = p.get('region', [])
            if (len(box) != 4 or any(type(x) is not int for x in box) or min(box[:2]) < 0 or
                    min(box[2:]) <= 0 or box[0]+box[2] > w or box[1]+box[3] > h or
                    len(p.get('rgb', [])) != 3 or any(type(x) is not int or not 0<=x<=255 for x in p['rgb']) or
                    not 0 <= p.get('tolerance', -1) <= 80 or
                    not 0 < p.get('minimum_pixels', 0) <= box[2]*box[3]):
                raise ValueError('Bounded actual-pixel row presence probe required')
            probes.append((g,row,p))
    expr='+'.join('eq(n\\,%d)'%f for f in indices)
    cmd=['ffmpeg','-nostdin','-v','error','-reinit_filter','0','-noautorotate','-i',str(video),
         '-map','0:'+str(stream['index']),'-vf','select='+expr+',format=rgb24',
         '-fps_mode','passthrough','-frames:v',str(len(indices)),'-f','rawvideo','-']
    observations=[]
    # communicate is avoided: long lessons can have hundreds of checkpoints.
    with subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as proc:
        try:
            for frame in indices:
                raw=proc.stdout.read(w*h*3)
                if len(raw)!=w*h*3:raise ValueError('Exact requested decoded frame is absent')
                pixels=np.frombuffer(raw,dtype=np.uint8).reshape(h,w,3);active=[];counts={}
                for g,row,p in probes:
                    if not source_to_display(max(0,min(r['trigger_frame'] for r in g['rows'])-1))<=frame<source_to_display(g['end_frame']):continue
                    a,b,c,d=p['region'];crop=pixels[b:b+d,a:a+c].astype(int)
                    n=int(np.all(abs(crop-np.array(p['rgb']))<=p['tolerance'],axis=2).sum())
                    shown=n>=p['minimum_pixels'];counts[row['node_id']]=n
                    start=source_to_display(row['trigger_frame'])
                    end=source_to_display(g['end_frame'])
                    # Before/at/stable observations also check that previous rows remain.
                    expected=start<=frame<end
                    if shown!=expected:raise ValueError('Encoded row presence/order mismatch at frame %d: %s'%(frame,row['node_id']))
                    if shown:active.append(row['node_id'])
                observations.append(dict(encoded_frame=frame,visible_node_ids=active,probe_counts=counts,
                    pixel_sha256=hashlib.sha256(raw).hexdigest()))
            if proc.stdout.read(1):raise ValueError('Unexpected decoded frame count')
            if proc.wait(timeout=120):raise ValueError(proc.stderr.read().decode(errors='replace')[:1000])
        except BaseException:
            proc.kill();proc.wait();raise
    return dict(video_sha256=sha(video),observations=observations,
                scope='Exact decoded marker/region presence; not OCR, semantic correctness or continuous hearing')


def inspect(project, doc, video, purpose, contract):
    c=Check('ordered_reveals')
    if purpose not in {'storyboard',*ENCODED}:return c.result()
    direction=contract.get('requirements',{}).get('direction',{})
    data=load(project,direction.get('semantic_alignment'))
    groups=doc.get('orderedRevealGroups',[])
    nodes,chains=graph(doc)
    marked={i for i,n in nodes.items() if n.get('orderedList')}
    declared={r.get('node_id') for g in groups for r in g.get('rows',[])}
    if marked-declared:c.error('REVEAL_GROUP_MISSING','Numbered list objects are missing their group declaration',node_ids=sorted(marked-declared))
    if not groups:
        c.details['applicability']='No declared numbered-list groups; this is not OCR of arbitrary raster/custom drawings'
        return c.result()
    mapping=load(project,data.get('map_path',data.get('mapping')))
    if purpose=='storyboard' and not doc.get('media',{}).get('audio') and not data.get('audio_path'):
        for g in groups:
            if g.get('mode') not in {'sequential','simultaneous'} or [r.get('number')for r in g.get('rows',[])]!=list(range(1,len(g.get('rows',[]))+1)):
                c.error('REVEAL_LAYOUT_INVALID','Declared numbering/layout is invalid',g.get('id'))
        c.details['applicability']='Narration not yet produced; exact occurrence/audio/pixel checks remain not_started for media stages'
        return c.result()
    script=path_in(project,data.get('script_path'))
    if not script or sha(script)!=data.get('script_sha256') or mapping.get('script_sha256')!=data.get('script_sha256'):
        c.error('REVEAL_SCRIPT_STALE','Current script bytes must bind the paragraph/word map')
    audio=path_in(project,data.get('audio_path'))
    if not audio or sha(audio)!=mapping.get('audio_sha256') or mapping.get('audio_sha256')!=data.get('audio_sha256'):
        c.error('REVEAL_AUDIO_STALE','Current audio bytes must bind the paragraph/word map')
    try:resolved=plan(mapping,groups,data.get('events',[]))
    except (ValueError,KeyError,TypeError) as exc:
        c.error('REVEAL_ORDER_INVALID',str(exc));return c.result()
    sfx=load(project,contract.get('requirements',{}).get('sfx',{}).get('plan_path'))
    sounds={e.get('id'):e for e in sfx.get('events',[])}
    for g in resolved:
        times=[r['trigger_frame'] for r in g['rows']]
        onsets=[]
        for r in g['rows']:
            identifier=r['node_id'];n=nodes.get(identifier,{})
            if not n or n.get('orderedList',{}).get('index')!=r['number'] or n.get('orderedList',{}).get('group_id')!=g['id']:
                c.error('REVEAL_OBJECT_INVALID','Actual numbered row identity/index differs from layout',identifier);continue
            first=first_readable(doc,nodes,chains,identifier);onsets.append(first)
            if g['mode']=='sequential' and first!=r['trigger_frame']:
                c.error('REVEAL_TIME_MISMATCH','Actual first readable row differs from its speech trigger',identifier)
            if g['mode']=='sequential' and not all(visible(doc,nodes,chains,identifier,f) for f in [r['stable_frame'],g['end_frame']-1]):
                c.error('REVEAL_RETENTION_MISSING','Earlier numbered rows must remain through the cumulative list',identifier)
            if r.get('sound_event_id'):
                e=sounds.get(r['sound_event_id'],{})
                if e.get('frame')!=r['trigger_frame'] or e.get('visual_event_id')!=r['event_id']:
                    c.error('REVEAL_SOUND_MISMATCH','Sound must follow this actual row event, not the old trigger',identifier)
            elif r.get('sound_required'):
                c.error('REVEAL_SOUND_MISSING','Required row sound has no actual plan event',identifier)
        axis={'vertical':'y','horizontal':'x'}.get(g.get('layout','vertical'))
        if not axis:c.error('REVEAL_LAYOUT_INVALID','Supported list layout is vertical or horizontal',g['id'])
        elif all(r['node_id']in nodes for r in g['rows']):
            from reading_pacing import _state
            frame=max(r['stable_frame']for r in g['rows'])
            positions=[sum(_state(nodes[k],frame).get(axis,0)for k in chains[r['node_id']])for r in g['rows']]
            if any(a>=b for a,b in zip(positions,positions[1:])):
                c.error('REVEAL_LAYOUT_ORDER','Numbered layout differs from the spoken row order',g['id'])
        if g['mode']=='simultaneous' and (not onsets or None in onsets or len(set(onsets))!=1):
            c.error('REVEAL_NOT_SIMULTANEOUS','A full-page list must actually appear together, not just declare that mode',g['id'])
    if purpose in ENCODED and not c.errors:
        from timeline import display_frame
        if any(g['mode']=='simultaneous' for g in resolved):
            # Presence start uses actual common onset; spoken order remains independent.
            resolved=[dict(g,rows=[dict(r,trigger_frame=first_readable(doc,nodes,chains,r['node_id'])) for r in g['rows']]) if g['mode']=='simultaneous' else g for g in resolved]
        try:c.details['actual_encoded_presence']=encoded_presence(resolve_current_video(project,video),resolved,
                lambda f:round(display_frame(f,doc.get('holds',[]),doc.get('cuts',[]))))
        except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as exc:c.error('REVEAL_ENCODED_INVALID',str(exc))
    c.details['groups_checked']=len(resolved)
    c.details['checkpoints']=checkpoints(resolved)
    return c.result()
