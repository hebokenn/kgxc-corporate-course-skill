"""Producer-side source accounting, with separate current-byte human receipts.

Counts registered independent business points, not words. Exact quotes establish
locations; their semantic completeness and the point inventory need human review.
Nothing in this module calls a model or grants a blind-review/stage approval.
"""
from contextlib import contextmanager
from collections import OrderedDict
import copy
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
from types import SimpleNamespace
import uuid
import xml.etree.ElementTree as ET
import zipfile


_SOURCE_TEXT_CACHE = OrderedDict()
_SOURCE_TEXT_CACHE_LOCK = threading.RLock()
_SOURCE_TEXT_CACHE_LIMIT = 2_000_000  # Unicode characters, across all cached inputs.
_SOURCE_TEXT_CACHE_ENTRIES = 16


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')


def _read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else copy.deepcopy(default)


def _atomic(path, value):
    temporary = path.with_name(path.name+'.pending-'+uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def _source_text(path):
    suffix = path.suffix.lower()
    if suffix in ['.txt', '.md', '.csv', '.json', '.tsv']:
        return path.read_text(encoding='utf-8')
    if suffix in ['.pptx', '.docx']:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', name)] if suffix == '.pptx' else ['word/document.xml']
            names.sort(key=lambda name: int(re.search(r'(\d+)\.xml', name)[1]) if re.search(r'(\d+)\.xml', name) else 0)
            return '\n\n'.join(name+': '+' '.join(node.text or '' for node in ET.fromstring(archive.read(name)).iter() if node.tag.endswith('}t')) for name in names)
    if suffix == '.pdf':
        return subprocess.check_output(['pdftotext', '-layout', str(path), '-'], text=True, timeout=30)
    raise ValueError('当前机械检查器不能提取此原件的文字；须注明人工视觉核验范围')


def _cached_source_text(path, expected_sha256):
    """Bounded process memory only; changed source bytes always change the key."""
    key = (str(path.resolve()), expected_sha256)
    with _SOURCE_TEXT_CACHE_LOCK:
        if key in _SOURCE_TEXT_CACHE:
            _SOURCE_TEXT_CACHE.move_to_end(key)
            return _SOURCE_TEXT_CACHE[key]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise FileExistsError('原件在提取前发生变化')
        text = _source_text(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise FileExistsError('原件在提取期间发生变化')
        if len(text) <= _SOURCE_TEXT_CACHE_LIMIT:
            _SOURCE_TEXT_CACHE[key] = text
            while (len(_SOURCE_TEXT_CACHE) > _SOURCE_TEXT_CACHE_ENTRIES or
                   sum(len(value) for value in _SOURCE_TEXT_CACHE.values()) > _SOURCE_TEXT_CACHE_LIMIT):
                _SOURCE_TEXT_CACHE.popitem(last=False)
        return text


class SourceCoverage:
    SCHEMA = 'source-coverage/1'
    CLICK_ACTORS = {'dsh-user-click', 'codex-user-click'}

    def __init__(self, course):
        self.course = course
        self.project = Path(course.project)
        self.path = self.project/'source-coverage.json'

    @contextmanager
    def locked(self):
        self.project.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _script(self):
        if (self.project/'workbench.json').is_file() and (self.project/'course-state.json').is_file():
            document = _read(self.project/'workbench.json', {})
            if 'title' not in document:
                # CLI-created projects may have an empty drawing document. A
                # missing UI title must not discard a real current draft.
                official = self.course.script().get('text', '')
                draft = _read(self.project/'script-editor.json')
                if draft is None:
                    return official, False
                if not isinstance(draft, dict) or not isinstance(draft.get('text', official), str):
                    raise ValueError('当前逐字稿草稿格式无效，保留现场后核对')
                text = draft.get('text', official)
                base_text = draft.get('base_text', official)
                base_sha = draft.get('base_sha256', _text_hash(official))
                unknown = bool(draft.get('base_unknown') or 'base_text' not in draft or 'base_sha256' not in draft) and text != official
                if not unknown and text in [base_text, official] and base_sha != _text_hash(official):
                    return official, False
                render = draft.get('render_request', {})
                if not unknown and isinstance(render, dict) and render.get('sha256') == _text_hash(official):
                    return text, False
                return text, unknown or base_sha != _text_hash(official)
            from script_editor import ScriptEditor
            editor = ScriptEditor(SimpleNamespace(root=self.course.root, project=self.project, file=self.project/'workbench.json')).read()
            return editor['text'], bool(editor.get('base_changed'))
        return self.course.script().get('text', ''), False

    def _sources(self):
        plan = _read(self.course.plan_file, {})
        inventory = []
        for source in plan.get('sources', []):
            if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id'].strip():
                raise ValueError('原件登记须有稳定source id')
            item = dict(source_id=source['id'], kind=source.get('kind'), location=source.get('location'), sha256=None, available=False)
            if source.get('kind') == 'file':
                try:
                    path = self.course.relative(source.get('location'))
                    if path.is_file():
                        item.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), available=True)
                except (ValueError, OSError, TypeError):
                    pass
            else:
                text = source.get('text') or source.get('content')
                if isinstance(text, str) and text.strip():
                    item.update(sha256=_text_hash(text), available=True)
            inventory.append(item)
        if len({item['source_id'] for item in inventory}) != len(inventory):
            raise ValueError('原件source id重复')
        return inventory

    def _source_texts(self, sources):
        plan = _read(self.course.plan_file, {})
        declared = {source['id']: source for source in plan.get('sources', [])}
        result = {}
        for item in sources:
            if not item['available']:
                result[item['source_id']] = None
                continue
            source = declared[item['source_id']]
            try:
                result[item['source_id']] = _cached_source_text(self.course.relative(source['location']), item['sha256']) if source.get('kind') == 'file' else source.get('text') or source.get('content')
            except (ValueError, OSError, UnicodeError, subprocess.SubprocessError, zipfile.BadZipFile, ET.ParseError, KeyError):
                result[item['source_id']] = None
        return result

    def _basis(self):
        text, conflict = self._script()
        sources = self._sources()
        return dict(script_sha256=_text_hash(text), sources_sha256=_hash(sources), sources=sources, script_conflict=conflict), text

    def source_excerpt(self, source_id, offset=0, limit=24000):
        """Read one bounded current-source excerpt without exposing write tools.

        Character offsets are Python Unicode code points. Exhausting extracted
        text does not claim images, charts or scanned text were inspected.
        """
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 60000:
            raise ValueError('原件读取offset须为非负整数，limit须为1至60000整数')
        sources = self._sources()
        item = next((row for row in sources if row['source_id'] == source_id), None)
        if item is None:
            raise ValueError('只能读取当前课程已登记source_id的原件')
        text = self._source_texts([item]).get(source_id)
        limitations = ['仅提取可读取正文；未执行OCR、下载或模型调用，文字读取不证明已核对图片、图表和业务语义']
        if text is None or not text.strip():
            return dict(source_id=source_id, source_sha256=item['sha256'], status='unknown', text='', offset=offset,
                        next_offset=None, total_chars=None, truncated=None, limitations=limitations+['原件缺失、格式不支持或提取为空；不得登记为全文已读'])
        current = next((row for row in self._sources() if row['source_id'] == source_id), None)
        if current != item:
            raise FileExistsError('提取期间原件发生变化，请按当前source hash重新读取')
        if offset > len(text):
            raise ValueError('offset超过当前提取正文长度')
        end = min(len(text), offset+limit)
        return dict(source_id=source_id, source_sha256=item['sha256'], status='available', text=text[offset:end], offset=offset,
                    next_offset=end if end < len(text) else None, total_chars=len(text), truncated=end < len(text),
                    read_scope=f'提取正文字符[{offset},{end})，共{len(text)}字符', limitations=limitations)

    @staticmethod
    def _string(value, label):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(label+'须为非空文字')

    def _validate(self, report, basis, text):
        if not isinstance(report, dict) or report.get('schema') != self.SCHEMA:
            raise ValueError('原件覆盖报告schema须为source-coverage/1')
        if set(report) - {'schema', 'source_inventory', 'points', 'additions', 'notes'}:
            raise ValueError('覆盖报告含未知字段；不能嵌入确认或统计结论')
        sources = {source['source_id']: source for source in basis['sources']}
        inventory = report.get('source_inventory')
        points, additions = report.get('points'), report.get('additions')
        if not isinstance(inventory, list) or not isinstance(points, list) or not isinstance(additions, list):
            raise ValueError('报告须含source_inventory、points、additions数组')
        seen = set()
        for row in inventory:
            if not isinstance(row, dict) or set(row) - {'source_id', 'sha256', 'read_scope', 'fully_read', 'unreadable'}:
                raise ValueError('原件读取记录字段无效')
            sid = row.get('source_id')
            if sid not in sources or sid in seen:
                raise ValueError('原件读取记录须逐项且不可重复')
            seen.add(sid)
            if row.get('sha256') != sources[sid]['sha256']:
                raise FileExistsError('原件已更新，覆盖报告hash不匹配：'+sid)
            self._string(row.get('read_scope'), '原件实际读取范围')
            if type(row.get('fully_read')) is not bool or not isinstance(row.get('unreadable'), list) or any(not isinstance(value, str) or not value.strip() for value in row['unreadable']):
                raise ValueError('原件须记录fully_read布尔值及unreadable文字数组')
        if seen != set(sources):
            raise ValueError('读取范围必须覆盖全部已登记来源，未读来源也须明确记录')
        texts = self._source_texts(basis['sources'])
        ids, source_evidence = set(), set()
        for point in points:
            if not isinstance(point, dict) or set(point) - {'id', 'source_id', 'locator', 'source_quote', 'critical', 'disposition', 'script_quotes', 'reason'}:
                raise ValueError('业务要点字段无效')
            for key in ['id', 'source_id', 'locator', 'source_quote', 'reason']:
                self._string(point.get(key), '要点'+key)
            if point['id'] in ids or point['source_id'] not in sources:
                raise ValueError('业务要点须有唯一稳定id及已登记来源')
            ids.add(point['id'])
            evidence_key = (point['source_id'], point['locator'], point['source_quote'])
            if evidence_key in source_evidence:
                raise ValueError('相同来源、定位和原文引文重复登记，不能仅换id增加业务要点分母')
            source_evidence.add(evidence_key)
            if type(point.get('critical')) is not bool or point.get('disposition') not in ['retained', 'merged', 'omitted']:
                raise ValueError('要点须标记critical及retained/merged/omitted')
            original = texts[point['source_id']]
            if original is not None and point['source_quote'] not in original:
                raise ValueError('原件引文未匹配当前实际来源：'+point['id'])
            quotes = point.get('script_quotes')
            if not isinstance(quotes, list) or any(not isinstance(quote, str) or not quote.strip() or quote not in text for quote in quotes):
                raise ValueError('要点须引用当前逐字稿实际文字：'+point['id'])
            if point['disposition'] in ['retained', 'merged'] and not quotes:
                raise ValueError('保留或合并要点必须有当前逐字稿定位：'+point['id'])
            if point['disposition'] == 'omitted' and quotes:
                raise ValueError('舍弃要点不能同时登记已覆盖引文：'+point['id'])
        added_ids = set()
        for addition in additions:
            if not isinstance(addition, dict) or set(addition) - {'id', 'script_quote', 'location', 'reason', 'basis_kind', 'basis'}:
                raise ValueError('新增内容字段无效')
            for key in ['id', 'script_quote', 'location', 'reason', 'basis']:
                self._string(addition.get(key), '新增内容'+key)
            if addition['id'] in added_ids:
                raise ValueError('新增内容id重复')
            added_ids.add(addition['id'])
            if addition.get('basis_kind') not in ['example', 'explanation', 'external']:
                raise ValueError('新增内容须区分example/explanation/external')
            if addition['script_quote'] not in text:
                raise ValueError('新增内容未匹配当前逐字稿：'+addition['id'])
        if sources and not points:
            raise ValueError('存在原件时须登记独立业务要点；不能用空清单宣称覆盖')
        return texts

    def _statistics(self, report, basis, text):
        points = report.get('points', []) if report else []
        inventory = report.get('source_inventory', []) if report else []
        covered = [point for point in points if point.get('disposition') in ['retained', 'merged'] and point.get('script_quotes') and all(quote in text for quote in point['script_quotes'])]
        critical = [point for point in points if point.get('critical')]
        covered_critical = [point for point in covered if point.get('critical')]
        texts = self._source_texts(basis['sources']) if report else {}
        unverified = [point['id'] for point in points if texts.get(point['source_id']) is None or point['source_quote'] not in texts[point['source_id']]]
        sources_with_points = {point['source_id'] for point in points}
        missing = [source['source_id'] for source in basis['sources'] if source['source_id'] not in sources_with_points]
        complete = bool(basis['sources']) and len(inventory) == len(basis['sources']) and all(row.get('fully_read') and not row.get('unreadable') for row in inventory) and all(source['available'] for source in basis['sources']) and not unverified and not missing
        rate = round(100*len(covered)/len(points), 2) if points else None
        return dict(total=len(points), covered=len(covered), omitted=sum(point.get('disposition') == 'omitted' for point in points),
                    retained=sum(point.get('disposition') == 'retained' for point in points), merged=sum(point.get('disposition') == 'merged' for point in points),
                    rate=rate if complete else None, registered_rate=rate, coverage_complete=complete,
                    critical=dict(total=len(critical), covered=len(covered_critical), omitted=sum(point.get('critical') and point.get('disposition') == 'omitted' for point in points), rate=round(100*len(covered_critical)/len(critical), 2) if complete and critical else None),
                    additions=len(report.get('additions', [])) if report else 0, source_quote_unverified=unverified, sources_without_points=missing,
                    denominator='全部已登记独立业务要点；舍弃项仍在分母，合并只按原要点分别计数，不按字数或关键词',
                    scope='仅统计已登记要点；拆点完整性、语义覆盖充分性、遗漏和新增项是否完整由人工对照确认，非算法证明')

    def view(self):
        basis, text = self._basis()
        state = _read(self.path, {})
        report = state.get('report')
        digest = _hash(report) if report else None
        current = bool(report and state.get('binding', {}).get('script_sha256') == basis['script_sha256'] and state.get('binding', {}).get('sources_sha256') == basis['sources_sha256'] and state.get('report_sha256') == digest and not basis['script_conflict'])
        confirmation = state.get('confirmation') or {}
        confirmed = bool(current and confirmation.get('report_sha256') == digest and confirmation.get('script_sha256') == basis['script_sha256'] and confirmation.get('sources_sha256') == basis['sources_sha256'] and confirmation.get('actor') in self.CLICK_ACTORS and confirmation.get('evidence') and confirmation.get('source'))
        required = bool(basis['sources'])
        reasons = []
        if basis['script_conflict']:
            reasons.append('当前草稿与正式稿基线冲突，须先合并再确认覆盖报告')
        if required and not report:
            reasons.append('尚未提交原件信息覆盖、舍弃与新增内容报告')
        elif required and not current:
            reasons.append('原件、逐字稿或覆盖报告已变更，须核对当前报告并重新人工确认')
        elif required and not confirmed:
            reasons.append('当前覆盖报告待人工明确点击确认')
        statistics = self._statistics(report, basis, text)
        if not current:
            statistics['rate'] = None
            statistics['critical']['rate'] = None
            statistics['coverage_complete'] = False
        rate_label = str(statistics['rate'])+'%' if statistics['rate'] is not None else '尚不能报告完整覆盖率'
        summary = ('无登记原件；不计算信息覆盖率' if not required else
                   f"按已登记独立业务要点：{statistics['covered']}/{statistics['total']}，{rate_label}；舍弃{statistics['omitted']}项，新增{statistics['additions']}项。语义拆点与取舍待人工对照。")
        return dict(schema=self.SCHEMA, required=required, current=current, confirmed=confirmed, can_confirm=bool(required and current), summary=summary,
                    status='not_required' if not required else 'confirmed' if confirmed else 'awaiting_confirmation' if current else 'stale' if report else 'missing',
                    report_sha256=digest, script_sha256=basis['script_sha256'], sources_sha256=basis['sources_sha256'], sources=copy.deepcopy(basis['sources']),
                    reasons=reasons, report=copy.deepcopy(report), statistics=statistics,
                    confirmation=copy.deepcopy(state.get('confirmation')), history_count=len(state.get('history', [])),
                    isolation='制作端原件对照，不附给独立学员盲审；确认不等于盲审通过、阶段批准或正式交付')

    def save(self, report, expected_script_sha256, expected_report_sha256=None):
        with self.locked():
            basis, text = self._basis()
            if expected_script_sha256 != basis['script_sha256']:
                raise FileExistsError('逐字稿已更新，不能保存旧稿的原件覆盖报告')
            if basis['script_conflict']:
                raise FileExistsError('正式稿与当前草稿存在基线冲突，不能绑定覆盖报告')
            previous = _read(self.path, {})
            if expected_report_sha256 is not None and previous.get('report_sha256') != expected_report_sha256:
                raise FileExistsError('覆盖报告已在其他窗口更新')
            self._validate(report, basis, text)
            if self._basis()[0] != basis:
                raise FileExistsError('读取核对期间原件或逐字稿发生变化，请按当前版本重试')
            history = previous.get('history', [])
            if previous and (previous.get('report_sha256') != _hash(report) or previous.get('binding') != basis):
                history = history+[dict(saved_at=previous.get('saved_at'), report_sha256=previous.get('report_sha256'), report=previous.get('report'), binding=previous.get('binding'), confirmation=previous.get('confirmation'))]
            same = previous.get('report_sha256') == _hash(report) and previous.get('binding') == basis
            _atomic(self.path, dict(schema=self.SCHEMA, saved_at=_now(), report=copy.deepcopy(report), report_sha256=_hash(report), binding=basis,
                                    confirmation=previous.get('confirmation') if same else None, history=history))
        return self.view()

    def confirm(self, report_sha256, evidence, actor='dsh-user-click', source=None):
        if actor not in self.CLICK_ACTORS:
            raise ValueError('原件覆盖确认只能来自人工明确点击，不能由制作代理代确认')
        self._string(evidence, '人工确认原话')
        self._string(source, '人工点击来源')
        with self.locked():
            view = self.view()
            if not view['required'] or not view['current'] or view['report_sha256'] != report_sha256:
                raise FileExistsError('覆盖报告不是当前原件和逐字稿版本，不能确认')
            basis, text = self._basis()
            self._validate(view['report'], basis, text)
            if self._basis()[0] != basis:
                raise FileExistsError('人工确认期间原件或逐字稿发生变化，请按当前版本重试')
            state = _read(self.path, {})
            state['confirmation'] = dict(at=_now(), actor=actor, source=source, evidence=evidence, report_sha256=report_sha256,
                                         script_sha256=view['script_sha256'], sources_sha256=view['sources_sha256'])
            _atomic(self.path, state)
        return self.view()

    def require_confirmed(self):
        result = self.view()
        if result['required'] and not result['confirmed']:
            raise ValueError('原件覆盖报告未获当前版本的人工确认：'+'；'.join(result['reasons']))
        return result
