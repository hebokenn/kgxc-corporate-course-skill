#!/usr/bin/env python3
"""Offline B2 narration, selectable presets, voice design and reference cloning."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'workbench'))
from runtime import config_dir
VOICE_ASSETS = ROOT/'assets/voice'
CATALOG = json.loads((VOICE_ASSETS/'profiles.json').read_text())
DEFAULT_CONFIG = config_dir()/'voice.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(config, profile=None, model=None, library=None):
    """Explicit selection resets model-specific settings; runtime paths stay local."""
    selected = profile or config.get('profile') or config.get('voice_id') or CATALOG['default']
    private = selected not in CATALOG['profiles']
    if private:
        from voice_library import load
        try:
            path, local = load(library or config_dir()/'voices', selected)
        except (OSError, ValueError, KeyError) as exc:
            raise ValueError('Unknown or changed local voice; use --list-voices or voice_library.py') from exc
        spec = dict(CATALOG['profiles']['B2-clone'], voice_id=selected, language='auto',
                    reference_audio=str(path/'reference.wav'), reference_text=str(path/'reference.txt'),
                    reference_sha256=local['audio_sha256'], delivery_rate=local['delivery_rate'],
                    description=local['label'], private_local_only=True)
    else:
        spec = CATALOG['profiles'][selected]
    data = dict(provider='qwen3_tts', **CATALOG['generation'], **spec)
    data.update(profile=selected, voice_id=spec.get('voice_id', selected))
    entry = CATALOG['models'][data['mode']]
    data.update(model=entry['repository'], model_repository=entry['repository'], model_revision=entry['revision'])
    for key in ['python', 'model_paths', 'cloud_generation_authorized']:
        if key in config:
            data[key] = config[key]
    if profile is None or selected == config.get('profile', config.get('voice_id')):
        data.update(config)
    if private:
        data.update(spec, profile=selected)
        data.pop('instruct', None)
    if model:
        data['model'] = str(model.expanduser())
    else:
        paths = config.get('model_paths', {})
        data['model'] = paths.get(data['mode'], data['model'])
    for key in ['reference_audio', 'reference_text']:
        if key in data:
            path = Path(data[key]).expanduser()
            data[key] = str(path if path.is_absolute() else VOICE_ASSETS/path)
    return data


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--profile', choices=list(CATALOG['profiles']))
    p.add_argument('--voice', choices=[k for k,v in CATALOG['profiles'].items() if v['mode']=='custom_voice'], help='Preset override for this invocation')
    p.add_argument('--model', type=Path, help='Already downloaded local model folder')
    p.add_argument('--text-file', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--ref-audio', type=Path)
    p.add_argument('--ref-text-file', type=Path)
    p.add_argument('--instruct-file', type=Path)
    p.add_argument('--delivery-rate', type=float, help='Pitch-preserving delivery tempo; raw generation stays 1.0')
    p.add_argument('--seed', type=int)
    p.add_argument('--gender', choices=['male','female'], help='Resolve the user-selected local default for this gender')
    p.add_argument('--voice-library', type=Path, default=config_dir()/'voices')
    p.add_argument('--max-tokens', type=int)
    p.add_argument('--list-voices', action='store_true')
    p.add_argument('--set-default', action='store_true', help='Save selected profile locally, with a configuration backup')
    p.add_argument('--dry-run', action='store_true')
    return p


def main():
    p = parser(); args = p.parse_args()
    if args.list_voices:
        from voice_library import read_defaults, load
        catalog = dict(CATALOG)
        catalog['local_defaults'] = read_defaults(args.voice_library)
        catalog['local_profiles'] = [load(args.voice_library, d.name)[1] for d in sorted(args.voice_library.iterdir()) if d.is_dir() and (d/'profile.json').is_file()] if args.voice_library.exists() else []
        print(json.dumps(catalog, ensure_ascii=False, indent=2)); return
    stored = json.loads(args.config.read_text()) if args.config.exists() else {}
    if args.voice and args.profile:
        p.error('Choose --voice or --profile')
    if args.gender and (args.voice or args.profile or args.ref_audio):
        p.error('Choose --gender or an explicit voice/reference')
    if bool(args.ref_audio) != bool(args.ref_text_file):
        p.error('Reference cloning needs both --ref-audio and --ref-text-file')
    selection = args.voice or args.profile or ('B2-clone' if args.ref_audio else None)
    if args.gender:
        from voice_library import read_defaults
        defaults = read_defaults(args.voice_library)
        if args.gender not in defaults:
            p.error('No local default for this gender; register and select voices first')
        selection = defaults[args.gender]
    try:
        cfg = resolve(stored, selection, args.model, args.voice_library)
    except ValueError as exc:
        p.error(str(exc))
    if args.ref_audio:
        if cfg['mode'] != 'clone': p.error('Reference audio requires a clone profile')
        cfg.update(reference_audio=str(args.ref_audio.expanduser().resolve()), reference_text=str(args.ref_text_file.expanduser().resolve()))
        cfg.pop('reference_sha256', None)
        cfg['voice_id'] = 'reference-clone'
    if args.instruct_file:
        if cfg['mode'] == 'clone': p.error('Clone timbre comes from reference audio; use VoiceDesign for voice instructions')
        cfg['instruct'] = args.instruct_file.read_text().strip()
    for key in ['delivery_rate', 'seed', 'max_tokens']:
        if getattr(args, key) is not None: cfg[key] = getattr(args, key)
    if cfg.get('provider') != 'qwen3_tts' or cfg.get('speed', 1.0) != 1.0:
        p.error('Generation speed must stay 1.0; choose --delivery-rate for delivery tempo')
    rate = cfg.get('delivery_rate', 1.0)
    if type(rate) not in [int,float] or not math.isfinite(rate) or not .5 <= rate <= 2:
        p.error('delivery_rate must be between 0.5 and 2.0')
    if type(cfg['max_tokens']) is not int or not 64 <= cfg['max_tokens'] <= 16000:
        p.error('max_tokens must be an integer between 64 and 16000')
    if cfg['mode'] == 'voice_design' and not cfg.get('instruct'):
        p.error('VoiceDesign requires a nonempty instruction')
    reference = {}
    if cfg['mode'] == 'clone':
        for key in ['reference_audio', 'reference_text']:
            if not Path(cfg[key]).is_file(): p.error('Missing clone '+key)
        reference = dict(audio_sha256=sha(cfg['reference_audio']), text_sha256=sha(cfg['reference_text']))
        if cfg.get('reference_sha256') and reference['audio_sha256'] != cfg['reference_sha256']:
            p.error('Bundled reference changed; select an explicit reference instead')
        if not Path(cfg['reference_text']).read_text().strip(): p.error('Reference transcript is empty')
    if args.dry_run:
        print(json.dumps(cfg, ensure_ascii=False, indent=2)); return
    if args.set_default:
        args.config.parent.mkdir(parents=True, exist_ok=True)
        if args.config.exists():
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            shutil.copy2(args.config, args.config.with_name('voice.backup-'+stamp+'.json'))
        args.config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2)+'\n')
        print('Saved default '+cfg['profile']+' to '+str(args.config))
        if args.text_file is None and args.out is None: return
    if args.text_file is None or args.out is None:
        p.error('--text-file and --out are required for generation')
    out = args.out.expanduser(); sidecar = out.with_suffix(out.suffix+'.json')
    raw_out = out.with_name(out.stem+'.raw.wav') if rate != 1 else out
    if out.suffix.lower() != '.wav': p.error('Output must be a WAV file')
    if any(x.exists() for x in {out, sidecar, raw_out}):
        p.error('Output exists; preserving existing recordings')
    text = args.text_file.read_text().strip()
    if not text: p.error('Text is empty')
    runtime = cfg.get('python')
    if runtime and os.path.abspath(sys.executable) != os.path.abspath(os.path.expanduser(runtime)):
        os.execv(os.path.expanduser(runtime), [os.path.expanduser(runtime), str(Path(__file__).resolve()), *sys.argv[1:]])
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import soundfile as sf
    import mlx.core as mx
    from huggingface_hub import snapshot_download
    from mlx_audio.tts.utils import load_model
    local = Path(cfg['model']).expanduser()
    model_path = str(local) if local.is_dir() else snapshot_download(cfg['model_repository'], revision=cfg['model_revision'], local_files_only=True)
    model = load_model(model_path)
    expected = {'voice_design':'voice_design','custom_voice':'custom_voice','clone':'base'}[cfg['mode']]
    if model.config.tts_model_type != expected:
        raise ValueError('Wrong model variant for '+cfg['mode']+'; choose the matching installed model')
    mx.random.seed(cfg['seed'])
    params = {k:cfg[k] for k in ['language','temperature','top_p','repetition_penalty','max_tokens','stream']}
    started = time.time()
    if cfg['mode'] == 'voice_design':
        params['instruct'] = cfg['instruct']; results = list(model.generate_voice_design(text=text, **params))
    elif cfg['mode'] == 'custom_voice':
        params['instruct'] = cfg.get('instruct'); results = list(model.generate_custom_voice(text=text, speaker=cfg['voice_id'], **params))
    else:
        clone_params = {k:v for k,v in params.items() if k != 'language'}
        results = list(model.generate(text=text, lang_code=params['language'], ref_audio=cfg['reference_audio'], ref_text=Path(cfg['reference_text']).read_text().strip(), **clone_params))
        params['effective_repetition_penalty'] = max(params['repetition_penalty'], 1.5)
    if not results or sum(r.token_count for r in results) >= cfg['max_tokens']:
        raise ValueError('Empty output or token ceiling reached; no delivery audio committed; check content and regenerate a shorter semantic section')
    audio = np.concatenate([np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in results]); sr = results[0].sample_rate
    if not np.isfinite(audio).all() or len(audio) == 0 or not .01 < np.max(np.abs(audio)) < 1:
        raise ValueError('Invalid, silent or clipped audio; no delivery committed')
    out.parent.mkdir(parents=True, exist_ok=True)
    with raw_out.open('xb') as handle: sf.write(handle, audio, sr, format='WAV', subtype='PCM_24')
    if rate != 1:
        subprocess.run(['ffmpeg','-v','error','-n','-i',str(raw_out),'-af',f'atempo={rate}','-c:a','pcm_s24le',str(out)],check=True)
    metadata = dict(provider=cfg['provider'],profile=cfg['profile'],mode=cfg['mode'],model_repository=cfg['model_repository'],model_revision=cfg['model_revision'],
        voice_id=cfg['voice_id'],model_config_sha256=sha(Path(model_path)/'config.json'),
        model_resolution='pinned cache snapshot' if Path(model_path).name==cfg['model_revision'] else 'local model folder; revision is configured provenance',parameters=params,seed=cfg['seed'],speed=1.0,delivery_rate=rate,raw_audio=raw_out.name,
        raw_sha256=sha(raw_out),reference=reference,duration_seconds=sf.info(out).duration,sample_rate=sr,generation_seconds=time.time()-started,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),audio_sha256=sha(out),review_status='candidate_requires_content_and_listening_check')
    with sidecar.open('x') as handle: json.dump(metadata,handle,ensure_ascii=False,indent=2)
    print(json.dumps(metadata,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
