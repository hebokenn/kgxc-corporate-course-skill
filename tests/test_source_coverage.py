"""Temporary sources only: point accounting and current-byte click receipts."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'))
from source_coverage import SourceCoverage
import source_coverage as coverage_module
from script_editor import ScriptEditor


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class SourceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve(); self.project = self.root/'project'
        (self.project/'source').mkdir(parents=True)
        self.source = self.project/'source/rules.txt'
        self.source.write_text('先核对订单。\n编码不一致时暂停交接。\n历史背景仅供了解。', encoding='utf-8')
        self.script = self.project/'source/transcript.md'
        self.script.write_text('大家好，欢迎来到酷果星创培训课堂。先核对订单。编码不一致时暂停交接。示例：P12与P21不同。', encoding='utf-8')
        self.plan = self.project/'design-plan.json'
        write(self.plan, dict(title='合成覆盖核对', schema_version=2, script_file='source/transcript.md', sources=[dict(id='S1', kind='file', location='source/rules.txt')]))
        write(self.project/'course-state.json', dict(schema='course-workflow/2'))
        write(self.project/'workbench.json', dict(title='合成覆盖核对', scenes=[]))
        def relative(name):
            target = (self.project/name).resolve()
            if not target.is_relative_to(self.root):
                raise ValueError('范围外')
            return target
        self.course = SimpleNamespace(root=self.root, project=self.project, plan_file=self.plan, relative=relative,
                                      script=lambda: dict(text=self.script.read_text(), path='source/transcript.md'))
        self.coverage = SourceCoverage(self.course)
        self.report = dict(schema='source-coverage/1',
            source_inventory=[dict(source_id='S1', sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(), read_scope='全部3行；纯文本无图片', fully_read=True, unreadable=[])],
            points=[dict(id='P1', source_id='S1', locator='第1行', source_quote='先核对订单。', critical=True, disposition='retained', script_quotes=['先核对订单。'], reason='岗位必要动作'),
                    dict(id='P2', source_id='S1', locator='第2行', source_quote='编码不一致时暂停交接。', critical=True, disposition='merged', script_quotes=['编码不一致时暂停交接。'], reason='并入交接示范讲清条件'),
                    dict(id='P3', source_id='S1', locator='第3行', source_quote='历史背景仅供了解。', critical=False, disposition='omitted', script_quotes=[], reason='当前岗位无需记忆的背景，保留在原件')],
            additions=[dict(id='N1', script_quote='示例：P12与P21不同。', location='正文末句', reason='示范怎样发现不一致', basis_kind='example', basis='教学虚构编码，不新增内部规则')])

    def tearDown(self):
        self.temp.cleanup()

    def save(self, report=None):
        return self.coverage.save(copy.deepcopy(report or self.report), self.coverage.view()['script_sha256'])

    def confirm(self):
        view = self.coverage.view()
        return self.coverage.confirm(view['report_sha256'], '我已对照原件核对覆盖、舍弃和新增内容，确认本稿取舍。', source='workbench-explicit-click')

    def test_point_denominator_keeps_omissions_and_separates_critical_points_and_additions(self):
        view = self.save(); stats = view['statistics']
        self.assertEqual((stats['covered'], stats['total'], stats['omitted'], stats['merged']), (2, 3, 1, 1))
        self.assertEqual(stats['rate'], 66.67); self.assertEqual(stats['critical']['rate'], 100)
        self.assertEqual(stats['additions'], 1); self.assertFalse(view['confirmed']); self.assertTrue(view['can_confirm'])
        self.assertIn('字数', stats['denominator']); self.assertIn('人工', stats['scope'])

    def test_save_does_not_confirm_or_change_source_and_script_and_view_is_read_only(self):
        original = (self.source.read_bytes(), self.script.read_bytes())
        self.save(); before = self.coverage.path.read_bytes()
        self.coverage.view(); self.coverage.view()
        self.assertEqual(before, self.coverage.path.read_bytes()); self.assertEqual(original, (self.source.read_bytes(), self.script.read_bytes()))
        with self.assertRaisesRegex(ValueError, '人工确认'):
            self.coverage.require_confirmed()

    def test_click_receipt_is_separate_and_exactly_bound(self):
        saved = self.save(); confirmed = self.confirm()
        self.assertTrue(confirmed['confirmed']); self.assertEqual(confirmed['report'], saved['report'])
        for key in ['report_sha256', 'script_sha256', 'sources_sha256']:
            self.assertEqual(confirmed['confirmation'][key], confirmed[key])
        self.assertEqual(self.coverage.require_confirmed()['status'], 'confirmed')

    def test_report_edit_resets_confirmation_and_retains_history(self):
        self.save(); self.confirm(); updated = copy.deepcopy(self.report); updated['points'][2]['reason'] = '同一受众当前不需记忆，背景留原件'
        view = self.save(updated)
        self.assertFalse(view['confirmed']); self.assertEqual(view['history_count'], 1)
        state = json.loads(self.coverage.path.read_text()); self.assertTrue(state['history'][0]['confirmation'])

    def test_current_draft_is_used_and_later_draft_edit_invalidates_confirmation(self):
        editor = ScriptEditor(SimpleNamespace(root=self.root, project=self.project, file=self.project/'workbench.json'))
        draft = editor.read(); editor.save(draft['text']+'先请同事协助。', draft['revision'])
        saved = self.save(); self.assertEqual(saved['script_sha256'], hashlib.sha256(editor.read()['text'].encode()).hexdigest())
        self.confirm(); draft = editor.read(); editor.save(draft['text']+'保持语速平稳。', draft['revision'])
        view = self.coverage.view(); self.assertFalse(view['current']); self.assertFalse(view['confirmed']); self.assertIsNone(view['statistics']['rate'])

    def test_source_or_report_byte_changes_invalidate_human_receipt(self):
        self.save(); self.confirm(); self.source.write_text(self.source.read_text()+'\n新增真实规则。')
        view = self.coverage.view(); self.assertFalse(view['current']); self.assertFalse(view['confirmed'])
        with self.assertRaises(FileExistsError):
            self.confirm()
        self.assertIsNone(view['statistics']['rate'])

    def test_report_tampering_without_matching_digest_is_stale(self):
        self.save(); self.confirm(); state = json.loads(self.coverage.path.read_text()); state['report']['points'][2]['reason'] = '未经确认的变更'; write(self.coverage.path, state)
        self.assertFalse(self.coverage.view()['current']); self.assertFalse(self.coverage.view()['confirmed'])

    def test_no_source_and_partial_read_never_report_full_coverage(self):
        report = copy.deepcopy(self.report); report['source_inventory'][0].update(fully_read=False, unreadable=['末行尚待辨认'])
        self.assertIsNone(self.save(report)['statistics']['rate'])
        plan = json.loads(self.plan.read_text()); plan['sources'] = []; write(self.plan, plan)
        view = self.coverage.require_confirmed(); self.assertEqual(view['status'], 'not_required'); self.assertIsNone(view['statistics']['rate'])

    def test_stale_script_or_source_hash_rejects_save_without_overwriting(self):
        self.save(); before = self.coverage.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.coverage.save(self.report, 'old-script-hash')
        bad = copy.deepcopy(self.report); bad['source_inventory'][0]['sha256'] = 'old-source-hash'
        with self.assertRaises(FileExistsError):
            self.save(bad)
        self.assertEqual(self.coverage.path.read_bytes(), before)

    def test_false_quotes_or_missing_reasons_and_addition_basis_are_rejected(self):
        for mutate in [lambda r: r['points'][0].update(source_quote='伪造原件引文'),
                       lambda r: r['points'][0].update(script_quotes=['伪造讲稿引文']),
                       lambda r: r['points'][2].update(reason=''),
                       lambda r: r['additions'][0].update(basis=''),
                       lambda r: r['additions'][0].update(script_quote='本稿未出现的新增内容')]:
            report = copy.deepcopy(self.report); mutate(report)
            with self.assertRaises(ValueError):
                self.save(report)
        self.assertFalse(self.coverage.path.exists())

    def test_producer_cannot_embed_receipt_or_claim_a_silent_confirmation(self):
        for key in ['confirmed', 'confirmation', 'receipt', 'user_approved']:
            report = copy.deepcopy(self.report); report[key] = True
            with self.assertRaises(ValueError):
                self.save(report)
        self.save()
        for actor in ['producer', 'assistant', 'chat', 'user-chat-confirmation']:
            with self.assertRaises(ValueError):
                self.coverage.confirm(self.coverage.view()['report_sha256'], '默认通过', actor=actor, source='workbench-explicit-click')
        for evidence, source in [('', 'workbench-explicit-click'), ('人工确认', None)]:
            with self.assertRaises(ValueError):
                self.coverage.confirm(self.coverage.view()['report_sha256'], evidence, source=source)
        self.assertFalse(self.coverage.view()['confirmed'])

    def test_missing_inventory_and_duplicate_ids_do_not_inflate_or_shrink_denominator(self):
        for mutate in [lambda r: r.update(source_inventory=[]), lambda r: r['points'].append(copy.deepcopy(r['points'][0])), lambda r: r.update(points=[])]:
            report = copy.deepcopy(self.report); mutate(report)
            with self.assertRaises(ValueError):
                self.save(report)

    def test_report_compare_and_swap_preserves_concurrent_newer_work(self):
        view = self.save(); updated = copy.deepcopy(self.report); updated['points'][0]['reason'] = '当前需要的岗位动作'; self.save(updated)
        before = self.coverage.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.coverage.save(self.report, self.coverage.view()['script_sha256'], view['report_sha256'])
        self.assertEqual(before, self.coverage.path.read_bytes())

    def test_bounded_source_excerpts_reconstruct_current_text_without_mutation(self):
        original = self.source.read_bytes(); first = self.coverage.source_excerpt('S1', limit=8)
        self.assertEqual(first['status'], 'available'); self.assertTrue(first['truncated']); self.assertEqual(first['next_offset'], 8)
        self.assertEqual(first['source_sha256'], hashlib.sha256(original).hexdigest())
        rest = self.coverage.source_excerpt('S1', offset=first['next_offset'])
        self.assertEqual(first['text']+rest['text'], original.decode()); self.assertIsNone(rest['next_offset'])
        self.assertFalse(rest['truncated']); self.assertIn('OCR', rest['limitations'][0]); self.assertFalse(self.coverage.path.exists())
        self.assertEqual(original, self.source.read_bytes())

    def test_source_excerpt_rejects_unknown_sources_and_invalid_ranges(self):
        for source_id, offset, limit in [('other-course', 0, 10), ('S1', -1, 10), ('S1', True, 10), ('S1', 0, 0), ('S1', 0, 60001), ('S1', 99999, 10)]:
            with self.subTest(source_id=source_id, offset=offset, limit=limit):
                with self.assertRaises(ValueError):
                    self.coverage.source_excerpt(source_id, offset, limit)

    def test_unextractable_source_stays_unknown_instead_of_claiming_fully_read(self):
        plan = json.loads(self.plan.read_text()); plan['sources'][0]['location'] = 'source/scan.png'; write(self.plan, plan)
        (self.project/'source/scan.png').write_bytes(b'not-a-real-image-synthetic-fixture')
        result = self.coverage.source_excerpt('S1')
        self.assertEqual(result['status'], 'unknown'); self.assertEqual(result['text'], '')
        self.assertIsNone(result['total_chars']); self.assertIsNone(result['truncated'])
        self.assertIn('不得登记为全文已读', result['limitations'][-1])

    def test_empty_cli_drawing_document_does_not_require_ui_title(self):
        from workflow import Course
        other = self.root/'cli-project'
        write(other/'project/workbench.json', {})
        course = Course(other)
        course.init('纯CLI新课')
        self.assertEqual(SourceCoverage(course).view()['status'], 'not_required')
        self.assertIsInstance(course.status(), dict)
        self.assertEqual(json.loads((other/'project/workbench.json').read_text()), {})

    def test_cli_without_title_keeps_current_draft_and_conflict_instead_of_official_fallback(self):
        write(self.project/'workbench.json', {})
        official = self.script.read_text()
        draft = dict(text=official+'人工未提交修改。', base_text=official, base_sha256=hashlib.sha256(official.encode()).hexdigest())
        write(self.project/'script-editor.json', draft)
        view = self.coverage.view()
        self.assertEqual(view['script_sha256'], hashlib.sha256(draft['text'].encode()).hexdigest())
        self.save(); self.confirm()
        self.script.write_text(official+'另一处正式修改。')
        view = self.coverage.view()
        self.assertEqual(view['script_sha256'], hashlib.sha256(draft['text'].encode()).hexdigest())
        self.assertFalse(view['current']); self.assertFalse(view['confirmed']); self.assertIn('基线冲突', ';'.join(view['reasons']))
        with self.assertRaises(FileExistsError):
            self.save()

    def test_cli_clean_draft_rebases_and_legacy_unknown_draft_remains_unconfirmed(self):
        write(self.project/'workbench.json', {})
        original = self.script.read_text()
        write(self.project/'script-editor.json', dict(text=original, base_text=original, base_sha256=hashlib.sha256(original.encode()).hexdigest()))
        self.script.write_text(original+'新的正式稿。')
        self.assertEqual(self.coverage.view()['script_sha256'], hashlib.sha256(self.script.read_bytes()).hexdigest())
        write(self.project/'script-editor.json', dict(text='旧版未记录基线的真实草稿'))
        view = self.coverage.view()
        self.assertEqual(view['script_sha256'], hashlib.sha256('旧版未记录基线的真实草稿'.encode()).hexdigest())
        self.assertIn('基线冲突', ';'.join(view['reasons']))

    def test_source_extraction_cache_reuses_only_current_source_hash_without_disk_writes(self):
        with patch.object(coverage_module, '_source_text', wraps=coverage_module._source_text) as extract:
            self.save(); self.coverage.view(); self.coverage.view()
            self.assertEqual(extract.call_count, 1)
            self.source.write_text(self.source.read_text()+'\n新增不同原文。')
            self.coverage.view(); self.coverage.view()
            self.assertEqual(extract.call_count, 2)
        self.assertFalse((self.project/'work').exists())
        self.assertLessEqual(sum(len(text) for text in coverage_module._SOURCE_TEXT_CACHE.values()), coverage_module._SOURCE_TEXT_CACHE_LIMIT)

    def test_same_source_locator_quote_with_a_new_id_cannot_inflate_point_count(self):
        report = copy.deepcopy(self.report); duplicate = copy.deepcopy(report['points'][0]); duplicate['id'] = 'P99'
        report['points'].append(duplicate)
        with self.assertRaisesRegex(ValueError, '不能仅换id'):
            self.save(report)
        self.source.write_text(self.source.read_text()+'\n必须核对日期。')
        report['source_inventory'][0].update(sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(), read_scope='全部4行')
        report['points'][-1].update(locator='第4行', source_quote='必须核对日期。', disposition='omitted', script_quotes=[], reason='另一独立事实，合成稿尚未讲到，明确登记舍弃供人工决定')
        self.assertEqual(self.save(report)['statistics']['total'], 4)


if __name__ == '__main__':
    unittest.main()
