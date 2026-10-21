"""Regression tests for the observed sample-to-full quality failure."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from motion_quality import preflight,require,audit_encoded,director_review
from render_routes import plan,effect_errors
from motion_catalog import CATALOG,TEACHING
from teaching_modules import expand


def fixture():
    return dict(fps=30,sourceDurationFrames=90,introFrames=0,bodyEndFrame=90,
        motionPolicy=dict(required=True),rendering=dict(route='motion-canvas'),
        scenes=[dict(id='S',sourceStartFrame=0,sourceEndFrame=90)],
        captions=[dict(id='C',startFrame=0,endFrame=90,text='请观察交接过程')],
        sceneGraph=dict(nodes=[dict(id='phone',type='rect',sceneId='S',role='subject',width=100,height=200,
            effects=[dict(type='handoff',startFrame=0,endFrame=60,dx=300)])]),
        motionPlan=dict(schema='course-motion-plan/1',language='object-demo',protectedEffects=['handoff'],beats=[
            dict(id='A',sceneId='S',startFrame=0,endFrame=60,objectIds=['phone'],purpose='看清交接',before='顾问持有',after='顾客接到'),
            dict(id='R',sceneId='S',kind='observe',startFrame=60,endFrame=90,reason='看清交接后的持有者')]))


class MotionContractTests(unittest.TestCase):
    def test_real_inventory_exceeds_30_teaching_actions_without_counting_styles(self):
        self.assertGreaterEqual(len(TEACHING),31)
        self.assertNotIn('gradient',CATALOG);self.assertNotIn('camera',CATALOG)
        self.assertNotIn('papercut',CATALOG)  # A composition is not another action.

    def test_action_and_intentional_reading_cover_the_actual_narration(self):
        self.assertEqual(preflight(fixture())['status'],'pass')

    def test_edited_hold_and_cut_map_narration_back_to_actual_source_actions(self):
        doc=fixture();doc['holds']=[dict(sourceFrame=30,frames=30)];doc['captions'][0]['endFrame']=120
        self.assertEqual(preflight(doc)['status'],'pass')
        doc=fixture();doc['cuts']=[dict(startFrame=0,endFrame=30)];doc['captions'][0]['endFrame']=60
        self.assertEqual(preflight(doc)['status'],'pass')
        doc['motionPlan']['beats'][0]['endFrame']=45
        self.assertEqual(preflight(doc)['status'],'fail')

    def test_short_intro_animation_cannot_cover_a_long_narration_beat(self):
        doc=fixture();doc['motionPlan']['beats'][0]['endFrame']=90;doc['motionPlan']['beats'].pop()
        self.assertEqual(preflight(doc)['status'],'fail')
        self.assertTrue(any('窗口长于' in x for x in preflight(doc)['errors']))

    def test_deleted_motion_and_uncovered_voice_are_rejected(self):
        doc=fixture();doc['sceneGraph']['nodes'][0]['effects']=[]
        self.assertEqual(preflight(doc)['status'],'fail')
        doc=fixture();doc['motionPlan']['beats'].pop()
        self.assertTrue(any('旁白缺少' in x for x in preflight(doc)['errors']))

    def test_titles_and_invented_object_ids_cannot_replace_subject_actions(self):
        doc=fixture();doc['sceneGraph']['nodes'][0]['role']='decoration'
        self.assertEqual(preflight(doc)['status'],'fail')
        doc=fixture();doc['motionPlan']['beats'][0]['objectIds']=['pretend']
        self.assertEqual(preflight(doc)['status'],'fail')

    def test_claimed_effects_and_renamed_native_routes_do_not_prove_implementation(self):
        spec=dict(sourceDurationFrames=90,sceneGraph=dict(nodes=[]),rendering=dict(requiredEffects=['handoff']))
        self.assertTrue(effect_errors(spec))
        self.assertFalse(plan(dict(sceneGraph=fixture()['sceneGraph'],rendering=dict(route='scene-graph')))['ready'])
        doc=fixture();doc['rendering']['route']='native-canvas'
        self.assertTrue(any('原生路线' in x for x in preflight(doc)['errors']))

    def test_new_project_cannot_delete_policy_to_pose_as_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'motion-contract.json').write_text('{}');doc=fixture();doc.pop('motionPolicy');doc.pop('motionPlan')
            with self.assertRaisesRegex(ValueError,'不能删除'):require(doc,p)

    def test_external_review_cannot_complete_new_project_with_deleted_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'motion-contract.json').write_text('{}');video=p/'candidate.mp4';video.write_bytes(b'candidate')
            result=director_review(p,dict(sourceDurationFrames=1),video)
            self.assertEqual(result['status'],'pending')
            self.assertTrue(result['errors'])

    def test_frozen_legacy_course_remains_opt_in(self):
        self.assertEqual(preflight(dict(sourceDurationFrames=1))['status'],'legacy-not-opted-in')

    def test_module_requires_course_content_and_actual_absolute_beats(self):
        spec=dict(sourceDurationFrames=90,scenes=[dict(id='S',sourceStartFrame=0,sourceEndFrame=90)],sceneGraph=dict(modules=[dict(id='M',module='papercut',sceneId='S',data=dict(title='使用场景',phases=[dict(title='接待前',labels=['状态准备'])]))]))
        with self.assertRaisesRegex(ValueError,'实际讲解节拍'):expand(spec)
        spec['sceneGraph']['modules'][0]['beats']=[dict(startFrame=0,endFrame=90)]
        compiled=expand(spec)
        self.assertTrue(compiled['sceneGraph']['nodes'])
        self.assertEqual(compiled['teachingModules'][0]['source']['data']['phases'][0]['labels'],['状态准备'])

    def test_missing_director_review_never_marks_generated_video_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);video=p/'video.mp4';video.write_bytes(b'candidate')
            self.assertEqual(director_review(p,fixture(),video)['status'],'pending')


class EncodedSubjectTests(unittest.TestCase):
    def test_caption_motion_alone_fails_but_real_subject_motion_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);doc=fixture();doc['motionPlan']['beats'][0]['endFrame']=90;doc['sceneGraph']['nodes'][0]['effects'][0]['endFrame']=90;doc['motionPlan']['beats'].pop()
            static=p/'caption-only.mp4';moving=p/'subject.mp4'
            for out,y in [(static,950),(moving,450)]:
                command=['ffmpeg','-y','-v','error','-f','lavfi','-i','color=white:s=1920x1080:r=30:d=3',
                    '-f','lavfi','-i','color=0x397a69:s=300x120:r=30:d=3','-filter_complex',f'[0:v][1:v]overlay=x=300+t*200:y={y}',
                    '-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',str(out)]
                subprocess.run(command,check=True)
            self.assertEqual(audit_encoded(static,doc,0,90)['status'],'fail')
            self.assertEqual(audit_encoded(moving,doc,0,90)['status'],'pass')


if __name__=='__main__':unittest.main()
