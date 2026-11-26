#!/usr/bin/env python3
"""Minimal-visual-beat Qwen3-TTS synthesizer with incremental cache, tail safety check, and exact timeline/SRT output.

Usage:
  python3 tts_sync.py --lines lines.json --out-dir project/audio/ep01
  python3 tts_sync.py --lines lines.json --out-dir project/audio/ep01 --mix narration.wav --srt captions.srt
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TTS_SCRIPT = ROOT / 'scripts/qwen3_tts.py'


def sha_text(voice: str, text: str) -> str:
    return hashlib.sha256(f'{voice}\0{text.strip()}'.encode('utf-8')).hexdigest()


def probe_wav(wav: Path) -> dict:
    out = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of', 'json', str(wav)],
        text=True,
    )
    data = json.loads(out)
    stream = (data.get('streams') or [{}])[0]
    return {
        'duration': float(data['format']['duration']),
        'sample_rate': int(stream.get('sample_rate', 24000)),
        'channels': int(stream.get('channels', 1)),
    }


def check_tail_energy(wav: Path, sample_rate: int = None) -> dict:
    """Measure final 80ms RMS vs body RMS to catch abrupt mid-syllable EOS cutoffs."""
    import numpy as np
    sr = sample_rate or probe_wav(wav)['sample_rate']
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(wav), '-ac', '1', '-f', 'f32le', '-'])
    samples = np.frombuffer(raw, dtype='<f4')
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    tail_n = min(len(samples), int(sr * 0.08))
    tail_rms = float(np.sqrt(np.mean(samples[-tail_n:] ** 2))) if tail_n else 0.0
    tail_db = 20.0 * math.log10(max(tail_rms, 1e-7))
    abrupt = tail_db > -20.0
    return {
        'peak_linear': round(peak, 4),
        'tail_80ms_db': round(tail_db, 2),
        'abrupt_cutoff_warning': abrupt,
    }


def _strip_all_punctuation(text: str) -> str:
    import unicodedata
    out = []
    for ch in text:
        if unicodedata.category(ch).startswith('P'):
            out.append(' ' if ch in '-—–/' else '')
        else:
            out.append(ch)
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def split_single_line_captions(text: str, start: float, duration: float, max_chars: int = 24) -> list:
    parts = [s.strip() for s in re.split(r'(?<=[，。！？；：——])', text.strip()) if s.strip()]
    chunks, cur = [], ''
    for part in parts:
        clean_part = _strip_all_punctuation(part)
        if not clean_part:
            continue
        if len(cur) + len(clean_part) <= max_chars:
            cur += clean_part
        else:
            if cur:
                chunks.append(cur)
            cur = clean_part
    if cur:
        chunks.append(cur)
    if not chunks:
        cleaned = _strip_all_punctuation(text).replace(' ', '')
        if cleaned:
            chunks = [cleaned[i:i + max_chars] for i in range(0, len(cleaned), max_chars)]
    total_len = sum(len(c) for c in chunks) or 1
    cursor = start
    cues = []
    for chunk in chunks:
        span = duration * (len(chunk) / total_len)
        cues.append({'start': round(cursor, 3), 'end': round(cursor + span, 3), 'text': chunk})
        cursor += span
    return cues


def fmt_srt(sec: float) -> str:
    ms = max(0, round(sec * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def synthesize_beats(lines: list, out_dir: Path, gap_seconds: float = 0.22,
                     lead_seconds: float = 0.18, tail_pad_seconds: float = 0.30,
                     mix_out: Path = None, srt_out: Path = None, no_punctuation: bool = True,
                     max_beat_chars: int = 28, max_beat_seconds: float = 5.8,
                     max_screen_chars: int = 35, strict_beats: bool = False) -> dict:
    """Synthesize 1-beat-1-visual Qwen3-TTS clips, check tail safety and beat granularity, and emit manifest + SRT."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / 'audio_manifest.json'
    previous = {}
    if manifest_path.is_file():
        try:
            old = json.loads(manifest_path.read_text(encoding='utf-8'))
            previous = {row['id']: row for row in old.get('lines', []) if isinstance(row, dict) and row.get('id')}
        except (ValueError, KeyError):
            previous = {}

    entries = []
    cursor = lead_seconds
    all_cues = []
    warnings = []
    beat_errors = []

    for beat_idx, item in enumerate(lines):
        lid = str(item['id'])
        voice = str(item.get('voice', 'didi'))
        role = str(item.get('role', '旁白'))
        text = str(item['text']).strip()
        if not text:
            raise ValueError(f'分镜配音文本为空: {lid}')
        clean_len = len(_strip_all_punctuation(text).replace(' ', ''))
        if clean_len > max_beat_chars:
            msg = f'{lid}: 口播过长 ({clean_len} 字 > {max_beat_chars})，建议拆分为多个独立视觉意象 Beat 以防退化为 PPT'
            warnings.append(msg)
            beat_errors.append(msg)
        screen_text = str(item.get('screen_text', '')).strip()
        if screen_text:
            screen_len = len(_strip_all_punctuation(screen_text).replace(' ', ''))
            if screen_len > max_screen_chars:
                msg = f'{lid}: 同屏正文过密 ({screen_len} 字 > {max_screen_chars})，请精简为锚点词交由口播展开'
                warnings.append(msg)
                beat_errors.append(msg)
        digest = sha_text(voice, text)
        txt_file = out_dir / f'{lid}.txt'
        wav_file = out_dir / f'{lid}.wav'
        prev = previous.get(lid, {})
        reuse = (prev.get('text_voice_sha256') == digest and wav_file.is_file() and wav_file.stat().st_size > 2000)
        if not reuse:
            for old_artifact in [wav_file, wav_file.with_suffix('.wav.json'), wav_file.with_name(f'{lid}.raw.wav')]:
                if old_artifact.exists():
                    old_artifact.unlink()
            tts_text = text if text[-1] in '。！？.!?…' else text + '。'
            txt_file.write_text(tts_text, encoding='utf-8')
            cmd = [sys.executable, str(TTS_SCRIPT), '--voice', voice, '--text-file', str(txt_file), '--out', str(wav_file)]
            if item.get('delivery_rate') is not None:
                cmd += ['--delivery-rate', str(item['delivery_rate'])]
            subprocess.run(cmd, check=True)
            best_tail = check_tail_energy(wav_file)
            if best_tail['abrupt_cutoff_warning']:
                for alt_seed in (20261021, 20261022):
                    cand = out_dir / f'{lid}.retry_{alt_seed}.wav'
                    for old_c in [cand, cand.with_suffix('.wav.json'), cand.with_name(f'{lid}.retry_{alt_seed}.raw.wav')]:
                        if old_c.exists():
                            old_c.unlink()
                    retry_cmd = [sys.executable, str(TTS_SCRIPT), '--voice', voice, '--seed', str(alt_seed), '--text-file', str(txt_file), '--out', str(cand)]
                    if item.get('delivery_rate') is not None:
                        retry_cmd += ['--delivery-rate', str(item['delivery_rate'])]
                    subprocess.run(retry_cmd, check=True)
                    cand_tail = check_tail_energy(cand)
                    if cand_tail['tail_80ms_db'] < best_tail['tail_80ms_db']:
                        cand.replace(wav_file)
                        best_tail = cand_tail
                    for old_c in [cand, cand.with_suffix('.wav.json'), cand.with_name(f'{lid}.retry_{alt_seed}.raw.wav')]:
                        if old_c.exists():
                            old_c.unlink()
                    if not best_tail['abrupt_cutoff_warning']:
                        break
        info = probe_wav(wav_file)
        tail = check_tail_energy(wav_file, sample_rate=info['sample_rate'])
        if tail['abrupt_cutoff_warning']:
            warnings.append(f'{lid}: 尾部80ms能量偏高 ({tail["tail_80ms_db"]} dB)，建议人工听检确认末字未截断')
        if info['duration'] > max_beat_seconds:
            msg = f'{lid}: 音频时长 {info["duration"]:.2f}s 超过 {max_beat_seconds:.1f}s，单镜易滞留成 PPT'
            warnings.append(msg)
            beat_errors.append(msg)
        start = round(cursor, 3)
        end = round(cursor + info['duration'], 3)
        cues = split_single_line_captions(text, start, info['duration']) if no_punctuation else [
            {'start': start, 'end': end, 'text': text}
        ]
        all_cues.extend(cues)
        entry = {
            'id': lid,
            'beat_index': beat_idx,
            'voice': voice,
            'role': role,
            'text': text,
            'text_chars': clean_len,
            'text_voice_sha256': digest,
            'wav': str(wav_file),
            'reused': reuse,
            'start': start,
            'end': end,
            'duration': round(info['duration'], 3),
            'tail_check': tail,
        }
        for optional_key in ('visual_metaphor', 'screen_text', 'scene_tag'):
            if item.get(optional_key) is not None:
                entry[optional_key] = item[optional_key]
        entries.append(entry)
        cursor = end + gap_seconds

    if strict_beats and beat_errors:
        raise ValueError('Strict Beat 校验未通过:\n' + '\n'.join(beat_errors))

    total_duration = round(cursor - gap_seconds + tail_pad_seconds, 3) if entries else 0.0
    manifest = {
        'schema': 'kgxc-tts-sync/1',
        'total_duration': total_duration,
        'gap_seconds': gap_seconds,
        'lead_seconds': lead_seconds,
        'tail_pad_seconds': tail_pad_seconds,
        'warnings': warnings,
        'lines': entries,
    }

    if mix_out and entries:
        mix_out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=stereo:d={total_duration:.3f}']
        filters = []
        mix_inputs = ['[0:a]']
        for idx, entry in enumerate(entries, start=1):
            cmd += ['-i', entry['wav']]
            delay_ms = round(entry['start'] * 1000)
            filters.append(f'[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay_ms}|{delay_ms}[a{idx}]')
            mix_inputs.append(f'[a{idx}]')
        filters.append(f'{"".join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest:normalize=0,alimiter=limit=0.95:level=0[out]')
        cmd += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-c:a', 'pcm_s24le', '-ar', '48000', str(mix_out)]
        subprocess.run(cmd, check=True)
        manifest['mix_wav'] = str(mix_out)

    if srt_out:
        srt_out.parent.mkdir(parents=True, exist_ok=True)
        srt_text = ''.join(
            f'{i}\n{fmt_srt(c["start"])} --> {fmt_srt(c["end"])}\n{c["text"]}\n\n'
            for i, c in enumerate(all_cues, start=1)
        )
        srt_out.write_text(srt_text, encoding='utf-8')
        manifest['srt'] = str(srt_out)

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lines', type=Path, required=True, help='JSON file with list of {id, voice, role, text}')
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--gap', type=float, default=0.22)
    p.add_argument('--lead', type=float, default=0.18)
    p.add_argument('--tail-pad', type=float, default=0.30)
    p.add_argument('--mix', type=Path, help='Optional output path for mixed 48kHz stereo WAV')
    p.add_argument('--srt', type=Path, help='Optional output path for synchronized single-line SRT')
    p.add_argument('--max-beat-chars', type=int, default=28)
    p.add_argument('--max-beat-seconds', type=float, default=5.8)
    p.add_argument('--max-screen-chars', type=int, default=35)
    p.add_argument('--strict-beats', action='store_true')
    args = p.parse_args()
    raw = json.loads(args.lines.read_text(encoding='utf-8'))
    lines = raw['lines'] if isinstance(raw, dict) else raw
    result = synthesize_beats(
        lines, args.out_dir, args.gap, args.lead, args.tail_pad, args.mix, args.srt,
        max_beat_chars=args.max_beat_chars, max_beat_seconds=args.max_beat_seconds,
        max_screen_chars=args.max_screen_chars, strict_beats=args.strict_beats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
