#!/usr/bin/env python3
"""Export machine storyboard JSON as a reviewer-friendly markdown scene list."""
from pathlib import Path
import argparse,json
ap=argparse.ArgumentParser()
ap.add_argument('project',type=Path)
ap.add_argument('--out',type=Path,default=None)
a=ap.parse_args()
root=a.project.resolve()
board=json.loads((root/'storyboard.json').read_text(encoding='utf8'))
scripts={x['id']:x['text'] for x in json.loads((root/'script_segments.json').read_text(encoding='utf8'))}
lines=['# 动态商务信息图分镜表','','> 所有镜头时间为规划估算；以实际配音对齐后重算。','']
for s in board:
    lines+=['## '+s['id']+' · '+s['headline'],
            '- 场景：'+s['section']+'｜'+s['visual_type']+'｜预计 '+str(s['duration_sec'])+'s',
            '- 制度溯源：'+', '.join(s['rule_ids']),
            '- 口播：'+' / '.join(scripts.get(x,'[缺失]') for x in s['narration_ids']),
            '- 画面事实：'+'；'.join(f['text']+'（'+f['rule_id']+'）' for f in s['on_screen_facts']),
            '- 设计注意：'+s.get('layout_notes',''),
            '- 知识关系：'+s.get('knowledge_relation','历史计划未填写'),
            '- 观众要理解：'+s.get('learning_goal','未填写'),
            '- 图示发生的动作：'+s.get('visual_action','未填写'),
            '- 镜头与移动理由：'+s.get('camera_plan','未填写')+'；'+s.get('camera_reason','未填写'),
            '- 连续画布/焦点：'+s.get('canvas_id','未填写')+' / '+', '.join(s.get('focus_object_ids',[])),
            '- 局部展开：'+s.get('local_expansion','未填写'),
            '- 回到全局：'+s.get('return_to_global','未填写'),
            '',
            '| 相对秒 | 动作 | 对象 | 对应口播词 |','|---:|---|---|---|']
    for cue in s['animation_cues']:
        lines.append(f'| {cue["at_sec"]} | {cue["action"]} | {cue["target"]} | {cue.get("narration_anchor", "")} |')
    lines.append('')
out=a.out or root/'qa/storyboard-review.md'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text('\n'.join(lines)+'\n',encoding='utf8')
print(f'分镜审阅稿：{out}')
