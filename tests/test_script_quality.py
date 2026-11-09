"""Synthetic narration only: opening contract and conservative quality signals."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/corporate-training-motion/workbench'))
from script_quality import inspect_script


class ScriptQualityTests(unittest.TestCase):
    greeting = '欢迎来到酷果星创企业培训课堂'

    def test_selected_greeting_tolerates_punctuation_and_heading(self):
        report = inspect_script('# 情境课\n\n大家好，欢迎来到酷果星创企业培训课堂。\n顾客提高音量时，先请同事接待，再离开柜台做三次缓慢呼吸。', self.greeting, True)
        self.assertEqual(report['status'], 'mechanical_checks_clear')
        self.assertEqual(report['blocking'], [])
        self.assertTrue(report['limitations'])

    def test_greeting_in_heading_or_late_summary_does_not_count(self):
        for text in ['# '+self.greeting+'\n\n先说处理方法。', '先说处理方法。'*40+'\n'+self.greeting]:
            with self.subTest(text=text[:25]):
                self.assertIn('opening-greeting-missing', [x['id'] for x in inspect_script(text, self.greeting, True)['blocking']])

    def test_fenced_production_note_does_not_supply_opening(self):
        text = '```notes\n'+self.greeting+'\n```\n\n先说处理方法。'
        self.assertEqual(inspect_script(text, self.greeting, True)['checks'][1]['status'], 'blocked')

    def test_hidden_comment_cannot_supply_opening_or_placeholder(self):
        text = '<!--\n'+self.greeting+'\n【补充案例】\n-->\n先说处理方法。'
        report = inspect_script(text, self.greeting, True)
        self.assertEqual([item['id'] for item in report['blocking']], ['opening-greeting-missing'])

    def test_generic_enterprise_does_not_gain_kgxc_brand(self):
        report = inspect_script('大家好。请先核对订单，再核对商品编号。')
        self.assertEqual(report['blocking'], [])
        self.assertEqual(report['checks'][1]['status'], 'not_required')

    def test_explicit_kgxc_contract_accepts_natural_greeting_without_locking_exact_copy(self):
        self.assertEqual(inspect_script('各位店长大家好，欢迎来到酷果星创培训课堂。', require_greeting=True)['blocking'], [])
        self.assertEqual(inspect_script('大家好。', require_greeting=True)['blocking'][0]['id'], 'opening-greeting-missing')

    def test_placeholder_has_actual_location(self):
        report = inspect_script('# 标题\n\n大家好。\n【补充案例】')
        self.assertEqual(report['blocking'][0]['line'], 4)
        self.assertEqual(report['blocking'][0]['quote'], '【补充案例】')

    def test_repetition_and_stock_wording_are_advisories_not_automatic_failure(self):
        passage = '顾客提高音量时，先请同事接待，再离开柜台做三次缓慢呼吸，等语速放慢后回到顾客面前说明当前可处理的事项。'
        report = inspect_script(passage+'\n'+passage+'\n先解释“闭环”的现场含义，避免只说形成闭环。')
        self.assertEqual(report['blocking'], [])
        self.assertEqual({x['id'] for x in report['advisories']}, {'repeated-passage', 'stock-wording'})
        self.assertEqual(report['advisories'][0]['first_line'], 1)


if __name__ == '__main__':
    unittest.main()
