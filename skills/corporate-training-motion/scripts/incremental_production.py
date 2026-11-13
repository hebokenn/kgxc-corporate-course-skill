#!/usr/bin/env python3
"""Plan scoped reuse from a declared dependency graph and actual bytes; never mutate a course."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


SCHEMA = 'kgxc-incremental-production/1'
LAYERS = {'narration', 'timing', 'body', 'captions', 'emphasis', 'sfx', 'mix', 'package'}
HASH = re.compile(r'[0-9a-f]{64}\Z')


def digest(file):
    """Reject files modified in the middle of a read."""
    path = Path(file)
    def version():
        st = path.stat()
        return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns
    before = version()
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(data)
    if version() != before:
        raise ValueError(f'输入正在变化，未生成复用计划：{path.name}')
    return hasher.hexdigest()


def project_root(course):
    project = (Path(course).resolve() / 'project').resolve(strict=True)
    if not project.is_dir() or project.parent != Path(course).resolve():
        raise ValueError('课程 project 目录不存在或不在本课程内')
    return project


def local(project, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('依赖须为非空 project 相对路径')
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name:
        raise ValueError(f'无效的项目相对路径：{name}')
    path = project / relative
    if path.resolve() != path or not path.is_relative_to(project) or path == project:
        raise ValueError(f'依赖不能跨课或经过符号链接：{name}')
    return path


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'JSON 字段重复：{key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_pairs)


def order(graph):
    if not isinstance(graph, dict) or not graph:
        raise ValueError('复用清单须含至少一个产物')
    done, pending, result = set(), set(), []
    def visit(key):
        if key in pending:
            raise ValueError(f'依赖循环：{key}')
        if key not in graph:
            raise ValueError(f'未登记的上游：{key}')
        if key in done:
            return
        pending.add(key)
        for dep in graph[key]['dependsOn']:
            visit(dep)
        pending.remove(key)
        done.add(key)
        result.append(key)
    for key in graph:
        visit(key)
    return result


def validate_receipt(project, receipt):
    if not isinstance(receipt, dict) or receipt.get('schema') != SCHEMA or receipt.get('project') != str(project):
        raise ValueError('快照不是当前课程的增量生产快照')
    nodes = receipt.get('nodes')
    if not isinstance(nodes, dict):
        raise ValueError('快照缺少产物依赖图')
    outputs = set()
    for key, node in nodes.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(node, dict):
            raise ValueError('产物 ID 或结构无效')
        if node.get('layer') not in LAYERS:
            raise ValueError(f'未知的制作层：{key}')
        deps = node.get('dependsOn')
        if not isinstance(deps, list) or any(not isinstance(dep, str) or not dep for dep in deps) or len(set(deps)) != len(deps):
            raise ValueError(f'无效的上游列表：{key}')
        inputs = node.get('inputs')
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError(f'缺少实际输入字节：{key}')
        for name, sha in inputs.items():
            local(project, name)
            if not isinstance(sha, str) or not HASH.fullmatch(sha):
                raise ValueError(f'无效的输入哈希：{key}')
        output = node.get('output')
        local(project, output)
        if output in outputs:
            raise ValueError(f'同一文件不能由两个产物写入：{output}')
        outputs.add(output)
        proof = node.get('outputSha256')
        if proof is not None and (not isinstance(proof, str) or not HASH.fullmatch(proof)):
            raise ValueError(f'无效的产物哈希：{key}')
    for key, node in nodes.items():
        if outputs.intersection(node['inputs']):
            raise ValueError(f'上游生成文件必须使用 dependsOn 声明：{key}')
    return order(nodes)


def snapshot(course, spec):
    project = project_root(course)
    if not isinstance(spec, dict) or spec.get('schema') != SCHEMA or not isinstance(spec.get('nodes'), dict):
        raise ValueError(f'请使用 {SCHEMA} 依赖清单')
    nodes = {}
    file_hashes = {}
    def hash_file(name):
        if name not in file_hashes:
            file_hashes[name] = digest(local(project, name))
        return file_hashes[name]
    for key, node in spec['nodes'].items():
        if not isinstance(node, dict):
            raise ValueError(f'产物节点结构无效：{key}')
        inputs = node.get('inputs')
        if not isinstance(inputs, list) or any(not isinstance(name, str) for name in inputs) or len(set(inputs)) != len(inputs):
            raise ValueError(f'inputs 须为不重复的实际文件路径列表：{key}')
        output = local(project, node.get('output'))
        if output.exists() and not output.is_file():
            raise ValueError(f'产物不是文件：{key}')
        nodes[key] = dict(layer=node.get('layer'), dependsOn=node.get('dependsOn', []),
                          inputs={name: hash_file(name) for name in inputs},
                          output=node['output'],
                          outputSha256=hash_file(node['output']) if output.is_file() else None)
    result = dict(schema=SCHEMA, project=str(project), nodes=nodes)
    validate_receipt(project, result)
    return result


def compare(course, previous, current):
    project = project_root(course)
    validate_receipt(project, previous)
    steps = validate_receipt(project, current)
    # A stored plan cannot grant reuse if files changed after it was captured.
    actual = snapshot(course, dict(schema=SCHEMA, nodes={
        key: dict(node, inputs=list(node['inputs'])) for key, node in current['nodes'].items()
    }))
    if actual != current:
        raise ValueError('当前快照已过期；先重新读取实际输入和产物')
    previous_nodes, current_nodes = previous['nodes'], current['nodes']
    decisions = {}
    for key in steps:
        before, now = previous_nodes.get(key), current_nodes[key]
        invalid_parents = [dep for dep in now['dependsOn'] if decisions[dep]['action'] == 'rebuild']
        reasons = []
        if before is None:
            reasons.append('no_previous_node')
        else:
            if any(before[k] != now[k] for k in ['layer', 'dependsOn', 'output']):
                reasons.append('dependency_definition_changed')
            if before['inputs'] != now['inputs']:
                reasons.append('input_bytes_or_paths_changed')
            if before['outputSha256'] is None or before['outputSha256'] != now['outputSha256']:
                reasons.append('previous_output_missing_or_bytes_changed')
        if invalid_parents:
            reasons.append('upstream_changed')
        decisions[key] = dict(action='rebuild' if reasons else 'reuse',
                              reasons=reasons, upstream=invalid_parents)
    return dict(schema=SCHEMA, project=str(project), decisions=decisions,
                removed=sorted(previous_nodes.keys() - current_nodes.keys()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('snapshot')
    capture.add_argument('course', type=Path)
    capture.add_argument('--spec', type=Path, required=True)
    plan = sub.add_parser('compare')
    plan.add_argument('course', type=Path)
    plan.add_argument('--previous', type=Path, required=True)
    plan.add_argument('--current', type=Path, required=True)
    args = parser.parse_args()
    try:
        value = (snapshot(args.course, read_json(args.spec)) if args.command == 'snapshot'
                 else compare(args.course, read_json(args.previous), read_json(args.current)))
    except (OSError, ValueError, TypeError, RecursionError) as error:
        print(f'无法安全计划复用：{error}', file=sys.stderr)
        return 1
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
