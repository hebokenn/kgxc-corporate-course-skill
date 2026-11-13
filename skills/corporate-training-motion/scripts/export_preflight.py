"""Probe export inputs and optionally exercise two short normalized video seams."""
import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

VIDEO = ('codec_name', 'codec_tag_string', 'profile', 'level', 'width', 'height', 'pix_fmt',
         'sample_aspect_ratio', 'r_frame_rate', 'avg_frame_rate', 'time_base', 'field_order',
         'color_range', 'color_space', 'color_transfer', 'color_primaries', 'chroma_location',
         'extradata_hash')
AUDIO = ('codec_name', 'codec_tag_string', 'profile', 'sample_rate', 'channels',
         'channel_layout', 'sample_fmt', 'time_base', 'extradata_hash')
LABELS = ('intro', 'body', 'outro')


def run(command):
    return subprocess.run(command, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=120).stdout


def probe(path, ffprobe):
    data = json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-show_format',
                           '-show_data_hash', 'sha256', '-of', 'json', str(path)]))
    streams = []
    for s in data['streams']:
        kind = s.get('codec_type')
        if s.get('disposition', {}).get('attached_pic') or kind not in ('video', 'audio'):
            continue
        signature = {key: s.get(key) for key in (VIDEO if kind == 'video' else AUDIO)}
        if kind == 'video':
            signature['display_rotation'] = next(
                (side.get('rotation') for side in s.get('side_data_list', []) if 'rotation' in side),
                s.get('tags', {}).get('rotate'))
        duration = s.get('duration')
        streams.append(dict(type=kind, index=s['index'], signature=signature,
                            duration=duration, start_time=s.get('start_time')))
    videos = [s for s in streams if s['type'] == 'video']
    if len(videos) != 1:
        raise ValueError(f'{path.name}: exactly one primary video stream required')
    return dict(streams=streams, video=videos[0])


def clip_length(media):
    try:
        duration = float(media['video']['duration'])
    except (TypeError, ValueError):
        raise ValueError('Native seam trial needs a measured video-stream duration')
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid video-stream duration')
    return duration


def trial(left, right, profiles, ffmpeg, ffprobe, args):
    fps = float(args.fps)
    lengths = [clip_length(p) for p in profiles]
    windows = [min(args.seconds, length) for length in lengths]
    expected = [max(1, round(w * fps)) for w in windows]
    normalize = (f'fps={args.fps},scale={args.width}:{args.height}:'
                 'force_original_aspect_ratio=decrease:force_divisible_by=2,'
                 f'pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2,'
                 'setsar=1,format=yuv420p,setpts=PTS-STARTPTS')
    i, j = (p['video']['index'] for p in profiles)
    with tempfile.TemporaryDirectory(prefix='kgxc-export-seam-') as directory:
        output = Path(directory) / 'trial.mp4'
        run([ffmpeg, '-nostdin', '-v', 'error', '-xerror',
             '-ss', f'{max(0, lengths[0] - windows[0]):.6f}', '-t', str(windows[0]), '-i', str(left),
             '-t', str(windows[1]), '-i', str(right), '-filter_complex',
             f'[0:{i}]{normalize}[left];[1:{j}]{normalize}[right];'
             '[left][right]concat=n=2:v=1:a=0[out]',
             '-map', '[out]', '-an', '-c:v', 'libx264', '-preset', 'veryfast', str(output)])
        run([ffmpeg, '-nostdin', '-v', 'error', '-xerror', '-err_detect', 'explode',
             '-i', str(output), '-map', '0:v:0', '-f', 'null', '-'])
        rows = json.loads(run([ffprobe, '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                               '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(output)]))
        actual = int(rows['streams'][0]['nb_read_frames'])
        if abs(actual - sum(expected)) > 2:
            raise ValueError(f'Seam trial decoded {actual} frames, expected about {sum(expected)}')
        return dict(status='passed', decoded_frames=actual, expected_approx_frames=sum(expected),
                    scope='normalized-video-only; not actual course mix or final export proof')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for label in LABELS:
        parser.add_argument('--' + label, type=Path, required=True)
    parser.add_argument('--trial', action='store_true', help='exercise normalized video seam fixtures')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--fps', type=Fraction, default=Fraction(30))
    parser.add_argument('--seconds', type=float, default=1.0, help='seconds on each side of each seam')
    args = parser.parse_args()
    if (not all(2 <= n <= 4096 and n % 2 == 0 for n in (args.width, args.height))
            or not 1 <= args.fps <= 120 or not 0.2 <= args.seconds <= 3):
        parser.error('use even dimensions 2–4096, fps 1–120, and seconds 0.2–3')
    ffprobe = os.environ.get('FFPROBE', 'ffprobe')
    ffmpeg = os.environ.get('FFMPEG', 'ffmpeg')
    report = dict(schema_version=1, status='passed', trials={})
    try:
        paths = [getattr(args, label).resolve(strict=True) for label in LABELS]
        if not all(path.is_file() for path in paths):
            raise ValueError('Each input must be a regular media file')
        media = [probe(path, ffprobe) for path in paths]
        report['inputs'] = dict(zip(LABELS, media))
        report['target'] = dict(width=args.width, height=args.height, fps=str(args.fps),
                                pixel_format='yuv420p', sample_aspect_ratio='1:1')
        mismatches = []
        ref = media[0]['streams']
        for label, item in zip(LABELS[1:], media[1:]):
            actual = item['streams']
            if [s['type'] for s in actual] != [s['type'] for s in ref]:
                mismatches.append(dict(input=label, field='stream_layout'))
                continue
            for index, (a, b) in enumerate(zip(ref, actual)):
                for field, old in a['signature'].items():
                    if old != b['signature'][field]:
                        mismatches.append(dict(input=label, stream=index, field=field,
                                               intro=old, actual=b['signature'][field]))
        report['stream_copy'] = dict(status='normalize-required' if mismatches else 'matching-signatures-only',
                                     mismatches=mismatches, verified=False)
        report['status'] = 'requires-normalization' if mismatches else 'probe-complete'
        if args.trial:
            for i in range(2):
                name = LABELS[i] + '_' + LABELS[i + 1]
                report['trials'][name] = trial(paths[i], paths[i + 1], media[i:i + 2], ffmpeg, ffprobe, args)
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as e:
        report.update(status='failed', error=getattr(e, 'stderr', None) or str(e))
        print(json.dumps(report, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 2 if mismatches else 0


if __name__ == '__main__':
    raise SystemExit(main())
