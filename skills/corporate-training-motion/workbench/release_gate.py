"""One fail-closed release decision for all entrypoints. Receipts are evidence, not authority."""
from pathlib import Path
import hashlib
import importlib
import json
import shutil
import uuid

VERSION = 'execution-release-gate/1'
MEDIA = {'pilot', 'final', 'delivery'}
PURPOSES = {'outline', 'script', 'storyboard', 'pilot', 'final', 'delivery', 'courseware'}
REQUIRED = {'course_id', 'purpose', 'current_document', 'current_video', 'current_contract', 'current_review_refs'}
OPTIONAL = {'input_refs', 'delivery_files', 'entrypoint', 'expected_hashes'}


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _error(code, message, **detail):
    return dict(code=code, message=message, **detail)


def _path(project, raw, root=None):
    if not isinstance(raw, (str, Path)) or not str(raw):
        raise ValueError('Expected an explicit current file path')
    p = Path(raw)
    p = (p if p.is_absolute() else project / p).resolve()
    if not p.is_relative_to(root or project) or not p.is_file():
        raise ValueError('Current file missing or outside course: ' + str(p))
    return p


def _call(module, function, project, context, **kwargs):
    # Fixed imports only. A producer-supplied lambda or receipt cannot replace a checker.
    fn = getattr(importlib.import_module(module), function)
    return fn(project, context, **kwargs)


def build_context(project, purpose, current_document, current_video=None, *, course_id=None,
                  current_review_refs=None, entrypoint=''):
    """Collect declared canonical references; never invent/refresh a verification."""
    p=Path(project).resolve()
    master=p/'production-contract.json'
    contract=json.loads(master.read_text()) if master.is_file() else {}
    from execution_requirements import applicable
    declared=[]
    for row in contract.get('obligations',[]):
        if applicable(row,purpose):declared.extend(row.get('evidence_refs',[]))
    declared.extend(contract.get('stage_review_refs',{}).get(purpose,[]))
    if purpose in MEDIA:
        for requirement in contract.get('requirements',{}).values():
            review=requirement.get('review',{}) if isinstance(requirement,dict) else {}
            if isinstance(review,dict) and review.get('evidence'):
                declared.append(dict(path=review['evidence'],sha256=review.get('evidence_sha256')))
    if current_review_refs is not None:declared.extend(current_review_refs)
    refs={}
    for item in declared:
        if not isinstance(item,dict) or not item.get('path'):
            continue
        path=Path(item['path']);path=(path if path.is_absolute() else p/path).resolve()
        # A missing path is retained as a missing ref, never silently made ready.
        claimed=item.get('sha256')
        actual=_sha(path) if path.is_relative_to(p) and path.is_file() else None
        refs[(str(path),claimed)]=dict(path=str(path),sha256=claimed or actual)
    return dict(course_id=course_id or contract.get('course_id') or p.parent.name,purpose=purpose,
                current_document=str(current_document),current_video=str(current_video) if current_video is not None else None,
                current_contract=str(master),current_review_refs=list(refs.values()),entrypoint=entrypoint)


def evaluate(project, context):
    """Read-only; explicit bytes, stage applicability, fixed checkers, no implicit approval."""
    p = Path(project).resolve()
    errors, checks, hashes, refs = [], {}, {}, []
    purpose = context.get('purpose') if isinstance(context, dict) else None
    result = dict(schema=VERSION, course_id=context.get('course_id') if isinstance(context, dict) else None,
                  purpose=purpose, allow_release=False, status='acceptance_blocked', errors=errors,
                  checks=checks, hashes=hashes, evidence_refs=refs, checker_executed=False,
                  host_permission_isolation='not-implemented-by-software-gate', user_acceptance=False)
    def data_only(v):
        return v is None or type(v) in (str,int,float,bool) or isinstance(v,Path) or isinstance(v,list) and all(data_only(x) for x in v) or isinstance(v,dict) and all(type(k)is str and data_only(x) for k,x in v.items())
    if not isinstance(context, dict) or not data_only(context) or REQUIRED - context.keys() or context.keys() - REQUIRED - OPTIONAL:
        errors.append(_error('GATE_CONTEXT_INVALID', 'Explicit data-only release context required; overrides/receipts are not authorization.'))
        return result
    if purpose not in PURPOSES or not isinstance(context['course_id'], str) or not context['course_id'].strip():
        errors.append(_error('GATE_CONTEXT_INVALID', 'Unknown stage or missing course identity.'))
        return result
    try:
        doc = _path(p, context['current_document'])
        contract = _path(p, context['current_contract'])
        if contract != (p / 'production-contract.json').resolve():
            raise ValueError('The canonical production-contract.json is the only master contract')
        value = json.loads(contract.read_text())
        if value.get('course_id') and value['course_id'] != context['course_id']:
            raise ValueError('Course identity differs from master contract')
        hashes.update(document_sha256=_sha(doc), contract_sha256=_sha(contract))
        video = _path(p, context['current_video'], p.parent) if context['current_video'] is not None else None
        if purpose in MEDIA and video is None:
            raise ValueError('Current encoded candidate is required at this stage')
        if video:
            hashes['video_sha256'] = _sha(video)
        expected = context.get('expected_hashes', {})
        if not isinstance(expected, dict) or any(hashes.get(k) != v for k, v in expected.items()):
            errors.append(_error('RELEASE_INPUT_CHANGED', 'Current bytes differ from requested release inputs.'))
        review_refs = context['current_review_refs']
        if not isinstance(review_refs, list) or not review_refs:
            errors.append(_error('EVIDENCE_STALE', 'Current stage review references are required.'))
        else:
            for item in review_refs:
                if not isinstance(item, dict):
                    raise ValueError('Review references require path and sha256')
                path = _path(p, item.get('path'))
                if not item.get('sha256') or _sha(path) != item['sha256']:
                    errors.append(_error('EVIDENCE_STALE', 'Review bytes missing or changed.', path=str(path)))
                refs.append(dict(path=str(path), sha256=_sha(path)))
        # Requirements and handoffs are stage-aware, and read the canonical contract.
        checks['requirements'] = _call('execution_requirements', 'inspect', p, context)
        checks['handoffs'] = _call('handoff_contract', 'inspect', p, context)
        checks['evidence'] = _call('evidence_versions', 'inspect', p, context)
        if purpose in MEDIA:
            base = importlib.import_module('production_contract')
            checks['contract'] = base.inspect(p, document=doc, video=video,
                                               purpose='final' if purpose == 'delivery' else purpose)
            prefs = importlib.import_module('production_preferences')
            pref_errors = prefs.review_errors(p, 'final' if purpose == 'delivery' else purpose,
                                               video, document=doc)
            checks['preferences'] = dict(ready=not pref_errors, errors=[_error('CONTRACT_NOT_READY', x) for x in pref_errors])
        # Content/media extension and final-media checker are fixed application modules.
        checks['production_validation'] = _call('production_validation', 'inspect_extra', p, context)
        checks['final_media'] = _call('final_media_checks', 'inspect', p, context)
        result['checker_executed'] = True
        for key, check in checks.items():
            if (not isinstance(check, dict) or type(check.get('ready')) is not bool or check['ready'] is not True or
                    not isinstance(check.get('errors'),list)):
                errors.append(_error('CONTRACT_NOT_READY', 'Required checker did not return ready.', check=key))
            if isinstance(check, dict):
                for e in check.get('errors', []):
                    errors.append(e if isinstance(e, dict) else _error('CONTRACT_NOT_READY', str(e), check=key))
                if check.get('critical_unknown'):
                    errors.append(_error('CONTRACT_NOT_READY', 'Critical unverified scope remains.', check=key,
                                         unknown=check['critical_unknown']))
        if _sha(doc) != hashes['document_sha256'] or _sha(contract) != hashes['contract_sha256'] or video and _sha(video) != hashes['video_sha256']:
            errors.append(_error('RELEASE_INPUT_CHANGED', 'Release inputs changed while checking.'))
    except Exception as exc:
        errors.append(_error('GATE_NOT_EXECUTED', type(exc).__name__ + ': ' + str(exc)))
    result['allow_release'] = not errors and result['checker_executed']
    result['status'] = 'allowed_for_formal_delivery' if result['allow_release'] else 'acceptance_blocked'
    result['checker_sha256'] = _sha(Path(__file__))
    result['checker_versions']={name:dict(path=str(module.__file__),sha256=_sha(module.__file__))
        for name in ['production_contract','production_preferences','production_validation','final_media_checks','execution_requirements','handoff_contract','evidence_versions','ordered_reveals','intro_pacing','semantic_alignment','media_frames']
        if (module:=__import__('sys').modules.get(name)) is not None and getattr(module,'__file__',None) and Path(module.__file__).is_file()}
    return result


class ReleaseBlocked(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__('CONTRACT_NOT_READY: ' + '; '.join(e['message'] for e in result['errors']))


def require_release(project, context):
    result = evaluate(project, context)
    if result['allow_release'] is not True:
        raise ReleaseBlocked(result)
    return result


def deliver(project, context, files):
    """Copy only after an actual fresh decision; verify every source and staged target."""
    if not isinstance(files, list) or not files:
        raise ValueError('Delivery requires explicit source/destination/sha256 entries')
    if context.get('purpose')=='delivery' and not {'video','subtitles','cover'}<={('subtitles' if f.get('role')=='srt' else f.get('role')) for f in files}:
        raise ReleaseBlocked(dict(allow_release=False,errors=[_error('RELEASE_INPUT_CHANGED','Formal course delivery requires video/subtitles/cover roles.')]))
    declared=context.get('delivery_files',[])
    if declared!=files:
        raise ReleaseBlocked(dict(allow_release=False,errors=[_error('RELEASE_INPUT_CHANGED','Delivery set differs from the checked context.')]))
    prepared = []
    for f in files:
        src = _path(Path(project).resolve(), f.get('source'), Path(project).resolve().parent)
        dst = Path(f.get('destination', '')).expanduser().resolve()
        formal_root=(Path.home()/'Desktop/ai 制课').resolve()
        if dst.is_relative_to(formal_root) and context.get('purpose')!='delivery':
            raise ReleaseBlocked(dict(allow_release=False,errors=[_error('RELEASE_PURPOSE_MISMATCH','Formal course directory requires the full delivery purpose and checks.')]))
        if not f.get('sha256') or _sha(src) != f['sha256'] or not f.get('role'):
            raise ReleaseBlocked(dict(allow_release=False, errors=[_error('RELEASE_INPUT_CHANGED', 'Unbound delivery file.')]))
        prepared.append((src, dst, f))
    if len({str(dst) for _, dst, _ in prepared}) != len(prepared):
        raise ValueError('Delivery destinations must be unique')
    expected_source=context.get('current_video') if context.get('purpose') in MEDIA else context.get('current_document')
    expected_path=_path(Path(project).resolve(),expected_source,Path(project).resolve().parent)
    if not any(src==expected_path for src,_,_ in prepared):
        raise ReleaseBlocked(dict(allow_release=False,errors=[_error('RELEASE_INPUT_CHANGED','Checked current artifact is absent from delivery set.')]))
    gate = require_release(project, context)
    receipt_path=Path(project)/'qa/release-gate'/('copy-'+uuid.uuid4().hex+'.json')
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt=dict(schema='course-release-copy/1',status='copy_in_progress',files=[],gate=gate,user_acceptance=False,
                 permission_isolation_verified=False,formally_delivered=False)
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    staged, outputs = [], []
    try:
        for src, dst, f in prepared:
            if _sha(src) != f['sha256']:
                raise ReleaseBlocked(dict(allow_release=False, errors=[_error('RELEASE_INPUT_CHANGED', 'Source changed before copy.')]))
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name('.' + dst.name + '.candidate-' + uuid.uuid4().hex)
            shutil.copyfile(src, tmp)
            staged.append(tmp)
            if _sha(src) != f['sha256'] or _sha(tmp) != f['sha256']:
                raise ReleaseBlocked(dict(allow_release=False, errors=[_error('RELEASE_INPUT_CHANGED', 'Copy SHA mismatch; no completion recorded.')]))
        # A previous formal file is retained in engineering history, not deleted.
        for (src, dst, f), tmp in zip(prepared, staged):
            for role,key in [('document_sha256','current_document'),('contract_sha256','current_contract'),('video_sha256','current_video')]:
                if key in context and context[key] is not None:
                    bound=_path(Path(project).resolve(),context[key],Path(project).resolve().parent)
                    if _sha(bound)!=gate['hashes'][role]:
                        raise ReleaseBlocked(dict(allow_release=False,errors=[_error('RELEASE_INPUT_CHANGED','Checked inputs changed before promoting delivery.')]))
            if dst.exists():
                old = Path(project) / 'work/delivery-history' / (_sha(dst) + '-' + dst.name)
                old.parent.mkdir(parents=True, exist_ok=True)
                if not old.exists():
                    shutil.copyfile(dst, old)
            tmp.replace(dst)
            if _sha(dst) != f['sha256']:
                raise ReleaseBlocked(dict(allow_release=False, errors=[_error('RELEASE_INPUT_CHANGED', 'Formal target SHA mismatch.')]))
            outputs.append(dict(role=f['role'], source=str(src), destination=str(dst),path=str(dst),sha256=f['sha256'],
                                source_sha256_before=f['sha256'],source_sha256_after=_sha(src),destination_sha256=_sha(dst)))
        if context.get('purpose')=='delivery':
            from delivery_visibility import verify_finder_files,prepare_visible
            parents={str(dst.parent)for _,dst,_ in prepared}
            if len(parents)!=1:raise ValueError('Formal course files must share one course folder')
            receipt['visibility_preparation']=prepare_visible(Path(next(iter(parents))),outputs)
            visibility=verify_finder_files(Path(next(iter(parents))),outputs)
            receipt['visibility']=visibility
            if not isinstance(visibility,dict) or visibility.get('status')!='verified' or not visibility.get('method'):
                raise ReleaseBlocked(dict(allow_release=False,errors=[_error('DELIVERY_VISIBILITY_UNVERIFIED','Actual Finder file readback did not verify all current files.')]))
    except Exception as exc:
        # Failed candidates/staged bytes remain available for diagnosis; never mark delivered.
        receipt.update(status='acceptance_blocked',files=outputs,error=str(exc))
        receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        raise
    formal=context.get('purpose')=='delivery'
    receipt.update(status='formally_delivered'if formal else 'stage_artifact_copied',files=outputs,formally_delivered=formal)
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return dict(receipt,receipt_path=str(receipt_path))
