"""Select a renderer from actual composition requirements; never discard effects."""
import copy
import hashlib
import math
from pathlib import Path
import shutil
import uuid
from motion_catalog import CATALOG

LIBRARIES = ('util.js', 'paint.js', 'motion.js', 'typo.js', 'diagram.js', 'ui.js', 'camera.js')
TEXT_EFFECTS = {'chars-in', 'text-rise', 'blur-in', 'typewriter'}
EFFECTS = {
    'chars-in': 'TY.charsIn: editable text with staggered characters',
    'text-rise': 'TY.rise: text rises through a clipping mask',
    'blur-in': 'TY.blurIn: blur, displacement and opacity',
    'typewriter': 'TY.typed: reveal characters without splitting editable text',
    'draw-on': 'DG.drawPartial: reveal a polyline by its real arc length',
    'mask-reveal': 'Canvas clip: reveal text, images or a group',
    'marker': 'TY.marker: highlight behind text or objects',
    'underline': 'TY.underline: draw an emphasis line',
    'gradient': 'Canvas linear/radial gradient fills and backgrounds',
    'mesh-gradient': 'UI.mesh: deterministic moving gradient background',
    'camera': 'CAM.apply: world camera with editable objects',
    'easing': 'MO: analytical easing and spring functions',
}
EFFECTS.update({key:value['purpose'] for key,value in CATALOG.items()})
EASES = {'linear', 'smooth', 'sineInOut', 'cubicIn', 'cubicOut', 'cubicInOut',
         'quartOut', 'quintOut', 'quintInOut', 'expoIn', 'expoOut', 'expoInOut',
         'backOut', 'elasticOut', 'appleOut', 'emphasized', 'k75', 'easyEase',
         'longTail', 'smoothSpring', 'snappy', 'bouncy'}
CONTENT_ASSETS_PRIOR_ENGINE_SHA256 = '09edb7d6a46c804e9c87528c564817ea91c7efa23d3da7be81f8105274f607cd'
PRIOR_ENGINE_SHA256 = '937481a1c77cdb571bd14abca34a9ebb72cde3f581d22ef62bce517c57abc2be'
PRIOR_ENTRY_SHA256 = '83f2035f70b5148e0de613b93d225abaf1827e77852cb90377f821fc1b9e40c3'
LEGACY_ENGINE_SHA256 = '07eebcc6d8a0f29e3f619f29d74f8ce136dadcdc558043c3ee03bb8753fc30a7'


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get('children', []))


def capabilities():
    return dict(routes={
        'scene-graph': dict(adapter='scene-graph-v1', use='basic shapes, images and transform keyframes'),
        'motion-canvas': dict(adapter='seek-bridge-v1', use='built-in effects with automatic editable bindings', effects=EFFECTS),
        'native-canvas': dict(adapter='seek-bridge-v1', use='custom Canvas/Three.js/other native implementation; apply/seek required'),
    }, effects=EFFECTS, executable_motion_count=len(CATALOG),
        teaching_modules=__import__('teaching_modules').catalog(), content_assets=__import__('content_assets').catalog(), easing=sorted(EASES),
        boundary='DOM-only animation needs a Canvas implementation for workbench export; 3D/assets/dependencies are not installed automatically')


def requirements(spec):
    if spec.get('sceneGraph',{}).get('modules') or spec.get('sceneGraph',{}).get('materials'):
        spec=__import__('teaching_modules').expand(spec)
    requested = spec.get('rendering', {}).get('requiredEffects', [])
    if not isinstance(requested, list) or any(not isinstance(x, str) for x in requested):
        raise ValueError('rendering.requiredEffects 须为能力名称数组；运行 course_tools.py capabilities 查看')
    result = set(requested)
    graph = spec.get('sceneGraph', {})
    for node in walk(graph.get('nodes', [])):
        for effect in node.get('effects', []):
            result.add(effect.get('type', 'unknown-effect'))
        for name in ['fill', 'stroke']:
            if isinstance(node.get(name), dict):
                result.add('gradient' if node[name].get('type') in ['linear-gradient', 'radial-gradient'] else node[name].get('type', 'unknown-fill'))
        if any(a.get('ease', 'smooth') not in ['linear', 'smooth'] for a in node.get('motion', [])):
            result.add('easing')
    background = graph.get('background')
    if isinstance(background, dict):
        result.add('gradient' if background.get('type') in ['linear-gradient', 'radial-gradient'] else background.get('type', 'unknown-background'))
    if graph.get('camera'):
        result.add('camera')
    return sorted(result)


def plan(spec):
    required = requirements(spec)
    route = spec.get('rendering', {}).get('route', 'auto')
    if route not in ['auto', 'scene-graph', 'motion-canvas', 'native-canvas']:
        raise ValueError('未知渲染路线 '+str(route))
    custom = sorted(set(required) - set(EFFECTS))
    if route == 'auto':
        if spec.get('adapter') == 'seek-bridge-v1' and not spec.get('rendering'):
            route = 'native-canvas'  # Preserve existing custom integrations.
        else:
            route = 'native-canvas' if custom else 'motion-canvas' if required else 'scene-graph'
    errors = []
    if route == 'scene-graph' and required:
        errors.append('简易画布不能满足 '+', '.join(required)+'；选择 motion-canvas 或提供实际 native-canvas 实现')
    if route == 'motion-canvas' and custom:
        errors.append('内置动效未封装 '+', '.join(custom)+'；须实现 native-canvas，不得忽略要求')
    if route == 'native-canvas' and spec.get('adapter') != 'seek-bridge-v1':
        errors.append('需要自定义 Canvas 渲染与真实 apply/seek 绑定；完成后显式声明 adapter=seek-bridge-v1')
    return dict(route=route, adapter='scene-graph-v1' if route == 'scene-graph' else 'seek-bridge-v1',
                requiredEffects=required, customRequirements=custom, ready=not errors, errors=errors,
                reason='保留已实现的自定义渲染' if route == 'native-canvas' else '按实际动效要求接入内置动画库' if required else '基础图形及变换足以表达本段内容')


def _number(value):
    return type(value) in [int, float] and math.isfinite(value)


def effect_errors(spec):
    """Validate public effect parameters before a browser or export is started."""
    errors = []
    total = spec['sourceDurationFrames']
    graph = spec.get('sceneGraph', {})
    inferred=copy.deepcopy(spec);inferred.pop('rendering',None)
    missing=set(spec.get('rendering',{}).get('requiredEffects',[]))-set(requirements(inferred))
    if missing:errors.append('仅声明但尚未在构图中实现的动效：'+', '.join(sorted(missing)))
    for node in walk(graph.get('nodes', [])):
        effects = node.get('effects', [])
        if not isinstance(effects, list):
            errors.append('effects 须为数组 '+str(node.get('id')))
            continue
        if sum(e.get('type') in TEXT_EFFECTS for e in effects) > 1:
            errors.append('一个文字对象只选择一种入场方式 '+node['id'])
        for e in effects:
            kind = e.get('type')
            if kind not in EFFECTS or kind in ['gradient', 'mesh-gradient', 'camera', 'easing']:
                errors.append('未知节点动效 '+str(kind))
                continue
            if not all(type(e.get(k)) is int for k in ['startFrame', 'endFrame']) or not 0 <= e['startFrame'] < e['endFrame'] <= total:
                errors.append('动效起止须为课程范围内的绝对整数帧 '+node['id'])
            if kind in TEXT_EFFECTS and node['type'] != 'text':
                errors.append(kind+' 只适用于可编辑文字')
            allowed=CATALOG.get(kind,{}).get('nodes',['*'])
            if '*' not in allowed and node['type'] not in allowed:errors.append(kind+' 不适用于 '+node['type'])
            if kind in ['path-follow','route-progress','flow-token','check-draw','cross-draw','brace-draw']:
                points=e.get('points',node.get('points',[]))
                if len(points)<2 or any(not isinstance(p,list) or len(p)!=2 or not all(_number(v) for v in p) for p in points):errors.append(kind+' 缺少真实路径坐标')
            if kind in ['group-collect','timeline-reflow','balance']:
                required=['from','to'] if kind=='group-collect' else ['to'] if kind=='timeline-reflow' else ['values']
                if any(not isinstance(e.get(k),list) or len(e[k])!=len(node.get('children',[])) for k in required):errors.append(kind+' 参数须与真实子对象一一对应')
            if kind=='record-filter' and (not isinstance(e.get('keep'),list) or any(type(v) is not int or not 0<=v<len(node.get('children',[])) for v in e['keep'])):errors.append('筛选须提供有效 keep 记录序号')
            if kind=='correct-replace' and not isinstance(e.get('fromText'),str):errors.append('差异纠正须提供起态 fromText')
            if kind=='presenter-gesture':
                assets={a['id'] for a in spec.get('assets',[])}
                if any(e.get(k) not in assets for k in ['kgAsset','openAsset','blinkAsset']):errors.append('人物手势缺少原始品牌素材绑定')
            if kind == 'draw-on':
                pts = node.get('points', [])
                if node['type'] not in ['line', 'path'] or len(pts) < 2 or any(not isinstance(p, list) or len(p) != 2 or not all(_number(v) for v in p) for p in pts):
                    errors.append('draw-on 须提供至少两个真实 points 坐标')
            if kind == 'mask-reveal':
                if not all(_number(node.get(k)) and node[k] > 0 for k in ['width', 'height']):
                    errors.append('mask-reveal 须明确对象或组的 width/height')
                if e.get('direction', 'right') not in ['right', 'left', 'up', 'down']:
                    errors.append('未知遮罩揭示方向')
            for key in ['blur', 'dy', 'stagger', 'scale0', 'size', 'lineWidth', 'skew']:
                if key in e and (not _number(e[key]) or abs(e[key]) > 1000 or key in ['blur','stagger','scale0','size','lineWidth'] and e[key] < 0):
                    errors.append('无效动效参数 '+key)
        for a in node.get('motion', []):
            if a.get('ease', 'smooth') not in EASES:
                errors.append('未知缓动 '+str(a.get('ease')))
    paints = [graph.get('background')]
    for node in walk(graph.get('nodes', [])):
        paints.extend([node.get('fill'), node.get('stroke')])
    for paint in paints:
        if not isinstance(paint, dict):
            continue
        if paint.get('type') == 'mesh-gradient':
            if paint is not graph.get('background'):
                errors.append('mesh-gradient 仅用作背景')
            if not isinstance(paint.get('blobs'), list) or not paint['blobs']:
                errors.append('mesh-gradient 须提供 blobs')
            else:
                for blob in paint['blobs']:
                    if not all(_number(blob.get(k)) for k in ['x','y','r']) or blob['r']<=0 or not isinstance(blob.get('col'),list) or len(blob['col'])!=3 or any(not _number(v) or not 0<=v<=255 for v in blob['col']):
                        errors.append('光斑须有有效 x/y/r 和 RGB col')
                    for k in ['ax','ay','period','ph','a']:
                        if k in blob and (not _number(blob[k]) or k=='period' and blob[k]<=0):errors.append('光斑参数无效 '+k)
            for k in ['scale','blur','grain']:
                if k in paint and (not _number(paint[k]) or paint[k]<0 or k=='scale' and not 0<paint[k]<=1 or k=='grain' and paint[k]>1):errors.append('光斑背景参数无效 '+k)
            continue
        if paint.get('type') not in ['linear-gradient', 'radial-gradient']:
            errors.append('未知填色类型 '+str(paint.get('type')))
            continue
        stops = paint.get('stops', [])
        if len(stops) < 2 or any(not isinstance(s, list) or len(s) != 2 or not _number(s[0]) or not 0 <= s[0] <= 1 or not isinstance(s[1], str) for s in stops):
            errors.append('渐变须提供至少两个 [0至1,色值] 色标')
        keys = ['from', 'to'] if paint['type'] == 'linear-gradient' else ['inner', 'outer']
        for key in keys:
            point = paint.get(key)
            size = 2 if paint['type'] == 'linear-gradient' else 3
            if not isinstance(point, list) or len(point) != size or not all(_number(v) for v in point) or size == 3 and point[2] < 0:
                errors.append('渐变坐标无效 '+key)
    camera = graph.get('camera', {})
    for key in ['x', 'y', 'zoom', 'rotation']:
        if key in camera and (not _number(camera[key]) or key == 'zoom' and camera[key] <= 0):
            errors.append('相机参数无效 '+key)
    for a in camera.get('motion', []):
        if a.get('property') not in ['x', 'y', 'zoom', 'rotation'] or not all(_number(a.get(k)) for k in ['from', 'to', 'startFrame', 'endFrame']) or not 0 <= a['startFrame'] < a['endFrame'] <= total or a.get('ease','smooth') not in EASES or a.get('property') == 'zoom' and min(a['from'],a['to']) <= 0:
            errors.append('相机关键帧无效')
    return errors


def stage_libraries(skill_root, destination):
    """Keep newly scaffolded editable packages usable without the installed Skill."""
    root = Path(skill_root)
    source = root/'libraries/illustration/scripts/engine/lib'
    if not source.is_dir():
        source = Path(__file__).resolve().parent/'motion/lib'
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in LIBRARIES:
        shutil.copy2(source/name, destination/name)
    license_file=source/'LICENSE' if (source/'LICENSE').is_file() else source.parents[2]/'LICENSE'
    shutil.copy2(license_file,destination/'LICENSE')


def prepare(project, selection, skill_root):
    p = Path(project)
    entry = p/'native/index.html'
    base = Path(__file__).resolve().parent
    starter = (base/'starter/index.html').read_bytes()
    managed = (base/'motion/index.html').read_bytes()
    engine=p/'native/scene-engine.js'
    recognized=engine.is_file() and hashlib.sha256(engine.read_bytes()).hexdigest() in {
        LEGACY_ENGINE_SHA256,PRIOR_ENGINE_SHA256,CONTENT_ASSETS_PRIOR_ENGINE_SHA256,hashlib.sha256((base/'starter/scene-engine.js').read_bytes()).hexdigest()}
    if selection['route'] == 'native-canvas':
        if not entry.is_file() or entry.read_bytes() in [starter, managed] and recognized:
            raise ValueError('尚未提供实际自定义渲染器；默认画布不能冒充 native-canvas')
        return
    if selection['route'] == 'scene-graph':
        if entry.read_bytes() != starter:
            raise ValueError('已有其他 native 源码，保留实现并选择对应路线，不自动覆盖')
        return
    if entry.read_bytes() not in [starter, managed] and hashlib.sha256(entry.read_bytes()).hexdigest()!=PRIOR_ENTRY_SHA256 or not recognized:
        raise ValueError('已有自定义 native 源码，不能自动覆盖；请沿用 native-canvas')
    (p/'native/motion').mkdir(exist_ok=True)
    stage_libraries(skill_root, p/'native/motion/lib')
    for name in ['effects.js','teaching-effects.js','m1-mesh.js']:
        shutil.copy2(base/'motion'/name,p/'native/motion'/name)
    shutil.copy2(base/'starter/scene-engine.js', p/'native/scene-engine.js')
    entry.write_bytes(managed)


def upgrade(course, spec_path, base_revision, dry_run=False):
    """Explicitly upgrade a known basic/rich graph, retaining edits and rollback files."""
    from backend import read,atomic,validate,LOCK
    p=Path(course).resolve();p=p if (p/'workbench.json').is_file() else p/'project'
    base=Path(__file__).resolve().parent
    with LOCK:
        old=read(p/'workbench.json');spec=read(spec_path)
        if old['revision']!=base_revision:raise ValueError('工程已更新，请重新读入当前revision；未覆盖编辑')
        if old.get('status')!='ready' or old['adapter'] not in ['scene-graph-v1','seek-bridge-v1'] or old.get('rendering',{}).get('route','scene-graph') not in ['scene-graph','motion-canvas']:
            raise ValueError('自动升级只适用于已制作的通用场景图；保留其他原生实现')
        for key in ['sourceDurationFrames','media','scenes','captions','holds','cuts','font']:
            if key in spec and spec[key]!=old.get(key):raise ValueError('升级渲染器不改动已有时间轴、配音或字幕：'+key)
        d=copy.deepcopy(old);d['sceneGraph']=copy.deepcopy(spec['sceneGraph'])
        d['rendering']=spec.get('rendering',dict(route='auto'));selection=plan(d)
        if not selection['ready'] or selection['route']!='motion-canvas':
            raise ValueError('本命令升级为内置动效画布；其他需求请保留源码后实现实际自定义桥接：'+'; '.join(selection['errors']))
        d['rendering']=selection;d['adapter']=selection['adapter'];bind_fields(d)
        fields={f['id']:f for f in d['fields']}
        for field in old['fields']:
            if field['id'] not in fields:raise ValueError('升级不能删除已有可编辑对象 '+field['id'])
            fields[field['id']].update({k:field[k] for k in ['text','dx','dy']})
        existing={a['id'] for a in d['assets']}
        for asset in spec.get('assets',[]):
            if asset['id'] not in existing:
                d['assets'].append(dict(id=asset['id'],label=asset.get('label',asset['id']),path=asset['path'],originalPath=asset['path']));existing.add(asset['id'])
        d['revision']=old['revision']+1;validate(d,p)
        entry=(p/'native/index.html').read_bytes()
        engine=p/'native/scene-engine.js'
        hashes={LEGACY_ENGINE_SHA256,PRIOR_ENGINE_SHA256,CONTENT_ASSETS_PRIOR_ENGINE_SHA256,hashlib.sha256((base/'starter/scene-engine.js').read_bytes()).hexdigest()}
        if entry not in [(base/'starter/index.html').read_bytes(),(base/'motion/index.html').read_bytes()] and hashlib.sha256(entry).hexdigest()!=PRIOR_ENTRY_SHA256 or not engine.is_file() or hashlib.sha256(engine.read_bytes()).hexdigest() not in hashes:
            raise ValueError('检测到自定义native源码，未覆盖；请保留实现并手动接入所需库')
        if dry_run:return dict(route=selection,currentRevision=old['revision'],nextRevision=d['revision'],dryRun=True)
        backup=p/'workbench-history'/('renderer-'+str(old['revision'])+'-'+uuid.uuid4().hex[:8])
        backup.mkdir(parents=True)
        atomic(backup/'workbench.json',old)
        shutil.copytree(p/'native',backup/'native')
        if (p/'editor').exists():shutil.copytree(p/'editor',backup/'editor',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        try:
            prepare(p,selection,base.parent)
            editor=p/'editor/workbench'
            if editor.resolve()!=base:
                shutil.copytree(base,editor,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                stage_libraries(base.parent,editor/'motion/lib')
                for name in ['workbench.py','workflow.py','single_line_subtitles.py','check_workbench.py','course_tools.py','character_assets.py']:
                    shutil.copy2(base.parent/'scripts'/name,p/'editor/scripts'/name)
                from sound import palette_root,PALETTE
                source=palette_root(p);target=p/'audio/sfx'/PALETTE
                if source.resolve()!=target.resolve():shutil.copytree(source,target,dirs_exist_ok=True)
            if read(p/'workbench.json')!=old:raise ValueError('升级期间工程被其他窗口修改，停止保存')
            atomic(p/'workbench.json',d)
        except Exception:
            shutil.rmtree(p/'native');shutil.copytree(backup/'native',p/'native')
            if (backup/'editor').exists():
                shutil.rmtree(p/'editor');shutil.copytree(backup/'editor',p/'editor')
            raise
        cfg=p/'project.json'
        if cfg.is_file():
            config=read(cfg);config['workbench']=dict(required=True,document='workbench.json',adapter=d['adapter'],contract_version=1);atomic(cfg,config)
        return dict(route=selection,revision=d['revision'],backup=str(backup.relative_to(p)),
                    review='原有成片与确认记录保留；改变画面后的旧运行证据和受影响小样须重新核对')


def bind_fields(doc):
    doc['fields'] = []
    for node in walk(doc['sceneGraph']['nodes']):
        prop = 'text' if node['type'] == 'text' else 'position'
        doc['fields'].append(dict(id=node['id']+':'+prop, target='node', objectId=node['id'],
                                 sceneId=node.get('sceneId',''), property=prop,
                                 label=('文字 · ' if prop == 'text' else '位置 · ')+node['id'],
                                 text=node.get('text',''), dx=0, dy=0))
