"""Synthetic-only contracts for one blind review and fixed issue acceptance."""
import copy
import subprocess
import unittest
import uuid

import test_ai_review as fixture
from test_ai_review import ROUTE,PRODUCER
from ai_review import Review
import blind_review as blind
from workflow import atomic,read


class SingleBlindReviewTests(unittest.TestCase):
    setUp=fixture.AIReviewTests.setUp
    tearDown=fixture.AIReviewTests.tearDown
    begin=fixture.AIReviewTests.begin
    result=fixture.AIReviewTests.result
    audit=fixture.AIReviewTests.audit
    recorded=fixture.AIReviewTests.recorded
    submit=fixture.AIReviewTests.submit
    passing_script=fixture.AIReviewTests.passing_script
    repair=fixture.AIReviewTests.repair

    def producer_accept(self,run,verdict='通过'):
        packet=self.review.producer_packet('script',run)['packet']
        result=self.result('script',run,verdict)
        audit=self.audit('producer');self.recorded('script',run,audit)
        result.update(agent_audit=audit,binding=packet['binding'])
        value=self.review.producer_submit('script',run,result)
        audit=self.audit('supervisor');self.recorded('script',run,audit)
        self.review.supervisor_submit('script',run,dict(binding=packet['binding'],passed=True,summary='合成夹具定向执行核验',findings=[],agent_audit=audit))
        return value

    def test_changed_hash_and_explicit_continue_never_create_second_blind_review(self):
        run=self.passing_script();editor=self.studio.editor.read()
        self.studio.editor.save(editor['text']+'\n\n新增检查订单日期。',editor['revision'])
        auto=self.review.begin('script','new-auto','auto',route=ROUTE,producer=PRODUCER)
        self.assertFalse(auto['started']);self.assertEqual(auto['run']['id'],run)
        value=self.review.begin('script','targeted-followup','continue',route=ROUTE,producer=PRODUCER)
        self.assertTrue(value['started']);self.assertTrue(value['producer_only']);self.assertEqual(value['run']['id'],run)
        with self.assertRaisesRegex(ValueError,'只盲审一次'):
            self.review.reserve_call('script',run,'second-reviewer',ROUTE,'reviewer')
        with self.assertRaisesRegex(ValueError,'已完成一次'):
            self.review.packet('script',run)
        self.assertEqual(len(self.review.load()['nodes']['script']['runs']),1)

    def test_one_repair_preserves_baseline_and_accepts_current_evidence(self):
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='明确核对对象')]
        self.submit('script',run,result)
        baseline=copy.deepcopy(self.review.node_view('script')['run']['blind_report'])
        self.repair('script',run,result['repairs'])
        packet=self.review.producer_packet('script',run)['packet']
        self.assertEqual(packet['acceptance_mode'],'targeted');self.assertNotEqual(packet['fingerprint'],baseline['fingerprint'])
        self.assertEqual(packet['blind_report'],baseline);self.assertTrue(packet['issue_ledger'])
        self.producer_accept(run);self.review.finish('script',run)
        view=self.review.node_view('script');self.assertTrue(view['passed']);self.assertFalse(view['user_confirmed'])
        self.assertEqual(view['run']['blind_report'],baseline)
        self.assertTrue(all(item['status']=='resolved' for item in view['issue_ledger']))
        self.assertEqual(sum(call['role']=='reviewer' for call in view['run']['calls']),1)
        self.assertEqual(view['run']['report']['fingerprint'],view['fingerprint'])

    def test_unresolved_acceptance_does_not_start_another_automatic_repair(self):
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='明确核对对象')]
        self.submit('script',run,result);self.repair('script',run,result['repairs'])
        packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单日期',replace='先核对订单时间',reason='仍需修改')]
        audit=self.audit('producer');self.recorded('script',run,audit);result.update(agent_audit=audit,binding=packet['binding'])
        value=self.review.producer_submit('script',run,result)
        self.assertFalse(value['can_repair']);self.assertFalse(value['report']['passed'])
        with self.assertRaisesRegex(ValueError,'批次已使用'):
            self.repair('script',run,result['repairs'])

    def test_only_explicit_new_scheme_creates_new_cycle_and_preserves_usage(self):
        run=self.passing_script();calls=self.review.node_view('script')['calls']
        self.review.select_scheme('script','new-user-selected-scheme','用户明确改选实质不同的教学方案')
        self.assertFalse(self.review.node_view('script')['passed'])
        next_run=self.begin(request='new-scheme')
        self.assertNotEqual(run,next_run);self.assertEqual(self.review.node_view('script')['calls'],calls)
        self.assertEqual(len(self.review.load()['nodes']['script']['runs']),2)

    def test_simulated_click_cannot_open_a_new_scheme_or_reset_used_blind_review(self):
        self.passing_script();before=self.review.path.read_bytes()
        atomic(self.project/'workbench-review-context.json',dict(scope='qa-simulation',course_id=read(self.course.state_file)['course_id']))
        with self.assertRaisesRegex(ValueError,'用户明确改选'):
            self.studio.action('review-select-scheme',dict(baseRevision=self.course.status()['revision'],stage='script',scheme_id='simulated-new-scheme',evidence='模拟点击'))
        self.assertEqual(self.review.path.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'用户实际选择'):
            self.review.select_scheme('script','model-new-scheme','自动换方案',actor='producer')
        self.assertEqual(self.review.path.read_bytes(),before)

    def test_storyboard_only_exposes_current_selected_option(self):
        board=dict(segments=[dict(id='S1',selected='B',script_excerpt='当前口播',options=[dict(id='A',opening='不选的坏方案'),dict(id='B',opening='当前方案')])])
        projected=blind.storyboard_artifact(board)
        self.assertEqual([option['id'] for option in projected['segments'][0]['options']],['B'])
        self.assertNotIn('不选的坏方案',str(projected))
        board['segments'][0]['selected']='missing'
        with self.assertRaisesRegex(ValueError,'唯一选定方案'):
            blind.storyboard_artifact(board)

    def test_findings_keep_stage_evidence_methods_and_private_contract_is_removed(self):
        for stage,method,refs in [('script','script_read',[]),('storyboard','storyboard_read',[]),
                                  ('final','frames',[dict(time=1)]),('pilot','frame_sequence',[dict(time=1),dict(time=2)])]:
            run=dict(stage=stage)
            self.review._freeze_issues(run,dict(fingerprint='baseline',items=[dict(id='finding:F01',critical=True,verdict='需修改',label='当前问题',reason='影响理解',evidence=refs)]))
            self.assertEqual(run['issue_ledger'][0]['required_method'],method)
        board=dict(schema=dict(source='PRIVATE_SCHEMA'),reading_contract=dict(source='PRIVATE_ORIGINAL',expected_answer='PRIVATE_EXPECTED'),segments=[])
        self.assertNotIn('PRIVATE',str(blind.storyboard_artifact(board)))

    def test_kgxc_greeting_preflight_covers_missing_config_and_targeted_continuation(self):
        atomic(self.project/'project.json',dict(brand=dict(profile='kgxc')))
        with self.assertRaisesRegex(ValueError,'质量检查未通过'):
            self.begin()
        editor=self.studio.editor.read();self.studio.editor.save('大家好，欢迎来到酷果星创。\n\n'+editor['text'],editor['revision'])
        run=self.begin(mode='continue');self.submit('script',run,self.result('script',run));self.review.finish('script',run)
        editor=self.studio.editor.read();self.studio.editor.save(editor['text'].replace('大家好，欢迎来到酷果星创。',''),editor['revision'])
        with self.assertRaisesRegex(ValueError,'质量检查未通过'):
            self.begin(request='must-keep-greeting',mode='continue')

    def test_media_finding_cannot_be_closed_by_current_script_quote(self):
        media=self.project/'fixture.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=30:d=1','-c:v','libx264','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['fixture.mp4'];atomic(self.course.state_file,state)
        run=self.begin('final',request='fixture-media',mode='continue');packet=self.review.packet('final',run)['packet']
        frame=packet['evidence']['frames'][0];refs=[dict(sha256=frame['sha256'],time=frame['time'])]
        audit=self.audit('reviewer',packet);self.recorded('final',run,audit,[frame['sha256']])
        self.review.submit('final',run,dict(binding=packet['binding'],learner=dict(about='当前画面',what_it_said='蓝色画面',learned=['蓝色'],confusions=[]),
            items=[],findings=[dict(id='F01',problem='当前角色被遮挡',evidence=refs)],summary='合成缺陷',inspected_frame_hashes=[frame['sha256']],agent_audit=audit))
        packet=self.review.producer_packet('final',run)['packet'];result=self.result('final',run)
        audit=self.audit('producer');self.recorded('final',run,audit);result.update(agent_audit=audit,binding=packet['binding'])
        self.review.producer_submit('final',run,result);self.review.finish('final',run,error='合成待修复问题')
        self.begin('final',request='targeted-media',mode='continue');packet=self.review.producer_packet('final',run)['packet']
        finding=next(item for item in packet['checklist'] if item['id']=='finding:F01')
        self.assertEqual(finding['required_method'],'frames')
        result=self.result('final',run);audit=self.audit('producer');self.recorded('final',run,audit);result.update(agent_audit=audit,binding=packet['binding'])
        value=self.review.producer_submit('final',run,result)
        self.assertFalse(value['report']['passed'])
        item=next(item for item in self.review.node_view('final')['issue_ledger'] if item['id']=='finding:F01')
        self.assertEqual(item['status'],'open')


if __name__=='__main__':unittest.main()
