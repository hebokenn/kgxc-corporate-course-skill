"""Business demonstrations: every action has a concrete retail object and outcome.
No anonymous colour-block fallback is allowed in this user-facing gallery.
"""
import copy
from content_assets import Drawing,phone,document,actor
from retail_assets import prop
from motion_catalog import CATALOG
# Domain describes the object that actually moves or changes, not a style alias.
CASES={
 'chars-in':('说清本次体验目标','用 iPhone 拍清孩子运动瞬间','text'),
 'text-rise':('先讲本次使用场景','带着真实场景开始体验','text'),
 'blur-in':('从模糊需求到清晰任务','先确认最在意的使用问题','text'),
 'typewriter':('记录顾客自己的原话','希望给家人拍照更方便','text'),
 'draw-on':('把服务步骤连接起来','需求 → 体验 → 核对结果','path'),
 'mask-reveal':('打开本次体验记录','把顾客需求与观察结果放到同一张记录里','record'),
 'marker':('标出顾客最关心的条件','这次先验证拍照效果','text'),
 'underline':('明确下一步动作','请顾客亲手试拍一次','text'),
 'assemble':('准备一套 iPhone 体验物品','iPhone、MagSafe 与充电线分别就位','kit'),
 'explode':('分别核对盒内物品','让设备、线材与凭单各自对应','kit'),
 'paper-fold':('展开服务工作单','从封面展开到任务与注意事项','record'),
 'scan':('扫描核对设备信息','检视范围覆盖设备与记录中的对应项目','scan'),
 'spotlight':('只看当前要核对的字段','保留整张工作单的上下文','spotlight'),
 'magnify':('放大检查 iPhone 摄像头区域','原物与局部特写保持同一对象','detail'),
 'path-follow':('沿正确服务动线移动','从体验桌前往服务台','carrier'),
 'handoff':('交接已经核对的服务记录','店员提交，店长接收同一份记录','handoff'),
 'sort':('将配件放回对应陈列位置','按用途归位，不靠物品颜色分类','kit'),
 'group-collect':('把顾客问题分到对应主题','拍照、数据、充电分别归组','records'),
 'branch-grow':('把使用需求拆成可验证问题','从拍照需求展开到三个观察角度','branches'),
 'compare-wipe':('对照体验前后的记录','新信息沿分界显露，原记录仍可对照','comparison'),
 'correct-replace':('修正记录中的错误口径','先核实条件，再替换旧记录','text'),
 'count-up':('统计已经完成的核对项','示例数量，不代表真实业绩','number'),
 'odometer':('显示逐项核验后的累计数','保留同一个统计对象','number'),
 'bar-grow':('对比两组示例体验次数','所有数量从共同零点起算','bar'),
 'ring-progress':('显示工作单核对进度','示例：完成四分之三','ring'),
 'area-fill':('显示 iPad 内容准备进度','进度只表示本次演示状态','fill'),
 'record-filter':('筛出需要后续联系的顾客','已完成的记录退出，待跟进记录保留','records'),
 'dot-aggregate':('把单次体验记录汇成数量','每个小设备代表一条示例记录','units'),
 'timeline-reflow':('调整员工任务时段','准备、接待与交接时段同步变化','schedule'),
 'route-progress':('按顺序走完服务流程','当前位置与已完成路线同时可见','path'),
 'dialogue':('顾客提问后由店员回应','气泡归属明确，问答内容可读','dialogue'),
 'quiz-feedback':('判断哪种回应更贴近需求','先选择，再展示解释','quiz'),
 'callout':('标注 iPhone 的当前检查位置','引线终点落在真实物件上','callout'),
 'flow-token':('传递同一份服务信息','信息从接待记录流转到交接记录','path'),
 'presenter-gesture':('店长指向当前知识点','使用原版黑衣 KG 店长形象','presenter'),
 'pixel-walk':('完成三个门店服务任务站','任务对象沿地面到达终点','carrier'),
 'split-merge':('把复杂问题拆开核对后汇总','需求、条件与结果分别检查再合并','records'),
 'balance':('用同一基线比较示例数量','三个柱形各自带有明确项目','bars'),
 'rotate-inspect':('在同一设备的正背面间检查','真实 iPhone 正面与背面分别绑定','device-faces'),
 'gauge-sweep':('把示例读数指向量表位置','读数变化可从刻度直接判断','gauge'),
 'threshold-cross':('根据明确阈值判断当前状态','示例阈值与数量条同时保留','threshold'),
 'venn-intersect':('找出需求与条件的共同部分','体验方案位于两个范围的交集','venn'),
 'swimlane-transfer':('跨岗位交接服务工作单','从店员职责区进入店长复核区','swimlane'),
 'parallel-sync':('两项准备完成后开始体验','设备准备、内容准备汇到同一节点','parallel'),
 'evidence-attach':('给结论附上实际核对依据','观察记录连接到对应判断','evidence'),
 'check-draw':('核对完成后留下可见标记','勾选位置对应真实检查项','check'),
 'cross-draw':('划除不适合本次需求的方案','先确认不适合的具体原因','cross'),
 'brace-draw':('把同一条件下的项目括在一起','让条件的适用范围看得见','brace'),
 'stack-push':('把新接待记录放入待处理栈','新记录在顶层，原记录下移','record-stack'),
 'stack-pop':('取出当前优先处理的记录','只取顶层，其余记录补位','record-stack'),
 'queue-enqueue':('下一位顾客进入等候队列','保留现有先后次序','people'),
 'queue-dequeue':('队首顾客开始体验','其余顾客依次向前','people'),
 'grid-deal':('把 iPad 发放到体验工位','设备从准备点分发到各工位','ipads'),
 'fan-spread':('展开三个 Apple 配件选项','分别核对 MagSafe、线材与电源','kit'),
 'card-flip':('翻开同一案例的处理依据','正面是问题，背面是核对提示','case-faces'),
 'page-turn':('从服务目标翻到工作步骤','下一页内容在翻页中显露','case-faces'),
 'carousel-shift':('轮流查看 Apple 体验设备','iPhone、iPad 与 Mac 进入当前位置','devices'),
 'accordion-open':('逐项展开接待记录的内容','标题保留，细节获得阅读空间','accordion'),
 'focus-isolate':('从三个问题中聚焦当前问题','其他问题仍保留但降低存在感','records'),
 'rank-reorder':('按顾客优先级重排体验任务','物件随对应需求一起移动','tasks'),
 'lane-distribute':('把任务分给对应岗位','同一入口分到店员与店长职责区','swimlane'),
 'cluster-pack':('按主题汇集顾客问题','每张小便签进入对应主题区','notes'),
 'tree-collapse':('讲完细节后回到核心需求','子问题收回到同一个中心','branches'),
 'connector-reroute':('调整服务信息的交接路线','原起点和终点保持身份','path'),
 'arrow-travel':('指出顾客下一步去哪里体验','方向箭头沿实际门店动线行进','path'),
 'dash-march':('表示服务信息持续同步','线路与端点保留，传输方向可见','path'),
 'chain-link':('把独立检查环节接成一条链','需求、验证、反馈依次接合','tasks'),
 'dependency-unlock':('完成前置核对后才进入体验','后续任务随前置条件满足而激活','tasks'),
 'progress-segments':('逐段完成接待准备清单','每一步有明确业务名称','steps'),
 'checklist-tick':('逐项核对交接清单','核验标记直接落到对应项目上','checklist'),
 'stamp-approve':('在工作单上登记复核通过','章面与工作单属于同一个复核情境','stamp'),
 'redaction-reveal':('逐行揭示案例的核对信息','遮挡后面是实际案例文字','redaction'),
 'signature-write':('在交接记录上留下签收示意','笔尖沿签名轨迹移动','signature'),
 'cursor-click':('点击 iPad 体验页的指定按钮','指针抵达真实按钮后给出反馈','ui-click'),
 'drag-drop':('把待跟进记录归入正确位置','先提起，再移动，最后落下','drag-record'),
 'swipe-pan':('横向浏览 iPhone 体验照片示意','滑动限制在设备显示视窗内','photo-strip'),
 'pinch-zoom':('放大一张体验结果图','缩放中心与两个接触点一致','photo-result'),
 'scroll-window':('在 iPad 视窗中滚动服务记录','内容留在固定显示窗口内','scroll-records'),
 'tab-switch':('在需求与体验结果两个页签间切换','选中页签与当前内容对应','case-faces'),
 'toggle-switch':('演示开关从关闭变为开启','用示意界面解释状态，不冒充真实系统菜单','toggle'),
 'slider-adjust':('在 iPad 示意界面调整体验音量','滑块停在对应的刻度位置','slider'),
 'dropdown-expand':('展开本次后续服务的选项','选项次序与标题保持联系','dropdown'),
 'notification-slide':('显示本次交接已到达的通知','通知进入后停稳供阅读','notification'),
 'tooltip-point':('说明 iPhone 上的当前检查目标','提示引线先落点，再展开文字','tooltip'),
 'search-match':('在记录中定位顾客关心的词','定位实际存在的需求关键词','search'),
 'table-row-insert':('把新的服务记录插入表格','原记录让出一行空间','table'),
 'table-row-delete':('移除已经合并的重复记录','后续记录上移补齐行位','table'),
 'cell-update':('将工作单状态改为已核对','同一单元格先后显示旧值与新值','status'),
 'column-resize':('为顾客原话增加记录列宽','右侧列随边界移动，保持邻接','table-columns'),
 'pie-sector':('表示示例服务类别占比','分子、总量与扇区属于同一范围','pie'),
 'line-plot':('逐点连接示例体验记录','点位与顺序可逐一追踪','linechart'),
 'scatter-converge':('把离散观察点归入参考位置','每条记录保持自己的身份','units'),
 'histogram-bin':('把等待时长记录分到区间','每条记录落入对应频数箱','units'),
 'ratio-normalize':('将不同数量换算为共同总宽','比例段共享一个总量','ratio'),
 'waterfall-step':('逐步展示示例任务数的增减','每一步从上一累计值继续','waterfall'),
 'funnel-narrow':('观察示例服务步骤中的留存数量','各阶段按同一范围显示数量','funnel'),
 'orbit-revolve':('围绕 iPhone 检查配件位置','移动对象保持在产品检查区内','orbit'),
 'pendulum-swing':('展示悬挂式价签的受力摆动','悬点固定，价签围绕悬点摆动','tag'),
 'gear-turn':('用齿轮隐喻说明岗位配合','转动发生在明确的传动轴心','gear'),
 'spring-compress':('演示缓冲结构受力后恢复','受力方向与恢复状态可见','spring'),
}
assert set(CASES)==set(CATALOG),(set(CATALOG)-set(CASES),set(CASES)-set(CATALOG))

class Demo:
 def __init__(self,kind,scene,a,z,roles):
  self.kind=kind;self.sid=scene;self.a=a-30;self.z=z+30;self.roles=roles;self.count=0;self.context=[]
 def n(self,t,**kw):
  self.count+=1;return dict(id=self.kind+'-demo-'+str(self.count),type=t,sceneId=self.sid,role='subject',**kw)
 def text(self,t,x,y,size=31,fill='#244946',**kw):return self.n('text',text=t,x=x,y=y,fontSize=size,fill=fill,width=1000,height=size*1.5,**kw)
 def rect(self,x,y,w,h,fill='#fffdf7',**kw):return self.n('rect',x=x,y=y,width=w,height=h,fill=fill,radius=kw.pop('radius',10),**kw)
 def group(self,children,x=0,y=0,w=1040,h=460,**kw):return self.n('group',x=x,y=y,width=w,height=h,children=children,**kw)
 def product(self,object,x,y,scale=.55):
  recipe=dict(id=self.kind+'-product-'+str(self.count),sceneId=self.sid,x=x,y=y,scale=scale,startFrame=self.a,endFrame=self.z,data=dict(object=object))
  n,_=prop(recipe,dict(id=self.sid,sourceStartFrame=self.a,sourceEndFrame=self.z));self.count+=1;return n
 def iphone(self,x,y,scale=.52,view='front'):
  recipe=dict(id=self.kind+'-iphone-'+str(self.count),sceneId=self.sid,x=x,y=y,scale=scale,startFrame=self.a,endFrame=self.z,data=dict(model='iphone-18-pro',finish='glacier-blue',view=view))
  n,_=phone(recipe,dict(id=self.sid,sourceStartFrame=self.a,sourceEndFrame=self.z));self.count+=1;return n
 def person(self,identity,x,y,scale=.5):
  if identity in ['C01','C02','C03']:
   data=self.roles[identity];ww,hh=data['sourceSize'];return self.group([self.n('image',x=0,y=0,width=ww,height=hh,assetId=data['headAsset'])],x,y,ww,hh,scaleX=scale*810/hh,scaleY=scale*810/hh)
  recipe=dict(id=self.kind+'-person-'+str(self.count),sceneId=self.sid,x=x,y=y,scale=scale,startFrame=self.a,endFrame=self.z,data=self.roles[identity]);self.count+=1;n,_=actor(recipe,dict(id=self.sid,sourceStartFrame=self.a,sourceEndFrame=self.z));return n
 def sheet(self,title,lines,x,y,width=280,height=250):
  c=[self.rect(0,0,width,height,'#fffdf6',stroke='#aec0b5',lineWidth=2),self.rect(0,0,width,48,'#dfe8dd'),self.text(title,18,10,27)]
  for i,line in enumerate(lines):c += [self.text(line,18,73+i*52,24),self.rect(18,111+i*52,width-36,1,'#d8dfd2',radius=0)]
  return self.group(c,x,y,width,height)
 def support(self):
  # A stable caption explains the observed outcome, separate from the moving subject.
  return [self.text(CASES[self.kind][0],115,286,35),self.text(CASES[self.kind][1],115,884,28,'#647b6d')]


def create(kind,scene,start,end,roles):
 info=CATALOG[kind];domain=CASES[kind][2];b=Demo(kind,scene,start,end,roles);typ=info['nodes'][0];typ='group' if typ=='*' else typ
 e=dict(type=kind,startFrame=start,endFrame=end,**copy.deepcopy(info.get('sample',{})))
 labels=['顾客需要','体验观察','后续核对'];children=[];context=b.support();x,y=380,390;w,h=1110,420
 # Put real owners and destinations behind moving handoffs.
 if domain in ['swimlane','handoff','parallel']:
  for i,(name,role) in enumerate([('店员接待职责','S01'),('店长复核职责','M1')]):
   xx=150+i*840;context += [b.rect(xx,360,790,455,'#e6ebde' if i==0 else '#ece3d0',stroke='#b9c6b6',lineWidth=2),b.text(name,xx+25,380,32),b.person(role,xx+35 if i==0 else xx+510,444,.39)]
  x,y=540,455;w,h=280,210;e.update(dx=600,dy=145,lift=50)
 if domain in ['record','record-stack','records','comparison','case-faces','evidence','drag-record','notification','dialogue','quiz','accordion','dropdown','checklist','steps','tasks']:
  count=5 if domain in ['checklist','steps','accordion','dropdown'] else 4 if domain in ['records','tasks'] else 3
  for i in range(count):
   title=['拍照需求','数据整理','充电使用','后续服务','体验反馈'][i%5]
   lines=[['家庭记录','邀请亲手试拍','核对观察结果'],['保留重要资料','确认迁移范围','再说明后续操作'],['核对设备接口','选择适配配件','观察连接结果']][i%3]
   children.append(b.sheet(title,lines,i*285,0,265,240))
  if count>3:
   children=[b.sheet(['准备设备','确认需要','邀请体验','核对结果','做好交接'][i],['当前任务','完成后进入下一步'],i%3*350,i//3*195,320,165) for i in range(count)];x,y=350,380;w,h=1200,440
 elif domain in ['kit','devices','ipads']:
  if domain=='devices':children=[b.iphone(0,0,.43),b.product('ipad',310,45,.52),b.product('macbook-air',650,45,.53)]
  elif domain=='ipads':children=[b.product('ipad',i*300,i%2*100,.5) for i in range(4)]
  else:children=[b.iphone(0,0,.44,view='back'),b.product('magsafe-charger',310,30,.55),b.product('apple-usb-c-adapter',660,25,.57)]
 elif domain=='people':
  children=[b.person(k,i*350,0,.48) for i,k in enumerate(['C01','C02','C03'])];x,y=350,380;w,h=1100,440
 elif domain in ['units','notes']:
  count=18 if domain=='units' else 8;children=[]
  for i in range(count):
   if domain=='units':children.append(b.group([b.rect(0,0,46,79,'#b8cde0',radius=9,stroke='#446576',lineWidth=2),b.rect(8,12,30,54,'#edf4f0',radius=3),b.text(str(i+1),12,28,18)],i%9*105,i//9*130,46,79))
   else:children.append(b.sheet(['拍照','数据','充电'][i%3],[str(i+1)+'号问题'],i%4*260,i//4*180,230,145))
  x,y=380,420;w,h=1120,380
 elif domain in ['bars','ratio','waterfall','funnel','schedule','table','table-columns']:
  count=4 if domain not in ['table','table-columns'] else 5
  for i in range(count):
   if domain in ['table','table-columns']:children.append(b.group([b.rect(0,0,1000,64,'#fffdf8' if i%2 else '#e1e9de',radius=0,stroke='#c1cdbc',lineWidth=1),b.text(['待跟进','已核对','待体验','已交接','待确认'][i],20,16,26),b.text(['拍照问题','数据需求','充电体验','配件适配','服务记录'][i],270,16,26),b.text('记录 '+str(i+1),780,16,26)],0,i*68,1000,64))
   else:children.append(b.group([b.rect(0,0,190,135,['#66978b','#bd945d','#769dac','#a69a79'][i],radius=4),b.text(['准备','体验','核对','交接'][i],22,147,25)],i*250,170-i*35,190,180))
 elif domain=='branches':
  context.append(b.sheet('顾客需求',['给家人拍照'],140,520,260,160));children=[]
  for i,t in enumerate(['拍摄对象','常见场景','体验结果']):children += [b.n('path',x=0,y=0,points=[[0,175],[320,175],[530,i*150+35]],path=f'M 0 175 L320 175 L530 {i*150+35}',fill=None,stroke='#6c9481',lineWidth=5),b.text(t,560,i*150,38)]
  x,y=450,390
 elif domain=='callout':
  context.append(b.iphone(260,350,.64,view='back'));children=[b.n('path',x=0,y=0,points=[[0,0],[260,0],[420,110]],path='M0 0 L260 0 L420 110',fill=None,stroke='#b1854e',lineWidth=5),b.sheet('检查目标',['摄像头区域','保持同一台设备'],460,80,330,200)];x,y=500,440
 elif domain=='venn':
  children=[b.n('ellipse',x=350,y=220,width=420,height=340,fill='#87ab9b88'),b.n('ellipse',x=750,y=220,width=420,height=340,fill='#d8b77c88'),b.text('可验证的体验',440,205,34)];x,y=250,375
 elif domain=='device-faces':children=[b.iphone(0,0,.46,'front'),b.iphone(0,0,.46,'back')];e['faceIndices']=[0,1];x,y=730,365;w,h=250,430
 elif domain=='orbit':
  context.append(b.iphone(750,390,.5,'back'));children=[b.product('magsafe-charger',0,0,.38)];x,y=1030,480;w,h=250,250;e.update(radiusX=150,radiusY=55)
 elif domain=='tag':children=[b.product('price-tag',0,70,.72)];x,y=680,400;w,h=400,300
 elif domain=='gear':
  import math
  pts=[]
  for j in range(48):
   a=j*math.pi/24;r=125 if j%4<2 else 155;pts.append([230+math.cos(a)*r,210+math.sin(a)*r])
  children=[b.n('path',x=0,y=0,path='M'+' L'.join(f'{a},{z}' for a,z in pts)+' Z',fill='#8eabb3',stroke='#42626c',lineWidth=4),b.n('ellipse',x=230,y=210,width=90,height=90,fill='#f1f0e7'),b.text('岗位协同',390,165,42)];x,y=500,370;w,h=460,420
 elif domain=='spring':
  pts=[[150,0]]+[[95 if j%2 else 205,30+j*28] for j in range(11)]+[[150,365]];children=[b.n('path',x=0,y=0,points=pts,path='M'+' L'.join(f'{a},{z}' for a,z in pts),fill=None,stroke='#66888f',lineWidth=13),b.rect(70,360,160,22,'#a6bab8')];x,y=790,390;w,h=300,385
 elif domain in ['photo-strip','photo-result','scroll-records']:
  context += [b.rect(220,350,1460,470,'#94aab0',radius=32),b.rect(250,380,1400,410,'#fbfcf5',radius=20),b.n('ellipse',x=950,y=365,width=9,height=9,fill='#203c42')];x,y=270,400;w,h=1350,370
  if domain=='scroll-records':children=[b.sheet('服务记录 '+str(i+1),[['需要后续联系','邀请下一次体验'],['已核对用途','记录当前结果']][i%2],0,i*160,1250,140) for i in range(6)];e['distance']=380
  else:children=[b.product(k,i*500,15,.75) for i,k in enumerate(['ipad','airpods','apple-watch','macbook-air'])];e.update(dx=600,zoom=.6)
 if typ=='group':
  if not children:children=[b.sheet('本次服务记录',['核对顾客需要','观察实际体验','记录后续问题'],0,0,900,330)]
  node=b.group(children,x,y,w,h)
 elif typ=='text':
  value='128' if domain=='number' else '已核对' if domain=='status' else '先确认拍照需求，再邀请体验' if domain=='search' else CASES[kind][1]
  node=b.text(value,300,490,108 if domain=='number' else 66);node.update(width=1350,height=180)
  if kind=='correct-replace':e['fromText']='只介绍产品参数'
  if kind=='cell-update':e['fromText']='待核对'
  if kind=='search-match':e['query']='拍照需求'
  if domain=='number':context.append(b.text('已完成的示例检查项',305,430,33))
 elif typ=='image':
  node=b.n('image',x=360,y=345,width=1080,height=480,assetId='detail' if domain=='detail' else 'm1')
  if domain=='presenter':node.update(x=300,y=310,width=490,height=620);e.update(kgAsset='kg',openAsset='m1-open',blinkAsset='m1-blink');context += [b.sheet('接待提醒',['先了解使用场景','再邀请顾客体验','最后核对结果'],980,450,550,300)]
 elif typ in ['path','line']:
  if domain in ['path','linechart']:
   pts=[[0,210],[300,210],[500,50],[800,50],[1080,210]];node=b.n(typ,x=350,y=420,points=pts,path='M'+' L'.join(f'{a},{z}' for a,z in pts),fill=None,stroke='#3c8170',lineWidth=9,width=1080,height=300)
   for i,(xx,yy,label) in enumerate([(350,650,'了解需要'),(850,460,'亲手体验'),(1430,650,'核对结果')]):context += [b.rect(xx-50,yy-32,100,64,'#d7e4d5',radius=30),b.text(label,xx-70,yy+48,29)]
  elif domain=='gauge':
   node=b.n('line',x=930,y=640,x2=260,y2=0,width=260,height=0,stroke='#446d68',lineWidth=10);context += [b.n('path',x=0,y=0,path='M 620 640 A 310 310 0 0 1 1240 640',fill=None,stroke='#becdbd',lineWidth=25),b.text('0',590,680,29),b.text('100',1200,680,29)]
  else:
   pts={'check':[[0,65],[50,115],[160,0]],'cross':[[0,0],[160,130],[80,65],[160,0],[0,130]],'brace':[[0,0],[0,65],[750,65],[750,0]],'signature':[[0,80],[40,10],[25,100],[90,30],[75,95],[180,55],[250,70]]}[domain];node=b.n('path',x=900 if domain!='brace' else 400,y=510,points=pts,path='M'+' L'.join(f'{a},{z}' for a,z in pts),fill=None,stroke='#3c8170',lineWidth=9,width=800,height=250);context.append(b.sheet('交接核对单',['设备信息已核对','体验记录已对应','后续问题已说明'],270,350,1360,470))
 elif typ=='ellipse':
  node=b.n('ellipse',x=920,y=580,width=340,height=340,fill=None,stroke='#487e6a');e.setdefault('fraction',.75);context += [b.text('本次示例进度',730,350,38),b.text('75%',850,540,70)]
 else:
  node=b.rect(350,440,1160,240,'#5d9686');node['type']=typ
  if domain in ['scan','spotlight','stamp','redaction']:
   context.append(b.sheet('服务工作单',['设备：iPhone 18 Pro','用途：记录家庭生活','体验：邀请亲手试拍'],250,350,1400,460));node.update(x=300,y=400,width=1280,height=345,fill=None)
   if domain=='spotlight':e.update(cx=460,cy=190,radius=135,fromRadius=1500)
   if domain=='stamp':e.update(label='已复核');node.update(x=800,y=490,width=540,height=250)
  if domain in ['ui-click','toggle','slider','tooltip']:
   context += [b.rect(250,350,1400,460,'#a4b9bf',radius=35),b.rect(280,380,1340,400,'#fbfcf5',radius=25),b.text('本次体验 · 操作示意',335,415,34)];node.update(x=350,y=480,width=1110,height=250,fill=None)
   if domain=='ui-click':context += [b.rect(890,565,280,90,'#447f6c'),b.text('开始体验',930,585,35,'#ffffff')];e.update(cx=650,cy=125)
   if domain=='tooltip':e.update(cx=660,cy=180,label='先核对当前目标')
  if domain=='bar':node.update(x=380,y=500,width=1100,height=115);context += [b.text('示例体验记录',380,420,36),b.text('共同零点',300,650,26)]
  if domain=='fill':node.update(x=770,y=380,width=350,height=410,fill='#6d9c8b');e['fraction']=.75;context.append(b.text('内容准备进度',730,330,38))
  if domain=='threshold':node.update(x=350,y=500,width=1180,height=110);e.update(value=.9,threshold=.65);context += [b.text('示例阈值 65%',1030,660,32),b.text('依据先说明，状态再变化',350,420,34)]
 # Special parameter arrays track actual objects; never leave old three-block sample params.
 if kind=='group-collect':e.update(**{'from':[[n.get('x',0),n.get('y',0)] for n in children],'to':[[i%2*520,i//2*200] for i in range(len(children))]})
 if kind=='sort':e.update(**{'from':[[700,180],[0,10],[350,80]],'to':[[0,0],[350,0],[700,0]]})
 if kind=='explode':node.update(y=455);e.update(dx=135,dy=30)
 if kind=='presenter-gesture':node.update(y=345,height=560,width=440)
 if kind=='timeline-reflow':
  node['children']=[b.rect(i*95,i*84,260,55,['#6b998b','#b78d59','#7297a6','#96945d'][i],radius=5) for i in range(4)];node.update(x=490,y=400,width=1080,height=370);e['to']=[[i*160+60,310+i*45] for i in range(4)]
  for i,t in enumerate(['设备准备','顾客接待','体验支持','服务交接']):context.append(b.text(t,230,410+i*84,31))
 if kind=='balance':e.update(values=[4,7,10,6],height=280,baseline=300)
 if kind=='record-filter':e.update(keep=[0,2],gap=205,exitX=380)
 if kind=='dot-aggregate':e.update(columns=9,gap=58)
 if kind=='quiz-feedback':e.update(selected=1,correct=True)
 if kind=='parallel-sync':
  node.update(x=500,y=450,width=1050,height=350);node['children']=[b.sheet('设备准备',['iPhone 已就位'],0,0,330,160),b.sheet('内容准备',['体验目标已明确'],0,190,330,160)];e['to']=[[620,0],[620,190]]
  context.append(b.text('两项到位后，开始体验',1100,416,27))
 if kind=='rank-reorder':e['order']=[2,0,3,1]
 if kind=='histogram-bin':e['bins']=[i%3 for i in range(len(children))]
 if kind=='histogram-bin':
  node.update(y=570);node['children']=[b.group([b.rect(0,0,46,54,'#d8e3e1',stroke='#678b93',lineWidth=2),b.text(str(i+1),10,13,21)],i%9*90,i//9*62,46,54) for i in range(9)];e['bins']=[i%3 for i in range(9)];e.update(gap=65)
 if kind=='scatter-converge':e['targets']=[[i%9*95,70+i//9*110] for i in range(len(children))]
 if kind in ['ratio-normalize','waterfall-step','funnel-narrow']:e['values']=[10,7,4,2] if kind!='waterfall-step' else [4,-2,5,1]
 if kind=='waterfall-step':
  node['children']=[b.rect(i*280,0,190,90,['#60998a','#bc7f66','#7b9da9','#a8a264'][i],radius=4) for i in range(4)];node.update(x=400,y=390,width=1120,height=420);e.update(baseline=310,unit=30)
  for i,t in enumerate(['新增 +4','合并 −2','新增 +5','转入 +1']):context.append(b.text(t,410+i*280,770,28))
 if kind in ['table-row-insert','table-row-delete','column-resize']:e['selected']=1
 if kind=='path-follow':e['points']=[[0,0],[180,-30],[350,40],[520,0]];node.update(x=450,y=530,width=250,height=200);node['children']=[b.iphone(0,0,.24)]
 if kind=='pixel-walk':node.update(x=350,y=500,width=230,height=250);node['children']=[b.iphone(0,0,.3)];e.update(dx=780,dy=0,pixelSize=2)
 if kind=='swimlane-transfer':node['children']=[b.sheet('同一份交接记录',['需求已说明','结果已核对'],0,0,270,180)]
 if kind=='lane-distribute':node.update(x=400,y=430,width=1050,height=350);node['children']=[b.sheet('接待记录',['店员继续接待'],0,0,260,180),b.sheet('复核记录',['店长核对条件'],0,0,260,180)];e.update(columns=2)
 if kind=='handoff':node['children']=[b.sheet('交接记录',['同一顾客','同一需求','同一结果'],0,0,270,210)]
 if kind=='card-flip' or kind=='page-turn' or kind=='tab-switch':
  node['children']=[b.sheet('顾客提出的问题',['主要用来拍家人','目前担心操作复杂'],0,0,1000,300),b.sheet('核对与体验提示',['先看实际使用场景','邀请完成一次试拍'],0,0,1000,300)];node.update(x=450,y=420,width=1000,height=320);e['selected']=1
 if kind=='dialogue':
  context += [b.person('C01',100,390,.47),b.person('S01',1430,390,.47)];node['children']=[b.rect(0,0,850,190,'#ffffff',stroke='#a9bcb1',lineWidth=2),b.text('我想给家人拍照，操作会复杂吗？',28,40,38),b.text('我们先用你的场景亲手试一次。',28,105,34)];node.update(x=550,y=430,width=850,height=190)
 if kind=='notification-slide':node.update(x=350,y=460,width=1120,height=220);node['children']=[b.sheet('交接已到达',['店长已收到本次服务记录','下一步：核对条件并反馈'],0,0,1120,220)]
 if kind=='dropdown-expand':node['children']=[b.sheet(t,['按本次实际需求选择'],0,i*120,1100,105) for i,t in enumerate(['设置与迁移','拍照与使用','后续联系'])];e['gap']=120;node.update(x=380,y=390,width=1120,height=390)
 if kind=='accordion-open':node['children']=[b.sheet(t,['展开当前项目'],0,i*120,1100,105) for i,t in enumerate(['顾客用途','体验观察','后续问题'])];e['gap']=120;node.update(x=380,y=390,width=1120,height=390)
 if kind=='checklist-tick':node['children']=[b.group([b.rect(0,0,1050,65,'#eff4e9',stroke='#adbeab',lineWidth=2),b.text(t,70,16,27)],0,i*72,1050,65) for i,t in enumerate(['设备与记录对应','体验结果已说明','后续需求已记录','责任岗位已确认','下一步已说清'])];node.update(x=400,y=400,width=1100,height=380);e['color']='#3c806b'
 if kind=='progress-segments':node['children']=[b.group([b.rect(0,0,195,150,'#dbe6d5',stroke='#93ad98',lineWidth=2),b.text(t,20,58,28)],i*220,90,195,150) for i,t in enumerate(['了解需要','准备设备','邀请体验','核对结果','服务交接'])];node.update(x=400,y=390,width=1120,height=350)
 if kind in ['stack-push','stack-pop']:node['children']=[b.sheet('记录 '+str(i+1),[['待跟进','已核对'],['本次用途','体验观察']][i%2],0,i*85,700,190) for i in range(3)];node.update(x=620,y=380,width=750,height=440);e['gap']=85
 if kind=='cluster-pack':
  node['children']=[b.sheet('问题 '+str(i+1),[['拍照需求'],['资料整理']][i%2],i%4*270,i//4*175,235,145) for i in range(8)]
  e.update(columns=2,centers=[[10,15],[610,15]],gapX=260,gapY=175);node.update(x=350,y=410,width=1200,height=380,clip=[0,0,1200,380])
 if kind=='orbit-revolve':e.update(radiusX=150,radiusY=45)
 if kind=='queue-dequeue':node.update(y=540);node['children']=[b.person(k,i*350,0,.35) for i,k in enumerate(['C01','C02','C03'])]
 if kind=='grid-deal':node.update(y=450)
 if kind=='carousel-shift':
  node.update(y=465);node['children']=[b.iphone(0,0,.34),b.product('ipad',310,0,.43),b.product('macbook-air',650,0,.44)]
 if kind=='gear-turn':
  node['children']=[child for child in node['children'] if child.get('type')!='text'];node.update(x=610,y=395,width=460,height=420);context.append(b.text('前后岗位保持协同',1120,575,36))
 if kind=='pinch-zoom':
  node['children']=[b.product('ipad',380,100,.55)];e.update(zoom=.35)
 if kind=='draw-on' and domain=='path':pass
 node['id']='object-'+kind;node['effects']=[e]
 # The title and footer are outside the demonstration region; all data objects stay here.
 if kind in ['scroll-window','swipe-pan']:node['clip']=[0,0,node['width'],node['height']]
 return [*context,node]
