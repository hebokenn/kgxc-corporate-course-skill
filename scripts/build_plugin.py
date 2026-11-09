#!/usr/bin/env python3
"""Build a bounded portable plugin without courses, local settings or caches."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from check_readme import check_readme

ROOT = Path(__file__).resolve().parents[1]


def main():
    check_readme(ROOT / 'README.md')
    subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build_native_client.py')],check=True)
    package = json.loads((ROOT / 'package.json').read_text())
    manifest = json.loads((ROOT / 'plugin.json').read_text())
    if (manifest['name'], manifest['version']) != (package['name'], package['version']):
        raise ValueError('宿主清单版本不一致')
    for name in ['corporate-training-motion', 'elearning-course-design']:
        subprocess.run([sys.executable, str(ROOT / 'skills/corporate-training-motion/scripts/check_skill_package.py'), str(ROOT / 'skills' / name)], check=True)
    files = {}
    public_config = {'tools.example.json','voice-model.json','azure.example.json','package.json','package-lock.json'}
    for folder in ['plugin', 'skills', 'docs', 'scripts', 'tests', 'config']:
        for path in sorted((ROOT / folder).rglob('*')):
            rel = path.relative_to(ROOT)
            if (not path.is_file()
                    or any(parent.is_symlink() for parent in [path, *path.parents] if parent != ROOT and parent.is_relative_to(ROOT))
                    or any(part.startswith('.') or part in {'__pycache__','node_modules','inputs','courses','work','logs','reviews','private'} for part in rel.parts)
                    or path.suffix in {'.pyc','.pem','.key','.log','.pdf','.docx'}):
                continue
            if folder == 'config' and (len(rel.parts) != 2 or path.name not in public_config):
                continue
            files[str(rel)] = path.read_bytes()
    for name in ['package.json', 'plugin.json', 'cordis.patch.yml', 'VERSION', 'README.md', 'release.json',
                 '安装制课插件.command', '安装或更新.command', 'install.sh', 'THIRD_PARTY_NOTICES.md',
                 'requirements.in', 'requirements.lock', 'requirements-voice.in', 'requirements-voice.lock']:
        files[name] = (ROOT / name).read_bytes()
    proof = dict(name=package['name'], version=package['version'], core_version=(ROOT / 'VERSION').read_text().strip(), files={name: hashlib.sha256(data).hexdigest() for name, data in files.items()})
    files['plugin-bundle-manifest.json'] = (json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode()
    out = ROOT / 'dist'; out.mkdir(exist_ok=True)
    archive = out / ('kgxc-course-plugin-v' + package['version'] + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo('kgxc-course-plugin/' + name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith(('.command','.sh')) else 0o100644) << 16
            bundle.writestr(entry, data)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip(): raise ValueError('插件包 ZIP CRC 失败')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = out / 'PLUGIN-SHA256SUMS'; sums.write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps(dict(version=package['version'], files=len(files), bytes=archive.stat().st_size, sha256=digest, archive=str(archive)), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
