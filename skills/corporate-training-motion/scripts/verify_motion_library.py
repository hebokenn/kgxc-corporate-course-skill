#!/usr/bin/env python3
"""Observe every action in the same renderer used by real course exports."""
import argparse
import base64
import hashlib
import http.server
import io
import json
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate,browser_options
activate()
from backend import Handler,Workspace,read
from motion_catalog import CATALOG
from motion_quality import preflight


def verify(course,out):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    from playwright.sync_api import sync_playwright
    p=Path(course).resolve()/'project';doc=read(p/'workbench.json');out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    assert preflight(doc)['status']=='pass',preflight(doc)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(p)
    threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_address[1]}'
    report=[];issues=[];posters=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url+'/renderer.html');page.wait_for_function('window.ready===true || window.renderError',timeout=120000)
            assert not page.evaluate('window.renderError||null'),page.evaluate('window.renderError')
            actual=page.evaluate('window.courseRenderer.native.CourseMotion.runtimeCatalog()')
            assert set(actual)==set(CATALOG),(set(CATALOG)-set(actual),set(actual)-set(CATALOG))
            for i,(kind,info) in enumerate(CATALOG.items()):
                a=i*150+30;stamps=[a+3,a+27,a+48,a+70,a+89];pictures={};calls=[]
                for frame in stamps:
                    result=page.evaluate('async f=>{const r=window.courseRenderer;const v=await r.drawFrame(f);return {png:r.canvas.toDataURL(),calls:v.motionReceipt}}',frame)
                    pictures[frame]=base64.b64decode(result['png'].split(',')[1]);calls.extend(result['calls'])
                regions=[np.asarray(Image.open(io.BytesIO(v)).convert('RGB'))[270:910,112:1808] for v in pictures.values()]
                changes=[int((np.max(np.abs(regions[i].astype(np.int16)-regions[i-1].astype(np.int16)),axis=2)>12).sum()) for i in range(1,len(regions))]
                visible=max(changes)>30
                reverse=True
                for frame in reversed(stamps):
                    raw=page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',frame)
                    reverse &= base64.b64decode(raw.split(',')[1])==pictures[frame]
                invoked=any(x['type']==kind and 0<x['progress']<1 for x in calls)
                item=dict(id=kind,title=info['title'],actualPixelsChanged=visible,maximumChangedPixels=max(changes),reverseSeekIdentical=reverse,runtimeInvoked=invoked)
                report.append(item)
                if not visible or not reverse or not invoked:issues.append(item)
                poster=Image.open(io.BytesIO(pictures[stamps[2]])).convert('RGB');poster.thumbnail((480,270));poster.save(out/(kind+'.png'));posters.append((kind,info['title'],poster))
            # Exercise actual editable text, position and image replacement.
            frame=150*list(CATALOG).index('magnify')+90
            async_draw='async ([d,f])=>{const r=window.courseRenderer;await r.load(d);await r.drawFrame(f);return r.canvas.toDataURL()}'
            original=page.evaluate(async_draw,[doc,frame]);changed=json.loads(json.dumps(doc))
            field=next(f for f in changed['fields'] if f['objectId']=='object-magnify');field['dx']=120
            moved=page.evaluate(async_draw,[changed,frame]);assert moved!=original,'位置修改未影响实际画面'
            changed=json.loads(json.dumps(doc));asset=next(a for a in changed['assets'] if a['id']=='detail');asset['path']='assets/M1-repaired.png'
            replaced=page.evaluate(async_draw,[changed,frame]);assert replaced!=original,'换图未影响实际画面'
            changed=json.loads(json.dumps(doc));field=next(f for f in changed['fields'] if f['objectId']=='object-count-up');field['text']='64'
            frame=150*list(CATALOG).index('count-up')+119
            before=page.evaluate(async_draw,[doc,frame]);after=page.evaluate(async_draw,[changed,frame]);assert before!=after,'数字改字未影响实际动画'
            browser.close()
        assert not errors,errors
    finally:server.shutdown();server.server_close()
    # A source-only label cannot pass: remove all claimed motion implementations.
    negative=json.loads(json.dumps(doc))
    from motion_quality import walk
    for n in walk(negative['sceneGraph']['nodes']):n.pop('effects',None);n.pop('motion',None)
    negative_result=preflight(negative);assert negative_result['status']=='fail'
    fontfile=ROOT/'assets/bookends/CourseTitle.otf';font=ImageFont.truetype(str(fontfile),24)
    sheet=Image.new('RGB',(1500,8*181+90),'#f4f3eb');draw=ImageDraw.Draw(sheet)
    draw.text((25,16),'48 种实际动作 · 由整课同一渲染入口生成',font=ImageFont.truetype(str(fontfile),33),fill='#183f3c')
    for i,(kind,title,im) in enumerate(posters):
        im=im.copy();im.thumbnail((245,138));x=4+i%6*250;y=80+i//6*181;sheet.paste(im,(x,y));draw.text((x+4,y+141),f'{i+1:02} {title}',font=font,fill='#183f3c')
    sheet.save(out/'48种真实动作.png')
    result=dict(status='fail' if issues else 'pass',count=len(report),actions=report,issues=issues,realEdits=dict(position=True,image=True,text=True),negativeControlRejected=negative_result['status']=='fail',scope='real canvas pixels, API calls and deterministic seeks; not whole-course aesthetic approval')
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],count=len(report),issues=issues),ensure_ascii=False))
    return not issues


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('course',type=Path);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    raise SystemExit(0 if verify(a.course,a.out) else 1)
