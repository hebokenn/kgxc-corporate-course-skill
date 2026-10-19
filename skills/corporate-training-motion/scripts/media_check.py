#!/usr/bin/env python3
"""Check one explicitly selected MP4. Audio presence cannot prove narration quality."""
import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

def check(path, width=1920, height=1080, fps=30, require_audio=True):
    errors = []
    path = Path(path)
    if not path.is_file():
        return ['MEDIA_MISSING: ' + str(path)]
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        return ['MEDIA_TOOLS: ffprobe and ffmpeg required']
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams',
                            '-show_format', '-of', 'json', str(path)],
                           capture_output=True, text=True)
    if probe.returncode:
        return ['MEDIA_PROBE: unreadable file']
    try:
        data = json.loads(probe.stdout)
        video = next(s for s in data['streams'] if s.get('codec_type') == 'video')
        audio = [s for s in data['streams'] if s.get('codec_type') == 'audio']
        if (video.get('width'), video.get('height')) != (width, height):
            errors.append('MEDIA_SIZE: dimensions mismatch')
        if Fraction(video.get('r_frame_rate', '0')) != Fraction(str(fps)):
            errors.append('MEDIA_FPS: frame rate mismatch')
        if video.get('codec_name') != 'h264' or video.get('pix_fmt') != 'yuv420p':
            errors.append('MEDIA_VIDEO_FORMAT: H264 yuv420p required')
        if float(data['format'].get('duration', 0)) <= 0:
            errors.append('MEDIA_DURATION: positive duration required')
        if require_audio and not audio:
            errors.append('MEDIA_AUDIO: narrated output has no audio stream')
        if require_audio and audio and any(s.get('codec_name') != 'aac' for s in audio):
            errors.append('MEDIA_AUDIO_FORMAT: AAC required')
    except (ValueError, KeyError, StopIteration, ZeroDivisionError):
        errors.append('MEDIA_METADATA: missing or invalid metadata')
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                             '-f', 'null', '-'], capture_output=True, text=True)
    if decode.returncode or decode.stderr.strip():
        errors.append('MEDIA_DECODE: full decode failed')
    return errors

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video', type=Path)
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--visual-only', action='store_true')
    args = ap.parse_args()
    errors = check(args.video, args.width, args.height, args.fps, not args.visual_only)
    print(json.dumps({'ok': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
