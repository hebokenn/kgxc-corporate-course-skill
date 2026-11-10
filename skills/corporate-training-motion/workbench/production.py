"""Shared production handoff and contract gate for every video entry point."""
import json
from pathlib import Path
from render_routes import plan,capabilities
from sound import PALETTE,ROLES

PORTABLE_CONTRACT_METADATA = (
    'assets/sfx/teaching-native-v1/palette.json',
    'assets/brand/logo.json',
    'assets/bookends/packaging-provenance.json',
)


def require_contract(project, video, purpose='final', document=None):
    """All official registrations re-run the fixed, current-byte release checker."""
    from release_gate import build_context, evaluate, ReleaseBlocked
    from workflow import atomic
    import uuid
    # This is a declared entrypoint default, never a suffix-based export guess.
    p=Path(project).resolve()
    context=build_context(p,purpose,document or p/'workbench.json',video,entrypoint='production.require_contract')
    result=evaluate(p,context)
    atomic(p/'qa/release-gate'/(uuid.uuid4().hex+'.json'),result)
    if result.get('allow_release') is not True:raise ReleaseBlocked(result)
    return dict(result,required=True,ready=True)


def stage_release(project,purpose,document,video=None,entrypoint='stage'):
    """Same checker for non-media stage transitions and custom/resume callers."""
    from release_gate import build_context, evaluate, ReleaseBlocked
    from workflow import atomic
    import uuid
    p=Path(project).resolve()
    result=evaluate(p,build_context(p,purpose,document,video,entrypoint=entrypoint))
    atomic(p/'qa/release-gate'/(uuid.uuid4().hex+'.json'),result)
    if result.get('allow_release') is not True:raise ReleaseBlocked(result)
    return result


def dispatch(project,task_id,purpose):
    """Persist the actual stage handoff before a controlled producer call."""
    from execution_requirements import applicable
    from evidence_versions import file_ref
    from handoff_contract import create
    from workflow import read
    p=Path(project).resolve();contract=read(p/'production-contract.json',{})
    existing=p/'work/handoffs'/(task_id+'.json')
    if existing.is_file():
        prior=read(existing)
        if prior.get('purpose')!=purpose:raise ValueError('HANDOFF_ID_REUSED: task stage changed')
        # The supervision operation performs persistent request/instruction CAS.
        # A completed return legitimately changed output/contract bytes; replay
        # reads the original frozen dispatch, and never re-signs current inputs.
        return dict(ok=True,task=prior,record=file_ref(p,existing),existing_dispatch=True,
                    return_command='kgxc-course return --project '+str(p)+' --input RESULT.json --document CURRENT.json')
    rows=[r for r in contract.get('obligations',[]) if applicable(r,purpose)]
    if not rows:raise ValueError('REQ_MISSING: register source-attributed obligations before dispatch')
    plan=read(p/'design-plan.json',{})
    names={'script':plan.get('script_file') or 'source/transcript.md','storyboard':'storyboard.json','pilot':'workbench.json','final':'workbench.json'}
    inputs=[file_ref(p,p/'production-contract.json')]
    for name in ['design-plan.json','production-preferences.json',plan.get('script_file'),'storyboard.json','workbench.json']:
        if name and (p/name).is_file():inputs.append(file_ref(p,p/name))
    task=dict(task_id=task_id,requirement_ids=[r['id'] for r in rows],inputs=inputs,
              owned_scope=[names[purpose]],forbidden_scope=['other courses','user confirmation','billing route','process deletion'],
              quotes={r['id']:r['original_quote'] for r in rows},actual_objects=contract.get('requirements',{}) if purpose in ['pilot','final'] else [],
              choices=contract.get('choices') or read(p/'production-preferences.json',{}).get('choices',{}),return_files=[names[purpose]],
              required_checks=sorted({c if isinstance(c,str) else c['id'] for r in rows for c in r['acceptance_checks']}),
              purpose=purpose,issue_ids=sorted({i for r in rows for i in r.get('issue_ids',[])}))
    if purpose in ['pilot','final'] and task['choices'].get('sound_effects')=='native':
        if not any(isinstance(r.get('scope'),dict) and (r['scope'].get('feature')=='sfx' or 'sfx' in r['scope'].get('features',[])) for r in rows):
            raise ValueError('REQ_MISSING: saved native-sfx choice needs its source-attributed current-stage obligation before dispatch')
        task['implementation_outputs']=['native_sfx']
    result=create(p,task)
    if not result['ready']:raise ValueError('HANDOFF_INCOMPLETE: '+json.dumps(result['errors'],ensure_ascii=False))
    return dict(ok=True,task=task,record=result,return_command='kgxc-course return --project '+str(p)+' --input RESULT.json --document CURRENT.json')


def require_dispatch_return(project,task_id):
    from handoff_contract import validate_result
    from workflow import read
    p=Path(project);task=read(p/'work/handoffs'/(task_id+'.json'),{})
    result=read(p/'work/handoffs'/(task_id+'-result.json'),{})
    errors=validate_result(p,task,result,read(p/'workbench.json',{}))
    if errors or result.get('unresolved_items') or result.get('status')!='implemented_unverified':
        raise ValueError('HANDOFF_RETURN_INCOMPLETE: '+json.dumps(errors,ensure_ascii=False))
    return result


def release_projection(project,state):
    from workflow import read,sha
    p=Path(project).resolve();decision=state.get('release_decisions',{}).get('final',{})
    names=state.get('candidate_artifacts',{}).get('final') or state.get('artifacts',{}).get('final',[])
    videos=[(p/n).resolve() for n in names if str(n).lower().endswith('.mp4')]
    current=bool(len(videos)==1 and videos[0].is_file() and decision.get('checker_executed') is True and decision.get('checker_sha256')==sha(Path(__file__).with_name('release_gate.py')))
    for role,path in [('document_sha256',p/'workbench.json'),('contract_sha256',p/'production-contract.json'),('video_sha256',videos[0] if videos else p/'missing')]:
        current=current and path.is_file() and decision.get('hashes',{}).get(role)==sha(path)
    if not videos:return dict(state='not_generated',candidate_generated=False,user_acceptance=False)
    ready=current and decision.get('allow_release') is True
    formal=next((r for r in reversed(state.get('formal_deliveries',[])) if all(Path(f['path']).is_file() and sha(Path(f['path']))==f['sha256'] for f in r.get('files',[])) and r.get('files')),None)
    formal_current=bool(formal and videos and any(f.get('sha256')==sha(videos[0]) for f in formal['files']))
    return dict(state='formally_delivered' if formal_current and ready else 'allowed_for_formal_delivery' if ready else 'acceptance_blocked',
                candidate_generated=True,current_evidence=current,errors=decision.get('errors',[]) if current else [dict(code='EVIDENCE_STALE',message='No current-byte release decision')],
                user_acceptance=None,user_acceptance_status='separately_recorded_in_current_review')


def handoff(project,status):
    p=Path(project);branch=status.get('branch');stage=status.get('stage')
    from production_contract import load as load_contract
    contract=load_contract(p)
    from production_preferences import load as load_preferences, choice_digest,storyboard_current
    preferences=load_preferences(p)
    preferences['choices_sha256']=choice_digest(p) if preferences['required'] else None
    preferences['storyboard_current']=storyboard_current(p)
    preferences['implementation_review']={
        'path':'qa/production-preferences-<pilot|final>-review.json',
        'required_fields':['choices_sha256','video_sha256','observations (customer, flower_text, sound_effects)','implemented (customer_ids, customer_nodes, flower_count, flower_nodes, sfx_count, sfx_palette; new_customer_profile when new)'],
        'policy':'先保存顾客/花字/音效选择；用save_storyboard保存结合当前选择的分镜；逐项检查实际编码画面和音轨后登记，不以启用配置代替真实接入。小样未覆盖的特征写deferred_features原因，整课启用项必须真实出现。新增顾客按33号参考完成后，把本课相对profile_path及design_approval{status:confirmed,actor,evidence}保存在production-preferences.json的new_customer内，不能用断手代替。'}
    from course_palette import read_plan
    palette=read_plan(p)
    active=stage!='complete' and (branch=='video' or branch is None and status.get('workflow_schema')!=2 and stage in ['visual','pilot','final'])
    if not active:return dict(active=False,production_preferences=preferences,production_contract=contract,reason='已完成，等待具体修改需求，不自动重制' if stage=='complete' else '沿用当前教学设计或课件阶段；此时不启动视频与混音')
    if status.get('planning_workflow')=='storyboard-v1' and stage=='storyboard':
        return dict(active=False,reason='先审阅全课内容演绎与分镜，逐片段至少三种表现；此时不生成完整配音或视频',
                    action='review-whole-course-storyboard',coverage=status.get('storyboard_report'),production_preferences=preferences,production_contract=contract)
    if status.get('planning_workflow')=='storyboard-v1' and stage=='pilot' and not status.get('sampling_valid'):
        return dict(active=False,reason='分镜已确认；先分层随机抽取三个片段再制作',action='sample-storyboard',production_preferences=preferences,production_contract=contract)
    def read(path):return json.loads(path.read_text()) if path.is_file() else {}
    doc=read(p/'workbench.json');spec_path=next((p/x for x in ['source/course-composition.json','source/composition.json','source/spec.json'] if (p/x).is_file()),None)
    spec=read(spec_path) if spec_path else doc
    director={} if status.get('planning_workflow')=='storyboard-v1' else read(p/'director-plan.json');requirements=director.get('rendering',{}).get('requiredEffects',[])
    if requirements:
        spec=json.loads(json.dumps(spec));rendering=spec.setdefault('rendering',{})
        rendering['requiredEffects']=sorted(set(rendering.get('requiredEffects',[])+requirements))
        if rendering.get('route')!='native-canvas':rendering['route']='auto'
    try:selection=plan(spec)
    except (ValueError,KeyError,TypeError,AttributeError) as e:selection=dict(ready=False,errors=[str(e)])
    current=doc.get('rendering',{}).get('route','scene-graph' if doc.get('adapter')=='scene-graph-v1' else 'native-canvas')
    action='configure' if doc.get('status')=='draft' else 'upgrade-renderer' if current=='scene-graph' and selection.get('route')=='motion-canvas' else 'continue-current-renderer'
    if not selection.get('ready'):action='resolve-specific-renderer-gap'
    if (status.get('director_review_status') or {}).get('status')=='pending' and status.get('artifacts',{}).get('final'):action='review-current-candidate'
    from workflow import export_job_projection
    projected_jobs=[export_job_projection(p,status,job) for job in status.get('jobs',[])]
    pending_candidates=[dict(id=job.get('id'),video=job.get('video'),srt=job.get('srt'),package=job.get('package'),
                            registration_status='held',contract_pending=job.get('contract_pending'))
                        for job in projected_jobs if job.get('status')=='complete' and
                        job.get('registration_status')=='held' and job.get('revision')==doc.get('revision') and
                        (job.get('contract_pending') or {}).get('purpose')==stage]
    if pending_candidates:action='verify-current-candidate'
    from direction_review import continuation
    return dict(active=True,automatic=True,storyboard_file='storyboard.json' if status.get('planning_workflow')=='storyboard-v1' else None,sampling=status.get('sampling') if status.get('sampling_valid') else None,current_route=current,route_audit=selection,direction=continuation(doc),
        production_preferences=preferences,production_contract=contract,pending_candidates=pending_candidates,
        candidate_policy='先核对已有当前编码候选，补齐同一版本的制作证据，再走checkpoint登记；候选完成不代表阶段或成品已登记，不因缺观察而反复渲染',
        palette_plan=palette,palette_policy='读取palette-plan.json；编译使用coursePalette；不按风格名称恢复灰绿，不重新抽色',
        composition_source=str(spec_path.relative_to(p)) if spec_path else 'workbench.json',action=action,
        timing=dict(prepare='course_tools.py prepare-narration --source RAW.wav --out PREPARED.wav --rate RATE [--start SOURCE_SECONDS --end SOURCE_SECONDS]',
                    map='audio_timing.NarrationClock(声音旁边的.wav.json).frame(原始配音词句秒数)',check='course_tools.py timing-check --spec COMPOSITION.json --project COURSE/project',
                    policy='先按原声裁切，再交付变速并实测时长；不在变速后用输出-t截短；越界先失败并修时轴，不能靠省略末句过检查'),
        available_effects=sorted(capabilities()['effects']),teaching_modules=capabilities()['teaching_modules'],motion_catalog_count=capabilities()['executable_motion_count'],
        motion_quality=__import__('motion_quality').preflight(doc),
        craft_quality=__import__('craft_quality').analyze(doc),reading_pacing=__import__('reading_pacing').inspect(doc),narration_continuity=__import__('continuity_pacing').inspect(doc),
        next_steps=['先读取42号按内容导演方法与41号人物演出：用当前逐字稿安排信息变化、焦点、人物意图/视线/反应、镜头理由和独立动作/读图时长；不导入示例课程模板。direction-check按实际动作、姿态、变换/标签边界给取证候选帧，实际复看后补峰值',
            '执行45号阅读与讲解节奏：文字稳定保留可与相关旁白重叠，动作结束不必换字；先精简正文、分组与保留结果，禁止自动插静音补阅读预算。6.0工程绑定同源时轴干声 media.narration 与 continuityPlan；reading-check、continuity-check及编码回执通过后仍按正常速度连续复看，不能把技术结果当听看或学员认可',
            '执行36号课程工艺规范：清楚与美观分别复核，声音自然、标准、干脆、连贯；查看实际画面并修正，不以数量和自评分当质量',
            '执行32号整课动效规范：真实模块、逐段旁白覆盖、编码主体与运行回执、绑定当前候选的逐段导演复核；不能简化后标记完成',
            '根据当前逐字稿与导演对象变化补齐能力要求，执行选路并落到实际画面，不停在分析或等待用户给技术指令',
            '基础图解可保留简易画布；复杂动效接入动效画布；特殊画面保留实际原生实现，不忽略未实现要求',
            '仅在画面需要新动效时升级旧画布，保留用户编辑、配音、字幕与时间轴；自定义源码不自动覆盖',
            '实际改字换图、正常速度动态、正反向定位、预览与编码一致性检查后交付当前阶段产物；沿用有效确认'],
        sound_defaults=dict(palette=PALETTE,roles=list(ROLES),selection='默认使用用户确定的两款原库音源；动作角色可复用同源，平等选项用groupId固定同素材同增益，按实际启动、峰值或完成点对齐',
            policy='先读46号花字与动作选音：新音效默认teaching-native-v1，嘟咚用于弹出和轻提醒，叮用于重点与完成；连续移动可静音，划线按组首/完成选音，不每字一响。natural-ui-v1仅为显式备选；保留既有旁白与批准混音，新增或修改后核对实际小样',
            commands=['course_tools.py sfx-catalog','course_tools.py sfx-plan COURSE --events EVENTS','course_tools.py sfx-mix COURSE --plan PLAN --narration DRY_AUDIO --out audio/course-mix.wav']),
        confirmation_boundary='技术选路与选音由制作端执行；用户的内容、风格和新小样确认仍按有效版本执行；完成或冻结工程不因恢复而改写')
