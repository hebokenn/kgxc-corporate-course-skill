"""Draft edits must never overwrite approved inputs, encode media, or lose newer work."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/corporate-training-motion/workbench'))
from script_editor import ScriptEditor


class ScriptEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name); self.project = self.root / 'project'
        (self.project / 'source').mkdir(parents=True)
        self.source = self.project / 'source/transcript.md'; self.source.write_text('先核对订单。\n\n再核对商品编码。')
        self.doc = self.project / 'workbench.json'; self.doc.write_text(json.dumps(dict(title='合成课程',scenes=[],revision=3)))
        self.editor = ScriptEditor(SimpleNamespace(root=self.root,project=self.project,file=self.doc))

    def tearDown(self): self.temp.cleanup()

    def test_manual_draft_is_persistent_and_does_not_render_or_change_official_input(self):
        official = self.source.read_bytes(); document = self.doc.read_bytes()
        result = self.editor.save('核对订单后，再检查编码。',0)
        self.assertEqual(result['revision'],1); self.assertTrue(result['changed'])
        self.assertEqual(self.source.read_bytes(),official); self.assertEqual(self.doc.read_bytes(),document)
        self.assertEqual(self.editor.read()['text'],result['text'])
        self.assertEqual(list(self.project.glob('**/*.mp4')),[])
        self.assertNotIn('render_request',result)

    def test_two_windows_reject_stale_write_and_preserve_newer_text(self):
        self.editor.save('窗口一的修改',0)
        with self.assertRaises(FileExistsError): self.editor.save('窗口二旧稿',0)
        self.assertEqual(self.editor.read()['text'],'窗口一的修改')

    def test_legacy_draft_without_baseline_is_read_without_writes_and_cannot_overwrite(self):
        self.editor.path.write_text(json.dumps(dict(revision=3,text='旧版人工草稿')))
        before = self.editor.path.read_bytes(); official = self.source.read_bytes()
        state = self.editor.read()
        self.assertEqual(state['text'], '旧版人工草稿'); self.assertEqual(state['revision'], 3)
        self.assertTrue(state['base_changed'])
        with self.assertRaises(FileExistsError): self.editor.save('不能猜测合并', 3)
        self.assertEqual(self.editor.path.read_bytes(), before); self.assertEqual(self.source.read_bytes(), official)

    def test_external_ai_script_change_does_not_overwrite_unsaved_draft(self):
        self.editor.save('手工草稿',0); self.source.write_text('AI 已更新正式稿')
        state = self.editor.read(); self.assertTrue(state['base_changed']); self.assertEqual(state['text'],'手工草稿')
        with self.assertRaises(FileExistsError): self.editor.save('继续手工改',1)

    def test_render_freezes_click_time_text_and_rejects_duplicates(self):
        self.editor.save('点击时的稿件',0); request = self.editor.request_render(1)
        self.editor.save('之后继续修改的稿件',1)
        state = self.editor.read()
        self.assertEqual(state['render_request']['text'],'点击时的稿件'); self.assertEqual(state['text'],'之后继续修改的稿件')
        with self.assertRaises(ValueError): self.editor.request_render(2)
        with self.assertRaises(FileExistsError): self.editor.render_update('wrong','complete')
        self.editor.render_update(request['id'],'failed',error='缺少确认的视觉方案')
        self.assertEqual(self.editor.read()['render_request']['status'],'failed')

    def test_expected_render_commit_preserves_edits_made_after_click(self):
        self.editor.save('点击渲染的稿件',0); self.editor.request_render(1)
        self.editor.save('渲染期间的新修改',1)
        self.source.write_text('点击渲染的稿件')
        state = self.editor.read()
        self.assertFalse(state['base_changed']); self.assertEqual(state['text'],'渲染期间的新修改')
        self.assertEqual(state['base_text'],'点击渲染的稿件')
        self.editor.save('继续编辑新稿',state['revision'])
        self.assertEqual(self.editor.read()['text'],'继续编辑新稿')

    def test_clean_editor_adopts_new_official_script_but_not_user_draft(self):
        self.editor.save(self.source.read_text(),0); self.source.write_text('新的正式稿')
        self.assertEqual(self.editor.read()['text'],'新的正式稿')
        self.assertFalse(self.editor.read()['base_changed'])


if __name__ == '__main__': unittest.main()
