"""Actual shared Studio mounted into the plugin DOM, backed by a real course."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'skills/corporate-training-motion/workbench'),str(ROOT/'skills/corporate-training-motion/scripts')]
from backend import Handler as BackendHandler,Workspace
from workflow import Course,atomic,read
from studio import Studio
from script_editor import ScriptEditor
from ai_review import Review
from test_branch_workflow import design
from authoring import init_project

HTML='''<!doctype html><meta charset="utf-8"><script>
window.__ModuleLoader__={load:spec=>{
 if(spec.chunk){window.nativeModule=spec.factory();return;}
 const require=()=>({});require.async=async name=>{if(name!=='./client.studio-native.js')throw Error('unexpected chunk');return nativeModule;};
 const plugin=spec.factory(require);plugin.apply({effect:()=>{},slots:{inject:()=>{}}});
}};</script><script src="/client.studio-native.js"></script><script src="/plugin-client.js"></script>
<script type="module">
const access=await (await fetch('/fixture-review')).json();
const node=document.createElement('kgxc-studio-view');node.id='native';node.setAttribute('class','kgxc-frame kgxc-native');const wrapper=document.createElement('div');wrapper.style.cssText='display:flex;width:620px;height:800px';document.body.append(wrapper);
node.setAttribute('session-id','fixture-session');node.setAttribute('course-path',access.course_path);
node.setAttribute('src',location.origin+'/studio.html?stage=script&parentOrigin='+encodeURIComponent(location.origin));
node.addEventListener('kgxc-message',async event=>{const data=event.detail;
 if(data.type==='kgxc-editor-ready')node.contentWindow.postMessage({type:'kgxc-editor-host',running:false},location.origin);
 if(data.type==='kgxc-studio-state')window.fixtureReady=true;
 if(data.type==='kgxc-editor-request'){
  const response=await fetch('/fixture-review'),result=await response.json();node.contentWindow.postMessage({type:'kgxc-editor-result',id:data.id,result},location.origin);
 }
});wrapper.append(node);
</script>'''


class Handler(BackendHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/native-fixture.html':
            value=HTML.encode();self.send_response(200);self.send_header('content-type','text/html; charset=utf-8');self.send_header('content-length',str(len(value)));self.end_headers();self.wfile.write(value)
        elif self.path=='/client.studio-native.js':self.file(ROOT/'plugin/client.studio-native.js')
        elif self.path=='/plugin-client.js':self.file(ROOT/'plugin/client.js')
        elif self.path=='/api/kgxc-course/meta':self.json(dict(ok=True,token='test'))
        elif self.path=='/fixture-review':self.json(dict(ok=True,course_path=str(self.space.root),review=Review(Course(self.space.root)).view()))
        else:super().do_GET()
    def do_POST(self):
        if self.path=='/api/kgxc-course/view':
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if value.get('course_path')!=str(self.space.root):return self.json(dict(error='wrong course'),403)
            return self.json(dict(ok=True,resource_base=''))
        return super().do_POST()

class NativeStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build_native_client.py')],check=True,capture_output=True)
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.pw.stop()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();p=self.root/'project'
        init_project(p,ROOT/'skills/corporate-training-motion')
        self.course=Course(self.root);self.course.init('插件直接挂载技术夹具');design(self.course);self.course.confirm('outline',self.course.status()['revision'],'技术结构确认')
        self.space=SimpleNamespace(root=self.root,project=p,file=p/'workbench.json')
        Studio(self.space).save_sections([dict(unit_id='U',body='核对订单后检查编码。示例：订单A写P12，实物也是P12，记录一致，再交接。')],self.course.status()['revision'],official=True)
        review=Review(self.course);review.ensure();review.hold(True,'独立界面验证，不调用模型')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.workspace=Workspace(self.root)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.context=self.browser.new_context(viewport=dict(width=900,height=900));self.page=self.context.new_page()
        self.page.goto('http://127.0.0.1:'+str(self.server.server_port)+'/native-fixture.html');self.page.wait_for_function('window.fixtureReady')
    def tearDown(self):self.context.close();self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def test_actual_script_and_review_controls_render_inside_plugin_without_a_visible_iframe(self):
        editor=self.page.get_by_role('textbox',name='当前章节逐字稿');self.assertTrue(editor.is_visible());self.assertIn('订单A',editor.input_value())
        self.page.get_by_role('button',name='AI 审阅 · 课程已暂停',exact=True).wait_for()
        self.assertEqual(self.page.locator('iframe:visible').count(),0)
        self.assertGreater(self.page.locator('#native').bounding_box()['width'],600)
        self.assertGreater(editor.bounding_box()['width'],300)
        self.assertFalse(self.page.evaluate('document.getElementById("native").scrollWidth>document.getElementById("native").clientWidth'))
    def test_native_manual_edit_saves_the_actual_course_and_keeps_official_script(self):
        before=self.course.script()['text'];editor=self.page.get_by_role('textbox',name='当前章节逐字稿');manual=editor.input_value()+'\n人工新增，请保留。';editor.fill(manual)
        self.page.wait_for_function('document.querySelector("#native").shadowRoot.getElementById("save-status").textContent==="已保存"')
        self.assertIn('人工新增，请保留。',ScriptEditor(self.space).read()['text']);self.assertEqual(self.course.script()['text'],before)
        self.assertEqual(sum(n.get('calls',0) for n in Review(self.course).load()['nodes'].values()),0)
    def test_native_refresh_preserves_a_just_typed_human_edit(self):
        editor=self.page.get_by_role('textbox',name='当前章节逐字稿');manual=editor.input_value()+'\n刚输入的人工内容也要保留。';editor.fill(manual)
        self.page.reload();self.page.wait_for_function('window.fixtureReady')
        self.assertEqual(self.page.get_by_role('textbox',name='当前章节逐字稿').input_value(),manual)
    def test_native_final_player_reads_the_actual_encoded_video(self):
        media=self.root/'delivery/test.mp4';media.parent.mkdir(exist_ok=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=1','-c:v','libx264','-y',str(media)],check=True)
        state=read(self.course.state_file);state['artifacts']['final']=['../delivery/test.mp4'];atomic(self.course.state_file,state)
        self.page.evaluate('document.getElementById("native").setAttribute("src",location.origin+"/studio.html?stage=final&parentOrigin="+encodeURIComponent(location.origin))')
        self.page.wait_for_function('document.getElementById("native").shadowRoot.querySelector("video")?.readyState>=2')
        video=self.page.locator('video');self.assertEqual(video.evaluate('v=>v.videoWidth'),320);self.assertAlmostEqual(video.evaluate('v=>v.duration'),1,places=1)

if __name__=='__main__':unittest.main()
