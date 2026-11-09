"""Synthetic media only: responsibility split is not a listening receipt."""
import copy
import json
from unittest import mock
import unittest

import test_ai_review as fixtures
import test_blind_review as media_fixtures
from ai_review import Review, approved, gate_errors
import blind_review as blind
from workflow import Course, atomic, read, sha, now, hashed


class AudioArrangementTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    movie=media_fixtures.BlindReviewTests.movie

    def select(self):
        return self.review.set_review_arrangement(blind.USER_AUDIO_ARRANGEMENT,'PRIVATE_REAL_CHOICE 用户负责听轨',
            actor='user-chat-confirmation',source=dict(kind='chat',id='actual-question-id'))

    def ready_media(self, stage='pilot'):
        self.movie(stage)
        state=read(self.course.state_file);state[stage+'_context']=self.course._video_context(state);atomic(self.course.state_file,state)
        return self.begin(stage,request='media-'+stage,mode='continue')

    def reviewer_result(self, stage, run, sequence=True):
        packet=self.review.packet(stage,run)['packet'];frames=packet['evidence']['frames']
        refs=[dict(method='frames',sha256=f['sha256'],time=f['time']) for f in (frames if sequence else frames[:1])]
        refs.append(dict(method='media_probe',sha256=packet['artifact_sha256']))
        return dict(binding=packet['binding'],learner=dict(about='当前可见画面',what_it_said='只复述画面可见内容，不推断未听口播',learned=['可见核对关系'],confusions=[]),
                    findings=[],items=[dict(id=c['id'],verdict='通过',reason='仅为合成媒体契约测试',evidence=copy.deepcopy(refs)) for c in packet['checklist']],
                    inspected_frame_hashes=[f['sha256'] for f in frames],agent_audit=self.audit('reviewer',packet),summary='画面证据范围合成测试')

    def blind_submit(self, stage, run, result=None):
        result=result or self.reviewer_result(stage,run)
        self.recorded(stage,run,result['agent_audit'],result['inspected_frame_hashes'])
        return self.review.submit(stage,run,result)

    def complete(self, stage='pilot'):
        run=self.ready_media(stage);result=self.reviewer_result(stage,run)
        next(c for c in result['items'] if c['id']=='ending')['verdict']='不适用'
        self.blind_submit(stage,run,result)
        packet=self.review.producer_packet(stage,run)['packet']
        refs=[dict(quote=packet['input']['text'],source_id='S',source_quote=packet['evidence']['sources'][0]['text'],locator='正文')]
        refs.extend(dict(sha256=f['sha256'],time=f['time']) for f in packet['evidence']['frames'])
        refs.extend(dict(sha256=m['sha256']) for m in packet['evidence']['media'])
        agent=self.audit('producer');frames=[f['sha256'] for f in packet['evidence']['frames']]
        self.recorded(stage,run,agent,frames)
        producer_result=dict(binding=packet['binding'],agent_audit=agent,inspected_frame_hashes=frames,
            items=[dict(id=c['id'],verdict='通过',reason='合成来源、当前文字和实际画面依据',evidence=copy.deepcopy(refs)) for c in packet['checklist']],repairs=[],summary='合成制作端核验')
        next(c for c in producer_result['items'] if c['id']=='ending')['verdict']='不适用'
        self.review.producer_submit(stage,run,producer_result)
        agent=self.audit('supervisor');self.recorded(stage,run,agent)
        self.review.supervisor_submit(stage,run,dict(binding=packet['binding'],agent_audit=agent,passed=True,findings=[],summary='三个真实合成身份及职责隔离'))
        self.review.finish(stage,run)
        return run

    def declaration(self, stage='pilot', ok=True, complete=True):
        value=self.review.node_view(stage)['user_audio_review']
        return dict(artifact_sha256s=value['artifact_sha256s'],artifacts=value['artifacts'],coverage='all_stage_videos',
                    listened_completely=complete,audio_and_sync_ok=ok,evidence='已完整播放当前全部小样，声音与音画配合无问题' if ok else '尚有音轨问题',
                    source=dict(kind='ui',id='actual-click-id'),feedback='' if ok else '实际用户音轨反馈')

    def test_native_error_terminal_can_recover_without_relabelling_or_rewriting_history(self):
        state=self.review.load();state['hold']=dict(held=True,reason='synthetic safe hold',at=now())
        identifier='synthetic-native-terminal-error'
        old=dict(operation_id=identifier,producer=copy.deepcopy(fixtures.PRODUCER),phase='failure',stage='script',
                 events=[dict(phase='failure',stage='script',at=now(),execution=[dict(type='production/settled',failed=True)],event_sha256='0'*64)],
                 calls=[dict(key='old-supervision',role='supervisor',status='failed',usage={},usage_status='unknown')],reports=[],usage={})
        state.setdefault('supervision',{}).setdefault('operations',{})[identifier]=copy.deepcopy(old)
        atomic(self.review.path,state)
        with self.assertRaises(ValueError):self.select()
        fact=dict(type='production/historical-native-terminal',phase='failure',status='failed',kind='error',failed=True,
                  seq=100,turn=10,time=1794000000000,agent_id=fixtures.PRODUCER['id'],operation=identifier,
                  invocation_id=fixtures.PRODUCER['session_id']+':step:90',observed_at=now(),label='turn/end',
                  error='CODEX_APP_SERVER: synthetic initialize timeout')
        self.review.production_event(fixtures.PRODUCER,identifier,'failure','script',execution=[fact])
        current=self.review.load();operation=current['supervision']['operations'][identifier]
        self.assertEqual(operation['events'][:-1],old['events'])
        for key in ['calls','reports','usage']:self.assertEqual(operation[key],old[key])
        self.assertEqual(operation['phase'],'failure');self.assertFalse(self.review._operation_blocks_arrangement(operation,current))
        self.select();self.assertTrue(self.review.load()['hold']['held'])
        self.assertEqual(operation['events'][-1]['execution'][0]['status'],'failed')
        self.assertEqual(operation['events'][-1]['execution'][0]['kind'],'error')

    def test_native_error_receipt_still_rejects_nonterminal_or_mismatched_evidence(self):
        state=self.review.load();state['hold']=dict(held=True,reason='synthetic safe hold',at=now())
        identifier='synthetic-native-error-negative'
        fact=dict(type='production/historical-native-terminal',phase='failure',status='failed',kind='error',failed=True,
                  seq=100,turn=10,time=1794000000000,agent_id=fixtures.PRODUCER['id'],operation=identifier,
                  invocation_id=fixtures.PRODUCER['session_id']+':step:90',observed_at=now(),label='turn/end',
                  error='CODEX_APP_SERVER: synthetic initialize timeout')
        original=dict(operation_id=identifier,producer=copy.deepcopy(fixtures.PRODUCER),phase='failure',stage='script',
                      events=[dict(phase='failure',stage='script',at=now(),execution=[fact],
                                   event_sha256=hashed(dict(phase='failure',stage='script',execution=[fact])))])
        self.assertFalse(self.review._operation_blocks_arrangement(original,state))
        for change in ['tool-error','step-end','missing-end','wrong-status','wrong-kind','missing-error','empty-error','unverified-code',
                       'multiline-error','wrong-operation','wrong-producer','wrong-session','missing-seq','bad-time','bad-turn',
                       'future-step','not-failed','unheld','later-progress','tampered-digest']:
            with self.subTest(change=change):
                operation=copy.deepcopy(original);context=copy.deepcopy(state);event=operation['events'][-1];item=event['execution'][0]
                if change=='tool-error':item['type']='tool/result'
                elif change=='step-end':item['label']='step/end'
                elif change=='missing-end':item.pop('label')
                elif change=='wrong-status':item['status']='aborted'
                elif change=='wrong-kind':item['kind']='aborted'
                elif change=='missing-error':item.pop('error')
                elif change=='empty-error':item['error']=''
                elif change=='unverified-code':item['error']='TOOL_ERROR: synthetic failure'
                elif change=='multiline-error':item['error']='CODEX_APP_SERVER: first\nsecond'
                elif change=='wrong-operation':item['operation']='other-operation'
                elif change=='wrong-producer':item['agent_id']='other-producer'
                elif change=='wrong-session':item['invocation_id']='other-session:step:90'
                elif change=='missing-seq':item.pop('seq')
                elif change=='bad-time':item['time']=float('inf')
                elif change=='bad-turn':item['turn']=True
                elif change=='future-step':item['invocation_id']=fixtures.PRODUCER['session_id']+':step:999'
                elif change=='not-failed':item['failed']=False
                elif change=='unheld':context['hold']['held']=False
                elif change=='later-progress':event['execution'].append(dict(type='step/start',seq=101))
                if change=='tampered-digest':event['event_sha256']='f'*64
                else:event['event_sha256']=hashed(dict(phase=event['phase'],stage=event['stage'],execution=event['execution']))
                self.assertTrue(self.review._operation_blocks_arrangement(operation,context))

    def test_default_keeps_full_av_gate_and_capabilities_cannot_be_invented(self):
        run=self.ready_media();result=self.reviewer_result('pilot',run)
        packet=self.review.packet('pilot',run)['packet']
        self.assertEqual(packet['review_contract'],blind.contract('pilot'))
        self.assertTrue(any(c['required_method']=='full_av' for c in packet['checklist']))
        # One actual simulated review call supports both structural validations;
        # rejecting a forged capability must not create a second review.
        self.recorded('pilot',run,result['agent_audit'],result['inspected_frame_hashes'])
        bad=copy.deepcopy(result);bad['agent_audit']['capabilities'].append('full_av')
        with self.assertRaises(ValueError):self.review.submit('pilot',run,bad)
        self.review.submit('pilot',run,result)
        report=self.review.node_view('pilot')['run']['blind_report']
        self.assertFalse(report['passed']);self.assertEqual(next(c for c in report['items'] if c['id']=='continuous-av')['verdict'],'无法验证')
        self.assertFalse(self.review.node_view('pilot')['user_audio_review']['required'])

    def test_explicit_choice_is_private_and_does_not_create_listening_or_approval(self):
        self.select();run=self.ready_media();packet=self.review.packet('pilot',run)['packet']
        encoded=json.dumps(packet,ensure_ascii=False)
        self.assertNotIn('PRIVATE_REAL_CHOICE',encoded);self.assertNotIn('actual-question-id',encoded);self.assertNotIn(fixtures.TEXT,encoded)
        self.assertEqual(packet['review_contract']['responsibilities']['mode'],blind.USER_AUDIO_ARRANGEMENT)
        self.assertIs(packet['review_contract']['responsibilities']['full_av'],False)
        self.assertEqual(packet['review_contract']['capabilities'],['text','images'])
        self.assertFalse(any(c['required_method']=='full_av' for c in packet['checklist']))
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'pending')
        private=self.review.producer_packet('pilot',run)['packet']
        self.assertIn('PRIVATE_REAL_CHOICE',private['review_arrangement']['evidence'])
        self.assertIn('source-accuracy',[c['id'] for c in private['checklist']])
        self.assertFalse(self.review.node_view('pilot')['user_confirmed'])
        self.assertNotIn('review_arrangement',self.review.basis('script'))

    def test_three_roles_pass_ai_scope_but_audio_items_stay_pending_until_real_listening(self):
        self.select();run=self.complete();node=self.review.node_view('pilot')
        self.assertTrue(node['passed']);self.assertFalse(node['user_confirmed']);self.assertTrue(gate_errors(self.course,'pilot'))
        self.assertFalse(approved(self.course,'pilot'))
        with self.assertRaisesRegex(ValueError,'完整播放'):self.review.approve('pilot',run)
        with self.assertRaisesRegex(ValueError,'完整播放'):self.studio.confirm('pilot',read(self.course.state_file)['revision'])
        report=node['run']['report'];self.assertNotIn('full_av',report['methods'])
        self.assertIs(report['responsibilities']['full_av'],False)
        self.assertTrue(all(c['verdict']=='待用户听审' for c in report['items'] if c.get('responsibility')=='user_audio'))
        entry=node['run']['iterations'][-1]
        for raw in [entry['raw_result'],entry['raw_producer_result']]:
            self.assertEqual(next(c for c in raw['items'] if c['id']=='continuous-av')['verdict'],'通过')
            self.assertEqual(next(c for c in raw['items'] if c['id']=='ending')['verdict'],'不适用')
        stored=read(self.project/'qa/ai-review'/run/'00/report.json')
        self.assertEqual(stored['raw_result'],entry['raw_result']);self.assertEqual(stored['raw_producer_result'],entry['raw_producer_result'])
        supervisor=self.review.supervisor_packet('pilot',run)['packet']
        self.assertEqual(supervisor['review_arrangement']['source']['id'],'actual-question-id')
        self.assertEqual(supervisor['user_audio_review']['status'],'pending')
        self.review.record_user_audio_review('pilot',**self.declaration())
        self.assertFalse(approved(self.course,'pilot'))  # Listening alone is not content approval.
        self.review.approve('pilot',run)
        self.assertTrue(approved(self.course,'pilot'));self.assertFalse(gate_errors(self.course,'pilot'))

    def test_non_audio_unknown_and_insufficient_frame_sequence_still_block(self):
        self.select();run=self.ready_media();result=self.reviewer_result('pilot',run,sequence=False)
        self.blind_submit('pilot',run,result);report=self.review.node_view('pilot')['run']['blind_report']
        self.assertFalse(report['passed'])
        self.assertIn('motion-pacing',report['blocking_ids']);self.assertIn('technical-anomalies',report['blocking_ids'])
        self.assertNotIn('continuous-av',report['blocking_ids'])

    def test_every_current_video_and_complete_range_are_required_and_cannot_transfer(self):
        self.select();self.movie('pilot');self.movie('final','red')
        state=read(self.course.state_file);state['artifacts']['pilot'].extend(state['artifacts']['final']);atomic(self.course.state_file,state)
        declaration=self.declaration();self.assertEqual(len(declaration['artifacts']),2)
        for wrong in [dict(declaration,artifact_sha256s=declaration['artifact_sha256s'][:1],artifacts=declaration['artifacts'][:1]),
                      dict(declaration,artifact_sha256s=[declaration['artifact_sha256s'][0]]*2,artifacts=[declaration['artifacts'][0]]*2),
                      dict(declaration,artifacts=[dict(a,end_seconds=a['end_seconds']/2) for a in declaration['artifacts']]),
                      dict(declaration,artifacts=[dict(a,end_seconds=float('nan')) for a in declaration['artifacts']]),
                      dict(declaration,artifacts=[dict(a,end_seconds=float('inf')) for a in declaration['artifacts']]),
                      dict(declaration,coverage='one_clip')]:
            with self.assertRaises(ValueError):self.review.record_user_audio_review('pilot',**wrong)
        self.review.record_user_audio_review('pilot',**declaration)
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'confirmed')
        target=self.course.relative(state['artifacts']['pilot'][0]);target.write_bytes(target.read_bytes()+b'changed bytes')
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'stale')
        with self.assertRaises(ValueError):self.review.record_user_audio_review('final',**declaration)

    def test_feedback_and_producer_identity_never_become_user_confirmation(self):
        self.select();run=self.complete();declaration=self.declaration(ok=False)
        self.review.record_user_audio_review('pilot',**declaration)
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'issues_reported')
        with self.assertRaises(ValueError):self.review.approve('pilot',run)
        with self.assertRaisesRegex(ValueError,'反馈'):self.review.record_user_audio_review('pilot',**dict(self.declaration(),feedback='末句截断'))
        for actor,source in [('producer',dict(kind='chat',id='forged')),('dsh-user-click',dict(kind='chat',id='wrong-origin'))]:
            with self.assertRaises(ValueError):self.review.record_user_audio_review('pilot',**dict(self.declaration(),source=source),actor=actor)
            with self.assertRaises(ValueError):self.review.set_review_arrangement(blind.USER_AUDIO_ARRANGEMENT,'自报',actor,source)
        state=self.review.load();state['nodes']['pilot']['user_audio_reviews'][-1]['actor']='producer';atomic(self.review.path,state)
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'invalid')

    def test_one_existing_studio_confirmation_can_record_both_without_extra_approval(self):
        self.select();run=self.complete();revision=read(self.course.state_file)['revision'];declaration=self.declaration()
        # Other production-readiness checks are outside this synthetic confirmation test.
        # The real Studio action, receipt validation and Review.approve remain unmocked.
        with mock.patch.object(Course,'confirm',return_value={}) as confirm:
            self.studio.action('review-approve',dict(stage='pilot',run_id=run,baseRevision=revision,audio_declaration=declaration))
        self.assertEqual(confirm.call_count,1)
        node=self.review.node_view('pilot');self.assertTrue(node['user_confirmed']);self.assertEqual(node['user_audio_review']['status'],'confirmed')
        self.assertEqual(len(self.review.load()['nodes']['pilot']['user_audio_reviews']),1)
        old_calls=node['calls'];self.review.ui('pilot',run,'dismiss')
        self.assertEqual(self.review.node_view('pilot')['calls'],old_calls)
        self.studio.feedback(dict(stage='pilot',time=0,text='当前媒体仍有声音问题',baseRevision=read(self.course.state_file)['revision']))
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['status'],'issues_reported')
        self.assertFalse(approved(self.course,'pilot'))
        with self.assertRaisesRegex(ValueError,'覆盖'):self.review.record_user_audio_review('pilot',**self.declaration())
        feedback=read(self.studio.feedback_file)[-1]
        self.assertEqual(feedback['artifact_sha256s'],declaration['artifact_sha256s'])
        self.assertEqual(self.review.node_view('pilot')['user_audio_review']['feedback'][0]['id'],feedback['id'])
        self.movie('pilot','red')
        self.assertNotEqual(self.review.node_view('pilot')['user_audio_review']['status'],'issues_reported')

    def test_selection_and_receipts_preserve_history_usage_and_do_not_expose_llm_confirm_tool(self):
        run=self.begin();self.review.reserve_call('script',run,'unfinished',fixtures.ROUTE)
        with self.assertRaisesRegex(ValueError,'未结算'):self.select()
        self.review.call_result('script',run,'unfinished',error='synthetic failure',execution_phase='unknown',model_invoked=None)
        self.review.finish('script',run,error='synthetic failure');before=copy.deepcopy(self.review.load()['nodes'])
        self.select();self.review.set_review_arrangement(blind.DEFAULT_ARRANGEMENT,'恢复原职责',source=dict(kind='ui',id='restore-click'))
        after=self.review.load();self.assertEqual(after['nodes'],before);self.assertEqual(len(after['review_arrangement_history']),2)
        state=self.review.load();state.setdefault('supervision',{}).setdefault('operations',{})['active-production']=dict(phase='progress',calls=[]);atomic(self.review.path,state)
        with self.assertRaisesRegex(ValueError,'安全停止'):self.select()
        tools=json.loads((fixtures.ROOT/'plugin/tools.json').read_text())
        self.assertFalse(any(t['name'] in ['review_arrangement','user_audio_review','kgxc_course_confirm'] for t in tools))

    def test_held_historical_supervision_block_is_preserved_but_active_or_unsettled_operation_rejects(self):
        # Actual 125 shape: progress phase was preserved after the independent
        # supervisor blocked execution; the current report/call is settled.
        audit=self.audit('supervisor');binding=dict(protocol='course-execution-supervision/1',execution_sha256='a'*64)
        report=dict(passed=False,binding=binding,agent_audit=audit,at='2026-11-08T06:38:56+08:00')
        operation=dict(operation_id='synthetic-held-history',phase='progress',producer=fixtures.PRODUCER,binding=binding,report=report,reports=[report],
                       calls=[dict(key='supervision-progress-6',role='supervisor',status='complete',agent_audit=audit,usage={})],events=[])
        state=self.review.load();state.update(route=fixtures.ROUTE,hold=dict(held=True,reason='已有真实监督阻断'))
        state['supervision']=dict(operations={operation['operation_id']:copy.deepcopy(operation)})
        atomic(self.review.path,state);before=copy.deepcopy(state['supervision'])
        self.select();self.assertEqual(self.review.load()['supervision'],before);self.assertTrue(self.review.load()['hold']['held'])
        for changed in ['unheld','no-report','stale-binding','unsettled','reserved','unverified-agent','not-current-history']:
            with self.subTest(changed=changed):
                candidate=copy.deepcopy(state);op=candidate['supervision']['operations'][operation['operation_id']]
                if changed=='unheld':candidate['hold']['held']=False
                elif changed=='no-report':op.pop('report')
                elif changed=='stale-binding':op['binding']=dict(binding,execution_sha256='b'*64)
                elif changed=='unsettled':op['calls'][0]['status']='failed'
                elif changed=='reserved':op['calls'][0]['status']='reserved'
                elif changed=='unverified-agent':op['report']['agent_audit']['invocation_ids']=[]
                else:op['reports']=[]
                atomic(self.review.path,candidate)
                with self.assertRaises(ValueError):self.select()
        # Three older operations had no accepted supervisor report. Never infer
        # inactivity from a hold/zero reservations: append the real terminal
        # readback through the existing API (synthetic native metadata here).
        candidate=copy.deepcopy(state);historical={}
        for number in range(3):
            identifier='synthetic-old-progress-'+str(number)
            item=dict(operation_id=identifier,producer=copy.deepcopy(fixtures.PRODUCER),phase='progress',stage='script',
                      events=[dict(phase='start',at='2026-11-08T04:00:00+08:00',execution=[],event_sha256='0'*64),
                              dict(phase='progress',at='2026-11-08T04:01:00+08:00',execution=[],event_sha256='1'*64)],
                      calls=[dict(key='old-supervision',role='supervisor',status='failed',usage={},usage_status='unknown')],reports=[],usage={})
            historical[identifier]=copy.deepcopy(item);candidate['supervision']['operations'][identifier]=item
        atomic(self.review.path,candidate);nodes_before=copy.deepcopy(candidate['nodes'])
        with self.assertRaises(ValueError):self.select()
        for number,(identifier,old) in enumerate(historical.items()):
            fact=dict(type='production/historical-native-terminal',phase='failure',status='aborted',kind='aborted',failed=True,
                seq=100+number,turn=10+number,time=1794000000000+number,agent_id=fixtures.PRODUCER['id'],operation=identifier,
                invocation_id=fixtures.PRODUCER['session_id']+':step:'+str(90+number),observed_at=now(),label='合成owned原生终态回证',error='合成用户中止')
            self.review.production_event(fixtures.PRODUCER,identifier,'failure','script',execution=[fact])
            current=self.review.load()['supervision']['operations'][identifier]
            self.assertEqual(current['events'][:-1],old['events'])
            for key in ['calls','reports','usage']:self.assertEqual(current[key],old[key])
            self.assertEqual(current['phase'],'failure')
            if number<2:
                with self.assertRaises(ValueError):self.select()
        self.select();recovered=self.review.load()
        self.assertTrue(recovered['hold']['held']);self.assertEqual(recovered['nodes'],nodes_before)
        self.assertEqual(recovered['supervision']['operations'][operation['operation_id']],state['supervision']['operations'][operation['operation_id']])
        terminal=copy.deepcopy(recovered['supervision']['operations'][next(iter(historical))])
        self.assertFalse(self.review._operation_blocks_arrangement(terminal,recovered))
        for changed in ['recoverable-error','no-terminal','missing-seq','wrong-operation','wrong-producer','wrong-session','wrong-phase','not-aborted','not-failed','bad-time','bad-turn','future-step','unheld','later-progress','tampered-digest']:
            with self.subTest(terminal_change=changed):
                invalid=copy.deepcopy(terminal);last=invalid['events'][-1];fact=last['execution'][0];context=copy.deepcopy(recovered)
                if changed=='recoverable-error':fact.update(type='tool/result',failed=True,status='failed')
                elif changed=='no-terminal':last['execution']=[]
                elif changed=='missing-seq':fact.pop('seq')
                elif changed=='wrong-operation':fact['operation']='other-operation'
                elif changed=='wrong-producer':fact['agent_id']='other-producer'
                elif changed=='wrong-session':fact['invocation_id']='other-session:step:90'
                elif changed=='wrong-phase':fact['phase']='progress'
                elif changed=='not-aborted':fact['status']='steered'
                elif changed=='not-failed':fact['failed']=False
                elif changed=='bad-time':fact['time']=float('inf')
                elif changed=='bad-turn':fact['turn']=True
                elif changed=='future-step':fact['invocation_id']=fixtures.PRODUCER['session_id']+':step:999'
                elif changed=='unheld':context['hold']['held']=False
                elif changed=='later-progress':last['execution']=[dict(type='step/start',seq=999)]
                if changed!='tampered-digest':last['event_sha256']=hashed(dict(phase=last['phase'],stage=last['stage'],execution=last['execution']))
                else:last['event_sha256']='f'*64
                self.assertTrue(self.review._operation_blocks_arrangement(invalid,context))


if __name__=='__main__':unittest.main()
