"""Requirement → task → actual files/objects → evidence, with immutable history."""
from pathlib import Path
import copy
import hashlib
import json
import re
import shutil
from execution_requirements import error, read, save, applicable, digest
from evidence_versions import file_ref

TASK_FIELDS = {'task_id', 'requirement_ids', 'inputs', 'owned_scope', 'forbidden_scope', 'quotes',
               'actual_objects', 'choices', 'return_files', 'required_checks', 'purpose', 'issue_ids'}
RESULT_FIELDS = {'task_id', 'requirement_ids', 'output_paths', 'object_bindings', 'checks_run',
                 'evidence_refs', 'unresolved_items', 'issue_ids'}


def _task_path(project, task_id, suffix=''):
    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',task_id):
        raise ValueError('Stable safe task_id required')
    return Path(project)/'work/handoffs'/(task_id+suffix+'.json')


def _nodes(document):
    nodes, ancestors = {}, {}
    def visit(items, parents):
        for n in items:
            if not n.get('id') or n['id'] in nodes:
                raise ValueError('Missing/duplicate scene node identity')
            nodes[n['id']] = n
            ancestors[n['id']] = parents
            visit(n.get('children',[]),parents+[n])
    visit(document.get('sceneGraph',{}).get('nodes',[]),[])
    return nodes, ancestors


def _owned_return(project,task,path):
    path=Path(path).resolve();p=Path(project)
    owned=any(path==q or path.is_relative_to(q)for q in [(p/x).resolve()for x in task.get('owned_scope',[])])
    forbidden=any(path==q or path.is_relative_to(q)for q in [(p/x).resolve()for x in task.get('forbidden_scope',[])])
    return owned and not forbidden and path in {(p/x).resolve()for x in task.get('return_files',[])}


def _master_dependency_equal(before,current):
    # Only execution bookkeeping may grow automatically. Source, acceptance,
    # scope, choices and physical plans remain protected input dependencies.
    def normalized(value):
        value=copy.deepcopy(value)
        for row in value.get('obligations',[]):
            for key in ['status','implementation_refs','evidence_refs','changes']:
                row.pop(key,None)
        for requirement in value.get('requirements',{}).values():
            if isinstance(requirement,dict):
                requirement.pop('review',None)
                requirement.pop('review_history',None)
        return value
    return normalized(before)==normalized(current)


def implementation_changed_fields(before,after,prefix=''):
    """Exact changed paths for fixed implementation tools, never a caller allowlist."""
    if isinstance(before,dict)and isinstance(after,dict):
        result=[]
        for key in sorted(set(before)|set(after)):
            path=(prefix+'.'if prefix else '')+key
            if key not in before or key not in after:result.append(path)
            else:result.extend(implementation_changed_fields(before[key],after[key],path))
        return result
    return []if before==after else[prefix]


def _event_ids(plan):
    events=plan.get('events',[])if isinstance(plan,dict)else []
    ids=[x.get('id')for x in events if isinstance(x,dict)]
    if len(ids)!=len(events)or any(not isinstance(x,str)or not x for x in ids)or len(ids)!=len(set(ids)):
        raise ValueError('Invalid event identities in actual plan')
    return set(ids)


def _snapshot(project,ref):
    path=file_ref(project,ref['path'])
    if path['sha256']!=ref.get('sha256'):raise ValueError('Implementation snapshot changed')
    return read(path['path']),path['sha256']


def _sound_delta_allowed(before,after):
    allowed={'assets','events','plan_path','receipt','calibration','review','status','plan_file_sha256','plan_sha256'}
    a=copy.deepcopy(before);b=copy.deepcopy(after)
    for value in [a,b]:
        sfx=value.get('requirements',{}).get('sfx',{})
        for key in allowed:sfx.pop(key,None)
    if not _master_dependency_equal(a,b):return False
    target=after.get('requirements',{}).get('sfx',{})
    return (after.get('choices',{}).get('sound_effects')=='native' and
            target.get('palette')=='teaching-native-v1' and target.get('status')in {'implemented_unverified','blocked'} and
            target.get('review',{}).get('status')!='verified')


def _fixed_sound_implementation(project,task,before,current,before_sha):
    """Only a dispatched native-sound tool chain may augment its exact bindings."""
    if 'native_sfx'not in task.get('implementation_outputs',[]):return False
    rows={r['id']:r for r in before.get('obligations',[])}
    def sound_scope(row):
        scope=row.get('scope',{})
        return isinstance(scope,dict)and (scope.get('feature')=='sfx'or'sfx'in scope.get('features',[]))
    if not any(sound_scope(rows.get(k,{}))for k in task.get('requirement_ids',[])):return False
    baseline=task.get('implementation_baseline',{}).get('native_sfx')
    if not isinstance(baseline,dict):return False
    p=Path(project);folder=p/'work/implementation-bindings'/task['task_id'];receipts=[]
    sound=Path(__file__).resolve().with_name('sound.py');sound_sha=hashlib.sha256(sound.read_bytes()).hexdigest()
    try:
        for path in folder.rglob('*.json'):
            receipt=read(path)
            if receipt.get('schema')!='course-implementation-binding/1':continue
            source=receipt.get('tool_source',{})
            if (receipt.get('kind')!='native_sfx'or receipt.get('task_id')!=task['task_id']or
                    receipt.get('tool')not in {'sound.make_plan','sound.mix'}or receipt.get('status')!='implemented_unverified'or
                    Path(source.get('path','')).resolve()!=sound or source.get('sha256')!=sound_sha):return False
            old,old_sha=_snapshot(p,receipt['before_master']);new,new_sha=_snapshot(p,receipt['after_master'])
            plan,plan_sha=_snapshot(p,receipt['after_plan'])
            if set(receipt.get('changed_fields',[]))!=set(implementation_changed_fields(old,new))or not _sound_delta_allowed(old,new):return False
            target=new['requirements']['sfx']
            if target.get('plan_file_sha256')!=plan_sha or target.get('plan_sha256')!=digest(plan):return False
            if receipt.get('before_plan'):
                previous_plan,_=_snapshot(p,receipt['before_plan'])
                if _event_ids(previous_plan)!=set(receipt.get('old_event_ids',[])):return False
            for output in receipt.get('outputs',[]):
                actual=file_ref(p,output['path'])
                if Path(actual['path'])==(p/'production-contract.json').resolve()or actual['sha256']!=output.get('sha256'):return False
            if not receipt.get('outputs'):return False
            receipts.append((receipt,old,old_sha,new,new_sha,plan,plan_sha))
        cursor=before_sha;old_ids=set(baseline.get('event_ids',[]));seen=set()
        while cursor not in seen:
            seen.add(cursor);links=[r for r in receipts if r[2]==cursor]
            if len(links)!=1:return False
            receipt,old,_,new,new_sha,plan,plan_sha=links[0]
            if set(receipt.get('old_event_ids',[]))!=old_ids or not old_ids<=_event_ids(plan):return False
            if _master_dependency_equal(new,current):
                current_plan=current.get('requirements',{}).get('sfx',{}).get('plan_path')
                return isinstance(current_plan,str)and file_ref(p,current_plan)['sha256']==plan_sha
            cursor=new_sha;old_ids=_event_ids(plan)
    except (OSError,ValueError,KeyError,TypeError):return False
    return False


def validate_dispatch(project,task,restored=False):
    p=Path(project)
    contract=read(p/'production-contract.json')
    rows={r['id']:r for r in contract.get('obligations',[])}
    if not isinstance(task,dict):return [error('HANDOFF_INCOMPLETE','Actual dispatch is missing/invalid.')]
    absent=TASK_FIELDS-task.keys()
    if absent or not task.get('requirement_ids') or any(k not in rows for k in task['requirement_ids']):
        return [error('HANDOFF_INCOMPLETE','Task lacks requirements or mandatory dispatch fields.',fields=sorted(absent))]
    if any(not applicable(rows[k],task['purpose']) for k in task['requirement_ids']):
        return [error('HANDOFF_INCOMPLETE','Task references a future-stage obligation.')]
    if (not task['owned_scope'] or not task['return_files'] or not task['required_checks'] or
            not isinstance(task['quotes'],dict) or any(task['quotes'].get(k)!=rows[k]['original_quote'] for k in task['requirement_ids'])):
        return [error('HANDOFF_INCOMPLETE','Task must carry exact source quotes, checks and return paths.')]
    if contract.get('choices') and task.get('choices')!=contract['choices']:
        return [error('HANDOFF_CHOICE_CHANGED','Dispatch must carry the current complete choices.')]
    if task.get('implementation_outputs'):
        features=[rows[k].get('scope',{})for k in task['requirement_ids']]
        sound=any(isinstance(s,dict)and(s.get('feature')=='sfx'or'sfx'in s.get('features',[]))for s in features)
        if task['implementation_outputs']!=['native_sfx']or not sound or contract.get('choices',{}).get('sound_effects')!='native':
            return [error('HANDOFF_IMPLEMENTATION_UNDECLARED','Fixed sound bindings need an explicit native-sfx requirement and saved native choice.')]
    errors=[]
    snapshots={r.get('path'):r for r in task.get('input_snapshots',[])if isinstance(r,dict)}
    for ref in task.get('inputs',[]):
        try:
            current=file_ref(p,ref['path'])
            baseline=None
            if restored:
                snapshot=snapshots.get(str(Path(current['path'])))
                if not snapshot or snapshot.get('sha256')!=ref.get('sha256'):
                    raise ValueError('Frozen original input snapshot missing')
                baseline=file_ref(p,snapshot['snapshot_path'])
                if baseline['sha256']!=ref['sha256']:raise ValueError('Original input snapshot changed')
            if current['sha256']!=ref.get('sha256'):
                if restored and _owned_return(p,task,current['path']):
                    pass  # Before is immutable; result output SHA proves after.
                elif (restored and Path(current['path'])==(p/'production-contract.json').resolve() and
                        (_master_dependency_equal(read(baseline['path']),read(current['path']))or
                         _fixed_sound_implementation(p,task,read(baseline['path']),read(current['path']),baseline['sha256']))):
                    pass
                else:raise ValueError('Protected input changed')
        except (OSError,ValueError,KeyError):
            errors.append(error('HANDOFF_INPUT_CHANGED','Dispatch input missing or changed.'))
    if not task.get('inputs'):
        errors.append(error('HANDOFF_INCOMPLETE','Dispatch must bind actual input hashes.'))
    return errors


def create(project, task):
    p=Path(project)
    value=copy.deepcopy(task)
    path=_task_path(p,task['task_id'])
    if 'input_snapshots'in task or'implementation_baseline'in task:
        return dict(ready=False,errors=[error('HANDOFF_INCOMPLETE','Input snapshots are produced by the dispatcher, not supplied as authorization.')])
    if path.exists():
        old=read(path);declared=copy.deepcopy(old);declared.pop('input_snapshots',None);declared.pop('implementation_baseline',None)
        if declared!=value:return dict(ready=False,errors=[error('HANDOFF_ID_REUSED','Task identity cannot replace previous dispatch.')])
        errors=validate_dispatch(p,old,restored=True)
        return dict(ready=not errors,errors=errors,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    errors=validate_dispatch(p,task)
    if errors:return dict(ready=False,errors=errors)
    snapshots=[]
    for ref in value['inputs']:
        current=file_ref(p,ref['path']);snapshot=p/'work/handoffs/input-snapshots'/(current['sha256']+'.bin')
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if not snapshot.exists():shutil.copyfile(current['path'],snapshot)
        if file_ref(p,snapshot)['sha256']!=current['sha256']or file_ref(p,current['path'])['sha256']!=current['sha256']:
            return dict(ready=False,errors=[error('HANDOFF_INPUT_CHANGED','Input changed while freezing its actual before bytes.')])
        snapshots.append(dict(path=current['path'],sha256=current['sha256'],snapshot_path=str(snapshot.relative_to(p))))
    value['input_snapshots']=snapshots
    if value.get('implementation_outputs'):
        if value['implementation_outputs']!=['native_sfx']:
            return dict(ready=False,errors=[error('HANDOFF_IMPLEMENTATION_UNDECLARED','Only the fixed native_sfx implementation channel is supported.')])
        sfx=read(p/'production-contract.json').get('requirements',{}).get('sfx',{})
        plan=sfx.get('plan_path');baseline=dict(event_ids=sorted(_event_ids({'events':sfx.get('events',[])})),plan_existed=False)
        if isinstance(plan,str)and (p/plan).is_file():
            original=file_ref(p,plan);target=p/'work/handoffs/input-snapshots'/(original['sha256']+'.bin')
            if not target.exists():shutil.copyfile(original['path'],target)
            if file_ref(p,target)['sha256']!=original['sha256']:raise ValueError('Original implementation plan changed')
            baseline.update(event_ids=sorted(_event_ids(read(target))),plan_existed=True,plan_snapshot=dict(path=str(target.relative_to(p)),sha256=original['sha256']))
        value['implementation_baseline']={'native_sfx':baseline}
    save(path,value)
    return dict(ready=True,errors=[],path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def validate_result(project, task, result, document,require_dispatch_binding=False):
    errors=validate_dispatch(project,task,restored=require_dispatch_binding or bool(task.get('input_snapshots')))
    if require_dispatch_binding:
        try:
            path=_task_path(project,result.get('task_id'))
            if result.get('dispatch_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
                errors.append(error('HANDOFF_DISPATCH_CHANGED','Returned result does not bind the current original dispatch bytes.'))
        except (OSError,ValueError):errors.append(error('HANDOFF_DISPATCH_CHANGED','Original dispatch cannot be read.'))
    if RESULT_FIELDS-result.keys() or result.get('task_id')!=task.get('task_id') or set(result.get('requirement_ids',[]))!=set(task.get('requirement_ids',[])):
        errors.append(error('HANDOFF_RETURN_INCOMPLETE','Result must preserve dispatched task and requirement IDs.'))
    if set(result.get('issue_ids',[]))!=set(task.get('issue_ids',[])):
        errors.append(error('HANDOFF_ISSUE_LOST','A new task/result cannot erase a frozen repair issue.'))
    for ref in result.get('output_paths',[]):
        try:
            current=file_ref(project,ref['path'])
            if current['sha256']!=ref.get('sha256'):
                raise ValueError('Output changed')
            output=Path(current['path'])
            def in_scope(scope):
                return any(output==q or output.is_relative_to(q) for q in [(Path(project)/s).resolve()for s in scope])
            if not in_scope(task.get('owned_scope',[])) or in_scope(task.get('forbidden_scope',[])):
                errors.append(error('HANDOFF_SCOPE_VIOLATION','Returned output is outside task ownership or inside forbidden scope.',path=str(output)))
        except (OSError,ValueError,KeyError):
            errors.append(error('HANDOFF_OUTPUT_MISSING','Returned output missing/outdated.'))
    if not result.get('output_paths'):
        errors.append(error('HANDOFF_OUTPUT_MISSING','Completed task requires actual readable output.'))
    actual_paths={str((Path(project)/x.get('path','')).resolve()) for x in result.get('output_paths',[]) if isinstance(x,dict)}
    if {str((Path(project)/x).resolve()) for x in task.get('return_files',[])}-actual_paths:
        errors.append(error('HANDOFF_OUTPUT_MISSING','Not all dispatched outputs returned.'))
    checks=result.get('checks_run',[])
    evidence_paths={str((Path(project)/r['path']).resolve()) for r in result.get('evidence_refs',[]) if isinstance(r,dict) and r.get('path')}
    checked={r.get('id') for r in checks if isinstance(r,dict) and r.get('status')=='passed' and
        r.get('evidence_ref') and str((Path(project)/r['evidence_ref']).resolve()) in evidence_paths}
    if set(task.get('required_checks',[]))-checked:
        errors.append(error('HANDOFF_CHECK_MISSING','Required checks have no actual result/evidence.'))
    nodes,ancestors=_nodes(document)
    bindings=result.get('object_bindings',[])
    if task.get('actual_objects') and not bindings:
        errors.append(error('HANDOFF_BINDING_MISSING','Objects and contract events must be returned together.'))
    for binding in bindings:
        ids=binding.get('object_ids',[])
        span=binding.get('frame_range',[])
        if (not binding.get('event_id') or not binding.get('quote') or not ids or len(span)!=2 or
                any(type(f)is not int for f in span) or span[0]>=span[1]):
            errors.append(error('HANDOFF_BINDING_MISSING','Event needs actual object IDs, exact quote and frame range.'))
            continue
        for identifier in ids:
            n=nodes.get(identifier)
            if n is None:
                errors.append(error('HANDOFF_OBJECT_MISSING','Returned object does not exist.',object_id=identifier))
                continue
            chain=ancestors[identifier]+[n]
            types=binding.get('allowed_types',[])
            if types and n.get('type') not in types:
                errors.append(error('HANDOFF_OBJECT_INVALID','Returned object has wrong purpose/type.',object_id=identifier))
            for parent in chain:
                if (parent.get('startFrame',0)>span[0] or parent.get('endFrame',document.get('sourceDurationFrames',0))<span[1]
                        or parent.get('visible')is False or parent.get('opacity',1)==0):
                    errors.append(error('HANDOFF_OBJECT_INVALID','Object/ancestor hidden or too short for its claimed event.',object_id=identifier,ancestor_id=parent['id']))
    if not result.get('evidence_refs'):
        errors.append(error('HANDOFF_EVIDENCE_MISSING','Result lacks actual evidence references.'))
    for ref in result.get('evidence_refs',[]):
        try:
            if file_ref(project,ref['path'])['sha256']!=ref.get('sha256'):
                raise ValueError('Evidence changed')
        except (OSError,ValueError,KeyError):
            errors.append(error('HANDOFF_EVIDENCE_MISSING','Result evidence missing/outdated.'))
    return errors


def submit(project,result,document):
    p=Path(project)
    task=read(_task_path(p,result.get('task_id')))
    errors=validate_result(p,task,result,document)
    value=copy.deepcopy(result)
    dispatch_path=_task_path(p,result.get('task_id'))
    value['dispatch_sha256']=hashlib.sha256(dispatch_path.read_bytes()).hexdigest() if dispatch_path.is_file()else None
    value.update(status='returned_incomplete' if errors else 'blocked' if result.get('unresolved_items') else 'implemented_unverified',errors=errors)
    path=_task_path(p,result['task_id'],'-result')
    if path.exists():
        old=path.read_bytes()
        history=p/'work/handoffs/history'/(hashlib.sha256(old).hexdigest()+'.json')
        history.parent.mkdir(parents=True,exist_ok=True)
        if not history.exists():history.write_bytes(old)
        value['previous_result_ref']=dict(path=str(history.relative_to(p)),sha256=hashlib.sha256(old).hexdigest())
    save(path,value)
    if not errors:
        contract=read(p/'production-contract.json')
        result_ref=dict(task_id=result['task_id'],path=str(path.relative_to(p)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for row in contract.get('obligations',[]):
            if row['id'] in result['requirement_ids']:
                previous=[r for r in row.get('implementation_refs',[]) if r.get('task_id')==result['task_id']]
                if previous:
                    row.setdefault('changes',[]).append(dict(reason='same-task concentrated repair',issue_ids=result['issue_ids'],
                        previous_implementation_refs=previous,previous_result_ref=value.get('previous_result_ref')))
                row['implementation_refs']=[r for r in row.get('implementation_refs',[]) if r.get('task_id')!=result['task_id']]+[result_ref]
                row['status']='blocked' if result['unresolved_items'] else 'implemented_unverified'
        save(p/'production-contract.json',contract)
    pending=[error('HANDOFF_UNRESOLVED','Returned implementation retains unresolved items.',task_id=result['task_id'],items=result['unresolved_items'])]if result.get('unresolved_items')else []
    return dict(ready=not errors and not pending,status=value['status'],errors=errors+pending,path=str(path))


def inspect(project,context):
    p=Path(project)
    contract=read(p/'production-contract.json')
    errors=[]
    document=read(Path(context['current_document']) if Path(context['current_document']).is_absolute() else p/context['current_document'])
    for row in contract.get('obligations',[]):
        if not applicable(row,context['purpose']) or row.get('status')in {'not_applicable','blocked'}:
            continue
        refs=row.get('implementation_refs',[])
        if not refs:
            errors.append(error('HANDOFF_RETURN_INCOMPLETE','Applicable requirement has no returned implementation or explicit blocker.',requirement_id=row['id']))
        for ref in refs:
            if not isinstance(ref,dict) or not ref.get('task_id'):
                errors.append(error('HANDOFF_RETURN_INCOMPLETE','Implementation must reference a real task result.',requirement_id=row['id']))
                continue
            try:
                path=file_ref(p,ref['path'])
                if path['sha256']!=ref.get('sha256'):raise ValueError('Result changed')
                result=read(path['path'])
                task=read(_task_path(p,ref['task_id']))
                errors.extend(validate_result(p,task,result,document,require_dispatch_binding=True))
                if result.get('unresolved_items'):
                    errors.append(error('HANDOFF_UNRESOLVED','A new task/status cannot erase a previous unresolved implementation.',task_id=ref['task_id'],items=result['unresolved_items']))
            except (OSError,ValueError,KeyError,TypeError):
                errors.append(error('HANDOFF_RETURN_INCOMPLETE','Implementation result cannot be read/validated.',requirement_id=row['id']))
    return dict(ready=not errors,errors=errors)
