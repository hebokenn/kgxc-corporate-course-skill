#!/usr/bin/env python3
"""Verify a new course's editable document, renderer and bound export; no approvals."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from backend import Workspace, Handler, read, validate, digest, atomic, safe, duration
from authoring import native_fingerprint
from runtime import activate, tools, browser_options
activate()


def required(config):
    version=config.get('owning_skill','').partition('@')[2]
    try:new_course=tuple(int(v) for v in version.split('.'))>=(3,2,0)
    except ValueError:new_course=False
    return new_course or config.get('workbench',{}).get('required',False)


def check(project, require_runtime=False, video=None):
    p=Path(project).resolve();errors=[]
    if (p/'project/workbench.json').exists():p=p/'project'
    try:
        d=read(p/'workbench.json');validate(d,p)
        if d.get('status')=='draft' or not d['scenes'] or (not d['captions'] and not d.get('cuts')):errors.append('课程工作台仍是草稿，缺少实际场景或字幕')
        if not d['media'].get('audio'):errors.append('工作台未绑定实际配音')
        if not (p/'native/index.html').is_file():errors.append('工作台缺少实际渲染入口')
        cfg=read(p/'project.json') if (p/'project.json').exists() else {}
        if required(cfg) and not cfg.get('workbench',{}).get('required'):errors.append('新课不得关闭默认工作台契约')
        boards=read(p/'storyboard.json') if (p/'storyboard.json').exists() else []
        planned={s['id'] for s in boards if s.get('duration_sec')}
        actual={s['id'] for s in d['scenes']}
        if planned and planned!=actual:errors.append('分镜与工作台场景ID不一致')
        for name,key in [('intro','intro_video'),('outro','outro_video')]:
            expected=cfg.get('brand',{}).get(key)
            if expected and (not d['media'].get(name) or digest(safe(p,expected))!=digest(safe(p,d['media'][name]))):errors.append('工作台未保留已指定品牌'+name)
        if require_runtime:
            proof=read(p/'qa/workbench-runtime.json')
            if proof.get('status')!='pass' or proof.get('document_sha256')!=digest(p/'workbench.json') or proof.get('native_sha256')!=native_fingerprint(p):errors.append('工作台运行验证缺失或已过期，请重新执行 --runtime')
            if set(proof.get('scene_ids',[]))!=actual:errors.append('运行验证没有覆盖所有场景')
            if proof.get('seek_deterministic') is not True:errors.append('缺少正反向定位验证')
            receipt=proof.get('binding_receipt') or {}
            for key in ['fields','assets']:
                if set(receipt.get(key,[]))!={v['id'] for v in d[key]}:errors.append('运行验证未绑定全部'+key)
        if video:
            v=Path(video);meta=read(v.with_suffix('.json'))
            if meta.get('document_sha256')!=digest(p/'workbench.json') or meta.get('video_sha256')!=digest(v) or meta.get('native_sha256')!=native_fingerprint(p):errors.append('成片与当前工作台数据或源码未绑定')
            from continuity_pacing import export_errors
            errors.extend(export_errors(d,p,v,meta))
    except Exception as e:errors.append(str(e))
    return dict(ok=not errors,errors=errors,scope='editable contract and current renderer evidence; no content or listening approval')


def runtime(project):
    import http.server
    from playwright.sync_api import sync_playwright
    p=Path(project).resolve();p=p if (p/'workbench.json').exists() else p/'project'
    result=check(p)
    if not result['ok']:return result
    d=read(p/'workbench.json');before=native_fingerprint(p);document_hash=digest(p/'workbench.json')
    http.server.ThreadingHTTPServer.request_queue_size=128
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(p)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080))
            for attempt in range(3):
                page.goto(f'http://127.0.0.1:{server.server_address[1]}/renderer.html')
                page.wait_for_function('window.ready===true || window.renderError',timeout=120000)
                if page.evaluate('window.ready'):break
            if page.evaluate('window.renderError'):raise ValueError(page.evaluate('window.renderError'))
            receipt=page.evaluate('window.courseRenderer.bindingReceipt')
            for key in ['fields','assets']:
                if set(receipt[key])!={v['id'] for v in d[key]}:raise ValueError('画面桥接未绑定全部'+key)
            frames=sorted({s['sourceStartFrame']+min(15,(s['sourceEndFrame']-s['sourceStartFrame'])//2) for s in d['scenes']})
            # Holds map authored source frames onto the current editable timeline.
            from backend import display_frame
            frames=[min(duration(d)-1,display_frame(f,d['holds'],d.get('cuts',[]))) for f in frames]
            hashes={};images={}
            for f in frames:
                png=page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',f)
                hashes[f]=hashlib.sha256(png.encode()).hexdigest();images[f]=png
            for f in reversed(frames):
                png=page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',f)
                if hashlib.sha256(png.encode()).hexdigest()!=hashes[f]:
                    import base64
                    debug=p/'work/workbench/seek-difference';debug.mkdir(parents=True,exist_ok=True)
                    (debug/'before.png').write_bytes(base64.b64decode(images[f].split(',')[1]));(debug/'after.png').write_bytes(base64.b64decode(png.split(',')[1]))
                    raise ValueError('双向定位画面不一致 frame '+str(f))
            browser.close()
        if before!=native_fingerprint(p) or document_hash!=digest(p/'workbench.json'):raise ValueError('验证中工程已改变，请重试')
        proof=dict(status='pass',document_sha256=document_hash,native_sha256=before,scene_ids=[s['id'] for s in d['scenes']],binding_receipt=receipt,seek_deterministic=True,frames=frames)
        atomic(p/'qa/workbench-runtime.json',proof)
        return dict(ok=True,errors=[],proof=proof)
    except Exception as e:return dict(ok=False,errors=[str(e)])
    finally:server.shutdown();server.server_close()


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);ap.add_argument('--runtime',action='store_true');ap.add_argument('--require-runtime',action='store_true');ap.add_argument('--video',type=Path);a=ap.parse_args()
    if a.runtime:
        interpreter=tools().get('python')
        interpreter=os.environ.get('COURSE_PYTHON',interpreter)
        if interpreter and os.path.abspath(sys.executable)!=os.path.abspath(interpreter):os.execv(interpreter,[interpreter,str(Path(__file__).resolve()),*sys.argv[1:]])
    result=runtime(a.project) if a.runtime else check(a.project,a.require_runtime,a.video)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(not result['ok'])
