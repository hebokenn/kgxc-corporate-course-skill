"""Author input checks remain optional for legacy plans and do not approve prose."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/elearning-course-design/scripts/check_design.py'
spec = importlib.util.spec_from_file_location('design_authoring_check', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def plan():
    return dict(schema_version=2, title='合成课', audience='合成受众', performance_task='核对编号', stage='script', script_file='script.md',
                sources=[dict(id='S1', title='示例规则', location='合成规则第1条', kind='provided_text')],
                objectives=[dict(id='O1', statement='核对编号', evidence='操作记录', criterion='编号一致')],
                units=[dict(id='U1', title='核对', media='文字', media_reason='动作简短', activity='核对', teaching_method='示范', teaching_reason='可观察', disposition='core', objective_ids=['O1'], source_refs=[dict(source_id='S1', locator='第1条')])],
                assessments=[dict(id='A1', task='核对示例', criteria='编号一致', feedback='指出首个不同位', objective_ids=['O1'])], decisions=[], issues=[],
                handoff=dict(ready_for_courseware=False, ready_for_production=False))


def authoring():
    return dict(schema='script-authoring/1', selected_plan='已选大纲v1', brand_greeting=None,
                unit_intents=[dict(unit_id='U1', trigger='收到商品', action='核对编号', decision_basis='示例规则第1条', new_information='发现不一致先停止交接', example='A102与A120不一致')],
                self_check=dict(status='complete', evidence='完整通读U1，补齐不同编号的反馈；未调用新审阅', unresolved=[]))


class DesignAuthoringTests(unittest.TestCase):
    def test_legacy_plan_without_new_record_remains_valid(self):
        self.assertTrue(module.check(plan(), Path('.'))['ok'])

    def test_script_needs_current_plan_and_unit_input(self):
        item = plan(); item['authoring'] = authoring(); item['authoring']['selected_plan'] = ''; item['authoring']['unit_intents'] = []
        report = module.check(item, Path('.'))
        self.assertIn('Script authoring needs the current selected plan', report['errors'])
        self.assertIn('U1: missing authoring input', report['errors'])

    def test_ready_cannot_skip_author_self_check(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); (base/'script.md').write_text('合成正文')
            item = plan(); item['authoring'] = authoring(); item['authoring']['self_check']['status'] = 'not_done'; item['handoff']['ready_for_production'] = True
            self.assertIn("Readiness requires the producer's complete-script self-check", module.check(item, base)['errors'])

    def test_input_record_is_not_a_score_or_approval(self):
        item = plan(); item['authoring'] = authoring()
        before = copy.deepcopy(item); report = module.check(item, Path('.'))
        self.assertTrue(report['ok']); self.assertEqual(item, before)
        self.assertNotIn('quality_score', report)
        self.assertIn('no proof of approval', report['scope'])

    def test_unresolved_authoring_conflicts_with_readiness(self):
        item = plan(); item['authoring'] = authoring(); item['authoring']['self_check']['unresolved'] = ['待核实来源']; item['handoff']['ready_for_courseware'] = True
        self.assertIn('Readiness conflicts with unresolved authoring items', module.check(item, Path('.'))['errors'])


if __name__ == '__main__':
    unittest.main()
