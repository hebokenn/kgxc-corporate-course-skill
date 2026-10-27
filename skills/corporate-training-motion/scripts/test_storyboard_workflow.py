"""Behavioral checks for full-script planning and bounded pilot selection."""
import copy
import json
import subprocess
import wave
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workbench'))
from storyboard import SCHEMA, paragraphs, check, basis, draw, check_samples, check_bindings
from workflow import Course, atomic, sha
from test_branch_workflow import design


def fixture(course):
    source = paragraphs(course.script()['text'])
    segments = []
    for i, p in enumerate(source):
        options = [dict(id=letter, method=method, opening='准备对应对象 '+letter,
                        action='执行有目的的对象变化 '+letter, result='保留可读结果 '+letter,
                        focus='当前解释的对象', feasibility='使用已验证对象；新资产先核对',
                        cost='低' if letter=='A' else '中', risk_note='检查动作前中后',
                        difference='比较信息关系而不是换色 '+letter, characters=i==1)
                   for letter, method in [('A','对象对应'),('B','前后对照'),('C','条件路径')]]
        for o in options:o['reading_design']=dict(information_groups=[dict(screen_text='核对项目',read_task='看清当前核对项',motion_seconds=.6,stable_read_seconds=3,retention='保留到本段反馈')],focus_order=['当前项目','动作','结果'])
        segments.append(dict(id=f'S{i+1}',unit_id='U',source_paragraph_ids=[p['id']],script_excerpt=p['text'],
                             teaching_goal='核对当前任务',kind=['concept','scenario','operation'][i%3],
                             risk='high' if i==2 else 'normal',options=options,recommended='A',
                             recommendation_reason='对应工作任务且已有素材',selected=None,
                             assessment_ids=['A'] if i==len(source)-1 else []))
    return dict(schema=SCHEMA,reading_contract='reading-pacing-v1',script_sha256=course.script_sha(),
                visual_direction=dict(palette='白与蓝',typography='中文黑体',graphics='物件与角色',atmosphere='清楚'),
                presentation_policy=dict(concept_characters=False,scenario_characters=True),segments=segments)


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        atomic(self.root/'project/workbench.json',{})
        self.course=Course(self.root);self.course.init('技术测试课')
        design(self.course)
        self.course.confirm('outline',self.course.status()['revision'],'测试夹具结构，不是用户课程认可',actor='qa-operator')
        self.course.save_script('先核对订单。\n\n顾客询问时，先倾听再回应。\n\n现在完成核对，并逐项复查。',self.course.status()['revision'])
        self.course.confirm('script',self.course.status()['revision'],'测试夹具逐字稿',actor='qa-operator')
        self.course.select_branch('video',self.course.status()['revision'],'技术测试视频分支',actor='qa-operator')

    def tearDown(self):
        self.tmp.cleanup()

    def enable(self):
        return self.course.enable_storyboard(self.course.status()['revision'],'QA显式升级测试',actor='qa-operator')

    def ready(self):
        self.enable();self.course.save_storyboard(fixture(self.course),self.course.status()['revision'])
        self.course.choose_shot('all','recommended',self.course.status()['revision'],'QA夹具选择',actor='qa-operator')
        return self.course.confirm('storyboard',self.course.status()['revision'],'QA夹具分镜确认',actor='qa-operator')

    def test_migration_keeps_content_receipts_and_old_workflow_is_not_automatic(self):
        self.assertEqual(self.course.status()['stage'],'style')
        atomic(self.course.project/'storyboard.json',[dict(id='old-placeholder')])
        old=copy.deepcopy(json.loads(self.course.state_file.read_text())['gates'])
        state=self.enable()
        self.assertEqual(state['stage'],'storyboard')
        self.assertEqual(self.course.storyboard(),{})
        self.assertTrue(any('old-placeholder' in p.read_text() for p in (self.course.project/'workflow-history').glob('*.json')))
        self.assertEqual(json.loads(self.course.state_file.read_text())['gates'],old)
        self.assertEqual([g['id'] for g in state['gates']],['outline','script','storyboard','pilot','final'])

    def test_new_planning_mode_is_available_without_mutating_existing_init(self):
        other=Course(self.root/'new');other.init('新课',planning='storyboard-v1')
        self.assertTrue(other.storyboard_mode());self.assertFalse(self.course.storyboard_mode())

    def test_tagged_transcript_excludes_production_notes(self):
        text='# 课名\n元数据\n\n## 第一节\n【口播】\n正文一。\n\n正文二。\n\n【练习引导】\n请尝试。\n\n## 制作及来源备注\n不能读出的备注'
        self.assertEqual([p['text'] for p in paragraphs(text)],['正文一。','正文二。','请尝试。'])

    def test_missing_or_duplicate_source_paragraph_cannot_pass(self):
        self.enable();data=fixture(self.course)
        for mutation in ['missing','duplicate','wrong-excerpt']:
            with self.subTest(mutation=mutation):
                d=copy.deepcopy(data)
                if mutation=='missing':d['segments'].pop()
                elif mutation=='duplicate':d['segments'][1]['source_paragraph_ids']=['P001']
                else:d['segments'][0]['script_excerpt']='摘要不能冒充完整原稿'
                with self.assertRaises(ValueError):self.course.save_storyboard(d,self.course.status()['revision'])

    def test_reading_contract_requires_every_alternative_to_plan_information(self):
        board=fixture(self.course)
        def report():return check(board,self.course.script()['text'],self.course.script_sha(),self.course.status()['plan'],reading_required=True)
        self.assertTrue(report()['ok'],report())
        option=board['segments'][0]['options'][2];saved=option.pop('reading_design')
        self.assertTrue(any('独立信息组'in e for e in report()['errors']))
        option['reading_design']=saved;saved['information_groups'][0]['stable_read_seconds']=.2
        self.assertTrue(any('估算下限'in e for e in report()['errors']))
        saved['information_groups']=[];self.assertTrue(any('没有新增正文'in e for e in report()['errors']))
        saved['no_new_text_reason']='用物件状态对照理解，无新增正文'
        self.assertTrue(report()['ok'],report())
        board.pop('reading_contract');self.assertTrue(any('reading_contract'in e for e in report()['errors']))

    def test_three_distinct_alternatives_and_person_policy(self):
        self.enable();data=fixture(self.course)
        for mutation in ['two','duplicate','person']:
            with self.subTest(mutation=mutation):
                d=copy.deepcopy(data)
                if mutation=='two':d['segments'][0]['options'].pop()
                elif mutation=='duplicate':
                    o=copy.deepcopy(d['segments'][0]['options'][0]);o['id']='C';d['segments'][0]['options'][2]=o
                else:d['segments'][0]['options'][0]['characters']=True
                with self.assertRaises(ValueError):self.course.save_storyboard(d,self.course.status()['revision'])

    def test_saving_does_not_accept_recommendations_or_forged_selection(self):
        self.enable();data=fixture(self.course)
        for s in data['segments']:s.update(selected='A',selection_receipt=dict(evidence='伪造文件内批准'))
        state=self.course.save_storyboard(data,self.course.status()['revision'])
        self.assertEqual(state['storyboard_report']['pending'],['S1','S2','S3'])
        with self.assertRaises(ValueError):self.course.sample_storyboard(state['revision'])
        with self.assertRaises(ValueError):self.course.confirm('storyboard',state['revision'],'没有选择不能确认')

    def test_sampling_is_reproducible_covers_types_and_is_stable(self):
        self.ready();self.course.sample_storyboard(self.course.status()['revision'],seed='qa-fixed-seed')
        plan=self.course.sample_plan();self.assertEqual(len(plan['selections']),3)
        self.assertEqual({s['kind'] for s in plan['selections']},{'scenario','concept','operation'})
        self.assertEqual(plan,draw(self.course.storyboard(),'qa-fixed-seed'))
        before=self.course.status()['revision']
        self.course.sample_storyboard(before,seed='different-ignored-without-redraw')
        self.assertEqual(self.course.sample_plan(),plan);self.assertEqual(self.course.status()['revision'],before)
        with self.assertRaisesRegex(ValueError,'原因'):self.course.sample_storyboard(before,redraw=True)

    def test_tampered_draw_and_post_approval_board_change_are_detected(self):
        self.ready();self.course.sample_storyboard(self.course.status()['revision'],seed='qa')
        plan=copy.deepcopy(self.course.sample_plan());plan['selections'][0]['option_id']='B'
        self.assertTrue(check_samples(self.course.storyboard(),plan))
        data=self.course.storyboard();data['segments'][0]['options'][0]['action']='更换实现与画面'
        self.course.save_storyboard(data,self.course.status()['revision'])
        self.assertEqual(self.course.status()['stage'],'storyboard')
        self.assertEqual(self.course.status()['gates'][1]['status'],'confirmed')

    def test_coverage_rejects_one_sample_cropped_sample_and_wrong_method(self):
        self.ready();self.course.sample_storyboard(self.course.status()['revision'],seed='qa')
        board=self.course.storyboard();plan=self.course.sample_plan();lookup={s['id']:s for s in board['segments']}
        doc=dict(sourceDurationFrames=300,scenes=[],storyboardBindings=[])
        for i,chosen in enumerate(plan['selections']):
            sid=chosen['segment_id'];scene='scene-'+sid
            doc['scenes'].append(dict(id=scene,sourceStartFrame=i*100,sourceEndFrame=(i+1)*100))
            doc['storyboardBindings'].append(dict(segment_id=sid,option_id=chosen['option_id'],script_excerpt=lookup[sid]['script_excerpt'],startFrame=i*100,endFrame=(i+1)*100,sceneIds=[scene]))
        self.assertEqual(check_bindings(board,plan,doc,0,300),[])
        self.assertTrue(check_bindings(board,plan,doc,0,250))
        held=copy.deepcopy(doc);held['holds']=[dict(sourceFrame=100,frames=30)]
        self.assertEqual(check_bindings(board,plan,held,0,330),[])
        cut=copy.deepcopy(doc);cut['cuts']=[dict(startFrame=20,endFrame=21)]
        self.assertTrue(check_bindings(board,plan,cut))
        gap=copy.deepcopy(doc);gap['scenes'][0]['sourceStartFrame']=1
        self.assertTrue(check_bindings(board,plan,gap))
        wrong=copy.deepcopy(doc);wrong['storyboardBindings'].pop()
        self.assertTrue(check_bindings(board,plan,wrong))
        wrong=copy.deepcopy(doc);wrong['storyboardBindings'][0]['option_id']='C'
        self.assertTrue(check_bindings(board,plan,wrong))

    def test_real_av_registration_requires_current_export_binding_and_freezes_sample(self):
        from performance_cache import native_fingerprint
        self.ready();self.course.sample_storyboard(self.course.status()['revision'],seed='qa')
        board,plan=self.course.storyboard(),self.course.sample_plan()
        lookup={s['id']:s for s in board['segments']}
        doc=dict(sourceDurationFrames=30,holds=[],scenes=[],storyboardBindings=[],assets=[dict(id='actor',path='assets/actor.txt')])
        actor=self.course.project/'assets/actor.txt';actor.parent.mkdir();actor.write_text('actual chosen source asset')
        for i,selection in enumerate(plan['selections']):
            sid=selection['segment_id'];scene='scene-'+sid
            doc['scenes'].append(dict(id=scene,sourceStartFrame=i*10,sourceEndFrame=(i+1)*10))
            doc['storyboardBindings'].append(dict(segment_id=sid,option_id=selection['option_id'],script_excerpt=lookup[sid]['script_excerpt'],startFrame=i*10,endFrame=(i+1)*10,sceneIds=[scene]))
        atomic(self.course.project/'workbench.json',doc)
        video=self.course.project/'qa-synthetic.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=gray:s=64x64:r=30:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(video)],check=True)
        with self.assertRaisesRegex(ValueError,'导出记录'):self.course.register('pilot',[video.name],self.course.status()['revision'])
        proof=dict(video_sha256=sha(video),storyboard_sampling=dict(storyboard_sha256=basis(board),sample_plan_sha256=__import__('storyboard').digest(plan),document_sha256=sha(self.course.project/'workbench.json'),native_sha256=native_fingerprint(self.course.project),bindings=doc['storyboardBindings']))
        atomic(video.with_suffix('.json'),proof)
        self.course.register('pilot',[video.name],self.course.status()['revision'])
        state=self.course.confirm('pilot',self.course.status()['revision'],'QA合成媒体仅检查登记流程',actor='qa-operator')
        self.assertEqual(state['stage'],'final')
        doc['newProductionField']='仅扩展新内容，冻结的小样本身不变'
        atomic(self.course.project/'workbench.json',doc)
        self.course.require_video('pilot')
        actor.write_text('changed character asset')
        with self.assertRaises(ValueError):self.course.require_video('pilot')
        actor.write_text('actual chosen source asset')
        doc['assets'].append(dict(id='new-full-course-only',path='assets/new.txt'))
        (actor.parent/'new.txt').write_text('newly added content asset')
        atomic(self.course.project/'workbench.json',doc);self.course.require_video('pilot')
        proof['storyboard_sampling']['native_sha256']='wrong';atomic(video.with_suffix('.json'),proof)
        with self.assertRaisesRegex(ValueError,'导出记录'):self.course.register('pilot',[video.name],self.course.status()['revision'])

    def test_default_course_configure_retains_bindings_and_export_blocks_partial_sample(self):
        from scaffold import create
        from authoring import configure
        from backend import Workspace
        from unittest.mock import patch
        path=self.root/'default-course';create(path);course=Course(path);design(course)
        course.confirm('outline',course.status()['revision'],'QA结构',actor='qa-operator')
        course.save_script(self.course.script()['text'],course.status()['revision'])
        course.confirm('script',course.status()['revision'],'QA正文',actor='qa-operator')
        course.select_branch('video',course.status()['revision'],'QA视频',actor='qa-operator')
        course.save_storyboard(fixture(course),course.status()['revision'])
        course.choose_shot('all','recommended',course.status()['revision'],'QA选择',actor='qa-operator')
        course.confirm('storyboard',course.status()['revision'],'QA分镜',actor='qa-operator')
        course.sample_storyboard(course.status()['revision'],seed='configure-qa')
        audio=course.project/'audio/test.wav'
        with wave.open(str(audio),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*24000)
        scenes=[];bindings=[];nodes=[];captions=[];lookup={s['id']:s for s in course.storyboard()['segments']}
        for i,item in enumerate(course.sample_plan()['selections']):
            sid=item['segment_id'];scene='scene-'+sid
            scenes.append(dict(id=scene,chapter='QA',title='QA segment',sourceStartFrame=i*10,sourceEndFrame=(i+1)*10))
            bindings.append(dict(segment_id=sid,option_id=item['option_id'],script_excerpt=lookup[sid]['script_excerpt'],startFrame=i*10,endFrame=(i+1)*10,sceneIds=[scene]))
            nodes.append(dict(id='node-'+sid,type='text',sceneId=scene,text='技术夹具',x=100,y=100))
            captions.append(dict(id='caption-'+sid,sceneId=scene,text='技术夹具',startFrame=i*10,endFrame=(i+1)*10))
        spec=dict(title='QA binding import',sourceDurationFrames=30,scenes=scenes,storyboardBindings=bindings,captions=captions,media=dict(audio='audio/test.wav',intro=None,outro=None),sceneGraph=dict(nodes=nodes))
        file=course.project/'source/spec.json';atomic(file,spec)
        doc=configure(path,file);self.assertEqual(doc['storyboardBindings'],bindings)
        with patch('backend.threading.Thread') as thread:
            with self.assertRaisesRegex(ValueError,'裁掉'):Workspace(path).start_export(doc['revision'],0,.9,'http://127.0.0.1:1',purpose='pilot')
            thread.assert_not_called()

    def test_less_than_three_segments_cannot_repeat_one_to_fill_slots(self):
        self.ready();data=self.course.storyboard();data['segments']=data['segments'][:2]
        with self.assertRaises(ValueError):draw(data,'qa')


if __name__=='__main__':unittest.main()
