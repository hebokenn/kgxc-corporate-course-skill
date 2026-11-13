"""Stage applicability and bounded source-QA evidence; synthetic inputs only."""
import copy
import json
import unittest

import test_ai_review as fixtures
from ai_review import Review, STAGES
from workflow import atomic, read, hashed


class ReviewRequirementScopeTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    def register(self):
        texts=['隔离规则：每阶段只提供当前成果','【逐字稿阶段】只审阅当前逐字稿','【分镜阶段】核验当前分镜执行','【有声小样和全片阶段】核验实际媒体执行','只挑毛病，不直接返修','保留预算、历史与继续制作委托']
        self.review.requirements(texts,'合成夹具用户原话')
        return copy.deepcopy(self.review.load()['requirements'])

    def migrate(self, requirements):
        stages=[list(STAGES),['script'],['storyboard'],['pilot','final'],list(STAGES),list(STAGES)]
        updates=[dict(id=r['id'],scope='execution',stages=s) for r,s in zip(requirements,stages)]
        self.review.requirements(updates,'合成夹具显式确认适用阶段与执行职责')
        return updates

    def test_id_migration_preserves_original_text_evidence_history_reports_and_budgets(self):
        original=self.register();run=self.begin();self.complete('script',run,self.result('script',run));self.review.finish('script',run)
        state=self.review.load();node=state['nodes']['script'];node.update(calls=11,usage={'totalTokens':603513},repairs=1)
        atomic(self.review.path,state);frozen=copy.deepcopy(node);authorizations=copy.deepcopy(state['authorizations'])
        updates=self.migrate(original);after=self.review.load()
        self.assertEqual(after['nodes']['script'],frozen);self.assertEqual(after['authorizations'],authorizations)
        for prior,current,update in zip(original,after['requirements'],updates):
            self.assertEqual({k:current[k] for k in prior},prior)
            self.assertEqual(current['scope'],'execution');self.assertEqual(current['stages'],update['stages'])
            self.assertEqual(current['applicability_history'][0]['before'],dict(scope='content',stages=list(STAGES)))
        once=copy.deepcopy(after['requirements']);self.review.requirements(updates,'重复同一适用性确认不得另建历史')
        self.assertEqual(self.review.load()['requirements'],once)

    def test_unknown_ids_fields_scopes_and_stages_fail_atomically(self):
        requirement=self.register()[0];valid=dict(id=requirement['id'],scope='execution',stages=list(STAGES));before=self.review.path.read_bytes()
        invalid=[dict(valid,id='REQ-unknown'),dict(valid,scope='other'),dict(valid,stages=[]),dict(valid,stages=['later']),dict(valid,stages='all'),dict(valid,stages=['script','script']),dict(valid,text='不能重写原要求'),dict(valid,from_stage='pilot')]
        for bad in invalid:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):self.review.requirements([valid,bad],'合成适用性修改')
                self.assertEqual(self.review.path.read_bytes(),before)

    def test_legacy_strings_and_from_stage_keep_compatibility_without_text_inference(self):
        values=self.register();self.assertIn(values[2]['id'],{r['id'] for r in self.review.requirements_for('script')})
        state=self.review.load();state['requirements'][2]['from_stage']='storyboard';atomic(self.review.path,state)
        self.assertNotIn(values[2]['id'],{r['id'] for r in self.review.requirements_for('script')})
        for stage in ['storyboard','pilot','final']:self.assertIn(values[2]['id'],{r['id'] for r in self.review.requirements_for(stage)})
        self.assertEqual(self.review.requirements_for('script','execution'),[])

    def test_content_stage_selection_and_execution_split_preserve_fixed_checks(self):
        original=self.register();before={s:{c['id'] for c in self.review.checklist(s) if not c['id'].startswith('REQ-')} for s in STAGES}
        self.migrate(original)
        self.review.requirements([dict(id=original[2]['id'],scope='content',stages=['storyboard'])],'合成夹具：该项明确改为分镜内容要求')
        for stage in STAGES:
            checks=self.review.checklist(stage);ids={c['id'] for c in checks}
            self.assertEqual({i for i in ids if not i.startswith('REQ-')},before[stage])
            self.assertEqual(original[2]['id'] in ids,stage=='storyboard')
            self.assertTrue({r['id'] for r in original if r['id']!=original[2]['id']}.isdisjoint(ids))
        self.assertIn('source-accuracy',before['script']);self.assertIn('objective:O',before['script'])
        self.assertTrue({'continuous-av','ending','duration','media-binding'}.issubset(before['final']))

    def test_supervision_keeps_all_requirements_and_defers_future_stages_without_leaking_to_blind(self):
        original=self.register();self.migrate(original)
        operation='scope-execution';self.review.production_event(fixtures.PRODUCER,operation,'start','script',[])
        packet=self.review.supervisor_packet(operation_id=operation)['packet']
        current={r['id'] for r in packet['current_requirements']};deferred={r['id'] for r in packet['deferred_requirements']}
        self.assertEqual(len(packet['requirements']),6);self.assertEqual(current,{original[i]['id'] for i in [0,1,4,5]})
        self.assertEqual(deferred,{original[i]['id'] for i in [2,3]})
        self.assertIn('不取消其后续义务',packet['requirement_applicability'])
        run=self.begin();blind=self.review.packet('script',run)['packet'];serialized=json.dumps(blind,ensure_ascii=False)
        for r in original:self.assertNotIn(r['text'],serialized)
        self.review.production_event(fixtures.PRODUCER,operation,'progress','storyboard',[])
        later=self.review.supervisor_packet(operation_id=operation)['packet']
        self.assertIn(original[2]['id'],{r['id'] for r in later['current_requirements']})
        self.assertIn(original[3]['id'],{r['id'] for r in later['deferred_requirements']})
        self.assertEqual({r['id'] for r in later['requirements']},{r['id'] for r in original})

    def test_source_quote_paraphrase_remains_blocked_with_bounded_normalized_metadata(self):
        self.migrate(self.register());run=self.begin();result=self.result('script',run)
        result['items'][0]['evidence'][0]['source_quote']='概述或拼接不等于原件逐字引文'
        self.complete('script',run,result);packet=self.review.supervisor_packet('script',run)['packet']
        report=self.review.node_view('script')['run']['producer_report'];meta=packet['producer_result']
        source=next(i for i in meta['items'] if i['id']=='source-accuracy')
        self.assertEqual(source['verdict'],'无法验证');self.assertFalse(meta['passed'])
        self.assertEqual(source['evidence_validation']['source_quotes_checked'],1);self.assertEqual(source['evidence_validation']['source_quotes_matched'],0)
        self.assertEqual(meta['report_sha256'],hashed(report));self.assertEqual(meta['inspection']['source_count'],1)
        self.assertIsNotNone(meta['inspection']['sources'][0]['sha256']);self.assertFalse(meta['inspection']['sources'][0]['truncated'])
        self.assertEqual(packet['next_action']['kind'],'blocked');self.assertFalse(packet['next_action']['content_block_is_execution_failure'])
        raw=json.dumps(meta,ensure_ascii=False)
        self.assertNotIn(self.review.script_input()['text'],raw);self.assertNotIn('概述或拼接不等于原件逐字引文',raw)
        self.assertNotIn('先核对订单，再核对编码。',raw);self.assertNotIn('source_quote":',raw)
        original_id=self.review.load()['requirements'][0]['id']
        self.assertTrue(source['quote_hashes']);self.assertIn(original_id,{r['id'] for r in packet['requirements']})
        self.assertIn(original_id,{r['id'] for r in packet['current_requirements']})

    def test_script_quote_summary_or_concatenation_is_still_rejected(self):
        run=self.begin();result=self.result('script',run)
        item=next(i for i in result['items'] if i['id']=='teaching-continuity');item['evidence'][0]['quote']='核对订单以及编码后再交接的总结'
        report=self.complete('script',run,result)['report'];normalized=next(i for i in report['producer_qa']['items'] if i['id']=='teaching-continuity')
        self.assertEqual(normalized['verdict'],'无法验证');self.assertEqual(normalized['evidence_validation']['script_quotes_matched'],0)

    def test_supervisor_sees_repair_plan_instead_of_mistaking_content_findings_for_release(self):
        run=self.begin();private=self.review.producer_packet('script',run)['packet'];result=self.result('script',run,'需修改')
        result['repairs']=[dict(issue_id='teaching-continuity',path='source/transcript.md',before_sha256=private['editable_files'][0]['sha256'],find='先核对订单',replace='先核对订单日期',reason='合成局部问题')]
        self.complete('script',run,result);packet=self.review.supervisor_packet('script',run)['packet']
        self.assertEqual(packet['next_action']['kind'],'repair');self.assertFalse(packet['producer_result']['passed'])
        self.assertFalse(packet['next_action']['course_release_authorized']);self.assertFalse(packet['next_action']['stage_advance_authorized'])
        self.assertIn('有阻断',packet['next_action']['reason']);self.assertIn('集中修复后按固定问题清单定向验收',packet['next_action']['reason'])
        self.assertIn('不再盲审',packet['next_action']['reason']);self.assertNotIn('repairs',packet)
        self.assertEqual(packet['current_run']['id'],run);self.assertEqual(packet['current_run']['route'],fixtures.ROUTE)
        self.assertIsNotNone(packet['current_run']['started_at']);self.assertEqual(packet['budget']['calls_used'],3)
        self.assertIn('未附入包的历史安装',packet['supervision_scope'])
        state=self.review.load();state['nodes']['script']['calls']=12;atomic(self.review.path,state)
        self.assertEqual(self.review.supervisor_packet('script',run)['packet']['next_action']['kind'],'blocked')

    def test_old_metadata_missing_validation_counts_stays_unrecorded_and_is_bounded(self):
        old=dict(passed=False,summary='摘要'*1000,blocking_ids=['source-accuracy'],methods=['script_read'],items=[dict(id='source-accuracy',label='原件依据',required_method='source_and_script',verdict='无法验证',reason='原因'*1000,evidence=[dict(quote='SCRIPT_FULL_BODY_PRIVATE',source_quote='SOURCE_FULL_BODY_PRIVATE')])],inspection=dict(sources=[dict(id='S',sha256='a'*64,error='读取未完成',truncated=True)]))
        frozen=copy.deepcopy(old);meta=self.review._producer_result_metadata(old)
        self.assertEqual(old,frozen);self.assertFalse(meta['passed']);self.assertEqual(meta['items'][0]['verdict'],'无法验证')
        self.assertEqual(meta['items'][0]['evidence_validation'],dict(status='not_recorded'));self.assertEqual(meta['items'][0]['evidence_count'],1)
        self.assertEqual(meta['inspection']['sources'][0]['error'],'读取未完成');self.assertTrue(meta['inspection']['sources'][0]['truncated'])
        self.assertLessEqual(len(meta['summary']),1200);self.assertLessEqual(len(meta['items'][0]['reason']),400)
        serialized=json.dumps(meta,ensure_ascii=False);self.assertNotIn('SCRIPT_FULL_BODY_PRIVATE',serialized);self.assertNotIn('SOURCE_FULL_BODY_PRIVATE',serialized)

    def test_budget_extension_records_real_chat_confirmation_without_resetting_usage(self):
        run=self.begin();state=self.review.load();node=state['nodes']['script'];node.update(calls=11,repairs=1,usage={'totalTokens':603513});atomic(self.review.path,state)
        self.review.extend('script',0,6,'合成夹具用户明确同意追加六次调用',actor='user-chat-confirmation')
        state=self.review.load();node=state['nodes']['script']
        self.assertEqual(node['calls'],11);self.assertEqual(node['repairs'],1);self.assertEqual(node['usage'],{'totalTokens':603513})
        self.assertEqual(node['policy']['max_calls'],18);self.assertEqual(state['authorizations'][-1]['actor'],'user-chat-confirmation')
        self.assertEqual(state['authorizations'][-1]['evidence'],'合成夹具用户明确同意追加六次调用')
        before=self.review.path.read_bytes()
        with self.assertRaises(ValueError):self.review.extend('script',0,1,'不得冒充制作授权',actor='producer')
        self.assertEqual(self.review.path.read_bytes(),before)
        self.review.extend('script',0,1,'合成真实UI确认');self.assertEqual(self.review.load()['authorizations'][-1]['actor'],'dsh-user-click')


if __name__=='__main__':unittest.main()
