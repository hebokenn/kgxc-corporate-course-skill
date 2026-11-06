"""Stage a course-specific vector actor and plan natural travel independently of speech."""
from pathlib import Path
import copy
import hashlib
import math
import shutil

CHANNELS = {'gesture', 'concern', 'relief', 'nod', 'head', 'turn', 'write',
            'reach', 'tryEar', 'shrug', 'yield', 'scribble', 'gazeDown'}
APPEARANCE = {'identity', 'hair', 'hairColor', 'skin', 'age', 'glasses',
              'shirtColor', 'innerColor', 'pantsColor', 'faceShape'}


def natural_walk(start, from_x, to_x, scale=1, fps=30, step_rate=2.6):
    """A starting recipe, refined by viewing: local stride, cadence, then duration."""
    if not all(type(v) in (int, float) and math.isfinite(v)
               for v in (from_x, to_x, scale, step_rate)) or scale <= 0:
        raise ValueError('行走位置、比例和步频须为有限数值，比例为正')
    if type(start) is not int or start < 0 or not 1.8 <= step_rate <= 3.6:
        raise ValueError('起步使用非负整数帧；步频起点为每秒1.8至3.6步')
    distance = abs(to_x-from_x)
    if distance < 1:
        raise ValueError('站立无需生成行走；请安排观察或倾听')
    steps = max(2, math.ceil(distance/(44*scale)))
    return dict(startFrame=start, endFrame=start+round(steps/step_rate*fps),
                fromX=from_x, toX=to_x, steps=steps)


def facing_for(walks, start, end, rest_yaw=0):
    """Author supported turns around travel, leaving the walking body side-on."""
    keys = [dict(frame=start, yaw=rest_yaw)]
    turns = []

    def turn_to(yaw, finish):
        prior = keys[-1]
        if abs(prior['yaw']-yaw) < 1e-6:
            if finish > prior['frame']:
                keys.append(dict(frame=finish, yaw=yaw))
            return
        duration = max(12, round(abs(yaw-prior['yaw'])*30/4))
        begin = finish-duration
        if begin < prior['frame']:
            raise ValueError('两段行走间需要留出停步与转身时间；不要压短调整步')
        if begin > prior['frame']:
            keys.append(dict(frame=begin, yaw=prior['yaw']))
        keys.append(dict(frame=finish, yaw=yaw))
        turns.append(dict(startFrame=begin, endFrame=finish,
                          fromYaw=prior['yaw'], toYaw=yaw))

    for walk in walks:
        yaw = math.copysign(math.pi/2, walk['toX']-walk['fromX'])
        # A scene can open already facing the travel direction.
        if walk['startFrame']-start < 16 and len(keys) == 1:
            keys[0]['yaw'] = yaw
        turn_to(yaw, max(start, walk['startFrame']-3))
        keys.append(dict(frame=walk['endFrame']+3, yaw=yaw))
        rest = walk.get('restYaw', rest_yaw)
        duration = max(12, round(abs(rest-yaw)*30/4))
        if keys[-1]['frame']+duration >= end:
            if abs(rest-yaw) > 1e-6:
                raise ValueError('场景末尾需留出停步转向；离场可显式设置 restYaw 为行进方向')
        else:
            turn_to(rest, keys[-1]['frame']+duration)
    return keys, turns


def stage(design, project, skill_root):
    """Return a new candidate node/assets, preserving existing identities and files."""
    p = Path(project)
    p = p if (p/'workbench.json').is_file() else p/'project'
    if not (p/'workbench.json').is_file():
        raise ValueError('先建立课程工作台')
    identity = design.get('identity')
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError('design.identity 须是本课人物ID；不冒称批准原图的绑定')
    role = design.get('characterRole', 'customer')
    if role not in {'customer', 'store_staff', 'store_manager', 'coach'}:
        raise ValueError('characterRole 须为 customer/store_staff/store_manager/coach')
    outfit=design.get('outfit','jacket')
    if role=='customer' and outfit not in {'jacket','tee','shirt'}:raise ValueError('顾客服装须为 jacket/tee/shirt')
    if design.get('faceShape','round') not in {'round','angular'}:raise ValueError('脸型须为 round/angular')
    if design.get('hair','short') not in {'spiky','mature','bob','pony','short','side-part','sidepart'}:raise ValueError('请使用已有可动发型 spiky/mature/bob/pony/short/side-part')
    a = {k: copy.deepcopy(design[k]) for k in APPEARANCE if k in design}
    a.update(characterRole=role, shirt=outfit if role == 'customer' else
             'blue' if role == 'store_staff' else 'black')
    assets = []
    if role != 'customer':
        src = Path(skill_root)/'assets/profiles/kgxc/kg-original.png'
        if role == 'coach':
            # The original Coach master embeds its mark; do not redraw or substitute KG.
            rel = design.get('logoPath', '')
            src = (p/rel).resolve()
            if not rel or not src.is_relative_to(p.resolve()) or not src.is_file():
                raise ValueError('新绘 Coach 需提供本工程内已获准的独立 MyCoach 原标 logoPath')
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if role == 'coach' and design.get('logoSha256') != digest:
            raise ValueError('Coach 原标需绑定已核对的 logoSha256')
        dest = p/'assets/acting'/(digest[:12]+'-'+src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise ValueError('保留已编辑标识，使用新版本路径')
        if not dest.exists():
            shutil.copy2(src, dest)
        aid = 'acting-mark-'+digest[:12]
        assets.append(dict(id=aid, path=str(dest.relative_to(p)), label=role+' original mark'))
        a.update(logoAsset=aid, logoSha256=digest, uniformMark='MyCoach' if role == 'coach' else 'KG')
    scale = design.get('height', 600)/375
    start, end = design.get('startFrame', 0), design['endFrame']
    walks = []
    for item in design.get('travel', []):
        w = natural_walk(item['startFrame'], item['fromX'], item['toX'], scale,
                         step_rate=item.get('stepRate', 2.6))
        if 'restYaw' in item:
            w['restYaw'] = item['restYaw']
        walks.append(w)
    if walks:
        a['facing'], a['turns'] = facing_for(walks, start, end, design.get('restYaw', 0))
    else:
        a['facing'], a['turns'] = [dict(frame=start, yaw=design.get('restYaw', 0))], []
    a['walks'] = walks
    for key in ['keys', 'blinks', 'speech', 'targets', 'props', 'targetId']:
        if key in design:
            a[key] = copy.deepcopy(design[key])
    node = dict(id=identity, type='group', sceneId=design['sceneId'], role='subject',
                x=design['x'], y=design['floorY'], width=280, height=375,
                scaleX=scale, scaleY=scale, startFrame=start, endFrame=end, vectorActor=a)
    spec = dict(sourceDurationFrames=end, assets=assets, sceneGraph=dict(nodes=[node]))
    # Targets may be added when merging the result into the real course.
    problems = errors(spec, check_targets=False)
    if problems:
        raise ValueError('; '.join(problems))
    return dict(assets=assets, node=node, representation='solid-vector-acting/1',
                note='本课简化人物候选；按既有设计与小样确认使用。合并至顶层nodes后按对白安排手势、视线和自己的speech。')


def errors(doc, check_targets=True):
    """Static input safeguards. Actual support, silhouettes and timing need rendering."""
    from authoring import walk
    nodes = list(walk(doc.get('sceneGraph', {}).get('nodes', [])))
    top = {id(n) for n in doc.get('sceneGraph', {}).get('nodes', [])}
    ids = {n.get('id') for n in nodes}
    assets = {a.get('id') for a in doc.get('assets', [])}
    total = doc.get('sourceDurationFrames', 0)
    result = []
    num = lambda x: type(x) in (int, float) and math.isfinite(x)
    for n in nodes:
        a = n.get('vectorActor')
        if not a:
            continue
        label = str(n.get('id'))
        def reject(message):
            result.append(message+' '+label)
        if n.get('type') != 'group' or id(n) not in top:
            reject('vectorActor 使用顶层group，根坐标为脚下地面')
        if (not num(n.get('scaleX', 1)) or n.get('scaleX', 1) <= 0 or
                n.get('scaleX', 1) != n.get('scaleY', 1) or n.get('rotation', 0) or n.get('matrix')):
            reject('人物使用正向等比缩放，朝向通过facing设置')
        if any(m.get('property') != 'opacity' for m in n.get('motion', [])):
            reject('人物位移与转向由walks/facing控制；根motion仅保留整人淡入淡出')
        x, y = n.get('x'), n.get('y')
        if not num(x) or not num(y):
            reject('人物需真实x与floorY坐标')
        for name in ['walks', 'turns']:
            previous = -1
            for item in a.get(name, []):
                s, z = item.get('startFrame'), item.get('endFrame')
                if not (type(s) is int and type(z) is int and 0 <= s < z <= total and s >= previous):
                    reject(name+'起止须有序、不重叠且位于课程范围')
                    continue
                previous = z
                if name == 'walks' and (type(item.get('steps')) is not int or item['steps'] < 2 or
                        not num(item.get('fromX')) or not num(item.get('toX')) or item['fromX'] == item['toX']):
                    reject('行走需不同起终点和至少两步')
                if name == 'turns' and any(not num(item.get(k)) or abs(item[k]) > math.pi/2+1e-6
                                           for k in ['fromYaw', 'toYaw']):
                    reject('转身需有效的起终朝向')
        for name in ['keys', 'facing']:
            previous = -1
            for item in a.get(name, []):
                f = item.get('frame')
                if type(f) is not int or not 0 <= f <= total or f <= previous:
                    reject(name+'关键帧须严格递增且位于课程范围')
                else:
                    previous = f
                if name == 'facing' and (not num(item.get('yaw')) or abs(item['yaw']) > math.pi/2+1e-6):
                    reject('当前侧面到正面人物的yaw范围为[-pi/2,pi/2]，不支持背面')
                if name == 'keys' and any(k not in CHANNELS or not num(v) or
                        not (-1 <= v <= 1 if k in {'head', 'turn'} else 0 <= v <= 1)
                        for k, v in item.get('values', {}).items()):
                    reject('人物关键值须为已支持的有限数值通道')
        if a.get('walks') and not a.get('facing'):
            reject('行走须同时安排全身朝向facing和转身调整步turns')
        # Diagnose the common paper-cutout slide before asking for visual fine-tuning.
        facing = a.get('facing', [])
        valid_facing = bool(facing) and all(type(k.get('frame')) is int and num(k.get('yaw')) for k in facing)
        def heading_at(frame):
            prior = facing[0]
            for key in facing[1:]:
                if key['frame'] <= frame:
                    prior = key
                    continue
                u = max(0, min(1, (frame-prior['frame'])/max(1, key['frame']-prior['frame'])))
                return prior['yaw']+(key['yaw']-prior['yaw'])*u*u*(3-2*u)
            return prior['yaw']
        previous_x = x
        for w in a.get('walks', []):
            if not all(num(w.get(k)) for k in ['fromX', 'toX', 'startFrame', 'endFrame']):
                continue
            if num(previous_x) and abs(w['fromX']-previous_x) > .01:
                reject('行走起点需接上当前脚下位置，避免瞬移')
            previous_x = w['toX']
            if valid_facing:
                yaw = math.copysign(math.pi/2, w['toX']-w['fromX'])
                points = {w['startFrame'], w['startFrame']+2, w['endFrame']-1, w['endFrame']+1}
                points.update(k['frame'] for k in facing if w['startFrame'] <= k['frame'] <= w['endFrame'])
                if any(abs(heading_at(frame)-yaw) > .001 for frame in points):
                    reject('行走期间全身朝向需与行进方向一致，转身排在停步区间')
            if any(type(t.get('startFrame')) is int and type(t.get('endFrame')) is int and
                   max(t['startFrame'], w['startFrame']) < min(t['endFrame'], w['endFrame']) for t in a.get('turns', [])):
                reject('先完成调整步再行走，转身与平移区间需分开')
        for line in a.get('speech', []):
            env, s = line.get('envelope'), line.get('startFrame')
            if (type(s) is not int or not isinstance(env, list) or not env or s < 0 or s+len(env) > total or
                    any(not num(v) or not 0 <= v <= 1 for v in env)):
                reject('speech须为角色本人对白的逐帧0至1能量，不用讲师旁白')
        for b in a.get('blinks', []):
            if not isinstance(b, list) or len(b) != 3 or any(type(v) is not int for v in b) or not 0 <= b[0] < b[1] < b[2] <= total:
                reject('眨眼需开始、闭合、回开三帧')
        if check_targets and any(t.get('id') not in ids for t in a.get('targets', [])):
            reject('视线目标需真实对象ID')
        if check_targets and a.get('targetId') and a['targetId'] not in ids:
            reject('targetId需真实对象ID')
        if a.get('characterRole') in {'store_staff', 'store_manager', 'coach'} and a.get('logoAsset') not in assets:
            reject('公司角色需原版胸标，使用stage-acting绑定')
    if check_targets and not result and doc.get('conversationPolicy',{}).get('required'):
        result.extend(conversation_errors(doc))
    return result


def conversation_errors(doc):
    """Reject absent addressees and reversed heads during actual character lines."""
    from authoring import walk
    actors={n['id']:n for n in walk(doc.get('sceneGraph',{}).get('nodes',[])) if n.get('vectorActor')}
    problems=[]
    def heading(keys,frame):
        if not keys:return 0
        prior=keys[0]
        for nxt in keys:
            if nxt['frame']<=frame:prior=nxt;continue
            t=max(0,min(1,(frame-prior['frame'])/(nxt['frame']-prior['frame'])));t=t*t*(3-2*t)
            return prior['yaw']+(nxt['yaw']-prior['yaw'])*t
        return prior['yaw']
    def position(node,frame):
        x=node['x']
        for w in node['vectorActor'].get('walks',[]):
            if frame<w['startFrame']:break
            if frame>=w['endFrame']:x=w['toX'];continue
            t=(frame-w['startFrame'])/(w['endFrame']-w['startFrame']);r=.12
            u=t*t/(2*r*(1-r)) if t<r else 1-(1-t)**2/(2*r*(1-r)) if t>1-r else (t-r/2)/(1-r)
            return w['fromX']+(w['toX']-w['fromX'])*u
        return x
    for identifier,node in actors.items():
        actor=node['vectorActor']
        for line in actor.get('speech',[]):
            if line.get('audience')=='viewer':continue
            start=line['startFrame'];end=start+len(line['envelope'])
            for frame in range(start,end):
                if not node.get('startFrame',0)<=frame<node.get('endFrame',doc['sourceDurationFrames']):
                    problems.append(f'对白说话人尚未在场：{identifier}，第{frame}帧');break
                target=next((v['id'] for v in reversed(actor.get('targets',[])) if v['frame']<=frame),actor.get('targetId'))
                listener=actors.get(target)
                if not listener or listener is node or listener.get('sceneId')!=node.get('sceneId') or not listener.get('startFrame',0)<=frame<listener.get('endFrame',doc['sourceDurationFrames']):
                    problems.append(f'对白受话人未在同场实际出现：{identifier} → {target}，第{frame}帧');break
                direction=position(listener,frame)-position(node,frame)
                yaw=heading(actor.get('facing',[]),frame+2)
                if abs(direction)>20 and direction*yaw < -2:
                    problems.append(f'对白时头部背向受话人：{identifier} → {target}，第{frame}帧');break
    return list(dict.fromkeys(problems))


def motion_intervals(node):
    """Actual authored CourseActors movement, excluding speech-only mouth changes."""
    actor=node.get('vectorActor',{});result=[]
    for item in actor.get('walks',[]):
        if item.get('fromX')!=item.get('toX'):result.append((item['startFrame'],item['endFrame']))
    keys=actor.get('facing',[])
    result.extend((a['frame'],b['frame']) for a,b in zip(keys,keys[1:]) if a['yaw']!=b['yaw'])
    for channel in CHANNELS:
        previous=dict(frame=node.get('startFrame',0),value=.1 if channel=='relief' else 0)
        for item in actor.get('keys',[]):
            if channel not in item.get('values',{}):continue
            if previous['value']!=item['values'][channel] and previous['frame']<item['frame']:
                result.append((previous['frame'],item['frame']))
            previous=dict(frame=item['frame'],value=item['values'][channel])
    return result


def inspect(doc):
    """Return dense critical ranges for the production renderer, never approval."""
    from authoring import walk
    total = doc.get('sourceDurationFrames', 0)
    rows = []
    for n in walk(doc.get('sceneGraph', {}).get('nodes', [])):
        if not n.get('vectorActor'):
            continue
        a = n['vectorActor']
        ranges = []
        for w in a.get('walks', []):
            for f, purpose in [(w['startFrame'], '起步：脚底、摆臂、袖口'), (w['endFrame'], '停步：落脚、收臂、回稳')]:
                ranges.append(dict(fromFrame=max(0, f-3), toFrame=min(total-1, f+12), purpose=purpose))
        for t in a.get('turns', []):
            ranges.append(dict(fromFrame=max(0, t['startFrame']-2), toFrame=min(total-1, t['endFrame']+2),
                               purpose='连续转身：头胸胯脚、支撑脚、面部和手臂遮挡'))
        rows.append(dict(objectId=n['id'], denseSourceRanges=ranges,
                         gestureKeyFrames=[k['frame'] for k in a.get('keys', [])]))
    problems = errors(doc)
    return dict(schema='course-acting-inspection/1', status='fail' if problems else 'inspection-plan',
                errors=problems, actors=rows,
                scope='编排与输入检查；需用同一生产渲染器查看连续帧和最终编码，再正常速度观看，不代表演出验收')
