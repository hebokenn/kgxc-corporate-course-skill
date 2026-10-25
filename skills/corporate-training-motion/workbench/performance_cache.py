"""Bounded, process-local caches for unchanged course files and review evidence.

Cache entries retain only digests and review results, never decoded video buffers.
The original validators still run on a miss; file replacement, edits, deletion and
new dependencies invalidate entries without changing any approval fingerprints.
"""
from collections import OrderedDict
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import threading
from urllib.parse import unquote


_LOCK = threading.RLock()
_RESULTS = OrderedDict()
_LIMIT = 512
APP = Path(__file__).resolve().parent


def _version(path):
    path = Path(path)
    try:
        stat = path.stat()
        return (str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_mode,
                stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except FileNotFoundError:
        return (str(path.absolute()), None)


def _cached(key, files, compute):
    # Serialize misses as well as lookups: concurrent HTTP handlers must not
    # decode or hash the same video simultaneously. RLock permits nested hashes.
    files = tuple(dict.fromkeys(Path(p).absolute() for p in files))
    with _LOCK:
        before = tuple(_version(p) for p in files)
        entry = _RESULTS.get(key)
        if entry is not None and entry[0] == before:
            _RESULTS.move_to_end(key)
            return copy.deepcopy(entry[1])
        result = compute()
        if before != tuple(_version(p) for p in files):
            raise OSError('校验期间文件已变化，请重试')
        _RESULTS[key] = (before, copy.deepcopy(result))
        _RESULTS.move_to_end(key)
        while len(_RESULTS) > _LIMIT:
            _RESULTS.popitem(last=False)
        return result


def sha(path):
    path = Path(path).absolute()

    def compute():
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    return _cached(('sha256', str(path)), [path], compute)


def _runtime_files():
    return sorted(p for p in APP.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts)


def native_fingerprint(project):
    from authoring import native_fingerprint as original
    project = Path(project).resolve()
    files = [project/'motion-contract.json']
    for name in ['native', 'assets', 'audio', 'media', 'source']:
        files.extend(sorted(p for p in (project/name).rglob('*')
                            if p.is_file() and '__pycache__' not in p.parts))
    files.extend(_runtime_files())
    return _cached(('native', str(project)), files, lambda: original(project))


def _review_files(project, video):
    files = [video, project/'workbench.json', project/'motion-contract.json',
             project/'craft-contract.json']

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ['path', 'coverPath', 'thumbnailPath', 'pagePath'] and isinstance(item, str) and item:
                    # Invalid paths remain the validators' responsibility.
                    path = (project/item).resolve()
                    if not Path(item).is_absolute() and path.is_relative_to(project):
                        files.append(path)
                        if key == 'pagePath' and path.is_file():
                            class Sources(HTMLParser):
                                def handle_starttag(self, tag, attrs):
                                    if tag == 'video':
                                        for name, source in attrs:
                                            if name in ['src', 'poster'] and source:
                                                files.append((path.parent/unquote(source)).resolve())
                            Sources().feed(path.read_text())
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for name in ['director-review.json', 'craft-review.json', 'cover-review.json', 'visual-hygiene-review.json']:
        path = project/'qa'/name
        files.append(path)
        try:
            collect(json.loads(path.read_text()))
        except (OSError, ValueError):
            pass
    files.extend(_runtime_files())
    return files


def director_review(project, doc, video):
    from motion_quality import director_review as original
    project = Path(project).resolve()
    video = Path(video).resolve()
    document = hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return _cached(('director', str(project), str(video), document),
                   _review_files(project, video), lambda: original(project, doc, video))
