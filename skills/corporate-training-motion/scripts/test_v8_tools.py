"""Unit tests for v8.0.0 cinematic director engine, strict actor contracts, anti-cheat gates, and telemetry audit."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_v7_tools
import tts_sync
import verify_delivery

SKILL_ROOT = Path(__file__).resolve().parents[1]
MOTION_DIR = SKILL_ROOT / 'workbench/motion'


class V8SkillTests(unittest.TestCase):
    def test_js_actor_contracts_collision_avoidance_and_director_stage(self):
        script = f"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const noop = () => {{}};
const mockCtx = new Proxy({{
  measureText: (t) => ({{ width: String(t || '').length * 22 }}),
  createLinearGradient: () => ({{ addColorStop: noop }}),
  createRadialGradient: () => ({{ addColorStop: noop }}),
}}, {{ get: (obj, prop) => (prop in obj ? obj[prop] : noop) }});

const sandbox = {{ console, Math, Object, Array, Number, String, Boolean, Error, Map, Set, Proxy }};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
const ctx = vm.createContext(sandbox);

for (const name of ['actors_v3_cute.js', 'visual_metaphors.js', 'director_stage.js']) {{
  const code = fs.readFileSync({json.dumps(str(MOTION_DIR))} + '/' + name, 'utf8');
  vm.runInContext(code, ctx, {{ filename: name }});
}}

const CA = sandbox.CourseActorsCute;
const VM = sandbox.VisualMetaphors;
const DS = sandbox.DirectorStage;

// 1. Floating walk params (walkPhase/strideAmp) MUST throw
assert.throws(() => {{
  CA.paintExpressive(mockCtx, CA.PRESETS.staff_bun, {{
    x: 600, footY: 850, scale: 1.72, facing: 1, walkPhase: 1.2, strideAmp: 1, t: 1,
  }});
}}, /walkPhase|walkState/);

// 2. Unknown mood or gesture MUST throw
assert.throws(() => {{
  CA.paint(mockCtx, CA.PRESETS.staff_bun, {{ x: 600, footY: 850, scale: 1.72, mood: 'alien_rage' }});
}}, /unsupported mood/);
assert.throws(() => {{
  CA.paint(mockCtx, CA.PRESETS.staff_bun, {{ x: 600, footY: 850, scale: 1.72, gesture: 'backflip' }});
}}, /unsupported gesture/);

// 3. Valid grounded walk + expanded moods/gestures + bounds return succeed
const ws = CA.computeMoodWalk(420, 720, 0.5, 0, 'brisk', 1.72);
const bStaff = CA.paintExpressive(mockCtx, CA.PRESETS.staff_bun, {{
  x: ws.x, footY: 850, scale: 1.72, facing: 1, walkState: ws, mood: 'happy', gesture: 'explain', t: 0.5,
}});
assert.ok(bStaff && bStaff.headRect.w > 100 && bStaff.exclusionRect.h > 300);

const bCust = CA.paintExpressive(mockCtx, CA.PRESETS.cust_male_glasses, {{
  x: 1230, footY: 850, scale: 1.72, facing: -1, mood: 'anxious', gesture: 'worry', t: 0.5,
}});
assert.ok(bCust.rootX === 1230);

// 4. drawSpeedLines MUST reject pixel coordinates passed as progress
assert.throws(() => {{
  VM.drawSpeedLines(mockCtx, 1300, 540, 1, 0.45);
}}, /progress must be/);
VM.drawSpeedLines(mockCtx, 0.4, -1, '#B32B3A', 7);

// 5. placeAvoidingActors shifts danmaku pill OFF customer face
const collidingPill = {{ x: 1145, y: 460, w: 180, h: 48 }};
const safePill = VM.placeAvoidingActors(collidingPill, [bCust.exclusionRect]);
assert.equal(VM.rectOverlapArea(safePill, bCust.headRect), 0);

// 6. DirectorStage dual-layer timeline keeps sceneT continuous across multi-beat scenes
const lines = [
  {{ id: 'b1', scene_id: 's1', scene: 'store', layout_kind: 'cinematic_store', start: 0.0, end: 3.0 }},
  {{ id: 'b2', scene_id: 's1', scene: 'store', layout_kind: 'cinematic_store', start: 3.2, end: 6.0 }},
];
const r1 = DS.resolveTimeline(lines, 1.5);
const r2 = DS.resolveTimeline(lines, 4.0);
assert.equal(r1.sceneId, 's1');
assert.equal(r2.sceneId, 's1');
assert.equal(r1.isSceneEntry, true);
assert.equal(r2.isSceneEntry, false);
assert.ok(Math.abs(r2.sceneT - 4.0) < 0.01 && Math.abs(r2.beatT - 0.8) < 0.01);

// 7. DirectorStage camera keyframe interpolation
const cam = DS.evalCamera([
  {{ at: 0, x: -40, y: 0, zoom: 1.0 }},
  {{ at: 2, x: 40, y: -20, zoom: 1.18, ease: 'linear' }},
], 1.0);
assert.ok(Math.abs(cam.x - 0) < 0.1 && Math.abs(cam.zoom - 1.09) < 0.01);

// 8. Frame auditor detects floating walk & text-actor overlap
const aud = DS.createFrameAuditor();
aud.beginFrame(0, 0.0, r1, 'cinematic_store', {{ x: 0, y: 0, zoom: 1.0 }});
aud.recordActor('staff', CA.getActorBounds({{ x: 500, footY: 850, scale: 1.72 }}), null);
aud.recordText('danmaku1', {{ x: 460, y: 460, w: 180, h: 48 }}, 'danmaku');
aud.beginFrame(1, 0.04, r1, 'cinematic_store', {{ x: 0, y: 0, zoom: 1.0 }});
aud.recordActor('staff', CA.getActorBounds({{ x: 530, footY: 850, scale: 1.72 }}), null);
const report = aud.finalize();
assert.equal(report.floating_walk_violations.length, 1);
assert.equal(report.text_actor_overlap_violations.length, 1);
console.log('JS_V8_OK');
"""
        proc = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('JS_V8_OK', proc.stdout)

    def test_tts_sync_blocks_cloned_scene_subbeats_and_bubble_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)

            def fake_run(cmd, **kwargs):
                out_idx = cmd.index('--out') + 1
                test_v7_tools.make_wav(Path(cmd[out_idx]), duration=0.4)

            real_run = subprocess.run
            cloned_lines = [
                {'id': 'b1', 'voice': 'didi', 'role': '旁白', 'text': '第一句解说内容。', 'scene_id': 's1', 'params': {'stage': 1}},
                {'id': 'b2', 'voice': 'didi', 'role': '旁白', 'text': '第二句拆出来的子句。', 'scene_id': 's1', 'params': {'stage': 1}},
            ]
            with patch('tts_sync.subprocess.run', side_effect=lambda cmd, **kwargs: fake_run(cmd, **kwargs) if 'qwen3_tts.py' in str(cmd) else real_run(cmd, **kwargs)):
                with self.assertRaisesRegex(ValueError, '雷同'):
                    tts_sync.synthesize_beats(cloned_lines, p / 'audio1', strict_beats=True)

                # Distinct visual_cue allows sharing scene_id cleanly
                cloned_lines[0]['visual_cue'] = '展示左半区'
                cloned_lines[1]['visual_cue'] = '点亮右半区对比'
                ok = tts_sync.synthesize_beats(cloned_lines, p / 'audio2', strict_beats=True)
                self.assertEqual(len(ok['lines']), 2)

                # Mismatched dialogue bubble must fail
                bad_bubble = [
                    {'id': 'b3', 'voice': 'pipi', 'role': '店员', 'text': '顺手递样机让他点两下。', 'speaker_bubble': '欢迎光临请问看哪款手机'},
                ]
                with self.assertRaisesRegex(ValueError, '气泡'):
                    tts_sync.synthesize_beats(bad_bubble, p / 'audio3', strict_beats=True)

    def test_tts_sync_spoken_pronunciation_normalization_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            captured = {}

            def fake_run(cmd, **kwargs):
                out_idx = cmd.index('--out') + 1
                txt_idx = cmd.index('--text-file') + 1
                out_wav = Path(cmd[out_idx])
                captured[out_wav.stem] = Path(cmd[txt_idx]).read_text(encoding='utf-8').strip()
                test_v7_tools.make_wav(out_wav, duration=0.4)

            real_run = subprocess.run
            lines = [
                {'id': 'w1', 'voice': 'didi', 'role': '旁白', 'text': '稳定创造让顾客记住的 WOW 时刻。', 'scene_id': 's1', 'visual_cue': 'a'},
                {'id': 'w2', 'voice': 'didi', 'role': '旁白', 'text': '第 01 节结束，进入第 02 节。', 'scene_id': 's2', 'visual_cue': 'b'},
                {'id': 'w3', 'voice': 'didi', 'role': '旁白', 'text': '理解 NPS 指标。', 'tts_text': '理解净推荐值指标。', 'scene_id': 's3', 'visual_cue': 'c'},
            ]
            srt_out = p / 'sub.srt'
            with patch('tts_sync.subprocess.run', side_effect=lambda cmd, **kwargs: fake_run(cmd, **kwargs) if 'qwen3_tts.py' in str(cmd) else real_run(cmd, **kwargs)):
                res = tts_sync.synthesize_beats(lines, p / 'audio', srt_out=srt_out, strict_beats=True)

            self.assertEqual(captured['w1'], '稳定创造让顾客记住的哇哦时刻。')
            self.assertEqual(captured['w2'], '第一节结束，进入第二节。')
            self.assertEqual(captured['w3'], '理解净推荐值指标。')
            srt_txt = srt_out.read_text(encoding='utf-8')
            self.assertIn('WOW 时刻', srt_txt)
            self.assertIn('第 02 节', srt_txt)
            self.assertIn('NPS 指标', srt_txt)
            self.assertEqual(res['lines'][0]['tts_text'], '稳定创造让顾客记住的哇哦时刻。')

    def test_verify_delivery_catches_animation_replay_and_render_audit_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Synthesize a 6s video where beat 2 (3..6s) replays beat 1's (0..3s) color ramp from scratch!
            # Frame color transitions black -> bright red across 0..3s, then snaps back to black -> bright red across 3..6s
            replay_vid = p / 'replay.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', "color=c=black:s=1920x1080:r=24:d=6.0,geq=r='min(255,mod(T,3.0)*85)':g='20':b='40'",
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=6.0',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(replay_vid),
            ], check=True)
            tl = p / 'timeline.json'
            tl.write_text(json.dumps({
                'timeline': [
                    {'id': 'b1', 'start': 0.0, 'end': 3.0},
                    {'id': 'b2', 'start': 3.0, 'end': 6.0},
                ]
            }), encoding='utf-8')
            res = verify_delivery.verify_video(replay_vid, check_first_frame_cover=False, timeline=tl, strict_ppt_guard=True)
            self.assertFalse(res['ok'], res)
            self.assertTrue(any('重播' in e for e in res['errors']), res['errors'])

            # Test render_audit hard gate blocking floating walk, text overlap, PPT >25%, dead camera
            bad_audit = p / 'bad_audit.json'
            bad_audit.write_text(json.dumps({
                'schema': 'kgxc-director-audit/1',
                'total_frames': 144,
                'total_beats': 10,
                'card_box_ratio': 0.6,
                'max_consecutive_card_box': 4,
                'floating_walk_violations': [{'beat_id': 'b1', 'actor': 'staff', 'dx': 18.2}],
                'text_actor_overlap_violations': [{'beat_id': 'b2', 'text_id': 'danmaku', 'actor': 'cust'}],
                'scene_replay_violations': [{'scene_id': 's1', 'beat_id': 'b3'}],
                'camera_summary': [{'scene_id': 's1', 'layout_kind': 'cinematic_store', 'frames': 96, 'zoom_span': 0.01, 'pan_span_px': 12}],
            }), encoding='utf-8')
            bad_res = verify_delivery.verify_video(replay_vid, check_first_frame_cover=False, render_audit=bad_audit)
            self.assertFalse(bad_res['ok'])
            self.assertEqual(len(bad_res['errors']), 6, bad_res['errors'])

            # Clean render_audit must pass
            good_audit = p / 'good_audit.json'
            good_audit.write_text(json.dumps({
                'schema': 'kgxc-director-audit/1',
                'total_frames': 144,
                'total_beats': 10,
                'card_box_ratio': 0.2,
                'max_consecutive_card_box': 1,
                'floating_walk_violations': [],
                'text_actor_overlap_violations': [],
                'scene_replay_violations': [],
                'camera_summary': [{'scene_id': 's1', 'layout_kind': 'cinematic_store', 'frames': 96, 'zoom_span': 0.14, 'pan_span_px': 72}],
            }), encoding='utf-8')
            good_res = verify_delivery.verify_video(replay_vid, check_first_frame_cover=False, render_audit=good_audit)
            self.assertTrue(good_res['ok'], good_res)


if __name__ == '__main__':
    unittest.main()
