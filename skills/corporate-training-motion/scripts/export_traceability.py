#!/usr/bin/env python3
"""Produce CSV audit map from rule -> script -> storyboard. Stdlib only."""
from pathlib import Path
import argparse
import csv
import json

ap=argparse.ArgumentParser(description='输出制度条款→文稿→分镜对照表')
ap.add_argument('project',type=Path)
ap.add_argument('--out',type=Path,default=None)
args=ap.parse_args()
path=args.project.resolve()
rules=json.loads((path/'source_rules.json').read_text(encoding='utf8'))
script=json.loads((path/'script_segments.json').read_text(encoding='utf8'))
shots=json.loads((path/'storyboard.json').read_text(encoding='utf8'))
output=args.out or path/'qa/source-traceability.csv'
output.parent.mkdir(parents=True,exist_ok=True)
with output.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f)
    w.writerow(['规则ID','原文条款','来源页码','强制性/建议性','范围','例外','审阅状态','问题编号','讲稿ID','镜头ID','摘要','原文摘录'])
    for r in rules:
        rid=r['id']
        w.writerow([rid,r.get('clause',''),r.get('page',''),r.get('modality',''),r.get('scope',''),
                    '；'.join(r.get('exceptions',[])),r.get('review_status',''),r.get('blocking_issue',''),
                    '、'.join(s['id'] for s in script if rid in s.get('rule_ids',[])),
                    '、'.join(s['id'] for s in shots if rid in s.get('rule_ids',[])),
                    r.get('summary',''),r.get('exact_excerpt','')])
print(f'制度条款溯源文件：{output}')
