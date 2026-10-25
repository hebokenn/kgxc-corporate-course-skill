#!/usr/bin/env python3
"""Keep reference voices in a private local library and reuse verified bytes."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'workbench'))
from runtime import config_dir


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry(root, name):
    if not re.fullmatch(r'[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff_-]{0,63}', name):
        raise ValueError('Use a voice id of 1-64 letters, Chinese characters, digits, underscores or hyphens')
    path = root / name
    if path.is_symlink():
        raise ValueError('Voice directory must not be a symlink')
    return path


def register(root, name, audio, text, label, origin, rate):
    dest = entry(root, name)
    if not .5 <= rate <= 2:
        raise ValueError('delivery_rate must be between 0.5 and 2.0')
    if not audio.is_file() or audio.suffix.lower() != '.wav':
        raise ValueError('Provide a WAV reference')
    if not text.is_file() or not text.read_text().strip():
        raise ValueError('Provide the exact nonempty reference transcript')
    if dest.exists():
        raise ValueError('Voice already exists; preserve it and choose a new id')
    root.mkdir(parents=True, exist_ok=True)
    dest.mkdir()
    try:
        shutil.copy2(audio, dest / 'reference.wav')
        shutil.copy2(text, dest / 'reference.txt')
        data = dict(schema='local-reference-voice/1', id=name, label=label,
                    origin=origin, mode='clone', audio_sha256=sha(dest / 'reference.wav'),
                    text_sha256=sha(dest / 'reference.txt'), delivery_rate=rate,
                    default_changed=False, private_local_only=True,
                    review_status='candidate_requires_user_audition')
        (dest / 'profile.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        return data
    except Exception:
        shutil.rmtree(dest)
        raise


def load(root, name):
    path = entry(root, name)
    data = json.loads((path / 'profile.json').read_text())
    if data.get('id') != name or data.get('mode') != 'clone':
        raise ValueError('Invalid local reference profile')
    for filename, key in [('reference.wav', 'audio_sha256'), ('reference.txt', 'text_sha256')]:
        if sha(path / filename) != data[key]:
            raise ValueError('Reference changed; register and review a new version')
    return path, data


def read_defaults(root):
    path = root.parent / 'voice-defaults.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    for gender in ['male', 'female']:
        load(root, data[gender])
    if data.get('default_gender') not in ['male', 'female']:
        raise ValueError('Invalid default gender')
    return data


def set_defaults(root, male, female, default_gender, evidence, samples=None):
    if default_gender not in ['male', 'female'] or not evidence.strip():
        raise ValueError('Provide default gender and explicit user selection evidence')
    selected = {gender: load(root, name) for gender, name in [('male', male), ('female', female)]}
    stamp = datetime.datetime.now().astimezone().isoformat()
    suffix = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    defaults_file = root.parent / 'voice-defaults.json'
    voice_file = root.parent / 'voice.json'
    for target in [defaults_file, voice_file]:
        if target.exists():
            shutil.copy2(target, target.with_name(target.stem + '.backup-' + suffix + '.json'))
    data = dict(schema='local-voice-defaults/1', male=male, female=female,
                default_gender=default_gender, evidence=evidence, selected_at=stamp)
    config = json.loads(voice_file.read_text()) if voice_file.exists() else {}
    path, spec = selected[default_gender]
    for key in ['instruct', 'model', 'model_repository', 'model_revision']:
        config.pop(key, None)
    config.update(profile=spec['id'], voice_id=spec['id'], mode='clone', language='auto',
                  delivery_rate=spec['delivery_rate'], reference_audio=str(path / 'reference.wav'),
                  reference_text=str(path / 'reference.txt'), reference_sha256=spec['audio_sha256'])
    voice_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    for gender, (path, spec) in selected.items():
        spec.update(review_status='user_selected_as_default', approval_evidence=evidence, selected_at=stamp)
        if samples and samples.get(gender):
            spec['approved_sample_sha256'] = sha(samples[gender])
        (path / 'profile.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
    defaults_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return data


def generate_command(root, name, text, out, config=None, rate=None, tokens=4096):
    path, data = load(root, name)
    if not text.is_file() or not text.read_text().strip():
        raise ValueError('Provide nonempty synthesis text')
    for p in [out, out.with_suffix(out.suffix + '.json'), out.with_suffix(out.suffix + '.voice.json')]:
        if p.exists():
            raise ValueError('Output exists; choose a new version')
    effective_rate = data['delivery_rate'] if rate is None else rate
    if not .5 <= effective_rate <= 2:
        raise ValueError('delivery_rate must be between 0.5 and 2.0')
    cmd = [sys.executable, str(ROOT / 'scripts/qwen3_tts.py'), '--profile', 'B2-clone',
           '--ref-audio', str(path / 'reference.wav'), '--ref-text-file', str(path / 'reference.txt'),
           '--text-file', str(text), '--out', str(out), '--delivery-rate', str(effective_rate),
           '--max-tokens', str(tokens)]
    if config:
        cmd += ['--config', str(config)]
    return cmd, data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=config_dir() / 'voices')
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('register')
    add.add_argument('--id', required=True)
    add.add_argument('--audio', type=Path, required=True)
    add.add_argument('--text', type=Path, required=True)
    add.add_argument('--label', required=True)
    add.add_argument('--origin', required=True)
    add.add_argument('--delivery-rate', type=float, default=1.0)
    sub.add_parser('list')
    sub.add_parser('defaults')
    default = sub.add_parser('set-defaults')
    default.add_argument('--male', required=True)
    default.add_argument('--female', required=True)
    default.add_argument('--default-gender', choices=['male', 'female'], default='male')
    default.add_argument('--evidence', required=True)
    default.add_argument('--male-sample', type=Path)
    default.add_argument('--female-sample', type=Path)
    gen = sub.add_parser('generate')
    gen.add_argument('--id', required=True)
    gen.add_argument('--text-file', type=Path, required=True)
    gen.add_argument('--out', type=Path, required=True)
    gen.add_argument('--config', type=Path)
    gen.add_argument('--delivery-rate', type=float)
    gen.add_argument('--max-tokens', type=int, default=4096)
    gen.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    root = args.library.expanduser().resolve()
    try:
        if args.command == 'register':
            result = register(root, args.id, args.audio, args.text, args.label, args.origin, args.delivery_rate)
        elif args.command == 'list':
            result = [load(root, p.name)[1] for p in sorted(root.iterdir()) if p.is_dir() and (p / 'profile.json').is_file()] if root.exists() else []
        elif args.command == 'defaults':
            result = read_defaults(root)
        elif args.command == 'set-defaults':
            samples = {'male': args.male_sample, 'female': args.female_sample}
            for p in samples.values():
                if p and not p.is_file():
                    raise ValueError('Approval sample is missing')
            result = set_defaults(root, args.male, args.female, args.default_gender, args.evidence, samples)
        else:
            cmd, data = generate_command(root, args.id, args.text_file, args.out, args.config, args.delivery_rate, args.max_tokens)
            if args.dry_run:
                result = dict(voice=data, command=cmd, generated=False)
            else:
                subprocess.run(cmd, check=True)
                result = dict(data, synthesis_text_sha256=sha(args.text_file), output_sha256=sha(args.out))
                args.out.with_suffix(args.out.suffix + '.voice.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
