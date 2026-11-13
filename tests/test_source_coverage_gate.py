"""Source accounting gates use explicit synthetic clicks, never live courses."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from workflow import Course,atomic,read
from studio import Studio
from source_coverage import SourceCoverage
from ai_review import Review
from test_branch_workflow import design


class SourceCoverageGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.project=self.root/'project'
        atomic(self.project/'workbench.json',dict(title='原件对照技术夹具',scenes=[],media={}))
        self.course=Course(self.root);self.course.init('原件对照技术夹具');design(self.course)
        self.course.confirm('outline',self.course.status()['revision'],'合成结构确认',actor='qa-operator')
        self.studio=Studio(SimpleNamespace(root=self.root,project=self.project,file=self.project/'workbench.json'))
        self.studio.save_sections([dict(unit_id='U',body='先核对订单，再核对编码。')],self.course.status()['revision'],official=True)
        self.coverage=SourceCoverage(self.course)

    def tearDown(self):self.tmp.cleanup()

    def report(self):
        source=self.course._source_files(read(self.course.plan_file))['S']
        return dict(schema='source-coverage/1',source_inventory=[dict(source_id='S',sha256=source['sha256'],read_scope='合成原件全文',fully_read=True,unreadable=[])],
                    points=[dict(id='P1',source_id='S',locator='正文首句',source_quote='先核对订单，再核对编码。',critical=True,
                                 disposition='retained',script_quotes=['先核对订单，再核对编码。'],reason='本课核心操作顺序')],additions=[])

    def save(self,report=None):
        return self.coverage.save(report or self.report(),self.coverage.view()['script_sha256'])

    def click(self):
        return self.coverage.confirm(self.coverage.view()['report_sha256'],'合成测试：人工查看并确认当前原件对照',actor='dsh-user-click',source='workbench-explicit-click')

    def test_missing_or_only_producer_saved_report_blocks_script_confirmation(self):
        before=self.course.state_file.read_bytes()
        with self.assertRaisesRegex(ValueError,'原件'):
            self.course.confirm('script',self.course.status()['revision'],'确认逐字稿')
        self.assertEqual(self.course.state_file.read_bytes(),before)
        self.save();self.assertFalse(self.coverage.view()['confirmed'])
        with self.assertRaisesRegex(ValueError,'人工'):
            self.studio.confirm('script',self.course.status()['revision'])
        self.assertNotIn('script',read(self.course.state_file)['gates'])
        review=Review(self.course)
        before_repair={path:path.read_bytes() for path in [self.course.state_file,self.course.plan_file,self.coverage.path]}
        with self.assertRaisesRegex(ValueError,'原件'):
            review.repair('storyboard','no-approved-downstream-run',[],producer_id='producer')
        self.assertFalse(review.path.exists())
        for path,data in before_repair.items():self.assertEqual(path.read_bytes(),data)

    def test_same_real_script_click_can_confirm_coverage_and_continue(self):
        self.save();digest=self.coverage.view()['report_sha256']
        view=self.studio.action('confirm',dict(baseRevision=self.course.status()['revision'],stage='script',
            source_coverage_declaration=dict(report_sha256=digest,evidence='合成测试明确勾选当前报告',source='workbench-explicit-click')))
        self.assertTrue(view['source_coverage']['confirmed']);self.assertEqual(view['plan']['schema_version'],2)
        self.assertEqual(read(self.course.state_file)['branch'],'video')
        self.course.require('script')

    def test_source_script_or_report_changes_invalidate_old_confirmation(self):
        self.save();self.click();self.course.confirm('script',self.course.status()['revision'],'合成逐字稿确认')
        receipt=copy.deepcopy(read(self.course.state_file)['gates']['script'])
        original=self.course.relative('../inputs/source.txt');original.write_text(original.read_text()+'原件补充。')
        with self.assertRaisesRegex(ValueError,'原件'):
            self.course.require('script')
        self.assertEqual(read(self.course.state_file)['gates']['script'],receipt)
        self.save();self.click();editor=self.studio.editor.read();self.studio.editor.save(editor['text']+'\n\n新增说明。',editor['revision'])
        with self.assertRaisesRegex(ValueError,'逐字稿'):
            self.coverage.require_confirmed()
        self.save();self.click();updated=self.report();updated['notes']='明确重新整理要点理由'
        self.save(updated);self.assertFalse(self.coverage.view()['confirmed'])
        with self.assertRaisesRegex(ValueError,'人工'):
            self.coverage.require_confirmed()

    def test_legacy_same_script_receipt_is_kept_but_downstream_requires_coverage(self):
        state=read(self.course.state_file);state['gates']['script']=dict(at='historical',actor='dsh-course-workbench',evidence='历史逐字稿确认',sha256=self.course._gate_hash('script',read(self.course.plan_file),state));atomic(self.course.state_file,state)
        receipt=copy.deepcopy(state['gates']['script']);status=self.course.status()
        self.assertEqual(next(g for g in status['gates'] if g['id']=='script')['status'],'stale')
        self.assertEqual(read(self.course.state_file)['gates']['script'],receipt)
        with self.assertRaisesRegex(ValueError,'原件'):
            self.course.select_branch('video',status['revision'],'继续旧课')

    def test_view_is_read_only_and_does_not_unhold_course(self):
        review=Review(self.course);review.ensure();review.hold(True,'本课暂停，只完善插件')
        before={path:path.read_bytes() for path in [self.course.state_file,self.course.plan_file,review.path]}
        for _ in range(2):self.course.status();self.studio.view();review.view()
        self.assertFalse(self.coverage.path.exists())
        for path,data in before.items():self.assertEqual(path.read_bytes(),data)
        self.assertTrue(review.load()['hold']['held'])

    def test_declaration_rejects_stale_revision_wrong_source_and_simulated_click(self):
        self.save();declaration=dict(report_sha256=self.coverage.view()['report_sha256'],evidence='合成明确动作',source='workbench-explicit-click')
        with self.assertRaises(FileExistsError):
            self.studio.confirm('script',self.course.status()['revision']-1,source_coverage_declaration=declaration)
        with self.assertRaisesRegex(ValueError,'明确勾选'):
            self.studio.confirm('script',self.course.status()['revision'],source_coverage_declaration=dict(declaration,source='producer-auto'))
        with self.assertRaises(FileExistsError):
            self.studio.confirm('script',self.course.status()['revision'],source_coverage_declaration=dict(declaration,report_sha256='0'*64))
        atomic(self.project/'workbench-review-context.json',dict(scope='qa-simulation',course_id=read(self.course.state_file)['course_id']))
        with self.assertRaisesRegex(ValueError,'真实用户'):
            self.studio.confirm('script',self.course.status()['revision'],source_coverage_declaration=declaration)
        self.assertFalse(self.coverage.view()['confirmed'])

    def test_producer_packet_keeps_coverage_private_from_single_blind_packet(self):
        self.save();review=Review(self.course);review.ensure()
        from test_ai_review import ROUTE,PRODUCER
        run=review.begin('script','synthetic-coverage-scope','continue',route=ROUTE,producer=PRODUCER)['run']['id']
        packet=review.producer_packet('script',run)['packet']
        self.assertEqual(packet['source_coverage']['report'],self.report());self.assertFalse(packet['source_coverage']['confirmed'])
        blind=review.packet('script',run)['packet']
        self.assertNotIn('source_coverage',blind);self.assertNotIn('原件读取',str(blind))

    def test_no_sources_has_no_fabricated_full_coverage(self):
        plan=read(self.course.plan_file);plan['sources']=[];atomic(self.course.plan_file,plan)
        view=self.coverage.require_confirmed()
        self.assertEqual(view['status'],'not_required');self.assertIsNone(view['statistics']['rate']);self.assertFalse(view['confirmed'])

    def test_source_only_request_survives_restart_without_automatic_blind_review(self):
        from test_ai_review import ROUTE,PRODUCER
        review=Review(self.course);review.ensure()
        review.production_event(PRODUCER,'source-only-operation','start','script',[
            dict(type='production/request',operation='source-coverage',call_id='source-only-operation',agent_id=PRODUCER['id'],stage='script')])
        reopened=Review(self.course)
        self.assertFalse(reopened.view()['auto_review'])
        before=reopened.path.read_bytes()
        value=reopened.begin('script','auto-after-restart','auto',route=ROUTE,producer=PRODUCER)
        self.assertFalse(value['started']);self.assertFalse(value['auto_review']);self.assertEqual(reopened.path.read_bytes(),before)
        reopened.production_event(PRODUCER,'explicit-next-production','start','script',[
            dict(type='production/request',operation='controlled-produce',call_id='explicit-next-production',agent_id=PRODUCER['id'],stage='script')])
        self.assertTrue(reopened.view()['auto_review'])


if __name__=='__main__':unittest.main()
