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

PALETTE='natural-ui-v1'
RATE=48000
ROLES={'click':(.10,'轻触点击'),'build':(.30,'模块构建落位'),'move':(.34,'平滑移动'),
       'zoom-in':(.30,'放大推进'),'zoom-out':(.30,'缩小退回'),'appear':(.18,'轻盈出现'),
       'disappear':(.18,'轻盈消失'),'rotate':(.46,'转动归位'),'grow':(.38,'增长展开'),
       'shrink':(.32,'收拢减少'),'reveal':(.23,'局部揭示'),'focus':(.10,'选中聚焦'),
       'confirm':(.32,'完成确认'),'transition':(.40,'切换交接'),'warning':(.20,'轻柔提醒')}
ALIASES={'enter':'appear','zoom_in':'zoom-in','zoom_out':'zoom-out','growth':'grow','construct':'build'}
SOURCES={'click':['click_001','click_002','click_003'],'build':['drop_001','drop_002','drop_003'],
         'move':['scroll_001','scroll_002','scroll_003'],'zoom-in':['maximize_001','maximize_002','maximize_003'],
         'zoom-out':['minimize_001','minimize_002','minimize_003'],'appear':['open_001','open_002','open_003'],
         'disappear':['close_001','close_002','close_003'],'rotate':['switch_005','switch_006','switch_007'],
         'grow':['maximize_006','maximize_007','maximize_008'],'shrink':['minimize_006','minimize_007','minimize_008'],
         'reveal':['pluck_001','pluck_002','open_004'],'focus':['select_001','select_002','select_003'],
         'confirm':['confirmation_001','confirmation_002','confirmation_003'],
         'transition':['switch_001','switch_002','switch_003'],'warning':['error_001','error_002','error_003']}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_root():return Path(__file__).resolve().parents[1]/'assets/sfx/kenney-interface-source'


def synth(role,variant):
    """Curate licensed interface recordings; no procedural noise generator."""
    source=source_root()/'Audio'/(SOURCES[role][variant]+'.ogg')
    duration=ROLES[role][0]*(.96+.05*variant)
    filters=f'highpass=f=100,lowpass=f=5200,atrim=duration={duration},afade=t=in:d=0.003'
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-af',filters,'-f','f32le','-ac','1','-ar',str(RATE),'-'])
    a=array('f');a.frombytes(raw)
    # Trim codec padding and real silence before setting action alignment.
    audible=[i for i,v in enumerate(a) if abs(v)>.0005]
    if not audible:raise ValueError('Interface source is silent: '+str(source))
    a=list(a[max(0,audible[0]-144):min(len(a),audible[-1]+481)])
    if role=='build':
        second=[v*.48 for v in a];offset=round(.085*RATE);combined=[0.]*(max(len(a),offset+len(second)))
        for i,v in enumerate(a):combined[i]+=v
        for i,v in enumerate(second):combined[offset+i]+=v
        a=combined
    if role=='rotate':
        # Three small detents suggest turning, without a sustained rushing bed.
        core=a[:min(len(a),int(.09*RATE))];combined=[0.]*int(.32*RATE)
        for at,weight in [(0,.58),(.10,.78),(.21,1.)]:
            for i,v in enumerate(core):combined[round(at*RATE)+i]+=v*weight
        a=combined
    peak=max(abs(v) for v in a);scale=(.145-variant*.008)/peak
    fade=max(1,min(int(.012*RATE),len(a)//4))
    return [v*scale*min(1,i/144,(len(a)-1-i)/fade) for i,v in enumerate(a)]


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
                sha256=sha(path),peakSample=max(range(len(samples)),key=lambda i:abs(samples[i])),samples=len(samples),
                source='kenney-interface-source/Audio/'+SOURCES[role][variant]+'.ogg',license='CC0-1.0'))
    catalog=dict(id=PALETTE,sampleRate=RATE,channels=1,source='Kenney Interface Sounds; curated EQ, trims and tactile sequences; CC0-1.0',
        selection='semantic role; stable per course and cue; no immediate same-role repeat',assets=assets)
    (destination/'palette.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    return catalog


def palette_root(project=None,palette=PALETTE):
    if palette not in [PALETTE,'soft-tactile-v1']:raise ValueError('未知音效库 '+str(palette))
    local=Path(project)/'audio/sfx'/palette if project else None
    if local and (local/'palette.json').is_file():return local
    installed=Path(__file__).resolve().parents[1]/'assets/sfx'/palette
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2]/'audio/sfx'/palette


def catalog(project=None,palette=PALETTE):return json.loads((palette_root(project,palette)/'palette.json').read_text())


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
    palette=spec.get('palette',PALETTE)
    source=palette_root(p,palette);library=p/'audio/sfx'/palette
    if source.resolve()!=library.resolve():shutil.copytree(source,library,dirs_exist_ok=True)
    data=catalog(p,palette);by_role={role:[a for a in data['assets'] if a['role']==role] for role in {a['role'] for a in data['assets']}}
    state=read(p/'course-state.json') if (p/'course-state.json').is_file() else {}
    identity=state.get('course_id',p.parent.name)
    events=spec.get('events',[]);ids=set();selected=[];skipped=[];last={}
    for e in events:
        if not isinstance(e.get('id'),str) or not e['id'] or e['id'] in ids:raise ValueError('音效事件ID缺失或重复')
        ids.add(e['id'])
        if type(e.get('frame')) is not int or not 0<=e['frame']<doc['sourceDurationFrames']:raise ValueError('音效事件须使用课程源时间轴内的整数frame')
        if palette==PALETTE:e['role']=ALIASES.get(e.get('role'),e.get('role'))
        if e.get('align','peak') not in ['start','peak','end']:raise ValueError('align须为start/peak/end')
        if e.get('role') not in [*by_role,'none']:raise ValueError('未知音效角色 '+str(e.get('role')))
        gain=e.get('gainDb',0)
        if type(gain) not in [int,float] or not math.isfinite(gain) or not -18<=gain<=6:raise ValueError('音效gainDb须在-18到6之间')
    for e in sorted(events,key=lambda e:(e['frame'],e['id'])):
        role=e['role']
        if role=='none':skipped.append(dict(id=e['id'],reason='explicit silence'));continue
        variants=by_role[role];index=int(hashlib.sha256(f'{identity}:{role}:{e["id"]}'.encode()).hexdigest()[:8],16)%len(variants)
        if last.get(role)==index:index=(index+1)%len(variants)
        if e.get('assetId'):
            index=next((i for i,a in enumerate(variants) if a['id']==e['assetId']),-1)
            if index<0:raise ValueError('assetId与动作角色不一致')
        last[role]=index;a=variants[index];asset=safe(p,'audio/sfx/'+palette+'/'+a['path'])
        if sha(asset)!=a['sha256']:raise ValueError('音效素材已变更，未覆盖用户音效 '+a['id'])
        selected.append(dict(id=e['id'],frame=e['frame'],role=role,gainDb=e.get('gainDb',0),
            assetId=a['id'],path=str(asset.relative_to(p)),sha256=a['sha256'],peakSample=a['peakSample'],align=e.get('align','peak')))
    result=dict(schema='course-sfx/1',palette=palette,sampleRate=RATE,fps=doc['fps'],timeline_source=timeline_source,
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
        peak=round(e['frame']/timeline['fps']*RATE)
        offset={'start':0,'peak':e['peakSample'],'end':len(clip)-1}[e.get('align','peak')];start=peak-offset
        a=max(0,peak-int(.12*RATE))*2;b=min(count,peak+int(.12*RATE))*2
        voice_rms=math.sqrt(sum(x*x for x in base[a:b])/max(1,b-a))
        gain=10**(e['gainDb']/20)
        if voice_rms>.035:
            clip_rms=math.sqrt(sum((x/32768)**2 for x in clip)/max(1,len(clip)))
            gain=min(gain,voice_rms*.25/max(.0001,clip_rms))
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
        if changed.get('continuityPolicy',{}).get('required'):changed['media']['narration']=str(voice.relative_to(p))
        validate(changed,p);atomic(p/'workbench-history'/f'{doc["revision"]:06}.json',doc);atomic(p/'workbench.json',changed)
        receipt['boundRevision']=changed['revision']
    atomic(output.with_suffix('.json'),receipt)
    return receipt
