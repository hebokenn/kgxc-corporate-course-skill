"""Exercise the real trim/tempo order which previously truncated the pilot's last phrase."""
from pathlib import Path
import json
import math
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'))
from audio_timing import prepare,NarrationClock,timeline_errors


class AudioTimingTests(unittest.TestCase):
    def test_trim_precedes_tempo_and_frames_bind_to_measured_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'original.wav';out=Path(folder)/'candidate.wav'
            with wave.open(str(source),'wb') as w:
                w.setparams((1,2,24000,0,'NONE','not compressed'))
                w.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(i*2*math.pi*220/24000))) for i in range(48000)))
            record=prepare(source,out,rate=.5,start=.2,end=1.4,profile='fixture')
            self.assertAlmostEqual(record['duration_seconds'],2.4,delta=.08)
            clock=NarrationClock(record);self.assertEqual(clock.frame(.2),0);self.assertLessEqual(clock.frame(1.4),clock.frames)
            with self.assertRaisesRegex(ValueError,'超出'):clock.frame(1.6)
            self.assertEqual(prepare(source,out,rate=.5,start=.2,end=1.4,profile='fixture'),record)
            self.assertTrue(source.is_file());out.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'已改变'):NarrationClock(record)
    def test_last_caption_or_object_beyond_audio_fails_before_node_lookup(self):
        doc=dict(fps=30,sourceDurationFrames=1526,captions=[dict(id='last-cue',startFrame=1536,endFrame=1695)],scenes=[],sceneGraph=dict(nodes=[dict(id='goal',startFrame=1536,endFrame=1526)]))
        errors=timeline_errors(doc,50.85)
        self.assertTrue(any('last-cue' in e and '1536' in e for e in errors));self.assertTrue(any('goal' in e for e in errors))
        self.assertTrue(any('实际声音' in e for e in timeline_errors(doc,56.49)))


if __name__=='__main__':unittest.main()
