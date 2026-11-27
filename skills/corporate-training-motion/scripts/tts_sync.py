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
    """Measure final 80ms RMS vs body RMS to catch abrupt mid-syllable EOS cutoffs, plus speech onset/end bounds."""
    import numpy as np
    sr = sample_rate or probe_wav(wav)['sample_rate']
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(wav), '-ac', '1', '-f', 'f32le', '-'])
    samples = np.frombuffer(raw, dtype='<f4')
    total_dur = len(samples) / float(sr) if sr else 0.0
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    tail_n = min(len(samples), int(sr * 0.08))
    tail_rms = float(np.sqrt(np.mean(samples[-tail_n:] ** 2))) if tail_n else 0.0
    tail_db = 20.0 * math.log10(max(tail_rms, 1e-7))
    abrupt = tail_db > -20.0

    # Measure actual vocal onset and speech end using 10ms RMS windows so visuals never pop ahead of leading silence
    win_n = max(1, int(sr * 0.01))
    n_wins = len(samples) // win_n
    onset_sec = 0.0
    speech_end_sec = total_dur
    if n_wins > 0:
        frames = samples[:n_wins * win_n].reshape(n_wins, win_n)
        rms = np.sqrt(np.mean(frames ** 2, axis=1))
        thresh = max(0.012, peak * 0.035)
        active = np.where(rms >= thresh)[0]
        if len(active):
            onset_sec = min(float(active[0]) * 0.01, total_dur * 0.45)
            speech_end_sec = min(total_dur, float(active[-1] + 1) * 0.01)

    return {
        'peak_linear': round(peak, 4),
        'tail_80ms_db': round(tail_db, 2),
        'abrupt_cutoff_warning': abrupt,
        'speech_onset_sec': round(onset_sec, 3),
        'speech_end_sec': round(max(speech_end_sec, onset_sec + 0.05), 3),
    }


def compute_phrase_anchors(text: str, speech_start: float, speech_end: float, cue_words: list = None) -> dict:
    """Estimate intra-beat timestamps for explicit cue_words (and clauses) inside [speech_start, speech_end]."""
    raw = str(text or '').strip()
    span = max(0.08, float(speech_end) - float(speech_start))
    # Build character-level weighted cumulative time map (punctuation gets small pause weight)
    import unicodedata
    weights = []
    clean_chars = []
    clean_to_raw = []
    for idx, ch in enumerate(raw):
        if ch.isspace():
            weights.append(0.15)
        elif unicodedata.category(ch).startswith('P'):
            weights.append(0.75 if ch in '，。！？；：——' else 0.25)
        else:
            weights.append(1.0)
            clean_chars.append(ch.lower())
            clean_to_raw.append(idx)
    total_w = sum(weights) or 1.0
    cum = []
    acc = 0.0
    for w in weights:
        cum.append(acc / total_w)
        acc += w
    clean_str = ''.join(clean_chars)

    anchors = {}
    for phrase in (cue_words or []):
        ph = str(phrase or '').strip()
        if not ph:
            continue
        clean_ph = _strip_all_punctuation(ph).replace(' ', '').lower()
        if not clean_ph:
            continue
        pos = clean_str.find(clean_ph)
        if pos >= 0:
            raw_idx = clean_to_raw[pos]
            anchors[ph] = round(speech_start + span * cum[raw_idx], 3)
    return anchors


def _strip_all_punctuation(text: str) -> str:
    import unicodedata
    out = []
    for ch in text:
        if unicodedata.category(ch).startswith('P'):
            out.append(' ' if ch in '-—–/' else '')
        else:
            out.append(ch)
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


_ZH_CHAPTER_DIGITS = {'1': '一', '2': '二', '3': '三', '4': '四', '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'}


def normalize_spoken_text(text: str) -> str:
    """Normalize display text into natural Chinese spoken text for TTS without altering captions.

    - Pronounce 'WOW' as '哇哦' instead of awkward English spelling.
    - Drop leading zeros in chapter labels ('第 01 节' -> '第一节', '第 02 节' -> '第二节').
    """
    spoken = str(text or '').strip()
    spoken = re.sub(r'\s*\bWOW\b\s*', '哇哦', spoken, flags=re.IGNORECASE)
    spoken = re.sub(r'第\s*0([1-9])\s*节', lambda m: f'第{_ZH_CHAPTER_DIGITS[m.group(1)]}节', spoken)
    return spoken


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
                     max_screen_chars: int = 35, strict_beats: bool = False,
                     normalize_spoken: bool = True) -> dict:
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
        clean_text = _strip_all_punctuation(text).replace(' ', '')
        clean_len = len(clean_text)
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

        # v8.0.0: Block mechanical sub-beat splitting that clones identical scene & params without distinct visual_cue
        if beat_idx > 0:
            prev_item = lines[beat_idx - 1]
            cur_scene = item.get('scene_id') or item.get('scene')
            prev_scene = prev_item.get('scene_id') or prev_item.get('scene')
            if cur_scene and cur_scene == prev_scene:
                p_cur = {k: v for k, v in (item.get('params') or {}).items() if k not in ('sub_idx', 'sub_total')}
                p_prev = {k: v for k, v in (prev_item.get('params') or {}).items() if k not in ('sub_idx', 'sub_total')}
                cur_cue = str(item.get('visual_cue', '')).strip()
                prev_cue = str(prev_item.get('visual_cue', '')).strip()
                if p_cur == p_prev and (not cur_cue or cur_cue == prev_cue):
                    msg = f'{lid}: 与上一条 {prev_item.get("id")} 场景及参数完全雷同且无独立 visual_cue，禁止机械拆句后重播同一画面'
                    warnings.append(msg)
                    beat_errors.append(msg)

        # v8.0.0: Check dialogue bubble alignment with spoken audio
        params_dict = item.get('params') or {}
        bubble_txt = str(item.get('speaker_bubble') or params_dict.get('bubble') or '').strip()
        if bubble_txt:
            if role == '旁白' and not params_dict.get('narrator_quote'):
                msg = f'{lid}: 旁白口播却挂载了角色对话气泡（{bubble_txt[:16]}），请核对说话人与音频角色是否匹配'
                warnings.append(msg)
                beat_errors.append(msg)
            clean_bubble = _strip_all_punctuation(bubble_txt).replace(' ', '')
            if clean_bubble and clean_text:
                overlap = sum(1 for ch in set(clean_bubble) if ch in clean_text) / max(1, len(set(clean_bubble)))
                if overlap < 0.25:
                    msg = f'{lid}: 对话气泡文案与本条口播内容不匹配（重合度 {overlap:.0%}），禁止跨句沿用旧气泡'
                    warnings.append(msg)
                    beat_errors.append(msg)
        raw_override = item.get('tts_text')
        if raw_override is not None and str(raw_override).strip():
            spoken = str(raw_override).strip()
        else:
            spoken = normalize_spoken_text(text) if normalize_spoken else text
        digest = sha_text(voice, spoken)
        txt_file = out_dir / f'{lid}.txt'
        wav_file = out_dir / f'{lid}.wav'
        prev = previous.get(lid, {})
        reuse = (prev.get('text_voice_sha256') == digest and wav_file.is_file() and wav_file.stat().st_size > 2000)
        if not reuse:
            for old_artifact in [wav_file, wav_file.with_suffix('.wav.json'), wav_file.with_name(f'{lid}.raw.wav')]:
                if old_artifact.exists():
                    old_artifact.unlink()
            tts_text = spoken if spoken[-1] in '。！？.!?…' else spoken + '。'
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
        onset_sec = float(tail.get('speech_onset_sec', 0.0))
        speech_start = round(start + onset_sec, 3)
        speech_end = round(min(end, max(speech_start + 0.08, start + float(tail.get('speech_end_sec', info['duration'])))), 3)
        cue_words = item.get('cue_words') or []
        anchors = compute_phrase_anchors(text, speech_start, speech_end, cue_words) if cue_words else {}
        cues = split_single_line_captions(text, speech_start, max(0.08, speech_end - speech_start)) if no_punctuation else [
            {'start': speech_start, 'end': speech_end, 'text': text}
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
            'speech_onset_sec': round(onset_sec, 3),
            'speech_start': speech_start,
            'speech_end': speech_end,
            'duration': round(info['duration'], 3),
            'tail_check': tail,
        }
        if anchors:
            entry['anchors'] = anchors
        if spoken != text:
            entry['tts_text'] = spoken
        for optional_key in (
            'scene_id', 'scene', 'layout_kind', 'visual_cue', 'visual_metaphor',
            'screen_text', 'scene_tag', 'speaker_bubble', 'params', 'sfx', 'flower_text', 'cue_words',
        ):
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
    p.add_argument('--no-spoken-normalize', action='store_true', help='Disable default spoken pronunciation normalization (e.g. WOW->哇哦, 第02节->第二节)')
    args = p.parse_args()
    raw = json.loads(args.lines.read_text(encoding='utf-8'))
    lines = raw['lines'] if isinstance(raw, dict) else raw
    result = synthesize_beats(
        lines, args.out_dir, args.gap, args.lead, args.tail_pad, args.mix, args.srt,
        max_beat_chars=args.max_beat_chars, max_beat_seconds=args.max_beat_seconds,
        max_screen_chars=args.max_screen_chars, strict_beats=args.strict_beats,
        normalize_spoken=not args.no_spoken_normalize,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
