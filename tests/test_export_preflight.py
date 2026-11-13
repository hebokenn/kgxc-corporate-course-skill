"""Exercise the read-only probe and real short normalized seams with synthetic media."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/corporate-training-motion/scripts/export_preflight.py'


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires local FFmpeg')
class ExportPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.intro = self.make('intro.mp4', 'red', '96x64', 30)
        self.body = self.make('body.mp4', 'blue', '128x72', 24)
        self.outro = self.make('outro.mp4', 'green', '96x64', 30)

    def make(self, name, color, size, fps):
        path = self.root / name
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                        f'color={color}:size={size}:rate={fps}:duration=2',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)],
                       check=True, capture_output=True)
        return path

    def run_check(self, body, *flags):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--intro', str(self.intro),
                               '--body', str(body), '--outro', str(self.outro),
                               '--width', '96', '--height', '64', *flags],
                              text=True, capture_output=True)

    def test_mismatch_is_reported_but_normalized_trials_can_pass(self):
        prior = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.run_check(self.body, '--trial')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['stream_copy']['status'], 'normalize-required')
        self.assertFalse(report['stream_copy']['verified'])
        self.assertIn('width', {m['field'] for m in report['stream_copy']['mismatches']})
        for name in ('intro_body', 'body_outro'):
            self.assertEqual(report['trials'][name]['status'], 'passed')
            self.assertEqual(report['trials'][name]['decoded_frames'], 60)
        self.assertEqual(prior, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_matching_input_signatures_do_not_claim_verified_stream_copy(self):
        result = self.run_check(self.intro)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['stream_copy']['status'], 'matching-signatures-only')
        self.assertFalse(report['stream_copy']['verified'])
        self.assertEqual(report['trials'], {})

    def test_missing_media_fails_closed(self):
        result = self.run_check(self.root / 'missing.mp4')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')
