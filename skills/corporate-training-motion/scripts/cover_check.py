#!/usr/bin/env python3
"""Verify this candidate's cover and actual poster/first-frame evidence."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from cover_quality import review

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('project',type=Path);p.add_argument('--video',type=Path,required=True);p.add_argument('--out',type=Path)
    a=p.parse_args();doc=json.loads((a.project/'workbench.json').read_text())
    doc.setdefault('qualityPolicy',{})['coverRequired']=True
    result=review(a.project,doc,a.video)
    if a.out:a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(result['status']!='pass')
