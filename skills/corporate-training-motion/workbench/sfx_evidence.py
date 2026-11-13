"""48 kHz calibrated source-presence evidence. Signal is never a listening review."""
import json
import subprocess
from pathlib import Path
import numpy as np
from production_validation import resolve_current_video, Check, load, path_in, sha, digest, ENCODED

RATE=48000


def decode(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ac','1','-ar',str(RATE),'-f','f32le','-'])
    return np.frombuffer(raw,dtype='<f4').astype(float)


def match(source, signal):
    """Normalized sliding matched filter; returned lag is measured, not a plan frame."""
    source=np.asarray(source,dtype=float);signal=np.asarray(signal,dtype=float)
    n=len(source)
    if not n or len(signal)<n or np.linalg.norm(source)<1e-10:
        return dict(score=0.,offset_sample=None)
    template=source-source.mean();norm=np.linalg.norm(template)
    if norm<1e-10:return dict(score=0.,offset_sample=None)
    size=1<<(len(signal)+n-2).bit_length()
    dot=np.fft.irfft(np.fft.rfft(signal,size)*np.fft.rfft(template[::-1],size),size)[n-1:len(signal)]
    sums=np.r_[0.,np.cumsum(signal)];squares=np.r_[0.,np.cumsum(signal*signal)]
    energy=np.maximum(0,squares[n:]-squares[:-n]-(sums[n:]-sums[:-n])**2/n)
    scores=dot/np.maximum(1e-12,np.sqrt(energy)*norm)
    best=int(np.argmax(scores))
    return dict(score=float(scores[best]),offset_sample=best)


def calibrate(source, positives, negatives):
    """Calibrate on current library signal/no-signal/narration/compression controls."""
    pos=[match(source,x) for x in positives];neg=[match(source,x) for x in negatives]
    low=min((x['score'] for x in pos),default=0);high=max((x['score'] for x in neg),default=1)
    return dict(ready=bool(pos and neg and low>high+.05),threshold=(low+high)/2,
                positive=pos,negative=neg,positive_floor=low,negative_ceiling=high,
                method='48k-mono-normalized-source-matched-filter/current-positive-negative-controls')


def inspect(project, doc, video, purpose, contract):
    c=Check('sfx');req=contract.get('requirements',{}).get('sfx',{})
    if contract.get('choices',{}).get('sound_effects')=='off':
        return c.result()
    if req.get('required') is False:c.error('SFX_NOT_IN_ENCODE','Enabled sound choice cannot be disabled by a local required flag')
    if purpose in {'script','design','storyboard'}:
        c.details['applicability']='Encoded source-presence is required after mixing, not during script/design'
        return c.result()
    plan=load(project,req.get('plan_path'));events=plan.get('events',[])
    assets={a.get('id'):a for a in req.get('assets',[])}
    palette=req.get('palette','teaching-native-v1')
    native=Path(__file__).resolve().parent.parent/'assets/sfx'/palette/'palette.json'
    catalog=json.loads(native.read_text()) if native.is_file() else {}
    selected={a['id']:a for a in catalog.get('assets',[])}
    if not events:c.error('SFX_NOT_IN_ENCODE','Enabled native sound plan has no events')
    receipt=load(project,req.get('receipt',req.get('receipt_path')))
    for key in ['dry','sfx_stem','mix']:
        p=path_in(project,receipt.get(key+'_path'))
        if not p or sha(p)!=receipt.get(key+'_sha256'):
            c.error('SFX_INPUT_STALE','Current dry/stem/mix receipt is absent or stale',key)
    if receipt.get('plan_sha256')!=digest(plan) or receipt.get('narration_timeline_changed') is not False:
        c.error('SFX_INPUT_STALE','Mix receipt must bind the exact persisted event plan and unchanged dry timeline')
    actual_mix=path_in(project,doc.get('media',{}).get('audio'))
    if sha(actual_mix)!=receipt.get('mix_sha256'):
        c.error('SFX_INPUT_STALE','Document does not use this exact current mix output')
    if c.errors:return c.result()
    encoded=decode(resolve_current_video(project,video));stem=decode(path_in(project,receipt['sfx_stem_path']))
    if not len(stem) or np.max(np.abs(stem),initial=0)<1e-7:
        c.error('SFX_NOT_IN_ENCODE','Actual independent sound stem has no signal')
    calibration=load(project,req.get('calibration'))
    signal_results=[]
    for e in events:
        eid=e.get('id');asset=assets.get(e.get('asset_id'),{})
        frozen=selected.get(e.get('asset_id'),{})
        p=path_in(project,asset.get('path'))
        canonical=(native.parent/str(frozen.get('path',''))).resolve()
        if p is None and asset.get('path') and Path(asset['path']).resolve()==canonical:p=canonical
        source_sha=sha(p)
        if not p or source_sha!=e.get('source_sha256') or source_sha!=asset.get('sha256') or source_sha!=frozen.get('sha256'):
            c.error('SFX_SOURCE_CHANGED','Source must be the exact selected library asset, not a same-name substitute',eid);continue
        source=decode(p);kind=e.get('trigger_kind');sample=e.get('source_'+str(kind)+'_sample')
        measured=(int(np.argmax(np.abs(source))) if kind=='peak' else
                  int(np.flatnonzero(np.abs(source)>np.max(np.abs(source))*.02)[0]) if kind=='onset' and np.max(np.abs(source),initial=0)>0 else None)
        if measured is None or sample!=measured or not e.get('visual_event_id') or not e.get('group_id') or not isinstance(e.get('gain'),(int,float)):
            c.error('SFX_BINDING_INVALID','Event requires actual source onset/peak sample, visual event, gain and semantic group',eid);continue
        rows=next((x for x in calibration.get('assets',[]) if x.get('source_sha256')==source_sha),{})
        positive=rows.get('positive_controls',[]);negative=rows.get('negative_controls',[])
        classes={x.get('kind') for x in positive+negative}
        if not {'source-present','compressed-present','silence','narration-only','compressed-absent'}<=classes:
            c.error('SFX_PRESENCE_UNCERTAIN','Calibration lacks source/silence/narration/compression positive and negative controls',eid);continue
        arrays=[]
        for item in positive+negative:
            q=path_in(project,item.get('path'))
            if not q or sha(q)!=item.get('sha256'):
                c.error('SFX_CALIBRATION_STALE','Calibration control bytes changed',eid);break
            arrays.append(decode(q))
        else:
            cal=calibrate(source,arrays[:len(positive)],arrays[len(positive):])
            if not cal['ready']:
                c.error('SFX_PRESENCE_UNCERTAIN','Current source cannot be separated from actual negative controls',eid);continue
            # Declared before mixing; never expand tolerance to accommodate the observed error.
            timing=e.get('timing_contract',{})
            if not timing.get('declared_before_mix') or not timing.get('tolerance_basis') or type(timing.get('measurement_error_samples')) is not int:
                c.error('SFX_TIMING_CONTRACT_MISSING','Target and calibrated tolerance must be declared before mixing',eid);continue
            fps=doc['fps'];frame=e.get('peak_or_onset_frame')
            if type(frame)is not int:c.error('SFX_BINDING_INVALID','Target frame missing',eid);continue
            expected=frame*RATE/fps
            expected_controls=[r.get('expected_offset_sample') for r in positive]
            if any(type(v)is not int for v in expected_controls):
                c.error('SFX_PRESENCE_UNCERTAIN','Calibration controls require their actual authored source positions',eid);continue
            measured_error=max(abs(r['offset_sample']-target) for r,target in zip(cal['positive'],expected_controls))
            error=timing['measurement_error_samples']
            if error!=measured_error:
                c.error('SFX_TIMING_CONTRACT_MISMATCH','Declared measurement tolerance must equal the current calibrated error, never a post-hoc wider window',eid,calibrated_error_samples=measured_error);continue
            # Search a bounded context, but accept only the exact quantization interval + calibrated error.
            left=max(0,int(expected-sample-RATE*.25));right=min(len(encoded),int(expected-sample+len(source)+RATE*.25))
            found=match(source,encoded[left:right]);actual=(left+found['offset_sample']+sample if found['offset_sample'] is not None else None)
            delta=None if actual is None else actual-expected
            present=found['score']>=cal['threshold']
            allowed=RATE/(2*fps)+error
            status='detected' if present and delta is not None and abs(delta)<=allowed else 'missing' if not present else 'offset'
            signal_results.append(dict(id=eid,status=status,match=found,threshold=cal['threshold'],actual_sample=actual,
                                       offset_samples=delta,allowed_samples=allowed,calibration=cal))
            if not present:c.error('SFX_NOT_IN_ENCODE','Exact library source is not detected in current encoded audio',eid,score=found['score'])
            elif abs(delta)>allowed:c.error('SFX_TIME_MISMATCH','Encoded source landmark falls outside predeclared frame quantization/calibration error',eid,offset_samples=delta,allowed_samples=allowed)
    review=load(project,req.get('review'))
    if review.get('video_sha256')!=sha(resolve_current_video(project,video)) or review.get('mix_sha256')!=receipt.get('mix_sha256'):
        c.error('SFX_EVIDENCE_STALE','Audio review must bind current video and mix bytes')
    audible=review.get('listening',{})
    if (audible.get('capability')!='actual-normal-speed-audio' or audible.get('speed')!=1 or not audible.get('actor') or
            not audible.get('method') or not {e['id'] for e in events}<={r.get('event_id') for r in audible.get('observations',[]) if all(r.get(k) for k in ['audibility','speech_interference','tail','density','weight','av_landing'])}):
        c.error('AUDIO_REVIEW_UNVERIFIED','Signal/source detection does not prove audibility, naturalness, density or AV perception')
    groups={}
    for e in events:
        if e.get('equal_options'):groups.setdefault(e.get('group_id'),[]).append((e.get('source_sha256'),e.get('gain')))
    for gid,values in groups.items():
        if len(set(values))>1:c.error('SFX_OPTION_WEIGHT_MISMATCH','Equal options must use the same source/gain',gid)
    c.details.update(signal_results=signal_results,sample_rate=RATE,hearing_is_separate=True)
    return c.result()


def mix_from_dry(project, dry_path, plan_path, assets, stem_path, mix_path, fps):
    """Build a bounded 48k mono stem/mix from frozen source landmarks.

    Does not alter dry voice timing, add silence, approve listening, or select a library.
    Events extending outside the narration are rejected rather than silently clipped.
    """
    from production_validation import digest
    p=Path(project).resolve();dry=path_in(p,dry_path);planfile=path_in(p,plan_path)
    plan=load(p,plan_path);dry_samples=decode(dry);stem=np.zeros(len(dry_samples))
    if not planfile or not planfile.is_file():raise ValueError('SFX_TIMING_CONTRACT_MISSING: persist the plan before mixing')
    sources=[]
    for event in plan.get('events',[]):
        if event.get('silence_reason'):continue
        asset=next((a for a in assets if a.get('id')==event.get('asset_id')), {})
        file=path_in(p,asset.get('path'))
        if not file or sha(file)!=event.get('source_sha256') or sha(file)!=asset.get('sha256'):
            raise ValueError('SFX_SOURCE_CHANGED: source bytes differ')
        source=decode(file);kind=event.get('trigger_kind');landmark=event.get('source_'+str(kind)+'_sample')
        actual=int(np.argmax(np.abs(source))) if kind=='peak' else int(np.flatnonzero(np.abs(source)>np.max(np.abs(source))*.02)[0]) if kind=='onset' else None
        if landmark!=actual:raise ValueError('SFX_BINDING_INVALID: source landmark differs')
        start=round(event['peak_or_onset_frame']*RATE/fps)-landmark
        if start<0 or start+len(source)>len(stem):raise ValueError('SFX_TAIL_OUT_OF_RANGE: preserve narration length and explicitly redesign placement')
        stem[start:start+len(source)]+=source*event['gain']
        sources.append(dict(id=event['id'],asset_id=event['asset_id'],source_sha256=sha(file),gain=event['gain'],start_sample=start,landmark_sample=landmark))
    mixed=dry_samples+stem
    if np.max(np.abs(mixed),initial=0)>1:raise ValueError('SFX_CLIPPING: reduce authored gain; no automatic voice normalization')
    for name,samples in [(stem_path,stem),(mix_path,mixed)]:
        out=path_in(p,name)
        if out is None:raise ValueError('SFX_OUTPUT_OUTSIDE_PROJECT')
        out.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(RATE),'-ac','1','-i','pipe:0','-c:a','pcm_s24le',str(out)],input=samples.astype('<f4').tobytes(),check=True,capture_output=True)
    return dict(plan_path=str(planfile.relative_to(p)),plan_sha256=digest(plan),dry_path=str(dry.relative_to(p)),dry_sha256=sha(dry),
                sfx_stem_path=stem_path,sfx_stem_sha256=sha(path_in(p,stem_path)),mix_path=mix_path,mix_sha256=sha(path_in(p,mix_path)),
                sample_rate=RATE,samples=len(dry_samples),source_events=sources,narration_timeline_changed=False,hearing_review=False)
