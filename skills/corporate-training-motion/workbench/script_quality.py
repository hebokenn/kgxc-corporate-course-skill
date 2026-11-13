"""Read-only mechanical preflight for narration, never a semantic quality score.

The caller explicitly enables the KGXC opening contract or supplies a selected
greeting. This module does not call a model, rewrite a draft, or approve it.
"""
import hashlib
import re


def _normal(text):
    return re.sub(r'[\W_]+', '', text, flags=re.UNICODE).casefold()


def _spoken_lines(text):
    """Ignore Markdown headings, comments and fenced production notes."""
    fenced = False
    comment = False
    for number, line in enumerate(text.splitlines(), 1):
        if comment:
            if '-->' not in line:
                continue
            line = line.split('-->', 1)[1]
            comment = False
        while '<!--' in line:
            before, after = line.split('<!--', 1)
            if '-->' in after:
                line = before + after.split('-->', 1)[1]
            else:
                line = before
                comment = True
                break
        value = line.strip()
        if re.match(r'^(```|~~~)', value):
            fenced = not fenced
            continue
        if fenced or not value or re.match(r'^#{1,6}\s', value) or value.startswith('<!--'):
            continue
        if re.match(r'^(?:来源|制作备注|导演备注|Source|Production notes)\s*[:：]', value, re.I):
            continue
        yield number, re.sub(r'^[-*>]\s*', '', value)


def inspect_script(text, greeting=None, require_greeting=False):
    """Return located findings; clear mechanics do not certify natural speech.

    Greeting matching tolerates punctuation/spacing. It must occur in the first
    220 spoken characters, so a heading or an end-of-course mention cannot
    satisfy the opening requirement. Repeated teaching may be purposeful;
    repetition and stock wording are advisories for the producer to assess.
    """
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    if greeting is not None and not isinstance(greeting, str):
        raise TypeError('greeting must be a string or None')
    lines = list(_spoken_lines(text))
    body = '\n'.join(value for _, value in lines)
    blocking, advisories = [], []
    checks = []

    if not body.strip():
        blocking.append(dict(id='empty-narration', line=1, quote='', reason='没有可检查的口播正文'))
    checks.append(dict(id='narration-present', status='clear' if body.strip() else 'blocked'))

    if require_greeting:
        opening = _normal(body)[:220]
        configured = bool(greeting and _normal(greeting))
        found = _normal(greeting) in opening if configured else bool(re.search(r'(?:欢迎|大家好).{0,30}酷果星创|酷果星创.{0,30}(?:欢迎|大家好)', opening))
        if not found:
            blocking.append(dict(id='opening-greeting-missing', line=lines[0][0] if lines else 1,
                                 quote=body[:120], reason='开场口播缺少当前选定品牌问候语：'+greeting if configured else '开场口播缺少包含“酷果星创”的欢迎问候'))
        checks.append(dict(id='opening-greeting', status='blocked' if any(x['id']=='opening-greeting-missing' for x in blocking) else 'clear'))
    else:
        checks.append(dict(id='opening-greeting', status='not_required'))

    placeholders = re.compile(r'\[(?:待补充|待填写|补充案例|插入案例|TODO)(?:[^\]]{0,60})\]|【(?:待补充|待填写|补充案例|插入案例)(?:[^】]{0,60})】|\{\{[^}\n]{1,80}\}\}', re.I)
    seen = {}
    stock = re.compile(r'赋能|形成闭环|打造闭环|持续提升|全面提升|至关重要|众所周知|相信大家|让我们共同|相信通过')
    for number, line in lines:
        for match in placeholders.finditer(line):
            blocking.append(dict(id='unfilled-placeholder', line=number, quote=match.group(), reason='口播仍含制作占位，先补成具体内容或删除'))
        normalized = _normal(line)
        if len(normalized) >= 35:
            if normalized in seen:
                advisories.append(dict(id='repeated-passage', line=number, first_line=seen[normalized], quote=line,
                                       reason='与前文实质相同；确认是有目的的练习/回顾，否则合并，保留新增判断或动作'))
            else:
                seen[normalized] = number
        matches = list(stock.finditer(line))
        if matches:
            advisories.append(dict(id='stock-wording', line=number, quote=line,
                                   terms=list(dict.fromkeys(x.group() for x in matches)),
                                   reason='检查本句是否给出具体对象、条件、动作或判断依据；术语本身不构成错误'))
    checks.append(dict(id='unfilled-placeholders', status='blocked' if any(x['id']=='unfilled-placeholder' for x in blocking) else 'clear'))
    return dict(schema='script-quality-preflight/1', status='blocked' if blocking else 'attention' if advisories else 'mechanical_checks_clear',
                script_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(), blocking=blocking, advisories=advisories, checks=checks,
                scope='当前逐字稿的机械预检；只读，不生成模型调用或审阅轮次',
                limitations=['不证明口语自然、信息量充分、事实正确或教学有效；制作端须通读当前完整正文自检',
                             '重复和套话仅为提示；有教学目的的回顾、术语及人物口头禅可保留并说明理由'])
