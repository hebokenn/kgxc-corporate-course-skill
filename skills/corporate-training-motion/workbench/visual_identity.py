"""Keep authored course colours consistent with the reviewed pilot.

UI colours are deliberately outside this contract. It checks authored paints,
not image pixels or whether a composition looks good.
"""
import hashlib
import json
import re
from pathlib import Path

SCHEMA = 'course-visual-palette/1'


def colors(paint):
    if isinstance(paint, str):
        value = paint.strip().lower()
        value = {'white': '#ffffff', 'black': '#000000'}.get(value, value)
        if value in ('none', 'transparent', ''):
            return []
        if re.fullmatch(r'#[0-9a-f]{3,4}', value):
            value = '#' + ''.join(c * 2 for c in value[1:])
        if re.fullmatch(r'#[0-9a-f]{6}([0-9a-f]{2})?', value):
            return [] if value.endswith('00') and len(value) == 9 else [value]
        return [value]
    if isinstance(paint, dict):
        result = []
        for key, value in paint.items():
            if key in ('color', 'colors', 'stops', 'fromColor', 'toColor'):
                result.extend(colors(value))
        return result
    if isinstance(paint, (tuple, list)):
        return [c for item in paint for c in colors(item) if not isinstance(item, (float, int))]
    return []


def paints(doc, intervals=None):
    intervals = intervals or [(0, doc.get('sourceDurationFrames', 1))]
    scenes = {s['id']: s for s in doc.get('scenes', [])}
    yield 'canvas', 'sceneGraph.background', doc.get('sceneGraph', {}).get('background', '#ffffff')

    def walk(nodes, exempt=False, parent_span=None):
        for node in nodes:
            reason = node.get('contentColorReason')
            # Natural product/illustration colours need an explicit local reason;
            # a theme name or boolean cannot silently exempt a container.
            skip = exempt or (isinstance(reason, str) and len(reason.strip()) >= 8)
            scene = scenes.get(node.get('sceneId'), {})
            a = max(node.get('startFrame', 0), scene.get('sourceStartFrame', 0), (parent_span or (0, 0))[0])
            z = min(node.get('endFrame', doc.get('sourceDurationFrames', 1)), scene.get('sourceEndFrame', doc.get('sourceDurationFrames', 1)), (parent_span or (0, doc.get('sourceDurationFrames', 1)))[1])
            visible = any(max(a, x) < min(z, y) for x, y in intervals)
            if not skip and visible:
                if node.get('type') in ('text', 'rect', 'ellipse', 'path') and node.get('fill') is not None:
                    role = 'text' if node['type'] == 'text' else 'surface'
                    yield role, node['id'] + '.fill', node.get('fill', '#202020')
                if node.get('stroke'):
                    yield 'line', node['id'] + '.stroke', node['stroke']
                for index, effect in enumerate(node.get('effects', [])):
                    for key in ['color', 'fill', 'stroke', 'colors', 'stops']:
                        if effect.get(key) is not None:
                            yield ('line' if key == 'stroke' else 'surface'), node['id'] + '.effects.' + str(index) + '.' + key, effect[key]
            if visible:
                yield from walk(node.get('children', []), skip, (a, z))
    yield from walk(doc.get('sceneGraph', {}).get('nodes', []))
    progress = doc.get('navigation', {}).get('progress', {})
    for key, role in [('background', 'canvas'), ('track', 'surface'), ('color', 'line')]:
        if progress.get(key):
            yield role, 'navigation.progress.' + key, progress[key]


def capture(doc, artifacts=None, project=None):
    intervals = None
    if project:
        spans = []
        for item in artifacts or []:
            video = (Path(project) / item['path']).resolve()
            sidecar = video.with_suffix('.json')
            if video.suffix.lower() != '.mp4' or not sidecar.is_file():
                continue
            metadata = json.loads(sidecar.read_text())
            r = metadata.get('range', {})
            a, z = r.get('firstFrame'), r.get('lastFrame')
            if not isinstance(a, int) or not isinstance(z, int) or a >= z:
                continue
            from timeline import segments
            for span in segments(doc):
                x, y = max(a, span['startFrame']), min(z, span['endFrame'])
                if x < y:
                    start = span['sourceFrame'] + (x - span['startFrame'] if span['kind'] == 'source' else 0)
                    spans.append((start, start + (y - x if span['kind'] == 'source' else 1)))
        if spans:
            intervals = spans
    palette = {role: set() for role in ['canvas', 'text', 'surface', 'line']}
    for role, _, paint in paints(doc, intervals):
        palette[role].update(colors(paint))
    return dict(schema=SCHEMA, palette={k: sorted(v) for k, v in palette.items()},
                references=artifacts or [], scope='exported pilot source intervals' if intervals else 'authored document; external reference has no mapped range',
                neutral_extensions=True)


def digest(lock):
    return hashlib.sha256(json.dumps(lock, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def check(doc, lock):
    if not lock:
        return []  # Do not retroactively rewrite historical approvals.
    if lock.get('schema') != SCHEMA:
        return ['配色约束版本无效']
    errors = []
    for role, target, paint in paints(doc):
        for color in colors(paint):
            allowed = lock.get('palette', {}).get(role, [])
            neutral = bool(re.fullmatch(r'#[0-9a-f]{6}([0-9a-f]{2})?', color) and color[1:3] == color[3:5] == color[5:7])
            if color not in allowed and not (role != 'canvas' and neutral and lock.get('neutral_extensions')):
                errors.append('配色偏离已确认小样：' + target + ' = ' + color + '（' + role + '）')
    return list(dict.fromkeys(errors))
