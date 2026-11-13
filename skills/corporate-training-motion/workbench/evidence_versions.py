"""Content-addressed input/evidence dependencies; never reset review cycles by hashes."""
from pathlib import Path
import copy
import hashlib
import json
from execution_requirements import error, read, save, digest


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def file_ref(project, raw, allow_implementation=False):
    p = Path(project).resolve()
    path = Path(raw)
    path = (path if path.is_absolute() else p / path).resolve()
    code_root=Path(__file__).resolve().parents[1]
    if not (path.is_relative_to(p.parent) or allow_implementation and path.is_relative_to(code_root)) or not path.is_file():
        raise ValueError('Missing/outside-course input: ' + str(path))
    return dict(path=str(path), sha256=sha(path))


def fingerprint(project, inputs):
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('Explicit named inputs required')
    refs = {key: [file_ref(project, p, allow_implementation=key=='render_implementation') for p in (raw if isinstance(raw, list) else [raw])]
            for key, raw in inputs.items()}
    return dict(schema='course-input-fingerprint/1', inputs=refs, sha256=digest(refs))


def freeze_inputs(project, inputs, render_id):
    if not isinstance(render_id, str) or not render_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in render_id):
        raise ValueError('Stable render ID required')
    value = fingerprint(project, inputs)
    value['render_id'] = render_id
    path = Path(project) / 'work/input-freezes' / (render_id + '.json')
    if path.exists() and read(path) != value:
        raise ValueError('INPUT_CHANGED_DURING_RENDER: frozen render identity cannot be rebound')
    save(path, value)
    return value


def check_frozen(project, frozen):
    errors = []
    for role, refs in frozen.get('inputs', {}).items():
        for ref in refs:
            try:
                current = file_ref(project, ref['path'],allow_implementation=role=='render_implementation')
                if current['sha256'] != ref['sha256']:
                    errors.append(error('INPUT_CHANGED_DURING_RENDER', 'Frozen input bytes changed.', role=role, path=ref['path']))
            except (OSError, ValueError, KeyError):
                errors.append(error('INPUT_CHANGED_DURING_RENDER', 'Frozen input missing.', role=role))
    if not frozen.get('inputs'):
        errors.append(error('INPUT_CHANGED_DURING_RENDER', 'No actual frozen inputs recorded.'))
    return dict(ready=not errors, errors=errors)


def validate_evidence(project, evidence, current):
    errors = []
    if not isinstance(evidence, dict):
        return [error('EVIDENCE_STALE', 'Evidence reference must be an object.')]
    for field in ['path', 'sha256', 'actor', 'method', 'scope', 'parents']:
        if not evidence.get(field):
            errors.append(error('EVIDENCE_STALE', 'Evidence lacks actual file/method/scope/parent.', field=field))
    try:
        if file_ref(project, evidence['path'])['sha256'] != evidence.get('sha256'):
            errors.append(error('EVIDENCE_STALE', 'Evidence bytes changed.'))
    except (OSError, ValueError, KeyError):
        errors.append(error('EVIDENCE_STALE', 'Evidence file missing or outside course.'))
    parents = evidence.get('parents', {})
    if not isinstance(parents, dict) or not parents or any(current.get(k) != v for k,v in parents.items()):
        errors.append(error('EVIDENCE_STALE', 'Evidence does not bind the current parent artifacts.'))
    method=str(evidence.get('method','')).lower()
    if any(k in method for k in ['encoded','continuous-av','thumbnail','audio-listening']) and 'video_sha256'not in parents:
        errors.append(error('EVIDENCE_STALE','Encoded-media observations must bind current video bytes.'))
    if 'asr'in method and 'audio_sha256'not in parents:
        errors.append(error('EVIDENCE_STALE','Source ASR evidence must bind current actual audio bytes.'))
    if evidence.get('status') not in {'verified', 'unverified', 'blocked'}:
        errors.append(error('EVIDENCE_STALE', 'Evidence status must disclose its actual verification state.'))
    if evidence.get('status') != 'verified':
        errors.append(error('CONTRACT_NOT_READY', 'Applicable evidence remains unverified.'))
    return errors


def invalidate_dependents(contract, changed_refs):
    """Return a new master value; preserve previous evidence and unrelated checks."""
    value = copy.deepcopy(contract)
    affected = []
    for row in value.get('obligations', []):
        refs = row.get('evidence_refs', [])
        if any(isinstance(r, dict) and set(r.get('parents', {})) & set(changed_refs) for r in refs):
            row.setdefault('changes', []).append(dict(reason='input dependency changed', changed_refs=list(changed_refs),
                previous_status=row.get('status'), previous_evidence=copy.deepcopy(refs)))
            row['status'] = 'implemented_unverified' if row.get('implementation_refs') else 'not_started'
            for ref in refs:
                if isinstance(ref, dict) and set(ref.get('parents', {})) & set(changed_refs):
                    ref['status'] = 'unverified'
                    ref['invalidated_by'] = list(changed_refs)
            affected.append(row['id'])
    for key,requirement in value.get('requirements',{}).items():
        if not isinstance(requirement,dict):continue
        review=requirement.get('review',{})
        if isinstance(review,dict) and (set(review.get('parents',{}))|set(review)) & set(changed_refs):
            requirement.setdefault('review_history',[]).append(copy.deepcopy(review))
            review['status']='unverified'
            review['invalidated_by']=list(changed_refs)
            affected.append('requirements.'+key)
    return value, affected


def inspect(project, context):
    p = Path(project)
    contract = read(p / 'production-contract.json')
    current = {}
    for role, key in [('document_sha256','current_document'),('video_sha256','current_video')]:
        if context.get(key):
            current[role] = file_ref(p,context[key])['sha256']
    doc_path=Path(context['current_document'])
    doc=read(doc_path if doc_path.is_absolute() else p/doc_path)
    for role,key in [('audio_sha256','audio'),('narration_sha256','narration')]:
        if doc.get('media',{}).get(key):
            current[role]=file_ref(p,doc['media'][key])['sha256']
    for role,raw in context.get('input_refs',{}).items():
        actual=file_ref(p,raw,allow_implementation=role=='render_implementation_sha256')['sha256']
        if role in current and current[role]!=actual:
            raise ValueError('Explicit input cannot override the current document dependency')
        current[role]=actual
    errors = []
    from execution_requirements import applicable
    for row in contract.get('obligations', []):
        if not applicable(row,context['purpose']) or row.get('status') == 'not_applicable':
            continue
        for evidence in row.get('evidence_refs', []):
            errors.extend(validate_evidence(p,evidence,current))
    return dict(ready=not errors, errors=errors, current_parents=current)
