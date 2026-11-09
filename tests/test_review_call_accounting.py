"""Preflight failures retain real identities without inventing model calls or usage."""
import unittest

import test_ai_review as fixtures
import test_blind_review as blind_fixtures
from ai_review import Review
import blind_review as blind
from workflow import atomic


class ReviewCallAccountingTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    report=blind_fixtures.BlindReviewTests.report

    def uninvoked(self, role='reviewer'):
        audit=self.audit(role,self.review.packet('script',self.run)['packet'] if role=='reviewer' else None)
        audit.update(invocation_ids=[],request_headers=[],accessible_tools=['unexpected-tool'])
        return audit

    def test_preflight_failure_after_hold_records_identity_and_preserves_all_prior_budgets(self):
        self.run=self.begin();state=self.review.load();node=state['nodes']['script']
        node.update(calls=7,usage={'totalTokens':447472},repairs=1);atomic(self.review.path,state)
        self.review.reserve_call('script',self.run,'check-0',fixtures.ROUTE)
        audit=self.uninvoked();self.review.hold(True,'合成夹具：停止重试')
        self.review.call_result('script',self.run,'check-0',usage={},error='只读 Agent 意外暴露了工具。',agent_audit=audit,execution_phase='preflight',model_invoked=False)
        node=Review(self.course).load()['nodes']['script'];call=node['runs'][-1]['calls'][-1]
        self.assertEqual(call['status'],'failed');self.assertEqual(call['failure_kind'],'preflight')
        self.assertIs(call['model_invoked'],False);self.assertEqual(call['execution_phase'],'preflight')
        self.assertEqual(call['usage'],{});self.assertEqual(call['usage_status'],'not_invoked')
        self.assertEqual(call['agent_audit'],audit);self.assertEqual(call['agent_audit']['invocation_ids'],[])
        self.assertEqual(node['calls'],8);self.assertEqual(node['repairs'],1);self.assertEqual(node['usage'],{'totalTokens':447472})
        self.assertEqual(node['runs'][-1]['status'],'failed');self.assertTrue(self.review.load()['hold']['held'])
        with self.assertRaisesRegex(ValueError,'实际代理调用'):self.review._actual_call(node['runs'][-1],audit)
        with self.assertRaisesRegex(ValueError,'已暂停'):self.review.reserve_call('script',self.run,'must-not-retry',fixtures.ROUTE)
        # A duplicate callback cannot turn this failed reservation into a model call.
        self.review.call_result('script',self.run,'check-0',usage={'totalTokens':9})
        self.assertEqual(self.review.load()['nodes']['script']['calls'],8)
        self.assertEqual(self.review.load()['nodes']['script']['usage'],{'totalTokens':447472})

    def test_empty_invocation_audit_is_allowed_only_for_explicit_no_dispatch_failure(self):
        self.run=self.begin();self.review.reserve_call('script',self.run,'check-0',fixtures.ROUTE);audit=self.uninvoked()
        for values in [dict(error='失败'),dict(error='失败',execution_phase='unknown'),dict(error='失败',execution_phase='model',model_invoked=True),dict(execution_phase='preflight',model_invoked=False)]:
            with self.assertRaises(ValueError):self.review.call_result('script',self.run,'check-0',agent_audit=audit,**values)
            self.assertEqual(self.review.load()['nodes']['script']['runs'][-1]['calls'][-1]['status'],'reserved')
        self.review.call_result('script',self.run,'check-0',error='明确调用前预检失败',agent_audit=audit,execution_phase='preflight',model_invoked=False)
        with self.assertRaisesRegex(ValueError,'实际代理调用'):blind.validate_audit(audit,'reviewer',fixtures.PRODUCER,fixtures.ROUTE)
        result=self.report('script',self.run);result['agent_audit']=audit
        with self.assertRaisesRegex(ValueError,'实际代理调用'):self.review.submit('script',self.run,result)

    def test_preflight_record_rejects_real_request_ids_and_invented_zero_usage(self):
        self.run=self.begin();self.review.reserve_call('script',self.run,'check-0',fixtures.ROUTE);audit=self.uninvoked()
        for malformed,usage in [(dict(audit,invocation_ids=['actual-model-call']),{}),(dict(audit,request_headers=[dict(id='actual-request')]),{}),(audit,{'totalTokens':0}),(audit,{'totalTokens':123})]:
            with self.assertRaises(ValueError):self.review.call_result('script',self.run,'check-0',usage=usage,error='预检失败',agent_audit=malformed,execution_phase='preflight',model_invoked=False)
        call=self.review.load()['nodes']['script']['runs'][-1]['calls'][-1]
        self.assertEqual(call['status'],'reserved');self.assertNotIn('usage',call)
        self.assertEqual(self.review.node_view('script')['calls'],1)

    def test_invoked_failure_and_unknown_failure_keep_usage_uncertainty_distinct(self):
        self.run=self.begin();audit=self.audit('reviewer',self.review.packet('script',self.run)['packet'])
        self.review.reserve_call('script',self.run,'invoked',fixtures.ROUTE)
        self.review.call_result('script',self.run,'invoked',usage={'inputTokens':17},error='调用已发出后中断，完整用量未知',agent_audit=audit,execution_phase='model',model_invoked=True)
        self.review.reserve_call('script',self.run,'unknown',fixtures.ROUTE,role='producer')
        self.review.call_result('script',self.run,'unknown',error='旧宿主未返回调用证据或用量')
        node=self.review.load()['nodes']['script'];invoked,unknown=node['runs'][-1]['calls']
        self.assertEqual(invoked['failure_kind'],'model');self.assertIs(invoked['model_invoked'],True);self.assertEqual(invoked['usage_status'],'partial')
        self.assertEqual(unknown['failure_kind'],'unknown');self.assertIsNone(unknown['model_invoked']);self.assertEqual(unknown['usage_status'],'unknown')
        self.assertNotIn('totalTokens',invoked['usage']);self.assertEqual(unknown['usage'],{})
        self.assertEqual(node['calls'],2);self.assertEqual(node['usage'],{'inputTokens':17})
        state=self.review.load();state['policy']['max_tokens']=100;atomic(self.review.path,state)
        with self.assertRaisesRegex(ValueError,'用量未返回'):self.review.reserve_call('script',self.run,'cannot-guess-usage',fixtures.ROUTE,role='producer')

    def test_production_supervisor_preflight_failure_records_without_creating_a_report(self):
        operation='supervisor-preflight';self.review.production_event(fixtures.PRODUCER,operation,'start','script',[])
        self.review.reserve_supervision_call(operation,'supervisor-0',fixtures.ROUTE)
        audit=self.audit('supervisor');audit.update(invocation_ids=[],request_headers=[])
        packet=self.review.supervisor_packet(operation_id=operation)['packet']
        self.review.hold(True,'合成夹具：守卫拦截')
        self.review.supervision_call_result(operation,'supervisor-0',error='监督Agent建立前预检失败',agent_audit=audit,execution_phase='preflight',model_invoked=False)
        state=self.review.load();op=state['supervision']['operations'][operation];call=op['calls'][0]
        self.assertEqual(call['status'],'failed');self.assertEqual(call['failure_kind'],'preflight');self.assertEqual(call['usage'],{})
        self.assertEqual(call['agent_audit']['id'],audit['id']);self.assertEqual(state['nodes']['supervision']['calls'],1)
        self.assertEqual(state['nodes']['supervision']['usage'],{});self.assertNotIn('report',op)
        with self.assertRaisesRegex(ValueError,'已暂停'):self.review.production_supervisor_submit(operation,dict(binding=packet['binding'],passed=True,findings=[],summary='不得伪造成功',agent_audit=audit))

    def test_proven_no_dispatch_does_not_become_unknown_token_usage_or_refund_call_budget(self):
        self.run=self.begin();state=self.review.load();state['policy'].update(max_tokens=100,max_calls=1);atomic(self.review.path,state)
        self.review.reserve_call('script',self.run,'preflight',fixtures.ROUTE)
        self.review.call_result('script',self.run,'preflight',error='明确模型调用前失败',agent_audit=self.uninvoked(),execution_phase='preflight',model_invoked=False)
        call=self.review.load()['nodes']['script']['runs'][-1]['calls'][0]
        self.assertFalse(blind.usage_unknown(call));self.assertEqual(call['usage'],{})
        with self.assertRaisesRegex(ValueError,'累计审阅预算'):self.review.reserve_call('script',self.run,'cannot-refund-attempt',fixtures.ROUTE)
        self.assertEqual(self.review.node_view('script')['calls'],1)
        # An explicitly authorized extra attempt may proceed without inventing zero tokens.
        self.review.extend('script',0,1,'合成夹具明确追加一次预约额度')
        self.assertTrue(self.review.reserve_call('script',self.run,'authorized-next-attempt',fixtures.ROUTE)['reserved'])
        self.assertEqual(self.review.node_view('script')['calls'],2);self.assertEqual(self.review.node_view('script')['usage'],{})

    def test_supervision_token_budget_distinguishes_no_dispatch_from_unknown_model_usage(self):
        operation='supervisor-token-budget';self.review.production_event(fixtures.PRODUCER,operation,'start','script',[])
        state=self.review.load();state['policy']['max_tokens']=100;atomic(self.review.path,state)
        self.review.reserve_supervision_call(operation,'preflight',fixtures.ROUTE)
        audit=self.audit('supervisor');audit.update(invocation_ids=[],request_headers=[])
        self.review.supervision_call_result(operation,'preflight',error='模型调用前失败',agent_audit=audit,execution_phase='preflight',model_invoked=False)
        self.assertTrue(self.review.reserve_supervision_call(operation,'after-proven-preflight',fixtures.ROUTE)['reserved'])
        self.review.supervision_call_result(operation,'after-proven-preflight',error='是否发出模型调用未知')
        with self.assertRaisesRegex(ValueError,'用量未返回'):self.review.reserve_supervision_call(operation,'after-unknown',fixtures.ROUTE)
        self.assertEqual(self.review.load()['nodes']['supervision']['calls'],2)

    def test_explicit_unknown_with_request_header_does_not_claim_provider_dispatch(self):
        self.run=self.begin();self.review.reserve_call('script',self.run,'request-only',fixtures.ROUTE,role='producer')
        audit=self.audit('producer')
        audit['request_headers']=[dict(id='constructed-request',route=fixtures.ROUTE,tools=[])]
        self.review.call_result('script',self.run,'request-only',error='已构造请求，实际dispatch无证据',agent_audit=audit,execution_phase='unknown',model_invoked=None)
        call=self.review.load()['nodes']['script']['runs'][-1]['calls'][0]
        self.assertIsNone(call['model_invoked']);self.assertEqual(call['execution_phase'],'unknown')
        self.assertEqual(call['failure_kind'],'unknown');self.assertEqual(call['usage_status'],'unknown');self.assertEqual(call['usage'],{})
        self.review.reserve_call('script',self.run,'unknown-with-partial-usage',fixtures.ROUTE,role='producer')
        self.review.call_result('script',self.run,'unknown-with-partial-usage',usage={'inputTokens':17},error='实际dispatch仍无确认，宿主另有部分用量',agent_audit=audit,execution_phase='unknown',model_invoked=None)
        node=self.review.load()['nodes']['script'];partial=node['runs'][-1]['calls'][1]
        self.assertIsNone(partial['model_invoked']);self.assertEqual(partial['failure_kind'],'unknown')
        self.assertEqual(partial['usage_status'],'partial');self.assertEqual(node['usage'],{'inputTokens':17})
        with self.assertRaises(ValueError):blind.call_completion('预检失败',{},audit,'preflight',False)


if __name__=='__main__':unittest.main()
