#!/usr/bin/env python3
"""Export compact phase atlases from the actual KGXC motion canvas.

This is renderer evidence, not a new library or complete lesson. Every source
frame is drawn by the exact released scene engine with genuine gallery objects.
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

FRAME_WIDTH, FRAME_HEIGHT, COLS, ROWS = 320, 180, 4, 3
ATLAS_SIZE = FRAME_WIDTH * COLS, FRAME_HEIGHT * ROWS
# Genuinely authored before / action / after states, not a decorative loop.
PHASES = [-.02, .05, .12, .22, .32, .42, .52, .62, .72, .82, .92, 1.08]
MOTION_BYTES = [
    'motion/effects.js',
    'motion/teaching-effects.js',
    'motion/retail-effects.js',
    'motion/acting.js',
    'motion/character-performance.js',
    'motion/m1-mesh.js',
    'motion/surface-materials.js',
    'motion_catalog.py',
    'motion_demos.py',
    'teaching_modules.py',
    'starter/scene-engine.js',
]

ATLAS_RENDER = """async ([frames, objectId, actionId, w, h, cols, rows])=>{
  const page=window.courseWorkbench;
  const original=document.querySelector("canvas"), atlas=document.createElement("canvas");
  atlas.width=w*cols;atlas.height=h*rows;
  const ctx=atlas.getContext("2d");
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality="high";
  const receipts=[];
  for(let i=0;i<frames.length;i++){
    const f=frames[i];
    await page.seek(f/30);
    const x=(i%cols)*w,y=Math.floor(i/cols)*h;
    ctx.drawImage(original,0,0,original.width,original.height,x,y,w,h);
    const called=page.motionReceipt().find(c=>c.nodeId===objectId&&c.type===actionId);
    const rgba=ctx.getImageData(x,y,w,h).data;
    let hash=2166136261;
    for(let n=0;n<rgba.length;n+=16){hash=Math.imul(hash^rgba[n],16777619);hash=Math.imul(hash^rgba[n+1],16777619);hash=Math.imul(hash^rgba[n+2],16777619);}
    receipts.push({frame:f,progress:called?.progress??null,visualHash:hash>>>0});
  }
  return {mime:atlas.toDataURL("image/jpeg",.91),receipts};
}"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(path, value):
    target = Path(path)
    temp = target.with_suffix(target.suffix + '.pending')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(target)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def export(repo, chromium, out, expected_count, version, source_commit):
    workbench = repo / 'skills/corporate-training-motion/workbench'
    skills = workbench.parent
    sys.path.insert(0, str(workbench))
    from motion_catalog import CATALOG
    from motion_demos import CASES
    if len(CATALOG) != expected_count or set(CASES) != set(CATALOG):
        raise ValueError('Released gallery definitions do not match expected catalogue size')
    print('Building actual release gallery fixture…', flush=True)
    (out / 'actions').mkdir(parents=True, exist_ok=True)
    manifest = dict(
        schema='kgxc-promo-real-actions/1', version=version, sourceCommit=source_commit,
        count=expected_count, finished=0, status='rendering', actualRuntimeCount=0,
        frameWidth=FRAME_WIDTH, frameHeight=FRAME_HEIGHT, columns=COLS, rows=ROWS,
        atlasWidth=ATLAS_SIZE[0], atlasHeight=ATLAS_SIZE[1], tileOrder='row-major',
        tilePositions=[dict(index=i, x=FRAME_WIDTH*(i%COLS), y=FRAME_HEIGHT*(i//COLS))
                       for i in range(COLS*ROWS)],
        sourceCanvas=[1920, 1080], sourceFPS=30, phaseFactors=PHASES,
        sourceHashes={name: sha(workbench / name) for name in MOTION_BYTES},
        scope='Native motion canvas; a 12-frame phase atlas for each real action. No lesson/approval claims.',
        actions=[])
    emit(out / 'manifest.json', manifest)
    with tempfile.TemporaryDirectory(prefix='kgxc-promo-gallery.') as tmp:
        root = Path(tmp) / 'gallery'
        subprocess.run([sys.executable, '-B', str(skills / 'scripts/motion_gallery.py'), str(root)], check=True)
        project = root / 'project'
        doc = json.loads((project / 'workbench.json').read_text())
        names = list(CATALOG)
        graph = {n['id']: n for n in doc['sceneGraph']['nodes']}
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                                                lambda *a, **kw: QuietHandler(*a, directory=tmp, **kw))
        # Native index references /project assets; serve from the project root's parent.
        server.RequestHandlerClass = lambda *a, **kw: QuietHandler(*a, directory=root, **kw)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, executable_path=chromium)
                page = browser.new_page(viewport={'width':1920,'height':1080})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_address[1]}/project/native/index.html')
                page.evaluate('async d=>await courseWorkbench.apply(d)', doc)
                runtime = page.evaluate('CourseMotion.runtimeCatalog()')
                if set(runtime) != set(names) or len(runtime) != len(set(runtime)):
                    raise ValueError(f'Registry mismatch: {sorted(set(runtime)^set(names))}')
                manifest['actualRuntimeCount'] = len(runtime)
                for i, name in enumerate(names):
                    node = graph['object-' + name]
                    effect = next(e for e in node['effects'] if e['type'] == name)
                    start, end = effect['startFrame'], effect['endFrame']
                    scene = doc['scenes'][i]
                    frames = [round(start + (end - start) * q) for q in PHASES]
                    if not scene['sourceStartFrame'] <= frames[0] < frames[-1] < scene['sourceEndFrame']:
                        raise ValueError(f'{name} selection escaped authored scene')
                    captured = page.evaluate(ATLAS_RENDER, [
                        frames, node['id'], name, FRAME_WIDTH, FRAME_HEIGHT, COLS, ROWS])
                    phases = captured['receipts']
                    distinct = len({r['visualHash'] for r in phases})
                    invocations = sum(r['progress'] is not None and 0 < r['progress'] < 1 for r in phases)
                    if distinct < 2 or not invocations:
                        raise ValueError(f'{name} had no actual visible sampled action: {distinct=}, {invocations=}')
                    raw = base64.b64decode(captured['mime'].split(',', 1)[1], validate=True)
                    filename = Path('actions') / (name + '.jpg')
                    p = out / filename
                    p.write_bytes(raw)
                    case = CASES[name]
                    action = dict(id=name, ordinal=i + 1, title=CATALOG[name]['title'],
                                  category=CATALOG[name]['category'], task=case[0],
                                  observe=case[1], objectFamily=case[2],
                                  path=filename.as_posix(), sha256=sha(p),
                                  distinctReducedFrames=distinct, activeRuntimeReceipts=invocations,
                                  sourceFrames=frames, scene=scene['id'], motionProfile=effect.get('motionProfile'),
                                  durationFrames=end - start, runtimeSamples=phases)
                    manifest['actions'].append(action)
                    manifest['finished'] = len(manifest['actions'])
                    emit(out / 'manifest.json', manifest)
                    if i < 3 or (i+1) % 10 == 0:
                        print(f'{i+1}/{expected_count} {name} ({distinct} phase frames)', flush=True)
                if errors:
                    raise ValueError('Native gallery page errors: ' + '; '.join(errors[:3]))
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    assert [action['id'] for action in manifest['actions']] == names
    assert len({action['sha256'] for action in manifest['actions']}) == expected_count
    manifest['status'] = 'complete'
    emit(out / 'manifest.json', manifest)
    print(f'{expected_count}/{expected_count} actual runtime actions exported to {out}', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--chrome', required=True)
    p.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--version', default='v6.9.8')
    p.add_argument('--source-commit', required=True)
    p.add_argument('--expected-actions', type=int, default=100)
    a = p.parse_args()
    export(a.repo.resolve(), a.chrome, a.out.resolve(), a.expected_actions, a.version, a.source_commit)
