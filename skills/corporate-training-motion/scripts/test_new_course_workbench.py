"""New-course defaults and stale/missing editable artifacts must be observable failures."""
import copy,json,sys,tempfile,unittest,wave
from pathlib import Path
from scaffold import create
from check_workbench import check
from validate import validate as course_validate
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from backend import read,atomic,validate
from authoring import configure,native_fingerprint

class NewCourseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.course=Path(self.temp.name)/'course';create(self.course);self.p=self.course/'project'
    def tearDown(self):self.temp.cleanup()
    def ready(self):
        audio=self.p/'audio/test.wav'
        with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*24000)
        spec=dict(title='独立课程',sourceDurationFrames=30,scenes=[dict(id='X',chapter='技术',title='对象',sourceStartFrame=0,sourceEndFrame=30)],
                  captions=[dict(id='c',sceneId='X',text='核对SN与订单',startFrame=0,endFrame=30)],media=dict(audio='audio/test.wav',intro=None,outro=None),
                  sceneGraph=dict(nodes=[dict(id='t',type='text',sceneId='X',text='单独场景',x=100,y=100)]))
        path=self.p/'source/spec.json';atomic(path,spec);return configure(self.course,path)
    def test_scaffold_is_openable_but_not_fake_finished_course(self):
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

if __name__=='__main__':unittest.main()
