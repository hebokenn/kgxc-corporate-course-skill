"""Chromium renders the actual scoped production-step painter, using metadata only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

from playwright.sync_api import sync_playwright

APP=Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'
SOURCE=(APP/'studio.js').read_text()
PAINTER=SOURCE[SOURCE.index('function paintProductionSteps('):SOURCE.index('async function pollProgress(')]
HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><link rel="stylesheet" href="/studio.css">
<main style="max-width:720px;margin:20px"><details id="production-steps"><summary>制作步骤</summary>
<p id="production-issue"></p><ul id="production-step-list"></ul></details></main>
<script>const $=id=>document.getElementById(id);const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};let lastNativeIssue=null;
'''+PAINTER+'''window.render=paintProductionSteps;</script></html>'''


class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/fixture.html':
            data=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data)
        else:super().do_GET()


class ProductionProgressUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(APP)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop();cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.context=self.browser.new_context(viewport=dict(width=760,height=800));self.page=self.context.new_page()
        self.page.goto('http://127.0.0.1:'+str(self.server.server_port)+'/fixture.html')
    def tearDown(self):self.context.close()
    def failure(self,identifier='old-helper'):
        return dict(id=identifier,key=identifier,label='保存稿件',subject='合成制作步骤',at=1000,error='旧版失败\n'+('<PRIVATE_TRACE>'*50),
                    count=1,critical=True,superseded_by=None,errors=[dict(at=1000,error='旧版失败\n'+('<PRIVATE_TRACE>'*50))])
    def test_current_task_and_unresolved_history_are_separate_and_raw_trace_starts_folded(self):
        self.page.evaluate('n=>render(n)',dict(available=True,stage='script',issue=None,items=[],history=[self.failure()]))
        self.assertIn('当前逐字稿',self.page.locator('#production-steps>summary').inner_text())
        self.assertTrue(self.page.locator('#production-issue').is_hidden())
        self.assertFalse(self.page.locator('[data-production-history]').evaluate('n=>n.open'))
        self.page.locator('#production-steps>summary').click();self.page.get_by_text('历史失败记录（1）',exact=True).click()
        self.assertIn('旧任务的未解决记录',self.page.locator('[data-production-history]').inner_text())
        self.assertFalse(self.page.locator('[data-failure-id]').evaluate('n=>n.open'))
        self.page.get_by_text('查看保留的错误与时间',exact=True).click()
        self.assertIn('<PRIVATE_TRACE>',self.page.locator('pre').inner_text());self.assertEqual(self.page.locator('PRIVATE_TRACE').count(),0)
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),760)
        self.page.evaluate('n=>render(n)',dict(available=True,stage='script',issue=None,items=[],history=[self.failure()]))
        self.assertTrue(self.page.locator('[data-production-history]').evaluate('n=>n.open'));self.assertTrue(self.page.locator('[data-failure-id]').evaluate('n=>n.open'))
    def test_actual_success_names_the_replacing_revision_and_new_failure_remains_current(self):
        history=self.failure();history['superseded_by']=dict(id='helper123',at=2000,workflow_revision=121,script_sha256='a'*64,basis='matching-candidate-source-revision')
        issue=self.failure('current-helper');issue.update(at=3000,error='当前真正失败')
        self.page.evaluate('n=>render(n)',dict(available=True,stage='script',issue=issue,items=[],history=[history]))
        self.assertIn('当前真正失败',self.page.locator('#production-issue').inner_text());self.assertFalse(self.page.locator('#production-issue').is_hidden())
        self.assertTrue(self.page.locator('#production-steps').evaluate('n=>n.open'))
        self.page.get_by_text('历史失败记录（1）',exact=True).click()
        self.assertIn('已被修订 121 的成功步骤替代',self.page.locator('[data-production-history]').inner_text())
        self.assertIn('helper123',self.page.locator('[data-production-history]').inner_text())
        self.assertIn('a'*64,self.page.locator('[data-production-history]').inner_text())


if __name__=='__main__':unittest.main()
