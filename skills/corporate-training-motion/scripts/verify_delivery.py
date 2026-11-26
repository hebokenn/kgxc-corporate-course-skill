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


def verify_video(video: Path, srt: Path = None, cover: Path = None,
                 require_attached_pic: bool = False, check_first_frame_cover: bool = True,
                 strict_no_punctuation: bool = True, max_srt_chars: int = 28) -> dict:
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

    report['checks'].update({
        'resolution': f'{v.get("width")}x{v.get("height")}',
        'fps': v.get('avg_frame_rate'),
        'duration': round(dur, 3),
        'sample_rate': a.get('sample_rate'),
        'has_attached_pic': bool(attached),
        'tail_150ms_peak_db': None if math.isinf(tail_db) else round(tail_db, 2),
        'scope': 'technical decode, single-frame cover, and SRT check; visual/audio quality requires human/frame inspection',
    })
    report['ok'] = not errors
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--srt', type=Path)
    p.add_argument('--cover', type=Path)
    p.add_argument('--require-attached-pic', action='store_true')
    p.add_argument('--no-first-frame-cover', action='store_true')
    p.add_argument('--allow-punctuation', action='store_true')
    args = p.parse_args()
    res = verify_video(
        args.video, args.srt, args.cover,
        require_attached_pic=args.require_attached_pic,
        check_first_frame_cover=not args.no_first_frame_cover,
        strict_no_punctuation=not args.allow_punctuation,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
