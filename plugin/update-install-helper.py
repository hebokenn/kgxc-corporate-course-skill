#!/usr/bin/env python3
"""External installer for a user-selected, SHA-pinned DSH plugin ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile

NAME = 'kgxc-course-plugin'
APP = Path('/Applications/DeepSeek Harness.app')
CLI = APP / 'Contents/Resources/runtime/cli/bin/dsh'
APP_EXECUTABLE = APP / 'Contents/MacOS/DeepSeek Harness'
MANIFEST = 'plugin-bundle-manifest.json'
REQUIRED = {'package.json', 'plugin.json', 'VERSION', 'plugin/dsh.mjs', 'scripts/install_plugin.py'}
MAX_ARCHIVE = 350 * 1024 * 1024
MAX_TOTAL = 550 * 1024 * 1024
MAX_MEMBER = 140 * 1024 * 1024
WAIT_SECONDS = 900
SHA = re.compile(r'[0-9a-f]{64}')


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('安装包清单含重复字段')
        result[key] = value
    return result


def parse_json(raw):
    value = json.loads(raw, object_pairs_hook=json_object)
    if not isinstance(value, dict):
        raise ValueError('安装包清单格式错误')
    return value


def private_file(path, *, existing=True):
    if not path.is_absolute() or path.parent.resolve() != path.parent or path.is_symlink():
        raise ValueError('更新文件不在安全的私有目录')
    st = path.parent.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError('更新目录不是当前用户私有目录')
    if existing or path.exists():
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
            raise ValueError('更新文件不是当前用户私有普通文件')


def write_status(path, state, version, message):
    fd, name = tempfile.mkstemp(prefix='.update-status-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(dict(status=state, message=message, version=version), stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def verify_extract(archive, version, digest, target):
    with archive.open('rb') as raw:
        if os.fstat(raw.fileno()).st_size > MAX_ARCHIVE:
            raise ValueError('安装包超过大小限制')
        checksum = hashlib.sha256()
        while chunk := raw.read(1024 * 1024):
            checksum.update(chunk)
        if checksum.hexdigest() != digest:
            raise ValueError('安装包 SHA-256 不一致')
        raw.seek(0)
        with zipfile.ZipFile(raw) as package:
            entries = package.infolist()
            if not 0 < len(entries) <= 6000 or sum(x.file_size for x in entries) > MAX_TOTAL:
                raise ValueError('安装包展开体积或条目超限')
            files, folded = {}, set()
            prefix = NAME + '/'
            for item in entries:
                name = item.orig_filename
                rel = name.removeprefix(prefix)
                mode = (item.external_attr >> 16) & 0o170000
                parts = rel.split('/')
                if (not name.startswith(prefix) or item.is_dir() or mode not in (0, stat.S_IFREG)
                        or '\\' in rel or ':' in rel or any(ord(x) < 32 or ord(x) == 127 for x in rel)
                        or any(p in ('', '.', '..') or len(p.encode()) > 255 for p in parts)
                        or item.file_size > MAX_MEMBER or item.flag_bits & 1):
                    raise ValueError('安装包包含不安全或超限的文件')
                key = unicodedata.normalize('NFC', rel).casefold()
                if key in folded:
                    raise ValueError('安装包包含重复或冲突的路径')
                folded.add(key)
                files[rel] = item
            for rel in folded:
                parts = rel.split('/')
                if any('/'.join(parts[:i]) in folded for i in range(1, len(parts))):
                    raise ValueError('安装包文件与目录路径冲突')
            if not REQUIRED | {MANIFEST} <= files.keys() or files[MANIFEST].file_size > 4 * 1024 * 1024:
                raise ValueError('安装包缺少必需文件或清单过大')
            proof = parse_json(package.read(files[MANIFEST]))
            digests = proof.get('files')
            if (proof.get('name') != NAME or proof.get('version') != version or not isinstance(digests, dict)
                    or digests.keys() != (files.keys() - {MANIFEST})
                    or any(not isinstance(v, str) or not SHA.fullmatch(v) for v in digests.values())):
                raise ValueError('安装包清单与发布版本或文件列表不一致')
            for name, item in files.items():
                if name == MANIFEST:
                    continue
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                checksum = hashlib.sha256()
                total = 0
                with package.open(item) as src, dest.open('xb') as out:
                    while chunk := src.read(1024 * 1024):
                        total += len(chunk)
                        if total > item.file_size:
                            raise ValueError('安装包文件展开体积异常')
                        out.write(chunk)
                        checksum.update(chunk)
                if total != item.file_size or checksum.hexdigest() != digests[name]:
                    raise ValueError('安装包文件校验未通过')
                if item.external_attr >> 16 & stat.S_IXUSR:
                    dest.chmod(0o700)
            for name in ('package.json', 'plugin.json'):
                meta = parse_json((target / name).read_bytes())
                if (meta.get('name'), meta.get('version')) != (NAME, version):
                    raise ValueError('安装包宿主与 npm 版本清单不一致')
            if (target / 'VERSION').read_text().strip() != proof.get('core_version'):
                raise ValueError('安装包核心版本清单不一致')


def process_table():
    result = subprocess.run(['/bin/ps', '-axww', '-o', 'pid=,command='], capture_output=True, text=True, check=True, timeout=10)
    processes = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdecimal():
            processes[int(parts[0])] = parts[1]
    return processes


def desktop_consumers(processes, installed):
    # Inspect only the official app executable and exact installed-package path
    # consumers, not global process names such as node or python.
    import shlex
    paths = {str(installed) + '/', str(installed.resolve()) + '/'}
    app = str(APP_EXECUTABLE)
    found = []
    for pid, command in processes.items():
        if command == app or command.startswith(app + ' '):
            found.append(pid)
            continue
        try:
            argv = shlex.split(command)
        except ValueError:
            argv = []
        # macOS ps may flatten paths containing spaces without shell quotes.
        if (any(arg.startswith(prefix) for arg in argv[1:] for prefix in paths)
                or any(re.search(r'\s' + re.escape(prefix) + r'plugin/(?:service\.py|dsh\.mjs)(?:\s|$)', command)
                       for prefix in paths)):
            found.append(pid)
    return found


def wait_for_exit(pids, installed, *, seconds=WAIT_SECONDS, read_processes=process_table,
                  clock=time.monotonic, sleep=time.sleep):
    observed = read_processes()
    original = {pid: observed[pid] for pid in pids if pid in observed}
    limit = clock() + seconds
    quiet = 0
    while clock() < limit:
        processes = read_processes()
        # If a tracked PID is reused by an unrelated command, do not wait for it.
        tracked = any(processes.get(pid) == command for pid, command in original.items())
        if not tracked and not desktop_consumers(processes, installed):
            quiet += 1
            if quiet >= 2:
                return
        else:
            quiet = 0
        sleep(.5)
    raise ValueError('等待 DSH 退出超时，未安装。请保存工作、退出 DSH 后重新更新。')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--wait-pid', type=int, action='append', default=[])
    args = parser.parse_args()
    private_file(args.status, existing=False)
    try:
        private_file(args.archive)
        if (args.archive.parent != args.status.parent or args.archive == args.status
                or not SHA.fullmatch(args.sha256) or not re.fullmatch(r'(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}', args.version)
                or not args.wait_pid or any(p <= 1 or p == os.getpid() for p in args.wait_pid)):
            raise ValueError('更新参数无效')
        if sys.platform != 'darwin' or not CLI.is_file() or not os.access(CLI, os.X_OK):
            raise ValueError('未找到官方 macOS DeepSeek Harness，未安装')
        home = Path(os.environ.get('DSH_HOME', Path.home() / '.dsh')).expanduser().resolve()
        if home != (Path.home() / '.dsh').resolve():
            raise ValueError('非默认 DSH 桌面环境暂不支持自动更新')
        installed = home / 'profiles/desktop/node_modules' / NAME
        if not (installed / 'package.json').is_file():
            raise ValueError('未找到当前 DSH 桌面安装，未更新')
        with tempfile.TemporaryDirectory(prefix='.verified-', dir=args.archive.parent) as stage:
            source = Path(stage)
            verify_extract(args.archive, args.version, args.sha256, source)
            write_status(args.status, 'waiting', args.version, '等待你正常退出 DSH，课程与配置保持原样。')
            wait_for_exit(args.wait_pid, installed)
            write_status(args.status, 'installing', args.version, '正在通过 DSH 安装已校验版本。')
            result = subprocess.run([sys.executable, '-B', str(source / 'scripts/install_plugin.py'),
                                     '--host', 'dsh', '--profile', 'desktop', '--dsh', str(CLI)],
                                    cwd=source, capture_output=True, text=True, timeout=600)
            if result.returncode:
                raise ValueError('DSH 安装器未成功完成，未自动重启。请重新打开 DSH 核对现有版本。')
            actual = parse_json((installed / 'package.json').read_bytes())
            if (actual.get('name'), actual.get('version')) != (NAME, args.version):
                raise ValueError('DSH 安装版本未通过核对，未自动重启。')
        # Store successful installation before opening DSH so its startup can see it.
        write_status(args.status, 'installed', args.version, '插件已更新。')
        try:
            subprocess.run(['/usr/bin/open', '-a', str(APP)], check=True, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            write_status(args.status, 'installed', args.version, '插件已更新；未能自动打开 DSH，请手动打开。')
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else '更新失败，未自动打开 DSH。'
        write_status(args.status, 'failed', args.version, message)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
