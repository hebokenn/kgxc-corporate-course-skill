"""Unit tests for v7.0.0 tts_sync and verify_delivery public tools."""
import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from PIL import Image

import tts_sync
import verify_delivery


def make_wav(path: Path, freq: int = 440, duration: float = 0.5, sample_rate: int = 24000, fade_out: bool = True):
    import math, struct
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(sample_rate * duration)
    frames = bytearray()
    for i in range(n):
        amp = 0.35
        if fade_out and i > n * 0.8:
            amp *= max(0.0, (n - i) / (n * 0.2))
        sample = int(amp * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        frames.extend(struct.pack('<h', sample))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


class V7ToolsTests(unittest.TestCase):
    def test_tts_sync_incremental_cache_mix_and_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            calls = []

            def fake_run(cmd, **kwargs):
                out_idx = cmd.index('--out') + 1
                txt_idx = cmd.index('--text-file') + 1
                calls.append(Path(cmd[txt_idx]).read_text(encoding='utf-8'))
                make_wav(Path(cmd[out_idx]), duration=0.4)

            lines = [
                {'id': 'b1', 'voice': 'didi', 'role': '旁白', 'text': '欢迎来到酷果星创企业培训课堂！'},
                {'id': 'b2', 'voice': 'pipi', 'role': '店员', 'text': '您好，请问有什么可以帮您？'},
            ]
            real_run = subprocess.run
            with patch('tts_sync.subprocess.run', side_effect=lambda cmd, **kwargs: fake_run(cmd, **kwargs) if 'qwen3_tts.py' in str(cmd) else real_run(cmd, **kwargs)):
                first = tts_sync.synthesize_beats(lines, p / 'audio', mix_out=p / 'mix.wav', srt_out=p / 'sub.srt')
                self.assertEqual(len(calls), 2)
                self.assertTrue((p / 'mix.wav').is_file())
                srt = (p / 'sub.srt').read_text(encoding='utf-8')
                self.assertNotIn('！', srt)
                self.assertNotIn('？', srt)

                # Re-running with only b2 edited must reuse b1 without calling TTS again.
                lines[1]['text'] = '您好，欢迎光临！'
                second = tts_sync.synthesize_beats(lines, p / 'audio', mix_out=p / 'mix.wav', srt_out=p / 'sub.srt')
                self.assertEqual(len(calls), 3)
                self.assertTrue(second['lines'][0]['reused'])
                self.assertFalse(second['lines'][1]['reused'])

    def test_verify_delivery_detects_first_frame_cover_and_srt_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cover = p / 'cover.png'
            Image.new('RGB', (1920, 1080), '#cc2233').save(cover)
            body = p / 'body.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=#224488:s=1920x1080:r=24:d=0.5',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=0.5',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(body),
            ], check=True)
            final = p / 'final.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y', '-i', str(body), '-loop', '1', '-framerate', '24', '-i', str(cover),
                '-filter_complex', "[0:v][1:v]overlay=shortest=1:enable='eq(n,0)'[v]",
                '-map', '[v]', '-map', '0:a:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(final),
            ], check=True)
            srt = p / 'final.srt'
            srt.write_text('1\n00:00:00,050 --> 00:00:00,450\n欢迎来到酷果星创企业培训课堂\n\n', encoding='utf-8')

            ok_report = verify_delivery.verify_video(final, srt=srt, cover=cover)
            self.assertTrue(ok_report['ok'], ok_report)

            # Punctuation in SRT must fail
            srt.write_text('1\n00:00:00,050 --> 00:00:00,450\n欢迎来到酷果星创！\n\n', encoding='utf-8')
            bad_srt = verify_delivery.verify_video(final, srt=srt, cover=cover)
            self.assertFalse(bad_srt['ok'])
            self.assertTrue(any('标点' in e for e in bad_srt['errors']))

            # Cover lingering onto frame 1 must fail
            lingering = p / 'lingering.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y', '-i', str(body), '-loop', '1', '-framerate', '24', '-i', str(cover),
                '-filter_complex', "[0:v][1:v]overlay=shortest=1:enable='lt(n,5)'[v]",
                '-map', '[v]', '-map', '0:a:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(lingering),
            ], check=True)
            bad_cover = verify_delivery.verify_video(lingering, cover=cover)
            self.assertFalse(bad_cover['ok'])
            self.assertTrue(any('第 1 帧' in e for e in bad_cover['errors']))

    def test_production_preferences_accepts_v7_and_legacy_ids(self):
        import sys
        workbench_dir = Path(__file__).resolve().parents[1] / 'workbench'
        if str(workbench_dir) not in sys.path:
            sys.path.insert(0, str(workbench_dir))
        import production_preferences as prefs
        from acting import stage as stage_cute_actor
        import test_new_course_workbench as fixture

        f = fixture.NewCourseTests()
        f.setUp()
        try:
            for customer_choice in ('C_M01', 'C_F01', 'vector_actor_layered'):
                res = prefs.update(f.p, 'customer', customer_choice, 'human')
                self.assertEqual(res['choices']['customer'], customer_choice)
            res = prefs.update(f.p, 'flower_text', 'enabled', 'human')
            self.assertEqual(res['choices']['flower_text'], 'enabled')
            res = prefs.update(f.p, 'sound_effects', 'enabled_teaching_native_v1', 'human')
            self.assertEqual(res['choices']['sound_effects'], 'enabled_teaching_native_v1')
            self.assertEqual(prefs.selection_errors(f.p), [])

            cust = stage_cute_actor(dict(
                identity='C_F01', sceneId='X', characterRole='customer', hair='bob', x=320, floorY=760, height=520, endFrame=30
            ), f.p, Path(__file__).resolve().parents[1])
            txt = dict(id='kw-1', type='text', sceneId='X', text='真实花字', x=200, y=200, fontSize=42, fill='#111111')
            doc = dict(
                media=dict(audio='audio/line.wav'),
                sceneGraph=dict(nodes=[cust['node'], txt]),
            )
            audio = f.p / 'audio/line.wav'
            make_wav(audio, freq=440, duration=0.3)
            sfx_stem = f.p / 'audio/sfx-stem.wav'
            make_wav(sfx_stem, freq=880, duration=0.3)
            audio.with_suffix('.json').write_text(json.dumps(dict(
                palette='teaching-native-v1',
                mix_sha256=prefs.sha(audio),
                events=2,
                appliedGains=[-12.0],
                sfxStem='audio/sfx-stem.wav',
            )))
            errs = prefs.material_errors(
                f.p,
                f.p / 'delivery/final.mp4',
                prefs.load(f.p)['choices'],
                dict(flower_nodes=['kw-1'], customer_nodes=['C_F01']),
                document=doc,
            )
            self.assertEqual(errs, [])
        finally:
            f.tearDown()


if __name__ == '__main__':
    unittest.main()
