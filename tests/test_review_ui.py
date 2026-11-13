"""Real Chromium interactions with the production dialog; isolated UI fixtures only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
import json
import threading
import unittest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'skills/corporate-training-motion/workbench'
HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><link rel="stylesheet" href="/studio.css">
<header><div><h1>独立UI验证夹具</h1></div><button id="primary">阶段操作</button></header><section id="production-progress"></section>
<script type="module">
import {createReviewPanel} from '/review-panel.js';
import {createSourceCoveragePanel} from '/source-coverage.js';
const fresh=()=>({enabled:true,nodes:{script:{stage:'script',label:'讲稿',status:'awaiting_confirmation',fingerprint:'a'.repeat(64),run:{id:'fixture-round-1',fingerprint:'a'.repeat(64),status:'awaiting_confirmation',repaired:[{reason:'补充完整示范',path:'source/transcript.md'}],report:{passed:false,summary:'独立技术夹具：实际业务课未验收',items:[{id:'e',label:'关键视听证据',critical:true,verdict:'无法验证',reason:'没有连续音轨理解证据',evidence:[]}],methods:['script_read'],limitations:['截图不能证明完整视听']},events:[]},passed:false,user_confirmed:false,repairs:1,calls:2,usage:{totalTokens:1200},elapsed_ms:4500,policy:{max_repairs:3,max_calls:12},history:[],draft:''}}});
window.reviewFixture=JSON.parse(localStorage.getItem('fixture-review')||'null')||fresh();window.fixtureStage=localStorage.getItem('fixture-stage')||'script';window.events=[];window.errors=[];
const persist=()=>localStorage.setItem('fixture-review',JSON.stringify(window.reviewFixture));
const host=async(_action,args)=>{events.push({host_action:_action,...args});const node=reviewFixture.nodes[args.stage||window.fixtureStage||'script'];
 if(args.review_action==='draft'){node.draft=args.text;persist();}
 if(args.review_action==='dismiss'){node.run[node.status==='checking'?'progress_dismissed_at':'dismissed_at']='fixture-time';persist();}
 if(['continue','modify'].includes(args.review_action)){node.status='checking';node.run={...node.run,id:args.request_id,fingerprint:node.fingerprint,status:'checking',dismissed_at:undefined,events:[{at:'fixture-time',text:args.review_action+' 已实际请求'}]};node.calls++;persist();}
 return {ok:true,review:structuredClone(reviewFixture)};};
window.ui=createReviewPanel({getData:()=>({title:'技术验证课程',ai_review:reviewFixture,artifacts:window.fixtureArtifacts||{},source_coverage:window.fixtureCoverage}),getStage:()=>window.fixtureStage||'script',host,mediaURL:path=>'/course-file?path='+encodeURIComponent(path),
 action:async(name,args)=>{events.push({action:name,...args});
  if(name==='review-arrangement'){reviewFixture.policy={...reviewFixture.policy,review_arrangement:{mode:args.mode}};persist();}
  if(name==='source-coverage-confirm'){if(args.report_sha256!==fixtureCoverage.report_sha256)throw Error('对照报告已变更');fixtureCoverage.confirmed=true;}
  if(name==='review-approve'&&args.stage!=='storyboard'){
    if(args.source_coverage_declaration){if(args.source_coverage_declaration.report_sha256!==fixtureCoverage.report_sha256)throw Error('对照报告已变更');fixtureCoverage.confirmed=true;}
    const n=reviewFixture.nodes[args.stage];
    if(['pilot','final'].includes(args.stage)&&reviewFixture.policy?.review_arrangement?.mode==='visual_ai_user_audio'){
      const d=args.audio_declaration,a=n.user_audio_review;
      if(!d||JSON.stringify(d.artifact_sha256s)!==JSON.stringify(a.artifact_sha256s)||JSON.stringify(d.artifacts)!==JSON.stringify(a.artifacts)||d.listened_completely!==true||d.audio_and_sync_ok!==true)throw Error('听审声明未匹配全部媒体');
      if(!window.refuseConfirmation){a.status='confirmed';n.user_confirmed=true;}
    }else n.user_confirmed=true;persist();
  }return {ai_review:reviewFixture};},save:async()=>{},refresh:async()=>{},onApproved:async()=>events.push({action:'next-stage'}),onError:error=>errors.push(error.message),isBusy:()=>false});
window.coveragePanel=createSourceCoveragePanel({getData:()=>({source_coverage:window.fixtureCoverage}),action:async(name,args)=>{events.push({action:name,...args});if(name==='source-coverage-confirm')fixtureCoverage.confirmed=true;},host,onError:e=>errors.push(e.message)});
await ui.sync();window.ready=true;
</script></html>'''

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.startswith('/fixture.html'):
            data=HTML.encode();self.send_response(200);self.send_header('content-type','text/html; charset=utf-8');self.send_header('content-length',str(len(data)));self.end_headers();self.wfile.write(data)
        else:super().do_GET()

class ReviewUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(APP)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop();cls.server.shutdown();cls.server.server_close()
    def setUp(self):self.context=self.browser.new_context(viewport=dict(width=760,height=800));self.page=self.context.new_page();self.page.goto('http://127.0.0.1:'+str(self.server.server_port)+'/fixture.html');self.page.wait_for_function('window.ready')
    def tearDown(self):self.context.close()
    def media(self,stage='pilot',count=3):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('''async ({stage,count})=>{const n=structuredClone(reviewFixture.nodes.script);reviewFixture.nodes.script.user_confirmed=true;
          reviewFixture.policy={review_arrangement:{mode:'visual_ai_user_audio'}};n.stage=stage;n.passed=true;n.user_confirmed=false;n.run.id='media-round-'+stage;n.run.dismissed_at=undefined;
          n.run.report={passed:true,summary:'当前文字与画面可验证范围通过',items:[{id:'audio',label:'声音与音画配合',responsibility:'user_audio',verdict:'待用户听审',reason:'由用户完整播放后确认'}],methods:['frames','frame_sequence'],limitations:['画面序列不是连续播放']};
          const artifacts=Array.from({length:count},(_,i)=>({sha256:String(i+1).repeat(64),start_seconds:0,end_seconds:12.25+i}));
          n.user_audio_review={required:true,status:'pending',artifact_sha256s:artifacts.map(a=>a.sha256),artifacts,coverage:'all_stage_videos'};
          reviewFixture.nodes[stage]=n;window.fixtureStage=stage;window.fixtureArtifacts={[stage]:artifacts.map((a,i)=>({...a,path:'delivery/sample-'+i+'.mp4',available:true}))};
          localStorage.setItem('fixture-stage',stage);localStorage.setItem('fixture-review',JSON.stringify(reviewFixture));await ui.sync();ui.open();}''',dict(stage=stage,count=count))
        self.page.locator('dialog.ai-review-dialog[open]').wait_for()
    def coverage(self):
        self.page.evaluate("""async()=>{window.fixtureCoverage={required:true,current:true,confirmed:false,status:'awaiting_confirmation',report_sha256:'c'.repeat(64),script_sha256:'a'.repeat(64),sources_sha256:'b'.repeat(64),statistics:{total:2,covered:1,omitted:1,rate:50,critical:{total:1,covered:1,omitted:0},additions:1},report:{source_inventory:[{source_id:'SRC-1',read_scope:'全文',fully_read:true,unreadable:[]}],points:[{id:'P1',source_id:'SRC-1',locator:'第1段',source_quote:'先检查日期',critical:true,disposition:'retained',script_quotes:['先检查订单日期'],reason:'对应实际检查动作'},{id:'P2',source_id:'SRC-1',locator:'第2段',source_quote:'历史活动安排',critical:false,disposition:'omitted',script_quotes:[],reason:'已过期，不适用于本次任务'}],additions:[{id:'A1',script_quote:'现在请判断这个例子',location:'练习段',reason:'帮助应用',basis_kind:'example',basis:'虚构示例'}]}};reviewFixture.nodes.script.passed=true;await ui.sync();ui.open();}""")
    def test_source_comparison_is_explicit_and_can_share_the_existing_script_confirmation(self):
        self.coverage()
        checkbox=self.page.get_by_role('checkbox',name='已对照当前原件与讲稿，确认保留、合并、舍弃及新增内容和理由',exact=True)
        confirm=self.page.get_by_role('button',name='确认并进入下一阶段',exact=True)
        self.assertFalse(checkbox.is_checked());self.assertTrue(confirm.is_disabled())
        self.page.evaluate('ui.sync()');self.assertFalse(checkbox.is_checked())
        checkbox.check();confirm.click();self.page.wait_for_function('events.some(e=>e.action==="review-approve")')
        event=self.page.evaluate('events.find(e=>e.action==="review-approve")')
        self.assertEqual(event['source_coverage_declaration']['report_sha256'],'c'*64)
        self.assertEqual(event['source_coverage_declaration']['source'],'workbench-explicit-click')
        self.assertTrue(self.page.evaluate('fixtureCoverage.confirmed'))
    def test_source_report_change_resets_unsubmitted_declaration(self):
        self.coverage();checkbox=self.page.get_by_role('checkbox',name='已对照当前原件与讲稿，确认保留、合并、舍弃及新增内容和理由',exact=True);checkbox.check()
        self.page.evaluate("async()=>{fixtureCoverage.report_sha256='d'.repeat(64);await ui.sync();}")
        self.assertFalse(checkbox.is_checked());self.assertTrue(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).is_disabled())
        self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-approve")'))
    def test_source_panel_shows_coverage_omission_and_addition_and_never_confirms_on_close(self):
        self.coverage();self.page.get_by_role('button',name='关闭，稍后处理').click();self.page.evaluate('coveragePanel.open()')
        dialog=self.page.get_by_role('dialog',name='原件与逐字稿对照');text=dialog.inner_text()
        for value in ['50%','历史活动安排','已过期，不适用于本次任务','新增理由：帮助应用','虚构示例']:self.assertIn(value,text)
        self.assertTrue(dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth'))
        self.page.get_by_role('button',name='关闭，稍后确认',exact=True).click();self.assertFalse(self.page.evaluate('fixtureCoverage.confirmed'))
        self.page.evaluate('coveragePanel.open()');self.page.get_by_role('button',name='请AI生成／更新当前对照',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.host_action==="source-coverage")')
        self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-approve"||e.review_action==="continue")'))
    def test_fixed_ledger_shows_current_acceptance_and_continues_without_new_blind_review(self):
        self.page.evaluate("""async()=>{const n=reviewFixture.nodes.script;
          n.review_cycle={blind_review_completed:true,producer_only:true};
          n.issue_ledger=[{id:'script-1',status:'resolved',label:'示范缺少判断依据',learning_impact:'影响学员自行判断',acceptance_condition:'示范中可找到条件和结果',acceptance_reason:'当前稿件已补齐',acceptance_evidence:[{locator:'S02'}]}];
          await ui.sync();ui.open();}""")
        text=self.page.locator('dialog[open]').inner_text()
        self.assertIn('script-1 · 已解决',text);self.assertIn('当前稿件已补齐',text)
        self.assertTrue(self.page.locator('dialog[open]').evaluate('(d)=>d.scrollWidth<=d.clientWidth'))
        self.assertEqual(self.page.get_by_role('button',name='开始一次盲审',exact=True).count(),0)
        self.page.get_by_role('button',name='继续清单验收',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.review_action==="continue")')
        self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-approve"||e.action==="next-stage")'))
    def test_arrangement_is_saved_only_by_explicit_choice_and_never_confirms_content(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.get_by_role('button',name='审阅分工',exact=True).click()
        self.page.get_by_label('本课审阅安排',exact=True).select_option('visual_ai_user_audio')
        self.page.get_by_role('button',name='取消，不保存分工',exact=True).click()
        self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-arrangement")'))
        self.page.get_by_role('button',name='审阅分工',exact=True).click()
        self.assertEqual(self.page.get_by_label('本课审阅安排',exact=True).input_value(),'default_full_av')
        self.page.get_by_label('本课审阅安排',exact=True).select_option('visual_ai_user_audio')
        self.page.get_by_role('button',name='保存审阅分工',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.action==="review-arrangement")')
        event=self.page.evaluate('events.find(e=>e.action==="review-arrangement")')
        self.assertEqual(event['source']['kind'],'ui');self.assertTrue(event['source']['id']);self.assertTrue(event['evidence'])
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.script.user_confirmed'))
        self.assertFalse(self.page.evaluate('events.some(e=>["review-approve","next-stage"].includes(e.action))'))
    def test_user_audio_declaration_is_unchecked_and_closing_refresh_or_polling_never_approves(self):
        self.media()
        checkbox=self.page.get_by_role('checkbox',name='已完整播放当前全部小样，声音与音画配合无问题',exact=True)
        self.assertFalse(checkbox.is_checked());self.assertTrue(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).is_disabled())
        text=self.page.locator('dialog[open]').inner_text();self.assertIn('AI文字与画面审阅通过',text);self.assertIn('画面序列不等于连续播放',text)
        for i in range(3):self.assertIn(str(i+1)*64,text)
        self.assertEqual(self.page.get_by_role('link',name='打开这一版完整视频').count(),3)
        checkbox.check();self.page.evaluate('ui.sync()');self.assertTrue(checkbox.is_checked())
        self.page.get_by_role('button',name='关闭，稍后处理').click();self.page.get_by_role('button',name='检查记录与问题清单',exact=True).click();self.assertFalse(checkbox.is_checked())
        checkbox.check();self.page.reload();self.page.wait_for_function('window.ready');self.page.get_by_role('button',name='检查记录与问题清单',exact=True).click();self.assertFalse(checkbox.is_checked())
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.pilot.user_confirmed'));self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-approve")'))
    def test_producer_audio_mode_removes_listening_approval_and_keeps_critical_unknown_visible(self):
        self.media('pilot',1)
        self.page.evaluate('''async()=>{reviewFixture.policy.review_arrangement.mode='visual_ai_producer_audio';const n=reviewFixture.nodes.pilot;
          n.passed=false;n.user_audio_review={required:false,status:'user_approval_not_required'};
          n.run.report={passed:false,summary:'自动技术事实已完成，关键听感尚未验证',items:[{id:'ending',label:'末句与结尾',responsibility:'producer_audio_unverified',critical:true,verdict:'无法验证',reason:'未执行连续听审'}],
            methods:['frames','automatic_audio_technical'],inspection:{media:[{sha256:'1'.repeat(64),audio_technical:{status:'passed'}}]}};
          await ui.sync();ui.open();}''')
        self.assertEqual(self.page.get_by_role('checkbox').count(),0)
        text=self.page.locator('dialog[open]').inner_text();self.assertIn('无需你逐句试听或审核配音',text)
        self.assertIn('未执行连续听审',text);self.assertIn('关键未知继续阻断正式放行',text);self.assertIn('通过（仅技术范围）',text)
        self.assertIn('无法验证 · 末句与结尾',text);self.assertNotIn('待你完整听审并确认',text)
        self.assertFalse(self.page.evaluate('events.some(e=>["review-approve","next-stage"].includes(e.action))'))
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.pilot.user_confirmed'))
    def test_producer_audio_arrangement_is_explicit_and_does_not_record_a_listening_receipt(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.get_by_role('button',name='审阅分工',exact=True).click()
        self.page.get_by_label('本课审阅安排',exact=True).select_option('visual_ai_producer_audio')
        self.page.get_by_role('button',name='保存审阅分工',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.action==="review-arrangement")')
        event=self.page.evaluate('events.find(e=>e.action==="review-arrangement")')
        self.assertEqual(event['mode'],'visual_ai_producer_audio');self.assertEqual(event['source']['kind'],'ui')
        self.assertFalse(self.page.evaluate('events.some(e=>["review-approve","next-stage"].includes(e.action)||e.audio_declaration)'))
    def test_one_explicit_pilot_confirmation_binds_every_sha_and_complete_duration(self):
        self.media();self.page.get_by_role('checkbox',name='已完整播放当前全部小样，声音与音画配合无问题',exact=True).check()
        self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).click();self.page.wait_for_function('events.some(e=>e.action==="next-stage")')
        event=self.page.evaluate('events.find(e=>e.action==="review-approve")');declaration=event['audio_declaration']
        self.assertEqual(declaration['artifact_sha256s'],[str(i+1)*64 for i in range(3)])
        self.assertEqual(declaration['artifacts'],[dict(sha256=str(i+1)*64,start_seconds=0,end_seconds=12.25+i) for i in range(3)])
        self.assertEqual(declaration['coverage'],'all_stage_videos');self.assertTrue(declaration['listened_completely']);self.assertTrue(declaration['audio_and_sync_ok']);self.assertEqual(declaration['source']['kind'],'ui')
        self.assertEqual(self.page.evaluate('events.filter(e=>e.action==="review-approve").length'),1);self.assertEqual(self.page.evaluate('events.filter(e=>e.action==="next-stage").length'),1)
    def test_final_uses_full_movie_declaration_and_keeps_audio_outside_ai_pass(self):
        self.media('final',1);self.assertIn('音轨仍按用户听审状态处理',self.page.locator('dialog[open]').inner_text())
        self.page.get_by_role('checkbox',name='已完整播放当前全部成片，声音与音画配合无问题',exact=True).check()
        self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).click();self.page.wait_for_function('events.some(e=>e.action==="next-stage")')
        self.assertEqual(self.page.evaluate('events.find(e=>e.action==="review-approve").audio_declaration.artifact_sha256s'),['1'*64])
    def test_missing_or_unknown_media_range_disables_declaration(self):
        self.media();self.page.evaluate('reviewFixture.nodes.pilot.user_audio_review.artifacts[2].end_seconds=null;ui.sync()')
        self.assertTrue(self.page.get_by_role('checkbox').is_disabled());self.assertTrue(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).is_disabled())
        self.assertIn('不能作听审声明',self.page.locator('dialog[open]').inner_text())
        self.page.evaluate('reviewFixture.nodes.pilot.user_audio_review.artifacts=[];ui.sync()')
        self.assertTrue(self.page.get_by_role('checkbox').is_disabled());self.assertFalse(self.page.evaluate('events.some(e=>e.action==="review-approve")'))
    def test_media_version_change_or_stale_report_invalidates_checked_declaration(self):
        self.media();self.page.get_by_role('checkbox').check()
        self.page.evaluate('''async()=>{const a=reviewFixture.nodes.pilot.user_audio_review;a.artifact_sha256s[0]='a'.repeat(64);a.artifacts[0].sha256='a'.repeat(64);a.status='stale';await ui.sync();}''')
        self.assertFalse(self.page.get_by_role('checkbox').is_checked());self.assertTrue(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).is_disabled())
        self.assertIn('先前听审对应旧媒体',self.page.locator('dialog[open]').inner_text())
        self.page.evaluate('reviewFixture.nodes.pilot.status="stale";ui.sync()');self.assertTrue(self.page.get_by_role('checkbox').is_disabled())
    def test_audio_problem_feedback_is_saved_without_declaration_or_stage_advance(self):
        self.media();self.page.get_by_role('textbox',name='审阅重点或修改意见').fill('第二个小样末尾有半句话，先保留问题')
        self.page.get_by_role('button',name='保存声音问题，不确认',exact=True).click();self.page.wait_for_function('events.some(e=>e.action==="feedback")')
        self.assertEqual(self.page.evaluate('events.find(e=>e.action==="feedback").text'),'第二个小样末尾有半句话，先保留问题')
        self.assertFalse(self.page.evaluate('events.some(e=>["review-approve","next-stage"].includes(e.action)||e.review_action==="modify")'))
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.pilot.user_confirmed'));self.assertEqual(self.page.evaluate('reviewFixture.nodes.pilot.user_audio_review.status'),'pending')
    def test_server_nonconfirmation_never_calls_next_stage(self):
        self.media();self.page.evaluate('window.refuseConfirmation=true');self.page.get_by_role('checkbox').check();self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).click()
        self.page.wait_for_function('errors.length===1');self.assertFalse(self.page.evaluate('events.some(e=>e.action==="next-stage")'));self.assertTrue(self.page.locator('dialog[open]').is_visible())
    def test_default_media_mode_preserves_existing_single_confirmation_without_audio_declaration(self):
        self.media('pilot',1);self.page.evaluate('reviewFixture.policy.review_arrangement.mode="default_full_av";ui.sync()')
        self.assertEqual(self.page.get_by_role('checkbox').count(),0);self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).click();self.page.wait_for_function('events.some(e=>e.action==="next-stage")')
        self.assertFalse(self.page.evaluate('"audio_declaration" in events.find(e=>e.action==="review-approve")'))
    def test_actual_studio_only_exposes_readonly_evidence_and_every_complete_pilot_video(self):
        self.media();fixture=self.page.evaluate('({ai_review:structuredClone(reviewFixture),artifacts:structuredClone(fixtureArtifacts)})')
        data=dict(title='完整媒体工作台夹具',course_id='ui-synthetic',course_path='/synthetic/course',revision=1,ai_review=fixture['ai_review'],artifacts=fixture['artifacts'],
            plan=dict(units=[],decisions=[]),sources=[],sections=[],editor=dict(text='',changed=False),gates=[dict(id='storyboard',status='confirmed'),dict(id='pilot',status='ready',ready=True)],
            jobs=[],feedback=[],proposals=[],production_preferences=dict(required=False),sampling=dict(selections=[]),undo_available=False)
        mutations=[]
        self.page.route('**/api/studio',lambda route:route.fulfill(content_type='application/json',body=json.dumps(data)))
        def mutation(route):
            mutations.append(route.request.url);route.fulfill(content_type='application/json',body=json.dumps(data))
        self.page.route('**/api/studio/*',mutation)
        self.page.route('**/api/activity',lambda route:route.fulfill(content_type='application/json',body='{}'))
        self.page.route('**/course-file?*',lambda route:route.abort())
        self.page.add_init_script('''window.uiHostEvents=[];window.addEventListener('message',e=>{if(e.data?.type!=='kgxc-editor-request')return;
          uiHostEvents.push(e.data);window.postMessage({type:'kgxc-editor-result',id:e.data.id,result:{review:JSON.parse(localStorage.getItem('fixture-review'))}},location.origin);});''')
        base='http://127.0.0.1:'+str(self.server.server_port)
        self.page.goto(base+'/studio.html?'+urlencode(dict(stage='pilot',parentOrigin=base)))
        self.page.wait_for_function('document.getElementById("course-title").textContent==="完整媒体工作台夹具"')
        self.assertEqual(self.page.get_by_label('完整听审小样',exact=False).count(),3)
        for i in range(3):
            video=self.page.get_by_label('完整听审小样 '+str(i+1),exact=True)
            self.assertIn('sample-'+str(i)+'.mp4',video.get_attribute('src'));self.assertNotIn('#t=',video.get_attribute('src'))
        self.page.evaluate('window.postMessage({type:"kgxc-editor-host",running:false},location.origin)')
        self.page.wait_for_function('uiHostEvents.some(e=>e.review_action==="sync")')
        self.assertEqual(self.page.locator('dialog.ai-review-dialog[open]').count(),0)
        self.assertTrue(self.page.locator('#primary').is_hidden())
        self.page.get_by_text('课程设置与记录',exact=True).click()
        self.page.get_by_role('button',name='检查记录与问题清单',exact=True).click()
        self.assertTrue(self.page.locator('dialog.ai-review-dialog[open]').is_visible())
        self.assertEqual(self.page.get_by_role('checkbox').count(),0)
        self.assertEqual(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).count(),0)
        self.assertEqual(mutations,[])
        self.assertFalse(self.page.evaluate('uiHostEvents.some(e=>e.action==="stage"||e.action==="deliver")'))
    def test_close_keeps_pending_input_and_reopen_after_refresh_without_approval(self):
        self.assertTrue(self.page.locator('dialog').is_visible());self.assertEqual(self.page.get_by_role('button',name='确认并进入下一阶段').count(),0)
        self.page.get_by_role('textbox',name='审阅重点或修改意见').fill('先检查身份转变，再核对完整示范')
        self.page.get_by_role('button',name='关闭，稍后处理').click();self.page.wait_for_function('!document.querySelector("dialog").open')
        self.page.reload();self.page.wait_for_function('window.ready');self.assertEqual(self.page.locator('dialog[open]').count(),0)
        self.page.get_by_role('button',name='检查记录与问题清单',exact=True).click()
        self.assertEqual(self.page.get_by_role('textbox',name='审阅重点或修改意见').input_value(),'先检查身份转变，再核对完整示范')
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.script.user_confirmed'));self.assertEqual(self.page.evaluate('reviewFixture.nodes.script.calls'),2)
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'),False)
    def test_continue_and_modify_buttons_send_real_distinct_operations(self):
        self.page.get_by_role('button',name='开始一次盲审',exact=True).click();self.page.wait_for_function('events.some(e=>e.review_action==="continue")')
        self.assertEqual(self.page.evaluate('reviewFixture.nodes.script.calls'),3)
        self.page.evaluate('reviewFixture.nodes.script.status="awaiting_confirmation";reviewFixture.nodes.script.run.status="awaiting_confirmation";ui.sync()')
        self.page.locator('dialog[open]').wait_for()
        self.page.get_by_role('textbox',name='审阅重点或修改意见').fill('把空表改成有过程和结果的完整示例')
        self.page.get_by_role('button',name='按意见修改并验收',exact=True).click();self.page.wait_for_function('events.some(e=>e.review_action==="modify")')
        self.assertEqual(self.page.evaluate('events.find(e=>e.review_action==="modify").instruction'),'把空表改成有过程和结果的完整示例')
        self.assertEqual(self.page.evaluate('reviewFixture.nodes.script.calls'),4)
    def test_valid_summary_only_advances_after_explicit_confirmation(self):
        self.page.evaluate('reviewFixture.nodes.script.passed=true;reviewFixture.nodes.script.run.report.passed=true;ui.sync()')
        self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).click();self.page.wait_for_function('events.some(e=>e.action==="next-stage")')
        self.assertTrue(self.page.evaluate('reviewFixture.nodes.script.user_confirmed'))
        self.assertFalse(self.page.evaluate('events.some(e=>e.action==="deliver")'))
    def test_hold_and_repair_limit_do_not_offer_unbounded_repair(self):
        self.page.evaluate('reviewFixture.hold={held:true,reason:"先修插件，再课程"};ui.sync()')
        self.assertTrue(self.page.get_by_role('button',name='集中修复并验收',exact=True).is_disabled())
        self.assertTrue(self.page.get_by_role('button',name='开始一次盲审',exact=True).is_disabled())
        self.page.evaluate('reviewFixture.hold.held=false;reviewFixture.nodes.script.status="limit_reached";ui.sync()')
        self.assertTrue(self.page.get_by_role('button',name='集中修复并验收',exact=True).is_disabled())
        self.assertTrue(self.page.get_by_role('button',name='按意见修改并验收',exact=True).is_disabled())
        self.assertEqual(self.page.evaluate('reviewFixture.nodes.script.calls'),2)
    def test_stale_report_displays_the_reviewed_input_and_current_version_separately(self):
        self.page.evaluate('reviewFixture.nodes.script.status="stale";reviewFixture.nodes.script.fingerprint="b".repeat(64);ui.sync()')
        self.assertIn('本轮输入 aaaaaaaaaaaa',self.page.locator('dialog').inner_text())
        self.assertIn('当前输入 bbbbbbbbbbbb',self.page.locator('dialog').inner_text())
    def test_new_round_retires_old_summary_and_preserves_both_inputs(self):
        self.page.get_by_role('textbox',name='审阅重点或修改意见').fill('旧轮尚未提交的意见')
        self.page.evaluate('reviewFixture.nodes.script.run={...reviewFixture.nodes.script.run,id:"replacement-round",status:"checking"};reviewFixture.nodes.script.status="checking";reviewFixture.nodes.script.draft="新轮的人工意见";ui.sync()')
        self.page.wait_for_function('!document.querySelector("dialog").open')
        self.assertTrue(self.page.evaluate('events.some(e=>e.review_action==="draft"&&e.run_id==="fixture-round-1"&&e.text==="旧轮尚未提交的意见")'))
        self.page.evaluate('reviewFixture.nodes.script.draft="新轮的人工意见";reviewFixture.nodes.script.status="awaiting_confirmation";reviewFixture.nodes.script.run.status="awaiting_confirmation";ui.sync()')
        self.page.locator('dialog[open]').wait_for()
        self.assertIn('审阅版本 replacem',self.page.locator('dialog').inner_text())
        self.assertEqual(self.page.get_by_role('textbox',name='审阅重点或修改意见').input_value(),'新轮的人工意见')
        self.assertEqual(self.page.evaluate('errors'),[])
    def test_immediate_refresh_preserves_input_before_debounced_server_save(self):
        self.page.get_by_role('textbox',name='审阅重点或修改意见').fill('刷新前刚输入的意见')
        self.page.reload();self.page.wait_for_function('window.ready')
        self.assertEqual(self.page.get_by_role('textbox',name='审阅重点或修改意见').input_value(),'刷新前刚输入的意见')
    def test_review_launch_waits_for_workflow_to_start_the_initial_review(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('async()=>{reviewFixture.nodes.script.run={};reviewFixture.nodes.script.status="not_started";await ui.sync();}')
        self.assertTrue(self.page.get_by_role('button',name='检查记录与问题清单',exact=True).is_disabled())
        self.assertFalse(self.page.evaluate('events.some(e=>e.review_action==="continue")'))
        self.assertEqual(self.page.evaluate('reviewFixture.nodes.script.calls'),2)
        self.assertEqual(self.page.evaluate('errors'),[])
    def test_closing_progress_still_opens_one_summary_when_the_round_finishes(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('async()=>{reviewFixture.nodes.script.run={...reviewFixture.nodes.script.run,id:"new-running-round",dismissed_at:undefined,status:"checking"};reviewFixture.nodes.script.status="checking";await ui.sync();ui.open()}')
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('reviewFixture.nodes.script.status="awaiting_confirmation";reviewFixture.nodes.script.run.status="awaiting_confirmation";ui.sync()')
        self.page.locator('dialog[open]').wait_for()
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('ui.sync()');self.assertEqual(self.page.locator('dialog[open]').count(),0)

    def test_storyboard_shows_visual_findings_and_learner_understanding_before_continuing(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('''async()=>{const n=structuredClone(reviewFixture.nodes.script);n.stage='storyboard';n.run.id='storyboard-round';n.run.repaired=[];n.run.dismissed_at=undefined;
          n.run.report={passed:false,summary:'只评当前分镜，不代表已经看过动画',learner:{about:'订单核对',what_it_said:'核对后再交接',learned:['先检查再操作'],confusions:['第二个要点为什么画面没有变化']},findings:[{id:'visual-1',severity:'major',problem:'第二段旁白推进到异常处理，画面仍停在完整清单',evidence:[{locator:'片段S02 / beat2'}]}],items:[],agent_audit:{id:'fresh-reviewer',role:'reviewer',isolated:true,read_only:true},supervision:{summary:'执行事件已核对，未改课程'}};
          reviewFixture.nodes.storyboard=n;window.fixtureStage='storyboard';await ui.sync();ui.open();}''')
        self.page.locator('dialog[open]').wait_for()
        text=self.page.locator('dialog').inner_text()
        self.assertIn('全课分镜与画面节奏',text)
        self.assertIn('学到了什么：先检查再操作',text)
        self.assertIn('第二段旁白推进到异常处理',text)
        self.assertEqual(self.page.get_by_role('button',name='确认并进入下一阶段',exact=True).count(),0)
        self.page.get_by_role('button',name='开始一次盲审',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.stage==="storyboard"&&e.review_action==="continue")')
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.storyboard.user_confirmed'))

    def test_passed_storyboard_keeps_existing_choices_without_inventing_user_approval(self):
        self.page.get_by_role('button',name='关闭，稍后处理').click()
        self.page.evaluate('''async()=>{const n=structuredClone(reviewFixture.nodes.script);n.stage='storyboard';n.passed=true;n.user_confirmed=false;n.run.id='storyboard-passed';n.run.dismissed_at=undefined;n.run.report.passed=true;
          reviewFixture.nodes.storyboard=n;window.fixtureStage='storyboard';await ui.sync();ui.open();}''')
        self.page.get_by_role('button',name='按既有选择继续制作',exact=True).click()
        self.page.wait_for_function('events.some(e=>e.action==="next-stage")')
        self.assertFalse(self.page.evaluate('reviewFixture.nodes.storyboard.user_confirmed'))
        self.assertEqual(self.page.evaluate('errors'),[])

    def test_preflight_failure_keeps_reservation_without_claiming_model_or_zero_usage(self):
        self.page.evaluate('''async()=>{const n=reviewFixture.nodes.script;n.calls=8;n.status='failed';n.run.status='failed';n.run.calls=[{key:'check-0',role:'reviewer',status:'failed',execution_phase:'preflight',model_invoked:false,usage_status:'not_invoked',usage:{}}];await ui.sync();}''')
        self.assertIn('调用预算 8/12 次',self.page.locator('dialog').inner_text())
        self.page.get_by_text('详细验收清单、检查范围与历史证据',exact=True).click()
        text=self.page.locator('dialog').inner_text()
        self.assertIn('模型未调用',text);self.assertIn('用量未返回',text)
        self.assertNotRegex(text,r'(?<![\d,])0 tokens')

    def test_temporary_unlimited_counts_shows_totals_and_keeps_actual_unknown_and_not_invoked_usage(self):
        self.page.evaluate('''async()=>{reviewFixture.policy={unlimited_counts:true};const n=reviewFixture.nodes.script;
          n.policy={unlimited_counts:true,max_calls:null};n.calls=21;n.repairs=5;n.usage={totalTokens:603513};
          n.run.calls=[{role:'reviewer',status:'failed',execution_phase:'preflight',model_invoked:false,usage_status:'not_invoked',usage:{}},
            {role:'producer',status:'failed',execution_phase:'unknown',model_invoked:null,usage:{}},
            {role:'supervisor',status:'complete',execution_phase:'model',model_invoked:true,usage:{totalTokens:5}}];await ui.sync();}''')
        text=self.page.locator('dialog').inner_text()
        self.assertIn('本轮调用/返修次数暂不限，累计21调用/5返修',text)
        self.assertIn('603,513 tokens',text);self.assertNotIn('调用预算 21/',text)
        self.assertNotRegex(text,r'/(?:null|undefined)')
        self.page.get_by_text('详细验收清单、检查范围与历史证据',exact=True).click()
        text=self.page.locator('dialog').inner_text()
        for expected in ['模型未调用','调用状态按原记录核对','用量未返回','模型已调用','5 tokens']:
            self.assertIn(expected,text)
        self.assertNotIn('免费',text);self.assertNotRegex(text,r'(?<![\d,])0 tokens')

    def test_restoring_finite_counts_preserves_original_limits_totals_and_usage(self):
        self.page.evaluate('''async()=>{reviewFixture.policy={unlimited_counts:true};const n=reviewFixture.nodes.script;
          n.policy={unlimited_counts:true,max_calls:12,max_repairs:3};n.calls=21;n.repairs=5;await ui.sync();
          reviewFixture.policy.unlimited_counts=false;await ui.sync();}''')
        text=self.page.locator('dialog').inner_text()
        self.assertIn('自动返修 5/3 轮 · 调用预算 21/12 次',text)
        self.assertIn('1,200 tokens',text);self.assertIn('预算次数包含已预留尝试',text)
        self.assertNotIn('次数暂不限',text)
        self.assertEqual(self.page.evaluate('[reviewFixture.nodes.script.calls,reviewFixture.nodes.script.repairs]'),[21,5])

if __name__=='__main__':unittest.main()
