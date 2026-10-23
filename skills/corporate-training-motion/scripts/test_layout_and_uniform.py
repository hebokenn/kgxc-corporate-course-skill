"""Reproduce the reported crossing outline; reject it using real font geometry."""
import copy,http.server,sys,threading,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate,browser_options
from backend import Handler,Workspace
from content_assets import expand
from company_characters import stage_company
import test_new_course_workbench as fixture
activate()


def composition():return dict(sourceDurationFrames=30,scenes=[dict(id='X',sourceStartFrame=0,sourceEndFrame=30)],assets=[],sceneGraph=dict(background='#f5f3e9',materials=[dict(id='paper',kind='document',sceneId='X',x=100,y=100,scale=1.17,data=dict(title='核对条件',rows=[['教育优惠','资格待核实'],['以旧换新 / 分期','按具体条件确认']],rowFrames=[0,12],rowFocus=[dict(row=0,atFrame=0,endFrame=12),dict(row=1,atFrame=12,endFrame=30)]))]))


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.NewCourseTests();self.fixture.setUp();self.p=self.fixture.p
    def tearDown(self):
        if hasattr(self,'browser'):self.browser.close();self.pw.stop()
        if hasattr(self,'server'):self.server.shutdown();self.server.server_close()
        self.fixture.tearDown()
    def start(self,s):
        from playwright.sync_api import sync_playwright
        self.doc=self.fixture.ready(s);http.server.ThreadingHTTPServer.request_queue_size=128
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.workspace=Workspace(self.p);threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.pw=sync_playwright().start();self.browser=self.pw.chromium.launch(headless=True,**browser_options());self.page=self.browser.new_page(viewport=dict(width=1920,height=1080));self.page.goto(f'http://127.0.0.1:{self.server.server_address[1]}/renderer.html');self.page.wait_for_function('window.ready===true||window.renderError',timeout=120000)
        return self.page.evaluate('window.renderError||null')
    def test_each_rendered_state_has_one_safe_highlight_with_real_text_bounds(self):
        self.assertIsNone(self.start(composition()));self.assertTrue(self.doc['layoutPolicy']['required'])
        for f in list(range(30))+[18,2,29]:
            r=self.page.evaluate('async f=>window.courseRenderer.drawFrame(f)',f);rules=r['layoutReceipt'];focus=[r for r in rules if r['rule']=='enclose-text'];self.assertEqual(len(focus),1);self.assertFalse(any(r['violations'] for r in rules));self.assertEqual(len(focus[0]['bounds']),2)
    def test_reported_fixed_width_outline_is_rejected_before_delivery(self):
        s=composition();s['sceneGraph']['materials'][0]['data'].pop('rowFocus');s=expand(s)
        s['sceneGraph']['nodes'].append(dict(id='bad-old-outline',type='rect',sceneId='X',x=150,y=260,width=570,height=56,fill=None,stroke='#b78e43',lineWidth=3,enclosesTextIds=['paper-label-0','paper-value-0']))
        self.assertIn('边框进入文字范围',self.start(s))
    def test_saved_text_offset_cannot_move_value_through_outline(self):
        self.assertIsNone(self.start(composition()));d=copy.deepcopy(self.doc);next(f for f in d['fields'] if f['objectId']=='paper-value-0')['dx']=100
        self.page.evaluate('async d=>window.courseRenderer.load(d)',d)
        with self.assertRaisesRegex(Exception,'边框进入文字范围'):self.page.evaluate('async()=>window.courseRenderer.drawFrame(3)')
    def test_long_column_text_collision_is_rejected(self):
        self.assertIsNone(self.start(composition()));d=copy.deepcopy(self.doc);next(f for f in d['fields'] if f['objectId']=='paper-label-0')['text']='教育优惠条件需要逐项确认并且不能自动认定适用的具体说明'
        self.page.evaluate('async d=>window.courseRenderer.load(d)',d)
        with self.assertRaisesRegex(Exception,'同一行文字重叠'):self.page.evaluate('async()=>window.courseRenderer.drawFrame(3)')
    def test_footer_cannot_be_edited_through_a_character(self):
        s=composition();s['sceneGraph']=dict(nodes=[dict(id='visible-person',type='group',sceneId='X',x=500,y=300,width=250,height=350,textExclusion=True,children=[dict(id='silhouette',type='rect',width=250,height=350,fill='#7fa097')]),dict(id='footer',type='text',sceneId='X',x=520,y=700,fontSize=32,text='核对本次体验结果',fill='#193d3d')])
        self.assertIsNone(self.start(s));d=copy.deepcopy(self.doc);next(f for f in d['fields'] if f['objectId']=='footer')['dy']=-100;self.page.evaluate('async d=>window.courseRenderer.load(d)',d)
        with self.assertRaisesRegex(Exception,'文字侵入人物'):self.page.evaluate('async()=>window.courseRenderer.drawFrame(3)')
    def test_device_cannot_float_above_its_bound_table(self):
        s=composition();s['sceneGraph']=dict(materials=[dict(id='shop',kind='store-scene',sceneId='X',data=dict(view='interior'))]);self.assertIsNone(self.start(s));d=copy.deepcopy(self.doc)
        next(f for f in d['fields'] if f['objectId']=='shop-device0-0-root')['dy']=-40;self.page.evaluate('async d=>window.courseRenderer.load(d)',d)
        with self.assertRaisesRegex(Exception,'底座脱离支撑面'):self.page.evaluate('async()=>window.courseRenderer.drawFrame(3)')
    def test_space_view_keeps_table_and_devices_in_one_transform(self):
        s=composition();s['sceneGraph']=dict(materials=[dict(id='shop',kind='store-scene',sceneId='X',data=dict(view='isometric'))]);self.assertIsNone(self.start(s));receipt=self.page.evaluate('async()=>window.courseRenderer.drawFrame(3)')['layoutReceipt'];contacts=[x for x in receipt if x['rule']=='contact'];self.assertEqual(len(contacts),12);self.assertFalse(any(x['violations'] for x in contacts))
    def test_overlapping_current_row_windows_are_rejected(self):
        s=composition();s['sceneGraph']['materials'][0]['data']['rowFocus'][0]['endFrame']=20
        with self.assertRaisesRegex(ValueError,'窗口不能重叠'):expand(s)
    def test_direct_crop_of_unbranded_blue_master_is_blocked(self):
        staged=stage_company('S01',self.p,ROOT);s=composition();s['assets']=staged['assets'];s['sceneGraph']=dict(nodes=[dict(id='bare-staff',type='image',sceneId='X',assetId=staged['data']['headAsset'],x=100,y=200,width=500,height=650,crop=[0,0,.48,1])])
        with self.assertRaisesRegex(ValueError,'不能直接裁切无标原图'):self.fixture.ready(s)
    def test_uniform_mark_must_cover_the_whole_character_interval(self):
        staged=stage_company('S01',self.p,ROOT);s=composition();s['assets']=staged['assets'];s['sceneGraph']['materials']=[dict(id='staff',kind='actor',sceneId='X',data=staged['data'])];s=expand(s)
        next(n for n in s['sceneGraph']['nodes'][0]['children'] if n['id']=='staff-uniform-KG')['endFrame']=5
        with self.assertRaisesRegex(ValueError,'随角色显示'):self.fixture.ready(s)

    def test_both_blue_staff_and_manager_require_KG_while_coach_keeps_MyCoach(self):
        for identity in ['M1','S01','S02','COACH']:
            staged=stage_company(identity,self.p,ROOT);s=composition();s['assets']=staged['assets'];s['sceneGraph']['materials']=[dict(id='role',kind='actor',sceneId='X',data=staged['data'])];out=expand(s)
            self.assertEqual(out['contentAssets'][0]['description']['characterRole'],staged['role'])
            if identity!='COACH':
                s['sceneGraph']['materials'][0]['data'].pop('logoAsset')
                with self.assertRaisesRegex(ValueError,'KG'):expand(s)
            else:
                s['sceneGraph']['materials'][0]['data']['logoAsset']='anything'
                with self.assertRaisesRegex(ValueError,'不能加 KG'):expand(s)


if __name__=='__main__':unittest.main()
