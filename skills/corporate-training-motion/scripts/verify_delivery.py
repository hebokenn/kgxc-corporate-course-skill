#!/usr/bin/env python3
"""Unified post-render technical & packaging self-check for delivered MP4/SRT/cover.

Verifies stream integrity, 48kHz AAC full decode, audio tail energy,
single-frame (frame 0) cover policy, attached_pic, and single-line SRT hygiene.
Note: Technical pass never substitutes for human/visual listening and aesthetics.
"""
import argparse
import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path


def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        text=True,
    ))


def read_srt(path: Path) -> list:
    content = path.read_text(encoding='utf-8-sig').strip()
    if not content:
        return []
    def parse_ts(ts):
        h, m, s, ms = map(int, re.split('[:,]', ts))
        return h * 3600 + m * 60 + s + ms / 1000.0
    cues = []
    for block in re.split(r'\n\s*\n', content):
        lines = block.splitlines()
        if len(lines) < 3 or ' --> ' not in lines[1]:
            raise ValueError(f'SRT 格式无效: {block[:60]}')
        a, b = lines[1].split(' --> ')
        cues.append({'start': parse_ts(a), 'end': parse_ts(b), 'text': '\n'.join(lines[2:])})
    return cues


def frame_rgb(video: Path, frame_index: int, stream_index: int) -> bytes:
    return subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(video), '-map', f'0:{stream_index}',
        '-vf', f'select=eq(n\\,{frame_index}),scale=320:180,format=rgb24',
        '-frames:v', '1', '-f', 'rawvideo', '-',
    ])


def sample_frames_rgb(video: Path, frame_indices: list, stream_index: int) -> dict:
    """Decode multiple frame indices in chunked ffmpeg passes (320x180 rgb24) to avoid select-expr parser limits."""
    unique = sorted({max(0, int(i)) for i in frame_indices})
    if not unique:
        return {}
    stride = 320 * 180 * 3
    out = {}
    batch_size = 50
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]
        expr = '+'.join(f'eq(n\\,{i})' for i in batch)
        raw = subprocess.check_output([
            'ffmpeg', '-v', 'error', '-i', str(video), '-map', f'0:{stream_index}',
            '-vf', f'select={expr},scale=320:180,format=rgb24',
            '-fps_mode', 'passthrough', '-f', 'rawvideo', '-',
        ])
        for pos, idx in enumerate(batch):
            if (pos + 1) * stride <= len(raw):
                out[idx] = raw[pos * stride:(pos + 1) * stride]
    return out


def _main_canvas_mae(buf_a: bytes, buf_b: bytes) -> float:
    """Compare main visual canvas (top 80% rows, excluding bottom subtitle strip)."""
    import numpy as np
    rows = 144  # 144 / 180 = top 80%, excludes bottom caption zone
    arr_a = np.frombuffer(buf_a, dtype=np.uint8).reshape(180, 320, 3)[:rows].astype(np.float32)
    arr_b = np.frombuffer(buf_b, dtype=np.uint8).reshape(180, 320, 3)[:rows].astype(np.float32)
    return float(np.mean(np.abs(arr_a - arr_b)))


def _coarse_structure_stats(buf_a: bytes, buf_b: bytes) -> tuple:
    """Return (coarse_mae, top3_block_mae) on 9x20 macro-blocks (16x16 each) of top-80% canvas.

    Distinguishes genuine localized steady-camera reveals (high top3_block_mae and high coarse/raw ratio)
    from fake ±12px camera-wiggle jitter (low coarse_mae and low coarse/raw ratio).
    """
    import numpy as np
    arr_a = np.frombuffer(buf_a, dtype=np.uint8).reshape(180, 320, 3)[:144].astype(np.float32)
    arr_b = np.frombuffer(buf_b, dtype=np.uint8).reshape(180, 320, 3)[:144].astype(np.float32)
    # 144 = 9 * 16, 320 = 20 * 16 -> 9x20 coarse grid
    coarse_a = arr_a.reshape(9, 16, 20, 16, 3).mean(axis=(1, 3))
    coarse_b = arr_b.reshape(9, 16, 20, 16, 3).mean(axis=(1, 3))
    block_diff = np.mean(np.abs(coarse_a - coarse_b), axis=2)
    coarse_mae = float(np.mean(block_diff))
    top3_blk = float(np.mean(np.sort(block_diff.ravel())[-3:]))
    return coarse_mae, top3_blk


def _coarse_structure_mae(buf_a: bytes, buf_b: bytes) -> float:
    return _coarse_structure_stats(buf_a, buf_b)[0]


def _parse_fps(rate_str: str) -> float:
    if not rate_str:
        return 24.0
    if '/' in str(rate_str):
        num, den = str(rate_str).split('/', 1)
        return float(num) / max(float(den), 1.0)
    return float(rate_str)


def check_beat_visual_pacing(video: Path, stream_index: int, fps: float, total_dur: float,
                             timeline_path: Path, max_static_span: float = 5.0,
                             min_scene_change_mae: float = 2.2,
                             steady_scenes: set = None) -> dict:
    """Detect PPT stagnation, micro-wiggle cheating, and beat-boundary animation replays."""
    data = json.loads(timeline_path.read_text(encoding='utf-8'))
    beats = data.get('timeline') or data.get('lines') or []
    steady_scenes = steady_scenes or set()
    issues = []
    if not beats:
        return {'beats_checked': 0, 'stagnant_spans': [], 'replay_pairs': [], 'issues': ['timeline.json 未包含任何配音 Beat']}

    def _is_steady_board(beat: dict) -> bool:
        return (beat.get('layout_kind') == 'summary_board') or (beat.get('scene_id') in steady_scenes)

    max_frame = max(1, int(total_dur * fps) - 1)
    beat_frames = []
    all_indices = []
    for b in beats:
        start = float(b.get('start', 0.0))
        end = float(b.get('end', start + 0.5))
        dur_b = max(0.1, end - start)
        pad = min(0.25, dur_b * 0.2)
        s_f = max(1, min(max_frame, round((start + pad) * fps)))
        mid_f = max(1, min(max_frame, round(((start + end) * 0.5) * fps)))
        e_f = max(1, min(max_frame, round((end - pad) * fps)))
        beat_frames.append((b, s_f, mid_f, e_f))
        all_indices.extend([s_f, mid_f, e_f])

    frames = sample_frames_rgb(video, all_indices, stream_index)
    stagnant_spans = []
    replay_pairs = []
    run_beats = [beats[0]]
    run_start = float(beats[0].get('start', 0.0))
    transitions = []

    def _has_real_visual_change(buf_a: bytes, buf_b: bytes, is_steady_pair: bool) -> tuple:
        mae = _main_canvas_mae(buf_a, buf_b)
        coarse, top3_blk = _coarse_structure_stats(buf_a, buf_b)
        solid_local_reveal = (top3_blk >= 11.5) and (coarse >= 0.38 * max(mae, 0.01))
        if is_steady_pair:
            changed = (mae >= 0.85) or solid_local_reveal
        else:
            global_change = (mae >= min_scene_change_mae) and (coarse >= 1.35 or mae >= 5.5)
            changed = global_change or solid_local_reveal
        return changed, mae, coarse, top3_blk

    for idx in range(1, len(beats)):
        prev_b, prev_s, prev_mid, prev_e = beat_frames[idx - 1]
        cur_b, cur_s, cur_mid, cur_e = beat_frames[idx]
        if prev_mid in frames and cur_mid in frames:
            steady_pair = _is_steady_board(prev_b) and _is_steady_board(cur_b)
            changed_mid, mae_m, coarse_m, top3_m = _has_real_visual_change(frames[prev_mid], frames[cur_mid], steady_pair)
            changed_end, mae_e, coarse_e, top3_e = (False, 0.0, 0.0, 0.0)
            if prev_e in frames and cur_e in frames:
                changed_end, mae_e, coarse_e, top3_e = _has_real_visual_change(frames[prev_e], frames[cur_e], steady_pair)
            use_end = (top3_e > top3_m and mae_e >= mae_m) or (changed_end and not changed_mid)
            mae = mae_e if use_end else mae_m
            coarse = coarse_e if use_end else coarse_m
            top3_blk = top3_e if use_end else top3_m
            transitions.append({
                'from': prev_b['id'], 'to': cur_b['id'],
                'main_mae': round(mae, 2), 'coarse_mae': round(coarse, 2), 'top3_block_mae': round(top3_blk, 2),
            })
            is_stagnant = not (changed_mid or changed_end)
            if is_stagnant:
                run_beats.append(cur_b)
            else:
                span = float(run_beats[-1].get('end', 0.0)) - run_start
                if len(run_beats) >= 2 and span >= max_static_span:
                    ids = ','.join(str(x.get('id')) for x in run_beats)
                    stagnant_spans.append({'beats': [x.get('id') for x in run_beats], 'seconds': round(span, 2)})
                    issues.append(f'连续 Beat ({ids}) 持续 {span:.1f}s 主画面几乎未切换（含微抖动静态 PPT 滞留），请为每句配置真实意象推进')
                run_beats = [cur_b]
                run_start = float(cur_b.get('start', 0.0))

        # Detect animation reset / replay across adjacent beats
        if prev_s in frames and prev_e in frames and cur_s in frames:
            prev_anim = _main_canvas_mae(frames[prev_s], frames[prev_e])
            snap_to_start = _main_canvas_mae(frames[cur_s], frames[prev_s])
            diff_from_end = _main_canvas_mae(frames[cur_s], frames[prev_e])
            if prev_anim >= 3.0 and snap_to_start <= 2.2 and diff_from_end >= snap_to_start + 2.0:
                replay_pairs.append({
                    'from': prev_b.get('id'), 'to': cur_b.get('id'),
                    'prev_anim_mae': round(prev_anim, 2),
                    'snap_to_start_mae': round(snap_to_start, 2),
                    'diff_from_end_mae': round(diff_from_end, 2),
                })
                issues.append(
                    f'Beat {prev_b.get("id")} -> {cur_b.get("id")} 检测到动画归零重播（新句起点回弹至上句起点），请使用 DirectorStage 连续 sceneT 状态机'
                )

    span = float(run_beats[-1].get('end', 0.0)) - run_start
    if len(run_beats) >= 2 and span >= max_static_span:
        ids = ','.join(str(x.get('id')) for x in run_beats)
        stagnant_spans.append({'beats': [x.get('id') for x in run_beats], 'seconds': round(span, 2)})
        issues.append(f'连续 Beat ({ids}) 持续 {span:.1f}s 主画面几乎未切换（含微抖动静态 PPT 滞留），请为每句配置真实意象推进')

    for b, s_f, _, e_f in beat_frames:
        dur_b = float(b.get('end', 0.0)) - float(b.get('start', 0.0))
        if dur_b > max_static_span and s_f in frames and e_f in frames:
            changed_single, _, _, _ = _has_real_visual_change(frames[s_f], frames[e_f], _is_steady_board(b))
            if not changed_single:
                issues.append(f'Beat {b.get("id")} 时长 {dur_b:.1f}s 且首尾主画面变化过小，建议拆句或补强视觉演进')

    return {
        'beats_checked': len(beats),
        'transitions': transitions,
        'stagnant_spans': stagnant_spans,
        'replay_pairs': replay_pairs,
        'issues': issues,
    }


def check_render_audit(audit_path: Path, max_card_box_ratio: float = 0.25,
                       max_consecutive_card_box: int = 2,
                       max_summary_board_ratio: float = 0.22) -> dict:
    """Validate DirectorStage render_audit.json telemetry as a non-negotiable v8.1 hard gate."""
    data = json.loads(audit_path.read_text(encoding='utf-8'))
    errors = []
    floating = data.get('floating_walk_violations') or []
    overlaps = data.get('text_actor_overlap_violations') or []
    replays = data.get('scene_replay_violations') or []
    sways = data.get('camera_sway_violations') or []
    premature = data.get('premature_reveal_violations') or []
    card_ratio = float(data.get('card_box_ratio', 0.0))
    summary_ratio = float(data.get('summary_board_ratio', 0.0))
    max_consec = int(data.get('max_consecutive_card_box', 0))
    cams = data.get('camera_summary') or []

    if floating:
        sample = floating[0]
        errors.append(
            f'检测到 {len(floating)} 帧人物无接地步态滑行/飘移（如 {sample.get("beat_id")} {sample.get("actor")} dx={sample.get("dx")}px），必须传入 walkState'
        )
    if overlaps:
        sample = overlaps[0]
        errors.append(
            f'检测到 {len(overlaps)} 处文字/气泡/弹幕与人物或字幕安全区重叠（如 {sample.get("beat_id")} {sample.get("text_id")} 压住 {sample.get("actor")}）'
        )
    if replays:
        sample = replays[0]
        errors.append(
            f'检测到 {len(replays)} 处同场景内 sceneT 回退归零重播（如 {sample.get("scene_id")} / {sample.get("beat_id")}）'
        )
    if sways:
        sample = sways[0]
        errors.append(
            f'检测到 {len(sways)} 个场景存在无意义镜头晃动/漂移（如 {sample.get("scene_id")} {sample.get("layout_kind")}: {sample.get("reason")}）'
        )
    if premature:
        sample = premature[0]
        errors.append(
            f'检测到 {len(premature)} 处画面元素抢先旁白出现（如 {sample.get("scene_id")}/{sample.get("beat_id")} {sample.get("item_id")} 提前 {sample.get("lead_sec")}s），请绑定 speech_start / phraseTime'
        )
    if card_ratio > max_card_box_ratio:
        errors.append(
            f'PPT 框体版式占比超标（{card_ratio:.1%} > {max_card_box_ratio:.0%} 上限），请将白框卡片改写为实景演出或开放画布动效'
        )
    if summary_ratio > max_summary_board_ratio:
        errors.append(
            f'定机位总结板书占比超标（{summary_ratio:.1%} > {max_summary_board_ratio:.0%} 上限），summary_board 仅用于总结卡与收尾清单'
        )
    if max_consec > max_consecutive_card_box:
        errors.append(
            f'连续出现 {max_consec} 个 PPT 框体 Beat（上限 {max_consecutive_card_box} 个），禁止连续卡片翻页'
        )
    dead_cams = [
        c for c in cams
        if c.get('layout_kind') in ('cinematic_store', 'kinetic_metaphor', 'data_sculpture')
        and int(c.get('frames', 0)) >= 48
        and float(c.get('zoom_span', 0.0)) < 0.035
        and float(c.get('pan_span_px', 0.0)) < 26.0
    ]
    if dead_cams:
        ids = ', '.join(str(c.get('scene_id')) for c in dead_cams[:5])
        errors.append(
            f'{len(dead_cams)} 个动态场景缺少真实电影级运镜（zoom_span<0.035 且 pan<26px）: {ids}'
        )

    pb = data.get('progress_bar_summary')
    total_beats = int(data.get('total_beats', 0))
    if total_beats >= 12:
        if not isinstance(pb, dict) or pb.get('mode') != 'segmented' or int(pb.get('segment_count', 0)) < 2:
            errors.append(
                '未检测到分段章节进度条（禁止退化为单根总进度条），请调用 VisualMetaphors.drawSegmentedProgressBar + DirectorStage.buildNavSegments 并记录 auditor.recordProgressBar()'
            )
        elif int(pb.get('visited_segments', 0)) < min(2, int(pb.get('segment_count', 0))):
            errors.append(
                f'分段进度条未随时间轴正常切换（仅激活 {pb.get("visited_segments", 0)}/{pb.get("segment_count", 0)} 段），请检查 buildNavSegments 场景绑定'
            )

    steady_scenes = [c.get('scene_id') for c in cams if c.get('layout_kind') == 'summary_board' and c.get('scene_id')]
    return {
        'total_frames': data.get('total_frames', 0),
        'total_beats': total_beats,
        'card_box_ratio': card_ratio,
        'summary_board_ratio': summary_ratio,
        'max_consecutive_card_box': max_consec,
        'floating_walk_count': len(floating),
        'text_actor_overlap_count': len(overlaps),
        'scene_replay_count': len(replays),
        'camera_sway_count': len(sways),
        'premature_reveal_count': len(premature),
        'progress_bar': pb,
        'steady_scenes': steady_scenes,
        'dead_camera_scenes': [c.get('scene_id') for c in dead_cams],
        'errors': errors,
    }


def verify_video(video: Path, srt: Path = None, cover: Path = None,
                 require_attached_pic: bool = False, check_first_frame_cover: bool = True,
                 strict_no_punctuation: bool = True, max_srt_chars: int = 28,
                 timeline: Path = None, visual_audit: Path = None,
                 render_audit: Path = None, strict_ppt_guard: bool = False) -> dict:
    errors = []
    warnings = []
    report = {'video': str(video), 'ok': False, 'errors': errors, 'warnings': warnings, 'checks': {}}

    if not video.is_file():
        errors.append('视频文件不存在')
        return report

    meta = probe(video)
    main_videos = [s for s in meta.get('streams', []) if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    attached = [s for s in meta.get('streams', []) if s.get('codec_type') == 'video' and s.get('disposition', {}).get('attached_pic')]
    audios = [s for s in meta.get('streams', []) if s.get('codec_type') == 'audio']

    if len(main_videos) != 1:
        errors.append(f'主视频流数量异常: {len(main_videos)}')
        return report
    if len(audios) != 1:
        errors.append(f'音频流数量异常: {len(audios)}')
        return report

    v = main_videos[0]
    a = audios[0]
    dur = float(meta['format'].get('duration', 0))
    if (v.get('width'), v.get('height')) != (1920, 1080):
        errors.append(f'分辨率非 1920x1080: {v.get("width")}x{v.get("height")}')
    if v.get('pix_fmt') != 'yuv420p':
        errors.append(f'像素格式非 yuv420p: {v.get("pix_fmt")}')
    if a.get('sample_rate') != '48000':
        errors.append(f'音频采样率非 48000Hz: {a.get("sample_rate")}')
    if dur <= 0:
        errors.append('视频时长无效')

    if require_attached_pic and not attached:
        errors.append('容器缺少 attached_pic 封面流')
    if cover is not None and not cover.is_file():
        errors.append(f'封面文件不存在: {cover}')

    # Full decode + audio stats
    decode = subprocess.run([
        'ffmpeg', '-nostdin', '-hide_banner', '-nostats', '-v', 'info', '-xerror', '-err_detect', 'explode',
        '-i', str(video), '-map', f'0:{v["index"]}', '-map', f'0:{a["index"]}',
        '-af', 'astats=metadata=0:reset=0', '-f', 'null', '-',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if decode.returncode != 0:
        errors.append('完整音视频流解码存在错误')
    peaks = re.findall(r'Peak level dB:\s*(-?(?:inf|[0-9]+(?:\.[0-9]+)?))', decode.stderr)
    if not peaks or float(peaks[-1]) <= -90:
        errors.append('音轨完全静音或无有效音频样本')

    # Tail audio cutoff check (last 0.15s)
    tail_start = max(0.0, dur - 0.15)
    tail_probe = subprocess.run([
        'ffmpeg', '-nostdin', '-hide_banner', '-nostats', '-v', 'info',
        '-ss', f'{tail_start:.3f}', '-i', str(video), '-map', f'0:{a["index"]}',
        '-af', 'astats=metadata=0:reset=0', '-f', 'null', '-',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    tail_peaks = re.findall(r'Peak level dB:\s*(-?(?:inf|[0-9]+(?:\.[0-9]+)?))', tail_probe.stderr)
    tail_db = float(tail_peaks[-1]) if tail_peaks else -999.0
    if tail_db > -18.0:
        warnings.append(f'最后 0.15s 峰值较高 ({tail_db:.1f} dB)，请人工确认尾句完整无截断或多余起音')

    # Cover frame 0 vs frame 1 check (must not linger on static cover beyond frame 0)
    if check_first_frame_cover and cover and cover.is_file():
        import numpy as np
        f0 = np.frombuffer(frame_rgb(video, 0, v['index']), dtype=np.uint8).astype(np.float32)
        f1 = np.frombuffer(frame_rgb(video, 1, v['index']), dtype=np.uint8).astype(np.float32)
        cov = np.frombuffer(subprocess.check_output([
            'ffmpeg', '-v', 'error', '-i', str(cover), '-vf', 'scale=320:180,format=rgb24', '-f', 'rawvideo', '-',
        ]), dtype=np.uint8).astype(np.float32)
        diff0 = float(np.mean(np.abs(f0 - cov)))
        diff1 = float(np.mean(np.abs(f1 - cov)))
        report['checks']['cover_frame0_mae'] = round(diff0, 2)
        report['checks']['cover_frame1_mae'] = round(diff1, 2)
        if diff0 > 12.0:
            errors.append(f'第 0 帧与封面图差异过大 (MAE={diff0:.1f})，首帧封面未写入')
        if diff1 < 2.0:
            errors.append(f'第 1 帧仍停留在封面图 (MAE={diff1:.1f})，违反默认仅首帧封面规范')

    # SRT checks
    if srt is not None:
        if not srt.is_file():
            errors.append(f'字幕文件不存在: {srt}')
        else:
            cues = read_srt(srt)
            if not cues:
                errors.append('字幕文件为空')
            for i, c in enumerate(cues):
                if '\n' in c['text']:
                    errors.append(f'字幕第 {i + 1} 条包含换行，须为单行')
                    break
                if len(c['text']) > max_srt_chars:
                    warnings.append(f'字幕第 {i + 1} 条较长 ({len(c["text"])} 字): {c["text"]}')
                if strict_no_punctuation and any(unicodedata.category(ch).startswith('P') for ch in c['text']):
                    errors.append(f'字幕第 {i + 1} 条含标点: {c["text"]}')
                    break
                if i > 0 and cues[i - 1]['end'] > c['start'] + 0.002:
                    errors.append(f'字幕第 {i} 与 {i + 1} 条时间重叠')
                    break
                if c['end'] > dur + 0.1:
                    errors.append(f'字幕第 {i + 1} 条超出视频总时长')
                    break
            report['checks']['srt_cues'] = len(cues)

    steady_scenes = set()
    if render_audit is not None:
        if not render_audit.is_file():
            errors.append(f'渲染遥测审计文件不存在: {render_audit}')
        else:
            ra = check_render_audit(render_audit)
            report['checks']['render_audit'] = ra
            steady_scenes = set(ra.get('steady_scenes') or [])
            errors.extend(ra['errors'])

    if timeline is not None:
        if not timeline.is_file():
            errors.append(f'时间轴文件不存在: {timeline}')
        else:
            fps = _parse_fps(v.get('avg_frame_rate') or v.get('r_frame_rate'))
            pacing = check_beat_visual_pacing(video, v['index'], fps, dur, timeline, steady_scenes=steady_scenes)
            report['checks']['beat_pacing'] = pacing
            target = errors if strict_ppt_guard else warnings
            target.extend(pacing['issues'])
            if srt is not None and srt.is_file():
                tl_data = json.loads(timeline.read_text(encoding='utf-8'))
                tl_beats = tl_data.get('timeline') or tl_data.get('lines') or []
                srt_cues = read_srt(srt)
                if tl_beats and srt_cues:
                    tail_drift = abs(float(srt_cues[-1]['end']) - float(tl_beats[-1].get('end', 0.0)))
                    report['checks']['srt_timeline_tail_drift_sec'] = round(tail_drift, 3)
                    if tail_drift > 0.8:
                        errors.append(
                            f'字幕文件与渲染时间轴尾部漂移 {tail_drift:.2f}s（请核对局部配音热替换后 .srt 与 timeline.json 是否同步）'
                        )

    if visual_audit is not None:
        if not visual_audit.is_file():
            errors.append(f'画面密度审计文件不存在: {visual_audit}')
        else:
            audit_data = json.loads(visual_audit.read_text(encoding='utf-8'))
            overloaded = [
                row for row in audit_data.get('beats', [])
                if int(row.get('screen_chars', 0)) > 45
            ]
            report['checks']['visual_audit_beats'] = len(audit_data.get('beats', []))
            report['checks']['overloaded_screen_beats'] = [r.get('id') for r in overloaded]
            if overloaded:
                msg = f'同屏文字过载（>45 字）的镜头: {", ".join(str(r.get("id")) for r in overloaded)}'
                (errors if strict_ppt_guard else warnings).append(msg)

    report['checks'].update({
        'resolution': f'{v.get("width")}x{v.get("height")}',
        'fps': v.get('avg_frame_rate'),
        'duration': round(dur, 3),
        'sample_rate': a.get('sample_rate'),
        'has_attached_pic': bool(attached),
        'tail_150ms_peak_db': None if math.isinf(tail_db) else round(tail_db, 2),
        'scope': 'technical decode, single-frame cover, SRT, beat-pacing/replay anti-cheat, and v8 DirectorStage render_audit hard gate',
    })
    report['ok'] = not errors
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--srt', type=Path)
    p.add_argument('--cover', type=Path)
    p.add_argument('--timeline', type=Path, help='Optional tts_sync timeline.json to detect stagnant PPT stretches and animation replays')
    p.add_argument('--visual-audit', type=Path, help='Optional per-beat screen_chars / visual_metaphor audit JSON')
    p.add_argument('--render-audit', type=Path, help='v8.0 DirectorStage render_audit.json hard gate (blocks floating walk, text overlap, PPT >25%%, dead camera)')
    p.add_argument('--strict-ppt-guard', action='store_true', help='Fail instead of warn when PPT stagnation, animation replay, or dense text is found')
    p.add_argument('--require-attached-pic', action='store_true')
    p.add_argument('--no-first-frame-cover', action='store_true')
    p.add_argument('--allow-punctuation', action='store_true')
    args = p.parse_args()
    res = verify_video(
        args.video, args.srt, args.cover,
        require_attached_pic=args.require_attached_pic,
        check_first_frame_cover=not args.no_first_frame_cover,
        strict_no_punctuation=not args.allow_punctuation,
        timeline=args.timeline,
        visual_audit=args.visual_audit,
        render_audit=args.render_audit,
        strict_ppt_guard=args.strict_ppt_guard,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
