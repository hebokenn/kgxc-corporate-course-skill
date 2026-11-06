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
    package = json.loads((ROOT / 'package.json').read_text())
    manifest = json.loads((ROOT / 'plugin.json').read_text())
    if (manifest['name'], manifest['version']) != (package['name'], package['version']):
        raise ValueError('宿主清单版本不一致')
    for name in ['corporate-training-motion', 'elearning-course-design']:
        subprocess.run([sys.executable, str(ROOT / 'skills/corporate-training-motion/scripts/check_skill_package.py'), str(ROOT / 'skills' / name)], check=True)
    files = {}
    for folder in ['plugin', 'skills']:
        for path in sorted((ROOT / folder).rglob('*')):
            if not path.is_file() or path.is_symlink() or '__pycache__' in path.parts or path.suffix == '.pyc' or path.name.startswith('.'):
                continue
            files[str(path.relative_to(ROOT))] = path.read_bytes()
    for name in ['package.json', 'plugin.json', 'cordis.patch.yml', 'VERSION', '安装制课插件.command', 'scripts/install_plugin.py', 'tests/test_plugin.py', 'tests/test_dsh_plugin.mjs', 'tests/test_script_editor.py', 'tests/test_script_editor.mjs', 'tests/test_editor_host.mjs', 'tests/test_session_courses.mjs', 'tests/test_course_client.mjs', 'tests/test_studio.py', 'tests/test_delivery.py', 'tests/test_delivery_files.mjs', 'tests/test_production_progress.mjs', 'tests/test_production_monitor.mjs', 'tests/test_audio_timing.py', 'tests/test_production_preferences.py', 'tests/test_layered_customers.py', 'docs/PLUGIN.md', 'docs/verification-plugin-v0.1.0.md', 'docs/verification-plugin-v0.2.0.md', 'docs/verification-plugin-v0.3.0.md', 'docs/verification-plugin-v0.4.0.md', 'docs/verification-plugin-v0.5.0.md', 'docs/verification-plugin-v0.6.0.md', 'THIRD_PARTY_NOTICES.md']:
        files[name] = (ROOT / name).read_bytes()
    files['README.md'] = (ROOT / 'docs/PLUGIN.md').read_bytes()
    proof = dict(name=package['name'], version=package['version'], core_version=(ROOT / 'VERSION').read_text().strip(), files={name: hashlib.sha256(data).hexdigest() for name, data in files.items()})
    files['plugin-bundle-manifest.json'] = (json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode()
    out = ROOT / 'dist'; out.mkdir(exist_ok=True)
    archive = out / ('kgxc-course-plugin-v' + package['version'] + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo('kgxc-course-plugin/' + name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            bundle.writestr(entry, data)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip(): raise ValueError('插件包 ZIP CRC 失败')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = out / 'PLUGIN-SHA256SUMS'; sums.write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps(dict(version=package['version'], files=len(files), bytes=archive.stat().st_size, sha256=digest, archive=str(archive)), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
