"""Compile reusable teaching compositions to ordinary editable motion-graph nodes.

The gallery and real courses call this same compiler. Content is provided by the
course, never by a hidden sample script. All timing uses absolute source frames.
"""
import copy
import hashlib
import json

MODULES = {
 'blueprint': ('工程蓝图 / 扫描连线', ['scan','route-progress','flow-token']),
 'editorial': ('编辑排版 / 公式拆解', ['assemble','draw-on','callout']),
 'whiteboard': ('手写白板 / 逐笔路径', ['route-progress','marker','branch-grow']),
 'presenter': ('品牌讲师 / 连续手势', ['presenter-gesture','callout']),
 'spotlight': ('细节检视 / 聚光放大', ['spotlight','magnify','callout']),
 'correction': ('双栏对照 / 差异纠正', ['correct-replace','compare-wipe','check-draw']),
 'sorting': ('流程归位 / 重排归组', ['sort','group-collect']),
 'quiz': ('课中问答 / 选择反馈', ['quiz-feedback','callout']),
 'timeline': ('排班信息图 / 时段编排', ['timeline-reflow','threshold-cross']),
 'data': ('量化教学 / 数据聚合', ['dot-aggregate','count-up','ring-progress']),
 'swiss': ('瑞士字体 / 信息层级', ['text-rise','marker','underline']),
 'isometric': ('等距空间 / 分层拆解', ['explode','callout']),
 'papercut': ('纸艺层叠 / 折页展开', ['paper-fold','assemble']),
 'comic': ('品牌人物 / 分镜对话', ['dialogue','handoff']),
 'terminal': ('诊断台 / 筛选追踪', ['record-filter','flow-token','count-up']),
 'ink': ('知识图 / 分枝归因', ['branch-grow','evidence-attach']),
 'pixel': ('像素任务 / 闯关流程', ['pixel-walk','route-progress','check-draw']),
}
INK='#183f3c';GREEN='#397a69';RED='#b43e42';GOLD='#c59645';PAPER='#f4f3eb';MUTED='#637b71'


def catalog():
    return [dict(id=k,title=v[0],effects=v[1],status='callable',entry='sceneGraph.modules',
                 editable='compiled ordinary nodes, fields and asset IDs') for k,v in MODULES.items()]


def path_string(points):
    return 'M'+' L'.join(f'{p[0]},{p[1]}' for p in points)


class Build:
    def __init__(self, module, scene):
        self.m=module;self.s=scene;self.data=module.get('data',{});self.nodes=[];self.sequence=0
        self.a=module.get('startFrame',scene['sourceStartFrame']);self.b=module.get('endFrame',scene['sourceEndFrame'])
        self.beats=module.get('beats',[])
        if not self.beats:
            raise ValueError('教学模块须绑定实际讲解节拍，不自动把十秒示例拉长：'+module['id'])
        if any(type(x.get(k)) is not int for x in self.beats for k in ['startFrame','endFrame']):
            raise ValueError('模块节拍须为绝对整数帧')
        if any(not self.a<=x['startFrame']<x['endFrame']<=self.b for x in self.beats):
            raise ValueError('模块节拍超出模块时间范围：'+module['id'])

    def node(self, kind, name, **kw):
        n=dict(id=self.m['id']+'-'+name,type=kind,sceneId=self.s['id'],moduleId=self.m['id'],
               role='subject',startFrame=self.a,endFrame=self.b,**kw)
        return n

    def text(self,name,text,x,y,size=44,fill=INK,**kw):
        return self.node('text',name,text=str(text),x=x,y=y,fontSize=size,fill=fill,**kw)

    def rect(self,name,x,y,w,h,fill='#fff',**kw):
        return self.node('rect',name,x=x,y=y,width=w,height=h,fill=fill,radius=kw.pop('radius',8),**kw)

    def line(self,name,points,fill=GREEN,**kw):
        return self.node('path',name,x=0,y=0,fill=None,stroke=fill,lineWidth=kw.pop('lineWidth',5),points=points,path=path_string(points),**kw)

    def group(self,name,x,y,children,w=1600,h=620,**kw):
        return self.node('group',name,x=x,y=y,width=w,height=h,children=children,**kw)

    def fx(self,kind,i=0,**kw):
        beat=self.beats[min(i,len(self.beats)-1)]
        return dict(type=kind,startFrame=beat['startFrame'],endFrame=beat['endFrame'],**kw)

    def at(self,n,i=0,kind='mask-reveal',**kw):
        if kind=='mask-reveal':n.setdefault('width',1500);n.setdefault('height',max(80,n.get('fontSize',44)*1.5))
        n.setdefault('effects',[]).append(self.fx(kind,i,**kw));return n

    def label(self,name,text,x,y,w=460,fill='#fff',color=INK):
        return self.group(name,x,y,[self.rect(name+'-bg',0,0,w,104,fill),self.text(name+'-text',text,24,28,40,color)],w,104)

    def shell(self):
        bg=self.data.get('background',PAPER)
        if self.m['module']=='blueprint':bg='#102e3d'
        if self.m['module']=='terminal':bg='#102b24'
        if self.m['module']=='pixel':bg='#24244d'
        dark=self.m['module'] in ['blueprint','terminal','pixel'];col='#edf2e3' if dark else INK
        self.nodes=[self.rect('background',0,0,1920,1080,bg,radius=0),
            self.text('context',self.data.get('context',''),100,70,30,'#a6c4b6' if dark else MUTED),
            self.text('title',self.data.get('title',''),100,150,72,col)]
        for n in self.nodes:n['role']='decoration'
        self.nodes+= [self.line('header-rule',[[100,258],[1820,258]],'#b7c8ba',lineWidth=2)]
        self.nodes[-1]['role']='decoration'
        return self

    def build(self):
        self.shell();getattr(self,'data_module' if self.m['module']=='data' else self.m['module'])()
        if self.data.get('purpose'):
            n=self.text('purpose',self.data['purpose'],100,890,36,MUTED)
            self.nodes.append(self.at(n,len(self.beats)-1,'text-rise'))
        family={'whiteboard':'CourseHand','ink':'CourseHand','editorial':'CourseSerif','swiss':'CourseHeavy'}.get(self.m['module'])
        if family:
            def assign(items):
                for item in items:
                    if item['type']=='text':item['fontFamily']=family
                    assign(item.get('children',[]))
            assign(self.nodes)
        return self.nodes

    def blueprint(self):
        left=self.data.get('left',[]);right=self.data.get('right',left)
        self.nodes += [self.rect('source',110,320,700,460,'#edf3ef'),self.rect('target',1130,320,650,460,'#e0cfaa')]
        for i,s in enumerate(left):self.nodes.append(self.at(self.text('source-'+str(i),s,150,365+i*100,43),i,'text-rise'))
        for i,s in enumerate(right):self.nodes.append(self.at(self.text('target-'+str(i),s,1170,365+i*100,43),i,'text-rise'))
        self.nodes.append(self.rect('scanner',1150,355,600,350,None,effects=[self.fx('scan',0,color='#6ccac5')]))
        self.nodes.append(self.line('connection',[[790,570],[960,570],[1095,500],[1180,500]],'#e1ba66',effects=[self.fx('route-progress',1)]))
        self.nodes.append(self.line('signal',[[790,570],[960,570],[1095,500],[1180,500]],'#e1ba66',effects=[self.fx('flow-token',2)]))

    def editorial(self):
        items=self.data.get('labels',['分子','对应分母','× 100%'])
        self.nodes += [self.text('lead',self.data.get('lead','先明确计算对象'),100,390,78),self.text('scope',self.data.get('scope','保持同一范围'),100,560,46,MUTED)]
        children=[self.text('numerator',items[0],0,0,68),self.line('fraction',[[0,120],[680,120]],effects=[self.fx('draw-on',1)]),self.text('denominator',items[1],0,170,58),self.text('unit',items[2],520,310,44)]
        self.nodes.append(self.group('formula',1000,350,children,720,430,effects=[self.fx('assemble',0,offsetX=100,offsetY=60)]))

    def whiteboard(self):
        labels=self.data.get('labels',[]);count=len(labels)
        if not count:raise ValueError('白板缺少步骤')
        positions=[(170+i*470,370) if i<4 else (1580-(i-4)*470,670) for i in range(count)]
        for i,(label,(x,y)) in enumerate(zip(labels,positions)):
            self.nodes.append(self.at(self.text('step-'+str(i),label,x,y,48),i,'text-rise'))
            self.nodes.append(self.at(self.text('number-'+str(i),str(i+1),x,y-64,32,GREEN,width=64,height=44),i,'marker',color='#dce8dd'))
            if i:
                px,py=positions[i-1];points=[[px+340,py+30],[x-20,y+30]] if y==py and i<4 else [[px+120,py+80],[x+120,y-55]] if y!=py else [[px-20,py+30],[x+360,y+30]]
                self.nodes.append(self.line('path-'+str(i),points,effects=[self.fx('route-progress',i)]))

    def presenter(self):
        a=self.data.get('actorAssets',{});required=['body','kg','open','blink']
        if any(not a.get(k) for k in required):raise ValueError('讲师模块须提供已确认的四个品牌素材ID')
        self.nodes.append(self.node('image','actor',x=90,y=290,width=450,height=570,assetId=a['body'],effects=[self.fx('presenter-gesture',0,kgAsset=a['kg'],openAsset=a['open'],blinkAsset=a['blink'])]))
        for i,s in enumerate(self.data.get('labels',[])):
            n=self.label('point-'+str(i),s,750,335+i*150,1000,'#e3ece2');self.nodes.append(self.at(n,i,'callout'))

    def spotlight(self):
        asset=self.data.get('assetId')
        if not asset:raise ValueError('聚光模块须提供本课真实素材ID')
        self.nodes.append(self.node('image','original',x=110,y=320,width=820,height=460,assetId=asset))
        self.nodes.append(self.rect('focus',80,290,860,540,None,effects=[self.fx('spotlight',0,cx=430,cy=270,radius=190)]))
        self.nodes.append(self.node('image','detail',x=1080,y=325,width=700,height=450,assetId=asset,effects=[self.fx('magnify',1,zoom=self.data.get('zoom',2),cx=self.data.get('cx',.5),cy=self.data.get('cy',.5))]))
        self.nodes.append(self.line('detail-link',[[780,590],[980,590],[1080,540]],GOLD,effects=[self.fx('route-progress',1)]))

    def correction(self):
        self.nodes += [self.rect('before-panel',110,320,790,420),self.rect('after-panel',1020,320,790,420),self.text('before-label',self.data.get('leftLabel','原记录'),150,350,36,MUTED),self.text('after-label',self.data.get('rightLabel','核对结果'),1060,350,36,MUTED)]
        self.nodes.append(self.text('before',self.data.get('before',''),150,500,56))
        self.nodes.append(self.text('after',self.data.get('after',''),1060,500,56,width=710,effects=[self.fx('correct-replace',1,fromText=self.data.get('before',''))]))
        self.nodes.append(self.line('confirm',[[1370,670],[1398,697],[1450,633]],effects=[self.fx('check-draw',2)]))

    def sorting(self):
        labels=self.data.get('labels',[]);count=len(labels)
        children=[self.label('item-'+str(i),s,0,i*125,1100,'#fff') for i,s in enumerate(labels)]
        source=[[-300+(i%2)*80,i*145] for i in range(count)];target=[[0,i*145] for i in range(count)]
        self.nodes.append(self.group('ordering',500,320,children,1150,550,effects=[self.fx('sort',0,**{'from':source,'to':target})]))

    def quiz(self):
        labels=self.data.get('labels',[]);children=[self.label('option-'+str(i),s,0,i*150,1600) for i,s in enumerate(labels)]
        self.nodes.append(self.group('options',140,340,children,1600,500,effects=[self.fx('quiz-feedback',1,selected=self.data.get('selected',0),correct=self.data.get('correct',True))]))
        if self.data.get('feedback'):self.nodes.append(self.at(self.text('feedback',self.data['feedback'],150,820,42,GREEN),2,'text-rise'))

    def timeline(self):
        labels=self.data.get('labels',[]);intervals=self.data.get('intervals',[[0,600],[100,950],[400,650]])
        self.nodes += [self.line('axis',[[380,350],[1760,350]],'#a7b4a9',lineWidth=2)]
        for i,s in enumerate(labels):self.nodes.append(self.text('role-'+str(i),s,110,400+i*145,39))
        bars=[self.rect('interval-'+str(i),v[0],i*145,v[1],85,[GREEN,'#7797a2',GOLD][i%3]) for i,v in enumerate(intervals)]
        self.nodes.append(self.group('intervals',380,395,bars,1380,460,effects=[self.fx('timeline-reflow',1,to=self.data.get('targets',intervals))]))

    def data_module(self):
        count=int(self.data.get('count',40));selected=int(self.data.get('selected',8))
        if not 1<=selected<=count<=160:raise ValueError('数据聚合需要 1 <= selected <= count <= 160')
        dots=[self.rect('record-'+str(i),(i%10)*62,(i//10)*62,45,45,GOLD if i<selected else '#bdd1cc',radius=3) for i in range(count)]
        source=[[o['x'],o['y']] for o in dots];target=[[o['x']+780,o['y']] if i<selected else [o['x'],o['y']] for i,o in enumerate(dots)]
        self.nodes.append(self.group('records',120,360,dots,1600,460,effects=[self.fx('dot-aggregate',0,**{'from':source,'to':target})]))
        self.nodes += [self.text('numerator',str(selected),1280,610,100,effects=[self.fx('count-up',1)]),self.text('ratio',str(round(selected/count*100))+'%',1280,750,92,GREEN,effects=[self.fx('odometer',2)],width=470)]

    def swiss(self):
        words=self.data.get('labels',[])
        for i,s in enumerate(words[:3]):
            n=self.text('word-'+str(i),s,110,330+i*165,115,RED if i%2 else INK,width=1500,height=150)
            self.nodes.append(self.at(n,i,'text-rise'))
        if self.data.get('question'):self.nodes.append(self.text('question',self.data['question'],1150,440,52,width=620,effects=[self.fx('marker',1,color='#e3e4cb')]))

    def isometric(self):
        labels=self.data.get('labels',[]);parts=[]
        for i,s in enumerate(labels):
            points=[[0,50],[460,0],[780,120],[320,170],[0,50]]
            plane=self.node('path','plane-'+str(i),x=0,y=0,path=path_string(points),points=points,fill=['#d6e5da','#f7f4dd','#d7ba7b'][i%3],stroke='#a1bba7',lineWidth=2)
            parts.append(self.group('layer-'+str(i),0,0,[plane,self.text('layer-label-'+str(i),s,220,75,40)],800,200,explodeX=i*100,explodeY=-i*145))
        self.nodes.append(self.group('layers',430,680,parts,1000,580,effects=[self.fx('explode',0)]))

    def papercut(self):
        phases=self.data.get('phases',[])
        for i,phase in enumerate(phases):
            x=110+i*580;items=[self.rect('paper-'+str(i),0,0,540,490,'#fff9e4',radius=1),self.rect('tab-'+str(i),0,0,540,90,[GOLD,GREEN,'#507f90'][i%3],radius=1),self.text('phase-'+str(i),phase['title'],270,23,44,'#fff',align='center')]
            for j,label in enumerate(phase['labels']):items.append(self.text('phase-item-'+str(i)+'-'+str(j),label,270,135+j*76,39,align='center'))
            self.nodes.append(self.group('fold-'+str(i),x,330,items,540,490,effects=[self.fx('paper-fold',i)]))

    def comic(self):
        frames=self.data.get('frames',[])
        for i,frame in enumerate(frames):
            x=100+i*590;children=[self.rect('panel-'+str(i),0,0,550,510,'#e5ebd7',stroke='#8aa28e',lineWidth=2),self.rect('speech-'+str(i),28,26,494,128,'#fff')]
            children.append(self.text('speech-text-'+str(i),frame['text'],48,57,37))
            if frame.get('assetId'):children.append(self.node('image','speaker-'+str(i),assetId=frame['assetId'],x=75,y=175,width=390,height=335))
            self.nodes.append(self.group('frame-'+str(i),x,330,children,550,510,effects=[self.fx('dialogue',i,side='left' if i%2==0 else 'right')]))

    def terminal(self):
        records=self.data.get('records',[]);keep=self.data.get('keep',list(range(len(records))))
        children=[]
        for i,s in enumerate(records):children.append(self.label('record-'+str(i),s,0,i*105,920,'#1a3c31','#d9e7c7'))
        self.nodes.append(self.group('record-table',110,335,children,970,520,effects=[self.fx('record-filter',0,keep=keep,gap=112)]))
        self.nodes.append(self.line('result-link',[[1050,590],[1200,590],[1200,460],[1340,460]],'#aacc88',effects=[self.fx('flow-token',1)]))
        self.nodes.append(self.text('result',str(self.data.get('result',len(keep))),1360,510,120,'#d8e9ac',effects=[self.fx('count-up',2)],width=450))

    def ink(self):
        root=self.data.get('root','');labels=self.data.get('labels',[]);children=[]
        self.nodes.append(self.text('root',root,130,535,60))
        for i,s in enumerate(labels):
            y=335+i*190;children.append(self.line('branch-'+str(i),[[620,575],[870,575+(y-575)*.45],[1110,y+30]],'#688171',lineWidth=5));children.append(self.text('leaf-'+str(i),s,1180,y,48))
        self.nodes.append(self.group('knowledge',0,0,children,1800,850,effects=[self.fx('branch-grow',0)]))

    def pixel(self):
        labels=self.data.get('labels',[]);self.nodes.append(self.rect('ground',100,790,1710,35,'#b58a5b',radius=0))
        for i,s in enumerate(labels):
            x=140+i*460;self.nodes += [self.rect('station-'+str(i),x,400,390,95,'#eccf71',radius=0),self.text('station-text-'+str(i),s,x+20,429,34,'#292d45'),self.line('post-'+str(i),[[x+195,495],[x+195,790]],'#8292ae',lineWidth=12)]
            self.nodes.append(self.line('done-'+str(i),[[x+165,560],[x+185,581],[x+230,535]],'#b4dfab',lineWidth=8,effects=[self.fx('check-draw',i)]))
        children=[self.rect('parcel',0,0,125,100,'#e7cb8d',radius=0),self.text('parcel-label',self.data.get('object','任务'),20,30,30,'#243c45')]
        self.nodes.append(self.group('carrier',130,670,children,125,100,effects=[self.fx('pixel-walk',0,dx=max(1,len(labels)-1)*460,steps=36)]))


def expand(spec):
    """Expand only requested modules. The compiled source remains the edit source."""
    result=copy.deepcopy(spec);graph=result.setdefault('sceneGraph',{});modules=graph.pop('modules',[])
    if not modules:return result
    scenes={s['id']:s for s in result.get('scenes',[])};nodes=graph.setdefault('nodes',[]);manifest=[];ids=set()
    for module in modules:
        if module.get('module') not in MODULES:raise ValueError('未实现的教学模块 '+str(module.get('module')))
        if not module.get('id') or module['id'] in ids:raise ValueError('教学模块ID缺失或重复')
        ids.add(module['id'])
        if module.get('sceneId') not in scenes:raise ValueError('教学模块缺少实际场景')
        built=Build(module,scenes[module['sceneId']]).build();nodes.extend(built)
        manifest.append(dict(id=module['id'],module=module['module'],sceneId=module['sceneId'],
            source=module,compiledNodeIds=[n['id'] for n in built],
            sourceSha256=hashlib.sha256(json.dumps(module,ensure_ascii=False,sort_keys=True).encode()).hexdigest()))
    result['teachingModules']=manifest
    return result
