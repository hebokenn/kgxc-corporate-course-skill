#!/usr/bin/env python3
"""Shared local course operations, exposed identically through DSH and MCP."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/corporate-training-motion'
sys.path.insert(0, str(ROOT / 'plugin'))
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'workbench'))
from runtime import activate, config_dir, tools as media_tools
activate()
from workflow import Course, VERSION as CORE_VERSION, open_course, atomic, read

VERSION = json.loads((ROOT / 'package.json').read_text())['version']
TOOLS = json.loads((ROOT / 'plugin/tools.json').read_text())
TOOL_MAP = {tool['name']: tool for tool in TOOLS}


def default_root(workspace=None):
    if workspace:
        folder = Path(workspace).expanduser().resolve()
        if not folder.is_dir(): raise ValueError('当前工作区不存在')
        return folder / 'courses'
    return Path(os.environ.get('KGXC_COURSES_DIR', str(Path.home() / '.local/share/kgxc-course/courses'))).expanduser().resolve()


def registry_file():
    return config_dir() / 'plugin-courses.json'


def remember(course):
    path = registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        records = read(path, {'courses': []})
        current = str(course.root)
        state = read(course.state_file)
        entries = [entry for entry in records['courses'] if entry.get('course_path') != current and entry.get('course_id') != state['course_id']]
        entries.insert(0, dict(course_path=current, course_id=state['course_id'], title=read(course.plan_file).get('title', '课程')))
        atomic(path, {'courses': entries[:100]})


def course_at(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('请提供实际课程目录')
    path = Path(value).expanduser().resolve()
    relocation = read(config_dir() / 'course-relocations.json', {}).get(str(path))
    if relocation:
        destination = Course(Path(relocation['course_path']))
        if read(destination.state_file, {}).get('course_id') != relocation['course_id']: raise ValueError('迁移目标身份不一致')
        path = destination.root
    course = Course(path)
    if not course.state_file.is_file() or not (course.project / 'workbench.json').is_file():
        raise ValueError('该目录不是现有课程工程；不会从已清理工程或审计目录自动恢复')
    return course


def workspace_action(action, args):
    try:
        if action=='open_delivery':
            from delivery import open_saved_folder
            return open_saved_folder(args['course_path'])
        course = course_at(args['course_path'])
        if action=='workbench_live':
            record=read(course.project/'work/workbench-service.json',{})
            url=record.get('url','');parsed=urllib.parse.urlparse(url)
            if parsed.scheme!='http' or parsed.hostname not in ['127.0.0.1','localhost','::1'] or not parsed.port:
                return dict(ok=True,alive=False)
            try:
                with urllib.request.urlopen(url+'/api/identity',timeout=1) as response:identity=json.load(response)
                alive=identity.get('course_id')==read(course.state_file)['course_id'] and identity.get('course_root')==str(course.root)
            except (ValueError,OSError):alive=False
            return dict(ok=True,alive=alive)
        if action=='deliver':
            from delivery import deliver
            return deliver(course,args['workspace_path'])
        if action=='cleanup_preview':
            from delivery import cleanup_preview
            return cleanup_preview(course,args['workspace_path'])
        if action=='retention':
            from delivery import retention
            return retention(course,args['workspace_path'],args.get('choice'),args.get('request_id'))
        if action != 'relocate': raise ValueError('未知工作区操作')
        from relocate import relocate
        result = relocate(course, args['workspace_path'])
        if result['moved']:
            path = config_dir() / 'course-relocations.json'
            aliases = read(path, {})
            aliases[result['previous_path']] = dict(course_path=result['course_path'], course_id=result['course_id'])
            atomic(path, aliases)
            course = course_at(result['course_path']); remember(course)
        url = workbench(course)
        return dict(result, ok=True, workbench_url=url, workflow=summary(course)['workflow'])
    except (ValueError, OSError, KeyError) as error:
        return dict(ok=False,error=str(error))


def summary(course, full=False):
    status = course.status()
    fields = ['version', 'workflow_schema', 'course_id', 'title', 'revision', 'stage', 'branch', 'next_action', 'gates', 'pending', 'jobs', 'narration_status', 'planning_workflow', 'deliveries', 'ai_review', 'production_handoff','candidate_artifacts','release_status']
    data = status if full else {key: status.get(key) for key in fields if key in status}
    from delivery import completed
    prior=completed(course.root)
    return dict(ok=True, course_path=str(course.root), workflow=data, **({'delivery':prior['delivery']} if prior else {}), paths={
        'skill': str(SKILL / 'SKILL.md'), 'design': str(course.plan_file),
        'transcript': str(course.project / 'source/transcript.md'),
        'storyboard': str(course.project / 'storyboard.json'), 'workbench': str(course.project / 'workbench.json'),
        'production_contract': str(course.project / 'production-contract.json'),
        'editor_draft': str(course.project / 'script-editor.json'),
    }, confirmation='待确认内容请在实际工作台审阅并确认；保存草稿不构成批准。')


def workbench(course):
    # One visible entry for DSH courses; the loopback server is an internal component.
    if read(course.state_file).get('preferred_workbench')!='dsh':
        with course.locked():
            state=read(course.state_file)
            if state.get('preferred_workbench')!='dsh':
                state['preferred_workbench']='dsh';course._commit(state,'workbench_host_selected',dict(host='dsh',external_browser=False))
    with redirect_stdout(io.StringIO()):
        url = open_course(course.root, open_browser=False)
    return url


def local_json(url, data=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password:
        raise ValueError('仅连接已核验身份的本机工作台')
    body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
    request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try: message = json.load(error).get('error', str(error))
        except (ValueError, OSError): message = str(error)
        raise ValueError(message) from error


def validate_arguments(name, args):
    if not isinstance(name, str) or name not in TOOL_MAP:
        raise ValueError('未知制课工具：' + str(name))
    if not isinstance(args, dict):
        raise ValueError('工具参数必须为对象')
    schema = TOOL_MAP[name]['inputSchema']
    unknown = set(args) - set(schema['properties'])
    if unknown:
        raise ValueError('不支持的参数：' + ', '.join(sorted(unknown)))
    for key in schema.get('required', []):
        if key not in args:
            raise ValueError('缺少参数：' + key)
    types = {'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'object': dict}
    for key, value in args.items():
        rule = schema['properties'][key]
        if not isinstance(value, types[rule['type']]) or rule['type'] in ['integer', 'number'] and isinstance(value, bool):
            raise ValueError('参数类型错误：' + key)
        if 'enum' in rule and value not in rule['enum']:
            raise ValueError('参数选项无效：' + key)
        if 'minimum' in rule and value < rule['minimum']:
            raise ValueError('参数数值无效：' + key)
        if 'minLength' in rule and not value.strip():
            raise ValueError('参数不能为空：' + key)
        if 'pattern' in rule and not re.fullmatch(rule['pattern'], value):
            raise ValueError('参数格式无效：' + key)


def execute(name, args):
    validate_arguments(name, args)
    if name == 'kgxc_course_environment':
        configured = media_tools()
        executables = {key: configured.get(key) or shutil.which(key) for key in ['python', 'node', 'ffmpeg', 'ffprobe']}
        return dict(ok=True, plugin_version=VERSION, core_version=CORE_VERSION, skill_root=str(SKILL),
                    default_course_root=str(default_root()), executables=executables,
                    voice_configured=(config_dir() / 'voice.json').is_file(),
                    verified_platform='macOS Apple silicon；其余平台未验证',
                    scope='环境可发现不代表已实测配音或整课生成')
    if name == 'kgxc_course_list':
        entries = []
        for entry in read(registry_file(), {'courses': []})['courses']:
            try:
                from delivery import completed
                delivered=completed(entry['course_path'])
                if delivered and delivered['delivery']['cleanup_status']=='complete':
                    entries.append(dict(entry,delivery_only=True));continue
                course = course_at(entry['course_path'])
                current = read(course.state_file)
                if current['course_id'] != entry['course_id']:
                    continue
                entries.append(dict(entry, revision=current['revision'], title=read(course.plan_file).get('title', entry['title'])))
            except (ValueError, OSError, KeyError):
                continue
        return dict(ok=True, courses=entries, default_course_root=str(default_root()))
    if name == 'kgxc_course_create':
        title = args['title'].strip()
        source = Path(args['source_path']).expanduser().resolve() if args.get('source_path') else None
        if source and not source.is_file():
            raise ValueError('原始素材不存在；尚未建立课程')
        slug = re.sub(r'[^\w\-\u4e00-\u9fff]+', '-', title).strip('-')[:60] or 'course'
        path = Path(args['course_path']).expanduser().resolve() if args.get('course_path') else default_root(args.get('workspace_path')) / (slug + '-' + uuid.uuid4().hex[:8])
        delivery_root = (Path.home() / 'Desktop/ai 制课').resolve()
        if path == delivery_root or path.is_relative_to(delivery_root):
            raise ValueError('桌面 ai 制课 只放成品，请为工作文件选择其他目录')
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError('目标目录非空，不覆盖现有文件')
        from scaffold import create
        with redirect_stdout(io.StringIO()):
            create(path)
        course = Course(path)
        from production_preferences import ensure as ensure_production_preferences
        ensure_production_preferences(course.project)
        status = course.status()
        plan = status['plan']; plan['title'] = title
        if source:
            dest = path / 'inputs' / source.name
            shutil.copy2(source, dest)
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            plan['sources'].append(dict(id='SRC-' + digest[:10], title=source.name, location='../inputs/' + source.name, kind='file', sha256=digest))
        course.save_plan(plan, status['revision'])
        remember(course)
        url = workbench(course)
        return dict(summary(course), workbench_url=url, editor_url=url + '/script-editor.html')
    if name in ['kgxc_course_resume','kgxc_course_status']:
        from delivery import completed
        delivered=completed(args['course_path'])
        if delivered and delivered['delivery']['cleanup_status']=='complete':return delivered
    course = course_at(args['course_path'])
    if name == 'kgxc_course_source_coverage':
        from source_coverage import SourceCoverage
        coverage = SourceCoverage(course)
        if args.get('limit',24000)>24000:
            raise ValueError('单次原件读取上限为24000字符，请按next_offset继续读取')
        if args['action'] == 'save':
            if not isinstance(args.get('report'),dict) or not args.get('expected_script_sha256'):
                raise ValueError('保存原件对照需要完整报告及当前逐字稿SHA-256；不能代填人工确认')
            coverage.save(args['report'], args['expected_script_sha256'])
        return dict(ok=True,course_path=str(course.root),source_coverage=coverage.view(),**(dict(source_excerpt=coverage.source_excerpt(args['source_id'],args.get('offset',0),args.get('limit',24000))) if args['action']=='status' and args.get('source_id') else {}))
    if name == 'kgxc_course_editor':
        from backend import Workspace
        from script_editor import ScriptEditor, sha
        editor = ScriptEditor(Workspace(course.root))
        if args['action'] == 'read':
            state = editor.read(); doc=state.pop('document', None);state['prepared_exports']={}
            if doc and doc.get('status')=='ready' and not state['changed'] and course.storyboard_mode():
                from storyboard import check_bindings
                for purpose in ['pilot','final']:
                    state['prepared_exports'][purpose]=not check_bindings(course.storyboard(),course.sample_plan(),doc,full=purpose=='final')
            return dict(ok=True, editor=state, editor_url=workbench(course) + '/script-editor.html')
        if args['action'] == 'save':
            if 'text' not in args or 'base_revision' not in args: raise ValueError('保存需要 text 和 base_revision')
            return dict(ok=True, editor=editor.save(args['text'], args['base_revision']))
        state = editor.read(); request = state.get('render_request', {})
        if request.get('id') != args.get('request_id'): raise ValueError('渲染请求已经改变')
        if args.get('error'):
            return dict(ok=True, render_request=editor.render_update(request['id'], 'failed', error=args['error']))
        if not args.get('job_id'): raise ValueError('需要真实 job_id 或具体失败原因 error')
        if sha(editor.official()) != request['sha256']: raise ValueError('实际逐字稿与点击渲染时的稿件不一致')
        url = workbench(course); job = local_json(url + '/api/jobs/' + args['job_id'])
        if job.get('status') not in ['queued', 'rendering', 'complete']: raise ValueError('导出任务未生成有效视频或已失败')
        return dict(ok=True, render_request=editor.render_update(request['id'], 'complete' if job['status'] == 'complete' else 'rendering', job=job))
    if name == 'kgxc_course_status':
        return summary(course, args.get('full', False))
    if name == 'kgxc_course_resume':
        url = workbench(course)
        remember(course)
        return dict(summary(course), workbench_url=url, editor_url=url + '/script-editor.html')
    if name == 'kgxc_course_update':
        stage = args['stage']
        if stage in ['design','storyboard'] and isinstance(args.get('data'),dict):
            manual=any(item.get('event')=='studio_outline_saved' for item in read(course.state_file).get('journal',[]))
            different=stage=='storyboard' and bool(course.storyboard().get('segments')) and args['data']!=course.storyboard() or stage=='design' and manual and args['data'].get('units')!=read(course.plan_file).get('units')
            if different:
                from backend import Workspace
                from studio import Studio
                Studio(Workspace(course.root)).proposal('outline' if stage=='design' else stage,args['data'],args['base_revision'])
                return dict(summary(course),proposal=True,message='已有人工编辑或方案选择，AI 修改建议已保存；由用户在当前阶段审阅差异后采用。待选问题可单独追加到原方案，再主动提问。')
        if stage == 'script':
            if isinstance(args.get('data',{}).get('sections'),list):
                from backend import Workspace
                from studio import Studio
                studio=Studio(Workspace(course.root))
                if studio.editor.read()['changed']:
                    proposal=studio.proposal('script',args['data'],args['base_revision'])
                    return dict(summary(course),proposal=True,message='人工草稿已保留。AI 建议已存入待审阅内容，需用户采用。')
                studio.save_sections(args['data']['sections'],args['base_revision'],official=True)
                return summary(course)
            if not args.get('text', '').strip():
                raise ValueError('请提供完整逐字稿 text')
            course.save_script(args['text'], args['base_revision'])
        else:
            if not isinstance(args.get('data'), dict):
                raise ValueError('请提供方案 data 对象')
            method = course.save_plan if stage == 'design' else course.save_storyboard
            method(args['data'], args['base_revision'])
        return summary(course)
    if name == 'kgxc_course_export':
        if course.status()['revision'] != args['base_revision']:
            raise ValueError('课程已被修改，请重新读取当前版本后导出')
        course.require_video('pilot' if args['purpose'] == 'final' else 'style')
        doc = read(course.project / 'workbench.json')
        from timeline import duration
        url = workbench(course)
        result = local_json(url + '/api/export', dict(revision=doc['revision'], start=args.get('start', 0),
                            end=args.get('end', duration(doc) / doc['fps']), purpose=args['purpose']))
        return dict(ok=True, course_path=str(course.root), workbench_url=url, job=result, scope='任务已提交；只有实际状态为complete并核验成品后才报告导出成功。')
    if name == 'kgxc_course_job':
        url = workbench(course)
        result = local_json(url + '/api/jobs/' + args['job_id'])
        return dict(ok=True, course_path=str(course.root), job=result)
    raise ValueError('工具尚未实现')


def call(name, args):
    try:
        return execute(name, args)
    except (ValueError, OSError, KeyError, FileExistsError) as error:
        return dict(ok=False, error=str(error), next_action='核对当前状态或在工作台完成所缺步骤；不得代填用户确认。')


def mcp(request):
    method = request.get('method')
    if 'id' not in request:
        return None
    result = None
    if method == 'initialize':
        requested = request.get('params', {}).get('protocolVersion', '2024-11-05')
        version = requested if requested in ['2024-11-05', '2025-03-26', '2025-06-18'] else '2024-11-05'
        result = dict(protocolVersion=version, capabilities={'tools': {}}, serverInfo=dict(name='kgxc-course', version=VERSION),
                      instructions='共用现有制课 Skill。新建/恢复后打开实际工作台；内容确认由用户完成，不得跳过逐字稿、分镜和小样步骤。')
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        params = request.get('params', {})
        value = call(params.get('name'), params.get('arguments', {}))
        result = dict(content=[dict(type='text', text=json.dumps(value, ensure_ascii=False))], structuredContent=value, isError=not value.get('ok', False))
    else:
        return dict(jsonrpc='2.0', id=request['id'], error=dict(code=-32601, message='Method not found'))
    return dict(jsonrpc='2.0', id=request['id'], result=result)


def review_action(action,args):
    from ai_review import Review,STAGES,RUNNING
    course=course_at(args['course_path']);review=Review(course)
    stage=args.get('stage');run=args.get('run_id')
    if action in ('stage_confirmation_request','stage_confirmation_answer','stage_feedback_save','stage_feedback_dispatch_spec','stage_feedback_dispatched'):
        from backend import Workspace
        from studio import Studio
        from stage_confirmation import StageConfirmation
        confirmations=StageConfirmation(Studio(Workspace(course.root)))
        if action=='stage_confirmation_request':return dict(ok=True,**confirmations.request(stage,args['question_id']))
        if action=='stage_confirmation_answer':return confirmations.answer(stage,args['question_id'],args['selected'])
        if action=='stage_feedback_save':return confirmations.feedback_save(args)
        if action=='stage_feedback_dispatch_spec':return confirmations.feedback_dispatch_spec(args)
        return confirmations.feedback_dispatched(args)
    if action=='production_dispatch':
        from production import dispatch
        return dispatch(course.project,args['task_id'],stage)
    if action=='capability_requirements':
        from blind_review import checklist
        return dict(ok=True,checklist=checklist(stage,review.arrangement() if stage in ['pilot','final'] else 'default_full_av'))
    if action=='enable':return dict(ok=True,review=review.ensure())
    if action=='status':return dict(ok=True,review=review.view())
    if action=='hold':return dict(ok=True,review=review.hold(args['held'],args.get('reason','')))
    if action=='review_arrangement':return dict(ok=True,review=review.set_review_arrangement(args['mode'],args['evidence'],args['actor'],args['source']))
    if action=='select_scheme':return dict(ok=True,review=review.select_scheme(stage,args['scheme_id'],args['evidence'],args['actor']))
    if action=='user_audio_review':return dict(ok=True,review=review.record_user_audio_review(stage,args['artifact_sha256s'],args['artifacts'],args['coverage'],args['listened_completely'],args['audio_and_sync_ok'],args['evidence'],args['actor'],args['source'],args.get('feedback','')))
    if action=='requirements':return dict(ok=True,review=review.requirements(args['values'],args['evidence']))
    if action=='production_event':
        if args['phase']=='end' and (course.project/'work/handoffs'/(args['operation_id']+'.json')).is_file():
            from production import require_dispatch_return
            require_dispatch_return(course.project,args['operation_id'])
        return review.production_event(args['producer'],args['operation_id'],args['phase'],args.get('stage'),args.get('execution'))
    if action=='supervisor_packet':return review.supervisor_packet(stage,run,args.get('operation_id'))
    if action=='supervisor_submit':return review.production_supervisor_submit(args['operation_id'],args['result']) if args.get('operation_id') else review.supervisor_submit(stage,run,args['result'])
    if action=='recover':
        state=review.load()
        for key,node in state['nodes'].items():
            if node.get('runs') and node['runs'][-1]['status'] in RUNNING and node['runs'][-1].get('owner')!=args.get('owner'):
                review.finish(key,node['runs'][-1]['id'],error='宿主已重启，上一轮检查中断；输入、费用与失败记录保留。请主动继续审阅，不会自动重复调用。')
        return dict(ok=True,review=review.view())
    if action=='begin':return review.begin(stage,args['request_id'],args.get('mode','auto'),args.get('instruction',''),args.get('route'),args.get('owner',''),args.get('producer'),args.get('supervision_operation_id'))
    if action=='resume_producer':return review.resume_producer(stage,run,args['request_id'],args['binding'],args['route'],args['producer'],args['owner'])
    if action=='packet':return review.packet(stage,run)
    if action=='producer_packet':return review.producer_packet(stage,run)
    if action=='producer_submit':return review.producer_submit(stage,run,args['result'])
    if action=='progress':review.progress(stage,run,args['text'],args.get('status'));return dict(ok=True)
    if action=='reserve':return review.reserve_supervision_call(args['operation_id'],args['key'],args['route'],args.get('role','supervisor')) if args.get('operation_id') else review.reserve_call(stage,run,args['key'],args['route'],args.get('role','reviewer'))
    if action=='call_result':return review.supervision_call_result(args['operation_id'],args['key'],args.get('usage'),args.get('error'),args.get('agent_audit'),args.get('execution_phase'),args.get('model_invoked')) if args.get('operation_id') else review.call_result(stage,run,args['key'],args.get('usage'),args.get('error'),args.get('sent_frames'),args.get('agent_audit'),args.get('execution_phase'),args.get('model_invoked'))
    if action=='submit':return review.submit(stage,run,args['result'])
    if action=='repair':return review.repair(stage,run,args['repairs'],args.get('producer_id'))
    if action=='repair_error':return review.repair_error(stage,run,args['error'])
    if action=='finish':return review.finish(stage,run,args.get('error'),args.get('limit',False))
    if action=='render':
        review.render_start(stage,run);url=workbench(course);doc=read(course.project/'workbench.json')
        from timeline import duration
        job=local_json(url+'/api/export',dict(revision=doc['revision'],start=0,end=duration(doc)/doc['fps'],purpose=stage,review_run_id=run))
        return dict(ok=True,job=job)
    if action=='render_result':return review.rebind_render(stage,run,args['fingerprint'])
    if action=='ui':return review.ui(stage,run,args['action'],args.get('text'))
    raise ValueError('未知审阅操作')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--once', action='store_true'); parser.add_argument('--stdio', action='store_true'); parser.add_argument('--workspace-once', action='store_true'); parser.add_argument('--review-once', action='store_true'); args = parser.parse_args()
    if args.review_once:
        request=json.load(sys.stdin)
        try:result=review_action(request['name'],request['arguments'])
        except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:result=dict(ok=False,error=str(error))
        print(json.dumps(result,ensure_ascii=False),flush=True);return
    if args.workspace_once:
        request = json.load(sys.stdin)
        print(json.dumps(workspace_action(request['name'], request['arguments']),ensure_ascii=False),flush=True)
        return
    if args.once:
        request = json.load(sys.stdin)
        print(json.dumps(call(request.get('name'), request.get('arguments', {})), ensure_ascii=False), flush=True)
        return
    if not args.stdio:
        parser.error('choose --once or --stdio')
    for line in sys.stdin:
        if not line.strip(): continue
        try:
            request = json.loads(line)
            response = mcp(request)
        except (ValueError, TypeError, KeyError) as error:
            response = dict(jsonrpc='2.0', id=None, error=dict(code=-32700, message=str(error)))
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
