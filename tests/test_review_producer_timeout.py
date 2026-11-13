"""Course-only producer QA timers preserve frozen attempts and quality evidence."""
import copy
import json
import unittest

import test_ai_review as fixtures
from ai_review import Review
from workflow import Course, atomic, sha


class ProducerTimeoutTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    def configure(self,value=1200000,evidence='合成维护记录：本课明确采用20分钟制作核验超时'):
        self.review.hold(True,'合成维护暂停，保留全部成果')
        return self.review.set_producer_timeout(value,evidence)

    def test_default_is_ten_minutes_independent_of_unlimited_counts_and_other_courses(self):
        self.review.set_unlimited_counts(True,'合成用户仅授权不限次数',actor='user-chat-confirmation')
        run=self.begin();packet=self.review.producer_packet('script',run)['packet']
        self.assertEqual(packet['producer_qa_timeout_ms'],600000)
        self.assertEqual(packet['producer_qa_timeout_authorization'],dict(source='default',recorded=False))
        self.assertNotIn('execution_settings',self.review.load())
        self.configure()
        other_root=self.root/'other-course';atomic(other_root/'project/workbench.json',dict(title='其他合成课',scenes=[],media={}))
        other=Course(other_root);other.init('其他合成课');other_review=Review(other)
        self.assertEqual(other_review._producer_timeout_metadata(other_review.load())['producer_qa_timeout_ms'],600000)
        self.assertNotIn('execution_settings',other_review.load())

    def test_explicit_setting_and_restore_keep_full_history_and_all_quality_state(self):
        run=self.begin();self.review.reserve_call('script',run,'old-failure',fixtures.ROUTE,'producer')
        self.review.call_result('script',run,'old-failure',error='合成未知用量失败',execution_phase='unknown',model_invoked=None)
        self.review.hold(True,'合成安全暂停')
        before=copy.deepcopy(self.review.load());fingerprints={stage:self.review.fingerprint(stage) for stage in ['script','storyboard']}
        value=self.review.set_producer_timeout(1200000,'合成明确延长等待，未授权任何质量放行')
        state=self.review.load();without_settings={k:v for k,v in state.items() if k not in ['execution_settings','execution_settings_history']}
        self.assertEqual(without_settings,before);self.assertEqual({stage:self.review.fingerprint(stage) for stage in fingerprints},fingerprints)
        record=state['execution_settings_history'][0]
        self.assertEqual(record['previous_timeout_ms'],600000);self.assertTrue(record['previous_was_default'])
        self.assertEqual(record['actor'],'codex-maintenance');self.assertEqual(value['producer_qa_timeout_ms'],1200000)
        self.assertEqual(record['evidence'],'合成明确延长等待，未授权任何质量放行');self.assertTrue(record['at'])
        restored=self.review.set_producer_timeout(600000,'合成用户恢复默认等待',actor='user-chat-confirmation')
        history=self.review.load()['execution_settings_history'];self.assertEqual(history[0],record)
        self.assertEqual(history[-1]['previous_timeout_ms'],1200000);self.assertFalse(history[-1]['previous_was_default'])
        self.assertEqual(history[-1]['actor'],'user-chat-confirmation');self.assertEqual(restored['producer_qa_timeout_ms'],600000)
        self.assertEqual(self.review.load()['nodes'],before['nodes']);self.assertEqual(self.review.load()['policy'],before['policy'])

    def test_invalid_settings_and_unheld_changes_are_rejected_atomically(self):
        original=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'先暂停'):self.review.set_producer_timeout(1200000,'合成依据')
        self.assertEqual(self.review.path.read_bytes(),original)
        self.review.hold(True,'合成暂停');original=self.review.path.read_bytes()
        for value,evidence,actor in [(True,'合成依据','codex-maintenance'),(False,'合成依据','codex-maintenance'),(1200000.0,'合成依据','codex-maintenance'),('1200000','合成依据','codex-maintenance'),(None,'合成依据','codex-maintenance'),(29999,'合成依据','codex-maintenance'),(3600001,'合成依据','codex-maintenance'),(1200000,' ','codex-maintenance'),(1200000,'合成依据','producer')]:
            with self.assertRaises(ValueError):self.review.set_producer_timeout(value,evidence,actor)
            self.assertEqual(self.review.path.read_bytes(),original)
        self.assertEqual(self.review.set_producer_timeout(30000,'合成下限')['producer_qa_timeout_ms'],30000)
        self.assertEqual(self.review.set_producer_timeout(3600000,'合成上限')['producer_qa_timeout_ms'],3600000)

    def test_any_reserved_review_or_production_supervision_call_blocks_changes(self):
        run=self.begin();self.review.reserve_call('script',run,'reserved-review',fixtures.ROUTE)
        self.review.hold(True,'合成暂停但保留未结算调用');original=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'未结算'):self.review.set_producer_timeout(1200000,'合成设置依据')
        self.assertEqual(self.review.path.read_bytes(),original)
        self.review.call_result('script',run,'reserved-review',error='合成预检未派发',execution_phase='preflight',model_invoked=False)
        self.review.hold(False,'合成恢复登记监督')
        self.review.production_event(fixtures.PRODUCER,'pending-supervision','start','script',[])
        self.review.reserve_supervision_call('pending-supervision','reserved-supervisor',fixtures.ROUTE)
        self.review.hold(True,'合成暂停但监督调用未结算');original=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'未结算'):self.review.set_producer_timeout(1200000,'合成设置依据')
        self.assertEqual(self.review.path.read_bytes(),original)

    def test_frozen_packet_stays_unchanged_and_only_new_attempt_gets_override(self):
        run=self.begin();old=self.review.producer_packet('script',run)['packet'];task=self.review.load()['nodes']['script']['runs'][-1]
        path=self.project/task['producer_packet_path'];content=path.read_bytes();digest=sha(path);history=copy.deepcopy(task['producer_packet_history'])
        self.configure();self.assertEqual(path.read_bytes(),content);self.assertEqual(sha(path),digest)
        self.review.hold(False,'合成恢复')
        self.assertEqual(self.review.producer_packet('script',run)['packet'],old)
        fresh=self.begin(request='explicit-new-producer-attempt',mode='continue');packet=self.review.producer_packet('script',fresh)['packet']
        self.assertEqual(packet['producer_qa_timeout_ms'],1200000);self.assertEqual(packet['producer_qa_timeout_authorization']['actor'],'codex-maintenance')
        self.assertTrue(packet['producer_qa_timeout_authorization']['recorded'])
        self.assertEqual(path.read_bytes(),content);self.assertEqual(self.review.load()['nodes']['script']['runs'][0]['producer_packet_history'],history)

    def test_supervisors_receive_only_bounded_timeout_authorization_not_private_body(self):
        evidence='合成实际维护依据'*500;self.configure(evidence=evidence);self.review.hold(False,'合成恢复')
        run=self.begin();self.complete('script',run,self.result('script',run))
        packet=self.review.supervisor_packet('script',run)['packet']
        self.assertEqual(packet['producer_qa_timeout_ms'],1200000)
        authorization=packet['producer_qa_timeout_authorization']
        self.assertEqual(len(authorization['evidence']),2000);self.assertTrue(authorization['evidence_truncated']);self.assertEqual(len(authorization['evidence_sha256']),64)
        self.assertEqual(self.review.load()['execution_settings_history'][-1]['evidence'],evidence)
        self.assertNotIn(fixtures.TEXT,json.dumps(packet,ensure_ascii=False));self.assertNotIn('sources',packet)
        self.review.production_event(fixtures.PRODUCER,'timeout-supervision','start','script',[])
        production=self.review.supervisor_packet(operation_id='timeout-supervision')['packet'];binding=copy.deepcopy(production['binding'])
        self.assertEqual(production['producer_qa_timeout_ms'],1200000);self.assertEqual(production['producer_qa_timeout_authorization'],authorization)
        self.review.hold(True,'合成设置恢复');self.review.set_producer_timeout(600000,'合成恢复默认')
        self.assertEqual(self.review.supervisor_packet(operation_id='timeout-supervision')['packet']['binding'],binding)
        self.review.hold(False,'合成回读旧已冻结QA包')
        old=self.review.supervisor_packet('script',run)['packet']
        self.assertEqual(old['producer_qa_timeout_ms'],1200000);self.assertEqual(old['producer_qa_timeout_authorization'],authorization)


if __name__=='__main__':unittest.main()
