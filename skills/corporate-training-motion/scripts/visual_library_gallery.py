#!/usr/bin/env python3
"""Render style and retail specimens through the actual editable course pipeline."""
import argparse,json,sys,shutil,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate,browser_options
activate()
from authoring import init_project,configure
from backend import atomic
from visual_styles import registry
from retail_assets import PROPS,ROLES,POSES,MOODS

def build(dest,mode,photo_id=None,annotations=None):
 root=Path(dest).resolve()
 if root.exists() and any(root.iterdir()):raise ValueError('不覆盖已有工程')
 p=root/'project'
 for n in ['source','assets','audio','work','qa']:(p/n).mkdir(parents=True,exist_ok=True)
 init_project(p,ROOT);doc=json.loads((p/'workbench.json').read_text());doc['motionPolicy'].update(required=False,semanticRequired=False);atomic(p/'workbench.json',doc);atomic(p/'motion-contract.json',dict(required=False,semanticRequired=False,purpose='silent library specimens'))
 scenes=[];styles=[];materials=[];nodes=[];assets=[];index=[]
 if mode=='styles':
  from company_characters import stage_company
  company=stage_company('M1',p,ROOT);assets.extend(company['assets'])
 if mode=='styles':items=list(registry().items())
 elif mode=='people':items=[(who+'-'+pose+'-'+mood,dict(title=who+' '+pose+' '+mood,kind='retail-person',data=dict(identity=who,pose=pose,mood=mood))) for who in ROLES for pose in POSES for mood in MOODS]
 else:items=[(k,dict(title=v,kind='retail-prop',data=dict(object=k))) for k,v in PROPS.items()]+[(k,dict(title='门店 '+k,kind='store-scene',data=dict(view=k))) for k in ['front','interior','isometric']]
 for i,(kind,meta) in enumerate(items):
  sid='S'+str(i);a=i*120;z=a+120;title=meta['title'];scenes.append(dict(id=sid,chapter='素材与风格技术画廊',title=title,sourceStartFrame=a,sourceEndFrame=z));index.append(dict(id=kind,title=title,frame=a+80))
  if mode=='styles':
   from visual_styles import stage_style_assets
   staged=stage_style_assets(root,kind,ROOT);assets.extend(staged['assets']);art_data=dict(title='先了解用途，再邀请体验',labels=['了解用途','邀请体验','核对结果'],**staged['data'])
   if kind=='photo-annotation' and photo_id:
    import importlib.util
    lib_spec=importlib.util.spec_from_file_location('user_asset_library',ROOT/'scripts/asset_library.py');lib=importlib.util.module_from_spec(lib_spec);lib_spec.loader.exec_module(lib)
    photo=lib.stage(root,photo_id);assets.extend(photo['assets']);from PIL import Image
    photo_size=Image.open(p/photo['assets'][0]['path']).size;art_data.update(photoAsset=photo['assets'][0]['id'],photoSize=list(photo_size),annotations=annotations or [],sourceLabel='用户提供的实际门店照片 · 仅本地审阅')
   elif kind=='photo-annotation':
    # Portable public example: an explicitly labelled original 3D render. A real
    # course supplies --photo-id or its own asset; never pretend this is a photo.
    source=ROOT/'assets/material-heroes-v1/lowpoly-facets.png';target=p/'assets/annotation-store-3d.png';shutil.copy2(source,target);assets.append(dict(id='annotation-store-3d',path='assets/annotation-store-3d.png'));art_meta=next(x for x in json.loads((ROOT/'assets/material-heroes-v1/provenance.json').read_text())['materials'] if x['surface']=='lowpoly-facets');art_data.update(photoAsset='annotation-store-3d',photoSize=art_meta['imageSize'],annotations=art_meta['labelAnchors'],sourceLabel='本地3D门店示意图 · 正式现场讲解请绑定本课实拍')
   styles.append(dict(id='style-'+kind,sceneId=sid,style=kind,data=art_data))
  else:
   is_store=meta['kind']=='store-scene';materials.append(dict(id='item-'+kind,sceneId=sid,kind=meta['kind'],x=160 if is_store else 560,y=200 if is_store else 260,scale=.85 if is_store else 1.3,data=meta['data']))
   nodes.append(dict(id='title-'+kind,type='text',sceneId=sid,x=110,y=100,text=title,fontSize=65,fill='#193d3d',role='decoration'))
  nodes.append(dict(id='id-'+kind,type='text',sceneId=sid,x=110,y=45,text=kind,fontSize=25,fill='#74867c',role='decoration'))
 total=len(items)*120
 with wave.open(str(p/'audio/silent.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*(total//30*24000))
 assets=list({a['id']:a for a in assets}.values())
 graph=dict(background='#f2f0e6',nodes=nodes,styleScenes=styles,materials=materials)
 spec=dict(title='视觉资源调用画廊',sourceDurationFrames=total,scenes=scenes,captions=[],media=dict(audio='audio/silent.wav',intro=None,outro=None),assets=assets,sceneGraph=graph,rendering=dict(route='auto'),voice='静音技术画廊')
 atomic(p/'source/library.json',spec);configure(root,p/'source/library.json');atomic(root/'index.json',index);return root

def verify(root,out):
 import http.server,threading,base64,io
 import numpy as np
 from PIL import Image,ImageDraw,ImageFont
 from playwright.sync_api import sync_playwright
 from backend import Handler,Workspace,read
 root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);p=root/'project';doc=read(p/'workbench.json');entries=read(root/'index.json')
 http.server.ThreadingHTTPServer.request_queue_size=128
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspace=Workspace(p);threading.Thread(target=server.serve_forever,daemon=True).start()
 report=[];pictures=[]
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page(viewport=dict(width=1920,height=1080));errs=[];failed=[];page.on('pageerror',lambda e:errs.append(str(e)));page.on('requestfailed',lambda r:failed.append(dict(url=r.url,error=r.failure)));page.goto(f'http://127.0.0.1:{server.server_address[1]}/renderer.html');page.wait_for_function('window.ready||window.renderError',timeout=120000)
   if page.evaluate('window.renderError||null'):raise ValueError(dict(error=page.evaluate('window.renderError'),failedRequests=failed))
   for item in entries:
    fn='async f=>{await window.courseRenderer.drawFrame(f);return window.courseRenderer.canvas.toDataURL()}'
    checked=[item['frame']-80,item['frame']-62,item['frame']-44,item['frame'],item['frame']+39]
    for f in checked:page.evaluate(fn,f)
    raw=page.evaluate(fn,item['frame']);layout=page.evaluate('window.courseRenderer.native.courseWorkbench.layoutReceipt?.()||[]');assert not any(v.get('violations') for v in layout),(item['id'],layout)
    im=Image.open(io.BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGB');im.save(out/(item['id']+'.png'));pixels=np.asarray(im)[200:925,150:1770];foreground=int((np.max(np.abs(pixels.astype(np.int16)-np.array([242,240,230])),axis=2)>16).sum());assert foreground>1000,item['id']
    # A specimen must render identically after a nonmonotonic seek.
    page.evaluate(fn,max(0,item['frame']-70));again=page.evaluate(fn,item['frame']);assert raw==again,item['id']
    pictures.append((item,im));report.append(dict(id=item['id'],title=item['title'],actualPixels=True,reverseSeekIdentical=True,layoutCheckedFrames=checked))
   assert not errs,errs
   browser.close()
 finally:server.shutdown();server.server_close()
 cols=4;tw,th=480,310;sheet=Image.new('RGB',(cols*tw,((len(pictures)+cols-1)//cols)*th+90),'#f5f0e4');dr=ImageDraw.Draw(sheet);font=ImageFont.truetype(str(ROOT/'assets/bookends/CourseTitle.otf'),25);dr.text((25,20),'同一课程引擎 · '+str(len(pictures))+' 个可调用视觉方案',font=ImageFont.truetype(str(ROOT/'assets/bookends/CourseTitle.otf'),36),fill='#193d3d')
 for i,(meta,pic) in enumerate(pictures):
  pic.thumbnail((476,268));x=i%cols*tw;y=i//cols*th+85;sheet.paste(pic,(x,y));dr.text((x+12,y+269),str(i+1).zfill(2)+' '+meta['title'],font=font,fill='#193d3d')
 sheet.save(out/'contact-sheet.jpg',quality=92);atomic(out/'verification.json',dict(status='pass',count=len(report),items=report,scope='actual renderer and deterministic seeks; not user style acceptance'));print(json.dumps(dict(status='pass',count=len(report))))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('destination',type=Path);a.add_argument('--mode',choices=['styles','retail','people'],default='styles');a.add_argument('--photo-id',help='Optional explicitly selected user-local photo; omit for the labelled public 3D annotation example');a.add_argument('--annotations',type=Path,help='JSON list of labels and normalized image points for an explicitly selected photo');a.add_argument('--out',type=Path,required=True);args=a.parse_args();verify(build(args.destination,args.mode,args.photo_id,json.loads(args.annotations.read_text()) if args.annotations else None),args.out)
