"""One chapter source for playback, metadata and executable progress checks."""
import re
from production_validation import Check, load, graph, digest, current_review, visible, ENCODED
from timeline import display_frame, source_frame
from reading_pacing import _state


def progress(chapter, frame):
    a, z = chapter['display_start'], chapter['display_end']
    return max(0., min(1., (frame-a)/(z-a)))


def expected_samples(table):
    return sorted({f for c in table for f in [c['display_start']-1, c['display_start'], c['display_start']+1,
        *[round(c['display_start']+(c['display_end']-c['display_start'])*p) for p in (.1,.5,.9)], c['display_end']-1] if f >= 0})


def canonical_table(doc, rows):
    """Compile all consumers from authored source boundaries; do not infer page names."""
    return [dict(c, display_start=display_frame(c['source_start'], doc.get('holds', []), doc.get('cuts', [])),
                    display_end=display_frame(c['source_end'], doc.get('holds', []), doc.get('cuts', []))) for c in rows]


def inspect(project, doc, video, purpose, contract):
    c = Check('chapters')
    if purpose in {'script', 'design'}:
        return c.result()
    req = contract.get('requirements', {}).get('chapters', {})
    table = load(project, req.get('chapter_table'), [])
    if not isinstance(table, list) or not table:
        c.error('CHAPTER_TABLE_STALE', 'A single explicit chapter table is required')
        return c.result()
    try:
        canonical = canonical_table(doc, table)
        if doc.get('chapterTable') != table or table != canonical or req.get('table_sha256') != digest(table):
            c.error('CHAPTER_TABLE_STALE', 'Document, contract and edited display chapter table differ')
        ids = [r['chapter_id'] for r in table]
        if len(ids) != len(set(ids)) or any(not r.get('label') or not r['source_start'] < r['source_end'] or
            not r['display_start'] < r['display_end'] for r in table) or any(a['source_end'] != b['source_start'] for a,b in zip(table,table[1:])):
            c.error('CHAPTER_TABLE_STALE', 'Chapter identities/ranges are invalid or discontinuous')
    except (KeyError, TypeError):
        c.error('CHAPTER_TABLE_STALE', 'Chapter table fields are incomplete')
        return c.result()
    nodes, chains = graph(doc)
    samples = expected_samples(table)
    for row in table:
        actual_ids = row.get('nav_node_ids', [])
        if not actual_ids or any(i not in nodes for i in actual_ids):
            c.error('NAV_TIME_MISMATCH', 'Chapter must bind real navigation groups/fills', row['chapter_id'])
            continue
        descendants = {i for target in actual_ids for i in nodes if target in chains[i]}
        fills = [nodes[i] for i in descendants if nodes[i].get('navigation', {}).get('kind') == 'progress-fill']
        labels = [nodes[i] for i in descendants if nodes[i].get('type') == 'text']
        if not labels or not any(n.get('text') == row['label'] for n in labels):
            c.error('NAV_CHOICE_IGNORED', 'Chapter label must be actual visible text', row['chapter_id'])
        if not req.get('allow_state_words', False) and any(re.search(r'已学|未学|当前|✓|✔|☑', str(n.get('text', ''))) for n in labels):
            c.error('NAV_CHOICE_IGNORED', 'Saved simple-label choice forbids status words or checkmarks', row['chapter_id'])
        if not fills:
            c.error('NAV_TIME_MISMATCH', 'Label motion/state metadata cannot replace a real progress fill', row['chapter_id'])
        for n in fills:
            nav = n['navigation']; width = nav.get('segment_width')
            if nav.get('chapter_id')!=row['chapter_id']:
                c.error('NAV_TIME_MISMATCH','Fill binds a different chapter identity',n['id'])
            a, z = n.get('startFrame', 0), n.get('endFrame', doc['sourceDurationFrames'])
            motions = [m for m in n.get('motion', []) if m.get('property') == 'width' and m.get('from') != m.get('to')]
            if not isinstance(width, (int,float)) or width <= 0:
                c.error('NAV_TIME_MISMATCH', 'Fill requires its actual full segment width', n['id'])
                continue
            if not motions and max(a,row['source_start']) < min(z,row['source_end']):
                c.error('NAV_TIME_MISMATCH', 'Active chapter fill lacks a genuine linear width operation', n['id'])
            for m in motions:
                expected_from=progress(row,display_frame(m['startFrame'],doc.get('holds',[]),doc.get('cuts',[])))*width
                expected_to=progress(row,display_frame(m['endFrame'],doc.get('holds',[]),doc.get('cuts',[])))*width
                if abs(m.get('from',0)-expected_from)>1e-5 or abs(m.get('to',0)-expected_to)>1e-5:
                    c.error('NAV_TIME_MISMATCH', 'Width operation endpoints disagree with the canonical edited chapter clock', n['id'])
                if m.get('ease', 'linear') != 'linear' or not a <= m['startFrame'] < m['endFrame'] <= z:
                    c.error('NAV_TIME_MISMATCH', 'Fill motion must be scoped, continuous and linear', n['id'])
            c.details.setdefault('expected_clip_progress',[]).append(dict(node_id=n['id'],chapter_id=row['chapter_id'],
                display_start=display_frame(a,doc.get('holds',[]),doc.get('cuts',[])),
                display_end=display_frame(z,doc.get('holds',[]),doc.get('cuts',[])),
                note='Expected display-clock function, not an actual runtime/pixel observation'))
    if purpose in ENCODED:
        observed=current_review(c, project, req.get('review'), doc, video, 'NAV_REVIEW_MISSING', samples)
        # Dedicated rectangular fills permit a bounded actual-pixel width measurement.
        # Unsupported paints/transforms stay unverified; a state receipt cannot replace pixels.
        import numpy as np
        from PIL import Image
        for observation in observed:
            f=observation.get('encoded_frame',observation.get('frame'))
            if f not in samples:continue
            sf=source_frame(f,doc.get('holds',[]),doc.get('cuts',[]))
            p=__import__('production_validation').path_in(project,observation.get('path'))
            if not p or not p.is_file():continue
            image=np.asarray(Image.open(p).convert('RGB')).astype(float)
            for chapter in table:
                for i,n in nodes.items():
                    if n.get('navigation',{}).get('kind')!='progress-fill' or n['navigation'].get('chapter_id')!=chapter['chapter_id'] or not visible(doc,nodes,chains,i,sf):continue
                    fill=n.get('fill','');ancestors=[_state(nodes[k],sf) for k in chains[i]]
                    if (not re.fullmatch(r'#[0-9a-fA-F]{6}',str(fill)) or any(a.get('rotation',0) or a.get('scaleX',1)!=1 or a.get('scaleY',1)!=1 or a.get('matrix') for a in ancestors)):
                        c.error('NAV_PIXEL_UNVERIFIED','Navigation paint/transform requires actual manual pixel observation',i);continue
                    x=round(sum(a.get('x',0) for a in ancestors));y=round(sum(a.get('y',0) for a in ancestors)+n.get('height',1)/2)
                    w=round(n['navigation']['segment_width']);color=np.array([int(fill[j:j+2],16) for j in (1,3,5)])
                    if x<0 or y<0 or y>=len(image) or x+w>image.shape[1]:
                        c.error('NAV_PIXEL_UNVERIFIED','Navigation is outside the encoded frame',i);continue
                    pixels=int((np.max(np.abs(image[y,x:x+w]-color),axis=1)<30).sum())
                    want=progress(chapter,f)*w
                    if abs(pixels-want)>3:
                        c.error('NAV_TIME_MISMATCH','Actual encoded navigation width differs from the display clock',i,frame=f,actual_pixels=pixels,expected_pixels=want)

    c.details.update(chapter_table=table, table_sha256=digest(table), required_encoded_frames=samples)
    return c.result()
