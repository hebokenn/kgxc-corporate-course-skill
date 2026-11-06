#!/usr/bin/env python3
"""Install the DSH course workbench through its package manager."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
NAME = 'kgxc-course-plugin'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def local_package(vendor):
    """Install immutable package bytes; pnpm directory specs may remain development links."""
    metadata = json.loads((ROOT / 'package.json').read_text())
    vendor.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.kgxc-package-', suffix='.tgz', dir=vendor)
    os.close(handle)
    temporary = Path(temporary)
    try:
        paths = {ROOT / 'package.json'}
        for name in metadata['files']:
            source = ROOT / name
            if source.is_dir(): paths.update(path for path in source.rglob('*') if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and path.suffix != '.pyc' and not path.name.startswith('.'))
            elif source.is_file(): paths.add(source)
        with temporary.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped, tarfile.open(fileobj=zipped, mode='w') as archive:
            for path in sorted(paths):
                info = archive.gettarinfo(str(path), 'package/' + str(path.relative_to(ROOT)))
                info.mtime = 0; info.uid = info.gid = 0; info.uname = info.gname = ''
                with path.open('rb') as data: archive.addfile(info, data)
        package = vendor / (NAME + '-' + metadata['version'] + '-' + digest(temporary)[:12] + '.tgz')
        if package.exists(): temporary.unlink()
        else: temporary.replace(package)
        return package
    finally:
        if temporary.exists(): temporary.unlink()


def dsh(executable, profile):
    home = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh')))
    folder = home / 'profiles' / profile
    source = folder / 'package.json'
    before = {name: digest(folder / name) for name in ['cordis.yml', 'cordis.patch.yml'] if (folder / name).is_file()}
    backup = home / 'plugin-install-records' / (NAME + '-' + time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, exist_ok=True)
    for name in ['package.json', 'pnpm-lock.yaml']:
        if (folder / name).is_file(): shutil.copy2(folder / name, backup / name)
    package = local_package(folder / 'vendor')
    installed = folder / 'node_modules' / NAME
    development_link = installed.is_symlink() and installed.resolve() == ROOT
    if development_link:
        # Updating a link: entry to a same-version tarball can preserve the old lock resolution.
        # Remove only this plugin's importer before adding immutable package bytes.
        subprocess.run([executable, 'plugin', '--profile', profile, 'remove', NAME], check=True)
    try:
        subprocess.run([executable, 'plugin', '--profile', profile, 'add', 'file:' + str(package)], check=True)
    except Exception:
        for filename in ['package.json', 'pnpm-lock.yaml']:
            if (backup / filename).is_file(): shutil.copy2(backup / filename, folder / filename)
        if development_link and not installed.exists(): installed.symlink_to(ROOT, target_is_directory=True)
        raise
    data = json.loads(source.read_text())
    bundles = data.setdefault('dsh', {}).setdefault('profile', {}).setdefault('bundles', [])
    if NAME not in bundles:
        bundles.append(NAME)
        pending = source.with_suffix('.json.kgxc-pending')
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        pending.replace(source)
    if not (installed / 'plugin/dsh.mjs').is_file(): raise ValueError('DSH 本地安装未落盘')
    if installed.resolve() == ROOT: raise ValueError('DSH 仍使用开发链接，未形成独立安装')
    after = {name: digest(folder / name) for name in before}
    if before != after: raise ValueError('DSH 配置在安装期间发生变化，请核对配置')
    report = dict(host='dsh', profile=profile, installed=str(installed), source=str(ROOT), package=str(package), package_sha256=digest(package),
                  registration_count=json.loads(source.read_text())['dsh']['profile']['bundles'].count(NAME),
                  existing_configuration_unchanged=before == after, version=json.loads((installed / 'package.json').read_text())['version'])
    (backup / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', choices=['dsh'], default='dsh')
    parser.add_argument('--profile', default='desktop')
    parser.add_argument('--dsh', default=shutil.which('dsh') or '/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh')
    args = parser.parse_args()
    results = []
    results.append(dsh(args.dsh, args.profile))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
