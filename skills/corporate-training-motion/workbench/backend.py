"""Local, file-backed course editor. All mutation stays in its imported copy."""
from pathlib import Path
from contextlib import contextmanager
import argparse
import array
import copy
import hashlib
import fcntl
import http.server
import json
import math
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import wave
import zipfile
from timeline import display_frame, source_frame, duration, segments
from runtime import activate, tools, ensure_dir
activate()

APP = Path(__file__).resolve().parent
LOCK = threading.RLock()


class ProductionHeld(ValueError):
    pass


def owned_export_process(command,**kwargs):
    process=subprocess.Popen(command,start_new_session=True,**kwargs)
    process.kgxc_export_process_group=process.pid
    return process


def stop_export_process(process):
    """Drain the owned group even if its leader has already exited."""
    group=getattr(process,'kgxc_export_process_group',None)
    if group is None:
        if process.poll() is not None:return
        if os.getpgid(process.pid)!=process.pid:raise ValueError('导出进程缺少独立进程组，不能终止其他任务')
        group=process.kgxc_export_process_group=process.pid
    try:os.killpg(group,signal.SIGTERM)
    except ProcessLookupError:return
    deadline=time.monotonic()+.8
    while time.monotonic()<deadline:
        process.poll()
        try:os.killpg(group,0)
        except ProcessLookupError:break
        time.sleep(.02)
    else:
        try:os.killpg(group,signal.SIGKILL)
        except ProcessLookupError:pass
    process.wait(timeout=3)


@contextmanager
def document_lock(project):
    with (Path(project)/'workbench.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, value):
    path = Path(path)
    ensure_dir(path.parent)
    tmp = path.with_name(path.name+'.pending-'+uuid.uuid4().hex)
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    tmp.replace(path)


def safe(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('需要工程内相对路径')
    p = (Path(root)/name).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError('文件路径超出当前工程')
    return p


def clean_caption(text):
    # Use the same meaning-preserving subtitle implementation as the Skill.
    script_dir = APP.parent/'scripts'
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from single_line_subtitles import clean
    return clean(text)


def validate(doc, project):
    if doc.get('schema') != 'course-workbench/1' or type(doc.get('fps')) not in [int,float] or not math.isfinite(doc['fps']) or not 1<=doc['fps']<=120:
        raise ValueError('不支持的工程格式或帧率')
    if (doc.get('width'),doc.get('height')) != (1920,1080) or doc.get('adapter') not in ['national-world-v1','scene-graph-v1','seek-bridge-v1']:
        raise ValueError('不支持的画布规格或课程适配器')
    if not isinstance(doc.get('sourceDurationFrames'), int) or not 1 <= doc['sourceDurationFrames'] <= 2592000:
        raise ValueError('原片时长无效')
    if len(doc.get('captions', [])) > 10000 or len(doc.get('holds', [])) > 500:
        raise ValueError('时间轴条目过多')
    for h in doc['holds']:
        if not isinstance(h.get('frames'), int) or not 0 <= h['frames'] <= 1800:
            raise ValueError('单处停留须在0至60秒内')
        if not isinstance(h.get('sourceFrame'), int) or not 0 < h['sourceFrame'] < doc['sourceDurationFrames']:
            raise ValueError('停留位置超出原片')
    if len({h['sourceFrame'] for h in doc['holds']}) != len(doc['holds']):
        raise ValueError('同一位置的停留应合并')
    if doc['holds'] != sorted(doc['holds'],key=lambda h:h['sourceFrame']):
        raise ValueError('停留必须按原时间轴排序')
    cuts=doc.get('cuts',[])
    if not isinstance(cuts,list) or len(cuts)>1000:raise ValueError('裁剪条目过多或格式无效')
    last_cut=-1
    for cut in cuts:
        if not isinstance(cut,dict) or any(type(cut.get(k)) is not int for k in ['startFrame','endFrame']):raise ValueError('裁剪时间须使用整数帧')
        a,b=cut['startFrame'],cut['endFrame']
        if not 0<=a<b<=doc['sourceDurationFrames'] or a<=last_cut:raise ValueError('裁剪区间必须有序且不重叠 相邻区间应合并')
        last_cut=b
    if duration(doc)<1:raise ValueError('至少保留一帧课程')
    if doc.get('audio',{}).get('speed') != 1:
        raise ValueError('本工作台保持原配音速度1.0')
    gain=doc.get('audio',{}).get('gain')
    if not isinstance(gain,(int,float)) or not math.isfinite(gain) or not 0 <= gain <= 2:
        raise ValueError('音量须在0至2之间')
    style=doc.get('captionStyle',{})
    if not 24 <= style.get('fontSize',0) <= 64 or not 100 <= style.get('y',0) <= 1025:
        raise ValueError('字幕字号或位置超出编辑范围')
    last = -1
    ids = set()
    for c in doc['captions']:
        if c['id'] in ids:
            raise ValueError('字幕ID重复')
        ids.add(c['id'])
        if not isinstance(c['text'], str) or not c['text'].strip() or len(c['text']) > 200:
            raise ValueError('字幕为空或过长')
        if clean_caption(c['text']) != c['text'] or '\n' in c['text']:
            raise ValueError('字幕须单行无标点；请先使用“整理为无标点”')
        if not all(isinstance(c[k], int) for k in ['startFrame','endFrame']):
            raise ValueError('字幕时间须使用整数帧')
        if c['startFrame'] < last or not c['startFrame'] < c['endFrame'] <= duration(doc):
            raise ValueError('字幕重叠、倒序或越界')
        if c['startFrame'] < 0:
            raise ValueError('字幕不能早于课程开始')
        last = c['endFrame']
    for a in doc['assets']:
        if not safe(project, a['path']).is_file():
            raise ValueError('素材不存在：'+a['id'])
        if not safe(project, a['originalPath']).is_file():
            raise ValueError('原素材不存在：'+a['id'])
    for key in ['fields','assets']:
        identifiers=[v.get('id') for v in doc[key]]
        if any(not isinstance(v,str) or not v for v in identifiers) or len(set(identifiers))!=len(identifiers):raise ValueError('登记ID缺失或重复：'+key)
    for key in ['audio','narration','intro','outro']:
        name=doc['media'].get(key)
        required=key=='audio' and doc.get('status','ready')!='draft' or key=='intro' and doc['introFrames']>0 or key=='outro' and doc['bodyEndFrame']<doc['sourceDurationFrames']
        if required and not name:raise ValueError('缺少媒体：'+key)
        if name and not safe(project, name).is_file():
            raise ValueError('缺少媒体：'+key)
    if not 0 <= doc['introFrames'] <= doc['bodyEndFrame'] <= doc['sourceDurationFrames']:
        raise ValueError('片头正文片尾边界无效')
    if doc.get('font') and not safe(project,doc['font']).is_file():raise ValueError('缺少工程字体')
    previous=-1;scene_ids=set()
    for scene in doc['scenes']:
        a,b=scene['sourceStartFrame'],scene['sourceEndFrame']
        if not isinstance(a,int) or not isinstance(b,int) or not 0 <= a < b <= doc['sourceDurationFrames'] or a<previous or scene['id'] in scene_ids:
            raise ValueError('场景ID或时间轴无效')
        previous=b;scene_ids.add(scene['id'])
    from course_palette import check as palette_check, read_plan
    palette_errors = palette_check(doc, read_plan(project))
    if palette_errors:raise ValueError('; '.join(palette_errors))
    if doc['adapter']=='scene-graph-v1' or doc.get('rendering',{}).get('route')=='motion-canvas':
        from character_performance import validate_assets
        validate_assets(doc,project)
        from authoring import graph_errors
        errors=graph_errors(doc)
        if errors:raise ValueError('; '.join(errors))
    if doc.get('rendering'):
        from render_routes import plan
        selection=plan(doc)
        if not selection['ready'] or selection['adapter']!=doc['adapter']:
            raise ValueError('渲染路线与能力要求不一致：'+'; '.join(selection['errors']))
    for field in doc['fields']:
        if not isinstance(field['text'],str) or len(field['text']) > 300:
            raise ValueError('画面文字无效')
        if not all(isinstance(field[k],(int,float)) and math.isfinite(field[k]) and abs(field[k]) <= 500 for k in ['dx','dy']):
            raise ValueError('画面位移超出允许范围')
    from company_characters import validate_uniforms
    validate_uniforms(doc,project)
    if doc.get('status')!='draft':
        from continuity_pacing import require as require_continuity
        require_continuity(doc,project)
    return doc


def import_course(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if (source/'project/timeline.json').is_file():
        source = source/'project'
    timeline = read(source/'timeline.json')
    # This first adapter retains the actual original world/canvas engine.
    data_file = source/'source/remake-data.js'
    if not data_file.is_file() or 'window.WORLD=' not in data_file.read_text():
        raise ValueError('第一版导入器支持WORLD画布国补课程；其他工程需要实现相同编辑桥接接口')
    if target.exists():
        raise ValueError('目标目录已存在；不覆盖原工程或编辑副本')
    target.mkdir(parents=True)
    p = target/'project'
    (p/'native/source').mkdir(parents=True)
    (p/'media').mkdir()
    for name in ['delivery','packages','inputs']:
        (target/name).mkdir()
    shutil.copy2(source/'index.html', p/'native/index.html')
    for name in ['timeline.js','source-assets.js','remake-data.js','art.js','scenes.js']:
        shutil.copy2(source/'source'/name, p/'native/source'/name)
    shutil.copytree(source/'assets', p/'native/assets', ignore=shutil.ignore_patterns('*.lock','.DS_Store'))
    shutil.copy2(source/'audio/course-mix.wav', p/'media/narration-original.wav')
    for name in ['intro','outro']:
        shutil.copy2(source/f'assets/brand/bookends/{name}.mp4', p/f'media/{name}.mp4')
    world = json.JSONDecoder().raw_decode(data_file.read_text().split('window.WORLD=',1)[1])[0]
    assets = json.loads((source/'source/source-assets.js').read_text().split('=',1)[1].rstrip(';\n'))
    fields=[]
    for group in world['groups']:
        fields.append(dict(id=group['id']+':label',target='group',objectId=group['id'],property='label',
                           label='场景标题 · '+group['id'],text=group['label'],dx=0,dy=0))
        for node in group['points']:
            for prop in ['label','note']:
                fields.append(dict(id=node['id']+':'+prop,target='point',objectId=node['id'],property=prop,
                                   label=('要点标题' if prop=='label' else '要点说明')+' · '+node['id'],
                                   text=node.get(prop,''),dx=0,dy=0))
    fps=30
    captions=[]
    source_cues=timeline['captions']
    srt=source/'source/course.srt'
    if srt.exists():
        source_cues=[]
        def seconds(value):
            h,m,s=value.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
        for block in re.split(r'\n\s*\n',srt.read_text().strip()):
            lines=block.splitlines()
            if len(lines)<3:continue
            a,b=lines[1].split(' --> ')
            start=seconds(a);end=seconds(b)
            scene=next((s['id'] for s in timeline['scenes'] if s['start'] <= start < s['end']),'')
            source_cues.append(dict(scene=scene,text=' '.join(lines[2:]),start=start,end=end))
    for i,c in enumerate(source_cues):
        captions.append(dict(id=f'C{i+1:04}',sceneId=c.get('scene',''),text=clean_caption(c['text']),
                             startFrame=round(c['start']*fps),endFrame=round(c['end']*fps)))
    doc=dict(schema='course-workbench/1',revision=0,title='国补业务流程指引 · 编辑验证副本',fps=fps,
             width=1920,height=1080,adapter='national-world-v1',sourceDurationFrames=round(timeline['duration']*fps),
             introFrames=round(timeline['intro_duration']*fps),bodyEndFrame=round(timeline['body_end']*fps),
             media=dict(audio='media/narration-original.wav',intro='media/intro.mp4',outro='media/outro.mp4'),
             holds=[],cuts=[],captions=captions,fields=fields,
             captionStyle=dict(fontSize=42,y=990,fill='#ffffff',stroke='#172b38',strokeWidth=8),
             audio=dict(gain=1,voice='沿用原课录音；未重新配音',speed=1),
             scenes=[dict(id=s['id'],title=s['title'],chapter=s['chapter'],
                          sourceStartFrame=round(s['start']*fps),sourceEndFrame=round(s['end']*fps)) for s in timeline['scenes']],
             assets=[dict(id=k,label=k,path='native/'+v,originalPath='native/'+v) for k,v in assets.items()])
    validate(doc,p)
    atomic(p/'workbench.json',doc)
    atomic(target/'inputs/import-receipt.json',dict(adapter=doc['adapter'],original_timeline_sha256=digest(source/'timeline.json'),
                                                  original_audio_sha256=digest(source/'audio/course-mix.wav'),
                                                  original_sources={f:digest(source/f) for f in ['index.html','source/scenes.js','source/remake-data.js']},
                                                  scope='Independent editable copy; original files untouched'))
    atomic(target/'workspace.json',dict(project_dir='project',delivery_dir='delivery',package_dir='packages',editor='course-workbench/1'))
    (target/'README.md').write_text('# 企业课程编辑副本\n\n使用企业课程Skill的workbench.py serve 本目录打开。workbench.json是编辑数据；原课程与原成片未改动。\n')
    print(target)
    return target


class Workspace:
    def __init__(self, root):
        root=Path(root).resolve()
        self.project=root if (root/'workbench.json').is_file() else root/'project'
        self.root=self.project.parent
        self.file=self.project/'workbench.json'
        validate(read(self.file),self.project)
        self.jobs={}
        self.work=self.project/'work/workbench'
        ensure_dir(self.work)

    def require_production_active(self, process=None):
        policy=self.project/'ai-review.json'
        hold=(read(policy) if policy.is_file() else {}).get('hold') or {}
        if hold.get('held'):
            if process is not None:stop_export_process(process)
            raise ProductionHeld('制作已暂停：'+str(hold.get('reason') or '等待解除暂停')+'；当前文件全部保留')

    def job(self, name):
        if not re.fullmatch('[a-f0-9]{12}',name):
            raise ValueError('导出任务ID无效')
        if name in self.jobs:return self.jobs[name]
        result=self.work/'exports'/name/'result.json'
        if result.exists():return read(result)
        resume=self.work/'exports'/name/'started.json'
        if resume.is_file():
            initial=read(resume)
            if initial.get('id')==name and initial.get('purpose') in ('pilot','final'):
                from render_input_guard import active as active_renders
                if any(lock.get('render_id')==name for lock in active_renders(self.project)):
                    return dict(initial,status='rendering')
                return dict(initial,status='cancelled',files_retained=True,error='上次制作中断；已保存的成果仍在。')
        return dict(id=name,status='missing',error='该任务未完成或服务曾中断，请重新导出')

    def save(self, doc, revision):
        with LOCK, document_lock(self.project):
            from render_input_guard import ensure_mutation_allowed
            ensure_mutation_allowed(self.project,'Workspace.save',dict(document=doc,revision=revision))
            current=read(self.file)
            if current['revision'] != revision:
                raise FileExistsError('工程已被其他窗口修改；请重新载入并核对，未覆盖修改')
            if doc==current:return copy.deepcopy(current)
            for key in ['schema','fps','width','height','adapter','sourceDurationFrames','introFrames','bodyEndFrame','media','scenes','status','font','sceneGraph','rendering','motionPlan','narrationLinks','readingPolicy','readingPlan','continuityPolicy','continuityPlan','teachingModules','coursePalette','orderedRevealGroups','introPolicy']:
                if doc.get(key) != current.get(key):
                    raise ValueError('不可通过编辑器修改原始结构字段：'+key)
            if [(a['id'],a['originalPath']) for a in doc['assets']] != [(a['id'],a['originalPath']) for a in current['assets']]:
                raise ValueError('素材登记身份不可修改')
            if [(f['id'],f['objectId'],f['property']) for f in doc['fields']] != [(f['id'],f['objectId'],f['property']) for f in current['fields']]:
                raise ValueError('画面登记身份不可修改')
            validate(doc,self.project)
            doc=copy.deepcopy(doc)
            doc['revision']=current['revision']+1
            history=self.project/'workbench-history'
            atomic(history/f'{current["revision"]:06}.json',current)
            atomic(self.file,doc)
            atomic(self.project/'qa/workbench-edit-status.json',dict(revision=doc['revision'],status='edited_requires_review',
                                                                  original_course_approval='not inherited by this edit'))
            return doc

    def waveform(self):
        doc=read(self.file)
        if not doc['media'].get('audio'):return dict(peaks=[],duration=doc['sourceDurationFrames']/doc['fps'])
        from performance_cache import sha
        source=safe(self.project,doc['media']['audio']);source_hash=sha(source)
        cache=self.work/('waveform-v2-'+source_hash+'.json')
        if cache.is_file():
            try:
                data=read(cache)
                if data.get('source_sha256')==source_hash and isinstance(data.get('peaks'),list) and type(data.get('duration')) in [int,float]:
                    return data
            except (OSError,ValueError,AttributeError):pass
        result=subprocess.run(['ffmpeg','-v','error','-i',str(source),
                               '-f','s16le','-ac','1','-ar','8000','-'],capture_output=True,check=True)
        if sha(source)!=source_hash:raise ValueError('波形生成期间音轨发生变化，请重试')
        samples=array.array('h');samples.frombytes(result.stdout)
        size=max(1,math.ceil(len(samples)/4000))
        peaks=[round(max(abs(x) for x in samples[i:i+size])/32768,4) for i in range(0,len(samples),size)]
        data=dict(peaks=peaks,duration=len(samples)/8000,source_sha256=source_hash)
        atomic(cache,data)
        return data

    def audio_key(self, doc):
        from performance_cache import sha
        from timeline import audio_filters
        source=safe(self.project,doc['media']['audio'])
        value=['prepared-audio-v2',doc['media']['audio'],sha(source),audio_filters(doc),'pcm_s16le/48000/mono']
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def audio(self, doc, production=False):
        validate(doc,self.project)
        if not doc['media'].get('audio'):raise ValueError('草稿尚无实际配音，不能播放或导出')
        if not doc['holds'] and not doc.get('cuts') and doc['audio']['gain']==1:
            return safe(self.project,doc['media']['audio'])
        key=self.audio_key(doc)
        path=self.work/(key+'.wav')
        receipt=path.with_suffix('.json')
        from performance_cache import sha
        if path.is_file() and receipt.is_file():
            try:
                if read(receipt)==dict(input_key=key,sha256=sha(path)):return path
            except (OSError,ValueError):pass
        from timeline import audio_filters
        temporary=path.with_name(path.stem+'.'+uuid.uuid4().hex+'.pending.wav')
        command=['ffmpeg','-v','error','-y','-i',str(safe(self.project,doc['media']['audio'])),
                 '-filter_complex',audio_filters(doc),'-map','[out]','-ar','48000','-ac','1','-c:a','pcm_s16le',str(temporary)]
        if production:
            self.require_production_active()
            with temporary.with_suffix('.log').open('w') as log:
                process=owned_export_process(command,stdout=log,stderr=subprocess.STDOUT)
                while process.poll() is None:
                    self.require_production_active(process)
                    time.sleep(.1)
                self.require_production_active(process)
                if process.returncode:raise ValueError('导出音轨处理失败，保留日志：'+str(temporary.with_suffix('.log')))
        else:subprocess.run(command,check=True)
        if self.audio_key(doc)!=key:raise ValueError('预处理期间音轨或剪辑输入发生变化；未缓存候选')
        output_hash=sha(temporary)
        temporary.replace(path)
        atomic(receipt,dict(input_key=key,sha256=output_hash))
        return path

    def archive_previous_exports(self, current_job):
        """Keep one current delivery for new courses; retain generated export history."""
        config_path=self.project/'project.json'
        if not config_path.exists() or not read(config_path).get('workbench',{}).get('required'):return
        config=read(config_path)
        protected={a.get('path') for a in read(self.root/'workspace.json').get('retain_artifacts',[])} if (self.root/'workspace.json').exists() else set()
        for result in (self.work/'exports').glob('*/result.json'):
            job=read(result)
            if job.get('id')==current_job or job.get('status')!='complete':continue
            for key in ['video','srt','package']:
                url=urllib.parse.unquote(job.get(key,''))
                if not url.startswith('/download/'):continue
                relative=url.removeprefix('/download/');old=safe(self.root,relative)
                if relative in protected or not old.exists():continue
                dest=result.parent/'published'/old.name;ensure_dir(dest.parent);old.replace(dest)
                if key=='video':
                    old_meta=old.with_suffix('.json')
                    if old_meta.exists():old_meta.replace(dest.with_suffix('.json'))
                    for stage,path in config.get('render_artifacts',{}).items():
                        if path and (self.project/path).resolve()==old:config['render_artifacts'][stage]=str(dest.relative_to(self.project))
        atomic(config_path,config)

    def start_export(self, revision, start, end, url, purpose=None, review_run_id=None):
        with LOCK:
            self.require_production_active()
            doc=read(self.file)
            validate(doc,self.project)
            if doc.get('status')=='draft' or not doc['scenes'] or (not doc['captions'] and not doc.get('cuts')):
                raise ValueError('课程尚未完成实际配音、字幕和场景，不能把草稿导出为成片')
            if revision != doc['revision']:raise FileExistsError('请先保存当前修改再导出')
            if any(j['status'] in ['queued','rendering'] for j in self.jobs.values()):
                raise ValueError('已有导出正在进行')
            first=round(float(start)*doc['fps']);last=round(float(end)*doc['fps'])
            if not 0 <= first < last <= duration(doc):raise ValueError('导出范围无效')
            if purpose not in [None,'pilot','final']:raise ValueError('导出用途须为pilot或final')
            key=purpose or ('final' if first==0 and last==duration(doc) else 'pilot')
            if key=='final' and (first!=0 or last!=duration(doc)):raise ValueError('完整视频须导出当前完整时间线')
            render_context=None
            if (self.project/'course-state.json').is_file():
                from workflow import Course
                course=Course(self.root)
                if course.modern():
                    if review_run_id:
                        from ai_review import Review
                        Review(course).allow_render(key,review_run_id)
                    else:course.require_video('pilot' if key=='final' else 'style')
                    if course.storyboard_mode():
                        from storyboard import check_bindings
                        issues=check_bindings(course.storyboard(),course.sample_plan(),doc,first,last,full=key=='final')
                        if issues:raise ValueError('；'.join(issues))
                    render_context=course._video_context()
                else:
                    if purpose:raise ValueError('旧工程沿原导出规则，不指定导出用途')
                    course.require('pilot' if first==0 and last==duration(doc) else 'visual')
            from motion_quality import require as require_motion
            motion_preflight=require_motion(doc,self.project)
            job_id=uuid.uuid4().hex[:12];directory=self.work/'exports'/job_id;directory.mkdir(parents=True)
            atomic(directory/'document.json',doc)
            atomic(directory/'motion-preflight.json',motion_preflight)
            from authoring import native_fingerprint
            native_hash=native_fingerprint(self.project)
            audio=self.audio(doc,production=True)
            if native_hash!=native_fingerprint(self.project):raise ValueError('INPUT_CHANGED_DURING_RENDER: inputs changed while preparing actual render audio')
            from render_input_guard import freeze_render
            frozen_inputs=freeze_render(self.project,job_id,directory/'document.json',extra_inputs={'prepared_audio':str(audio)})
            job=dict(id=job_id,status='queued',progress=0,firstFrame=first,lastFrame=last,revision=revision,purpose=key)
            atomic(directory/'started.json',job)
            self.jobs[job_id]=job
        def worker():
            try:
                self.require_production_active()
                job['status']='rendering'
                from continuity_pacing import audit as audit_continuity
                continuity=audit_continuity(doc,self.project,first,last)
                atomic(directory/'continuity-preflight.json',continuity)
                if continuity['status']=='fail':raise ValueError('旁白连贯性检查未通过：'+'；'.join(continuity['errors']))
                config=tools()
                interpreter=os.environ.get('COURSE_PYTHON',config.get('python',sys.executable))
                command=[interpreter,str(APP/'render_worker.py'),'--url',url+'/renderer.html?job='+job_id,
                         '--directory',str(directory),'--project',str(self.project),'--audio',str(audio),'--first',str(first),'--last',str(last),
                         '--fps',str(doc['fps'])]
                if render_context is not None and (doc['introFrames']>0 or doc['bodyEndFrame']<doc['sourceDurationFrames']):
                    command.append('--seam-preflight')
                    job['phase']='seam_preflight'
                with (directory/'render.log').open('w') as log:
                    self.require_production_active()
                    process=owned_export_process(command,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                    atomic(directory/'execution.json',dict(pid=process.pid,process_group=process.pid,scope='owned-export-process-group',job_id=job_id,argv=command,files_retained=True))
                    while process.poll() is None:
                        self.require_production_active(process)
                        if job.get('phase')=='seam_preflight' and (directory/'seam-preflight.json').exists():
                            if read(directory/'seam-preflight.json').get('status') in ['pass','not-applicable']:
                                job['phase']='render'
                        status=directory/'progress.json'
                        if status.exists():
                            try:job['progress']=read(status)['progress']
                            except ValueError:pass
                        time.sleep(.4)
                    if process.returncode:raise ValueError((directory/'render.log').read_text()[-1800:])
                if job.get('phase')=='seam_preflight':job['phase']='render'
                self.require_production_active()
                from render_input_guard import check_render
                check_render(self.project,frozen_inputs)
                if native_hash!=native_fingerprint(self.project):raise ValueError('导出期间源码或媒体已改变，请重新导出；没有把旧帧绑定到新源码')
                if render_context is not None and read(self.file)!=doc:raise ValueError('导出期间编辑版本已改变，请重新生成当前版本')
                delivery=self.root/'delivery';ensure_dir(delivery)
                video=delivery/f'course-edit-r{revision}-{job_id}.mp4'
                shutil.copy2(directory/'video.mp4',video)
                cues=[]
                for c in doc['captions']:
                    a=max(first,c['startFrame']);b=min(last,c['endFrame'])
                    if b>a:cues.append(dict(id=c['id'],text=c['text'],start=(a-first)/doc['fps'],end=(b-first)/doc['fps']))
                srt=video.with_suffix('.srt')
                def stamp(t):
                    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
                srt.write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
                metadata=dict(schema=doc['schema'],revision=revision,purpose=key,native_sha256=native_hash,range=dict(firstFrame=first,lastFrame=last,fps=doc['fps']),
                              document_sha256=digest(directory/'document.json'),video_sha256=digest(video),
                              subtitles_sha256=digest(srt),review='technical_export_verified; content/user acceptance pending',
                              verification=read(directory/'verification.json'))
                from export_playback import playback,audio_settings
                metadata['playback']=playback(doc,first,last)
                metadata['audio_settings']=audio_settings(doc,self.project)
                if (self.project/'course-state.json').is_file():
                    from workflow import Course
                    planning_course=Course(self.root)
                    if planning_course.storyboard_mode():
                        from storyboard import basis, digest as plan_digest
                        metadata['storyboard_sampling']=dict(storyboard_sha256=basis(planning_course.storyboard()),
                            sample_plan_sha256=plan_digest(planning_course.sample_plan()),document_sha256=digest(self.file),
                            native_sha256=native_hash,bindings=doc.get('storyboardBindings'))
                atomic(video.with_suffix('.json'),metadata)
                # A current encoded candidate is needed before its visual/audio
                # evidence can be checked. Keep it viewable without registering
                # a stage or replacing a prior accepted export prematurely.
                if (self.project/'course-state.json').is_file():
                    from workflow import Course
                    Course(self.root).stage_candidate(key,[str(video.relative_to(self.project.parent)).replace('delivery/','../delivery/',1),str(srt.relative_to(self.project.parent)).replace('delivery/','../delivery/',1)],directory/'document.json',render_context)
                from release_gate import evaluate,build_context
                contract=evaluate(self.project,build_context(self.project,key,directory/'document.json',video,entrypoint='backend.export'))
                atomic(self.project/'qa/release-gate'/(job_id+'.json'),contract)
                if (self.project/'course-state.json').is_file():Course(self.root).record_release_check(key,contract)
                contract_pending=contract.get('allow_release') is not True
                metadata.update(registration_status='held' if contract_pending else 'pending',
                                stage_registered=False,contract_pending=contract if contract_pending else None)
                atomic(video.with_suffix('.json'),metadata)
                archive=None
                if key=='final':
                    packages=self.root/'packages';ensure_dir(packages)
                    archive=packages/f'editable-r{revision}-{job_id}.zip'
                    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
                        modern=doc['adapter']!='national-world-v1'
                        editor_prefix='project/editor' if modern else 'editor'
                        z.write(directory/'document.json','project/workbench.json')
                        for f in self.project.rglob('*'):
                            rel=f.relative_to(self.project)
                            # work/style-previews 是风格确认引用的预览件，不是缓存；缺它则重开副本无法通过风格闸门
                            preview=len(rel.parts)>1 and rel.parts[0]=='work' and rel.parts[1]=='style-previews'
                            if f.is_file() and not f.name.startswith('.') and f!=self.file and '__pycache__' not in rel.parts and (rel.parts[0] not in ['work','workbench-history','editor','qa'] or preview):
                                z.write(f,'project/'+str(rel))
                        for f in APP.rglob('*'):
                            if f.is_file() and '__pycache__' not in f.parts:z.write(f,editor_prefix+'/workbench/'+str(f.relative_to(APP)))
                        for name in ['workbench.py','single_line_subtitles.py','check_workbench.py','workflow.py','course_tools.py','character_assets.py']:
                            z.write(APP.parent/'scripts'/name,editor_prefix+'/scripts/'+name)
                        if modern:
                            from production import PORTABLE_CONTRACT_METADATA
                            for name in PORTABLE_CONTRACT_METADATA:
                                source=APP.parent/name
                                if not source.is_file():raise ValueError('可编辑工程缺少制作基准元数据：'+name)
                                z.write(source,editor_prefix+'/'+name)
                            z.writestr('README.md','# 可编辑企业课程\n\n运行 python3 project/editor/scripts/workbench.py serve . 打开工作台。\n建议先按Skill仓库README完成完整安装，再运行 kgxc-course serve .。视频导出使用本机配置的ffmpeg、Python Playwright和Chromium。\n')
                            for folder in ['inputs/','delivery/','packages/']:z.writestr(folder,b'')
                            workspace=self.root/'workspace.json'
                            if workspace.exists():z.write(workspace,'workspace.json')
                            else:z.writestr('workspace.json',json.dumps(dict(layout_version=2,project_dir='project',delivery_dir='delivery',package_dir='packages',retain_artifacts=[])))
                            for f in (self.root/'inputs').rglob('*'):
                                if f.is_file():z.write(f,'inputs/'+str(f.relative_to(self.root/'inputs')))
                        else:z.writestr('打开说明.txt','运行 python3 editor/scripts/workbench.py serve . 打开课程。\n编辑无需额外Python包；视频导出需要已有ffmpeg和Playwright运行环境。\n')
                    with zipfile.ZipFile(archive) as z:
                        if z.testzip():raise ValueError('工程包CRC校验失败')
                    if native_hash!=native_fingerprint(self.project):raise ValueError('打包期间素材发生变化，请重试')
                self.require_production_active()
                # Only a whole-course export establishes complete editable-engine evidence.
                if first==0 and last==duration(doc) and read(self.file)==doc:
                    proof=read(directory/'verification.json')
                    atomic(self.project/'qa/workbench-runtime.json',dict(status='pass',document_sha256=digest(self.file),native_sha256=native_hash,
                           scene_ids=[s['id'] for s in doc['scenes']],binding_receipt=proof.get('bindingReceipt'),seek_deterministic=proof.get('seekDeterministic'),full_decode=proof['fullDecode']))
                if (self.project/'course-state.json').is_file():
                    from workflow import Course,bundle_course
                    course=Course(self.root)
                    if not contract_pending:
                        with LOCK:
                            self.require_production_active()
                            if course.modern():course.register(key,[str(video.relative_to(self.root)).replace('delivery/','../delivery/',1),str(srt.relative_to(self.root)).replace('delivery/','../delivery/',1)],course.status()['revision'],render_context=render_context,review_run_id=review_run_id)
                            else:course.register(key,[str(video.relative_to(self.root)).replace('delivery/','../delivery/',1)],course.status()['revision'])
                        metadata.update(registration_status='registered',stage_registered=True)
                    atomic(video.with_suffix('.json'),metadata)
                if not contract_pending:
                    self.archive_previous_exports(job_id)
                    cfg=self.project/'project.json'
                    if cfg.exists():
                        config=read(cfg);config.setdefault('render_artifacts',{})['final' if key=='final' else 'preview']=str(video.relative_to(self.project.parent)).replace('delivery/','../delivery/',1);atomic(cfg,config)
                if archive is not None:
                    if (self.project/'course-state.json').is_file():bundle_course(self.root,archive)
                    job['package']='/download/'+urllib.parse.quote(str(archive.relative_to(self.root)))
                job.update(status='complete',progress=1,video='/download/'+urllib.parse.quote(str(video.relative_to(self.root))),
                           srt='/download/'+urllib.parse.quote(str(srt.relative_to(self.root))),verification=metadata,
                           registration_status=metadata['registration_status'],stage_registered=metadata['stage_registered'],
                           release_state='acceptance_blocked' if contract_pending else 'allowed_for_formal_delivery',
                           candidate_generated=True,user_acceptance=False,contract_pending=contract if contract_pending else None)
                atomic(directory/'result.json',job)
            except ProductionHeld as exc:
                job.update(status='cancelled',error=str(exc),files_retained=True);atomic(directory/'result.json',job)
            except Exception as exc:
                job.update(status='failed',error=str(exc));atomic(directory/'result.json',job)
            finally:
                from render_input_guard import end_render
                end_render(self.project,job_id,job.get('status','unknown'))
        threading.Thread(target=worker,daemon=True).start()
        return job


class Handler(http.server.BaseHTTPRequestHandler):
    server_version='CourseWorkbench/1'

    def log_message(self,*args):pass

    @property
    def space(self):return self.server.workspace

    def json(self,value,status=200):
        content=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)

    def file(self,path):
        if not path.is_file():raise FileNotFoundError('文件不存在')
        size=path.stat().st_size;start=0;end=size-1;code=200
        request_range=self.headers.get('Range','')
        if request_range:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',request_range)
            if not match or int(match[1]) >= size or (match[2] and int(match[2])<int(match[1])):
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            start=int(match[1]);end=min(size-1,int(match[2]) if match[2] else size-1);code=206
        self.send_response(code)
        self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(max(0,end-start+1)));self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','no-cache')
        if code==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as handle:
            handle.seek(start);left=end-start+1
            while left>0:
                chunk=handle.read(min(left,256*1024))
                if not chunk:break
                self.wfile.write(chunk);left-=len(chunk)

    def do_GET(self):
        try:
            url=urllib.parse.urlparse(self.path);path=urllib.parse.unquote(url.path);q=urllib.parse.parse_qs(url.query)
            if path=='/api/document':return self.json(read(self.space.file))
            if path=='/api/studio/live-media':
                from live_media import index
                return self.json(index(self.space))
            if path=='/api/studio':
                from studio import Studio
                return self.json(Studio(self.space).view())
            if path=='/api/studio/source-preview':
                from source_preview import render_pdf
                return self.file(render_pdf(self.space,q.get('id',[''])[0],int(q.get('page',['1'])[0])))
            if path=='/api/editor':
                from script_editor import ScriptEditor
                editor=ScriptEditor(self.space);state=editor.read();request=state.get('render_request',{})
                if request.get('job',{}).get('id') and request.get('status')=='rendering':
                    job=self.space.job(request['job']['id'])
                    status='complete' if job.get('status')=='complete' else 'failed' if job.get('status') in ['failed','missing'] else 'rendering'
                    state['render_request']=editor.render_update(request['id'],status,job=job,error=job.get('error'))
                return self.json(state)
            if path=='/api/identity':
                from workflow import VERSION,service_build
                from lifecycle import POLICY
                state=read(self.space.project/'course-state.json') if (self.space.project/'course-state.json').is_file() else {}
                return self.json(dict(course_id=state.get('course_id'),course_root=str(self.space.root.resolve()),pid=os.getpid(),version=VERSION,lifecycle_policy=POLICY,runtime_build=getattr(self.server,'runtime_build',None),runtime_disk_build=service_build(),execution_runtime=getattr(self.server,'execution_runtime',None)))
            if path=='/api/workflow':
                from workflow import Course
                return self.json(Course(self.space.root).status())
            if path=='/api/courseware':
                from workflow import Course
                return self.json(Course(self.space.root).courseware())
            if path=='/api/script':
                from workflow import Course
                return self.json(Course(self.space.root).script())
            if path=='/course-file':
                from workflow import Course
                return self.file(Course(self.space.root).relative(q.get('path',[''])[0]))
            if path=='/api/waveform':return self.json(self.space.waveform())
            if path=='/api/history':return self.json([dict(revision=int(p.stem)) for p in sorted((self.space.project/'workbench-history').glob('*.json'))])
            if path.startswith('/api/history/'):
                return self.json(read(safe(self.space.project,'workbench-history/'+str(int(path.rsplit('/',1)[1])).zfill(6)+'.json')))
            if path.startswith('/api/job-document/'):
                name=path.rsplit('/',1)[1]
                if not re.fullmatch('[a-f0-9]{12}',name):raise ValueError('导出任务ID无效')
                return self.json(read(self.space.work/'exports'/name/'document.json'))
            if path.startswith('/api/jobs/'):
                return self.json(self.space.job(path.rsplit('/',1)[1]))
            if path=='/api/jobs':
                folders=sorted((self.space.work/'exports').glob('*'),key=lambda p:(p/'document.json').stat().st_mtime if (p/'document.json').exists() else 0)
                return self.json([self.space.job(p.name) for p in folders if p.is_dir()])
            if path=='/api/audio':return self.file(self.space.audio(read(self.space.file)))
            if path.startswith('/preview-audio/'):
                name=path.rsplit('/',1)[1]
                return self.file(safe(self.space.work,'preview/'+name))
            if path.startswith('/project/'):return self.file(safe(self.space.project,path[len('/project/'):]))
            if path.startswith('/native/'):return self.file(safe(self.space.project,'native/'+path[len('/native/'):]))
            if path.startswith('/download/'):
                name=path[len('/download/'):]
                if name.split('/')[0] not in ['delivery','packages']:raise ValueError('仅允许下载交付文件')
                f=safe(self.space.root,name)
                if not f.exists():
                    match=re.search(r'-([a-f0-9]{12})\.(mp4|srt|json|zip)$',f.name)
                    if match:f=safe(self.space.work,'exports/'+match[1]+'/published/'+f.name)
                return self.file(f)
            if path in ['/','/index.html']:
                if (self.space.project/'course-state.json').is_file() and read(self.space.project/'course-state.json').get('preferred_workbench')=='dsh':
                    return self.json(dict(service='DSH course workbench internal service',message='本课统一从DSH课程工作台插件进入；本地址不再展示独立制课界面。'))
                return self.file(APP/('design.html' if (self.space.project/'course-state.json').is_file() else 'index.html'))
            if path=='/edit.html':return self.file(APP/'index.html')
            return self.file(safe(APP,path.lstrip('/')))
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as exc:self.json(dict(error=str(exc)),404 if isinstance(exc,FileNotFoundError) else 400)

    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):raise ValueError('仅允许当前本地工作台修改')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=25*1024*1024:raise ValueError('请求大小无效或超过25MB')
            raw=self.rfile.read(length);path=urllib.parse.urlparse(self.path).path
            if path=='/api/studio/source':
                from studio import Studio
                return self.json(Studio(self.space).add_source(urllib.parse.unquote(self.headers.get('X-Filename','')),raw,int(self.headers['X-Base-Revision'])))
            if path=='/api/upload':
                name=urllib.parse.unquote(self.headers.get('X-Filename','image.png'));suffix=Path(name).suffix.lower()
                if suffix not in ['.png','.jpg','.jpeg','.webp']:raise ValueError('只接受PNG、JPEG、WebP图片')
                dest=self.space.project/'media/uploads'/(uuid.uuid4().hex+suffix);ensure_dir(dest.parent)
                dest.write_bytes(raw)
                probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(dest)],capture_output=True,text=True)
                if probe.returncode or not json.loads(probe.stdout).get('streams'):
                    dest.unlink();raise ValueError('无法解码该图片')
                return self.json(dict(path=str(dest.relative_to(self.space.project)),name=name,sha256=digest(dest)))
            data=json.loads(raw)
            if ((path=='/api/studio/source-coverage-confirm') or
                    (path in ['/api/studio/confirm','/api/studio/review-approve','/api/workflow/confirm']
                     and data.get('stage',data.get('gate')) in ['script','content','pilot','final'])):
                state_path=self.space.project/'course-state.json'
                state=read(state_path) if state_path.is_file() else {}
                if state.get('preferred_workbench')=='dsh':
                    raise ValueError('请在 DSH 右侧原生问答确认当前版本；工作台不接受另一个确认入口。')
            if path.startswith('/api/studio/'):
                from studio import Studio
                return self.json(Studio(self.space).action(path.rsplit('/',1)[1],data))
            if path.startswith('/api/editor/'):
                from script_editor import ScriptEditor
                editor=ScriptEditor(self.space)
                if path=='/api/editor/save':return self.json(editor.save(data['text'],data['baseRevision']))
                if path=='/api/editor/render-error':return self.json(editor.render_update(data['requestId'],'failed',error=data['error']))
                if path=='/api/editor/render':
                    request=editor.request_render(data['baseRevision']);state=editor.read();doc=state['document']
                    if not state['changed'] and doc.get('status')!='draft' and doc.get('media',{}).get('audio'):
                        try:
                            from workflow import Course
                            course=Course(self.space.root)
                            purpose='final' if any(g.get('id')=='pilot' and g.get('status')=='confirmed' for g in course.status().get('gates',[])) else 'pilot'
                            job=self.space.start_export(doc['revision'],0,duration(doc)/doc['fps'],'http://'+self.headers['Host'],purpose if course.modern() else None)
                            request=editor.render_update(request['id'],'rendering',job=job)
                        except Exception as exc:
                            editor.render_update(request['id'],'failed',error=str(exc));raise
                    return self.json(request)
                raise ValueError('未知编辑操作')
            if path.startswith('/api/workflow/'):
                from workflow import Course
                course=Course(self.space.root)
                with LOCK:
                    if path=='/api/workflow/design':return self.json(course.save_plan(data['plan'],data['baseRevision']))
                    if path=='/api/workflow/decision':return self.json(course.decide(data['id'],data['selected'],data['baseRevision'],data['evidence']))
                    if path=='/api/workflow/confirm':return self.json(course.confirm(data['gate'],data['baseRevision'],data['evidence']))
                    if path=='/api/workflow/artifacts':return self.json(course.register(data['gate'],data['paths'],data['baseRevision']))
                    if path=='/api/workflow/courseware':return self.json(course.save_courseware(data['text'],data['baseRevision']))
                    if path=='/api/workflow/script':return self.json(course.save_script(data['text'],data['baseRevision']))
                    if path=='/api/workflow/branch':return self.json(course.select_branch(data['branch'],data['baseRevision'],data['evidence'],actor='workbench'))
                    if path=='/api/workflow/planning':return self.json(course.enable_storyboard(data['baseRevision'],data['evidence'],actor='workbench'))
                    if path=='/api/workflow/storyboard':return self.json(course.save_storyboard(data['storyboard'],data['baseRevision']))
                    if path=='/api/workflow/shot':return self.json(course.choose_shot(data['id'],data['option'],data['baseRevision'],data['evidence']))
                    if path=='/api/workflow/sample':return self.json(course.sample_storyboard(data['baseRevision'],data.get('seed'),data.get('redraw',False),data.get('evidence','')))
                    if path=='/api/workflow/director':return self.json(course.save_director(data['director'],data['baseRevision']))
                    if path=='/api/workflow/style':return self.json(course.select_style(data['id'],data['baseRevision'],data['evidence']))
                raise ValueError('未知课程操作')
            if path=='/api/save':return self.json(self.space.save(data['document'],data['baseRevision']))
            if path=='/api/clean-caption':return self.json(dict(text=clean_caption(data['text'])))
            if path=='/api/preview-audio':
                doc=data['document'];audio=self.space.audio(doc)
                name=self.space.audio_key(doc)+'.wav'
                dest=self.space.work/'preview'/name;ensure_dir(dest.parent)
                if not dest.exists():shutil.copy2(audio,dest)
                return self.json(dict(url='/preview-audio/'+name))
            if path=='/api/export':
                return self.json(self.space.start_export(data['revision'],data['start'],data['end'],'http://'+self.headers['Host'],data.get('purpose') or None,data.get('review_run_id')))
            raise ValueError('未知操作')
        except FileExistsError as exc:self.json(dict(error=str(exc)),409)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as exc:self.json(dict(error=str(exc)),400)


def serve(root,port=0):
    http.server.ThreadingHTTPServer.request_queue_size=128
    server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler);server.workspace=Workspace(root)
    if (server.workspace.project/'course-state.json').is_file():
        from workflow import VERSION,service_build
        server.runtime_build=service_build()
        from execution_runtime_identity import capture
        server.execution_runtime=capture()
        atomic(server.workspace.project/'work/workbench-service.json',dict(pid=os.getpid(),version=VERSION,url='http://127.0.0.1:'+str(server.server_address[1])))
    print('WORKBENCH_URL=http://127.0.0.1:'+str(server.server_address[1]),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import');imp.add_argument('--course',type=Path,required=True);imp.add_argument('--out',type=Path,required=True)
    launch=sub.add_parser('serve');launch.add_argument('course',type=Path);launch.add_argument('--port',type=int,default=0)
    config=sub.add_parser('configure');config.add_argument('course',type=Path);config.add_argument('--spec',type=Path,required=True)
    export=sub.add_parser('export');export.add_argument('course',type=Path);export.add_argument('--server',required=True);export.add_argument('--start',type=float,default=0);export.add_argument('--end',type=float)
    export.add_argument('--purpose',choices=['pilot','final'],help='独立短小样也可以导出其完整时间线；整片用途需要小样确认')
    args=parser.parse_args()
    if args.command=='import':import_course(args.course,args.out)
    elif args.command=='configure':
        from authoring import configure
        configure(args.course,args.spec)
    elif args.command=='export':
        import urllib.request
        url=args.server.rstrip('/');parsed=urllib.parse.urlparse(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path:raise ValueError('请提供本次工作台实际打印的127.0.0.1地址')
        space=Workspace(args.course);doc=read(space.file)
        from workflow import local_json
        current=local_json(url+'/api/document')
        if current!=doc:raise ValueError('该服务打开的不是当前保存工程')
        payload=json.dumps(dict(revision=doc['revision'],start=args.start,end=args.end if args.end is not None else duration(doc)/doc['fps'],purpose=args.purpose)).encode()
        job=local_json(url+'/api/export',json.loads(payload))
        until=time.monotonic()+14400
        while time.monotonic()<until:
            job=local_json(url+'/api/jobs/'+job['id'])
            if job['status']=='complete':print(json.dumps(job,ensure_ascii=False,indent=2));return
            if job['status'] in ['failed','missing']:raise ValueError(job.get('error','导出未完成'))
            time.sleep(1)
        raise ValueError('等待导出超时；工程和任务日志保留，请检查实际任务状态')
    else:serve(args.course,args.port)
