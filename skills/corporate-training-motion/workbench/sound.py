"""Deterministic tactile SFX, semantic variation and narration-preserving mixing."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import wave
from fractions import Fraction
import uuid

PALETTE='teaching-native-v1'
NATURAL_PALETTE='natural-ui-v1'
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
    catalog=dict(id=NATURAL_PALETTE,sampleRate=RATE,channels=1,source='Kenney Interface Sounds; curated EQ, trims and tactile sequences; CC0-1.0',
        selection='semantic role; stable per course and cue; no immediate same-role repeat',assets=assets)
    (destination/'palette.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    return catalog


def palette_root(project=None,palette=PALETTE):
    if not isinstance(palette,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',palette):raise ValueError('无效音效库ID '+str(palette))
    local=Path(project)/'audio/sfx'/palette if project else None
    if local and (local/'palette.json').is_file():
        local.resolve().relative_to(Path(project).resolve())
        return local
    if palette not in [PALETTE,NATURAL_PALETTE,'soft-tactile-v1']:raise ValueError('未知音效库 '+str(palette))
    installed=Path(__file__).resolve().parents[1]/'assets/sfx'/palette
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2]/'audio/sfx'/palette


def catalog(project=None,palette=PALETTE):return json.loads((palette_root(project,palette)/'palette.json').read_text())


def project_path(course):
    p=Path(course).resolve();return p if (p/'workbench.json').is_file() else p/'project'


def source_timeline(project,spec_file=None):
    from backend import read,safe
    p=Path(project).resolve();doc=read(p/'workbench.json')
    if doc.get('status')!='draft':return doc,'workbench.json'
    candidates=[safe(p,spec_file)] if spec_file else [p/x for x in ['source/course-composition.json','source/composition.json','source/spec.json']]
    for path in candidates:
        if path.is_file():
            spec=read(path)
            fps=spec.get('fps',doc.get('fps',30))
            if type(spec.get('sourceDurationFrames')) is int and spec['sourceDurationFrames']>0 and type(fps) in [int,float] and math.isfinite(fps) and fps>0:
                return dict(spec,fps=fps),str(path.relative_to(p))
    raise ValueError('新课先在构图spec保存实际源时间轴，再准备音效；可用 --spec 指定课程内文件')


def make_plan(course,events_file,out=None,spec_file=None):
    from backend import read,atomic,safe
    p=project_path(course)
    if _execution_required(p):
        from render_input_guard import _locked,ensure_mutation_allowed
        with _locked(p):
            ensure_mutation_allowed(p,'sound.make_plan',dict(events=str(events_file),out=out,spec=spec_file))
            return _execution_make_plan(p,events_file,out,spec_file)
    doc,timeline_source=source_timeline(p,spec_file);spec=read(events_file)
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
        if palette in [PALETTE,NATURAL_PALETTE]:e['role']=ALIASES.get(e.get('role'),e.get('role'))
        if e.get('align','peak') not in ['start','peak','end']:raise ValueError('align须为start/peak/end')
        if e.get('role') not in [*by_role,'none']:raise ValueError('未知音效角色 '+str(e.get('role')))
        gain=e.get('gainDb',0)
        if type(gain) not in [int,float] or not math.isfinite(gain) or not -18<=gain<=6:raise ValueError('音效gainDb须在-18到6之间')
        if 'groupId' in e and (not isinstance(e['groupId'],str) or not e['groupId'].strip() or len(e['groupId'])>64):raise ValueError('音效groupId须为非空短文本')
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
        selected.append(dict(id=e['id'],frame=e['frame'],role=role,gainDb=e.get('gainDb',0)+a.get('gainDb',0),
            assetId=a['id'],path=str(asset.relative_to(p)),sha256=a['sha256'],peakSample=a['peakSample'],align=e.get('align','peak'),
            **({'groupId':e['groupId']} if 'groupId' in e else {})))
    groups={}
    for e in selected:
        if 'groupId' not in e:continue
        signature=(e['sha256'],e['gainDb'])
        if groups.setdefault(e['groupId'],signature)!=signature:raise ValueError('平等音效组须使用同一素材与音量 '+e['groupId'])
    result=dict(schema='course-sfx/1',palette=palette,sampleRate=RATE,fps=doc['fps'],timeline_source=timeline_source,
        sourceDurationFrames=doc['sourceDurationFrames'],events=selected,skipped=skipped,
        listening='not yet reviewed in the course mix; no user acceptance inferred')
    target=safe(p,out or 'audio/sfx-plan.json');atomic(target,result)
    return dict(path=str(target.relative_to(p)),plan=result)


def mix(course,plan_file,narration,out,bind=False):
    from backend import read,atomic,safe,validate
    p=project_path(course)
    if _execution_required(p):
        from render_input_guard import _locked,ensure_mutation_allowed
        with _locked(p):
            ensure_mutation_allowed(p,'sound.mix',dict(plan=str(plan_file),narration=narration,out=out,bind=bind))
            return _execution_mix(p,plan_file,narration,out,bind)
    doc=read(p/'workbench.json');plan=read(plan_file)
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
    track=array('f',[0.])*(count*2);prepared=[];group_gains={};group_sources={}
    for e in plan['events']:
        path=safe(p,e['path'])
        if sha(path)!=e['sha256']:raise ValueError('音效素材哈希已变化 '+e['assetId'])
        with wave.open(str(path),'rb') as w:
            channels=w.getnchannels()
            if w.getframerate()!=RATE or channels not in [1,2] or w.getsampwidth()!=2:raise ValueError('音效须为48kHz单声道或立体声PCM16')
            clip=array('h');clip.frombytes(w.readframes(w.getnframes()))
        frames=len(clip)//channels
        peak=round(e['frame']/timeline['fps']*RATE)
        offset={'start':0,'peak':e['peakSample'],'end':frames-1}[e.get('align','peak')];start=peak-offset
        a=max(0,peak-int(.12*RATE))*2;b=min(count,peak+int(.12*RATE))*2
        voice_rms=math.sqrt(sum(x*x for x in base[a:b])/max(1,b-a))
        gain=10**(e['gainDb']/20)
        if voice_rms>.035:
            clip_rms=math.sqrt(sum((x/32768)**2 for x in clip)/max(1,len(clip)))
            gain=min(gain,voice_rms*.25/max(.0001,clip_rms))
        if 'groupId' in e:
            group=e['groupId'];signature=(e['sha256'],e['gainDb'])
            if group_sources.setdefault(group,signature)!=signature:raise ValueError('平等音效组须使用同一素材与音量 '+group)
            group_gains[group]=min(group_gains.get(group,gain),gain)
        prepared.append((e,clip,channels,frames,start,gain))
    applied=[]
    for e,clip,channels,frames,start,gain in prepared:
        if 'groupId' in e:gain=group_gains[e['groupId']]
        applied.append(dict(id=e['id'],assetId=e['assetId'],gainDb=20*math.log10(max(gain,1e-12)),**({'groupId':e['groupId']} if 'groupId' in e else {})))
        for i in range(frames):
            at=start+i
            if 0<=at<count:
                track[at*2]+=clip[i*channels]/32768*gain
                track[at*2+1]+=clip[i*channels+(channels-1)]/32768*gain
    combined=array('f',(a+b for a,b in zip(base,track)))
    peak=max((abs(x) for x in combined),default=0)
    if peak>.98:raise ValueError('混音会削波；降低相关音效gainDb后重混，不压低整段旁白')
    stem=output.with_name(output.stem+'-sfx.wav')
    if stem==voice:raise ValueError('音效分轨与旁白路径冲突')
    write_wav(stem,track,2);write_wav(output,combined,2)
    if sha(voice)!=voice_hash:raise ValueError('旁白源在混音期间变化，请重新核对')
    receipt=dict(execution_policy='legacy-candidate-only',formal_release_eligible=False,palette=plan['palette'],narration=str(voice.relative_to(p)),narration_sha256=voice_hash,
        narration_source_unchanged=True,plan_sha256=sha(plan_file),mix=str(output.relative_to(p)),mix_sha256=sha(output),
        sfxStem=str(stem.relative_to(p)),peak=peak,duration=count/RATE,events=len(plan['events']),appliedGains=applied,
        listening='technical mix only; listen for timbre, fatigue, speech masking and actual audibility')
    if bind:
        if read(p/'workbench.json')!=doc:raise ValueError('混音期间工程已更新；已保留新文件，未改工作台绑定')
        changed=json.loads(json.dumps(doc));changed['media']['audio']=str(output.relative_to(p));changed['revision']+=1
        if changed.get('continuityPolicy',{}).get('required'):changed['media']['narration']=str(voice.relative_to(p))
        validate(changed,p);atomic(p/'workbench-history'/f'{doc["revision"]:06}.json',doc);atomic(p/'workbench.json',changed)
        receipt['boundRevision']=changed['revision']
    atomic(output.with_suffix('.json'),receipt)
    return receipt


# Execution-required courses use this canonical path. Legacy files are not migrated.
def _execution_required(project):
    from backend import read
    file=Path(project)/'production-contract.json'
    return file.is_file() and read(file).get('execution_policy')=='required'


def _inside(project,raw):
    p=Path(project).resolve();file=(p/Path(raw)).resolve()
    if not file.is_relative_to(p):raise ValueError('SFX_PATH_OUTSIDE_PROJECT: '+str(raw))
    return file


def _object(project,value):
    from backend import read
    return value if isinstance(value,dict) else read(_inside(project,value)) if value else {}


def _basis(doc):
    from production_validation import digest
    return digest({k:doc.get(k) for k in ['sourceDurationFrames','fps','scenes','sceneGraph','motionPlan','narrationLinks','holds','cuts','captions','fields']})


def _visual_map(project,doc,contract):
    result={}
    def walk(items):
        for node in items:
            yield node
            yield from walk(node.get('children',[]))
    nodes={n.get('id'):n for n in walk(doc.get('sceneGraph',{}).get('nodes',[]))};node_ids=set(nodes)
    def put(row,identifier,trigger,result_frame,landing=None):
        targets=row.get('node_ids',row.get('objectIds',row.get('target_node_ids',[])))
        if not identifier or not targets or any(i not in node_ids for i in targets):return
        from production_validation import changed
        def activity(node):
            return (changed(node,trigger or 0,(result_frame or trigger or 0)+1) or node.get('startFrame') in {trigger,result_frame,landing} or
                    any(max(trigger or 0,e.get('startFrame',0))<min((result_frame or trigger or 0)+1,e.get('endFrame',0)) for e in node.get('effects',[])))
        if not any(activity(nodes[i]) for i in targets):return
        values={'trigger':trigger,'result':result_frame,'landing':landing if landing is not None else result_frame}
        if identifier in result and result[identifier]!=values:raise ValueError('SFX_VISUAL_BINDING_AMBIGUOUS: '+identifier)
        result[identifier]=values
    for row in doc.get('motionPlan',{}).get('beats',[]):
        if row.get('kind','action')=='action':put(row,row.get('id'),row.get('startFrame'),row.get('endFrame'))
    data=_object(project,contract.get('requirements',{}).get('direction',{}).get('semantic_alignment'))
    for row in data.get('events',[]):put(row,row.get('semantic_event_id',row.get('id')),row.get('trigger_frame'),row.get('result_frame'),row.get('stable_from_frame'))
    for row in contract.get('requirements',{}).get('emphasis',{}).get('events',[]):
        put(row,row.get('id'),row.get('animation_start'),row.get('animation_end'),row.get('landing_frame'))
    return result


def _decode_channels(path):
    """Decode without changing rate/channel count; require prepared 48k dry/source."""
    import numpy as np
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=sample_rate,channels','-of','json',str(path)]))
    stream=info.get('streams',[{}])[0];rate=int(stream.get('sample_rate',0));channels=stream.get('channels')
    if rate!=RATE or channels not in [1,2]:raise ValueError('SFX_AUDIO_FORMAT: prepare 48k mono/stereo audio explicitly; no implicit resampling or channel collapse')
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','f64le','-'])
    samples=np.frombuffer(raw,dtype='<f8').reshape(-1,channels)
    if not len(samples):raise ValueError('SFX_AUDIO_EMPTY')
    return samples.copy(),channels


def _landmarks(path):
    import numpy as np
    from sfx_evidence import decode
    mono=decode(path);peak=int(np.argmax(np.abs(mono)));level=np.max(np.abs(mono))
    if level<=1e-10:raise ValueError('SFX_SOURCE_SILENT')
    onset=int(np.flatnonzero(np.abs(mono)>level*.02)[0])
    return dict(peak=peak,onset=onset,samples=len(mono),analysis='actual 48k mono analysis of original preserved-channel source; onset = 2% of peak, not a hearing claim')


def _write_new_audio(path,samples,channels):
    import numpy as np
    path=Path(path)
    if path.exists():raise ValueError('SFX_OUTPUT_EXISTS: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-n','-f','f64le','-ar',str(RATE),'-ac',str(channels),'-i','pipe:0','-c:a','pcm_s24le',str(path)],
                   input=np.asarray(samples,dtype='<f8').tobytes(),capture_output=True,check=True)


def _prior_plan(project,contract):
    path=contract.get('requirements',{}).get('sfx',{}).get('plan_path')
    file=_inside(project,path) if path else None
    if file and file.is_file():return dict(path=file,raw=file.read_bytes(),value=json.loads(file.read_text()))
    return None


def _bind_execution(project,before,plan_path,plan,assets,extra=None,*,tool,prior_plan=None,outputs=None):
    from backend import atomic,read
    from production_validation import digest
    from handoff_contract import implementation_changed_fields
    p=Path(project);file=p/'production-contract.json'
    if read(file)!=before:raise ValueError('SFX_INPUT_CHANGED: contract changed; generated candidates retained, no binding overwritten')
    before_bytes=file.read_bytes();value=json.loads(json.dumps(before));req=value.setdefault('requirements',{}).setdefault('sfx',{})
    task_id=plan.get('task_id')
    if task_id:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',task_id):raise ValueError('SFX_TASK_INVALID')
        task=read(p/'work/handoffs'/(task_id+'.json'))
        if 'native_sfx' not in task.get('implementation_outputs',[]):raise ValueError('SFX_TASK_UNDECLARED: actual original dispatch must own native_sfx')
    identity=task_id or 'standalone-'+uuid.uuid4().hex
    folder=p/'work/implementation-bindings'/identity/uuid.uuid4().hex;folder.mkdir(parents=True)
    def snapshot(name,raw):
        target=folder/name
        with target.open('xb') as f:f.write(raw)
        return dict(path=str(target.relative_to(p)),sha256=sha(target))
    before_ref=snapshot('before-master.json',before_bytes)
    previous_ref=snapshot('before-plan.json',prior_plan['raw']) if prior_plan else None
    old_ids=sorted(e['id'] for e in prior_plan['value'].get('events',[])) if prior_plan else sorted(e['id'] for e in req.get('events',[]))
    new_ids={e['id'] for e in plan['events']}
    if not set(old_ids)<=new_ids:raise ValueError('SFX_EVENT_REMOVED: retain existing event IDs or obtain an explicit new scope')
    if req.get('palette',plan['palette'])!=plan['palette']:raise ValueError('SFX_SOURCE_CHANGED: preserve saved palette')
    req.update(assets=assets,plan_path=str(Path(plan_path).relative_to(p)),plan_sha256=digest(plan),plan_file_sha256=sha(plan_path),status='implemented_unverified',review={})
    if extra:req.update(extra)
    atomic(file,value)
    after_ref=snapshot('after-master.json',file.read_bytes());plan_ref=snapshot('after-plan.json',Path(plan_path).read_bytes())
    refs=[]
    for raw in dict.fromkeys([str(plan_path),*(outputs or [])]):
        output=_inside(p,raw)
        if output==file:raise ValueError('SFX_BINDING_OUTPUT_INVALID: master is never a returned output')
        refs.append(dict(path=str(output.relative_to(p)),sha256=sha(output)))
    receipt=dict(schema='course-implementation-binding/1',kind='native_sfx',tool=tool,task_id=task_id,
        tool_source=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),before_master=before_ref,after_master=after_ref,before_plan=previous_ref,after_plan=plan_ref,
        old_event_ids=old_ids,outputs=refs,changed_fields=implementation_changed_fields(before,value),status='implemented_unverified')
    target=folder/'binding-receipt.json';atomic(target,receipt)
    return dict(contract=value,binding=dict(path=str(target.relative_to(p)),sha256=sha(target)))


def _execution_make_plan(project,events_file,out,spec_file):
    from backend import read,atomic
    from production_validation import digest
    from timeline import display_frame,segments
    p=Path(project);contract=read(p/'production-contract.json')
    if contract.get('choices',{}).get('sound_effects') not in {'native','on','enabled'}:
        raise ValueError('SFX_CHOICE_UNRECORDED: save the actual selected sound choice before planning')
    prior=_prior_plan(p,contract)
    doc,timeline_source=source_timeline(p,spec_file);fps=doc.get('fps')
    if type(fps) not in [int,float] or not math.isfinite(fps) or fps<=0:raise ValueError('SFX_FPS_INVALID')
    event_path=_inside(p,events_file);spec=read(event_path);palette=spec.get('palette',contract.get('requirements',{}).get('sfx',{}).get('palette',PALETTE))
    expected_palette=contract.get('requirements',{}).get('sfx',{}).get('palette',PALETTE)
    if palette!=expected_palette:raise ValueError('SFX_SOURCE_CHANGED: event palette differs from the saved selection')
    source=palette_root(p,palette);data=catalog(p,palette);role_assets={}
    for a in data['assets']:role_assets.setdefault(a['role'],[]).append(a)
    visual=_visual_map(p,doc,contract);ids=set();selected=[];skipped=[]
    spans=segments(dict(doc,holds=doc.get('holds',[]),cuts=doc.get('cuts',[])))
    for original in spec.get('events',[]):
        e=dict(original);eid=e.get('id');frame=e.get('source_frame',e.get('frame',e.get('peak_or_onset_frame')))
        if not isinstance(eid,str) or not eid or eid in ids:raise ValueError('SFX_EVENT_ID_INVALID')
        ids.add(eid)
        if type(frame)is not int or not 0<=frame<doc['sourceDurationFrames']:raise ValueError('SFX_TIME_MISMATCH: source frame outside actual timeline')
        if e.get('align') not in [None,'peak','onset']:raise ValueError('SFX_LANDMARK_REQUIRED: file start/end alignment is not an actual onset/peak landmark')
        vid=e.get('visual_event_id');kind=e.get('trigger_kind',e.get('align','peak'));phase=e.get('visual_phase','result' if kind=='peak' else 'trigger')
        if kind not in {'peak','onset'} or not vid or vid not in visual or phase not in visual[vid] or visual[vid][phase]!=frame:
            raise ValueError('SFX_VISUAL_BINDING_MISSING: explicit real event and exact trigger/result/landing frame required for '+eid)
        if not any(s['kind']=='source' and s['sourceFrame']<=frame<s['sourceFrame']+s['endFrame']-s['startFrame'] for s in spans):
            raise ValueError('SFX_VISUAL_EVENT_REMOVED: source event was cut from playback')
        group=e.get('group_id',e.get('groupId'))
        if not isinstance(group,str) or not group.strip():raise ValueError('SFX_GROUP_MISSING: semantic sound group required')
        role=ALIASES.get(e.get('role'),e.get('role'))
        if role=='none':
            if not e.get('silence_reason'):raise ValueError('SFX_SILENCE_REASON_MISSING')
            skipped.append(dict(id=eid,visual_event_id=vid,source_frame=frame,reason=e['silence_reason']));continue
        variants=role_assets.get(role,[])
        if not variants:raise ValueError('SFX_ROLE_INVALID: '+str(role))
        aid=e.get('asset_id',e.get('assetId'));asset=next((a for a in variants if not aid or a['id']==aid),None)
        if not asset:raise ValueError('SFX_SOURCE_CHANGED: asset does not implement the chosen role')
        file=source/asset['path']
        if sha(file)!=asset['sha256']:raise ValueError('SFX_SOURCE_CHANGED: frozen library bytes changed')
        landmarks=_landmarks(file)
        gain=e.get('gain',10**((e.get('gainDb',0)+asset.get('gainDb',0))/20))
        if type(gain) not in [int,float] or not math.isfinite(gain) or not 0<gain<=4:raise ValueError('SFX_GAIN_INVALID')
        rel='audio/sfx/'+palette+'/'+asset['path']
        selected.append(dict(id=eid,asset_id=asset['id'],source_sha256=asset['sha256'],visual_event_id=vid,visual_phase=phase,
            trigger_kind=kind,source_peak_sample=landmarks['peak'],source_onset_sample=landmarks['onset'],source_frame=frame,
            peak_or_onset_frame=display_frame(frame,doc.get('holds',[]),doc.get('cuts',[])),gain=gain,group_id=group,equal_options=e.get('equal_options',False),
            source_landmark_method=landmarks['analysis'],timing_contract=dict(declared_before_mix=False,measurement_error_samples=None,
              tolerance_basis='integer-frame quantization plus measured current source/voice/AAC controls; calibration pending before mixing'),
            # Compatibility aliases remain read-only views of the same event.
            frame=frame,role=role,gainDb=20*math.log10(gain),assetId=asset['id'],path=rel,sha256=asset['sha256'],peakSample=landmarks['peak'],align=kind,
            groupId=group))
    if not selected:raise ValueError('SFX_PLAN_EMPTY: enabled sound requires actual events or an explicit changed selection')
    _equal_groups(selected)
    target=_inside(p,out or 'audio/sfx-plan.json')
    if target.exists():raise ValueError('SFX_OUTPUT_EXISTS: preserve the prior plan and choose a new --out')
    library=p/'audio/sfx'/palette
    # Never overwrite a changed copied source or private library.
    for file in source.rglob('*'):
        if file.is_file():
            dest=library/file.relative_to(source)
            if dest.exists() and sha(dest)!=sha(file):raise ValueError('SFX_SOURCE_CHANGED: preserve edited asset '+str(dest))
    for file in source.rglob('*'):
        if file.is_file():
            dest=library/file.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():shutil.copy2(file,dest)
    assets=[dict(a,path=str((library/a['path']).relative_to(p))) for a in data['assets']]
    plan=dict(task_id=spec.get('task_id'),schema='course-sfx/1',execution_schema='course-sfx-execution/1',execution_policy='required',palette=palette,sampleRate=RATE,
              fps=fps,sourceDurationFrames=doc['sourceDurationFrames'],timeline_source=timeline_source,timeline_basis_sha256=_basis(doc),
              input_events_path=str(event_path.relative_to(p)),input_events_sha256=sha(event_path),events=selected,skipped=skipped,
              preparation_state='awaiting-current-dry-calibration',listening='unverified; technical preparation is not user acceptance')
    atomic(target,plan);bound=_bind_execution(p,contract,target,plan,assets,tool='sound.make_plan',prior_plan=prior,outputs=[str(p/a['path']) for a in assets])
    return dict(path=str(target.relative_to(p)),plan=plan,ready_for_mix_preparation=True,verified=False,implementation_binding=bound['binding'])


def _equal_groups(events):
    groups={}
    for e in events:
        if e.get('equal_options'):
            signature=(e['source_sha256'],e['gain'])
            if groups.setdefault(e['group_id'],signature)!=signature:raise ValueError('SFX_OPTION_WEIGHT_MISMATCH: equal options require the same actual source and gain')


def _calibration(project,folder,events,voice,channels):
    """Generate controls from actual dry voice and exact assets, before mixing."""
    import numpy as np
    from sfx_evidence import decode,calibrate
    p=Path(project);rows=[];errors={}
    for source_sha in dict.fromkeys(e['source_sha256'] for e in events):
        uses=[e for e in events if e['source_sha256']==source_sha];event=min(uses,key=lambda e:e['gain'])
        source,source_channels=_decode_channels(_inside(p,event['path']));n=max(len(source)+RATE,2*RATE);prefix=RATE//4
        # Use a real dry-voice region near this cue; no synthetic substitute source.
        at=max(0,min(len(voice)-min(n,len(voice)),event['_placement_sample']))
        base=voice[at:at+n]
        if len(base)<n:base=np.pad(base,((0,n-len(base)),(0,0))) # calibration context only; never alter narration
        count=max(channels,source_channels);base=np.repeat(base,count,axis=1) if base.shape[1]==1 and count==2 else base.copy()
        original=np.repeat(source,count,axis=1) if source_channels==1 and count==2 else source
        present=base.copy();present[prefix:prefix+len(original)]+=original*event['gain']
        if np.max(np.abs(present),initial=0)>=1:raise ValueError('SFX_CALIBRATION_CLIPPING: current dry/gain controls clip')
        stem=source_sha[:12];paths={k:folder/(stem+'-'+k+'.wav') for k in ['positive','narration','silence']}
        _write_new_audio(paths['positive'],present,count);_write_new_audio(paths['narration'],base,count);_write_new_audio(paths['silence'],np.zeros_like(base),count)
        for key in ['positive','narration']:
            output=paths[key].with_suffix('.m4a')
            subprocess.run(['ffmpeg','-v','error','-n','-i',str(paths[key]),'-c:a','aac','-b:a','192k',str(output)],capture_output=True,check=True)
        positive=[dict(kind='source-present',path=str(paths['positive'].relative_to(p)),sha256=sha(paths['positive']),expected_offset_sample=prefix),
                  dict(kind='compressed-present',path=str(paths['positive'].with_suffix('.m4a').relative_to(p)),sha256=sha(paths['positive'].with_suffix('.m4a')),expected_offset_sample=prefix)]
        negative=[dict(kind='silence',path=str(paths['silence'].relative_to(p)),sha256=sha(paths['silence'])),dict(kind='narration-only',path=str(paths['narration'].relative_to(p)),sha256=sha(paths['narration'])),
                  dict(kind='compressed-absent',path=str(paths['narration'].with_suffix('.m4a').relative_to(p)),sha256=sha(paths['narration'].with_suffix('.m4a')))]
        result=calibrate(decode(_inside(p,event['path'])),[decode(_inside(p,r['path'])) for r in positive],[decode(_inside(p,r['path'])) for r in negative])
        if not result['ready']:raise ValueError('SFX_PRESENCE_UNCERTAIN: current source/gain cannot be distinguished from dry/codec controls')
        error=max(abs(r['offset_sample']-prefix) for r in result['positive']);errors[source_sha]=error
        rows.append(dict(source_sha256=source_sha,positive_controls=positive,negative_controls=negative,calibration_result=result,measurement_error_samples=error))
    return dict(schema='course-sfx-calibration/1',sample_rate=RATE,assets=rows,hearing_review=False),errors


def _execution_mix(project,plan_file,narration,out,bind):
    import numpy as np
    from backend import read,atomic,validate
    from production_validation import digest
    from timeline import display_frame
    p=Path(project);contract=read(p/'production-contract.json');prior=_prior_plan(p,contract);doc=read(p/'workbench.json');input_plan=_inside(p,plan_file);plan=read(input_plan)
    if plan.get('execution_schema')!='course-sfx-execution/1' or plan.get('execution_policy')!='required':raise ValueError('SFX_PLAN_NOT_EXECUTABLE: regenerate the old candidate plan under the current contract')
    timeline,timeline_source=source_timeline(p,plan.get('timeline_source'))
    if plan['fps']!=timeline.get('fps') or plan['sourceDurationFrames']!=timeline.get('sourceDurationFrames') or plan.get('timeline_basis_sha256')!=_basis(timeline):raise ValueError('SFX_TIME_MISMATCH: source/document edit changed after planning')
    current_req=contract.get('requirements',{}).get('sfx',{})
    if current_req.get('plan_path')!=str(input_plan.relative_to(p)) or current_req.get('plan_file_sha256')!=sha(input_plan):raise ValueError('SFX_PLAN_STALE: mix must consume the actual current contract plan')
    voice_path=_inside(p,narration);output=_inside(p,out);stem=output.with_name(output.stem+'-sfx.wav');sidecar=output.with_suffix('.json');receipt_path=output.with_name(output.stem+'-execution-receipt.json')
    if output.suffix.lower()!='.wav':raise ValueError('SFX_OUTPUT_FORMAT: preserve source PCM in WAV before AAC export')
    if output==voice_path or any(file.exists() for file in [output,stem,sidecar,receipt_path]):raise ValueError('SFX_OUTPUT_EXISTS: choose new outputs; source and previous candidates are preserved')
    before_voice=sha(voice_path);voice,channels=_decode_channels(voice_path);count=len(voice);fps=Fraction(str(plan['fps']));expected=Fraction(plan['sourceDurationFrames'])*RATE/fps
    if abs(count-float(expected))>float(Fraction(RATE,2)/fps):raise ValueError('SFX_NARRATION_DURATION_MISMATCH: keep actual dry samples, reconcile the source timeline explicitly')
    selected=json.loads(json.dumps(plan['events']));_equal_groups(selected);clips=[];visual=_visual_map(p,timeline,contract);output_channels=channels
    for e in selected:
        if visual.get(e['visual_event_id'],{}).get(e['visual_phase'])!=e['source_frame']:raise ValueError('SFX_VISUAL_BINDING_MISSING: current semantic/subject event changed')
        file=_inside(p,e['path'])
        if sha(file)!=e['source_sha256']:raise ValueError('SFX_SOURCE_CHANGED')
        actual=_landmarks(file)
        if e['source_'+e['trigger_kind']+'_sample']!=actual[e['trigger_kind']]:raise ValueError('SFX_SOURCE_LANDMARK_CHANGED')
        clip,clip_channels=_decode_channels(file);output_channels=max(output_channels,clip_channels)
        start=round(Fraction(e['source_frame'])*RATE/fps)-actual[e['trigger_kind']]
        if start<0 or start+len(clip)>count:raise ValueError('SFX_TAIL_OUT_OF_RANGE: do not crop the source or extend/trim narration')
        e['_placement_sample']=start;clips.append((e,clip,clip_channels,start))
    # Compute the real output and all preconditions before creating any new output.
    base=np.repeat(voice,2,axis=1) if channels==1 and output_channels==2 else voice.copy();track=np.zeros_like(base)
    for e,clip,ch,start in clips:
        clip=np.repeat(clip,2,axis=1) if ch==1 and output_channels==2 else clip
        track[start:start+len(clip)]+=clip*e['gain']
    combined=base+track;peak=float(np.max(np.abs(combined),initial=0))
    if peak>=1:raise ValueError('SFX_CLIPPING: lower the authored source gain; no automatic ducking/normalization')
    folder=p/'audio/sfx-execution'/uuid.uuid4().hex;folder.mkdir(parents=True)
    calibration,errors=_calibration(p,folder,selected,voice,channels);cal_path=folder/'calibration.json';atomic(cal_path,calibration)
    prepared=json.loads(json.dumps(plan));prepared.update(preparation_state='frozen-before-mix',parent_plan_path=str(input_plan.relative_to(p)),parent_plan_file_sha256=sha(input_plan),
        dry_path=str(voice_path.relative_to(p)),dry_sha256=before_voice,actual_dry_samples=count,dry_channels=channels,output_channels=output_channels,
        calibration_path=str(cal_path.relative_to(p)),calibration_sha256=sha(cal_path))
    for e in prepared['events']:
        e['timing_contract'].update(declared_before_mix=True,measurement_error_samples=errors[e['source_sha256']])
    prepared_path=folder/'plan.json';atomic(prepared_path,prepared)
    # The prepared plan (with measured tolerance) exists before either full stem/mix.
    _write_new_audio(stem,track,output_channels);_write_new_audio(output,combined,output_channels)
    if sha(voice_path)!=before_voice or read(p/'workbench.json')!=doc:raise ValueError('SFX_INPUT_CHANGED: current input changed during mixing; candidates retained unbound')
    receipt=dict(schema='course-sfx-execution-receipt/1',execution_policy='required',status='implemented_unverified',palette=plan['palette'],
        plan_path=str(prepared_path.relative_to(p)),plan_sha256=digest(prepared),plan_file_sha256=sha(prepared_path),input_plan_path=str(input_plan.relative_to(p)),input_plan_file_sha256=sha(input_plan),
        dry_path=str(voice_path.relative_to(p)),dry_sha256=before_voice,sfx_stem_path=str(stem.relative_to(p)),sfx_stem_sha256=sha(stem),mix_path=str(output.relative_to(p)),mix_sha256=sha(output),
        source_events=[dict(id=e['id'],source_sha256=e['source_sha256'],gain=e['gain'],source_frame=e['source_frame'],display_frame=e['peak_or_onset_frame'],start_sample=e['_placement_sample'],source_channels=ch)for e,clip,ch,start in clips],
        sample_rate=RATE,samples=count,dry_channels=channels,output_channels=output_channels,narration_timeline_changed=False,narration_source_unchanged=True,
        calibration_path=str(cal_path.relative_to(p)),calibration_sha256=sha(cal_path),peak=peak,hearing_review=False,listening='unverified; signal detection is not a listening review')
    atomic(receipt_path,receipt)
    legacy=dict(receipt,plan_sha256=sha(prepared_path),canonical_plan_sha256=digest(prepared),canonical_receipt_path=str(receipt_path.relative_to(p)),
        narration=receipt['dry_path'],narration_sha256=before_voice,mix=receipt['mix_path'],sfxStem=receipt['sfx_stem_path'],duration=count/RATE,events=len(selected),
        appliedGains=[dict(id=e['id'],assetId=e['asset_id'],gainDb=20*math.log10(e['gain']),groupId=e['group_id'])for e in selected])
    atomic(sidecar,legacy)
    if bind:
        if doc.get('status')=='draft' and timeline_source!='workbench.json':
            target=_inside(p,timeline_source);changed=read(target)
            if _basis(changed)!=_basis(timeline):raise ValueError('SFX_INPUT_CHANGED: draft composition changed')
            changed.setdefault('media',{}).update(audio=str(output.relative_to(p)),narration=str(voice_path.relative_to(p)))
            atomic(target,changed);receipt['bound_specification']=timeline_source
        else:
            changed=json.loads(json.dumps(doc));changed.setdefault('media',{}).update(audio=str(output.relative_to(p)),narration=str(voice_path.relative_to(p)))
            changed['revision']+=1;validate(changed,p);atomic(p/'workbench-history'/f'{doc["revision"]:06}.json',doc);atomic(p/'workbench.json',changed);receipt['bound_revision']=changed['revision']
    assets=current_req.get('assets',[])
    bound=_bind_execution(p,contract,prepared_path,prepared,assets,dict(receipt=str(receipt_path.relative_to(p)),calibration=str(cal_path.relative_to(p))),tool='sound.mix',prior_plan=prior,outputs=[str(output),str(stem),str(sidecar),str(receipt_path),str(cal_path)])
    return dict(receipt,receipt_path=str(receipt_path.relative_to(p)),technical_only=True,verified=False,implementation_binding=bound['binding'])
