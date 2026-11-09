"""One-course, explicit execution-only policy migration; no source files are edited."""
import copy
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

import test_ai_review as fixtures
import ai_review
from ai_review import Review
import blind_review as blind
from workflow import atomic, read, hashed

OLD='a'*64
NEW='c'*64
BOUNDARY='b'*64


class ReviewPolicyCompatibilityTests(unittest.TestCase):
    setUp=fixtures.AIReviewTests.setUp
    tearDown=fixtures.AIReviewTests.tearDown
    begin=fixtures.AIReviewTests.begin
    audit=fixtures.AIReviewTests.audit
    recorded=fixtures.AIReviewTests.recorded
    result=fixtures.AIReviewTests.result
    complete=fixtures.AIReviewTests.submit

    @contextmanager
    def code(self,backend,boundary=BOUNDARY):
        actual_sha=ai_review.sha
        def digest(path):
            if Path(path)==Path(ai_review.__file__):return backend
            if Path(path)==Path(blind.__file__):return boundary
            return actual_sha(path)
        with patch('ai_review.sha',side_effect=digest):yield

    def passing_old(self):
        with self.code(OLD):
            run=self.begin();self.complete('script',run,self.result('script',run));self.review.finish('script',run)
            self.review.approve('script',run)
            self.assertTrue(self.review.node_view('script')['passed'])
            return run,self.review.fingerprint('script')

    def preserve(self):return self.review.preserve_policy_for_execution_update(OLD,BOUNDARY,'合成维护依据：已核对仅执行次数与显示变化，保留源码差异及测试记录')

    def test_source_change_without_explicit_course_migration_remains_fail_closed(self):
        run,previous=self.passing_old();before=copy.deepcopy(self.review.load()['nodes'])
        with self.code(NEW):
            current=self.review.node_view('script')
            self.assertNotEqual(current['fingerprint'],previous);self.assertFalse(current['passed']);self.assertEqual(current['status'],'stale')
            self.assertEqual(self.review.load()['nodes'],before);self.assertNotIn('execution_policy_compatibility',self.review.load())

    def test_explicit_execution_update_preserves_binding_reports_usage_and_confirmation(self):
        run,previous=self.passing_old();summary=self.project/'qa/ai-review'/run/'summary.json';summary_bytes=summary.read_bytes()
        self.review.set_unlimited_counts(True,'合成用户明确授权当前课临时取消次数限制',actor='user-chat-confirmation')
        before=self.review.load();nodes=copy.deepcopy(before['nodes']);policy=copy.deepcopy(before['policy']);authorizations=copy.deepcopy(before['authorizations'])
        with self.code(NEW):
            self.assertFalse(self.review.node_view('script')['passed'])
            view=self.preserve();state=self.review.load();compat=state['execution_policy_compatibility']
            self.assertTrue(view['nodes']['script']['passed']);self.assertTrue(view['nodes']['script']['user_confirmed'])
            self.assertEqual(view['nodes']['script']['fingerprint'],previous);self.assertEqual(state['nodes'],nodes)
            self.assertEqual(state['policy'],policy);self.assertEqual(state['authorizations'],authorizations);self.assertEqual(summary.read_bytes(),summary_bytes)
            self.assertEqual(compat['from_backend_sha256'],OLD);self.assertEqual(compat['to_backend_sha256'],NEW);self.assertEqual(compat['boundary_sha256'],BOUNDARY)
            self.assertEqual(compat['old_policy_sha256'],hashed(dict(protocol=blind.PROTOCOL,backend=OLD,boundary=BOUNDARY)))
            self.assertEqual(compat['passed_run_ids'],[run]);self.assertEqual(compat['actor'],'codex-maintenance')
            self.assertEqual(state['execution_policy_compatibility_history'],[compat])
        # This record is scoped to this project, never a module-global default.
        other_root=self.root/'other';atomic(other_root/'project/workbench.json',dict(title='合成另一课',scenes=[],media={}))
        other=fixtures.Course(other_root);other.init('合成另一课')
        with self.code(NEW):self.assertEqual(Review(other).basis('script')['review_policy_sha256'],hashed(dict(protocol=blind.PROTOCOL,backend=NEW,boundary=BOUNDARY)))

    def test_tampered_source_boundary_policy_or_baseline_binding_invalidates_compatibility(self):
        self.passing_old()
        with self.code(NEW):self.preserve()
        baseline=copy.deepcopy(self.review.load())
        for key,value in [('to_backend_sha256','d'*64),('boundary_sha256','d'*64),('old_policy_sha256','d'*64),('from_backend_sha256','d'*64),('from_backend_sha256',None),('passed_run_ids',['unknown']),('actor','other')]:
            with self.subTest(key=key):
                state=copy.deepcopy(baseline);state['execution_policy_compatibility'][key]=value;atomic(self.review.path,state)
                with self.code(NEW):self.assertFalse(self.review.node_view('script')['passed'])
        atomic(self.review.path,baseline)
        with self.code('e'*64):self.assertFalse(self.review.node_view('script')['passed'])
        with self.code(NEW,'d'*64):
            self.assertFalse(self.review.node_view('script')['passed'])
            before=self.review.path.read_bytes()
            with self.assertRaisesRegex(ValueError,'边界模块已改变'):self.preserve()
            self.assertEqual(self.review.path.read_bytes(),before)

    def test_failed_legacy_or_unaudited_baselines_and_invalid_sha_are_rejected(self):
        with self.code(OLD):
            run=self.begin();self.review.finish('script',run,error='合成失败不成为迁移基线')
        state=self.review.load();old=copy.deepcopy(state['nodes']['script']['runs'][-1])
        with self.code(NEW):
            before=self.review.path.read_bytes()
            for backend,boundary,evidence in [('short',BOUNDARY,'证据'),(OLD,'x'*64,'证据'),(OLD,BOUNDARY,' '),(OLD,BOUNDARY,'合成失败基线')]:
                with self.assertRaises(ValueError):self.review.preserve_policy_for_execution_update(backend,boundary,evidence)
                self.assertEqual(self.review.path.read_bytes(),before)
            for legacy in [False,True]:
                fake=copy.deepcopy(old);fake.update(status='awaiting_confirmation',report=dict(protocol=blind.PROTOCOL,passed=True,fingerprint=old['fingerprint'],binding=dict(fingerprint=old['fingerprint']),producer_qa=dict(passed=True),supervision=dict(passed=True)))
                if legacy:fake.pop('protocol',None)
                state['nodes']['script']['runs'][-1]=fake;atomic(self.review.path,state);before=self.review.path.read_bytes()
                with self.assertRaisesRegex(ValueError,'真实通过'):self.preserve()
                self.assertEqual(self.review.path.read_bytes(),before)

    def test_content_sources_or_applicable_requirements_still_change_overall_fingerprint(self):
        run,previous=self.passing_old()
        with self.code(NEW):
            self.preserve();self.assertEqual(self.review.fingerprint('script'),previous)
            editor=self.studio.editor;draft=editor.read();original=draft['text'];editor.save(original+'\n\n合成人工新增正文。',draft['revision'])
            self.assertFalse(self.review.node_view('script')['passed']);self.assertFalse(self.review.node_view('script')['user_confirmed'])
            draft=editor.read();editor.save(original,draft['revision']);self.assertTrue(self.review.node_view('script')['passed'])
            source=self.course.relative(read(self.course.plan_file)['sources'][0]['location']);source_text=source.read_text();source.write_text(source_text+'\n合成原件新增要求')
            self.assertFalse(self.review.node_view('script')['passed']);source.write_text(source_text);self.assertTrue(self.review.node_view('script')['passed'])
            self.review.requirements(['合成新增当前逐字稿内容要求'],'合成真实用户补充')
            self.assertFalse(self.review.node_view('script')['passed']);self.assertEqual(self.review.load()['nodes']['script']['runs'][-1]['id'],run)


if __name__=='__main__':unittest.main()
