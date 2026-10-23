"""Public, synthetic regression cases for registered reactions and object evidence."""
from pathlib import Path
import copy,http.server,json,sys,tempfile,threading,unittest,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from character_performance import stage,errors,validate_assets
from content_assets import expand
from motion_quality import policy,preflight,require,audit_encoded
from motion_evidence import predicate,inspect,verify
from backend import Workspace,Handler
from runtime import activate,browser_options
import test_new_course_workbench as fixture
activate()

class StateEvidenceTests(unittest.TestCase):
 def test_new_default_requires_bound_states_and_cannot_delete_marker(self):
  self.assertTrue(policy()['stateProofRequired'])
  from test_motion_quality import linked_fixture
  d=linked_fixture();d['motionPolicy']['stateProofRequired']=True
  self.assertTrue(any('状态断言'in e for e in preflight(d)['errors']))
  with tempfile.TemporaryDirectory()as tmp:
   p=Path(tmp);(p/'motion-contract.json').write_text('{"stateProofRequired":true}');d['motionPolicy']['stateProofRequired']=False
   with self.assertRaisesRegex(ValueError,'不能删除 stateProofRequired'):require(d,p)
 def test_false_expectation_and_whole_scene_observe_are_rejected_but_reference_allowed(self):
  self.assertFalse(predicate(dict(objectId='a',property='performance.concern',op='gt',expected=.8),{'a':{'performance':{'concern':0}}})['passed'])
  d=dict(motionPolicy=dict(stateProofRequired=True),scenes=[dict(id='S',sourceStartFrame=0,sourceEndFrame=90)],motionPlan=dict(beats=[dict(id='R',sceneId='S',kind='observe',startFrame=0,endFrame=90,objectIds=['a'])]));nodes={'a':dict(role='subject')}
  self.assertTrue(any('整场observe'in e for e in inspect(d,nodes)));d['scenes'][0]['presentation']=dict(mode='reference');self.assertFalse(inspect(d,nodes))
 def test_caption_inside_old_roi_is_excluded_at_its_actual_height(self):
  from test_motion_quality import fixture
  with tempfile.TemporaryDirectory()as tmp:
   video=Path(tmp)/'caption.mp4';d=fixture();d['captionStyle']=dict(y=894,fontSize=42,strokeWidth=7)
   subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=white:s=1920x1080:r=30:d=3','-f','lavfi','-i','color=red:s=300x40:r=30:d=3','-filter_complex','[0:v][1:v]overlay=x=300+t*200:y=870','-c:v','libx264','-preset','ultrafast','-threads','2','-pix_fmt','yuv420p',str(video)],check=True)
   self.assertEqual(audit_encoded(video,d,0,90)['status'],'fail')
 def test_camera_pixels_and_a_changed_target_label_cannot_fake_object_action(self):
  from PIL import Image,ImageDraw
  with tempfile.TemporaryDirectory()as tmp:
   p=Path(tmp);captures={};frames=[]
   for i,x in enumerate([200,360,550]):
    a=Image.new('RGB',(1920,1080),'white');ImageDraw.Draw(a).rectangle((x,400,x+180,600),fill='red');a.save(p/f'{i}.png');hidden=p/f'hidden-{i}.png';Image.new('RGB',a.size,'white').save(hidden)
    captures[('A',i)]={'base':str(p/f'{i}.png'),'hidden':str(hidden),'states':{'a':{'x':1,'performance':{'gazeX':0,'gazeTarget':str(i)}}}};frames.append(dict(source=i,display=i,encoded=i))
   video=p/'camera.mp4';subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(p/'%d.png'),'-frames:v','3','-c:v','libx264','-threads','2','-pix_fmt','yuv420p',str(video)],check=True)
   request=dict(id='A',objects=['a'],frames=frames,stateChecks=[dict(sourceFrame=0,objectId='a',property='x',op='eq',expected=1)])
   result=verify(video,[request],captures,p/'proof');self.assertEqual(result['status'],'fail');self.assertFalse(result['events'][0]['objectStateChanged'])

class ActualWorkbenchPerformanceTests(unittest.TestCase):
 def test_two_own_profiles_gaze_reactions_editing_and_reverse_seek(self):
  from playwright.sync_api import sync_playwright
  f=fixture.NewCourseTests();f.setUp()
  try:
   all_assets=[];materials=[]
   for i,who in enumerate(['C01','S01']):
    item=stage(who,f.p,ROOT);data=item['data'];data['performance'].update(keys=[dict(frame=0,values=dict(concern=1,gazeX=1 if i==0 else-1)),dict(frame=14,values=dict(concern=0,relief=.7,gazeY=.65,leftFore=24)),dict(frame=29,values=dict(relief=.8,gazeY=0,leftFore=0))],blinks=[[17,20,23]],targets=[dict(frame=0,id='other-'+str(i))]);all_assets.extend(item['assets']);materials.append(dict(id='actor-'+str(i),kind='actor',sceneId='X',x=110+i*950,y=210,scale=.8,data=data))
   # Targets are stable graph objects, not unbound descriptive strings.
   graph=dict(nodes=[dict(id='other-'+str(i),type='rect',sceneId='X',x=650+i*600,y=470,width=100,height=80,fill='#dddddd')for i in range(2)],materials=materials)
   doc=f.ready(dict(assets=all_assets,rendering=dict(route='auto'),sceneGraph=graph));space=Workspace(f.p);http.server.ThreadingHTTPServer.request_queue_size=128;server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=space;threading.Thread(target=server.serve_forever,daemon=True).start()
   try:
    with sync_playwright()as pw:
     browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));page.goto(f'http://127.0.0.1:{server.server_port}/renderer.html');page.wait_for_function('window.ready||window.renderError',timeout=60000);self.assertIsNone(page.evaluate('window.renderError||null'))
     def draw(frame):return page.evaluate('async f=>{const r=window.courseRenderer;await r.drawFrame(f);return {png:r.canvas.toDataURL(),states:r.native.courseWorkbench.objectReceipt()}}',frame)
     a=draw(0);b=draw(14);self.assertNotEqual(a['png'],b['png']);self.assertEqual(a['states']['actor-0-performance']['performance']['concern'],1);self.assertEqual(b['states']['actor-1-performance']['performance']['gazeY'],.65);self.assertEqual(draw(0)['png'],a['png'])
     # Existing image-position bindings remain effective for the performed actor.
     changed=copy.deepcopy(doc);field=next(v for v in changed['fields']if v['objectId']=='actor-0-performance');field['dx']+=80;page.evaluate('async d=>window.courseRenderer.load(d)',changed);self.assertNotEqual(draw(0)['png'],a['png'])
     browser.close()
   finally:server.shutdown();server.server_close()
   changed=copy.deepcopy(doc);node=next(n for n in __import__('authoring').walk(changed['sceneGraph']['nodes'])if n.get('performance'));node['performance']['profile']['sourceSha256']='0'*64
   with self.assertRaisesRegex(ValueError,'原图已换'):validate_assets(changed,f.p)
  finally:f.tearDown()

if __name__=='__main__':unittest.main()
