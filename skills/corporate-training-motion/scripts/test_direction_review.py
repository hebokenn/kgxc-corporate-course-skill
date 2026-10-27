"""Different content and timings must drive the inspection, never a sample lesson."""
from pathlib import Path
import base64,copy,hashlib,http.server,json,os,subprocess,sys,tempfile,threading,time,unittest,wave
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from direction_review import inspect,continuation
from production import handoff
from timeline import source_frame


def fixture():
    doc=dict(fps=30,sourceDurationFrames=180,introFrames=0,bodyEndFrame=180,holds=[],cuts=[],
        scenes=[dict(id='SHIFT',title='错开休息',sourceStartFrame=0,sourceEndFrame=60),
                dict(id='ARCHIVE',title='任务接收',sourceStartFrame=60,sourceEndFrame=120),
                dict(id='READ',title='对照结果',sourceStartFrame=120,sourceEndFrame=180,presentation=dict(mode='reference'))],
        captions=[dict(id='C1',text='调整休息时段',startFrame=0,endFrame=60),dict(id='C2',text='把记录放入对应档案',startFrame=60,endFrame=120),dict(id='C3',text='请对照调整后的结果',startFrame=120,endFrame=180)],
        sceneGraph=dict(nodes=[dict(id='schedule',type='group',sceneId='SHIFT',children=[dict(id='person-slot',type='rect',x=180,y=420,width=160,height=80,role='subject',motion=[dict(property='x',startFrame=6,endFrame=24,**{'from':180,'to':650})])]),
            dict(id='record',type='rect',sceneId='ARCHIVE',x=1200,y=400,width=180,height=250,role='subject',motion=[dict(property='x',startFrame=74,endFrame=94,**{'from':1200,'to':500})]),
            dict(id='read-table',type='rect',sceneId='READ',x=200,y=360,width=1420,height=300,role='subject')]),
        motionPlan=dict(schema='course-motion-plan/1',language='synthetic-three-different-tasks',beats=[]),
        narrationLinks=dict(schema='narration-object-events/1',cueLinks=[dict(cueId='C1',text='调整休息时段',purpose='看清两个休息安排如何错开',visibleObjectIds=['person-slot']),dict(cueId='C2',text='把记录放入对应档案',purpose='看清接收对象',visibleObjectIds=['record']),dict(cueId='C3',text='请对照调整后的结果',purpose='稳定比较表中的调整前后',visibleObjectIds=['read-table'])]))
    nodes=doc['sceneGraph']['nodes'];schedule=nodes[0]
    def text(sid,identifier,value,x,y,size=38):return dict(id=identifier,type='text',sceneId=sid,text=value,x=x,y=y,fontSize=size,fill='#202020',role='decoration')
    for i,day in enumerate(['周一','周二','周三','周四','周五']):
        nodes.extend([dict(id='day-'+str(i),type='rect',sceneId='SHIFT',x=160+i*235,y=350,width=220,height=380,fill='#eeeeee',role='decoration'),text('SHIFT','day-name-'+str(i),day,180+i*235,380)])
    # The calendar sits behind the moving slot, keeping the same employee identity.
    nodes.remove(schedule);nodes.append(schedule)
    label=text('SHIFT','employee-a','甲·休息',195,467,32);label['motion']=[dict(property='x',startFrame=6,endFrame=24,**{'from':195,'to':665})];schedule['children'].append(label)
    nodes.extend([dict(id='employee-b',type='rect',sceneId='SHIFT',x=180,y=570,width=160,height=80,fill='#a0a0a0',role='decoration'),text('SHIFT','employee-b-label','乙·休息',195,617,32)])
    record=next(n for n in nodes if n['id']=='record');nodes.remove(record)
    label=text('ARCHIVE','record-label','交接单 A',1220,470,31);label['motion']=[dict(property='x',startFrame=74,endFrame=94,**{'from':1220,'to':520})]
    nodes.append(dict(id='archive-camera',type='group',sceneId='ARCHIVE',role='camera',x=0,y=0,motion=[dict(property='x',startFrame=96,endFrame=110,**{'from':0,'to':-60}),dict(property='scaleX',startFrame=96,endFrame=110,**{'from':1,'to':1.08}),dict(property='scaleY',startFrame=96,endFrame=110,**{'from':1,'to':1.08})],children=[dict(id='folder-tab',type='rect',x=460,y=320,width=180,height=65,fill='#dddddd',role='decoration'),dict(id='folder',type='rect',x=460,y=370,width=330,height=330,fill='#eeeeee',role='decoration'),record,label]))
    nodes.extend([text('ARCHIVE','folder-title','对应档案',500,745),text('ARCHIVE','overview-label','同一笔交接记录',1140,350)])
    nodes[-1]['endFrame']=96
    nodes.remove(next(n for n in nodes if n['id']=='read-table'))
    nodes.append(dict(id='read-table',type='group',sceneId='READ',role='subject',children=[dict(id='table-paper',type='rect',x=200,y=350,width=1420,height=400,fill='#eeeeee',role='subject'),text('READ','table-left','原安排',260,410),text('READ','table-right','调整后',990,410),text('READ','table-before','甲与乙同日休息',260,520),text('READ','table-after','甲周三 乙周一',990,520),text('READ','table-result','休息时段错开',990,650)]))
    return doc


class DirectionTests(unittest.TestCase):
    def test_different_tasks_keep_their_words_objects_and_nonuniform_timings(self):
        doc=fixture();before=copy.deepcopy(doc);r=inspect(doc);a,b,c=r['scenes'];self.assertEqual(doc,before)
        self.assertIn('person-slot',a['subjectObjectIds']);self.assertIn('record',b['subjectObjectIds']);self.assertNotIn('record',a['subjectObjectIds'])
        self.assertEqual(a['narration'][0]['text'],'调整休息时段');self.assertEqual(c['narration'][0]['purpose'],'稳定比较表中的调整前后')
        af={f['sourceFrame']for f in a['inspectionFrames']};bf={f['sourceFrame']for f in b['inspectionFrames']}
        self.assertTrue({6,14,23,24,60}<=af);self.assertTrue({74,83,93,94,120}<=bf)
        self.assertNotIn(30,af);self.assertNotIn(90,bf);self.assertEqual(c['presentation']['mode'],'reference');self.assertEqual(r['status'],'inspection-plan')
    def test_viewport_label_exit_reaction_and_user_selected_peaks_are_sampled(self):
        d=fixture();next(n for n in d['sceneGraph']['nodes']if n['id']=='schedule')['children'].extend([dict(id='label',type='text',text='区域',startFrame=0,endFrame=17),dict(id='actor',type='image',performance=dict(keys=[dict(frame=4,values={}),dict(frame=19,values=dict(nod=1))],blinks=[[25,27,29]]))]);d['scenes'][0]['reviewFrames']=[21]
        r=inspect(d)['scenes'][0];fs={v['sourceFrame']:v['reasons']for v in r['inspectionFrames']}
        self.assertTrue({4,16,17,19,21,25,27,29}<=set(fs));self.assertIn('actor',r['performanceObjectIds']);self.assertIn('producer-scene-peak',fs[21])
    def test_cut_frames_do_not_point_to_another_picture_and_holds_have_two_boundaries(self):
        d=fixture();d['cuts']=[dict(startFrame=12,endFrame=20)];d['holds']=[dict(sourceFrame=24,frames=13)]
        r=inspect(d);samples=[v for row in r['scenes']for v in row['inspectionFrames']]
        self.assertFalse(any(12<=v['sourceFrame']<20 for v in samples))
        for v in samples:self.assertEqual(source_frame(v['displayFrame'],d['holds'],d['cuts']),v['sourceFrame'])
        held=[v['displayFrame']for v in samples if v['sourceFrame']==23];self.assertTrue({15,16,28}<=set(held))
    def test_resume_surfaces_current_content_and_preserves_completed_or_courseware(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);(p/'workbench.json').write_text(json.dumps(fixture()));before=(p/'workbench.json').read_bytes()
            r=handoff(p,dict(branch='video',stage='final'));self.assertEqual(r['direction']['scenes'],3);self.assertTrue(all((ROOT/v).is_file()for v in r['direction']['requiredGuides']))
            self.assertFalse(handoff(p,dict(branch='video',stage='complete'))['active']);self.assertFalse(handoff(p,dict(branch='courseware',stage='courseware'))['active'])
            self.assertEqual(before,(p/'workbench.json').read_bytes())
    def test_geometry_reuse_is_a_content_decision_not_an_automatic_failure(self):
        d=fixture();d['sceneGraph']['nodes']=[dict(id=s['id']+'-table',type='rect',sceneId=s['id'],x=100,y=300,width=1000,height=400)for s in d['scenes']]
        r=inspect(d);self.assertTrue(r['compositionSignals']);self.assertEqual(r['status'],'inspection-plan')
    def test_cli_does_not_overwrite_input_or_previous_evidence(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);f=p/'spec.json';f.write_text(json.dumps(fixture()));before=f.read_bytes();out=p/'plan.json'
            cli=[sys.executable,str(ROOT/'scripts/course_tools.py'),'direction-check','--spec',str(f),'--out']
            one=subprocess.run(cli+[str(out)],capture_output=True,text=True);self.assertEqual(one.returncode,0,one.stderr);r=json.loads(out.read_text());self.assertEqual(r['documentSha256'],hashlib.sha256(before).hexdigest())
            saved=out.read_bytes();self.assertNotEqual(subprocess.run(cli+[str(out)],capture_output=True).returncode,0);self.assertNotEqual(subprocess.run(cli+[str(f)],capture_output=True).returncode,0)
            self.assertEqual(saved,out.read_bytes());self.assertEqual(before,f.read_bytes())

    def test_actual_different_tasks_render_seek_and_encode_with_own_state_proofs(self):
        from authoring import init_project,configure
        from backend import Workspace,Handler
        from runtime import activate,browser_options
        from motion_quality import preflight
        from playwright.sync_api import sync_playwright
        activate()
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(os.environ.get('COURSE_DIRECTION_QA_DIR',tmp));p=root/'project';p.mkdir(parents=True)
            for n in ['assets','audio','source','qa']:(p/n).mkdir()
            init_project(p,ROOT)
            with wave.open(str(p/'audio/synthetic-silence.wav'),'wb')as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*(48000*6))
            spec=fixture();spec.update(title='异内容技术验证 无配音教学结论',media=dict(audio='audio/synthetic-silence.wav',intro=None,outro=None),assets=[],rendering=dict(route='auto'))
            spec['readingPlan']=dict(schema='course-reading-plan/1',groups=[],referenceTextIds=[],noNewTextReason='本夹具检查图形对象动作和状态，没有正文阅读任务')
            from authoring import walk
            for n in walk(spec['sceneGraph']['nodes']):
                if n['id']in ['person-slot','record']:n['fill']='#536d83'
            for scene in spec['scenes']:
                sid=scene['id'];spec['sceneGraph']['nodes'].append(dict(id=sid+'-title',type='text',sceneId=sid,text=scene['title'],x=140,y=170,fontSize=58,fill='#202020',role='decoration'))
            for sid,bid,obj,cid,start,end,expect,op in [('SHIFT','reschedule','person-slot','C1',6,24,600,'gt'),('ARCHIVE','receive','record','C2',74,94,600,'lt')]:
                cue=next(v for v in spec['captions']if v['id']==cid);before=180 if sid=='SHIFT'else 1200;fs=[start,(start+end-1)//2,end-1]
                spec['motionPlan']['beats'].append(dict(id=bid,sceneId=sid,kind='action',startFrame=start,endFrame=end,objectIds=[obj],purpose='错开休息时段'if sid=='SHIFT'else'记录归入接收档案',before='原时段'if sid=='SHIFT'else'记录待接收',after='新时段'if sid=='SHIFT'else'记录已归入',anchor=dict(cueId=cid,phrase=cue['text'],atFrame=start),evidenceFrames=fs,stateChecks=[dict(sourceFrame=start,objectId=obj,property='x',op='eq',expected=before),dict(sourceFrame=end-1,objectId=obj,property='x',op=op,expected=expect)]))
            spec['motionPlan']['beats'].append(dict(id='compare',sceneId='READ',kind='read',startFrame=120,endFrame=180,objectIds=['read-table'],reason='稳定比较调整前后的结果'))
            path=p/'source/synthetic.json';path.write_text(json.dumps(spec,ensure_ascii=False));doc=configure(root,path);self.assertEqual(preflight(doc)['status'],'pass',preflight(doc))
            report=inspect(doc);(p/'qa/direction-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));space=Workspace(root)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=space;threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                url=f'http://127.0.0.1:{server.server_port}';hashes={};frames=sorted({v['displayFrame']for s in report['scenes']for v in s['inspectionFrames']})
                with sync_playwright()as pw:
                    browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));page.goto(url+'/renderer.html');page.wait_for_function('window.ready||window.renderError',timeout=60000);self.assertIsNone(page.evaluate('window.renderError||null'))
                    for f in frames+list(reversed(frames)):
                        png=page.evaluate('async f=>{await courseRenderer.drawFrame(f);return courseRenderer.canvas.toDataURL().split(",")[1]}',f);digest=hashlib.sha256(png.encode()).hexdigest()
                        if f in hashes:self.assertEqual(hashes[f],digest)
                        hashes[f]=digest;(p/'qa'/f'{f:05}.png').write_bytes(base64.b64decode(png))
                    browser.close()
                self.assertNotEqual(hashes[6],hashes[23]);self.assertNotEqual(hashes[74],hashes[93]);self.assertEqual(hashes[120],hashes[179])
                job=space.start_export(doc['revision'],0,6,url,purpose='pilot');deadline=time.monotonic()+240
                while job['status']not in ['complete','failed']and time.monotonic()<deadline:time.sleep(.1);job=space.job(job['id'])
                self.assertEqual(job['status'],'complete',job)
                proof=json.loads((space.work/'exports'/job['id']/'verification.json').read_text());self.assertEqual(proof['fullDecode'],'pass');self.assertEqual(proof['objectStateProof']['status'],'pass')
                (p/'qa/transfer-result.json').write_text(json.dumps(dict(status='pass',source='public synthetic fixture; no private lesson files',differentTasks=[v['title']for v in doc['scenes']],reverseSeek=True,inspectionFrames=frames,fullDecode='pass',objectStateProof=proof['objectStateProof']['status'],scope='synthetic input-dependent timing, stable reading and actual native/encoded object evidence; not aesthetic, voice or learner acceptance'),ensure_ascii=False,indent=2))
            finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
