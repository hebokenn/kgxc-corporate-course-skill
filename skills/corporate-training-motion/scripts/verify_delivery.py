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
    """Decode multiple frame indices in one ffmpeg pass (320x180 rgb24)."""
    unique = sorted({max(0, int(i)) for i in frame_indices})
    if not unique:
        return {}
    expr = '+'.join(f'eq(n\\,{i})' for i in unique)
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(video), '-map', f'0:{stream_index}',
        '-vf', f'select={expr},scale=320:180,format=rgb24',
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-',
    ])
    stride = 320 * 180 * 3
    return {
        idx: raw[pos * stride:(pos + 1) * stride]
        for pos, idx in enumerate(unique)
        if (pos + 1) * stride <= len(raw)
    }


def _main_canvas_mae(buf_a: bytes, buf_b: bytes) -> float:
    """Compare main visual canvas (top 80% rows, excluding bottom subtitle strip)."""
    import numpy as np
    rows = 144  # 144 / 180 = top 80%, excludes bottom caption zone
    arr_a = np.frombuffer(buf_a, dtype=np.uint8).reshape(180, 320, 3)[:rows].astype(np.float32)
    arr_b = np.frombuffer(buf_b, dtype=np.uint8).reshape(180, 320, 3)[:rows].astype(np.float32)
    return float(np.mean(np.abs(arr_a - arr_b)))


def _parse_fps(rate_str: str) -> float:
    if not rate_str:
        return 24.0
    if '/' in str(rate_str):
        num, den = str(rate_str).split('/', 1)
        return float(num) / max(float(den), 1.0)
    return float(rate_str)


def check_beat_visual_pacing(video: Path, stream_index: int, fps: float, total_dur: float,
                             timeline_path: Path, max_static_span: float = 5.0,
                             min_scene_change_mae: float = 2.2) -> dict:
    """Detect PPT-like visual stagnation across consecutive spoken beats (ignoring bottom subtitles)."""
    data = json.loads(timeline_path.read_text(encoding='utf-8'))
    beats = data.get('timeline') or data.get('lines') or []
    issues = []
    if not beats:
        return {'beats_checked': 0, 'stagnant_spans': [], 'issues': ['timeline.json 未包含任何配音 Beat']}

    max_frame = max(1, int(total_dur * fps) - 1)
    sample_plan = []
    for b in beats:
        start = float(b.get('start', 0.0))
        end = float(b.get('end', start + 0.5))
        mid_f = max(1, min(max_frame, round(((start + end) * 0.5) * fps)))
        sample_plan.append((b, mid_f))
        if end - start > max_static_span:
            s_f = max(1, min(max_frame, round((start + 0.25) * fps)))
            e_f = max(1, min(max_frame, round((end - 0.25) * fps)))
            sample_plan.append((b, s_f))
            sample_plan.append((b, e_f))

    frames = sample_frames_rgb(video, [f for _, f in sample_plan], stream_index)
    stagnant_spans = []
    run_beats = [beats[0]]
    run_start = float(beats[0].get('start', 0.0))
    transitions = []

    for idx in range(1, len(beats)):
        prev_mid = max(1, min(max_frame, round(((float(beats[idx - 1]['start']) + float(beats[idx - 1]['end'])) * 0.5) * fps)))
        cur_mid = max(1, min(max_frame, round(((float(beats[idx]['start']) + float(beats[idx]['end'])) * 0.5) * fps)))
        if prev_mid in frames and cur_mid in frames:
            mae = _main_canvas_mae(frames[prev_mid], frames[cur_mid])
            transitions.append({'from': beats[idx - 1]['id'], 'to': beats[idx]['id'], 'main_mae': round(mae, 2)})
            if mae < min_scene_change_mae:
                run_beats.append(beats[idx])
                continue
        span = float(run_beats[-1].get('end', 0.0)) - run_start
        if len(run_beats) >= 2 and span >= max_static_span:
            ids = ','.join(str(x.get('id')) for x in run_beats)
            stagnant_spans.append({'beats': [x.get('id') for x in run_beats], 'seconds': round(span, 2)})
            issues.append(f'连续 Beat ({ids}) 持续 {span:.1f}s 主画面几乎未切换（PPT 式滞留），请为每句配置独立意象镜头')
        run_beats = [beats[idx]]
        run_start = float(beats[idx].get('start', 0.0))

    span = float(run_beats[-1].get('end', 0.0)) - run_start
    if len(run_beats) >= 2 and span >= max_static_span:
        ids = ','.join(str(x.get('id')) for x in run_beats)
        stagnant_spans.append({'beats': [x.get('id') for x in run_beats], 'seconds': round(span, 2)})
        issues.append(f'连续 Beat ({ids}) 持续 {span:.1f}s 主画面几乎未切换（PPT 式滞留），请为每句配置独立意象镜头')

    for b in beats:
        dur_b = float(b.get('end', 0.0)) - float(b.get('start', 0.0))
        if dur_b > max_static_span:
            s_f = max(1, min(max_frame, round((float(b['start']) + 0.25) * fps)))
            e_f = max(1, min(max_frame, round((float(b['end']) - 0.25) * fps)))
            if s_f in frames and e_f in frames and _main_canvas_mae(frames[s_f], frames[e_f]) < min_scene_change_mae:
                issues.append(f'Beat {b.get("id")} 时长 {dur_b:.1f}s 且首尾主画面变化过小，建议拆句或补强视觉演进')

    return {
        'beats_checked': len(beats),
        'transitions': transitions,
        'stagnant_spans': stagnant_spans,
        'issues': issues,
    }


def verify_video(video: Path, srt: Path = None, cover: Path = None,
                 require_attached_pic: bool = False, check_first_frame_cover: bool = True,
                 strict_no_punctuation: bool = True, max_srt_chars: int = 28,
                 timeline: Path = None, visual_audit: Path = None,
                 strict_ppt_guard: bool = False) -> dict:
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

    if timeline is not None:
        if not timeline.is_file():
            errors.append(f'时间轴文件不存在: {timeline}')
        else:
            fps = _parse_fps(v.get('avg_frame_rate') or v.get('r_frame_rate'))
            pacing = check_beat_visual_pacing(video, v['index'], fps, dur, timeline)
            report['checks']['beat_pacing'] = pacing
            target = errors if strict_ppt_guard else warnings
            target.extend(pacing['issues'])

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
        'scope': 'technical decode, single-frame cover, SRT, and optional beat-level visual pacing check',
    })
    report['ok'] = not errors
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--srt', type=Path)
    p.add_argument('--cover', type=Path)
    p.add_argument('--timeline', type=Path, help='Optional tts_sync timeline.json to detect stagnant PPT stretches')
    p.add_argument('--visual-audit', type=Path, help='Optional per-beat screen_chars / visual_metaphor audit JSON')
    p.add_argument('--strict-ppt-guard', action='store_true', help='Fail instead of warn when PPT stagnation or dense text is found')
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
        strict_ppt_guard=args.strict_ppt_guard,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
