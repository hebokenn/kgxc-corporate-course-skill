import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/'skills/corporate-training-motion'
sys.path.insert(0,str(ROOT/'workbench'))
from layered_customers import PRESETS,catalog,stage,design_for_course
from acting import stage as stage_actor,conversation_errors,motion_intervals


class LayeredCustomerTests(unittest.TestCase):
    def test_presets_are_distinct_multipart_customers_with_different_hair_and_clothes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp);(project/'workbench.json').write_text('{}')
            looks=[]
            for key in PRESETS:
                result=stage(key,dict(sceneId='scene',x=300,floorY=700,endFrame=90),project,ROOT)
                node=result['node'];actor=node['vectorActor']
                self.assertEqual(node['type'],'group');self.assertEqual(actor['characterRole'],'customer')
                self.assertNotIn('assetId',node);self.assertNotIn('logoAsset',actor)
                looks.append((actor['hair'],actor['shirt'],actor['shirtColor']))
            self.assertEqual(len(set(v[0] for v in looks)),3)
            self.assertEqual(len(set(v[1] for v in looks)),3)
            self.assertEqual(len(set(looks)),3)
    def test_preset_overrides_are_scoped_and_unknown_appearance_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp);(project/'workbench.json').write_text('{}')
            placement=dict(sceneId='scene',x=300,floorY=700,endFrame=90)
            value=stage('V01',placement,project,ROOT,dict(identity='new',hair='pony',characterRole='store_manager'))
            self.assertEqual(value['node']['id'],'new');self.assertEqual(value['node']['vectorActor']['characterRole'],'customer')
            with self.assertRaises(ValueError):stage('C01',placement,project,ROOT)
            with self.assertRaises(ValueError):stage('V01',placement,project,ROOT,dict(hair='unknown'))
            with self.assertRaises(ValueError):stage('V01',placement,project,ROOT,dict(outfit='unknown'))
    def test_catalog_returns_independent_designs_and_preview_of_same_family(self):
        first=catalog();first[0]['design']['hair']='changed'
        second=catalog();self.assertEqual(second[0]['design']['hair'],'side-part')
        self.assertTrue(all(v['representation']=='solid-vector-acting/1' for v in second))
    def test_course_design_varies_between_courses_and_is_stable_on_resume(self):
        first=design_for_course('course-one','visitor-one')
        self.assertEqual(first,design_for_course('course-one','visitor-one'))
        people=[design_for_course('course-'+str(i),'visitor-one') for i in range(10)]
        self.assertGreater(len({(p['hair'],p['outfit'],p['shirtColor']) for p in people}),5)
        self.assertEqual(design_for_course('course-one','visitor-one',dict(hair='pony',shirtColor='#123456'))['hair'],'pony')


if __name__=='__main__':unittest.main()


class DialoguePresenceTests(unittest.TestCase):
    def doc(self):
        speaker=dict(id='speaker',type='group',sceneId='scene',x=100,startFrame=0,endFrame=100,vectorActor=dict(facing=[dict(frame=0,yaw=.5)],speech=[dict(startFrame=20,envelope=[.8]*30)],targets=[dict(frame=0,id='listener')]))
        listener=dict(id='listener',type='group',sceneId='scene',x=400,startFrame=0,endFrame=100,vectorActor=dict(facing=[dict(frame=0,yaw=-.5)]))
        return dict(sourceDurationFrames=100,sceneGraph=dict(nodes=[speaker,listener]))
    def test_visible_recipient_and_right_direction_pass(self):
        self.assertEqual(conversation_errors(self.doc()),[])
    def test_absent_offscreen_and_other_scene_recipients_fail(self):
        for field,value in [('sceneId','other'),('startFrame',25),('endFrame',40)]:
            doc=self.doc();doc['sceneGraph']['nodes'][1][field]=value;self.assertTrue(conversation_errors(doc))
        doc=self.doc();doc['sceneGraph']['nodes'].pop();self.assertTrue(conversation_errors(doc))
    def test_reversed_head_fails_even_when_both_actors_exist(self):
        doc=self.doc();doc['sceneGraph']['nodes'][0]['vectorActor']['facing'][0]['yaw']=-.5
        self.assertTrue(any('背向' in item for item in conversation_errors(doc)))
    def test_viewer_address_is_explicit_and_not_an_automatic_missing_person_fallback(self):
        doc=self.doc();doc['sceneGraph']['nodes'].pop();doc['sceneGraph']['nodes'][0]['vectorActor']['speech'][0]['audience']='viewer'
        self.assertEqual(conversation_errors(doc),[])


class ActorImplementationTests(unittest.TestCase):
    def test_true_head_gesture_and_walk_are_implemented_without_a_proxy_line(self):
        node=dict(startFrame=0,vectorActor=dict(facing=[dict(frame=0,yaw=-.5),dict(frame=20,yaw=.5)],keys=[dict(frame=20,values=dict(gesture=0)),dict(frame=30,values=dict(gesture=.4))],walks=[dict(startFrame=40,endFrame=60,fromX=100,toX=200)]))
        spans=motion_intervals(node);self.assertIn((0,20),spans);self.assertIn((20,30),spans);self.assertIn((40,60),spans)
    def test_static_pose_and_speech_only_are_not_a_subject_action(self):
        node=dict(startFrame=0,vectorActor=dict(facing=[dict(frame=0,yaw=.5),dict(frame=20,yaw=.5)],keys=[dict(frame=0,values=dict(gesture=0)),dict(frame=20,values=dict(gesture=0))],speech=[dict(startFrame=0,envelope=[.8]*20)]))
        self.assertEqual(motion_intervals(node),[])
