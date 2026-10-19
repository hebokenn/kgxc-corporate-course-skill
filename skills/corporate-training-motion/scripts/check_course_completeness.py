#!/usr/bin/env python3
"""Validate declared maps, source-image inventory and closing; not visual/audio quality."""
import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

CLOSING = '本节课程到此结束，感谢大家观看'
EDGE_TYPES = {'sequence', 'handoff', 'contains', 'parallel', 'condition', 'field_link'}
RELATION_EDGES = {
    'process': {'sequence', 'condition', 'handoff'}, 'hierarchy': {'contains'},
    'handoff': {'handoff'}, 'condition': {'condition'}, 'field_linkage': {'field_link'},
}
DIAGRAM_TYPES = {'flowchart', 'swimlane', 'relationship', 'tree', 'prototype', 'comparison'}


def normalized(text):
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def closing_errors(project, segments):
    if project.get('deliverable', 'full') != 'full':
        return []
    text = normalized(''.join(s.get('text', '') for s in segments if isinstance(s, dict)))
    closing = project.get('brand', {}).get('closing', CLOSING)
    if not closing:return []
    phrase = normalized(closing)
    if not text.endswith(phrase) or text.count(phrase) != 1:
        return ['COURSE_CLOSING: 完整课末句须且仅须说一次“' + closing + '”']
    return []


def indexed(items, label, errors):
    result = {}
    if not isinstance(items, list):
        errors.append(f'{label}: 必须为数组')
        return result
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
            errors.append(f'{label}: 缺少有效ID')
        elif item['id'] in result:
            errors.append(f'{label}: 重复ID {item["id"]}')
        else:
            result[item['id']] = item
    return result


def map_errors(data, scenes):
    errors = []
    maps = indexed(data.get('maps'), 'MAPS', errors)
    boards = indexed(scenes, 'MAP_SCENES', errors)
    order = {sid: index for index, sid in enumerate(boards)}
    node_sets = {}
    edge_sets = {}
    for mid, item in maps.items():
        if item.get('diagram_type') not in DIAGRAM_TYPES or not item.get('canvas_id'):
            errors.append(f'MAP_TYPE: {mid} 缺少有效图类型或共享画布')
        nodes = indexed(item.get('nodes'), f'MAP_NODES {mid}', errors)
        if len(nodes) < 2 or any(not n.get('label') for n in nodes.values()):
            errors.append(f'MAP_NODES: {mid} 至少两个具名节点')
        node_sets[mid] = set(nodes)
        edges = item.get('edges')
        edge_sets[mid] = []
        if not isinstance(edges, list) or not edges:
            errors.append(f'MAP_EDGES: {mid} 缺少真实语义连线')
        else:
            for edge in edges:
                if (not isinstance(edge, dict) or edge.get('from') not in nodes
                        or edge.get('to') not in nodes or edge.get('type') not in EDGE_TYPES
                        or not edge.get('label')):
                    errors.append(f'MAP_EDGE: {mid} 连线端点、类型或关系说明无效')
                else:
                    edge_sets[mid].append(edge)
        overview = boards.get(item.get('overview_scene_id'), {})
        if overview.get('map_id') != mid or overview.get('view_mode') != 'overview':
            errors.append(f'MAP_OVERVIEW: {mid} 缺少真实总览分镜')
        returns = item.get('return_scene_ids')
        if not isinstance(returns, list) or not returns:
            errors.append(f'MAP_RETURN: {mid} 缺少归回分镜')
        else:
            for sid in returns:
                scene = boards.get(sid, {})
                if scene.get('map_id') != mid or scene.get('view_mode') != 'return':
                    errors.append(f'MAP_RETURN: {mid} 未绑定有效归回分镜 {sid}')
        local_positions = [order[sid] for sid, scene in boards.items()
                           if scene.get('map_id') == mid and scene.get('view_mode') == 'local']
        overview_position = order.get(item.get('overview_scene_id'), len(boards))
        return_positions = [order[sid] for sid in (returns if isinstance(returns, list) else [])
                            if sid in boards]
        if local_positions and (overview_position >= min(local_positions)
                                or not return_positions or max(return_positions) <= max(local_positions)):
            errors.append(f'MAP_ORDER: {mid} 必须先总览再讲局部，并在最后局部后归回')
    for sid, scene in boards.items():
        relation = scene.get('knowledge_relation')
        mid = scene.get('map_id')
        if not mid and scene.get('map_mode') is not True:
            continue
        if mid not in maps:
            errors.append(f'MAP_BINDING: {sid} 关系型分镜未绑定实际地图')
            continue
        unit = scene.get('unit_id')
        if not unit or scene.get('canvas_id') != maps[mid].get('canvas_id'):
            errors.append(f'MAP_CANVAS: {sid} 缺少业务单元或未使用地图共享画布')
        focus = scene.get('map_node_ids')
        if not isinstance(focus, list) or not focus or any(n not in node_sets[mid] for n in focus):
            errors.append(f'MAP_FOCUS: {sid} 缺少实际地图节点或引用未知节点')
        elif relation in RELATION_EDGES and not any(
                e['type'] in RELATION_EDGES[relation] and (e['from'] in focus or e['to'] in focus)
                for e in edge_sets[mid]):
            errors.append(f'MAP_RELATION: {sid} 焦点没有匹配知识关系的连线')
        if scene.get('view_mode') not in {'overview', 'local', 'return'}:
            errors.append(f'MAP_VIEW: {sid} 缺少全局/局部/归回状态')
    return errors


def image_errors(folder, project, data, scenes):
    folder = Path(folder).resolve()
    errors = []
    images = indexed(data.get('images'), 'SOURCE_IMAGES', errors)
    boards = indexed(scenes, 'IMAGE_SCENES', errors)
    count = project.get('source_pages')
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        return errors + ['IMAGE_PAGES: 须填写原件实际页数']
    reviews = data.get('page_reviews')
    if data.get('review_status') != 'reviewed' or not isinstance(reviews, list):
        return errors + ['IMAGE_INVENTORY: 逐页图片盘点未完成']
    seen_pages = set()
    listed = set()
    for page in reviews:
        if not isinstance(page, dict):
            errors.append('IMAGE_PAGE: 页记录必须为对象'); continue
        number = page.get('page')
        ids = page.get('image_ids')
        if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= count or number in seen_pages:
            errors.append('IMAGE_PAGE: 页号越界或重复'); continue
        seen_pages.add(number)
        if not isinstance(ids, list) or not page.get('note'):
            errors.append(f'IMAGE_PAGE: 第{number}页缺少图片清单或查看说明'); continue
        for iid in ids:
            if iid not in images or images[iid].get('source_page') != number or iid in listed:
                errors.append(f'IMAGE_PAGE: 第{number}页图片引用不符 {iid}')
            listed.add(iid)
    if seen_pages != set(range(1, count + 1)) or listed != set(images):
        errors.append('IMAGE_COVERAGE: 页或图片有遗漏，含无图/空白页均须登记')
    boundary = folder.parent if folder.name == 'project' and (folder.parent/'workspace.json').is_file() else folder
    for iid, item in images.items():
        if not item.get('source_region') or not item.get('kind'):
            errors.append(f'IMAGE_SOURCE: {iid} 缺少来源区域或图种类')
        value, decision = item.get('information_value'), item.get('decision')
        if value not in {'instructional', 'decorative', 'blank', 'duplicate'}:
            errors.append(f'IMAGE_VALUE: {iid} 未判断信息价值')
        if decision == 'exclude':
            if value not in {'decorative', 'blank', 'duplicate'} or not item.get('exclusion_reason'):
                errors.append(f'IMAGE_OMISSION: {iid} 信息图不能无依据排除')
            if value == 'duplicate' and images.get(item.get('duplicate_of'), {}).get('decision') != 'include':
                errors.append(f'IMAGE_DUPLICATE: {iid} 重复图未指向实际纳入的图')
        elif decision == 'include':
            name = item.get('asset_path', '')
            path = (folder/name).resolve()
            if (not name or Path(name).is_absolute() or not path.is_relative_to(boundary)
                    or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get('sha256')):
                errors.append(f'IMAGE_ASSET: {iid} 原图文件不存在、越界或哈希不符')
            ids = item.get('scene_ids')
            if not isinstance(ids, list) or not ids:
                errors.append(f'IMAGE_UNUSED: {iid} 未进入分镜')
            else:
                for sid in ids:
                    if iid not in boards.get(sid, {}).get('source_image_ids', []):
                        errors.append(f'IMAGE_BINDING: {iid} 与分镜{sid}不一致')
        else:
            errors.append(f'IMAGE_DECISION: {iid} 未决定纳入或排除')
    for sid, scene in boards.items():
        for iid in scene.get('source_image_ids', []):
            item = images.get(iid, {})
            if item.get('decision') != 'include' or sid not in item.get('scene_ids', []):
                errors.append(f'IMAGE_BINDING: {sid} 引用未知、未纳入或未反向绑定的图 {iid}')
    return errors


def check(folder, stage='storyboard'):
    folder = Path(folder).resolve()
    try:
        project = json.loads((folder/'project.json').read_text())
        segments = json.loads((folder/'script_segments.json').read_text())
        errors = closing_errors(project, segments)
        if stage == 'script':
            return errors
        scenes = json.loads((folder/'storyboard.json').read_text())
        errors += map_errors(json.loads((folder/'knowledge_maps.json').read_text()), scenes)
        errors += image_errors(folder, project, json.loads((folder/'source_images.json').read_text()), scenes)
        return errors
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        return ['COURSE_CONTRACT_FILE: 契约缺失或格式错误: ' + str(exc)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--stage', choices=['script', 'storyboard'], default='storyboard')
    args = parser.parse_args()
    findings = check(args.project, args.stage)
    print(json.dumps({'ok': not findings, 'scope': 'declared plan and file bindings only',
                      'visual_audio_quality': 'not machine-certified', 'errors': findings}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(findings))
