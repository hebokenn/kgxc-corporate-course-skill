"""Exact source spans and real audio-word enclosures; no nearest-cue fallback."""
from production_validation import resolve_current_video, Check, load, path_in, sha, graph, first_readable, visible, current_review, ENCODED

FORBIDDEN = {'nearest-caption', 'proportional', 'equal-split', 'fuzzy-first', 'segment-start', 'reading-clamp'}


def resolve(mapping, event):
    sid = event.get('segment_id', event.get('scene_id'))
    row = next((s for s in mapping.get('segments', []) if s.get('id') == sid), None)
    if not row:
        raise ValueError('missing source segment')
    text = row.get('narration', '')
    span = event.get('raw_span', [event.get('raw_start'), event.get('raw_end')])
    a, z = span if isinstance(span, list) and len(span) == 2 else (None, None)
    quote = event.get('quote', event.get('source_phrase'))
    if type(a) is not int or type(z) is not int or not 0 <= a < z <= len(text) or text[a:z] != quote:
        raise ValueError('quote and exact raw span differ')
    starts = [i for i in range(len(text)) if text.startswith(quote, i)]
    occurrence = event.get('occurrence')
    if type(occurrence) is not int or occurrence >= len(starts) or occurrence < 0 or starts[occurrence] != a:
        raise ValueError('explicit occurrence does not identify the selected source span')
    chars = [c for c in row.get('char_map', []) if c.get('raw_start', z) < z and c.get('raw_end', a) > a]
    covered = {i for c in chars for i in range(max(a, c['raw_start']), min(z, c['raw_end']))}
    if covered != set(range(a, z)) or any(c.get('alignment_kind') in FORBIDDEN or not c.get('word_ids') for c in chars):
        raise ValueError('source span lacks actual word coverage or uses an estimated fallback')
    word_ids = list(dict.fromkeys(w for c in chars for w in c['word_ids']))
    words = {w['word_id']: w for w in row.get('words', [])}
    if any(w not in words for w in word_ids):
        raise ValueError('actual word ids are missing')
    selected = [words[w] for w in word_ids]
    if any(w.get('alignment_kind') in FORBIDDEN or type(w.get('start_frame')) not in (int,float) or
           type(w.get('end_frame')) not in (int,float) or w['end_frame'] < w['start_frame'] for w in selected):
        raise ValueError('word envelope is invalid')
    return dict(start=min(w['start_frame'] for w in selected), end=max(w['end_frame'] for w in selected),
                word_ids=word_ids, raw_span=[a,z], occurrence=occurrence)


def inspect(project, doc, video, purpose, contract):
    c = Check('semantic')
    if purpose in {'script', 'design'}:
        c.details['applicability'] = 'no audio alignment required before narration exists'
        return c.result()
    data = load(project, contract.get('requirements', {}).get('direction', {}).get('semantic_alignment'))
    mapping = load(project, data.get('map_path', data.get('mapping')))
    if purpose=='storyboard' and not doc.get('media',{}).get('audio') and not data.get('audio_path'):
        c.details['applicability']='Narration not yet produced; exact audio alignment remains not_started for later media stage'
        return c.result()
    audio = path_in(project, data.get('audio_path'))
    if not audio or sha(audio) != data.get('audio_sha256') or mapping.get('audio_sha256') != data.get('audio_sha256'):
        c.error('SEMANTIC_AUDIO_STALE', 'Word map must bind the current actual narration audio')
    events = data.get('events', [])
    if not events:
        c.error('SEMANTIC_ANCHOR_MISSING', 'Actual source-word semantic events are missing')
    nodes, chains = graph(doc)
    fps = doc.get('fps', 30)
    evidence_frames = []
    for e in events:
        eid = e.get('semantic_event_id', e.get('id'))
        try:
            aligned = resolve(mapping, e)
        except (ValueError, KeyError, TypeError) as exc:
            c.error('SEMANTIC_ANCHOR_MISSING', str(exc), eid)
            continue
        f, end = e.get('trigger_frame'), e.get('result_frame')
        if (type(f) is not int or not aligned['start']-.5 <= f <= aligned['start']+.5 or
                type(end) is not int or end < f):
            c.error('SEMANTIC_TIME_MISMATCH', 'Trigger must use the actual selected word start (only integer rounding is allowed)', eid)
            continue
        anchor = e.get('semantic_anchor', {})
        if anchor.get('word_ids') != aligned['word_ids'] or anchor.get('raw_span') != aligned['raw_span']:
            c.error('SEMANTIC_BINDING_INVALID', 'Semantic anchor must preserve selected span and actual word identities', eid)
        # A technical cue can use a source-word intersection, never a nearby different cue.
        technical = e.get('technical_anchor')
        if technical:
            cue = next((x for x in doc.get('captions', []) if x.get('id') == technical.get('cueId')), {})
            from timeline import display_frame
            t = technical.get('atFrame'); phrase = technical.get('phrase', '')
            if (type(t) is not int or not aligned['start'] <= t <= aligned['end'] or not phrase or
                    phrase not in str(e.get('quote', e.get('source_phrase', ''))) or phrase not in cue.get('text', '') or
                    not cue.get('startFrame', 1) <= display_frame(t, doc.get('holds', []), doc.get('cuts', [])) < cue.get('endFrame', 0)):
                c.error('SEMANTIC_TECHNICAL_ANCHOR_INVALID', 'Technical proof must intersect the same source word and actual caption', eid)
        ids = e.get('node_ids', [])
        if not ids or any(i not in nodes for i in ids):
            c.error('SEMANTIC_OBJECT_MISSING', 'Semantic event has no actual current objects', eid)
            continue
        for i in e.get('new_value_node_ids', ids):
            first = first_readable(doc, nodes, chains, i)
            if first != f:
                c.error('SEMANTIC_FIELD_TIME_MISMATCH', 'First readable field does not match its own word trigger', eid,
                        node_id=i, first_readable_frame=first, trigger_frame=f)
        if e.get('result_node_ids'):
            try:
                result_alignment=resolve(mapping,e.get('result_anchor',{}))
                if not result_alignment['start']-.5<=end<=result_alignment['start']+.5:
                    raise ValueError('Result frame differs from its own actual word start')
            except (ValueError,KeyError,TypeError) as exc:
                c.error('SEMANTIC_RESULT_ANCHOR_MISSING',str(exc),eid)
        for i in e.get('result_node_ids', []):
            first = first_readable(doc, nodes, chains, i)
            if first != end:
                c.error('SEMANTIC_RESULT_TIME_MISMATCH', 'Result needs its own actual word anchor and readable frame', eid, node_id=i)
        if any(not visible(doc, nodes, chains, i, end) for i in e.get('proof_node_ids', ids)):
            c.error('SEMANTIC_PROOF_OBJECT_GONE', 'Proof references objects already hidden or removed', eid)
        read_end = e.get('reading_end_frame', end)
        if type(read_end) is int:
            evidence_frames += [max(0,f-1),f,(f+end)//2,end,read_end]
    covered={i for e in events for i in e.get('new_value_node_ids',e.get('node_ids',[]))}
    scaffolds=data.get('neutral_scaffolds',[])
    neutral={r.get('node_id') for r in scaffolds if r.get('reason')}
    unmapped=[i for i,n in nodes.items() if n.get('type')=='text' and n.get('role') not in
              {'title','caption','navigation','decoration','brand'} and i not in covered|neutral]
    if unmapped:c.error('SEMANTIC_FIELD_UNBOUND','Every new body field needs its own word binding or an explicit neutral scaffold reason',node_ids=unmapped)
    if purpose in ENCODED:
        mapping_out = data.get('encoded_mapping', {})
        if (mapping_out.get('verified') is not True or mapping_out.get('video_sha256') != sha(resolve_current_video(project, video)) or
                mapping_out.get('audio_sha256') != data.get('audio_sha256') or not mapping_out.get('method')):
            c.error('SEMANTIC_ENCODED_MAPPING_MISSING', 'Current encoded audio offset/frame mapping has not been measured')
        else:
            offset = mapping_out.get('display_frame_offset', 0)
            from timeline import display_frame
            checkpoints=mapping_out.get('source_checkpoints',[])
            if len(set(checkpoints))<3:
                c.error('SEMANTIC_ENCODED_MAPPING_MISSING','Measure actual beginning/middle/end voice checkpoints against the current encoded audio')
            measurements=[]
            for source_checkpoint in checkpoints:
                measured=measure_audio_mapping(audio,resolve_current_video(project,video),source_checkpoint,
                    display_frame(source_checkpoint,doc.get('holds',[]),doc.get('cuts',[])),fps,offset)
                measurements.append(measured)
                if measured['score']<.7 or measured['offset_error_samples'] is None:
                    c.error('SEMANTIC_ENCODED_MAPPING_UNCERTAIN','Actual voice window cannot establish a reliable timing match',source_checkpoint)
                elif abs(measured['offset_error_samples'])>48000/(2*fps):
                    c.error('SEMANTIC_ENCODED_TIME_MISMATCH','Measured encoded voice mapping exceeds integer-frame quantization',source_checkpoint,measurement=measured)
            c.details['actual_audio_mapping_measurements']=measurements
            mapped = [round(display_frame(f, doc.get('holds', []), doc.get('cuts', []))+offset) for f in evidence_frames]
            current_review(c, project, data.get('review'), doc, video, 'SEMANTIC_REVIEW_MISSING', mapped)
    c.details['events_checked'] = len(events)
    return c.result()


def measure_audio_mapping(source, encoded, source_frame, display_frame, fps, declared_offset_frames=0):
    """Measure a source voice window against encoded audio, in 48k sample space.

    This establishes a bounded timing checkpoint, never voice naturalness or hearing.
    """
    import subprocess
    import numpy as np
    from sfx_evidence import match, RATE
    def window(path,a,z):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-af',
            'aresample=48000,atrim=start_sample=%d:end_sample=%d'%(a,z),'-ac','1','-f','f32le','-'])
        return np.frombuffer(raw,dtype='<f4').astype(float)
    start=round(source_frame*RATE/fps);length=round(.3*RATE)
    target=(display_frame+declared_offset_frames)*RATE/fps
    left=max(0,round(target-.15*RATE));right=round(target+length+.15*RATE)
    template=window(source,start,start+length);signal=window(encoded,left,right)
    found=match(template,signal)
    actual=left+found['offset_sample'] if found['offset_sample'] is not None else None
    return dict(source_frame=source_frame,display_frame=display_frame,declared_offset_frames=declared_offset_frames,
                actual_start_sample=actual,expected_start_sample=target,offset_error_samples=None if actual is None else actual-target,
                score=found['score'],measurement_rate=RATE,window_samples=length,
                method='actual-source-voice-window/current-encoded-48k-sample-matched-timing; not listening')
