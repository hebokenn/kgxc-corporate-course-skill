"""Synthetic content hashes and selective invalidation; no media/hearing claims."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from evidence_versions import fingerprint,freeze_inputs,check_frozen,validate_evidence,invalidate_dependents,sha


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project';self.p.mkdir()
        for name in ['script.md','audio.wav','report.json']:(self.p/name).write_bytes(('synthetic-'+name).encode())
    def tearDown(self):self.tmp.cleanup()
    def test_actual_input_hash_and_render_drift(self):
        frozen=freeze_inputs(self.p,dict(script='script.md',narration='audio.wav'),'render1')
        self.assertTrue(check_frozen(self.p,frozen)['ready'])
        (self.p/'audio.wav').write_bytes(b'changed')
        self.assertFalse(check_frozen(self.p,frozen)['ready'])
        self.assertEqual(check_frozen(self.p,frozen)['errors'][0]['code'],'INPUT_CHANGED_DURING_RENDER')
        with self.assertRaisesRegex(ValueError,'INPUT_CHANGED'):freeze_inputs(self.p,dict(script='script.md',narration='audio.wav'),'render1')
    def evidence(self):
        return dict(path='report.json',sha256=sha(self.p/'report.json'),actor='fixture',method='synthetic-text-inspection',scope='one fixture',parents=dict(audio_sha256=sha(self.p/'audio.wav')),status='verified')
    def test_current_parent_and_scope_required(self):
        e=self.evidence();current=dict(audio_sha256=sha(self.p/'audio.wav'))
        self.assertEqual(validate_evidence(self.p,e,current),[])
        e['parents']['audio_sha256']='0'*64
        self.assertIn('EVIDENCE_STALE',{x['code']for x in validate_evidence(self.p,e,current)})
        e=self.evidence();e.pop('method')
        self.assertTrue(validate_evidence(self.p,e,current))
    def test_updating_timestamp_does_not_refresh_old_evidence(self):
        e=self.evidence();(self.p/'report.json').write_text('new report');e['checked_at']='tomorrow'
        self.assertIn('EVIDENCE_STALE',{x['code']for x in validate_evidence(self.p,e,dict(audio_sha256=sha(self.p/'audio.wav')))})
    def test_encoded_frames_cannot_bind_only_unchanged_document(self):
        e=self.evidence();e.update(method='encoded-frames',parents=dict(document_sha256='same'))
        self.assertIn('EVIDENCE_STALE',{x['code']for x in validate_evidence(self.p,e,dict(document_sha256='same',video_sha256='new-video'))})
    def test_only_affected_dependencies_invalidated_and_old_evidence_kept(self):
        a=dict(id='a',status='verified',implementation_refs=['impl'],evidence_refs=[self.evidence()],changes=[])
        b=copy.deepcopy(a);b['id']='b';b['evidence_refs'][0]['parents']=dict(document_sha256='fixed')
        original=dict(obligations=[a,b]);value,affected=invalidate_dependents(original,['audio_sha256'])
        self.assertEqual(affected,['a']);self.assertEqual(value['obligations'][1],b)
        self.assertEqual(original['obligations'][0]['status'],'verified')
        self.assertEqual(value['obligations'][0]['status'],'implemented_unverified')
        self.assertEqual(value['obligations'][0]['changes'][0]['previous_evidence'][0]['status'],'verified')
    def test_fingerprint_includes_bytes_not_filename_only(self):
        old=fingerprint(self.p,dict(script='script.md'))
        (self.p/'script.md').write_text('new contents')
        self.assertNotEqual(old['sha256'],fingerprint(self.p,dict(script='script.md'))['sha256'])
    def test_physical_requirement_review_invalidates_without_losing_unrelated_proof(self):
        c=dict(requirements=dict(sfx=dict(review=dict(status='verified',audio_sha256='old',scope='encoded signal')),
            logo=dict(review=dict(status='verified',document_sha256='same',scope='finite logo pixels'))))
        value,affected=invalidate_dependents(c,['audio_sha256'])
        self.assertEqual(affected,['requirements.sfx']);self.assertEqual(value['requirements']['logo'],c['requirements']['logo'])
        self.assertEqual(value['requirements']['sfx']['review']['status'],'unverified')
        self.assertEqual(value['requirements']['sfx']['review_history'][0]['status'],'verified')

if __name__=='__main__':unittest.main()
