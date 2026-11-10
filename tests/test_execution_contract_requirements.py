"""Synthetic obligations: current stage, source authority, and downgrade history."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from execution_requirements import validate,update,inspect,digest
from evidence_versions import sha


def obligation(key='dedicated-emphasis',stage='storyboard'):
    return dict(id=key,source_type='user_current',source_ref='messages/synthetic-user.txt',
        original_quote='Use a dedicated emphasis design, preserve the condition.',stage=stage,
        scope=dict(scenes=['S1']),required_behavior='Dedicated emphasis, not ordinary body text',
        acceptance_checks=['Current object binding','Current encoded visible emphasis'],
        implementation_refs=[],evidence_refs=[],status='not_started',changes=[])


class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project';self.p.mkdir()
        (self.p/'production-contract.json').write_text(json.dumps(dict(requirements={})))
    def tearDown(self):self.tmp.cleanup()
    def codes(self,rows,old=None,purpose='storyboard',complete=False):
        return {e['code'] for e in validate(self.p,dict(obligations=rows),purpose,old,complete)}
    def test_complete_metadata_future_stage_not_required_early(self):
        self.assertEqual(self.codes([obligation(stage='final')],purpose='script',complete=True),set())
        self.assertIn('CONTRACT_NOT_READY',self.codes([obligation(stage='final')],purpose='final',complete=True))
        self.assertEqual(self.codes([obligation(stage='final')],purpose='courseware',complete=True),set())
        self.assertEqual(self.codes([obligation(stage='courseware')],purpose='final',complete=True),set())
    def test_missing_and_downgraded_requirement_rejected(self):
        old=obligation();new=obligation();new['required_behavior']='Ordinary text suffices'
        self.assertIn('REQ_DOWNGRADED',self.codes([new],dict(obligations=[old])))
        second=obligation('second')
        self.assertIn('REQ_MISSING',self.codes([old],dict(obligations=[old,second])))
    def test_scope_check_and_off_reductions_are_not_silent(self):
        for field,value in [('scope',dict(scenes=[])),('acceptance_checks',['Current object binding']),('required',False),('stage','final')]:
            old=obligation();new=copy.deepcopy(old);new[field]=value
            self.assertIn('REQ_DOWNGRADED',self.codes([new],dict(obligations=[old])),field)
    def test_source_document_instruction_not_operational_authority(self):
        row=obligation();row.update(source_type='source_document_content')
        self.assertIn('REQ_SOURCE_NOT_AUTHORITY',self.codes([row]))
        row['operational_authority']=False
        self.assertEqual(self.codes([row]),set())
    def test_not_applicable_needs_basis_and_user_change_if_previous_required(self):
        old=obligation();row=copy.deepcopy(old);row['status']='not_applicable'
        self.assertIn('REQ_APPLICABILITY_MISSING',self.codes([row]))
        row['applicability_basis']='No video in this selected courseware branch'
        self.assertEqual(self.codes([row]),set())
        self.assertIn('REQ_DOWNGRADED',self.codes([row],dict(obligations=[old])))
    def test_real_attributed_change_file_allows_change_and_hash_change_invalidates(self):
        old=obligation();new=copy.deepcopy(old);new['required_behavior']='No emphasis, per new choice'
        path=self.p/'change.json';path.write_text(json.dumps(dict(actor_type='user',event_id='synthetic-user-event',action='requirement_change',original_quote='Turn this feature off',requirement_ids=[old['id']])))
        new['changes']=[dict(previous_obligation_sha256=digest(old),user_change_ref=dict(path='change.json',sha256=sha(path)))]
        self.assertEqual(self.codes([new],dict(obligations=[old])),set())
        path.write_text('{}')
        self.assertIn('REQ_DOWNGRADED',self.codes([new],dict(obligations=[old])))
    def test_implementation_index_is_not_verified_evidence(self):
        row=obligation();row['status']='verified'
        self.assertIn('REQ_EVIDENCE_MISSING',self.codes([row]))
        row['status']='complete'
        self.assertIn('REQ_MISSING',self.codes([row]))
    def test_delegation_not_human_action(self):
        c=dict(obligations=[obligation()],production_delegation=dict(no_intermediate_confirmation=True,source_ref='actual-user-text',human_clicked=True))
        self.assertIn('REQ_AUTHORIZATION_SCOPE',{e['code']for e in validate(self.p,c,'script')})
    def test_registered_snapshot_catches_direct_deletion_and_keeps_history(self):
        a=obligation();b=obligation('other')
        self.assertTrue(update(self.p,[a,b])['ready'])
        c=json.loads((self.p/'production-contract.json').read_text());c['obligations']=[a]
        (self.p/'production-contract.json').write_text(json.dumps(c))
        self.assertIn('REQ_MISSING',{e['code']for e in inspect(self.p,dict(purpose='script'))['errors']})
        self.assertGreaterEqual(len(list((self.p/'work/requirements-history').glob('*.json'))),2)


class ActionGraphTests(unittest.TestCase):
    def test_real_child_action_counts_without_fake_parent_motion(self):
        from production_contract import _has_action
        parent=dict(type='group',startFrame=0,endFrame=100,children=[dict(type='rect',startFrame=0,endFrame=100,
            motion=[dict(property='width',startFrame=0,endFrame=100,**{'from':0,'to':200})])])
        self.assertTrue(_has_action(parent,0,100));self.assertNotIn('motion',parent)
        parent['children'][0]['motion'][0]['to']=0
        self.assertFalse(_has_action(parent,0,100))
    def test_hidden_or_outside_parent_cannot_supply_action_proof(self):
        from production_contract import _has_action
        child=dict(startFrame=50,endFrame=100,motion=[dict(property='width',startFrame=50,endFrame=100,**{'from':0,'to':200})])
        parent=dict(startFrame=0,endFrame=40,children=[child])
        self.assertFalse(_has_action(parent,0,100));parent['endFrame']=100;parent['visible']=False
        self.assertFalse(_has_action(parent,0,100))

if __name__=='__main__':unittest.main()
