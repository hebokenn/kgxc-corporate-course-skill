"""Durable course design, decisions and recovery. Standard library only."""
from pathlib import Path
from contextlib import contextmanager
import argparse
import copy
import datetime
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
import webbrowser
from runtime import ensure_dir, tools

VERSION = '5.3.0'
GATES = [('source', '素材诊断'), ('outline', '课程结构'), ('content', '完整课件稿'),
         ('visual', '视觉与声音方案'), ('pilot', '代表样段'), ('final', '整课候选')]


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')


def read(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).is_file() else copy.deepcopy(default)


def atomic(path, data):
    path = Path(path); ensure_dir(path.parent)
    tmp = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def hashed(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    from performance_cache import sha as cached_sha
    return cached_sha(path)


class LegacyCourse:
    def __init__(self, root):
        root = Path(root).expanduser().resolve()
        self.project = root if any((root/name).is_file() for name in ['workbench.json','course-state.json','project.json']) else root / 'project'
        self.root = self.project.parent
        self.state_file = self.project / 'course-state.json'
        self.plan_file = self.project / 'design-plan.json'

    def available_gates(self):
        return GATES

    def design_schema(self):
        return 1

    def relative(self, value, base=None):
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError('需要课程内的相对路径')
        p = ((base or self.project) / value).resolve()
        if not p.is_relative_to(self.root): raise ValueError('文件超出当前课程')
        return p

    @contextmanager
    def locked(self):
        ensure_dir(self.project / 'work')
        with (self.project / 'work/workflow.lock').open('a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(f, fcntl.LOCK_UN)

    def init(self, title='新课程'):
        with self.locked():
            if not self.plan_file.exists():
                atomic(self.plan_file, dict(schema_version=1, title=title, stage='outline', audience='',
                    performance_task='', sources=[], objectives=[], units=[], assessments=[], decisions=[], issues=[],
                    handoff=dict(ready_for_courseware=False, ready_for_production=False)))
            if not self.state_file.exists():
                atomic(self.state_file, dict(schema='course-workflow/1', version=VERSION, course_id=uuid.uuid4().hex,
                    revision=0, created_at=now(), updated_at=now(), gates={}, artifacts={}, journal=[],
                    narration_status='not_started'))
        return self.status()

    def _commit(self, state, event, details=None):
        state['revision'] += 1; state['updated_at'] = now()
        state.setdefault('journal', []).append(dict(at=now(), event=event, details=details or {}))
        atomic(self.state_file, state)

    def _snapshot(self, state):
        folder = self.project / 'workflow-history'; ensure_dir(folder)
        atomic(folder / (str(state['revision']).zfill(6) + '.json'),
               dict(state=state, design_plan=read(self.plan_file)))

    @staticmethod
    def _subject(decision):
        return {k: v for k, v in decision.items() if k not in
                ['selected', 'status', 'evidence', 'confirmed_at', 'confirmed_subject_sha256', 'actor']}

    def _source_files(self, plan):
        result = {}
        for item in plan.get('sources', []):
            if item.get('kind') == 'file':
                value = item.get('location', '')
                try:
                    p = self.relative(value)
                    result[item['id']] = dict(path=value, sha256=sha(p) if p.is_file() else None)
                except (ValueError, OSError): result[item.get('id', '?')] = dict(path=value, sha256=None)
        return result

    def _gate_hash(self, key, plan, state):
        decision_values = [{k: d.get(k) for k in ['id', 'question', 'finding', 'options', 'selected', 'status']}
                           for d in plan.get('decisions', []) if d.get('gate', 'outline') == key]
        if key == 'source':
            value = dict(sources=plan.get('sources'), files=self._source_files(plan), ledger=plan.get('source_items', []))
        elif key == 'outline':
            value = {k: plan.get(k) for k in ['audience', 'performance_task', 'objectives', 'units']}
        elif key == 'content':
            f = plan.get('courseware_file')
            p = self.relative(f) if f else None
            value = dict(assessments=plan.get('assessments'), file=f, sha256=sha(p) if p and p.is_file() else None)
        else:
            value = []
            for name in state.get('artifacts', {}).get(key, []):
                p = self.relative(name)
                value.append(dict(path=name, sha256=sha(p) if p.is_file() else None))
            if key=='visual':
                from performance_cache import native_fingerprint
                document=read(self.project/'workbench.json',{})
                value.append(dict(native=native_fingerprint(self.project),
                    drawing={k:document.get(k) for k in ['sceneGraph','fields','assets','media','scenes']}))
            if key == 'final':
                document = self.project / 'workbench.json'
                value.append(dict(workbench=sha(document) if document.is_file() else None))
        return hashed(dict(data=value, decisions=decision_values))

    def _pending(self, plan):
        result = []
        for d in plan.get('decisions', []):
            stale = d.get('confirmed_subject_sha256') and d['confirmed_subject_sha256'] != hashed(self._subject(d))
            if d.get('status') == 'open' or stale:
                result.append(dict(id=d['id'], question=d['question'], gate=d.get('gate', 'outline'),
                    blocking_for=d.get('blocking_for', []), stale=bool(stale)))
        for issue in plan.get('issues', []):
            if issue.get('state') == 'open':
                result.append(dict(id=issue['id'], question=issue.get('detail', ''), kind='issue',
                    blocking_for=[] if issue.get('blocks') == 'none' else [issue.get('blocks', 'production')]))
        return result

    def _readiness(self, key, plan, state, pending):
        errors = []
        if key == 'source':
            if not plan.get('sources'): errors.append('先登记原始素材')
            if any(v['sha256'] is None for v in self._source_files(plan).values()): errors.append('来源文件缺失或路径无效')
        elif key in ['outline', 'content']:
            try:
                from check_design import check
                candidate=copy.deepcopy(plan)
                candidate['handoff']=dict(ready_for_courseware=False,ready_for_production=False)
                report = check(candidate, self.project); errors.extend(report['errors'])
            except ImportError: errors.append('教学设计校验器缺失，请重装完整技能包')
            block = 'courseware' if key == 'outline' else 'production'
            errors.extend('待解决：' + p['id'] for p in pending if block in p.get('blocking_for', []))
            if key == 'content':
                f = plan.get('courseware_file')
                if plan.get('stage') != 'courseware' or not f or not self.relative(f).is_file():
                    errors.append('需要实际完整课件稿')
        else:
            paths = state.get('artifacts', {}).get(key, [])
            if not paths or any(not self.relative(p).is_file() for p in paths): errors.append('先登记本阶段实际审阅产物')
            if key in ['pilot', 'final'] and not any(Path(p).suffix.lower() == '.mp4' for p in paths):
                errors.append('需要有声视频候选')
        errors.extend('待选择：' + p['id'] for p in pending if p.get('gate') == key)
        return list(dict.fromkeys(errors))

    def status(self):
        plan = read(self.plan_file, {}); state = read(self.state_file, {})
        pending = self._pending(plan); gates = []; upstream = True
        for key, label in GATES:
            receipt = state.get('gates', {}).get(key, {})
            current = self._gate_hash(key, plan, state)
            errors = self._readiness(key, plan, state, pending)
            valid = bool(receipt and receipt.get('sha256') == current and upstream and not errors)
            gates.append(dict(id=key, label=label, status='confirmed' if valid else 'stale' if receipt else 'open',
                              ready=upstream and not errors, reasons=errors, receipt=receipt))
            upstream = valid
        next_gate = next((g for g in gates if g['status'] != 'confirmed'), None)
        confirmed={g['id'] for g in gates if g['status']=='confirmed'}
        plan['handoff']=dict(ready_for_courseware='outline' in confirmed,
                             ready_for_production='content' in confirmed and not any('production' in p.get('blocking_for',[]) for p in pending))
        jobs = []
        for p in sorted((self.project / 'work/workbench/exports').glob('*/result.json')):
            job = read(p, {}); jobs.append({k: job.get(k) for k in ['id', 'status', 'video', 'srt', 'package', 'revision']})
        return dict(version=VERSION, state_key=hashed(dict(plan=plan,gates=gates)), course_id=state.get('course_id'), title=plan.get('title', ''),
            revision=state.get('revision', 0), stage=next_gate['id'] if next_gate else 'complete',
            next_action=('审阅并确认' + next_gate['label']) if next_gate else '当前候选已确认，可交付',
            gates=gates, pending=pending, plan=plan, artifacts=state.get('artifacts', {}), jobs=jobs,
            narration_status=state.get('narration_status', 'not_started'),
            source_files=self._source_files(plan), updated_at=state.get('updated_at'))

    def _revision(self, expected, state):
        if expected != state['revision']: raise FileExistsError('工程已被其他窗口修改，请刷新后重试')

    def save_plan(self, plan, expected):
        with self.locked():
            state = read(self.state_file); self._revision(expected, state)
            old = read(self.plan_file)
            if plan.get('schema_version') != self.design_schema(): raise ValueError('教学设计格式无效，请沿用本工程的schema_version')
            for name in ['sources', 'objectives', 'units', 'assessments', 'decisions', 'issues']:
                values = plan.get(name)
                if not isinstance(values, list): raise ValueError(name + '须为数组')
                ids = [d.get('id') for d in values if isinstance(d, dict)]
                if len(ids) != len(values) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
                    raise ValueError(name + '的ID缺失或重复')
            previous = {d['id']: d for d in old.get('decisions', [])}
            for d in plan['decisions']:
                if d.get('gate', 'outline') not in dict(self.available_gates()): raise ValueError('选择节点无效')
                opts = d.get('options', [])
                if not d.get('question') or len(opts) < 2 or len({o.get('id') for o in opts}) != len(opts):
                    raise ValueError('每个选择需有问题和至少两个不同选项')
                prev = previous.get(d['id'])
                if prev and hashed(self._subject(prev)) == hashed(self._subject(d)):
                    for k in ['selected', 'status', 'evidence', 'confirmed_at', 'confirmed_subject_sha256', 'actor']:
                        if k in prev: d[k] = copy.deepcopy(prev[k])
                        else: d.pop(k, None)
                else:
                    d.update(selected=None, status='open', evidence='')
                    for k in ['confirmed_at', 'confirmed_subject_sha256', 'actor']: d.pop(k, None)
            for item in plan['sources']:
                if item.get('kind') == 'file': self.relative(item.get('location', ''))
            if plan.get('courseware_file'): self.relative(plan['courseware_file'])
            if plan.get('script_file'): self.relative(plan['script_file'])
            self._snapshot(state); atomic(self.plan_file, plan); self._commit(state, 'design_saved')
        return self.status()

    def decide(self, identifier, selected, expected, evidence, actor='workbench', delegated=False):
        if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('请保留提交内容或授权原话')
        with self.locked():
            state = read(self.state_file); self._revision(expected, state); plan = read(self.plan_file)
            d = next((d for d in plan['decisions'] if d['id'] == identifier), None)
            if not d or selected not in [o['id'] for o in d['options']]: raise ValueError('选择或选项不存在')
            self._snapshot(state)
            d.update(selected=selected, status='delegated' if delegated else 'confirmed', evidence=evidence.strip(),
                     actor=actor, confirmed_at=now(), confirmed_subject_sha256=hashed(self._subject(d)))
            atomic(self.plan_file, plan)
            self._commit(state, 'decision_saved', dict(id=identifier, selected=selected, evidence=evidence, actor=actor))
        return self.status()

    def confirm(self, key, expected, evidence, actor='workbench'):
        if not evidence or not str(evidence).strip(): raise ValueError('需要本次审阅的确认说明')
        with self.locked():
            state = read(self.state_file); self._revision(expected, state)
            status = self.status(); gate = next((g for g in status['gates'] if g['id'] == key), None)
            if not gate or not gate['ready']: raise ValueError('本阶段尚不能确认：' + '；'.join(gate['reasons'] if gate else ['未知阶段']))
            self._snapshot(state)
            if key == 'pilot' and getattr(self, 'modern', lambda: False)():
                from visual_identity import capture
                state['visual_palette'] = capture(read(self.project/'workbench.json', {}), self._artifact_hashes('pilot', state), self.project)
            state['gates'][key] = dict(at=now(), evidence=str(evidence), actor=actor,
                                      sha256=self._gate_hash(key, read(self.plan_file), state))
            self._commit(state, 'stage_confirmed', dict(gate=key, evidence=evidence, actor=actor))
        return self.status()

    def register(self, key, paths, expected):
        if key not in dict(GATES): raise ValueError('未知阶段')
        if not paths or any(not self.relative(p).is_file() for p in paths): raise ValueError('审阅产物不存在')
        if key in ['pilot','final']:
            from motion_quality import require as require_motion
            require_motion(read(self.project/'workbench.json'),self.project)
            videos=[self.relative(p) for p in paths if Path(p).suffix.lower()=='.mp4']
            if not videos:raise ValueError('需要真实有声MP4候选')
            for video in videos:
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
                kinds={s.get('codec_type') for s in probe.get('streams',[])}
                if not {'video','audio'}.issubset(kinds) or float(probe['format']['duration'])<=0:raise ValueError('候选需要真实画面与声音')
        with self.locked():
            state = read(self.state_file); self._revision(expected, state); self._snapshot(state)
            import shutil
            stable=[]
            for name in paths:
                p=self.relative(name)
                if p.is_relative_to(self.root/'delivery'):
                    dest=self.project/'qa/reviews'/key/(sha(p)[:12]+'-'+p.name);ensure_dir(dest.parent)
                    if not dest.exists():shutil.copy2(p,dest)
                    sidecar=p.with_suffix('.json')
                    if key=='pilot' and p.suffix.lower()=='.mp4' and sidecar.is_file() and read(sidecar).get('video_sha256')==sha(p):
                        shutil.copy2(sidecar,dest.with_suffix('.json'))
                    name=str(dest.relative_to(self.project))
                stable.append(name)
            state['artifacts'][key] = stable; self._commit(state, 'artifacts_registered', dict(gate=key, paths=stable))
        return self.status()

    def courseware(self):
        plan = read(self.plan_file, {}); value = plan.get('courseware_file')
        return dict(path=value, text=self.relative(value).read_text(encoding='utf-8') if value and self.relative(value).is_file() else '')

    def save_courseware(self, text, expected):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000000: raise ValueError('课件稿为空或过长')
        with self.locked():
            state = read(self.state_file); self._revision(expected, state); self._snapshot(state)
            plan = read(self.plan_file); name = plan.get('courseware_file') or 'source/courseware.md'
            p = self.relative(name); ensure_dir(p.parent)
            tmp = p.with_name(p.name + '.pending-' + uuid.uuid4().hex); tmp.write_text(text, encoding='utf-8'); tmp.replace(p)
            plan.update(stage='courseware', courseware_file=name); atomic(self.plan_file, plan)
            state['narration_status'] = 'needs_regeneration'
            self._commit(state, 'courseware_saved', dict(path=name, sha256=sha(p)))
        return self.status()

    def require(self, key):
        status = self.status(); ids = [g['id'] for g in status['gates']]; end = ids.index(key)
        missing = [g['label'] for g in status['gates'][:end+1] if g['status'] != 'confirmed']
        if missing: raise ValueError('请先完成本版确认：' + '、'.join(missing))

    def brief(self):
        s = self.status(); lines = [s['title'], '当前阶段：' + s['stage'], '下一步：' + s['next_action']]
        lines += ['已确认：' + '、'.join(g['label'] for g in s['gates'] if g['status'] == 'confirmed')]
        lines += ['选择 ' + d['id'] + '：' + str(d.get('selected')) + '｜' + str(d.get('confirmed_at', '')) + '｜' + str(d.get('evidence', ''))
                  for d in s['plan'].get('decisions', []) if d.get('status') in ['confirmed', 'delegated']]
        lines += ['待解决 ' + p['id'] + '：' + p['question'] for p in s['pending']]
        lines += ['已登记产物：' + json.dumps(s['artifacts'], ensure_ascii=False),
                  '运行/完成任务：' + json.dumps(s['jobs'], ensure_ascii=False), '配音状态：' + s['narration_status']]
        if s.get('production_handoff',{}).get('active'):
            lines.append('制作接续（制作端自动执行）：'+json.dumps(s['production_handoff'],ensure_ascii=False))
        return '\n'.join(lines)


class Course(LegacyCourse):
    """v5 branches share an approved transcript; v4 courses retain their old contract."""
    COMMON = [('outline', '课程结构与讲解方法'), ('script', '逐字稿')]
    VIDEO = [('style', '导演画面与三个视觉风格'), ('pilot', '配音与画面小样'), ('final', '完整视频交付')]

    def modern(self):
        return read(self.state_file, {}).get('schema') == 'course-workflow/2'

    def design_schema(self):
        return 2 if self.modern() else 1

    def available_gates(self):
        return self.COMMON + self.VIDEO + [('courseware', '课件交付')] if self.modern() else GATES

    def init(self, title='新课程'):
        if self.state_file.exists(): return self.status()
        with self.locked():
            if self.state_file.exists(): return self.status()
            atomic(self.plan_file, dict(schema_version=2, title=title, stage='outline', audience='',
                performance_task='', sources=[], objectives=[], units=[], assessments=[], decisions=[], issues=[],
                handoff=dict(ready_for_courseware=False, ready_for_production=False)))
            atomic(self.state_file, dict(schema='course-workflow/2', version=VERSION, course_id=uuid.uuid4().hex,
                revision=0, created_at=now(), updated_at=now(), gates={}, artifacts={}, journal=[],
                branch=None, branch_history=[], deliveries=[], narration_status='not_started'))
        return self.status()

    def script(self):
        if not self.modern(): return super().courseware()
        plan=read(self.plan_file);name=plan.get('script_file')
        return dict(path=name,text=self.relative(name).read_text(encoding='utf-8') if name and self.relative(name).is_file() else '')

    def courseware(self):
        return self.script() if self.modern() else super().courseware()

    def script_sha(self, plan=None):
        plan=plan or read(self.plan_file);name=plan.get('script_file')
        p=self.relative(name) if name else None
        return sha(p) if p and p.is_file() else None

    def save_script(self, text, expected):
        if not self.modern(): return super().save_courseware(text, expected)
        if not isinstance(text,str) or not text.strip() or len(text)>2000000: raise ValueError('逐字稿为空或过长')
        with self.locked():
            state=read(self.state_file);self._revision(expected,state);self.require('outline');self._snapshot(state)
            plan=read(self.plan_file);name='source/transcript.md';path=self.relative(name);ensure_dir(path.parent)
            tmp=path.with_name(path.name+'.pending-'+uuid.uuid4().hex);tmp.write_text(text,encoding='utf-8');tmp.replace(path)
            plan.update(stage='script',script_file=name);plan.pop('courseware_file',None);atomic(self.plan_file,plan)
            state['narration_status']='needs_regeneration' if state.get('branch')=='video' else 'not_required'
            self._commit(state,'script_saved',dict(path=name,sha256=sha(path)))
        return self.status()

    def save_courseware(self, text, expected):
        return self.save_script(text,expected) if self.modern() else super().save_courseware(text,expected)

    def select_branch(self, branch, expected, evidence, actor='chat'):
        if not self.modern(): raise ValueError('旧版工程保留原流程；分支流程请新建v5工程')
        if branch not in ['courseware','video'] or not str(evidence).strip(): raise ValueError('请选择课件或视频并记录实际请求')
        with self.locked():
            state=read(self.state_file);self._revision(expected,state);self.require('script');self._snapshot(state)
            receipt=dict(branch=branch,at=now(),evidence=str(evidence),actor=actor,script_sha256=self.script_sha())
            state['branch']=branch;state['branch_receipt']=receipt;state['branch_history'].append(receipt)
            if branch=='courseware':state['narration_status']='not_required'
            elif state.get('narration_status')=='not_required':state['narration_status']='not_started'
            self._commit(state,'branch_selected',receipt)
        return self.status()

    def director(self):
        return read(self.project/'director-plan.json',{})

    def _director_proof(self, data=None):
        data=data if data is not None else self.director();errors=[];previews={}
        if data.get('basis')!='approved-transcript' or data.get('script_sha256')!=self.script_sha():
            errors.append('导演方案须绑定当前已确认逐字稿')
        excerpt=data.get('script_excerpt','')
        compact=lambda value: ''.join(value.split())
        if not isinstance(excerpt,str) or not excerpt.strip() or compact(excerpt) not in compact(self.script()['text']):
            errors.append('三个风格须使用本稿中的同一段实际内容')
        original=self._source_files(read(self.plan_file));allowed={v['path'] for v in original.values() if v['sha256']}
        generated={item['sha256'] for d in read(self.state_file).get('deliveries',[]) if d['branch']=='courseware' for item in d['files'] if Path(item['path']).suffix.lower()!='.md'}
        inputs=data.get('inputs',[])
        if not isinstance(inputs,list) or not any(isinstance(i,dict) and i.get('role')=='transcript' and i.get('path')==self.script()['path'] for i in inputs):
            errors.append('导演输入缺少当前逐字稿')
        for item in inputs:
            try:
                path=self.relative(item['path']);role=item['role']
                if not path.is_file() or role not in ['transcript','original'] or (role=='original' and item['path'] not in allowed):
                    errors.append('导演仅接受逐字稿和已登记原始素材')
                elif sha(path) in generated or path.is_relative_to(self.root/'delivery/courseware'):
                    errors.append('独立生成的课件不能成为视频制作基础')
            except (KeyError,ValueError,TypeError):errors.append('导演输入路径无效')
        styles=data.get('styles',[])
        visual_scope=data.get('style_scope')=='visual'
        if data.get('style_scope') not in [None,'visual']:
            errors.append('style_scope 须为 visual；旧方案可保留未声明状态')
        ids=[i.get('id') for i in styles if isinstance(i,dict)]
        if len(styles)!=3 or len(ids)!=3 or any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=3:
            errors.append('导演须提供三个不同的视觉风格')
        for style in styles:
            if not isinstance(style,dict):continue
            required=['id','title','rationale','production_impact','preview_file']+([] if visual_scope else ['motion'])
            if any(not isinstance(style.get(k),str) or not style[k].strip() for k in required):
                errors.append('风格须含实际预览、推荐理由与制作影响'+('' if visual_scope else '；旧方案还须保留动作说明'));continue
            if visual_scope:
                visual=style.get('visual',{})
                if not isinstance(visual,dict) or any(not isinstance(visual.get(k),str) or not visual[k].strip() for k in ['palette','typography','graphics','atmosphere']):
                    errors.append('视觉风格须说明配色、字体、图形与材质、画面气质；动效在分镜中按内容安排')
            try:
                p=self.relative(style['preview_file'])
                if not p.is_file() or p.suffix.lower() not in ['.svg','.png','.jpg','.jpeg','.webp','.html'] or not p.stat().st_size:
                    errors.append('视觉风格缺少可查看的画面预览')
                else:previews[style['id']]=sha(p)
            except ValueError:errors.append('视觉预览路径超出工程')
        if len(set(previews.values()))!=3:errors.append('三个风格须有不同的实际预览')
        if data.get('recommended') not in ids:errors.append('请说明推荐的视觉风格')
        beats=data.get('beats',[])
        if not isinstance(beats,list) or not beats:errors.append('缺少由逐字稿拆解的画面与动作')
        expected_units={u['id'] for u in read(self.plan_file).get('units',[]) if u.get('disposition')=='core'}
        covered=set();assessment_ids=set();source_text=compact(self.script()['text'])
        for beat in beats:
            if not isinstance(beat,dict) or any(not isinstance(beat.get(k),str) or not beat[k].strip() for k in ['id','unit_id','script_excerpt','picture','action']):
                errors.append('分镜需绑定教学单元、逐字稿片段、画面与动作');continue
            if compact(beat['script_excerpt']) not in source_text:errors.append('分镜引用了逐字稿中不存在的内容')
            covered.add(beat['unit_id']);assessment_ids.update(beat.get('assessment_ids',[]))
        if expected_units-covered:errors.append('核心教学单元尚未映射到导演画面：'+','.join(sorted(expected_units-covered)))
        expected_assessments={a['id'] for a in read(self.plan_file).get('assessments',[])}
        if expected_assessments-assessment_ids:errors.append('练习与反馈尚未映射到导演画面：'+','.join(sorted(expected_assessments-assessment_ids)))
        proof=dict(errors=list(dict.fromkeys(errors)),sha256=hashed(dict(plan=data,previews=previews)))
        if visual_scope:
            # The selected art direction is shared; scene actions remain content-led.
            # The full plan still fingerprints each actual preview/export version.
            choices=[{k:s.get(k) for k in ['id','title','rationale','visual','production_impact','preview_file']} for s in styles if isinstance(s,dict)]
            proof['style_sha256']=hashed(dict(scope='visual',basis=data.get('basis'),script_sha256=data.get('script_sha256'),
                script_excerpt=excerpt,styles=choices,recommended=data.get('recommended'),previews=previews))
        return proof

    def save_director(self, data, expected):
        if not isinstance(data,dict):raise ValueError('导演方案须为对象')
        with self.locked():
            state=read(self.state_file);self._revision(expected,state);self.require_video('script')
            proof=self._director_proof(data)
            if proof['errors']:raise ValueError('；'.join(proof['errors']))
            self._snapshot(state);atomic(self.project/'director-plan.json',data)
            self._commit(state,'director_saved',dict(sha256=proof['sha256']))
        return self.status()

    def select_style(self, identifier, expected, evidence, actor='workbench'):
        with self.locked():
            state=read(self.state_file);self._revision(expected,state);self.require_video('script')
            proof=self._director_proof();data=self.director()
            if proof['errors']:raise ValueError('；'.join(proof['errors']))
            plan=read(self.plan_file);errors=self._readiness('style',plan,state,self._pending(plan))
            if errors:raise ValueError('；'.join(errors))
            if identifier not in [s['id'] for s in data['styles']] or not str(evidence).strip():raise ValueError('请明确选择风格并保留确认说明')
            self._snapshot(state);state['selected_style']=identifier
            state['gates']['style']=dict(at=now(),evidence=str(evidence),actor=actor,selected=identifier,
                sha256=self._gate_hash('style',read(self.plan_file),state))
            self._commit(state,'style_confirmed',dict(selected=identifier,evidence=str(evidence),actor=actor))
        return self.status()

    def _video_context(self, state=None):
        from performance_cache import native_fingerprint
        state=state or read(self.state_file)
        return dict(script_sha256=self.script_sha(),director_sha256=self._director_proof()['sha256'],
            style=state.get('selected_style'),workbench=hashed(read(self.project/'workbench.json',{})),native=native_fingerprint(self.project))

    def _pilot_basis(self,state):
        """Approval covers the frozen prototype and its shared creative choices.

        Full production may add scenes and narration after approval. It is a new
        artifact, not an edit to the immutable reviewed MP4.
        """
        doc=read(self.project/'workbench.json',{});audio=doc.get('audio',{});proof=self._director_proof()
        visual_scope=self.director().get('style_scope')=='visual'
        basis=dict(script_sha256=self.script_sha(),director_sha256=proof.get('style_sha256',proof['sha256']),
            style=state.get('selected_style'),voice=audio.get('voice'),speed=audio.get('speed',1),
            gain=audio.get('gain',1),caption_style=doc.get('captionStyle'))
        if doc.get('motionPolicy',{}).get('required'):
            if doc.get('motionPolicy',{}).get('semanticRequired'):basis['narration_object_contract']='narration-object-events/1'
            from motion_quality import runtime_digest
            basis['motion_library']=runtime_digest(self.project,doc)
            if not visual_scope:
                basis['motion_language']=doc.get('motionPlan',{}).get('language')
                basis['protected_effects']=sorted(doc.get('motionPlan',{}).get('protectedEffects',[]))
        if visual_scope:basis['style_scope']='visual'
        if state.get('visual_palette'):
            from visual_identity import digest
            basis['visual_palette_sha256'] = digest(state['visual_palette'])
        return basis

    def _artifact_hashes(self, key, state):
        result=[]
        for name in state.get('artifacts',{}).get(key,[]):
            p=self.relative(name);result.append(dict(path=name,sha256=sha(p) if p.is_file() else None))
        return result

    def _pending(self,plan):
        pending=super()._pending(plan)
        if not self.modern():return pending
        branch=read(self.state_file).get('branch');issues={i['id']:i for i in plan.get('issues',[])};result=[]
        for item in pending:
            issue=issues.get(item['id']) if item.get('kind')=='issue' else None
            if issue:
                item['gate']=issue.get('gate','outline' if issue.get('blocks')=='courseware' else 'script')
                if branch and branch not in issue.get('branches',['courseware','video']):continue
            result.append(item)
        return result

    def _gate_hash(self, key, plan, state):
        if not self.modern():return super()._gate_hash(key,plan,state)
        decisions=[dict(id=d['id'],subject=self._subject(d),selected=d.get('selected'),status=d.get('status')) for d in plan['decisions'] if d.get('gate','outline')==key]
        if key=='outline':data=dict(plan={k:plan.get(k) for k in ['sources','source_items','audience','performance_task','objectives','units','assessments']},sources=self._source_files(plan))
        elif key=='script':data=dict(script=self.script_sha(plan),assessments=plan['assessments'])
        elif key=='style':
            proof=self._director_proof();data=dict(director=proof.get('style_sha256',proof['sha256']),selected=state.get('selected_style'))
        elif key=='courseware':data=dict(script=self.script_sha(plan),files=self._artifact_hashes(key,state))
        elif key=='pilot':data=dict(basis=self._pilot_basis(state),files=self._artifact_hashes(key,state))
        else:data=dict(context=self._video_context(state),files=self._artifact_hashes(key,state))
        return hashed(dict(data=data,decisions=decisions))

    def _readiness(self,key,plan,state,pending):
        if not self.modern():return super()._readiness(key,plan,state,pending)
        errors=[]
        if key in ['outline','script']:
            from check_design import check
            candidate=copy.deepcopy(plan);candidate['handoff']=dict(ready_for_courseware=False,ready_for_production=False)
            errors.extend(check(candidate,self.project)['errors'])
            if any(v['sha256'] is None for v in self._source_files(plan).values()):errors.append('原始素材文件缺失')
            if key=='script' and not self.script_sha(plan):errors.append('请先生成完整逐字稿')
            block='courseware' if key=='outline' else 'production'
            upstream=['outline'] if key=='outline' else ['outline','script']
            errors.extend('待解决：'+p['id'] for p in pending if block in p.get('blocking_for',[]) and p.get('gate') in upstream)
        elif key=='style':errors.extend(self._director_proof()['errors'])
        else:
            files=self._artifact_hashes(key,state)
            if not files or any(f['sha256'] is None for f in files):errors.append('尚未生成本阶段实际产物')
            reviewed=key=='pilot' and state.get('gates',{}).get('pilot',{}).get('sha256')==self._gate_hash('pilot',plan,state)
            if reviewed and state.get('visual_palette'):
                from visual_identity import check as check_palette
                errors.extend(check_palette(read(self.project/'workbench.json', {}), state['visual_palette']))
            if key in ['pilot','final'] and not reviewed and state.get(key+'_context')!=self._video_context(state):errors.append('样片或成片与当前逐字稿、风格或画面版本不一致，请重新生成')
        if key=='final' and state.get('artifacts',{}).get('final'):
            from performance_cache import director_review
            target=self.relative(state['artifacts']['final'][0])
            if target.is_file():errors.extend(director_review(self.project,read(self.project/'workbench.json'),target)['errors'])
        errors.extend(('待解决：' if p.get('kind')=='issue' else '待选择：')+p['id'] for p in pending if p.get('gate')==key)
        return list(dict.fromkeys(errors))

    def status(self):
        if not self.modern():
            result=super().status()
            from production import handoff
            result['production_handoff']=handoff(self.project,result)
            return result
        plan=read(self.plan_file);state=read(self.state_file);pending=self._pending(plan);branch=state.get('branch')
        keys=self.COMMON+(self.VIDEO if branch=='video' else [('courseware','课件交付')] if branch=='courseware' else [])
        gates=[];upstream=True
        for key,label in keys:
            receipt=state.get('gates',{}).get(key,{})
            errors=self._readiness(key,plan,state,pending);valid=bool(receipt and receipt.get('sha256')==self._gate_hash(key,plan,state) and upstream and not errors)
            delivery=key in ['courseware','final'];current='delivered' if delivery and valid else 'confirmed' if valid else 'stale' if receipt else 'open'
            needs_artifact=(key=='script' and not self.script_sha(plan)) or (key=='style' and not self.director().get('styles')) or (key=='pilot' and not self._artifact_hashes(key,state))
            gates.append(dict(id=key,label=label,status=current,ready=upstream and not errors,reasons=errors,receipt=receipt,delivery=delivery,needs_artifact=needs_artifact))
            upstream=valid
        common=all(g['status']=='confirmed' for g in gates[:2]);complete=common and bool(branch) and upstream
        first=next((g for g in gates if g['status'] not in ['confirmed','delivered']),None)
        stage='complete' if complete else first['id'] if first else 'branch'
        if stage=='complete':action='课件与逐字稿已交付；以后可从本稿启动视频' if branch=='courseware' else '完整视频已生成并交付，可观看与提出修改'
        elif stage=='branch':action='逐字稿已确认，请选择制作课件或视频'
        elif stage in ['courseware','final']:action='生成并交付课件与逐字稿' if stage=='courseware' else '小样已确认，可以生成完整视频'
        elif stage=='script' and not self.script_sha(plan):action='教学方案已确认，编写逐字稿供你审阅'
        elif stage=='pilot' and not state['artifacts'].get('pilot'):action='风格已确认，生成配音与画面小样供你审阅'
        elif stage=='pilot' and state.get('pilot_context')!=self._video_context(state):action='内容已变化，请重新生成配音与画面小样供你审阅'
        elif stage=='style':action='导演基于逐字稿提供三个风格，选择并确认画面方案'
        else:action='审阅并确认'+next(g['label'] for g in gates if g['id']==stage)
        plan['handoff']=dict(ready_for_courseware=common,ready_for_production=common and branch=='video' and any(g['id']=='style' and g['status']=='confirmed' for g in gates))
        jobs=[{k:d.get(k) for k in ['id','status','video','srt','package','revision']} for p in sorted((self.project/'work/workbench/exports').glob('*/result.json')) for d in [read(p)]]
        narration=state.get('narration_status','not_started')
        if branch=='video' and narration=='not_required':narration='not_started'
        result=dict(version=VERSION,workflow_schema=2,course_id=state['course_id'],title=plan['title'],revision=state['revision'],stage=stage,next_action=action,
            branch=branch,branch_receipt=state.get('branch_receipt'),branch_history=state.get('branch_history',[]),selected_style=state.get('selected_style'),director=self.director(),script_sha256=self.script_sha(plan),
            deliveries=state.get('deliveries',[]),gates=gates,pending=pending,plan=plan,artifacts=state['artifacts'],jobs=jobs,source_files=self._source_files(plan),
            narration_status='not_required' if branch!='video' else 'ready' if complete else 'sample_ready' if any(g['id']=='pilot' and g['status'] in ['open','confirmed'] and g['ready'] for g in gates) else 'needs_regeneration' if state['artifacts'].get('pilot') else narration,updated_at=state['updated_at'])
        result['rendering']=read(self.project/'workbench.json',{}).get('rendering',{})
        result['director_review_status']=state.get('director_review_status')
        if stage=='final' and state.get('artifacts',{}).get('final') and state.get('director_review_status',{}).get('status')=='pending':result['next_action']='当前完整视频为候选；制作端完成逐段导演复核后登记，不重复渲染或代填用户认可'
        from production import handoff
        result['production_handoff']=handoff(self.project,result)
        result['state_key']=hashed(dict(plan=plan,gates=gates,branch=branch,selected_style=state.get('selected_style'),director=result['director'],deliveries=result['deliveries']))
        return result

    def require(self,key):
        if not self.modern():return super().require(key)
        key={'content':'script','visual':'style'}.get(key,key)
        gates=self.status()['gates'];ids=[g['id'] for g in gates]
        if key not in ids:raise ValueError('本分支没有该阶段：'+key)
        missing=[g['label'] for g in gates[:ids.index(key)+1] if g['status'] not in ['confirmed','delivered']]
        if missing:raise ValueError('请先完成本版确认：'+'、'.join(missing))

    def require_video(self,key):
        if self.modern() and read(self.state_file).get('branch')!='video':raise ValueError('当前未选择视频分支，不能启动视频制作')
        self.require(key)

    def confirm(self,key,expected,evidence,actor='workbench'):
        if self.modern() and key in ['style','courseware','final']:
            raise ValueError('风格请使用明确的风格选择；交付产物由实际文件检查登记')
        return super().confirm(key,expected,evidence,actor)

    def register(self,key,paths,expected,evidence='实际产物已生成',actor='artifact-check',render_context=None):
        if not self.modern():return super().register(key,paths,expected)
        if key not in ['pilot','final','courseware']:raise ValueError('请用director保存导演方案，用script保存逐字稿')
        self.require_video('style' if key=='pilot' else 'pilot') if key!='courseware' else self.require('script')
        if key=='courseware' and read(self.state_file).get('branch')!='courseware':raise ValueError('请先选择课件分支')
        if not paths or any(not self.relative(p).is_file() for p in paths):raise ValueError('实际交付文件不存在')
        if key in ['pilot','final']:
            from motion_quality import require as require_motion
            require_motion(read(self.project/'workbench.json'),self.project)
            videos=[self.relative(p) for p in paths if Path(p).suffix.lower()=='.mp4']
            if not videos:raise ValueError('配音和画面小样须有真实有声MP4，不能只交音频')
            for path in videos:
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
                if not {'video','audio'}.issubset({s.get('codec_type') for s in probe['streams']}) or float(probe['format']['duration'])<=0:raise ValueError('需要实际画面与声音')
        else:
            import zipfile
            documents=[self.relative(p) for p in paths if Path(p).suffix.lower() in ['.pptx','.pdf','.html']]
            if not documents:raise ValueError('课件须为实际PPTX、PDF或HTML，不能用逐字稿代替')
            for path in documents:
                if not (path.is_relative_to(self.root/'delivery/courseware') or path.is_relative_to(self.project/'courseware')):
                    raise ValueError('独立课件请存放在delivery/courseware或project/courseware，避免混入视频源码')
                if path.suffix=='.pptx':
                    with zipfile.ZipFile(path) as z:
                        if z.testzip() or 'ppt/presentation.xml' not in z.namelist() or not any(n.startswith('ppt/slides/slide') and n.endswith('.xml') for n in z.namelist()):raise ValueError('PPTX课件无有效幻灯片')
                elif path.suffix=='.pdf' and not path.read_bytes().startswith(b'%PDF'):raise ValueError('PDF课件格式无效')
                elif path.suffix=='.html' and '<html' not in path.read_text(encoding='utf-8').lower():raise ValueError('HTML课件格式无效')
        with self.locked():
            state=read(self.state_file);self._revision(expected,state);self._snapshot(state)
            context=self._video_context(state) if key!='courseware' else None
            if render_context is not None and context!=render_context:raise ValueError('导出时版本已改变，请重新生成当前小样或成片')
            import shutil
            stable=[]
            for name in paths:
                path=self.relative(name);dest=self.project/'qa/reviews'/key/(sha(path)[:12]+'-'+path.name);ensure_dir(dest.parent)
                if path!=dest and not dest.exists():shutil.copy2(path,dest)
                sidecar=path.with_suffix('.json')
                if key=='pilot' and path.suffix.lower()=='.mp4' and sidecar.is_file() and read(sidecar).get('video_sha256')==sha(path) and sidecar!=dest.with_suffix('.json'):
                    shutil.copy2(sidecar,dest.with_suffix('.json'))
                stable.append(str(dest.relative_to(self.project)))
            if key=='courseware':
                target=self.root/'delivery/courseware/课程逐字稿.md';ensure_dir(target.parent);target.write_text(self.script()['text'],encoding='utf-8')
                stable.append('../'+str(target.relative_to(self.root)))
            state['artifacts'][key]=stable
            if context:state[key+'_context']=context
            quality_ready=True
            if key=='final':
                from motion_quality import director_review
                quality=director_review(self.project,read(self.project/'workbench.json'),videos[0])
                state['director_review_status']=quality
                quality_ready=quality['status'] in ['pass','legacy-not-opted-in']
                if not quality_ready:state['gates'].pop('final',None)
            if key in ['courseware','final'] and quality_ready:
                receipt=dict(at=now(),evidence=str(evidence),actor=actor,sha256=self._gate_hash(key,read(self.plan_file),state))
                state['gates'][key]=receipt
                state['deliveries'].append(dict(branch='courseware' if key=='courseware' else 'video',at=now(),script_sha256=self.script_sha(),files=self._artifact_hashes(key,state),evidence=str(evidence)))
            self._commit(state,'artifacts_registered',dict(gate=key,paths=stable))
        return self.status()

    def brief(self):
        if not self.modern():return super().brief()
        status=self.status();lines=[super().brief(),'当前分支：'+str(status['branch']),'已选视觉风格：'+str(status['selected_style']),
            '已交付：'+json.dumps(status['deliveries'],ensure_ascii=False),'导演输入：仅已确认逐字稿与原始素材；独立课件不进入视频制作']
        lines += ['分支请求：'+json.dumps(receipt,ensure_ascii=False) for receipt in status['branch_history']]
        lines += ['审阅记录 '+gate['id']+'：'+json.dumps(gate['receipt'],ensure_ascii=False)
                  for gate in status['gates'] if gate['receipt']]
        return '\n'.join(lines)


def local_json(url, data=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1': raise ValueError('仅连接本地工作台')
    request = urllib.request.Request(url, data=None if data is None else json.dumps(data).encode(),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        try:message=json.load(exc).get('error')
        except (ValueError,AttributeError):message=None
        raise ValueError(message or '工作台请求失败：HTTP '+str(exc.code)) from exc


def bundle_course(root, destination):
    """Package the current saved course, including review evidence and portable editor."""
    import zipfile
    course=Course(root);destination=Path(destination);ensure_dir(destination.parent)
    app=Path(__file__).resolve().parent;files={}
    for base in ['inputs','project','delivery']:
        for p in (course.root/base).rglob('*'):
            rel=p.relative_to(course.root)
            # work/style-previews 是风格确认引用的实操预览，不是可重建缓存；漏掉它重开副本会卡在风格闸门
            preview=len(rel.parts)>2 and rel.parts[1]=='work' and rel.parts[2]=='style-previews'
            if not p.is_file() or p.is_symlink() or (any(x in rel.parts for x in ['work','workbench-history','editor','__pycache__']) and not preview):continue
            if p.name.startswith('.') or p.suffix=='.pyc' or p.name in ['tools.json','voice.json']:continue
            if 'qa' in rel.parts and not p.is_relative_to(course.project/'qa/reviews'):continue
            files[str(rel)]=p
    for p in app.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
            files['project/editor/workbench/'+str(p.relative_to(app))]=p
    from render_routes import LIBRARIES
    library_root=app.parent/'libraries/illustration/scripts/engine/lib'
    if not library_root.is_dir():library_root=app/'motion/lib'
    for name in LIBRARIES:
        files['project/editor/workbench/motion/lib/'+name]=library_root/name
    license_file=library_root/'LICENSE' if (library_root/'LICENSE').is_file() else library_root.parents[2]/'LICENSE'
    files['project/editor/workbench/motion/lib/LICENSE']=license_file
    from sound import palette_root,PALETTE
    for p in palette_root(course.project).glob('*'):
        if p.is_file():files['project/audio/sfx/'+PALETTE+'/'+p.name]=p
    for name in ['workbench.py','workflow.py','single_line_subtitles.py','check_workbench.py','course_tools.py','character_assets.py']:
        files['project/editor/scripts/'+name]=app.parent/'scripts'/name
    for name in ['workspace.json','打开课程工作台.command','README.md']:
        if (course.root/name).is_file():files[name]=course.root/name
    proof=dict(version=VERSION,created_at=now(),course_id=course.status()['course_id'],
        files={name:sha(p) for name,p in files.items()},scope='current saved design, choices, review receipts, media and editable renderer')
    tmp=destination.with_name(destination.name+'.pending-'+uuid.uuid4().hex)
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.writestr('course-package-manifest.json',json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(tmp) as z:
        if z.testzip():raise ValueError('工程包CRC检查失败')
    tmp.replace(destination)
    return dict(path=str(destination),bytes=destination.stat().st_size,sha256=sha(destination),files=len(files))


def open_course(root, open_browser=True):
    course = Course(root)
    if not course.state_file.is_file(): raise ValueError('该工程未接入新版流程，旧课请使用原工作台入口')
    record = course.project / 'work/workbench-service.json'; server = read(record, {})
    url = server.get('url', '')
    try:
        identity = local_json(url + '/api/identity')
        from lifecycle import POLICY
        if identity.get('course_id') != read(course.state_file)['course_id'] or identity.get('version') != VERSION or identity.get('course_root')!=str(course.root) or identity.get('lifecycle_policy')!=POLICY: url = ''
    except (ValueError, OSError): url = ''
    if not url:
        ensure_dir(record.parent); log = record.parent / 'workbench-service.log'
        configured = tools().get('python', sys.executable)
        python = configured if Path(configured).is_file() else sys.executable
        with log.open('ab') as handle:
            process = subprocess.Popen([python, str(Path(__file__).resolve().parents[1]/'scripts/workbench.py'), 'serve', str(course.root)],
                stdin=subprocess.DEVNULL, stdout=handle, stderr=handle, start_new_session=True)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None: raise ValueError('工作台启动失败，请查看 ' + str(log))
            current = read(record, {})
            if current.get('pid') == process.pid:
                try:
                    identity=local_json(current['url'] + '/api/identity')
                    if identity.get('course_id') == read(course.state_file)['course_id'] and identity.get('course_root')==str(course.root):
                        url = current['url']; break
                except (ValueError, OSError): pass
            time.sleep(.15)
        if not url: raise ValueError('工作台尚未就绪，请查看 ' + str(log))
    opened = False
    if open_browser: opened = bool(webbrowser.open(url))
    print(course.brief()); print('WORKBENCH_URL=' + url)
    print('WORKBENCH_IDENTITY=' + json.dumps(dict(course_id=identity['course_id'],course_root=str(course.root),version=identity['version'],verified=True),ensure_ascii=False))
    print('WORKFLOW_STATE_URL=' + url + '/api/workflow')
    print('BROWSER_OPEN_REQUESTED=' + str(open_browser).lower() + '; accepted=' + str(opened).lower())
    return url


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    for name in ['start', 'resume', 'status']:
        a = sub.add_parser(name); a.add_argument('course', type=Path); a.add_argument('--no-open', action='store_true')
        if name == 'start': a.add_argument('--title', default='新课程'); a.add_argument('--source', type=Path)
        if name == 'status': a.add_argument('--json', action='store_true')
    a = sub.add_parser('design'); a.add_argument('course', type=Path); a.add_argument('--file', type=Path, required=True)
    a = sub.add_parser('decide'); a.add_argument('course', type=Path); a.add_argument('--id', required=True); a.add_argument('--option', required=True)
    a.add_argument('--evidence', required=True); a.add_argument('--actor', default='chat'); a.add_argument('--delegated', action='store_true')
    all_gates=dict(GATES+Course.COMMON+Course.VIDEO+[('courseware','课件交付')])
    for name in ['script','director']:
        a=sub.add_parser(name);a.add_argument('course',type=Path);a.add_argument('--file',type=Path,required=True)
    a=sub.add_parser('branch');a.add_argument('course',type=Path);a.add_argument('--type',choices=['courseware','video'],required=True);a.add_argument('--evidence',required=True);a.add_argument('--actor',default='chat')
    a=sub.add_parser('style');a.add_argument('course',type=Path);a.add_argument('--id',required=True);a.add_argument('--evidence',required=True);a.add_argument('--actor',default='chat')
    a = sub.add_parser('checkpoint'); a.add_argument('course', type=Path); a.add_argument('--gate', choices=all_gates, required=True)
    a.add_argument('--artifact', action='append', default=[])
    a = sub.add_parser('review');a.add_argument('course',type=Path);a.add_argument('--gate',choices=all_gates,required=True)
    a.add_argument('--evidence',required=True);a.add_argument('--actor',default='chat')
    a = sub.add_parser('package'); a.add_argument('course',type=Path);a.add_argument('--out',type=Path,required=True)
    args = p.parse_args(); course = Course(args.course)
    if args.command == 'start':
        created=not (course.project / 'workbench.json').is_file()
        if created:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
            from scaffold import create
            create(args.course)
        course.init(args.title)
        if created:
            current=course.status();plan=current['plan'];plan['title']=args.title
            course.save_plan(plan,current['revision'])
        if args.source:
            import shutil
            source = args.source.expanduser().resolve()
            if not source.is_file(): raise ValueError('原始素材不存在')
            dest = course.root / 'inputs' / source.name
            if dest.exists() and sha(source) != sha(dest): raise ValueError('同名原件已存在且内容不同')
            if source != dest and not dest.exists(): shutil.copy2(source, dest)
            status = course.status(); plan = status['plan']
            if not any(s.get('location') == '../inputs/' + source.name for s in plan['sources']):
                plan['sources'].append(dict(id='SRC-' + sha(dest)[:10], title=source.name,
                    location='../inputs/' + source.name, kind='file', sha256=sha(dest)))
                course.save_plan(plan, status['revision'])
        open_course(args.course, not args.no_open)
    elif args.command == 'resume': open_course(args.course, not args.no_open)
    elif args.command == 'status': print(json.dumps(course.status(), ensure_ascii=False, indent=2) if args.json else course.brief())
    elif args.command == 'design': print(json.dumps(course.save_plan(read(args.file), course.status()['revision']), ensure_ascii=False, indent=2))
    elif args.command == 'script':print(json.dumps(course.save_script(args.file.read_text(encoding='utf-8'),course.status()['revision']),ensure_ascii=False,indent=2))
    elif args.command == 'director':print(json.dumps(course.save_director(read(args.file),course.status()['revision']),ensure_ascii=False,indent=2))
    elif args.command == 'branch':print(json.dumps(course.select_branch(args.type,course.status()['revision'],args.evidence,args.actor),ensure_ascii=False,indent=2))
    elif args.command == 'style':print(json.dumps(course.select_style(args.id,course.status()['revision'],args.evidence,args.actor),ensure_ascii=False,indent=2))
    elif args.command == 'decide': print(json.dumps(course.decide(args.id, args.option, course.status()['revision'], args.evidence, args.actor, args.delegated), ensure_ascii=False, indent=2))
    elif args.command == 'checkpoint': print(json.dumps(course.register(args.gate, args.artifact, course.status()['revision']), ensure_ascii=False, indent=2))
    elif args.command == 'review':print(json.dumps(course.confirm(args.gate,course.status()['revision'],args.evidence,args.actor),ensure_ascii=False,indent=2))
    elif args.command == 'package':print(json.dumps(bundle_course(args.course,args.out),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError) as exc: print(str(exc), file=sys.stderr); raise SystemExit(2)
