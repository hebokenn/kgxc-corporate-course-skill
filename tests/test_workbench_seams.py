"""Bounded native seam checks: exact edited clocks and actual FFmpeg A/V."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from render_worker import packaging_windows,seam_preflight


class WorkbenchSeamTests(unittest.TestCase):
    document=dict(fps=24,sourceDurationFrames=24,introFrames=6,bodyEndFrame=18,holds=[],cuts=[])

    def test_cuts_and_holds_use_retained_display_clock(self):
        doc=dict(self.document,holds=[dict(sourceFrame=6,frames=4)],cuts=[dict(startFrame=14,endFrame=17)])
        self.assertEqual([(x['first'],x['edge'],x['last'],x['left'],x['right']) for x in packaging_windows(doc)],
                         [(7,10,13,'intro','native'),(16,19,22,'native','outro')])
        self.assertEqual(packaging_windows(dict(self.document,introFrames=0,bodyEndFrame=24)),[])
        with self.assertRaisesRegex(ValueError,'缺少预定包装或正文：intro'):
            packaging_windows(dict(self.document,cuts=[dict(startFrame=0,endFrame=6)]))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'requires FFmpeg')
    def test_real_encoders_mux_both_boundaries_and_reject_wrong_renderer_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            frames={}
            for kind,color in [('intro','red'),('native','green'),('outro','blue')]:
                jpeg=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=1920x1080',
                                              '-frames:v','1','-threads','1','-c:v','mjpeg','-f','image2pipe','-'])
                frames[kind]=base64.b64encode(jpeg).decode()
            audio=out/'audio.wav'
            with wave.open(str(audio),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*48000)
            class FixtureCanvas:
                def evaluate(self,script,args):
                    f=args['frame'];kind='intro' if f<6 else 'native' if f<18 else 'outro'
                    return dict(kind=kind,source=f,jpeg=frames[kind])
            report=seam_preflight(FixtureCanvas(),out,self.document,audio,24.0)
            self.assertEqual(report['status'],'pass')
            self.assertEqual([x['edge'] for x in report['seams']],[6,18])
            for seam in report['seams']:
                clip=out/seam['clip']
                self.assertEqual(hashlib.sha256(clip.read_bytes()).hexdigest(),seam['sha256'])
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(clip)]))
                self.assertEqual([stream['codec_name'] for stream in probe['streams']],['h264','aac'])
                self.assertGreater(seam['verified_aac_packets'],0)
            class WrongCanvas:
                def evaluate(self,script,args):
                    return dict(kind='outro',source=args['frame'],jpeg=frames['outro'])
            other=out/'wrong';other.mkdir()
            with self.assertRaisesRegex(ValueError,'实际画面段落与时间轴不一致'):
                seam_preflight(WrongCanvas(),other,self.document,audio,24.0)
            self.assertEqual(list(other.rglob('*.mp4')),[])
