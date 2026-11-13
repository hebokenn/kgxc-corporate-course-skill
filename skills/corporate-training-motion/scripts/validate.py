#!/usr/bin/env python3
"""Rule-backed training plan validator. Pure Python stdlib, no network.

This checks structural facts and known risky mismatches. It does NOT substitute
for a line-by-line human comparison with the source material.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import subprocess
import shutil
import unicodedata
from media_check import check as check_media
from review_gate import check as check_approval
from check_visual_plan import check as check_visual_plan
from check_course_completeness import check as check_course_completeness
from check_workbench import required as requires_workbench
from pathlib import Path

STAGES = ['analyze', 'script', 'storyboard', 'preview', 'final']
VISUAL_TYPES = {'ChapterIntro','ClockTimeline','ShiftGantt','ProcessFlow',
                'ResponsibilityMatrix','WeeklyCalendar','DecisionTree',
                'MetricCard','Checklist','SourceHighlight'}
MODALITIES = {'mandatory','recommended','conditional','descriptive'}
STATUSES = {'verified','pending'}

class Report:
    def __init__(self): self.errors=[]; self.warnings=[]
    def error(self, code, message): self.errors.append(f'{code}: {message}')
    def warn(self, code, message): self.warnings.append(f'{code}: {message}')

def load(path: Path, report: Report, required=True):
    if not path.exists():
        if required: report.error('MISSING_FILE', str(path))
        return None
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        report.error('BAD_JSON', f'{path}: {exc}')
        return None

def check_ids(items, kind, report):
    ids=[]
    if not isinstance(items,list):
        report.error('WRONG_TYPE', f'{kind}必须是JSON数组')
        return {}
    mapping={}
    for k,item in enumerate(items):
        if not isinstance(item,dict):
            report.error('WRONG_ITEM',f'{kind}[{k}]不是对象')
            continue
        rid=item.get('id')
        if not isinstance(rid,str) or not rid.strip():
            report.error('MISSING_ID', f'{kind}[{k}]缺少id')
        elif rid in ids:
            report.error('DUPLICATE_ID',f'{kind}重复ID {rid}')
        else:
            ids.append(rid)
            mapping[rid]=item
    return mapping

def all_rules_have_status(rules, stage, report):
    for rid,rule in rules.items():
        for key in ('clause','page','exact_excerpt','summary','modality','scope',
                    'importance','review_status','teaching_status'):
            if rule.get(key) in (None, ''):
                report.error('RULE_FIELD',f'{rid}: 缺少{key}')
        if rule.get('modality') not in MODALITIES:
            report.error('BAD_MODALITY',f'{rid}: 未识别 {rule.get("modality")}')
        if rule.get('review_status') not in STATUSES:
            report.error('BAD_REVIEW_STATUS',f'{rid}: review_status必须verified/pending')
        if not isinstance(rule.get('page'),int) or rule.get('page',0)<1:
            report.error('BAD_PAGE',f'{rid}: 页码不是正整数')
        if not isinstance(rule.get('exceptions',[]),list):
            report.error('EXCEPTIONS_TYPE',f'{rid}: exceptions必须为数组')
        if rule.get('review_status')=='pending':
            if not rule.get('blocking_issue'):
                report.error('PENDING_WITHOUT_ISSUE',f'{rid}: 待确认规则没有Q编号')
            else: report.warn('OPEN_ISSUE',f'{rid}: {rule["blocking_issue"]} 未确认')
        if rule.get('teaching_status')=='excluded' and not rule.get('exclusion_reason'):
            report.error('EXCLUDED_UNJUSTIFIED',f'{rid}: 排除的规则没有人工理由')

def check_refs(owner_id,kind,ids,allowed,report):
    if not isinstance(ids,list):
        report.error('REF_LIST',f'{kind} {owner_id}: rule_ids/narration_ids 必须数组')
        return
    for i in ids:
        if i not in allowed: report.error('BROKEN_REF',f'{kind} {owner_id} 引用不存在的ID: {i}')

def check_scene(scene, rid, rule_map, segment_map, report):
    dur=scene.get('duration_sec')
    if not isinstance(dur,(int,float)) or dur<=0:
        report.error('SCENE_DURATION',f'{rid} 缺少正数duration_sec')
        dur=0
    if scene.get('visual_type') not in VISUAL_TYPES:
        report.error('VISUAL_TYPE',f'{rid}: 无效 visual_type {scene.get("visual_type")}')
    rules=scene.get('rule_ids',[])
    narrs=scene.get('narration_ids',[])
    check_refs(rid,'分镜规则',rules,rule_map,report)
    check_refs(rid,'分镜文稿',narrs,segment_map,report)
    for n in narrs:
        if n in segment_map:
            unused=set(segment_map[n].get('rule_ids',[]))-set(rules)
            if unused:report.warn('SCRIPT_SCENE_GAP',f'{rid} 引用文稿 {n}，但镜头未关联 {sorted(unused)}')
    facts=scene.get('on_screen_facts',[])
    if not isinstance(facts,list):
        report.error('FACT_LIST',f'{rid}: on_screen_facts 不是数组')
    else:
        for f in facts:
            if not isinstance(f,dict):
                report.error('FACT_TYPE',f'{rid}: 事实必须为对象')
                continue
            fr=f.get('rule_id')
            if fr not in rule_map:
                report.error('FACT_SOURCE',f'{rid}: 无效事实来源 {fr}')
            elif fr not in rules:
                report.error('FACT_NOT_IN_SCENE',f'{rid}: 事实{f.get("text")}未关联到场景规则 {fr}')
            if not f.get('text'):
                report.error('FACT_EMPTY',f'{rid}: 屏幕事实不能为空')
            elif fr in rule_map:
                # A structural numerical check: numerals shown on screen must have a
                # source numeral in the attached rule. This catches e.g. 28 -> 29.
                # It cannot prove business accuracy; humans still review semantics.
                norm=lambda s:unicodedata.normalize('NFKC',s or '')
                visible=set(re.findall(r'\d+(?:\.\d+)?',norm(f['text'])))
                evidence=set(re.findall(r'\d+(?:\.\d+)?',norm(rule_map[fr].get('exact_excerpt',''))))
                unseen=visible-evidence
                if unseen:
                    report.error('UNSOURCED_NUMERAL',f'{rid}: {f["text"]!r} 中数字 {sorted(unseen)} 未出现在 {fr} 原文，请核对换算前提')
    cues=scene.get('animation_cues',[])
    if not isinstance(cues,list):
        report.error('CUE_LIST',f'{rid}: animation_cues 不是数组')
    else:
        old=-1
        for cue in cues:
            if not isinstance(cue,dict):
                report.error('BAD_CUE',f'{rid}: cue不是对象')
                continue
            t=cue.get('at_sec')
            if not isinstance(t,(int,float)) or t<0 or t>dur:
                report.error('CUE_TIME',f'{rid}: cue时间超出时长 ({t}/{dur})')
            elif t<old: report.error('CUE_ORDER',f'{rid}: cue时间乱序')
            elif t>=0: old=t
            if not cue.get('target') or not cue.get('action'):
                report.error('CUE_FIELDS',f'{rid}: cue缺少target/action')
            if not cue.get('narration_anchor'):
                report.warn('CUE_ANCHOR',f'{rid}: cue尚未绑定明确的口播锚点')

def validate(folder: Path, stage: str, require_approved=False):
    report=Report()
    separated=folder.name=='project' and (folder.parent/'workspace.json').is_file()
    boundary=folder.parent.resolve() if separated else folder.resolve()
    delivery=folder.parent/'delivery' if separated else folder/'output'
    voice=folder/'audio' if separated else folder/'voice'
    project=load(folder/'project.json',report)
    if (folder/'course-state.json').is_file():
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
        from workflow import Course
        from check_design import check as check_design
        course=Course(folder);status=course.status()
        if not status['source_files'] or any(x['sha256'] is None for x in status['source_files'].values()):
            report.error('SOURCE_INFO','需要存在的原始素材及来源登记')
        if stage!='analyze':
            for error in check_design(status['plan'],folder)['errors']:report.error('TEACHING_DESIGN',error)
            required=({'script':'outline','storyboard':'script','preview':'style','final':'final'}.get(stage,'outline') if course.modern() else {'script':'outline','storyboard':'content','preview':'visual','final':'pilot'}.get(stage,'source'))
            if course.modern() and status.get('branch')=='courseware' and stage=='final':required='courseware'
            try:
                if course.modern() and stage in ('preview','final') and status.get('branch')!='courseware':course.require_video(required)
                else:course.require(required)
            except ValueError as exc:report.error('WORKFLOW_CONFIRMATION',str(exc))
        if stage in ('preview','final') and not (course.modern() and status.get('branch')=='courseware'):
            from check_workbench import check as check_editable
            for error in check_editable(folder,require_runtime=True)['errors']:report.error('WORKBENCH_CONTRACT',error)
        return report
    rules_arr=load(folder/'source_rules.json',report)
    if project is None or rules_arr is None:return report
    if not isinstance(project,dict):
        report.error('PROJECT_TYPE','project.json必须为对象')
        return report
    if stage in ('preview','final') and requires_workbench(project):
        from check_workbench import check as check_editable
        for error in check_editable(folder,require_runtime=True)['errors']:
            report.error('WORKBENCH_CONTRACT',error)
    if not project.get('source_file') or not project.get('source_version'):
        report.error('SOURCE_INFO','project.json缺少source_file/source_version')
    if (project.get('width'),project.get('height'),project.get('fps'))!=(1920,1080,30):
        report.warn('NONSTANDARD_VIDEO','默认推荐1920×1080@30，如故意修改可忽略')
    approvals=project.get('approvals',{})
    if not isinstance(approvals,dict):approvals={}
    rule_map=check_ids(rules_arr,'规则',report)
    if not rule_map:report.error('NO_RULES','规则台账不能为空')
    all_rules_have_status(rule_map,stage,report)
    if not (folder/'open_questions.md').exists():
        report.error('NO_QUESTIONS','缺少open_questions.md')
    if stage=='analyze':return report
    segs=load(folder/'script_segments.json',report)
    if segs is None:return report
    segment_map=check_ids(segs,'逐字稿',report)
    if not segment_map:report.error('NO_SCRIPT','逐字稿不能为空')
    referenced=set()
    for sid,seg in segment_map.items():
        if not seg.get('text'):
            report.error('EMPTY_SCRIPT',f'{sid}: 口播为空')
        refs=seg.get('rule_ids',[])
        check_refs(sid,'逐字稿',refs,rule_map,report)
        referenced.update(i for i in refs if i in rule_map)
        if not refs and seg.get('tag') not in {'intro','recap'}:
            report.error('SCRIPT_NO_EVIDENCE',f'{sid}: 事实段没有对应条款')
    scope=project.get('deliverable','full')
    selected=project.get('pilot_rule_ids',[]) if scope=='pilot' else [k for k,r in rule_map.items() if r.get('importance')=='critical']
    if scope=='pilot' and not selected:report.error('PILOT_SCOPE','试播未定义pilot_rule_ids')
    for rid in selected:
        if rid not in rule_map:
            report.error('PILOT_RULE_UNKNOWN',f'pilot_rule_ids中不存在{rid}')
        elif rid not in referenced and rule_map[rid].get('teaching_status')!='excluded':
            report.error('RULE_NOT_COVERED',f'{rid}: 教学范围内关键规则未进入逐字稿')
    if project.get('content_contract_version',0)>=1:
        for error in check_course_completeness(folder,stage='script' if stage=='script' else 'storyboard'):
            report.error('COURSE_COMPLETENESS',error)
    if stage=='script':return report
    boards=load(folder/'storyboard.json',report)
    if boards is None:return report
    scene_map=check_ids(boards,'分镜',report)
    if not scene_map:report.error('NO_STORYBOARD','分镜不能为空')
    visual_refs=set()
    narration_refs=set()
    for bid,sc in scene_map.items():
        check_scene(sc,bid,rule_map,segment_map,report)
        visual_refs.update(sc.get('rule_ids',[]))
        narration_refs.update(sc.get('narration_ids',[]))
    for sid in segment_map:
        if sid not in narration_refs:
            report.error('SCRIPT_NOT_ON_SCREEN',f'文稿段{sid}没有对应镜头')
    for rid in selected:
        if rid in rule_map and rid not in visual_refs and rule_map[rid].get('teaching_status')!='excluded':
            report.error('RULE_NOT_VISUALIZED',f'关键规则{rid}没有对应分镜')
    if project.get('visual_plan_version',0)>=2:
        for error in check_visual_plan(folder,require_evidence=stage in ('preview','final')):
            report.error('DIRECTOR_CONTRACT',error)
    else:
        report.warn('LEGACY_DIRECTOR_PLAN','历史计划未迁移导演分镜契约2；新建或重做视觉必须设置visual_plan_version=2，结构通过不表示视觉合格')
    # Stage approval flags are only gates for PRODUCTION, not for drafting/previewing a plan.
    if stage in ('preview','final') and not approvals.get('content'):
        report.error('GATE_CONTENT','未确认逐字稿/规则台账，不允许渲染')
    if stage in ('preview','final') and not approvals.get('visual'):
        report.error('GATE_VISUAL','未确认视觉规范，不允许渲染')
    if stage in ('preview','final'):
        for error in check_approval(folder, 'pilot' if stage=='preview' else 'release'):
            report.error('GATE_RECORD', error)
        affected=[rid for rid in referenced if rule_map[rid].get('review_status')=='pending']
        if affected:
            report.error('GATE_SELECTED_PENDING','本次口播含未确认规则: '+','.join(sorted(affected)))
        artifacts=project.get('render_artifacts',{})
        selected=artifacts.get(stage) if isinstance(artifacts,dict) else None
        if selected:
            selected_path=(folder/selected).resolve()
            if Path(selected).is_absolute() or not selected_path.is_relative_to(boundary):
                report.error('MEDIA_PATH','render_artifacts必须为课程内相对路径')
                videos=[]
            else: videos=[selected_path]
        else:
            videos=sorted((delivery if separated else folder/('previews' if stage=='preview' else 'output')).glob('*.mp4'))
            if len(videos)>1:
                report.error('MEDIA_SELECTION','多个MP4候选，请在render_artifacts中指定本次文件')
                videos=[]
        if not videos:
            report.error('MISSING_VIDEO','未指定唯一可检查的MP4')
        else:
            require_audio=stage=='final' or project.get('preview_mode','narrated')!='visual_only'
            for error in check_media(videos[0],project.get('width',1920),project.get('height',1080),project.get('fps',30),require_audio):
                report.error('MEDIA',error)
            if requires_workbench(project):
                from check_workbench import check as check_editable
                for error in check_editable(folder,require_runtime=True,video=videos[0])['errors']:
                    report.error('WORKBENCH_EXPORT',error)
        if not (folder/'qa'/'review.md').exists():
            report.error('NO_QA_REVIEW','缺少 qa/review.md 人工审片记录')
    if stage=='final':
        if scope!='full':report.error('GATE_SCOPE','试播项目不能作为完整课程交付')
        if not approvals.get('pilot'):report.error('GATE_PILOT','样片未经确认')
        if not approvals.get('final'):report.error('GATE_FINAL','成片未经正式批准')
        pending=[k for k,v in rule_map.items() if v.get('review_status')=='pending']
        if pending:report.error('GATE_PENDING','正式交付时仍有未确认源规则: '+','.join(pending))
        if not list(delivery.glob('*.srt')):
            report.error('MISSING_SUBTITLES','正式交付必须含 SRT 字幕')
        if not list(voice.rglob('*.wav')) and not list(voice.rglob('*.mp3')):
            report.error('MISSING_VOICE','正式交付须有已授权口播音轨备查')
    return report

def main(argv=None):
    ap=argparse.ArgumentParser(description='培训工程阶段检查（并不能替代人工事实核对）')
    ap.add_argument('folder',type=Path)
    ap.add_argument('--stage',choices=STAGES,default='analyze')
    ap.add_argument('--json',action='store_true',help='以机器可读JSON输出')
    args=ap.parse_args(argv)
    r=validate(args.folder,args.stage)
    if args.json:
        print(json.dumps({'stage':args.stage,'ok':not r.errors,'scope':'source coverage, structure and declared evidence only','director_visual_quality':'not assessed by this validator','encoded_film_quality':'not certified by structure checks','errors':r.errors,'warnings':r.warnings},ensure_ascii=False,indent=2))
    else:
        print(f'[{args.stage}] {"PASS" if not r.errors else "FAIL"} / 错误 {len(r.errors)} / 提醒 {len(r.warnings)}')
        for s in r.errors:print('  ERROR ',s)
        for s in r.warnings:print('  NOTICE',s)
    return 1 if r.errors else 0
if __name__=='__main__':sys.exit(main())
