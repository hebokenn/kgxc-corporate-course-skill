"""Character identity, approval and unsupported-action boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from character_assets import check,stage,sha
from PIL import Image


class CharacterAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.folder=self.p/'character';self.folder.mkdir()
        image=Image.new('RGBA',(600,900),(0,0,0,0));image.paste((80,140,110,255),(150,30,450,870));image.save(self.folder/'master.png');image.save(self.folder/'design.png')
        self.profile=self.folder/'profile.json'
        self.doc=dict(schema='course-character/1',id='C',assets=dict(master=dict(path='master.png',sha256=sha(self.folder/'master.png')),design=dict(path='design.png',sha256=sha(self.folder/'design.png'))),approval=dict(stage='design',evidence='QA fixture only',approvedFiles=[dict(sha256=sha(self.folder/'design.png'))]),views=dict(full=dict(crop=[0,0,1,1]),half=dict(crop=[0,0,1,.6])),performance=dict(validated=['static-full','static-half']))
        self.write();(self.p/'course/project').mkdir(parents=True);(self.p/'course/project/workbench.json').write_text('{}')
    def write(self):self.profile.write_text(json.dumps(self.doc))
    def tearDown(self):self.tmp.cleanup()
    def test_full_and_half_views_preserve_the_same_actual_master(self):
        a=stage(self.profile,self.p/'course',view='full');b=stage(self.profile,self.p/'course',view='half',action='static-half')
        self.assertEqual(a['asset'],b['asset']);self.assertNotEqual(a['node']['crop'],b['node']['crop']);self.assertTrue(check(self.profile)['designApproved'])
    def test_unapproved_design_cannot_be_staged(self):
        self.doc['approval']=None;self.write()
        with self.assertRaisesRegex(ValueError,'确认未通过'):stage(self.profile,self.p/'course')
    def test_unvalidated_natural_motion_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'尚未验证动作'):stage(self.profile,self.p/'course',action='natural-walk')
    def test_changed_asset_invalidates_the_profile(self):
        with (self.folder/'master.png').open('ab') as f:f.write(b'changed')
        self.assertFalse(check(self.profile)['ok'])


if __name__=='__main__':unittest.main()
