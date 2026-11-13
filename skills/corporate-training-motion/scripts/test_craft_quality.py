"""Actual encoded-frame proof, legacy boundaries and composition decision regression."""
import copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from craft_quality import policy,analyze,review,CRITERIA
from motion_quality import require
from scaffold import create

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture():
    legacy_policy=policy();legacy_policy.pop('coverRequired');legacy_policy.pop('visualHygieneRequired')  # Isolate the v5.4 craft contract.
    return dict(width=64,height=36,fps=6,sourceDurationFrames=18,introFrames=0,bodyEndFrame=18,qualityPolicy=legacy_policy,holds=[],cuts=[],
        scenes=[dict(id='S'+str(j),sourceStartFrame=j*3,sourceEndFrame=j*3+3) for j in range(6)],
        sceneGraph=dict(nodes=[dict(id='node'+str(j),sceneId='S'+str(j),type='text',text='内容'+str(j),x=j*80,y=20,fontSize=24) for j in range(6)]))

class CompositionTests(unittest.TestCase):
    def test_ids_and_different_copy_do_not_hide_a_repeated_layout(self):
        d=fixture()
        for n in d['sceneGraph']['nodes']:n['x']=100
        signals=analyze(d)['signals'];self.assertEqual({s['kind'] for s in signals},{'consecutive-composition','dominant-composition'})
        self.assertEqual(signals[0]['sceneIds'],['S'+str(i) for i in range(6)])
    def test_different_composition_and_decorative_noise(self):
        d=fixture();self.assertEqual(analyze(d)['status'],'pass')
        for j,n in enumerate(d['sceneGraph']['nodes']):n['x']=100
        d['sceneGraph']['nodes'] += [dict(type='rect',role='decoration',sceneId='S'+str(j),width=j*100) for j in range(6)]
        self.assertEqual(analyze(d)['status'],'review-required')
    def test_new_course_defaults_and_marker_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as t:
            c=Path(t)/'course';create(c);p=c/'project';d=json.loads((p/'workbench.json').read_text())
            self.assertTrue(d['qualityPolicy']['required']);self.assertTrue(d['qualityPolicy']['coverRequired']);self.assertTrue((p/'craft-contract.json').is_file())
            d.pop('qualityPolicy')
            with self.assertRaisesRegex(ValueError,'不能删除 qualityPolicy'):require(d,p)
    def test_legacy_projects_remain_opt_in(self):
        self.assertEqual(review('/tmp',dict(),'/tmp/no-video')['status'],'legacy-not-opted-in')

class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.p=Path(cls.tmp.name);cls.video=cls.p/'candidate.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=64x36:rate=6:duration=3','-c:v','libx264','-pix_fmt','yuv420p',str(cls.video)],check=True)
        (cls.p/'qa').mkdir()
        cls.frames=[]
        for i in [2,8,14]:
            path=cls.p/'qa'/f'frame-{i}.png'
            subprocess.run(['ffmpeg','-v','error','-ss',f'{i/6:.9f}','-i',str(cls.video),'-frames:v','1',str(path)],check=True)
            cls.frames.append(dict(path=str(path.relative_to(cls.p)),sha256=digest(path),sourceFrame=i,origin='encoded-video',observation='实际编码图形与字号边距可见 '+str(i)))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.doc=fixture();(self.p/'workbench.json').write_text(json.dumps(self.doc))
        self.record=dict(schema='course-craft-review/1',status='reviewed',videoSha256=digest(self.video),documentSha256=digest(self.p/'workbench.json'),reviewer='automated QA fixture; not a human aesthetic verdict',scope='test encoded pixels and record requirements',
            aesthetics={k:'Concrete observation for '+k for k in CRITERIA},voice={k:'Test evidence scope '+k for k in ['naturalTone','standardMandarin','crispPacing','speakerContinuity','reviewScope']},evidenceFrames=copy.deepcopy(self.frames),compositionDecisions=[],unresolvedIssues=[])
    def check(self,pixels=False):
        (self.p/'qa/craft-review.json').write_text(json.dumps(self.record));return review(self.p,self.doc,self.video,verify_pixels=pixels)
    def test_complete_actual_encoded_evidence(self):self.assertEqual(self.check(True)['status'],'pass')
    def test_preview_or_changed_pixels_cannot_stand_in_for_encoded_frames(self):
        path=self.p/'qa/fake.png';Image.new('RGB',(64,36),'black').save(path)
        self.record['evidenceFrames'][0].update(path='qa/fake.png',sha256=digest(path))
        self.assertTrue(any('真实像素' in e for e in self.check(True)['errors']))
    def test_all_six_aesthetic_observations_and_voice_scope_required(self):
        for section,key in [('aesthetics','whitespace'),('voice','standardMandarin'),('voice','reviewScope')]:
            old=self.record[section].pop(key);self.assertEqual(self.check()['status'],'pending');self.record[section][key]=old
        self.record['aesthetics']={k:'Looks great' for k in CRITERIA}
        self.assertTrue(any('同一句' in e for e in self.check()['errors']))
    def test_missing_middle_old_hash_and_unresolved_issue_rejected(self):
        for change in ['middle','hash','issue','origin','path']:
            old=copy.deepcopy(self.record)
            if change=='middle':self.record['evidenceFrames'].pop(1)
            elif change=='hash':self.record['documentSha256']='old'
            elif change=='issue':self.record['unresolvedIssues']=['unfixed overlap']
            elif change=='origin':self.record['evidenceFrames'][0]['origin']='native-preview'
            else:self.record['evidenceFrames'][0]['path']='../../outside.png'
            with self.subTest(change=change):self.assertEqual(self.check()['status'],'pending')
            self.record=old
    def test_same_form_comparison_requires_a_reason_not_forced_novelty(self):
        for n in self.doc['sceneGraph']['nodes']:n['x']=100
        (self.p/'workbench.json').write_text(json.dumps(self.doc));self.record['documentSha256']=digest(self.p/'workbench.json')
        self.assertEqual(self.check()['status'],'pending')
        self.record['compositionDecisions']=[dict(sceneIds=[s['id'] for s in self.doc['scenes']],reason='连续核对同一张表的字段，保持位置便于比较。')]
        self.assertEqual(self.check()['status'],'pass')
    def test_edited_timeline_uses_display_frame(self):
        self.doc['holds']=[dict(sourceFrame=2,frames=2)];(self.p/'workbench.json').write_text(json.dumps(self.doc))
        self.record['documentSha256']=digest(self.p/'workbench.json');self.record['evidenceFrames'][0]['sourceFrame']=0
        # source 0 is display 0, while the stored frame is display 2: must fail.
        self.assertEqual(self.check(True)['status'],'pending')
    def test_missing_or_invalid_review_not_accepted(self):
        path=self.p/'qa/craft-review.json';path.unlink(missing_ok=True)
        self.assertEqual(review(self.p,self.doc,self.video)['status'],'pending')
        path.write_text('invalid');self.assertEqual(review(self.p,self.doc,self.video)['status'],'pending')

if __name__=='__main__':unittest.main()
