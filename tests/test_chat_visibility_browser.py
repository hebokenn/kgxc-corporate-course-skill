"""Real Chromium/React regression for the chat toggle; no model requests.
Run with KGXC_REACT_TEST_ROOT pointing to a directory containing node_modules
with react@18 and react-dom@18. This is a client UI harness, not a DSH desktop test.
"""
import os
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
import unittest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
REACT=Path(os.environ.get('KGXC_REACT_TEST_ROOT','/tmp/dsh-ui'))/'node_modules'
HTML='''<!doctype html><meta charset="utf-8"><style>html,body,#app{height:100%;margin:0}</style>
<div id="app"></div><script src="/react.js"></script><script src="/react-dom.js"></script><script>
window.__ModuleLoader__={load:spec=>{
 const require=()=>React;
 require.async=async()=>({mountNative:host=>{
   host.shadowRoot.innerHTML='<style>:host{position:relative}main{height:2400px;background:#fafbfc}header{position:sticky;top:0;background:white;padding:30px}</style><main><header>逐字稿课程界面</header><p>长课程内容</p></main>';
   return {receive:()=>{},dispose:()=>{}};
 }});
 window.plugin=spec.factory(require);
}};
window.fetch=async(url,options)=>{const data=options?.body?JSON.parse(options.body):{};
 const value=url.endsWith('/meta')?{token:'test'}:url.endsWith('/context')?{course_path:'/test/course'}:url.endsWith('/view')?{resource_base:location.origin}:url.endsWith('/courses')?{courses:[{course_id:'1',course_path:'/test/course',title:'测试课程'}]}:data.name==='kgxc_course_resume'?{course_path:'/test/course',workbench_url:location.origin,workflow:{stage:'script'}}:{};
 return {ok:true,json:async()=>value};};
</script><script src="/client.js"></script><script>
const entries=[],ctx={effect:fn=>fn(),slots:{inject:(name,fn)=>fn(),register:(options,component)=>{entries.push({options,component});return()=>{};}},uiWorkspace:{selection:{getSnapshot:()=>({sessionId:'test'})}}};
plugin.apply(ctx);
const panel=entries.find(e=>e.options.name==='kgxc.workspace').component;
const props={ctx,sessionId:'test',useSession:()=>({openState:'ready'}),useSessionStatus:fn=>fn(new Map([['test',{}]])),renderSlot:()=>React.createElement('div',{'data-testid':'native-chat'},'原生 AI 对话')};
ReactDOM.createRoot(document.getElementById('app')).render(React.createElement(panel,props));
</script>'''

class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  paths={'/client.js':ROOT/'plugin/client.js','/react.js':REACT/'react/umd/react.development.js','/react-dom.js':REACT/'react-dom/umd/react-dom.development.js'}
  body=paths[self.path].read_bytes() if self.path in paths else HTML.encode()
  self.send_response(200);self.send_header('Content-Type','text/javascript' if self.path in paths else 'text/html; charset=utf-8');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass

@unittest.skipUnless((REACT/'react/umd/react.development.js').exists(),'Install React 18 test assets; see module docstring')
class ChatVisibilityBrowserTests(unittest.TestCase):
 def test_persistent_toolbar_reopens_chat_after_collapse_reload_and_narrow_resize(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1300,'height':820})
    page.goto(f'http://127.0.0.1:{server.server_port}');toggle=page.locator('.kgxc-chat-toggle')
    page.locator('kgxc-studio-view').wait_for()
    for width in [1300,680]:
     page.set_viewport_size({'width':width,'height':820})
     for _ in range(3):
      self.assertEqual(toggle.get_attribute('aria-expanded'),'true');toggle.click()
      self.assertEqual(toggle.inner_text(),'打开 AI 对话');self.assertTrue(toggle.is_visible())
      self.assertEqual(page.locator('.kgxc-chat').count(),0)
      # Scroll the real overflow region; the control is not its child or overlay.
      page.locator('kgxc-studio-view').evaluate('(el)=>el.scrollTop=1500')
      box=toggle.bounding_box();self.assertGreaterEqual(box['x'],0);self.assertLessEqual(box['x']+box['width'],width)
      self.assertTrue(toggle.evaluate('(el)=>el.contains(document.elementFromPoint(el.getBoundingClientRect().x+5,el.getBoundingClientRect().y+5))'))
      toggle.click();self.assertTrue(page.locator('[data-testid=native-chat]').is_visible())
    toggle.click();page.reload();toggle.wait_for();self.assertEqual(toggle.inner_text(),'打开 AI 对话');toggle.click()
    self.assertTrue(page.locator('[data-testid=native-chat]').is_visible());browser.close()
  finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
