"""Human-facing course stages over the existing workflow, with stable content identities."""
from pathlib import Path
from contextlib import contextmanager
import copy
import difflib
import hashlib
import json
import math
import re
import uuid

from workflow import Course, read, atomic, now, sha as file_sha
from script_editor import ScriptEditor, sha
from storyboard import paragraphs

STAGES = [('sources','资料'),('outline','大纲'),('script','逐字稿'),('storyboard','分镜'),('pilot','有声小样'),('final','整课交付')]


def paragraph_id(): return 'P-' + uuid.uuid4().hex[:16]


def blocks(body, previous=()):
    actual = paragraphs(body)
    old = [p['text'] for p in previous]
    new = [p['text'] for p in actual]
    for tag,a,b,c,d in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
        for offset,index in enumerate(range(c,d)):
            retained = tag == 'equal' or tag == 'replace' and b-a == d-c
            actual[index]['id'] = previous[a+offset]['id'] if retained else paragraph_id()
    return [{k:p[k] for k in ['id','text','sha256']} for p in actual]


def ordered_sections(units, sections):
    lookup = {s['unit_id']:copy.deepcopy(s) for s in sections}
    return [dict(lookup.get(u['id'],{'unit_id':u['id'],'body':'','paragraphs':[]}),title=u['title'])
            for u in units if u.get('disposition','core') == 'core']


def compose(sections):
    return '\n\n'.join('## '+str(i+1)+'. '+s['title']+'\n\n'+s.get('body','').strip()
                         for i,s in enumerate(sections)).strip() if any(s.get('body','').strip() for s in sections) else ''


def identity_map(sections):
    text = compose(sections)
    return {'schema':'course-paragraph-identities/1','script_sha256':sha(text),
            'paragraphs':[dict(id=p['id'],unit_id=s['unit_id'],sha256=p['sha256']) for s in sections for p in s['paragraphs']]}


class Studio:
    def __init__(self, space):
        self.space=space; self.course=Course(space.root); self.project=space.project
        self.editor=ScriptEditor(space); self.file=self.project/'studio-content.json'
        self.impact=self.project/'studio-impact.json'; self.feedback_file=self.project/'studio-feedback.json'
        self.proposals=self.project/'studio-proposals.json'

    def content(self, plan=None):
        plan=plan or read(self.course.plan_file)
        value=read(self.file,{'schema':'course-studio-content/1','sections':[],'official_sections':[],'revision':0})
        value['sections']=ordered_sections(plan['units'],value['sections'])
        return value

    def review_context(self):
        context=read(self.project/'workbench-review-context.json',{})
        return 'qa-simulation' if context.get('scope')=='qa-simulation' and context.get('course_id')==read(self.course.state_file)['course_id'] else 'course-review'

    @contextmanager
    def transaction(self, expected, event):
        with self.course.locked():
            state=read(self.course.state_file);self.course._revision(expected,state)
            if any(j.get('status') in ['queued','rendering','encoding','packaging'] for j in self.course.status().get('jobs',[])):
                raise ValueError('当前正在制作视频，完成后再修改结构')
            paths=[self.course.plan_file,self.course.state_file,self.file,self.editor.path,self.impact,
                   self.project/'source/transcript.md',self.project/'storyboard.json',self.feedback_file,self.proposals,
                   self.project/'production-preferences.json',self.project/'production-preferences-storyboard.json']
            before={str(p.relative_to(self.project)):p.read_text() if p.is_file() else None for p in paths}
            history=self.project/'studio-history';history.mkdir(exist_ok=True)
            snapshot=history/(str(state['revision']).zfill(8)+'.json')
            atomic(snapshot,{'at':now(),'event':event,'after_revision':expected+1,'files':before})
            try:
                yield state
                self.course._commit(state,event)
            except Exception:
                for name,text in before.items():
                    path=self.project/name
                    if text is None:
                        if path.exists():path.unlink()
                    else:
                        path.parent.mkdir(parents=True,exist_ok=True)
                        pending=path.with_name(path.name+'.rollback-'+uuid.uuid4().hex)
                        pending.write_text(text);pending.replace(path)
                raise

    def affected(self, unit_ids, paragraph_ids=(), reason='讲稿发生修改'):
        segments=[s['id'] for s in self.course.storyboard().get('segments',[])
                  if s.get('unit_id') in unit_ids or set(s.get('source_paragraph_ids',[])).intersection(paragraph_ids)]
        atomic(self.impact,{'at':now(),'unit_ids':list(dict.fromkeys(unit_ids)),
                           'paragraph_ids':list(paragraph_ids),'segment_ids':segments,'reason':reason,
                           'stages':['script','storyboard','pilot','final']})

    def view(self):
        status=self.course.status();plan=status['plan'];content=self.content(plan);editor=self.editor.read()
        mapped=compose(content['sections'])==editor['text']
        sources=[]
        for source in plan.get('sources',[]):
            path=self.course.relative(source['location']) if source.get('location') else None
            item=dict(source,available=bool(path and path.is_file()),bytes=path.stat().st_size if path and path.is_file() else 0)
            if path and path.is_file() and path.suffix.lower()=='.pdf':
                from source_preview import pdf_info
                item.update(pdf_info(path))
            sources.append(item)
        artifacts={}
        for key,values in status.get('artifacts',{}).items():
            artifacts[key]=[]
            for name in values:
                path=self.course.relative(name);item=dict(path=name,available=path.is_file(),bindings=[],chapters=[])
                if path.is_file() and path.suffix.lower()=='.mp4':
                    meta=read(path.with_suffix('.json'),{})
                    if meta.get('video_sha256')==file_sha(path):
                        item['sha256']=meta['video_sha256'];item['audio_settings']=meta.get('audio_settings',{});frozen=meta.get('playback',{})
                        # Older exports are navigable only when the editable document is still identical.
                        if not frozen and meta.get('document_sha256')==file_sha(self.space.file):
                            from export_playback import playback
                            limits=meta.get('range',{});frozen=playback(editor['document'],limits.get('firstFrame',0),limits.get('lastFrame'))
                        item.update(bindings=frozen.get('bindings',[]),chapters=frozen.get('chapters',[]),duration_seconds=frozen.get('duration_seconds'))
                        from storyboard import basis
                        item['current_storyboard']=meta.get('storyboard_sampling',{}).get('storyboard_sha256')==basis(self.course.storyboard())
                artifacts[key].append(item)
        from export_playback import audio_settings
        settings=audio_settings(editor['document'],self.project)
        progress_jobs=[];exports=getattr(self.space,'work',self.project/'work/workbench')/'exports'
        for folder in sorted(exports.glob('*'),key=lambda p:(p/'document.json').stat().st_mtime if (p/'document.json').exists() else 0):
            if not folder.is_dir():continue
            job=self.space.job(folder.name) if hasattr(self.space,'job') else read(folder/'result.json',{})
            item={key:job[key] for key in ['id','purpose','status','progress','error','video','srt','package','revision'] if key in job}
            if (folder/'document.json').is_file():item['created_at']=int((folder/'document.json').stat().st_mtime*1000)
            if job.get('status') in ['complete','failed'] and (folder/'result.json').is_file():item['completed_at']=int((folder/'result.json').stat().st_mtime*1000)
            progress_jobs.append(item)
        from production_preferences import load as production_preferences,storyboard_current
        preferences=production_preferences(self.project);preferences['storyboard_current']=storyboard_current(self.project)
        return dict(ok=True,course_path=str(self.course.root),course_id=status['course_id'],title=plan['title'],review_context=self.review_context(),
                    revision=status['revision'],stage=status['stage'],gates=status['gates'],plan=plan,sources=sources,
                    sections=content['sections'],content_revision=content['revision'],mapped=mapped,
                    editor={k:editor[k] for k in ['revision','text','changed','base_changed','has_scenes']},
                    storyboard=status.get('storyboard',{}),storyboard_report=status.get('storyboard_report',{}),
                    sampling=status.get('sampling',{}),artifacts=artifacts,jobs=progress_jobs,
                    deliveries=status.get('deliveries',[]),impact=read(self.impact,{}),
                    feedback=read(self.feedback_file,[]),proposals=read(self.proposals,[]),
                    rendering=status.get('rendering',{}),audio_settings=settings,narration_status=status.get('narration_status'),
                    production_preferences=preferences,
                    undo_available=any((self.project/'studio-history').glob('*.json')))

    def save_production_choice(self,args):
        from production_preferences import update
        actor='qa-operator' if self.review_context()=='qa-simulation' else 'dsh-course-workbench'
        with self.transaction(args['baseRevision'],'studio_production_preference_saved'):
            update(self.project,args.get('key'),args.get('value'),actor,args.get('brief',''),args.get('reference_path',''))
            atomic(self.impact,dict(at=now(),unit_ids=[],paragraph_ids=[],segment_ids=[],
                stages=['storyboard','pilot','final'],reason='制作偏好已修改，请更新相关画面、音效与样片；讲稿保留。'))
        return self.view()

    def save_sections(self, sections, expected, editor_revision=None, official=False):
        plan=read(self.course.plan_file);old=self.content(plan)
        wanted=[u['id'] for u in plan['units'] if u.get('disposition','core')=='core']
        if [s.get('unit_id') for s in sections] != wanted:raise ValueError('逐字稿章节必须与当前大纲的稳定章节对应')
        normalized=[];seen=set()
        for section in sections:
            body=section.get('body','')
            if not isinstance(body,str) or len(body)>2_000_000:raise ValueError('章节逐字稿格式无效')
            previous=next((s for s in old['sections'] if s['unit_id']==section['unit_id']),{})
            entry={'unit_id':section['unit_id'],'body':body,'paragraphs':blocks(body,previous.get('paragraphs',[]))}
            for p in entry['paragraphs']:
                if p['id'] in seen:raise ValueError('段落身份重复')
                seen.add(p['id'])
            normalized.append(entry)
        normalized=ordered_sections(plan['units'],normalized);text=compose(normalized)
        with self.transaction(expected,'studio_script_committed' if official else 'studio_script_draft_saved') as state:
            current=self.editor.read()
            if editor_revision is not None and current['revision']!=editor_revision:raise FileExistsError('讲稿已在另一处更新，请先刷新核对')
            if current['base_changed']:raise FileExistsError('正式稿已在另一处更新，人工稿仍保留，请先合并')
            if official:
                self.course.require('outline')
                if not text.strip():raise ValueError('逐字稿尚未填写')
                dest=self.project/'source/transcript.md';dest.parent.mkdir(exist_ok=True);dest.write_text(text)
                plan.update(stage='script',script_file='source/transcript.md',script_mapping=identity_map(normalized))
                atomic(self.course.plan_file,plan);old['official_sections']=copy.deepcopy(normalized)
                current.update(text=text,base_text=text,base_sha256=sha(text),revision=current['revision']+1)
                self.editor.write(current)
                state['narration_status']='needs_regeneration' if state.get('branch')=='video' else 'not_required'
            else:self.editor.save(text,current['revision'])
            changed=[s['unit_id'] for s in normalized if s.get('body')!=next((o.get('body') for o in old['sections'] if o['unit_id']==s['unit_id']),None)]
            old.update(sections=normalized,revision=old['revision']+1);atomic(self.file,old)
            if changed:self.affected(changed,reason='章节讲稿发生修改，优先更新关联片段')
        return self.view()

    def save_outline(self, units, expected, transform=None, plan_fields=None):
        plan=read(self.course.plan_file);previous=copy.deepcopy(plan['units']);content=self.content(plan)
        global_changed=bool(plan_fields and any(plan.get(key)!=plan_fields[key] for key in ['audience','performance_task','objectives','assessments'] if key in plan_fields))
        if not isinstance(units,list) or any(not isinstance(u,dict) or not str(u.get('id','')).strip() or not str(u.get('title','')).strip() for u in units):
            raise ValueError('每章需要稳定身份和标题')
        ids=[u['id'] for u in units]
        if len(set(ids))!=len(ids):raise ValueError('章节身份重复')
        current=self.editor.read();old_text=compose(content['sections'])
        if current['text'] and current['text']!=old_text:
            raise ValueError('现有人工逐字稿尚未绑定到章节，请先在逐字稿页完成绑定再调整结构；原稿已保留')
        if transform:transform(content)
        with self.transaction(expected,'studio_outline_saved'):
            plan['units']=units
            for key in ['audience','performance_task','objectives','assessments','source_items']:
                if plan_fields is not None and key in plan_fields:plan[key]=copy.deepcopy(plan_fields[key])
            content['sections']=ordered_sections(units,content['sections'])
            official=content.get('official_sections',[])
            if official and compose(official)==self.course.script()['text']:
                content['official_sections']=ordered_sections(units,official)
                text=compose(content['official_sections'])
                self.course.relative(plan['script_file']).write_text(text)
                plan['script_mapping']=identity_map(content['official_sections'])
            official_text=self.course.script()['text']
            current.update(text=compose(content['sections']),base_text=official_text,base_sha256=sha(official_text),revision=current['revision']+1)
            self.editor.write(current);content['revision']+=1
            atomic(self.file,content);atomic(self.course.plan_file,plan)
            board=self.course.storyboard();rank={u:i for i,u in enumerate(ids)}
            if board.get('segments'):
                board['segments'].sort(key=lambda s:rank.get(s.get('unit_id'),len(ids)))
                # Preserve the old script hash: reordering never pretends the old timing is current.
                atomic(self.project/'storyboard.json',board)
            changed=ids if global_changed else [u['id'] for i,u in enumerate(units) if i>=len(previous) or previous[i]!=u]
            if not global_changed:
                nearby=list(changed)
                for ordered in [previous,units]:
                    for i,u in enumerate(ordered):
                        if u['id'] in changed:nearby.extend(v['id'] for v in ordered[max(0,i-1):i+2])
                changed=list(dict.fromkeys(nearby))
            self.affected(changed,reason='大纲结构或次序改变，请检查开场、过渡、分镜排序与成片时轴')
        return self.view()

    def restructure(self, action, args):
        plan=read(self.course.plan_file);units=copy.deepcopy(plan['units']);index=next((i for i,u in enumerate(units) if u['id']==args.get('unit_id')),None)
        if action=='reorder':
            order=args.get('order',[])
            if sorted(order)!=sorted(u['id'] for u in units):raise ValueError('排序与当前章节不一致')
            lookup={u['id']:u for u in units};return self.save_outline([lookup[i] for i in order],args['baseRevision'])
        if action=='add':
            entry={'id':'U-'+uuid.uuid4().hex[:12],'title':'新章节','disposition':'core','activity':'','teaching_method':'','teaching_reason':'','media':'','media_reason':'','objective_ids':[]}
            units.insert(index+1 if index is not None else len(units),entry)
            return self.save_outline(units,args['baseRevision'])
        if index is None:raise ValueError('当前章节不存在')
        if action=='remove':
            if len(units)<=1:raise ValueError('至少保留一个章节')
            units.pop(index);return self.save_outline(units,args['baseRevision'])
        if action=='split':
            entry=copy.deepcopy(units[index]);entry.update(id='U-'+uuid.uuid4().hex[:12],title=entry['title']+'（续）');units.insert(index+1,entry)
            def split(content):
                for key in ['sections','official_sections']:
                    section=next((s for s in content[key] if s['unit_id']==args['unit_id']),None)
                    if section:
                        pieces=section.get('body','').split('\n\n');cut=max(1,min(len(pieces),int(args.get('paragraph_index',len(pieces)//2))))
                        left='\n\n'.join(pieces[:cut]);right='\n\n'.join(pieces[cut:]);prior=section.get('paragraphs',[])
                        section.update(body=left,paragraphs=blocks(left,prior));content[key].append({'unit_id':entry['id'],'title':entry['title'],'body':right,'paragraphs':blocks(right,prior[len(section['paragraphs']):])})
            return self.save_outline(units,args['baseRevision'],split)
        if action=='merge':
            if index+1>=len(units):raise ValueError('后面没有可合并的章节')
            removed=units.pop(index+1);units[index]['title']+=' / '+removed['title']
            def merge(content):
                for key in ['sections','official_sections']:
                    left=next((s for s in content[key] if s['unit_id']==args['unit_id']),None);right=next((s for s in content[key] if s['unit_id']==removed['id']),None)
                    if left and right:left.update(body=(left['body']+'\n\n'+right['body']).strip(),paragraphs=left['paragraphs']+right['paragraphs'])
            return self.save_outline(units,args['baseRevision'],merge)
        raise ValueError('未知章节操作')

    def confirm(self, stage, expected):
        simulated=self.review_context()=='qa-simulation';actor='qa-operator' if simulated else 'dsh-course-workbench'
        evidence=('授权模拟操作，仅用于独立验证课，不代表正式课程内容验收：' if simulated else '用户在 DSH 课程工作台点击确认当前')+dict(STAGES).get(stage,stage)
        if stage=='script':
            value=self.view()
            if not value['mapped']:raise ValueError('当前稿件尚未完成章节绑定，不能确认')
            self.save_sections(value['sections'],expected,value['editor']['revision'],official=True)
            expected=self.course.status()['revision']
        result=self.course.confirm(stage,expected,evidence,actor=actor)
        if stage=='script' and result.get('branch')!='video':
            self.course.select_branch('video',result['revision'],evidence+'，进入视频分镜',actor=actor)
        if stage=='storyboard':
            status=self.course.status()
            if not status.get('sampling_valid'):self.course.sample_storyboard(status['revision'])
        return self.view()

    def feedback(self,args):
        text=str(args.get('text','')).strip()
        if not text:raise ValueError('请填写具体修改要求')
        stamp=float(args.get('time',0))
        if not math.isfinite(stamp) or stamp<0:raise ValueError('反馈时间点无效')
        artifact=None
        if args.get('artifact_path'):
            artifact=next((f for f in self.view()['artifacts'].get(args['stage'],[]) if f['path']==args['artifact_path'] and f.get('sha256')==args.get('artifact_sha256')),None)
            if not artifact:raise ValueError('视频版本已变化，请刷新后重新定位反馈')
            if artifact.get('duration_seconds') is not None and stamp>artifact['duration_seconds']:raise ValueError('反馈时间点超过视频时长')
        with self.transaction(args['baseRevision'],'studio_feedback_saved'):
            values=read(self.feedback_file,[]);values.append({'id':uuid.uuid4().hex[:12],'at':now(),'stage':args['stage'],'segment_id':args.get('segment_id'),'time':stamp,'text':text,
                'artifact_path':artifact['path'] if artifact else None,'artifact_sha256':artifact['sha256'] if artifact else None})
            atomic(self.feedback_file,values)
        return self.view()

    def undo(self,expected):
        candidates=sorted((self.project/'studio-history').glob('*.json'))
        if not candidates:raise ValueError('没有可撤销的编辑')
        latest=candidates[-1];snapshot=read(latest)
        with self.course.locked():
            state=read(self.course.state_file);self.course._revision(expected,state)
            if state['revision']!=snapshot['after_revision']:raise ValueError('此后已有其他更新，请核对相关内容，不能直接撤销旧编辑')
            editor_revision=self.editor.read()['revision']
            # Restore content, never manufacture or roll back an approval receipt.
            for name,text in snapshot['files'].items():
                if name=='course-state.json':continue
                path=self.project/name
                if text is None:
                    if path.is_file():path.unlink()
                else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            draft=self.editor.read();draft['revision']=editor_revision+1;self.editor.write(draft)
            self.course._commit(state,'studio_undo',{'snapshot':latest.name});latest.unlink()
        return self.view()

    def add_source(self,name,raw,expected):
        name=Path(name).name
        if not name or Path(name).suffix.lower() not in ['.pdf','.docx','.pptx','.xlsx','.txt','.md','.csv','.png','.jpg','.jpeg','.webp']:
            raise ValueError('请选择 PDF、Office 文档、文字或图片资料')
        if not raw:raise ValueError('文件为空')
        digest=hashlib.sha256(raw).hexdigest();identifier='SRC-'+digest[:10]
        plan=read(self.course.plan_file)
        if any(s['id']==identifier for s in plan['sources']):return self.view()
        dest=self.course.root/'inputs'/name
        if dest.exists():dest=dest.with_name(dest.stem+'-'+digest[:8]+dest.suffix)
        created=False
        try:
            with self.transaction(expected,'studio_source_added'):
                dest.parent.mkdir(exist_ok=True)
                if not dest.exists():dest.write_bytes(raw);created=True
                plan['sources'].append({'id':identifier,'title':name,'location':str(dest.relative_to(self.course.root)).replace('inputs/','../inputs/',1),'kind':'file','sha256':digest})
                atomic(self.course.plan_file,plan)
        except Exception:
            if created:dest.unlink()
            raise
        return self.view()

    def proposal(self,stage,candidate,expected):
        if stage not in ['outline','script','storyboard']:raise ValueError('建议阶段无效')
        with self.transaction(expected,'studio_ai_proposal_saved'):
            values=read(self.proposals,[])
            values.append({'id':uuid.uuid4().hex[:12],'stage':stage,'at':now(),'candidate':candidate,'status':'open','base_revision':expected})
            atomic(self.proposals,values[-30:])
        return self.view()

    def action(self,action,args):
        expected=args['baseRevision']
        if action=='production-choice':return self.save_production_choice(args)
        if action=='outline':return self.save_outline(args['units'],expected,plan_fields=args.get('plan_fields'))
        if action in ['reorder','add','remove','split','merge']:return self.restructure(action,args)
        if action=='sections':return self.save_sections(args['sections'],expected,args.get('baseEditorRevision'))
        if action=='confirm':return self.confirm(args['stage'],expected)
        if action=='choice':
            simulated=self.review_context()=='qa-simulation'
            self.course.choose_shot(args['id'],args['option'],expected,'独立验证课模拟选择' if simulated else '用户在课程工作台明确选择画面方案',actor='qa-operator' if simulated else 'dsh-course-workbench');return self.view()
        if action=='sample':self.course.sample_storyboard(expected);return self.view()
        if action=='feedback':return self.feedback(args)
        if action=='undo':return self.undo(expected)
        if action=='adopt':
            values=read(self.proposals,[]);proposal=next((p for p in values if p['id']==args['id'] and p['status']=='open'),None)
            if not proposal:raise ValueError('建议已经改变，请刷新')
            if expected!=proposal['base_revision']+1:raise ValueError('生成建议后已有其他编辑，请让 AI 基于当前内容重新给出建议')
            if proposal['stage']=='script':self.save_sections(proposal['candidate']['sections'],expected,self.editor.read()['revision'])
            elif proposal['stage']=='outline':self.save_outline(proposal['candidate']['units'],expected,plan_fields=proposal['candidate'])
            else:self.course.save_storyboard(proposal['candidate'],expected)
            proposal['status']='adopted';atomic(self.proposals,values);return self.view()
        raise ValueError('未知课程工作台操作')
