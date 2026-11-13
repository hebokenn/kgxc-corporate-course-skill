"""Review reuse, single-flight execution and file-change invalidation regressions."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workbench'))
import performance_cache as cache


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache._RESULTS.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project/'qa').mkdir()
        self.video = self.project/'candidate.mp4'
        self.video.write_bytes(b'candidate')
        self.doc = dict(title='test', scenes=[])
        (self.project/'workbench.json').write_text(json.dumps(self.doc))

    def tearDown(self):
        self.temp.cleanup()
        cache._RESULTS.clear()

    def test_sha_reuses_bytes_and_detects_same_size_edit_with_restored_mtime(self):
        self.assertEqual(cache.sha(self.video), hashlib.sha256(b'candidate').hexdigest())
        with mock.patch.object(Path, 'open', side_effect=AssertionError('unchanged file was read again')):
            self.assertEqual(cache.sha(self.video), hashlib.sha256(b'candidate').hexdigest())
        stamp = self.video.stat()
        self.video.write_bytes(b'different')
        os.utime(self.video, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(cache.sha(self.video), hashlib.sha256(b'different').hexdigest())
        self.video.unlink()
        with self.assertRaises(FileNotFoundError):
            cache.sha(self.video)

    def test_native_fingerprint_preserves_approval_algorithm_and_tracks_added_files(self):
        from authoring import native_fingerprint as original
        folder = self.project/'assets'
        folder.mkdir()
        asset = folder/'one.txt'
        asset.write_text('one')
        expected = original(self.project)
        self.assertEqual(cache.native_fingerprint(self.project), expected)
        with mock.patch('authoring.native_fingerprint', side_effect=AssertionError('fingerprint was recalculated')):
            self.assertEqual(cache.native_fingerprint(self.project), expected)
        (folder/'two.txt').write_text('two')
        self.assertNotEqual(cache.native_fingerprint(self.project), expected)
        self.assertEqual(cache.native_fingerprint(self.project), original(self.project))
        asset.unlink()
        self.assertEqual(cache.native_fingerprint(self.project), original(self.project))

    def test_review_changes_invalidate_without_mutating_cached_results(self):
        evidence = self.project/'qa/frame.png'
        evidence.write_bytes(b'evidence')
        cover = self.project/'cover.png'
        cover.write_bytes(b'cover')
        poster_video = self.project/'player.mp4'
        poster_video.write_bytes(b'player-video')
        page = self.project/'player.html'
        page.write_text('<video src="player.mp4" poster="cover.png"></video>')
        record = self.project/'qa/cover-review.json'
        record.write_text(json.dumps(dict(pagePath='player.html', coverPath='cover.png',
                                         evidenceFrames=[dict(path='qa/frame.png')])))
        with mock.patch('motion_quality.director_review', return_value=dict(status='pass', errors=[])) as validate:
            def review():
                return cache.director_review(self.project, self.doc, self.video)
            result = review()
            result['errors'].append('caller edit')
            self.assertEqual(review()['errors'], [])
            self.assertEqual(validate.call_count, 1)
            for path in [evidence, cover, poster_video, page, record, self.video, self.project/'workbench.json']:
                before = validate.call_count
                path.write_bytes(path.read_bytes()+b' ')
                review()
                self.assertEqual(validate.call_count, before+1, str(path))
                review()
                self.assertEqual(validate.call_count, before+1)
            marker = self.project/'craft-contract.json'
            marker.write_text('{}')
            review()
            before = validate.call_count
            marker.unlink()
            review()
            self.assertEqual(validate.call_count, before+1)
            before = validate.call_count
            self.doc['title'] = 'changed in memory'
            review()
            self.assertEqual(validate.call_count, before+1)
            before = validate.call_count
            evidence.unlink()
            review()
            self.assertEqual(validate.call_count, before+1)

    def test_concurrent_requests_run_expensive_review_once(self):
        calls = 0
        barrier = threading.Barrier(8)

        def expensive(*args):
            nonlocal calls
            calls += 1
            time.sleep(.05)
            return dict(status='pending', errors=['still requires review'])

        def request(_):
            barrier.wait(timeout=3)
            return cache.director_review(self.project, self.doc, self.video)

        with mock.patch('motion_quality.director_review', side_effect=expensive):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(request, range(8)))
        self.assertEqual(calls, 1)
        self.assertTrue(all(r['status'] == 'pending' for r in results))

    def test_replacement_and_mid_check_change_cannot_reuse_success(self):
        cache.sha(self.video)
        stamp = self.video.stat()
        replacement = self.project/'replacement'
        replacement.write_bytes(b'different')
        os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        replacement.replace(self.video)
        self.assertEqual(cache.sha(self.video), hashlib.sha256(b'different').hexdigest())

        def change(*args):
            self.video.write_bytes(b'changed again')
            return dict(status='pass', errors=[])

        with mock.patch('motion_quality.director_review', side_effect=change):
            with self.assertRaisesRegex(OSError, '文件已变化'):
                cache.director_review(self.project, self.doc, self.video)
        with mock.patch('motion_quality.director_review', return_value=dict(status='pending', errors=['new evidence'])) as check:
            self.assertEqual(cache.director_review(self.project, self.doc, self.video)['status'], 'pending')
            self.assertEqual(check.call_count, 1)

    def test_failed_checks_are_retried_and_cache_is_bounded(self):
        with mock.patch('motion_quality.director_review', side_effect=[OSError('temporary'), dict(status='pending')]) as check:
            with self.assertRaises(OSError):
                cache.director_review(self.project, self.doc, self.video)
            self.assertEqual(cache.director_review(self.project, self.doc, self.video)['status'], 'pending')
            self.assertEqual(check.call_count, 2)
        with mock.patch.object(cache, '_LIMIT', 4):
            for i in range(10):
                path = self.project/str(i)
                path.write_text(str(i))
                cache.sha(path)
            self.assertLessEqual(len(cache._RESULTS), 4)


if __name__ == '__main__':
    unittest.main()
