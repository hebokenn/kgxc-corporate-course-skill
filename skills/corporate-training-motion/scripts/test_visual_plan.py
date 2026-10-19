#!/usr/bin/env python3
"""Behavioral regressions for missing pedagogy, slide-only plans and static-only evidence."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from check_visual_plan import check_scenes,check

def run():
    good=dict(id='B1',knowledge_relation='handoff',learning_goal='识别商务到运营的交接条件',visual_action='系统价格维护完成后，政策对象沿连接线交给运营',camera_reason='沿交接路径移动，让观众看见责任主体变化',canvas_id='map',camera_plan='商务节点平移到运营节点后停住',local_expansion='在商务节点旁展开两系统价格字段',return_to_global='沿原位置拉回五角色全图',visual_strategy='diagram',canvas_mode='continuous',focus_object_ids=['systems','ops'])
    assert not check_scenes([good])
    no_reason=copy.deepcopy(good);no_reason.pop('camera_reason')
    assert any('camera_reason' in e for e in check_scenes([no_reason]))
    slide=copy.deepcopy(good);slide['visual_strategy']='text_cards'
    assert any('DIRECTOR_TEXT_ONLY' in e for e in check_scenes([slide]))
    separate=copy.deepcopy(good);separate['canvas_mode']='separate'
    separate.pop('local_expansion');separate.pop('return_to_global')
    separate['visual_strategy']='object_action'
    assert not check_scenes([separate])
    separate['separate_scene_reason']='独立实物近景用于核对交接单据字段，之后沿同节点回图'
    assert not check_scenes([separate])
    selected_map=copy.deepcopy(separate);selected_map['map_mode']=True
    assert any('DIRECTOR_MAP_FIELD' in e for e in check_scenes([selected_map]))
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'storyboard.json').write_text(json.dumps([good]));(root/'qa').mkdir()
        skill=Path(__file__).resolve().parents[1]/'references/12-director-teaching.md'
        (root/'director_execution.json').write_text(json.dumps(dict(skill_path=str(skill),skill_sha256=hashlib.sha256(skill.read_bytes()).hexdigest(),read_resources=[str(skill)],steps=[dict(id='plan',status='done')])) )
        # A static image with correct hash cannot stand in for the required moving sample.
        still=root/'qa/frame.png';still.write_bytes(b'static fixture')
        item=dict(path='qa/frame.png',sha256=hashlib.sha256(still.read_bytes()).hexdigest())
        (root/'qa/visual-evidence.json').write_text(json.dumps(dict(keyframes=[item],dynamic_sample={},review={})))
        assert not check(root)
        errs=check(root,True);assert any('DIRECTOR_PATH' in e for e in errs);assert any('DIRECTOR_REVIEW' in e for e in errs)
    print('PASS: standalone handoff action needs no map/return fields; selected map requires its fields; missing camera reason and static-only evidence are rejected')

if __name__=='__main__':run()
