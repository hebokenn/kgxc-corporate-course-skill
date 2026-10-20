"""Default editable authoring contract for new courses; legacy import is separate."""
from pathlib import Path
import copy
import hashlib
import json
import math
import shutil
import subprocess
from runtime import ensure_dir


def native_fingerprint(project):
    root=Path(project);h=hashlib.sha256()
    for parent in ['native','assets','audio','media','source']:
        folder=root/parent
        if folder.exists():
            for p in sorted(folder.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:
                    h.update(str(p.relative_to(root)).encode());h.update(p.read_bytes())
    for name in ['renderer.js','renderer.html','render_worker.py','backend.py','authoring.py','timeline.py','timeline.js','runtime.py']:
        f=Path(__file__).resolve().parent/name
        h.update(('@runtime/'+name).encode());h.update(f.read_bytes())
    return h.hexdigest()


def init_project(project, skill_root):
    from backend import atomic
    p=Path(project);skill=Path(skill_root)
    shutil.copytree(skill/'workbench/starter',p/'native',dirs_exist_ok=True)
    font=p/'native/assets/fonts';ensure_dir(font)
    original=skill/'libraries/illustration/scripts/engine/lib/fonts'
    shutil.copy2(original/'NotoSansSC-500.woff',font/'CourseHan.woff')
    shutil.copy2(original/'OFL.txt',font/'OFL.txt')
    doc=dict(schema='course-workbench/1',revision=0,status='draft',title='待输入课程名称',fps=30,width=1920,height=1080,
             adapter='scene-graph-v1',sourceDurationFrames=1,introFrames=0,bodyEndFrame=1,
             font='native/assets/fonts/CourseHan.woff',media=dict(audio=None,intro=None,outro=None),
             holds=[],cuts=[],captions=[],fields=[],assets=[],scenes=[],sceneGraph=dict(background='#f3f2ec',nodes=[]),
             captionStyle=dict(fontSize=42,y=990,fill='#ffffff',stroke='#172b38',strokeWidth=8),
             audio=dict(gain=1,voice='Aiden 原速 · 尚未生成配音',speed=1))
    atomic(p/'workbench.json',doc)
    return doc


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n.get('children',[]))


def graph_errors(doc):
    errors=[];nodes=list(walk(doc.get('sceneGraph',{}).get('nodes',[])));ids=set();scene_ids={s['id'] for s in doc['scenes']};assets={a['id'] for a in doc['assets']}
    allowed={'text','image','rect','ellipse','path','line','group'};motion={'x','y','opacity','rotation','scaleX','scaleY','width','height'}
    if doc.get('status')!='draft' and not nodes:errors.append('课程场景图为空，不能交付空画布')
    for n in nodes:
        if not n.get('id') or n['id'] in ids:errors.append('画面对象ID缺失或重复')
        ids.add(n.get('id'))
        if n.get('type') not in allowed:errors.append('不支持的画面类型 '+str(n.get('type')))
        if n.get('sceneId') and n['sceneId'] not in scene_ids:errors.append('画面引用不存在的场景 '+n['id'])
        if n.get('type')=='image' and n.get('assetId') not in assets:errors.append('图片节点缺少素材 '+n['id'])
        for a in n.get('motion',[]):
            if a.get('property') not in motion or not all(isinstance(a.get(k),(int,float)) and math.isfinite(a[k]) for k in ['from','to','startFrame','endFrame']) or a['endFrame']<=a['startFrame']:
                errors.append('动作参数无效 '+n['id'])
    fields=doc['fields'];text_bindings={f['objectId'] for f in fields if f['property']=='text'}
    if any(n.get('type')=='text' and n['id'] not in text_bindings for n in nodes):errors.append('存在未登记到工作台的画面文字')
    if any(f['objectId'] not in ids for f in fields):errors.append('工作台字段未绑定到画面对象')
    return errors


def configure(course, spec_path):
    from backend import read,atomic,safe,validate
    p=Path(course).resolve();p=p if (p/'workbench.json').exists() else p/'project'
    old=read(p/'workbench.json')
    if (p/'course-state.json').is_file():
        from workflow import Course
        course=Course(p)
        course.require_video('style') if course.modern() else course.require('content')
    if old.get('status')!='draft' or old['revision']!=0:raise ValueError('已制作或编辑的工程不重新初始化；直接修改现有工程，保留工作台改动')
    spec=read(spec_path);d=copy.deepcopy(old)
    d.update({k:spec[k] for k in ['title','sourceDurationFrames','scenes','captions','media','sceneGraph'] if k in spec})
    d['status']='ready';d['bodyEndFrame']=spec.get('bodyEndFrame',d['sourceDurationFrames']);d['introFrames']=spec.get('introFrames',0)
    d['adapter']=spec.get('adapter','scene-graph-v1');d['audio']['voice']=spec.get('voice','Aiden 原速 · 以实际配音文件为准')
    if spec.get('font'):d['font']=spec['font']
    d['assets']=[dict(id=a['id'],label=a.get('label',a['id']),path=a['path'],originalPath=a['path']) for a in spec.get('assets',[])]
    if d['adapter']=='scene-graph-v1':
        d['fields']=[]
        for n in walk(d['sceneGraph']['nodes']):
            prop='text' if n['type']=='text' else 'position'
            d['fields'].append(dict(id=n['id']+':'+prop,target='node',objectId=n['id'],sceneId=n.get('sceneId',''),property=prop,
                                    label=('文字 · ' if prop=='text' else '位置 · ')+n['id'],text=n.get('text',''),dx=0,dy=0))
    elif d['adapter']=='seek-bridge-v1':d['fields']=spec.get('fields',[])
    else:raise ValueError('新课只使用通用场景图或统一seek桥接，不使用国补专用适配器')
    validate(d,p)
    if not d['media'].get('audio'):raise ValueError('尚未接入实际混音；保留可打开的草稿，不能标为可导出')
    actual=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(safe(p,d['media']['audio']))]))['format']['duration'])
    if abs(actual-d['sourceDurationFrames']/30)>.12:raise ValueError('课程时间轴与真实混音时长不一致；请先按实际音轨对齐')
    atomic(p/'workbench.json',d)
    config=p/'project.json'
    if config.exists():
        cfg=read(config);cfg['course_title']=d['title'];cfg['workbench']=dict(required=True,document='workbench.json',adapter=d['adapter'],contract_version=1);atomic(config,cfg)
    print(p/'workbench.json');return d
