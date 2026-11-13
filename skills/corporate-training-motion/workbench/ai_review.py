"""Version-bound AI review transactions. A report, approval and delivery are distinct.

Independent reviewers only find problems in stage artifacts. Source QA and repairs
belong to the bound producer; execution supervision has a separate agent identity.
"""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import copy
import difflib
import fcntl
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET

from workflow import read, atomic, hashed, sha, now
import blind_review as blind

STAGES = ('script', 'storyboard', 'pilot', 'final')
LABELS = dict(script='教学内容与逐字稿',storyboard='当前全课分镜成品',pilot='实际有声小样',final='当前完整成片')
VERDICTS = ('通过', '需修改', '无法验证', '不适用')
RUNNING = ('queued', 'checking', 'repairing', 'rendering', 'rechecking')
PROTECTED = ('audience', 'performance_task', 'objectives', 'duration', 'duration_minutes', 'constraints', 'decisions')
DOC_REPAIR_FIELDS = {'captions','captionStyle','fields','sceneGraph','assets','scenes','motionPlan','narrationLinks','readingPlan','continuityPlan','media'}
REQUIREMENT_APPLICABILITY = '保留全部原要求及适用阶段；只核验当前已发生阶段的执行。deferred_requirements中的未来或其他阶段要求不能作为本阶段失败依据，也不取消其后续义务。content要求的成果证据由制作端核验；execution要求由独立监督核对执行记录。'
_MEDIA_DURATION_CACHE = {}
_AUDIO_TECHNICAL_CACHE = {}
_AUDIO_TECHNICAL_SCHEMA = 'course-audio-technical/1'


def _audio_technical(path, digest, probe):
    """Measure current encoded bytes. This is never a listening or quality receipt."""
    if sha(path)!=digest:raise ValueError('自动音轨检查前视频字节已改变')
    key=(_AUDIO_TECHNICAL_SCHEMA,digest)
    if key in _AUDIO_TECHNICAL_CACHE:return copy.deepcopy(_AUDIO_TECHNICAL_CACHE[key])
    result=dict(schema=_AUDIO_TECHNICAL_SCHEMA,media_sha256=digest,method='automatic_audio_technical',status='unverified',
                continuous_listening_performed=False,subjective_audio_status='not_evaluated',checks={},issues=[],
                limitations=['未执行连续听审；不评价声音自然度、残音、末句语义完整性或连续音画同步。',
                             '流时长和样本长度只检查技术边界，不能证明人声没有被截断。'])
    try:
        seconds=float(probe['format']['duration'])
        if not math.isfinite(seconds) or seconds<=0:raise ValueError('duration')
        videos=[s for s in probe['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')]
        audios=[s for s in probe['streams'] if s.get('codec_type')=='audio']
        result['checks']['audio_and_video_present']=bool(videos and audios)
        if not videos or not audios:
            result.update(status='failed',issues=['missing_audio_or_video_stream'])
        elif len(audios)!=1 or len(videos)!=1:
            result['issues'].append('multiple_streams_not_fully_supported')
        else:
            audio_duration=float(audios[0]['duration']);video_duration=float(videos[0]['duration'])
            sample_rate=int(audios[0]['sample_rate'])
            if not all(math.isfinite(v) and v>0 for v in [audio_duration,video_duration,sample_rate]):raise ValueError('stream_duration')
            # One pass decodes both actual streams. astats summarizes all decoded
            # audio samples; no samples or process output are exposed to the model.
            if any(type(stream.get('index')) is not int for stream in [videos[0],audios[0]]):raise ValueError('stream_index')
            completed=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-nostats','-v','info','-xerror','-err_detect','explode',
                '-i',str(path),'-map','0:'+str(videos[0]['index']),'-map','0:'+str(audios[0]['index']),'-af','astats=metadata=0:reset=0','-f','null','-'],
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=min(600,max(30,seconds*2+30)))
            result['checks']['full_stream_decode']=completed.returncode==0
            if completed.returncode!=0:
                result.update(status='failed',issues=['stream_decode_failed'])
            else:
                counts=re.findall(r'Number of samples:\s*([0-9]+)',completed.stderr)
                peaks=re.findall(r'Peak level dB:\s*(-?(?:inf|[0-9]+(?:\.[0-9]+)?))',completed.stderr)
                rms=re.findall(r'RMS level dB:\s*(-?(?:inf|[0-9]+(?:\.[0-9]+)?))',completed.stderr)
                if not counts or not peaks or not rms:raise ValueError('audio_statistics')
                count=int(counts[-1]);peak=float(peaks[-1]);mean=float(rms[-1]);decoded_seconds=count/sample_rate
                non_silent=count>0 and math.isfinite(peak) and math.isfinite(mean) and peak>-90
                boundary_ok=max(abs(audio_duration-video_duration),abs(audio_duration-seconds),abs(video_duration-seconds))<=.25
                sample_length_ok=count>0 and abs(decoded_seconds-audio_duration)<=.1
                result['checks'].update(decoded_samples_present=count>0,non_silent=non_silent,
                    stream_duration_boundaries=boundary_ok,decoded_audio_length=sample_length_ok)
                result.update(audio_sample_count=count,sample_rate=sample_rate,decoded_audio_seconds=decoded_seconds,
                    audio_stream_seconds=audio_duration,video_stream_seconds=video_duration,
                    peak_dbfs=peak if math.isfinite(peak) else None,rms_dbfs=mean if math.isfinite(mean) else None,
                    stream_boundary_tolerance_seconds=.25,decoded_length_tolerance_seconds=.1,non_silent_peak_threshold_dbfs=-90)
                if not non_silent:result['issues'].append('all_silent_or_inaudible_audio')
                if not boundary_ok:result['issues'].append('audio_video_stream_boundary_mismatch')
                if not sample_length_ok:result['issues'].append('decoded_audio_length_mismatch')
                result['status']='passed' if all(result['checks'].values()) else 'failed'
    except (ValueError,KeyError,TypeError,OSError,OverflowError,subprocess.SubprocessError) as error:
        result['issues'].append('technical_check_unavailable:'+type(error).__name__)
    if sha(path)!=digest:raise ValueError('自动音轨检查期间视频字节已改变')
    # This process-local, byte-keyed cache cannot be replaced by a producer file.
    _AUDIO_TECHNICAL_CACHE[key]=copy.deepcopy(result)
    return result


def _automatic_audio_item(check, media):
    reports=[m.get('audio_technical') for m in media]
    refs=[dict(method='automatic_audio_technical',sha256=m['sha256']) for m in media if m.get('audio_technical')]
    if not reports or any(not isinstance(r,dict) or r.get('schema')!=_AUDIO_TECHNICAL_SCHEMA or r.get('media_sha256')!=m.get('sha256') or r.get('status') not in ['passed','failed']
                          for m,r in zip(media,reports)):
        return dict(check,verdict='无法验证',reason='当前视频字节的自动技术检查未完成；不能由模型自报或用户免审核替代',evidence=refs)
    failed=[r for r in reports if r['status']=='failed']
    return dict(check,verdict='需修改' if failed else '通过',
                reason='当前视频自动技术检查发现：'+', '.join(issue for r in failed for issue in r.get('issues',[])) if failed else '已核对当前视频字节的音视频流、完整解码、非静音样本及流时长边界；未进行听审，不证明自然度、尾句或音画同步',evidence=refs)


def _execution_evidence(value, event_type, tool_name=None):
    """Accept bounded host projections, never raw arguments, output or file contents.

    Reported assertions describe committed tool output, not independently verified
    filesystem facts. The backend does not open any path in this metadata.
    """
    def require(condition):
        if not condition:raise ValueError('监督证据只能包含有界结构化执行元数据，不能包含正文、命令或凭据')
    def fields(item, required, optional=()):
        require(isinstance(item,dict) and set(required)<=set(item)<=set(required)|set(optional))
    def integer(item, maximum=2**53-1, minimum=0):
        return type(item) is int and minimum<=item<=maximum
    def digest(item):
        return isinstance(item,str) and re.fullmatch(r'[a-fA-F0-9]{64}',item) is not None
    def identifier(item):
        return isinstance(item,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',item) is not None
    def path(item):
        return (isinstance(item,str) and 0<len(item)<=1024
                and not re.search(r'[\x00-\x1f\x7f<>$`|;?*#]',item)
                and not re.search(r'[A-Za-z][A-Za-z0-9+.-]*://',item)
                and '..' not in re.split(r'[\\/]',item)
                and not re.fullmatch(r'(?:\.env(?:\..*)?|auth\.json|credentials?(?:\..*)?|id_rsa|id_ed25519|.*\.(?:key|pem))',re.split(r'[\\/]',item)[-1],re.I)
                and re.search(r'^(?:/?[^\s/][^/]*/|\.\.?/|~/|[A-Za-z]:[\\/]|[^\s/]+\.[A-Za-z0-9]{1,8}$)',item) is not None)
    def metadata(item, required=(), optional=()):
        fields(item,{'sha256','bytes',*required},optional)
        require(digest(item['sha256']) and integer(item['bytes']))

    call=event_type in ['tool/call','tool/ptc-dispatch-start']
    result=event_type in ['tool/result','tool/ptc-dispatch']
    require(call or result)
    fields(value,{'arguments'} if call else {'result'},{'read','command','mutation'} if call else ())
    if call:
        metadata(value['arguments'])
        if 'read' in value:
            require(tool_name in ['read','read_file'])
            item=value['read'];fields(item,{'basis','range'},{'path'})
            require(item['basis']=='committed_tool_arguments' and ('path' not in item or path(item['path'])))
            fields(item['range'],(),{'offset','limit','start_line','end_line','line_start','line_end'})
            require(all(integer(count,10**9) for count in item['range'].values()))
        if 'mutation' in value:
            item=value['mutation'];fields(item,{'basis','scope','operation','fs_verified','paths','paths_complete'})
            require(tool_name in ['write','edit','apply_patch'] and item['operation']==tool_name
                    and item['basis']=='committed_tool_arguments' and item['scope']=='requested_targets' and item['fs_verified'] is False
                    and isinstance(item['paths'],list) and len(item['paths'])<=32 and all(path(v) for v in item['paths'])
                    and type(item['paths_complete']) is bool)
        if 'command' in value:
            require(tool_name=='bash')
            item=value['command'];metadata(item,{'type'},{'interpreter','script_path','argv'})
            require(item['type'] in ['opaque','simple_script'])
            if item['type']=='opaque':fields(item,{'type','sha256','bytes'})
            else:
                fields(item,{'type','sha256','bytes','interpreter','script_path','argv'})
                interpreter=item['interpreter']
                require(isinstance(interpreter,str) and 0<len(interpreter)<=1024)
                name=re.split(r'[\\/]',interpreter)[-1]
                require(re.fullmatch(r'(?:python(?:\d+(?:\.\d+)*)?|node(?:js)?)',name) is not None
                        and ('/' not in interpreter and '\\' not in interpreter or path(interpreter)))
                require(path(item['script_path']) and (name.startswith('python') and item['script_path'].endswith('.py')
                        or name.startswith('node') and re.search(r'\.[cm]?js$',item['script_path']) is not None))
                require(isinstance(item['argv'],list) and len(item['argv'])<=32)
                flag=None
                for argument in item['argv']:
                    fields(argument,{'kind'},{'value','sha256','bytes'})
                    kind=argument['kind'];require(kind in ['flag','number','path','enum','sha256','opaque'])
                    if kind=='opaque':metadata(argument,{'kind'})
                    else:
                        fields(argument,{'kind','value'});argument_value=argument['value']
                        if kind=='flag':
                            require(isinstance(argument_value,str) and (argument_value in ['-B','-u','-s','-S','-E','-I','--no-warnings','--enable-source-maps']
                                    or re.fullmatch(r'--[a-z][a-z0-9-]{0,62}',argument_value) is not None))
                        elif kind=='number':require(integer(argument_value,10**9,-10**9))
                        elif kind=='path':require(path(argument_value))
                        elif kind=='enum':require(argument_value in ['script','storyboard','pilot','final','outline','readback','check','verify','validate','true','false','json','metadata','dry-run','apply'])
                        elif kind=='sha256':require(digest(argument_value) and re.search(r'(?:^|[-_])sha(?:256)?$',flag or '') is not None)
                    if kind=='flag':flag=argument['value']
                    else:
                        require(not re.search(r'token|password|secret|credential|api[-_]?key|auth|cookie|prompt|instruction|text|code|data',flag or '',re.I) or kind=='opaque')
                        flag=None
    else:
        item=value['result'];metadata(item,{'basis','coverage','format'},{'structure','reported'})
        require(item['basis']=='committed_tool_result' and item['coverage']=='reported_fields_only' and item['format'] in ['opaque','json'])
        if item['format']=='opaque':fields(item,{'basis','coverage','format','sha256','bytes'})
        else:
            require('structure' in item)
            structure=item['structure'];types=['object','array','string','number','boolean','null']
            fields(structure,{'type'},{'fields','field_count','length'});require(structure['type'] in types)
            if structure['type']=='object':
                fields(structure,{'type','fields','field_count'})
                require(isinstance(structure['fields'],list) and len(structure['fields'])<=32
                        and integer(structure['field_count']) and structure['field_count']>=len(structure['fields']))
                names=[]
                for field in structure['fields']:
                    fields(field,{'name','type'},{'length'})
                    require(identifier(field['name']) and field['type'] in types)
                    require('length' not in field or field['type']=='array' and integer(field['length']))
                    names.append(field['name'])
                require(len(set(names))==len(names))
            elif structure['type']=='array':
                fields(structure,{'type','length'});require(integer(structure['length']))
            else:fields(structure,{'type'})
            if 'reported' in item:
                require(structure['type']=='object')
                reported=item['reported'];require(isinstance(reported,dict))
                booleans={'ok','completed','all_selected_A','only_process_receipt_written','new_user_confirmation','review_not_triggered','independent_review_passed','baseline_matches'}
                counts={'workflow_revision','segments','options','backed_up_files','revision'};paths={'receipt','receipt_path','output'}
                hashes=[key for key in reported if identifier(key) and key.endswith('_sha256')]
                require(len(hashes)<=32 and set(reported)<=booleans|counts|paths|{'protected_files','checks'}|set(hashes))
                for key,assertion in reported.items():
                    if key in booleans:require(type(assertion) is bool)
                    elif key in counts:require(integer(assertion,10**9))
                    elif key in paths:require(path(assertion))
                    elif key in hashes:require(digest(assertion))
                    else:
                        require(isinstance(assertion,dict) and len(assertion)<=32)
                        require(all(path(k) and digest(v) if key=='protected_files' else identifier(k) and type(v) is bool for k,v in assertion.items()))
    return copy.deepcopy(value)


def enabled(course):
    return (course.project / 'ai-review.json').is_file() or read(getattr(course,'state_file',course.project/'course-state.json'),{}).get('preferred_workbench')=='dsh'


def gate_errors(course, stage):
    if stage not in STAGES or not enabled(course):
        return []
    view = Review(course).node_view(stage)
    if not view.get('passed'):
        return ['AI审阅尚未通过：' + (view.get('reason') or '本阶段需要审阅当前实际成果')]
    if view['user_audio_review']['required'] and view['user_audio_review']['status']!='confirmed':
        return ['AI文字与画面检查通过；仍需用户完整播放当前全部媒体并确认声音与音画配合']
    return []


def approved(course, stage):
    return stage not in STAGES or not enabled(course) or Review(course).node_view(stage).get('passed' if stage=='storyboard' else 'user_confirmed', False)


def formally_delivered(course):
    records=read(course.state_file).get('formal_deliveries',[])
    if not records:return False
    latest=records[-1]
    return latest.get('fingerprint')==Review(course).fingerprint('final') and bool(latest.get('files')) and all(Path(f['path']).is_file() and sha(Path(f['path']))==f['sha256'] for f in latest['files'])


def substantive_example(text):
    """Reject obvious schemas/placeholders. Semantic completeness is still AI-reviewed."""
    text = re.sub(r'[#|*_`\-:：\s]+', '', text)
    text = re.sub(r'(触发(?:事件)?|身体信号|我做了什么|对方(?:怎么)?回应|下次(?:改哪句话)?|姓名|步骤|结果|示范|示例|案例|字段|标题|填写|待填|略|XXX|TODO|\.{2,}|…+)', '', text, flags=re.I)
    return len(text) >= 24 and not re.fullmatch(r'[\[\]【】（）()<>／/]+', text or ' ')


def root_cause_needed(node,run):
    return node['no_improvement']>=2 or len([e for e in run.get('error_history',[]) if not e.get('resolved_by')])>=2


class Review:
    def __init__(self, course):
        self.course = course
        self.project = course.project
        self.path = self.project / 'ai-review.json'

    @contextmanager
    def locked(self):
        folder = self.project / 'work'; folder.mkdir(exist_ok=True)
        with (folder / 'ai-review.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self):
        return read(self.path, dict(schema='course-ai-review/1', course_id=read(self.course.state_file)['course_id'],
                                   nodes={}, requirements=[], authorizations=[], policy=dict(max_repairs=3, max_calls=12)))

    def ensure(self):
        with self.locked():
            if not self.path.exists(): atomic(self.path, self.load())
        return self.view()

    def hold(self, held, reason=''):
        if not isinstance(held, bool): raise ValueError('暂停状态无效')
        with self.locked():
            state=self.load();state['hold']=dict(held=held,reason=str(reason),at=now())
            atomic(self.path,state)
        if held:
            for stage,node in state['nodes'].items():
                if node.get('runs') and node['runs'][-1]['status'] in RUNNING:
                    self.finish(stage,node['runs'][-1]['id'],error=reason or '课程审阅已暂停，已完成的成果与用量保留。')
        return self.view()

    def _unheld(self, state=None):
        hold=(state or self.load()).get('hold',{})
        if hold.get('held'): raise ValueError('课程已暂停：'+hold.get('reason','请明确恢复后再审阅'))

    def _policy(self, state, node=None):
        policy={**state['policy'],**(node or {}).get('policy',{})}
        policy['unlimited_counts']=state['policy'].get('unlimited_counts',False) is True
        return policy

    def arrangement(self, state=None):
        value=(state or self.load()).get('policy',{}).get('review_arrangement',{})
        mode=value.get('mode',blind.DEFAULT_ARRANGEMENT) if isinstance(value,dict) else None
        if mode not in blind.ARRANGEMENTS:raise ValueError('课程审阅分工记录无效')
        return mode

    def _arrangement_context(self, state):
        mode=self.arrangement(state)
        scope='保持完整视听审查门禁；当前文本/图片能力不证明完整视听通过。'
        if mode==blind.USER_AUDIO_ARRANGEMENT:
            scope='当前明确分工仅由AI核验当前文字、实际画面/帧序列可证范围和技术事实；原件、制作输入全文及来源仍由制作代理独立核验。音轨听感、残音、末句、连续音画配合由用户完整播放当前全部媒体后明确确认，仍为未完成义务，不能标记已听或通过。旧要求全文及历史保留；听审条款按本次真实分工承接，不能因能力不具备冒称已满足；其他内容、视觉或技术关键项不能借分工豁免。'
        elif mode==blind.PRODUCER_AUDIO_ARRANGEMENT:
            scope='本课配音无需用户逐句试听或人工审批，由制作端完成当前视频字节的自动技术检查。AI只核验当前文字、实际画面/帧序列可证范围及技术事实；原件与制作输入仍由制作代理核验。未执行连续听审，声音自然度、残音、末句和连续音画配合仍未评估；不能把技术检查或免人工审批写成声音通过。可继续制作候选，内容/视觉确认及正式放行的其他关键未知仍保留。旧要求与用户选择历史不改写。'
        return dict(review_arrangement=copy.deepcopy(state['policy'].get('review_arrangement',dict(mode=blind.DEFAULT_ARRANGEMENT))),
                    review_responsibility_scope=scope)

    def _user_receipt(self, evidence, actor, source):
        if (actor not in ['dsh-user-click','user-chat-confirmation'] or not isinstance(evidence,str) or not evidence.strip() or len(evidence)>8000
                or not isinstance(source,dict) or set(source)!={'kind','id'} or source.get('kind')!=('ui' if actor=='dsh-user-click' else 'chat')
                or not isinstance(source.get('id'),str) or not source['id'].strip() or len(source['id'])>200):
            raise ValueError('须保留真实用户点击或聊天选择的原话及操作来源，制作代理不能代报用户确认')
        return dict(evidence=evidence,actor=actor,source=copy.deepcopy(source),at=now())

    def _operation_blocks_arrangement(self, operation, state):
        phase=operation.get('phase')
        if phase=='end':return False
        if phase=='failure':return not self._historical_native_terminal(operation,state)
        if phase not in ['start','progress']:return True
        # A failed independent supervision may leave the historical phase at
        # progress. Under an existing hold it stays blocked, not running again;
        # changing responsibilities does not resume or rewrite that operation.
        report=operation.get('report',{})
        if (state.get('hold',{}).get('held') is not True or report.get('passed') is not False
                or not operation.get('binding') or report.get('binding')!=operation['binding']
                or not operation.get('reports') or report!=operation['reports'][-1]):return True
        try:
            audit=blind.validate_audit(report.get('agent_audit'),'supervisor',operation.get('producer'),state.get('route'))
            self._actual_call(operation,audit)
        except (ValueError,KeyError,TypeError):return True
        return False

    def _historical_native_terminal(self, operation, state):
        """Read a committed native turn terminal receipt, never a tool error."""
        if state.get('hold',{}).get('held') is not True:return False
        events=operation.get('events',[]);event=events[-1] if events else {}
        producer=operation.get('producer',{});facts=event.get('execution',[])
        if (event.get('phase')!='failure' or event.get('stage')!=operation.get('stage') or not event.get('stage')
                or not isinstance(facts,list) or len(facts)!=1 or not isinstance(facts[0],dict)
                or producer.get('role')!='producer' or not isinstance(producer.get('id'),str) or not producer['id']
                or not isinstance(producer.get('session_id'),str) or not producer['session_id']):return False
        fact=facts[0];required={'type','phase','status','kind','failed','agent_id','operation','seq','time','turn','invocation_id','observed_at'}
        if (not required<=set(fact)<=required|{'label','error'} or fact['type']!='production/historical-native-terminal'
                or fact['phase']!='failure' or fact['failed'] is not True
                or fact['operation']!=operation.get('operation_id') or fact['agent_id']!=producer['id']
                or any(type(fact[key]) is not int or not 0<fact[key]<=2**53-1 for key in ['seq','time','turn'])):return False
        terminal=(fact['status'],fact['kind'])
        if terminal!=('aborted','aborted'):
            # This is an observed *turn/end*, not a recoverable model/tool
            # failure. Keep its original failure kind and error instead of
            # relabelling it aborted just to recover the held course.
            if (terminal!=('failed','error') or fact.get('label')!='turn/end'
                    or not isinstance(fact.get('error'),str)
                    or not re.fullmatch(r'CODEX_APP_SERVER: [^\r\n]{1,1900}',fact['error'])):return False
        invocation=fact['invocation_id'];prefix=producer['session_id']+':step:'
        if not isinstance(invocation,str) or not invocation.startswith(prefix) or not re.fullmatch(r'[1-9]\d{0,15}',invocation[len(prefix):]) or int(invocation[len(prefix):])>=fact['seq']:return False
        if event.get('event_sha256')!=hashed(dict(phase=event['phase'],stage=event['stage'],execution=facts)):return False
        try:
            observed=datetime.fromisoformat(fact['observed_at']);recorded=datetime.fromisoformat(event['at'])
            if observed.tzinfo is None or recorded.tzinfo is None or not fact['time']<=observed.timestamp()*1000<=recorded.timestamp()*1000:return False
        except (ValueError,TypeError,KeyError,OverflowError):return False
        return True

    def set_review_arrangement(self, mode, evidence, actor='dsh-user-click', source=None):
        if mode not in blind.ARRANGEMENTS:raise ValueError('审阅分工无效')
        receipt=self._user_receipt(evidence,actor,source)
        with self.locked():
            state=self.load()
            if (any(c.get('status')=='reserved' for node in state['nodes'].values() for run in node.get('runs',[]) for c in run.get('calls',[]))
                    or any(c.get('status')=='reserved' for op in state.get('supervision',{}).get('operations',{}).values() for c in op.get('calls',[]))):
                raise ValueError('当前仍有审阅调用未结算，不能改变本轮职责分工')
            if (any(run.get('status') in RUNNING for node in state['nodes'].values() for run in node.get('runs',[]))
                    or any(self._operation_blocks_arrangement(op,state) for op in state.get('supervision',{}).get('operations',{}).values())):
                raise ValueError('当前生产或审阅尚未结束，须先安全停止后再改变职责分工')
            previous=copy.deepcopy(state['policy'].get('review_arrangement'))
            state['policy']['review_arrangement']=dict(mode=mode,**receipt)
            state.setdefault('review_arrangement_history',[]).append(dict(previous=previous,current=copy.deepcopy(state['policy']['review_arrangement'])))
            atomic(self.path,state)
        return self.view()

    def _stage_files(self, stage, state=None):
        state=state or read(self.course.state_file)
        return state.get('candidate_artifacts',{}).get(stage) or state.get('artifacts',{}).get(stage,[])

    def _audio_artifacts(self, stage):
        if stage not in ['pilot','final']:return []
        artifacts=[]
        for name in self._stage_files(stage):
            if not str(name).lower().endswith('.mp4'):continue
            path=self.course.relative(name)
            if not path.is_file() or path.is_symlink():raise ValueError('当前听审媒体缺失或不是固定实际文件')
            digest=sha(path);key=(str(path.resolve()),digest)
            if key not in _MEDIA_DURATION_CACHE:
                try:
                    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],timeout=30))
                    if not math.isfinite(duration) or duration<=0:raise ValueError('duration')
                except (ValueError,OSError,subprocess.SubprocessError) as error:raise ValueError('当前媒体无法探测完整听审范围') from error
                _MEDIA_DURATION_CACHE[key]=duration
            if sha(path)!=digest:raise ValueError('听审范围探测期间媒体发生变化，请刷新当前版本')
            artifacts.append(dict(sha256=digest,start_seconds=0,end_seconds=_MEDIA_DURATION_CACHE[key]))
        return artifacts

    def _audio_review(self, stage, state=None):
        state=state or self.load();required=stage in ['pilot','final'] and self.arrangement(state)==blind.USER_AUDIO_ARRANGEMENT
        result=dict(required=required,status='not_required',coverage='all_stage_videos',artifact_sha256s=[],artifacts=[],receipt=None)
        if stage in ['pilot','final'] and self.arrangement(state)==blind.PRODUCER_AUDIO_ARRANGEMENT:
            result.update(status='user_approval_not_required',continuous_listening_performed=False,subjective_audio_status='not_evaluated')
        if not required:return result
        result['status']='pending'
        try:result['artifacts']=self._audio_artifacts(stage)
        except ValueError as error:result['reason']=str(error)
        result['artifact_sha256s']=[item['sha256'] for item in result['artifacts']]
        issues=self._audio_feedback(stage,result['artifact_sha256s'])
        if issues:result.update(status='issues_reported',feedback=issues)
        receipts=state.get('nodes',{}).get(stage,{}).get('user_audio_reviews',[])
        if not receipts:return result
        receipt=copy.deepcopy(receipts[-1]);result['receipt']=receipt
        try:self._user_receipt(receipt.get('evidence'),receipt.get('actor'),receipt.get('source'))
        except ValueError:result['status']='invalid';return result
        if receipt.get('stage')!=stage or receipt.get('course_id')!=state['course_id']:result['status']='invalid';return result
        if not result['artifacts'] or receipt.get('artifacts')!=result['artifacts'] or receipt.get('artifact_sha256s')!=result['artifact_sha256s'] or receipt.get('coverage')!='all_stage_videos':result['status']='stale'
        elif receipt.get('listened_completely') is True and receipt.get('audio_and_sync_ok') is True and not receipt.get('feedback','').strip():
            result['status']='issues_reported' if issues else 'confirmed'
            if issues:result['reason']='当前同版本媒体仍有真实用户问题反馈；须处理后对新版本重新听审，不能用新声明覆盖问题'
        else:result['status']='issues_reported'
        return result

    def _audio_feedback(self, stage, hashes):
        values=[]
        for item in read(self.project/'studio-feedback.json',[]):
            if item.get('stage')!=stage:continue
            bound=item.get('artifact_sha256')
            matches=bound in hashes if bound else bool(hashes) and item.get('artifact_sha256s')==hashes
            if matches:values.append({key:copy.deepcopy(item[key]) for key in ['id','at','artifact_sha256','artifact_sha256s'] if key in item})
        return values

    def record_user_audio_review(self, stage, artifact_sha256s, artifacts, coverage, listened_completely, audio_and_sync_ok, evidence, actor='dsh-user-click', source=None, feedback=''):
        receipt=self._user_receipt(evidence,actor,source)
        if (stage not in ['pilot','final'] or self.arrangement()!=blind.USER_AUDIO_ARRANGEMENT or coverage!='all_stage_videos'
                or type(listened_completely) is not bool or type(audio_and_sync_ok) is not bool or not isinstance(feedback,str) or len(feedback)>8000):
            raise ValueError('听审声明须明确当前全部媒体的完整播放范围及真实声音、音画配合结论')
        if listened_completely and audio_and_sync_ok and feedback.strip():raise ValueError('有音轨问题反馈时不能同时声明声音与音画配合无问题')
        with self.locked():
            state=self.load();current=self._audio_artifacts(stage)
            if (not current or not isinstance(artifacts,list) or artifacts!=current or artifact_sha256s!=[item['sha256'] for item in current]
                    or any(not isinstance(item,dict) or set(item)!={'sha256','start_seconds','end_seconds'} or type(item['start_seconds']) not in [int,float] or type(item['end_seconds']) not in [int,float] for item in artifacts)):
                raise ValueError('听审声明必须精确绑定当前全部视频SHA与每个文件完整起止范围，片段或旧版本不能代替')
            if listened_completely and audio_and_sync_ok and self._audio_feedback(stage,artifact_sha256s):raise ValueError('当前同版本媒体已有用户问题反馈，不能用新听审声明覆盖；须实际修复后核验新版本')
            value=dict(stage=stage,course_id=state['course_id'],artifact_sha256s=copy.deepcopy(artifact_sha256s),artifacts=copy.deepcopy(current),coverage=coverage,
                       listened_completely=listened_completely,audio_and_sync_ok=audio_and_sync_ok,feedback=feedback,**receipt)
            self._node(state,stage).setdefault('user_audio_reviews',[]).append(value);atomic(self.path,state)
        return self.node_view(stage)

    def require_user_audio(self, stage):
        value=self._audio_review(stage)
        if value['required'] and value['status']!='confirmed':raise ValueError('须由用户完整播放当前全部媒体并明确确认声音与音画配合；分工选择或制作授权不代表已听审')
        return value

    def _count_limit(self, policy, key):
        return None if policy.get('unlimited_counts') else policy.get(key)

    def _count_blocked(self, policy, key, used):
        limit=self._count_limit(policy,key)
        return limit is not None and used>=limit

    def _count_remaining(self, policy, key, used):
        limit=self._count_limit(policy,key)
        return None if limit is None else max(0,limit-used)

    def _count_authorization_metadata(self, state, stage):
        applicable=[(i,a) for i,a in enumerate(state['authorizations']) if a.get('kind')=='temporary-unlimited-counts' or a.get('stage')==stage and ('calls' in a or 'repairs' in a)]
        recent=applicable[-12:]
        mode=next((item for item in reversed(applicable) if item[1].get('kind')=='temporary-unlimited-counts'),None)
        if mode and mode not in recent:recent=[mode]+recent[-11:]
        entries=[]
        for _,entry in sorted(recent,key=lambda item:item[0]):
            value={key:copy.deepcopy(entry[key]) for key in ['kind','stage','calls','repairs','enabled','previous_enabled','evidence','actor','at'] if key in entry}
            if isinstance(value.get('evidence'),str) and len(value['evidence'])>2000:
                value['evidence_sha256']=blind.artifact_digest(value['evidence']);value['evidence']=value['evidence'][:2000];value['evidence_truncated']=True
            entries.append(value)
        return dict(authorizations=entries,authorization_count=len(applicable),authorizations_omitted=max(0,len(applicable)-len(entries)))

    def set_unlimited_counts(self, enabled, evidence, actor='dsh-user-click'):
        if type(enabled) is not bool or not isinstance(evidence,str) or not evidence.strip() or actor not in ['dsh-user-click','user-chat-confirmation']:
            raise ValueError('临时次数限制变更需要明确启停状态、用户原话和真实确认来源')
        with self.locked():
            state=self.load();previous=state['policy'].get('unlimited_counts',False) is True
            state['policy']['unlimited_counts']=enabled
            state['authorizations'].append(dict(kind='temporary-unlimited-counts',enabled=enabled,previous_enabled=previous,evidence=evidence,actor=actor,at=now()))
            atomic(self.path,state)
        return self.view()

    def _producer_timeout_metadata(self, state):
        settings=state.get('execution_settings',{});configured='producer_qa_timeout_ms' in settings
        timeout=settings.get('producer_qa_timeout_ms',600000)
        if type(timeout) is not int or not 30000<=timeout<=3600000:raise ValueError('制作核验超时须为30000至3600000毫秒的整数')
        authorization=dict(source='course-execution-setting' if configured else 'default',recorded=False)
        records=[r for r in state.get('execution_settings_history',[]) if r.get('kind')=='producer-qa-timeout']
        if configured and records and records[-1].get('timeout_ms')==timeout:
            record=records[-1]
            authorization.update({k:copy.deepcopy(record[k]) for k in ['kind','timeout_ms','previous_timeout_ms','previous_was_default','evidence','actor','at'] if k in record},recorded=True)
            if len(authorization.get('evidence',''))>2000:
                authorization['evidence_sha256']=blind.artifact_digest(authorization['evidence']);authorization['evidence']=authorization['evidence'][:2000];authorization['evidence_truncated']=True
        return dict(producer_qa_timeout_ms=timeout,producer_qa_timeout_authorization=authorization)

    def set_producer_timeout(self, timeout_ms, evidence, actor='codex-maintenance'):
        if (type(timeout_ms) is not int or not 30000<=timeout_ms<=3600000 or not isinstance(evidence,str) or not evidence.strip() or
            actor not in ['codex-maintenance','dsh-user-click','user-chat-confirmation']):raise ValueError('制作核验超时须为30000至3600000毫秒的整数，并保留实际设置依据与来源')
        with self.locked():
            state=self.load()
            if state.get('hold',{}).get('held') is not True:raise ValueError('须先暂停本课，才能变更制作核验超时')
            calls=[c for node in state['nodes'].values() for run in node.get('runs',[]) for c in run.get('calls',[])]
            calls.extend(c for operation in state.get('supervision',{}).get('operations',{}).values() for c in operation.get('calls',[]))
            if any(c.get('status')=='reserved' for c in calls):raise ValueError('本课仍有未结算调用，不能变更制作核验超时')
            settings=state.setdefault('execution_settings',{})
            record=dict(kind='producer-qa-timeout',timeout_ms=timeout_ms,previous_timeout_ms=copy.deepcopy(settings.get('producer_qa_timeout_ms',600000)),
                        previous_was_default='producer_qa_timeout_ms' not in settings,evidence=evidence,actor=actor,at=now())
            settings['producer_qa_timeout_ms']=timeout_ms
            state.setdefault('execution_settings_history',[]).append(record)
            atomic(self.path,state)
        return dict(ok=True,**self._producer_timeout_metadata(state))

    def requirements(self, values, evidence):
        if not evidence or not isinstance(values, list) or not values:
            raise ValueError('需要本次用户要求及其实际依据')
        with self.locked():
            state = self.load()
            for value in values:
                if isinstance(value,dict):
                    if set(value)!={'id','scope','stages'} or not isinstance(value['id'],str) or not value['id']:raise ValueError('要求适用性更新仅支持已有ID、scope和stages')
                    requirement=next((r for r in state['requirements'] if r['id']==value['id']),None)
                    if requirement is None:raise ValueError('要求ID不存在，不能重建或替换历史要求')
                    stages=value['stages']
                    if value['scope'] not in ['content','execution'] or not isinstance(stages,list) or not stages or any(s not in STAGES for s in stages) or len(set(stages))!=len(stages):raise ValueError('要求scope或适用stages无效')
                    stages=[s for s in STAGES if s in stages]
                    if requirement.get('scope')!=value['scope'] or requirement.get('stages')!=stages:
                        before=dict(scope=requirement.get('scope','content'),stages=self._requirement_stages(requirement))
                        requirement.setdefault('applicability_history',[]).append(dict(at=now(),evidence=evidence,before=before,after=dict(scope=value['scope'],stages=stages)))
                        requirement.update(scope=value['scope'],stages=stages)
                else:
                    if not isinstance(value, str) or not value.strip(): raise ValueError('要求不能为空')
                    if not any(r['text'] == value.strip() for r in state['requirements']):
                        state['requirements'].append(dict(id='REQ-' + uuid.uuid4().hex[:10], text=value.strip(), evidence=evidence, at=now()))
            atomic(self.path, state)
        return self.view()

    def script_input(self):
        # A saved human draft is a real input; it invalidates an older official-script review.
        from script_editor import ScriptEditor
        editor = ScriptEditor(SimpleNamespace(root=self.course.root,project=self.project,file=self.project/'workbench.json')).read()
        return dict(text=editor['text'], editor_revision=editor['revision'], changed=editor['changed'], base_changed=editor['base_changed'])

    def _requirement_stages(self, requirement):
        return requirement['stages'] if 'stages' in requirement else list(STAGES[STAGES.index(requirement.get('from_stage','script')):])

    def requirements_for(self, stage, scope='content'):
        return [r for r in self.load()['requirements'] if r.get('scope','content')==scope and stage in self._requirement_stages(r)]

    def _requirement_context(self, stage, requirements):
        current=[];deferred=[]
        for requirement in requirements:
            value=dict(copy.deepcopy(requirement),scope=requirement.get('scope','content'),stages=self._requirement_stages(requirement))
            applicable=stage in value['stages'] if stage in STAGES else value['scope']=='execution' and value['stages']==list(STAGES)
            (current if applicable else deferred).append(value)
        return dict(current_requirements=current,deferred_requirements=deferred)

    def _passed_policy_runs(self, state, policy_sha256):
        found=[]
        for node in state['nodes'].values():
            for run in node.get('runs',[]):
                report=run.get('report',{})
                if (run.get('protocol')!=blind.PROTOCOL or run.get('status')!='awaiting_confirmation' or
                    run.get('input_basis',{}).get('review_policy_sha256')!=policy_sha256 or report.get('protocol')!=blind.PROTOCOL or
                    report.get('passed') is not True or report.get('fingerprint')!=run.get('fingerprint') or
                    report.get('binding',{}).get('fingerprint')!=run.get('fingerprint') or
                    report.get('producer_qa',{}).get('passed') is not True or report.get('supervision',{}).get('passed') is not True):continue
                try:
                    reviewer=report.get('agent_audit')
                    for audit,role in [(reviewer,'reviewer'),(report['producer_qa'].get('agent_audit'),'producer'),(report['supervision'].get('agent_audit'),'supervisor')]:
                        blind.validate_audit(audit,role,run.get('producer'),state.get('route'),reviewer if role=='supervisor' else None)
                        self._actual_call(run,audit)
                except (ValueError,KeyError,TypeError):continue
                found.append(run['id'])
        return found

    def _review_policy_sha256(self):
        backend=sha(Path(__file__));boundary=sha(Path(blind.__file__))
        current=hashed(dict(protocol=blind.PROTOCOL,backend=backend,boundary=boundary))
        state=self.load();compat=state.get('execution_policy_compatibility',{})
        if not isinstance(compat,dict):return current
        previous=compat.get('from_backend_sha256','')
        if (compat.get('actor')!='codex-maintenance' or compat.get('protocol')!=blind.PROTOCOL or not isinstance(previous,str) or not re.fullmatch(r'[0-9a-f]{64}',previous) or
            compat.get('to_backend_sha256')!=backend or compat.get('boundary_sha256')!=boundary):return current
        old=hashed(dict(protocol=blind.PROTOCOL,backend=previous,boundary=boundary))
        if compat.get('old_policy_sha256')!=old:return current
        approved=set(self._passed_policy_runs(state,old))
        ids=compat.get('passed_run_ids')
        if not isinstance(ids,list) or not ids or any(not isinstance(value,str) for value in ids) or not set(ids).issubset(approved):return current
        return old

    def preserve_policy_for_execution_update(self, previous_backend_sha256, previous_boundary_sha256, evidence):
        if (not isinstance(previous_backend_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',previous_backend_sha256) or
            not isinstance(previous_boundary_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',previous_boundary_sha256) or
            not isinstance(evidence,str) or not evidence.strip()):raise ValueError('维护兼容须提供准确旧源码SHA与本次已核对的执行层变更依据')
        backend=sha(Path(__file__));boundary=sha(Path(blind.__file__))
        if previous_boundary_sha256!=boundary:raise ValueError('盲审边界模块已改变，不能沿用旧策略审阅')
        old=hashed(dict(protocol=blind.PROTOCOL,backend=previous_backend_sha256,boundary=boundary))
        with self.locked():
            state=self.load();passed=self._passed_policy_runs(state,old)
            if not passed:raise ValueError('没有匹配旧源码策略且三角色真实通过的当前协议审阅基线')
            record=dict(protocol=blind.PROTOCOL,from_backend_sha256=previous_backend_sha256,to_backend_sha256=backend,boundary_sha256=boundary,
                        old_policy_sha256=old,passed_run_ids=passed,evidence=evidence,actor='codex-maintenance',at=now())
            state['execution_policy_compatibility']=record
            state.setdefault('execution_policy_compatibility_history',[]).append(copy.deepcopy(record))
            atomic(self.path,state)
        return self.view()

    def basis(self, stage):
        if stage not in STAGES: raise ValueError('正式审阅阶段无效')
        plan = read(self.course.plan_file)
        state = read(self.course.state_file)
        script = self.script_input()
        value = dict(course_id=state['course_id'], stage=stage, script_sha256=hashed(script['text']), base_conflict=script['base_changed'],
                     review_policy_sha256=self._review_policy_sha256(),
                     plan={k: plan.get(k) for k in ['title', 'audience', 'performance_task', 'objectives', 'units', 'assessments', 'decisions', 'constraints', 'duration_minutes', 'duration']},
                     sources=self.course._source_files(plan), requirements=self.requirements_for(stage),execution_requirements=self.requirements_for(stage,'execution'))
        if stage=='storyboard':value['storyboard']=read(self.project/'storyboard.json',{})
        if stage in ['pilot','final']:
            from performance_cache import native_fingerprint
            from production_preferences import creative_basis
            value.update(review_arrangement=self.arrangement(),storyboard=read(self.project / 'storyboard.json', {}),
                         production=self.course._pilot_basis(state) if stage=='pilot' else dict(workbench=sha(self.project / 'workbench.json'),native=native_fingerprint(self.project)),
                         preferences=creative_basis(self.project),
                         files=[dict(path=n,sha256=sha(self.course.relative(n))) for n in self._stage_files(stage,state)])
        return value

    def fingerprint(self, stage): return hashed(self.basis(stage))

    def artifact_hashes(self, stage):
        if stage=='script':return [blind.artifact_digest(self.script_input()['text'])]
        if stage=='storyboard':return [hashed(read(self.project/'storyboard.json',{}))]
        state=read(self.course.state_file)
        return [sha(self.course.relative(p)) for p in self._stage_files(stage,state) if str(p).lower().endswith('.mp4') and self.course.relative(p).is_file()]

    def _confirmation(self, node, stage):
        approval=node.get('approval',{})
        if not approval:
            production=read(self.course.state_file);receipt=production.get('gates',{}).get(stage,{})
            actor=str(receipt.get('actor',''))
            if stage=='storyboard' or not receipt.get('evidence') or not actor or actor.startswith(('ai-','producer','render')):return None
            if stage=='script' and self.script_input()['changed']:return None
            if receipt.get('sha256')!=self.course._gate_hash(stage,read(self.course.plan_file),production):return None
            return dict(receipt,source='course-workflow-gate',stage=stage,artifact_hashes=self.artifact_hashes(stage))
        prior=next((r for r in node.get('runs',[]) if r.get('id')==approval.get('run_id')),None)
        if not prior:return None
        recorded=approval.get('artifact_hashes')
        if recorded is None:
            basis=prior.get('input_basis',{})
            # Historical confirmation can be reused only with an exact content binding.
            if stage=='script':
                if basis.get('script_sha256')!=hashed(self.script_input()['text']):return None
                recorded=self.artifact_hashes(stage)
            elif stage=='storyboard':recorded=[hashed(basis['storyboard'])] if basis.get('storyboard') else []
            else:recorded=[f.get('sha256') for f in basis.get('files',[]) if str(f.get('path','')).lower().endswith('.mp4')]
        return dict(approval,artifact_hashes=recorded) if recorded and recorded==self.artifact_hashes(stage) else None

    def candidate(self, stage):
        if stage == 'script': return bool(self.script_input()['text'].strip())
        if stage=='storyboard':return bool(read(self.project/'storyboard.json',{}).get('segments'))
        state = read(self.course.state_file)
        return any(str(p).lower().endswith('.mp4') and self.course.relative(p).is_file() for p in self._stage_files(stage,state))

    def _node(self, state, stage):
        return state['nodes'].setdefault(stage, dict(runs=[], repairs=0, calls=0, usage={}, elapsed_ms=0,
                                                     no_improvement=0, automatic_inputs=[], draft=''))

    def _script_preflight(self, text=None):
        from script_quality import inspect_script
        brand=read(self.project/'project.json',{}).get('brand',{})
        quality=inspect_script(self.script_input()['text'] if text is None else text,greeting=brand.get('greeting'),
                               require_greeting=bool(brand.get('greeting') or brand.get('profile')=='kgxc'))
        if quality.get('blocking'):
            raise ValueError('逐字稿制作前质量检查未通过：'+'；'.join(str(item.get('message',item.get('reason',item))) for item in quality['blocking']))
        return quality

    def _baseline_report(self, run):
        report=run.get('blind_report')
        if report:return report
        return next((entry.get('report') for entry in reversed(run.get('iterations',[]))
                     if entry.get('report',{}).get('protocol')==blind.PROTOCOL),None)

    def _scheme(self, node):
        return node.get('selected_scheme',{}).get('id','initial-selected-scheme')

    def select_scheme(self, stage, scheme_id, evidence, actor='user-chat-confirmation'):
        """Only an explicit substantive user choice opens another review cycle."""
        if stage not in STAGES or actor not in ['dsh-user-click','user-chat-confirmation'] or not isinstance(scheme_id,str) or not scheme_id.strip() or not isinstance(evidence,str) or not evidence.strip():
            raise ValueError('新方案须记录当前阶段、稳定方案ID与用户实际选择原话')
        with self.locked():
            state=self.load();self._unheld(state);node=self._node(state,stage)
            if any(r.get('status') in RUNNING for r in node['runs']):raise ValueError('须先结束当前执行，再记录用户新选的实质方案')
            if scheme_id==self._scheme(node):return self.node_view(stage,state)
            if any(r.get('scheme_id','initial-selected-scheme')==scheme_id for r in node['runs']):raise ValueError('旧方案ID不能被重新使用以重置盲审次数')
            receipt=dict(id=scheme_id,evidence=evidence,actor=actor,at=now(),substantive_new_selection=True)
            node.setdefault('scheme_history',[]).append(copy.deepcopy(node.get('selected_scheme',dict(id=self._scheme(node)))))
            node['selected_scheme']=receipt;atomic(self.path,state)
        return self.node_view(stage)

    def _acceptance_binding(self, run):
        baseline=self._baseline_report(run) or {}
        if not baseline or baseline.get('fingerprint')==run['fingerprint']:return copy.deepcopy(baseline.get('binding'))
        return dict(protocol='course-targeted-acceptance/1',stage=run['stage'],run_id=run['id'],fingerprint=run['fingerprint'],
                    scheme_id=run.get('scheme_id','initial-selected-scheme'),baseline_binding=copy.deepcopy(baseline['binding']),
                    issue_ledger_sha256=hashed([{key:value for key,value in item.items() if key not in ['status','acceptance_fingerprint','acceptance_evidence','acceptance_reason']} for item in run.get('issue_ledger',[])]))

    def _freeze_issues(self, run, report, source='blind'):
        ledger=run.setdefault('issue_ledger',[]);known={item['id'] for item in ledger}
        for item in report.get('items',[]):
            if item.get('verdict') not in ['需修改','无法验证'] or item['id'] in known:continue
            ledger.append(dict(id=item['id'],source=source,severity='blocking' if item.get('critical') else 'advisory',
                               label=item.get('label',item['id']),location=copy.deepcopy(item.get('evidence',[])),
                               evidence=copy.deepcopy(item.get('evidence',[])),learning_impact=item.get('reason',''),
                               acceptance_condition=item.get('label',item['id'])+'；以修复后的当前成果提供可定位证据',
                               required_method=item.get('required_method') or ('script_read' if run['stage']=='script' else 'storyboard_read' if run['stage']=='storyboard' else 'frame_sequence' if len([ref for ref in item.get('evidence',[]) if isinstance(ref,dict) and type(ref.get('time')) in [int,float]])>=2 else 'frames'),allow_na=item.get('allow_na',False),
                               baseline_fingerprint=report.get('fingerprint'),status='open'))
        return ledger

    def _prepare_targeted(self, run, stage, instruction=''):
        baseline=self._baseline_report(run)
        if not baseline:raise ValueError('一次盲审未形成可接受报告；保留失败，不能自动重复盲审')
        run['blind_report']=copy.deepcopy(baseline);self._freeze_issues(run,baseline)
        if run.get('producer_report') and not run.get('issue_ledger_frozen'):
            self._freeze_issues(run,run['producer_report'],'producer');run['issue_ledger_frozen']=True
        run.setdefault('producer_report_history',[]).extend([copy.deepcopy(run['producer_report'])] if run.get('producer_report') else [])
        run.pop('producer_report',None);run.pop('supervisor_report',None)
        run['fingerprint']=self.fingerprint(stage)
        run['acceptance_mode']='targeted';run['producer_only']=True
        run['iterations'].append(dict(index=len(run['iterations']),at=now(),acceptance_mode='targeted',proposed_repairs=[]))
        if instruction:run['instruction']=instruction
        run['report']=dict(passed=False,items=[],blocking_ids=['targeted-acceptance'])

    def node_view(self, stage, state=None):
        state = state or self.load(); node = state['nodes'].get(stage, {})
        run = node.get('runs', [{}])[-1] if node.get('runs') else {}
        current = self.fingerprint(stage)
        protocol=run.get('protocol',blind.LEGACY_PROTOCOL) if run else None
        matches = bool(run and run.get('fingerprint') == current and protocol==blind.PROTOCOL and run.get('scheme_id','initial-selected-scheme')==self._scheme(node))
        status = run.get('status', 'not_started') if matches else 'stale' if run else 'not_started'
        report = run.get('report', {})
        passed = matches and status == 'awaiting_confirmation' and report.get('passed', False)
        confirmation=self._confirmation(node,stage)
        audio_review=self._audio_review(stage,state)
        from source_coverage import SourceCoverage
        coverage=SourceCoverage(self.course).view()
        confirmed = passed and bool(confirmation) and (not audio_review['required'] or audio_review['status']=='confirmed') and (not coverage['required'] or coverage['confirmed'])
        reason = ('历史原件知情审阅已保留，不计为当前独立盲审' if run and protocol!=blind.PROTOCOL else '输入或实际媒体已修改，旧报告失效' if run and not matches else run.get('reason') or run.get('last_error') or '')
        if run and protocol!=blind.PROTOCOL:status='legacy'
        run_view=copy.deepcopy(run)
        if run_view:run_view['review_protocol']=protocol
        return dict(stage=stage, label=LABELS[stage], fingerprint=current, status=status, run=run_view,
                    passed=bool(passed), user_confirmed=bool(confirmed), reason=reason, draft=node.get('draft', ''),
                    ai_responsibility_passed=bool(passed),user_audio_review=audio_review,source_coverage_pending=bool(coverage['required'] and not coverage['confirmed']),source_coverage_status=coverage['status'],
                    audio_review_scope=(dict(mode=blind.PRODUCER_AUDIO_ARRANGEMENT,user_audio_approval_required=False,continuous_listening_performed=False,
                        subjective_audio_status='not_evaluated',formal_audio_passed=False) if stage in ['pilot','final'] and self.arrangement(state)==blind.PRODUCER_AUDIO_ARRANGEMENT else None),
                    review_protocol=protocol,legacy=bool(run and protocol!=blind.PROTOCOL),content_confirmation_preserved=bool(confirmation),confirmation=confirmation,
                    repairs=node.get('repairs', 0), calls=node.get('calls', 0), usage=node.get('usage', {}),
                    elapsed_ms=node.get('elapsed_ms', 0) + (int((time.time()-run['started_at'])*1000) if matches and status in RUNNING else 0),
                    policy=self._policy(state,node),
                    review_cycle=dict(scheme_id=self._scheme(node),blind_review_limit=1,automatic_repair_batches=1,automatic_acceptance_passes=1,
                                      blind_review_completed=bool(self._baseline_report(run)),producer_only=bool(run.get('producer_only')),
                                      acceptance_mode=run.get('acceptance_mode','initial'),automatic_repair_batches_used=run.get('automatic_repair_batches_used',0)),
                    issue_ledger=copy.deepcopy(run.get('issue_ledger',[])),
                    history=[dict({k: r.get(k) for k in ['id', 'status', 'reason', 'fingerprint', 'completed_at', 'superseded_by']},review_protocol=r.get('protocol',blind.LEGACY_PROTOCOL),legacy=r.get('protocol')!=blind.PROTOCOL) for r in node.get('runs', [])[:-1]])

    def view(self):
        state = self.load()
        from source_coverage import SourceCoverage
        return dict(enabled=enabled(self.course), course_id=state['course_id'],
                    nodes={stage: self.node_view(stage, state) for stage in STAGES},source_coverage=SourceCoverage(self.course).view(),production_scope=copy.deepcopy(state.get('production_scope',{})),auto_review=state.get('production_scope',{}).get('auto_review',True),policy=self._policy(state),requirements=state['requirements'],hold=state.get('hold',{}),
                    supervision=dict(operations=list(copy.deepcopy(state.get('supervision',{}).get('operations',{})).values()),
                                     calls=state.get('nodes',{}).get('supervision',{}).get('calls',0),usage=state.get('nodes',{}).get('supervision',{}).get('usage',{}),
                                     policy=self._policy(state,state.get('nodes',{}).get('supervision',{}))))

    def begin(self, stage, request_id, mode='auto', instruction='', route=None, owner='', producer=None, supervision_operation_id=None):
        if mode not in ['auto', 'continue', 'modify']: raise ValueError('审阅请求类型无效')
        if not isinstance(request_id, str) or not request_id: raise ValueError('需要稳定的审阅请求ID')
        if mode == 'modify' and not str(instruction).strip(): raise ValueError('请填写本次修改意见')
        if not self.candidate(stage): raise ValueError('尚无本阶段实际成果')
        blind.route(route)
        if not isinstance(producer,dict) or producer.get('role')!='producer' or not producer.get('id') or not producer.get('session_id'):raise ValueError('需要当前课程实际绑定的制作代理身份')
        with self.locked():
            state = self.load(); self._unheld(state)
            if self.script_input()['base_changed']: raise FileExistsError('正式稿与人工草稿存在未合并修改；保留两份内容，合并后再审阅')
            node = self._node(state, stage); fingerprint = self.fingerprint(stage)
            if mode=='auto' and state.get('production_scope',{}).get('auto_review') is False:
                return dict(ok=True,started=False,auto_review=False,production_scope=copy.deepcopy(state['production_scope']),
                            run=copy.deepcopy(node['runs'][-1]) if node['runs'] else {},review=self.node_view(stage,state),
                            reason='当前任务仅生成原件对照报告；不自动启动或恢复独立盲审')
            if stage=='script':self._script_preflight()
            for old in node['runs']:
                if old.get('protocol')==blind.PROTOCOL and old.get('scheme_id','initial-selected-scheme')==self._scheme(node) and (old.get('request_id') == request_id or mode == 'auto' and fingerprint in [old.get('automatic_input'),old.get('fingerprint')]):
                    return dict(ok=True, started=False, run=old, review=self.node_view(stage, state))
            active = next((r for r in reversed(node['runs']) if r['status'] in RUNNING), None)
            if active: return dict(ok=True, started=False, run=active, review=self.node_view(stage, state))
            if any(s!=stage and n.get('runs') and n['runs'][-1]['status'] in RUNNING for s,n in state['nodes'].items()):raise ValueError('本课另一节点正在审阅，请等待本轮结束')
            scheme=self._scheme(node)
            if mode=='auto':
                previous=next((r for r in reversed(node['runs']) if r.get('scheme_id','initial-selected-scheme')==scheme),None)
                if previous:
                    return dict(ok=True,started=False,producer_only=bool(self._baseline_report(previous)),run=previous,review=self.node_view(stage,state),
                                reason='本方案已有执行记录；保留失败或成果，不因版本漂移自动重试')
            consumed=next((r for r in reversed(node['runs']) if r.get('scheme_id','initial-selected-scheme')==scheme and
                           (self._baseline_report(r) or any(c.get('role','reviewer')=='reviewer' and c.get('failure_kind')!='preflight' for c in r.get('calls',[])))),None)
            if consumed:
                if mode=='auto' or not self._baseline_report(consumed) or consumed.get('report',{}).get('passed') and consumed.get('fingerprint')==fingerprint and not instruction:
                    return dict(ok=True,started=False,producer_only=bool(self._baseline_report(consumed)),run=consumed,review=self.node_view(stage,state),
                                reason='当前选定方案本阶段已完成一次盲审；只按固定问题清单集中处理，不自动重审')
                if consumed is not node['runs'][-1]:raise ValueError('历史盲审已消耗本方案次数；先核对当前绑定，不能新建一轮')
                if producer!=consumed.get('producer') or route!=state.get('route'):raise ValueError('定向验收须沿用原制作代理与模型通道')
                if any(c.get('status')=='reserved' for c in consumed.get('calls',[])):raise ValueError('仍有未结算调用，不能并发恢复')
                self._prepare_targeted(consumed,stage,str(instruction).strip())
                if str(instruction).strip():
                    issue_id='USER-FOLLOWUP-'+hashed(str(instruction).strip())[:12]
                    if not any(issue['id']==issue_id for issue in consumed['issue_ledger']):
                        consumed['issue_ledger'].append(dict(id=issue_id,source='explicit-user-followup',severity='blocking',label=str(instruction).strip(),
                            location=[],evidence=[],learning_impact='用户本次明确修改意见',acceptance_condition=str(instruction).strip(),
                            required_method='storyboard_read' if stage=='storyboard' else 'script_read' if stage=='script' else 'frames',allow_na=False,
                            baseline_fingerprint=consumed['fingerprint'],status='open'))
                consumed.update(status='queued',owner=owner,started_at=time.time(),reason='沿用一次盲审与固定问题清单，仅恢复制作端定向处理',
                                targeted_repair_authorized=True,repair_batch_used=False,repair_batch_grant=dict(request_id=request_id,mode=mode,instruction=str(instruction),at=now()))
                consumed.pop('completed_at',None)
                self._event(consumed,consumed['reason']);atomic(self.path,state)
                return dict(ok=True,started=True,producer_only=True,iteration=consumed['iterations'][-1]['index'],run=consumed,review=self.node_view(stage,state))
            if mode=='auto' and stage=='script' and self.script_input()['changed']:raise ValueError('人工草稿尚在编辑；保存不会自动调用模型，请明确继续审阅')
            if mode=='auto' and stage in ['pilot','final']:
                current_state=read(self.course.state_file)
                if self.script_input()['changed'] or (current_state.get('candidate_context',{}).get(stage) or current_state.get(stage+'_context'))!=self.course._video_context(current_state):raise ValueError('实际媒体尚未更新到本次制作版本，生成后再自动审阅')
            policy = self._policy(state,node)
            pinned = state.get('route')
            if pinned and route and pinned != route: raise ValueError('模型或计费通道已改变；保留成果，不能自动切换来源')
            if route and not pinned: state['route'] = route
            if mode=='modify' and not any(r['text']==instruction.strip() and STAGES.index(stage)>=STAGES.index(r.get('from_stage','script')) for r in state['requirements']):
                state['requirements'].append(dict(id='FEEDBACK-'+stage+'-'+hashed(instruction)[:10],text=instruction.strip()[:8000],from_stage=stage,evidence='本次按意见修改请求：'+request_id,at=now()))
                atomic(self.path,state);fingerprint=self.fingerprint(stage)
            run = dict(id=uuid.uuid4().hex, request_id=request_id, stage=stage, mode=mode, instruction=str(instruction)[:8000],
                       protocol=blind.PROTOCOL,scheme_id=scheme,producer=copy.deepcopy(producer),supervision_operation_id=supervision_operation_id,
                       status='queued', started_at=time.time(), at=now(), fingerprint=fingerprint, initial_fingerprint=fingerprint,
                       input_basis=self.basis(stage), owner=owner, iterations=[], events=[], calls=[], repaired=[],
                       automatic_input=fingerprint if mode == 'auto' else None)
            run['repair_grant']={prior:self.node_view(prior,state)['passed' if prior=='storyboard' else 'user_confirmed'] for prior in STAGES[:STAGES.index(stage)]}
            if self._count_blocked(policy,'max_calls',node['calls']):
                run.update(status='limit_reached', reason='已到累计模型调用上限；保留成果。追加额度须另行明确授权。', completed_at=now())
            node['runs'].append(run)
            self._event(run, run.get('reason') or '排队等待审阅')
            atomic(self.path, state)
            return dict(ok=True, started=run['status']=='queued', run=run, review=self.node_view(stage, state))

    def _find(self, state, stage, run_id, latest=True):
        node = self._node(state, stage)
        run = next((r for r in node['runs'] if r['id'] == run_id), None)
        if not run or latest and run is not node['runs'][-1]: raise ValueError('审阅任务已被新版替代')
        return node, run

    def _current(self, stage, run):
        self._unheld()
        if run['fingerprint'] != self.fingerprint(stage): raise FileExistsError('审阅期间课程出现新修改；已保留人工内容，请基于当前版本重新审阅')

    def _event(self, run, text, status=None, **details):
        if status: run['status'] = status
        run['events'].append(dict(at=now(), time_ms=int(time.time()*1000), text=text, **details))

    def progress(self, stage, run_id, text, status=None):
        with self.locked():
            state=self.load(); self._unheld(state); _,run=self._find(state,stage,run_id)
            if run['status'] not in RUNNING:raise ValueError('本轮已结束，不能恢复旧任务')
            self._event(run,text,status); atomic(self.path,state)

    def reserve_call(self, stage, run_id, key, route, role='reviewer'):
        blind.route(route)
        if role not in ['reviewer','producer','supervisor']:raise ValueError('审阅调用职责无效')
        with self.locked():
            state=self.load(); node,run=self._find(state,stage,run_id); self._current(stage,run)
            prior=next((c for c in run['calls'] if c['key']==key),None)
            if prior: return dict(ok=True,reserved=False,call=prior)
            if role=='reviewer':
                scheme=run.get('scheme_id','initial-selected-scheme')
                calls=[c for r in node['runs'] if r.get('scheme_id','initial-selected-scheme')==scheme for c in r.get('calls',[])
                       if c.get('role','reviewer')=='reviewer' and c.get('failure_kind')!='preflight']
                if self._baseline_report(run) or calls:raise ValueError('当前选定方案本阶段只盲审一次；修复后仅做固定问题清单定向验收')
            if run['status'] not in RUNNING:raise ValueError('本轮已完成；新的审阅须由用户主动发起')
            attempt=run.get('producer_attempt',{})
            if attempt.get('retry') and attempt.get('fingerprint')==run['fingerprint']:
                if role=='reviewer':raise ValueError('本次仅恢复制作核验；实际成果未修改前不得重复盲审')
                if key!=attempt.get('producer_key' if role=='producer' else 'supervisor_key'):raise ValueError('恢复调用必须使用本次唯一事务调用标识')
            if route != state.get('route'): raise ValueError('实际模型通道与本轮绑定不一致，停止调用')
            policy=self._policy(state,node)
            if policy.get('max_tokens') is not None and any(blind.usage_unknown(c) for r in node['runs'] for c in r.get('calls',[])):
                raise ValueError('已有调用用量未返回，无法核对累计token预算；保留成果，核对用量后再继续')
            if self._count_blocked(policy,'max_calls',node['calls']) or policy.get('max_tokens') is not None and node['usage'].get('totalTokens',0)>=policy['max_tokens']:
                raise ValueError('累计审阅预算已用完；须另行明确追加授权')
            call=dict(key=key,at=now(),status='reserved',route=route,role=role)
            if role=='producer' and attempt.get('packet_path'):
                call.update(producer_attempt_id=attempt['id'],producer_packet_path=attempt['packet_path'],producer_packet_sha256=attempt['packet_sha256'])
            run['calls'].append(call); node['calls']+=1
            self._event(run,'正在核对本轮验收项','checking' if not run['iterations'] else 'rechecking')
            atomic(self.path,state);return dict(ok=True,reserved=True,call=call)

    def call_result(self, stage, run_id, key, usage=None, error=None, sent_frames=None, agent_audit=None, execution_phase=None, model_invoked=None):
        with self.locked():
            state=self.load(); node,run=self._find(state,stage,run_id,latest=False)
            call=next(c for c in run['calls'] if c['key']==key)
            if call.get('status')!='reserved': return dict(ok=True)
            outcome=blind.call_completion(error,usage,agent_audit,execution_phase,model_invoked)
            if agent_audit is not None:
                call['agent_audit']=blind.validate_audit(agent_audit,call.get('role','reviewer'),run.get('producer'),call['route'],allow_uninvoked=outcome['failure_kind']=='preflight')
            call.update(outcome,completed_at=now())
            if sent_frames is not None:
                if call.get('role')=='producer':
                    packet=read(self.project/call.get('producer_packet_path',run.get('producer_packet_path','')), {})
                    allowed={frame['sha256'] for frame in packet.get('evidence',{}).get('frames',[])}
                    if not isinstance(sent_frames,list) or any(digest not in allowed for digest in sent_frames):raise ValueError('制作端实际发送帧不属于本次冻结验收包')
                    call['sent_frames']=copy.deepcopy(sent_frames)
                else:run['sent_frames']=sent_frames
            for k,v in (usage or {}).items():
                if isinstance(v,(float,int)) and not isinstance(v,bool):node['usage'][k]=node['usage'].get(k,0)+max(0,v)
            atomic(self.path,state)
        return dict(ok=True)

    def _actual_call(self, run, audit):
        if not any(c.get('status')=='complete' and c.get('role')==audit['role'] and c.get('agent_audit')==audit for c in run.get('calls',[])):
            raise ValueError('报告缺少匹配的实际代理调用与用量登记，不能接受自报身份')

    def _producer_packet_record(self, stage, run, name, known_sha256=None):
        path=self.project/name;boundary=(self.project/'qa/ai-review'/run['id']).resolve()
        if path.is_symlink() or not path.resolve().is_relative_to(boundary) or not path.is_file():raise ValueError('制作核验包路径无效，保留原文件后核对')
        digest=sha(path)
        if known_sha256 and digest!=known_sha256:raise FileExistsError('已冻结的制作核验包字节已改变')
        packet=read(path)
        if (packet.get('protocol')!=blind.PRODUCER_PROTOCOL or packet.get('stage')!=stage or packet.get('run_id')!=run['id'] or
            packet.get('fingerprint')!=run['fingerprint'] or packet.get('binding')!=self._acceptance_binding(run)):raise ValueError('制作核验包不属于本轮当前成果及已接受盲审绑定')
        return dict(path=name,sha256=digest,attempt_id=packet.get('attempt_id'),iteration=packet.get('iteration'),fingerprint=packet['fingerprint'],at=now())

    def resume_producer(self, stage, run_id, request_id, binding, route, producer, owner):
        if not isinstance(request_id,str) or not request_id.strip() or not isinstance(owner,str) or not owner.strip():raise ValueError('制作核验恢复需要稳定请求ID与实际宿主身份')
        blind.route(route)
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id);self._current(stage,run)
            if run.get('protocol')!=blind.PROTOCOL or route!=state.get('route') or producer!=run.get('producer'):raise ValueError('制作核验恢复必须沿用当前协议、原制作代理与原模型通道')
            report=run.get('blind_report',{})
            if (not report or report.get('protocol')!=blind.PROTOCOL or binding!=self._acceptance_binding(run)):
                raise ValueError('制作核验恢复不能更换当前验收成果或已接受的基线盲审绑定')
            packet=read(self.project/run['packet_path']);blind.validate_packet(packet)
            if packet.get('binding')!=run.get('packet_binding'):raise ValueError('已冻结基线盲审包与原绑定不符')
            audit=blind.validate_audit(report.get('agent_audit'),'reviewer',producer,route);self._actual_call(run,audit)
            if not run.get('iterations') or not self._baseline_report(run):raise ValueError('本轮真实基线盲审尚未完整入库')
            previous=next((r for r in run.get('producer_retry_history',[]) if r['request_id']==request_id),None)
            if previous:return dict(ok=True,started=False,run=copy.deepcopy(run),review=self.node_view(stage,state),**{k:previous[k] for k in ['attempt_id','producer_key','supervisor_key','iteration']})
            if run['status']!='failed':raise ValueError('仅已失败且等待制作核验的当前任务可以恢复')
            if 'producer_report' in run or 'producer_report' in run['iterations'][-1]:raise ValueError('当前制作核验已有报告，不能重复调用或替换结论')
            if run.get('acceptance_mode')!='targeted' and (run.get('repaired') or any(entry.get('repair_attempted') or entry.get('proposed_repairs') for entry in run['iterations'])):
                raise ValueError('初始核验出现未绑定的修复进度；须核对当前成果及定向验收绑定，不能当作同成果失败重试')
            if any(c.get('status')=='reserved' for c in run['calls']):raise ValueError('本轮仍有未结算调用，不能并发重试制作核验')
            if any(s!=stage and n.get('runs') and n['runs'][-1]['status'] in RUNNING for s,n in state['nodes'].items()):raise ValueError('本课另一节点仍在运行，不能并发恢复')
            calls=[c for c in run['calls'] if c.get('role')=='producer']
            if not calls or calls[-1].get('status')!='failed' or calls[-1].get('route')!=route:raise ValueError('没有本轮原通道已登记的制作核验失败')
            policy=self._policy(state,node)
            if policy.get('max_tokens') is not None and any(blind.usage_unknown(c) for r in node['runs'] for c in r.get('calls',[])):raise ValueError('已有调用用量未返回，不能跳过独立token预算限制')
            if self._count_blocked(policy,'max_calls',node['calls']) or policy.get('max_tokens') is not None and node['usage'].get('totalTokens',0)>=policy['max_tokens']:raise ValueError('累计制作核验预算已到上限，保留全部历史')
            if not run.get('producer_packet_path'):raise ValueError('原制作核验包未登记，不能恢复未冻结输入')
            old=self._producer_packet_record(stage,run,run['producer_packet_path'],run.get('producer_packet_sha256'))
            history=run.setdefault('producer_packet_history',[])
            if not any(p['path']==old['path'] for p in history):history.append(dict(old,legacy_import='producer_packet_sha256' not in run))
            attempt_id=uuid.uuid4().hex;iteration=run['iterations'][-1]['index']
            retry=dict(request_id=request_id,attempt_id=attempt_id,producer_key='producer-retry-'+attempt_id,supervisor_key='supervisor-retry-'+attempt_id,iteration=iteration,
                       binding=copy.deepcopy(binding),previous_call_key=calls[-1]['key'],previous_packet=old,
                       previous={k:copy.deepcopy(run.get(k)) for k in ['status','reason','completed_at','started_at','owner']},owner=owner,at=now())
            summary=self.project/'qa/ai-review'/run_id/'summary.json'
            if summary.is_file():
                archive=self.project/'qa/ai-review'/run_id/('producer-retry-'+attempt_id)/'previous-summary.json';archive.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(summary,archive);retry['previous_summary']=dict(path=str(archive.relative_to(self.project)),sha256=sha(archive))
            run.setdefault('producer_retry_history',[]).append(retry)
            run['producer_attempt']=dict(id=attempt_id,iteration=iteration,fingerprint=run['fingerprint'],binding=copy.deepcopy(binding),retry=True,producer_key=retry['producer_key'],supervisor_key=retry['supervisor_key'])
            run.update(owner=owner,started_at=time.time(),reason='原制作核验调用失败已保留；仅重试同一成果的制作端核验',resumed_at=now())
            run.pop('completed_at',None)
            self._event(run,'保留原盲审、失败用量与原核验包，仅恢复制作端核验','rechecking',attempt_id=attempt_id,previous_call_key=calls[-1]['key'])
            atomic(self.path,state)
            return dict(ok=True,started=True,run=copy.deepcopy(run),review=self.node_view(stage,state),**{k:retry[k] for k in ['attempt_id','producer_key','supervisor_key','iteration']})

    def _distinct_scope(self, state, audit):
        other_role='supervisor' if audit['role']=='reviewer' else 'reviewer'
        calls=[c for node in state['nodes'].values() for run in node.get('runs',[]) for c in run.get('calls',[])]
        calls.extend(c for op in state.get('supervision',{}).get('operations',{}).values() for c in op.get('calls',[]))
        for call in calls:
            other=call.get('agent_audit',{})
            if other.get('role')==other_role and (other.get('id')==audit['id'] or other.get('session_id')==audit['session_id']):raise ValueError('独立审阅者与侦探监督者必须始终使用不同代理和会话')

    def _source_text(self, path):
        if path.suffix.lower() in ['.txt','.md','.csv']:return path.read_text(errors='replace')
        if path.suffix.lower() in ['.pptx','.docx']:
            with zipfile.ZipFile(path) as archive:
                names=[n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)] if path.suffix.lower()=='.pptx' else ['word/document.xml']
                names.sort(key=lambda n:int(re.search(r'(\d+)\.xml',n)[1]) if re.search(r'(\d+)\.xml',n) else 0)
                return '\n\n'.join(n+': '+' '.join(t.text or '' for t in ET.fromstring(archive.read(n)).iter() if t.tag.endswith('}t')) for n in names)
        if path.suffix.lower()=='.pdf':
            return subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True,timeout=30)
        raise ValueError('当前检查器不能读取此格式的正文')

    def checklist(self, stage):
        plan=read(self.course.plan_file); req=self.requirements_for(stage); items=[]
        mode=self.arrangement();user_audio=stage in ['pilot','final'] and mode==blind.USER_AUDIO_ARRANGEMENT
        visual_audio=stage in ['pilot','final'] and mode in blind.VISUAL_ARRANGEMENTS
        def add(identifier,label,basis,method,critical=True,na=False):
            items.append(dict(id=identifier,label=label,basis=basis,required_method=method,critical=critical,allow_na=na))
        content_method='script_read' if stage in ['script','storyboard'] else 'source_and_script' if visual_audio else 'full_av'
        add('source-accuracy','内容准确与原件依据',[s['id'] for s in plan.get('sources',[])],'source_and_script' if stage in ['script','storyboard'] else 'source_and_frames' if visual_audio else 'source_and_media')
        add('audience-context','符合目标受众与实际工作情境',dict(audience=plan.get('audience'),task=plan.get('performance_task')),content_method)
        add('teaching-continuity','主线、概念解释与教学衔接',dict(units=[u['id'] for u in plan.get('units',[])],user_requirements=[r['id'] for r in req]),content_method)
        for obj in plan.get('objectives',[]):add('objective:'+str(obj['id']),'学习目标落实：'+str(obj.get('statement','')),obj,content_method)
        # Whether a demonstration/practice is needed is decided from this course's goals, not a fixed count.
        add('example-completeness','教学示例为完整示范，练习有对应反馈',dict(units=[u['id'] for u in plan.get('units',[])],assessments=plan.get('assessments')),content_method,na=True)
        for requirement in req:add(requirement['id'],requirement['text'],requirement,content_method)
        if stage in ['pilot','final']:
            add('media-binding','当前媒体文件与制作输入版本绑定',self.basis(stage).get('files'),'media_probe')
            add('visual-purpose','抽检静态画面的布局与角色教学关联','仅证明实际编码抽帧时间点的布局与外观，不证明连续动作','frames')
            add('continuous-av','配音、字幕、动作、节奏的连续视听一致性','必须连续检查当前实际视频和音轨；抽帧、波形、ASR均不能替代','full_av')
            add('ending','末句完整，结尾无多余人声或截断','当前编码末尾的实际声音与画面','full_av')
            add('duration','实际时长符合已确定限制',{k:plan.get(k) for k in ['constraints','duration','duration_minutes']},'media_probe')
            from production_preferences import load
            preferences=load(self.project)
            for key,value in preferences.get('choices',{}).items():
                if value not in [None,False,'off','none','disabled']:
                    add('preference:'+key,'已选制作偏好实际接入：'+key,dict(value=value,preferences=preferences),'encoded_audio' if key in ['sfx','sound','sound_effects'] else 'frames')
            if user_audio:
                for item in items:
                    if item['required_method'] in ['full_av','encoded_audio']:
                        item.update(required_method='user_listening',responsibility='user_audio',critical=False,allow_na=False)
                        item['label']+='；由用户完整播放当前全部媒体核验，AI不能代听或标记通过'
            elif mode==blind.PRODUCER_AUDIO_ARRANGEMENT:
                for item in items:
                    if item['required_method'] in ['full_av','encoded_audio']:
                        item.update(required_method='full_av',responsibility='producer_audio_unverified',critical=True,allow_na=False)
                        item['label']+='；未执行完整听审，不能以自动技术检查代替'
                add('audio-technical','当前视频字节的自动音轨技术检查，不代表听审','全流解码、非静音样本及流时长边界','automatic_audio_technical')
                items[-1]['responsibility']='producer_audio_technical'
        return items

    def _validate_packet_files(self, packet, expected_binding=None):
        blind.validate_packet(packet)
        mode=self.arrangement() if packet['stage'] in ['pilot','final'] else blind.DEFAULT_ARRANGEMENT
        if packet['review_contract']!=blind.contract(packet['stage'],mode):raise ValueError('盲审职责分工与当前课程明确选择不一致')
        if expected_binding is not None and packet['binding']!=expected_binding:raise ValueError('已冻结的盲审资料包或成果绑定被修改')
        stage=packet['stage']
        if stage=='script':current=blind.artifact_digest(self.script_input()['text'])
        elif stage=='storyboard':current=hashed(blind.storyboard_artifact(read(self.project/'storyboard.json',{})))
        else:
            hashes=self.artifact_hashes(stage);current=hashes[0] if len(hashes)==1 else None
        if packet['artifact_sha256']!=current:raise ValueError('盲审资料包不是当前阶段实际成果')
        for item in packet['allowed_artifacts']:
            if 'path' not in item:continue
            path=self.project/item['path']
            boundary=(self.project/'qa/ai-review'/packet['run_id']).resolve()
            if path.is_symlink() or not path.resolve().is_relative_to(boundary) or not path.is_file() or sha(path)!=item['sha256']:
                raise ValueError('盲审成果白名单路径或实际字节已改变')

    def packet(self, stage, run_id):
        state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run)
        if self._baseline_report(run):raise ValueError('本阶段盲审已完成一次；请读取制作端固定问题清单定向验收包')
        index=len(run['iterations'])
        if run.get('packet_index')==index and run.get('packet_path'):
            value=read(self.project/run['packet_path'])
            self._validate_packet_files(value,run.get('packet_binding'))
            return dict(ok=True,packet=value)
        folder=self.project/'qa/ai-review'/run_id/str(index).zfill(2);folder.mkdir(parents=True,exist_ok=True)
        arrangement=self.arrangement() if stage in ['pilot','final'] else blind.DEFAULT_ARRANGEMENT
        value=dict(protocol=blind.PROTOCOL,stage=stage,run_id=run_id,fingerprint=run['fingerprint'],
                   review_contract=blind.contract(stage,arrangement),checklist=blind.checklist(stage,arrangement),
                   evidence=dict(media=[],frames=[],limitations=blind.contract(stage,arrangement)['limitations']),allowed_artifacts=[])
        if stage=='script':
            text=self.script_input()['text'];digest=blind.artifact_digest(text)
            value.update(input=dict(text=text),artifact_sha256=digest)
            value['allowed_artifacts']=[dict(id='transcript',kind='transcript',sha256=digest)]
        elif stage=='storyboard':
            board=blind.storyboard_artifact(read(self.project/'storyboard.json',{}));digest=hashed(board)
            value.update(input=dict(storyboard=board),artifact_sha256=digest)
            value['allowed_artifacts']=[dict(id='storyboard',kind='storyboard',sha256=digest)]
        else:
            names=[name for name in self._stage_files(stage) if str(name).lower().endswith('.mp4')]
            if len(names)!=1:raise ValueError('每轮媒体盲审须绑定一个实际视频；多个片段请分别审阅，不能混入其他阶段成果')
            source=self.course.relative(names[0]);digest=sha(source);target=folder/'artifact.mp4'
            if source.is_symlink():raise ValueError('实际视频不能通过符号链接改变审阅范围')
            if not target.exists():shutil.copyfile(source,target)
            if sha(target)!=digest:raise FileExistsError('实际视频已在盲审取样期间改变，保留文件后重新审阅')
            value['artifact_sha256']=digest
            value['allowed_artifacts'].append(dict(id='video',kind='video',path=str(target.relative_to(self.project)),sha256=digest))
            try:
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(target)],timeout=30))
                seconds=float(probe['format']['duration'])
                media=dict(id='video',sha256=digest,duration=seconds,method='media_probe',streams=[{k:s.get(k) for k in ['codec_type','codec_name','width','height','sample_rate','channels']} for s in probe['streams']])
                if arrangement==blind.PRODUCER_AUDIO_ARRANGEMENT:media['audio_technical']=_audio_technical(target,digest,probe)
                value['evidence']['media'].append(media)
                times=sorted(set([0,min(1/float(__import__('fractions').Fraction(next(s for s in probe['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))['avg_frame_rate'])),seconds/2),max(0,seconds-2),max(0,seconds-.15)]+[round(seconds*i/12,3) for i in range(1,12)]))
                for number,second in enumerate(times):
                    frame=folder/('frame-'+str(number).zfill(2)+'.jpg')
                    from fractions import Fraction
                    from media_frames import main_video,extract
                    stream=main_video(target);fps=Fraction(stream['avg_frame_rate'])
                    frame_index=max(0,min(int(stream.get('nb_frames') or round(seconds*float(fps)))-1,int(second*fps)))
                    decoded=extract(target,frame_index,frame)
                    item=dict(id='frame-'+str(number).zfill(2),kind='frame',path=str(frame.relative_to(self.project)),sha256=sha(frame),parent_sha256=digest)
                    value['allowed_artifacts'].append(item)
                    value['evidence']['frames'].append(dict(id=item['id'],path=item['path'],sha256=item['sha256'],time=decoded['time'],decoded_frame=decoded['decoded_frame'],media_sha256=digest,method='frames'))
            except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
                # Error paths/details may contain unrelated paths; expose only the capability boundary.
                value['evidence']['limitations'].append('当前视频探测或抽帧未完成：'+type(error).__name__)
        blind.seal(value);self._validate_packet_files(value)
        atomic(folder/'packet.json',value)
        with self.locked():
            state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run)
            run.update(packet_path=str((folder/'packet.json').relative_to(self.project)),packet_index=index,packet_binding=value['binding'],checklist=value['checklist'])
            atomic(self.path,state)
        return dict(ok=True,packet=value)

    def _aggregate(self, run, state):
        report=copy.deepcopy(run.get('blind_report',{}))
        if not report:return dict(passed=False,items=[],blocking_ids=['independent-blind-review'])
        current=run['fingerprint'];items=report['items']
        producer=run.get('producer_report',{})
        if producer.get('fingerprint')==current:
            producer_items={item['id']:item for item in producer['items']}
            issues={item['id']:item for item in run.get('issue_ledger',[])}
            for item in items:
                issue=issues.get(item['id'])
                if issue and issue.get('acceptance_fingerprint')==current and issue.get('status')=='resolved':
                    item.update(verdict='通过',reason='制作端已按固定问题清单核验当前成果；原始盲审意见保留',evidence=copy.deepcopy(issue.get('acceptance_evidence',[])),resolution_scope='producer_targeted_acceptance')
                elif report.get('fingerprint')!=current and item.get('verdict')=='通过':
                    item['baseline_only']=True
            items.extend(copy.deepcopy(producer['items']))
        else:items.append(dict(id='producer-source-qa',label='制作端原件、用户要求与目标私有核验',critical=True,verdict='无法验证',reason='等待绑定制作代理单独核对；不向盲审者披露',evidence=[]))
        supervisor=run.get('supervisor_report',{})
        operation=state.get('supervision',{}).get('operations',{}).get(run.get('supervision_operation_id'),{})
        supervisor_current=supervisor.get('fingerprint',current)==current and supervisor.get('passed') is True
        if operation:
            operation_report=operation.get('report',{})
            supervisor_current=supervisor_current and operation_report.get('binding')==operation.get('binding') and operation_report.get('passed') is True and operation.get('phase')=='end'
        items.append(dict(id='independent-supervision',label='独立侦探监督执行及用户指令遵守',critical=True,verdict='通过' if supervisor_current else '无法验证',reason=supervisor.get('summary') or '缺少当前执行的独立监督记录',evidence=[dict(agent_id=supervisor.get('agent_audit',{}).get('id'),binding=supervisor.get('binding'))] if supervisor else []))
        blocking=[i['id'] for i in items if i.get('critical') and i['verdict'] not in ['通过','不适用']]
        report.update(fingerprint=current,baseline_fingerprint=run.get('blind_report',{}).get('fingerprint'),binding=self._acceptance_binding(run),issue_ledger=copy.deepcopy(run.get('issue_ledger',[])),acceptance_mode=run.get('acceptance_mode','initial'),items=items,passed=not blocking,blocking_ids=blocking,producer_qa=copy.deepcopy(producer),supervision=copy.deepcopy(supervisor),
                      root_cause=producer.get('root_cause',''),next_step=producer.get('next_step',''))
        if self.arrangement(state)==blind.USER_AUDIO_ARRANGEMENT and run.get('stage') in ['pilot','final']:
            report.update(ai_responsibility_passed=not blocking,user_audio_pending=True,
                          pending_user_checks=[item['id'] for item in items if item.get('responsibility')=='user_audio'])
        elif self.arrangement(state)==blind.PRODUCER_AUDIO_ARRANGEMENT and run.get('stage') in ['pilot','final']:
            report.update(review_arrangement=blind.PRODUCER_AUDIO_ARRANGEMENT,user_audio_pending=False,
                          audio_review_scope=dict(user_audio_approval_required=False,continuous_listening_performed=False,
                              subjective_audio_status='not_evaluated',formal_audio_passed=False))
        return report

    def _frame_refs(self, refs, frames, inspected, sequence=False):
        located=[]
        for ref in refs:
            if not isinstance(ref,dict):continue
            match=next((frame for frame in frames if frame['sha256'] in inspected and frame['sha256']==ref.get('sha256') and frame['time']==ref.get('time') and type(ref.get('time')) in [int,float]),None)
            if match:located.append(match['time'])
        return len(located)>=2 and all(a<b for a,b in zip(located,located[1:])) if sequence else bool(located)

    def _storyboard_reference(self, ref, board):
        """Resolve an exact segment locator, then verify actual string leaves."""
        if not isinstance(ref,dict):return False
        if isinstance(ref.get('locator'),str) and ref['locator'].startswith('input.storyboard.navigation'):
            return blind.storyboard_reference(ref,board)
        segments=[s for s in board.get('segments',[]) if isinstance(s,dict) and isinstance(s.get('id'),str) and s['id']]
        if 'segment_id' in ref:matches=[s for s in segments if s['id']==ref['segment_id']]
        else:
            locator=ref.get('locator')
            if not isinstance(locator,str):return False
            matches=[s for s in segments if locator==s['id'] or locator.startswith(s['id']+'.')]
        if len(matches)!=1:return False
        segment=matches[0];quote=ref.get('quote')
        if quote is not None and not isinstance(quote,str):return False
        def leaves(value):
            if isinstance(value,str):yield value
            elif isinstance(value,dict):
                for child in value.values():yield from leaves(child)
            elif isinstance(value,list):
                for child in value:yield from leaves(child)
        if quote and not any(quote in value for value in leaves(segment)):return False
        resolved=dict(ref,segment_id=segment['id']);resolved.pop('quote',None)
        if resolved.get('beat') or 'time' in resolved:return blind.storyboard_reference(resolved,board)
        return bool(quote)

    def submit(self, stage, run_id, result):
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id);self._current(stage,run)
            if self._baseline_report(run):raise ValueError('本阶段只接受一次盲审报告；后续只处理固定问题清单')
            if run.get('packet_index')!=len(run['iterations']):raise ValueError('本轮盲审已经提交，不能重复替换结论')
            packet=read(self.project/run['packet_path']);self._validate_packet_files(packet,run.get('packet_binding'));blind.validate_result(result,packet)
            agent=blind.validate_audit(result.get('agent_audit'),'reviewer',run.get('producer'),state.get('route'),run.get('supervisor_report',{}).get('agent_audit'))
            self._actual_call(run,agent)
            self._distinct_scope(state,agent)
            for n in state['nodes'].values():
                for old in n.get('runs',[]):
                    for iteration in old.get('iterations',[]):
                        prior=iteration.get('report',{}).get('agent_audit',{})
                        if prior.get('role')=='reviewer' and (prior.get('id')==agent['id'] or prior.get('session_id')==agent['session_id']):raise ValueError('每个阶段及更新后的成果必须创建新的独立审阅代理')
            for operation in state.get('supervision',{}).get('operations',{}).values():
                other=operation.get('report',{}).get('agent_audit',{})
                if other and (other.get('id')==agent['id'] or other.get('session_id')==agent['session_id']):raise ValueError('审阅者与侦探监督者不能共用身份')
            methods={'script_read'} if stage=='script' else {'storyboard_read'} if stage=='storyboard' else {'media_probe'} if packet['evidence']['media'] else set()
            frames=set(result.get('inspected_frame_hashes',[]));actual={f['sha256'] for f in packet['evidence']['frames']}
            if frames and frames.issubset(actual.intersection(run.get('sent_frames',[]))):methods.add('frames')
            if 'frames' in methods and len({f['time'] for f in packet['evidence']['frames'] if f['sha256'] in frames})>=2:methods.add('frame_sequence')
            if packet['evidence']['media'] and all(m.get('audio_technical') for m in packet['evidence']['media']):methods.add('automatic_audio_technical')
            supplied={i.get('id'):i for i in result['items'] if isinstance(i,dict)};items=[]
            text=packet.get('input',{}).get('text','')
            board=packet.get('input',{}).get('storyboard',{})
            for check in packet['checklist']:
                item=supplied.get(check['id'],{});verdict=item.get('verdict','无法验证');reason=str(item.get('reason','')).strip();refs=item.get('evidence',[])
                if verdict not in VERDICTS:verdict='无法验证';reason='审阅未返回有效结论'
                if not isinstance(refs,list):refs=[]
                if check.get('responsibility')=='user_audio':
                    items.append(dict(check,verdict='待用户听审',reason='当前分工仅授权AI文字与画面检查；须由用户完整播放当前全部媒体，音轨及音画配合尚未在AI报告中核验',evidence=[]));continue
                if check.get('responsibility')=='producer_audio_unverified':
                    items.append(dict(check,verdict='无法验证',reason='本课配音免用户人工审核；当前能力未执行连续听审，声音、末句和连续音画配合尚未核验，自动技术检查不能替代',evidence=[]));continue
                if check.get('responsibility')=='producer_audio_technical':
                    items.append(_automatic_audio_item(check,packet['evidence']['media']));continue
                if verdict=='不适用' and (not check.get('allow_na') or not reason):verdict='无法验证';reason='必检项不能无依据标记不适用'
                if verdict=='通过':
                    if check['required_method'] not in methods:verdict='无法验证';reason='缺少所需实际检查能力或证据：'+check['required_method']
                    elif not refs:verdict='无法验证';reason='缺少当前成果中可定位的证据'
                    elif stage=='script':
                        quotes=[r.get('quote','') for r in refs if isinstance(r,dict)]
                        if not any(q and q in text for q in quotes):verdict='无法验证';reason='证据未引用当前实际逐字稿'
                        elif check['id']=='example-completeness' and not any(q in text and substantive_example(q) for q in quotes):verdict='需修改';reason='示例只是字段、标题或空表，未给出完整示范'
                    elif stage=='storyboard':
                        if not any(self._storyboard_reference(r,board) for r in refs):verdict='无法验证';reason='分镜结论缺少实际片段和原句、时间或节拍定位'
                    elif check['required_method'] in ['frames','frame_sequence']:
                        if not self._frame_refs(refs,packet['evidence']['frames'],frames,check['required_method']=='frame_sequence'):verdict='无法验证';reason='画面结论缺少已提交实际帧、准确时间码或递增帧序列'
                    elif check['required_method']=='media_probe' and not any(isinstance(r,dict) and any(m['sha256']==r.get('sha256') for m in packet['evidence']['media']) for r in refs):verdict='无法验证';reason='技术结论缺少当前视频的实际探测绑定'
                    if verdict=='通过' and check['id']=='visual-ending' and not any(isinstance(r,dict) and r.get('time')==max(f['time'] for f in packet['evidence']['frames']) and self._frame_refs([r],packet['evidence']['frames'],frames) for r in refs):verdict='无法验证';reason='画面结尾检查须引用已提交的实际末尾帧'
                    if verdict=='通过' and check['id']=='media-technical' and not all({'video','audio'}<=set(s.get('codec_type') for s in m['streams']) and m['duration']>0 for m in packet['evidence']['media']):verdict='无法验证';reason='当前探测未证明具有有效的音视频流与时长'
                items.append(dict(check,verdict=verdict,reason=reason or '未提供依据',evidence=refs))
            for finding in result['findings']:
                refs=finding['evidence']
                if stage=='script':located=any(isinstance(r,dict) and r.get('quote') and r['quote'] in text for r in refs)
                elif stage=='storyboard':located=any(self._storyboard_reference(r,board) for r in refs)
                else:located=any(isinstance(r,dict) and r.get('sha256') in frames and any(f['sha256']==r.get('sha256') and f['time']==r.get('time') for f in packet['evidence']['frames']) for r in refs)
                if not located and stage!='storyboard':raise ValueError('盲审问题缺少当前成果的原句、片段节拍或已提交实际帧时间码')
                items.append(dict(id='finding:'+finding['id'],label='独立学员发现的问题',critical=finding.get('severity','blocking')!='advisory',verdict='需修改' if located else '无法验证',
                                  reason=finding['problem'] if located else finding['problem']+'；分镜证据未匹配当前片段的真实原句、时间或节拍，须由制作代理独立核验，不能据此放行或直接当真。',evidence=refs))
            blocking=[i['id'] for i in items if i['critical'] and i['verdict'] not in ['通过','不适用']]
            report=dict(protocol=blind.PROTOCOL,scope='blind-review',at=now(),fingerprint=run['fingerprint'],binding=packet['binding'],
                        agent_audit=agent,learner=copy.deepcopy(result['learner']),findings=copy.deepcopy(result['findings']),items=items,
                        passed=not blocking,blocking_ids=blocking,summary=str(result.get('summary','')),methods=sorted(methods),limitations=packet['evidence']['limitations'],
                        inspection=dict(media=packet['evidence']['media'],frames=[f for f in packet['evidence']['frames'] if f['sha256'] in frames]))
            if packet['review_contract'].get('responsibilities'):
                report.update(responsibilities=copy.deepcopy(packet['review_contract']['responsibilities']),ai_responsibility_passed=not blocking,
                              user_audio_pending=self.arrangement(state)==blind.USER_AUDIO_ARRANGEMENT)
            previous=run.get('blind_report')
            if previous:
                old={i['id']:i['verdict'] for i in previous['items']};new={i['id']:i['verdict'] for i in items}
                node['no_improvement']=0 if any(old.get(k) in ['需修改','无法验证'] and v=='通过' for k,v in new.items()) else node['no_improvement']+1
            entry=dict(index=len(run['iterations']),report=report,proposed_repairs=[],at=now())
            if stage=='storyboard' or stage in ['pilot','final'] and self.arrangement(state) in blind.VISUAL_ARRANGEMENTS:entry['raw_result']=copy.deepcopy(result)
            run['iterations'].append(entry)
            run['blind_report']=report;self._freeze_issues(run,report);run.pop('producer_report',None);run.pop('supervisor_report',None);run['report']=self._aggregate(run,state)
            atomic(self.project/'qa/ai-review'/run_id/str(entry['index']).zfill(2)/'report.json',entry)
            self._event(run,'独立学员盲审已返回；交回制作代理核验原件并处理发现','rechecking');atomic(self.path,state)
        return dict(ok=True,report=run['report'],repairs=[],can_repair=False,needs_producer=True,limit_reached=False)

    def supervisor_submit(self, stage, run_id, result):
        with self.locked():
            state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run)
            blind.reject_writes(result)
            packet=read(self.project/run['packet_path'])
            if result.get('binding')!=self._acceptance_binding(run):raise ValueError('监督报告不属于当前实际成果与执行版本')
            agent=blind.validate_audit(result.get('agent_audit'),'supervisor',run.get('producer'),state.get('route'),run.get('blind_report',{}).get('agent_audit'))
            self._actual_call(run,agent)
            self._distinct_scope(state,agent)
            if not isinstance(result.get('findings'),list) or not isinstance(result.get('passed'),bool) or not str(result.get('summary','')).strip():raise ValueError('监督报告须返回发现、依据与实际执行结论')
            if result['passed'] and result['findings']:raise ValueError('监督发现尚未解决，不能标记通过')
            report=dict(binding=self._acceptance_binding(run),fingerprint=run['fingerprint'],agent_audit=agent,findings=result['findings'],summary=result['summary'],passed=result['passed'],at=now())
            run['supervisor_report']=report;run['report']=self._aggregate(run,state)
            if not report['passed']:state['hold']=dict(held=True,reason='独立监督发现执行或用户指令遵守问题：'+report['summary'],at=now(),source='supervisor',agent_id=agent['id'])
            atomic(self.project/'qa/ai-review'/run_id/'supervisor-report.json',report);atomic(self.path,state)
        return dict(ok=True,report=run['report'],passed=report['passed'],blocked=not report['passed'])

    def _producer_result_metadata(self, report):
        def short(value, limit):return str(value or '')[:limit]
        items=[]
        for item in report.get('items',[])[:80]:
            refs=item.get('evidence',[]) if isinstance(item.get('evidence'),list) else []
            quote_hashes=[]
            for ref in refs:
                if not isinstance(ref,dict):continue
                for key in ['quote','source_quote']:
                    if isinstance(ref.get(key),str) and ref[key]:quote_hashes.append(dict(kind=key,sha256=blind.artifact_digest(ref[key])))
            proof=item.get('evidence_validation')
            proof={k:proof[k] for k in ['status','script_quotes_checked','script_quotes_matched','source_quotes_checked','source_quotes_matched'] if k in proof} if isinstance(proof,dict) else None
            items.append(dict(id=short(item.get('id'),160),label=short(item.get('label'),180),required_method=item.get('required_method'),
                              verdict=item.get('verdict'),reason=short(item.get('reason'),400),evidence_count=len(refs),quote_hashes=quote_hashes[:12],
                              evidence_validation=copy.deepcopy(proof) if proof else dict(status='not_recorded'),quote_hashes_omitted=max(0,len(quote_hashes)-12)))
        inspection=report.get('inspection',{})
        sources=[dict(id=short(s.get('id'),120),sha256=s.get('sha256'),error=short(s.get('error'),400) if s.get('error') else None,truncated=s.get('truncated')) for s in inspection.get('sources',[])[:64]]
        return dict(passed=report.get('passed') is True,blocking_ids=copy.deepcopy(report.get('blocking_ids',[])),
                    report_sha256=hashed(report) if report else None,summary=short(report.get('summary'),1200),methods=copy.deepcopy(report.get('methods',[])),
                    items=items,item_count=len(report.get('items',[])),items_omitted=max(0,len(report.get('items',[]))-80),
                    inspection=dict(script_sha256=inspection.get('script',{}).get('sha256'),sources=sources,source_count=len(inspection.get('sources',[])),
                                    sources_omitted=max(0,len(inspection.get('sources',[]))-64),media=[{k:m.get(k) for k in ['sha256','duration','method']} for m in inspection.get('media',[])[:8]],
                                    frame_count=len(inspection.get('frames',[]))),
                    validation_scope='引文匹配及证据计数仅登记已有核验，不提升原结论，也不证明连续视听。旧报告未记录的验证计数保持未记录。')

    def _supervision_next_action(self, stage, node, run, policy):
        producer=run.get('producer_report',{});blind_report=run.get('blind_report',{})
        blocked=bool(run.get('report',{}).get('blocking_ids',[])) and any(item.get('critical') and item.get('id')!='independent-supervision' and item.get('verdict') not in ['通过','不适用'] for item in run.get('report',{}).get('items',[]))
        repairs=run.get('iterations',[{}])[-1].get('proposed_repairs',[]) if run.get('iterations') else []
        if blocked:
            repair=bool(repairs) and not run.get('repair_batch_used',False) and (run.get('acceptance_mode')!='targeted' or run.get('targeted_repair_authorized') is True) and not self._count_blocked(policy,'max_repairs',node.get('repairs',0)) and not self._count_blocked(policy,'max_calls',node.get('calls',0))
            kind='repair' if repair else 'blocked'
            reason='当前内容核验有阻断，准备由绑定制作代理集中修复后按固定问题清单定向验收；不再盲审。' if repair else '当前内容核验有阻断且本轮没有可执行返修或已达预算；保留未通过结论并结束本轮，不放行当前成果。'
        else:kind='finish';reason='当前盲审与制作端核验已完成，监督后结束本轮并沿用原有确认契约；监督不代替用户批准。'
        return dict(kind=kind,stage=stage,reason=reason,course_release_authorized=False,stage_advance_authorized=False,
                    content_block_is_execution_failure=False,proposed_repair_count=len(repairs))

    def _supervision_packet(self, state, operation):
        packet=dict(protocol='course-execution-supervision/1',operation_id=operation['operation_id'],producer=operation['producer'],
                    requirements=copy.deepcopy(state['requirements']),execution=copy.deepcopy(operation['events']),
                    phase=operation['phase'],stage=operation.get('stage'),capabilities=blind.CAPABILITIES,
                    review_contract=dict(role='supervisor',read_only=True,scope='观察实际执行、指令遵守、代理职责隔离、模型通道及能力边界；只返回可定位发现，不生产、不改稿、不执行修复、不代用户确认'))
        packet.update(self._requirement_context(operation.get('stage'),state['requirements']),requirement_applicability=REQUIREMENT_APPLICABILITY)
        packet.update(self._arrangement_context(state))
        packet['binding']=dict(protocol=packet['protocol'],operation_id=operation['operation_id'],execution_sha256=hashed(packet),
                               artifact_fingerprints=copy.deepcopy(operation.get('artifact_fingerprints',{})))
        node=state['nodes'].get('supervision',{});policy=self._policy(state,node)
        # Budget authorization is read-only context, not a content/execution fingerprint.
        packet['budget']=dict(ledger='supervision',calls_used=node.get('calls',0),max_calls=policy.get('max_calls'),repairs_used=node.get('repairs',0),max_repairs=policy.get('max_repairs'),
                              usage=copy.deepcopy(node.get('usage',{})),unlimited_counts=policy['unlimited_counts'],
                              calls_remaining=self._count_remaining(policy,'max_calls',node.get('calls',0)),repairs_remaining=self._count_remaining(policy,'max_repairs',node.get('repairs',0)),
                              **self._count_authorization_metadata(state,operation.get('stage')))
        packet.update(self._producer_timeout_metadata(state))
        return packet

    def production_event(self, producer, operation_id, phase, stage=None, execution=None):
        if not isinstance(producer,dict) or producer.get('role')!='producer' or not producer.get('id') or not producer.get('session_id'):raise ValueError('生产监督须绑定实际制作代理')
        if not isinstance(operation_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',operation_id) or phase not in ['start','progress','failure','end']:raise ValueError('生产监督操作或阶段无效')
        if stage is not None and stage not in [*STAGES,'outline','design','production','courseware','style']:raise ValueError('生产监督课程阶段无效')
        safe=[]
        for item in execution or []:
            keys={'phase','stage','status','tool','operation','artifact_sha256','error','agent_id','role','capabilities','observed_at','route','invocation_id','call_key','read_only','isolated','artifact_ids','seq','time','type','call_id','name','kind','label','failed','exit_code','job_id','job_status','turn','step','tools','user_instruction','evidence'}
            if not isinstance(item,dict) or set(item)-keys:raise ValueError('生产监督只接收已提交的执行事实，不接收素材正文、堆栈或计划内容')
            if item.get('route') is not None:blind.route(item['route'])
            item=copy.deepcopy(item)
            for key,value in item.items():
                if key=='route':continue
                if key=='evidence':
                    item[key]=_execution_evidence(value,item.get('type'),item.get('name'));continue
                if key in ['capabilities','artifact_ids','tools']:
                    if not isinstance(value,list) or any(not isinstance(v,str) for v in value):raise ValueError('监督执行列表只能包含标识，不能包含原始参数或正文')
                elif value is not None and type(value) not in [str,int,float,bool]:raise ValueError('监督执行事件不能嵌入素材、命令或原始工具参数')
                if isinstance(value,str) and len(value)>(8000 if key=='user_instruction' else 2000):raise ValueError('监督执行事件过长，不接收原始正文或堆栈')
            safe.append(item)
        with self.locked():
            state=self.load()
            operations=state.setdefault('supervision',{}).setdefault('operations',{})
            operation=operations.get(operation_id)
            created=operation is None;digest=hashed(dict(phase=phase,stage=stage,execution=safe))
            if operation is not None:
                if operation['producer']!=producer:raise ValueError('生产监督操作已绑定其他制作代理')
                if phase=='start':
                    initial=next((event for event in operation['events'] if event.get('phase')=='start'),None)
                    if not initial or initial.get('event_sha256')!=digest:raise ValueError('生产请求ID已绑定不同的阶段或派发指令，不能覆盖或重启')
                    return dict(ok=True,started=False,supervision=copy.deepcopy(operation))
            if phase in ['start','progress']:self._unheld(state)
            if not operation:
                if phase!='start':raise ValueError('须先登记实际生产开始事件')
                operation=dict(operation_id=operation_id,producer=copy.deepcopy(producer),phase=phase,stage=stage,events=[],calls=[],usage={},at=now())
                operations[operation_id]=operation
            if digest not in [e.get('event_sha256') for e in operation['events']]:
                if operation['phase']=='end':raise ValueError('已结束的生产操作不能被追加或重写')
                operation['events'].append(dict(at=now(),phase=phase,stage=stage,execution=safe,event_sha256=digest))
                if phase=='start':
                    request=next((item for item in safe if item.get('type')=='production/request'),None)
                    if request:
                        scope='source-coverage' if request.get('operation')=='source-coverage' else 'production'
                        state['production_scope']=dict(operation_id=operation_id,scope=scope,auto_review=scope!='source-coverage',stage=stage,at=now(),request_sha256=hashed(request))
                operation.update(phase=phase,stage=stage or operation.get('stage'),artifact_fingerprints={s:self.fingerprint(s) for s in STAGES if self.candidate(s)})
                packet=self._supervision_packet(state,operation);operation['binding']=packet['binding']
                operation.pop('report',None)
                atomic(self.project/'qa/ai-supervision'/operation_id/'execution.json',operation)
                atomic(self.path,state)
        return dict(ok=True,started=created,supervision=copy.deepcopy(operation))

    def supervisor_packet(self, stage=None, run_id=None, operation_id=None):
        state=self.load()
        if operation_id:
            operation=state.get('supervision',{}).get('operations',{}).get(operation_id)
            if not operation:raise ValueError('没有实际生产监督操作')
            packet=self._supervision_packet(state,operation)
            if packet['binding']!=operation['binding']:raise ValueError('生产监督依据已改变，请登记当前执行事件')
            return dict(ok=True,packet=packet)
        node,run=self._find(state,stage,run_id);self._current(stage,run)
        if not run.get('blind_report') or not run.get('producer_report'):raise ValueError('监督报告须先接收本轮独立审阅与制作端实际执行记录')
        packet=read(self.project/run['packet_path'])
        operation=state.get('supervision',{}).get('operations',{}).get(run.get('supervision_operation_id'),{})
        policy=self._policy(state,node)
        value=dict(protocol='course-execution-supervision/1',binding=self._acceptance_binding(run),stage=stage,producer=run['producer'],
                    requirements=copy.deepcopy(state['requirements']),execution=copy.deepcopy(run['events']),
                    calls=[{k:c.get(k) for k in ['key','status','role','route','agent_audit','error']} for c in run['calls']],
                    reviewer_audit=run['blind_report']['agent_audit'],producer_audit=run['producer_report']['agent_audit'],
                    review_result=dict(passed=run['blind_report']['passed'],blocking_ids=run['blind_report']['blocking_ids'],capabilities=blind.CAPABILITIES),
                    producer_result=self._producer_result_metadata(run['producer_report']),
                    next_action=self._supervision_next_action(stage,node,run,policy),
                    budget=dict(calls_used=node.get('calls',0),max_calls=policy.get('max_calls'),repairs_used=node.get('repairs',0),max_repairs=policy.get('max_repairs'),usage=copy.deepcopy(node.get('usage',{})),
                                unlimited_counts=policy['unlimited_counts'],calls_remaining=self._count_remaining(policy,'max_calls',node.get('calls',0)),repairs_remaining=self._count_remaining(policy,'max_repairs',node.get('repairs',0))),
                    current_run=dict(id=run['id'],stage=stage,started_at=run.get('started_at'),at=run.get('at'),status=run['status'],route=copy.deepcopy(state.get('route')),hold=copy.deepcopy(state.get('hold',{}))),
                    supervision_scope='只认证本轮当前阶段的实际执行与已登记核验；未附入包的历史安装、升级、冷启动或未来节点记录不被认证为全部已通过。',
                    production_supervision=copy.deepcopy(operation.get('report')),
                    review_contract=dict(role='supervisor',read_only=True,scope='只监督真实执行、用户要求、盲审隔离、能力与通道遵守；内容发现及blocked/repair计划不是执行失败，不修改、不代用户确认'))
        value.update(self._requirement_context(stage,state['requirements']),requirement_applicability=REQUIREMENT_APPLICABILITY)
        value.update(self._arrangement_context(state))
        value['user_audio_review']=self._audio_review(stage,state)
        value['budget'].update(self._count_authorization_metadata(state,stage))
        timeout_metadata=self._producer_timeout_metadata({})
        private=read(self.project/run['producer_packet_path'],{}) if run.get('producer_packet_path') else {}
        timeout_metadata.update({k:copy.deepcopy(private[k]) for k in timeout_metadata if k in private})
        value.update(timeout_metadata)
        return dict(ok=True,packet=value)

    def reserve_supervision_call(self, operation_id, key, route, role='supervisor'):
        blind.route(route)
        if role!='supervisor':raise ValueError('生产监督调用只能由独立侦探监督代理执行')
        with self.locked():
            state=self.load();self._unheld(state)
            operation=state.get('supervision',{}).get('operations',{}).get(operation_id)
            if not operation:raise ValueError('没有实际生产监督操作')
            prior=next((c for c in operation['calls'] if c['key']==key),None)
            if prior:return dict(ok=True,reserved=False,call=prior)
            node=self._node(state,'supervision');policy=self._policy(state,node)
            if self._count_blocked(policy,'max_calls',node['calls']) or policy.get('max_tokens') is not None and node['usage'].get('totalTokens',0)>=policy['max_tokens']:raise ValueError('累计监督预算已到上限，保留历史；须明确追加授权')
            if policy.get('max_tokens') is not None and any(blind.usage_unknown(c) for op in state['supervision']['operations'].values() for c in op['calls']):raise ValueError('已有监督用量未返回，无法核对累计token预算')
            pinned=state.get('route')
            if pinned and pinned!=route:raise ValueError('模型或计费通道已改变，停止监督调用')
            state['route']=route;call=dict(key=key,role=role,route=route,status='reserved',at=now(),binding=operation['binding'])
            operation['calls'].append(call);node['calls']+=1;atomic(self.path,state)
        return dict(ok=True,reserved=True,call=call)

    def supervision_call_result(self, operation_id, key, usage=None, error=None, agent_audit=None, execution_phase=None, model_invoked=None):
        with self.locked():
            state=self.load();operation=state.get('supervision',{}).get('operations',{}).get(operation_id)
            if not operation:raise ValueError('没有实际生产监督操作')
            call=next((c for c in operation['calls'] if c['key']==key),None)
            if not call:raise ValueError('监督调用尚未登记')
            if call.get('status')!='reserved':return dict(ok=True)
            outcome=blind.call_completion(error,usage,agent_audit,execution_phase,model_invoked)
            if agent_audit is not None:call['agent_audit']=blind.validate_audit(agent_audit,'supervisor',operation['producer'],call['route'],allow_uninvoked=outcome['failure_kind']=='preflight')
            call.update(outcome,completed_at=now())
            node=self._node(state,'supervision')
            for k,v in (usage or {}).items():
                if isinstance(v,(float,int)) and not isinstance(v,bool):
                    node['usage'][k]=node['usage'].get(k,0)+max(0,v);operation['usage'][k]=operation['usage'].get(k,0)+max(0,v)
            atomic(self.path,state)
        return dict(ok=True)

    def production_supervisor_submit(self, operation_id, result):
        with self.locked():
            state=self.load();self._unheld(state);operation=state.get('supervision',{}).get('operations',{}).get(operation_id)
            if not operation:raise ValueError('没有实际生产监督操作')
            blind.reject_writes(result)
            if result.get('binding')!=operation['binding']:raise ValueError('监督报告不属于当前生产执行版本')
            audit=blind.validate_audit(result.get('agent_audit'),'supervisor',operation['producer'],state.get('route'))
            self._actual_call(operation,audit)
            self._distinct_scope(state,audit)
            for node in state['nodes'].values():
                for run in node.get('runs',[]):
                    for iteration in run.get('iterations',[]):
                        reviewer=iteration.get('report',{}).get('agent_audit',{})
                        if reviewer and (reviewer.get('id')==audit['id'] or reviewer.get('session_id')==audit['session_id']):raise ValueError('侦探监督不能兼任成果盲审')
            if not isinstance(result.get('passed'),bool) or not isinstance(result.get('findings'),list) or not str(result.get('summary','')).strip():raise ValueError('监督报告格式无效')
            if result['passed'] and result['findings']:raise ValueError('监督仍有发现，不能标记通过')
            report=dict(binding=operation['binding'],passed=result['passed'],findings=result['findings'],summary=result['summary'],agent_audit=audit,at=now())
            operation['report']=report;operation.setdefault('reports',[]).append(copy.deepcopy(report))
            if not report['passed']:state['hold']=dict(held=True,reason='独立监督发现执行或用户指令遵守问题：'+report['summary'],at=now(),source='supervisor',agent_id=audit['id'])
            atomic(self.project/'qa/ai-supervision'/operation_id/'supervisor-report.json',report);atomic(self.path,state)
        return dict(ok=True,supervision=copy.deepcopy(operation),passed=report['passed'],blocked=not report['passed'])

    def producer_packet(self, stage, run_id):
        state=self.load();node,run=self._find(state,stage,run_id);self._current(stage,run)
        if stage=='script':self._script_preflight()
        iteration=run['iterations'][-1]['index'] if run['iterations'] else -1
        binding=self._acceptance_binding(run);attempt=run.get('producer_attempt',{})
        same=attempt.get('iteration')==iteration and attempt.get('fingerprint')==run['fingerprint'] and attempt.get('binding')==binding
        if same and attempt.get('packet_path'):
            self._producer_packet_record(stage,run,attempt['packet_path'],attempt['packet_sha256'])
            return dict(ok=True,packet=read(self.project/attempt['packet_path']))
        attempt_id=attempt['id'] if same else uuid.uuid4().hex
        folder=self.project/'qa/ai-review'/run_id/('producer-'+str(len(run['iterations'])).zfill(2)+'-'+attempt_id);folder.mkdir(parents=True,exist_ok=True)
        script=self.script_input();sources=[];seen_source_pages={}
        for source in read(self.course.plan_file).get('sources',[]):
            try:
                path=self.course.relative(source['location']);cache=self.project/'work/ai-review-sources'/(sha(path)+'.txt');cache.parent.mkdir(parents=True,exist_ok=True)
                if not cache.exists():cache.write_text(self._source_text(path))
                text=cache.read_text();parts=[]
                for page in re.split(r'\n\n(?=ppt/slides/slide)',text):
                    locator,_,body=page.partition(': ');normalized=re.sub(r'[^\w\u4e00-\u9fff]','',body or page)
                    digest=hashed(normalized)
                    if normalized and digest in seen_source_pages:parts.append(locator+': 与 '+seen_source_pages[digest]+' 正文相同，合并读取。')
                    else:
                        parts.append(page)
                        if normalized:seen_source_pages[digest]=source['id']+' '+locator
                compact='\n\n'.join(parts)
                sources.append(dict(id=source['id'],path=source['location'],sha256=sha(path),text=compact if stage=='storyboard' else compact[:60000],truncated=stage!='storyboard' and len(compact)>60000,method='全部正文提取；相同页正文去重并保留来源；未检查嵌入图片'))
            except (ValueError,OSError,subprocess.SubprocessError,zipfile.BadZipFile) as error:sources.append(dict(id=source['id'],error=str(error)))
        script_evidence=dict(method='script_read',sha256=hashed(script['text']),sha256_semantics='json-serialized-text',
                             raw_text_sha256=hashlib.sha256(script['text'].encode('utf-8')).hexdigest(),json_text_sha256=hashed(script['text']),
                             current_source_file_sha256=None,current_source_file_matches_raw_text=None,range='全文，见 input.text')
        source_name=self.course.script().get('path')
        if source_name:
            try:
                source_file=self.course.relative(source_name)
                if source_file.is_file():
                    script_evidence['current_source_file_sha256']=hashlib.sha256(source_file.read_bytes()).hexdigest()
                    script_evidence['current_source_file_matches_raw_text']=script_evidence['current_source_file_sha256']==script_evidence['raw_text_sha256']
            except (ValueError,OSError):pass
        evidence=dict(script=script_evidence,sources=sources,media=[],frames=[],limitations=[])
        if stage in ['pilot','final']:
            frozen_technical={}
            if self.arrangement()==blind.PRODUCER_AUDIO_ARRANGEMENT and run.get('packet_path'):
                frozen=read(self.project/run['packet_path']);blind.validate_packet(frozen)
                if frozen.get('binding')!=run.get('packet_binding'):raise ValueError('已冻结盲审包被修改')
                frozen_technical={m['sha256']:copy.deepcopy(m['audio_technical']) for m in frozen['evidence']['media']
                                  if m.get('audio_technical',{}).get('schema')==_AUDIO_TECHNICAL_SCHEMA}
            artifacts=self._stage_files(stage)
            for name in artifacts:
                path=self.course.relative(name)
                if path.suffix.lower()=='.srt':evidence.setdefault('subtitles',[]).append(dict(path=name,sha256=sha(path),text=path.read_text()))
                if path.suffix.lower()!='.mp4':continue
                try:
                    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],timeout=30))
                    seconds=float(probe['format']['duration']);digest=sha(path)
                    media=dict(path=name,sha256=digest,duration=seconds,streams=[{k:s.get(k) for k in ['codec_type','codec_name','width','height','sample_rate','channels']} for s in probe['streams']],method='media_probe')
                    if self.arrangement()==blind.PRODUCER_AUDIO_ARRANGEMENT:
                        media['audio_technical']=frozen_technical[digest] if digest in frozen_technical else _audio_technical(path,digest,probe)
                        if sha(path)!=digest:raise ValueError('复用自动技术检查时视频字节已改变')
                    evidence['media'].append(media)
                    # Evidence scope is explicit. No frame set is labelled continuous video review.
                    times=sorted(set([0,min(1/float(__import__('fractions').Fraction(next(s for s in probe['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))['avg_frame_rate'])),seconds/2),max(0,seconds-2),max(0,seconds-.15)]+[round(seconds*i/12,3) for i in range(1,12)]))
                    for index,second in enumerate(times):
                        target=folder/(digest[:12]+'-'+str(index).zfill(2)+'.jpg')
                        from fractions import Fraction
                        from media_frames import main_video,extract
                        stream=main_video(path);fps=Fraction(stream['avg_frame_rate'])
                        frame_index=max(0,min(int(stream.get('nb_frames') or round(seconds*float(fps)))-1,int(second*fps)))
                        decoded=extract(path,frame_index,target)
                        evidence['frames'].append(dict(path=str(target.relative_to(self.project)),sha256=sha(target),time=decoded['time'],decoded_frame=decoded['decoded_frame'],media_sha256=digest,method='frames'))
                except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:evidence['limitations'].append('媒体解码未完成：'+str(error))
            evidence['limitations'].append('当前宿主适配器只提交文本与可读取图片；没有连续视频/音频理解能力。抽帧与ASR不能支持完整视听通过。')
        doc=None if stage=='storyboard' else read(self.project/'workbench.json',{})
        native=[]
        if stage in ['pilot','final']:
            for path in sorted((self.project/'native').glob('*.js')):
                if path.stat().st_size<=180000:native.append(dict(path=str(path.relative_to(self.project)),sha256=sha(path),text=path.read_text()))
        current_plan=read(self.course.plan_file)
        model_plan={k:current_plan.get(k) for k in ['title','audience','performance_task','objectives','units','assessments','decisions','constraints','source_fusion','user_direction','supplement_notes']}
        model_plan['units']=[{k:v for k,v in u.items() if k!='content_points'} for u in current_plan.get('units',[])]
        previous=node['runs'][-2] if len(node['runs'])>1 else {}
        previous_round=dict(id=previous.get('id'),fingerprint=previous.get('fingerprint'),reason=previous.get('reason'),
                            unresolved=[i for i in previous.get('report',{}).get('items',[]) if i['verdict'] in ['需修改','无法验证']])
        checks=self.checklist(stage)
        if run.get('acceptance_mode')=='targeted':
            issue_ids={item['id'] for item in run.get('issue_ledger',[])}
            invariants={'source-accuracy','media-binding','duration','audio-technical','continuous-av','ending'}
            # Fixed findings, factual/technical invariants and directly changed checks
            # replace the open-ended first-pass quality checklist.
            checks=[item for item in checks if item['id'] in issue_ids or item['id'] in invariants]
            known={item['id'] for item in checks}
            for issue in run.get('issue_ledger',[]):
                if issue['id'] not in known:
                    checks.append(dict(id=issue['id'],label=issue['acceptance_condition'],required_method=issue['required_method'],
                                       critical=issue['severity']=='blocking',allow_na=issue.get('allow_na',False),fixed_issue=True))
                    known.add(issue['id'])
        if run.get('had_repair_error'):checks.append(dict(id='repair-execution',label='返修执行或导出失败已由实际成果恢复',basis=run.get('error_history',[]),required_method='repair_execution',critical=True,allow_na=False))
        evidence['repair_execution']=dict(verified=bool(run.get('recovery_verified')),last_error=run.get('last_error'),history=run.get('error_history',[]))
        value=dict(protocol=blind.PRODUCER_PROTOCOL,role='producer',course_id=state['course_id'],course_path=str(self.course.root),stage=stage,run_id=run_id,fingerprint=run['fingerprint'],attempt_id=attempt_id,iteration=iteration,
                   checklist=checks,input=script,evidence=evidence,plan=model_plan,
                   sections=[{k:s.get(k) for k in ['unit_id','title']} for s in read(self.project/'studio-content.json',{}).get('sections',[])],document=doc if stage!='script' else None,native=native,
                   editable_files=[dict(path='source/transcript.md',sha256=hashlib.sha256(script['text'].encode()).hexdigest())]+([dict(path='workbench.json',sha256=sha(self.project/'workbench.json'),editable_fields=sorted(DOC_REPAIR_FIELDS),preserve_existing_media=True)] if stage!='script' else [])+[{k:f[k] for k in ['path','sha256']} for f in native],
                   instruction=run['instruction'],mode=run['mode'],prior=run['iterations'][-1:] or [],previous_round=previous_round,
                   repairs_remaining=self._count_remaining(self._policy(state,node),'max_repairs',node['repairs']),unlimited_counts=self._policy(state,node)['unlimited_counts'],
                   root_cause_required=root_cause_needed(node,run),protected={k:read(self.course.plan_file).get(k) for k in PROTECTED})
        from source_coverage import SourceCoverage
        value['source_coverage']=SourceCoverage(self.course).view()
        value['blind_report']=copy.deepcopy(run.get('blind_report'))
        value['binding']=copy.deepcopy(binding)
        value['acceptance_mode']=run.get('acceptance_mode','initial')
        value['targeted_repair_authorized']=bool(run.get('targeted_repair_authorized'))
        value['issue_ledger']=copy.deepcopy(run.get('issue_ledger',[]))
        value['review_cycle']=dict(scheme_id=run.get('scheme_id','initial-selected-scheme'),blind_review_limit=1,automatic_repair_batches=1,automatic_acceptance_passes=1)
        if stage in ['pilot','final']:
            value.update(self._arrangement_context(state))
            value['user_audio_review']=self._audio_review(stage,state)
        value.update(self._producer_timeout_metadata(state))
        if stage=='storyboard':
            value['storyboard']=read(self.project/'storyboard.json',{})
            value['editable_files']=[dict(path='storyboard.json',sha256=sha(self.project/'storyboard.json'))]
            value['plan']=copy.deepcopy(current_plan)
            archived={}
            for key in ['source_items','revision_context_history']:
                if key in value['plan']:
                    data=json.dumps(value['plan'].pop(key),ensure_ascii=False,separators=(',',':')).encode('utf-8')
                    archived[key]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
            value['plan_archive_metadata']=dict(path=str(self.course.plan_file),sha256=sha(self.course.plan_file),archived_fields=archived,
                                               explanation='仅从本次QA输入移出重复来源整理账与旧修订历史；完整原档保留。当前units、全部content_points/source_refs及其他现行字段保留，原件全文另见evidence.sources。')
            for key in ['document','native','prior','previous_round','sections']:value.pop(key,None)
            production=read(self.course.state_file);script_node=self.node_view('script',state)
            value['confirmations']=dict(script={k:copy.deepcopy(script_node.get(k)) for k in ['passed','user_confirmed','content_confirmation_preserved','confirmation']},outline=copy.deepcopy(production.get('gates',{}).get('outline')),branch=copy.deepcopy(production.get('branch_receipt')))
            value['selections']=[{k:copy.deepcopy(s.get(k)) for k in ['id','selected','selection_receipt']} for s in value['storyboard'].get('segments',[])]
            from production_preferences import creative_basis
            value['production_preferences']=creative_basis(self.project)
            value['applicable_requirements']=self._requirement_context(stage,state['requirements'])['current_requirements']
            value['requirement_applicability']=REQUIREMENT_APPLICABILITY
            value['authorization_context']=dict(unlimited_counts=self._policy(state,node)['unlimited_counts'],**self._count_authorization_metadata(state,stage))
        target=folder/'producer-packet.json'
        if target.exists():raise FileExistsError('本次制作核验包已存在，不能覆盖原始资料包')
        atomic(target,value)
        # Frozen expected checks cannot be weakened by the model's response.
        with self.locked():
            state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run)
            path=str(target.relative_to(self.project));digest=sha(target)
            if run.get('producer_packet_path') and not any(p['path']==run['producer_packet_path'] for p in run.get('producer_packet_history',[])):
                prior_path=self.project/run['producer_packet_path']
                if prior_path.is_file():run.setdefault('producer_packet_history',[]).append(dict(path=run['producer_packet_path'],sha256=sha(prior_path),legacy_import=True,at=now()))
            record=dict(path=path,sha256=digest,attempt_id=attempt_id,iteration=iteration,fingerprint=run['fingerprint'],binding_sha256=hashed(binding),at=now())
            run.setdefault('producer_packet_history',[]).append(record)
            existing=run.get('producer_attempt',{})
            run['producer_attempt']=dict(existing if existing.get('id')==attempt_id else {},id=attempt_id,iteration=iteration,fingerprint=run['fingerprint'],binding=copy.deepcopy(binding),packet_path=path,packet_sha256=digest)
            run.update(producer_packet_path=path,producer_packet_sha256=digest,producer_checklist=value['checklist']);atomic(self.path,state)
        return dict(ok=True,packet=value)

    def producer_submit(self, stage, run_id, result):
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id);self._current(stage,run)
            if not self._baseline_report(run):raise ValueError('制作核验须先接收本选定方案的一次独立盲审发现')
            agent=blind.validate_audit(result.get('agent_audit'),'producer',run.get('producer'),state.get('route'))
            self._actual_call(run,agent)
            packet=read(self.project/run['producer_packet_path'])
            self._producer_packet_record(stage,run,run['producer_packet_path'],run.get('producer_packet_sha256'))
            if packet.get('fingerprint')!=run['fingerprint']:raise ValueError('制作核验资料已过期')
            if not packet.get('binding') or result.get('binding')!=packet['binding']:raise ValueError('制作端原件核验报告不属于当前成果或审阅协议版本')
            supplied={i.get('id'):i for i in result.get('items',[]) if isinstance(i,dict)};items=[]
            script=packet['input']['text'];methods={'script_read','source_and_script'}
            if stage=='storyboard':methods.add('storyboard_read')
            if run.get('recovery_verified'):methods.add('repair_execution')
            if packet['evidence']['media']:methods.add('media_probe')
            if packet['evidence']['media'] and all(m.get('audio_technical') for m in packet['evidence']['media']):methods.add('automatic_audio_technical')
            actual_call=next((call for call in reversed(run.get('calls',[])) if call.get('status')=='complete' and call.get('role')=='producer' and call.get('agent_audit')==agent and call.get('producer_packet_sha256')==run.get('producer_packet_sha256')), {})
            sent_frames=set(actual_call.get('sent_frames',[]))
            if packet['evidence']['frames'] and sent_frames and result.get('inspected_frame_hashes'):
                actual={f['sha256'] for f in packet['evidence']['frames']}
                if set(result['inspected_frame_hashes']).issubset(actual.intersection(sent_frames)):methods.add('frames')
            inspected=set(result.get('inspected_frame_hashes',[])) if 'frames' in methods else set()
            if 'frames' in methods:
                methods.add('source_and_frames')
                if len({f['time'] for f in packet['evidence']['frames'] if f['sha256'] in inspected})>=2:methods.add('frame_sequence')
            for check in packet['checklist']:
                item=supplied.get(check['id'],{});verdict=item.get('verdict','无法验证');reason=str(item.get('reason','')).strip();refs=item.get('evidence',[])
                if verdict not in VERDICTS:verdict='无法验证';reason='审阅没有返回有效结论'
                if check.get('responsibility')=='user_audio':
                    items.append(dict(check,verdict='待用户听审',reason='制作端保留声音与音画配合核验义务；当前AI能力不能代替用户完整播放当前全部媒体',evidence=[]));continue
                if check.get('responsibility')=='producer_audio_unverified':
                    items.append(dict(check,verdict='无法验证',reason='配音免用户人工审批；未执行连续听审，主观听感、末句、残音与连续音画配合仍未验证，不能由技术检测代替',evidence=[]));continue
                if check.get('responsibility')=='producer_audio_technical':
                    items.append(_automatic_audio_item(check,packet['evidence']['media']));continue
                if verdict=='不适用' and (not check.get('allow_na') or not reason):verdict='无法验证';reason='必检项不能无依据标记不适用'
                if verdict=='通过':
                    if check['required_method'] not in methods:verdict='无法验证';reason='缺少所需实际检查能力或证据：'+check['required_method']
                    elif not refs:verdict='无法验证';reason='缺少可核对的实际成果证据'
                    elif check['required_method'] in ['script_read','source_and_script','source_and_frames']:
                        quotes=[r.get('quote','') for r in refs if isinstance(r,dict)]
                        if not any(q and q in script for q in quotes):verdict='无法验证';reason='证据未引用本轮实际讲稿正文'
                        elif check['id']=='example-completeness' and not any(q in script and substantive_example(q) for q in quotes):verdict='需修改';reason='示例证据只是字段、标题或空表，未给出完整示范'
                    if check['required_method'] in ['frames','source_and_frames'] and not self._frame_refs(refs,packet['evidence']['frames'],inspected):verdict='无法验证';reason='制作端画面核验缺少已提交的实际帧与准确时间码'
                    if check['required_method']=='frame_sequence' and not self._frame_refs(refs,packet['evidence']['frames'],inspected,True):verdict='无法验证';reason='定向验收缺少实际当前帧序列及递增时间码'
                    if check['required_method']=='storyboard_read' and not any(self._storyboard_reference(ref,packet.get('storyboard',{})) for ref in refs):verdict='无法验证';reason='定向验收缺少当前已选分镜原句、片段或节拍定位'
                    if check['required_method']=='media_probe' and not any(isinstance(ref,dict) and any(media['sha256']==ref.get('sha256') for media in packet['evidence']['media']) for ref in refs):verdict='无法验证';reason='定向验收缺少当前实际媒体探测绑定'
                    if check['id']=='source-accuracy' and any(s.get('error') or s.get('truncated') for s in packet['evidence']['sources']):verdict='无法验证';reason='原始资料有未读取范围；不能宣称完整核验'
                    if check['id']=='source-accuracy' and verdict=='通过':
                        source_text={s['id']:s.get('text','') for s in packet['evidence']['sources'] if not s.get('error')}
                        if not any(isinstance(r,dict) and r.get('source_id') in source_text and r.get('locator') and r.get('source_quote') and r['source_quote'] in source_text[r['source_id']] for r in refs):verdict='无法验证';reason='缺少可回查的原始资料引文及其具体定位'
                    if check['id']=='media-binding':
                        stage_context=read(self.course.state_file).get(stage+'_context')
                        if self.script_input()['changed'] or stage_context!=self.course._video_context():verdict='需修改';reason='实际媒体的制作上下文与当前工程或最新讲稿不一致'
                evidence_refs=[r for r in refs if isinstance(r,dict)] if isinstance(refs,list) else []
                script_quotes=[r['quote'] for r in evidence_refs if isinstance(r.get('quote'),str) and r['quote']]
                source_refs=[r for r in evidence_refs if isinstance(r.get('source_quote'),str) and r['source_quote']]
                sources={s['id']:s.get('text','') for s in packet['evidence']['sources'] if not s.get('error')}
                validation=dict(status='recorded',script_quotes_checked=len(script_quotes),script_quotes_matched=sum(q in script for q in script_quotes),
                                source_quotes_checked=len(source_refs),source_quotes_matched=sum(bool(r.get('source_id') in sources and r.get('locator') and r['source_quote'] in sources[r['source_id']]) for r in source_refs))
                items.append(dict(check,verdict=verdict,reason=reason or '未提供结论依据',evidence=refs,evidence_validation=validation))
            blocking=[i for i in items if i['critical'] and i['verdict'] not in ['通过','不适用']]
            report=dict(at=now(),protocol=blind.PRODUCER_PROTOCOL,scope='producer',agent_audit=agent,fingerprint=run['fingerprint'],items=items,passed=not blocking,blocking_ids=[i['id'] for i in blocking],
                        summary=str(result.get('summary','')),next_step=str(result.get('next_step','')),root_cause=str(result.get('root_cause','')),
                        methods=sorted(methods),limitations=packet['evidence']['limitations'],
                        inspection=dict(script=packet['evidence']['script'],sources=[{k:s.get(k) for k in ['id','path','sha256','method','truncated','error']} for s in packet['evidence']['sources']],media=packet['evidence']['media'],frames=packet['evidence']['frames']))
            if stage in ['pilot','final'] and self.arrangement(state)==blind.USER_AUDIO_ARRANGEMENT:
                report.update(ai_responsibility_passed=not blocking,user_audio_pending=True,review_arrangement=blind.USER_AUDIO_ARRANGEMENT)
            elif stage in ['pilot','final'] and self.arrangement(state)==blind.PRODUCER_AUDIO_ARRANGEMENT:
                report.update(user_audio_pending=False,review_arrangement=blind.PRODUCER_AUDIO_ARRANGEMENT,
                              audio_review_scope=dict(user_audio_approval_required=False,continuous_listening_performed=False,subjective_audio_status='not_evaluated',formal_audio_passed=False))
            repairs=result.get('repairs',[])
            if not isinstance(repairs,list):repairs=[]
            if run.get('acceptance_mode')=='targeted':
                allowed_issues={item['id'] for item in packet['checklist']}
                repairs=[repair for repair in repairs if isinstance(repair,dict) and repair.get('issue_id') in allowed_issues]
            if root_cause_needed(node,run) and repairs and not report['root_cause'].strip():repairs=[];report['next_step']='连续两轮没有实质改善；先分析根因，再调整方法。'
            if run.get('acceptance_mode')!='targeted' and not run.get('issue_ledger_frozen'):
                self._freeze_issues(run,report,'producer');run['issue_ledger_frozen']=True
            current_items={item['id']:item for item in items}
            for issue in run.get('issue_ledger',[]):
                current=current_items.get(issue['id'],{})
                issue['status']='resolved' if current.get('verdict') in ['通过','不适用'] else 'open'
                issue['acceptance_fingerprint']=run['fingerprint'];issue['acceptance_evidence']=copy.deepcopy(current.get('evidence',[]))
                issue['acceptance_reason']=current.get('reason','尚无本问题的当前成果定向验收')
            entry=run['iterations'][-1]
            if entry.get('producer_report'):raise ValueError('本轮制作核验已提交，不能重复替换结论')
            if stage in ['pilot','final'] and self.arrangement(state) in blind.VISUAL_ARRANGEMENTS:entry['raw_producer_result']=copy.deepcopy(result)
            entry.update(producer_report=report,proposed_repairs=repairs,producer_at=now());run['producer_report']=report
            run['report']=self._aggregate(run,state)
            folder=self.project/'qa/ai-review'/run_id/str(entry['index']).zfill(2);atomic(folder/'report.json',entry)
            policy=self._policy(state,node)
            can_repair=bool(repairs) and not self._count_blocked(policy,'max_repairs',node['repairs']) and not run['report']['passed'] and not run.get('repair_batch_used',False) and (run.get('acceptance_mode')!='targeted' or run.get('targeted_repair_authorized') is True)
            self._event(run,'检查完成，'+('开始本轮局部返修' if can_repair else '准备审阅汇总'), 'repairing' if can_repair else 'rechecking')
            atomic(self.path,state)
            return dict(ok=True,report=run['report'],repairs=repairs if can_repair else [],can_repair=can_repair,limit_reached=bool(repairs) and self._count_blocked(policy,'max_repairs',node['repairs']))

    def repair(self, stage, run_id, repairs, producer_id=None):
        if stage!='script':
            from source_coverage import SourceCoverage
            SourceCoverage(self.course).require_confirmed()
        # Lock ordering is always course then review. Fingerprints include manual drafts.
        from script_editor import ScriptEditor
        from backend import document_lock
        editor=ScriptEditor(SimpleNamespace(root=self.course.root,project=self.project,file=self.project/'workbench.json'))
        with self.course.locked(), self.locked(), editor.locked(), document_lock(self.project):
            state=self.load();node,run=self._find(state,stage,run_id);self._current(stage,run)
            if not run.get('producer_report') or producer_id!=run.get('producer',{}).get('id'):raise ValueError('只有当前绑定制作代理可以执行返修；审阅者与监督者只读')
            if run.get('repair_batch_used',False) or run.get('acceptance_mode')=='targeted' and run.get('targeted_repair_authorized') is not True:raise ValueError('本次集中自动修复批次已使用；定向验收不再自动返修或盲审')
            policy=self._policy(state,node)
            if self._count_blocked(policy,'max_repairs',node['repairs']):raise ValueError('已到三轮或本次授权的自动返修上限')
            if not run['iterations'] or repairs != run['iterations'][-1]['proposed_repairs']:raise ValueError('返修必须对应本轮实际发现的问题')
            if root_cause_needed(node,run) and not run['report'].get('root_cause'):raise ValueError('连续无改善，须先分析根因')
            if run['iterations'][-1].get('repair_attempted'):raise ValueError('本轮返修已经执行，不能重复消耗')
            node['repairs']+=1;run['automatic_repair_batches_used']=run.get('automatic_repair_batches_used',0)+1;run['repair_batch_used']=True;run['targeted_repair_authorized']=False;run['iterations'][-1]['repair_attempted']=True;atomic(self.path,state)
            changes={};descriptions=[]
            for repair in repairs:
                if not isinstance(repair,dict):raise ValueError('返修格式无效')
                issue=repair.get('issue_id');allowed={i['id'] for i in run['report']['items'] if i['verdict'] in ['需修改','无法验证'] and i['id'] not in ['independent-supervision','producer-source-qa']}
                if issue not in allowed:raise ValueError('返修没有绑定未解决的检查项')
                path=self.course.relative(repair.get('path',''))
                rel=str(path.relative_to(self.project))
                if stage=='script' and rel!='source/transcript.md':raise ValueError('讲稿节点只能修改本轮讲稿，不能提前更改声音或画面')
                if stage=='storyboard' and rel!='storyboard.json':raise ValueError('分镜节点只能返修当前分镜，不能修改讲稿、声音或实际媒体')
                if rel not in ['source/transcript.md','storyboard.json','workbench.json'] and not (rel.startswith('native/') and path.suffix in ['.js','.json']):raise ValueError('返修超出内容、画面与同步范围；不能改验收标准、偏好或审阅结论')
                actual=self.script_input()['text'] if rel=='source/transcript.md' else path.read_text() if path.is_file() else ''
                actual_sha=hashlib.sha256(actual.encode()).hexdigest()
                if path.is_symlink() or rel!='source/transcript.md' and not path.is_file() or actual_sha!=repair.get('before_sha256'):raise FileExistsError('文件已被人工或其他任务修改，保留现状并重新审阅：'+rel)
                before=changes.get(path,actual);find=repair.get('find');replacement=repair.get('replace')
                if not isinstance(find,str) or not find or before.count(find)!=1 or not isinstance(replacement,str):raise ValueError('需要唯一、精确的原文和替换内容：'+rel)
                changes[path]=before.replace(find,replacement,1);descriptions.append(dict(issue_id=issue,path=rel,reason=repair.get('reason','')))
            if not changes:raise ValueError('没有实际可执行的修改')
            if self.project/'source/transcript.md' in changes:self._script_preflight(changes[self.project/'source/transcript.md'])
            # Validate the entire patch before touching any file.
            for path,text in changes.items():
                if path.suffix=='.json':
                    candidate=json.loads(text)
                    if path.name=='storyboard.json':
                        original=read(path)
                        if {k:v for k,v in candidate.items() if k!='segments'}!={k:v for k,v in original.items() if k!='segments'}:raise ValueError('分镜返修不能改变既定通道、规则、美术选择或来源绑定')
                        old_segments=original.get('segments',[]);new_segments=candidate.get('segments',[])
                        protected=['id','unit_id','source_paragraph_ids','script_excerpt','selected','selection_receipt']
                        if len(old_segments)!=len(new_segments) or any(any(a.get(k)!=b.get(k) for k in protected) for a,b in zip(old_segments,new_segments)):raise ValueError('分镜返修不能篡改原文、来源、顺序或已有实际选择')
                        from storyboard import check as check_storyboard
                        checked=check_storyboard(candidate,self.course.script()['text'],self.course.script_sha(),read(self.course.plan_file),reading_required=bool(read(self.project/'workbench.json',{}).get('readingPolicy',{}).get('required')))
                        if checked['errors']:raise ValueError('分镜返修结构或覆盖未通过：'+'；'.join(checked['errors']))
                    if path.name=='workbench.json':
                        from backend import validate
                        original=read(path)
                        if any(candidate.get(k)!=original.get(k) for k in set(original)|set(candidate) if k not in DOC_REPAIR_FIELDS):raise ValueError('不得更改已确认声音、制作通道或降低工程验收标准')
                        if any(candidate.get('media',{}).get(k)!=v for k,v in original.get('media',{}).items()):raise ValueError('不得替换已确定的配音或品牌媒体；只允许接入新的授权素材')
                        for key in ['revision','fps','title','productionPreferences','duration','audioSettings','rendering','storyboardBindings']:
                            if candidate.get(key)!=original.get(key):raise ValueError('不得擅改已确定时长、标题、制作偏好或渲染通道')
                        from timeline import duration
                        if duration(candidate)!=duration(original):raise ValueError('返修不能擅自改变已确定的成片时长')
                        validate(candidate,self.project)
                        candidate['revision']=original['revision']+1
                        changes[path]=json.dumps(candidate,ensure_ascii=False,indent=2)+'\n'
                if path.suffix=='.js':
                    check=subprocess.run(['node','--check','--input-type=module'],input=text,text=True,capture_output=True,timeout=15)
                    if check.returncode:raise ValueError('人物/画面修改有语法错误：'+check.stderr[-1500:])
            self._current(stage,run)
            folder=self.project/'qa/ai-review'/run_id/('repair-'+str(node['repairs']));folder.mkdir(parents=True,exist_ok=True)
            diffs=[]
            for path,text in changes.items():
                before=self.script_input()['text'] if path==self.project/'source/transcript.md' else path.read_text();rel=str(path.relative_to(self.project));backup=folder/rel;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(before)
                diffs.extend(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile=rel+' (before)',tofile=rel+' (after)'))
            (folder/'changes.diff').write_text(''.join(diffs));atomic(folder/'changes.json',descriptions)
            if self.project/'storyboard.json' in changes:self.course._snapshot(read(self.course.state_file))
            for path,text in changes.items():
                if path==self.project/'source/transcript.md':continue
                if path.name=='workbench.json':
                    original=read(path);atomic(self.project/'workbench-history'/f'{original["revision"]:06}.json',original)
                temporary=path.with_name(path.name+'.review-'+uuid.uuid4().hex);temporary.write_text(text);temporary.replace(path)
            # Keep the current editor/paragraph identities in sync without any user approval.
            if self.project/'source/transcript.md' in changes:
                from studio import blocks,compose,identity_map
                draft=editor.read();new=changes[self.project/'source/transcript.md']
                draft.update(text=new,revision=draft['revision']+1);editor.write(draft)
                content=read(self.project/'studio-content.json',{})
                if content.get('sections'):
                    headings=list(re.finditer(r'^##\s+.+$',new,re.M));sections=content['sections']
                    if len(headings)==len(sections):
                        for i,section in enumerate(sections):
                            section['body']=new[headings[i].end():headings[i+1].start() if i+1<len(headings) else len(new)].strip();section['paragraphs']=blocks(section['body'],section.get('paragraphs',[]))
                        content['revision']=content.get('revision',0)+1;atomic(self.project/'studio-content.json',content)
                course_state=read(self.course.state_file);course_state['narration_status']='needs_regeneration';self.course._commit(course_state,'ai_review_script_repaired',dict(run_id=run_id,paths=[str(p.relative_to(self.project)) for p in changes]))
            if self.project/'storyboard.json' in changes:
                from storyboard import export_html
                from production_preferences import record_storyboard
                export_html(read(self.project/'storyboard.json'),self.project/'storyboard.html')
                record_storyboard(self.project,'ai-review-producer-repair','绑定制作代理已依据当前独立发现返修分镜；不代表新增用户确认')
                course_state=read(self.course.state_file);self.course._commit(course_state,'ai_review_storyboard_repaired',dict(run_id=run_id,actor=producer_id,paths=['storyboard.json']))
            if node.get('approval'):node.setdefault('historical_approvals',[]).append(node.pop('approval'))
            run['repaired'].extend(descriptions)
            self._prepare_targeted(run,stage)
            if stage in ['script','storyboard']:self._resolve_errors(run,'updated-'+stage)
            self._event(run,'已保留修改前版本及差异；检查更新后的实际成果','rechecking',repair_round=node['repairs'])
            atomic(self.path,state)
            return dict(ok=True,rerender=stage in ['pilot','final'],fingerprint=run['fingerprint'],repair_round=node['repairs'])

    def _resolve_errors(self,run,scope):
        if not run.get('had_repair_error'):return
        run.pop('last_error',None);run['recovery_verified']=True
        for error in run.get('error_history',[]):
            if not error.get('resolved_by'):error.update(resolved_by=run['fingerprint'],resolution_scope=scope,resolved_at=now())

    def repair_error(self,stage,run_id,error):
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id)
            if run['status'] not in RUNNING or state.get('hold',{}).get('held') or run['fingerprint']!=self.fingerprint(stage):return dict(ok=True,retry=False,limit_reached=False)
            run.update(had_repair_error=True,last_error=str(error),recovery_verified=False)
            run.setdefault('error_history',[]).append(dict(at=now(),reason=str(error),repair_round=node['repairs']))
            policy=self._policy(state,node)
            retry=not self._count_blocked(policy,'max_repairs',node['repairs']) and not self._count_blocked(policy,'max_calls',node['calls'])
            self._event(run,'返修执行未完成：'+str(error)+'；'+('正在分析实际失败原因并调整局部方法' if retry else '达到累计上限，保留全部成果'),'rechecking')
            atomic(self.path,state)
        return dict(ok=True,retry=retry,limit_reached=not retry)

    def rebind_render(self, stage, run_id, expected_fingerprint):
        with self.locked():
            state=self.load();self._unheld(state);_,run=self._find(state,stage,run_id)
            if run['status']!='rendering':raise ValueError('本轮不在重新渲染阶段')
            if run['fingerprint']!=expected_fingerprint:raise FileExistsError('返修任务的输入版本已改变')
            # A render may only replace artifact files/context; all other inputs must be unchanged.
            before=run.get('render_basis')
            current=self.basis(stage)
            if before:
                if {k:v for k,v in before.items() if k!='files'} != {k:v for k,v in current.items() if k!='files'}:raise FileExistsError('重新渲染期间有人工修改，不能绑定旧审阅')
            old_media={f.get('sha256') for f in (before or {}).get('files',[]) if f['path'].lower().endswith('.mp4')}
            new_media={f.get('sha256') for f in current.get('files',[]) if f['path'].lower().endswith('.mp4')}
            if not before or not new_media or None in new_media or new_media==old_media:raise ValueError('尚未登记更新后的实际视频；不能用旧媒体完成返修复核')
            run['fingerprint']=hashed(current);self._resolve_errors(run,'updated-media');self._event(run,'更新后的实际媒体已生成，开始复核','rechecking');atomic(self.path,state)
        return dict(ok=True)

    def render_start(self,stage,run_id):
        from source_coverage import SourceCoverage
        SourceCoverage(self.course).require_confirmed()
        with self.locked():
            state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run);run['render_basis']=self.basis(stage);self._event(run,'局部返修已完成，正在重新编码实际成果','rendering');atomic(self.path,state)
        return dict(ok=True,fingerprint=run['fingerprint'])

    def allow_render(self,stage,run_id):
        from source_coverage import SourceCoverage
        SourceCoverage(self.course).require_confirmed()
        state=self.load();_,run=self._find(state,stage,run_id);self._current(stage,run)
        if stage=='script' or run['status']!='rendering' or not run.get('repaired') or not all(run.get('repair_grant',{}).values()):raise ValueError('缺少本轮局部返修授权或原先有效的前置确认')
        if self.script_input()['changed']:raise ValueError('讲稿已修改，须先完成讲稿审阅及相关配音更新，不能拿旧声音直接重编码')
        if run.get('render_basis')!=self.basis(stage):raise FileExistsError('返修期间出现人工修改，停止旧输入的重新编码')
        return True

    def finish(self,stage,run_id,error=None,limit=False):
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id)
            if run['status'] not in RUNNING:return dict(ok=True,review=self.node_view(stage,state))
            changed=run['fingerprint']!=self.fingerprint(stage)
            status='stale' if changed else 'limit_reached' if limit else 'failed' if error else 'awaiting_confirmation'
            reason='审阅期间出现新修改；已保留，旧结果不能批准' if changed else (str(error or '')+'；已到累计返修或预算上限，保留所有成果' if limit else str(error or ''))
            run.update(status=status,reason=reason,completed_at=now());node['elapsed_ms']+=int((time.time()-run['started_at'])*1000)
            if not error and not changed and run.get('report',{}).get('passed'):
                for old in node['runs'][:-1]:
                    if old['status'] in ['failed','limit_reached','stale'] or not old.get('report',{}).get('passed'):old['superseded_by']=run_id
            self._event(run,reason or '本轮完成，待你确认');atomic(self.path,state)
            atomic(self.project/'qa/ai-review'/run_id/'summary.json',run)
        if stage=='storyboard' and self.node_view(stage)['passed']:
            production=read(self.course.state_file)
            if self.course.storyboard_mode() and production.get('branch')=='video' and production.get('branch_receipt',{}).get('evidence'):
                from backend import Workspace
                from studio import Studio
                try:
                    Studio(Workspace(self.course.root)).confirm('storyboard',production['revision'])
                    with self.locked():
                        state=self.load();_,run=self._find(state,stage,run_id)
                        run['continuation_grant']=dict(authorized=True,stage='pilot',requires_user_confirmation=False,actor='ai-production-preflight',
                                                       based_on=copy.deepcopy(production['branch_receipt']),review_run_id=run_id,fingerprint=run['fingerprint'],at=now())
                        atomic(self.path,state)
                except ValueError as failure:
                    with self.locked():
                        state=self.load();_,run=self._find(state,stage,run_id)
                        run['preflight_error']=str(failure)
                        self._event(run,'独立分镜审阅通过；已有制作委托的预检仍待解决：'+str(failure));atomic(self.path,state)
        state=self.load()
        view=self.node_view(stage,state)
        return dict(ok=True,review=view,continuation=view['run'].get('continuation_grant') if view['passed'] else None)

    def ui(self,stage,run_id,action,text=None):
        with self.locked():
            state=self.load();node,run=self._find(state,stage,run_id,latest=False)
            if action=='draft':
                run['ui_draft']=str(text or '')[:8000]
                if run is node['runs'][-1]:node['draft']=run['ui_draft']
            elif action=='dismiss':run['progress_dismissed_at' if run['status'] in RUNNING else 'dismissed_at']=now()
            else:raise ValueError('无效审阅窗口操作')
            atomic(self.path,state)
        return dict(ok=True,review=self.node_view(stage,state))

    def require_pass(self, stage, run_id=None):
        self._unheld()
        view=self.node_view(stage)
        if run_id is not None and view['run'].get('id')!=run_id:raise ValueError('报告已更新，请核对本轮结果')
        if not view['passed']:raise ValueError('关键检查项尚未通过或证据不足，不能确认进入下一阶段')
        return view

    def approve(self,stage,run_id,actor='dsh-user-click'):
        if stage=='script':
            from source_coverage import SourceCoverage
            SourceCoverage(self.course).require_confirmed()
        with self.locked():
            view=self.require_pass(stage,run_id);state=self.load();node,run=self._find(state,stage,run_id)
            if stage=='storyboard':return self.view()
            self.require_user_audio(stage)
            if actor not in ['dsh-user-click','user-chat-confirmation']:raise ValueError('内容确认须来自真实用户点击或聊天回复')
            node['approval']=dict(run_id=run_id,fingerprint=view['fingerprint'],artifact_hashes=self.artifact_hashes(stage),at=now(),actor=actor)
            node['draft']='';atomic(self.path,state)
        return self.view()

    def extend(self,stage,repairs,calls,evidence,actor='dsh-user-click'):
        if actor not in ['dsh-user-click','user-chat-confirmation']:raise ValueError('追加预算须保留真实用户确认来源')
        if not isinstance(repairs,int) or not isinstance(calls,int) or repairs<0 or calls<0 or not (repairs or calls) or not evidence:raise ValueError('需要明确的追加返修范围与授权原话')
        with self.locked():
            state=self.load();node=self._node(state,stage);policy=self._policy(state,node)
            if policy.get('max_repairs') is not None:policy['max_repairs']+=repairs
            if policy.get('max_calls') is not None:policy['max_calls']+=calls
            policy.pop('unlimited_counts',None);node['policy']=policy
            state['authorizations'].append(dict(stage=stage,repairs=repairs,calls=calls,evidence=evidence,at=now(),actor=actor))
            atomic(self.path,state)
        return self.view()
