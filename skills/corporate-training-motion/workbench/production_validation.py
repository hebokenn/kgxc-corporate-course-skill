"""Production execution checks (04–09), consumed by the one release contract.

No approvals are written. Evidence remains in the course, never in the Skill.
"""
import hashlib
import json
import math
from pathlib import Path

ENCODED = {'sample', 'pilot', 'final', 'export', 'delivery', 'release'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def sha(path):
    if path is None:
        return None
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def path_in(project, value):
    if not isinstance(value, (str, Path)) or not str(value):
        return None
    p = (Path(project) / value).resolve()
    return p if p.is_relative_to(Path(project).resolve()) else None


def resolve_current_video(project,value):
    """Explicit current media may live in the same course's delivery sibling."""
    if not isinstance(value,(str,Path)) or not str(value):return None
    project=Path(project).resolve();p=(project/value).resolve()
    return p if p.is_relative_to(project.parent) else None


def load(project, value, default=None):
    if isinstance(value, (dict, list)):
        return value
    p = path_in(project, value)
    if p and p.is_file():
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            pass
    return {} if default is None else default


class Check:
    def __init__(self, section):
        self.section = section
        self.errors, self.evidence, self.details = [], [], {}

    def error(self, code, message, item=None, **extra):
        self.errors.append(dict(code=code, message=message, section=self.section,
                                item_id=item, **extra))

    def result(self):
        return dict(ready=not self.errors, errors=self.errors, evidence_refs=self.evidence,
                    details=self.details, scope='execution evidence only; not user approval')


def graph(doc):
    from reading_pacing import _index
    return _index(doc)


def visible(doc, nodes, chains, identifier, frame):
    from reading_pacing import _state, REVEALS
    if identifier not in nodes:
        return False
    alpha = 1
    for k in chains[identifier]:
        n = nodes[k]
        if n.get('sceneId') and not any(s.get('id')==n['sceneId'] and s.get('sourceStartFrame',0)<=frame<s.get('sourceEndFrame',0) for s in doc.get('scenes',[])):
            return False
        if n.get('visible', True) is False or not n.get('startFrame', 0) <= frame < n.get('endFrame', doc.get('sourceDurationFrames', 0)):
            return False
        alpha *= _state(n, frame).get('opacity', 1)
        if any(e.get('type') in REVEALS and frame < e['endFrame'] for e in n.get('effects', [])):
            return False
    return alpha >= .99


def first_readable(doc, nodes, chains, identifier, end=None):
    if identifier not in nodes:
        return None
    a = max(nodes[k].get('startFrame', 0) for k in chains[identifier])
    z = min([nodes[k].get('endFrame', doc.get('sourceDurationFrames', 0)) for k in chains[identifier]] +
            [end if end is not None else doc.get('sourceDurationFrames', 0)])
    return next((f for f in range(max(0, a), z) if visible(doc, nodes, chains, identifier, f)), None)


def changed(node, a, z, recursive=True):
    """Actual child properties count; descriptive states/IDs never count."""
    for m in node.get('motion', []):
        if (m.get('property') in {'x', 'y', 'width', 'height', 'rotation', 'scaleX', 'scaleY', 'opacity'} and
                m.get('from') != m.get('to') and max(a, m.get('startFrame', z)) < min(z, m.get('endFrame', a))):
            return True
    actor=node.get('vectorActor') or node.get('acting') or {}
    for walk in actor.get('walks',[]):
        if walk.get('fromX')!=walk.get('toX') and max(a,walk.get('startFrame',z))<min(z,walk.get('endFrame',a)):return True
    for name in ('keys','facing'):
        keys=actor.get(name,[])
        if len({json.dumps(k.get('values',k.get('yaw')),sort_keys=True) for k in keys if a<=k.get('frame',-1)<z})>1:return True
    if recursive:
        return any(changed(c, a, z) for c in node.get('children', []))
    return False


def main_video_index(video):
    import subprocess
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    return next(s['index'] for s in streams if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))


_DECODED_FRAME_CACHE = {}

def decoded_frame_hashes(video, indices):
    """One exact from-head decode per missing set; excludes attached cover streams."""
    import subprocess
    from fractions import Fraction
    key=sha(video);missing=sorted(set(indices)-set(_DECODED_FRAME_CACHE.get(key,{})))
    if missing:
        from motion_samples import balanced_sum
        expression=balanced_sum(['eq(n\\,%d)'%f for f in missing])
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-map','0:'+str(main_video_index(video)),
            '-vf','select='+expression+',format=rgb24','-fps_mode','passthrough','-f','framemd5','-']).decode()
        tb=Fraction(next(line.split(':',1)[1].strip() for line in raw.splitlines() if line.startswith('#tb 0:')))
        rows=[line.split(',') for line in raw.splitlines() if line and not line.startswith('#')]
        if len(rows)!=len(missing):raise ValueError('Requested decoded frame is absent')
        cache=_DECODED_FRAME_CACHE.setdefault(key,{})
        for frame,row in zip(missing,rows):cache[frame]=dict(pixel_md5=row[-1].strip(),actual_pts=float(int(row[2])*tb))
    return {f:_DECODED_FRAME_CACHE[key][f] for f in indices}


def current_review(check, project, review, doc, video, code='EVIDENCE_STALE', required_frames=None):
    review = load(project, review)
    video_path = resolve_current_video(project, video)
    expected = sha(video_path) if video_path else None
    if not review or review.get('document_sha256') != digest(doc) or (expected and review.get('video_sha256') != expected):
        check.error(code, 'Evidence is absent or does not bind the current document/video')
        return []
    rows = review.get('observations', [])
    if not isinstance(rows, list) or not rows:
        check.error(code, 'Current encoded observations are empty')
        return []
    found = set()
    indices=[r.get('encoded_frame',r.get('frame')) for r in rows]
    actual={}
    if expected and all(type(f)is int and f>=0 for f in indices):
        try:actual=decoded_frame_hashes(video_path,indices)
        except Exception as exc:check.error(code,'Current encoded frame decode failed: '+str(exc))
    for r in rows:
        p = path_in(project, r.get('path'))
        frame = r.get('encoded_frame', r.get('frame'))
        if (not p or sha(p) != r.get('sha256') or not str(r.get('observation', '')).strip() or
                type(frame) is not int or r.get('video_sha256', expected) != expected):
            check.error(code, 'Observation must reference a real current decoded image and an actual observation', r.get('id'))
        else:
            from PIL import Image
            pixels=hashlib.md5(Image.open(p).convert('RGB').tobytes()).hexdigest()
            if frame not in actual or actual[frame]['pixel_md5']!=pixels:
                check.error(code,'PNG pixels do not match the exact current encoded frame',r.get('id'),frame=frame)
                continue
            claimed=r.get('actualPTS',r.get('actual_decoded_pts'))
            if claimed is None or abs(claimed-actual[frame]['actual_pts'])>1e-6:
                check.error(code,'Observation actual PTS is missing or differs from the decoded frame',r.get('id'),frame=frame)
                continue
            found.add(frame)
            check.evidence.append(dict(path=str(p), sha256=sha(p), frame=frame))
    if required_frames and not set(required_frames) <= found:
        check.error(code, 'Missing specified before/trigger/mid/landing/read-end images', missing_frames=sorted(set(required_frames)-found))
    if rows and len(rows) > 1 and len({r.get('observation') for r in rows}) == 1:
        check.error('EVIDENCE_GENERIC_OBSERVATION', 'A repeated generic sentence does not establish individual event observations')
    return rows


def inspect_extra(project, document=None, video=None, purpose='final', contract=None):
    """Also accepts (project, release_context); never accepts a caller checker hook."""
    p = Path(project).resolve()
    if isinstance(document, dict) and 'current_document' in document:
        context = document
        document, video, purpose, contract = (context.get('current_document'), context.get('current_video'),
            context.get('purpose', purpose), context.get('current_contract'))
    if purpose in {'outline','courseware'}:
        return dict(schema='course-execution-inspection/1',ready=True,errors=[],warnings=[],checks={},evidence_refs=[],
                    applicability='04–09 video execution checks do not demand future video/audio at outline or standalone courseware exit')
    doc = load(p, document)
    value = load(p, contract if contract is not None else 'production-contract.json')
    if not isinstance(doc, dict) or not isinstance(value, dict):
        return dict(ready=False, errors=[dict(code='EXECUTION_INPUT_INVALID', message='Document and contract must be objects')], checks={}, evidence_refs=[])
    from author_input_checks import inspect as inputs
    from presentation_signatures import inspect as presentations
    from semantic_alignment import inspect as semantic
    from emphasis_checks import inspect as emphasis
    from sfx_evidence import inspect as sfx
    from chapter_table import inspect as chapters
    checks = {}
    for name, fn in [('author_input', inputs), ('presentation', presentations), ('semantic', semantic),
                     ('emphasis', emphasis), ('sfx', sfx), ('chapters', chapters)]:
        try:
            checks[name] = fn(p, doc, video, purpose, value)
        except Exception as exc:
            checks[name] = dict(ready=False, errors=[dict(code='EXECUTION_CHECK_FAILED', section=name,
                message=type(exc).__name__+': '+str(exc))], evidence_refs=[])
    errors = [e for c in checks.values() for e in c.get('errors', [])]
    return dict(schema='course-execution-inspection/1', ready=not errors, errors=errors, warnings=[],
                checks=checks, evidence_refs=[e for c in checks.values() for e in c.get('evidence_refs', [])],
                scope='04–09 structural and current-media evidence; not continuous AV or human acceptance')
