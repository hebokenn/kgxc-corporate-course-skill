"""Editable retail props, schematic stores and code-drawn customers.
Named product geometry remains in device_models; these props are generic teaching art.
"""
import math
from content_assets import Drawing,INK,GREEN,GOLD,PAPER
PROPS={
 'tablet':'iPad','laptop':'MacBook Air','desktop':'iMac','watch':'Apple Watch','earbuds':'AirPods',
 'phone-case':'iPhone 18 Pro 适配保护壳','screen-film':'iPhone 适配保护膜','usb-c-cable':'Apple USB-C 充电线','power-adapter':'Apple USB-C 电源适配器','magnetic-charger':'MagSafe 充电器',
 'speaker':'HomePod mini','keyboard':'Magic Keyboard','mouse':'Magic Mouse','stylus':'Apple Pencil','phone-stand':'iPhone 体验展架','shopping-bag':'购物袋',
 'stock-box':'库存包装盒','price-tag':'商品价签','receipt':'服务凭单','name-badge':'工作胸牌','display-table':'体验桌',
 'stool':'体验凳','accessory-wall':'配件陈列墙','service-counter':'服务台','store-sign':'门头标牌','monitor-sign':'信息屏'}

APPLE_PRODUCTS={
 'tablet':('ipad','https://www.apple.com.cn/ipad/','rounded thin slab, landscape camera and full-display bezel'),
 'laptop':('macbook-air','https://www.apple.com.cn/macbook-air/','thin aluminium base, rounded display and central notch'),
 'desktop':('imac','https://www.apple.com.cn/imac/','thin coloured display, lower chin and aluminium stand'),
 'watch':('apple-watch','https://www.apple.com.cn/watch/','rounded rectangular face, band and right digital crown'),
 'earbuds':('airpods','https://www.apple.com.cn/airpods/','white open-fit earbuds with short stems and compact charging case'),
 'speaker':('homepod-mini','https://www.apple.com.cn/homepod-mini/','spherical fabric-mesh body, flat foot and luminous top touch surface'),
 'keyboard':('magic-keyboard','https://www.apple.com.cn/shop/mac/accessories/mice-keyboards','low aluminium body, white square keys and extended space bar'),
 'mouse':('magic-mouse','https://www.apple.com.cn/shop/mac/accessories/mice-keyboards','smooth seamless white multitouch top, no visible scroll wheel or split buttons'),
 'stylus':('apple-pencil','https://www.apple.com.cn/apple-pencil/','white elongated pencil with narrow tip and flat side'),
 'magnetic-charger':('magsafe-charger','https://www.apple.com.cn/shop/accessories/all','round magnetic charging disc with connected USB-C cable'),
 'usb-c-cable':('apple-usb-c-cable','https://www.apple.com.cn/shop/accessories/all','white cable and symmetric rounded USB-C connectors'),
 'power-adapter':('apple-usb-c-adapter','https://www.apple.com.cn/shop/accessories/all','white rounded power adapter with a USB-C port'),
 'phone-case':('iphone-18-pro-case','https://www.apple.com.cn/iphone-18-pro/','unbranded iPhone-compatible case; wide camera platform opening'),
 'screen-film':('iphone-screen-film','https://www.apple.com.cn/iphone/','unbranded iPhone-compatible clear protective film'),
 'phone-stand':('iphone-display-stand','https://www.apple.com.cn/iphone-18-pro/','display fixture with the existing iPhone 18 Pro geometry')}
ALIASES={a:k for k,(a,_,_) in APPLE_PRODUCTS.items()}
PRODUCT_POLICY=dict(schema='course-products/1',allowedBrands=['Apple'],allowedCompatibleAccessories='unbranded with explicit Apple device compatibility',otherBrandsAllowed=False,checked='2026-10-23')

ROLES=['adult','senior','child','business-customer']
POSES=['stand','welcome','question','point','listen']
MOODS=['neutral','smile','concern','curious','relieved']

def catalog():return dict(props=[dict(id=APPLE_PRODUCTS[k][0] if k in APPLE_PRODUCTS else k,legacyId=k,title=v,brand='Apple' if k in APPLE_PRODUCTS and k not in ['phone-case','screen-film','phone-stand'] else 'Apple-compatible-unbranded' if k in APPLE_PRODUCTS else 'store-fixture',reference=APPLE_PRODUCTS[k][1] if k in APPLE_PRODUCTS else None) for k,v in PROPS.items()],productPolicy=PRODUCT_POLICY,people=dict(identities=ROLES,poses=POSES,expressions=MOODS),stores=['front','interior','isometric'],namedDevices='Use phone model=iphone-18-pro for the existing versioned geometry; generic props are not exact product models',source='original code geometry; no image generation')

def prop(r,s):
 b=Drawing(r,s);d=r.get('data',{});k=ALIASES.get(d.get('object','tablet'),d.get('object','tablet'))
 if d.get('brand','Apple') not in ['Apple','Apple-compatible-unbranded']:raise ValueError('本素材库只允许 Apple 产品及无其他品牌的 Apple 适配配件')
 if k not in PROPS:raise ValueError('未知门店物品 '+str(k))
 color=d.get('color','#a2b4bc');screen=d.get('screenColor','#d7e6e7');c=[]
 def rect(key,x,y,w,h,f,**kw):c.append(b.rect(key,x,y,w,h,f,**kw))
 def ellipse(key,x,y,w,h,f,**kw):c.append(b.ellipse(key,x,y,w,h,f,**kw))
 def path(key,path,f=None,stroke=INK,lw=3):c.append(b.path(key,path,f,stroke,lw))
 if k in ['tablet','laptop','desktop','monitor-sign']:
  rect('shell',40,35,400,270,color,radius=22,stroke=INK,lineWidth=3);rect('screen',54,49,372,242,screen,radius=14)
  rect('ui-head',78,76,170,18,'#608895');rect('ui-copy',78,119,250,11,'#a9bdba');rect('ui-copy2',78,145,210,11,'#a9bdba');rect('ui-picture',78,181,110,80,'#e8c391');rect('ui-pane',208,181,185,80,'#b8cfbd')
  ellipse('camera',240,42,5,5,INK)
  if k=='laptop':
   rect('notch',211,49,58,14,'#273a40',radius=5)
   for row in range(3):
    for col in range(11):rect(f'base-key-{row}-{col}',75+col*30,307+row*9,23,6,'#53616a',radius=1)
  if k=='desktop':rect('chin',45,266,390,35,color,radius=0)
  if k=='laptop':path('keyboard-base','M 40 305 L 0 355 L 480 355 L 440 305 Z','#cad3d4');rect('trackpad',185,320,110,22,'#b0babc',radius=5)
  if k in ['desktop','monitor-sign']:path('neck','M 220 305 L 260 305 L 270 370 L 210 370 Z','#b7c3c5');rect('base',165,367,150,16,'#a1aeb2')
 elif k=='watch':
  rect('strap-top',168,0,144,150,d.get('strapColor','#c79879'),radius=40);rect('strap-bottom',168,240,144,160,d.get('strapColor','#c79879'),radius=40);rect('body',130,98,220,210,color,radius=52,stroke=INK,lineWidth=4);rect('glass',143,111,194,184,'#253d46',radius=44);ellipse('dial',240,203,130,130,None,stroke='#7cb6b1',lineWidth=5);path('hands','M 240 155 L 240 203 L 276 220',None,'#ffffff',6);rect('crown',350,156,15,34,'#89979e')
 elif k=='earbuds':
  # Open-fit AirPods family: short stems, curved earbud shell, compact white case.
  rect('case',105,208,270,155,'#fafbf8',radius=65,stroke='#93a5aa',lineWidth=3);path('lid','M 112 255 Q 240 275 368 255',None,'#aebcbf',3);ellipse('led',240,293,6,6,GREEN)
  for i,x in enumerate([164,316]):
   path('bud'+str(i),f'M {x-40} 76 C {x-51} 35 {x+27} 24 {x+43} 63 C {x+55} 91 {x+21} 115 {x+1} 104 L {x+8} 173 Q {x-5} 190 {x-22} 173 L {x-25} 113 Q {x-45} 103 {x-40} 76 Z','#fafbf8','#93a5aa',2)
   ellipse('grille'+str(i),x-18,73,26,15,'#273f46');ellipse('vent'+str(i),x+19,63,8,14,'#354b50');path('stem-line'+str(i),f'M {x-15} 121 L {x-9} 167',None,'#d6dfdc',2)
 elif k in ['phone-case','screen-film']:
  rect('outline',135,5,210,380,color if k=='phone-case' else '#dcebf188',radius=38,stroke=INK,lineWidth=4)
  if k=='phone-case':rect('cutout',148,22,184,78,PAPER,radius=18,stroke=INK,lineWidth=2)
  else:rect('front-sensor-clearance',212,17,56,14,'#f3f5ef',radius=7)
  if k=='screen-film':path('peel','M 290 5 L 345 60 L 290 60 Z','#b9d5e1');path('shine','M 160 310 L 310 140',None,'#ffffff',8)
 elif k=='usb-c-cable':
  path('cable','M 85 115 C 0 260 80 385 225 315 C 370 240 250 130 185 200 C 120 280 295 390 400 225',None,color,15)
  for i,(x,y) in enumerate([(70,40),(382,148)]):rect('plug'+str(i),x,y,42,80,'#f4f6f3',radius=13,stroke=INK,lineWidth=3);rect('usb'+str(i),x+7,y-20,28,25,'#a2b2b9',radius=6,stroke=INK,lineWidth=2)
 elif k=='power-adapter':
  rect('case',130,95,220,225,'#f4f6f4',radius=36,stroke='#9cabae',lineWidth=3);rect('port',194,260,92,24,'#2e4249',radius=12)
  for i,x in enumerate([184,273]):rect('prong'+str(i),x,45,22,65,'#b6c2c8',radius=3)
 elif k=='magnetic-charger':ellipse('pad',235,155,220,220,'#e8efed',stroke='#9badb0',lineWidth=5);ellipse('coil',235,155,164,164,None,stroke='#cad4d0',lineWidth=4);path('cord','M 235 266 L 235 320 Q 235 370 340 375',None,'#a8b8b6',10)
 elif k=='speaker':
  ellipse('body',240,224,286,272,color,stroke='#6d858d',lineWidth=3)
  for i in range(12):
   y=120+i*18;half=math.sqrt(max(0,1-((y-224)/136)**2))*140
   path('mesh-h'+str(i),f'M {240-half} {y} Q 240 {y+15} {240+half} {y}',None,'#779198',1)
  for i in range(9):path('mesh-v'+str(i),f'M {170+i*17} 112 Q {145+i*23} 224 {175+i*16} 342',None,'#8da5aa',1)
  ellipse('top',240,103,150,51,'#e2e8e9',stroke='#7f999f',lineWidth=3);ellipse('siri-light',240,103,88,28,'#c2cbdc');path('plus','M 278 96 L 278 110 M 270 103 L 286 103',None,'#647580',2);path('minus','M 194 103 L 208 103',None,'#647580',2);rect('foot',186,344,108,12,'#8da5a7',radius=5)
 elif k=='keyboard':
  rect('base',10,100,460,210,color,radius=22,stroke=INK,lineWidth=3)
  for row in range(4):
   for col in range(10):rect(f'key-{row}-{col}',24+col*44,115+row*38,34,28,'#f6f8f5',radius=4)
  rect('space',130,275,220,22,'#f6f8f5',radius=4)
 elif k=='mouse':
  ellipse('base',240,211,194,288,'#a7b7bf',stroke='#93a5aa',lineWidth=2);ellipse('seamless-top',240,199,184,276,'#fafbf9',stroke='#a6b5b9',lineWidth=2);path('side-reflection','M 170 141 Q 155 227 184 294',None,'#e3eae6',5)
 elif k=='stylus':path('body','M 120 330 L 322 60 L 344 76 L 143 345 Z','#f5f6f2');path('tip','M 120 330 L 112 360 L 143 345 Z','#adbfc7')
 elif k=='phone-stand':
  from content_assets import phone
  path('stem','M 190 275 L 220 110 L 270 110 L 300 275 Z','#becaca');rect('base',120,275,240,60,'#ecf0ec',radius=20,stroke=INK,lineWidth=3)
  handset,_=phone(dict(id=r['id']+'-iphone',sceneId=s['id'],x=180,y=0,scale=.30,startFrame=b.a,endFrame=b.z,data=dict(model='iphone-18-pro',finish='silver',view='front')),s);c.append(handset)
 elif k=='shopping-bag':
  path('bag','M 90 110 L 390 110 L 420 370 L 60 370 Z',d.get('bagColor','#f6efe0'));path('handle','M 160 132 L 160 80 Q 240 0 320 80 L 320 132',None,INK,10);c.append(b.text('label',d.get('label','酷果星创'),240,245,38,GREEN,align='center'))
 elif k=='stock-box':
  path('top','M 50 100 L 300 20 L 440 120 L 190 200 Z','#e7d4a6');path('front','M 50 100 L 190 200 L 190 370 L 50 270 Z','#c6aa76');path('side','M 190 200 L 440 120 L 440 290 L 190 370 Z','#d7bd8d');rect('label',235,200,150,66,'#fbf9f1');c.append(b.text('code',d.get('label','教学示意'),249,220,24,INK))
 elif k in ['price-tag','receipt','name-badge']:
  ww,hh=(430,220) if k!='receipt' else (300,380);xx=(480-ww)/2;rect('paper',xx,10,ww,hh,'#fffcf5',radius=14,stroke='#aab6ae',lineWidth=3)
  c.append(b.text('title',d.get('title',PROPS[k]),240,48,34,INK,align='center'))
  if k=='name-badge':ellipse('clip',240,14,26,26,GOLD);c.append(b.text('name',d.get('name','姓名 / 岗位'),240,126,30,GREEN,align='center'))
  else:
   for i,line in enumerate(d.get('lines',['项目名称','以实际信息为准'])):c.append(b.text('line'+str(i),line,xx+25,110+i*53,26,INK))
 elif k=='display-table':
  path('top','M 25 80 L 345 35 L 465 115 L 145 160 Z','#f9faf7');path('edge','M 25 80 L 145 160 L 465 115 L 465 140 L 145 185 L 25 105 Z','#d1d9d2')
  for i,(x,y) in enumerate([(40,105),(145,183),(432,143)]):rect('leg'+str(i),x,y,25,200,'#d8ded8',radius=8)
 elif k=='stool':ellipse('seat',240,100,230,90,'#f9f9f2',stroke='#97a9a8',lineWidth=3);path('legs','M 155 115 L 130 360 M 325 115 L 350 360 M 175 125 L 190 350 M 305 125 L 290 350',None,'#a4b1af',9);path('brace','M 146 255 L 336 255',None,'#a4b1af',6)
 elif k=='accessory-wall':
  rect('frame',20,0,440,390,'#bfc9c7',radius=10);rect('inside',35,15,410,360,'#e9ede6',radius=3)
  for row in range(4):
   for col in range(7):rect(f'pack-{row}-{col}',50+col*56,32+row*84,40,64,['#f7f8f2','#c5d6d7','#dfc9ad'][(row+col)%3],radius=4,stroke='#a5b5b2',lineWidth=1)
 elif k=='service-counter':rect('top',20,100,440,30,'#fbfcf5',radius=6);rect('front',35,130,410,250,'#d7ded6',radius=8);rect('drawer-line',55,220,370,3,'#9aaba2',radius=0);rect('screen',240,15,145,85,'#2b454c');rect('stand',300,100,25,15,'#849797')
 elif k=='store-sign':
  rect('frame',5,95,470,150,'#525d61',radius=3);c.append(b.text('label',d.get('label','KG 酷果星创'),240,140,48,'#ffffff',align='center'));rect('seal',411,139,28,60,'#bc3d44',radius=3)
 elif k=='monitor-sign':pass
 root=b.group('root',r.get('x',0),r.get('y',0),c,480,400,scaleX=r.get('scale',1),scaleY=r.get('scale',1))
 return root,dict(kind='retail-prop',object=k,title=PROPS[k],productFamily=APPLE_PRODUCTS[k][0] if k in APPLE_PRODUCTS else None,brand='Apple' if k in APPLE_PRODUCTS and k not in ['phone-case','screen-film','phone-stand'] else 'Apple-compatible-unbranded' if k in APPLE_PRODUCTS else 'store-fixture',reference=APPLE_PRODUCTS[k][1] if k in APPLE_PRODUCTS else None,features=APPLE_PRODUCTS[k][2] if k in APPLE_PRODUCTS else None,accuracy='editable teaching schematic; not engineering dimensions or exact product specification')

def customer(r,s):
 b=Drawing(r,s);d=r.get('data',{});who=d.get('identity','adult');pose=d.get('pose','stand');mood=d.get('mood','smile')
 if who not in ROLES or pose not in POSES or mood not in MOODS:raise ValueError('未实现的顾客身份/姿态/表情')
 skin=d.get('skin','#dfad87');shirt=d.get('shirt','#a2baca' if who!='child' else '#d6ae64');pants=d.get('pants','#445761');hair='#b6b8b3' if who=='senior' else '#3c3938';c=[]
 c += [b.rect('leg-l',160,400,46,175,pants,radius=18),b.rect('leg-r',232,400,46,175,pants,radius=18),b.rect('shoe-l',147,552,65,27,'#394c52'),b.rect('shoe-r',229,552,65,27,'#394c52')]
 c.append(b.path('body','M 145 220 Q 217 195 290 220 L 288 424 L 150 424 Z',shirt,None));c.append(b.rect('neck',201,180,34,48,skin,radius=12));c.append(b.ellipse('head',218,145,130,150,skin));c.append(b.path('hair','M 151 147 Q 130 55 210 53 Q 292 41 287 145 L 265 118 Q 228 133 181 96 L 166 154 Z',hair,None))
 for i,x in enumerate([194,243]):c.append(b.ellipse('eye'+str(i),x,150,7,9,INK))
 mouth='M 198 179 Q 218 194 239 179' if mood in ['smile','relieved'] else 'M 202 184 Q 220 176 236 184' if mood=='concern' else 'M 205 183 L 233 183'
 c.append(b.path('mouth',mouth,None,'#7c4a3e',3))
 if mood=='curious':c.append(b.path('brow','M 184 133 L 205 127',None,hair,3))
 if who=='business-customer':c += [b.path('jacket','M 148 219 L 190 205 L 217 360 L 244 205 L 289 219 L 289 425 L 147 425 Z',d.get('jacket','#526777'),None),b.path('tie','M 213 227 L 225 227 L 233 310 L 218 331 L 205 310 Z',GOLD,None)]
 if who=='senior':c.append(b.path('glasses','M 174 142 L 208 142 L 208 164 L 174 164 Z M 231 142 L 264 142 L 264 164 L 231 164 Z M 208 150 L 231 150',None,'#6a7776',3))
 a=[(161,237,139,370),(280,236,302,369)]
 if pose=='welcome':a[1]=(280,236,353,230)
 if pose=='point':a[1]=(280,236,384,173)
 if pose=='question':a[1]=(280,236,314,149)
 if pose=='listen':a[0]=(161,237,193,336)
 for i,(x,y,z,v) in enumerate(a):c.append(b.path('arm'+str(i),f'M {x} {y} Q {(x+z)/2-12} {(y+v)/2} {z} {v}',None,shirt,32));c.append(b.ellipse('hand'+str(i),z,v,28,31,skin))
 if who=='child':c.append(b.ellipse('shirt-motif',218,310,50,50,'#f2dfac'))
 scale=r.get('scale',1)*(.73 if who=='child' else 1)
 return b.group('root',r.get('x',0),r.get('y',0),c,440,590,scaleX=scale,scaleY=scale),dict(kind='retail-person',identity=who,pose=pose,mood=mood,source='code-drawn fictional customer; not an approved branded master or real employee')

def store(r,s):
 b=Drawing(r,s);d=r.get('data',{});view=d.get('view','interior');c=[]
 if view not in ['front','interior','isometric']:raise ValueError('未知门店视角')
 def rect(k,x,y,w,h,f,**kw):c.append(b.rect(k,x,y,w,h,f,**kw))
 def path(k,p,f=None,stroke=None,lw=2):c.append(b.path(k,p,f,stroke,lw))
 rect('wall',0,0,1600,840,'#f2f1e8',radius=0)
 path('floor','M 0 840 L 1600 840 L 1300 500 L 300 500 Z','#dbc8aa')
 path('left-wall','M 0 0 L 300 170 L 300 500 L 0 840 Z','#ddded6');path('right-wall','M 1300 170 L 1600 0 L 1600 840 L 1300 500 Z','#e4e6df')
 for i in range(8):path('floor-line'+str(i),f'M {i*220-100} 840 L {500+i*85} 500',None,'#c6b799',1)
 for i in range(4):path('ceiling-light'+str(i),f'M {250+i*340} 0 L {590+i*135} 155',None,'#ffffff',9)
 rect('video-screen',575,205,450,180,'#bfd8dc',radius=3);c.append(b.text('screen-title',d.get('screenTitle','欢迎体验'),800,255,56,INK,align='center'))
 for side in [0,1]:
  for j in range(3):
   rr={'id':r['id']+f'-wall-{side}-{j}','sceneId':s['id'],'startFrame':b.a,'endFrame':b.z,'x':30+side*1260,'y':190+j*135,'scale':.63,'data':{'object':'accessory-wall'}}
   n,_=prop(rr,s);c.append(n)
 for i,(x,y,z) in enumerate([(350,480,.85),(820,480,.85),(270,620,1.12),(820,620,1.12)]):
  rr={'id':r['id']+'-table'+str(i),'sceneId':s['id'],'startFrame':b.a,'endFrame':b.z,'x':x,'y':y,'scale':z,'data':{'object':'display-table'}};n,_=prop(rr,s);c.append(n)
  for j in range(3):
   rr={'id':r['id']+f'-device{i}-{j}','sceneId':s['id'],'startFrame':b.a,'endFrame':b.z,'x':x+85+j*90*z,'y':y-15,'scale':z*.15,'data':{'object':'phone-stand'}};n,_=prop(rr,s);c.append(n)
 if view=='front':
  rect('header',0,0,1600,145,'#515b5e',radius=0);c.append(b.text('sign',d.get('sign','KG 酷果星创'),800,44,78,'#ffffff',align='center'));rect('seal',1110,49,34,68,'#b83f49',radius=3)
  rect('left-frame',0,145,70,695,'#b7c1bd',radius=0);rect('right-frame',1530,145,70,695,'#b7c1bd',radius=0);path('glass','M 80 145 L 320 180 L 320 760 L 80 835 Z','#c8e3e34d','#adbeb7',3)
 if view=='isometric':
  # Authored 2.5D schematic, not a camera-measured reconstruction.
  for n in c:n['x']=(n.get('x',0))*.8+160
 root=b.group('root',r.get('x',0),r.get('y',0),c,1600,840,scaleX=r.get('scale',1),scaleY=r.get('scale',1))
 return root,dict(kind='store-scene',view=view,accuracy='schematic inspired by retail layout; photo-linked variants live in the private user library',editable=['sign','screenTitle','display furniture','wall products','colors'])
