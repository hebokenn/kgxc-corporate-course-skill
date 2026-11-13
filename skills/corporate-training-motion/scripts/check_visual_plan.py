#!/usr/bin/env python3
"""Check director-plan contracts and evidence bindings, never certify visual quality."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

RELATIONS={'process','hierarchy','handoff','condition','comparison','field_linkage','definition','recap'}
STRATEGIES={'diagram','demonstration','object_action','comparison','source_diagram'}
REVIEW_ITEMS={'spatial_continuity','diagram_expression','reading_time','occlusion'}

def check_scenes(scenes):
    errors=[]
    if not isinstance(scenes,list) or not scenes:
        return ['DIRECTOR_PLAN: 分镜必须为非空数组']
    for index,scene in enumerate(scenes):
        if not isinstance(scene,dict):
            errors.append(f'DIRECTOR_SCENE: 第{index}段不是对象');continue
        sid=scene.get('id',str(index))
        for key in ('learning_goal','visual_action','camera_reason','canvas_id','camera_plan'):
            value=scene.get(key)
            if not isinstance(value,str) or not value.strip():errors.append(f'DIRECTOR_FIELD: {sid} 缺少{key}')
        if scene.get('knowledge_relation') not in RELATIONS:errors.append(f'DIRECTOR_RELATION: {sid} 未判断知识关系')
        if scene.get('visual_strategy') not in STRATEGIES:errors.append(f'DIRECTOR_TEXT_ONLY: {sid} 必须用图示或教学动作，不能只有标题/文字卡片')
        if scene.get('canvas_mode') not in {'continuous','separate'}:errors.append(f'DIRECTOR_CANVAS: {sid} 未确定连续画布或独立场景')
        if not (scene.get('visual_choice_reason','').strip() or scene.get('separate_scene_reason','').strip() or scene.get('camera_reason','').strip()):
            errors.append(f'DIRECTOR_CHOICE: {sid} 未说明画面选择理由')
        if scene.get('map_mode') is True:
            for key in ('local_expansion','return_to_global'):
                if not isinstance(scene.get(key),str) or not scene[key].strip():
                    errors.append(f'DIRECTOR_MAP_FIELD: {sid} 地图分镜缺少{key}')
        ids=scene.get('focus_object_ids')
        if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x.strip() for x in ids):errors.append(f'DIRECTOR_FOCUS: {sid} 缺少稳定焦点对象ID')
    return errors

def check(folder,require_evidence=False):
    folder=Path(folder).resolve();errors=[]
    boundary=folder.parent if folder.name=='project' and (folder.parent/'workspace.json').exists() else folder
    def load(name):
        try:return json.loads((folder/name).read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:errors.append(f'DIRECTOR_FILE: {name}: {exc}');return None
    scenes=load('storyboard.json')
    if scenes is not None:errors.extend(check_scenes(scenes))
    execution=load('director_execution.json')
    if isinstance(execution,dict):
        path=Path(execution.get('skill_path','')).expanduser()
        if not path.is_absolute():path=(folder/path).resolve()
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=execution.get('skill_sha256'):
            errors.append('DIRECTOR_SKILL: 缺少实际导演方法文件或SHA256不符')
        elif not ((path.name=='SKILL.md' and path.parent.name in {'corporate-training-motion','code-video-director'}) or path.name in {'12-director-teaching.md','24-visual-and-motion.md'}):
            errors.append('DIRECTOR_SKILL: 未指向实际采用的导演Skill或包内导演方法')
        if not execution.get('read_resources') or not execution.get('steps'):
            errors.append('DIRECTOR_EXECUTION: 缺少适用参考阅读记录或实际执行步骤')
    elif execution is not None:errors.append('DIRECTOR_EXECUTION: 执行记录必须为对象')
    if not require_evidence:return errors
    evidence=load('qa/visual-evidence.json')
    if not isinstance(evidence,dict):return errors+['DIRECTOR_EVIDENCE: 缺少视觉证据对象']
    def artifact(item):
        if not isinstance(item,dict):errors.append('DIRECTOR_ARTIFACT: 证据项必须为对象');return None
        name=item.get('path','');path=(folder/name).resolve()
        if not name or Path(name).is_absolute() or not path.is_relative_to(boundary):
            errors.append('DIRECTOR_PATH: 证据路径越界或为空');return None
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get('sha256'):
            errors.append(f'DIRECTOR_HASH: 证据不存在或已变化 {name}');return None
        return path
    keys=evidence.get('keyframes')
    if not isinstance(keys,list) or not keys:errors.append('DIRECTOR_KEYFRAMES: 缺少实际关键帧')
    else:
        for key in keys:artifact(key)
    dynamic=artifact(evidence.get('dynamic_sample'))
    if dynamic:
        try:
            result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_type,width,height,duration','-of','json',str(dynamic)],capture_output=True,text=True,check=True)
            streams=json.loads(result.stdout).get('streams',[])
            if not streams or streams[0].get('codec_type')!='video':raise ValueError('无视频流')
        except (OSError,ValueError,subprocess.CalledProcessError) as exc:errors.append(f'DIRECTOR_DYNAMIC: 动态证据不是可探测视频: {exc}')
    reviews=evidence.get('review',{})
    for key in sorted(REVIEW_ITEMS):
        item=reviews.get(key,{}) if isinstance(reviews,dict) else {}
        if item.get('status')!='pass' or not item.get('method') or not item.get('range'):
            errors.append(f'DIRECTOR_REVIEW: {key} 尚无范围和方法完整的动态复核记录')
    return errors

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('project',type=Path);parser.add_argument('--require-evidence',action='store_true');args=parser.parse_args()
    findings=check(args.project,args.require_evidence)
    print(json.dumps({'ok':not findings,'scope':'director contract and evidence bindings only','visual_quality':'not machine-certified','errors':findings},ensure_ascii=False,indent=2))
    raise SystemExit(bool(findings))
