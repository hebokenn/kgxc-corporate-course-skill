#!/usr/bin/env python3
"""Decode the two frozen user-selected sources and build their role aliases offline."""
from array import array
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/corporate-training-motion'
sys.path.insert(0, str(SKILL / 'workbench'))
from sound import PALETTE, RATE, ROLES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = SKILL / 'assets/sfx' / PALETTE
    source = json.loads((folder / 'source.json').read_text())
    clips = {}
    for name, item in source['clips'].items():
        original = folder / item['original']
        if sha(original) != item['originalSha256']:
            raise ValueError('Frozen source changed: ' + name)
        target = folder / item['renderFile']
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(original),
                        '-map', '0:a:0', '-vn', '-ar', str(RATE), '-ac', '2',
                        '-c:a', 'pcm_s16le', '-map_metadata', '-1', str(target)], check=True)
        with wave.open(str(target), 'rb') as audio:
            assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (RATE, 2, 2)
            samples = array('h'); samples.frombytes(audio.readframes(audio.getnframes()))
        energy = [max(abs(samples[i]), abs(samples[i+1])) for i in range(0, len(samples), 2)]
        clips[name] = dict(path=target.name, sha256=sha(target), samples=len(energy),
                           peakSample=max(range(len(energy)), key=energy.__getitem__),
                           firstAudibleSample=next(i for i, v in enumerate(energy) if v > 16),
                           source=item['original'], sourceSha256=item['originalSha256'],
                           sourceAssetId=item['sourceAssetId'], title=item['title'],
                           gainDb=item['gainDb'], license=item['rights'])
    assets = []
    for role in ROLES:
        name = 'ding' if role in ['focus', 'reveal', 'confirm'] else 'dudong'
        assets.append(dict(id=role+'-native', role=role, label=ROLES[role][1], **clips[name]))
    catalog = dict(id=PALETTE, sampleRate=RATE, channels=2, uniqueSources=2,
                   source='User-selected Heycan 提示音 and 嘟咚，提示音1; see source.json',
                   selection='Fixed native source per role; aliases are not additional recordings. Continuous motion may remain silent.',
                   assets=assets)
    (folder / 'palette.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(palette=PALETTE, sourceClips=2, roleAliases=len(assets),
                          renderHashes={name: item['sha256'] for name, item in clips.items()}), indent=2))


if __name__ == '__main__':
    main()
