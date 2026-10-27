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
    marker=root/'motion-contract.json'
    if marker.is_file():h.update(marker.read_bytes())
    for parent in ['native','assets','audio','media','source']:
        folder=root/parent
        if folder.exists():
            for p in sorted(folder.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:
                    h.update(str(p.relative_to(root)).encode());h.update(p.read_bytes())
    for name in ['renderer.js','renderer.html','render_worker.py','backend.py','authoring.py','timeline.py','timeline.js','runtime.py','render_routes.py','motion_quality.py','motion_samples.py','semantic_motion.py','motion_catalog.py','motion_extensions.py','teaching_modules.py','content_assets.py','retail_assets.py','visual_styles.py','visual-styles.json','visual_identity.py','character_rig.py','character_performance.py','performance-profiles.json','motion_evidence.py','character_pose.py','company_characters.py','device_models.py']:
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
    for source,name in [('LXGWWenKai-500.woff','CourseHand.woff'),('NotoSerifSC-sub.woff','CourseSerif.woff'),('NotoSansSC-900.woff','CourseHeavy.woff')]:shutil.copy2(original/source,font/name)
    shutil.copy2(original/'OFL.txt',font/'OFL.txt')
    doc=dict(schema='course-workbench/1',revision=0,status='draft',title='待输入课程名称',fps=30,width=1920,height=1080,
             adapter='scene-graph-v1',sourceDurationFrames=1,introFrames=0,bodyEndFrame=1,
             font='native/assets/fonts/CourseHan.woff',media=dict(audio=None,intro=None,outro=None),
             holds=[],cuts=[],captions=[],fields=[],assets=[],scenes=[],sceneGraph=dict(background='#ffffff',nodes=[]),
             captionStyle=dict(fontSize=42,y=990,fill='#ffffff',stroke='#172b38',strokeWidth=8),
             audio=dict(gain=1,voice='didi 推荐教学男声 · 尚未生成配音',speed=1))
    doc['characterPolicy']=dict(required=True,scope='known company masters require their original uniform mark')
    from motion_quality import policy
    doc['motionPolicy']=policy()
    atomic(p/'motion-contract.json',dict(schema='course-motion-policy/1',required=True,createdBy='5.8.0',semanticRequired=True,stateProofRequired=True))
    from craft_quality import policy as craft_policy
    doc['qualityPolicy']=craft_policy();doc['qualityPolicy']['spatialReviewRequired']=True
    atomic(p/'craft-contract.json',dict(schema='course-craft-policy/1',required=True,coverRequired=True,visualHygieneRequired=True,spatialReviewRequired=True,createdBy='5.7.0'))
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
        for rule in ['enclosesTextIds','nonOverlappingTextIds']:
            if rule in n and (not isinstance(n[rule],list) or not n[rule] or any(not isinstance(i,str) for i in n[rule])):errors.append('文字布局约束无效 '+n['id'])
        if 'crop' in n:
            crop=n['crop']
            if not isinstance(crop,list) or len(crop)!=4 or any(type(v) not in [int,float] or not math.isfinite(v) for v in crop) or min(crop)<0 or crop[2]<=0 or crop[3]<=0 or crop[0]+crop[2]>1 or crop[1]+crop[3]>1:errors.append('图片取景范围无效 '+n['id'])
        if 'clip' in n:
            box=n['clip']
            if not isinstance(box,list) or len(box)!=4 or any(type(v) not in [int,float] or not math.isfinite(v) for v in box) or box[2]<=0 or box[3]<=0:errors.append('局部取景范围无效 '+n['id'])
        if 'matrix' in n:
            matrix=n['matrix']
            if not isinstance(matrix,list) or len(matrix)!=6 or any(type(v) not in [int,float] or not math.isfinite(v) for v in matrix) or abs(matrix[0]*matrix[3]-matrix[1]*matrix[2])<1e-9:errors.append('素材平面变换无效 '+n['id'])
        for a in n.get('motion',[]):
            if a.get('property') not in motion or not all(isinstance(a.get(k),(int,float)) and math.isfinite(a[k]) for k in ['from','to','startFrame','endFrame']) or a['endFrame']<=a['startFrame']:
                errors.append('动作参数无效 '+n['id'])
    fields=doc['fields'];text_bindings={f['objectId'] for f in fields if f['property']=='text'}
    if any(n.get('type')=='text' and n['id'] not in text_bindings for n in nodes):errors.append('存在未登记到工作台的画面文字')
    if any(f['objectId'] not in ids for f in fields):errors.append('工作台字段未绑定到画面对象')
    text_ids={n['id'] for n in nodes if n.get('type')=='text'}
    for n in nodes:
        if any(identifier not in text_ids for rule in ['enclosesTextIds','nonOverlappingTextIds'] for identifier in n.get(rule,[])):errors.append('布局约束引用不存在的文字 '+n['id'])
    from character_performance import errors as performance_errors
    for node in nodes:
        if node.get('performance'):errors.extend(performance_errors(node,doc))
    from render_routes import effect_errors, requirements
    if doc.get('rendering',{}).get('route')=='motion-canvas':errors.extend(effect_errors(doc))
    elif requirements(doc):errors.append('当前简易画布不能实现所需动效；先选择 motion-canvas 或实际自定义渲染')
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
    from teaching_modules import expand
    spec=expand(read(spec_path));d=copy.deepcopy(old)
    d.update({k:spec[k] for k in ['title','sourceDurationFrames','scenes','captions','media','sceneGraph','motionPlan','narrationLinks','teachingModules','contentAssets','visualStyles','storyboardBindings'] if k in spec})
    d['status']='ready';d['bodyEndFrame']=spec.get('bodyEndFrame',d['sourceDurationFrames']);d['introFrames']=spec.get('introFrames',0)
    if any(n.get('enclosesTextIds') or n.get('nonOverlappingTextIds') or n.get('textExclusion') or n.get('supportBinding') for n in walk(d['sceneGraph'].get('nodes',[]))):d['layoutPolicy']=dict(required=True,scope='measured text enclosure, row separation and declared character exclusion on each rendered state')
    from render_routes import plan,prepare,bind_fields
    selection=plan(spec)
    if not selection['ready']:raise ValueError('; '.join(selection['errors']))
    d['rendering']=selection;d['adapter']=selection['adapter'];d['audio']['voice']=spec.get('voice','didi 推荐教学男声 · 以实际配音文件为准')
    if spec.get('font'):d['font']=spec['font']
    d['assets']=[dict(id=a['id'],label=a.get('label',a['id']),path=a['path'],originalPath=a['path']) for a in spec.get('assets',[])]
    if selection['route'] in ['scene-graph','motion-canvas']:
        bind_fields(d)
    elif d['adapter']=='seek-bridge-v1':d['fields']=spec.get('fields',[])
    else:raise ValueError('新课只使用通用场景图或统一seek桥接，不使用国补专用适配器')
    validate(d,p)
    if (p/'course-state.json').is_file() and course.storyboard_mode():
        from storyboard import check_bindings
        issues=check_bindings(course.storyboard(),course.sample_plan(),d,full=course.status()['stage']=='final')
        if issues:raise ValueError('；'.join(issues))
    if not d['media'].get('audio'):raise ValueError('尚未接入实际混音；保留可打开的草稿，不能标为可导出')
    actual=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(safe(p,d['media']['audio']))]))['format']['duration'])
    if abs(actual-d['sourceDurationFrames']/30)>.12:raise ValueError('课程时间轴与真实混音时长不一致；请先按实际音轨对齐')
    prepare(p,selection,Path(__file__).resolve().parents[1])
    atomic(p/'workbench.json',d)
    config=p/'project.json'
    if config.exists():
        cfg=read(config);cfg['course_title']=d['title'];cfg['workbench']=dict(required=True,document='workbench.json',adapter=d['adapter'],contract_version=1);atomic(config,cfg)
    print(p/'workbench.json');return d
