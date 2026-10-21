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


def effect_node(kind,scene,start,end):
    info=CATALOG[kind];typ=info['nodes'][0]
    if typ=='*':typ='group'
    node=dict(id='object-'+kind,type=typ,sceneId=scene,x=320,y=380,width=1040,height=310,fill='#468c79',role='subject')
    effect=dict(type=kind,startFrame=start,endFrame=end)
    if typ=='group':
        node['children']=[dict(id=kind+'-part-'+str(i),type='rect',x=i*285,y=i*22,width=240,height=130,fill=['#3c8170','#dbb767','#7f9eac'][i],radius=10) for i in range(3)]
    if typ=='text':node.update(text='128' if kind in ['count-up','odometer'] else '需求已经确认',fontSize=100,width=1200)
    if typ=='image':node.update(assetId='detail',width=900,height=420,y=340)
    if typ in ['path','line']:
        pts=[[0,120],[180,120],[320,0],[720,0],[920,160]]
        node.update(points=pts,path='M'+' L'.join(f'{x},{y}' for x,y in pts),fill=None,stroke='#3c8170',lineWidth=12)
    if typ=='ellipse':node.update(x=900,y=540,width=350,height=350,fill=None,stroke='#3c8170')
    if kind in ['check-draw','cross-draw','brace-draw']:
        pts={'check-draw':[[0,100],[90,190],[270,0]],'cross-draw':[[0,0],[220,220],[110,110],[220,0],[0,220]],'brace-draw':[[0,0],[0,80],[360,80],[360,0]]}[kind]
        node.update(points=pts,path='M'+' L'.join(f'{x},{y}' for x,y in pts))
    if kind in ['scan','spotlight']:node.update(width=1040,height=360,fill=None)
    if kind=='spotlight':effect.update(cx=520,cy=180,radius=140,fromX=100,fromY=100,fromRadius=1000)
    if kind=='magnify':effect.update(zoom=2.5,cx=.7,cy=.45)
    if kind=='path-follow':effect['points']=[[0,0],[150,-80],[360,0],[620,60]]
    if kind in ['handoff','pixel-walk','swimlane-transfer']:effect.update(dx=480,dy=110)
    if kind in ['group-collect','sort']:
        effect['from']=[[0,0],[480,170],[160,280]];effect['to']=[[700,0],[700,160],[700,320]]
        node.update(y=300,height=540)
    if kind=='correct-replace':effect['fromText']='仍有疑问'
    if kind=='record-filter':effect['keep']=[0,2]
    if kind=='timeline-reflow':effect['to']=[[0,450],[300,700],[760,350]]
    if kind=='quiz-feedback':effect.update(selected=1,correct=True)
    if kind=='balance':effect.update(values=[4,7,10],height=330,baseline=350)
    if kind=='presenter-gesture':
        node.update(assetId='m1',x=300,y=285,width=430,height=550)
        effect.update(kgAsset='kg',openAsset='m1-open',blinkAsset='m1-blink')
    if kind=='gauge-sweep':node.update(x=900,y=600,width=310,height=0,x2=310,y2=0)
    if kind=='venn-intersect':
        node['children']=[dict(id='range-'+str(i),type='ellipse',x=i*550,y=170,width=430,height=330,fill=['#709b82aa','#d9ad60aa'][i]) for i in range(2)]
    if kind=='parallel-sync':effect['to']=[[680,150],[680,150],[680,150]]
    if kind=='dot-aggregate':
        node['children']=[dict(id='record-'+str(i),type='rect',x=i%6*110,y=i//6*100,width=60,height=60,fill='#3c8170') for i in range(18)]
        effect.update(columns=6,gap=42)
    if kind=='callout':node['children'][0].update(type='path',fill=None,stroke='#3c8170',lineWidth=8,points=[[0,100],[150,100],[240,0]],path='M0,100 L150,100 L240,0')
    node['effects']=[effect]
    return node


def build(destination,modules=False):
    root=Path(destination).resolve()
    if root.exists() and any(root.iterdir()):raise ValueError('目标非空；不覆盖工程')
    p=root/'project'
    for name in ['inputs','delivery','packages','project/source','project/assets','project/audio','project/media','project/qa','project/work']: (root/name).mkdir(parents=True,exist_ok=True)
    init_project(p,ROOT)
    (p/'assets/detail.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="450"><rect width="900" height="450" fill="#e5ebd9"/><rect x="70" y="70" width="310" height="300" rx="25" fill="#3c8170"/><circle cx="650" cy="220" r="130" fill="#d9ad60"/><path d="M70 70L380 370M380 70L70 370" stroke="#ffffff" stroke-width="15"/><text x="650" y="240" text-anchor="middle" font-size="72" fill="#183f3c">128</text></svg>')
    assets=[dict(id='detail',path='assets/detail.svg')]
    for ident,name in [('m1','M1-repaired.png'),('m1-open','M1-speaking-open.png'),('m1-blink','M1-blink.png'),('kg','kg-original.png')]:
        shutil.copy2(ROOT/'assets/profiles/kgxc'/name,p/'assets'/name);assets.append(dict(id=ident,path='assets/'+name))
    nodes=[];scenes=[];captions=[];beats=[];fps=30;span=150
    for i,(kind,info) in enumerate(CATALOG.items()):
        a=i*span;b=a+span;scene='M'+str(i+1).zfill(2)
        scenes.append(dict(id=scene,chapter='真实动效技术验证',title=info['title'],sourceStartFrame=a,sourceEndFrame=b))
        nodes.append(dict(id='title-'+kind,type='text',sceneId=scene,x=110,y=130,fontSize=68,text=f'{i+1:02}  {info["title"]}',fill='#183f3c',role='decoration'))
        nodes.append(dict(id='kind-'+kind,type='text',sceneId=scene,x=110,y=245,fontSize=30,text=kind,fill='#647b72',role='decoration'))
        nodes.append(effect_node(kind,scene,a+30,a+120))
        captions.append(dict(id='caption-'+kind,sceneId=scene,text='动效技术演示 无配音',startFrame=a,endFrame=b))
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
    spec=dict(title='48种真实动效技术验证',sourceDurationFrames=total,bodyEndFrame=total,scenes=scenes,captions=captions,media=dict(audio='audio/diagnostic-silence.wav',intro=None,outro=None),assets=assets,sceneGraph=graph,rendering=dict(route='auto'),voice='无配音 技术验证',motionPlan=dict(schema='course-motion-plan/1',language='motion-gallery-v1',beats=beats))
    atomic(p/'source/gallery.json',spec);doc=configure(root,p/'source/gallery.json')
    editor=p/'editor';shutil.copytree(ROOT/'workbench',editor/'workbench',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));stage_libraries(ROOT,editor/'workbench/motion/lib')
    (editor/'scripts').mkdir()
    for name in ['workbench.py','single_line_subtitles.py','check_workbench.py','workflow.py','course_tools.py','character_assets.py']:shutil.copy2(ROOT/'scripts'/name,editor/'scripts'/name)
    atomic(root/'workspace.json',dict(layout_version=2,project_dir='project',delivery_dir='delivery',package_dir='packages',retain_artifacts=[]))
    return root


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path);parser.add_argument('--modules',action='store_true');args=parser.parse_args()
    print(build(args.destination,args.modules))
