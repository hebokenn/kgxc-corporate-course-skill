#!/usr/bin/env python3
"""Requirement dispatch and mandatory release checks for standard/custom/resumed work."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['requirements','dispatch','return','release-check','release-copy'])
    p.add_argument('--project',required=True,type=Path)
    p.add_argument('--input',required=True,type=Path,help='Actual JSON input, never an allow_release receipt')
    p.add_argument('--document',type=Path)
    a=p.parse_args(argv)
    try:
        value=json.loads(a.input.read_text())
        if a.action=='requirements':
            from execution_requirements import update
            result=update(a.project,value['obligations'],purpose=value.get('purpose','outline'))
        elif a.action=='dispatch':
            from handoff_contract import create
            result=create(a.project,value)
        elif a.action=='return':
            if not a.document:raise ValueError('Current --document is required')
            from handoff_contract import submit
            result=submit(a.project,value,json.loads(a.document.read_text()))
        elif a.action=='release-check':
            from release_gate import evaluate
            result=evaluate(a.project,value)
        else:
            from release_gate import deliver
            result=deliver(a.project,value,value.get('delivery_files',[]))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('ready') is True or result.get('allow_release') is True or result.get('status') in {'formally_delivered','stage_artifact_copied'} else 2
    except Exception as error:
        result=getattr(error,'result',None) or dict(ready=False,allow_release=False,errors=[dict(code=str(error).split(':',1)[0],message=str(error))])
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2

if __name__=='__main__':raise SystemExit(main())
