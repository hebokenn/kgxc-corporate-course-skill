"""Behavioral recovery and confirmation tests; no business approvals or rendering."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from workflow import LegacyCourse as Course, atomic, bundle_course
from runtime import ensure_dir


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'project').mkdir();(self.root/'inputs').mkdir()
        atomic(self.root/'project/workbench.json',{})
        (self.root/'inputs/original.csv').write_text('period,value\nDecember,7\n')
        self.course=Course(self.root);self.course.init('恢复测试')
        s=self.course.status();p=s['plan'];p.update(audience='测试受众',performance_task='解释同期数据变化')
        p['sources']=[dict(id='S1',title='保留原表',kind='file',location='../inputs/original.csv')]
        p['objectives']=[dict(id='O1',statement='解释数据',evidence='计算并说明',criterion='周期与单位一致')]
        p['units']=[dict(id='U1',title='读表',objective_ids=['O1'],source_refs=[dict(source_id='S1',locator='第2行')],
                        disposition='core',media='对比图',media_reason='显示同周期变化',activity='解释差异')]
        p['assessments']=[dict(id='A1',objective_ids=['O1'],task='说明周期',criteria='与原表一致',feedback='先核对月份')]
        p['decisions']=[dict(id='D1',question='如何使用旧数据',finding='原件属于历史资料',gate='outline',
            options=[dict(id='A',label='历史练习',impact='保留数字并标日期'),dict(id='B',label='补充新数据',impact='需要补资料')],
            recommended='A',selected='A',status='confirmed',evidence='不应被导入成确认',blocking_for=['courseware','production'])]
        self.course.save_plan(p,s['revision'])

    def tearDown(self):self.temp.cleanup()

    def decide(self):
        return self.course.decide('D1','A',self.course.status()['revision'],'测试选择：历史练习',actor='qa-agent')

    def test_recommendation_and_import_do_not_approve(self):
        d=self.course.status()['plan']['decisions'][0]
        self.assertIsNone(d['selected']);self.assertEqual(d['status'],'open')
        with self.assertRaises(ValueError):self.course.require('content')

    def test_subcommand_help_exposes_its_actual_parameters(self):
        cli=Path(__file__).with_name('kgxc_course.py')
        result=subprocess.run([sys.executable,str(cli),'start','--help'],capture_output=True,text=True,check=True)
        self.assertIn('--source',result.stdout);self.assertNotIn('bookends',result.stdout)

    def test_selection_survives_a_fresh_process(self):
        self.decide()
        cli=Path(__file__).with_name('workflow.py')
        p=subprocess.run([sys.executable,str(cli),'status',str(self.root),'--json'],capture_output=True,text=True,check=True)
        d=json.loads(p.stdout)['plan']['decisions'][0]
        self.assertEqual(d['selected'],'A');self.assertEqual(d['evidence'],'测试选择：历史练习')
        self.assertEqual(d['actor'],'qa-agent')

    def test_optimistic_conflict_preserves_first_answer(self):
        old=self.course.status()['revision'];self.decide()
        with self.assertRaises(FileExistsError):self.course.decide('D1','B',old,'旧页面提交')
        self.assertEqual(self.course.status()['plan']['decisions'][0]['selected'],'A')

    def test_question_change_requires_new_answer_keeps_history(self):
        self.decide();s=self.course.status();p=copy.deepcopy(s['plan']);p['decisions'][0]['finding']='来源版本已经更换'
        self.course.save_plan(p,s['revision'])
        self.assertEqual(self.course.status()['plan']['decisions'][0]['status'],'open')
        histories=list((self.root/'project/workflow-history').glob('*.json'))
        self.assertTrue(any('测试选择：历史练习' in p.read_text() for p in histories))

    def test_editing_json_cannot_overwrite_a_saved_choice(self):
        self.decide();s=self.course.status();p=copy.deepcopy(s['plan']);p['decisions'][0]['selected']='B'
        self.course.save_plan(p,s['revision'])
        self.assertEqual(self.course.status()['plan']['decisions'][0]['selected'],'A')

    def test_source_change_invalidates_review_chain(self):
        self.decide();self.course.confirm('source',self.course.status()['revision'],'QA 已核对原表',actor='qa-agent')
        self.course.confirm('outline',self.course.status()['revision'],'QA 选定结构',actor='qa-agent')
        self.assertEqual(self.course.status()['stage'],'content')
        (self.root/'inputs/original.csv').write_text('period,value\nJanuary,8\n')
        self.assertEqual(self.course.status()['gates'][0]['status'],'stale')
        with self.assertRaises(ValueError):self.course.require('outline')

    def test_courseware_save_marks_voice_and_preserves_source(self):
        before=(self.root/'inputs/original.csv').read_bytes()
        s=self.course.save_courseware('完整测试稿，包括示范与反馈。',self.course.status()['revision'])
        self.assertEqual(s['narration_status'],'needs_regeneration')
        self.assertEqual((self.root/'inputs/original.csv').read_bytes(),before)
        self.assertEqual(self.course.courseware()['text'],'完整测试稿，包括示范与反馈。')

    def test_new_fact_issue_blocks_production_but_keeps_outline(self):
        self.decide()
        for key in ['source','outline']:self.course.confirm(key,self.course.status()['revision'],'QA 阶段审阅',actor='qa-agent')
        self.course.save_courseware('测试讲稿',self.course.status()['revision'])
        self.course.confirm('content',self.course.status()['revision'],'QA 稿件审阅',actor='qa-agent')
        s=self.course.status();p=s['plan'];p['issues'].append(dict(id='I1',detail='指标口径需确认',state='open',blocks='production'))
        self.course.save_plan(p,s['revision'])
        states={g['id']:g['status'] for g in self.course.status()['gates']}
        self.assertEqual(states['outline'],'confirmed');self.assertEqual(states['content'],'stale')
        with self.assertRaises(ValueError):self.course.require('content')

    def test_path_escape_and_permission_errors_are_not_suppressed(self):
        with self.assertRaises(ValueError):self.course.relative('../../outside')
        with patch.object(Path,'mkdir',side_effect=PermissionError('host denied')):
            ensure_dir(self.root)
            with self.assertRaises(PermissionError):ensure_dir(self.root/'forbidden')

    def test_package_reopens_choices_without_original_installation_path(self):
        import zipfile
        self.decide();out=self.root/'packages/recovery.zip';bundle_course(self.root,out)
        target=self.root/'unpacked'
        with zipfile.ZipFile(out) as z:self.assertIsNone(z.testzip());z.extractall(target)
        recovered=Course(target).status()
        self.assertEqual(recovered['plan']['decisions'][0]['selected'],'A')
        self.assertEqual(recovered['source_files']['S1']['sha256'],self.course.status()['source_files']['S1']['sha256'])
        self.assertTrue((target/'project/editor/scripts/workflow.py').is_file())


if __name__=='__main__':unittest.main()
