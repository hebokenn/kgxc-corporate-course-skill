"""Copy/cleanup fixtures test file safety, not video or aesthetic quality."""
from contextlib import nullcontext
from pathlib import Path
import copy
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'plugin'),str(ROOT/'skills/corporate-training-motion/workbench')]
from delivery import deliver,completed,digest,cleanup_preview,retention,open_saved_folder
from workflow import atomic


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.workspace=self.base/'workspace';root=self.workspace/'courses/fixture';project=root/'project'
        for folder in ['project/qa','inputs','delivery','packages']:(root/folder).mkdir(parents=True)
        (root/'delivery/final.mp4').write_bytes(b'COPY TEST ONLY: not a real video');(root/'delivery/final.srt').write_text('COPY TEST subtitle');(project/'cover.png').write_bytes(b'COPY TEST cover')
        (root/'inputs/original.txt').write_text('original business source')
        (project/'source').mkdir();(project/'source/transcript.md').write_text('人工逐字稿须保留')
        (project/'qa/pilot.mp4').write_bytes(b'pilot fixture');(root/'packages/work.zip').write_bytes(b'editable fixture')
        atomic(project/'qa/cover-review.json',dict(coverPath='cover.png',coverSha256=digest(project/'cover.png')))
        atomic(root/'delivery/final.json',dict(video_sha256=digest(root/'delivery/final.mp4'),playback=dict(chapters=[dict(title='技术夹具',start=0)])))
        self.state=dict(stage='complete',course_id='a'*32,title='独立交付夹具',revision=9,gates=[dict(id='final',status='delivered')],jobs=[],artifacts=dict(final=['../delivery/final.mp4','../delivery/final.srt']),plan=dict(sources=[dict(location='../inputs/original.txt')]))
        class Fixture:
            def __init__(inside):inside.root=root;inside.project=project
            def locked(inside):return nullcontext()
            def status(inside):return copy.deepcopy(self.state)
            def relative(inside,name):return (project/name).resolve()
        # These unit tests isolate copy/retention safety; the real production gate
        # is exercised without mocks in test_production_contract_entrypoints.py.
        self.contract_gate=patch('production.require_contract',return_value=dict(required=False,ready=True));self.contract_gate.start()
        self.addCleanup(self.contract_gate.stop)
        self.course=Fixture();self.env=patch.dict(os.environ,{'COURSE_CONFIG_DIR':str(self.base/'config')});self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_delivery_preserves_transcript_samples_and_engineering_by_default(self):
        result=deliver(self.course,self.workspace,self.base/'Desktop/ai 制课')
        self.assertTrue(result['delivery_only']);self.assertTrue(self.course.root.exists())
        value=result['delivery'];self.assertEqual(value['cleanup_status'],'retained');self.assertEqual(len(value['files']),3)
        for file in value['files']:self.assertEqual(digest(file['path']),file['sha256'])
        self.assertEqual((self.course.project/'source/transcript.md').read_text(),'人工逐字稿须保留')
        self.assertTrue((self.course.project/'qa/pilot.mp4').is_file());self.assertTrue((self.course.root/'packages/work.zip').is_file())
        self.assertEqual(completed(self.course.root)['delivery']['chapters'][0]['title'],'技术夹具')
        self.assertNotIn('transcript',json.dumps(value));self.assertNotIn('studio-content',json.dumps(value))
    def test_incomplete_or_busy_work_cannot_be_cleaned(self):
        self.state['stage']='final'
        with self.assertRaisesRegex(ValueError,'校验'):deliver(self.course,self.workspace,self.base/'desktop')
        self.state['stage']='complete';self.state['jobs']=[dict(status='rendering')]
        with self.assertRaisesRegex(ValueError,'任务尚未结束'):deliver(self.course,self.workspace,self.base/'desktop')
        self.assertTrue(self.course.root.is_dir())
    def test_unknown_files_and_missing_originals_are_preserved_for_review(self):
        unknown=self.course.root/'keep-me.txt';unknown.write_text('protected')
        deliver(self.course,self.workspace,self.base/'desktop')
        with self.assertRaisesRegex(ValueError,'未识别'):cleanup_preview(self.course,self.workspace)
        self.assertEqual(unknown.read_text(),'protected');unknown.unlink();(self.course.root/'inputs/original.txt').unlink();self.state['revision']+=1
        with self.assertRaisesRegex(ValueError,'原始资料'):deliver(self.course,self.workspace,self.base/'desktop')
        self.assertTrue((self.course.root/'delivery/final.mp4').is_file())
    def test_failed_media_copy_keeps_engineering_and_removes_its_staging_folder(self):
        import delivery
        real=delivery.copy_verified
        def copy(source,target):
            if source.suffix=='.mp4':raise OSError('injected copy failure')
            return real(source,target)
        with patch.object(delivery,'copy_verified',copy):
            with self.assertRaises(OSError):deliver(self.course,self.workspace,self.base/'desktop')
        self.assertTrue(self.course.root.is_dir());self.assertFalse(list((self.base/'desktop').iterdir()));self.assertIsNone(completed(self.course.root))
    def test_repeat_save_reuses_verified_desktop_delivery_without_deleting_work(self):
        first=deliver(self.course,self.workspace,self.base/'desktop')
        second=deliver(self.course,self.workspace,self.base/'desktop')
        self.assertEqual(first['delivery']['delivery_root'],second['delivery']['delivery_root']);self.assertEqual(len(list((self.base/'desktop').iterdir())),1)
        self.assertTrue((self.course.project/'source/transcript.md').is_file())
    def test_keep_later_and_unanswered_preview_never_delete(self):
        deliver(self.course,self.workspace,self.base/'desktop');preview=cleanup_preview(self.course,self.workspace)
        self.assertGreater(preview['preview']['file_count'],3);self.assertTrue(self.course.root.is_dir())
        with self.assertRaisesRegex(ValueError,'明确确认'):retention(self.course,self.workspace,'delete-process-files')
        self.assertEqual(retention(self.course,self.workspace,'later')['delivery']['cleanup_status'],'deferred')
        self.assertEqual(retention(self.course,self.workspace,'keep')['delivery']['cleanup_status'],'retained');self.assertTrue((self.course.project/'source/transcript.md').is_file())
    def test_explicit_current_cleanup_inventory_removes_only_this_course_after_preserving_originals(self):
        deliver(self.course,self.workspace,self.base/'desktop');preview=cleanup_preview(self.course,self.workspace)['preview']
        result=retention(self.course,self.workspace,'delete-process-files',preview['request_id']);self.assertFalse(self.course.root.exists());self.assertEqual(result['delivery']['cleanup_status'],'complete')
        self.assertEqual(Path(result['delivery']['originals'][0]['path']).read_text(),'original business source')
        for file in result['delivery']['files']:self.assertEqual(digest(file['path']),file['sha256'])
    def test_changed_process_files_or_revision_require_another_visible_inventory(self):
        deliver(self.course,self.workspace,self.base/'desktop');preview=cleanup_preview(self.course,self.workspace)['preview']
        draft=self.course.project/'source/transcript.md';draft.write_text('用户新改的逐字稿')
        with self.assertRaisesRegex(ValueError,'已变化'):retention(self.course,self.workspace,'delete-process-files',preview['request_id'])
        preview=cleanup_preview(self.course,self.workspace)['preview'];self.state['revision']+=1
        with self.assertRaisesRegex(ValueError,'已变化'):retention(self.course,self.workspace,'delete-process-files',preview['request_id'])
        self.assertEqual(draft.read_text(),'用户新改的逐字稿')
    def test_explicit_keep_policy_is_saved_and_damaged_desktop_media_blocks_cleanup(self):
        atomic(self.course.project/'retention-policy.json',dict(mode='keep',evidence='用户要求保留所有过程文件',actor='user'))
        value=deliver(self.course,self.workspace,self.base/'desktop')['delivery'];self.assertEqual(value['cleanup_decision']['choice'],'keep')
        Path(value['files'][0]['path']).write_bytes(b'changed final')
        with self.assertRaisesRegex(ValueError,'桌面成品'):cleanup_preview(self.course,self.workspace)
        self.assertTrue(self.course.root.exists())
    def test_versions_is_known_history_and_remains_until_explicit_cleanup(self):
        history=self.course.root/'versions';history.mkdir();(history/'0001.json').write_text('{"historical":true}')
        deliver(self.course,self.workspace,self.base/'desktop');preview=cleanup_preview(self.course,self.workspace)['preview']
        self.assertGreater(next(g for g in preview['groups'] if g['label']=='小样、审阅版与旧版本')['files'],1)
        retention(self.course,self.workspace,'keep');self.assertTrue((history/'0001.json').is_file())
        result=retention(self.course,self.workspace,'delete-process-files',preview['request_id'])
        self.assertEqual(result['delivery']['cleanup_status'],'complete');self.assertFalse(self.course.root.exists())
    def test_unknown_cleanup_files_do_not_block_keep_or_later(self):
        unknown=self.course.root/'unrecognized.txt';unknown.write_text('keep this')
        deliver(self.course,self.workspace,self.base/'desktop')
        with self.assertRaisesRegex(ValueError,'未识别'):cleanup_preview(self.course,self.workspace)
        self.assertEqual(retention(self.course,self.workspace,'keep')['delivery']['cleanup_status'],'retained')
        self.assertEqual(retention(self.course,self.workspace,'later')['delivery']['cleanup_status'],'deferred')
        self.assertEqual(unknown.read_text(),'keep this')
    def test_open_saved_folder_uses_the_verified_receipt_location(self):
        result=deliver(self.course,self.workspace,self.base/'desktop')
        with patch('delivery.sys.platform','darwin'),patch('delivery.subprocess.run') as opened:
            value=open_saved_folder(self.course.root)
            self.assertEqual(value['folder'],result['delivery']['delivery_root']);self.assertTrue(value['verified'])
            opened.assert_called_once_with(['open',value['folder']],check=True,capture_output=True)
        Path(result['delivery']['files'][0]['path']).write_bytes(b'tampered')
        with patch('delivery.subprocess.run') as opened:
            with self.assertRaisesRegex(ValueError,'已改变'):open_saved_folder(self.course.root)
            opened.assert_not_called()
    @unittest.skipUnless(hasattr(os,'chflags') and hasattr(stat,'UF_HIDDEN'),'macOS BSD visibility flags')
    def test_delivery_and_repeat_save_clear_hidden_flags_on_folder_and_all_three_files(self):
        for source in [self.course.root/'delivery/final.mp4',self.course.root/'delivery/final.srt',self.course.project/'cover.png']:
            os.chflags(source,source.stat().st_flags|stat.UF_HIDDEN)
        first=deliver(self.course,self.workspace,self.base/'desktop')['delivery']
        paths=[Path(first['delivery_root']),*[Path(f['path'])for f in first['files']]]
        self.assertTrue(all(not p.stat().st_flags&stat.UF_HIDDEN for p in paths))
        for p in paths:os.chflags(p,p.stat().st_flags|stat.UF_HIDDEN)
        second=deliver(self.course,self.workspace,self.base/'desktop')['delivery']
        self.assertEqual(first['delivery_root'],second['delivery_root'])
        self.assertTrue(all(not p.stat().st_flags&stat.UF_HIDDEN for p in paths))
        self.assertTrue(all(digest(f['path'])==f['sha256'] for f in second['files']))


if __name__=='__main__':unittest.main()
