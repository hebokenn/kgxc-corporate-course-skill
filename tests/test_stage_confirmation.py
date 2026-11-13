from pathlib import Path
from types import SimpleNamespace
import copy
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'))
from stage_confirmation import StageConfirmation
from workflow import atomic,read


class StudioFixture:
    def __init__(self, directory):
        self.project=Path(directory)
        self.applied=[];self.feedback_file=self.project/'studio-feedback.json'
        self.visible=dict(revision=4,sections=[dict(unit_id='U1')],artifacts=dict(pilot=[dict(available=True,path='x.mp4',sha256='b'*64,duration_seconds=33.0)]))
        self.media=dict(script=['a'*64],pilot=['b'*64,'c'*64,'d'*64],final=['e'*64,'f'*64])
        self.state=dict(course_id='fixture',revision=4,ai_review=dict(enabled=True,nodes={stage:dict(passed=True,fingerprint='fp-'+stage,run=dict(id=stage+'-review')) for stage in ['script','storyboard','pilot','final']}))
        self.course=SimpleNamespace(status=lambda:copy.deepcopy(self.state))

    def review_context(self):return 'course-review'

    def view(self):return copy.deepcopy(self.visible)

    def feedback(self,args):
        entry=dict(id=args['feedback_id'],text=args['text'],stage=args['stage'],question_id=args['question_id'],
                   time=args['time'],version_binding=args['version_binding'])
        atomic(self.feedback_file,read(self.feedback_file,[])+[entry])


    def confirm(self,*args,**kwargs):
        self.applied.append((args,kwargs))
        self.state['ai_review']['nodes'][args[0]]['user_confirmed']=True


class TestStageConfirmation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.studio=StudioFixture(self.tmp.name)
        self.check=StageConfirmation(self.studio)
        self.check._review=lambda:SimpleNamespace(artifact_hashes=lambda stage:self.studio.media[stage],require_pass=lambda stage,run_id:self.assertEqual(run_id,stage+'-review'))

    def tearDown(self):self.tmp.cleanup()

    def set_source(self,current=True):
        self.studio.state['source_coverage']=dict(required=True,current=current,report_sha256='1'*64,sources_sha256='2'*64,script_sha256='3'*64)

    def set_audio(self,stage='pilot'):
        self.studio.state['ai_review']['nodes'][stage]['user_audio_review']=dict(
            required=True,status='pending',artifact_sha256s=self.studio.media[stage],
            artifacts=[dict(sha256=value,start_seconds=0,end_seconds=12.5+i) for i,value in enumerate(self.studio.media[stage])])

    def test_only_three_checkpoints_and_stable_question_id(self):
        spec=self.check.describe(self.studio.state)
        self.assertEqual([q['stage'] for q in spec],['script','pilot','final'])
        self.assertEqual([q['id'] for q in spec],[q['id'] for q in self.check.describe(self.studio.state)])
        self.studio.state['ai_review']['nodes']['final']['passed']=False
        self.assertEqual([q['stage'] for q in self.check.describe(self.studio.state)],['script','pilot'])

    def test_source_and_media_are_bound_and_cannot_approve_old_version(self):
        self.set_source();self.set_audio()
        script,pilot,final=self.check.describe(self.studio.state)
        self.assertIn('原件对照',script['approve'])
        self.assertIn('完整看听',pilot['approve'])
        self.studio.state['source_coverage']['report_sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'已过期'):self.check.answer('script',script['id'],script['approve'])
        script=self.check.describe(self.studio.state)[0]
        self.check.answer('script',script['id'],script['approve'])
        args,kwargs=self.studio.applied[-1]
        self.assertEqual(args[3]['report_sha256'],'9'*64)
        self.assertEqual(args[3]['source'],'dsh-native-question:'+script['id'])
        self.assertEqual(kwargs['native_question_id'],script['id'])
        self.check.answer('pilot',pilot['id'],pilot['approve'])
        declaration=self.studio.applied[-1][0][2]
        self.assertEqual(declaration['artifact_sha256s'],self.studio.media['pilot'])
        self.assertEqual([item['start_seconds'] for item in declaration['artifacts']],[0,0,0])
        self.assertEqual([item['end_seconds'] for item in declaration['artifacts']],[12.5,13.5,14.5])
        self.assertTrue(declaration['listened_completely'])
        self.check.answer('final',final['id'],final['approve'])
        self.assertEqual(self.studio.applied[-1][0][0],'final')
        self.assertEqual(len(StageConfirmation(self.studio).view(self.studio.state)['confirmation_records']),3)

    def test_located_feedback_binds_actual_video_and_same_id_retries_without_duplicate(self):
        [pilot]=[q for q in self.check.describe(self.studio.state) if q['stage']=='pilot']
        self.check.answer('pilot',pilot['id'],'需要修改')
        args=dict(stage='pilot',question_id=pilot['id'],base_revision=4,feedback_id='a'*36,
                  text='改一下这个画面',artifact_path='x.mp4',artifact_sha256='b'*64,time=21.4)
        item=self.check.feedback_save(args)['feedback']
        self.assertEqual(item['version_binding']['time'],21.4)
        self.assertEqual(self.check.feedback_save(args)['feedback'],item)
        self.assertEqual(len(read(self.studio.feedback_file,[])),1)
        with self.assertRaisesRegex(ValueError,'其他内容'):self.check.feedback_save(dict(args,time=22))
        self.assertEqual(self.check.feedback_dispatch_spec(args)['dispatch_status'],'not_requested')
        self.studio.media['pilot'][0]='f'*64
        with self.assertRaisesRegex(ValueError,'成果已变更'):self.check.feedback_dispatch_spec(args)

    def test_feedback_checks_script_chapter_and_video_range(self):
        args=dict(stage='script',base_revision=4,feedback_id='a'*36,text='改这一章',segment_id='old')
        with self.assertRaisesRegex(ValueError,'章节已经变化'):self.check.feedback_save(args)
        self.assertEqual(self.check.feedback_save(dict(args,segment_id='U1'))['feedback']['version_binding']['segment_id'],'U1')
        with self.assertRaisesRegex(ValueError,'不在视频范围'):
            self.check.feedback_save(dict(args,stage='pilot',feedback_id='b'*36,artifact_path='x.mp4',artifact_sha256='b'*64,time=35))

    def test_deferred_is_durable_not_an_approval_and_only_three_real_samples_allowed(self):
        self.set_source(current=False)
        self.studio.media['pilot'].pop()
        [final]=self.check.describe(self.studio.state)
        self.assertEqual(final['stage'],'final')
        self.check.answer('final',final['id'],'稍后确认')
        fresh=StageConfirmation(self.studio)
        fresh._review=self.check._review
        self.assertEqual(fresh.view(self.studio.state)['pending_confirmations'][0]['decision_status'],'deferred')
        self.assertFalse(self.studio.applied)
        self.check.answer('final',final['id'],final['approve'])
        self.assertEqual(self.studio.applied[-1][0][0],'final')


if __name__=='__main__':unittest.main()
