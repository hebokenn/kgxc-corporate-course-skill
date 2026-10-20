"""Deterministic tactile SFX, semantic variation and narration-preserving mixing."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import wave

PALETTE='soft-tactile-v1'
RATE=48000
ROLES={'enter':(.16,'柔和落位'), 'move':(.28,'轻空气位移'), 'reveal':(.23,'纸面展开'),
       'focus':(.13,'轻触聚焦'), 'confirm':(.30,'低柔双触'), 'transition':(.42,'宽缓空气过渡'),
       'warning':(.22,'低沉止步')}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def synth(role,variant):
    duration=ROLES[role][0]*(.94+.06*variant)
    rng=random.Random(f'{PALETTE}:{role}:{variant}');low=mid=0.;samples=[]
    for i in range(round(duration*RATE)):
        t=i/RATE;p=t/duration;n=rng.uniform(-1,1)
        low+=.06*(n-low);mid+=.25*(n-mid)
        if role in ['move','transition']:
            v=(mid-low*.6)*math.sin(math.pi*p)**2
        elif role=='reveal':
            v=(mid-low)*min(1,t/.012)*(1-p)**1.7*(.7+.3*math.sin(2*math.pi*(36+variant*9)*t)**2)
        else:
            v=0.
            for at,weight in ([(0,1),(.105,.60)] if role=='confirm' else [(0,1)]):
                d=t-at
                if d<0:continue
                f=(170 if role=='warning' else 260 if role=='focus' else 310)+variant*37
                body=.18*math.sin(2*math.pi*f*d)*math.exp(-d*42)
                v+=weight*min(1,d/.006)*math.exp(-d*(25 if role=='warning' else 35))*(low*1.8+mid*.24+body)
            v*=min(1,(duration-t)/.02)
        samples.append(v)
    scale=(.17-variant*.012)/max(abs(x) for x in samples)
    return [x*scale for x in samples]


def write_wav(path,samples,channels=1):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pcm=array('h',(round(max(-1,min(1,x))*32767) for x in samples))
    with wave.open(str(path),'wb') as w:
        w.setnchannels(channels);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(pcm.tobytes())


def build_palette(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);assets=[]
    for role in ROLES:
        for variant in range(3):
            samples=synth(role,variant);name=f'{role}-{variant+1}.wav';path=destination/name
            write_wav(path,samples)
            assets.append(dict(id=f'{role}-{variant+1}',role=role,label=ROLES[role][1],path=name,
                sha256=sha(path),peakSample=max(range(len(samples)),key=lambda i:abs(samples[i])),samples=len(samples)))
    catalog=dict(id=PALETTE,sampleRate=RATE,channels=1,source='original deterministic local foley synthesis',
        selection='semantic role; stable per course and cue; no immediate same-role repeat',assets=assets)
    (destination/'palette.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    return catalog


def palette_root(project=None):
    local=Path(project)/'audio/sfx'/PALETTE if project else None
    if local and (local/'palette.json').is_file():return local
    installed=Path(__file__).resolve().parents[1]/'assets/sfx'/PALETTE
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2]/'audio/sfx'/PALETTE


def catalog(project=None):return json.loads((palette_root(project)/'palette.json').read_text())


def project_path(course):
    p=Path(course).resolve();return p if (p/'workbench.json').is_file() else p/'project'


def source_timeline(project,spec_file=None):
    from backend import read,safe
    p=Path(project);doc=read(p/'workbench.json')
    if doc.get('status')!='draft':return doc,'workbench.json'
    candidates=[safe(p,spec_file)] if spec_file else [p/x for x in ['source/course-composition.json','source/composition.json','source/spec.json']]
    for path in candidates:
        if path.is_file():
            spec=read(path)
            if type(spec.get('sourceDurationFrames')) is int and spec['sourceDurationFrames']>0 and spec.get('fps',30)==30:
                return dict(sourceDurationFrames=spec['sourceDurationFrames'],fps=30),str(path.relative_to(p))
    raise ValueError('新课先在构图spec保存实际源时间轴，再准备音效；可用 --spec 指定课程内文件')


def make_plan(course,events_file,out=None,spec_file=None):
    from backend import read,atomic,safe
    p=project_path(course);doc,timeline_source=source_timeline(p,spec_file);spec=read(events_file)
    if spec.get('palette',PALETTE)!=PALETTE:raise ValueError('未知音效色板；保留用户另选音色，不能自行替换')
    source=palette_root(p);library=p/'audio/sfx'/PALETTE
    if source.resolve()!=library.resolve():shutil.copytree(source,library,dirs_exist_ok=True)
    data=catalog(p);by_role={role:[a for a in data['assets'] if a['role']==role] for role in ROLES}
    state=read(p/'course-state.json') if (p/'course-state.json').is_file() else {}
    identity=state.get('course_id',p.parent.name)
    events=spec.get('events',[]);ids=set();selected=[];skipped=[];last={}
    for e in events:
        if not isinstance(e.get('id'),str) or not e['id'] or e['id'] in ids:raise ValueError('音效事件ID缺失或重复')
        ids.add(e['id'])
        if type(e.get('frame')) is not int or not 0<=e['frame']<doc['sourceDurationFrames']:raise ValueError('音效事件须使用课程源时间轴内的整数frame')
        if e.get('role') not in [*ROLES,'none']:raise ValueError('未知音效角色 '+str(e.get('role')))
        gain=e.get('gainDb',0)
        if type(gain) not in [int,float] or not math.isfinite(gain) or not -18<=gain<=6:raise ValueError('音效gainDb须在-18到6之间')
    for e in sorted(events,key=lambda e:(e['frame'],e['id'])):
        role=e['role']
        if role=='none':skipped.append(dict(id=e['id'],reason='explicit silence'));continue
        variants=by_role[role];index=int(hashlib.sha256(f'{identity}:{role}:{e["id"]}'.encode()).hexdigest()[:8],16)%len(variants)
        if last.get(role)==index:index=(index+1)%len(variants)
        last[role]=index;a=variants[index];asset=safe(p,'audio/sfx/'+PALETTE+'/'+a['path'])
        if sha(asset)!=a['sha256']:raise ValueError('音效素材已变更，未覆盖用户音效 '+a['id'])
        selected.append(dict(id=e['id'],frame=e['frame'],role=role,gainDb=e.get('gainDb',0),
            assetId=a['id'],path=str(asset.relative_to(p)),sha256=a['sha256'],peakSample=a['peakSample']))
    result=dict(schema='course-sfx/1',palette=PALETTE,sampleRate=RATE,fps=doc['fps'],timeline_source=timeline_source,
        sourceDurationFrames=doc['sourceDurationFrames'],events=selected,skipped=skipped,
        listening='not yet reviewed in the course mix; no user acceptance inferred')
    target=safe(p,out or 'audio/sfx-plan.json');atomic(target,result)
    return dict(path=str(target.relative_to(p)),plan=result)


def mix(course,plan_file,narration,out,bind=False):
    from backend import read,atomic,safe,validate
    p=project_path(course);doc=read(p/'workbench.json');plan=read(plan_file)
    timeline,_=source_timeline(p,plan.get('timeline_source'))
    if plan.get('schema')!='course-sfx/1' or plan['sourceDurationFrames']!=timeline['sourceDurationFrames'] or plan['fps']!=timeline['fps']:raise ValueError('音效计划与当前课程源时间轴不一致')
    if bind and doc.get('status')=='draft':raise ValueError('草稿先将实际混音写入构图spec的media.audio再configure，不直接绑定未制作画布')
    voice=safe(p,narration);output=safe(p,out)
    if output.suffix.lower()!='.wav':raise ValueError('制作混音请输出WAV，视频导出时再编码AAC')
    if output==voice:raise ValueError('不能覆盖旁白或原始混音；请指定新输出')
    voice_hash=sha(voice)
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(voice),'-f','f32le','-ac','2','-ar',str(RATE),'-'])
    base=array('f');base.frombytes(raw);count=round(timeline['sourceDurationFrames']/timeline['fps']*RATE)
    if abs(len(base)//2-count)>RATE*.12:raise ValueError('实际旁白长度与课程源时间轴不一致')
    if len(base)<count*2:base.extend(array('f',[0.])*(count*2-len(base)))
    elif len(base)>count*2:del base[count*2:]
    track=array('f',[0.])*(count*2)
    for e in plan['events']:
        path=safe(p,e['path'])
        if sha(path)!=e['sha256']:raise ValueError('音效素材哈希已变化 '+e['assetId'])
        with wave.open(str(path),'rb') as w:
            if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(RATE,1,2):raise ValueError('音效须为48kHz单声道PCM16')
            clip=array('h');clip.frombytes(w.readframes(w.getnframes()))
        peak=round(e['frame']/timeline['fps']*RATE);start=peak-e['peakSample']
        a=max(0,peak-int(.12*RATE))*2;b=min(count,peak+int(.12*RATE))*2
        voice_rms=math.sqrt(sum(x*x for x in base[a:b])/max(1,b-a))
        gain=10**(e['gainDb']/20)*(.68 if voice_rms>.035 else 1.)
        for i,x in enumerate(clip):
            at=start+i
            if 0<=at<count:
                value=x/32768*gain;track[at*2]+=value;track[at*2+1]+=value
    combined=array('f',(a+b for a,b in zip(base,track)))
    peak=max((abs(x) for x in combined),default=0)
    if peak>.98:raise ValueError('混音会削波；降低相关音效gainDb后重混，不压低整段旁白')
    stem=output.with_name(output.stem+'-sfx.wav')
    if stem==voice:raise ValueError('音效分轨与旁白路径冲突')
    write_wav(stem,track,2);write_wav(output,combined,2)
    if sha(voice)!=voice_hash:raise ValueError('旁白源在混音期间变化，请重新核对')
    receipt=dict(palette=plan['palette'],narration=str(voice.relative_to(p)),narration_sha256=voice_hash,
        narration_source_unchanged=True,plan_sha256=sha(plan_file),mix=str(output.relative_to(p)),mix_sha256=sha(output),
        sfxStem=str(stem.relative_to(p)),peak=peak,duration=count/RATE,events=len(plan['events']),
        listening='technical mix only; listen for timbre, fatigue, speech masking and actual audibility')
    if bind:
        if read(p/'workbench.json')!=doc:raise ValueError('混音期间工程已更新；已保留新文件，未改工作台绑定')
        changed=json.loads(json.dumps(doc));changed['media']['audio']=str(output.relative_to(p));changed['revision']+=1
        validate(changed,p);atomic(p/'workbench-history'/f'{doc["revision"]:06}.json',doc);atomic(p/'workbench.json',changed)
        receipt['boundRevision']=changed['revision']
    atomic(output.with_suffix('.json'),receipt)
    return receipt
