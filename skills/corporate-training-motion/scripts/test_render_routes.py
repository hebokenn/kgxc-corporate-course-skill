"""Verify visible effects, real edits and portable export, not only routing labels."""
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate,tools,browser_options
activate()
from render_routes import plan,effect_errors,upgrade
from backend import Handler,Workspace,read,atomic,validate
from authoring import configure
import test_new_course_workbench as course_fixture


def graph():
    return dict(background='#f3f2ec',nodes=[
        dict(id='heading',type='text',sceneId='X',text='先核对 再提交',x=120,y=110,fontSize=64,
             effects=[dict(type='chars-in',startFrame=0,endFrame=24)]),
        dict(id='image',type='image',sceneId='X',assetId='sample',x=120,y=280,width=240,height=180,
             effects=[dict(type='mask-reveal',startFrame=0,endFrame=20,direction='right')]),
        dict(id='line',type='path',sceneId='X',x=620,y=350,fill=None,stroke='#17654b',lineWidth=10,
             points=[[0,0],[120,0],[120,120],[240,120]],effects=[dict(type='draw-on',startFrame=0,endFrame=24)]),
        dict(id='blur',type='text',sceneId='X',text='编码一致',x=120,y=600,fontSize=56,
             effects=[dict(type='blur-in',startFrame=0,endFrame=20)]),
        dict(id='rise',type='text',sceneId='X',text='数量一致',x=620,y=600,fontSize=56,
             effects=[dict(type='text-rise',startFrame=0,endFrame=20)]),
        dict(id='typed',type='text',sceneId='X',text='核对完成再提交',x=120,y=780,fontSize=56,
             effects=[dict(type='typewriter',startFrame=0,endFrame=24)]),
        dict(id='gradient',type='rect',sceneId='X',x=1000,y=280,width=360,height=180,
             fill=dict(type='linear-gradient',**{'from':[0,0]},to=[360,0],stops=[[0,'#ff0000'],[1,'#0000ff']])),
    ])


class RouteSelectionTests(unittest.TestCase):
    def test_basic_and_effect_requirements_choose_different_real_routes(self):
        self.assertEqual(plan(dict(sceneGraph=dict(nodes=[])))['route'],'scene-graph')
        selected=plan(dict(sceneGraph=graph(),rendering=dict(route='auto')))
        self.assertTrue(selected['ready']);self.assertEqual(selected['route'],'motion-canvas')
        self.assertIn('draw-on',selected['requiredEffects']);self.assertIn('gradient',selected['requiredEffects'])

    def test_forced_basic_and_unimplemented_requirements_never_silently_downgrade(self):
        self.assertFalse(plan(dict(sceneGraph=graph(),rendering=dict(route='scene-graph')))['ready'])
        selected=plan(dict(rendering=dict(route='auto',requiredEffects=['three-d'])))
        self.assertEqual(selected['route'],'native-canvas');self.assertFalse(selected['ready'])
        spec=dict(sourceDurationFrames=30,sceneGraph=dict(nodes=[]),rendering=dict(requiredEffects=['blur-in']))
        self.assertTrue(effect_errors(spec))

    def test_old_custom_implementations_keep_their_route(self):
        self.assertEqual(plan(dict(adapter='seek-bridge-v1'))['route'],'native-canvas')

    def test_invalid_effect_geometry_and_time_are_rejected(self):
        spec=dict(sourceDurationFrames=30,sceneGraph=graph())
        self.assertFalse(effect_errors(spec))
        spec['sceneGraph']['nodes'][2]['points']=[[0,0]]
        self.assertTrue(effect_errors(spec))
        spec['sceneGraph']['nodes'][0]['effects'][0]['endFrame']=31
        self.assertTrue(effect_errors(spec))


class RendererUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=course_fixture.NewCourseTests();self.fixture.setUp();self.p=self.fixture.p
        for name,color in [('red','#ff0000'),('blue','#0000ff')]:
            (self.p/f'assets/{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="{color}"/></svg>')
        self.doc=self.fixture.ready(dict(sceneGraph=dict(nodes=[dict(id='t',type='text',sceneId='X',text='原文字',x=120,y=120),dict(id='i',type='image',sceneId='X',assetId='picture',x=120,y=300)]),assets=[dict(id='picture',path='assets/red.svg')]))
        self.spec=dict(rendering=dict(route='auto'),sceneGraph=copy.deepcopy(self.doc['sceneGraph']))
        self.spec['sceneGraph']['nodes'][0]['effects']=[dict(type='chars-in',startFrame=0,endFrame=20)]
        self.path=self.p/'source/upgrade.json';atomic(self.path,self.spec)

    def tearDown(self):self.fixture.tearDown()

    def test_upgrade_retains_saved_text_offsets_image_and_audio_timeline(self):
        changed=copy.deepcopy(self.doc);changed['fields'][0].update(text='用户保存的改字',dx=88)
        changed['assets'][0]['path']='assets/blue.svg';changed['holds']=[dict(sourceFrame=15,frames=3,sceneId='X')]
        saved=Workspace(self.p).save(changed,0)
        before_native=(self.p/'native/scene-engine.js').read_bytes()
        result=upgrade(self.p,self.path,saved['revision']);actual=read(self.p/'workbench.json')
        self.assertEqual(actual['fields'],saved['fields']);self.assertEqual(actual['assets'],saved['assets'])
        for key in ['media','scenes','captions','holds','cuts','audio']:self.assertEqual(actual[key],saved[key])
        self.assertEqual(actual['rendering']['route'],'motion-canvas');self.assertEqual(actual['revision'],2)
        self.assertEqual((self.p/result['backup']/'native/scene-engine.js').read_bytes(),before_native)
        self.assertTrue((self.p/'editor/workbench/motion/lib/paint.js').is_file())
        self.assertEqual(read(self.p/'project.json')['workbench']['adapter'],'seek-bridge-v1')

    def test_custom_engine_is_never_overwritten(self):
        engine=self.p/'native/scene-engine.js';engine.write_text(engine.read_text()+'\n// custom course implementation\n')
        before=engine.read_bytes();document=(self.p/'workbench.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'自定义native'):upgrade(self.p,self.path,0)
        self.assertEqual(engine.read_bytes(),before);self.assertEqual((self.p/'workbench.json').read_bytes(),document)

    def test_stale_revision_and_timeline_changes_stop_before_mutation(self):
        before=(self.p/'workbench.json').read_bytes()
        result=upgrade(self.p,self.path,0,dry_run=True)
        self.assertTrue(result['dryRun']);self.assertEqual((self.p/'workbench.json').read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'revision'):upgrade(self.p,self.path,5)
        self.spec['sourceDurationFrames']=60;atomic(self.path,self.spec)
        with self.assertRaisesRegex(ValueError,'配音或字幕'):upgrade(self.p,self.path,0)
        self.assertEqual(read(self.p/'workbench.json')['adapter'],'scene-graph-v1')


class MotionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=course_fixture.NewCourseTests();self.fixture.setUp();self.p=self.fixture.p
        from playwright.sync_api import sync_playwright
        # Different source images make replacement observable in the actual Canvas.
        def svg(color):return f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="180"><rect width="240" height="180" fill="{color}"/></svg>'
        (self.p/'assets/red.svg').write_text(svg('#ff0000'))
        (self.p/'assets/blue.svg').write_text(svg('#0000ff'))
        self.doc=self.fixture.ready(dict(sceneGraph=graph(),rendering=dict(route='auto'),
            assets=[dict(id='sample',path='assets/red.svg')]))
        self.space=Workspace(self.p)
        http.server.ThreadingHTTPServer.request_queue_size=128
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.workspace=self.space
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
        self.pw=sync_playwright().start();self.browser=self.pw.chromium.launch(headless=True,**browser_options())
        self.page=self.browser.new_page(viewport=dict(width=1920,height=1080));self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url+'/renderer.html');self.page.wait_for_function('window.ready===true || window.renderError')
        self.assertIsNone(self.page.evaluate('window.renderError || null'))

    def tearDown(self):
        if hasattr(self,'browser'):self.browser.close();self.pw.stop()
        if hasattr(self,'server'):self.server.shutdown();self.server.server_close()
        self.fixture.tearDown()

    def draw(self,frame):
        return self.page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',frame)

    def pixel(self,x,y):
        return self.page.evaluate('([x,y])=>Array.from(window.courseRenderer.ctx.getImageData(x,y,1,1).data)',[x,y])

    def test_saved_light_and_dark_palette_reaches_real_canvas_pixels(self):
        from course_palette import catalog, select, binding
        from render_routes import bind_fields
        import base64
        for index, palette in enumerate([catalog()['palettes'][0], catalog()['palettes'][4]]):
            saved=select(self.p,specified=palette,redraw=bool(index),evidence='QA explicit light/dark runtime fixture')
            d=copy.deepcopy(self.doc);d['coursePalette']=binding(saved)
            d['sceneGraph']=dict(background=palette['canvas'],nodes=[
                dict(id='palette-title',type='text',sceneId='X',text='课程配色验证',x=120,y=110,fontSize=64,fill=palette['ink']),
                dict(id='palette-swatch',type='rect',sceneId='X',x=120,y=280,width=600,height=200,fill=palette['accent'],effects=[dict(type='mask-reveal',startFrame=0,endFrame=24)])])
            d['rendering']=dict(route='auto');d['rendering']=plan(d);d['adapter']=d['rendering']['adapter'];bind_fields(d);validate(d,self.p)
            atomic(self.p/'workbench.json',d)
            self.page.evaluate('async d=>window.courseRenderer.load(d)',d);self.draw(26)
            rgb=lambda c:[int(c[i:i+2],16) for i in [1,3,5]]
            self.assertEqual(self.pixel(50,50)[:3],rgb(palette['canvas']))
            self.assertEqual(self.pixel(200,330)[:3],rgb(palette['accent']))
            if os.environ.get('PALETTE_RENDER_PROOF_DIR'):
                folder=Path(os.environ['PALETTE_RENDER_PROOF_DIR']);folder.mkdir(parents=True,exist_ok=True)
                png=self.page.evaluate('window.courseRenderer.canvas.toDataURL("image/png")')
                (folder/(palette['id']+'.png')).write_bytes(base64.b64decode(png.split(',',1)[1]))

    def test_effects_are_visible_editable_and_reverse_seek_is_identical(self):
        self.assertEqual(self.doc['rendering']['route'],'motion-canvas')
        self.assertEqual(len([f for f in self.doc['fields'] if f['objectId']=='heading']),1)
        frames={f:self.draw(f) for f in [0,6,14,26]}
        self.assertEqual(len(set(frames.values())),4)
        for x,y,w,h in [(100,90,650,130),(100,570,400,130),(600,570,400,130),(100,750,650,130)]:
            regions=[]
            for f in [0,6,26]:
                self.draw(f)
                data=self.page.evaluate('([x,y,w,h])=>Array.from(window.courseRenderer.ctx.getImageData(x,y,w,h).data)',[x,y,w,h])
                regions.append(hashlib.sha256(bytes(data)).hexdigest())
            self.assertEqual(len(set(regions)),3,'文字动效必须在实际像素中呈现过程')
        for f in [26,0,14,6]:self.assertEqual(self.draw(f),frames[f])
        self.draw(0);self.assertNotEqual(self.pixel(200,330)[:3],[255,0,0])
        self.draw(26);self.assertEqual(self.pixel(200,330)[:3],[255,0,0])
        self.assertGreater(self.pixel(1020,330)[0],self.pixel(1020,330)[2])
        self.assertGreater(self.pixel(1340,330)[2],self.pixel(1340,330)[0])
        # A real path endpoint is reached, instead of scaling the whole path.
        self.assertEqual(self.pixel(850,470)[:3],[23,101,75])
        crop=lambda:self.page.evaluate('()=>Array.from(window.courseRenderer.ctx.getImageData(100,570,1000,290).data)')
        dynamic_end=crop()
        static=copy.deepcopy(self.doc)
        for n in static['sceneGraph']['nodes']:
            if n['type']=='text':n.pop('effects',None)
        static['rendering']['requiredEffects']=[e for e in static['rendering']['requiredEffects'] if e not in ['chars-in','blur-in','text-rise','typewriter']]
        self.page.evaluate('async d=>window.courseRenderer.load(d)',static);self.draw(26)
        self.assertEqual(crop(),dynamic_end,'入场结束须与原字号和top位置一致，不能把文字向上偏移')
        self.page.evaluate('async d=>window.courseRenderer.load(d)',self.doc);self.draw(26)
        changed=copy.deepcopy(self.doc)
        next(f for f in changed['fields'] if f['objectId']=='heading')['text']='修改后可重新排字'
        changed['assets'][0]['path']='assets/blue.svg'
        next(f for f in changed['fields'] if f['objectId']=='image')['dx']=80
        saved=self.space.save(changed,self.doc['revision'])
        self.page.evaluate('async d=>window.courseRenderer.load(d)',saved)
        edited=self.draw(26);self.assertNotEqual(edited,frames[26]);self.assertEqual(self.pixel(300,330)[:3],[0,0,255])
        self.assertNotEqual(self.pixel(140,330)[:3],[0,0,255])
        self.assertEqual(self.draw(6),self.draw(6));self.assertFalse(self.errors)

    def test_mesh_camera_easing_and_emphasis_remain_seek_deterministic(self):
        changed=copy.deepcopy(self.doc);g=changed['sceneGraph']
        g['background']=dict(type='mesh-gradient',base='#e6eee8',grain=.02,blur=25,
            blobs=[dict(x=500,y=280,r=600,col=[30,120,90],ax=45,period=2)])
        g['camera']=dict(x=960,y=540,zoom=1,motion=[dict(property='zoom',**{'from':1},to=1.15,startFrame=0,endFrame=24,ease='sineInOut')])
        g['nodes'][0].update(width=620,height=90)
        g['nodes'][0]['effects'].extend([dict(type='marker',startFrame=0,endFrame=20),dict(type='underline',startFrame=0,endFrame=24)])
        g['nodes'][-1]['motion']=[dict(property='x',**{'from':1000},to=1200,startFrame=0,endFrame=24,ease='snappy')]
        changed['rendering']=plan(changed);validate(changed,self.p)
        self.page.evaluate('async d=>window.courseRenderer.load(d)',changed)
        frames={f:self.draw(f) for f in [0,7,19,26]}
        self.assertEqual(len(set(frames.values())),4)
        for f in [19,0,26,7]:self.assertEqual(self.draw(f),frames[f])
        self.assertFalse(self.errors)

    def test_export_and_reopen_without_installed_skill(self):
        job=self.space.start_export(self.doc['revision'],0,1,self.url,purpose='pilot')
        deadline=time.monotonic()+90
        while job['status'] not in ['complete','failed'] and time.monotonic()<deadline:time.sleep(.1)
        self.assertEqual(job['status'],'complete',str(job))
        result=self.p/'work/workbench/exports'/job['id']
        self.assertEqual(read(result/'verification.json')['fullDecode'],'pass')
        from workflow import bundle_course
        archive=self.fixture.course/'packages/portable.zip';bundle_course(self.fixture.course,archive)
        reopened=self.fixture.course.parent/'unpacked'
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip());z.extractall(reopened)
        # Start the actual copied backend so no imports or server files come from ROOT.
        log=reopened/'server.log'
        with log.open('w') as out:
            proc=subprocess.Popen([tools().get('python',sys.executable),str(reopened/'project/editor/scripts/workbench.py'),'serve',str(reopened),'--port','0'],stdout=out,stderr=out,env={**os.environ,'PYTHONUNBUFFERED':'1'})
        try:
            import re
            deadline=time.monotonic()+20;url=None
            while time.monotonic()<deadline and proc.poll() is None:
                match=re.search(r'http://127\.0\.0\.1:\d+',log.read_text())
                if match:url=match[0];break
                time.sleep(.1)
            self.assertTrue(url,log.read_text())
            page=self.browser.new_page(viewport=dict(width=1920,height=1080));page.goto(url+'/renderer.html')
            page.wait_for_function('window.ready===true || window.renderError')
            self.assertIsNone(page.evaluate('window.renderError || null'))
            original=self.draw(26)
            self.assertEqual(page.evaluate('async()=>{const r=window.courseRenderer;await r.drawFrame(26);return r.canvas.toDataURL()}'),original)
            from workflow import local_json
            changed=read(reopened/'project/workbench.json')
            next(f for f in changed['fields'] if f['objectId']=='heading')['text']='解压后再次编辑'
            saved=local_json(url+'/api/save',dict(document=changed,baseRevision=changed['revision']))
            # The same public export CLI must work using only the unpacked project.
            command=[tools().get('python',sys.executable),str(reopened/'project/editor/scripts/workbench.py'),'export',str(reopened),'--server',url,'--purpose','pilot']
            completed=subprocess.run(command,capture_output=True,text=True,timeout=90)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            page.reload();page.wait_for_function('window.ready===true || window.renderError')
            self.assertNotEqual(page.evaluate('async()=>{const r=window.courseRenderer;await r.drawFrame(26);return r.canvas.toDataURL()}'),original)
        finally:proc.terminate();proc.wait(timeout=10)


if __name__=='__main__':unittest.main()
