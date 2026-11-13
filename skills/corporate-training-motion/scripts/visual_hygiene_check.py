#!/usr/bin/env python3
"""Check the current candidate's per-scene visual hygiene review."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from visual_hygiene import review

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path)
    p.add_argument('--video',required=True,type=Path);p.add_argument('--out',type=Path);args=p.parse_args()
    doc=json.loads((args.project/'workbench.json').read_text());result=review(args.project,doc,args.video)
    if args.out:args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(result['status']=='pending')
