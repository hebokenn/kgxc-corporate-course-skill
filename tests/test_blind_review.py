"""Synthetic-only behavioral tests for the independent learner/producer boundary."""
import copy
import json
from pathlib import Path
import subprocess
import shutil
import unittest
import uuid
from types import SimpleNamespace

import test_ai_review as fixtures
from test_ai_review import PRODUCER, ROUTE, TEXT
from ai_review import Review, STAGES, approved, gate_errors, enabled
import blind_review as blind
from workflow import read, atomic, sha, hashed


class BlindReviewTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    def report(self,stage,run,verdict='通过'):
        packet=self.review.packet(stage,run)['packet']
        if stage=='script':refs=[dict(method='script_read',quote=packet['input']['text'])]
        elif stage=='storyboard':refs=[dict(method='storyboard_read',segment_id='S1',quote='先核对订单')]
        else:refs=[dict(method='frames',sha256=packet['evidence']['frames'][0]['sha256'],time=packet['evidence']['frames'][0]['time'])]
        return dict(binding=copy.deepcopy(packet['binding']),learner=dict(about='商品交接核对',what_it_said='先核对订单与编码，再交接。',learned=['核对一致后再交接；不一致先暂停。'],confusions=[]),findings=[],
                    items=[dict(id=c['id'],verdict=verdict,reason='合成夹具当前成果依据',evidence=copy.deepcopy(refs)) for c in packet['checklist']],summary='独立学员合成报告',
                    inspected_frame_hashes=[f['sha256'] for f in packet['evidence']['frames']],agent_audit=self.audit('reviewer',packet))

    def send(self,stage,run,result):
        packet=read(self.project/self.review.node_view(stage)['run']['packet_path'])
        self.review._validate_packet_files(packet)
        blind.validate_result(result,packet)
        blind.validate_audit(result['agent_audit'],'reviewer',PRODUCER,ROUTE)
        if not any(call.get('role')=='reviewer' and call.get('agent_audit')==result['agent_audit'] for call in self.review.node_view(stage)['run']['calls']):
            self.recorded(stage,run,result['agent_audit'],result.get('inspected_frame_hashes',[]))
        return self.review.submit(stage,run,result)

    def movie(self,stage,color='blue'):
        target=self.project/'media'/f'{stage}.mp4';target.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=96x64:r=10:d=0.4','-f','lavfi','-i','sine=frequency=440:duration=0.4','-c:v','libx264','-c:a','aac','-shortest','-y',str(target)],check=True)
        state=read(self.course.state_file);state.setdefault('artifacts',{})[stage]=[str(target.relative_to(self.project))];atomic(self.course.state_file,state)
        return target

    def board(self):
        value=dict(schema='course-storyboard/1',visual_direction=dict(palette='红白',typography='清晰无衬线',graphics='简洁图形',atmosphere='清楚'),segments=[dict(id='S1',kind='concept',script_excerpt='先核对订单，再核对编码。',duration=12,selected='A',options=[dict(id=i,method='对象演示 '+i,opening='订单和标签并排',action='核对框依次移动到两个编码',result='两个编码一致后显示交接',focus='核对结果',characters=False) for i in ['A','B','C']])])
        atomic(self.project/'storyboard.json',value)
        return value

    def test_script_packet_contains_only_current_transcript_and_generic_protocol(self):
        plan=read(self.course.plan_file);plan['audience']='AUDIENCE_PRIVATE';plan['performance_task']='TASK_PRIVATE'
        plan['objectives'][0]['statement']='OBJECTIVE_PRIVATE';atomic(self.course.plan_file,plan)
        source=self.course.relative(plan['sources'][0]['location']);source.write_text('SOURCE_PRIVATE 原始业务资料')
        self.review.requirements(['USER_PRIVATE'],'合成用户要求')
        run=self.begin(mode='modify',instruction='INSTRUCTION_PRIVATE')
        packet=self.review.packet('script',run)['packet'];serialized=json.dumps(packet,ensure_ascii=False)
        for canary in ['AUDIENCE_PRIVATE','TASK_PRIVATE','OBJECTIVE_PRIVATE','SOURCE_PRIVATE','USER_PRIVATE','INSTRUCTION_PRIVATE',str(self.root)]:self.assertNotIn(canary,serialized)
        self.assertEqual(packet['input'],dict(text=self.review.script_input()['text']))
        self.assertEqual(packet['allowed_artifacts'],[dict(id='transcript',kind='transcript',sha256=blind.artifact_digest(packet['input']['text']))])
        private=self.review.producer_packet('script',run)['packet']
        self.assertIn('SOURCE_PRIVATE',private['evidence']['sources'][0]['text'])
        self.assertEqual(private['instruction'],'INSTRUCTION_PRIVATE')
        self.assertTrue(any(c['id']=='source-accuracy' for c in private['checklist']))

    def test_stage_allowlist_never_imports_standalone_script_subtitles_native_or_other_movie(self):
        pilot=self.movie('pilot');final=self.movie('final','red')
        srt=self.project/'media/pilot.srt';srt.write_text('STANDALONE_SUBTITLE_PRIVATE')
        state=read(self.course.state_file);state['artifacts']['pilot'].append('media/pilot.srt');atomic(self.course.state_file,state)
        (self.project/'native').mkdir();(self.project/'native/private.js').write_text('NATIVE_PRIVATE')
        run=self.begin('pilot',mode='continue');packet=self.review.packet('pilot',run)['packet'];serialized=json.dumps(packet,ensure_ascii=False)
        for canary in [TEXT,'STANDALONE_SUBTITLE_PRIVATE','NATIVE_PRIVATE',sha(final),'media/pilot.mp4','media/pilot.srt']:self.assertNotIn(canary,serialized)
        self.assertNotIn('input',packet);self.assertEqual(packet['artifact_sha256'],sha(pilot))
        self.assertTrue(packet['evidence']['frames'])
        for item in packet['allowed_artifacts']:
            if item['kind']=='frame':self.assertEqual(item['parent_sha256'],sha(pilot))
            self.assertEqual(sha(self.project/item['path']),item['sha256'])
        result=self.report('pilot',run);result['agent_audit']['artifact_ids'].append('other-stage-video')
        with self.assertRaisesRegex(ValueError,'白名单'):self.send('pilot',run,result)

    def test_review_and_supervision_payloads_reject_every_write_authority(self):
        run=self.begin();result=self.report('script',run)
        for payload in [dict(repairs=[]),dict(patch={'path':'source/transcript.md'}),dict(learner={**result['learner'],'rewrite':'new text'}),dict(findings=[dict(id='bad',problem='问题',evidence=[dict(quote=TEXT)],replacement='改写')])]:
            wrong={**result,**payload}
            with self.assertRaises(ValueError):self.send('script',run,wrong)
        self.assertEqual(self.review.node_view('script')['repairs'],0)
        self.assertIn(TEXT,self.course.script()['text'])

    def test_learner_reconstruction_and_real_call_are_mandatory(self):
        run=self.begin();result=self.report('script',run)
        with self.assertRaisesRegex(ValueError,'实际代理调用'):self.review.submit('script',run,result)
        for wrong in [dict(result,learner={}),dict(result,learner=dict(result['learner'],what_it_said=''))]:
            with self.assertRaisesRegex(ValueError,'还原'):self.send('script',run,wrong)
        value=self.send('script',run,result)
        self.assertFalse(value['report']['passed']);self.assertTrue(value['needs_producer'])
        self.assertEqual(value['report']['learner']['learned'],result['learner']['learned'])

    def test_report_protocol_and_actual_version_must_match(self):
        run=self.begin();result=self.report('script',run)
        for key in ['protocol','fingerprint','artifact_sha256','packet_sha256','stage']:
            wrong=copy.deepcopy(result);wrong['binding'][key]='older-or-other'
            with self.assertRaisesRegex(ValueError,'协议版本'):self.send('script',run,wrong)
        self.send('script',run,result)
        with self.assertRaisesRegex(ValueError,'只接受一次'):self.review.submit('script',run,result)

    def test_original_material_injected_into_saved_packet_is_rejected(self):
        run=self.begin();result=self.report('script',run)
        state=self.review.load();path=self.project/state['nodes']['script']['runs'][-1]['packet_path'];packet=read(path)
        packet['sources']=[dict(text='FORBIDDEN_SOURCE')];atomic(path,packet)
        with self.assertRaisesRegex(ValueError,'非本阶段成果'):self.send('script',run,result)

    def test_reviewer_and_producer_and_supervisor_cannot_share_identity(self):
        run=self.begin();result=self.report('script',run)
        result['agent_audit'].update(id=PRODUCER['id'],session_id=PRODUCER['session_id'])
        with self.assertRaisesRegex(ValueError,'兼任'):self.send('script',run,result)
        result=self.report('script',run);self.send('script',run,result)
        supervisor={**result['agent_audit'],'role':'supervisor'}
        self.recorded('script',run,supervisor)
        with self.assertRaisesRegex(ValueError,'不同代理'):self.review.supervisor_submit('script',run,dict(binding=result['binding'],passed=True,findings=[],summary='合成',agent_audit=supervisor))

    def test_revision_reuses_report_and_new_stage_requires_a_fresh_reviewer_agent(self):
        run=self.begin();result=self.report('script',run);self.send('script',run,result);self.review.finish('script',run,error='合成阶段结束')
        newer=self.begin(request='new',mode='continue');self.assertEqual(newer,run)
        with self.assertRaisesRegex(ValueError,'已完成一次'):self.report('script',newer)
        self.review.finish('script',newer,error='合成定向任务结束')
        self.board();other=self.begin('storyboard',request='other-stage',mode='continue');next_result=self.report('storyboard',other)
        next_result['agent_audit'].update(id=result['agent_audit']['id'],session_id=result['agent_audit']['session_id'])
        with self.assertRaisesRegex(ValueError,'新的独立'):self.send('storyboard',other,next_result)

    def test_independent_findings_block_even_with_all_checklist_items_passing(self):
        run=self.begin();private=self.result('script',run)
        result=self.report('script',run);result['findings']=[dict(id='F1',problem='当前例子有歧义',evidence=[dict(quote='先核对订单')])]
        self.send('script',run,result)
        self.review.producer_packet('script',run)
        audit=self.audit('producer');self.recorded('script',run,audit)
        value=self.review.producer_submit('script',run,dict(private,agent_audit=audit,binding=result['binding']))
        self.assertIn('finding:F1',value['report']['blocking_ids']);self.assertFalse(value['report']['passed'])
        audit=self.audit('supervisor');self.recorded('script',run,audit)
        self.review.supervisor_submit('script',run,dict(binding=result['binding'],passed=True,findings=[],summary='执行隔离无异常',agent_audit=audit))
        self.review.finish('script',run)
        with self.assertRaises(ValueError):self.review.approve('script',run)

    def test_advisory_preference_is_preserved_without_blocking_current_scheme(self):
        run=self.begin();private=self.result('script',run)
        result=self.report('script',run)
        result['findings']=[dict(id='PREFERENCE',severity='advisory',problem='个人偏好：可以用另一种问候语气',evidence=[dict(quote='先核对订单')])]
        self.send('script',run,result)
        self.review.producer_packet('script',run)
        audit=self.audit('producer');self.recorded('script',run,audit)
        self.review.producer_submit('script',run,dict(private,agent_audit=audit,binding=result['binding']))
        audit=self.audit('supervisor');self.recorded('script',run,audit)
        self.review.supervisor_submit('script',run,dict(binding=result['binding'],passed=True,findings=[],summary='合成执行核验',agent_audit=audit))
        self.review.finish('script',run)
        view=self.review.node_view('script');self.assertTrue(view['passed']);self.assertFalse(view['user_confirmed'])
        finding=next(item for item in view['run']['report']['items'] if item['id']=='finding:PREFERENCE')
        self.assertFalse(finding['critical']);self.assertEqual(finding['verdict'],'需修改')
        self.assertEqual(view['issue_ledger'][0]['severity'],'advisory')
        self.assertEqual(view['run']['blind_report']['findings'],result['findings'])

    def test_unknown_finding_severity_cannot_silently_downgrade_a_problem(self):
        run=self.begin();result=self.report('script',run)
        for severity in ['preference','low','',None,False]:
            wrong=copy.deepcopy(result);wrong['findings']=[dict(id='F1',severity=severity,problem='合成级别',evidence=[dict(quote='先核对订单')])]
            with self.assertRaisesRegex(ValueError,'级别'):
                self.send('script',run,wrong)

    def test_advisory_finding_does_not_downgrade_unverified_required_checks(self):
        run=self.begin();result=self.report('script',run,'无法验证')
        for item in result['items']:item['critical']=False
        result['findings']=[dict(id='PREFERENCE',severity='advisory',problem='可选表达偏好',evidence=[dict(quote='先核对订单')])]
        self.send('script',run,result)
        report=self.review.node_view('script')['run']['blind_report']
        self.assertFalse(report['passed']);self.assertIn('teaching-continuity',report['blocking_ids'])
        self.assertNotIn('finding:PREFERENCE',report['blocking_ids'])
        self.assertTrue(next(item for item in report['items'] if item['id']=='teaching-continuity')['critical'])

    def test_unknown_or_missing_finding_locations_are_rejected(self):
        run=self.begin();result=self.report('script',run)
        for refs in [[],[dict(quote='原件里有但成果里没有')]]:
            wrong=copy.deepcopy(result);wrong['findings']=[dict(id='F1',problem='合成',evidence=refs)]
            with self.assertRaises(ValueError):self.send('script',run,wrong)

    def test_legacy_source_aware_pass_is_retained_but_never_counts_as_blind_review(self):
        run=self.begin();state=self.review.load();node=state['nodes']['script'];old=node['runs'][-1]
        old.pop('protocol');old.update(status='awaiting_confirmation',report=dict(passed=True),fingerprint=self.review.fingerprint('script'))
        node['calls']=2;node['usage']={'totalTokens':456};node['approval']=dict(run_id=run,fingerprint=old['fingerprint'],at='recorded-time',actor='dsh-user-click')
        atomic(self.review.path,state);view=self.review.node_view('script')
        self.assertTrue(view['legacy']);self.assertEqual(view['status'],'legacy');self.assertFalse(view['passed']);self.assertTrue(view['content_confirmation_preserved']);self.assertFalse(view['user_confirmed'])
        self.assertFalse(self.review.begin('script','automatic-upgrade','auto',route=ROUTE,producer=PRODUCER)['started'])
        newer=self.begin(request='new-protocol',mode='continue')
        self.assertNotEqual(newer,run);self.assertEqual(self.review.node_view('script')['calls'],2)
        self.assertEqual(self.review.node_view('script')['usage']['totalTokens'],456)
        self.assertEqual(self.review.load()['nodes']['script']['approval']['at'],'recorded-time')
        self.assertTrue(self.review.node_view('script')['history'][0]['legacy'])

    def test_unchanged_explicit_content_confirmation_reuses_original_actor_without_repeat_review(self):
        run=self.begin();self.complete('script',run,self.result('script',run));self.review.finish('script',run);self.review.approve('script',run)
        original=copy.deepcopy(self.review.load()['nodes']['script']['approval'])
        newer=self.begin(request='same-selected-scheme',mode='continue');self.assertEqual(newer,run)
        self.assertTrue(self.review.node_view('script')['user_confirmed'])
        self.assertEqual(self.review.load()['nodes']['script']['approval'],original)

    def test_existing_workflow_content_receipt_reuses_exact_gate_hash_without_new_click(self):
        state=read(self.course.state_file)
        receipt=dict(actor='qa-operator',evidence='合成夹具此前实际内容确认',at='earlier-confirmation',sha256=self.course._gate_hash('script',read(self.course.plan_file),state))
        state['gates']['script']=copy.deepcopy(receipt);atomic(self.course.state_file,state)
        self.assertTrue(self.review.node_view('script')['content_confirmation_preserved'])
        self.assertFalse(self.review.node_view('script')['user_confirmed'])
        run=self.begin();self.complete('script',run,self.result('script',run));self.review.finish('script',run)
        self.assertTrue(self.review.node_view('script')['user_confirmed'])
        self.assertNotIn('approval',self.review.load()['nodes']['script'])
        self.assertEqual(read(self.course.state_file)['gates']['script'],receipt)
        value=self.studio.editor.read();self.studio.editor.save(value['text']+'\n新草稿',value['revision'])
        self.assertFalse(self.review.node_view('script')['content_confirmation_preserved'])

    def test_storyboard_packet_removes_nested_private_metadata_but_retains_visual_data(self):
        board=self.board();board['teaching_goals']='GOAL_PRIVATE';board['visual_direction']['source_notes']='NESTED_SOURCE_PRIVATE'
        board['segments'][0]['teaching_goal']='SEGMENT_GOAL_PRIVATE';board['segments'][0]['recommendation_reason']='ANSWER_PRIVATE';board['segments'][0]['selection_receipt']={'evidence':'HISTORY_PRIVATE'}
        option=board['segments'][0]['options'][0]
        option['sceneGraph']=dict(nodes=[dict(id='chart',type='bar',data={'Q1':5,'Q2':8},metadata=dict(original_materials='NESTED_ORIGINAL_PRIVATE'))])
        option['motionPlan']=dict(objectStates={'chart':dict(**{'from':{'Q1':0,'Q2':0},'to':{'Q1':5,'Q2':8}})},expected_conclusion='EXPECTED_PRIVATE')
        atomic(self.project/'storyboard.json',board)
        run=self.begin('storyboard',mode='continue');packet=self.review.packet('storyboard',run)['packet'];serialized=json.dumps(packet,ensure_ascii=False)
        for canary in ['GOAL_PRIVATE','NESTED_SOURCE_PRIVATE','SEGMENT_GOAL_PRIVATE','ANSWER_PRIVATE','HISTORY_PRIVATE','NESTED_ORIGINAL_PRIVATE','EXPECTED_PRIVATE']:self.assertNotIn(canary,serialized)
        self.assertEqual(set(packet['input']),{'storyboard'})
        projected=packet['input']['storyboard']['segments'][0]['options'][0]
        self.assertEqual(projected['sceneGraph']['nodes'][0]['data'],{'Q1':5,'Q2':8})
        self.assertEqual(projected['motionPlan']['objectStates']['chart']['to'],{'Q1':5,'Q2':8})

    def navigation(self):
        return dict(schema='course-navigation/1',brand_bookends=dict(intro='media/PRIVATE_INTRO.mp4',outro='media/PRIVATE_OUTRO.mp4'),
                    open_sequence=['PRIVATE_PRODUCER_SEQUENCE'],timing_budget='PRIVATE_PRODUCER_TIMING',
                    toc=dict(sections=[dict(unit_id='U',label='合成章节')],design='PRIVATE_DESIGN_RULE'),
                    section_titles=[dict(unit_id='U',before='S1',label='合成章节')],
                    progress_bar=dict(position='底部安全区',style='细线',visible_from='S1',visible_until='S1',hide_on=['brand-intro','toc','chapter-title','outro']),
                    actual_timeline=dict(fps=30,total_frames=900,body=[90,810],toc_visible=[90,150],
                        section_title_windows=[dict(unit_id='U',window=[150,180])],coordinate='PRIVATE_PRODUCER_CLOCK_DESCRIPTION',
                        basis='PRIVATE_SOURCE_BINDING',inserted_frames=0,media_or_navigation_retimed=False))

    def test_storyboard_navigation_preserves_actual_display_windows_labels_and_visibility(self):
        board=self.board();board['navigation']=self.navigation();atomic(self.project/'storyboard.json',board);original=copy.deepcopy(board)
        run=self.begin('storyboard',mode='continue');packet=self.review.packet('storyboard',run)['packet'];projected=packet['input']['storyboard']
        self.assertEqual(projected['navigation'],dict(schema='course-navigation/1',toc=dict(sections=[dict(unit_id='U',label='合成章节')]),
            section_titles=[dict(unit_id='U',label='合成章节',before='S1')],progress_bar=board['navigation']['progress_bar'],
            actual_timeline=dict(fps=30,total_frames=900,body=[90,810],toc_visible=[90,150],section_title_windows=[dict(unit_id='U',window=[150,180])])))
        self.assertEqual(packet['artifact_sha256'],hashed(projected));blind.validate_packet(packet)
        self.assertEqual(blind.storyboard_artifact(projected),projected)
        self.assertEqual(read(self.project/'storyboard.json'),original)
        for absent in ['scope','exit','coordinate','basis','inserted_frames','media_or_navigation_retimed']:
            self.assertNotIn(absent,projected['navigation']['actual_timeline'])

    def test_storyboard_navigation_strips_nested_sources_goals_history_and_resource_paths(self):
        board=self.board();nav=board['navigation']=self.navigation();nav['source_notes']='NAV_SOURCE_PRIVATE'
        nav['actual_timeline']['metadata']=dict(original_materials='ORIGINAL_PRIVATE',goals='GOALS_PRIVATE',history='HISTORY_PRIVATE',path='work/PRIVATE.json')
        nav['actual_timeline']['section_title_windows'][0].update(source='WINDOW_SOURCE_PRIVATE',goals='WINDOW_GOAL_PRIVATE',history='WINDOW_HISTORY_PRIVATE',path='qa/WINDOW_PATH_PRIVATE.json')
        nav['toc']['sections'][0].update(source='TOC_SOURCE_PRIVATE',goals='TOC_GOAL_PRIVATE',history='TOC_HISTORY_PRIVATE',path='inputs/TOC_PATH_PRIVATE.pdf')
        nav['section_titles'][0].update(original='TITLE_ORIGINAL_PRIVATE',expected='TITLE_ANSWER_PRIVATE',receipt='TITLE_RECEIPT_PRIVATE')
        nav['progress_bar']['metadata']=dict(source='BAR_SOURCE_PRIVATE');nav['progress_bar']['hide_on'].append(dict(history='HIDE_HISTORY_PRIVATE'))
        nav['progress_bar']['position']='file:///tmp/POSITION_PATH_PRIVATE.pdf'
        nav['toc']['sections'].append(dict(unit_id='U2',label='inputs/LABEL_PATH_PRIVATE.pdf'))
        projected=blind.storyboard_artifact(board);serialized=json.dumps(projected,ensure_ascii=False)
        self.assertNotIn('PRIVATE',serialized);self.assertNotIn('position',projected['navigation']['progress_bar'])
        self.assertEqual(projected['navigation']['toc']['sections'],[dict(unit_id='U',label='合成章节')])
        self.assertEqual(projected['navigation']['actual_timeline']['section_title_windows'],[dict(unit_id='U',window=[150,180])])
        self.assertEqual(projected['navigation']['progress_bar']['hide_on'],['brand-intro','toc','chapter-title','outro'])

    def test_storyboard_navigation_visible_window_or_label_changes_artifact_hash(self):
        board=self.board();board['navigation']=self.navigation();baseline=hashed(blind.storyboard_artifact(board))
        window=copy.deepcopy(board);window['navigation']['actual_timeline']['section_title_windows'][0]['window'][1]=210
        label=copy.deepcopy(board);label['navigation']['toc']['sections'][0]['label']='合成新标题'
        visibility=copy.deepcopy(board);visibility['navigation']['progress_bar']['visible_until']='S2'
        for changed in [window,label,visibility]:self.assertNotEqual(hashed(blind.storyboard_artifact(changed)),baseline)

    def test_storyboard_navigation_private_metadata_changes_do_not_change_learner_artifact_hash(self):
        board=self.board();board['navigation']=self.navigation();baseline=hashed(blind.storyboard_artifact(board));changed=copy.deepcopy(board)
        changed['navigation']['timing_budget']='OTHER_PRODUCER_RULE_PRIVATE';changed['navigation']['brand_bookends']['intro']='inputs/OTHER_ORIGINAL_PRIVATE.mp4'
        changed['navigation']['actual_timeline'].update(basis='OTHER_SOURCE_PRIVATE',coordinate='OTHER_PRODUCER_HISTORY_PRIVATE',metadata=dict(goals='OTHER_GOAL_PRIVATE',history='OTHER_HISTORY_PRIVATE'))
        changed['navigation']['toc']['sections'][0]['source_path']='inputs/OTHER_SOURCE_PRIVATE.pdf'
        changed['navigation']['actual_timeline']['section_title_windows'][0]['source_materials']=['OTHER_ORIGINAL_PRIVATE']
        self.assertEqual(hashed(blind.storyboard_artifact(changed)),baseline)

    def test_storyboard_navigation_rejects_wrong_types_and_invalid_windows_without_inventing_defaults(self):
        board=self.board();nav=board['navigation']=self.navigation();clock=nav['actual_timeline']
        clock.update(fps=True,body=[False,810],toc_visible=[150,90],section_title_windows=[dict(unit_id='U',window=[150,901]),dict(unit_id=dict(source='PRIVATE'),window=[180,210])])
        nav['progress_bar'].update(visible_from=dict(source='PRIVATE'),visible_until=15,hide_on=[dict(history='PRIVATE')])
        projected=blind.storyboard_artifact(board)['navigation']
        self.assertEqual(projected['actual_timeline'],dict(total_frames=900))
        for field in ['visible_from','visible_until','hide_on','scope','exit']:self.assertNotIn(field,projected['progress_bar'])
        self.assertNotIn('PRIVATE',json.dumps(projected,ensure_ascii=False))

    def test_storyboard_navigation_references_locate_safe_labels_and_exact_frame_json(self):
        board=self.board();board['navigation']=self.navigation();projected=blind.storyboard_artifact(board)
        refs=[dict(method='storyboard_read',locator='input.storyboard.navigation.toc.sections[0].label',quote='合成章节'),
              dict(locator='input.storyboard.navigation.actual_timeline.section_title_windows[0].window',quote='[150,180]'),
              dict(locator='input.storyboard.navigation.actual_timeline.section_title_windows.0.window',quote='[150, 180]'),
              dict(locator='input.storyboard.navigation.actual_timeline.fps',quote='30')]
        for ref in refs:
            original=copy.deepcopy(ref)
            self.assertTrue(blind.storyboard_reference(ref,board));self.assertTrue(blind.storyboard_reference(ref,projected));self.assertEqual(ref,original)
        self.assertEqual(blind.storyboard_artifact(projected),projected)

    def test_storyboard_navigation_references_reject_sensitive_fake_or_mixed_locators(self):
        board=self.board();board['navigation']=self.navigation();valid=dict(method='storyboard_read',locator='input.storyboard.navigation.toc.sections[0].label',quote='合成章节')
        invalid=[dict(valid,quote=''),dict(valid,quote=' '),dict(valid,quote='不存在的标题'),dict(valid,locator='input.storyboard.navigation.actual_timeline.basis',quote='PRIVATE_SOURCE_BINDING'),
                 dict(valid,locator='input.storyboard.navigation.actual_timeline.section_title_windows[99].window'),
                 dict(valid,locator='input.storyboard.navigation.toc.sections[-1].label'),dict(valid,locator='input.storyboard.navigation.toc.sections[00].label'),
                 dict(valid,locator='input.storyboard.navigation.toc.sections[0].source'),dict(valid,locator='input.storyboard.navigation..toc.sections[0].label'),
                 dict(valid,locator='input.storyboard.navigation.segments[0].options[0].focus'),dict(valid,locator='input.storyboard.navigation_typo.toc.sections[0].label'),
                 dict(valid,segment_id='S1'),dict(valid,option_id='A'),dict(valid,time=1),dict(valid,beat='fake-beat'),dict(valid,sha256='fake-media'),dict(valid,method='source_and_script')]
        for ref in invalid:self.assertFalse(blind.storyboard_reference(ref,board),ref['locator'])
        self.assertFalse(blind.storyboard_reference(dict(valid,locator='input.storyboard.navigation.toc.sections['+'9'*5000+'].label'),board))

    def test_navigation_evidence_format_is_generic_and_only_changes_storyboard_contract(self):
        contract=blind.contract('storyboard');self.assertIn('input.storyboard.navigation.',contract['evidence_format'])
        self.assertIn('segment_id',contract['evidence_format']);self.assertIn('JSON',contract['evidence_format'])
        for stage in ['script','pilot','final']:self.assertNotIn('evidence_format',blind.contract(stage))

    def test_storyboard_pass_is_stable_across_downstream_render_work_without_fabricated_user_click(self):
        self.board();run=self.begin('storyboard',mode='continue');self.complete('storyboard',run,self.result('storyboard',run));self.review.finish('storyboard',run)
        self.assertFalse(gate_errors(self.course,'storyboard'));self.assertTrue(approved(self.course,'storyboard'))
        self.assertNotIn('approval',self.review.load()['nodes']['storyboard'])
        before=self.review.fingerprint('storyboard');doc=read(self.project/'workbench.json');doc['scenes']=[dict(id='new-scene')];atomic(self.project/'workbench.json',doc)
        (self.project/'native').mkdir();(self.project/'native/new-scene.js').write_text('export const visual=1;')
        self.assertEqual(before,self.review.fingerprint('storyboard'));self.assertTrue(self.review.node_view('storyboard')['passed'])
        self.movie('pilot');pilot=self.begin('pilot',mode='continue')
        self.assertTrue(self.review.node_view('pilot')['run']['repair_grant']['storyboard'])

    def test_storyboard_findings_need_real_quote_beat_or_time_in_exact_segment(self):
        self.board();run=self.begin('storyboard',mode='continue');result=self.report('storyboard',run)
        refs=[dict(segment_id='S1',quote='不存在的原句'),dict(segment_id='S1',beat='fake-beat'),dict(segment_id='S1',time=999)]
        wrong=copy.deepcopy(result);wrong['findings']=[dict(id='F'+str(i),problem='合成',evidence=[ref]) for i,ref in enumerate(refs)]
        value=self.send('storyboard',run,wrong);self.assertFalse(value['report']['passed'])
        for i,ref in enumerate(refs):
            item=next(v for v in value['report']['items'] if v['id']=='finding:F'+str(i))
            self.assertEqual(item['verdict'],'无法验证');self.assertTrue(item['critical']);self.assertEqual(item['evidence'],[ref])
        private=self.review.producer_packet('storyboard',run)['packet']
        self.assertEqual(private['blind_report']['findings'],wrong['findings']);self.assertFalse(private['blind_report']['passed'])

    def test_storyboard_producer_repair_saves_real_board_revision_backup_and_delegated_preflight(self):
        from test_storyboard_workflow import fixture as storyboard_fixture,choose_fixture_preferences
        from test_workbench import WorkbenchTests
        document_fixture=WorkbenchTests();document_fixture.setUp()
        try:
            for path in document_fixture.project.iterdir():
                if path.is_file():shutil.copy2(path,self.project/path.name)
        finally:document_fixture.tearDown()
        self.studio.save_sections([dict(unit_id='U',body=TEXT+'\n\n第二段：'+TEXT+'\n\n第三段：'+TEXT)],self.course.status()['revision'],self.studio.editor.read()['revision'],official=True)
        from source_coverage_fixture import confirm_fixture_coverage
        confirm_fixture_coverage(self.course)
        script=self.begin();self.complete('script',script,self.result('script',script));self.review.finish('script',script);self.review.approve('script',script)
        self.course.confirm('script',self.course.status()['revision'],'合成夹具明确内容确认',actor='qa-operator')
        self.course.select_branch('video',self.course.status()['revision'],'合成夹具已有视频制作委托',actor='qa-operator')
        self.course.enable_storyboard(self.course.status()['revision'],'合成夹具启用分镜',actor='qa-operator')
        choose_fixture_preferences(self.course)
        board=storyboard_fixture(self.course)
        for segment,paragraph in zip(board['segments'],read(self.course.plan_file)['script_mapping']['paragraphs']):segment['source_paragraph_ids']=[paragraph['id']]
        self.course.save_storyboard(board,self.course.status()['revision'])
        self.course.choose_shot('all','recommended',self.course.status()['revision'],'合成制作端选择',actor='qa-operator')
        run=self.begin('storyboard',mode='continue');private=self.review.producer_packet('storyboard',run)['packet'];before=(self.project/'storyboard.json').read_text();revision=read(self.course.state_file)['revision']
        result=self.result('storyboard',run,'需修改')
        target='"action": "执行有目的的对象变化 A"'
        # Only the first segment changes; exact CAS is unique in the whole file.
        unique='"opening": "准备对应对象 A",\n          '+target
        self.assertEqual(before.count(unique),3)
        old=board['segments'][0]['options'][0]['action'];replacement=old+'，先停稳核对，再把焦点移到实际结果'
        start=before.index(target)
        find=before[:start+len(target)]
        changed=find[:-len(target)]+target.replace(old,replacement)
        result['repairs']=[dict(issue_id='teaching-continuity',path='storyboard.json',before_sha256=private['editable_files'][0]['sha256'],find=find,replace=changed,reason='给首段动作添加可见过程和结果停稳')]
        self.complete('storyboard',run,result)
        with self.assertRaisesRegex(ValueError,'制作代理'):self.review.repair('storyboard',run,result['repairs'],'reviewer')
        applied=self.review.repair('storyboard',run,result['repairs'],PRODUCER['id'])
        self.assertFalse(applied['rerender']);self.assertIn(replacement,(self.project/'storyboard.json').read_text())
        self.assertIn(replacement,(self.project/'storyboard.html').read_text())
        self.assertEqual(read(self.course.state_file)['revision'],revision+1)
        self.assertEqual(read(self.course.state_file)['journal'][-1]['event'],'ai_review_storyboard_repaired')
        self.assertEqual((self.project/'qa/ai-review'/run/'repair-1/storyboard.json').read_text(),before)
        self.complete('storyboard',run,self.result('storyboard',run));finished=self.review.finish('storyboard',run)
        self.assertTrue(finished['continuation']['authorized']);self.assertFalse(finished['continuation']['requires_user_confirmation'])
        self.assertNotIn('approval',self.review.load()['nodes']['storyboard'])
        self.assertEqual(read(self.course.state_file)['gates']['storyboard']['actor'],'ai-production-preflight')
        self.assertTrue(self.course.status()['sampling_valid'])

    def test_media_capability_boundary_preserves_frame_findings_but_blocks_continuous_claims(self):
        self.movie('final');run=self.begin('final',mode='continue');result=self.report('final',run)
        value=self.send('final',run,result)['report']
        self.assertEqual(next(i for i in value['items'] if i['id']=='visual-composition')['verdict'],'通过')
        for identifier in ['continuous-av','ending','motion-pacing','dialogue-staging','visual-expression','technical-anomalies']:
            self.assertEqual(next(i for i in value['items'] if i['id']==identifier)['verdict'],'无法验证')
        self.assertNotIn('video',result['agent_audit']['artifact_ids']);self.assertFalse(value['passed'])

    def test_media_findings_reject_wrong_time_for_a_real_sent_frame(self):
        self.movie('final');run=self.begin('final',mode='continue');result=self.report('final',run)
        ref=copy.deepcopy(result['items'][0]['evidence'][0]);ref['time']=999999
        result['findings']=[dict(id='F1',problem='假时间定位',evidence=[ref])]
        with self.assertRaisesRegex(ValueError,'时间码'):self.send('final',run,result)

    def test_supervisor_failure_persists_hold_and_is_explicitly_blocked(self):
        run=self.begin();result=self.report('script',run);self.send('script',run,result)
        audit=self.audit('supervisor');self.recorded('script',run,audit)
        value=self.review.supervisor_submit('script',run,dict(binding=result['binding'],passed=False,findings=[dict(id='S1',problem='执行偏离用户指令',evidence=[dict(call_key='synthetic-call')])],summary='执行偏离用户指令',agent_audit=audit))
        self.assertTrue(value['blocked']);self.assertFalse(value['passed'])
        hold=Review(self.course).view()['hold'];self.assertTrue(hold['held']);self.assertEqual(hold['source'],'supervisor')
        with self.assertRaisesRegex(ValueError,'已暂停'):self.review.reserve_call('script',run,'after-supervisor-block',ROUTE)

    def test_formal_review_requires_distinct_supervision_and_private_source_qa(self):
        run=self.begin();result=self.report('script',run);value=self.send('script',run,result)
        self.assertIn('producer-source-qa',value['report']['blocking_ids']);self.assertIn('independent-supervision',value['report']['blocking_ids'])
        self.review.finish('script',run)
        with self.assertRaises(ValueError):self.review.require_pass('script',run)

    def test_execution_supervision_begins_before_review_and_preserves_shared_budget(self):
        operation='synthetic-production'
        value=self.review.production_event(PRODUCER,operation,'start','script',[dict(seq=1,time=1,type='turn/start',turn=1)])
        self.assertFalse(self.review.load()['nodes'].get('script',{}).get('runs'))
        packet=self.review.supervisor_packet(operation_id=operation)['packet']
        audit=self.audit('supervisor');key='supervision-call-1'
        self.review.reserve_supervision_call(operation,key,ROUTE)
        self.review.supervision_call_result(operation,key,dict(totalTokens=17),agent_audit=audit)
        result=dict(binding=packet['binding'],passed=True,findings=[],summary='监督实际生产开始与通道',agent_audit=audit)
        self.assertTrue(self.review.production_supervisor_submit(operation,result)['passed'])
        self.review.production_event(PRODUCER,operation,'progress','script',[dict(seq=2,time=2,type='request/header',route=ROUTE,tools=['read-only'])])
        with self.assertRaisesRegex(ValueError,'执行版本'):self.review.production_supervisor_submit(operation,result)
        self.review.production_event(PRODUCER,operation,'end','script',[dict(seq=3,time=3,type='turn/end',status='complete')])
        view=Review(self.course).view()['supervision'];self.assertEqual(view['calls'],1);self.assertEqual(view['usage']['totalTokens'],17)
        self.assertEqual(view['operations'][0]['phase'],'end');self.assertEqual(len(view['operations'][0]['events']),3)
        with self.assertRaises(ValueError):self.review.production_event(PRODUCER,'leaking-event','start','script',[dict(type='tool/call',body='PRIVATE_SOURCE')])
        with self.assertRaises(ValueError):self.review.production_event(PRODUCER,'nested-leaking-event','start','script',[dict(type='tool/call',tools=[dict(arguments='PRIVATE_SOURCE')])])

    def test_wrong_provider_or_billing_route_never_falls_back(self):
        with self.assertRaisesRegex(ValueError,'不能切换'):self.review.begin('script','wrong','continue',route=dict(provider='deepseek-account',model='anything'),producer=PRODUCER)
        self.assertEqual(STAGES,('script','storyboard','pilot','final'))

    def test_minimal_course_interface_still_enforces_canonical_dsh_state(self):
        project=self.root/'standalone-project';project.mkdir();minimal=SimpleNamespace(project=project)
        self.assertFalse(enabled(minimal))
        atomic(project/'course-state.json',dict(preferred_workbench='dsh'))
        self.assertTrue(enabled(minimal))
        atomic(project/'course-state.json',dict(preferred_workbench='standalone'))
        self.assertFalse(enabled(minimal))
        atomic(project/'ai-review.json',dict(schema='course-ai-review/1'))
        self.assertTrue(enabled(minimal))


if __name__=='__main__':unittest.main()
