"""Small, read-only production handoff included in every course continuation."""
import json
from pathlib import Path
from render_routes import plan,capabilities
from sound import PALETTE,ROLES


def handoff(project,status):
    p=Path(project);branch=status.get('branch');stage=status.get('stage')
    active=stage!='complete' and (branch=='video' or branch is None and status.get('workflow_schema')!=2 and stage in ['visual','pilot','final'])
    if not active:return dict(active=False,reason='已完成，等待具体修改需求，不自动重制' if stage=='complete' else '沿用当前教学设计或课件阶段；此时不启动视频与混音')
    def read(path):return json.loads(path.read_text()) if path.is_file() else {}
    doc=read(p/'workbench.json');spec_path=next((p/x for x in ['source/course-composition.json','source/composition.json','source/spec.json'] if (p/x).is_file()),None)
    spec=read(spec_path) if spec_path else doc
    director=read(p/'director-plan.json');requirements=director.get('rendering',{}).get('requiredEffects',[])
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
    from direction_review import continuation
    return dict(active=True,automatic=True,current_route=current,route_audit=selection,direction=continuation(doc),
        composition_source=str(spec_path.relative_to(p)) if spec_path else 'workbench.json',action=action,
        available_effects=sorted(capabilities()['effects']),teaching_modules=capabilities()['teaching_modules'],motion_catalog_count=capabilities()['executable_motion_count'],
        motion_quality=__import__('motion_quality').preflight(doc),
        craft_quality=__import__('craft_quality').analyze(doc),
        next_steps=['先读取42号按内容导演方法与41号人物演出：用当前逐字稿安排信息变化、焦点、人物意图/视线/反应、镜头理由和独立动作/读图时长；不导入示例课程模板。direction-check按实际动作、姿态、变换/标签边界给取证候选帧，实际复看后补峰值',
            '执行36号课程工艺规范：清楚与美观分别复核，声音自然、标准、干脆、连贯；查看实际画面并修正，不以数量和自评分当质量',
            '执行32号整课动效规范：真实模块、逐段旁白覆盖、编码主体与运行回执、绑定当前候选的逐段导演复核；不能简化后标记完成',
            '根据当前逐字稿与导演对象变化补齐能力要求，执行选路并落到实际画面，不停在分析或等待用户给技术指令',
            '基础图解可保留简易画布；复杂动效接入动效画布；特殊画面保留实际原生实现，不忽略未实现要求',
            '仅在画面需要新动效时升级旧画布，保留用户编辑、配音、字幕与时间轴；自定义源码不自动覆盖',
            '实际改字换图、正常速度动态、正反向定位、预览与编码一致性检查后交付当前阶段产物；沿用有效确认'],
        sound_defaults=dict(palette=PALETTE,roles=list(ROLES),selection='按动作角色选声，同类轮换，固定课程种子，按动作起点、峰值或完成点对齐',
            policy='新音效使用natural-ui-v1真实界面素材，按点击、构建、移动、缩放、显隐、旋转、增长等动作选择；不用统一蜂鸣声，不每字鸣叫；保留既有旁白与批准混音，新增或修改音效后实听小样',
            commands=['course_tools.py sfx-catalog','course_tools.py sfx-plan COURSE --events EVENTS','course_tools.py sfx-mix COURSE --plan PLAN --narration DRY_AUDIO --out audio/course-mix.wav']),
        confirmation_boundary='技术选路与选音由制作端执行；用户的内容、风格和新小样确认仍按有效版本执行；完成或冻结工程不因恢复而改写')
