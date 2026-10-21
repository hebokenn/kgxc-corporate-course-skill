"""Decode exact action phases; sampling frequency must never dictate pacing."""
import subprocess


def balanced_sum(terms):
    if len(terms)==1:return terms[0]
    m=len(terms)//2
    return '('+balanced_sum(terms[:m])+'+'+balanced_sum(terms[m:])+')'


def decode_selected(video,frame_indices,width=424,height=160):
    import numpy as np
    indices=sorted(set(frame_indices))
    if not indices:return {}
    expression=balanced_sum(['eq(n,'+str(f)+')' for f in indices])
    command=['ffmpeg','-v','error','-i',str(video),'-vf',"select='"+expression+"',crop=1696:640:112:270,scale="+str(width)+':'+str(height)+',format=gray',
             '-fps_mode','vfr','-f','rawvideo','-']
    raw=subprocess.check_output(command);pictures=np.frombuffer(raw,dtype=np.uint8).reshape(-1,height,width)
    if len(pictures)!=len(indices):raise ValueError('实际动作帧解码数量不匹配')
    return dict(zip(indices,pictures))


def action_phase_audit(video,doc,first,last):
    import numpy as np
    from timeline import segments
    spans=[]
    for s in segments(dict(doc,holds=doc.get('holds',[]))):
        a=max(first,s['startFrame']);z=min(last,s['endFrame'])
        if a<z and s['kind']=='source':spans.append((a,z,s['sourceFrame']+a-s['startFrame']))
    requests=[];all_indices=set()
    for beat in doc.get('motionPlan',{}).get('beats',[]):
        if beat.get('kind','action')!='action':continue
        indices=[]
        for a,z,source_a in spans:
            x=max(source_a,beat['startFrame']);y=min(source_a+z-a,beat['endFrame'])
            if x>=y:continue
            # First, middle and last active frames include transient gestures and taps.
            for source in sorted({x,x+(y-x)//2,y-1}):indices.append(a+source-source_a-first)
        if not indices:continue
        indices=sorted(set(indices));all_indices.update(indices);requests.append((beat,indices))
    pictures=decode_selected(video,all_indices);proofs=[];failures=[]
    for beat,indices in requests:
        counts=[]
        for x,y in zip(indices,indices[1:]):
            delta=np.abs(pictures[x].astype(np.int16)-pictures[y].astype(np.int16));counts.append(int((delta>12).sum()) if delta.mean()>.01 else 0)
        changed=sum(c>10 for c in counts)
        proofs.append(dict(id=beat['id'],method='exact-encoded-action-phases',encodedFrames=indices,samplePairs=len(counts),changedPairs=changed,maximumChangedPixels=max(counts,default=0)))
        if len(indices)>1 and not changed:failures.append('成片主体未检测到所声明动作 '+beat['id'])
    return proofs,failures
