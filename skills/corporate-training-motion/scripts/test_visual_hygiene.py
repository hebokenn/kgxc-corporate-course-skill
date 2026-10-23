"""Regression coverage for visible padding, endpoint residue and encoded scene review."""
import copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from visual_hygiene import review
from measure_visible_bounds import measure
from craft_quality import policy

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class BoundsTests(unittest.TestCase):
    def test_transparent_canvas_center_does_not_replace_visible_center(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'sprite.png';im=Image.new('RGBA',(200,120));ImageDraw.Draw(im).rectangle((20,30,59,89),fill='#397a99');im.save(p)
            self.assertEqual(measure(p,anchor_x=40,anchor_y=60)['status'],'pass')
            self.assertEqual(measure(p,anchor_x=100)['offsets']['x'],-60)
            self.assertEqual(measure(p,anchor_x=100)['status'],'misaligned')
    def test_scene_difference_measures_only_the_subject_and_can_check_one_axis(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);background=Image.new('RGB',(120,100),'#f6ead8');background.save(p/'background.png')
            foreground=background.copy();ImageDraw.Draw(foreground).rectangle((30,10,69,69),fill='#397a99');foreground.save(p/'foreground.png')
            r=measure(p/'foreground.png',p/'background.png',anchor_x=50)
            self.assertEqual(r['bounds'],[30,10,70,70]);self.assertEqual(r['status'],'pass')
            with self.assertRaisesRegex(ValueError,'Opaque'):measure(p/'foreground.png')

class EndMarkerTests(unittest.TestCase):
    def test_actual_registered_actions_hide_finished_markers_and_keep_explicit_states(self):
        source=ROOT/'workbench/motion/teaching-effects.js'
        script=r'''
const fs=require('fs'),vm=require('vm');
const C={before(){},text(){},path(){}};
const sandbox={window:{CourseMotion:C},MO:{smooth:x=>x},DG:{cum:()=>[0,100],drawPartial(){},pointAt:()=>[100,0]}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
const results={};
for(const name of ['route-progress','flow-token']){
 const run=(p,e={})=>{let arcs=0;const c={globalAlpha:1,save(){},restore(){},beginPath(){},arc(){arcs++},fill(){}};
 C.actions[name].fn(c,{points:[[0,0],[100,0]],stroke:'#a85b39'},e,p);return arcs;};
 results[name]=[run(0),run(.5),run(1),run(1,{retainMarker:true}),run(.5,{marker:false})];
}
process.stdout.write(JSON.stringify(results));
'''
        r=json.loads(subprocess.check_output(['node','-e',script,str(source)]))
        self.assertEqual(r,{'route-progress':[0,1,0,1,0],'flow-token':[0,1,0,1,0]})

class SceneReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.p=Path(cls.tmp.name);cls.video=cls.p/'candidate.mp4';(cls.p/'qa').mkdir()
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=white:size=64x36:rate=10:duration=2',
            '-vf',"drawbox=x=3:y=8:w=12:h=12:color=red:t=fill:enable='lt(t,1)',drawbox=x=40:y=8:w=12:h=12:color=blue:t=fill:enable='gte(t,1)'",
            '-c:v','libx264','-pix_fmt','yuv420p',str(cls.video)],check=True)
        for f in [3,15]:subprocess.run(['ffmpeg','-v','error','-ss',str((f-.1)/10),'-i',str(cls.video),'-frames:v','1',str(cls.p/f'qa/frame-{f}.png')],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        (self.p/'craft-contract.json').unlink(missing_ok=True)
        self.doc=dict(width=64,height=36,fps=10,qualityPolicy={'visualHygieneRequired':True},scenes=[{'id':'A'},{'id':'B'}])
        (self.p/'workbench.json').write_text(json.dumps(self.doc))
        self.record=dict(schema='course-visual-hygiene-review/1',status='reviewed',videoSha256=sha(self.video),documentSha256=sha(self.p/'workbench.json'),
            reviewer='technical fixture, not human aesthetic acceptance',scope='two current encoded states',unresolvedIssues=[],sceneReviews=[])
        for identifier,frame in [('A',3),('B',15)]:
            self.record['sceneReviews'].append(dict(sceneId=identifier,alignment='Observed subject within its intended region '+identifier,
                connectors='No connectors in this synthetic state '+identifier,animationResidue='No stray mark in the held state '+identifier,
                evidenceFrames=[dict(path=f'qa/frame-{frame}.png',sha256=sha(self.p/f'qa/frame-{frame}.png'),encodedFrame=frame,origin='encoded-video',observation='Current encoded box state')]))
    def check(self,pixels=True):
        (self.p/'qa/visual-hygiene-review.json').write_text(json.dumps(self.record));return review(self.p,self.doc,self.video,pixels)
    def test_new_policy_and_all_scenes_with_real_encoded_pixels(self):
        self.assertTrue(policy()['visualHygieneRequired']);self.assertEqual(self.check()['status'],'pass')
    def test_new_spatial_review_requires_actual_support_and_typography_observations(self):
        self.doc['qualityPolicy']['spatialReviewRequired']=True;(self.p/'workbench.json').write_text(json.dumps(self.doc));self.record['documentSha256']=sha(self.p/'workbench.json')
        self.assertEqual(self.check(False)['status'],'pending')
        for row in self.record['sceneReviews']:row.update(physicalSupport='Observed the drawn object supported by its surface',typography='No visible text overlaps the object')
        self.assertEqual(self.check()['status'],'pass')
    def test_missing_scene_missing_observation_and_unresolved_issue_are_pending(self):
        for change in ['scene','observation','issue']:
            original=copy.deepcopy(self.record)
            if change=='scene':self.record['sceneReviews'].pop()
            elif change=='observation':self.record['sceneReviews'][0].pop('animationResidue')
            else:self.record['unresolvedIssues']=['unfixed endpoint dot']
            with self.subTest(change=change):self.assertEqual(self.check(False)['status'],'pending')
            self.record=original
    def test_stale_video_preview_and_wrong_encoded_frame_cannot_pass(self):
        for change in ['hash','preview','frame','path']:
            original=copy.deepcopy(self.record)
            if change=='hash':self.record['videoSha256']='old'
            elif change=='preview':self.record['sceneReviews'][0]['evidenceFrames'][0]['origin']='native-preview'
            elif change=='frame':self.record['sceneReviews'][0]['evidenceFrames'][0]['encodedFrame']=15
            else:self.record['sceneReviews'][0]['evidenceFrames'][0]['path']='../../outside.png'
            with self.subTest(change=change):self.assertEqual(self.check()['status'],'pending')
            self.record=original
    def test_legacy_opt_in_and_marker_prevents_removing_the_requirement(self):
        self.assertEqual(review(self.p,{},self.video)['status'],'legacy-not-opted-in')
        (self.p/'craft-contract.json').write_text('{"visualHygieneRequired":true}')
        self.doc['qualityPolicy'].pop('visualHygieneRequired')
        self.assertEqual(self.check(False)['status'],'pending')

if __name__=='__main__':unittest.main()
