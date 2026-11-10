"""Capture actual imported checker code at service startup, separate from disk version."""
from pathlib import Path
import hashlib
import importlib
import inspect
import json
import types

MODULES=('workflow','backend','production','release_gate','execution_requirements','handoff_contract',
         'evidence_versions','production_contract','production_preferences','production_validation',
         'final_media_checks','review_preflight','blind_review','ai_review','render_input_guard')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _code(code):
    def constant(value):
        if isinstance(value,types.CodeType):return _code(value)
        if isinstance(value,tuple):return [constant(v) for v in value]
        if isinstance(value,frozenset):return sorted(repr(v) for v in value)
        return repr(value)
    return dict(bytecode=code.co_code.hex(),constants=[constant(v)for v in code.co_consts],names=code.co_names,
                vars=code.co_varnames,free=code.co_freevars,cell=code.co_cellvars,flags=code.co_flags,
                args=code.co_argcount,kwonly=code.co_kwonlyargcount,posonly=code.co_posonlyargcount,firstline=code.co_firstlineno)

def capture():
    rows=[]
    for name in MODULES:
        module=importlib.import_module(name);path=Path(module.__file__).resolve()
        compiled=compile(path.read_bytes(),str(path),'exec',dont_inherit=True)
        source_codes={}
        def collect(code):
            source_codes[code.co_qualname]=_code(code)
            for child in code.co_consts:
                if isinstance(child,types.CodeType):collect(child)
        collect(compiled)
        functions=[]
        for value in vars(module).values():
            if inspect.isfunction(value) and value.__module__==name:functions.append(inspect.unwrap(value))
            elif inspect.isclass(value) and value.__module__==name:
                for item in vars(value).values():
                    if isinstance(item,(staticmethod,classmethod)):item=item.__func__
                    if inspect.isfunction(item):functions.append(inspect.unwrap(item))
        actual={f.__code__.co_qualname:_code(f.__code__) for f in functions if Path(f.__code__.co_filename).resolve()==path}
        matching=bool(actual) and all(source_codes.get(key)==code for key,code in actual.items())
        rows.append(dict(module=name,path=str(path),source_sha256=sha(path),loaded_function_count=len(actual),
                         loaded_functions_match_source=matching,
                         loaded_code_sha256=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest()))
    return dict(schema='loaded-execution-runtime/1',root=str(Path(__file__).resolve().parent),modules=rows,
                all_loaded_code_matches=all(r['loaded_functions_match_source'] for r in rows),
                scope='actual imported Python functions and source at startup; no model inference or media acceptance')
