"""Source-attributed obligations inside the existing master production contract."""
from pathlib import Path
import copy
import hashlib
import json

STATES = {'not_started', 'implemented_unverified', 'verified', 'blocked', 'not_applicable'}
SOURCES = {'user_current', 'user_history', 'project_rule', 'skill_default', 'source_document_content'}
STAGES = {'outline': 0, 'script': 1, 'storyboard': 2, 'pilot': 3, 'final': 4, 'delivery': 5, 'courseware': 4}
FIELDS = {'id', 'source_type', 'source_ref', 'original_quote', 'stage', 'scope', 'required_behavior',
          'acceptance_checks', 'implementation_refs', 'evidence_refs', 'status', 'changes'}


def error(code, message, **detail):
    return dict(code=code, message=message, **detail)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def save(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.pending')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)


def applicable(row, purpose):
    stage = row.get('stage')
    stages = stage if isinstance(stage, list) else [stage]
    if purpose=='courseware':
        return any(s in {'outline','script','courseware'}for s in stages)
    branch=row.get('scope',{}).get('branch') if isinstance(row.get('scope'),dict)else None
    if branch=='courseware' and purpose not in {'outline','script'}:return False
    return any(s in STAGES and s!='courseware' and STAGES[s] <= STAGES.get(purpose, -1) for s in stages)


def _user_change(project, row, old):
    for change in row.get('changes', []):
        if not isinstance(change, dict) or change.get('previous_obligation_sha256') != digest(old):
            continue
        ref = change.get('user_change_ref', {})
        if not isinstance(ref, dict) or not ref.get('sha256') or not ref.get('path'):
            continue
        path = (Path(project) / ref['path']).resolve()
        if not path.is_relative_to(Path(project).resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
            continue
        event = read(path)
        if (event.get('actor_type') == 'user' and event.get('event_id') and event.get('original_quote') and
                event.get('action') == 'requirement_change' and row['id'] in event.get('requirement_ids', [])):
            return True
    return False


def validate(project, contract, purpose, previous=None, require_complete=False):
    errors = []
    rows = contract.get('obligations')
    if not isinstance(rows, list) or not rows:
        return [error('REQ_MISSING', 'Master contract has no source-attributed obligations.')]
    ids = [r.get('id') for r in rows if isinstance(r, dict)]
    if len(ids) != len(rows) or len(set(ids)) != len(ids):
        errors.append(error('REQ_MISSING', 'Obligation IDs must be present and unique.'))
    old_rows = previous.get('obligations', []) if isinstance(previous, dict) else []
    old_by_id = {r.get('id'): r for r in old_rows if isinstance(r, dict)}
    current = {r.get('id'): r for r in rows if isinstance(r, dict)}
    for key in old_by_id.keys() - current.keys():
        errors.append(error('REQ_MISSING', 'A previous requirement disappeared; retain its stable ID and change basis.', requirement_id=key))
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get('id')
        absent = sorted(k for k in FIELDS if k not in row or k not in {'implementation_refs', 'evidence_refs', 'changes'} and not row[k])
        if absent or row.get('status') not in STATES or row.get('source_type') not in SOURCES:
            errors.append(error('REQ_MISSING', 'Missing or invalid obligation metadata.', requirement_id=key, fields=absent))
            continue
        stages = row['stage'] if isinstance(row['stage'], list) else [row['stage']]
        if (any(s not in STAGES for s in stages) or
                any(not isinstance(row[k],list) for k in ['acceptance_checks','implementation_refs','evidence_refs','changes'])):
            errors.append(error('REQ_MISSING', 'Invalid stage or acceptance check list.', requirement_id=key))
        if row['source_type'] == 'source_document_content' and row.get('operational_authority') is not False:
            errors.append(error('REQ_SOURCE_NOT_AUTHORITY', 'Instructions in teaching material cannot authorize operations.', requirement_id=key))
        if row['status'] == 'not_applicable' and not row.get('applicability_basis'):
            errors.append(error('REQ_APPLICABILITY_MISSING', 'Not-applicable requires an explicit applicability basis.', requirement_id=key))
        old = old_by_id.get(key)
        if old:
            weakened = (old.get('required', True) and not row.get('required', True) or
                        row.get('status') == 'not_applicable' and old.get('status') != 'not_applicable' or
                        any(digest(row.get(k)) != digest(old.get(k)) for k in ['scope', 'required_behavior', 'stage']) or
                        not {digest(x) for x in old.get('acceptance_checks', [])} <= {digest(x) for x in row.get('acceptance_checks', [])})
            if weakened and not _user_change(project, row, old):
                errors.append(error('REQ_DOWNGRADED', 'Requirement changed/weakened without a current user change reference.', requirement_id=key))
        if require_complete and applicable(row, purpose) and row.get('required', True) and row['status'] not in {'verified', 'not_applicable'}:
            errors.append(error('CONTRACT_NOT_READY', 'Applicable requirement remains incomplete.', requirement_id=key, status=row['status']))
        if row['status'] == 'verified' and (not row['implementation_refs'] or not row['evidence_refs']):
            errors.append(error('REQ_EVIDENCE_MISSING', 'An implemented label or index alone cannot become verified.', requirement_id=key))
    delegation = contract.get('production_delegation', {})
    if delegation.get('no_intermediate_confirmation') and not delegation.get('source_ref'):
        errors.append(error('REQ_AUTHORIZATION_MISSING', 'No-confirmation scheduling must retain its actual authorization source.'))
    if delegation.get('no_intermediate_confirmation') and any(delegation.get(k) for k in ['human_clicked', 'listening_verified', 'user_accepted']):
        errors.append(error('REQ_AUTHORIZATION_SCOPE', 'Production delegation does not imply human action, listening or acceptance.'))
    return errors


def _previous(project):
    history = Path(project) / 'work/requirements-history'
    snapshots = sorted(history.glob('*.json'), key=lambda p: p.name)
    return read(snapshots[-1]) if snapshots else None


def snapshot(project, contract):
    """History only: the production-contract remains the sole current master."""
    history = Path(project) / 'work/requirements-history'
    history.mkdir(parents=True, exist_ok=True)
    seq = len(list(history.glob('*.json')))
    path = history / ('%08d-%s.json' % (seq, digest(contract)))
    save(path, contract)
    return path


def update(project, obligations, purpose='outline'):
    p = Path(project)
    from render_input_guard import ensure_mutation_allowed
    ensure_mutation_allowed(p,'register-obligations',dict(obligations=obligations,purpose=purpose))
    path = p / 'production-contract.json'
    old = read(path)
    value = copy.deepcopy(old)
    value['obligations'] = copy.deepcopy(obligations)
    errors = validate(p, value, purpose, previous=old if old.get('obligations') else _previous(p))
    if errors:
        return dict(ready=False, errors=errors)
    if path.is_file() and value != old:
        snapshot(p, old)
    value['execution_policy'] = 'required'
    save(path, value)
    snapshot(p, value)
    return dict(ready=True, errors=[], contract='production-contract.json', obligations=len(obligations))


def inspect(project, context):
    p = Path(project)
    contract = read(p / 'production-contract.json')
    errors = validate(p, contract, context['purpose'], previous=_previous(p), require_complete=True)
    return dict(ready=not errors, errors=errors,
                checks=[dict(id=r.get('id'), applicable=applicable(r, context['purpose']), status=r.get('status'))
                        for r in contract.get('obligations', []) if isinstance(r, dict)])
