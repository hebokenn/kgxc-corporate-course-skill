"""Actual named props, original-texture rigs and editable rendering share one path."""
import copy,hashlib,http.server,json,math
from pathlib import Path
import subprocess,sys,tempfile,threading,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from content_assets import expand,phone
from device_models import profile
from character_rig import stage,prepare,pose_angles,PROFILES,inverse
from character_pose import stage_pose
from authoring import walk
from runtime import activate,browser_options
from backend import Workspace,Handler
import test_new_course_workbench as fixture
activate()


def spec():return dict(sourceDurationFrames=30,scenes=[dict(id='X',sourceStartFrame=0,sourceEndFrame=30)],assets=[],sceneGraph=dict(nodes=[],materials=[dict(id='p',kind='phone',sceneId='X',x=900,y=270,scale=.9,data=dict(model='iphone-18-pro',finish='glacier-blue',deviceId='trial',screenStates=[dict(atFrame=0,mode='camera'),dict(atFrame=16,mode='gallery')],interactions=[dict(atFrame=8,durationFrames=7,target='shutter',capture=True)]))]))


class AssetContractTests(unittest.TestCase):
    def test_store_roles_do_not_confuse_manager_staff_and_coach(self):
        profile=json.loads((ROOT/'assets/profiles/kgxc/profile.json').read_text());roles=json.loads((ROOT/'assets/profiles/kgxc/roles.json').read_text());by_id={r['id']:r for r in roles['roles']}
        self.assertEqual(by_id['store_manager']['outfit'],'black');self.assertEqual(by_id['store_manager']['mark'],'KG');self.assertEqual(by_id['store_manager']['asset'],'M1-repaired.png')
        self.assertEqual(by_id['store_staff']['outfit'],'blue');self.assertEqual(by_id['coach']['mark'],'MyCoach');self.assertEqual(by_id['coach']['outfit'],'black')
        self.assertNotIn('blue-cast',profile['characters']['manager']);self.assertEqual(profile['characters']['default_presenter_role'],'store_manager')

    def test_named_model_has_own_geometry_reference_and_front_back_side(self):
        p=profile('iphone-18-pro');self.assertAlmostEqual(p['width']/p['height'],71.9/150)
        self.assertAlmostEqual(p['screenWidth']/p['screenHeight'],1206/2622)
        self.assertIn('apple.com.cn',p['metadata']['references'][0])
        for view,required in [('front','dynamic-island'),('back','lidar'),('side','side-camera-control')]:
            s=spec();s['sceneGraph']['materials'][0]['data']['view']=view
            out=expand(s);ids=[n['id'] for n in walk(out['sceneGraph']['nodes'])];self.assertIn('p-'+required,ids)
        for model,finish in [('unverified-phone','black'),('iphone-18-pro','orange')]:
            with self.assertRaises(ValueError):profile(model,finish)

    def test_bad_state_asset_id_and_scene_are_rejected(self):
        for change in ['state','scene','identity','duplicate']:
            s=spec();p=s['sceneGraph']['materials'][0]
            if change=='state':p['data']['screenStates'][0]['atFrame']=2
            if change=='scene':p['sceneId']='missing'
            if change=='identity':p.update(kind='actor',data=dict(identity='C01',rig=dict(identity='C01',files={'body':{'assetId':'absent'}})))
            if change=='duplicate':s['sceneGraph']['materials'].append(copy.deepcopy(p))
            with self.assertRaises(ValueError):expand(s)

    def test_layer_order_preserves_background_then_material_then_explanation(self):
        s=spec();s['sceneGraph']['nodes']=[dict(id='bg',zIndex=0),dict(id='explanation',zIndex=20)];s['sceneGraph']['materials'][0]['zIndex']=10
        out=expand(s);self.assertEqual([n['id'] for n in out['sceneGraph']['nodes']],['bg','p-root','explanation'])
        self.assertIn('materials',s['sceneGraph']);self.assertNotIn('materials',out['sceneGraph'])
        self.assertEqual(out['contentAssets'][0]['source']['data']['model'],'iphone-18-pro')

    def test_each_identity_uses_own_joints_and_ik_does_not_stretch(self):
        self.assertEqual(len({tuple(d['left']['S']) for d in PROFILES.values()}),3)
        for identity,p in PROFILES.items():
            rig=dict(identity=identity,joints={side:{k:p[side][k] for k in ['S','E','W']} for side in ['left','right']})
            for pose in ['rest','question','phone-use','tap-phone']:
                values=pose_angles(rig,pose)
                self.assertTrue(all(math.isfinite(v) for side in values.values() for v in side.values()))
            with self.assertRaises(ValueError):inverse(p['left']['S'],p['left']['E'],p['left']['W'],[10000,10000])


class RigAndRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixture.NewCourseTests();cls.fixture.setUp();cls.p=cls.fixture.p
        cls.r=stage('C01',cls.p,ROOT);cls.contact=stage_pose('C01',cls.p,ROOT)
    @classmethod
    def tearDownClass(cls):cls.fixture.tearDown()

    def test_expressions_keep_silhouette_and_only_change_local_features(self):
        from PIL import Image
        import numpy as np
        f=self.r['rig']['files'];arrays={k:np.asarray(Image.open(self.p/next(a['path'] for a in self.r['assets'] if a['id']==v['assetId']))) for k,v in f.items() if k.startswith('head-')}
        a=arrays['head-smile'];b=arrays['head-neutral'];self.assertEqual(a.shape,b.shape);self.assertTrue(np.array_equal(a[:,:,3],b[:,:,3]))
        ys,xs=np.where(np.any(a[:,:,:3]!=b[:,:,:3],axis=2));self.assertGreater(len(xs),300)
        x0,y0,_,_=f['head-smile']['bbox'];self.assertTrue(xs.min()+x0>=470 and xs.max()+x0<=545);self.assertTrue(ys.min()+y0>=200 and ys.max()+y0<=251)
        self.assertFalse(self.r['rig']['naturalWalkReady'])

    def test_rejected_grip_and_unbranded_uniform_cannot_be_generated(self):
        s=spec();s['assets']=self.r['assets'];s['sceneGraph']['materials']=[dict(id='bad',kind='actor',sceneId='X',data=dict(identity='C01',rig=self.r['rig'],pose='phone-use'))]
        with self.assertRaisesRegex(ValueError,'停用'):expand(s)
        s['assets']=[dict(id='m1')];s['sceneGraph']['materials']=[dict(id='m',kind='actor',sceneId='X',data=dict(identity='M1',headAsset='m1'))]
        with self.assertRaisesRegex(ValueError,'KG'):expand(s)
        s['assets'].append(dict(id='kg'));s['sceneGraph']['materials'][0]['data']['logoAsset']='kg';out=expand(s)
        logo=next(n for n in walk(out['sceneGraph']['nodes']) if n['id']=='m-uniform-KG');self.assertEqual([logo['x'],logo['y'],logo['width']],[559,458,70])

    def test_staging_preserves_edited_parts_instead_of_silently_regenerating(self):
        asset=self.p/self.r['assets'][0]['path'];raw=asset.read_bytes();folder=asset.parent;source=ROOT/'assets/characters/kgxc-customers-v1/C01-full-v1.png'
        try:
            asset.write_bytes(raw+b'changed')
            with self.assertRaisesRegex(ValueError,'编辑'):prepare('C01',source,folder)
            self.assertEqual(asset.read_bytes(),raw+b'changed')
        finally:asset.write_bytes(raw)

    def test_actual_pixels_edits_reverse_seek_clip_and_transform_receipt(self):
        from playwright.sync_api import sync_playwright
        s=spec();s['assets']=self.r['assets']+self.contact['assets'];s['sceneGraph']['materials'].append(dict(id='c',kind='actor',sceneId='X',x=120,y=270,scale=.7,data=dict(identity='C01',rig=self.r['rig'],pose='rest',view='half',deviceId='trial',poseKeys=[dict(frame=0,pose='rest'),dict(frame=6,pose='rest'),dict(frame=14,pose='question'),dict(frame=22,pose='rest')])))
        s['sceneGraph']['materials'].append(dict(id='contact',kind='actor',sceneId='X',x=470,y=270,scale=.65,data=dict(identity='C01',contactPose=self.contact['pose'],deviceId='trial')))
        doc=self.fixture.ready(s);space=Workspace(self.p);http.server.ThreadingHTTPServer.request_queue_size=128;server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=space;threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));page.goto(f'http://127.0.0.1:{server.server_address[1]}/renderer.html');page.wait_for_function('window.ready===true||window.renderError',timeout=120000);self.assertIsNone(page.evaluate('window.renderError||null'))
                def draw(f):return page.evaluate('async f=>{let r=window.courseRenderer;await r.drawFrame(f);return r.canvas.toDataURL()}',f)
                frames={f:draw(f) for f in [3,10,24]};self.assertEqual(len(set(frames.values())),3)
                draw(10);receipt=page.evaluate('window.courseRenderer.native.courseWorkbench.motionReceipt()');self.assertTrue(any(r['type']=='transform-rotation' and 'right-' in r['nodeId'] for r in receipt))
                self.assertTrue(any(r['type']=='ring-progress' for r in receipt))
                # Seek back: effects and linked state must be deterministic.
                self.assertEqual(draw(3),frames[3]);self.assertEqual(draw(24),frames[24])
                field=next(f for f in doc['fields'] if f['objectId']=='p-screen-1-title');changed=copy.deepcopy(doc);next(f for f in changed['fields'] if f['id']==field['id'])['text']='实际可编辑的照片标题'
                # The public adapter is also the renderer's actual editing path.
                page.evaluate('async d=>{await window.courseRenderer.load(d)}',changed);self.assertNotEqual(draw(24),frames[24])
                # Half-body crop should leave the lower body background untouched.
                self.assertEqual(page.evaluate('Array.from(window.courseRenderer.ctx.getImageData(290,910,1,1).data)')[:3],page.evaluate('Array.from(window.courseRenderer.ctx.getImageData(20,910,1,1).data)')[:3])
                browser.close()
        finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
