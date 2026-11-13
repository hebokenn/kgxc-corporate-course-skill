"""Synthetic dispatch/return traceability and ancestor visibility regressions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from handoff_contract import create,submit,validate_result,inspect
from evidence_versions import sha
from execution_requirements import update
from test_execution_contract_requirements import obligation


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project';self.p.mkdir()
        self.doc=dict(sourceDurationFrames=100,sceneGraph=dict(nodes=[dict(id='container',type='group',startFrame=0,endFrame=100,
            children=[dict(id='subject',type='text',text='Keep conditions',startFrame=10,endFrame=90)])]))
        (self.p/'document.json').write_text(json.dumps(self.doc));(self.p/'output.json').write_text('synthetic rendered description')
        (self.p/'check.json').write_text('synthetic check result')
        self.row=obligation(stage='script');update(self.p,[self.row])
        self.task=dict(task_id='task1',requirement_ids=[self.row['id']],inputs=[dict(path='document.json',sha256=sha(self.p/'document.json'))],
            owned_scope=['output.json'],forbidden_scope=['audio/'],quotes={self.row['id']:self.row['original_quote']},actual_objects=['subject'],
            choices=dict(emphasis='dedicated'),return_files=['output.json'],required_checks=['object-check'],purpose='script',issue_ids=['ISSUE-1'])
        self.result=dict(task_id='task1',requirement_ids=[self.row['id']],output_paths=[dict(path='output.json',sha256=sha(self.p/'output.json'))],
            object_bindings=[dict(event_id='event1',quote='Keep conditions',object_ids=['subject'],allowed_types=['text'],frame_range=[20,80])],
            checks_run=[dict(id='object-check',status='passed',evidence_ref='check.json')],evidence_refs=[dict(path='check.json',sha256=sha(self.p/'check.json'))],
            unresolved_items=[],issue_ids=['ISSUE-1'])
    def tearDown(self):self.tmp.cleanup()
    def codes(self,result=None,doc=None):
        return {e['code']for e in validate_result(self.p,self.task,result or self.result,doc or self.doc)}
    def test_good_handoff_returns_unverified_and_backlinks_master(self):
        self.assertTrue(create(self.p,self.task)['ready'])
        self.assertTrue(submit(self.p,self.result,self.doc)['ready'])
        c=json.loads((self.p/'production-contract.json').read_text())
        self.assertEqual(c['obligations'][0]['status'],'implemented_unverified')
        self.assertTrue(c['obligations'][0]['implementation_refs'][0]['task_id']=='task1')
        self.assertTrue(inspect(self.p,dict(purpose='script',current_document='document.json'))['ready'])
    def test_dispatch_missing_requirements_or_changed_input_rejected(self):
        task=copy.deepcopy(self.task);task['requirement_ids']=['missing']
        self.assertFalse(create(self.p,task)['ready'])
        (self.p/'document.json').write_text('{}')
        self.assertEqual(create(self.p,self.task)['errors'][0]['code'],'HANDOFF_INPUT_CHANGED')
    def test_nonexistent_object_and_empty_mapping_do_not_pass(self):
        r=copy.deepcopy(self.result);r['object_bindings'][0]['object_ids']=['missing']
        self.assertIn('HANDOFF_OBJECT_MISSING',self.codes(r))
        r['object_bindings']=[]
        self.assertIn('HANDOFF_BINDING_MISSING',self.codes(r))
    def test_parent_visibility_and_shortened_lifetime_invalidate_binding(self):
        d=copy.deepcopy(self.doc);d['sceneGraph']['nodes'][0]['endFrame']=50
        self.assertIn('HANDOFF_OBJECT_INVALID',self.codes(doc=d))
        d=copy.deepcopy(self.doc);d['sceneGraph']['nodes'][0]['opacity']=0
        self.assertIn('HANDOFF_OBJECT_INVALID',self.codes(doc=d))
    def test_result_cannot_erase_issue_or_claim_missing_check(self):
        r=copy.deepcopy(self.result);r['issue_ids']=[];r['checks_run']=[]
        self.assertIn('HANDOFF_ISSUE_LOST',self.codes(r));self.assertIn('HANDOFF_CHECK_MISSING',self.codes(r))
    def test_output_removed_or_hash_changed_returns_incomplete(self):
        create(self.p,self.task);(self.p/'output.json').unlink()
        result=submit(self.p,self.result,self.doc)
        self.assertFalse(result['ready']);self.assertEqual(result['status'],'returned_incomplete')
    def test_return_outside_owned_scope_or_in_forbidden_scope_is_rejected(self):
        self.task['forbidden_scope']=['output.json']
        self.assertIn('HANDOFF_SCOPE_VIOLATION',self.codes())
        self.task['forbidden_scope']=[];self.task['owned_scope']=['another.json']
        self.assertIn('HANDOFF_SCOPE_VIOLATION',self.codes())
    def test_restored_dispatch_must_keep_exact_quotes_and_automatic_result_hash(self):
        create(self.p,self.task);incoming=copy.deepcopy(self.result);incoming['dispatch_sha256']='producer-cannot-authorize'
        self.assertTrue(submit(self.p,incoming,self.doc)['ready'])
        result=json.loads((self.p/'work/handoffs/task1-result.json').read_text())
        self.assertEqual(result['dispatch_sha256'],sha(self.p/'work/handoffs/task1.json'))
        self.assertTrue(inspect(self.p,dict(purpose='script',current_document='document.json'))['ready'])
        dispatch=self.p/'work/handoffs/task1.json';d=json.loads(dispatch.read_text());d.pop('quotes');dispatch.write_text(json.dumps(d))
        codes={e['code']for e in inspect(self.p,dict(purpose='script',current_document='document.json'))['errors']}
        self.assertIn('HANDOFF_DISPATCH_CHANGED',codes);self.assertIn('HANDOFF_INCOMPLETE',codes)
    def test_owned_input_output_edit_keeps_actual_before_snapshot_and_after_hash(self):
        self.task['inputs'].append(dict(path='output.json',sha256=sha(self.p/'output.json')))
        before=(self.p/'output.json').read_bytes();self.assertTrue(create(self.p,self.task)['ready'])
        (self.p/'output.json').write_text('legitimate producer update')
        self.result['output_paths'][0]['sha256']=sha(self.p/'output.json')
        self.assertTrue(submit(self.p,self.result,self.doc)['ready'])
        self.assertTrue(inspect(self.p,dict(purpose='script',current_document='document.json'))['ready'])
        task=json.loads((self.p/'work/handoffs/task1.json').read_text())
        snapshot=next(r for r in task['input_snapshots']if Path(r['path']).name=='output.json')
        self.assertEqual((self.p/snapshot['snapshot_path']).read_bytes(),before)
        self.assertNotEqual(snapshot['sha256'],self.result['output_paths'][0]['sha256'])
    def test_unowned_source_edit_remains_rejected_after_snapshot(self):
        create(self.p,self.task);(self.p/'document.json').write_text('{"changed":"protected source"}')
        self.assertIn('HANDOFF_INPUT_CHANGED',{e['code']for e in submit(self.p,self.result,self.doc)['errors']})
    def test_master_runtime_backlink_growth_is_allowed_but_source_acceptance_change_is_not(self):
        master=self.p/'production-contract.json';self.task['inputs'].append(dict(path='production-contract.json',sha256=sha(master)))
        create(self.p,self.task);self.assertTrue(submit(self.p,self.result,self.doc)['ready'])
        self.assertTrue(inspect(self.p,dict(purpose='script',current_document='document.json'))['ready'])
        value=json.loads(master.read_text());value['obligations'][0]['acceptance_checks']=['weakened test'];master.write_text(json.dumps(value))
        self.assertIn('HANDOFF_INPUT_CHANGED',{e['code']for e in inspect(self.p,dict(purpose='script',current_document='document.json'))['errors']})
    def test_same_task_cannot_replace_dispatch_and_result_history_is_preserved(self):
        create(self.p,self.task);task=copy.deepcopy(self.task);task['owned_scope']=['another.json']
        self.assertEqual(create(self.p,task)['errors'][0]['code'],'HANDOFF_ID_REUSED')
        submit(self.p,self.result,self.doc);r=copy.deepcopy(self.result);r['unresolved_items']=['still unknown']
        submit(self.p,r,self.doc)
        self.assertTrue(list((self.p/'work/handoffs/history').glob('*.json')))
        c=json.loads((self.p/'production-contract.json').read_text());self.assertEqual(c['obligations'][0]['status'],'blocked')

if __name__=='__main__':unittest.main()
