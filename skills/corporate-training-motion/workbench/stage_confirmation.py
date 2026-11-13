"""Version-bound confirmations from the DSH host's native user question service."""
import copy
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import re

from workflow import atomic, now, read

STAGES = {'script': '逐字稿', 'pilot': '三段有声小样', 'final': '整课成片'}
WAIT = '稍后确认'
REVISE = '需要修改'


class StageConfirmation:
    def __init__(self, studio):
        self.studio = studio
        self.course = studio.course
        self.path = studio.project / 'stage-confirmation-records.json'
        self.lock_path = studio.project / '.stage-confirmation.lock'
        self.dispatch_path = studio.project / 'stage-feedback-dispatch.json'

    @contextmanager
    def locked(self):
        with self.lock_path.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def describe(self, status):
        if self.studio.review_context() == 'qa-simulation':
            return []
        review = status.get('ai_review') or {}
        if not review.get('enabled') or (review.get('hold') or {}).get('held'):
            return []
        pending = []
        for stage, label in STAGES.items():
            node = (review.get('nodes') or {}).get(stage) or {}
            if not node.get('passed') or node.get('user_confirmed') or not node.get('run', {}).get('id'):
                continue
            audio = node.get('user_audio_review') or {}
            media = self._review().artifact_hashes(stage)
            if not media or (stage == 'pilot' and len(media) != 3):
                continue
            source = (status.get('source_coverage') or {}) if stage == 'script' else {}
            need_source = source.get('required') and not source.get('confirmed')
            if need_source and not (source.get('current') and source.get('report_sha256')):
                continue
            need_audio = audio.get('required') and audio.get('status') != 'confirmed'
            if need_audio and (audio.get('status')=='issues_reported' or not audio.get('artifacts') or audio.get('artifact_sha256s') != media):
                continue
            binding = dict(
                course_id=status['course_id'], stage=stage, run_id=node['run']['id'],
                fingerprint=node['fingerprint'], artifacts=media,
                source={key: source.get(key) for key in ('report_sha256','script_sha256','sources_sha256')} if need_source else None,
                audio=copy.deepcopy(audio['artifacts']) if need_audio else None,
            )
            question_id = 'kgxc-confirm-' + hashlib.sha256(json.dumps(binding, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:36]
            detail = '请先在左侧查看当前版本。确认只适用于本版本；选「需要修改」后可在右侧写明意见；选「稍后确认」会暂停在当前阶段。'
            if need_source:
                detail += ' 请同时查看原件对照中的保留、舍弃和新增内容。'
            if need_audio:
                detail += ' 请先完整播放当前全部视频，检查声音和音画配合。'
            approve = '确认当前版本'
            if need_source:
                approve = '确认讲稿及原件对照'
            if need_audio:
                approve = '已完整看听全部视频，声音及同步正常，确认当前版本'
            pending.append(dict(stage=stage,id=question_id,label=label,binding=binding,approve=approve,
                                question=dict(id=question_id,header=label+'确认',question='确认当前'+label+'吗？',detail=detail,
                                              options=[dict(label=approve),dict(label=WAIT),dict(label=REVISE)])))
        return pending

    def _review(self):
        from ai_review import Review
        return Review(self.course)

    def view(self, status):
        records = read(self.path,[])
        legacy = []
        for stage,label in STAGES.items():
            review = ((status.get('ai_review') or {}).get('nodes') or {}).get(stage) or {}
            receipt = review.get('confirmation') or {}
            if receipt and not any(record['stage']==stage and record['status']=='confirmed' and record.get('fingerprint')==review.get('fingerprint') for record in records):
                legacy.append(dict(stage=stage,id='existing-'+stage,status='confirmed',at=receipt.get('at'),label=label,evidence=receipt.get('evidence') or '已有当前版本确认记录'))
        pending = []
        for q in self.describe(status):
            last = next((item for item in reversed(records) if item['id']==q['id']), None)
            feedback=next((item for item in reversed(read(self.studio.feedback_file,[])) if item.get('question_id')==q['id']),None) if getattr(self.studio,'feedback_file',None) else None
            pending.append(dict(stage=q['stage'],id=q['id'],label=q['label'],decision_status=last['status'] if last else None,
                                feedback=feedback))
        return dict(pending_confirmations=pending,confirmation_records=sorted(records+legacy,key=lambda item:item.get('at') or '',reverse=True))

    def request(self, stage, question_id):
        question = next((q for q in self.describe(self.course.status()) if q['stage']==stage and q['id']==question_id),None)
        if not question:
            raise ValueError('该确认已过期、尚无当前通过证据或已处理，请查看当前状态。')
        return question

    def answer(self, stage, question_id, selected):
        with self.locked():
            previous = read(self.path,[])
            if any(x['id']==question_id and x['status']=='confirmed' for x in previous):
                raise ValueError('此版本已经确认，不重复记录。')
            q = self.request(stage,question_id)
            if selected not in (q['approve'],WAIT,REVISE):
                raise ValueError('该答案不是当前确认题的有效选择。')
            evidence = '用户在 DSH 右侧问答选择「'+selected+'」'
            if selected == q['approve']:
                binding = q['binding']
                review = self._review()
                current = self.course.status()
                current_question=self.request(stage,question_id)
                if current_question['binding'] != binding:
                    raise ValueError('当前内容已变更，不接受旧版本确认。')
                review.require_pass(stage,binding['run_id'])
                source = dict(report_sha256=binding['source']['report_sha256'],evidence=evidence,source='dsh-native-question:'+question_id) if binding['source'] else None
                audio = dict(artifact_sha256s=binding['artifacts'],artifacts=binding['audio'],coverage='all_stage_videos',listened_completely=True,audio_and_sync_ok=True,
                             evidence=evidence,source=dict(kind='ui',id=question_id)) if binding['audio'] else None
                self.studio.confirm(stage,current['revision'],audio,source,native_question_id=question_id)
                decision='confirmed'
            else:
                decision='deferred' if selected==WAIT else 'changes_requested'
            previous.append(dict(stage=stage,id=question_id,status=decision,at=now(),label=q['label'],evidence=evidence,fingerprint=q['binding']['fingerprint']))
            atomic(self.path,previous)
            return dict(ok=True,stage=stage,status=decision)

    def feedback_binding(self, args, status, view):
        stage=args.get('stage')
        if stage not in STAGES:
            raise ValueError('反馈必须对应讲稿、小样或成片。')
        node=((status.get('ai_review') or {}).get('nodes') or {}).get(stage) or {}
        artifact_path=args.get('artifact_path')
        artifact_hash=args.get('artifact_sha256')
        when=args.get('time')
        segment=args.get('segment_id')
        if segment is not None and (not isinstance(segment,str) or len(segment)>300):
            raise ValueError('反馈定位不正确。')
        if stage=='script':
            if any(v is not None for v in (artifact_path,artifact_hash,when)):
                raise ValueError('讲稿反馈不使用视频时间。')
            if segment and not any(item.get('unit_id')==segment for item in view.get('sections',[])):
                raise ValueError('此讲稿章节已经变化，请重新定位。')
        elif any(v is not None for v in (artifact_path,artifact_hash,when)):
            if not isinstance(artifact_path,str) or not isinstance(artifact_hash,str) or not re.fullmatch('[a-f0-9]{64}',artifact_hash):
                raise ValueError('视频反馈需要当前视频版本及文件。')
            media=next((x for x in view.get('artifacts',{}).get(stage,[]) if x.get('available') and x.get('path')==artifact_path and x.get('sha256')==artifact_hash),None)
            duration=media.get('duration_seconds') if media else None
            if type(when) not in (float,int) or not math.isfinite(when) or type(duration) not in (float,int) or not 0<=when<=duration:
                raise ValueError('当前视频版本已变更，或时间不在视频范围内，请重新定位。')
        hashes=self._review().artifact_hashes(stage)
        if not hashes:
            raise ValueError('当前没有可绑定的成果，未提交反馈。')
        return dict(stage=stage,fingerprint=node.get('fingerprint'),artifacts=hashes,
                    artifact_path=artifact_path,artifact_sha256=artifact_hash,time=when,segment_id=segment)

    def feedback_save(self, args):
        feedback_id=args.get('feedback_id')
        if not isinstance(feedback_id,str) or not re.fullmatch('[0-9a-f-]{36}',feedback_id):
            raise ValueError('反馈标识无效。')
        text=args.get('text')
        if not isinstance(text,str) or not text.strip() or len(text)>8000:
            raise ValueError('请填写具体修改意见（不超过8000字）。')
        text=text.strip()
        with self.locked():
            prior=next((f for f in read(self.studio.feedback_file,[]) if f.get('id')==feedback_id),None)
            if prior:
                if prior['text']!=text or prior['stage']!=args.get('stage') or any(prior['version_binding'].get(key)!=args.get(key) for key in ('artifact_path','artifact_sha256','time','segment_id')) or prior.get('question_id')!=args.get('question_id'):
                    raise ValueError('反馈标识已用于其他内容。')
                return dict(ok=True,feedback=prior)
            status=self.course.status()
            if status['revision']!=args.get('base_revision'):
                raise ValueError('工作台内容已更新，请核对当前版本后重试。')
            view=self.studio.view()
            if view['revision']!=status['revision']:
                raise ValueError('工作台内容已更新，请重新定位。')
            binding=self.feedback_binding(args,status,view)
            question=args.get('question_id')
            if question is not None:
                last=next((r for r in reversed(read(self.path,[])) if r.get('id')==question and r.get('stage')==binding['stage']),None)
                if not last or last['status']!='changes_requested' or last.get('fingerprint')!=binding['fingerprint']:
                    raise ValueError('此修改选择不再对应当前成果，请重新定位。')
            label=args.get('location_label')
            self.studio.feedback(dict(baseRevision=status['revision'],stage=binding['stage'],time=binding['time'] or 0,text=text,
                segment_id=binding['segment_id'],artifact_path=binding['artifact_path'],artifact_sha256=binding['artifact_sha256'],
                question_id=question,feedback_id=feedback_id,version_binding=binding,location_label=label[:160] if isinstance(label,str) else ''))
            item=next(f for f in read(self.studio.feedback_file,[]) if f['id']==feedback_id)
            return dict(ok=True,feedback=item)

    def feedback_dispatch_spec(self,args):
        item=next((f for f in read(self.studio.feedback_file,[]) if f.get('id')==args.get('feedback_id') and f.get('version_binding')),None)
        if not item:
            raise ValueError('先保存具体修改意见，再交给 AI。')
        receipts=read(self.dispatch_path,{})
        if item['id'] in receipts:
            return dict(ok=True,feedback=item,dispatch_status='requested')
        binding=item['version_binding']
        status=self.course.status()
        if self.feedback_binding(binding,status,self.studio.view())!=binding:
            raise ValueError('成果已变更，不能把旧版本的修改要求直接用于新成果。')
        return dict(ok=True,feedback=item,dispatch_status='not_requested')

    def feedback_dispatched(self,args):
        with self.locked():
            fid=args.get('feedback_id')
            if not any(f.get('id')==fid and f.get('version_binding') for f in read(self.studio.feedback_file,[])):
                raise ValueError('未找到已保存的修改意见。')
            receipt=read(self.dispatch_path,{})
            receipt.setdefault(fid,dict(at=now(),state='requested'))
            atomic(self.dispatch_path,receipt)
        return dict(ok=True)
