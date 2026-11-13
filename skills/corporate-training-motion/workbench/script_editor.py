"""Transcript drafts, separate from approved production inputs and encoded media."""
from pathlib import Path
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import re
import time
import uuid


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ScriptEditor:
    def __init__(self, space):
        self.space = space
        self.path = space.project / 'script-editor.json'

    @contextmanager
    def locked(self):
        with self.path.with_suffix('.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def official(self):
        from workflow import Course
        if (self.space.project / 'course-state.json').is_file():
            return Course(self.space.root).script().get('text', '')
        source = self.space.project / 'source/transcript.md'
        return source.read_text() if source.is_file() else ''

    def read(self):
        from backend import read
        text = self.official()
        doc = read(self.space.file)
        title = doc['title']
        plan = self.space.project / 'design-plan.json'
        if plan.is_file(): title = read(plan).get('title') or title
        state = read(self.path) if self.path.is_file() else dict(schema='course-script-editor/1', revision=0, text=text, base_text=text, base_sha256=sha(text))
        state = copy.deepcopy(state)
        # Legacy drafts did not record their baseline. Reading them must retain
        # their bytes and text; an unknown baseline cannot authorize a merge.
        missing_base = 'base_text' not in state or 'base_sha256' not in state
        state.setdefault('schema', 'course-script-editor/1')
        state.setdefault('revision', 0)
        state.setdefault('text', text)
        state.setdefault('base_text', text)
        state.setdefault('base_sha256', sha(text))
        unknown_base = (state.get('base_unknown', False) or missing_base) and state['text'] != text
        state['base_unknown'] = unknown_base
        # Adopt an AI's newly written transcript only when this window has no edits.
        if not unknown_base and state['text'] in [state['base_text'], text] and state['base_sha256'] != sha(text):
            state.update(text=text, base_text=text, base_sha256=sha(text), revision=state['revision'] + 1)
        elif not unknown_base and state.get('render_request', {}).get('sha256') == sha(text):
            # Expected production of a frozen render input is safe to rebase onto;
            # text written after the click remains the user's current draft.
            state.update(base_text=text, base_sha256=sha(text))
        state.update(title=title, course_path=str(self.space.root), document=doc,
                     official_sha256=sha(text), base_changed=unknown_base or state['base_sha256'] != sha(text),
                     changed=state['text'] != text, has_scenes=bool(doc.get('scenes')))
        return state

    def write(self, state):
        from backend import atomic
        keep = ['schema', 'revision', 'text', 'base_text', 'base_sha256', 'base_unknown', 'render_request']
        atomic(self.path, {key: state[key] for key in keep if key in state})

    def save(self, text, expected):
        from render_input_guard import ensure_mutation_allowed
        ensure_mutation_allowed(self.space.project,'ScriptEditor.save',dict(text=text,expected=expected))
        if not isinstance(text, str) or len(text) > 2_000_000:
            raise ValueError('逐字稿超过可编辑长度')
        with self.locked():
            state = self.read()
            if state['revision'] != expected:
                raise FileExistsError('逐字稿已在其他窗口更新；当前修改仍留在编辑区，请重新打开后核对')
            if state['base_changed']:
                raise FileExistsError('正式稿与当前草稿的基线不一致；当前修改仍留在编辑区，请核对后再合并')
            if text != state['text']:
                state.update(text=text, revision=state['revision'] + 1)
                self.write(state)
            return self.read()

    def request_render(self, expected):
        if (self.space.project / 'course-state.json').is_file():
            from workflow import Course
            Course(self.space.root).require('outline')
        with self.locked():
            state = self.read()
            if state['revision'] != expected or state['base_changed']:
                raise FileExistsError('逐字稿已更新，请保存并核对当前内容后再渲染')
            if not state['text'].strip():
                raise ValueError('请先填写逐字稿')
            previous = state.get('render_request', {})
            if previous.get('status') in ['preparing', 'rendering']:
                raise ValueError('已有渲染任务正在处理')
            request = dict(id=uuid.uuid4().hex[:12], status='preparing', text=state['text'],
                           script_revision=state['revision'], sha256=sha(state['text']),
                           requested_at=time.time(), evidence='用户在逐字稿编辑窗口点击渲染，授权按当前所见稿件更新配音、对应画面并渲染；未授权补填其他方案确认。')
            state['render_request'] = request
            self.write(state)
            return request

    def render_update(self, request_id, status, *, error=None, job=None):
        if status not in ['preparing', 'rendering', 'complete', 'failed']:
            raise ValueError('渲染状态无效')
        with self.locked():
            state = self.read()
            request = state.get('render_request', {})
            if request.get('id') != request_id:
                raise FileExistsError('渲染请求已经改变')
            request.update(status=status)
            if error is not None: request['error'] = str(error)
            if job is not None: request['job'] = job
            self.write(state)
            return request
