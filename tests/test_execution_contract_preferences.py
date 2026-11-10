"""Explicit current document and truthful producer adoption, synthetic local files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
import production_preferences as prefs
from evidence_versions import sha


class ExplicitPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project';self.p.mkdir()
        self.doc=self.p/'explicit.json';self.doc.write_text(json.dumps(dict(sceneGraph=dict(nodes=[]),media={})))
        self.video=self.p/'human-readable-filename.mp4';self.video.write_bytes(b'synthetic-only')
    def tearDown(self):self.tmp.cleanup()
    def test_explicit_document_does_not_need_hash_filename_or_export_projection(self):
        self.assertEqual(prefs.material_errors(self.p,self.video,dict(customer='none',flower_text='off',sound_effects='off'),{},document=self.doc),[])
        self.assertTrue(prefs.material_errors(self.p,self.video,dict(customer='none',flower_text='off',sound_effects='off'),{}))
    def test_explicit_review_rejects_old_document_and_unverified_review(self):
        choices=dict(customer='none',flower_text='off',sound_effects='off')
        value=dict(required=True,choices=choices)
        proof=dict(choices_sha256='choice',video_sha256=sha(self.video),document_sha256=sha(self.doc),status='verified',actor='fixture',evidence='synthetic finite check',
            observations=dict(customer='none seen in fixture',flower_text='disabled',sound_effects='disabled'),implemented=dict(customer_ids=[],flower_count=0,sfx_count=0))
        path=self.p/'qa/production-preferences-final-review.json';path.parent.mkdir();path.write_text(json.dumps(proof))
        with mock.patch.object(prefs,'selection_errors',return_value=[]),mock.patch.object(prefs,'load',return_value=value),mock.patch.object(prefs,'choice_digest',return_value='choice'):
            self.assertEqual(prefs.review_errors(self.p,'final',self.video,document=self.doc),[])
            self.doc.write_text('{}')
            self.assertTrue(prefs.review_errors(self.p,'final',self.video,document=self.doc))
    def test_delegated_actual_adoption_does_not_fabricate_human_confirmation(self):
        profile=self.p/'profile.json';profile.write_text('{"identity":"fixture-customer"}')
        event=self.p/'delegation.json';event.write_text(json.dumps(dict(event_id='synthetic-delegation',actor_type='user',original_quote='Choose the creative design for this course',scopes=['creative_choices'])))
        path=self.p/'production-preferences.json';path.write_text(json.dumps(dict(choices=dict(customer='new',flower_text='off',sound_effects='off'),new_customer={})))
        result=prefs.record_design_adoption(self.p,'profile.json','fixture-producer','actual synthetic profile adopted',dict(path='delegation.json',sha256=sha(event)))
        self.assertTrue(result['new_customer_ready'])
        raw=json.loads(path.read_text());self.assertNotIn('design_approval',raw['new_customer'])
        self.assertIs(raw['new_customer']['design_adoption']['human_clicked'],False)
        profile.write_text('{"identity":"changed"}')
        self.assertFalse(prefs.load(self.p)['new_customer_ready'])
    def test_unscoped_or_changed_delegation_cannot_adopt(self):
        profile=self.p/'profile.json';profile.write_text('{}')
        event=self.p/'delegation.json';event.write_text(json.dumps(dict(event_id='fixture',actor_type='user',original_quote='No intermediate questions',scopes=['interaction_only'])))
        (self.p/'production-preferences.json').write_text(json.dumps(dict(choices=dict(customer='new'),new_customer={})))
        with self.assertRaises(ValueError):prefs.record_design_adoption(self.p,'profile.json','producer','actual profile',dict(path='delegation.json',sha256=sha(event)))

if __name__=='__main__':unittest.main()
