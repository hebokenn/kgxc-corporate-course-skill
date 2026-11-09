from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from workflow import Course,read,atomic
from studio import Studio
from script_editor import ScriptEditor
from ai_review import Review,substantive_example,gate_errors,approved
from test_branch_workflow import design

ROUTE=dict(provider='codex-chatgpt',model='gpt-6.1-sol')
PRODUCER=dict(id='fixture-producer',session_id='fixture-producer-session',role='producer')
TEXT='先核对订单，再核对编码。示例：订单A列出的编码是P12，实物标签也是P12；核对后记录一致，再把商品交给同事。练习请核对下一件，若编码不同，先暂停交接并记录差异。'


class AIReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.project=self.root/'project'
        atomic(self.project/'workbench.json',dict(title='审阅闭环技术夹具',scenes=[],media={}))
        self.course=Course(self.root);self.course.init('审阅闭环技术夹具');design(self.course)
        self.course.confirm('outline',self.course.status()['revision'],'QA结构确认')
        self.space=SimpleNamespace(root=self.root,project=self.project,file=self.project/'workbench.json')
        self.studio=Studio(self.space)
        self.studio.save_sections([dict(unit_id='U',body=TEXT)],self.course.status()['revision'],official=True)
        self.review=Review(self.course);self.review.ensure()
        from source_coverage_fixture import confirm_fixture_coverage
        confirm_fixture_coverage(self.course)
    def tearDown(self):self.tmp.cleanup()
    def begin(self,stage='script',request='automatic-input',mode='auto',instruction=''):
        value=self.review.begin(stage,request,mode,instruction,ROUTE,'test-owner',PRODUCER);return value['run']['id']
    def result(self,stage,run,verdict='通过'):
        packet=self.review.producer_packet(stage,run)['packet'];quote=packet['input']['text']
        return dict(summary='技术夹具结论，不代表真实课程验收',items=[dict(id=c['id'],verdict=verdict,reason='依据实际成果',evidence=[dict(method=c['required_method'],quote=quote,source_id='S',source_quote=packet['evidence']['sources'][0]['text'],locator='正文')]) for c in packet['checklist']],repairs=[])
    def audit(self,role,packet=None):
        identity=uuid.uuid4().hex
        value=dict(id=PRODUCER['id'] if role=='producer' else identity,session_id=PRODUCER['session_id'] if role=='producer' else identity+'-session',role=role,route=ROUTE,invocation_ids=[identity+'-call'])
        if role!='producer':value.update(read_only=True,isolated=True)
        if role=='reviewer':value.update(capabilities=['text','images'],artifact_ids=[a['id'] for a in packet['allowed_artifacts'] if a['kind']!='video'])
        return value
    def recorded(self,stage,run,audit,frames=None):
        key=uuid.uuid4().hex
        self.review.reserve_call(stage,run,key,ROUTE,audit['role'])
        self.review.call_result(stage,run,key,dict(totalTokens=0),sent_frames=frames,agent_audit=audit)
    def submit(self,stage,run,result):
        baseline=self.review.node_view(stage)['run'].get('blind_report')
        if not baseline:
            packet=Review.packet(self.review,stage,run)['packet'];audit=self.audit('reviewer',packet)
            if stage=='script':refs=[dict(method='script_read',quote=packet['input']['text'])]
            elif stage=='storyboard':refs=[dict(method='storyboard_read',segment_id=packet['input']['storyboard']['segments'][0]['id'],quote=packet['input']['storyboard']['segments'][0]['script_excerpt'])]
            else:refs=[dict(method='frames',sha256=packet['evidence']['frames'][0]['sha256'],time=packet['evidence']['frames'][0]['time'])] if packet['evidence']['frames'] else []
            review=dict(binding=packet['binding'],learner=dict(about='核对交接',what_it_said='先核对订单，再核对编码。',learned=['核对后再交接'],confusions=[]),findings=[],summary='合成夹具独立学员审阅',items=[dict(id=c['id'],verdict='通过',reason='实际成果',evidence=refs) for c in packet['checklist']],inspected_frame_hashes=[f['sha256'] for f in packet['evidence']['frames']],agent_audit=audit)
            self.recorded(stage,run,audit,review['inspected_frame_hashes']);Review.submit(self.review,stage,run,review)
        packet=self.review.producer_packet(stage,run)['packet']
        audit=self.audit('producer');result=dict(result,agent_audit=audit,binding=packet['binding'])
        self.recorded(stage,run,audit);value=self.review.producer_submit(stage,run,result)
        audit=self.audit('supervisor');self.recorded(stage,run,audit)
        self.review.supervisor_submit(stage,run,dict(binding=packet['binding'],passed=True,summary='合成夹具执行监督通过',findings=[],agent_audit=audit))
        value['report']=self.review.node_view(stage)['run']['report']
        return value
    def repair(self,stage,run,repairs):return self.review.repair(stage,run,repairs,PRODUCER['id'])
    def passing_script(self):
        run=self.begin();self.submit('script',run,self.result('script',run));self.review.finish('script',run);return run
    def test_headings_and_empty_table_cannot_be_a_complete_example(self):
        empty='| 触发 | 身体信号 | 我做了什么 | 对方回应 | 下次改哪句话 |\n|---|---|---|---|---|\n|待填|待填|待填|待填|待填|'
        self.assertFalse(substantive_example(empty));self.assertTrue(substantive_example(TEXT))
        self.studio.save_sections([dict(unit_id='U',body=empty)],self.course.status()['revision'],self.studio.editor.read()['revision'],official=True)
        run=self.begin();report=self.submit('script',run,self.result('script',run))['report']
        self.assertFalse(report['passed']);self.assertEqual(next(i for i in report['items'] if i['id']=='example-completeness')['verdict'],'需修改')
    def test_close_keeps_pending_and_draft_and_does_not_approve(self):
        run=self.passing_script();self.review.ui('script',run,'draft','请重点检查身份转变');self.review.ui('script',run,'dismiss')
        reopened=Review(self.course).node_view('script')
        self.assertEqual(reopened['status'],'awaiting_confirmation');self.assertEqual(reopened['draft'],'请重点检查身份转变')
        self.assertFalse(reopened['user_confirmed']);self.assertFalse(approved(self.course,'script'))
    def test_auto_events_and_call_reservations_are_durable_and_idempotent(self):
        run=self.begin();self.assertFalse(Review(self.course).begin('script','other-ui-event','auto',route=ROUTE,producer=PRODUCER)['started'])
        self.assertTrue(self.review.reserve_call('script',run,'c1',ROUTE)['reserved'])
        self.assertFalse(Review(self.course).reserve_call('script',run,'c1',ROUTE)['reserved'])
        self.assertEqual(self.review.node_view('script')['calls'],1)
    def test_old_summary_can_close_without_overwriting_new_round_input(self):
        old=self.passing_script();self.review.ui('script',old,'draft','旧轮意见')
        self.review.select_scheme('script','new-explicit-scheme','用户明确选择新的实质方案')
        new=self.begin(request='new-round',mode='continue');self.review.ui('script',new,'draft','新轮人工意见')
        self.review.ui('script',old,'draft','旧窗口尚未保存的意见');self.review.ui('script',old,'dismiss')
        current=self.review.node_view('script');self.assertEqual(current['run']['id'],new)
        self.assertEqual(current['draft'],'新轮人工意见');self.assertFalse(current['user_confirmed'])
        prior=self.review.load()['nodes']['script']['runs'][0];self.assertEqual(prior['ui_draft'],'旧窗口尚未保存的意见');self.assertTrue(prior['dismissed_at'])
    def test_explicit_continue_and_modify_reuse_blind_report_without_resetting_usage(self):
        run=self.begin();self.review.reserve_call('script',run,'c1',ROUTE,'producer');self.review.call_result('script',run,'c1',dict(totalTokens=321));self.submit('script',run,self.result('script',run));self.review.finish('script',run)
        second=self.begin(request='explicit-continue',mode='continue');self.assertEqual(run,second)
        third=self.begin(request='explicit-modify',mode='modify',instruction='补充完整示范')
        self.assertEqual(second,third);self.assertEqual(self.review.node_view('script')['calls'],4);self.assertEqual(self.review.node_view('script')['usage']['totalTokens'],321)
        packet=self.review.producer_packet('script',third)['packet'];self.assertEqual(packet['instruction'],'补充完整示范');self.assertEqual(packet['acceptance_mode'],'targeted')
        self.assertTrue(packet['targeted_repair_authorized'])
    def test_modification_feedback_stays_in_acceptance_checks_on_later_rounds(self):
        run=self.begin(request='modify-feedback',mode='modify',instruction='必须说明编码不一致时如何反馈')
        self.review.producer_packet('script',run);self.review.finish('script',run,error='技术夹具：本轮中断')
        newer=self.begin(request='continue-feedback',mode='continue');packet=self.review.producer_packet('script',newer)['packet']
        feedback=next(c for c in packet['checklist'] if c['label']=='必须说明编码不一致时如何反馈')
        result=self.result('script',newer);result['items']=[i for i in result['items'] if i['id']!=feedback['id']]
        report=self.submit('script',newer,result)['report'];self.assertFalse(report['passed']);self.assertIn(feedback['id'],report['blocking_ids'])
    def test_final_feedback_does_not_invalidate_an_unchanged_approved_script(self):
        run=self.passing_script();self.review.approve('script',run);before=self.review.fingerprint('script')
        media=self.root/'delivery/test.mp4';media.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=1','-c:v','libx264','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['../delivery/test.mp4'];atomic(self.course.state_file,state)
        self.begin('final',request='final-feedback',mode='modify',instruction='核对结尾声音完整')
        self.assertEqual(before,self.review.fingerprint('script'));self.assertTrue(self.review.node_view('script')['user_confirmed'])
    def test_autosave_does_not_trigger_a_review_of_old_media(self):
        media=self.root/'delivery/test.mp4';media.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=1','-c:v','libx264','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['../delivery/test.mp4'];state['final_context']={'outdated':True};atomic(self.course.state_file,state)
        with self.assertRaisesRegex(ValueError,'实际媒体尚未更新'):self.begin('final')
        self.assertEqual(self.review.node_view('final')['calls'],0)
        run=self.begin('final',request='explicit-old-media-inspection',mode='continue');self.assertTrue(run)
    def test_new_human_draft_invalidates_old_report_and_cannot_be_approved(self):
        run=self.passing_script();editor=ScriptEditor(self.space);value=editor.read();editor.save(value['text']+'\n\n人工新增：先检查订单日期。',value['revision'])
        self.assertEqual(self.review.node_view('script')['status'],'stale')
        with self.assertRaises(ValueError):self.review.approve('script',run)
    def test_patch_does_not_overwrite_human_changes_during_review(self):
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='明确核对对象')]
        self.submit('script',run,result);editor=ScriptEditor(self.space);value=editor.read();manual=value['text']+'\n\n人工新增，请保留。';editor.save(manual,value['revision'])
        with self.assertRaises(FileExistsError):self.repair('script',run,result['repairs'])
        self.assertEqual(editor.read()['text'],manual);self.assertEqual(self.course.script()['text'],packet['input']['text'])
    def test_actual_local_repair_is_saved_with_before_diff_and_rechecks_new_text(self):
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='明确核对对象')]
        self.submit('script',run,result);self.repair('script',run,result['repairs'])
        after=self.review.producer_packet('script',run)['packet'];self.assertIn('先核对订单日期',after['input']['text']);self.assertNotEqual(packet['fingerprint'],after['fingerprint'])
        backup=self.project/'qa/ai-review'/run/'repair-1/source/transcript.md';self.assertEqual(backup.read_text(),packet['input']['text'])
        self.assertIn('+', (backup.parents[1]/'changes.diff').read_text());self.assertEqual(self.course.script()['text'],packet['input']['text'])
        self.submit('script',run,self.result('script',run));self.review.finish('script',run)
        self.assertTrue(self.review.node_view('script')['passed']);self.assertFalse(self.review.node_view('script')['user_confirmed'])

    def test_official_human_change_during_draft_review_preserves_both_versions(self):
        editor=ScriptEditor(self.space);value=editor.read();draft=value['text']+'\n\n尚未确认的人工草稿。';editor.save(draft,value['revision'])
        run=self.begin(request='review-human-draft',mode='continue');packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='明确核对对象')]
        self.submit('script',run,result)
        official=self.course.script()['text']+'\n\n审阅期间人工更新正式稿。';(self.project/'source/transcript.md').write_text(official)
        self.assertEqual(self.review.node_view('script')['status'],'stale')
        with self.assertRaises(FileExistsError):self.repair('script',run,result['repairs'])
        with self.assertRaises(FileExistsError):self.begin(request='cannot-review-conflict',mode='continue')
        self.assertEqual(editor.read()['text'],draft);self.assertEqual(self.course.script()['text'],official)
    def test_one_automatic_repair_batch_stops_without_resetting_cumulative_budget(self):
        self.review.extend('script',0,18,'合成夹具：检查一批自动修复与累计预算')
        run=self.begin();packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=packet['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='补充明确依据')]
        self.submit('script',run,result);self.repair('script',run,result['repairs'])
        packet=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改');result['repairs']=[dict(issue_id='teaching-continuity')]
        value=self.submit('script',run,result);self.assertFalse(value['can_repair']);self.assertEqual(self.review.node_view('script')['repairs'],1)
        with self.assertRaisesRegex(ValueError,'批次已使用'):self.repair('script',run,result['repairs'])
        self.review.finish('script',run,error='当前定向验收尚未闭合')
        second=self.begin(request='explicit-followup',mode='continue');self.assertEqual(second,run)
        self.assertEqual(self.review.node_view('script')['repairs'],1)
        self.assertTrue(self.review.producer_packet('script',second)['packet']['targeted_repair_authorized'])
    def test_second_blind_report_cannot_expand_the_frozen_problem_list(self):
        run=self.begin();self.submit('script',run,self.result('script',run,'需修改'))
        original=copy.deepcopy(self.review.node_view('script')['run']['blind_report'])
        with self.assertRaisesRegex(ValueError,'只接受一次'):
            self.review.submit('script',run,{})
        self.assertEqual(self.review.node_view('script')['run']['blind_report'],original)
    def test_missing_checks_cannot_be_dropped_and_critical_na_cannot_pass(self):
        run=self.begin();result=self.result('script',run);result['items']=result['items'][:1];result['items'][0]['verdict']='不适用'
        report=self.submit('script',run,result)['report'];self.assertFalse(report['passed']);self.assertGreater(len(report['items']),1)
        self.assertEqual(next(i for i in report['items'] if i['id']=='source-accuracy')['verdict'],'无法验证')
    def test_unverifiable_source_reference_cannot_pass(self):
        run=self.begin();result=self.result('script',run)
        result['items'][0]['evidence'][0]['source_quote']='原件中没有这句话'
        report=self.submit('script',run,result)['report']
        self.assertEqual(next(i for i in report['items'] if i['id']=='source-accuracy')['verdict'],'无法验证');self.assertFalse(report['passed'])
    def test_course_hold_survives_reload_and_blocks_new_calls_and_repairs(self):
        run=self.begin();self.review.reserve_call('script',run,'c1',ROUTE)
        self.review.hold(True,'先修插件，再课程')
        self.assertTrue(Review(self.course).view()['hold']['held'])
        self.assertEqual(self.review.node_view('script')['status'],'failed')
        self.review.call_result('script',run,'c1',dict(totalTokens=123),error='已取消')
        self.assertEqual(self.review.node_view('script')['usage']['totalTokens'],123)
        with self.assertRaises(ValueError):self.begin(request='must-not-call',mode='continue')
        with self.assertRaises(ValueError):self.review.reserve_call('script',run,'c2',ROUTE)
        self.review.hold(False,'用户明确恢复')
        self.assertFalse(self.review.begin('script','refresh-again','auto',route=ROUTE,producer=PRODUCER)['started'])
    def test_initial_manual_draft_can_start_explicit_review_and_progress_close_does_not_dismiss_summary(self):
        editor=ScriptEditor(self.space);value=editor.read();editor.save(value['text']+'\n人工新增的讲解。',value['revision'])
        with self.assertRaisesRegex(ValueError,'人工草稿'):self.begin()
        run=self.begin(request='human-start',mode='continue');self.review.ui('script',run,'dismiss')
        self.assertNotIn('dismissed_at',self.review.node_view('script')['run'])
        self.submit('script',run,self.result('script',run));self.review.finish('script',run)
        self.assertNotIn('dismissed_at',self.review.node_view('script')['run'])
    def test_budget_and_route_remain_pinned_across_explicit_requests(self):
        state=self.review.load();state['policy']['max_calls']=1;atomic(self.review.path,state)
        run=self.begin();self.review.reserve_call('script',run,'c1',ROUTE);self.review.call_result('script',run,'c1',dict(totalTokens=10));self.review.finish('script',run,error='技术模拟失败')
        value=self.review.begin('script','new-request','continue',route=ROUTE,producer=PRODUCER);self.assertFalse(value['started']);self.assertEqual(value['run']['status'],'failed');self.assertEqual(value['run']['id'],run);self.assertEqual(self.review.node_view('script')['calls'],1)
        with self.assertRaises(ValueError):self.review.begin('script','wrong-provider','continue',route=dict(provider='other-paid-source',model='other'))
    def test_unknown_usage_cannot_bypass_a_configured_token_budget(self):
        state=self.review.load();state['policy']['max_tokens']=100;atomic(self.review.path,state)
        run=self.begin();self.review.reserve_call('script',run,'c1',ROUTE)
        self.review.call_result('script',run,'c1',error='技术夹具：调用中断，用量未返回')
        with self.assertRaisesRegex(ValueError,'用量未返回'):self.review.reserve_call('script',run,'c2',ROUTE,'producer')
        self.assertEqual(self.review.node_view('script')['calls'],1)
    def test_late_usage_is_counted_once_without_reviving_a_superseded_run(self):
        run=self.begin();self.review.reserve_call('script',run,'c1',ROUTE);self.review.finish('script',run,error='调用取消')
        newer=self.begin(request='new-explicit-request',mode='continue')
        self.review.call_result('script',run,'c1',dict(totalTokens=321),error='已中断')
        self.review.call_result('script',run,'c1',dict(totalTokens=321),error='重复回调')
        node=self.review.node_view('script');self.assertEqual(node['run']['id'],newer);self.assertEqual(node['usage']['totalTokens'],321)
    def test_only_explicit_report_confirmation_creates_user_approval(self):
        run=self.passing_script();self.assertFalse(gate_errors(self.course,'script'));self.assertFalse(approved(self.course,'script'))
        value=self.studio.action('review-approve',dict(baseRevision=self.course.status()['revision'],stage='script',run_id=run))
        self.assertTrue(value['ai_review']['nodes']['script']['user_confirmed']);self.assertFalse(value['ai_review']['nodes']['final']['user_confirmed'])
        self.assertEqual(value['deliveries'],[])
    def test_visual_repair_increments_document_revision_and_preserves_new_manual_edits(self):
        from backend import Workspace
        from test_workbench import WorkbenchTests
        fixture=WorkbenchTests();fixture.setUp()
        try:
            for path in fixture.project.iterdir():
                if path.is_file():shutil.copy2(path,self.project/path.name)
        finally:fixture.tearDown()
        media=self.project/'media/test.mp4';media.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=1','-c:v','libx264','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['media/test.mp4'];atomic(self.course.state_file,state)
        space=Workspace(self.root);before=read(space.file);original=space.file.read_bytes();space.save(copy.deepcopy(before),before['revision']);self.assertEqual(space.file.read_bytes(),original)
        run=self.begin('final',mode='continue');result=self.result('final',run,'需修改')
        result['repairs']=[dict(issue_id='visual-purpose',path='workbench.json',before_sha256=hashlib.sha256(space.file.read_bytes()).hexdigest(),find='"voice": "original"',replace='"voice": "another-voice"',reason='技术夹具：禁止擅改既定声音')]
        self.submit('final',run,result)
        with self.assertRaisesRegex(ValueError,'验收标准'):self.repair('final',run,result['repairs'])
        self.assertEqual(read(space.file),before);self.review.finish('final',run,error='已拒绝越权修改')
        run=self.begin('final',request='explicit-visual-repair',mode='continue');result=self.result('final',run,'需修改')
        result['repairs']=[dict(issue_id='visual-purpose',path='workbench.json',before_sha256=hashlib.sha256(space.file.read_bytes()).hexdigest(),find='核对SN 2026',replace='先核对SN 2026',reason='明确画面核对动作')]
        self.submit('final',run,result);self.repair('final',run,result['repairs'])
        self.assertEqual(read(space.file)['revision'],before['revision']+1)
        self.assertEqual(read(self.project/'workbench-history/000000.json'),before)
        with self.assertRaises(FileExistsError):space.save(before,before['revision'])
        manual=read(space.file);manual['captions'][0]['text']='人工新增的核对说明';space.save(manual,manual['revision'])
        with self.assertRaises(FileExistsError):self.repair('final',run,result['repairs'])
        self.assertEqual(read(space.file)['captions'][0]['text'],'人工新增的核对说明')
    def test_modified_media_and_missing_continuous_av_evidence_do_not_pass(self):
        media=self.root/'delivery/test.mp4';media.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['../delivery/test.mp4'];state['final_context']=self.course._video_context(state);atomic(self.course.state_file,state)
        run=self.begin('final');result=self.result('final',run);report=self.submit('final',run,result)['report']
        self.assertFalse(report['passed']);self.assertEqual(next(i for i in report['items'] if i['id']=='continuous-av')['verdict'],'无法验证')
        self.assertEqual(next(i for i in report['items'] if i['id']=='ending')['verdict'],'无法验证')
        self.assertEqual(next(i for i in report['items'] if i['id']=='source-accuracy')['verdict'],'无法验证')
        self.assertEqual(next(i for i in report['items'] if i['id']=='objective:O')['verdict'],'无法验证')
        self.review.render_start('final',run);expected=self.review.node_view('final')['run']['fingerprint']
        with self.assertRaises(ValueError):self.review.rebind_render('final',run,expected)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=320x180:r=30:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest','-y',str(media)],check=True)
        self.review.rebind_render('final',run,expected)
        new_packet=self.review.producer_packet('final',run)['packet']
        self.assertNotEqual(new_packet['fingerprint'],expected);self.assertTrue(new_packet['evidence']['frames'])
        self.assertNotEqual(new_packet['evidence']['media'][0]['sha256'],report['inspection']['media'][0]['sha256'])
        self.review.finish('final',run);media.write_bytes(media.read_bytes()+b'version-change')
        self.assertEqual(self.review.node_view('final')['status'],'stale')
        with self.assertRaises(ValueError):self.review.require_pass('final',run)


if __name__=='__main__':unittest.main()
