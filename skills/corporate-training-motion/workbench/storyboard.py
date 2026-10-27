"""Whole-course alternatives and reproducible, coverage-aware pilot sampling.

Checks establish traceability and workflow state, not aesthetic or human approval.
"""
import copy
import hashlib
import html
import json
import random
import re
import secrets
from pathlib import Path

SCHEMA = 'course-storyboard/1'
SAMPLING = 'course-storyboard-samples/1'
MODE = 'storyboard-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def paragraphs(text):
    """Only actual spoken/learner instructions; retain stable source ordering."""
    tagged = '【口播】' in text or '【练习引导】' in text
    active = not tagged
    unit = 0
    result, pending = [], []

    def flush():
        if pending:
            value = '\n'.join(pending).strip()
            if value:
                result.append(dict(id=f'P{len(result)+1:03}', text=value,
                                   unit_index=unit, sha256=hashlib.sha256(value.encode()).hexdigest()))
            pending.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r'^#{1,3}\s+.*(?:制作及来源|制作备注|来源备注|制作端)', stripped):
            flush()
            break
        if re.match(r'^##\s+', stripped):
            flush()
            unit += 1
            active = not tagged
            continue
        if stripped in ['【口播】', '【练习引导】']:
            flush()
            active = True
            continue
        if not stripped or stripped == '---' or stripped.startswith('#'):
            flush()
            continue
        if active:
            pending.append(line)
    flush()
    return result


def check(board, script_text, script_sha, design,reading_required=False):
    errors = []
    if not isinstance(board, dict):
        return dict(ok=False, errors=['分镜须为对象'], pending=[])
    if board.get('schema') != SCHEMA:
        errors.append('分镜格式须为 ' + SCHEMA)
    if board.get('script_sha256') != script_sha:
        errors.append('分镜未绑定当前逐字稿')
    if reading_required and board.get('reading_contract')!='reading-pacing-v1':errors.append('新课分镜须声明 reading_contract=reading-pacing-v1，并分别设计动作与信息阅读')
    reading_required=reading_required or board.get('reading_contract')=='reading-pacing-v1'
    visual = board.get('visual_direction', {})
    if not isinstance(visual, dict) or any(not str(visual.get(k, '')).strip()
            for k in ['palette', 'typography', 'graphics', 'atmosphere']):
        errors.append('请说明共用美术规范：配色、字体、图形材质和气质')
    units = {u['id'] for u in design.get('units', []) if u.get('disposition') == 'core'}
    assessments = {a['id'] for a in design.get('assessments', [])}
    source = paragraphs(script_text)
    lookup = {p['id']: p for p in source}
    segments = board.get('segments', [])
    if not isinstance(segments, list) or not segments:
        return dict(ok=False, errors=errors + ['缺少全课教学片段'], pending=[])
    seen, covered_units, covered_assessments, ids, pending = [], set(), set(), set(), []
    for segment in segments:
        sid = segment.get('id') if isinstance(segment, dict) else None
        if not isinstance(sid, str) or not sid or sid in ids:
            errors.append('片段ID缺失或重复')
            continue
        ids.add(sid)
        for key in ['teaching_goal', 'kind', 'risk', 'recommendation_reason']:
            if not isinstance(segment.get(key), str) or not segment[key].strip():
                errors.append(sid + ' 缺少 ' + key)
        if segment.get('risk') not in ['normal', 'high']:
            errors.append(sid + ' 风险须为normal或high')
        uid = segment.get('unit_id')
        if uid not in units:
            errors.append(sid + ' 未对应主课单元')
        covered_units.add(uid)
        aid = segment.get('assessment_ids', [])
        if not isinstance(aid, list) or any(a not in assessments for a in aid):
            errors.append(sid + ' 练习引用无效')
        else:
            covered_assessments.update(aid)
        refs = segment.get('source_paragraph_ids', [])
        if not isinstance(refs, list) or not refs or any(p not in lookup for p in refs):
            errors.append(sid + ' 逐字稿段落引用无效')
        else:
            seen.extend(refs)
            excerpt = '\n\n'.join(lookup[p]['text'] for p in refs)
            if segment.get('script_excerpt') != excerpt:
                errors.append(sid + ' 原文须完整对应所引段落，不能摘要或漏句')
        options = segment.get('options', [])
        if not isinstance(options, list) or len(options) < 3:
            errors.append(sid + ' 至少需要三种画面表现方案')
            continue
        option_ids, fingerprints = set(), set()
        for option in options:
            oid = option.get('id') if isinstance(option, dict) else None
            if not isinstance(oid, str) or not oid or oid in option_ids:
                errors.append(sid + ' 方案ID缺失或重复')
                continue
            option_ids.add(oid)
            for key in ['method', 'opening', 'action', 'result', 'focus',
                        'feasibility', 'cost', 'risk_note', 'difference']:
                if not isinstance(option.get(key), str) or not option[key].strip():
                    errors.append(sid + '/' + oid + ' 缺少 ' + key)
            if not isinstance(option.get('characters'), bool):
                errors.append(sid + '/' + oid + ' 须声明是否使用人物')
            if reading_required:
                from reading_pacing import estimate
                import math
                rd=option.get('reading_design',{});groups=rd.get('information_groups')if isinstance(rd,dict)else None
                if not isinstance(groups,list):errors.append(sid+'/'+oid+' 缺少独立信息组、动作时长、稳定读图时长与保留设计')
                elif not groups and not str(rd.get('no_new_text_reason','')).strip():errors.append(sid+'/'+oid+' 没有新增正文时须说明如何用图像理解')
                else:
                    for group in groups:
                        if not isinstance(group,dict):errors.append(sid+'/'+oid+' 信息组须为对象');continue
                        for key in ['screen_text','read_task','retention']:
                            if not isinstance(group.get(key),str)or not group[key].strip():errors.append(sid+'/'+oid+' 信息组缺少 '+key)
                        for key in ['motion_seconds','stable_read_seconds']:
                            if type(group.get(key))not in [int,float]or not math.isfinite(group[key])or group[key]<0:errors.append(sid+'/'+oid+' 信息组时长无效 '+key)
                        if type(group.get('stable_read_seconds'))in [int,float]and group['stable_read_seconds']<estimate([group.get('screen_text','')]):errors.append(sid+'/'+oid+' 稳定阅读时长低于该组文字的估算下限')
                if not isinstance(rd,dict)or not isinstance(rd.get('focus_order'),list)or not rd.get('focus_order')or any(not isinstance(v,str)or not v.strip()for v in rd['focus_order']):errors.append(sid+'/'+oid+' 缺少依次推进的观看焦点')
            policy = board.get('presentation_policy', {})
            if segment.get('kind') == 'concept' and policy.get('concept_characters') is False and option.get('characters'):
                errors.append(sid + '/' + oid + ' 概念段按本课约定不使用人物')
            if segment.get('kind') == 'scenario' and policy.get('scenario_characters') is True and not option.get('characters'):
                errors.append(sid + '/' + oid + ' 情境段按本课约定需要人物演绎')
            fingerprints.add(digest({k: option.get(k) for k in ['method', 'opening', 'action', 'result']}))
        if len(fingerprints) < 3:
            errors.append(sid + ' 方案重复；差异还须人工核对，不能只换配色')
        if segment.get('recommended') not in option_ids:
            errors.append(sid + ' 推荐方案不存在')
        selected = segment.get('selected')
        if selected is None:
            pending.append(sid)
        elif selected not in option_ids:
            errors.append(sid + ' 已选方案不存在')
        elif not segment.get('selection_receipt', {}).get('evidence', '').strip():
            errors.append(sid + ' 选择缺少实际依据')
    expected = [p['id'] for p in source]
    if seen != expected:
        missing = [p for p in expected if p not in seen]
        duplicate = sorted({p for p in seen if seen.count(p) > 1})
        errors.append('逐字稿须按顺序完整覆盖且不重复；缺少：' + ','.join(missing) + '；重复：' + ','.join(duplicate))
    if units - covered_units:
        errors.append('分镜未覆盖单元：' + ','.join(sorted(units - covered_units)))
    if assessments - covered_assessments:
        errors.append('分镜未覆盖练习与反馈：' + ','.join(sorted(assessments - covered_assessments)))
    return dict(ok=not errors, errors=list(dict.fromkeys(errors)), pending=pending,
                paragraph_count=len(source), segment_count=len(segments),
                option_count=sum(len(s.get('options', [])) for s in segments if isinstance(s, dict)),
                scope='结构、逐段覆盖与引用；不证明美观、方案实质差异、可执行性或用户认可')


def basis(board):
    value = copy.deepcopy(board)
    for segment in value.get('segments', []):
        segment.pop('selection_receipt', None)
    return digest(value)


def draw(board, seed=None):
    segments = board['segments']
    if len(segments) < 3:
        raise ValueError('三段抽样至少需要三个完整教学片段；短课须明确调整范围，不能重复同一片段凑数')
    if any(not s.get('selected') for s in segments):
        raise ValueError('先确定全部分镜方案再抽样')
    seed = seed or secrets.token_hex(16)
    if not isinstance(seed, str) or not seed:
        raise ValueError('抽样种子须为非空文字')
    rng = random.Random(seed)
    chosen = []

    def choose(pool, reason):
        pool = sorted([s for s in pool if s['id'] not in {i['segment_id'] for i in chosen}], key=lambda s: s['id'])
        if pool:
            s = rng.choice(pool)
            chosen.append(dict(segment_id=s['id'], option_id=s['selected'], kind=s['kind'],
                               risk=s['risk'], reason=reason, eligible_ids=[i['id'] for i in pool]))

    choose([s for s in segments if s['kind'] == 'scenario'], '人物情境类内随机')
    choose([s for s in segments if s['kind'] == 'concept'], '无人物概念类内随机')
    covered = {i['kind'] for i in chosen}
    high = [s for s in segments if s['risk']=='high' and s['id'] not in {i['segment_id'] for i in chosen}]
    choose([s for s in high if s['kind'] not in covered] or high, '优先未覆盖类型的高风险实现内随机')
    while len(chosen) < 3:
        covered = {i['kind'] for i in chosen}
        choose([s for s in segments if s['kind'] not in covered] or segments, '优先未覆盖表现类型，再在剩余片段中随机')
    kinds = {s['kind'] for s in segments}
    covered = {s['kind'] for s in chosen}
    return dict(schema=SAMPLING, storyboard_sha256=basis(board), seed=seed, selections=chosen,
                population_ids=[s['id'] for s in segments], uncovered_kinds=sorted(kinds-covered),
                unsampled_high_risk_ids=[s['id'] for s in segments if s['risk']=='high' and s['id'] not in {c['segment_id'] for c in chosen}],
                scope='三段为表现覆盖样本，不证明整课质量；未抽到的高风险实现仍需在生产中验证')


def check_samples(board, plan):
    try:
        expected = draw(board, plan.get('seed'))
        return [] if expected == plan else ['抽样计划与当前分镜或随机种子不符，请按当前分镜重新抽样']
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return ['抽样计划无效：' + str(error)]


def check_bindings(board, plan, doc, first=None, last=None, full=False):
    from timeline import segments as timeline_segments, duration
    errors = check_samples(board, plan)
    bindings = doc.get('storyboardBindings', [])
    if not isinstance(bindings, list) or any(not isinstance(s, dict) for s in bindings):
        return errors + ['实际时间线的分镜绑定格式无效']
    wanted = ({s['id']: dict(option_id=s['selected']) for s in board.get('segments', [])} if full else {s['segment_id']: s for s in plan.get('selections', [])})
    actual = {s.get('segment_id'): s for s in bindings}
    if len(bindings) != len(wanted) or set(actual) != set(wanted):
        errors.append('整课时间线须覆盖全部已确定分镜' if full else '小样时间线必须对应本次抽中的三个不同片段，不能用自选片段或重复片段替代')
    scenes = {s['id']: s for s in doc.get('scenes', [])}
    content = {s['id']: s for s in board.get('segments', [])}
    end = doc.get('sourceDurationFrames', 0)
    normalized = dict(doc, holds=doc.get('holds', []))
    if not isinstance(end, int) or end <= 0:
        return errors + ['实际时间线缺少有效源帧范围']
    first = 0 if first is None else first
    last = duration(normalized) if last is None else last
    retained = []
    for item in timeline_segments(normalized):
        a, b = max(first, item['startFrame']), min(last, item['endFrame'])
        if item['kind'] == 'source' and a < b:
            retained.append((item['sourceFrame']+a-item['startFrame'], item['sourceFrame']+b-item['startFrame']))

    def covers(ranges, start, stop):
        cursor = start
        for a, b in sorted(ranges):
            if a > cursor: break
            if b > cursor: cursor = b
            if cursor >= stop: return True
        return False

    windows, used_scenes = [], set()
    for sid, binding in actual.items():
        if sid not in wanted:
            continue
        if binding.get('option_id') != wanted[sid]['option_id']:
            errors.append(sid + ' 未使用已确定的画面方案')
        if binding.get('script_excerpt') != content[sid]['script_excerpt']:
            errors.append(sid + ' 未绑定完整逐字稿原文')
        start, stop = binding.get('startFrame'), binding.get('endFrame')
        if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= end:
            errors.append(sid + ' 时间范围无效')
            continue
        if not covers(retained, start, stop):
            errors.append(sid + ' 被时间线裁剪或导出区间裁掉，须导出完整样段')
        windows.append((start, stop))
        refs = binding.get('sceneIds', [])
        if not isinstance(refs, list) or not refs or any(i not in scenes for i in refs):
            errors.append(sid + ' 未连接实际场景')
            continue
        ranges = [(scenes[i].get('sourceStartFrame'), scenes[i].get('sourceEndFrame')) for i in refs]
        if any(type(a) is not int or type(b) is not int or not start <= a < b <= stop for a, b in ranges):
            errors.append(sid + ' 场景与样段源帧范围不一致')
        elif not covers(ranges, start, stop):
            errors.append(sid + ' 场景没有完整覆盖样段，存在未说明的空白')
        if used_scenes.intersection(refs):errors.append(sid + ' 不能复用同一场景冒充不同样段')
        used_scenes.update(refs)
    if any(a[1] > b[0] for a, b in zip(sorted(windows), sorted(windows)[1:])):
        errors.append('分镜片段的时间区间不能重叠')
    return list(dict.fromkeys(errors))


def export_html(board, path):
    """Portable, read-only review with full source text and three real alternatives."""
    esc = lambda s: html.escape(str(s))
    kinds = dict(concept='概念讲解',scenario='人物情境',operation='过程演示',practice='练习与反馈')
    rows, index = [], []
    for s in board['segments']:
        alternatives = []
        for o in s['options']:
            title = o['id']+' · '+o['method']+(' · 推荐' if o['id']==s['recommended'] else '')
            rd=o.get('reading_design',{});reading=''
            if rd:
                reading='<p><b>焦点顺序：</b>'+esc(' → '.join(rd.get('focus_order',[])))+'</p>'+''.join('<p><b>信息组：</b>'+esc(g.get('screen_text',''))+'<br>读懂什么：'+esc(g.get('read_task',''))+'<br>动作 '+esc(g.get('motion_seconds'))+'秒；完整停稳阅读 '+esc(g.get('stable_read_seconds'))+'秒<br>保留：'+esc(g.get('retention',''))+'</p>'for g in rd.get('information_groups',[]))
                if not rd.get('information_groups'):reading+='<p>'+esc(rd.get('no_new_text_reason',''))+'</p>'
            alternatives.append('<section><h3>'+esc(title)+'</h3>'+''.join(
                '<p><b>'+label+'</b>'+esc(o[key])+'</p>' for key,label in [
                ('opening','开始：'),('action','画面变化：'),('result','结果：'),('focus','观看焦点：'),
                ('difference','方案差异：'),('feasibility','实现条件：'),('cost','预计成本：'),('risk_note','需检查：')])+
                reading+'<p class="tag">'+('使用人物' if o['characters'] else '不使用人物')+'</p></section>')
        index.append('<a href="#'+esc(s['id'])+'">'+esc(s['id']+' '+s['teaching_goal'])+'</a>')
        rows.append('<article id="'+esc(s['id'])+'"><h2>'+esc(s['id']+' · '+s['teaching_goal'])+'</h2><p class="meta">'+
            esc(s['unit_id']+' / '+kinds.get(s['kind'],s['kind'])+' / '+('需重点验证' if s['risk']=='high' else '常规风险')+' / '+', '.join(s['source_paragraph_ids']))+
            '</p><blockquote><b>逐字稿原文</b><br>'+esc(s['script_excerpt']).replace('\n','<br>')+'</blockquote><div class="options">'+
            ''.join(alternatives)+'</div><p class="recommend">推荐 '+esc(s['recommended'])+'：'+esc(s['recommendation_reason'])+
            '</p><p>当前选择：<b>'+esc(s.get('selected') or '待确认')+'</b></p></article>')
    visual = ''.join('<span><b>'+label+'：</b>'+esc(board['visual_direction'][key])+'</span>' for key,label in [
        ('palette','配色'),('typography','字体'),('graphics','图形与材质'),('atmosphere','气质')])
    count = len(board['segments']);options = sum(len(s['options']) for s in board['segments'])
    css = 'body{font-family:system-ui,sans-serif;color:#20252b;background:#f5f6f7;margin:0;padding:28px;line-height:1.7}main{max-width:1500px;margin:auto}header,article{background:white;border:1px solid #dfe3e8;border-radius:12px;padding:24px;margin:0 0 24px}h1{font-size:30px;line-height:1.3}.lead{font-size:18px}.options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.options section{background:#fafbfc;border:1px solid #e1e5e9;border-radius:8px;padding:16px}h2{font-size:22px;line-height:1.4}h3{font-size:18px}blockquote{margin:16px 0;padding:16px;border-left:3px solid #53657b;background:#f4f6f8}.meta{color:#637083}.visual{display:grid;grid-template-columns:1fr 1fr;gap:16px}p{overflow-wrap:anywhere}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}nav a{font-size:13px;text-decoration:none;background:#f1f4f7;color:#283d56;padding:4px 8px;border-radius:4px}.tag{font-weight:600;color:#365c58}.recommend{border-top:1px solid #eee;padding-top:16px}article{scroll-margin-top:20px}@media(max-width:900px){.options,.visual{grid-template-columns:1fr}body{padding:12px}}@media print{body{padding:0;background:white}article{break-inside:avoid}nav{display:none}.options section{background:white}}'
    text = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(board.get('title','全课内容演绎与分镜'))+'</title><style>'+css+'</style><main><header><p class="meta">完整逐字稿 → 逐段三种表现 → 确认分镜 → 三段随机有声小样 → 正式制作</p><h1>'+esc(board.get('title','全课内容演绎与分镜'))+'</h1><p class="lead">'+str(count)+' 个完整片段 · '+str(options)+' 种表现方案 · 本页为设计审阅，尚未生成动态样段</p><p>对照每段原文查看开始、变化与结果，逐段选择或明确采用推荐组合。共同美术规范与实际画面仍待确认；文字方案和结构检查不证明最终视觉质量。</p><details><summary>共用美术候选</summary><div class="visual">'+visual+'</div></details><details><summary>全课索引</summary><nav>'+''.join(index)+'</nav></details></header>'+''.join(rows)+'</main></html>'
    Path(path).write_text(text,encoding='utf-8')
