from pathlib import Path
from unittest import mock
import array
import json
import os
import shutil
import sys
import tempfile
import unittest
import wave

WORKBENCH = Path(__file__).resolve().parents[1] / 'skills/corporate-training-motion/workbench'
sys.path.insert(0, str(WORKBENCH))
import backend


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
class AudioReuseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        self.work = self.project/'work'
        self.work.mkdir()
        self.source = self.project/'voice.wav'
        self.doc = dict(media=dict(audio='voice.wav'), fps=30, sourceDurationFrames=30,
                        holds=[], cuts=[dict(startFrame=1,endFrame=2)], audio=dict(gain=1))
        self.workspace = object.__new__(backend.Workspace)
        self.workspace.project = self.project
        self.workspace.work = self.work
        self.workspace.file = self.project/'workbench.json'
        self.workspace.file.write_text(json.dumps(self.doc))
        self.write_source(1000)
        # Other tests own the full document validator; here exercise real audio I/O.
        patch = mock.patch.object(backend, 'validate')
        patch.start()
        self.addCleanup(patch.stop)

    def write_source(self, value):
        with wave.open(str(self.source), 'wb') as wav:
            wav.setparams((1,2,48000,0,'NONE','not compressed'))
            wav.writeframes(array.array('h', [value] * 48000).tobytes())

    def test_reuses_verified_audio_but_not_after_artifact_tampering(self):
        path = self.workspace.audio(self.doc)
        first_bytes = path.read_bytes()
        with mock.patch.object(backend.subprocess,'run',side_effect=AssertionError('valid cached audio was recomputed')):
            self.assertEqual(path, self.workspace.audio(self.doc))
        path.write_bytes(b'wrong bytes')
        self.assertEqual(path, self.workspace.audio(self.doc))
        self.assertEqual(first_bytes, path.read_bytes())

    def test_fps_and_same_stat_input_change_invalidate_cache(self):
        initial = self.workspace.audio_key(self.doc)
        self.assertNotEqual(initial, self.workspace.audio_key(dict(self.doc, fps=24)))
        before = self.source.stat()
        self.write_source(2000)
        os.utime(self.source, ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(before.st_size,self.source.stat().st_size)
        self.assertNotEqual(initial, self.workspace.audio_key(self.doc))

    def test_waveform_updates_after_source_change(self):
        original = self.workspace.waveform()
        with mock.patch.object(backend.subprocess,'run',side_effect=AssertionError('unchanged waveform was regenerated')):
            self.assertEqual(original,self.workspace.waveform())
        self.write_source(2000)
        changed = self.workspace.waveform()
        self.assertNotEqual(original['peaks'],changed['peaks'])
        self.assertNotEqual(original['source_sha256'],changed['source_sha256'])


if __name__ == '__main__':
    unittest.main()
