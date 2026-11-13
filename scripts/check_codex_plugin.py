#!/usr/bin/env python3
"""Verify the installed Codex plugin through app-server, without a model turn."""
from pathlib import Path
import argparse
import json
import queue
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path); parser.add_argument('--course', type=Path); args = parser.parse_args()
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    replies = queue.Queue()
    def reader():
        for line in process.stdout:
            try: replies.put(json.loads(line))
            except ValueError: pass
    threading.Thread(target=reader, daemon=True).start()
    sequence = 0
    def rpc(method, params, timeout=45):
        nonlocal sequence
        sequence += 1; identity = sequence
        process.stdin.write(json.dumps(dict(id=identity, method=method, params=params)) + '\n'); process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            item = replies.get(timeout=max(.1, deadline - time.monotonic()))
            if item.get('id') == identity:
                if 'error' in item: raise ValueError(str(item['error']))
                return item['result']
        raise TimeoutError(method)
    try:
        rpc('initialize', dict(clientInfo=dict(name='kgxc_plugin_check', version='0.1.0'), capabilities=dict(experimentalApi=True)))
        process.stdin.write(json.dumps(dict(method='initialized')) + '\n'); process.stdin.flush()
        started = rpc('thread/start', dict(cwd=str(ROOT), approvalPolicy='never', sandbox='read-only', ephemeral=True))
        thread_id = started['thread']['id']
        status = rpc('mcpServerStatus/list', dict(threadId=thread_id, detail='toolsAndAuthOnly', limit=100))
        servers = status.get('data', status.get('servers', []))
        own = [server for server in servers if 'kgxc' in server.get('name', '')]
        if not own: raise ValueError('Codex 未发现制课 MCP；server names=' + str([server.get('name') for server in servers]))
        server = own[0]
        result = rpc('mcpServer/tool/call', dict(threadId=thread_id, server=server['name'], tool='kgxc_course_environment', arguments={}))
        if result.get('isError') or not result.get('structuredContent', {}).get('ok'):
            raise ValueError('Codex 环境工具未执行成功')
        report = dict(ok=True, server=server['name'], tool_names=sorted(server.get('tools', {}).keys()) if isinstance(server.get('tools'), dict) else server.get('tools'),
                      environment_result=result, scope='Codex 原生插件发现、MCP握手、工具发现与实际环境工具调用；没有发起模型生成')
        if args.course:
            resumed = rpc('mcpServer/tool/call', dict(threadId=thread_id, server=server['name'], tool='kgxc_course_resume', arguments=dict(course_path=str(args.course.resolve()))))
            if resumed.get('isError') or not resumed.get('structuredContent', {}).get('ok'):
                raise ValueError('Codex 未能恢复 DSH 测试课程')
            value = resumed['structuredContent']
            report['course_recovery'] = dict(course_path=value['course_path'], course_id=value['workflow']['course_id'], revision=value['workflow']['revision'], stage=value['workflow']['stage'], workbench_url=value['workbench_url'])
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__': main()
