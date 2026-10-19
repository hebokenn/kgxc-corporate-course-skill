#!/usr/bin/env python3
"""Local Qwen3 CustomVoice generation using the user's selected Aiden defaults."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workbench'))
from runtime import config_dir
DEFAULT_CONFIG = config_dir()/'voice.json'
DEFAULTS = dict(provider='qwen3_tts', model='mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16',
                voice_id='Aiden', language='auto', instruct=None, speed=1.0,
                temperature=0.65, top_p=0.9, repetition_penalty=1.05,
                seed=20261019, max_tokens=4096, stream=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--text-file', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--voice', help='Explicit voice override for this task only')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = dict(DEFAULTS)
    if args.config.exists():
        config.update(json.loads(args.config.read_text()))
    if args.voice:
        config['voice_id'] = args.voice
    if config['provider'] != 'qwen3_tts' or config['speed'] != 1.0:
        parser.error('This local adapter preserves original speed; invalid provider/speed')
    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return
    if args.text_file is None or args.out is None:
        parser.error('--text-file and --out are required')
    out = args.out
    sidecar = out.with_suffix(out.suffix + '.json')
    if out.exists() or sidecar.exists():
        parser.error('Output exists; preserving the existing audio and metadata')
    text = args.text_file.read_text().strip()
    if not text:
        parser.error('Text is empty')
    runtime = config.get('python')
    if runtime and os.path.abspath(sys.executable) != os.path.abspath(os.path.expanduser(runtime)):
        os.execv(os.path.expanduser(runtime), [os.path.expanduser(runtime), str(Path(__file__).resolve()), *sys.argv[1:]])
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import soundfile as sf
    import mlx.core as mx
    from mlx_audio.tts.utils import load_model
    model = load_model(config['model'])
    mx.random.seed(config['seed'])
    params = {k: config[k] for k in ('language', 'instruct', 'temperature', 'top_p',
                                    'repetition_penalty', 'max_tokens', 'stream')}
    started = time.time()
    results = list(model.generate_custom_voice(text=text, speaker=config['voice_id'], **params))
    if not results or sum(r.token_count for r in results) >= config['max_tokens']:
        raise ValueError('Empty output or token limit reached; no final audio committed')
    audio = np.concatenate([np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in results])
    sr = results[0].sample_rate
    if not np.isfinite(audio).all() or len(audio) == 0 or np.max(np.abs(audio)) < 0.01:
        raise ValueError('Invalid or near-silent audio; no final audio committed')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as handle:
        sf.write(handle, audio, sr, format='WAV', subtype='PCM_24')
    metadata = dict(provider=config['provider'], model=config['model'], voice_id=config['voice_id'],
                    parameters=params, seed=config['seed'], speed=1.0,
                    duration_seconds=len(audio)/sr, sample_rate=sr,
                    generation_seconds=time.time()-started,
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    audio_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                    review_status='candidate_requires_content_and_listening_check')
    with sidecar.open('x') as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
