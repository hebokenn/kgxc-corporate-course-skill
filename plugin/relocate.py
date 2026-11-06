"""Move a live course into its conversation workspace without copying an old project."""
from pathlib import Path
import hashlib
import os
import signal
import urllib.request
import json


def fingerprints(root):
    result = {}
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if not path.is_file() or path.suffix == '.lock' or rel.parts[:2] == ('project', 'work'):
            continue
        if path.is_symlink(): raise ValueError('工程内含符号链接，请先核对实际文件')
        result[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def relocate(course, workspace):
    from workflow import read
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir(): raise ValueError('会话工作区不存在')
    source = course.root.resolve()
    if source.is_relative_to(root): return dict(course_path=str(source), previous_path=str(source), moved=False)
    state = read(course.state_file)
    server = read(course.project / 'work/workbench-service.json', {})
    identity = None
    if server.get('url'):
        try:
            with urllib.request.urlopen(server['url'] + '/api/identity', timeout=3) as response: identity = json.load(response)
        except (OSError, ValueError): pass
    if identity:
        if identity.get('course_root') != str(source) or identity.get('course_id') != state['course_id'] or identity.get('pid') != server.get('pid'):
            raise ValueError('当前工作台身份不匹配，未迁移')
        with urllib.request.urlopen(server['url'] + '/api/jobs', timeout=5) as response: jobs = json.load(response)
        if any(job.get('status') in ['queued', 'rendering', 'encoding', 'packaging'] for job in jobs):
            raise ValueError('当前仍有视频制作任务，完成后再迁移工程')
    target = root / 'courses' / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists(): raise ValueError('工作区内已有同名目录，未覆盖')
    with course.locked():
        before = fingerprints(source)
        if identity: os.kill(identity['pid'], signal.SIGTERM)
        source.rename(target)
        after = fingerprints(target)
        if before != after:
            target.rename(source)
            raise ValueError('迁移文件校验不一致，已恢复原目录')
    return dict(course_path=str(target), previous_path=str(source), moved=True,
                course_id=state['course_id'], verified_files=len(before), file_sha256=before)
