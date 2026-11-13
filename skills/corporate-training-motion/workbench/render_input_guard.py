"""Freeze actual render dependencies and queue editor changes without applying them."""
from pathlib import Path
from contextlib import contextmanager
import fcntl
import functools
import json
import os
import threading
import uuid
from evidence_versions import freeze_inputs,check_frozen

def atomic(*args,**kwargs):
    from workflow import atomic as write
    return write(*args,**kwargs)
def read(*args,**kwargs):
    from workflow import read as load
    return load(*args,**kwargs)
def now():
    from workflow import now as clock
    return clock()
_local=threading.local()

@contextmanager
def _locked(project):
    identity=str(Path(project).resolve());held=getattr(_local,'held',set())
    if identity in held:
        yield;return
    path=Path(project)/'work/render-input.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as file:
        fcntl.flock(file,fcntl.LOCK_EX)
        _local.held=held|{identity}
        try:yield
        finally:
            _local.held=held;fcntl.flock(file,fcntl.LOCK_UN)

def active(project):
    rows=[]
    for path in (Path(project)/'work/render-locks').glob('*.json'):
        value=read(path,{})
        if value.get('status')!='running':continue
        try:os.kill(int(value['owner_pid']),0)
        except (OSError,ValueError,KeyError):continue
        rows.append(value)
    return rows

def ensure_mutation_allowed(project,operation,payload=None):
    rows=active(project)
    if not rows:return
    target=Path(project)/'work/pending-input-changes'/(uuid.uuid4().hex+'.json')
    atomic(target,dict(schema='queued-input-change/1',at=now(),operation=operation,payload=payload,
                       renders=[r['render_id'] for r in rows],applied=False))
    raise ValueError('INPUT_CHANGED_DURING_RENDER: modification queued; current render inputs retained: '+str(target))

def guarded_mutation(function):
    @functools.wraps(function)
    def wrapped(self,*args,**kwargs):
        with _locked(self.project):
            ensure_mutation_allowed(self.project,function.__qualname__,dict(args=args,kwargs=kwargs))
            return function(self,*args,**kwargs)
    return wrapped

def freeze_render(project,render_id,document,extra_inputs=None):
    p=Path(project).resolve();doc=read(document,{})
    inputs={'document':str(document),'render_implementation':[]}
    plan=read(p/'design-plan.json',{})
    # All executable renderer dependencies are part of this render's identity.
    code=Path(__file__).resolve().parent
    inputs['render_implementation']=[str(f) for f in code.rglob('*') if f.is_file() and f.suffix in {'.py','.js','.html','.css'} and '__pycache__' not in f.parts]
    for role,name in [('contract','production-contract.json'),('preferences','production-preferences.json'),('storyboard','storyboard.json'),('design_plan','design-plan.json'),('script',plan.get('script_file') or 'source/transcript.md')]:
        if (p/name).is_file():inputs[role]=str(p/name)
    media=[]
    for raw in doc.get('media',{}).values():
        if isinstance(raw,str) and (p/raw).is_file():media.append(str(p/raw))
    for item in doc.get('assets',[]):
        for key in ['path','originalPath']:
            raw=item.get(key)
            if isinstance(raw,str) and (p/raw).is_file():media.append(str(p/raw))
    if media:inputs['media']=sorted(set(media))
    native=[str(f) for f in (p/'native').rglob('*') if f.is_file() and f.suffix in {'.js','.json','.css','.html'}]
    if native:inputs['native_source']=native
    if extra_inputs:
        if not isinstance(extra_inputs,dict) or set(extra_inputs)&set(inputs):raise ValueError('Explicit extra render inputs cannot replace fixed dependencies')
        inputs.update(extra_inputs)
    with _locked(p):
        frozen=freeze_inputs(p,inputs,render_id)
        atomic(p/'work/render-locks'/(render_id+'.json'),dict(schema='active-render-inputs/1',render_id=render_id,
               owner_pid=os.getpid(),at=now(),status='running',frozen=frozen))
    return frozen

def check_render(project,frozen):
    value=check_frozen(project,frozen)
    if not value['ready']:raise ValueError('INPUT_CHANGED_DURING_RENDER: '+json.dumps(value['errors'],ensure_ascii=False))
    return value

def end_render(project,render_id,status):
    path=Path(project)/'work/render-locks'/(render_id+'.json')
    with _locked(project):
        value=read(path,{})
        if value:
            value.update(status=status,ended_at=now(),files_retained=True);atomic(path,value)
