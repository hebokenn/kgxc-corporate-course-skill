"""Real browser pixels, H264/AAC and source-presence controls for 05/08/09."""
import base64,copy,functools,hashlib,http.server,json,os,shutil,subprocess,sys,tempfile,threading,unittest,wave
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];WB=ROOT/'skills/corporate-training-motion/workbench'
sys.path.insert(0,str(WB))
from production_validation import digest,sha,Check,current_review,decoded_frame_hashes
from chapter_table import canonical_table,progress,expected_samples,inspect as chapter_inspect
from sfx_evidence import decode,match,calibrate,inspect as sfx_inspect,mix_from_dry
from motion_quality import audit_encoded
from semantic_alignment import measure_audio_mapping


def run(args):return subprocess.run(args,check=True,capture_output=True)
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def wav(path,samples):
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000);f.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())


class EncodedExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('ffmpeg'):raise unittest.SkipTest('ffmpeg needed')
        cls.tmp=tempfile.TemporaryDirectory();cls.p=Path(os.environ.get('EXECUTION_MEDIA_EVIDENCE_DIR',cls.tmp.name));cls.p.mkdir(parents=True,exist_ok=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_08_calibrated_native_source_vs_silence_narration_compression(self):
        p=self.p/'sfx';p.mkdir(exist_ok=True)
        palette=ROOT/'skills/corporate-training-motion/assets/sfx/teaching-native-v1'
        catalog=json.loads((palette/'palette.json').read_text());asset=catalog['assets'][0]
        source=p/'native.wav';shutil.copy2(palette/asset['path'],source);s=decode(source)
        count=48000*3;t=np.arange(count)/48000
        voice=.008*np.sin(2*np.pi*143*t)+.006*np.sin(2*np.pi*(277*t+12*t*t))
        silence=np.zeros(count);start=48000-int(np.argmax(np.abs(s)))
        positive=voice.copy();positive[start:start+len(s)]+=.4*s
        wav(p/'dry.wav',voice);wav(p/'silence.wav',silence);wav(p/'mix.wav',positive)
        stem=np.zeros(count);stem[start:start+len(s)]=.4*s;wav(p/'stem.wav',stem)
        for name in ['mix','dry']:
            run(['ffmpeg','-v','error','-y','-i',str(p/(name+'.wav')),'-c:a','aac','-b:a','160k',str(p/(name+'.m4a'))])
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=64x64:r=25:d=3','-i',str(p/'mix.wav'),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(p/'current.mp4')])
        positives=[decode(p/'mix.wav'),decode(p/'mix.m4a')];negatives=[decode(p/'silence.wav'),decode(p/'dry.wav'),decode(p/'dry.m4a')]
        report=calibrate(s,positives,negatives)
        self.assertTrue(report['ready'],report)
        self.assertGreater(match(s,decode(p/'current.mp4'))['score'],report['threshold'])
        self.assertLess(match(s,negatives[1])['score'],report['threshold'])
        controls=dict(assets=[dict(source_sha256=sha(source),positive_controls=[dict(kind=k,path='sfx/'+name,sha256=sha(p/name),expected_offset_sample=start) for k,name in [('source-present','mix.wav'),('compressed-present','mix.m4a')]],negative_controls=[dict(kind=k,path='sfx/'+name,sha256=sha(p/name)) for k,name in [('silence','silence.wav'),('narration-only','dry.wav'),('compressed-absent','dry.m4a')]])])
        peak=int(np.argmax(np.abs(s)))
        event=dict(id='native-event',asset_id=asset['id'],source_sha256=sha(source),visual_event_id='land',trigger_kind='peak',source_peak_sample=peak,gain=.4,group_id='choice',peak_or_onset_frame=25,timing_contract=dict(declared_before_mix=True,tolerance_basis='integer-frame quantization + measured AAC calibration error',measurement_error_samples=0))
        receipt={k+'_path':'sfx/'+v for k,v in [('dry','dry.wav'),('sfx_stem','stem.wav'),('mix','mix.wav')]}
        receipt.update({k+'_sha256':sha(p/v) for k,v in [('dry','dry.wav'),('sfx_stem','stem.wav'),('mix','mix.wav')]})
        write(p/'plan.json',dict(events=[event]))
        made=mix_from_dry(self.p,'sfx/dry.wav','sfx/plan.json',[dict(id=asset['id'],path='sfx/native.wav',sha256=sha(source))],'sfx/built-stem.wav','sfx/built-mix.wav',25)
        self.assertEqual(len(decode(p/'built-mix.wav')),len(voice));self.assertFalse(made['narration_timeline_changed'])
        receipt.update(plan_path='sfx/plan.json',plan_sha256=digest(dict(events=[event])),narration_timeline_changed=False)
        contract=dict(choices=dict(sound_effects='native'),requirements=dict(sfx=dict(palette='teaching-native-v1',assets=[dict(id=asset['id'],path='sfx/native.wav',sha256=sha(source))],plan_path=dict(events=[event]),receipt=receipt,calibration=controls,review=dict(video_sha256=sha(p/'current.mp4'),mix_sha256=sha(p/'mix.wav')))))
        doc=dict(fps=25,media=dict(audio='sfx/mix.wav'))
        r=sfx_inspect(self.p,doc,p/'current.mp4','final',contract)
        codes={e['code'] for e in r['errors']}
        self.assertNotIn('SFX_NOT_IN_ENCODE',codes,r);self.assertNotIn('SFX_TIME_MISMATCH',codes,r);self.assertIn('AUDIO_REVIEW_UNVERIFIED',codes)
        mapping=measure_audio_mapping(p/'dry.wav',p/'current.mp4',40,40,25,0)
        self.assertGreater(mapping['score'],.7,mapping);self.assertLess(abs(mapping['offset_error_samples']),960,mapping)
        wrong_mapping=measure_audio_mapping(p/'dry.wav',p/'current.mp4',40,40,25,2)
        self.assertGreater(abs(wrong_mapping['offset_error_samples']),960,wrong_mapping)
        write(p/'audio-timing-checkpoints.json',dict(actual=mapping,wrong_two_frame_mapping=wrong_mapping,hearing=False))
        # Same plan with encoded sound removed must fail, not infer it from a nonzero stem.
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=64x64:r=25:d=3','-i',str(p/'dry.wav'),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(p/'absent.mp4')])
        missing=sfx_inspect(self.p,doc,p/'absent.mp4','final',contract)
        self.assertIn('SFX_NOT_IN_ENCODE',{e['code'] for e in missing['errors']})
        # A real source shifted two frames cannot be accepted by widening tolerance post-hoc.
        shifted=np.zeros(count);shifted[start+3840:start+3840+len(s)]=.4*s;wav(p/'shifted.wav',voice+shifted)
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=64x64:r=25:d=3','-i',str(p/'shifted.wav'),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(p/'shifted.mp4')])
        shifted_r=sfx_inspect(self.p,doc,p/'shifted.mp4','final',contract)
        self.assertIn('SFX_TIME_MISMATCH',{e['code'] for e in shifted_r['errors']})
        write(p/'signal-results.json',dict(calibration=report,present=r,absent=missing,shifted=shifted_r,actual_source_sha256=sha(source),auditory_review_performed=False))
    def test_05_actual_body_static_despite_moving_bottom_progress(self):
        p=self.p/'static';p.mkdir(exist_ok=True)
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=white:s=640x360:r=24:d=2','-f','lavfi','-i','color=c=red:s=40x8:r=24:d=2','-filter_complex',"[0:v]drawbox=x=40:y=100:w=150:h=80:color=black:t=fill[body];[body][1:v]overlay=x='t*200':y=340[out]",'-map','[out]','-c:v','libx264','-pix_fmt','yuv420p',str(p/'static.mp4')])
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(p/'static.mp4'),'-map','0:v:0','-vf','select=eq(n\\,0)+eq(n\\,24),format=rgb24','-fps_mode','passthrough','-f','rawvideo','-'])
        images=np.frombuffer(raw,dtype=np.uint8).reshape(2,360,640,3)
        self.assertGreater(np.abs(images[0,340:350].astype(float)-images[1,340:350]).sum(),1000)
        self.assertLess(np.abs(images[0,90:210,40:240].astype(float)-images[1,90:210,40:240]).mean(),1)
        d=dict(fps=24,sourceDurationFrames=48,holds=[],cuts=[],width=640,height=360,scenes=[dict(id='s',sourceStartFrame=0,sourceEndFrame=48)],motionPolicy=dict(required=True,longStaticWarningSeconds=.8,stateProofRequired=True,subjectROI=[40,90,200,120]),motionPlan=dict(beats=[]))
        # Existing ROI is a body-only field; bottom navigation cannot close the risk.
        a=audit_encoded(p/'static.mp4',d,0,48)
        self.assertTrue(a['longStaticRuns'],a);self.assertTrue(a['unresolvedStaticRuns'],a)
        write(p/'body-static-report.json',a)
    def test_09_fractional_fps_audio_uses_rounded_span_boundaries(self):
        from timeline import audio_filters,duration
        from fractions import Fraction
        p=self.p/'fractional';p.mkdir(exist_ok=True)
        wav(p/'source.wav',np.sin(np.arange(48000*12)*.023)*.01)
        d=dict(fps=29.97,sourceDurationFrames=300,holds=[dict(sourceFrame=47,frames=13)],cuts=[dict(startFrame=130,endFrame=163)],audio=dict(gain=1))
        filters=audio_filters(d)
        run(['ffmpeg','-v','error','-y','-i',str(p/'source.wav'),'-filter_complex',filters,'-map','[out]','-c:a','pcm_s16le',str(p/'edited.wav')])
        actual=len(decode(p/'edited.wav'));expected=round(Fraction(duration(d))*48000/Fraction(str(d['fps'])))
        self.assertEqual(actual,expected)
        write(p/'sample-boundary-proof.json',dict(fps=d['fps'],display_frames=duration(d),actual_samples=actual,expected_samples=expected,filter=filters,source_sha256=sha(p/'source.wav'),output_sha256=sha(p/'edited.wav')))
    def test_09_actual_renderer_cut_hold_seek_state_and_h264_pixels(self):
        try:
            from runtime import activate,browser_options
            activate()
            from playwright.sync_api import sync_playwright
        except ImportError:raise unittest.SkipTest('Run with configured course runtime for actual browser pixel proof')
        p=self.p/'navigation';p.mkdir(exist_ok=True);(p/'frames').mkdir(exist_ok=True)
        d=dict(fps=24,sourceDurationFrames=48,width=1920,height=1080,holds=[dict(sourceFrame=12,frames=12)],cuts=[dict(startFrame=30,endFrame=36)],introFrames=0,bodyEndFrame=48,adapter='teaching-native-v1',font='font.otf',fields=[],assets=[],media={},captions=[],scenes=[dict(id='s',sourceStartFrame=0,sourceEndFrame=48)],sceneGraph=dict(background='#ffffff',nodes=[]))
        table=canonical_table(d,[dict(chapter_id='c1',label='First',source_start=0,source_end=24),dict(chapter_id='c2',label='Second',source_start=24,source_end=48)]);d['chapterTable']=table
        for j,row in enumerate(table):row.update(body_visible_windows=[[0,48]],nav_node_ids=['label'+str(j),'fill'+str(j)])
        d['sceneGraph']['nodes'].append(dict(id='body',type='rect',x=100,y=100,width=100,height=100,fill='#000000',startFrame=0,endFrame=48,motion=[dict(property='x',startFrame=0,endFrame=48,**{'from':100,'to':580},ease='linear')]))
        for j,row in enumerate(table):
            d['sceneGraph']['nodes'] += [dict(id='base'+str(j),type='rect',role='navigation',x=100+j*400,y=900,width=240,height=8,fill='#cccccc',startFrame=0,endFrame=48),dict(id='fill'+str(j),type='rect',role='navigation',x=100+j*400,y=900,width=0,height=8,fill='#006633',startFrame=0,endFrame=48,navigation=dict(kind='progress-fill',chapter_id=row['chapter_id'],segment_width=240),motion=[dict(property='width',startFrame=row['source_start'],endFrame=row['source_end'],**{'from':0,'to':240},ease='linear')])]
        for j,row in enumerate(table):d['sceneGraph']['nodes'].append(dict(id='label'+str(j),type='text',text=row['label'],role='navigation',x=100+j*400,y=850,fontSize=28,fontFamily='Arial',startFrame=0,endFrame=48))
        write(p/'document.json',d);shutil.copy2(ROOT/'skills/corporate-training-motion/assets/bookends/CourseTitle.otf',p/'font.otf')
        (p/'native.html').write_text('<canvas width="1920" height="1080"></canvas><script src="/scene-engine.js"></script>')
        (p/'index.html').write_text('''<canvas id="output" width="1920" height="1080"></canvas><iframe id="native" src="/native.html"></iframe><script type="module">import {CourseRenderer} from '/renderer.js';const d=await fetch('/document.json').then(r=>r.json());window.renderer=new CourseRenderer(document.querySelector('#output'),document.querySelector('#native'));await renderer.load(d);window.ready=true;</script>''')
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
            def translate_path(self,url):
                if url in ['/scene-engine.js','/renderer.js','/timeline.js']:return str(WB/('starter/scene-engine.js' if url=='/scene-engine.js' else url[1:]))
                if url.startswith('/project/'):url=url[len('/project'):]
                return str(p/url.lstrip('/'))
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        states=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));page.goto('http://127.0.0.1:'+str(server.server_port)+'/index.html');page.wait_for_function('window.ready===true')
                for f in range(54):
                    result=page.evaluate('async f=>{const r=await renderer.drawFrame(f);return {frame:f,source:r.sourceFrame,states:renderer.native.courseWorkbench.objectReceipt(),png:document.querySelector("#output").toDataURL().split(",")[1]}}',f)
                    (p/'frames'/f'{f:03}.png').write_bytes(base64.b64decode(result.pop('png')));states.append(result)
                seek=page.evaluate('async()=>{await renderer.drawFrame(20);return renderer.native.courseWorkbench.objectReceipt()}')
                self.assertAlmostEqual(seek['fill0']['width'],240*20/36)
                self.assertEqual(states[13]['source'],states[20]['source']);self.assertEqual(states[13]['states']['body']['x'],states[20]['states']['body']['x'])
                self.assertLess(states[13]['states']['fill0']['width'],states[20]['states']['fill0']['width'])
                browser.close()
        finally:server.shutdown();server.server_close()
        run(['ffmpeg','-v','error','-y','-framerate','24','-i',str(p/'frames/%03d.png'),'-c:v','libx264','-pix_fmt','yuv420p',str(p/'current.mp4')])
        out=p/'encoded';out.mkdir(exist_ok=True)
        run(['ffmpeg','-v','error','-y','-i',str(p/'current.mp4'),'-map','0:v:0','-vf','select=eq(n\\,13)+eq(n\\,20)','-fps_mode','passthrough',str(out/'%02d.png')])
        widths=[]
        for f,file in zip([13,20],sorted(out.glob('*.png'))):
            a=np.asarray(Image.open(file).convert('RGB'));line=a[903,100:340];width=int(((line[:,1]>line[:,0]+25)&(line[:,1]>line[:,2]+20)).sum());widths.append(width)
            self.assertLess(abs(width-states[f]['states']['fill0']['width']),4)
        self.assertGreater(widths[1],widths[0]+30)
        # Current screenshot bytes must match actual encoded pixels, not producer labels.
        f=13;png=sorted(out.glob('*.png'))[0]
        review=dict(document_sha256=digest(d),video_sha256=sha(p/'current.mp4'),observations=[dict(frame=f,actualPTS=f/24,path=str(png.relative_to(self.p)),sha256=sha(png),observation='Green progress is part filled while body source is frozen')])
        check=Check('fixture');current_review(check,self.p,review,d,p/'current.mp4');self.assertFalse(check.errors,check.errors)
        forged=copy.deepcopy(review);forged['observations'][0]['path']=str((p/'frames/013.png').relative_to(self.p));forged['observations'][0]['sha256']=sha(p/'frames/013.png')
        bad=Check('fixture');current_review(bad,self.p,forged,d,p/'current.mp4');self.assertTrue(bad.errors)
        needed=expected_samples(table);proofdir=p/'chapter-boundaries';proofdir.mkdir(exist_ok=True)
        expression='+'.join('eq(n\\,%d)'%f for f in needed)
        run(['ffmpeg','-v','error','-y','-i',str(p/'current.mp4'),'-map','0:v:0','-vf','select='+expression,'-fps_mode','passthrough',str(proofdir/'%02d.png')])
        observations=[dict(frame=f,actualPTS=f/24,path=str(file.relative_to(self.p)),sha256=sha(file),observation='Actual current encoded rectangular fill width measured at display frame '+str(f)) for f,file in zip(needed,sorted(proofdir.glob('*.png')))]
        chapter_contract=dict(requirements=dict(chapters=dict(chapter_table=table,table_sha256=digest(table),allow_state_words=False,review=dict(document_sha256=digest(d),video_sha256=sha(p/'current.mp4'),observations=observations))))
        navproof=chapter_inspect(self.p,d,p/'current.mp4','final',chapter_contract)
        self.assertTrue(navproof['ready'],navproof['errors'])
        fake=copy.deepcopy(d);fake['sceneGraph']['nodes'][2]['motion']=[]
        fakeproof=chapter_inspect(self.p,fake,p/'current.mp4','storyboard',chapter_contract)
        self.assertFalse(fakeproof['ready'])
        write(p/'chapter-pixel-proof.json',navproof)
        write(p/'actual-render-and-encoded.json',dict(video_sha256=sha(p/'current.mp4'),document_sha256=digest(d),states=states,seek20=seek,encoded_fill_widths=widths,pixel_review=check.result(),forged_pixel_review=bad.result(),continuous_av_review=False))

if __name__=='__main__':unittest.main()
