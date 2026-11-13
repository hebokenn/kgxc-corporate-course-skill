"""Reading is measured on actual text and edited time, separately from actions."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from reading_pacing import inspect,require,estimate,RuntimeAudit,policy


def fixture(total=300):
    text='接收人员：示例甲\n交接日期：周三'
    return dict(fps=30,sourceDurationFrames=total,holds=[],cuts=[],introFrames=0,bodyEndFrame=total,
        scenes=[dict(id='S',sourceStartFrame=0,sourceEndFrame=total)],fields=[],
        readingPolicy=policy(),sceneGraph=dict(nodes=[dict(id='card',type='group',sceneId='S',motion=[dict(property='x',startFrame=0,endFrame=60,**{'from':0,'to':100})],children=[dict(id='body',type='text',text=text,x=100,y=200)])]),
        readingPlan=dict(schema='course-reading-plan/1',referenceTextIds=[],groups=[dict(id='assignment',sceneId='S',textIds=['body'],task='读清接收人与日期',window=dict(startFrame=0,endFrame=total),minimumStableSeconds=4,retention=dict(mode='keep',untilFrame=total,reason='后续核对仍需查看'))]))


def receipt(text,x=100,**kwargs):
    return dict(objectId='body',text=text,bounds=[x,200,x+420,280],alpha=1,complete=True,inFrame=True,occluded=False,**kwargs)


class ReadingTests(unittest.TestCase):
    def test_motion_can_be_brisk_while_completed_text_remains_readable(self):
        d=fixture();r=inspect(d);self.assertEqual(r['status'],'pass',r['errors']);self.assertEqual(r['groups'][0]['availableStableSeconds'],8)

    def test_parent_movement_and_fade_are_not_reading_time(self):
        d=fixture(90)
        self.assertEqual(inspect(d)['groups'][0]['availableStableSeconds'],1)
        d['sceneGraph']['nodes'][0]['motion']=[dict(property='opacity',startFrame=0,endFrame=75,**{'from':0,'to':1})]
        self.assertEqual(inspect(d)['groups'][0]['availableStableSeconds'],.5)

    def test_declaring_a_read_beat_does_not_supply_exposure(self):
        d=fixture(90);d['motionPlan']=dict(beats=[dict(kind='read',reason='可阅读',startFrame=0,endFrame=90)])
        self.assertEqual(inspect(d)['status'],'fail')

    def test_edits_to_actual_text_increase_required_budget(self):
        d=fixture();d['fields']=[dict(property='text',objectId='body',text='新增字段需要逐项解释'*12)]
        r=inspect(d);self.assertGreater(r['groups'][0]['estimatedFloorSeconds'],4);self.assertEqual(r['status'],'fail')

    def test_last_second_replacement_cannot_count_all_scene_time(self):
        d=fixture();d['sceneGraph']['nodes'][0]['children'][0]['startFrame']=285
        r=inspect(d);self.assertEqual(r['groups'][0]['availableStableSeconds'],.5);self.assertEqual(r['status'],'fail')

    def test_disconnected_short_stops_are_not_added_as_one_read(self):
        d=fixture(240);p=d['sceneGraph']['nodes'][0];p['motion']=[dict(property='x',startFrame=a,endFrame=a+30,**{'from':i*100,'to':(i+1)*100})for i,a in enumerate([0,60,120,180])]
        r=inspect(d);self.assertEqual(r['groups'][0]['availableStableSeconds'],1);self.assertEqual(r['status'],'fail')

    def test_real_hold_extends_reading_but_fading_hold_does_not(self):
        d=fixture(90);d['holds']=[dict(sourceFrame=75,frames=120)]
        self.assertEqual(inspect(d)['status'],'pass')
        d['sceneGraph']['nodes'][0]['motion']=[dict(property='opacity',startFrame=0,endFrame=80,**{'from':0,'to':1})]
        self.assertEqual(inspect(d)['status'],'fail')

    def test_cut_can_destroy_a_previously_valid_reading_window(self):
        d=fixture();self.assertEqual(inspect(d)['status'],'pass');d['cuts']=[dict(startFrame=90,endFrame=285)]
        self.assertEqual(inspect(d)['status'],'fail')

    def test_previous_information_needs_real_retention_or_summary(self):
        d=fixture();g=d['readingPlan']['groups'][0];g['window']['endFrame']=180;d['sceneGraph']['nodes'][0]['children'][0]['endFrame']=180
        self.assertTrue(any('回看时消失'in e for e in inspect(d)['errors']))
        d['sceneGraph']['nodes'].append(dict(id='summary',type='text',sceneId='S',startFrame=180,text='人员与日期已核实',x=800,y=200))
        g['retention']['viaTextIds']=['summary']
        d['readingPlan']['groups'].append(dict(id='summary-reading',sceneId='S',textIds=['summary'],task='回看本步结果',window=dict(startFrame=180,endFrame=300),minimumStableSeconds=3,retention=dict(mode='replace',reason='本段结束后不再引用')))
        self.assertEqual(inspect(d)['status'],'pass',inspect(d)['errors'])

    def test_competing_new_information_must_be_sequenced_or_grouped(self):
        d=fixture();d['sceneGraph']['nodes'].append(dict(id='another',type='text',sceneId='S',text='核对异常信息',x=900,y=300))
        g=copy.deepcopy(d['readingPlan']['groups'][0]);g.update(id='other',textIds=['another']);d['readingPlan']['groups'].append(g)
        self.assertTrue(any('窗口竞争'in e for e in inspect(d)['errors']))
        d['readingPlan']['groups'].pop();d['readingPlan']['groups'][0]['textIds'].append('another');d['readingPlan']['groups'][0]['minimumStableSeconds']=6
        self.assertEqual(inspect(d)['status'],'pass',inspect(d)['errors'])

    def test_ephemeral_text_cannot_be_declared_a_permanent_label(self):
        d=fixture();d['readingPlan'].update(groups=[],referenceTextIds=['body'])
        self.assertTrue(any('常驻标签实际'in e for e in inspect(d)['errors']))

    def test_missing_plan_and_unmapped_text_fail_new_course(self):
        d=fixture();d.pop('readingPlan');self.assertEqual(inspect(d)['status'],'fail')
        d=fixture();d['sceneGraph']['nodes'].append(dict(id='unmapped',type='text',text='额外正文',sceneId='S'))
        self.assertTrue(any('unmapped'in e for e in inspect(d)['errors']))

    def test_deleting_new_contract_cannot_pose_as_legacy(self):
        with tempfile.TemporaryDirectory()as tmp:
            Path(tmp,'motion-contract.json').write_text('{"readingRequired":true}')
            d=fixture();d.pop('readingPolicy')
            with self.assertRaisesRegex(ValueError,'不能删除 readingPolicy'):require(d,tmp)

    def test_legacy_inspection_is_read_only_and_not_automatically_enforced(self):
        d=fixture(90);d.pop('readingPolicy');d.pop('readingPlan');original=copy.deepcopy(d)
        self.assertEqual(inspect(d)['status'],'legacy-not-opted-in');self.assertEqual(inspect(d,force=True)['status'],'fail');self.assertEqual(d,original)

    def test_runtime_uses_same_actual_text_positions_not_authored_claim(self):
        d=fixture();a=RuntimeAudit(d,0,300);text=d['sceneGraph']['nodes'][0]['children'][0]['text']
        for f in range(300):a.consume(f,f,[receipt(text,x=f if f<60 else 160)])
        self.assertEqual(a.result()['status'],'pass',a.result())
        self.assertEqual(a.result()['groups'][0]['actualStableSeconds'],8)
        b=RuntimeAudit(d,0,300)
        for f in range(300):b.consume(f,f,[receipt(text,x=f)])
        self.assertEqual(b.result()['status'],'fail')

    def test_runtime_clipping_occlusion_or_wrong_text_blocks_delivery(self):
        for bad in ['clipped','covered','changed','missing','transparent','incomplete']:
            d=fixture();a=RuntimeAudit(d,0,300);text=d['sceneGraph']['nodes'][0]['children'][0]['text']
            r=receipt(text)
            if bad=='clipped':r['inFrame']=False
            elif bad=='covered':r['occluded']=True
            elif bad=='changed':r['text']='旧文字'
            elif bad=='transparent':r['alpha']=0
            elif bad=='incomplete':r['complete']=False
            for f in range(300):a.consume(f,f,[]if bad=='missing'else[r])
            with self.subTest(bad=bad):self.assertEqual(a.result()['status'],'fail')

    def test_partial_export_cannot_invent_missing_read_time(self):
        d=fixture();a=RuntimeAudit(d,60,90);text=d['sceneGraph']['nodes'][0]['children'][0]['text']
        for f in range(60,90):a.consume(f,f,[receipt(text)])
        self.assertEqual(a.result()['status'],'fail')

    def test_floor_is_content_sensitive_not_one_duration_for_every_screen(self):
        self.assertGreater(estimate(['人员：甲\n日期：周三\n异常：需复核']),estimate(['核对']))

    def test_sibling_alpha_is_not_multiplied_across_fields(self):
        d=fixture();p=d['sceneGraph']['nodes'][0];p['motion']=[]
        p['children']=[dict(id=i,type='text',text='核实',opacity=.995,y=j*120)for j,i in enumerate(['one','two','three'])]
        d['readingPlan']['groups'][0]['textIds']=['one','two','three']
        self.assertEqual(inspect(d)['status'],'pass',inspect(d))
        p['opacity']=.995
        self.assertEqual(inspect(d)['status'],'pass',inspect(d))
        p['opacity']=.99
        self.assertEqual(inspect(d)['status'],'fail')

    def test_counting_digits_and_parent_reveal_are_not_complete_text(self):
        for effect in ['count-up','odometer','mask-reveal','compare-wipe']:
            d=fixture(180);p=d['sceneGraph']['nodes'][0];p['motion']=[]
            p['effects']=[dict(type=effect,startFrame=0,endFrame=150)]
            with self.subTest(effect=effect):self.assertEqual(inspect(d)['groups'][0]['availableStableSeconds'],1)

    def test_constant_labels_are_checked_in_actual_render_too(self):
        d=fixture();d['sceneGraph']['nodes'][0]['motion']=[];text=d['sceneGraph']['nodes'][0]['children'][0]['text']
        d['readingPlan'].update(groups=[],referenceTextIds=['body'])
        for failure in ['offscreen','later-cover','moving']:
            a=RuntimeAudit(d,0,300)
            for f in range(300):
                r=receipt(text,x=f if failure=='moving'else 100)
                if failure=='offscreen':r['inFrame']=False
                if failure=='later-cover'and f>=200:r['occluded']=True
                a.consume(f,f,[r])
            with self.subTest(failure=failure):self.assertEqual(a.result()['status'],'fail',a.result())

    def test_retention_only_crop_still_checks_later_information(self):
        d=fixture();d['sceneGraph']['nodes'][0]['motion']=[];g=d['readingPlan']['groups'][0];g['window']['endFrame']=150
        text=d['sceneGraph']['nodes'][0]['children'][0]['text']
        for covered in [False,True]:
            a=RuntimeAudit(d,240,300)
            for f in range(240,300):
                r=receipt(text);r['occluded']=covered;a.consume(f,f,[r])
            self.assertEqual(a.result()['status'],'fail'if covered else'pass',a.result())
            self.assertFalse(a.result()['groups'][0]['readingPhaseIncluded'])

    def test_enable_is_explicit_idempotent_and_preserves_prior_document(self):
        from reading_pacing import enable
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'project';p.mkdir();d=fixture();d.update(revision=7);d.pop('readingPolicy');(p/'workbench.json').write_text(json.dumps(d));(p/'motion-contract.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'实际修改依据'):enable(Path(tmp),'')
            r=enable(Path(tmp),'QA opt-in, not course approval');self.assertEqual(r['revision'],8)
            self.assertEqual(json.loads((p/'workbench-history/000007.json').read_text()),d)
            self.assertEqual(enable(Path(tmp),'QA')['status'],'already-enabled')


class RenderReceiptTests(unittest.TestCase):
    def test_actual_canvas_text_bounds_parent_clip_and_later_cover(self):
        script=r'''
const fs=require('fs'),vm=require('vm');let stack=[],m={a:1,b:0,c:0,d:1,e:0,f:0};
const ctx={globalAlpha:1,save(){stack.push({...m})},restore(){m=stack.pop()},translate(x,y){m.e+=x;m.f+=y},scale(){},rotate(){},setTransform(){m={a:1,b:0,c:0,d:1,e:0,f:0}},getTransform(){return m},measureText(t){return{actualBoundingBoxLeft:0,actualBoundingBoxRight:t.length*20,actualBoundingBoxAscent:0,actualBoundingBoxDescent:30}}};
const c=new Proxy(ctx,{get:(o,k)=>k in o?o[k]:()=>{},set:(o,k,v)=>(o[k]=v,true)});
const sandbox={window:{},structuredClone,document:{querySelector:()=>({getContext:()=>c}),fonts:{load:async()=>{},ready:Promise.resolve()}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
(async()=>{const api=sandbox.window.courseWorkbench;let doc={fps:30,sourceDurationFrames:180,fields:[],assets:[],readingPolicy:{required:true},scenes:[{id:'S',sourceStartFrame:0,sourceEndFrame:180}],sceneGraph:{nodes:[{id:'parent',type:'group',x:100,y:200,children:[{id:'text',type:'text',text:'read',fontSize:30}]}]}};
const results=[];await api.apply(doc);await api.seek(0);results.push(api.readingReceipt());doc.sceneGraph.nodes[0].clip=[0,0,20,80];await api.apply(doc);await api.seek(0);results.push(api.readingReceipt());delete doc.sceneGraph.nodes[0].clip;doc.sceneGraph.nodes.push({id:'cover',type:'rect',x:90,y:190,width:300,height:100,fill:'#fff'});await api.apply(doc);await api.seek(0);results.push(api.readingReceipt());console.log(JSON.stringify(results));})();
'''
        result=json.loads(subprocess.check_output(['node','-e',script,str(ROOT/'workbench/starter/scene-engine.js')],text=True))
        self.assertTrue(result[0][0]['inFrame']);self.assertFalse(result[0][0]['occluded']);self.assertFalse(result[1][0]['inFrame']);self.assertTrue(result[2][0]['occluded'])


class ActualRenderTests(unittest.TestCase):
    def test_same_renderer_checks_reveals_covers_references_and_caption_layer(self):
        from runtime import activate,browser_options
        activate()
        from playwright.sync_api import sync_playwright
        lib=ROOT/'libraries/illustration/scripts/engine/lib'
        native='<style>@font-face{font-family:CourseHan;src:url(/font.woff)}</style><canvas width="1920" height="1080"></canvas>'
        for name in ['util','paint','motion','typo','diagram','ui','camera']:
            native+=f'<script src="/lib/{name}.js"></script>'
        for name in ['effects','teaching-effects']:
            native+=f'<script src="/motion/{name}.js"></script>'
        native+='<script src="/scene-engine.js"></script>'
        routes={'/native.html':('text/html',native.encode()),
            '/index.html':('text/html',b'<canvas id="final" width="1920" height="1080"></canvas><iframe id="native" src="/native.html" hidden></iframe><script type="module">import {CourseRenderer} from "/renderer.js";window.r=new CourseRenderer(document.querySelector("#final"),document.querySelector("#native"));window.ready=true;</script>'),
            '/font.woff':('font/woff',(lib/'fonts/NotoSansSC-500.woff').read_bytes())}
        routes['/project/font.woff']=routes['/font.woff']
        for name in ['renderer.js','timeline.js']:
            routes['/'+name]=('application/javascript',(ROOT/'workbench'/name).read_bytes())
        routes['/scene-engine.js']=('application/javascript',(ROOT/'workbench/starter/scene-engine.js').read_bytes())
        for name in ['effects','teaching-effects']:
            routes[f'/motion/{name}.js']=('application/javascript',(ROOT/'workbench/motion'/f'{name}.js').read_bytes())
        for name in ['util','paint','motion','typo','diagram','ui','camera']:
            routes[f'/lib/{name}.js']=('application/javascript',(lib/f'{name}.js').read_bytes())
        def base():
            d=fixture(180);d.update(width=1920,height=1080,adapter='scene-graph-v1',assets=[],media={},font='font.woff',captions=[],captionStyle=dict(fontSize=48,y=950,strokeWidth=8,stroke='#fff',fill='#202020'))
            parent=d['sceneGraph']['nodes'][0];parent['motion']=[]
            parent['children'][0].update(x=100,y=100,fontSize=48)
            return d
        def cover(start=0,fill='#fff'):
            return dict(id='cover',type='rect',sceneId='S',x=90,y=90,width=800,height=220,startFrame=start,fill=fill)
        cases=[]
        good=base();cases.append(('stable-complete-text',good,'pass'))
        d=base();d['sceneGraph']['nodes'].append(cover(fill='rgba(255,255,0,0.1)'));cases.append(('transparent-marker',d,'pass'))
        d=base();parent=d['sceneGraph']['nodes'][0];parent.update(width=900,height=400,effects=[dict(type='mask-reveal',startFrame=0,endFrame=120)])
        d['sceneGraph']['nodes'].append(cover(start=120));cases.append(('parent-mask-then-cover',d,'fail'))
        for effect in ['count-up','odometer']:
            d=base();d['sceneGraph']['nodes'][0]['children'][0].update(text='1000000',effects=[dict(type=effect,startFrame=0,endFrame=120)])
            d['sceneGraph']['nodes'].append(cover(start=120));cases.append((effect+'-then-cover',d,'fail'))
        d=base();d['sceneGraph']['nodes'][0]['children'][0].update(text='接收人员：甲',x=650,y=920)
        d['captions']=[dict(id='caption',text='确认后交给店长',startFrame=0,endFrame=180)];cases.append(('final-caption-overlap',d,'fail'))
        for name,offscreen in [('offscreen-reference',True),('later-covered-reference',False)]:
            d=base();d['readingPlan'].update(groups=[],referenceTextIds=['body'])
            if offscreen:d['sceneGraph']['nodes'][0]['children'][0]['x']=2100
            else:d['sceneGraph']['nodes'].append(cover(start=120))
            cases.append((name,d,'fail'))
        with sync_playwright()as pw:
            browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            def route(request):
                from urllib.parse import urlparse
                item=routes.get(urlparse(request.request.url).path)
                request.fulfill(status=200 if item else 404,content_type=item[0]if item else'text/plain',body=item[1]if item else b'not found')
            page.route('**/*',route);page.goto('http://reading-fixture.test/index.html');page.wait_for_function('window.ready===true')
            for name,d,expected in cases:
                frames=page.evaluate('''async d=>{await r.load(d);const rows=[];for(let f=0;f<d.sourceDurationFrames;f++)rows.push(await r.drawFrame(f));return rows}''',d)
                audit=RuntimeAudit(d,0,180)
                for row in frames:audit.consume(row['frame'],row['sourceFrame'],row['readingReceipt'])
                with self.subTest(case=name):self.assertEqual(audit.result()['status'],expected,audit.result())
            self.assertFalse(errors);browser.close()


if __name__=='__main__':unittest.main()
