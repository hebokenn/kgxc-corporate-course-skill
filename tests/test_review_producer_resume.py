"""Producer-only retry retains accepted blind evidence and immutable input attempts."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest

import test_ai_review as fixtures
import test_review_storyboard_evidence as storyboard_fixtures
from test_storyboard_workflow import fixture as board_fixture
from ai_review import Review
from workflow import atomic, read, sha


class ProducerResumeTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    report=storyboard_fixtures.StoryboardEvidenceTests.report
    send=storyboard_fixtures.StoryboardEvidenceTests.send

    def board(self):
        value=board_fixture(self.course)
        for i,(segment,paragraph) in enumerate(zip(value['segments'],read(self.course.plan_file)['script_mapping']['paragraphs'])):
            segment.update(id='S'+str(i+12),source_paragraph_ids=[paragraph['id']],selected='A',selection_receipt=dict(actor='qa-operator',evidence='合成制作端既有选择'))
        atomic(self.project/'storyboard.json',value)
        return value

    def accepted(self):
        board=self.board();run=self.begin('storyboard',mode='continue',instruction='合成本轮完整指令：逐段给出动作起态、过程、结果。')
        findings=[dict(id='F1',problem='动作结果需核对',evidence=[dict(locator='S12.A.action',quote=board['segments'][0]['options'][0]['action'])]),dict(id='F2',problem='讲述推进需核对',evidence=[dict(locator='S12.script_excerpt',quote=board['segments'][0]['script_excerpt'])]),dict(id='F3',problem='概述尚未证实',evidence=[dict(locator='S12.A.action',quote='未出现在实际分镜中的概述')])]
        result=self.report(run,findings);self.send(run,result)
        return run,copy.deepcopy(result['binding'])

    def failed(self):
        self.review.set_unlimited_counts(True,'合成夹具用户授权本课临时不限次数',actor='user-chat-confirmation')
        run,binding=self.accepted();packet=self.review.producer_packet('storyboard',run)['packet']
        packet.update(document=dict(legacy_uneditable='OLD_WORKBENCH_PRIVATE'*3000),native=[dict(text='OLD_NATIVE_PRIVATE'*1000)],prior=[dict(raw_result='OLD_DUPLICATED_REVIEW')])
        old=self.project/'qa/ai-review'/run/'producer-01/producer-packet.json';atomic(old,packet)
        state=self.review.load();task=state['nodes']['storyboard']['runs'][-1]
        for key in ['producer_attempt','producer_packet_history','producer_packet_sha256']:task.pop(key,None)
        task['producer_packet_path']=str(old.relative_to(self.project));atomic(self.review.path,state)
        self.review.reserve_call('storyboard',run,'producer-0',fixtures.ROUTE,'producer')
        self.review.call_result('storyboard',run,'producer-0',error='180秒未返回事件，是否实际调用和用量未知',execution_phase='unknown',model_invoked=None)
        self.review.finish('storyboard',run,error='制作核验未返回，保留unknown usage')
        return run,binding,old,old.read_bytes()

    def resume(self,run,binding,request='retry-producer-1'):
        return self.review.resume_producer('storyboard',run,request,binding,fixtures.ROUTE,fixtures.PRODUCER,'new-host-owner')

    def test_storyboard_packet_removes_uneditable_duplicates_but_keeps_complete_qa_material(self):
        plan=read(self.course.plan_file);plan['units'][0]['content_points']=['PLAN_COMPLETE_SENTINEL'];plan['extra_qa_field']='FULL_PLAN_SENTINEL';atomic(self.course.plan_file,plan)
        source=self.course.relative(plan['sources'][0]['location']);original='原始业务资料完整正文。'*7000;source.write_text(original)
        script=self.begin('script');script_packet=self.review.producer_packet('script',script)['packet']
        self.assertTrue(script_packet['evidence']['sources'][0]['truncated']);self.assertEqual(len(script_packet['evidence']['sources'][0]['text']),60000)
        self.review.finish('script',script,error='合成夹具只检查旧脚本资料边界')
        (self.project/'native').mkdir(exist_ok=True);(self.project/'native/old.js').write_text('UNEDITABLE_NATIVE_SENTINEL')
        doc=read(self.project/'workbench.json');doc['old_private_document']='UNEDITABLE_DOCUMENT_SENTINEL';atomic(self.project/'workbench.json',doc)
        self.review.set_unlimited_counts(True,'合成当前课真实次数授权',actor='user-chat-confirmation')
        self.review.requirements(['合成当前分镜内容要求'],'合成用户原话')
        run,binding=self.accepted();packet=self.review.producer_packet('storyboard',run)['packet'];raw=json.dumps(packet,ensure_ascii=False)
        for key in ['document','native','prior','previous_round','sections']:self.assertNotIn(key,packet)
        self.assertNotIn('UNEDITABLE_NATIVE_SENTINEL',raw);self.assertNotIn('UNEDITABLE_DOCUMENT_SENTINEL',raw)
        self.assertEqual(packet['evidence']['sources'][0]['text'],original);self.assertFalse(packet['evidence']['sources'][0]['truncated'])
        self.assertEqual(packet['input']['text'],self.review.script_input()['text']);self.assertEqual(packet['plan'],{k:v for k,v in read(self.course.plan_file).items() if k not in ['source_items','revision_context_history']})
        self.assertEqual(packet['storyboard'],read(self.project/'storyboard.json'));self.assertEqual(packet['binding'],binding)
        self.assertEqual(packet['instruction'],'合成本轮完整指令：逐段给出动作起态、过程、结果。');self.assertTrue(packet['checklist'])
        self.assertEqual(packet['editable_files'],[dict(path='storyboard.json',sha256=sha(self.project/'storyboard.json'))])
        self.assertEqual(packet['selections'][0]['selection_receipt']['actor'],'qa-operator');self.assertFalse(packet['confirmations']['script']['user_confirmed'])
        self.assertEqual(packet['authorization_context']['authorizations'][-1]['evidence'],'合成当前课真实次数授权')
        self.assertTrue(packet['applicable_requirements']);self.assertEqual(len(packet['blind_report']['findings']),3)

    def test_storyboard_dispatch_archives_only_duplicate_source_ledger_and_old_revision_history(self):
        plan=read(self.course.plan_file);plan['source_items']=[dict(original_ledger='ARCHIVED_SOURCE_LEDGER'*5000)];plan['revision_context_history']=[dict(old_context='ARCHIVED_REVISION_HISTORY'*1000)]
        plan['units'][0]['content_points']=['CURRENT_CONTENT_POINTS_MUST_REMAIN'];plan['units'][0]['source_refs']=[dict(source_id='S',locator='正文',note='CURRENT_SOURCE_REF_MUST_REMAIN')]
        plan['current_constraint_note']='CURRENT_PLAN_FIELD_MUST_REMAIN';atomic(self.course.plan_file,plan)
        original_bytes=self.course.plan_file.read_bytes();run,_=self.accepted();packet=self.review.producer_packet('storyboard',run)['packet']
        self.assertEqual(self.course.plan_file.read_bytes(),original_bytes)
        self.assertEqual(packet['plan'],{k:v for k,v in plan.items() if k not in ['source_items','revision_context_history']})
        self.assertEqual(packet['plan']['units'],plan['units']);self.assertEqual(packet['evidence']['sources'][0]['text'],self.course.relative(plan['sources'][0]['location']).read_text())
        metadata=packet['plan_archive_metadata'];self.assertEqual(metadata['path'],str(self.course.plan_file));self.assertEqual(metadata['sha256'],sha(self.course.plan_file))
        for key in ['source_items','revision_context_history']:
            data=json.dumps(plan[key],ensure_ascii=False,separators=(',',':')).encode('utf-8')
            self.assertEqual(metadata['archived_fields'][key],dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        dispatch=json.dumps(packet,ensure_ascii=False)
        self.assertNotIn('ARCHIVED_SOURCE_LEDGER',dispatch);self.assertNotIn('ARCHIVED_REVISION_HISTORY',dispatch)
        self.assertIn('CURRENT_CONTENT_POINTS_MUST_REMAIN',dispatch);self.assertIn('CURRENT_SOURCE_REF_MUST_REMAIN',dispatch)

    def test_legal_resume_is_idempotent_preserves_unknown_usage_and_never_overwrites_old_packet(self):
        run,binding,old,raw=self.failed();before=self.review.load();task=before['nodes']['storyboard']['runs'][-1]
        blind=copy.deepcopy(task['blind_report']);calls=copy.deepcopy(task['calls']);count=before['nodes']['storyboard']['calls'];usage=copy.deepcopy(before['nodes']['storyboard']['usage'])
        summary=(self.project/'qa/ai-review'/run/'summary.json').read_bytes();value=self.resume(run,binding)
        self.assertTrue(value['started']);self.assertEqual(value['iteration'],0);self.assertEqual(value['run']['owner'],'new-host-owner')
        after=self.review.load();current=after['nodes']['storyboard']['runs'][-1]
        self.assertEqual(current['blind_report'],blind);self.assertEqual(current['calls'],calls);self.assertEqual(after['nodes']['storyboard']['calls'],count);self.assertEqual(after['nodes']['storyboard']['usage'],usage)
        retry=current['producer_retry_history'][0];self.assertEqual(retry['previous']['reason'],task['reason']);self.assertEqual(retry['previous']['completed_at'],task['completed_at']);self.assertEqual(retry['previous']['owner'],'test-owner')
        self.assertEqual((self.project/retry['previous_summary']['path']).read_bytes(),summary)
        again=self.resume(run,binding);self.assertFalse(again['started']);self.assertEqual(again['producer_key'],value['producer_key'])
        self.assertEqual(len(self.review.load()['nodes']['storyboard']['runs'][-1]['producer_retry_history']),1)
        packet=self.review.producer_packet('storyboard',run)['packet'];current=self.review.load()['nodes']['storyboard']['runs'][-1]
        self.assertNotEqual(current['producer_packet_path'],str(old.relative_to(self.project)));self.assertEqual(old.read_bytes(),raw)
        self.assertEqual(current['producer_packet_history'][0]['sha256'],sha(old));self.assertEqual(packet['attempt_id'],value['attempt_id'])
        self.assertNotIn('document',packet);self.assertNotIn('native',packet);self.assertEqual(self.review.producer_packet('storyboard',run)['packet'],packet)
        with self.assertRaisesRegex(ValueError,'只盲审一次'):self.review.reserve_call('storyboard',run,'new-reviewer',fixtures.ROUTE,'reviewer')
        with self.assertRaisesRegex(ValueError,'唯一事务'):self.review.reserve_call('storyboard',run,'wrong-producer',fixtures.ROUTE,'producer')
        self.assertTrue(self.review.reserve_call('storyboard',run,value['producer_key'],fixtures.ROUTE,'producer')['reserved'])
        self.assertFalse(self.review.reserve_call('storyboard',run,value['producer_key'],fixtures.ROUTE,'producer')['reserved'])
        self.assertEqual(self.review.node_view('storyboard')['calls'],count+1)

    def test_hold_fake_binding_changed_identity_report_repair_reserved_and_nonlatest_are_rejected(self):
        run,binding,_,_=self.failed();baseline=copy.deepcopy(self.review.load())
        mutations=[lambda s:s.update(hold=dict(held=True,reason='合成暂停')),lambda s:s['nodes']['storyboard']['runs'][-1].update(status='awaiting_confirmation'),lambda s:s['nodes']['storyboard']['runs'][-1].update(producer_report=dict(passed=False)),lambda s:s['nodes']['storyboard']['runs'][-1]['iterations'][-1].update(producer_report=dict(passed=False)),lambda s:s['nodes']['storyboard']['runs'][-1].update(repaired=[dict(path='storyboard.json')]),lambda s:s['nodes']['storyboard']['runs'][-1]['iterations'][-1].update(repair_attempted=True),lambda s:s['nodes']['storyboard']['runs'][-1]['calls'][-1].update(status='reserved'),lambda s:s['nodes']['storyboard']['runs'].append(dict(id='newer',status='failed'))]
        for mutation in mutations:
            state=copy.deepcopy(baseline);mutation(state);atomic(self.review.path,state);before=self.review.path.read_bytes()
            with self.assertRaises((ValueError,FileExistsError)):self.resume(run,binding)
            self.assertEqual(self.review.path.read_bytes(),before)
        atomic(self.review.path,baseline)
        wrong=dict(binding,packet_sha256='forged')
        with self.assertRaises(ValueError):self.resume(run,wrong)
        with self.assertRaises(ValueError):self.review.resume_producer('storyboard',run,'retry',binding,fixtures.ROUTE,dict(fixtures.PRODUCER,id='other'),'owner')
        with self.assertRaises(ValueError):self.review.resume_producer('storyboard',run,'retry',binding,dict(provider='other',model='other'),fixtures.PRODUCER,'owner')

    def test_changed_artifact_or_corrupted_frozen_input_cannot_be_reused(self):
        run,binding,_,_=self.failed();board_path=self.project/'storyboard.json';original=board_path.read_bytes();board=read(board_path);board['segments'][0]['options'][0]['action']+='新修改';atomic(board_path,board)
        with self.assertRaises(FileExistsError):self.resume(run,binding)
        board_path.write_bytes(original);task=self.review.load()['nodes']['storyboard']['runs'][-1];path=self.project/task['packet_path'];packet=read(path);packet['plan']='forbidden';atomic(path,packet)
        with self.assertRaises(ValueError):self.resume(run,binding)

    def test_unknown_usage_is_preserved_and_independent_token_budget_still_blocks_retry(self):
        run,binding,_,_=self.failed();state=self.review.load();old=copy.deepcopy(state['nodes']['storyboard']['runs'][-1]['calls'][-1]);state['policy']['max_tokens']=1000;atomic(self.review.path,state);before=self.review.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'用量未返回'):self.resume(run,binding)
        self.assertEqual(self.review.path.read_bytes(),before);self.assertEqual(self.review.load()['nodes']['storyboard']['runs'][-1]['calls'][-1],old)
        self.assertEqual(old['usage'],{});self.assertIsNone(old['model_invoked'])

    def test_successful_producer_and_supervisor_repair_then_use_targeted_acceptance(self):
        run,binding,_,_=self.failed();value=self.resume(run,binding);packet=self.review.producer_packet('storyboard',run)['packet']
        audit=self.audit('producer');self.review.reserve_call('storyboard',run,value['producer_key'],fixtures.ROUTE,'producer');self.review.call_result('storyboard',run,value['producer_key'],dict(totalTokens=5),agent_audit=audit)
        items=[dict(id=c['id'],verdict='通过',reason='合成真实原句',evidence=[dict(quote=packet['input']['text'],source_id='S',source_quote=packet['evidence']['sources'][0]['text'],locator='正文')]) for c in packet['checklist']]
        action=packet['storyboard']['segments'][0]['options'][0]['action'];replacement=action+'，再让焦点停稳到结果'
        repair=dict(issue_id='finding:F1',path='storyboard.json',before_sha256=packet['editable_files'][0]['sha256'],find=action,replace=replacement,reason='合成修复动作结果')
        result=dict(binding=binding,agent_audit=audit,items=items,repairs=[repair],summary='合成源核验完成');verdict=self.review.producer_submit('storyboard',run,result)
        self.assertTrue(verdict['can_repair']);self.assertFalse(verdict['report']['passed'])
        supervisor=self.audit('supervisor');self.review.reserve_call('storyboard',run,value['supervisor_key'],fixtures.ROUTE,'supervisor');self.review.call_result('storyboard',run,value['supervisor_key'],dict(totalTokens=7),agent_audit=supervisor)
        self.review.supervisor_submit('storyboard',run,dict(binding=binding,agent_audit=supervisor,passed=True,findings=[],summary='合成执行核验通过，不批准内容'))
        self.review.repair('storyboard',run,[repair],fixtures.PRODUCER['id']);new_packet=self.review.producer_packet('storyboard',run)['packet']
        self.assertNotEqual(new_packet['fingerprint'],binding['fingerprint']);self.assertIn(replacement,(self.project/'storyboard.json').read_text())
        with self.assertRaisesRegex(ValueError,'已完成一次'):self.review.packet('storyboard',run)
        task=self.review.node_view('storyboard')['run']
        self.assertEqual(len(task['iterations']),2);self.assertEqual(task['iterations'][1]['acceptance_mode'],'targeted')
        self.assertNotIn('report',task['iterations'][1]);self.assertEqual(new_packet['blind_report'],task['iterations'][0]['report'])
        old=next(c for c in task['calls'] if c['key']=='producer-0');self.assertEqual(old['status'],'failed');self.assertEqual(old['usage'],{})
        self.review.reserve_call('storyboard',run,'targeted-producer',fixtures.ROUTE,'producer')
        self.review.call_result('storyboard',run,'targeted-producer',error='合成当前定向验收连接失败',execution_phase='preflight',model_invoked=False)
        self.review.finish('storyboard',run,error='当前定向验收预检失败')
        resumed=self.resume(run,new_packet['binding'],request='retry-current-targeted')
        self.assertTrue(resumed['started']);self.assertEqual(resumed['iteration'],1)
        self.assertEqual(sum(call.get('role')=='reviewer' for call in resumed['run']['calls']),1)


if __name__=='__main__':unittest.main()
