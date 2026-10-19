#!/usr/bin/env python3
"""Create a real voiced KGXC technical sample; optionally verify full MP4 export."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import threading
import time
import http.server

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate
activate()
from scaffold import create
from authoring import configure
from backend import Workspace, Handler, atomic, duration


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    create(a.destination);root=a.destination.resolve();project=root/'project';example=ROOT/'examples/quickstart'
    for name in ['assets','audio']:shutil.copytree(example/name,project/name,dirs_exist_ok=True)
    shutil.copy2(example/'course-composition.json',project/'source/course-composition.json');shutil.copy2(example/'narration.txt',root/'inputs/技术样例口播.txt')
    cfg=json.loads((project/'project.json').read_text());cfg['deliverable']='pilot';atomic(project/'project.json',cfg)
    doc=configure(root,project/'source/course-composition.json')
    print('已创建酷果星创收货核对技术样例：真实预生成Aiden录音、3个场景、可编辑字幕和图片。不是完整课程业务验收。')
    if a.verify:
        http.server.ThreadingHTTPServer.request_queue_size=128
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(root)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            job=server.workspace.start_export(doc['revision'],0,duration(doc)/30,'http://127.0.0.1:'+str(server.server_address[1]));until=time.monotonic()+300
            while job['status'] not in ['complete','failed'] and time.monotonic()<until:time.sleep(.2)
            if job['status']!='complete':raise ValueError(job.get('error','样例导出超时'))
            atomic(project/'qa/installation-example.json',job);print('技术样例完整导出检查通过：'+job['video'])
        finally:server.shutdown();server.server_close()
    print('打开编辑：kgxc-course serve '+str(root))


if __name__=='__main__':main()
