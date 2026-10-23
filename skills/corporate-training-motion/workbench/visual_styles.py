"""Extensible art-direction recipes compiled into the ordinary course renderer."""
import copy,json,hashlib,re
from pathlib import Path
from runtime import config_dir
from content_assets import Drawing
LAYOUTS={'presenter','scene','cosmos','whiteboard','chalk','storybook','papercut','collage','comic','isometric','blueprint','cutaway','soft','lowpoly','pixel','data','math','ui','photo','minimal','ink','kinetic','flowmap','simulation'}

def validate_style(d):
 if not re.fullmatch('[a-z][a-z0-9-]{1,63}',d.get('id','')):raise ValueError('风格ID须为小写字母、数字和连字符')
 if d.get('layout') not in LAYOUTS:raise ValueError('未知风格布局，新增布局须实现对应图形编译器')
 if len(d.get('palette',[]))!=4 or any(not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in d['palette']):raise ValueError('风格须提供四个六位色值：背景、文字、强调、辅助')
 if d.get('font','CourseHan') not in ['CourseHan','CourseHand','CourseSerif','CourseHeavy']:raise ValueError('未打包字体，先接入实际字体再注册')
 if not isinstance(d.get('outline',3),(int,float)) or not 0<=d.get('outline',3)<=24:raise ValueError('轮廓宽度须在0至24之间')
 if not d.get('title') or not d.get('rules') or not d.get('tags'):raise ValueError('风格须有名称、美术规范和用途标签')
 if d.get('surface','vector-clean') not in ['vector-clean','cel-paint','neon-emission','ink-paper','chalk-dust','watercolor','cut-paper','newsprint','comic-halftone','wood-grain','cyanotype','brushed-metal','clay-matte','lowpoly-facets','pixel-dither','screen-print','clear-acrylic','polished-glass','photo-real','ceramic-glaze','graphite','letterpress','felt-fabric','plastic-toy']:raise ValueError('材质还没有真实运行实现')
 from motion_catalog import CATALOG
 if any(x not in CATALOG for x in d.get('motions',[])):raise ValueError('风格引用尚未实现的动作')
 return d

def registry():
 rows=json.loads((Path(__file__).parent/'visual-styles.json').read_text())['styles'];data={x['id']:validate_style(x) for x in rows}
 for p in sorted((config_dir()/'visual-styles').glob('*.json')):
  d=validate_style(json.loads(p.read_text()));data[d['id']]=d
 return data

def catalog():return dict(schema='course-visual-styles/1',count=len(registry()),styles=list(registry().values()),extension='register-style --file JSON stores a user-local recipe; existing styles can be overridden without editing the Skill')

def register(path):
 d=validate_style(json.loads(Path(path).read_text()));folder=config_dir()/'visual-styles';folder.mkdir(parents=True,exist_ok=True);out=folder/(d['id']+'.json')
 if out.exists():raise ValueError('同名用户风格已存在；显式编辑该文件，保留原有选择')
 out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');return dict(id=d['id'],path=str(out))

def recommend(intent):
 aliases={'顾客':'role-play','对话':'role-play','接待':'service','讲解':'explanation','流程':'process','交接':'handoff','结构':'structure','操作':'operation','排错':'troubleshoot','数据':'quantity','比较':'comparison','案例':'case','证据':'evidence','场景':'space','练习':'practice','推演':'simulation','定义':'definition','因果':'causality'}
 wanted=set(re.split(r'[,\s]+',intent))|{tag for word,tag in aliases.items() if word in intent};rows=sorted(registry().values(),key=lambda s:len(wanted&set(s['tags'])),reverse=True)
 chosen=[];families=set()
 for s in rows:
  if s['family'] not in families:chosen.append(s);families.add(s['family'])
  if len(chosen)==3:break
 return dict(intent=intent,candidates=[dict(id=s['id'],title=s['title'],family=s['family'],surface=s.get('surface'),matchedTags=sorted(wanted&set(s['tags'])),why=s['rules'],motions=s['motions']) for s in chosen],instruction='choose one coherent art direction for the course; alternatives differ in visual family and material. Combine dialogue, demonstrations, charts and props per narration event; never rotate styles to meet a quota. Motion-catalog includes business task and visible result for each real action.')

def build(recipe,scene,style):
 from retail_assets import prop,customer,store
 b=Drawing(recipe,scene);data=recipe.get('data',{});bg,ink,accent,soft=style['palette'];layout=style['layout'];c=[];title=data.get('title','先了解用途，再邀请体验');labels=data.get('labels',['了解用途','邀请体验','核对结果'])
 if not labels:raise ValueError('风格场景须提供实际讲解标签')
 a=recipe.get('startFrame',scene['sourceStartFrame']);z=recipe.get('endFrame',scene['sourceEndFrame']);duration=min(36,z-a)
 def fx(kind,delay=0,**kw):return dict(type=kind,startFrame=min(a+delay,z-2),endFrame=min(a+delay+duration,z),**kw)
 def rect(k,x,y,w,h,color,**kw):
  if kw.get('stroke'):kw['lineWidth']=kw.get('lineWidth',3)*style.get('outline',3)/3
  n=b.rect(k,x,y,w,h,color,**kw);c.append(n);return n
 def text(k,v,x,y,size=36,color=None,**kw):
  kw['fontFamily']=style.get('font','CourseHan')
  n=b.text(k,v,x,y,size,color or ink,**kw);n.setdefault('width',1580-x);n.setdefault('height',size*1.6);c.append(n);return n
 def path(k,pts,color=None,width=5,**kw):n=b.path(k,'M'+' L'.join(f'{x},{y}' for x,y in pts),None,color or ink,width*style.get('outline',3)/3,points=pts,**kw);c.append(n);return n
 def object(k,x,y,scale=1,kind='tablet'):
  r=dict(id=recipe['id']+'-'+k,sceneId=scene['id'],x=x,y=y,scale=scale,startFrame=a,endFrame=z,data=dict(object=kind,color=soft,screenColor=bg));n,_=prop(r,scene);c.append(n);return n
 def person(k,x,y,scale=.8,pose='point'):
  if data.get('actor'):
   from content_assets import actor
   n,_=actor(dict(id=recipe['id']+'-'+k,sceneId=scene['id'],x=x,y=y,scale=scale*.73,startFrame=a,endFrame=z,data=data['actor']),scene);c.append(n);return n
  role='customer' if k.startswith('customer') else 'staff' if k.startswith('staff') else 'host'
  identity=data.get('roleIdentities',{}).get(role,{'customer':'C01','staff':'S01','host':'M1'}[role])
  allowed={'customer':['C01','C02','C03'],'staff':['S01','S02'],'host':['M1','S01','S02','COACH']}
  if identity not in allowed[role]:raise ValueError('人物身份与当前岗位不匹配 '+role)
  aid=data.get('roleAssets',{}).get(identity)
  if not aid:raise ValueError('人物风格必须先 stage-style-assets 绑定原版门店角色，不能退回通用人')
  provenance=data.get('roleProvenance',{}).get(identity,{})
  if not provenance.get('visibleBox') or not provenance.get('imageSize'):raise ValueError('人物缺少可见轮廓与脚底锚点，重新 stage-style-assets')
  ix,iy,ex,ey=provenance['visibleBox'];iw,ih=provenance['imageSize'];height=590*scale;width=height*(ex-ix)/(ey-iy)
  image=b.node('image',k+'-master',x=0,y=0,width=width,height=height,crop=[ix/iw,iy/ih,(ex-ix)/iw,(ey-iy)/ih],assetId=aid,fit='contain',approvedIdentity=identity,roleProvenance=provenance)
  shadow=b.ellipse(k+'-contact-shadow',width/2,height-1,width*.72,12,'#24403b20')
  n=b.group(k,x,y,[shadow,image],width,height,groundContact=[width/2,height],textExclusion=True);c.append(n);return n
 def on_table(k,table,kind='ipad',scale=.34,u=.5,v=.5):
  n=object(k,0,0,scale,kind);anchor=n.get('contactAnchor')
  if not anchor:raise ValueError('物件缺少可见底边锚点 '+kind)
  aa,bb,cc,dd=table['supportSurface'];px=aa[0]+u*(bb[0]-aa[0])+v*(dd[0]-aa[0]);py=aa[1]+u*(bb[1]-aa[1])+v*(dd[1]-aa[1]);sx=table.get('scaleX',1);sy=table.get('scaleY',1)
  n['x']=table['x']+px*sx-anchor[0]*scale;n['y']=table['y']+py*sy-anchor[1]*scale;n['supportBinding']=dict(objectId=table['id'],point=[px,py],anchor=anchor)
  return n
 def labelset(x=720,y=300,step=150):
  for i,l in enumerate(labels[:4]):text('step'+str(i),str(i+1).zfill(2),x,y+i*step,42,accent);text('label'+str(i),l,x+95,y+i*step,44,ink,effects=[fx('text-rise',i*12)])
 rect('background',0,0,1600,840,bg,radius=0)
 # Every layout changes object arrangement and material logic, not just colours.
 if layout in ['presenter','scene','storybook']:
  if layout=='scene':
   n,_=store(dict(id=recipe['id']+'-store',sceneId=scene['id'],x=35,y=225,scale=.65,startFrame=a,endFrame=z,data=dict(view='interior',screenTitle='现场体验')),scene);c.append(n)
  elif layout=='storybook':
   for i in range(9):path('paper-line'+str(i),[[100,170+i*65],[1500,168+i*65]],soft,1)
   rect('page-edge',36,28,12,775,soft,radius=0)
  if layout=='storybook':
   # A book is a physical scene with approved people, not ruled paper plus bullets.
   c=[n for n in c if n.get('id','').endswith('-background')]
   for layer in range(4):rect('book-edge'+str(layer),90+layer*3,155+layer*5,1430,630,'#d3c4a4',radius=5)
   rect('left-page',90,145,710,630,'#fff9e8',radius=4,stroke='#b99d78',lineWidth=2);rect('right-page',800,145,710,630,'#f7ecd3',radius=4,stroke='#b99d78',lineWidth=2);path('spine',[[800,160],[800,760]],'#b09674',8)
   person('customer-story',150,300,.75,'question');person('staff-story',835,295,.76,'point');table=object('story-table',1230,570,.48,'display-table');on_table('ipad-story',table,'ipad',.32)
   text('left-narration','顾客：主要想给家人拍照。',130,195,34);text('right-narration','店员：按你的场景亲手试一次。',840,195,34);result=text('book-result','带着使用问题体验，再一起核对结果。',800,800,27,align='center');rect('book-result-safe',100,786,1400,52,None,radius=0,enclosesTextIds=[result['id']]);text('title',title,90,50,58)
  else:
   if layout=='scene':
    # Keep the host in the clear left aisle. The store already owns four tables;
    # adding a fifth in front of the character caused the reported intersection.
    # All store objects share one world transform; feet land below the wall
    # cabinet on the floor, not on the cabinet's apparent base.
    role=person('staff-host',85,790-590*.72,.72,'point');c.pop();n['children'].append(role);labelset(1160,300,150)
   else:
    person('host',100,230,.92,'point');object('table',440,580,.62,'display-table');labelset(850,275)
   text('title',title,90,70,58)
 elif layout=='cosmos':
  for i in range(36):rect('star'+str(i),60+(i*193)%1480,160+(i*73)%600,3+i%3,3+i%3,soft,radius=2)
  for i,l in enumerate(labels[:3]):
   x=330+i*465;n=b.ellipse('planet'+str(i),x,430,200,200,[accent,soft,'#d9af91'][i]);n['effects']=[fx('orbit-revolve',i*9,radiusX=22,radiusY=10)];c.append(n);text('label'+str(i),l,x,600,42,ink,align='center')
  text('title',title,90,70,58);path('orbit',[[120,480],[480,530],[930,360],[1440,440]],soft,3)
 elif layout in ['whiteboard','chalk','ink']:
  if layout=='chalk':
   for i in range(26):path('chalk-grain'+str(i),[[40,32+i*31],[1560,31+i*31]],'#ffffff0a',1)
  if layout=='ink':
   for i in range(23):rect('grain'+str(i),48+(i*71)%1510,30+(i*113)%750,2,2,soft,radius=0)
  text('title',title,95,80,58,fontFamily='CourseHand');object('device',100,290,.82,'tablet')
  for i,l in enumerate(labels[:3]):
   y=260+i*175;path('branch'+str(i),[[580,440],[800,440],[925,y+25]],accent,5,effects=[fx('signature-write',i*14)]);text('label'+str(i),l,985,y,44,fontFamily='CourseHand')
 elif layout=='papercut':
  for i,(x,y) in enumerate([(65,215),(525,300),(1000,215)]):
   rect('shadow'+str(i),x+14,y+17,410,400,soft+'88',radius=0);n=rect('paper'+str(i),x,y,410,400,['#f6d69a','#bdcdb5','#e4b298'][i],radius=0,effects=[fx('paper-fold',i*14)]);path('fold'+str(i),[[x+340,y],[x+410,y+70],[x+340,y+70]],bg,3);text('label'+str(i),labels[i%len(labels)],x+35,y+240,42);object('device'+str(i),x+55,y+30,.48,['tablet','earbuds','watch'][i])
  text('title',title,80,65,58)
 elif layout in ['collage','photo']:
  photo=data.get('photoAsset')
  if layout=='photo' and not photo:raise ValueError('实拍风格须绑定当前课程的真实照片，不能用示意图冒充')
  rect('photo-mat',65,195,900,555,'#fffdf5',rotation=-.025)
  if photo:c.append(b.node('image','photo',x=90,y=220,width=850,height=490,assetId=photo,fit='contain'))
  else:
   n,_=store(dict(id=recipe['id']+'-store',sceneId=scene['id'],x=90,y=220,scale=.53,startFrame=a,endFrame=z,data=dict(view='front')),scene);c.append(n)
  if layout=='photo':
   annotations=data.get('annotations',[])
   if not annotations or not data.get('photoSize'):raise ValueError('照片标注须绑定实际图像尺寸及逐物件标注点，不自动用课程步骤猜位置')
   iw,ih=data['photoSize'];q=min(850/iw,490/ih);ww,hh=iw*q,ih*q;xx,yy=90+(850-ww)/2,220+(490-hh)/2
   marks=[]
   for mark in annotations[:3]:
    px,py=mark['point']
    if not 0<=px<=1 or not 0<=py<=1:raise ValueError('标注点必须在当前图像范围内')
    marks.append((mark['label'],xx+px*ww,yy+py*hh))
  else:marks=[('体验桌',365,545),('配件陈列墙',840,460),('门头标牌',515,260)]
  # Match the vertical order of the observed objects so right-side leaders
  # do not cross each other merely because the input list used another order.
  marks.sort(key=lambda mark:mark[2])
  for i,(label,px,py) in enumerate(marks):
   y=255+i*150;rect('note'+str(i),1040,y,470,105,soft if layout=='photo' else '#e4c796',rotation=(-.025 if i%2 else .025));text('label'+str(i),label,1070,y+28,36);path('callout'+str(i),[[1015,y+50],[940,y+50],[px,py]],accent,4,effects=[fx('arrow-travel',i*14)])
  text('title',title,75,60,56);source=text('source',data.get('sourceLabel','代码门店示意 · 实拍需绑定本地素材'),95,780,23,ink);rect('source-safe',65,767,1470,57,None,radius=0,enclosesTextIds=[source['id']])
 elif layout=='comic':
  text('title',title,65,55,60)
  panel_text=[('顾客询问','主要给家人拍照，\n操作会复杂吗？'),('店员邀请','先按你的使用场景，\n亲手试一次。'),('共同核对','这次体验结果，\n符合你的需要吗？')]
  for i,(who,speech) in enumerate(panel_text):
   x=40+i*515;rect('panel'+str(i),x,180,485,610,'#fffaf0',radius=0,stroke=ink,lineWidth=5)
   if i==0:person('customer-ask',x+80,365,.68,'question')
   elif i==1:person('staff-invite',x+12,355,.66,'point');table=object('demo-table',x+270,590,.40,'display-table');on_table('demo-ipad',table,'ipad',.29)
   else:person('customer-result',x+15,415,.52);person('staff-result',x+200,415,.52)
   rect('bubble'+str(i),x+20,205,445,140,bg,stroke=ink,lineWidth=3);text('speaker'+str(i),who,x+38,217,25,accent)
   # Two short lines fit the real speech bubble; tails stay away from the faces.
   text('speech'+str(i),speech,x+38,260,30,lineHeight=1.25)
   path('tail'+str(i),[[x+110,345],[x+130,365],[x+150,345]],ink,3)
 elif layout in ['isometric','lowpoly']:
  text('title',title,70,45,58);path('floor',[[120,500],[800,240],[1480,500],[800,790],[120,500]],soft,5)
  for i,l in enumerate(labels[:3]):
   x=220+i*440;table=object('table'+str(i),x,385,.75,'display-table');on_table('dev'+str(i),table,'laptop',.28);text('label'+str(i),l,x+40,710,37,ink)
  if layout=='lowpoly':
   for i in range(7):path('facet'+str(i),[[180+i*170,510],[800,250],[800,780]],'#b6c7b9',2)
 elif layout in ['blueprint','cutaway']:
  if layout=='blueprint':
   for i in range(32):path('gridx'+str(i),[[i*50,0],[i*50,840]],'#def1ed16',1)
   for i in range(17):path('gridy'+str(i),[[0,i*50],[1600,i*50]],'#def1ed16',1)
  text('title',title,80,60,58);n=object('main',110,285,1.25,'laptop');n['effects']=[fx('rotate-inspect',0,angle=.2)]
  for i,l in enumerate(labels[:3]):
   y=290+i*160;path('call'+str(i),[[450,350+i*60],[920,y+20],[1000,y+20]],accent,4,effects=[fx('route-progress',i*13)]);text('label'+str(i),l,1030,y,40);text('number'+str(i),str(i+1),940,y-8,25,accent)
  if layout=='cutaway':
   for i in range(3):rect('layer'+str(i),180+i*55,500-i*45,470,55,[soft,accent,'#b8cbc2'][i],rotation=-.13,effects=[fx('handoff',i*7,dx=20,dy=-45,lift=0)])
 elif layout=='soft':
  text('title',title,75,60,58)
  for i,l in enumerate(labels[:3]):
   x=240+i*480;rect('shadow'+str(i),x-60,650,240,22,'#4c495418',radius=11);object('obj'+str(i),x-100,260,.8,['earbuds','watch','speaker'][i]);text('label'+str(i),l,x+50,705,38,ink,align='center')
 elif layout=='pixel':
  text('title',title,80,65,58);rect('floor',60,660,1480,32,accent,radius=0)
  for i,l in enumerate(labels[:3]):
   x=140+i*480
   for j in range(i+1):rect(f'step-{i}-{j}',x,600-j*75,110,65,soft,radius=0)
   text('label'+str(i),l,x-35,280,38,ink);rect('post'+str(i),x+48,340,14,270,soft,radius=0)
  n=rect('token',120,565,70,80,accent,radius=0,effects=[fx('pixel-walk',0,dx=980,steps=14)])
 elif layout in ['data','math']:
  text('title',title,80,60,58);path('axes',[[180,200],[180,680],[1460,680]],soft,3)
  if layout=='data':
   for i,l in enumerate(labels[:3]):rect('bar'+str(i),300+i*380,680-(i+1)*110,190,(i+1)*110,[accent,soft,accent][i],effects=[fx('bar-grow',i*12,axis='y')]);text('label'+str(i),l,395+i*380,720,36,ink,align='center')
   text('unit','示意关系 · 不代表真实业绩',220,195,26,ink)
  else:
   path('curve',[[180,620],[420,570],[660,450],[900,390],[1180,230],[1420,180]],accent,7,effects=[fx('line-plot')]);text('formula','观察变化关系',950,520,62,ink);text('labels',' → '.join(labels[:3]),270,725,34,ink)
 elif layout=='ui':
  text('title',title,80,55,58);object('tablet',100,230,1.65,'tablet');labelset(1000,270,150);c.append(b.node('rect','pointer',x=300,y=300,width=700,height=350,fill=None,effects=[fx('cursor-click',0,cx=330,cy=160)]))
 elif layout=='minimal':
  text('section','工作中的一个关键动作',90,90,28,accent);text('title',title,90,200,82);path('rule',[[95,350],[1490,350]],ink,2);object('object',90,430,.85,'tablet');labelset(690,440,100)
 elif layout=='kinetic':
  text('title',title,75,55,52);sizes=[110,150,110]
  for i,l in enumerate(labels[:3]):text('word'+str(i),l,90+i*160,220+i*170,sizes[i],ink if i!=1 else accent,effects=[fx('text-rise',i*12)])
 elif layout=='flowmap':
  text('title',title,70,65,58)
  for i,l in enumerate(labels[:3]):
   x=160+i*490;y=300+(i%2)*220;rect('station'+str(i),x,y,330,135,soft,radius=50);text('label'+str(i),l,x+32,y+42,42)
   if i<2:path('link'+str(i),[[x+330,y+65],[x+410,y+65],[x+410,585 if i==0 else 365],[x+490,585 if i==0 else 365]],accent,7,effects=[fx('arrow-travel',i*12)])
 elif layout=='simulation':
  text('title',title,75,55,58);text('rule','每张卡代表一项体验任务；核对后进入对应职责区。',90,155,31,ink)
  rect('waiting-zone',90,270,670,440,'#e0e8d9',stroke=ink,lineWidth=2);rect('checked-zone',840,270,670,440,'#e5d7bc',stroke=ink,lineWidth=2)
  text('waiting-label','店员 · 体验任务',115,295,35);text('checked-label','店长 · 核对任务',865,295,35)
  children=[]
  for i in range(8):
   sub=[b.rect('task-bg'+str(i),0,0,205,100,'#f9f6ec',stroke=ink,lineWidth=2),b.text('task-id'+str(i),'任务 '+str(i+1).zfill(2),20,16,29,ink),b.text('task-type'+str(i),'体验记录' if i%2==0 else '结果复核',20,59,22,ink)]
   children.append(b.group('task'+str(i),30+i%4*340,15+i//4*140,sub,205,100))
  n=b.group('agents',100,365,children,1400,315,clip=[0,0,1400,315],effects=[fx('cluster-pack',0,centers=[[20,20],[770,20]],columns=2,gapX=300,gapY=140)]);c.append(n)
  text('result','体验记录归店员跟进，结果复核归店长处理。',150,765,28)
 else:raise ValueError('未实现布局 '+layout)
 if data.get('heroAsset'):
  c=[n for n in c if n.get('id','').endswith('-background') or n.get('type')=='text' and (n.get('id','').endswith('-title') or n.get('id','').endswith('-source'))]
  surface=style.get('surface');meta=data.get('heroLayout',{})
  if not meta.get('labelAnchors') or not meta.get('imageSize'):raise ValueError('立体素材须附实际相机投影和图像尺寸，不能按整页等分摆标签')
  def hero_image(x,y,w,h):
   iw,ih=meta['imageSize'];q=min(w/iw,h/ih);ww,hh=iw*q,ih*q;xx,yy=x+(w-ww)/2,y+(h-hh)/2
   c.append(b.node('image','physical-hero',x=xx,y=yy,width=ww,height=hh,assetId=data['heroAsset'],fit='contain'))
   anchors=[(r['label'],xx+r['point'][0]*ww,yy+r['point'][1]*hh) for r in meta['labelAnchors']]
   return (xx,yy,ww,hh),anchors
  def footer(key,line):
   label=text(key,line,800,787,24,ink,align='center')
   rect(key+'-safe',90,775,1420,57,None,radius=0,enclosesTextIds=[label['id']])
  if surface in ['brushed-metal','clear-acrylic']:
   box,anchors=hero_image(180,165,1240,510)
   for i,(label,x,y) in enumerate(anchors):
    path('label-guide'+str(i),[[x,box[1]+box[3]+8],[x,715]],soft,2)
    node=text('device-label'+str(i),label,x,727,31,ink,align='center')
    rect('label-safe'+str(i),x-92,714,184,57,None,radius=0,enclosesTextIds=[node['id']])
   footer('hero-note','外观分层示意 · 不代表内部拆机结构' if surface=='brushed-metal' else '从顾客使用的设备出发，核对本次体验要解决的问题。')
  elif surface=='clay-matte':
   box,anchors=hero_image(55,180,1030,550)
   text('clay-object','AirPods 与 Apple Watch',1100,290,30,ink);text('clay-purpose','先说使用场景，\n再亲手体验。',1100,385,42,ink,lineHeight=1.5)
   label,x,y=anchors[1];path('clay-note',[[1090,565],[990,565],[x,y]],accent,3);text('clay-material','圆润捏塑 / 粗糙哑光 / 接触阴影',1100,665,22,ink)
  else:
   box,anchors=hero_image(135,170,950,580)
   object_notes=sorted(zip(anchors,['留出接待通道','在体验桌验证用途','在配件墙核对适配']),key=lambda pair:pair[0][2])
   for i,((label,x,y),line) in enumerate(object_notes):
    yy=300+i*140;path('store-guide'+str(i),[[x,y],[1065,yy+20],[1100,yy+20]],accent,2);text('store-zone'+str(i),line,1120,yy,30,ink)
   footer('hero-note','先明确顾客的场景，再沿门店动线安排体验。')
 def coat(n):
  if n.get('type') in ['rect','ellipse','path','text','image']:
   if 'shadow' in n.get('id',''):return
   n['surface']=style.get('surface','vector-clean')
   if layout=='isometric' and '-table' in n.get('id','') and n.get('fill') is not None and n['type']!='text':
    n['fill']='#c2965d' if n['id'].endswith('-top') else '#997247' if n['id'].endswith('-edge') else '#b58a58'
   if layout=='blueprint' and '-main-' in n.get('id','') and n['type'] in ['path','rect','ellipse']:
    n['fill']=None;n['stroke']='#a8dce6';n['lineWidth']=2
   if n['type']=='rect' and n.get('width',0)>=1500 and n.get('height',0)>=800:n['surfaceRole']='ground'
  for child in n.get('children',[]):coat(child)
 for n in c:coat(n)
 return b.group('root',recipe.get('x',160),recipe.get('y',125),c,1600,840,scaleX=recipe.get('scale',1),scaleY=recipe.get('scale',1))

def expand(spec):
 result=copy.deepcopy(spec);graph=result.setdefault('sceneGraph',{});recipes=graph.pop('styleScenes',[])
 if not recipes:return result
 rows=registry();scenes={s['id']:s for s in result['scenes']};seen=set();manifest=[]
 for r in recipes:
  if not r.get('id') or r['id'] in seen:raise ValueError('风格场景ID缺失或重复')
  seen.add(r['id'])
  if r.get('style') not in rows or r.get('sceneId') not in scenes:raise ValueError('风格或场景尚未注册')
  style=rows[r['style']];node=build(r,scenes[r['sceneId']],style);graph.setdefault('nodes',[]).append(node)
  manifest.append(dict(id=r['id'],styleId=style['id'],style=style,recipe=r,sha256=hashlib.sha256(json.dumps([style,r],sort_keys=True,ensure_ascii=False).encode()).hexdigest()))
 result['visualStyles']=manifest;return result


def stage_style_assets(course,style_id,skill_root):
    """Stage real approved identities and optional local 3D material renders."""
    import shutil
    p=Path(course).resolve();p=p if (p/'workbench.json').exists() else p/'project'
    if not p.is_dir():raise ValueError('先建立当前课程project目录')
    styles=registry()
    if style_id not in styles:raise ValueError('未知风格 '+style_id)
    surface=styles[style_id].get('surface','vector-clean');root=Path(skill_root);base=root/'assets/role-surfaces-v1';data=dict(roleAssets={},roleProvenance={});assets=[]
    for identity in ['M1','S01','S02','COACH','C01','C02','C03']:
        source=base/(identity+'-'+surface+'.png')
        if not source.exists():source=base/(identity+'-original.png')
        if not source.exists():raise ValueError('缺少已批准人物的实际材质衍生图 '+identity)
        digest=hashlib.sha256(source.read_bytes()).hexdigest();dest=p/'assets/style-library'/(digest[:12]+'-'+source.name);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise ValueError('课程素材已被编辑，保留原件并使用新版本')
        if not dest.exists():shutil.copy2(source,dest)
        from PIL import Image
        im=Image.open(source);visible=im.getchannel('A').point(lambda x:255 if x>8 else 0).getbbox()
        aid='role-'+identity+'-'+digest[:12];assets.append(dict(id=aid,path=str(dest.relative_to(p))));data['roleAssets'][identity]=aid;data['roleProvenance'][identity]=dict(masterIdentity=identity,sourceFile=source.name,sha256=digest,imageSize=list(im.size),visibleBox=list(visible),uniform='KG' if identity in ['M1','S01','S02'] else 'MyCoach' if identity=='COACH' else 'customer')
    if surface in ['brushed-metal','clay-matte','lowpoly-facets','clear-acrylic']:
        source=root/'assets/material-heroes-v1'/(surface+'.png')
        if not source.exists():raise ValueError('尚未完成真实本地3D材质渲染 '+surface)
        digest=hashlib.sha256(source.read_bytes()).hexdigest();dest=p/'assets/style-library'/(digest[:12]+'-'+source.name);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(source,dest)
        aid='material-hero-'+digest[:12];assets.append(dict(id=aid,path=str(dest.relative_to(p))));data['heroAsset']=aid
        meta=json.loads((source.parent/'provenance.json').read_text());data['heroLayout']=next(v for v in meta['materials'] if v['surface']==surface)
    return dict(assets=assets,data=data,surface=surface,scope='approved master identity with local surface processing; no new generated identity')
