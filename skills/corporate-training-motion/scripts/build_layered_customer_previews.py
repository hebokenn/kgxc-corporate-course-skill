#!/usr/bin/env python3
"""Render customer thumbnails and a motion specimen with the real CourseActors code."""
import argparse
import base64
import hashlib
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'workbench'))
from layered_customers import PRESETS, stage
from runtime import activate, browser_options
activate()


def build(out, preview_dir=None):
    from playwright.sync_api import sync_playwright
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    project=out/'project';project.mkdir(exist_ok=True)
    marker=project/'workbench.json'
    if not marker.exists():marker.write_text('{}\n')
    nodes=[]
    for i,key in enumerate(PRESETS):
        item=stage(key,dict(sceneId='specimen',x=260+i*380,floorY=650,height=510,endFrame=90,
            keys=[dict(frame=0,values=dict(gesture=0)),dict(frame=24,values=dict(gesture=.65)),
                  dict(frame=44,values=dict(gesture=.65)),dict(frame=65,values=dict(gesture=0))],
            blinks=[[48,51,54]]),project,ROOT)
        nodes.append(item['node'])
    (out/'designs.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2)+'\n')
    runtime=ROOT/'workbench/motion/acting.js'
    html='''<!doctype html><canvas id="c" width="1280" height="720"></canvas><script src="/acting.js"></script><script>
const nodes=NODES,c=document.querySelector('canvas'),ctx=c.getContext('2d');
window.draw=(frame,selected=null)=>{ctx.clearRect(0,0,c.width,c.height);const active=selected?[nodes.find(n=>n.id===selected)]:nodes;
CourseActors.prepare(active,frame);const states={};for(const original of active){const n=selected?{...original,x:225,y:580,scaleX:1.38,scaleY:1.38}:original;
ctx.save();const g=CourseActors.motionState(n,frame);ctx.translate(g.x,g.y);ctx.scale(n.scaleX,n.scaleY);states[n.id]=CourseActors.paint(ctx,n,frame,{},new Set());ctx.restore();}
return {png:c.toDataURL(),states};};window.ready=true;
</script>'''.replace('NODES',json.dumps(nodes))
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            data=runtime.read_bytes() if self.path=='/acting.js' else html.encode()
            self.send_response(200);self.send_header('Content-Type','text/javascript' if self.path=='/acting.js' else 'text/html');self.end_headers();self.wfile.write(data)
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    frames=out/'frames';frames.mkdir(exist_ok=True);previews=Path(preview_dir) if preview_dir else out/'previews';previews.mkdir(parents=True,exist_ok=True)
    observations=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page()
            page.goto('http://127.0.0.1:'+str(server.server_port));page.wait_for_function('window.ready')
            for key in PRESETS:
                value=page.evaluate('key=>{c.width=450;c.height=620;return draw(0,key)}',key)
                (previews/(key+'.png')).write_bytes(base64.b64decode(value['png'].split(',')[1]))
            for frame in range(90):
                value=page.evaluate('f=>{c.width=1280;c.height=720;return draw(f)}',frame)
                (frames/(str(frame).zfill(3)+'.png')).write_bytes(base64.b64decode(value['png'].split(',')[1]))
                if frame in [0,24,44,65]:observations.append(dict(frame=frame,states=value['states']))
            a=page.evaluate('()=>draw(24).png');page.evaluate('()=>draw(80)');assert page.evaluate('()=>draw(24).png')==a
            browser.close()
    finally:server.shutdown();server.server_close()
    for key in PRESETS:
        before=observations[0]['states'][key];after=observations[1]['states'][key]
        assert before['hands']!=after['hands'] and before['elbows']!=after['elbows']
        assert all(row['states'][key]['maxBoneError']<1e-6 for row in observations)
        assert before['mouthOpen']==0
    video=out/'layered-customers-motion.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(frames/'%03d.png'),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(video)],check=True)
    report=dict(status='pass',scope='actual CourseActors appearance, joint motion and deterministic seeking; not course acceptance',
        renderer_sha256=hashlib.sha256(runtime.read_bytes()).hexdigest(),video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
        presets=list(PRESETS),states=observations)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],video=str(video),previews=str(previews)),ensure_ascii=False))


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('output');cli.add_argument('--preview-dir');args=cli.parse_args();build(args.output,args.preview_dir)
