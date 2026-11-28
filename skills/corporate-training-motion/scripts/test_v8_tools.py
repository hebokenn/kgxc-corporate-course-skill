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

    def test_v8_2_cumulative_kpi_hand_props_and_anti_ppt_flip_gates(self):
        """v8.2.0: heldProp hand sockets, cumulative KPI/event stack, handover/screen-inset, open-canvas & Gate A guards."""
        script = f"""
const fs = require('node:fs');
const assert = require('node:assert/strict');
global.window = global;
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'actors_v3_cute.js'))}, 'utf8'));
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'visual_metaphors.js'))}, 'utf8'));
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'director_stage.js'))}, 'utf8'));
const CA = window.CourseActorsCute;
const VM = window.VisualMetaphors;
const DS = window.DirectorStage;

assert.equal(DS.VERSION, '9.0.0');
assert.ok(CA.VALID_HELD_PROPS.includes('phone'));
assert.ok(CA.VALID_HELD_PROPS.includes('qr_card'));

// 1. CourseActorsCute heldProp validation + live hand socket coordinates
assert.throws(() => CA.validatePaintState({{ x: 500, footY: 850, heldProp: 'invalid_prop' }}), /unsupported heldProp/);
const noop = () => {{}};
const mockCtx = new Proxy({{
  measureText: t => ({{ width: String(t).length * 20 }}),
  createLinearGradient: () => ({{ addColorStop: noop }}),
  createRadialGradient: () => ({{ addColorStop: noop }}),
}}, {{
  get(target, prop) {{ return prop in target ? target[prop] : noop; }},
  set() {{ return true; }},
}});
const bStaff = CA.paintExpressive(mockCtx, CA.getPreset('staff_bun'), {{
  x: 600, footY: 850, scale: 1.6, facing: 1, t: 1.0,
  mood: 'happy', gesture: 'present', heldProp: 'phone',
}}, {{}});
assert.ok(bStaff.frontHand && bStaff.frontHand.x > 600, JSON.stringify(bStaff.frontHand));
assert.ok(bStaff.backHand && Number.isFinite(bStaff.backHand.y), JSON.stringify(bStaff.backHand));

// 2. VisualMetaphors v8.2.0 primitives (KPI rail, cumulative stack, handover, screen inset, open-canvas)
const pal = {{ accent: '#254C99', secondary: '#8C4E12', gold: '#D48A1D', ok: '#18794E', error: '#C4313D', ink: '#222630', muted: '#5F6678' }};
const rail = VM.drawKpiRail(mockCtx, [
  {{ id: 'k1', label: '状态待客得分率', value: '< 30%', tone: 'error', progress: 1 }},
  {{ id: 'k2', label: '建立联系得分率', value: '< 10%', tone: 'error', progress: 1 }},
], pal);
assert.equal(rail.rects.length, 2);
assert.ok(rail.rects[1].rect.y > rail.rects[0].rect.y);

const stack = VM.drawCumulativeStack(mockCtx, [
  {{ id: 'e1', text: '掏自己手机现查', tone: 'bad', progress: 1 }},
  {{ id: 'e2', text: '干报官方授权店', tone: 'bad', progress: 1 }},
], pal);
assert.equal(stack.rects.length, 2);
assert.ok(stack.rects[1].rect.y > stack.rects[0].rect.y);

const ho = VM.drawHandoverProp(mockCtx, {{ x: 700, y: 650 }}, {{ x: 1100, y: 650 }}, 0.5, {{ type: 'phone' }});
assert.ok(ho && ho.cx === 900 && ho.cy < 650);
const inset = VM.drawScreenInset(mockCtx, bStaff.frontHand, {{ x: 800, y: 260, w: 360, h: 220 }}, {{ mode: 'camera_live', title: '实况选帧', progress: 1 }});
assert.ok(inset && inset.w === 360);
VM.drawOpenChapterDots(mockCtx, [{{ label: '01 差距' }}, {{ label: '02 动作' }}], 1, pal);
const barRect = VM.drawSculptureBar(mockCtx, 1310, 816, 400, 1.0, {{ valText: '96.5', subText: '高分', progress: 1 }});
// Safe max height cap <= 210 keeps bar top >= 816 - 210 - 46 = 560
assert.ok(barRect.y >= 555, JSON.stringify(barRect));
const tagRect = VM.drawFloatingTag(mockCtx, 960, 440, '开放画布关键词', 'gold', 1, {{ pal }});
assert.ok(tagRect && tagRect.h === 56);
VM.draw3DPhoneProp(mockCtx, 960, 560, 0.5, 0.2, 0.1, 1, pal, {{ showOrbit: false, showShadow: false }});

// 3. DirectorStage auditor catches all 3 v8.2.0 violations
const lines = [
  {{ id: 'b1', scene_id: 'sc_store', layout_kind: 'cinematic_store', start: 0, end: 3.0 }},
  {{ id: 'b2', scene_id: 'sc_store', layout_kind: 'cinematic_store', start: 3.0, end: 6.0 }},
  {{ id: 'b3', scene_id: 'sc_ppt', layout_kind: 'kinetic_metaphor', start: 6.0, end: 8.5 }},
  {{ id: 'b4', scene_id: 'sc_ppt', layout_kind: 'kinetic_metaphor', start: 8.5, end: 11.0 }},
  {{ id: 'b5', scene_id: 'sc_ppt', layout_kind: 'kinetic_metaphor', start: 11.0, end: 13.5 }},
];
const badAud = DS.createFrameAuditor();
for (let f = 0; f < 324; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  badAud.beginFrame(f, t, st, st.layoutKind, {{ x: f * 0.15, y: 0, zoom: 1.02 }});
  if (st.sceneId === 'sc_store') {{
    badAud.recordMetricSlot('top_kpi', t < 3.0 ? '状态待客得分率' : '建立联系得分率', '< 10%', {{ x: 1550, y: 164, w: 244, h: 92 }});
    badAud.recordProp('midair_phone', {{ x: 900, y: 500, w: 120, h: 200 }}, {{ attachment: 'floating', interactive: false }});
  }} else {{
    // Giant panel (>28% screen) flipping every 2.5s (3 swaps < 5s)
    badAud.recordPanel('ppt_board', {{ x: 140, y: 240, w: 1640, h: 620 }}, {{ contentKey: st.beatId }});
  }}
}}
const badRep = badAud.finalize();
assert.ok(badRep.info_overwrite_violations.length >= 1, JSON.stringify(badRep.info_overwrite_violations));
assert.ok(badRep.floating_prop_violations.length >= 1, JSON.stringify(badRep.floating_prop_violations));
assert.ok(badRep.rapid_card_flip_violations.length >= 1, JSON.stringify(badRep.rapid_card_flip_violations));

// Clean v8.2.0 usage passes with 0 violations
const cleanAud = DS.createFrameAuditor();
for (let f = 0; f < 324; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  cleanAud.beginFrame(f, t, st, st.layoutKind, {{ x: f * 0.15, y: 0, zoom: 1.02 }});
  if (st.sceneId === 'sc_store') {{
    cleanAud.recordMetricSlot('kpi_1', '状态待客得分率', '< 30%', {{ x: 1550, y: 164, w: 244, h: 92 }});
    if (t >= 3.0) cleanAud.recordMetricSlot('kpi_2', '建立联系得分率', '< 10%', {{ x: 1550, y: 268, w: 244, h: 92 }});
    cleanAud.recordProp('demo_phone', {{ x: 700, y: 600, w: 40, h: 70 }}, {{ attachment: 'hand', interactive: true }});
  }} else {{
    // Same thematic open-canvas stage stays calmly across 7.5s
    cleanAud.recordPanel('open_stage', {{ x: 140, y: 240, w: 1640, h: 620 }}, {{ contentKey: 'gap_01' }});
  }}
}}
const cleanRep = cleanAud.finalize();
assert.equal(cleanRep.info_overwrite_violations.length, 0);
assert.equal(cleanRep.floating_prop_violations.length, 0);
assert.equal(cleanRep.rapid_card_flip_violations.length, 0);
console.log('JS_V8_2_OK');
"""
        proc = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('JS_V8_2_OK', proc.stdout)

        # 4. verify_delivery.py Gate A blocks all 3 new violation types
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            vid = p / 'ok.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=white:s=1920x1080:r=24:d=2.0',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2.0',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(vid),
            ], check=True)
            bad_v82 = p / 'bad_v82.json'
            bad_v82.write_text(json.dumps({
                'schema': 'kgxc-director-audit/1',
                'total_frames': 48, 'total_beats': 4,
                'card_box_ratio': 0.0, 'summary_board_ratio': 0.0, 'max_consecutive_card_box': 0,
                'floating_walk_violations': [], 'text_actor_overlap_violations': [], 'scene_replay_violations': [],
                'camera_sway_violations': [], 'premature_reveal_violations': [],
                'info_overwrite_violations': [{'scene_id': 'sc05', 'beat_id': 'b4', 'prev_label': '状态', 'next_label': '建联'}],
                'floating_prop_violations': [{'scene_id': 'sc02', 'beat_id': 'b1', 'prop_id': 'hover_phone'}],
                'rapid_card_flip_violations': [{'scene_id': 'sc04', 'panel_id': 'board', 'swaps': 4, 'avg_sec': 2.6}],
                'camera_summary': [{'scene_id': 'sc02', 'layout_kind': 'cinematic_store', 'frames': 48, 'zoom_span': 0.06, 'pan_span_px': 40.0}],
            }), encoding='utf-8')
            bad_out = verify_delivery.verify_video(vid, check_first_frame_cover=False, render_audit=bad_v82)
            self.assertFalse(bad_out['ok'])
            self.assertTrue(any('原地覆盖' in e for e in bad_out['errors']), bad_out['errors'])
            self.assertTrue(any('悬空道具' in e for e in bad_out['errors']), bad_out['errors'])
            self.assertTrue(any('高频翻页快闪 PPT' in e for e in bad_out['errors']), bad_out['errors'])

    def test_v8_3_incremental_scene_partition_audit_merge_and_cache_invalidation(self):
        """v8.3.0: integer-frame scene partitioning, mergeFrameAudits parity, source isolation & incremental Chrome render."""
        render_script = SKILL_ROOT / 'scripts/render_director_incremental.mjs'
        self.assertTrue(render_script.exists(), f'Missing {render_script}')

        # 1. JS unit checks: partitionSceneFrames + mergeFrameAudits 100% parity with single-pass auditor
        js_check = f"""
const fs = require('node:fs');
const assert = require('node:assert/strict');
global.window = global;
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'visual_metaphors.js'))}, 'utf8'));
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'director_stage.js'))}, 'utf8'));
const DS = window.DirectorStage;

const lines = [
  {{ id: 'b1', scene_id: 'sc01', layout_kind: 'cinematic_store', start: 0.0, end: 2.0, speech_start: 0.1, speech_end: 1.9, text: '第一句' }},
  {{ id: 'b2', scene_id: 'sc01', layout_kind: 'cinematic_store', start: 2.0, end: 4.0, speech_start: 2.1, speech_end: 3.9, text: '第二句' }},
  {{ id: 'b3', scene_id: 'sc02', layout_kind: 'card_box', start: 4.0, end: 6.0, speech_start: 4.1, speech_end: 5.9, text: '第三句' }},
  {{ id: 'b4', scene_id: 'sc03', layout_kind: 'card_box', start: 6.0, end: 8.0, speech_start: 6.1, speech_end: 7.9, text: '第四句' }},
  {{ id: 'b5', scene_id: 'sc04', layout_kind: 'card_box', start: 8.0, end: 10.0, speech_start: 8.1, speech_end: 9.9, text: '第五句' }},
];
const part = DS.partitionSceneFrames(lines, 10.0, 24);
assert.equal(part.totalFrames, 240);
assert.equal(part.segments.length, 4);
assert.equal(part.segments[0].startFrame, 0);
assert.equal(part.segments[3].endFrame, 240);
let covered = 0;
for (let i = 0; i < part.segments.length; i++) {{
  const s = part.segments[i];
  if (i > 0) assert.equal(s.startFrame, part.segments[i - 1].endFrame);
  for (let f = s.startFrame; f < s.endFrame; f++) {{
    const st = DS.resolveTimeline(lines, f / 24);
    assert.equal(st.sceneId, s.scene_id, `frame ${{f}} expected ${{s.scene_id}} got ${{st.sceneId}}`);
    covered++;
  }}
}}
assert.equal(covered, 240);

// Compare single-pass audit vs per-scene merged audit (including cross-scene max_consecutive_card_box = 3)
const single = DS.createFrameAuditor();
for (let f = 0; f < 240; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  const cam = st.layoutKind === 'card_box' ? DS.steadyCamera() : {{ x: st.sceneT * 10, y: 0, zoom: 1 + st.sceneT * 0.02 }};
  single.beginFrame(f, t, st, st.layoutKind, cam);
  single.recordProgressBar({{ mode: 'segmented', style: 'inline_pill', segment_count: 4, labels: ['A','B','C','D'], barTopY: 1032, activeIdx: Math.min(3, Math.floor(t / 2.5)) }});
}}
const singleRep = single.finalize();

const segAudits = part.segments.map(seg => {{
  const aud = DS.createFrameAuditor();
  for (let f = seg.startFrame; f < seg.endFrame; f++) {{
    const t = f / 24;
    const st = DS.resolveTimeline(lines, t);
    const cam = st.layoutKind === 'card_box' ? DS.steadyCamera() : {{ x: st.sceneT * 10, y: 0, zoom: 1 + st.sceneT * 0.02 }};
    aud.beginFrame(f, t, st, st.layoutKind, cam);
    aud.recordProgressBar({{ mode: 'segmented', style: 'inline_pill', segment_count: 4, labels: ['A','B','C','D'], barTopY: 1032, activeIdx: Math.min(3, Math.floor(t / 2.5)) }});
  }}
  return aud.finalize();
}});
const mergedRep = DS.mergeFrameAudits(segAudits);
assert.equal(mergedRep.total_frames, singleRep.total_frames);
assert.equal(mergedRep.total_beats, singleRep.total_beats);
assert.equal(mergedRep.max_consecutive_card_box, 3);
assert.equal(mergedRep.max_consecutive_card_box, singleRep.max_consecutive_card_box);
assert.equal(mergedRep.card_box_ratio, singleRep.card_box_ratio);
assert.deepEqual(mergedRep.layout_kind_counts, singleRep.layout_kind_counts);
assert.equal(mergedRep.progress_bar_summary.visited_segments, singleRep.progress_bar_summary.visited_segments);
assert.deepEqual(mergedRep.camera_summary, singleRep.camera_summary);
console.log('JS_V8_3_PARITY_OK');
"""
        proc = subprocess.run(['node', '-e', js_check], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('JS_V8_3_PARITY_OK', proc.stdout)

        # 2. Source block isolation check (ESM import)
        iso_check = f"""
import assert from 'node:assert/strict';
import {{ extractSceneSourceBlocks }} from {json.dumps(render_script.as_uri())};
const htmlA = `
<script>
const SHARED = 1;
function renderSc01(ctx, st) {{ ctx.fillStyle = '#111'; }}
function renderSc02(ctx, st) {{ ctx.fillStyle = '#222'; }}
const SCENE_RENDERERS = {{ sc01: renderSc01, sc02: renderSc02 }};
</script>`;
const htmlB = htmlA.replace('#222', '#333');
const htmlC = htmlA.replace('SHARED = 1', 'SHARED = 2');
const a = extractSceneSourceBlocks(htmlA);
const b = extractSceneSourceBlocks(htmlB);
const c = extractSceneSourceBlocks(htmlC);
assert.equal(a.sharedBase, b.sharedBase);
assert.equal(a.sceneBlocks.renderSc01, b.sceneBlocks.renderSc01);
assert.notEqual(a.sceneBlocks.renderSc02, b.sceneBlocks.renderSc02);
assert.notEqual(a.sharedBase, c.sharedBase);
console.log('JS_V8_3_ISOLATION_OK');
"""
        proc2 = subprocess.run(['node', '--input-type=module', '-e', iso_check], capture_output=True, text=True)
        self.assertEqual(proc2.returncode, 0, proc2.stderr + proc2.stdout)
        self.assertIn('JS_V8_3_ISOLATION_OK', proc2.stdout)

        # 3. End-to-end incremental headless Chrome render (3 scenes, 2 workers): cold -> 1-scene edit -> shared edit
        chrome_candidates = [
            Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
            Path('/Applications/Chromium.app/Contents/MacOS/Chromium'),
            Path('/usr/bin/google-chrome'),
            Path('/usr/bin/chromium'),
        ]
        if not any(p.exists() for p in chrome_candidates):
            return

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            audio_dir = p / 'audio'
            out_dir = p / 'out'
            tmp_dir = p / 'tmp'
            audio_dir.mkdir()

            mix_wav = audio_dir / 'mix.wav'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=6.0',
                '-af', 'afade=t=out:st=5.6:d=0.4',
                '-c:a', 'pcm_s16le', str(mix_wav),
            ], check=True)
            manifest = {
                'total_duration': 6.0,
                'mix_wav': str(mix_wav),
                'lines': [
                    {'id': 'b1', 'scene_id': 'sc01_open', 'layout_kind': 'kinetic_metaphor', 'start': 0.0, 'end': 2.0, 'speech_start': 0.05, 'speech_end': 1.9, 'text': '第一场开场介绍'},
                    {'id': 'b2', 'scene_id': 'sc02_mid', 'layout_kind': 'data_sculpture', 'start': 2.0, 'end': 4.0, 'speech_start': 2.05, 'speech_end': 3.9, 'text': '第二场数据拆解'},
                    {'id': 'b3', 'scene_id': 'sc03_end', 'layout_kind': 'cinematic_store', 'start': 4.0, 'end': 6.0, 'speech_start': 4.05, 'speech_end': 5.9, 'text': '第三场门店收尾'},
                ],
            }
            (audio_dir / 'audio_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
            (audio_dir / 'body.srt').write_text(
                '1\n00:00:00,050 --> 00:00:01,900\n第一场开场介绍\n\n'
                '2\n00:00:02,050 --> 00:00:03,900\n第二场数据拆解\n\n'
                '3\n00:00:04,050 --> 00:00:05,900\n第三场要点总结\n',
                encoding='utf-8',
            )
            meta_json = p / 'meta.json'
            meta_json.write_text(json.dumps({'ep_id': 'inc_test', 'stem': 'inc_test'}), encoding='utf-8')

            director_html = p / 'director.html'
            base_html = """<!doctype html><html><body style="margin:0;overflow:hidden;background:#F7F8FC">
<canvas id="c" width="1920" height="1080"></canvas>
<script>__ACTORS_CUTE_JS__</script>
<script>__VISUAL_METAPHORS_JS__</script>
<script>__DIRECTOR_STAGE_JS__</script>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const DS = window.DirectorStage;
let SHARED_BG = '#F7F8FC';
let AUDITOR = null;
window.initAudit = () => { AUDITOR = DS.createFrameAuditor(); };
window.finalizeAudit = () => AUDITOR ? AUDITOR.finalize() : null;
window.renderCover = () => { ctx.fillStyle = '#254C99'; ctx.fillRect(0, 0, 1920, 1080); };
function renderSc01(ctx, st) {
  const cam = DS.evalCamera([{at:0,x:-30,y:0,zoom:0.98},{at:1.2,x:20,y:0,zoom:1.05,holdUntil:2.0}], st.sceneT, st.t);
  ctx.fillStyle = '#254C99';
  ctx.fillRect(200 + st.sceneT * 180, 260, 420, 240);
  return cam;
}
function renderSc02(ctx, st) {
  const cam = DS.evalCamera([{at:0,x:30,y:0,zoom:0.98},{at:1.2,x:-20,y:0,zoom:1.05,holdUntil:2.0}], st.sceneT, st.t);
  ctx.fillStyle = '#C4313D';
  ctx.fillRect(300 + st.sceneT * 200, 320, 480, 220);
  return cam;
}
function renderSc03(ctx, st) {
  const cam = DS.evalCamera([{at:0,x:-20,y:0,zoom:0.99},{at:1.4,x:24,y:0,zoom:1.06,holdUntil:2.0}], st.sceneT, st.t);
  ctx.fillStyle = '#18794E';
  ctx.fillRect(360, 260, 180 + Math.round(st.sceneT * 260), 260);
  return cam;
}
const SCENE_RENDERERS = { sc01_open: renderSc01, sc02_mid: renderSc02, sc03_end: renderSc03 };
window.renderFrame = (f, t, data) => {
  ctx.fillStyle = SHARED_BG;
  ctx.fillRect(0, 0, 1920, 1080);
  const st = DS.resolveTimeline(data.lines, t);
  const cam = SCENE_RENDERERS[st.sceneId](ctx, st);
  if (AUDITOR) AUDITOR.beginFrame(f, t, st, st.layoutKind, cam);
};
</script></body></html>"""
            director_html.write_text(base_html, encoding='utf-8')

            def run_inc(port):
                r = subprocess.run([
                    'node', str(render_script),
                    '--html', str(director_html),
                    '--audio-dir', str(audio_dir),
                    '--out-dir', str(out_dir),
                    '--tmp-dir', str(tmp_dir),
                    '--meta-json', str(meta_json),
                    '--workers', '2',
                    '--port', str(port),
                    '--skip-cover',
                ], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                return json.loads((tmp_dir / 'inc_test_render_cache_report.json').read_text(encoding='utf-8'))

            # Pass 1: cold cache renders all 3 scenes
            rep1 = run_inc(9481)
            self.assertEqual(rep1['cache_hits'], 0)
            self.assertEqual(rep1['cache_misses'], 3)
            self.assertEqual(rep1['total_frames'], 144)

            # Pass 2: edit ONLY renderSc02 -> 2 hits (sc01, sc03), 1 miss (sc02)
            director_html.write_text(base_html.replace('#C4313D', '#D98A2B'), encoding='utf-8')
            rep2 = run_inc(9482)
            self.assertEqual(rep2['cache_hits'], 2, rep2)
            self.assertEqual(rep2['cache_misses'], 1, rep2)
            statuses = {s['scene_id']: s['status'] for s in rep2['scenes']}
            self.assertEqual(statuses, {'sc01_open': 'hit', 'sc02_mid': 'miss', 'sc03_end': 'hit'})

            # Verify merged output passes Gate A (verify_delivery.py)
            vres = verify_delivery.verify_video(
                out_dir / 'inc_test.mp4',
                srt=out_dir / 'inc_test.srt',
                timeline=tmp_dir / 'inc_test_timeline.json',
                render_audit=tmp_dir / 'inc_test_render_audit.json',
                check_first_frame_cover=False,
                strict_ppt_guard=True,
            )
            self.assertTrue(vres['ok'], vres)

            # Pass 3: edit shared helper -> all 3 scenes automatically invalidate
            director_html.write_text(base_html.replace('#F7F8FC', '#F2F5FA'), encoding='utf-8')
            rep3 = run_inc(9483)
            self.assertEqual(rep3['cache_hits'], 0, rep3)
            self.assertEqual(rep3['cache_misses'], 3, rep3)

    def test_v9_0_editorial_primitives_diversity_blueprint_and_redundancy_gates(self):
        """v9.0.0: 12-col editorial primitives, anti-redundancy & double-headline telemetry, blueprint validator & Gate A."""
        import check_visual_blueprint

        # 1. JS unit checks for v9.0.0 VisualMetaphors primitives + DirectorStage telemetry + mergeFrameAudits parity
        js_check = f"""
const fs = require('node:fs');
const assert = require('node:assert/strict');
global.window = global;
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'visual_metaphors.js'))}, 'utf8'));
eval(fs.readFileSync({json.dumps(str(MOTION_DIR / 'director_stage.js'))}, 'utf8'));
const VM = window.VisualMetaphors;
const DS = window.DirectorStage;

assert.equal(DS.VERSION, '9.0.0');
assert.equal(VM.GRID_12.cols, 12);
const left7 = VM.gridCols(1, 7);
const right5 = VM.gridCols(8, 5);
assert.equal(left7.x, 120);
assert.equal(right5.right, 1800);
assert.ok(right5.x > left7.right);

const noop = () => {{}};
const mockCtx = new Proxy({{
  measureText: t => ({{ width: String(t).length * 20 }}),
  createLinearGradient: () => ({{ addColorStop: noop }}),
  createRadialGradient: () => ({{ addColorStop: noop }}),
}}, {{
  get(target, prop) {{ return prop in target ? target[prop] : noop; }},
  set() {{ return true; }},
}});
const pal = {{ ink: '#1E2430', muted: '#667085', accent: '#234B9A', error: '#C02B3A', ok: '#1A7454', stroke: '#D0C9BC' }};

const topBar = VM.drawQuietTopBar(mockCtx, null, '第 06 节', '诊断+', pal, {{ rightMeta: '开场' }});
assert.equal(topBar.x, 120);
const h1 = VM.drawEditorialHeadline(mockCtx, 120, 122, '专项暗访实证', '真正流失信任的，往往不是技术', pal, {{ highlightPhrase: '往往不是技术' }});
assert.ok(h1 && h1.rect.w > 100 && h1.bottomY > 180);

const bars = VM.drawSpotlightHorizontalBars(mockCtx, left7.x, 316, left7.w, [
  {{ label: '未讲清维修', ratio: 0.66, value: '近 2/3' }},
  {{ label: '等待零沟通', ratio: 0.62, value: '> 60%' }},
  {{ label: '检测失败率', ratio: 0.21, value: '21%', muted: true }},
], pal, {{ focusIdx: 0, groupSplitAfter: 1, topGroupLabel: '沟通黑盒', bottomGroupLabel: '技术层面' }});
assert.equal(bars.rowAnchors.length, 3);
assert.ok(bars.rowAnchors[2].y > bars.rowAnchors[1].y);

const picto = VM.drawPictogramGrid(mockCtx, right5.x, 340, right5.w, 260, pal, {{ total: 9, active: 6, cols: 3, shape: 'person' }});
assert.equal(picto.active, 6);
const leader = VM.drawLeaderLine(mockCtx, bars.rowAnchors[0].rightX, bars.rowAnchors[0].y, right5.x, 380);
assert.ok(leader && leader.x2 === right5.x);
const bracket = VM.drawGroupingBracket(mockCtx, 1080, 320, 560, 1184);
assert.equal(bracket.tipX, 1184);

const journey = VM.drawJourneyFunnel(mockCtx, 120, 320, 1680, [
  {{ label: '迎宾', metric: '100%', tone: 'ok' }},
  {{ label: '等待', metric: '>60% 零沟通', tone: 'error' }},
  {{ label: '讲解', metric: '近2/3 未讲清', tone: 'error' }},
], pal, {{ activeIdx: 1 }});
assert.equal(journey.anchors.length, 3);

const checklist = VM.drawEditorialChecklist(mockCtx, 864, 260, 560, [
  {{ id: 's1', title: '真实盘点', sub: '近两周接待', revealed: true, active: true }},
  {{ id: 's2', title: '手写弱项', revealed: false }},
], pal, {{ eyebrow: 'STEP 02', title: '门店闭环动作' }});
assert.equal(checklist.itemRects.length, 2);
assert.equal(checklist.itemRects[0].revealed, true);
assert.equal(checklist.itemRects[1].revealed, false);

// 2. DirectorStage v9.0.0 catches redundant data, double headline, and cross-scene chart repetition (incl. mergeFrameAudits)
const lines = [
  {{ id: 'b1', scene_id: 'sc05', layout_kind: 'data_sculpture', start: 0, end: 2.0 }},
  {{ id: 'b2', scene_id: 'sc11', layout_kind: 'data_sculpture', start: 2.0, end: 4.0 }},
];
const aud1 = DS.createFrameAuditor();
for (let f = 0; f < 48; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  aud1.beginFrame(f, t, st, st.layoutKind, {{ x: f * 0.6, y: 0, zoom: 1.0 + f * 0.001 }});
  aud1.recordHeadline('h_top', {{ x: 120, y: 112, w: 600, h: 48 }});
  aud1.recordHeadline('h_mid', {{ x: 600, y: 200, w: 600, h: 48 }});
  aud1.recordDataCarrier('left_bars', ['>60%', '>50%', '21%'], {{ x: 120, y: 400, w: 800, h: 300 }}, 'sculpture_bar');
  aud1.recordDataCarrier('right_kpi', ['21%', '>50%', '>60%'], {{ x: 1400, y: 200, w: 320, h: 500 }}, 'kpi_rail');
  aud1.recordVisualPattern('sculpture_bar', {{ skeleton: 'grid_7_5' }});
}}
const aud2 = DS.createFrameAuditor();
for (let f = 48; f < 96; f++) {{
  const t = f / 24;
  const st = DS.resolveTimeline(lines, t);
  aud2.beginFrame(f, t, st, st.layoutKind, {{ x: (f - 48) * 0.6, y: 0, zoom: 1.0 + (f - 48) * 0.001 }});
  aud2.recordHeadline('h_sc11', {{ x: 120, y: 112, w: 600, h: 48 }});
  aud2.recordVisualPattern('sculpture_bar', {{ skeleton: 'grid_7_5' }});
}}
const merged = DS.mergeFrameAudits([aud1.finalize(), aud2.finalize()]);
assert.ok(merged.redundant_data_violations.length >= 1, JSON.stringify(merged.redundant_data_violations));
assert.ok(merged.double_headline_violations.length >= 1, JSON.stringify(merged.double_headline_violations));
assert.ok(merged.visual_pattern_violations.some(v => v.kind === 'chart_repeat_limit'), JSON.stringify(merged.visual_pattern_violations));
assert.ok(merged.visual_pattern_violations.some(v => v.kind === 'adjacent_template_clone'), JSON.stringify(merged.visual_pattern_violations));
console.log('JS_V9_0_OK');
"""
        proc = subprocess.run(['node', '-e', js_check], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn('JS_V9_0_OK', proc.stdout)

        # 2. Blueprint validator catches redundant secondary zone, repeated built-in chart, adjacent clone & missing custom visual
        bad_bp = {
            'episode': 'ep06_bad',
            'scenes': [
                {'scene_id': 'sc05', 'layout_kind': 'data_sculpture', 'layout_skeleton': 'grid_7_5',
                 'l1_headline': '五大黑盒痛点', 'primary_visual': 'sculpture_bar',
                 'secondary_role': 'duplicate_kpi_rail', 'callout_style': 'floating_pill_wall'},
                {'scene_id': 'sc06', 'layout_kind': 'data_sculpture', 'layout_skeleton': 'grid_7_5',
                 'l1_headline': '维修流程四要素', 'primary_visual': 'sculpture_bar',
                 'secondary_role': 'none', 'callout_style': 'leader_line'},
                {'scene_id': 'sc07', 'layout_kind': 'kinetic_metaphor', 'layout_skeleton': 'center_focus',
                 'l1_headline': '例外场景', 'primary_visual': 'journey_funnel', 'secondary_role': 'none'},
                {'scene_id': 'sc08', 'layout_kind': 'summary_board', 'layout_skeleton': 'grid_5_7',
                 'l1_headline': '课后行动', 'primary_visual': 'editorial_checklist', 'secondary_role': 'none'},
            ],
        }
        bad_res = check_visual_blueprint.validate_blueprint(bad_bp)
        self.assertFalse(bad_res['ok'])
        joined = '\n'.join(bad_res['errors'])
        self.assertIn('重复展示同一组数据', joined)
        self.assertIn('漂浮圆角胶囊过多', joined)
        self.assertIn('复用了相同的版式骨架', joined)
        self.assertIn('上限 1 次', joined)
        self.assertIn('custom:*', joined)

        good_bp = {
            'episode': 'ep06_good',
            'scenes': [
                {'scene_id': 'sc05', 'layout_kind': 'data_sculpture', 'layout_skeleton': 'grid_7_5',
                 'l1_headline': '真正流失信任的，往往不是技术', 'primary_visual': 'horizontal_spotlight_bars',
                 'secondary_role': 'insight_pictogram', 'callout_style': 'leader_line'},
                {'scene_id': 'sc06', 'layout_kind': 'kinetic_metaphor', 'layout_skeleton': 'full_journey',
                 'l1_headline': '五步透明诊断服务动线', 'primary_visual': 'journey_funnel',
                 'secondary_role': 'none', 'callout_style': 'spotlight'},
                {'scene_id': 'sc11', 'layout_kind': 'kinetic_metaphor', 'layout_skeleton': 'grid_4_8',
                 'l1_headline': '维修沟通必须一次讲清四要素', 'primary_visual': 'custom:repair_quote_sheet',
                 'secondary_role': 'none', 'callout_style': 'leader_line'},
                {'scene_id': 'sc18', 'layout_kind': 'summary_board', 'layout_skeleton': 'grid_5_7',
                 'l1_headline': '真正带来门店改变的，是最后一步闭环动作', 'primary_visual': 'editorial_checklist',
                 'secondary_role': 'custom:workbook_artifact', 'callout_style': 'none'},
            ],
        }
        good_res = check_visual_blueprint.validate_blueprint(good_bp)
        self.assertTrue(good_res['ok'], good_res)
        md = check_visual_blueprint.render_markdown_table(good_bp)
        self.assertIn('custom:repair_quote_sheet', md)

        # 3. verify_delivery.py Gate A blocks v9.0.0 telemetry violations + invalid blueprint
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            vid = p / 'ok.mp4'
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=white:s=1920x1080:r=24:d=2.0',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2.0',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(vid),
            ], check=True)
            bad_v9 = p / 'bad_v9.json'
            bad_v9.write_text(json.dumps({
                'schema': 'kgxc-director-audit/1',
                'total_frames': 48, 'total_beats': 4,
                'card_box_ratio': 0.0, 'summary_board_ratio': 0.0, 'max_consecutive_card_box': 0,
                'floating_walk_violations': [], 'text_actor_overlap_violations': [], 'scene_replay_violations': [],
                'camera_sway_violations': [], 'premature_reveal_violations': [],
                'info_overwrite_violations': [], 'floating_prop_violations': [], 'rapid_card_flip_violations': [],
                'redundant_data_violations': [{'scene_id': 'sc05', 'beat_id': 'b2', 'carriers': ['left_bars', 'right_kpi']}],
                'double_headline_violations': [{'scene_id': 'sc05', 'beat_id': 'b1', 'headline_ids': ['h_top', 'h_mid']}],
                'visual_pattern_violations': [{'kind': 'chart_repeat_limit', 'pattern': 'sculpture_bar', 'reason': '内置图表 sculpture_bar 重复 2 次'}],
                'camera_summary': [{'scene_id': 'sc05', 'layout_kind': 'data_sculpture', 'frames': 48, 'zoom_span': 0.05, 'pan_span_px': 32.0}],
            }), encoding='utf-8')
            bp_file = p / 'bad_bp.json'
            bp_file.write_text(json.dumps(bad_bp, ensure_ascii=False), encoding='utf-8')

            out = verify_delivery.verify_video(
                vid, check_first_frame_cover=False, render_audit=bad_v9, visual_blueprint=bp_file
            )
            self.assertFalse(out['ok'])
            self.assertTrue(any('双载体重复' in e for e in out['errors']), out['errors'])
            self.assertTrue(any('多套 L1 主标题' in e for e in out['errors']), out['errors'])
            self.assertTrue(any('模板重复超限' in e for e in out['errors']), out['errors'])
            self.assertTrue(any('visual_blueprint' in out['checks'] for _ in [1]))


if __name__ == '__main__':
    unittest.main()
