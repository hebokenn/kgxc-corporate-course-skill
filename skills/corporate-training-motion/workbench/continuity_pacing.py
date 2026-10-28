"""Purposeful pauses and measured narration gaps; never manufacture reading silence.

All plan windows use source frames. Reports use the edited display clock, including
cuts and inserted holds. Acoustic thresholds are diagnostics, not teaching norms.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from timeline import duration, segments

SCHEMA = 'course-continuity-plan/1'


def policy():
    return dict(schema='course-continuity-policy/1', required=True,
                noiseFloorDB=-42, gapSeconds=2.5,
                scope='diagnostic threshold only; reading exposure overlaps related narration')


def _number(value):
    return type(value) in [int, float] and math.isfinite(value)


def _windows(doc, start, end):
    """Map source windows to retained playback, including holds in that window."""
    result = []
    for span in segments(dict(doc, holds=doc.get('holds', []))):
        if span['kind'] == 'hold':
            if start <= span['holdFrame'] < end:
                result.append([span['startFrame'], span['endFrame']])
        else:
            a = max(start, span['sourceFrame'])
            z = min(end, span['sourceFrame'] + span['endFrame'] - span['startFrame'])
            if a < z:
                result.append([span['startFrame'] + a - span['sourceFrame'],
                               span['startFrame'] + z - span['sourceFrame']])
    merged = []
    for a, z in sorted(result):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(z, merged[-1][1])
        else:
            merged.append([a, z])
    return merged


def inspect(doc, force=False):
    """Read-only structure check. It does not insert holds or relax reading rules."""
    enabled = bool(doc.get('continuityPolicy', {}).get('required'))
    if not enabled and not force:
        return dict(status='legacy-not-opted-in', errors=[], pauses=[])
    config = doc.get('continuityPolicy', {}) if enabled else policy()
    errors = []
    for key, low, high in [('noiseFloorDB', -80, -15), ('gapSeconds', .5, 5)]:
        if not _number(config.get(key)) or not low <= config[key] <= high:
            errors.append('连贯性诊断参数无效 ' + key)
    plan = doc.get('continuityPlan', {})
    if plan.get('schema') != SCHEMA or not isinstance(plan.get('pauses'), list):
        errors.append('缺少 continuityPlan；无计划停顿时也须明确 pauses=[]，不能自动插静音补阅读预算')
        pauses = []
    else:
        pauses = plan['pauses']
    scenes = {s['id']: s for s in doc.get('scenes', [])}
    rows = []
    ids = set()
    for pause in pauses:
        if not isinstance(pause, dict):
            errors.append('计划停顿须为对象'); continue
        identifier = pause.get('id')
        scene = scenes.get(pause.get('sceneId'))
        window = pause.get('window', {})
        a, z = window.get('startFrame'), window.get('endFrame')
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            errors.append('计划停顿ID缺失或重复'); continue
        ids.add(identifier)
        # A real handoff can end just inside the next scene. Keep its start
        # bound to the declared scene and its entire playback window budgeted.
        if not scene or type(a) is not int or type(z) is not int or not (scene['sourceStartFrame'] <= a < scene['sourceEndFrame'] and a < z <= doc['sourceDurationFrames']):
            errors.append('计划停顿须绑定场景中的实际源帧窗口 ' + identifier); continue
        kind = pause.get('kind')
        if kind not in ['practice', 'observation', 'brand']:
            errors.append('停顿只能用于明确作答、观察任务或品牌包装；阅读不足须重新编排 ' + identifier)
        if kind == 'brand' and scene.get('kind') != 'brand':
            errors.append('普通讲解或目录不能声明成品牌静音 ' + identifier)
        if not str(pause.get('reason', '')).strip() or kind != 'brand' and not str(pause.get('learnerCue', '')).strip():
            errors.append('计划停顿须说明用途及给学员的作答/观察提示 ' + identifier)
        maximum = pause.get('maxSeconds')
        if not _number(maximum) or maximum <= 0 or maximum > 60:
            errors.append('计划停顿须声明有限的总静音预算 ' + identifier); continue
        windows = _windows(doc, a, z)
        # A scene-wide whitelist cannot hide arbitrary narration gaps.
        if any((v-u)/doc.get('fps', 30) > maximum + 1/doc.get('fps', 30) for u, v in windows):
            errors.append('停顿窗口大于声明预算，不能整场豁免 ' + identifier)
        rows.append(dict(id=identifier, sceneId=pause['sceneId'], kind=kind,
                         windows=windows, maxSeconds=maximum,
                         learnerCue=pause.get('learnerCue'), reason=pause.get('reason')))
    for i, left in enumerate(rows):
        for right in rows[i+1:]:
            if any(max(a, b) < min(z, y) for a, z in left['windows'] for b, y in right['windows']):
                errors.append('计划停顿窗口重叠，不能叠加豁免 ' + left['id'] + '/' + right['id'])
    for span in segments(dict(doc, holds=doc.get('holds', []))):
        if span['kind'] != 'hold': continue
        a, z = span['startFrame'], span['endFrame']
        allowed = [r for r in rows if any(u <= a < z <= v for u, v in r['windows'])]
        if not allowed:
            errors.append('额外静音未绑定明确作答/观察任务；禁止用停留补阅读预算 @' + str(span['holdFrame']))
        if any(c['startFrame'] < a and c['endFrame'] > z for c in doc.get('captions', [])):
            errors.append('停顿切在尚未结束的口播字幕中 @' + str(span['holdFrame']))
    return dict(schema='course-continuity-preflight/1', status='fail' if errors else 'pass',
                errors=list(dict.fromkeys(errors)), pauses=rows,
                addedHoldSeconds=sum(h['frames'] for h in doc.get('holds', []))/doc.get('fps', 30),
                scope='planned tasks and edited timing; cues and semantic boundaries still require actual review',
                userFinalAcceptance=False)


def require(doc, project=None):
    if project:
        marker = Path(project)/'motion-contract.json'
        contract = json.loads(marker.read_text()) if marker.is_file() else {}
        if contract.get('continuityRequired') and not doc.get('continuityPolicy', {}).get('required'):
            raise ValueError('本工程要求讲解连贯性检查，不能删除 continuityPolicy 绕过检查')
    result = inspect(doc)
    if result['status'] == 'fail':
        raise ValueError('讲解连贯性未通过：' + '；'.join(result['errors']))
    return result


def _detect(path, seconds, config, offset=0, edits=None):
    command = ['ffmpeg', '-hide_banner', '-nostats', '-v', 'info', '-i', str(path),
               '-vn', '-af',
               f'atrim=start={offset}:end={offset+seconds},asetpts=PTS-STARTPTS,'
               f'silencedetect=noise={config["noiseFloorDB"]}dB:d={config["gapSeconds"]}',
               '-f', 'null', '-']
    if edits:
        from timeline import audio_filters
        filters=audio_filters(edits,gain=1)+';[out]'+command[command.index('-af')+1]+'[checked]'
        command[command.index('-af'):command.index('-f')]=['-filter_complex',filters,'-map','[checked]']
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    events = re.findall(r'silence_(start|end):\s*(-?[\d.]+)', result.stderr)
    intervals = []; start = None
    for kind, value in events:
        if kind == 'start': start = max(0., float(value))
        elif start is not None:
            intervals.append([start, min(seconds, float(value))]); start = None
    if start is not None: intervals.append([start, seconds])
    return [[a, z] for a, z in intervals if z-a >= config['gapSeconds']-.01]


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''): h.update(part)
    return h.hexdigest()


def audit(doc, project, first=0, last=None, video=None, force=False):
    """Analyze the dry narration on the same edited clock, plus actual encoded audio.

    Dry narration is required even when a mixed MP4 has continuous background music.
    Source silence is mapped through edits without creating temporary audio files.
    """
    structure = inspect(doc, force=force)
    if structure['status'] == 'legacy-not-opted-in': return structure
    errors = list(structure['errors']); p = Path(project).resolve()
    fps = doc.get('fps', 30); last = duration(doc) if last is None else last
    if not 0 <= first < last <= duration(doc): raise ValueError('连贯性检查范围无效')
    config = doc.get('continuityPolicy', {}) if doc.get('continuityPolicy', {}).get('required') else policy()
    if errors: return dict(structure, narrationIntervals=[], encodedIntervals=[])
    from backend import safe
    name = doc.get('media', {}).get('narration')
    if not name:
        errors.append('缺少 media.narration 干声；不能用带背景音乐的混音证明旁白连续')
        return dict(structure, status='fail', errors=errors, narrationIntervals=[], encodedIntervals=[])
    source = safe(p, name)
    if not source.is_file(): raise ValueError('旁白干声不存在：' + name)
    seconds = float(json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(source)]))['format']['duration'])
    if abs(seconds-doc['sourceDurationFrames']/fps) > .12:
        errors.append('旁白干声与源时间轴时长不一致；先统一时间基准')
    # A cut or inserted hold can join otherwise short natural gaps. Decode the
    # actual edited dry track when edits exist, rather than assuming source gaps
    # alone describe the final sound.
    edits=doc if doc.get('holds') or doc.get('cuts') else None
    mapped = [[a+first/fps, z+first/fps] for a, z in _detect(source, (last-first)/fps, config, first/fps, edits)]
    def classify(intervals, track):
        rows = []
        for a, z in intervals:
            if z-a < config['gapSeconds']-.01: continue
            permit = next((r for r in structure['pauses'] if z-a <= r['maxSeconds']+.08 and
                           any(u/fps-.08 <= a and z <= v/fps+.08 for u, v in r['windows'])), None)
            rows.append(dict(start=round(a, 4), end=round(z, 4), seconds=round(z-a, 4),
                             plannedPause=permit['id'] if permit else None))
            if not permit: errors.append(f'{track}存在未安排的讲解中断 {a:.2f}–{z:.2f}秒；重新编排，不能自动补静音')
        return rows
    narration = classify(mapped, '旁白干声')
    encoded = []
    if video:
        encoded = classify([[a+first/fps, z+first/fps] for a, z in _detect(video, (last-first)/fps, config)], '最终编码音轨')
    return dict(schema='course-continuity-audit/1', status='fail' if errors else 'pass', errors=errors,
                documentSha256=hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                narrationSha256=_sha(source), videoSha256=_sha(video) if video else None,
                firstFrame=first, lastFrame=last, fps=fps, thresholds=config,
                narrationIntervals=narration, encodedIntervals=encoded, plan=structure,
                scope='acoustic gap diagnosis on dry narration and optional final encoded audio; not ASR, semantic or listening approval',
                userFinalAcceptance=False)


def export_errors(doc, project, video, metadata):
    """Do not register a different video, document, narration or cropped receipt."""
    require(doc, project)
    if not doc.get('continuityPolicy', {}).get('required'): return []
    report=metadata.get('verification',{}).get('narrationContinuity',{})
    from backend import safe
    name=doc.get('media',{}).get('narration')
    if not name: return ['缺少同轴旁白干声']
    document_sha=hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    expected=metadata.get('range',{})
    if (any(type(expected.get(k))is not int for k in ['firstFrame','lastFrame','fps']) or
        expected.get('fps')!=doc.get('fps',30) or
        not 0<=expected.get('firstFrame',-1)<expected.get('lastFrame',-1)<=duration(doc) or
        report.get('status')!='pass' or report.get('errors') or
        report.get('videoSha256')!=_sha(video) or report.get('narrationSha256')!=_sha(safe(project,name)) or
        report.get('documentSha256')!=document_sha or
        any(report.get(k)!=expected.get(k) for k in ['firstFrame','lastFrame','fps'])):
        return ['缺少绑定当前文档、干声、实际导出范围及编码视频的讲解连贯性回执']
    return []


def enable(course, evidence):
    """Explicit opt-in only; no course regeneration or invented acceptance."""
    if not str(evidence).strip(): raise ValueError('旧课启用连贯性检查须保留实际修改依据')
    from backend import atomic
    from workflow import Course, read
    c = Course(course); p = c.project
    with c.locked():
        doc = read(p/'workbench.json'); contract = read(p/'motion-contract.json', {})
        if doc.get('continuityPolicy', {}).get('required') and contract.get('continuityRequired'):
            return dict(status='already-enabled', revision=doc['revision'])
        history = p/'workbench-history'/f'{doc["revision"]:06}.json'
        if history.is_file() and read(history) != doc: raise ValueError('历史版本同名且内容不同，保留原件后处理')
        atomic(history, doc)
        doc['continuityPolicy'] = policy(); doc['revision'] += 1; contract['continuityRequired'] = True
        atomic(p/'motion-contract.json', contract); atomic(p/'workbench.json', doc)
        atomic(p/'work/continuity-policy'/f'r{doc["revision"]:06}.json', dict(evidence=evidence, revision=doc['revision'], notUserApproval=True))
    return dict(status='enabled', revision=doc['revision'], next='绑定同时间轴 media.narration 干声与 continuityPlan；不生成或批准视频')
