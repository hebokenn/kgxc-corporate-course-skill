#!/usr/bin/env python3
"""Build a portable technical gallery through the real full-course authoring API.

No course approvals are fabricated. This is a labelled silent diagnostic gallery,
not a narrated lesson. A separate continuous lesson verifies teaching quality.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from motion_catalog import CATALOG
from authoring import init_project,configure
from backend import atomic
from render_routes import stage_libraries


def effect_node(kind,scene,start,end,roles):
    from motion_demos import create
    return create(kind,scene,start,end,roles)


def build(destination,modules=False):
    root=Path(destination).resolve()
    if root.exists() and any(root.iterdir()):raise ValueError('目标非空；不覆盖工程')
    p=root/'project'
    for name in ['inputs','delivery','packages','project/source','project/assets','project/audio','project/media','project/qa','project/work']: (root/name).mkdir(parents=True,exist_ok=True)
    init_project(p,ROOT)
    diagnostic=json.loads((p/'workbench.json').read_text());diagnostic['motionPolicy']['semanticRequired']=False;atomic(p/'workbench.json',diagnostic)
    marker=json.loads((p/'motion-contract.json').read_text());marker.update(semanticRequired=False,purpose='silent technical gallery');atomic(p/'motion-contract.json',marker)
    (p/'assets/detail.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="450"><rect width="900" height="450" fill="#e5ebd9"/><rect x="70" y="70" width="310" height="300" rx="25" fill="#3c8170"/><circle cx="650" cy="220" r="130" fill="#d9ad60"/><path d="M70 70L380 370M380 70L70 370" stroke="#ffffff" stroke-width="15"/><text x="650" y="240" text-anchor="middle" font-size="72" fill="#183f3c">128</text></svg>')
    assets=[dict(id='detail',path='assets/detail.svg')]
    for ident,name in [('m1','M1-repaired.png'),('m1-open','M1-speaking-open.png'),('m1-blink','M1-blink.png'),('kg','kg-original.png')]:
        shutil.copy2(ROOT/'assets/profiles/kgxc'/name,p/'assets'/name);assets.append(dict(id=ident,path='assets/'+name))
    from company_characters import stage_company
    roles={}
    for identity in ['M1','S01','S02','COACH']:
        staged=stage_company(identity,root,ROOT);roles[identity]=staged['data'];assets.extend(staged['assets'])
    for identity in ['C01','C02','C03']:
        name=identity+'-full-v1.png';shutil.copy2(ROOT/'assets/characters/kgxc-customers-v1'/name,p/'assets'/name);aid='customer-'+identity;assets.append(dict(id=aid,path='assets/'+name));from PIL import Image
        size=Image.open(p/'assets'/name).size;roles[identity]=dict(identity=identity,headAsset=aid,sourceSize=list(size))
    # The detail image is the same independently authored iPhone geometry as the course prop.
    from content_assets import phone
    import importlib.util
    export_spec=importlib.util.spec_from_file_location('retail_svg_export',ROOT/'scripts/export_retail_assets.py');export=importlib.util.module_from_spec(export_spec);export_spec.loader.exec_module(export)
    handset,_=phone(dict(id='detail-device',data=dict(model='iphone-18-pro',finish='glacier-blue',view='back')),dict(id='D',sourceStartFrame=0,sourceEndFrame=90))
    (p/'assets/detail.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="450" viewBox="0 0 900 450"><rect width="900" height="450" fill="#e8ece3"/><g transform="translate(140 20) rotate(-9 200 210) scale(.75)">'+export.svg(handset)+'</g><text x="550" y="140" font-size="38" fill="#22453f">iPhone 18 Pro</text><text x="550" y="200" font-size="24" fill="#5c786b">同一设备 · 局部检查</text></svg>')
    nodes=[];scenes=[];captions=[];beats=[];fps=30;span=150
    for i,(kind,info) in enumerate(CATALOG.items()):
        a=i*span;b=a+span;scene='M'+str(i+1).zfill(2)
        scenes.append(dict(id=scene,chapter='真实动效技术验证',title=info['title'],sourceStartFrame=a,sourceEndFrame=b))
        nodes.append(dict(id='title-'+kind,type='text',sceneId=scene,x=110,y=130,fontSize=68,text=f'{i+1:02}  {info["title"]}',fill='#183f3c',role='decoration'))
        nodes.append(dict(id='kind-'+kind,type='text',sceneId=scene,x=110,y=245,fontSize=30,text=kind,fill='#647b72',role='decoration'))
        nodes.extend(effect_node(kind,scene,a+30,a+120,roles))
        captions.append(dict(id='caption-'+kind,sceneId=scene,text=__import__('motion_demos').CASES[kind][0],startFrame=a,endFrame=b))
        beats += [dict(id=kind+'-before',sceneId=scene,kind='read',startFrame=a,endFrame=a+30,reason='先辨认对象起态'),dict(id=kind+'-action',sceneId=scene,startFrame=a+30,endFrame=a+120,purpose=info['purpose'],before='观察起始对象',after='观察动作完成状态',objectIds=['object-'+kind]),dict(id=kind+'-after',sceneId=scene,kind='observe',startFrame=a+120,endFrame=b,reason='检查动作结果')]
    if modules:
        from teaching_modules import MODULES,expand
        nodes=[];scenes=[];captions=[];beats=[];requested=[];span=300
        for i,(kind,meta) in enumerate(MODULES.items()):
            a=i*span;b=a+span;scene='T'+str(i+1).zfill(2)
            scenes.append(dict(id=scene,chapter='真实教学构图验证',title=meta[0],sourceStartFrame=a,sourceEndFrame=b))
            data=dict(title=meta[0].split(' / ')[-1],context='同一编排器 · 同一画布 · 实际可编辑模块',purpose='技术演示：观察对象、过程和结果',labels=['准备工作','准备迎宾','建立联系'],left=['订单记录','商品信息','编码对应'],right=['对应实物','对应标签','核对结果'],lead='先明确计算对象',scope='分子与分母对应同一范围',root='顾客需要',before='A1B2-C3D4-E5F9',after='A1B2-C3D4-E5F6',selected=1,count=40,records=['线下 · 当前范围 · 40','线上 · 当前范围 · 30','线下 · 当前范围 · 60'],keep=[0,2],result=100,assetId='detail',phases=[dict(title='接待前',labels=['准备工作','准备迎宾']),dict(title='接待中',labels=['建立联系','发掘线索','展示体验','达成交易']),dict(title='接待后',labels=['建立长远关系'])],actorAssets=dict(body='m1',kg='kg',open='m1-open',blink='m1-blink'),frames=[dict(text='先了解使用场景',assetId='m1'),dict(text='确认最在意什么',assetId='m1'),dict(text='邀请顾客亲手体验',assetId='m1')])
            if kind=='whiteboard':data['labels']=['状态准备','待客之道','建立联系','发掘线索','展示体验','达成交易','长远关系']
            if kind=='data':data['selected']=8
            if kind=='editorial':data['labels']=['线下主机销量','对应真实客流','× 100%']
            if kind=='pixel':data['labels']=['核对订单','编码与包装','拍照留存','完成交接']
            if kind=='ink':data['labels']=['使用场景','优先考虑','体验验证']
            requested.append(dict(id='module-'+kind,module=kind,sceneId=scene,data=data,beats=[dict(startFrame=a+15+j*36,endFrame=a+51+j*36) for j in range(7)]))
            captions.append(dict(id='caption-'+kind,sceneId=scene,text='教学构图技术演示 无配音',startFrame=a,endFrame=b))
        total=len(scenes)*span
        temp=expand(dict(sourceDurationFrames=total,scenes=scenes,sceneGraph=dict(modules=requested)))
        from motion_quality import walk,intervals_subtract
        for scene in scenes:
            covered=[]
            for node in walk(temp['sceneGraph']['nodes']):
                if node.get('sceneId')!=scene['id'] or node.get('role')=='decoration':continue
                for e in node.get('effects',[]):
                    covered.append((e['startFrame'],e['endFrame']))
                    beats.append(dict(id=node['id']+'-'+e['type'],sceneId=scene['id'],startFrame=e['startFrame'],endFrame=e['endFrame'],purpose='验证实际模块动作',before='对象初态',after='模块动作结果',objectIds=[node['id']]))
            for j,(x,y) in enumerate(intervals_subtract((scene['sourceStartFrame'],scene['sourceEndFrame']),covered)):
                beats.append(dict(id=scene['id']+'-observe-'+str(j),sceneId=scene['id'],kind='observe',startFrame=x,endFrame=y,reason='无配音技术演示，观察该构图及动作结果'))
        graph=dict(background='#f4f3eb',modules=requested)
    else:
        total=len(scenes)*span;graph=dict(background='#f4f3eb',nodes=nodes)
    with wave.open(str(p/'audio/diagnostic-silence.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*(total//fps*24000))
    spec=dict(title=str(len(CATALOG))+'种真实动效技术验证',sourceDurationFrames=total,bodyEndFrame=total,scenes=scenes,captions=captions,media=dict(audio='audio/diagnostic-silence.wav',intro=None,outro=None),assets=assets,sceneGraph=graph,rendering=dict(route='auto'),voice='无配音 技术验证',motionPlan=dict(schema='course-motion-plan/1',language='motion-gallery-v1',beats=beats))
    atomic(p/'source/gallery.json',spec);doc=configure(root,p/'source/gallery.json')
    editor=p/'editor';shutil.copytree(ROOT/'workbench',editor/'workbench',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));stage_libraries(ROOT,editor/'workbench/motion/lib')
    (editor/'scripts').mkdir()
    for name in ['workbench.py','single_line_subtitles.py','check_workbench.py','workflow.py','course_tools.py','character_assets.py']:shutil.copy2(ROOT/'scripts'/name,editor/'scripts'/name)
    atomic(root/'workspace.json',dict(layout_version=2,project_dir='project',delivery_dir='delivery',package_dir='packages',retain_artifacts=[]))
    return root


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path);parser.add_argument('--modules',action='store_true');args=parser.parse_args()
    print(build(args.destination,args.modules))
