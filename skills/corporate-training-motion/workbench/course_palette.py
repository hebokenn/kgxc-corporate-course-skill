"""Persistent course palette selection, shared by planning and actual compilation."""
import colorsys
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import random
import re
import secrets
import uuid

SCHEMA = 'course-palette-plan/1'
BINDING = 'course-palette-binding/1'
ROLES = ('canvas', 'ink', 'accent', 'secondary', 'soft', 'stroke', 'muted', 'surface', 'error')
FAMILIES = ('green', 'pale-green', 'blue', 'purple', 'red', 'orange', 'yellow', 'pink')


def project_path(course):
    p = Path(course).expanduser().resolve()
    return p if p.name == 'project' or (p/'course-state.json').is_file() or (p/'workbench.json').is_file() else p/'project'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.pending-'+uuid.uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def rgb(color):
    return [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]


def contrast(a, b):
    def light(c):
        vals = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb(c)]
        return sum(v*w for v,w in zip(vals, (.2126,.7152,.0722)))
    high, low = sorted((light(a), light(b)), reverse=True)
    return (high+.05)/(low+.05)


def family(color):
    h, l, s = colorsys.rgb_to_hls(*rgb(color))
    h *= 360
    if s < .12 or l < .06 or l > .98:
        return set()
    key = 'green' if 75 <= h < 170 else 'blue' if 170 <= h < 260 else 'purple' if 260 <= h < 300 else 'pink' if 300 <= h < 345 else 'red' if h >= 345 or h < 15 else 'orange' if h < 45 else 'yellow'
    return {key, 'pale-green'} if key == 'green' and l >= .65 else {key}


def validate(palette):
    if not isinstance(palette, dict) or not palette.get('id') or not palette.get('name'):
        raise ValueError('色板须有id、name及完整角色色值')
    if any(not re.fullmatch(r'#[0-9a-fA-F]{6}', str(palette.get(k, ''))) for k in ROLES):
        raise ValueError('色板须包含九个角色的六位色值：'+', '.join(ROLES))
    for role in ('ink', 'accent', 'secondary', 'muted', 'error'):
        for bg in ('canvas', 'surface', 'soft'):
            if contrast(palette[role], palette[bg]) < 4.5:
                raise ValueError('色板文字对比不足4.5：'+role+' / '+bg)
    return palette


def catalog():
    data = json.loads((Path(__file__).parent/'course-palettes.json').read_text())
    for p in data['palettes']:
        validate(p)
    return data


def read_plan(course):
    path = project_path(course)/'palette-plan.json'
    if not path.is_file():
        return None
    plan = json.loads(path.read_text())
    if plan.get('schema') != SCHEMA:
        raise ValueError('课程色板记录版本无效')
    validate(plan['palette'])
    return plan


def select(course, exclude=None, specified=None, redraw=False, evidence='', seed=None):
    """Only a new course or an explicit command draws. Read/resume never redraws."""
    project = project_path(course)
    project.mkdir(parents=True, exist_ok=True)
    lock = project/'work/palette.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        old = read_plan(project)
        if old and not redraw:
            if specified is not None or exclude is not None and sorted(set(exclude)) != old['exclude']:
                raise ValueError('已保存色板；改色须 --redraw --evidence 记录实际要求')
            return old
        if redraw and not evidence.strip():
            raise ValueError('重新选色须记录用户要求或具体原因')
        state_path = project/'course-state.json'
        state = json.loads(state_path.read_text()) if state_path.is_file() else {}
        if state.get('visual_palette'):
            raise ValueError('已有小样配色确认；沿用实际画面，按受影响范围返修后更新确认，不重签旧记录')
        excluded = sorted(set(old['exclude'] if exclude is None and old else exclude or []))
        if any(x not in FAMILIES for x in excluded):
            raise ValueError('未知禁用色系；可用：'+', '.join(FAMILIES))
        if specified is not None:
            if not evidence.strip():
                raise ValueError('指定色板须记录用户要求或品牌依据')
            pool = [validate(copy.deepcopy(specified))]
        else:
            pool = catalog()['palettes']
        pool = [p for p in pool if not any(family(p[k]) & set(excluded) for k in ROLES)]
        if not pool:
            raise ValueError('禁用色筛选后没有合格色板；请提供符合条件的色板，不能忽略禁用色')
        actual_seed = None if specified is not None else seed or secrets.token_hex(16)
        chosen = copy.deepcopy(pool[0] if specified is not None else random.Random(actual_seed).choice(pool))
        plan = dict(schema=SCHEMA, at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
            mode='specified' if specified is not None else 'random', seed=actual_seed,
            algorithm='user-specified' if specified is not None else 'random.Random(seed).choice(filtered_pool)',
            candidate_pool=pool, candidate_ids=[p['id'] for p in pool], exclude=excluded,
            palette=chosen, evidence=evidence, revision=old['revision']+1 if old else 1,
            approval='candidate; random selection does not approve the storyboard or pilot')
        if old:
            write(project/'palette-history'/(str(old['revision']).zfill(6)+'-'+digest(old)[:12]+'.json'), old)
        write(project/'palette-plan.json', plan)
        board_path = project/'storyboard.json'
        if old and board_path.is_file():
            board = json.loads(board_path.read_text())
            if isinstance(board, dict) and board.get('schema') == 'course-storyboard/1':
                write(project/'palette-history'/(str(old['revision']).zfill(6)+'-storyboard.json'), board)
                board['coursePalette'] = binding(plan)
                p = plan['palette']
                board.setdefault('visual_direction', {})['palette'] = f"{p['name']}：画布{p['canvas']}、文字{p['ink']}、强调{p['accent']}、辅助{p['secondary']}；按本课保存色板，恢复不重抽。"
                write(board_path, board)
                from storyboard import export_html
                export_html(board, project/'storyboard.html')
        document = project/'workbench.json'
        if document.is_file():
            doc = json.loads(document.read_text())
            if doc.get('status') == 'draft' and doc.get('revision') == 0 and not doc.get('sceneGraph', {}).get('nodes'):
                doc['coursePalette'] = binding(plan)
                doc.setdefault('sceneGraph', {})['background'] = chosen['canvas']
                write(document, doc)
        return plan


def binding(plan):
    validate(plan['palette'])
    return dict(schema=BINDING, plan_sha256=digest(plan), palette=copy.deepcopy(plan['palette']), exclude=plan['exclude'])


def bind(spec, plan):
    """Carry the saved selection into the real render spec, with no new draw."""
    out = copy.deepcopy(spec)
    if plan is None:
        return out
    expected = binding(plan)
    if out.get('coursePalette') and out['coursePalette'] != expected:
        raise ValueError('构图色板与本课已保存记录不符')
    out['coursePalette'] = expected
    graph = out.setdefault('sceneGraph', {})
    if 'background' in graph and graph['background'].lower() != plan['palette']['canvas'].lower():
        raise ValueError('画布底色与本课已保存色板不符')
    graph['background'] = plan['palette']['canvas']
    return out


def remap_nodes(nodes, palette, mapping=None):
    """Translate old recipe paints; product/character source colours stay local."""
    role_mapping = mapping or {}
    mapping = {k.lower(): palette[v] for k,v in role_mapping.items()}
    allowed = {palette[k].lower() for k in ROLES}
    def paint(value, role):
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{3,8}', value):
            return value
        key = value.lower()
        if len(key) == 4:
            key = '#'+''.join(c*2 for c in key[1:])
        base, alpha = key[:7], key[7:]
        if base in allowed:
            return value
        target = mapping.get(base, palette['ink' if role == 'text' else 'stroke' if role == 'line' else 'surface'])
        return target+alpha
    def paints(value, role):
        if isinstance(value, dict):
            return {k:paints(v, role) if k in ('fill','stroke','color','colors','stops','fromColor','toColor') else v for k,v in value.items()}
        if isinstance(value, list):
            return [paints(v, role) for v in value]
        return paint(value, role)
    for n in nodes:
        if isinstance(n.get('contentColorReason'), str) and len(n['contentColorReason'].strip()) >= 8:
            continue
        for key in ('fill', 'stroke'):
            if key in n:
                n[key] = paints(n[key], 'text' if n['type'] == 'text' else 'line' if key == 'stroke' else 'surface')
        for e in n.get('effects', []):
            for k in ('color','fill','stroke','colors','stops'):
                if k in e:
                    e[k] = paints(e[k], 'text' if n['type'] == 'text' else 'line' if k == 'stroke' else 'surface')
        remap_nodes(n.get('children', []), palette, role_mapping)
    return nodes


def check(doc, plan=None):
    contract = doc.get('coursePalette')
    if not contract:
        return ['新课缺少已保存课程色板绑定'] if plan else []
    if contract.get('schema') != BINDING:
        return ['课程色板绑定版本无效']
    try:
        p = validate(contract['palette'])
    except (ValueError, KeyError) as error:
        return [str(error)]
    errors = []
    if plan and contract != binding(plan):
        errors.append('画面没有沿用本课已保存色板')
    from visual_identity import colors, paints
    allowed = {p[k].lower() for k in ROLES}
    for role, target, value in paints(doc):
        for c in colors(value):
            base = c[:7]
            neutral = bool(re.fullmatch(r'#[0-9a-f]{6}', base) and base[1:3] == base[3:5] == base[5:7])
            if role == 'canvas' and base != p['canvas'].lower():
                errors.append('画布偏离已保存色板：'+target)
            elif base not in allowed and not neutral:
                errors.append('教学画面颜色未绑定本课色板：'+target+' = '+c)
            if re.fullmatch(r'#[0-9a-f]{6}', base) and family(base) & set(contract.get('exclude', [])):
                errors.append('教学画面使用了禁用色系：'+target+' = '+c)
    return list(dict.fromkeys(errors))
