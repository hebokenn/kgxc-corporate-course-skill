"""Read-only, version-bound production gates; never manufacture creative approval.

The contract carries executable requirements.  A plan, an event count, and a
producer's observation are different evidence and are deliberately checked apart.
``inspect`` accepts a standalone document and does not require an export filename.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import wave

FILENAME = 'production-contract.json'
REQUIRED_MARKER = 'production-contract-required.json'
SCHEMA = 'course-production-contract/1'
ROOT = Path(__file__).resolve().parents[1]
LABELS = dict(sfx='所选原库音效与编码音轨', emphasis='重点花字及阅读窗',
              direction='内容语义动作与制作端复核', logo='右上原版Logo',
              chapters='有标签和当前状态的分段导航', bookends='R5片头与R8片尾实际拼接')
IMPLEMENTATION_FIELDS = {
    'sfx': 'palette, assets[{id,path,sha256}], required_asset_ids, plan_path, review.encoded_audio_sha256',
    'emphasis': 'events[{id,quote,purpose,node_id,start_frame,end_frame,reading_window:[a,z]}], review',
    'direction': 'scenes[{scene_id,quote,purpose,before,process,after,node_ids,start_frame,end_frame,change_kind?,reason?,reading_window?,diagram_labels?}], review (observations include scene_id)',
    'diagram_labels': 'Optional scene bindings [{diagram_node_ids,label_node_ids,meaning,start_frame,end_frame}]. Important business diagrams need identifiable body labels; captions, headers and navigation do not substitute. Validate declared bindings and frame windows; producer checks actual meaning/readability, not decoration counts.',
    'logo': 'asset{path,sha256}, node_ids, position:top-right, review',
    'chapters': 'segments[{id,label,node_id,start_frame,end_frame,states:[{frame,state}]}], review',
    'bookends': 'brand_version, manifest_path, assembly_path; current video hash, actual ranges and source hashes',
    'review': 'status:verified, actor, evidence, document_sha256, video_sha256, observations:[{frame,observation,scene_id?,stage?}]',
    'pilot_defer': 'pilot only: reason, actor, evidence, document_sha256, video_sha256, source_range:[a,z]; explicitly scoped producer evidence, never valid for final',
}


def _read(path, default=None):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else copy.deepcopy(default or {})
    except (OSError, ValueError, TypeError):
        return copy.deepcopy(default or {})


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def document_digest(document):
    """Semantic JSON hash for dictionary callers; file callers may use byte SHA."""
    return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def _path(project, value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return None
    path = Path(value).expanduser()
    return (path if path.is_absolute() else Path(project) / path).resolve()


def _file(project, value, digest=None):
    path = _path(project, value)
    return path if path and path.is_file() and (not digest or _sha(path) == digest) else None


def _scope(project):
    p = Path(project)
    state, plan = _read(p / 'course-state.json'), _read(p / 'teaching-plan.json')
    branch = state.get('branch') or plan.get('branch')
    if isinstance(branch, dict):
        branch = branch.get('id') or branch.get('type')
    if branch == 'courseware':
        return False, False, 'courseware'
    gates = state.get('gates', {})
    final = gates.get('final', {}) if isinstance(gates, dict) else {}
    registered = set(state.get('artifacts', {}).get('final', []))
    delivered = [item for delivery in state.get('deliveries', []) if delivery.get('branch') == 'video'
                 for item in delivery.get('files', []) if isinstance(item, dict)]
    frozen = bool(final and delivered and any(item.get('path') in registered and
                  str(item.get('path', '')).lower().endswith('.mp4') and
                  _file(p, item.get('path'), item.get('sha256')) and item.get('sha256') for item in delivered))
    if frozen and state.get('schema') == 'course-workflow/2':
        # Use the owning workflow's current content/native basis, not a stale
        # final receipt left in a state file after a revision.  This does not
        # call status/handoff (which themselves read this module).
        try:
            from workflow import Course
            course = Course(p)
            frozen = bool(final.get('sha256') and final['sha256'] == course._gate_hash('final', plan, state))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            frozen = False
    existing = _read(p / 'production-preferences.json').get('recorded_existing_production', {})
    if str(state.get('version', '')).startswith(('6.4.', '6.3.', '6.2.')):
        frozen = frozen or bool(existing.get('video_path') in registered and
            existing.get('video_sha256') and _file(p, existing.get('video_path'), existing['video_sha256']) and
            existing.get('actor') and existing.get('evidence'))
    # Missing files in an active project do not opt it out.  An existing frozen
    # course without a contract remains untouched until an explicit new task.
    teaching = state.get('schema') == 'course-workflow/2' and branch is None
    required = ((p / FILENAME).is_file() or (p / REQUIRED_MARKER).is_file() or
                (p / 'work/production-contract-history').is_dir() or not frozen and not teaching)
    return required, frozen, branch or 'video'


def _profile(project, explicit=None, document=None):
    p = Path(project)
    candidates = [('explicit', explicit)] if explicit is not None else []
    for name in ['teaching-plan.json', 'course-state.json', 'project.json', 'profile.json', 'workbench.json']:
        doc = _read(p / name)
        brand = doc.get('brand', {})
        candidates.extend([(name, doc.get('profile')), (name, doc.get('brand_profile')),
                           (name, brand.get('profile') if isinstance(brand, dict) else brand)])
        if name == 'profile.json':
            candidates.append((name, doc.get('id')))
    if document:
        candidates.extend([('document', document.get('profile')), ('document', document.get('brand_profile'))])
    for source, item in candidates:
        identifier = item.get('id') or item.get('profile') if isinstance(item, dict) else item
        if isinstance(identifier, str) and identifier.strip():
            possible = _file(p, identifier)
            if possible and possible.suffix == '.json':
                identifier = _read(possible).get('id', identifier)
            return dict(id=identifier, basis=source)
    # These are unique, already-present KG identifiers; a title containing a
    # generic company/course word is never used as brand evidence.
    for name in ['source/current-final-assembly.json', 'current-status.json', 'source/course-composition.json', 'workbench.json']:
        value = _read(p / name)
        text = json.dumps(value, ensure_ascii=False)
        if any(marker in text for marker in ['R5-intro-R8-outro', 'kgxc-bookends-r5',
                'fd088e5b6b5d8b35d4a73ed0ada69afbc6a56aecd9e483123add67a4257e73a9']):
            return dict(id='kgxc', basis=name + ':existing-unique-brand-identifier')
    if document and 'fd088e5b6b5d8b35d4a73ed0ada69afbc6a56aecd9e483123add67a4257e73a9' in json.dumps(document):
        return dict(id='kgxc', basis='document:original-KG-asset-sha256')
    return dict(id=None, basis='no-brand-profile')


def _native_assets():
    palette = ROOT / 'assets/sfx/teaching-native-v1'
    catalog = _read(palette / 'palette.json')
    return [dict(id=a['id'], path=str(palette / a['path']), sha256=a['sha256'])
            for a in catalog.get('assets', []) if all(k in a for k in ['id', 'path', 'sha256'])]


def _defaults(project, profile=None, document=None):
    p = Path(project)
    preferences = _read(p / 'production-preferences.json')
    choices = preferences.get('choices', {})
    if not isinstance(choices, dict):
        choices = {}
    brand = _profile(p, profile, document)
    kg = brand['id'] == 'kgxc'
    original = _read(ROOT / 'assets/brand/logo.json')
    requirements = {
        'sfx': dict(required=choices.get('sound_effects') != 'off', palette='teaching-native-v1',
                    assets=_native_assets() if choices.get('sound_effects') == 'native' else [],
                    required_asset_ids=['focus-native'] if choices.get('sound_effects') == 'native' else [],
                    plan_path='audio/sfx-plan.json', review={}),
        'emphasis': dict(required=choices.get('flower_text') != 'off', events=[], review={}),
        'direction': dict(required=True, scenes=[], review={}),
        'logo': dict(required=kg, asset=dict(path=str(ROOT / 'assets/brand/kgxc-logo.png'),
                     sha256=original.get('sha256')), position='top-right', node_ids=[], review={}),
        'chapters': dict(required=True, segments=[], review={}),
        'bookends': dict(required=kg, brand_version='R5-intro-R8-outro' if kg else None,
                         manifest_path='', assembly_path='source/current-final-assembly.json', review={}),
    }
    return dict(schema=SCHEMA, profile=brand, choices=copy.deepcopy(choices), requirements=requirements)


def ensure(project, profile=None, activate=False):
    """Create missing requirements once; preserve saved decisions and evidence."""
    p = Path(project).resolve()
    required, frozen, _ = _scope(p)
    if not required and not activate:
        return load(p)
    old = _read(p / FILENAME)
    defaults = _defaults(p, profile)
    value = copy.deepcopy(old) if old else defaults
    value.setdefault('schema', SCHEMA)
    value.setdefault('profile', defaults['profile'])
    value.setdefault('choices', defaults['choices'])
    for key, requirement in defaults['requirements'].items():
        value.setdefault('requirements', {}).setdefault(key, requirement)
    if value.get('choices') != defaults['choices']:
        value['choices'] = defaults['choices']
        for key, requirement in defaults['requirements'].items():
            current = value['requirements'][key]
            current['required'] = requirement['required']
            current['review'] = {}  # Prior observations remain in immutable history.
        if defaults['choices'].get('sound_effects') == 'native' and not value['requirements']['sfx'].get('assets'):
            value['requirements']['sfx'].update(assets=defaults['requirements']['sfx']['assets'],
                                               required_asset_ids=defaults['requirements']['sfx']['required_asset_ids'])
    if profile is not None and value.get('profile') != defaults['profile']:
        value['profile'] = defaults['profile']
        for key in ['logo', 'bookends']:
            value['requirements'][key]['required'] = defaults['requirements'][key]['required']
            value['requirements'][key]['review'] = {}
    path = p / FILENAME
    if not path.is_file() or value != old:
        p.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            history = p / 'work/production-contract-history' / (_sha(path) + '.json')
            if not history.is_file():
                history.parent.mkdir(parents=True, exist_ok=True)
                history.write_bytes(path.read_bytes())
        temporary = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    marker = p / REQUIRED_MARKER
    if not marker.is_file():
        marker.write_text(json.dumps(dict(schema='course-production-contract-required/1',
                                         contract=FILENAME, policy='missing contract or preferences never disables this gate'),
                                    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return load(p)


def load(project):
    p = Path(project).resolve()
    required, frozen, branch = _scope(p)
    value = _read(p / FILENAME)
    defaults = _defaults(p)
    preferences = _read(p / 'production-preferences.json')
    choices = preferences.get('choices', {})
    choices = choices if isinstance(choices, dict) else {}
    brand = value.get('profile', defaults['profile'])
    kg = (brand.get('id') if isinstance(brand, dict) else brand) == 'kgxc' or defaults['profile']['id'] == 'kgxc'
    answers = preferences.get('answers', {})
    logo_answer = answers.get('logo', {}) if isinstance(answers, dict) else {}
    logo_answer = logo_answer if isinstance(logo_answer, dict) else {}
    logo_off = choices.get('logo') == 'off' and logo_answer.get('value') == 'off' and logo_answer.get('actor') and logo_answer.get('evidence')
    enabled = dict(sfx=choices.get('sound_effects') != 'off', emphasis=choices.get('flower_text') != 'off',
                   direction=True, chapters=True, logo=kg and not logo_off, bookends=kg)
    return dict(schema=SCHEMA, contract_path=FILENAME, exists=(p / FILENAME).is_file(),
                required=required, ready=not required, frozen=frozen, branch=branch,
                profile=brand, choices=choices,
                requirements={key: dict(id=key, required=bool(enabled[key]),
                                        label=label, path=FILENAME + '#requirements.' + key) for key, label in LABELS.items()},
                implementation_fields=IMPLEMENTATION_FIELDS,
                next_steps=['读取契约并落实六项实际对象、事件、混音和拼接；保留有效选择与历史',
                            '有业务含义且需要说明的图示、节点或关系须登记diagram_labels并在正文标清含义；逐字稿旁白、字幕、页眉不替代图示标签，装饰图标不强制加字；制作端核对实际画面是否可理解',
                            '制作端按当前文档和当前视频定向实查并登记，inspect通过后继续现有确认流程；不新增模型盲审'])


def _document(project, document, video):
    if isinstance(document, dict):
        return document, None
    if document is not None:
        path = _file(project, document)
        return (_read(path), path) if path else ({}, None)
    # Bind a real export to its video metadata, not to a filename convention.
    metadata = _read(video.with_suffix('.json')) if video else {}
    if video and metadata.get('video_sha256') == _sha(video) and metadata.get('document_sha256'):
        for path in sorted((Path(project) / 'work/workbench/exports').glob('*/document.json')):
            doc = _read(path)
            if metadata['document_sha256'] in [_sha(path), document_digest(doc)]:
                return doc, path
    assembly = _read(Path(project) / 'source/current-final-assembly.json')
    if video and assembly.get('video_sha256') == _sha(video):
        path = _file(project, assembly.get('body_document'))
        if path:
            return _read(path), path
    return {}, None


def _walk(nodes):
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        yield node
        yield from _walk(node.get('children', []))


def _range(value, limit=None):
    return (isinstance(value, list) and len(value) == 2 and all(type(v) is int for v in value)
            and 0 <= value[0] < value[1] and (limit is None or value[1] <= limit))


def _node_range(node, a, z, duration):
    return node.get('visible', True) is not False and node.get('opacity', 1) != 0 and \
        node.get('startFrame', 0) <= a < z <= node.get('endFrame', duration)


def _node_ancestors(nodes):
    """Keep declared parent visibility/scope when inspecting nested labels."""
    result = {}
    def visit(items, parents):
        for node in items if isinstance(items, list) else []:
            if not isinstance(node, dict):
                continue
            result[node.get('id')] = parents
            visit(node.get('children', []), parents + [node])
    visit(nodes, [])
    return result


def _diagram_label_errors(scene, nodes, duration, ancestors, non_body_ids):
    """Check explicit bindings, never infer semantic completeness from icons.

    Omitting this optional field preserves older contracts.  Declared labels
    still require the same current encoded producer observations as direction;
    metadata alone cannot establish reading, occlusion or teaching meaning.
    """
    if 'diagram_labels' not in scene:
        return []
    bindings = scene['diagram_labels']
    if not isinstance(bindings, list) or not bindings:
        return ['图示标签已登记但缺少实际图示与正文标签绑定；不需要时省略并保留制作端依据']
    errors = []
    excluded_roles = {'caption', 'subtitle', 'navigation', 'title', 'header', 'footer'}
    for index, binding in enumerate(bindings):
        prefix = '图示标签绑定' + str(index + 1) + '：'
        if not isinstance(binding, dict):
            errors.append(prefix + '必须登记实际图示、正文标签、含义和帧窗')
            continue
        a, z = binding.get('start_frame'), binding.get('end_frame')
        span = [a, z]
        if (not _range(span, duration) or
                not scene.get('start_frame', 0) <= a < z <= scene.get('end_frame', duration)):
            errors.append(prefix + '帧窗须在当前教学片段内')
            continue
        meaning = binding.get('meaning')
        if not isinstance(meaning, str) or not meaning.strip():
            errors.append(prefix + '缺少图示或关系所代表的业务含义')
        for field, is_label in [('diagram_node_ids', False), ('label_node_ids', True)]:
            ids = binding.get(field)
            label = '正文文字标签' if is_label else '图示对象'
            if (not isinstance(ids, list) or not ids or
                    any(not isinstance(identifier, str) or not identifier.strip() for identifier in ids)):
                errors.append(prefix + '缺少实际' + label + '节点ID')
                continue
            for identifier in ids:
                node = nodes.get(identifier)
                if not node:
                    errors.append(prefix + label + '节点不存在：' + identifier)
                    continue
                lineage = ancestors.get(identifier, []) + [node]
                if any(n.get('sceneId') not in [None, scene.get('scene_id')] for n in lineage):
                    errors.append(prefix + label + '不属于当前片段：' + identifier)
                if any(not _node_range(n, a, z, duration) for n in lineage):
                    errors.append(prefix + label + '或父容器未覆盖登记帧窗：' + identifier)
                if is_label:
                    if node.get('type') != 'text' or not isinstance(node.get('text'), str) or not node['text'].strip():
                        errors.append(prefix + '须使用实际非空正文text标签：' + identifier)
                    if any(str(n.get('role', '')).lower() in excluded_roles or n.get('id') in non_body_ids
                           for n in lineage):
                        errors.append(prefix + '字幕、页眉或导航不能替代正文图示标签：' + identifier)
    return errors


def _has_action(node, a, z):
    # Opacity-only appearance is not evidence of semantic change.
    actor = node.get('vectorActor', {})
    if any(max(a, m.get('startFrame', 0)) < min(z, m.get('endFrame', 0))
           for m in actor.get('walks', []) + actor.get('turns', [])):
        return True
    keys = actor.get('keys', []) + node.get('performance', {}).get('keys', [])
    if len({json.dumps(k.get('values', {}), sort_keys=True) for k in keys
            if a <= k.get('frame', -1) <= z}) > 1:
        return True
    for motion in node.get('motion', []) + node.get('effects', []):
        if max(a, motion.get('startFrame', 0)) >= min(z, motion.get('endFrame', 0)):
            continue
        kind = motion.get('kind') or motion.get('type') or motion.get('property')
        if kind and kind not in ['opacity', 'fade', 'fade-in', 'fade-out', 'appear', 'disappear']:
            return True
    return False


def _directed_change(scene, nodes, duration, review):
    a, z = scene['start_frame'], scene['end_frame']
    if any(_has_action(nodes[identifier], a, z) for identifier in scene['node_ids']):
        return True
    kind = scene.get('change_kind')
    observations = [row for row in review.get('observations', []) if isinstance(row, dict) and
                    row.get('scene_id') == scene.get('scene_id')]
    if kind == 'purposeful-reading':
        span = scene.get('reading_window')
        return bool(scene.get('reason') and _range(span, duration) and a <= span[0] < span[1] <= z and observations)
    if kind not in ['information-reveal', 'comparison-reveal', 'focus-change']:
        return False
    stages = {row.get('stage') for row in observations}
    if not {'before', 'after'} <= stages:
        return False
    # Whether the new fact or comparison teaches the claimed point remains a
    # producer judgment; only its real visibility change is determined here.
    for identifier in scene['node_ids']:
        node = nodes[identifier]
        if a < node.get('startFrame', 0) < z:
            return True
        for motion in node.get('motion', []) + node.get('effects', []):
            kind = motion.get('kind') or motion.get('type') or motion.get('property')
            if kind in ['opacity', 'fade', 'fade-in', 'appear'] and max(a, motion.get('startFrame', 0)) < min(z, motion.get('endFrame', 0)):
                return True
    return False


def _review_errors(review, hashes, video_sha, duration):
    if not isinstance(review, dict):
        return ['缺少制作端实物复核']
    if review.get('status') != 'verified' or not review.get('actor') or not review.get('evidence'):
        return ['缺少带实际观察依据的制作端复核；程序不能断言语义、声音自然度或美观']
    if review.get('document_sha256') not in hashes or not video_sha or review.get('video_sha256') != video_sha:
        return ['制作端复核未绑定当前文档与当前视频字节']
    observations = review.get('observations', [])
    if not isinstance(observations, list) or not observations or any(
            not isinstance(row, dict) or type(row.get('frame')) is not int or row['frame'] < 0 or
            not isinstance(row.get('observation'), str) or not row['observation'].strip() for row in observations):
        return ['制作端复核须列实际编码帧和观察，不能只写数量或通过']
    return []


def _audio_hash(video):
    try:
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-map', '0:a:0',
                                 '-c:a', 'copy', '-f', 'hash', '-hash', 'sha256', '-'],
                                capture_output=True, text=True, timeout=30)
        return result.stdout.strip().split('=')[-1].lower() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _video_probe(video):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                 'stream=codec_type,width,height,nb_frames,duration', '-of', 'json', str(video)],
                                capture_output=True, text=True, timeout=15)
        streams = json.loads(result.stdout).get('streams', []) if result.returncode == 0 else []
        return bool(streams and streams[0].get('codec_type') == 'video' and streams[0].get('width', 0) > 0)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def _bookends(project, requirement, video_sha):
    p = Path(project)
    assembly_path = _file(p, requirement.get('assembly_path') or 'source/current-final-assembly.json')
    assembly = _read(assembly_path) if assembly_path else {}
    if assembly.get('video_sha256', assembly.get('current_video_sha256')) != video_sha or not video_sha:
        return ['缺少绑定当前视频的首尾实际拼接回执'], {}
    reports = [assembly]
    for key in ['source_timeline', 'composition_receipt', 'report', 'targeted_acceptance']:
        path = _file(p, assembly.get(key))
        if path:
            reports.append(_read(path))
    manifest_path = _file(p, requirement.get('manifest_path') or assembly.get('brand_manifest'))
    manifest = _read(manifest_path) if manifest_path else {}
    if not manifest_path or not ('r5' in str(manifest.get('brand_version', '')).lower() and
                                  'r8' in str(manifest.get('brand_version', '')).lower()):
        return ['首尾缺少实际R5/R8品牌资产清单'], {}
    approved_backgrounds = _read(ROOT / 'assets/bookends/packaging-provenance.json').get('backgrounds', {})
    backgrounds = manifest.get('source', {}).get('backgrounds', {})
    if any(not approved_backgrounds.get(kind, {}).get('sha256') or
           backgrounds.get(kind, {}).get('sha256') != approved_backgrounds[kind]['sha256']
           for kind in ['intro', 'outro']):
        return ['首尾片段未继承已批准R5/R8原始背景哈希'], {}
    digest = _sha(manifest_path)
    if not any(report.get('brand_manifest_sha256') == digest for report in reports):
        return ['首尾拼接回执未绑定当前品牌资产清单哈希'], {}
    errors, evidence = [], dict(manifest=str(manifest_path), manifest_sha256=digest)
    for kind in ['intro', 'outro']:
        filename = next((name for name in [kind + '.mp4', kind + '-1080p30.mp4']
                         if manifest.get('files', {}).get(name)), None)
        if not filename or not _file(manifest_path.parent, filename, manifest['files'][filename]):
            errors.append('首尾实际片段缺失或哈希变化：' + kind)
        ranges = [report.get(kind + '_frames') for report in reports]
        for report in reports:
            brand_ranges = report.get('brand_ranges', {})
            if isinstance(brand_ranges, dict):
                ranges.append(brand_ranges.get(kind))
            elif isinstance(brand_ranges, list):
                ranges += [row.get('range', [row.get('startFrame'), row.get('endFrame')])
                           for row in brand_ranges if isinstance(row, dict) and row.get('kind', row.get('type')) == kind]
        valid = next((span for span in ranges if _range(span)), None)
        if not valid:
            errors.append('首尾缺少当前成片实际帧范围：' + kind)
        evidence[kind] = dict(file=filename, range=valid)
    if not any((report.get('current_video_sha256', report.get('video_sha256')) == video_sha and
                (report.get('actual_frames_visual_inspection') or report.get('observations'))) for report in reports):
        errors.append('首尾缺少绑定当前编码的实际画面复核记录')
    return errors, evidence


def _inspect(project, document=None, video=None, purpose='final'):
    """Fail closed on required, missing or stale implementation evidence.

    No file is changed.  Successful structure checks only mean the recorded
    implementation and producer review are current; they are not user approval.
    """
    p = Path(project).resolve()
    required, frozen, branch = _scope(p)
    supplied_video = _file(p, video) if video is not None else None
    if frozen and supplied_video and not (p / FILENAME).is_file():
        state = _read(p / 'course-state.json')
        known = [item.get('sha256') for delivery in state.get('deliveries', [])
                 for item in delivery.get('files', []) if isinstance(item, dict)]
        known.append(_read(p / 'production-preferences.json').get('recorded_existing_production', {}).get('video_sha256'))
        if _sha(supplied_video) not in known:
            required = True  # A historical delivery never exempts a new candidate.
    if not required:
        return dict(required=False, ready=True, errors=[], checks={}, frozen=frozen,
                    reason='沿用已冻结旧课或独立课件，不自动迁移或改写', purpose=purpose)
    video_path = _file(p, video) if video is not None else None
    if video_path is None and video is None:
        assembly = _read(p / 'source/current-final-assembly.json')
        video_path = _file(p, assembly.get('video_source', assembly.get('video_path')))
    doc, doc_path = _document(p, document, video_path)
    video_sha = _sha(video_path) if video_path else None
    hashes = {document_digest(doc)} if doc else set()
    if doc_path:
        hashes.add(_sha(doc_path))
    value = _read(p / FILENAME)
    defaults = _defaults(p, document=doc)
    preferences = _read(p / 'production-preferences.json')
    choices = preferences.get('choices', {})
    if not isinstance(choices, dict):
        choices = {}
    errors, checks = [], {}

    def error(key, message, evidence=None):
        errors.append(dict(id=key + '-' + str(sum(e['requirement'] == key for e in errors) + 1),
                           requirement=key, message=message, evidence=evidence or {}))

    if not (p / FILENAME).is_file() or value.get('schema') != SCHEMA:
        error('contract', '当前视频缺少有效制作契约；删除契约不能免检', dict(path=FILENAME))
    if not (p / 'production-preferences.json').is_file():
        error('preferences', '当前视频缺少实际制作偏好文件，不能把缺失当作关闭')
    for key, options in [('sound_effects', ['native', 'off']), ('flower_text', ['key-points', 'minimal', 'off'])]:
        if choices.get(key) not in options:
            error('preferences', '尚无实际选择：' + key)
    if value and value.get('choices', {}) != choices:
        error('contract', '制作契约的选择快照已过期；保留历史并按实际当前选择更新契约')
    if not doc:
        error('document', '缺少绑定当前视频的实际导出文档；可显式提供document字典或JSON路径')
    if not video_path:
        error('video', '缺少当前实际编码视频，计划不能代替实物')
    elif not _video_probe(video_path):
        error('video', '当前文件无法识别为实际编码视频，未放行')
    nodes = {node.get('id'): node for node in _walk(doc.get('sceneGraph', {}).get('nodes', []))}
    ancestors = _node_ancestors(doc.get('sceneGraph', {}).get('nodes', []))
    non_body_ids = {caption.get('id') for caption in doc.get('captions', []) if isinstance(caption, dict)}
    assets = doc.get('assets', [])
    if isinstance(assets, list):
        assets = {asset.get('id'): asset for asset in assets if isinstance(asset, dict)}
    if not isinstance(assets, dict):
        assets = {}
    duration = doc.get('sourceDurationFrames', 0)
    requirements = value.get('requirements', {})
    if not isinstance(requirements, dict):
        requirements = {}
    chapter_requirement = requirements.get('chapters', {})
    if isinstance(chapter_requirement, dict):
        non_body_ids.update(segment.get('node_id') for segment in chapter_requirement.get('segments', [])
                            if isinstance(segment, dict))
    profile = value.get('profile', defaults['profile'])
    kg = (profile.get('id') if isinstance(profile, dict) else profile) == 'kgxc' or defaults['profile']['id'] == 'kgxc'
    answers = preferences.get('answers', {})
    def explicit_answer(key):
        answer = answers.get(key, {}) if isinstance(answers, dict) else {}
        return bool(isinstance(answer, dict) and answer.get('value') == choices.get(key) and
                    answer.get('actor') and answer.get('evidence'))
    if kg and choices.get('logo') == 'off' and not explicit_answer('logo'):
        error('logo', '隐藏原版Logo的本课明确选择缺少actor/evidence，不按自报required:false免检')
    if kg and choices.get('logo_position', 'top-right') != 'top-right' and not explicit_answer('logo_position'):
        error('logo', 'Logo位置例外缺少本课明确选择的actor/evidence，仍按默认右上检查')
    metadata = _read(video_path.with_suffix('.json')) if video_path else {}
    source_range = None
    if purpose == 'pilot' and metadata.get('video_sha256') == video_sha:
        span = metadata.get('range', {})
        candidate = [span.get('firstFrame'), span.get('lastFrame')]
        if _range(candidate, duration):
            source_range = candidate

    for key in LABELS:
        requirement = requirements.get(key, defaults['requirements'][key])
        if not isinstance(requirement, dict):
            requirement = {}
        enabled = (choices.get('sound_effects') != 'off' if key == 'sfx' else
                   choices.get('flower_text') != 'off' if key == 'emphasis' else
                   kg and not (choices.get('logo') == 'off' and explicit_answer('logo')) if key == 'logo' else
                   kg if key == 'bookends' else True)
        start = len(errors)
        evidence = {}
        deferred = requirement.get('pilot_defer', value.get('deferred_features', {}).get(key, {}))
        defer_range = deferred.get('source_range') if isinstance(deferred, dict) else None
        out_of_sample = (key == 'bookends' and _range(defer_range, duration) and 0 < defer_range[0] < defer_range[1] < duration)
        if key in ['sfx', 'emphasis'] and _range(defer_range, duration):
            planned_events = (_read(_path(p, requirement.get('plan_path', 'audio/sfx-plan.json'))).get('events', [])
                              if key == 'sfx' else requirement.get('events', []))
            out_of_sample = bool(planned_events) and all(
                not (defer_range[0] <= event.get('frame', event.get('start_frame', -1)) < defer_range[1])
                for event in planned_events if isinstance(event, dict))
        if (enabled and out_of_sample and purpose == 'pilot' and isinstance(deferred, dict) and deferred.get('reason') and
                deferred.get('actor') and deferred.get('evidence') and
                deferred.get('document_sha256') in hashes and video_sha and deferred.get('video_sha256') == video_sha and
                _range(defer_range, duration) and (source_range is None or defer_range == source_range)):
            checks[key] = dict(required=enabled, ready=True, status='deferred-outside-current-pilot', evidence=deferred)
            continue
        if not enabled:
            if key == 'sfx':
                audio = _file(p, doc.get('media', {}).get('audio'))
                receipt = _read(audio.with_suffix('.json')) if audio else {}
                if audio and receipt.get('mix_sha256') == _sha(audio) and receipt.get('events', 0):
                    error(key, '已选择关闭音效，但当前文档仍绑定含提示音的实际混音')
            if key == 'emphasis' and any(event.get('node_id') in nodes for event in requirement.get('events', []) if isinstance(event, dict)):
                error(key, '已选择关闭花字，但契约仍绑定当前花字节点')
            checks[key] = dict(required=False, ready=len(errors) == start, status='explicitly-off' if key in ['sfx', 'emphasis'] else 'not-applicable')
            continue
        if key == 'sfx':
            plan_path = _file(p, requirement.get('plan_path', 'audio/sfx-plan.json'))
            plan = _read(plan_path) if plan_path else {}
            trusted = {a['id']: a for a in _native_assets()}
            frozen_assets = {a.get('id'): a for a in requirement.get('assets', []) if isinstance(a, dict)}
            events = plan.get('events', [])
            if plan.get('palette') != 'teaching-native-v1' or not events:
                error(key, '已选原库音效未落实到非空原库事件计划')
            for event in events:
                source = frozen_assets.get(event.get('assetId'), {})
                original = trusted.get(event.get('assetId'), {})
                if (not original or source.get('sha256') != original.get('sha256') or
                        not _file(p, source.get('path'), original.get('sha256')) or
                        event.get('sha256') != original.get('sha256') or
                        not _file(p, event.get('path'), original.get('sha256'))):
                    error(key, '音效事件不是冻结的所选原库素材，或实际文件已变更', dict(event=event.get('id')))
            # The selected ding is a distinct source; aliases do not create new
            # sources, and a renamed older library cannot satisfy this check.
            ding = trusted.get('focus-native', {}).get('sha256')
            if not ding or not any(e.get('sha256') == ding for e in events):
                error(key, '已选“叮”尚未用于当前课程重点或完成事件')
            for identifier in requirement.get('required_asset_ids', []):
                source = trusted.get(identifier, {})
                if not source or not any(event.get('sha256') == source.get('sha256') for event in events):
                    error(key, '契约要求的冻结音源尚未被消费：' + str(identifier))
            audio = _file(p, doc.get('media', {}).get('audio'))
            receipt = _read(audio.with_suffix('.json')) if audio else {}
            stem = _file(p, receipt.get('sfxStem'))
            applied = {row.get('id') for row in receipt.get('appliedGains', []) if isinstance(row, dict)}
            if (not audio or not plan_path or receipt.get('palette') != 'teaching-native-v1' or
                    receipt.get('mix_sha256') != _sha(audio) or receipt.get('plan_sha256') != _sha(plan_path) or
                    not events or any(e.get('id') not in applied for e in events) or not stem):
                error(key, '原库事件尚未绑定当前文档实际混音、计划哈希与音效分轨')
            elif stem:
                try:
                    with wave.open(str(stem), 'rb') as stream:
                        audible = any(any(chunk) for chunk in iter(lambda: stream.readframes(65536), b''))
                    if not audible:
                        error(key, '当前音效分轨完全静音')
                except (OSError, wave.Error, EOFError):
                    error(key, '当前音效分轨无法解码')
            review = requirement.get('review', {})
            for message in _review_errors(review, hashes, video_sha, duration):
                error(key, message)
            expected_audio = review.get('encoded_audio_sha256')
            if not expected_audio or not video_path or _audio_hash(video_path) != expected_audio:
                error(key, '缺少匹配当前编码音轨的SHA-256与实际听审观察')
            evidence = dict(plan=str(plan_path) if plan_path else None, events=len(events), encoded_audio_sha256=expected_audio)
        elif key == 'emphasis':
            events = requirement.get('events', [])
            if not isinstance(events, list) or not events:
                error(key, '花字已启用，但缺少绑定原句、用途、真实节点及阅读窗的事件')
                events = []
            for event in events:
                node = nodes.get(event.get('node_id'), {})
                span, reading = [event.get('start_frame'), event.get('end_frame')], event.get('reading_window')
                captions = ''.join(str(c.get('text', '')) for c in doc.get('captions', [])
                                   if _range(span, duration) and c.get('startFrame', 0) < span[1] and c.get('endFrame', duration) > span[0])
                if (not event.get('quote') or event['quote'] not in captions or not event.get('purpose') or
                        not node or node.get('type') not in ['text', 'path', 'rect', 'line', 'group'] or
                        not _range(span, duration) or not _range(reading, duration) or
                        not span[0] <= reading[0] < reading[1] <= span[1] or
                        not _node_range(node, span[0], span[1], duration)):
                    error(key, '花字事件未落实当前原句、对象与实际稳定阅读区间', dict(event=event.get('id')))
            for message in _review_errors(requirement.get('review'), hashes, video_sha, duration):
                error(key, message)
        elif key == 'direction':
            scenes = requirement.get('scenes', [])
            scene_ids = {s.get('id') for s in doc.get('scenes', [])}
            if source_range:
                scene_ids = {scene.get('id') for scene in doc.get('scenes', [])
                             if max(source_range[0], scene.get('sourceStartFrame', 0)) <
                             min(source_range[1], scene.get('sourceEndFrame', duration))}
            planned = {s.get('scene_id') for s in scenes if isinstance(s, dict)} if isinstance(scenes, list) else set()
            if not scene_ids or not scene_ids <= planned or purpose != 'pilot' and planned != scene_ids:
                error(key, '语义演绎须覆盖当前所有片段的起态、过程、结果，不能只登记动作数量')
            for scene in scenes if isinstance(scenes, list) else []:
                if purpose == 'pilot' and scene.get('scene_id') not in scene_ids:
                    continue
                span = [scene.get('start_frame'), scene.get('end_frame')]
                ids = scene.get('node_ids', [])
                captions = ''.join(str(c.get('text', '')) for c in doc.get('captions', []))
                if (not all(scene.get(field) for field in ['quote', 'purpose', 'before', 'process', 'after']) or
                        scene.get('quote', '') not in captions or
                        not _range(span, duration) or not ids or any(identifier not in nodes for identifier in ids)):
                    error(key, '缺少可核对的语义动作计划与当前对象', dict(scene=scene.get('scene_id')))
                elif not _directed_change(scene, nodes, duration, requirement.get('review', {})):
                    error(key, '未找到与原句和对象绑定的演绎变化或有目的阅读依据；不能只用淡入数量声明充分', dict(scene=scene.get('scene_id')))
                for message in _diagram_label_errors(scene, nodes, duration, ancestors, non_body_ids):
                    error(key, message, dict(scene=scene.get('scene_id')))
            for message in _review_errors(requirement.get('review'), hashes, video_sha, duration):
                error(key, message)
            observed = {row.get('scene_id') for row in requirement.get('review', {}).get('observations', []) if isinstance(row, dict)}
            if scene_ids - observed:
                error(key, '制作端语义动作复核未逐段给出实际观察', dict(missing_scene_ids=sorted(scene_ids - observed)))
        elif key == 'logo':
            original = _read(ROOT / 'assets/brand/logo.json').get('sha256')
            selected = requirement.get('asset', {})
            ids = requirement.get('node_ids', [])
            if selected.get('sha256') != original or not _file(p, selected.get('path'), original):
                error(key, '缺少冻结原版Logo文件与SHA-256；文字KG或人物胸标不能代替')
            if not ids:
                error(key, '缺少当前画面右上原版Logo的真实图像节点')
            for identifier in ids:
                node = nodes.get(identifier, {})
                asset = assets.get(node.get('assetId'), {})
                path = node.get('src') or asset.get('path')
                position = choices.get('logo_position', 'top-right') if explicit_answer('logo_position') else 'top-right'
                horizontal = (node.get('x', 0) >= doc.get('width', 1920) * .6 if position.endswith('right')
                              else node.get('x', 9999) <= doc.get('width', 1920) * .2)
                vertical = (node.get('y', 9999) <= doc.get('height', 1080) * .2 if position.startswith('top')
                            else node.get('y', 0) >= doc.get('height', 1080) * .6)
                if (node.get('type') != 'image' or not _file(p, path, original) or
                        position not in ['top-right', 'top-left', 'bottom-right', 'bottom-left'] or not horizontal or not vertical or
                        node.get('width', 0) <= 0 or node.get('height', 0) <= 0 or node.get('visible', True) is False):
                    error(key, 'Logo未真实绑定原图或未位于右上可见区域', dict(node=identifier))
            for message in _review_errors(requirement.get('review'), hashes, video_sha, duration):
                error(key, message)
        elif key == 'chapters':
            segments = requirement.get('segments', [])
            if not isinstance(segments, list) or not segments:
                error(key, '缺少带独立标签、节点和当前状态的分段导航；一条长进度条不能替代')
                segments = []
            ids = [segment.get('id') for segment in segments]
            if len(set(ids)) != len(ids):
                error(key, '分段导航ID重复')
            node_ids = [segment.get('node_id') for segment in segments]
            if len(set(node_ids)) != len(node_ids):
                error(key, '分段导航须绑定独立实际节点，不能全用同一长条')
            for segment in segments:
                node = nodes.get(segment.get('node_id'), {})
                span = [segment.get('start_frame'), segment.get('end_frame')]
                states = segment.get('states', [])
                label = segment.get('label')
                visible_text = ' '.join(str(n.get('text', '')) for n in _walk([node]))
                if (not segment.get('id') or not label or label not in visible_text or not _range(span, duration) or
                        not any(row.get('state') == 'current' and type(row.get('frame')) is int and span[0] <= row['frame'] < span[1]
                                for row in states if isinstance(row, dict))):
                    error(key, '导航分段缺少实际标签、有效帧范围或当前章节状态', dict(segment=segment.get('id')))
                if node and _range(span, duration) and not _has_action(node, *span):
                    error(key, '导航当前状态尚未绑定实际节点变化，状态清单不能代替画面', dict(segment=segment.get('id')))
            for message in _review_errors(requirement.get('review'), hashes, video_sha, duration):
                error(key, message)
        elif key == 'bookends':
            messages, evidence = _bookends(p, requirement, video_sha)
            for message in messages:
                error(key, message)
        checks[key] = dict(required=True, ready=len(errors) == start,
                           status='verified-evidence' if len(errors) == start else 'unverified', evidence=evidence)
    return dict(schema='course-production-inspection/1', required=True, ready=not errors,
                errors=errors, checks=checks, purpose=purpose, contract_path=FILENAME,
                document_sha256=document_digest(doc) if doc else None,
                document_file_sha256=_sha(doc_path) if doc_path else None, video_sha256=video_sha,
                next_steps=[dict(requirement=key, action=LABELS.get(key, key), messages=[e['message'] for e in errors if e['requirement'] == key])
                            for key in dict.fromkeys(e['requirement'] for e in errors)],
                scope='结构、资产哈希和当前版本证据检查；语义/美观/自然度依赖制作端实查；不代表用户确认或新增盲审')


def inspect(project, document=None, video=None, purpose='final'):
    try:
        return _inspect(project, document, video, purpose)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        return dict(required=True, ready=False, purpose=purpose, checks={},
                    errors=[dict(id='contract-invalid', requirement='contract',
                                 message='制作契约或实物证据格式无效，未放行',
                                 evidence=dict(error=str(exc)))],
                    next_steps=[dict(requirement='contract', action='修正具体无效字段后重新检查；不删除文件绕过')])
