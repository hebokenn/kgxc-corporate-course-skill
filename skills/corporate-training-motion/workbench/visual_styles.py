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
 return dict(intent=intent,candidates=[dict(id=s['id'],title=s['title'],matchedTags=sorted(wanted&set(s['tags'])),why=s['rules'],motions=s['motions']) for s in rows[:3]],instruction='choose one coherent art direction for the course; combine dialogue, demonstrations, charts and props per narration event; do not rotate styles to meet a quota')

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
  n,_=customer(dict(id=recipe['id']+'-'+k,sceneId=scene['id'],x=x,y=y,scale=scale,startFrame=a,endFrame=z,data=dict(identity='adult',pose=pose,shirt=accent)),scene);c.append(n);return n
 def labelset(x=720,y=300,step=150):
  for i,l in enumerate(labels[:4]):text('step'+str(i),str(i+1).zfill(2),x,y+i*step,42,accent);text('label'+str(i),l,x+95,y+i*step,44,ink,effects=[fx('text-rise',i*12)])
 rect('background',0,0,1600,840,bg,radius=0)
 # Every layout changes object arrangement and material logic, not just colours.
 if layout in ['presenter','scene','storybook']:
  if layout=='scene':
   n,_=store(dict(id=recipe['id']+'-store',sceneId=scene['id'],x=0,y=0,scale=1,startFrame=a,endFrame=z,data=dict(view='interior',screenTitle='现场体验')),scene);c.append(n);rect('scrim',660,200,880,500,bg+'e8',radius=22)
  elif layout=='storybook':
   for i in range(9):path('paper-line'+str(i),[[100,170+i*65],[1500,168+i*65]],soft,1)
   rect('page-edge',36,28,12,775,soft,radius=0)
  person('host',100,230,.92,'point');object('table',135,620,.75,'display-table');labelset(680,275);text('title',title,90,70,58)
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
   rect('shadow'+str(i),x+14,y+17,410,400,soft+'88',radius=0);n=rect('paper'+str(i),x,y,410,400,['#f6d69a','#bdcdb5','#e4b298'][i],radius=0,effects=[fx('paper-fold',i*14)]);path('fold'+str(i),[[x+340,y],[x+410,y+70],[x+340,y+70]],bg,3);text('label'+str(i),labels[i%len(labels)],x+35,y+240,42);object('device'+str(i),x+55,y+30,.56,['tablet','earbuds','watch'][i])
  text('title',title,80,65,58)
 elif layout in ['collage','photo']:
  photo=data.get('photoAsset')
  rect('photo-mat',65,195,900,555,'#fffdf5',rotation=-.025)
  if photo:c.append(b.node('image','photo',x=90,y=220,width=850,height=490,assetId=photo,fit='contain'))
  else:
   n,_=store(dict(id=recipe['id']+'-store',sceneId=scene['id'],x=90,y=220,scale=.53,startFrame=a,endFrame=z,data=dict(view='front')),scene);c.append(n)
  for i,l in enumerate(labels[:3]):
   y=255+i*150;rect('note'+str(i),1040,y,470,105,soft if layout=='photo' else '#e4c796',rotation=(-.025 if i%2 else .025));text('label'+str(i),l,1070,y+28,40);path('callout'+str(i),[[1015,y+50],[920,y+50],[760,y+80]],accent,4,effects=[fx('arrow-travel',i*14)])
  text('title',title,75,60,56);text('source',data.get('sourceLabel','场景示意 · 实拍请绑定本地素材'),95,730,23,ink)
 elif layout=='comic':
  text('title',title,65,55,60)
  for i,l in enumerate(labels[:3]):
   x=50+i*510;rect('panel'+str(i),x,190,480,590,'#fffaf0',radius=0,stroke=ink,lineWidth=5);person('actor'+str(i),x+80,340,.65,'question' if i==0 else 'welcome');rect('bubble'+str(i),x+25,220,425,110,bg,stroke=ink,lineWidth=3,effects=[fx('dialogue',i*14)]);text('speech'+str(i),l,x+45,252,38)
 elif layout in ['isometric','lowpoly']:
  text('title',title,70,45,58);path('floor',[[120,500],[800,240],[1480,500],[800,790],[120,500]],soft,5)
  for i,l in enumerate(labels[:3]):
   x=220+i*440;object('table'+str(i),x,385,.75,'display-table');object('dev'+str(i),x+100,340,.28,'laptop');text('label'+str(i),l,x+40,660,37,ink)
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
   for i,l in enumerate(labels[:3]):rect('bar'+str(i),300+i*380,640-(i+1)*110,190,(i+1)*110,[accent,soft,accent][i],effects=[fx('bar-grow',i*12,axis='y')]);text('label'+str(i),l,395+i*380,720,36,ink,align='center')
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
  text('title',title,75,55,58);text('rule','规则先说明，再观察状态变化',90,155,32,ink)
  children=[]
  for i in range(24):children.append(b.rect('agent'+str(i),120+i%8*165,280+i//8*135,70,70,accent if i%3 else soft,radius=35))
  c.append(b.group('agents',0,0,children,1550,650,effects=[fx('cluster-pack')]))
  for i,l in enumerate(labels[:3]):text('label'+str(i),l,150+i*500,730,36)
 else:raise ValueError('未实现布局 '+layout)
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
