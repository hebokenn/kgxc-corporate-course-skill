"""Exercise actual editor UI and export in an already prepared disposable sample."""
import argparse,hashlib,http.server,json,os,sys,threading,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--skill',type=Path,required=True);p.add_argument('--course',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.skill/'workbench'))
from runtime import activate,browser_options
activate()
from backend import Workspace,Handler,read,duration
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
project=a.course/'project';original=read(project/'workbench.json')
if original['revision']!=0:raise ValueError('Use a fresh disposable demo at revision0')
source=project/original['media']['audio'];source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
replacement=a.report.parent/'replacement.png';im=Image.new('RGB',(800,500),'#e6f0e8');ImageDraw.Draw(im).text((40,40),'KGXC 2026 / EDIT TEST',fill='#195641');im.save(replacement)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(a.course)
threading.Thread(target=server.serve_forever,daemon=True).start();url='http://127.0.0.1:'+str(server.server_address[1])
try:
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True,**browser_options());page=b.new_page(viewport=dict(width=1600,height=1100));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url);page.wait_for_function('window.workbench && window.workbench.document.captions.length===3')
  page.locator('#caption-text').fill('收货时先核对订单信息');page.locator('#caption-end').fill('2.4');page.locator('#apply-caption').click()
  page.locator('[data-tab="visual"]').click();page.locator('#visual-scene').select_option('N001');page.locator('#hold-seconds').fill('1');page.locator('#apply-hold').click()
  page.locator('#field-select').select_option('N001-tag:text');page.locator('#field-text').fill('01 / KGXC');page.locator('#apply-field').click()
  page.locator('[data-tab="cut"]').click();page.locator('#cut-start').fill('2.5');page.locator('#cut-end').fill('3');page.locator('#apply-cut').click()
  page.wait_for_function('window.workbench.document.holds[0].frames===15')
  page.locator('#undo').click();page.wait_for_function('window.workbench.document.holds[0].frames===30')
  page.locator('#redo').click();page.wait_for_function('window.workbench.document.holds[0].frames===15')
  page.locator('[data-tab="assets"]').click();page.locator('#asset-upload').set_input_files(str(replacement));page.wait_for_function('window.workbench.document.assets.some(a=>a.path.startsWith("media/uploads/"))')
  page.locator('#save').click();page.wait_for_function('window.workbench.document.revision===1');page.reload();page.wait_for_function('window.workbench && window.workbench.document.revision===1')
  saved=read(project/'workbench.json');assert saved['captions'][0]['text']=='收货时先核对订单信息';assert saved['captions'][0]['endFrame']==72;assert saved['holds'][0]['frames']==15;assert any(f.get('text')=='01 / KGXC' for f in saved['fields']);assert duration(saved)==286
  page.locator('#export').click();page.locator('#start-export').click();page.locator('#job-links a[href*="r1-"]').first.wait_for(state='visible',timeout=240000)
  page.screenshot(path=str(a.report.with_suffix('.png')),full_page=True)
  assert not errors,errors
  jobs=page.request.get(url+'/api/jobs').json();job=jobs[-1];assert job['status']=='complete';assert job['revision']==1
  for key in ['video','srt','package']:assert page.request.get(url+job[key]).ok
  b.close()
 assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
 archives=list((a.course/'packages').glob('*.zip'));assert len(archives)==1
 with zipfile.ZipFile(archives[0]) as z:
  assert z.testzip() is None
  packed=json.loads(z.read('project/workbench.json'));assert packed==saved
  assert 'project/editor/workbench/runtime.py' in z.namelist()
  extracted=a.report.parent/'unpacked-course';z.extractall(extracted)
 assert read(extracted/'project/workbench.json')==saved
 server.workspace=Workspace(extracted)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,**browser_options());opened=browser.new_page();opened.goto(url);opened.wait_for_function('window.workbench && window.workbench.document.revision===1');opened.wait_for_function('document.getElementById("preview").contentWindow.ready');assert opened.locator('#caption-text').input_value()=='收货时先核对订单信息';browser.close()
 report=dict(status='pass',checks=['subtitle text and timing','hold insertion','cut half of hold','undo and redo','visual text','image upload','save and reload','UI MP4/SRT/ZIP export','ZIP CRC and document equality','unpacked editor opens in Chromium','source audio unchanged'],frames=286,seconds=286/30,job=job)
 a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('PASS UI edits, saved reload, synchronized timeline and complete export')
finally:server.shutdown();server.server_close()
