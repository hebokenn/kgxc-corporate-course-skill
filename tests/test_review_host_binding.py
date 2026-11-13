"""Native synthetic-stream envelopes still meet strict real backend versions."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest

import test_ai_review as fixtures

ELECTRON=Path('/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness')


@unittest.skipUnless(ELECTRON.is_file(),'installed native runtime unavailable')
class NativeHostBindingBackendTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown

    def packet(self):
        self.review.production_event(fixtures.PRODUCER,'synthetic-native-binding','start','script',[
            dict(type='production/dispatch',operation='controlled-produce',user_instruction='Isolated binding fixture only')])
        return self.review.supervisor_packet(operation_id='synthetic-native-binding')['packet']

    def native_result(self,packet,key):
        self.review.reserve_supervision_call('synthetic-native-binding',key,fixtures.ROUTE)
        process=subprocess.run([str(ELECTRON),str(fixtures.ROOT/'tests/fixtures/native_review_host_binding.mjs'),'--external-fixture-packet'],
            input=json.dumps(packet),text=True,capture_output=True,check=True,env=dict(os.environ,ELECTRON_RUN_AS_NODE='1'))
        value=json.loads(process.stdout.strip().splitlines()[-1])
        self.assertEqual(value['network_inference_calls'],0)
        self.assertEqual(value['audit']['binding_host']['source'],'host-attached-missing')
        self.assertTrue(value['audit']['request_boundary']['boundary_observed'])
        self.review.supervision_call_result('synthetic-native-binding',key,value['usage'],agent_audit=value['audit'],execution_phase='model',model_invoked=True)
        return value['result']

    def test_missing_body_binding_is_accepted_only_for_unchanged_actual_backend_version(self):
        course_state=self.course.state_file.read_bytes();packet=self.packet();result=self.native_result(packet,'native-current')
        self.assertEqual(result['binding'],packet['binding'])
        outcome=self.review.production_supervisor_submit('synthetic-native-binding',result)
        self.assertTrue(outcome['passed']);self.assertEqual(len(outcome['supervision']['reports']),1)
        self.assertEqual(self.course.state_file.read_bytes(),course_state)

    def test_real_new_progress_still_rejects_actual_native_old_envelope_without_state_change(self):
        packet=self.packet();result=self.native_result(packet,'native-before-progress')
        self.review.production_event(fixtures.PRODUCER,'synthetic-native-binding','progress','script',[
            dict(type='production/progress',status='actual-new-fixture-event')])
        current=self.review.supervisor_packet(operation_id='synthetic-native-binding')['packet']
        self.assertNotEqual(result['binding'],current['binding'])
        before=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'当前生产执行版本'):
            self.review.production_supervisor_submit('synthetic-native-binding',result)
        self.assertEqual(self.review.path.read_bytes(),before)

    def test_rejected_historical_wrong_binding_is_not_repaired_by_a_new_missing_body_result(self):
        packet=self.packet();old=self.native_result(packet,'native-old-wrong')
        old['binding']['operation_id']='synthetic-transcription-error'
        old_result=copy.deepcopy(old)
        with self.assertRaisesRegex(ValueError,'当前生产执行版本'):
            self.review.production_supervisor_submit('synthetic-native-binding',old)
        fresh=self.native_result(packet,'native-fresh-missing')
        self.assertTrue(self.review.production_supervisor_submit('synthetic-native-binding',fresh)['passed'])
        self.assertEqual(old,old_result)
        reports=self.review.load()['supervision']['operations']['synthetic-native-binding']['reports']
        self.assertEqual(len(reports),1);self.assertEqual(reports[0]['agent_audit']['id'],fresh['agent_audit']['id'])
        self.assertNotEqual(reports[0]['agent_audit']['id'],old['agent_audit']['id'])


if __name__=='__main__':unittest.main()
