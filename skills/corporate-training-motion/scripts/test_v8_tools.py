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

    def test_v8_1_speech_onset_anchors_hold_camera_and_sway_reveal_gates(self):
        # 1. JS tests for phraseTime, holdUntil camera locking, steady_board sway block, and premature reveal block
        script = f"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const sandbox = {{ console, Math, Object, Array, Number, String, Boolean, Error, Map, Set, RegExp, Infinity }};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
const ctx = vm.createContext(sandbox);
vm.runInContext(fs.readFileSync({json.dumps(str(MOTION_DIR / 'director_stage.js'))}, 'utf8'), ctx);
const DS = sandbox.DirectorStage;

const lines = [
  {{ id: 'b1', scene_id: 's_sum', layout_kind: 'summary_board', start: 0.0, end: 4.0, speech_start: 0.45, speech_end: 3.8, text: '先看第一点，再说谢谢大家！' }},
  {{ id: 'b2', scene_id: 's_kin', layout_kind: 'kinetic_metaphor', start: 4.0, end: 11.0, speech_start: 4.2, speech_end: 10.8, text: '核心公式是体验等于实际感知减去心理预期。' }},
];
const rEarly = DS.resolveTimeline(lines, 0.15);
assert.equal(rEarly.speechT, 0);
const ty = DS.phraseTime(lines[0], '谢谢大家', 0);
assert.ok(ty > 2.0 && ty < 3.6, 'phraseTime should place 谢谢大家 near end: ' + ty);

// evalCamera with holdUntil stays rock steady during dwell window
const kf = [
  {{ at: 0.0, x: -30, y: 0, zoom: 0.98 }},
  {{ at: 1.0, x: 0, y: 0, zoom: 1.04, ease: 'easeOut', holdUntil: 5.0 }},
  {{ at: 6.0, x: 20, y: 0, zoom: 1.06, ease: 'easeInOut' }},
];
const cA = DS.evalCamera(kf, 2.0);
const cB = DS.evalCamera(kf, 4.5);
assert.equal(cA.x, 0);
assert.equal(cB.x, 0);
assert.equal(cA.zoom, 1.04);
assert.equal(cB.zoom, 1.04);

// Frame auditor blocks: (a) swaying summary_board, (b) bubble before speech_start, (c) premature reveal, (d) endless oscillating kinetic_metaphor
const aud = DS.createFrameAuditor();
for (let f = 0; f < 96; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  const badCam = {{ x: Math.sin(t * 2) * 50, y: 0, zoom: 1.05 }};
  aud.beginFrame(f, t, st, 'summary_board', badCam);
  if (f === 2) {{
    aud.recordText('b1_bub', {{ x: 200, y: 200, w: 200, h: 60 }}, 'bubble');
    aud.recordReveal('thanks_badge', ty, true);
  }}
}}
for (let f = 96; f < 264; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  // Continuous back-and-forth swaying on kinetic_metaphor (>=6s, never holds)
  const oscCam = {{ x: Math.sin((t - 4) * 1.8) * 60, y: 0, zoom: 1.04 }};
  aud.beginFrame(f, t, st, 'kinetic_metaphor', oscCam);
}}
const rep = aud.finalize();
assert.equal(rep.camera_sway_violations.length, 2, JSON.stringify(rep.camera_sway_violations));
assert.equal(rep.premature_reveal_violations.length, 2, JSON.stringify(rep.premature_reveal_violations));

// Steady summary_board + hold-settled kinetic_metaphor passes cleanly
const cleanAud = DS.createFrameAuditor();
for (let f = 0; f < 96; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  cleanAud.beginFrame(f, t, st, 'summary_board', DS.steadyCamera());
  if (t >= ty) cleanAud.recordReveal('thanks_badge', ty, true);
}}
for (let f = 96; f < 264; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  const holdCam = DS.evalCamera([
    {{ at: 0.0, x: -30, y: 0, zoom: 0.98 }},
    {{ at: 1.2, x: 0, y: 0, zoom: 1.04, ease: 'easeOut', holdUntil: 6.5 }},
  ], st.sceneT, t);
  cleanAud.beginFrame(f, t, st, 'kinetic_metaphor', holdCam);
}}
const cleanRep = cleanAud.finalize();
assert.equal(cleanRep.camera_sway_violations.length, 0, JSON.stringify(cleanRep.camera_sway_violations));
assert.equal(cleanRep.premature_reveal_violations.length, 0, JSON.stringify(cleanRep.premature_reveal_violations));
console.log('JS_V8_1_OK');
"""
        proc = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('JS_V8_1_OK', proc.stdout)

        # 2. tts_sync vocal onset + cue_words anchor + verify_delivery new hard gates
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Build a wav with 0.40s leading silence + 1.20s tone
            def make_delayed_wav(out_wav: Path):
                subprocess.run([
                    'ffmpeg', '-v', 'error', '-y',
                    '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono:d=0.40',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000:duration=1.20',
                    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[a]',
                    '-map', '[a]', '-c:a', 'pcm_s16le', str(out_wav),
                ], check=True)

            real_run = subprocess.run
            lines = [{
                'id': 'on1', 'voice': 'didi', 'role': '旁白',
                'text': '在服务学里有一个公式：体验等于实际感知减去心理预期。',
                'cue_words': ['体验等于实际感知'],
                'scene_id': 's1', 'visual_cue': '公式逐段显现',
            }]
            srt_out = p / 'on.srt'
            with patch('tts_sync.subprocess.run', side_effect=lambda cmd, **kwargs: make_delayed_wav(Path(cmd[cmd.index('--out') + 1])) if 'qwen3_tts.py' in str(cmd) else real_run(cmd, **kwargs)):
                res = tts_sync.synthesize_beats(lines, p / 'audio', srt_out=srt_out, strict_beats=True)
            entry = res['lines'][0]
            self.assertGreaterEqual(entry['speech_onset_sec'], 0.35)
            self.assertIn('体验等于实际感知', entry['anchors'])
            self.assertGreater(entry['anchors']['体验等于实际感知'], entry['speech_start'] + 0.3)

            # verify_delivery must block camera_sway_violations & premature_reveal_violations
            vid = p / 'ok.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=white:s=1920x1080:r=24:d=2.0',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2.0',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(vid),
            ], check=True)
            bad_v81 = p / 'bad_v81.json'
            bad_v81.write_text(json.dumps({
                'schema': 'kgxc-director-audit/1',
                'total_frames': 48, 'total_beats': 4,
                'card_box_ratio': 0.0, 'summary_board_ratio': 0.2, 'max_consecutive_card_box': 0,
                'floating_walk_violations': [], 'text_actor_overlap_violations': [], 'scene_replay_violations': [],
                'camera_sway_violations': [{'scene_id': 'sc14', 'layout_kind': 'summary_board', 'reason': 'sway'}],
                'premature_reveal_violations': [{'scene_id': 'sc14', 'beat_id': 'b1', 'item_id': 'col2', 'lead_sec': 3.5}],
                'camera_summary': [{'scene_id': 'sc14', 'layout_kind': 'summary_board', 'frames': 48, 'zoom_span': 0.0, 'pan_span_px': 0.0}],
            }), encoding='utf-8')
            bad_out = verify_delivery.verify_video(vid, check_first_frame_cover=False, render_audit=bad_v81)
            self.assertFalse(bad_out['ok'])
            self.assertTrue(any('晃动' in e for e in bad_out['errors']), bad_out['errors'])
            self.assertTrue(any('抢先旁白' in e for e in bad_out['errors']), bad_out['errors'])

            # Coarse stats distinguish fake ±12px wiggle (blocked) from genuine steady-camera localized reveal (allowed)
            import numpy as np
            base = np.full((180, 320, 3), 250, dtype=np.uint8)
            base[25:125, 40:280] = 255
            base[25:27, 40:280] = 40; base[123:125, 40:280] = 40; base[25:125, 40:42] = 40; base[25:125, 278:280] = 40
            base[40:46, 60:200] = 35; base[60:64, 60:240] = 60
            wiggle = np.roll(base, shift=2, axis=1)
            w_mae = verify_delivery._main_canvas_mae(base.tobytes(), wiggle.tobytes())
            w_coarse, w_top3 = verify_delivery._coarse_structure_stats(base.tobytes(), wiggle.tobytes())
            self.assertFalse((w_top3 >= 11.5) and (w_coarse >= 0.38 * max(w_mae, 0.01)))
            revealed = base.copy()
            revealed[32:64, 210:274] = [37, 76, 153]  # Solid localized new badge on rock-steady canvas
            r_mae = verify_delivery._main_canvas_mae(base.tobytes(), revealed.tobytes())
            r_coarse, r_top3 = verify_delivery._coarse_structure_stats(base.tobytes(), revealed.tobytes())
            self.assertTrue((r_top3 >= 11.5) and (r_coarse >= 0.38 * max(r_mae, 0.01)))

    def test_v8_1_segmented_progress_bar_and_gate_a(self):
        # 1. JS check: DS.buildNavSegments + VM.drawSegmentedProgressBar + auditor.recordProgressBar
        script = f"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const sandbox = {{ console, Math, Object, Array, Number, String, Boolean, Error, Map, Set, RegExp, Infinity }};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
const ctx = vm.createContext(sandbox);
vm.runInContext(fs.readFileSync({json.dumps(str(MOTION_DIR / 'visual_metaphors.js'))}, 'utf8'), ctx);
vm.runInContext(fs.readFileSync({json.dumps(str(MOTION_DIR / 'director_stage.js'))}, 'utf8'), ctx);
const VM = sandbox.VisualMetaphors;
const DS = sandbox.DirectorStage;

const lines = [];
for (let i = 0; i < 12; i++) {{
  const sid = i < 4 ? 'sc01' : (i < 8 ? 'sc02' : 'sc03');
  lines.push({{ id: 'b' + i, scene_id: sid, layout_kind: 'kinetic_metaphor', start: i * 2.0, end: (i + 1) * 2.0, speech_start: i * 2.0 + 0.1, speech_end: (i + 1) * 2.0 - 0.1, text: '测试短句' }});
}}
const navSegs = DS.buildNavSegments(lines, [
  {{ id: 'c1', label: '开场引入', scenes: ['sc01'] }},
  {{ id: 'c2', label: '核心方法', scenes: ['sc02'] }},
  {{ id: 'c3', label: '总结练习', scenes: ['sc03'] }},
], 24.0);
assert.equal(navSegs.length, 3);
assert.equal(navSegs[0].start, 0);
assert.equal(navSegs[2].end, 24.0);

const noop = () => {{}};
const grad = {{ addColorStop: noop }};
const mockCtx = {{
  save: noop, restore: noop, fillRect: noop, beginPath: noop, moveTo: noop, lineTo: noop,
  stroke: noop, fill: noop, roundRect: noop, clip: noop, fillText: noop,
  createLinearGradient: () => grad, measureText: s => ({{ width: String(s).length * 16 }}),
}};

const aud = DS.createFrameAuditor();
for (let i = 0; i < 12; i++) {{
  const t = i * 2.0 + 1.0;
  const st = DS.resolveTimeline(lines, t);
  aud.beginFrame(i, t, st, 'kinetic_metaphor', {{ x: i * 5, y: 0, zoom: 1 + i * 0.01 }});
  const nav = VM.drawSegmentedProgressBar(mockCtx, navSegs, t, {{ accent: '#254C99', gold: '#D98A2B' }});
  assert.equal(nav.mode, 'segmented');
  assert.equal(nav.segment_count, 3);
  aud.recordProgressBar(nav);
}}
const rep = aud.finalize();
assert.equal(rep.progress_bar_summary.mode, 'segmented');
assert.equal(rep.progress_bar_summary.segment_count, 3);
assert.equal(rep.progress_bar_summary.visited_segments, 3);
console.log('SEG_BAR_JS_OK');
"""
        proc = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
        self.assertIn('SEG_BAR_JS_OK', proc.stdout)

        # 2. Gate A check: blocks missing/single progress_bar_summary when total_beats >= 12, passes segmented
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            vid = p / 'seg.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=white:s=1920x1080:r=24:d=2.0',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2.0',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(vid),
            ], check=True)
            base_audit = {
                'schema': 'kgxc-director-audit/1',
                'total_frames': 48, 'total_beats': 14,
                'card_box_ratio': 0.0, 'summary_board_ratio': 0.14, 'max_consecutive_card_box': 0,
                'floating_walk_violations': [], 'text_actor_overlap_violations': [],
                'scene_replay_violations': [], 'camera_sway_violations': [], 'premature_reveal_violations': [],
                'camera_summary': [{'scene_id': 's1', 'layout_kind': 'kinetic_metaphor', 'frames': 48, 'zoom_span': 0.06, 'pan_span_px': 40.0}],
            }
            bad_p = p / 'missing_seg.json'
            bad_p.write_text(json.dumps(base_audit), encoding='utf-8')
            bad_res = verify_delivery.verify_video(vid, check_first_frame_cover=False, render_audit=bad_p)
            self.assertFalse(bad_res['ok'])
            self.assertTrue(any('分段章节进度条' in e for e in bad_res['errors']), bad_res['errors'])

            good_p = p / 'good_seg.json'
            good_audit = dict(base_audit, progress_bar_summary={
                'mode': 'segmented', 'style': 'inline_pill', 'segment_count': 6,
                'labels': ['A', 'B', 'C', 'D', 'E', 'F'], 'bar_top_y': 1032, 'visited_segments': 6,
            })
            good_p.write_text(json.dumps(good_audit), encoding='utf-8')
            good_res = verify_delivery.verify_video(vid, check_first_frame_cover=False, render_audit=good_p)
            self.assertTrue(good_res['ok'], good_res)

    def test_v812_tts_punctuation_and_zero_token_tail_guard(self):
        """v8.1.2: clean sentence-final punctuation, 30ms/80ms tail guard, and codebook-0 zero-token decode fix."""
        self.assertEqual(tts_sync.prepare_tts_text('更不是冲上去抢单的超级销售，'), '更不是冲上去抢单的超级销售。')
        self.assertEqual(tts_sync.prepare_tts_text('直接在记录表上打勾——'), '直接在记录表上打勾。')
        self.assertEqual(tts_sync.prepare_tts_text('现场诊断、聚焦计划、'), '现场诊断、聚焦计划。')
        self.assertEqual(tts_sync.prepare_tts_text('店长要摆正自己的站位：'), '店长要摆正自己的站位。')
        self.assertEqual(tts_sync.prepare_tts_text('“这周转化掉了一个点，下周大家加把劲！”'), '“这周转化掉了一个点，下周大家加把劲！”')
        self.assertEqual(tts_sync.prepare_tts_text('第一步，现场诊断，找真根因。'), '第一步，现场诊断，找真根因。')

        # Verify 30ms abrupt cutoff detection vs clean tapered tail
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            abrupt_wav = p / 'abrupt.wav'
            clean_wav = p / 'clean.wav'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000:duration=1.0',
                '-af', 'volume=2.0', '-c:a', 'pcm_s16le', str(abrupt_wav),
            ], check=True)
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000:duration=1.0',
                '-af', 'volume=2.0,afade=t=out:st=0.75:d=0.25', '-c:a', 'pcm_s16le', str(clean_wav),
            ], check=True)
            ab = tts_sync.check_tail_energy(abrupt_wav)
            cl = tts_sync.check_tail_energy(clean_wav)
            self.assertIn('tail_30ms_db', ab)
            self.assertTrue(ab['abrupt_cutoff_warning'], ab)
            self.assertFalse(cl['abrupt_cutoff_warning'], cl)

        # Verify qwen3_tts._patch_zero_token_decode helper exists and preserves valid token 0
        import qwen3_tts
        self.assertTrue(hasattr(qwen3_tts, '_patch_zero_token_decode'))
        self.assertFalse(qwen3_tts._patch_zero_token_decode(object()))


if __name__ == '__main__':
    unittest.main()
