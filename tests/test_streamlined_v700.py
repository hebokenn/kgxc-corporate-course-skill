"""Regression tests for KGXC 7.0.0 streamlined workflow, palettes, and template masters."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / 'skills' / 'corporate-training-motion' / 'workbench'
if str(WORKBENCH) not in sys.path:
    sys.path.insert(0, str(WORKBENCH))

import course_palette  # noqa: E402
import storyboard  # noqa: E402
import workflow  # noqa: E402


def _make_option(oid, method, opening, action, result):
    return {
        'id': oid,
        'title': f'方案 {oid}',
        'method': method,
        'opening': opening,
        'action': action,
        'result': result,
        'focus': '关键业务动作',
        'feasibility': '纯代码 SVG/Canvas 实现，无外部依赖',
        'cost': 'low',
        'risk_note': '低风险，重点对齐口播节奏',
        'difference': f'采用 {method} 结构呈现核心对比',
        'characters': False,
    }


class StreamlinedV700Tests(unittest.TestCase):
    def test_version_is_700(self):
        self.assertEqual(workflow.VERSION, '7.0.0')
        self.assertEqual((ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '7.0.0')

    def test_sixteen_bright_light_palettes_in_random_pool_and_dark_opt_in(self):
        cat = course_palette.catalog()
        eligible = [p for p in cat['palettes'] if p.get('random_eligible', True)]
        opt_in = [p for p in cat['palettes'] if not p.get('random_eligible', True)]
        self.assertEqual(len(eligible), 16)
        self.assertGreaterEqual(len(opt_in), 2)
        for p in cat['palettes']:
            course_palette.validate(p)
        for p in eligible:
            self.assertEqual(p.get('tone'), 'light')
            r, g, b = course_palette.rgb(p['canvas'])
            self.assertGreaterEqual((r + g + b) / 3.0, 0.9)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            plan = course_palette.select(project, exclude=['green'], seed='v700-bright-check')
            self.assertTrue(plan['palette'].get('random_eligible', True))
            self.assertEqual(plan['palette'].get('tone'), 'light')
            self.assertEqual(len(plan['candidate_pool']), 16)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            dark = opt_in[0]
            plan = course_palette.select(
                project,
                exclude=['green'],
                specified=dark,
                evidence='用户明确要求深色风测试',
            )
            self.assertEqual(plan['palette']['id'], dark['id'])

    def test_template_masters_allow_single_shot_per_segment_and_reject_invalid(self):
        script_text = '## 第一单元\n\n【口播】\n大家好，欢迎来到酷果星创。今天我们看第一步核对动作。\n'
        script_sha = hashlib.sha256(script_text.encode('utf-8')).hexdigest()
        parsed = storyboard.paragraphs(script_text)
        self.assertEqual(len(parsed), 1)
        p0 = parsed[0]
        design = {'units': [{'id': 'u1', 'title': '第一单元', 'disposition': 'core'}], 'assessments': []}
        masters = [
            {
                'id': 'M1',
                'title': '认知模型类母版',
                'recommended': 'A',
                'options': [
                    _make_option('A', 'diagram', '起态A', '动作A', '结果A'),
                    _make_option('B', 'comparison', '起态B', '动作B', '结果B'),
                    _make_option('C', 'timeline', '起态C', '动作C', '结果C'),
                ],
            }
        ]
        valid_board = {
            'schema': storyboard.SCHEMA,
            'script_sha256': script_sha,
            'visual_direction': {
                'palette': '晴雪银与星创红明亮浅色',
                'typography': 'PingFang SC 清晰层级',
                'graphics': '代码化动态图示',
                'atmosphere': '明亮通透专业',
            },
            'presentation_policy': {'concept_characters': False, 'scenario_characters': False},
            'template_masters': masters,
            'segments': [
                {
                    'id': 'S01',
                    'kind': 'concept',
                    'title': '开场核对',
                    'teaching_goal': '让学员看清第一步核对对象',
                    'risk': 'normal',
                    'recommendation_reason': '用结构图示直观对齐动作与结果',
                    'unit_id': 'u1',
                    'source_paragraph_ids': [p0['id']],
                    'script_excerpt': p0['text'],
                    'template_id': 'M1',
                    'recommended': 'A',
                    'selected': 'A',
                    'selection_receipt': {'evidence': '用户确认采用母版 M1 方案 A'},
                    'options': [_make_option('A', 'diagram', '起态A', '动作A', '结果A')],
                }
            ],
        }
        res = storyboard.check(valid_board, script_text, script_sha, design)
        self.assertTrue(res['ok'], res)

        # Invalid template_id should be rejected
        bad_tid = json.loads(json.dumps(valid_board))
        bad_tid['segments'][0]['template_id'] = 'MISSING'
        res_bad = storyboard.check(bad_tid, script_text, script_sha, design)
        self.assertFalse(res_bad['ok'])
        self.assertTrue(any('template_id' in e for e in res_bad['errors']))

        # Without template_id, legacy 3-option requirement still applies
        legacy_one = json.loads(json.dumps(valid_board))
        del legacy_one['template_masters']
        del legacy_one['segments'][0]['template_id']
        res_legacy = storyboard.check(legacy_one, script_text, script_sha, design)
        self.assertFalse(res_legacy['ok'])
        self.assertTrue(any('至少需要三种画面表现方案' in e for e in res_legacy['errors']))

        # Master with fewer than 3 distinct options should be rejected
        bad_master = json.loads(json.dumps(valid_board))
        bad_master['template_masters'][0]['options'] = bad_master['template_masters'][0]['options'][:2]
        res_bm = storyboard.check(bad_master, script_text, script_sha, design)
        self.assertFalse(res_bm['ok'])
        self.assertTrue(any('母版至少需要三种实质不同的画面表现方案' in e for e in res_bm['errors']))

    def test_selfcheck_workflow_skips_stage_release_without_ai_review_json(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'course'
            course = workflow.Course(project)
            course.init('测试7.0课程')
            self.assertFalse((course.project / 'ai-review.json').exists())
            rev = course.status()['revision']
            with patch('production.stage_release') as mock_release:
                with self.assertRaisesRegex(ValueError, '本阶段尚不能确认'):
                    course.confirm('script', rev, '已完成自查并确认', actor='user')
                mock_release.assert_not_called()
            (course.project / 'ai-review.json').write_text('{"schema":"course-ai-review/1","nodes":{}}\n', encoding='utf-8')
            with patch('production.stage_release', side_effect=RuntimeError('legacy_gate_called')) as mock_release:
                with self.assertRaisesRegex(RuntimeError, 'legacy_gate_called'):
                    course.confirm('script', rev, '已完成自查并确认', actor='user')
                mock_release.assert_called_once()


if __name__ == '__main__':
    unittest.main()
