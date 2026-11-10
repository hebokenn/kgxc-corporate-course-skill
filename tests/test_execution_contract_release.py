"""Central gate integration contract, synthetic adapters only: no real AV acceptance."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
import release_gate
from evidence_versions import sha
from execution_requirements import update
from handoff_contract import create,submit
from test_execution_contract_requirements import obligation


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.p=self.root/'project';self.p.mkdir()
        self.document=self.p/'current.json';self.document.write_text(json.dumps(dict(sourceDurationFrames=20,sceneGraph=dict(nodes=[]))))
        self.video=self.p/'arbitrary-current-name.mp4';self.video.write_bytes(b'synthetic fixture; not a playable movie')
        self.proof=self.p/'review.json';self.proof.write_text('Synthetic exact-scope evidence, no AV claim')
        row=obligation(stage='script');update(self.p,[row])
        task=dict(task_id='task1',requirement_ids=[row['id']],inputs=[dict(path='current.json',sha256=sha(self.document))],
            owned_scope=['review.json'],forbidden_scope=[],quotes={row['id']:row['original_quote']},actual_objects=[],choices={},
            return_files=['review.json'],required_checks=['check1'],purpose='script',issue_ids=[])
        create(self.p,task)
        result=dict(task_id='task1',requirement_ids=[row['id']],output_paths=[dict(path='review.json',sha256=sha(self.proof))],object_bindings=[],
            checks_run=[dict(id='check1',status='passed',evidence_ref='review.json')],evidence_refs=[dict(path='review.json',sha256=sha(self.proof))],
            unresolved_items=[],issue_ids=[])
        self.assertTrue(submit(self.p,result,json.loads(self.document.read_text()))['ready'])
        c=json.loads((self.p/'production-contract.json').read_text());c['course_id']='synthetic-course';r=c['obligations'][0]
        r['status']='verified';r['evidence_refs']=[dict(path='review.json',sha256=sha(self.proof),actor='fixture',method='synthetic-inspection',scope='fixture-only',parents=dict(document_sha256=sha(self.document)),status='verified')]
        (self.p/'production-contract.json').write_text(json.dumps(c))
        self.ctx=dict(course_id='synthetic-course',purpose='script',current_document='current.json',current_video=None,
            current_contract='production-contract.json',current_review_refs=[dict(path='review.json',sha256=sha(self.proof))])
        self.modules=mock.patch.dict(sys.modules,{
            'production_validation':types.SimpleNamespace(inspect_extra=lambda p,c:dict(ready=True,errors=[],evidence_refs=[])),
            'final_media_checks':types.SimpleNamespace(inspect=lambda p,c:dict(ready=True,errors=[],evidence_refs=[]))})
        self.modules.start()
    def tearDown(self):self.modules.stop();self.tmp.cleanup()
    def media(self):
        c=copy.deepcopy(self.ctx);c.update(purpose='final',current_video=str(self.video))
        return c
    def test_early_stage_does_not_require_future_media(self):
        out=release_gate.evaluate(self.p,self.ctx)
        self.assertTrue(out['allow_release'],out['errors']);self.assertNotIn('contract',out['checks'])
        c=self.media()
        with mock.patch('production_contract.inspect',return_value=dict(ready=False,errors=[])),mock.patch('production_preferences.review_errors',return_value=[]):
            self.assertFalse(release_gate.evaluate(self.p,c)['allow_release'])
    def test_all_fixed_checks_are_consumed_for_media(self):
        c=self.media()
        with mock.patch('production_contract.inspect',return_value=dict(ready=True,errors=[]))as contract,mock.patch('production_preferences.review_errors',return_value=[])as prefs:
            out=release_gate.evaluate(self.p,c);self.assertTrue(out['allow_release'],out['errors'])
            contract.assert_called_once();self.assertEqual(prefs.call_args.kwargs['document'],self.document.resolve())
    def test_untrusted_allow_or_callback_cannot_authorize(self):
        for key,value in [('allow_release',True),('final_media_checker',lambda *_:dict(ready=True)),('skip',True)]:
            c=copy.deepcopy(self.ctx);c[key]=value
            self.assertFalse(release_gate.evaluate(self.p,c)['allow_release'])
        c=copy.deepcopy(self.ctx);c['input_refs']={'fake':lambda:True}
        self.assertFalse(release_gate.evaluate(self.p,c)['allow_release'])
    def test_missing_checker_exception_unknown_and_nonboolean_are_closed(self):
        cases=[dict(ready=None,errors=[]),dict(ready=1,errors=[]),dict(ready=True,errors=[],critical_unknown=['hearing unknown'])]
        for value in cases:
            with mock.patch.object(sys.modules['final_media_checks'],'inspect',return_value=value):
                self.assertFalse(release_gate.evaluate(self.p,self.ctx)['allow_release'])
        with mock.patch.object(sys.modules['final_media_checks'],'inspect',side_effect=ImportError('missing checker')):
            self.assertIn('GATE_NOT_EXECUTED',{x['code']for x in release_gate.evaluate(self.p,self.ctx)['errors']})
    def test_old_review_and_changed_doc_cannot_pass(self):
        self.proof.write_text('changed bytes')
        out=release_gate.evaluate(self.p,self.ctx)
        self.assertFalse(out['allow_release']);self.assertIn('EVIDENCE_STALE',{x['code']for x in out['errors']})
    def test_false_contract_or_preferences_cannot_pass_custom_entry(self):
        c=self.media();c['entrypoint']='custom-script'
        with mock.patch('production_contract.inspect',return_value=dict(ready=False,errors=[dict(code='EMPHASIS_UNIMPLEMENTED',message='events empty')])) ,mock.patch('production_preferences.review_errors',return_value=[]):
            self.assertFalse(release_gate.evaluate(self.p,c)['allow_release'])
        with mock.patch('production_contract.inspect',return_value=dict(ready=True,errors=[])),mock.patch('production_preferences.review_errors',return_value=['unimplemented customer']):
            self.assertFalse(release_gate.evaluate(self.p,c)['allow_release'])
    def test_changed_input_during_check_is_detected(self):
        def changing(p,c):
            self.document.write_text('modified while checking');return dict(ready=True,errors=[])
        with mock.patch.object(sys.modules['final_media_checks'],'inspect',side_effect=changing):
            self.assertIn('RELEASE_INPUT_CHANGED',{e['code']for e in release_gate.evaluate(self.p,self.ctx)['errors']})
    def delivery(self):
        f=dict(source=str(self.document),destination=str(self.root/'formal/course/current.json'),sha256=sha(self.document),role='document')
        c=copy.deepcopy(self.ctx);c['delivery_files']=[f]
        return c,[f]
    def test_real_copy_and_postcopy_hash_and_previous_delivery_retained(self):
        c,files=self.delivery();dst=Path(files[0]['destination']);dst.parent.mkdir(parents=True);dst.write_bytes(b'previous formal')
        out=release_gate.deliver(self.p,c,files)
        self.assertEqual(out['status'],'stage_artifact_copied');self.assertFalse(out['formally_delivered']);self.assertEqual(sha(dst),sha(self.document))
        self.assertTrue(list((self.p/'work/delivery-history').glob('*')));self.assertFalse(out['permission_isolation_verified'])
    def test_blocked_copy_writes_no_formal_directory(self):
        c,files=self.delivery();self.proof.write_text('stale')
        with self.assertRaises(release_gate.ReleaseBlocked):release_gate.deliver(self.p,c,files)
        self.assertFalse((self.root/'formal').exists())
    def test_corrupted_copy_does_not_replace_old_formal_or_record_complete(self):
        c,files=self.delivery();dst=Path(files[0]['destination']);dst.parent.mkdir(parents=True);dst.write_text('old')
        def corrupt(src,dst):Path(dst).write_bytes(b'bad copy')
        with mock.patch('release_gate.shutil.copyfile',side_effect=corrupt):
            with self.assertRaises(release_gate.ReleaseBlocked):release_gate.deliver(self.p,c,files)
        self.assertEqual(dst.read_text(),'old')
    def test_manual_receipt_is_not_accepted_as_context(self):
        c,files=self.delivery();c['receipt']=dict(allow_release=True)
        with self.assertRaises(release_gate.ReleaseBlocked):release_gate.deliver(self.p,c,files)
        self.assertFalse((self.root/'formal').exists())
    def final_delivery(self):
        files=[]
        for role,name in [('video',self.video.name),('subtitles','fixture.srt'),('cover','fixture.png')]:
            src=self.p/name
            if not src.exists():src.write_bytes(('synthetic-'+role).encode())
            files.append(dict(source=str(src),destination=str(self.root/'formal/course'/name),sha256=sha(src),role=role))
        c=self.media();c['purpose']='delivery';c['delivery_files']=files
        return c,files
    def test_final_copy_requires_three_roles_and_fixed_finder_adapter(self):
        c,files=self.final_delivery()
        with mock.patch('production_contract.inspect',return_value=dict(ready=True,errors=[])),mock.patch('production_preferences.review_errors',return_value=[]),mock.patch('delivery_visibility.verify_finder_files',side_effect=ValueError('native adapter unavailable')):
            with self.assertRaisesRegex(ValueError,'native adapter'):release_gate.deliver(self.p,c,files)
        receipts=[json.loads(p.read_text())for p in (self.p/'qa/release-gate').glob('copy-*.json')]
        self.assertEqual(receipts[-1]['status'],'acceptance_blocked');self.assertIs(receipts[-1]['formally_delivered'],False)
        self.assertTrue(all(Path(f['destination']).is_file()for f in files))
    def test_fixed_adapter_success_fixture_records_copy_hashes_not_user_acceptance(self):
        c,files=self.final_delivery()
        with mock.patch('production_contract.inspect',return_value=dict(ready=True,errors=[])),mock.patch('production_preferences.review_errors',return_value=[]),mock.patch('delivery_visibility.verify_finder_files',return_value=dict(status='verified',method='synthetic fixed-adapter mock, not an actual Finder observation')):
            result=release_gate.deliver(self.p,c,files)
        self.assertTrue(result['formally_delivered']);self.assertFalse(result['user_acceptance'])
        self.assertTrue(all(f['source_sha256_before']==f['source_sha256_after']==f['destination_sha256']for f in result['files']))

if __name__=='__main__':unittest.main()
