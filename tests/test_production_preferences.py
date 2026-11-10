from pathlib import Path
import tempfile
import unittest
import sys
import wave
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from workflow import Course,atomic,read,sha
from production_preferences import ensure,load,update,creative_basis,choice_digest,selection_errors,review_errors,storyboard_current
from studio import Studio
from test_branch_workflow import design


class ProductionPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.project=self.root/'project'
        atomic(self.project/'workbench.json',dict(title='偏好验证夹具',scenes=[],media={}))
        self.course=Course(self.root);self.course.init('偏好验证夹具',planning='storyboard-v1');design(self.course)
        self.studio=Studio(SimpleNamespace(root=self.root,project=self.project,file=self.project/'workbench.json'))
    def tearDown(self):self.tmp.cleanup()
    def rev(self):return read(self.course.state_file)['revision']
    def choose(self,key,value,**extra):return self.studio.action('production-choice',dict(baseRevision=self.rev(),key=key,value=value,**extra))
    def ready(self):
        self.choose('customer','V01');self.choose('flower_text','key-points');self.choose('sound_effects','native')
    def test_legacy_read_does_not_modify_frozen_course_or_invent_answers(self):
        self.assertIsNone(creative_basis(self.project));self.assertFalse(load(self.project)['required'])
        self.assertEqual(selection_errors(self.project),[]);self.assertFalse((self.project/'production-preferences.json').exists())
    def test_actual_choices_of_older_delivery_do_not_revoke_approval_until_changed(self):
        self.ready();video=self.root/'delivery/old.mp4';video.parent.mkdir();video.write_bytes(b'isolated legacy fixture')
        state=read(self.course.state_file);state.update(version='6.4.0',artifacts=dict(final=['../delivery/old.mp4']));atomic(self.course.state_file,state)
        value=read(self.project/'production-preferences.json');value['recorded_existing_production']=dict(video_path='../delivery/old.mp4',video_sha256=sha(video),actor='qa-operator',evidence='实际旧版本成片的已记录选择');atomic(self.project/'production-preferences.json',value)
        self.assertFalse(load(self.project)['required']);self.assertIsNone(creative_basis(self.project))
        self.choose('customer','V02');self.assertTrue(load(self.project)['required']);self.assertIsNotNone(creative_basis(self.project))
    def test_new_courses_cannot_skip_current_contract_using_legacy_record(self):
        self.ready();video=self.root/'delivery/new.mp4';video.parent.mkdir();video.write_bytes(b'isolated new fixture')
        state=read(self.course.state_file);state['artifacts']=dict(final=['../delivery/new.mp4']);atomic(self.course.state_file,state)
        value=read(self.project/'production-preferences.json');value['recorded_existing_production']=dict(video_path='../delivery/new.mp4',video_sha256=sha(video),actor='qa-operator',evidence='not a legacy course');atomic(self.project/'production-preferences.json',value)
        self.assertTrue(load(self.project)['required']);self.assertIsNotNone(creative_basis(self.project))
    def test_three_clicks_persist_individually_and_reopen_without_reasking(self):
        ensure(self.project);self.assertEqual(len(selection_errors(self.project)),3)
        first=self.choose('customer','V02');self.assertEqual(first['production_preferences']['choices'],{'customer':'V02'})
        self.assertEqual(first['production_preferences']['pending'],['flower_text','sound_effects'])
        self.choose('flower_text','minimal');result=self.choose('sound_effects','off')
        self.assertTrue(result['production_preferences']['ready']);self.assertEqual(selection_errors(self.project),[])
        self.assertEqual(self.studio.view()['production_preferences']['choices'],dict(customer='V02',flower_text='minimal',sound_effects='off'))
        self.assertEqual(read(self.project/'studio-impact.json')['stages'],['storyboard','pilot','final'])
    def test_stale_click_cannot_replace_a_newer_choice(self):
        old=self.rev();self.choose('customer','V01')
        with self.assertRaises(FileExistsError):self.studio.action('production-choice',dict(baseRevision=old,key='customer',value='V02'))
        self.assertEqual(load(self.project)['choices']['customer'],'V01')
    def test_choice_changes_do_not_revoke_unrelated_content_approval(self):
        self.course.confirm('outline',self.rev(),'夹具确认',actor='qa-operator')
        old=read(self.course.state_file)['gates']['outline'].copy();self.ready()
        self.assertEqual(read(self.course.state_file)['gates']['outline'],old)
        self.assertEqual(self.course.status()['gates'][0]['status'],'confirmed')
    def ready_storyboard(self):
        from test_branch_workflow import approve_script
        from test_storyboard_workflow import fixture
        # These preference unit cases predate the central execution contract.
        # Keep their real stale-choice/body-material checks, isolate only admission.
        # This is not evidence that a current release passed its canonical gate.
        from unittest.mock import patch
        stage_gate=patch('production.stage_release',return_value=dict(ready=True,scope='historical-preference-fixture-only',current_release_gate_tested=False))
        stage_gate.start();self.addCleanup(stage_gate.stop)
        self.ready();approve_script(self.course)
        self.course.select_branch('video',self.rev(),'合成夹具视频需求',actor='qa-operator')
        self.course.save_storyboard(fixture(self.course),self.rev())
    def test_selecting_an_existing_shot_preserves_current_preference_binding(self):
        self.ready_storyboard()
        receipt=self.project/'production-preferences-storyboard.json';old=receipt.read_bytes()
        choices=choice_digest(self.project)
        self.assertTrue(storyboard_current(self.project))
        self.course.choose_shot('all','recommended',self.rev(),'合成夹具明确选择既有方案',actor='qa-operator')
        self.assertTrue(storyboard_current(self.project));self.assertEqual(choice_digest(self.project),choices)
        self.assertEqual(read(receipt)['actor'],'storyboard-choice-preserved-preferences')
        self.assertTrue(any(path.read_bytes()==old for path in (self.project/'work/production-preferences-history').glob('*.json')))
        self.course.confirm('storyboard',self.rev(),'合成夹具分镜确认，不代表业务课程批准',actor='qa-operator')
    def test_selecting_a_shot_cannot_revalidate_changed_preferences(self):
        self.ready_storyboard()
        receipt=self.project/'production-preferences-storyboard.json';old=receipt.read_bytes()
        self.choose('sound_effects','off')
        self.assertFalse(storyboard_current(self.project))
        self.course.choose_shot('all','recommended',self.rev(),'合成夹具选择，尚未按新偏好重做分镜',actor='qa-operator')
        self.assertEqual(receipt.read_bytes(),old);self.assertFalse(storyboard_current(self.project))
        with self.assertRaisesRegex(ValueError,'制作偏好更新'):
            self.course.confirm('storyboard',self.rev(),'合成夹具不能绕过失效偏好',actor='qa-operator')
    def test_selecting_a_shot_cannot_invent_a_missing_preference_binding(self):
        self.ready_storyboard()
        receipt=self.project/'production-preferences-storyboard.json';receipt.unlink()
        self.course.choose_shot('all','recommended',self.rev(),'合成夹具仅选择方案，不造缺失依据',actor='qa-operator')
        self.assertFalse(receipt.exists());self.assertFalse(storyboard_current(self.project))
    def test_uploaded_customer_reference_is_scoped_and_design_must_be_adopted(self):
        outside=self.root/'private.png';outside.write_bytes(b'image')
        with self.assertRaises(ValueError):self.choose('customer','new',brief='便装顾客',reference_path='../private.png')
        self.assertNotIn('customer',load(self.project)['choices'])
        reference=self.project/'media/uploads/reference.png';reference.parent.mkdir(parents=True);reference.write_bytes(b'fixture-image')
        self.choose('customer','new',brief='成年顾客',reference_path='media/uploads/reference.png')
        self.choose('flower_text','off');self.choose('sound_effects','off')
        self.assertTrue(any('已采用' in error for error in selection_errors(self.project)))
        profile=self.project/'assets/customer-profile.json';atomic(profile,dict(id='C04'))
        value=read(self.project/'production-preferences.json');value['new_customer'].update(profile_path='assets/customer-profile.json',design_approval=dict(status='confirmed',actor='qa-operator',evidence='夹具明确采用设计'))
        atomic(self.project/'production-preferences.json',value);self.assertEqual(selection_errors(self.project),[])
    def proof(self,video,flower=2,sfx=1):
        return dict(choices_sha256=choice_digest(self.project),video_sha256=sha(video),
            observations=dict(customer='实际编码可见V01顾客',flower_text='实际编码可见重点花字',sound_effects='实际混音含原库提示音'),
            implemented=dict(customer_ids=['V01'],customer_nodes=['customer'],flower_count=flower,flower_nodes=['emphasis'] if flower else [],sfx_count=sfx,sfx_palette='teaching-native-v1'))
    def video(self):
        video=self.project/'course-final-r1-000000000001.mp4';video.write_bytes(b'current fixture video')
        audio=self.project/'audio/mix.wav';audio.parent.mkdir(exist_ok=True);audio.write_bytes(b'bound mixed fixture audio')
        stem=self.project/'audio/mix-sfx.wav'
        with wave.open(str(stem),'wb')as stream:stream.setparams((1,2,24000,0,'NONE','not compressed'));stream.writeframes(b'\x01\x02'*128)
        atomic(audio.with_suffix('.json'),dict(palette='teaching-native-v1',mix_sha256=sha(audio),events=1,appliedGains=[dict(id='real-event')],sfxStem='audio/mix-sfx.wav'))
        atomic(self.project/'work/workbench/exports/000000000001/document.json',dict(sceneGraph=dict(nodes=[dict(id='customer',type='group',vectorActor=dict(identity='V01',characterRole='customer',hair='side-part',shirt='jacket')),dict(id='emphasis',type='text',text='先核实')]),media=dict(audio='audio/mix.wav')))
        return video
    def test_enabled_features_cannot_be_signed_off_without_actual_events_or_current_video(self):
        self.ready();video=self.video()
        self.assertTrue(review_errors(self.project,'final',video))
        f=self.project/'qa/production-preferences-final-review.json';atomic(f,self.proof(video,flower=0,sfx=0))
        self.assertTrue(any('花字' in error for error in review_errors(self.project,'final',video)))
        self.assertTrue(any('音效' in error for error in review_errors(self.project,'final',video)))
        atomic(f,self.proof(video));self.assertEqual(review_errors(self.project,'final',video),[])
        video.write_bytes(b'changed video');self.assertTrue(review_errors(self.project,'final',video))
    def test_changed_preference_rejects_old_review_and_off_is_enforced(self):
        self.ready();video=self.video()
        f=self.project/'qa/production-preferences-final-review.json';atomic(f,self.proof(video))
        self.choose('flower_text','off');self.assertTrue(review_errors(self.project,'final',video))
        atomic(f,self.proof(video,flower=1));self.assertTrue(any('关闭' in error for error in review_errors(self.project,'final',video)))
        atomic(f,self.proof(video,flower=0));self.assertEqual(review_errors(self.project,'final',video),[])
    def test_checkbox_report_cannot_pass_with_missing_objects_or_unmixed_sound(self):
        self.ready();video=self.video();f=self.project/'qa/production-preferences-final-review.json';proof=self.proof(video)
        proof['implemented']['flower_nodes']=['not-in-export'];atomic(f,proof)
        self.assertTrue(any('真实文字' in error for error in review_errors(self.project,'final',video)))
        atomic(f,self.proof(video));(self.project/'audio/mix.wav').write_bytes(b'different audio without verified effects')
        self.assertTrue(any('混音' in error for error in review_errors(self.project,'final',video)))
    def test_silent_sound_stem_and_off_choice_are_checked_against_bound_mix(self):
        self.ready();video=self.video();f=self.project/'qa/production-preferences-final-review.json';atomic(f,self.proof(video))
        with wave.open(str(self.project/'audio/mix-sfx.wav'),'wb')as stream:stream.setparams((1,2,24000,0,'NONE','not compressed'));stream.writeframes(bytes(256))
        self.assertTrue(any('完全静音' in error for error in review_errors(self.project,'final',video)))
        self.choose('sound_effects','off');atomic(f,self.proof(video,sfx=0))
        self.assertTrue(any('仍绑定' in error for error in review_errors(self.project,'final',video)))


if __name__=='__main__':unittest.main()
