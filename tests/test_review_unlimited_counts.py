"""Explicit, reversible count limits for one course; no real course or model use."""
import copy
import unittest

import test_ai_review as fixtures
from ai_review import Review, gate_errors
from workflow import Course, atomic, read


class ReviewUnlimitedCountTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    def enable(self):return self.review.set_unlimited_counts(True,'合成夹具用户明确临时取消本课调用和返修次数限制',actor='user-chat-confirmation')

    def cap(self,calls=18,repairs=3):
        state=self.review.load();node=self.review._node(state,'script')
        node.update(calls=calls,repairs=repairs,usage={'totalTokens':603513},policy=dict(max_calls=18,max_repairs=3,unlimited_counts=False))
        atomic(self.review.path,state)

    def test_course_scope_and_reversible_authorization_preserve_legacy_limits_and_history(self):
        self.assertFalse(self.review.view()['policy']['unlimited_counts'])
        run=self.begin();self.review.finish('script',run,error='合成旧失败保留');self.cap()
        before=copy.deepcopy(self.review.load()['nodes'])
        enabled=self.enable();state=self.review.load()
        self.assertEqual(state['nodes'],before);self.assertTrue(enabled['policy']['unlimited_counts'])
        self.assertTrue(enabled['nodes']['script']['policy']['unlimited_counts']);self.assertEqual(enabled['nodes']['script']['policy']['max_calls'],18)
        self.assertEqual(state['authorizations'][-1]['actor'],'user-chat-confirmation');self.assertFalse(state['authorizations'][-1]['previous_enabled'])
        other_root=self.root/'another-course';atomic(other_root/'project/workbench.json',dict(title='另一门合成课',scenes=[],media={}))
        other=Course(other_root);other.init('另一门合成课');other_review=Review(other)
        self.assertFalse(other_review.view()['policy']['unlimited_counts']);self.assertEqual(other_review.load()['policy']['max_calls'],12)
        # A copied node flag cannot override the authoritative course-level restoration.
        state=self.review.load();state['nodes']['script']['policy']['unlimited_counts']=True;atomic(self.review.path,state)
        restored=self.review.set_unlimited_counts(False,'合成夹具用户恢复原次数门槛')
        self.assertFalse(restored['policy']['unlimited_counts']);self.assertFalse(restored['nodes']['script']['policy']['unlimited_counts'])
        self.assertEqual(restored['nodes']['script']['calls'],18);self.assertEqual(restored['nodes']['script']['repairs'],3)
        self.assertEqual(restored['nodes']['script']['usage'],{'totalTokens':603513});self.assertEqual(restored['nodes']['script']['policy']['max_calls'],18)
        self.assertEqual(self.review.load()['authorizations'][-1]['actor'],'dsh-user-click');self.assertTrue(self.review.load()['authorizations'][-1]['previous_enabled'])

    def test_begin_and_reserve_continue_beyond_old_call_cap_without_reset_or_duplicate_charge(self):
        self.cap(calls=18);self.enable();run=self.begin()
        self.assertEqual(self.review.node_view('script')['run']['status'],'queued')
        self.assertTrue(self.review.reserve_call('script',run,'beyond-old-cap',fixtures.ROUTE)['reserved'])
        self.assertFalse(self.review.reserve_call('script',run,'beyond-old-cap',fixtures.ROUTE)['reserved'])
        self.assertEqual(self.review.node_view('script')['calls'],19)
        self.review.call_result('script',run,'beyond-old-cap',error='合成测试失败，用量未知')
        self.review.set_unlimited_counts(False,'合成夹具明确恢复')
        with self.assertRaisesRegex(ValueError,'累计审阅预算'):self.review.reserve_call('script',run,'limited-again',fixtures.ROUTE,role='producer')
        self.assertEqual(self.review.node_view('script')['calls'],19)

    def test_producer_repair_and_supervisor_plan_honor_unlimited_counts_but_keep_quality_gates(self):
        self.cap(calls=18,repairs=3);self.enable();run=self.begin();packet=self.review.producer_packet('script',run)['packet']
        self.assertTrue(packet['unlimited_counts']);self.assertIsNone(packet['repairs_remaining'])
        result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='合成局部修复')]
        value=self.complete('script',run,result)
        self.assertTrue(value['can_repair']);self.assertFalse(value['limit_reached'])
        supervisor=self.review.supervisor_packet('script',run)['packet']
        self.assertEqual(supervisor['next_action']['kind'],'repair');self.assertTrue(supervisor['budget']['unlimited_counts'])
        self.assertEqual(supervisor['budget']['max_calls'],18);self.assertEqual(supervisor['budget']['max_repairs'],3)
        self.assertIsNone(supervisor['budget']['calls_remaining']);self.assertIsNone(supervisor['budget']['repairs_remaining'])
        authorization=next(a for a in supervisor['budget']['authorizations'] if a.get('kind')=='temporary-unlimited-counts')
        self.assertEqual(authorization['evidence'],'合成夹具用户明确临时取消本课调用和返修次数限制');self.assertEqual(authorization['actor'],'user-chat-confirmation')
        self.assertTrue(authorization['enabled']);self.assertTrue(authorization['at'])
        with self.assertRaisesRegex(ValueError,'制作代理'):self.review.repair('script',run,result['repairs'],'reviewer')
        repaired=self.review.repair('script',run,result['repairs'],fixtures.PRODUCER['id'])
        self.assertEqual(repaired['repair_round'],4);self.assertEqual(self.review.node_view('script')['calls'],21)
        self.assertTrue((self.project/'qa/ai-review'/run/'repair-4/source/transcript.md').is_file())
        self.assertTrue(gate_errors(self.course,'script'));self.assertFalse(self.review.node_view('script')['user_confirmed'])

    def test_repair_error_retry_uses_effective_course_count_policy(self):
        run=self.begin();self.cap(calls=30,repairs=9);self.enable()
        retry=self.review.repair_error('script',run,'合成执行错误，仍需真实恢复后复核')
        self.assertTrue(retry['retry']);self.assertFalse(retry['limit_reached'])
        self.review.set_unlimited_counts(False,'合成恢复次数限制')
        limited=self.review.repair_error('script',run,'合成再次失败')
        self.assertFalse(limited['retry']);self.assertTrue(limited['limit_reached'])
        self.assertEqual(self.review.node_view('script')['repairs'],9);self.assertEqual(self.review.node_view('script')['calls'],30)

    def test_production_supervision_counts_are_course_scoped_and_still_cumulative(self):
        self.enable();operation='unlimited-supervisor';self.review.production_event(fixtures.PRODUCER,operation,'start','script',[])
        state=self.review.load();node=self.review._node(state,'supervision');node['calls']=24;node['policy']=dict(max_calls=12,unlimited_counts=False);atomic(self.review.path,state)
        self.assertTrue(self.review.reserve_supervision_call(operation,'beyond-supervision-cap',fixtures.ROUTE)['reserved'])
        self.assertEqual(self.review.load()['nodes']['supervision']['calls'],25);self.assertTrue(self.review.view()['supervision']['policy']['unlimited_counts'])
        self.review.supervision_call_result(operation,'beyond-supervision-cap',error='合成未知失败')
        packet=self.review.supervisor_packet(operation_id=operation)['packet'];authorization=packet['budget']['authorizations'][-1]
        self.assertEqual(authorization['evidence'],'合成夹具用户明确临时取消本课调用和返修次数限制');self.assertTrue(authorization['enabled'])
        self.assertEqual(authorization['actor'],'user-chat-confirmation');self.assertEqual(packet['budget']['ledger'],'supervision')
        self.review.set_unlimited_counts(False,'合成恢复监督次数限制')
        restored=self.review.supervisor_packet(operation_id=operation)['packet']
        self.assertEqual(restored['binding'],packet['binding']);self.assertFalse(restored['budget']['authorizations'][-1]['enabled'])
        self.assertEqual(restored['budget']['authorizations'][-1]['evidence'],'合成恢复监督次数限制')
        with self.assertRaisesRegex(ValueError,'累计监督预算'):self.review.reserve_supervision_call(operation,'limited-supervision',fixtures.ROUTE)
        self.assertEqual(self.review.load()['nodes']['supervision']['calls'],25)

    def test_independent_token_caps_and_unknown_usage_still_block(self):
        self.enable();run=self.begin();state=self.review.load();state['policy']['max_tokens']=100;state['nodes']['script']['usage']={'totalTokens':100};atomic(self.review.path,state)
        with self.assertRaisesRegex(ValueError,'累计审阅预算'):self.review.reserve_call('script',run,'token-cap',fixtures.ROUTE)
        state=self.review.load();state['nodes']['script']['usage']={};atomic(self.review.path,state)
        self.review.reserve_call('script',run,'unknown-usage',fixtures.ROUTE);self.review.call_result('script',run,'unknown-usage',error='合成模型用量缺失')
        with self.assertRaisesRegex(ValueError,'用量未返回'):self.review.reserve_call('script',run,'cannot-guess',fixtures.ROUTE,role='producer')
        self.review.production_event(fixtures.PRODUCER,'token-supervisor','start','script',[])
        state=self.review.load();self.review._node(state,'supervision')['usage']={'totalTokens':100};atomic(self.review.path,state)
        with self.assertRaisesRegex(ValueError,'累计监督预算'):self.review.reserve_supervision_call('token-supervisor','token-cap',fixtures.ROUTE)
        self.assertEqual(self.review.load()['policy']['max_tokens'],100)

    def test_none_count_limits_do_not_raise_and_extension_does_not_invent_finite_caps(self):
        state=self.review.load();state['policy'].update(max_calls=None,max_repairs=None);atomic(self.review.path,state)
        run=self.begin();self.assertTrue(self.review.reserve_call('script',run,'none-cap',fixtures.ROUTE)['reserved'])
        self.review.call_result('script',run,'none-cap',error='合成失败')
        self.assertIsNone(self.review.producer_packet('script',run)['packet']['repairs_remaining'])
        self.assertTrue(self.review.repair_error('script',run,'合成可恢复失败')['retry'])
        self.review.extend('script',1,1,'合成已有授权增量，不改变显式无上限字段')
        policy=self.review.node_view('script')['policy'];self.assertIsNone(policy['max_calls']);self.assertIsNone(policy['max_repairs'])
        self.review.production_event(fixtures.PRODUCER,'none-cap-supervisor','start','script',[])
        self.assertTrue(self.review.reserve_supervision_call('none-cap-supervisor','none-cap',fixtures.ROUTE)['reserved'])

    def test_invalid_authorization_is_atomic_and_unlimited_does_not_relax_hold_or_route(self):
        before=self.review.path.read_bytes()
        for enabled,evidence,actor in [(1,'证据','user-chat-confirmation'),(True,' ','user-chat-confirmation'),(True,'证据','producer')]:
            with self.assertRaises(ValueError):self.review.set_unlimited_counts(enabled,evidence,actor)
            self.assertEqual(self.review.path.read_bytes(),before)
        self.enable();self.assertTrue(gate_errors(self.course,'script'))
        with self.assertRaisesRegex(ValueError,'不能切换'):self.review.begin('script','wrong-route','continue',route=dict(provider='other',model='other'),producer=fixtures.PRODUCER)
        self.review.hold(True,'合成明确暂停')
        self.review.set_unlimited_counts(True,'合成临时次数授权仍不取消暂停',actor='user-chat-confirmation')
        self.assertTrue(self.review.load()['hold']['held'])
        with self.assertRaisesRegex(ValueError,'已暂停'):self.begin(request='must-not-resume',mode='continue')


if __name__=='__main__':unittest.main()
