"""Render the exact workbench composition and independently decode its output."""
import argparse
import base64
import json
import subprocess
import hashlib
import math
from fractions import Fraction
from pathlib import Path
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from runtime import activate, browser_options
activate()

def canvas_encode_args(fps,count,target):
    """One encoding path for bounded seam samples and the actual export."""
    return ['ffmpeg','-v','error','-y','-f','image2pipe','-framerate',str(fps),'-c:v','mjpeg','-i','-',
            '-map','0:v:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-pix_fmt','yuv420p',
            '-vf','scale=in_range=full:out_range=limited,format=yuv420p','-color_range','tv',
            '-frames:v',str(count),'-movflags','+faststart',str(target)]


def packaging_windows(document):
    """Find actual output transitions after cuts and holds, without scanning all frames."""
    from timeline import segments
    intro,body_end=document['introFrames'],document['bodyEndFrame']
    def kind(frame):
        return 'intro' if frame<intro else 'native' if frame<body_end else 'outro'
    spans=[];previous=None
    for span in segments(document):
        first,last=span['startFrame'],span['endFrame']
        source=span['sourceFrame']
        splits=[first,last]
        if span['kind']=='source':
            splits.extend(first+edge-source for edge in {intro,body_end} if source<edge<source+last-first)
        splits.sort()
        for start,end in zip(splits,splits[1:]):
            tag=kind(source+(start-first if span['kind']=='source' else 0))
            if spans and previous==tag:
                spans[-1]['end']=end
            else:
                spans.append(dict(start=start,end=end,kind=tag));previous=tag
    if intro>0 or body_end<document['sourceDurationFrames']:
        expected={'native'} | ({'intro'} if intro>0 else set()) | ({'outro'} if body_end<document['sourceDurationFrames'] else set())
        missing=expected-{span['kind'] for span in spans}
        if missing:raise ValueError('SEAM_PREFLIGHT: 当前时间轴已缺少预定包装或正文：'+', '.join(sorted(missing)))
    return [dict(first=max(left['start'],left['end']-3),last=min(right['end'],right['start']+3),
                 edge=right['start'],left=left['kind'],right=right['kind']) for left,right in zip(spans,spans[1:])]


def seam_preflight(page,directory,document,audio,fps):
    """Encode and independently decode the real A/V either side of each retained seam."""
    from timeline import source_frame
    windows=packaging_windows(document);reports=[]
    for window in windows:
        first,last,edge=window['first'],window['last'],window['edge'];count=last-first
        # The clips are diagnostics, never user-facing sample or acceptance artifacts.
        work=directory/f'seam-{edge}';work.mkdir()
        clip=work/'clip.mp4';video_only=work/'video-only.mp4'
        captured=[]
        for frame in range(first,last):
            result=page.evaluate("""async ({frame})=>{
              let timer;
              try {
                const r=window.courseRenderer;
                const result=await Promise.race([r.drawFrame(frame),new Promise((_,reject)=>{
                  timer=setTimeout(()=>reject(Error('接缝试拼画面定位超时')),12000);
                })]);
                return {kind:result.kind,source:result.sourceFrame,jpeg:r.canvas.toDataURL('image/jpeg',.96).split(',')[1]};
              } finally {clearTimeout(timer);}
            }""",dict(frame=frame))
            if result['kind']!=window['left' if frame<edge else 'right'] or result['source']!=source_frame(frame,document['holds'],document.get('cuts',[])):
                raise ValueError(f'SEAM_PREFLIGHT: {edge} 实际画面段落与时间轴不一致')
            captured.append(dict(frame=frame,source_frame=result['source'],kind=result['kind'],
                                 jpeg=base64.b64decode(result['jpeg'],validate=True)))
        subprocess.run(canvas_encode_args(fps,count,video_only),input=b''.join(x['jpeg'] for x in captured),check=True,timeout=20)
        clock=Fraction(str(fps))
        start_sample=round(Fraction(first)*48000/clock)
        end_sample=round(Fraction(last)*48000/clock)
        mux=complete_audio_and_mux(video_only,audio,clip,work,document,first,last,fps,timeout=20)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(clip)],timeout=15))
        video=next((s for s in probe['streams'] if s.get('codec_type')=='video'),{})
        sound=next((s for s in probe['streams'] if s.get('codec_type')=='audio'),{})
        if (video.get('width'),video.get('height'),video.get('pix_fmt'),video.get('codec_name'))!=(1920,1080,'yuv420p','h264') or (
                int(video.get('nb_frames',0))!=count or abs(float(Fraction(video.get('avg_frame_rate','0/1')))-fps)>.001 or
                sound.get('codec_name')!='aac' or sound.get('sample_rate')!='48000' or
                abs(float(sound.get('duration',0))-(end_sample-start_sample)/48000)>.025):
            raise ValueError(f'SEAM_PREFLIGHT: {edge} 接缝试拼的画面、帧数或音轨长度不正确')
        subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(clip),'-f','null','-'],check=True,timeout=20)
        reports.append(dict(window,frames=[{k:v for k,v in f.items() if k!='jpeg'} for f in captured],
                            audio_start_sample=start_sample,audio_end_sample=end_sample,clip=str(clip.relative_to(directory)),
                            verified_aac_packets=mux['copied_aac_packets'],
                            sha256=hashlib.sha256(clip.read_bytes()).hexdigest()))
        video_only.unlink()
    report=dict(status='pass' if reports else 'not-applicable',seams=reports,scope='actual-canvas-encoder-and-audio-mux',subjective_listening=False)
    return report


def complete_audio_and_mux(video_only,audio,output,directory,document,first,last,fps,*,timeout=None):
    """Finish AAC independently, preserve every encoded packet, embed one chapter clock."""
    from timeline import duration
    full=first==0 and last==duration(document)
    complete=Path(directory)/'audio-complete.m4a'
    filters=['aresample=48000']
    if not full:
        filters.append('atrim=start_sample=%d:end_sample=%d'%(round(first/fps*48000),round(last/fps*48000)))
        filters.append('asetpts=PTS-STARTPTS')
    audio_argv=['ffmpeg','-v','error','-y','-i',str(audio),'-map','0:a:0','-vn','-af',','.join(filters),
                    '-c:a','aac','-b:a','192k','-ar','48000',str(complete)]
    subprocess.run(audio_argv,check=True,timeout=timeout)
    args=['ffmpeg','-v','error','-y','-i',str(video_only),'-i',str(complete)]
    table=document.get('chapterTable')
    if table:
        from chapter_table import canonical_table
        if table!=canonical_table(document,table):raise ValueError('CHAPTER_TABLE_STALE: current rendered table differs')
        rate=Fraction(str(fps));lines=[';FFMETADATA1']
        for row in table:
            start=max(first,row['display_start']);end=min(last,row['display_end'])
            if start>=end:continue
            title=str(row['label']).replace('\\','\\\\').replace('\n',' ').replace('=','\\=').replace(';','\\;').replace('#','\\#')
            lines+=['[CHAPTER]',f'TIMEBASE={rate.denominator}/{rate.numerator}',f'START={start-first}',f'END={end-first}','title='+title]
        metadata=Path(directory)/'chapters.ffmetadata';metadata.write_text('\n'.join(lines)+'\n')
        args+=['-f','ffmetadata','-i',str(metadata),'-map_metadata','2','-map_chapters','2']
    args+=['-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(output)]
    subprocess.run(args,check=True,timeout=timeout)
    def packets(path):
        return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=data_hash,pts_time,duration_time','-of','json',str(path)],timeout=timeout))['packets']
    before,after=packets(complete),packets(output)
    if not before or before!=after:raise ValueError('AAC_PAYLOAD_MISMATCH: worker final mux lost/reordered audio packets or timestamps')
    return dict(method='independent-complete-AAC-then-packet-preserving-remux',audio_complete_path=str(complete),
                audio_complete_sha256=hashlib.sha256(complete.read_bytes()).hexdigest(),audio_source_sha256=hashlib.sha256(Path(audio).read_bytes()).hexdigest(),
                copied_aac_packets=len(after),all_packets_and_timestamps_equal=True,full_source_audio=full,subjective_listening=False,
                audio_encode_argv=audio_argv,mux_argv=args)


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--audio',type=Path,required=True);p.add_argument('--first',type=int,required=True);p.add_argument('--last',type=int,required=True);p.add_argument('--fps',type=float,required=True)
    p.add_argument('--project',type=Path);p.add_argument('--seam-preflight',action='store_true')
    a=p.parse_args();output=a.directory/'video.mp4';count=a.last-a.first
    if not math.isfinite(a.fps) or not 1<=a.fps<=120 or count<=0:raise ValueError('Invalid actual frame clock')
    video_only=a.directory/'video-only.mp4'
    args=canvas_encode_args(a.fps,count,video_only)
    metrics={};captured=0;motion_calls={};layout_checks={};layout_frames=0
    document=json.loads((a.directory/'document.json').read_text())
    seam_report=dict(status='not-requested',seams=[])
    from reading_pacing import RuntimeAudit
    reading_audit=RuntimeAudit(document,a.first,a.last)
    from motion_evidence import requests as proof_requests,verify as verify_objects
    requests=proof_requests(document,a.first,a.last)if document.get('motionPolicy',{}).get('stateProofRequired')else[]
    requested={};captures={};proof_dir=a.directory/'object-proof';proof_dir.mkdir(exist_ok=True)
    for request in requests:
        for phase in request['frames']:requested.setdefault(phase['display'],[]).append((request,phase))
    with sync_playwright() as pw, (a.directory/'encoder.log').open('w') as log:
        browser=pw.chromium.launch(headless=True,**browser_options())
        page=browser.new_page(viewport=dict(width=1920,height=1080));errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' and '404' not in message.text else None)
        # Chromium cancels obsolete media range requests when deterministic frame
        # seeking jumps between bookends. A loaded video's intentional seek abort
        # is harmless; renderer seek/onerror and final decode still check media.
        page.on('requestfailed',lambda request:errors.append(request.url+' '+str(request.failure))
                if not (request.resource_type=='media' and request.failure=='net::ERR_ABORTED') else None)
        page.on('response',lambda response:errors.append(str(response.status)+' '+response.url) if response.status>=400 and not response.url.endswith('favicon.ico') else None)
        for attempt in range(3):
            errors.clear()
            page.goto(a.url,wait_until='load');page.wait_for_function('window.ready === true || window.renderError',timeout=120000)
            if page.evaluate('window.ready'):break
        if page.evaluate('window.renderError'):raise ValueError(page.evaluate('window.renderError')+'; '+ '; '.join(errors))
        receipt=page.evaluate('window.courseRenderer.bindingReceipt')
        if a.seam_preflight:
            try:
                seam_report=seam_preflight(page,a.directory,document,a.audio,a.fps)
                if errors:raise ValueError('; '.join(errors))
            except (ValueError,RuntimeError,OSError,subprocess.SubprocessError,PlaywrightError) as error:
                seam_report=dict(status='failed',error=str(error))
                raise ValueError('接缝试拼未通过；未开始正式渲染：'+str(error)) from error
            finally:
                seam_receipt=a.directory/'seam-preflight.json'
                temporary=seam_receipt.with_suffix('.pending')
                temporary.write_text(json.dumps(seam_report,ensure_ascii=False,indent=2))
                temporary.replace(seam_receipt)
        samples=sorted(set([a.first,(a.first+a.last)//2,a.last-1]));fingerprints={}
        for f in samples+list(reversed(samples)):
            png=page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',f)
            import hashlib
            fingerprint=hashlib.sha256(png.encode()).hexdigest()
            if f in fingerprints and fingerprints[f]!=fingerprint:raise ValueError('正反向定位画面不一致')
            fingerprints[f]=fingerprint
        encoder=subprocess.Popen(args,stdin=subprocess.PIPE,stderr=log)
        last_key=None;buffer=None;preview_warning=False
        try:
            for f in range(a.first,a.last):
                data=page.evaluate('''async ({frame,old})=>{const r=window.courseRenderer,key=r.key(frame);if(key===old)return {key};const result=await r.drawFrame(frame);return {...result,jpeg:r.canvas.toDataURL('image/jpeg',.96).split(',')[1]}}''',dict(frame=f,old=last_key))
                if f in requested:
                    for request,phase in requested[f]:
                        proof=page.evaluate('''async ({frame,ids})=>{const r=window.courseRenderer,b=r.native.courseWorkbench;if(typeof b.objectReceipt!=='function'||typeof b.isolate!=='function')throw Error('当前引擎缺少对象隔离与状态回执');await r.drawFrame(frame);const states=b.objectReceipt(),base=r.canvas.toDataURL('image/png').split(',')[1];let hidden;try{b.isolate(ids);await r.drawFrame(frame);hidden=r.canvas.toDataURL('image/png').split(',')[1]}finally{b.isolate([]);await r.drawFrame(frame)}return {states,base,hidden}}''',dict(frame=f,ids=request['objects']))
                        paths={}
                        for kind in ['base','hidden']:
                            file=proof_dir/(str(len(captures))+'-'+kind+'.png');file.write_bytes(base64.b64decode(proof[kind]));paths[kind]=str(file)
                        captures[(request['id'],phase['source'])]=dict(states=proof['states'],**paths)
                if document.get('readingPolicy',{}).get('required'):
                    if 'readingReceipt'not in data:
                        data.update(page.evaluate('async f=>await window.courseRenderer.drawFrame(f)',f))
                    reading_audit.consume(f,data.get('sourceFrame',f),data.get('readingReceipt',[]))
                if data.get('jpeg'):
                    buffer=base64.b64decode(data['jpeg']);captured+=1
                    if data.get('caption'):metrics[data['caption']['id']]=data['caption']
                    if data.get('layoutReceipt'):layout_frames+=1
                    for rule in data.get('layoutReceipt',[]):
                        key=(rule['objectId'],rule['rule']);item=layout_checks.setdefault(key,dict(objectId=rule['objectId'],rule=rule['rule'],checkedStates=0,firstFrame=f,lastFrame=f));item['checkedStates']+=1;item['lastFrame']=f
                for call in data.get('motionReceipt',[]):
                    if 0<call.get('progress',0)<1 and call.get('role')!='decoration':
                        key=(call['nodeId'],call['type']);source_f=call.get('frame',data.get('sourceFrame',f))
                        item=motion_calls.setdefault(key,dict(nodeId=call['nodeId'],type=call['type'],firstFrame=source_f,lastFrame=source_f,sampledFrames=0))
                        item['lastFrame']=source_f;item['sampledFrames']+=1
                last_key=data['key'];encoder.stdin.write(buffer)
                if (f-a.first)%15==0:
                    from live_media import publish_render_preview
                    try:publish_render_preview(a.directory,buffer)
                    except OSError as error:
                        # The optional observer must not interrupt the original render.
                        if not preview_warning:
                            print('Live preview unavailable; render continues: '+str(error),flush=True)
                            preview_warning=True
                    path=a.directory/'progress.json';tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(dict(progress=(f-a.first+1)/count)));tmp.replace(path)
            encoder.stdin.close()
            if encoder.wait()!=0:raise ValueError('视频编码失败：'+(a.directory/'encoder.log').read_text()[-1200:])
            if errors:raise ValueError('; '.join(errors))
        except Exception:
            encoder.kill();encoder.wait();raise
        finally:browser.close()
    audio_completion=complete_audio_and_mux(video_only,a.audio,output,a.directory,document,a.first,a.last,a.fps)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'],video['pix_fmt'])==(1920,1080,'yuv420p'), str({k:video.get(k) for k in ['width','height','pix_fmt','color_range']})
    assert int(video['nb_frames'])==count
    assert abs(float(probe['format']['duration'])-count/a.fps)<.09
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)
    from motion_quality import audit_encoded
    object_proof=verify_objects(output,requests,captures,proof_dir)if requests else dict(status='not-required'if not document.get('motionPolicy',{}).get('stateProofRequired')else'pass',events=[])
    if object_proof['status']=='fail':raise ValueError('对象状态与编码像素验证失败：'+str(object_proof['failures']))
    motion_audit=audit_encoded(output,document,a.first,a.last)
    motion_audit['objectStateProof']=object_proof
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
    reading=reading_audit.result()
    (a.directory/'reading-audit.json').write_text(json.dumps(reading,ensure_ascii=False,indent=2))
    if reading['status']=='fail':raise ValueError('实际成片文字阅读未通过：'+'；'.join(reading['errors'])+'；候选保留，未登记为小样或成片')
    from continuity_pacing import audit as audit_continuity
    if document.get('continuityPolicy',{}).get('required') and not a.project:
        raise ValueError('连贯性检查需要 --project 以核对当前旁白干声')
    continuity=audit_continuity(document,a.project or a.directory,a.first,a.last,video=output)
    (a.directory/'continuity-audit.json').write_text(json.dumps(continuity,ensure_ascii=False,indent=2))
    if continuity['status']=='fail':raise ValueError('实际成片讲解连贯性未通过：'+'；'.join(continuity['errors'])+'；候选保留，未登记为小样或成片')
    report=dict(frames=count,capturedFrames=captured,fps=a.fps,duration=float(probe['format']['duration']),
                width=video['width'],height=video['height'],pixelFormat=video['pix_fmt'],colorRange=video.get('color_range'),audioCodec=audio['codec_name'],fullDecode='pass',
                video_encode_argv=args,worker_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),audioCompletion=audio_completion,seamPreflight=seam_report,objectStateProof=object_proof,captionMetrics=list(metrics.values()),bindingReceipt=receipt,seekDeterministic=True,motionAudit=motion_audit,readingPacing=reading,narrationContinuity=continuity,
                layoutAudit=dict(status='pass' if layout_checks else 'not-declared',checkedRenderedStates=layout_frames,rules=list(layout_checks.values()),scope='declared text enclosure and row separation, not all possible visual collisions'),renderer='same renderer.html and immutable document snapshot as preview')
    (a.directory/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
