"""New-course defaults and stale/missing editable artifacts must be observable failures."""
import copy,json,sys,tempfile,unittest,wave
from pathlib import Path
from scaffold import create
from check_workbench import check
from validate import validate as course_validate
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from backend import read,atomic,validate
from authoring import configure,native_fingerprint
from workflow import Course

class NewCourseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.course=Path(self.temp.name)/'course';create(self.course);self.p=self.course/'project'
    def tearDown(self):self.temp.cleanup()
    def ready(self, composition_overrides=None):
        # This shared fixture exercises the pre-5.1 authoring/approval contract.
        # The new mandatory motion path has separate real-render and negative tests.
        historical_state=read(self.p/'course-state.json');historical_state.pop('planning_workflow',None);atomic(self.p/'course-state.json',historical_state)
        historical=read(self.p/'workbench.json');historical.pop('motionPolicy',None);atomic(self.p/'workbench.json',historical)
        (self.p/'motion-contract.json').unlink(missing_ok=True)
        course=Course(self.course);s=course.status();plan=s['plan']
        source=self.course/'inputs/test.txt';source.write_text('验收用原件')
        plan.update(audience='测试人员',performance_task='核对订单')
        plan['sources']=[dict(id='S',title='测试原件',location='../inputs/test.txt',kind='file')]
        plan['objectives']=[dict(id='O',statement='核对订单',evidence='完成核对',criterion='信息一致')]
        plan['units']=[dict(id='U',title='核对',objective_ids=['O'],source_refs=[dict(source_id='S',locator='第1行')],disposition='core',media='画布',media_reason='显示信息',activity='完成核对',teaching_method='示范后练习',teaching_reason='观察并执行核对动作')]
        plan['assessments']=[dict(id='A',objective_ids=['O'],task='核对订单',criteria='一致',feedback='复核字段')]
        course.save_plan(plan,s['revision'])
        for key in ['outline']:course.confirm(key,course.status()['revision'],'自动化验收夹具，非业务批准',actor='qa-agent')
        course.save_script('先核对订单，再核对编码。现在请完成一次核对，逐项复核。',course.status()['revision'])
        course.confirm('script',course.status()['revision'],'自动化验收夹具，非业务批准',actor='qa-agent')
        course.select_branch('video',course.status()['revision'],'QA请求视频',actor='qa-agent')
        from test_branch_workflow import director
        proposal=director(course);proposal['inputs'][1]['path']='../inputs/test.txt'
        course.save_director(proposal,course.status()['revision']);course.select_style('S1',course.status()['revision'],'QA选择实际画面',actor='qa-agent')
        audio=self.p/'audio/test.wav'
        with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*24000)
        spec=dict(title='独立课程',sourceDurationFrames=30,scenes=[dict(id='X',chapter='技术',title='对象',sourceStartFrame=0,sourceEndFrame=30)],
                  captions=[dict(id='c',sceneId='X',text='核对SN与订单',startFrame=0,endFrame=30)],media=dict(audio='audio/test.wav',intro=None,outro=None),
                  sceneGraph=dict(nodes=[dict(id='t',type='text',sceneId='X',text='单独场景',x=100,y=100)]))
        if composition_overrides:spec.update(composition_overrides)
        path=self.p/'source/spec.json';atomic(path,spec);return configure(self.course,path)
    def test_configure_requires_real_design_review_chain(self):
        path=self.p/'source/spec.json';atomic(path,{})
        with self.assertRaisesRegex(ValueError,'视频分支'):configure(self.course,path)
    def test_scaffold_is_openable_but_not_fake_finished_course(self):
        self.assertTrue(Course(self.course).storyboard_mode())
        self.assertEqual(Course(self.course).storyboard(),{})
        d=read(self.p/'workbench.json');validate(d,self.p)
        self.assertEqual(d['status'],'draft');self.assertEqual(d['adapter'],'scene-graph-v1');self.assertIsNone(d['media']['audio'])
        self.assertTrue((self.p/'editor/scripts/workbench.py').exists());self.assertTrue((self.p/'native/scene-engine.js').exists())
        self.assertTrue((self.p/'media').is_dir())
        self.assertTrue(read(self.p/'project.json')['workbench']['required']);self.assertFalse(check(self.p)['ok'])
    def test_authoring_generates_bindings_and_does_not_overwrite_edits(self):
        d=self.ready();self.assertEqual(d['fields'][0]['objectId'],'t');self.assertTrue(check(self.p)['ok'])
        cfg=read(self.p/'project.json');cfg['workbench']['required']=False;atomic(self.p/'project.json',cfg);self.assertFalse(check(self.p)['ok']);cfg['workbench']['required']=True;atomic(self.p/'project.json',cfg)
        with self.assertRaises(ValueError):configure(self.course,self.p/'source/spec.json')
        changed=copy.deepcopy(d);changed['fields']=[]
        with self.assertRaises(ValueError):validate(changed,self.p)
        changed=copy.deepcopy(d);changed['assets']=[dict(id='missing',path='assets/no.png',originalPath='assets/no.png')]
        with self.assertRaises(ValueError):validate(changed,self.p)
    def test_current_runtime_is_required_and_changes_invalidate_it(self):
        self.ready();self.assertFalse(check(self.p,require_runtime=True)['ok'])
        from backend import digest
        atomic(self.p/'qa/workbench-runtime.json',dict(status='pass',document_sha256=digest(self.p/'workbench.json'),native_sha256=native_fingerprint(self.p),scene_ids=['X'],seek_deterministic=True,binding_receipt=dict(fields=['t:text'],assets=[])))
        self.assertTrue(check(self.p,require_runtime=True)['ok'])
        d=read(self.p/'workbench.json');d['fields'][0]['text']='修改后';atomic(self.p/'workbench.json',d)
        self.assertFalse(check(self.p,require_runtime=True)['ok'])
        self.assertTrue(any('WORKBENCH_CONTRACT' in e for e in course_validate(self.p,'preview').errors))
    def test_missing_document_and_broken_scene_registration_block_new_course(self):
        self.ready();d=read(self.p/'workbench.json');d['sceneGraph']['nodes'][0]['sceneId']='other';atomic(self.p/'workbench.json',d)
        self.assertFalse(check(self.p)['ok']);(self.p/'workbench.json').unlink()
        self.assertFalse(check(self.p)['ok'])
    def test_standalone_short_timeline_can_export_as_pilot_but_not_as_final(self):
        from backend import Workspace
        from unittest.mock import patch
        doc=self.ready();space=Workspace(self.course)
        with self.assertRaises(ValueError):space.start_export(doc['revision'],0,1,'http://127.0.0.1:1',purpose='final')
        with patch('backend.threading.Thread') as thread:
            job=space.start_export(doc['revision'],0,1,'http://127.0.0.1:1',purpose='pilot')
            self.assertEqual(job['purpose'],'pilot');thread.return_value.start.assert_called_once()

if __name__=='__main__':unittest.main()
