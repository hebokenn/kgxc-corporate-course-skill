"""Render the exact workbench composition and independently decode its output."""
import argparse
import base64
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from runtime import activate, browser_options
activate()


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--audio',type=Path,required=True);p.add_argument('--first',type=int,required=True);p.add_argument('--last',type=int,required=True);p.add_argument('--fps',type=int,required=True)
    a=p.parse_args();output=a.directory/'video.mp4';count=a.last-a.first
    args=['ffmpeg','-v','error','-y','-f','image2pipe','-framerate',str(a.fps),'-c:v','mjpeg','-i','-',
          '-ss',str(a.first/a.fps),'-i',str(a.audio),'-map','0:v:0','-map','1:a:0',
          '-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p',
          '-vf','scale=in_range=full:out_range=limited,format=yuv420p','-color_range','tv',
          '-frames:v',str(count),'-c:a','aac','-b:a','192k','-ar','48000','-af','apad',
          '-t',str(count/a.fps),'-movflags','+faststart',str(output)]
    metrics={};captured=0;motion_calls={}
    document=json.loads((a.directory/'document.json').read_text())
    with sync_playwright() as pw, (a.directory/'encoder.log').open('w') as log:
        browser=pw.chromium.launch(headless=True,**browser_options())
        page=browser.new_page(viewport=dict(width=1920,height=1080));errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' and '404' not in message.text else None)
        page.on('requestfailed',lambda request:errors.append(request.url+' '+str(request.failure)))
        page.on('response',lambda response:errors.append(str(response.status)+' '+response.url) if response.status>=400 and not response.url.endswith('favicon.ico') else None)
        for attempt in range(3):
            errors.clear()
            page.goto(a.url,wait_until='load');page.wait_for_function('window.ready === true || window.renderError',timeout=120000)
            if page.evaluate('window.ready'):break
        if page.evaluate('window.renderError'):raise ValueError(page.evaluate('window.renderError')+'; '+ '; '.join(errors))
        receipt=page.evaluate('window.courseRenderer.bindingReceipt')
        samples=sorted(set([a.first,(a.first+a.last)//2,a.last-1]));fingerprints={}
        for f in samples+list(reversed(samples)):
            png=page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',f)
            import hashlib
            fingerprint=hashlib.sha256(png.encode()).hexdigest()
            if f in fingerprints and fingerprints[f]!=fingerprint:raise ValueError('正反向定位画面不一致')
            fingerprints[f]=fingerprint
        encoder=subprocess.Popen(args,stdin=subprocess.PIPE,stderr=log)
        last_key=None;buffer=None
        try:
            for f in range(a.first,a.last):
                data=page.evaluate('''async ({frame,old})=>{const r=window.courseRenderer,key=r.key(frame);if(key===old)return {key};const result=await r.drawFrame(frame);return {...result,jpeg:r.canvas.toDataURL('image/jpeg',.96).split(',')[1]}}''',dict(frame=f,old=last_key))
                if data.get('jpeg'):
                    buffer=base64.b64decode(data['jpeg']);captured+=1
                    if data.get('caption'):metrics[data['caption']['id']]=data['caption']
                for call in data.get('motionReceipt',[]):
                    if 0<call.get('progress',0)<1 and call.get('role')!='decoration':
                        key=(call['nodeId'],call['type']);source_f=call.get('frame',data.get('sourceFrame',f))
                        item=motion_calls.setdefault(key,dict(nodeId=call['nodeId'],type=call['type'],firstFrame=source_f,lastFrame=source_f,sampledFrames=0))
                        item['lastFrame']=source_f;item['sampledFrames']+=1
                last_key=data['key'];encoder.stdin.write(buffer)
                if (f-a.first)%15==0:
                    path=a.directory/'progress.json';tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(dict(progress=(f-a.first+1)/count)));tmp.replace(path)
            encoder.stdin.close()
            if encoder.wait()!=0:raise ValueError('视频编码失败：'+(a.directory/'encoder.log').read_text()[-1200:])
            if errors:raise ValueError('; '.join(errors))
        except Exception:
            encoder.kill();encoder.wait();raise
        finally:browser.close()
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'],video['pix_fmt'])==(1920,1080,'yuv420p'), str({k:video.get(k) for k in ['width','height','pix_fmt','color_range']})
    assert int(video['nb_frames'])==count
    assert abs(float(probe['format']['duration'])-count/a.fps)<.09
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)
    from motion_quality import audit_encoded
    motion_audit=audit_encoded(output,document,a.first,a.last)
    motion_audit['runtimeCalls']=list(motion_calls.values())
    if document.get('motionPolicy',{}).get('required'):
        from timeline import segments
        retained=[]
        for span in segments(dict(document,holds=document.get('holds',[]))):
            x=max(a.first,span['startFrame']);z=min(a.last,span['endFrame'])
            if x<z and span['kind']=='source':retained.append((span['sourceFrame']+x-span['startFrame'],span['sourceFrame']+z-span['startFrame']))
        for beat in document.get('motionPlan',{}).get('beats',[]):
            if beat.get('kind','action')!='action' or not any(max(x,beat['startFrame'])<min(z,beat['endFrame']) for x,z in retained):continue
            if not any(item['nodeId'] in beat.get('objectIds',[]) and item['firstFrame']<beat['endFrame'] and item['lastFrame']>=beat['startFrame'] for item in motion_calls.values()):
                motion_audit.setdefault('failures',[]).append('没有实际运行回执 '+beat['id']);motion_audit['status']='fail'
    (a.directory/'motion-audit.json').write_text(json.dumps(motion_audit,ensure_ascii=False,indent=2))
    if motion_audit['status'] in ['fail','review-required']:
        raise ValueError('编码成片动效未通过：'+json.dumps(dict(failures=motion_audit.get('failures',[]),unresolved=motion_audit.get('unresolvedStaticRuns',[])),ensure_ascii=False)+'；候选和证据保留在本次导出目录，未登记为完成')
    report=dict(frames=count,capturedFrames=captured,fps=a.fps,duration=float(probe['format']['duration']),
                width=video['width'],height=video['height'],pixelFormat=video['pix_fmt'],colorRange=video.get('color_range'),audioCodec=audio['codec_name'],fullDecode='pass',
                captionMetrics=list(metrics.values()),bindingReceipt=receipt,seekDeterministic=True,motionAudit=motion_audit,renderer='same renderer.html and immutable document snapshot as preview')
    (a.directory/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
