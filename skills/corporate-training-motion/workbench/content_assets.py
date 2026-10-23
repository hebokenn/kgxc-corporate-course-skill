"""Content-driven, editable props and registered 2D character performances.

Recipes compile to the same ordinary graph used by preview, editing and export.
They are not screenshots or a second renderer. Character performances use
registered parts of approved raster masters; those masters remain intact.
"""
import copy
import hashlib
import json
import math

INK='#193d3d';MUTED='#758680';GREEN='#3c806b';GOLD='#d1a15b';PAPER='#f6f5ef'
SCREENS=('home','camera','gallery','battery','transfer','storage','support')
MOODS=('neutral','smile','concern','curious','relieved')
IDENTITIES=('C01','C02','C03','M1')


def gradient(a,b,x=200,y=0):return dict(type='linear-gradient',**{'from':[0,0],'to':[x,y]},stops=[[0,a],[1,b]])


class Drawing:
    def __init__(self,recipe,scene):
        self.r=recipe;self.scene=scene;self.a=recipe.get('startFrame',scene['sourceStartFrame']);self.z=recipe.get('endFrame',scene['sourceEndFrame'])
        if not scene['sourceStartFrame']<=self.a<self.z<=scene['sourceEndFrame']:raise ValueError('素材时间超出场景 '+recipe['id'])
    def node(self,t,key,**kw):return dict(id=self.r['id']+'-'+key,type=t,sceneId=self.scene['id'],role='subject',startFrame=self.a,endFrame=self.z,**kw)
    def rect(self,k,x,y,w,h,fill,**kw):return self.node('rect',k,x=x,y=y,width=w,height=h,fill=fill,radius=kw.pop('radius',8),**kw)
    def ellipse(self,k,x,y,w,h,fill,**kw):return self.node('ellipse',k,x=x,y=y,width=w,height=h,fill=fill,**kw)
    def text(self,k,value,x,y,size=18,fill=INK,**kw):return self.node('text',k,text=str(value),x=x,y=y,fontSize=size,fill=fill,**kw)
    def path(self,k,path,fill=None,stroke=INK,width=2,**kw):return self.node('path',k,x=0,y=0,path=path,fill=fill,stroke=stroke,lineWidth=width,**kw)
    def group(self,k,x,y,children,w=360,h=810,**kw):return self.node('group',k,x=x,y=y,width=w,height=h,children=children,**kw)
    def motion(self,n,prop,values):
        for (a,v),(z,w) in zip(values,values[1:]):
            if not self.a<=a<z<=self.z:raise ValueError('动作帧须在素材内并递增 '+n['id'])
            n.setdefault('motion',[]).append(dict(property=prop,startFrame=a,endFrame=z,**{'from':v,'to':w},ease='sineInOut'))
        return n


def family_photo(b,key,x,y,w,h,variant='family'):
    """An authored illustration, rather than the same generic mountain icon."""
    children=[b.rect(key+'-sky',0,0,w,h,gradient('#d4e5e7','#f1e4bf',w,h),radius=0),
        b.ellipse(key+'-sun',w*.82,h*.2,h*.16,h*.16,'#e7bc78'),
        b.path(key+'-hills',f'M 0 {h*.68} Q {w*.2} {h*.3} {w*.5} {h*.7} Q {w*.75} {h*.45} {w} {h*.62} L {w} {h} L 0 {h} Z','#799c83',None)]
    people=[(.29,.55,.21,'#456c78'),(.67,.55,.21,'#ae735d'),(.48,.70,.14,'#d0a44c')] if variant=='family' else [(.46,.56,.24,'#4d7791')]
    for i,(cx,cy,size,color) in enumerate(people):
        r=min(w,h)*size;px=w*cx;py=h*cy
        children.extend([b.path(key+f'-hair-{i}',f'M {px-r*.5} {py} Q {px-r*.65} {py-r} {px} {py-r} Q {px+r*.7} {py-r} {px+r*.55} {py} Z','#473d34',None),
            b.ellipse(key+f'-face-{i}',px,py,r,r*1.1,'#e8b590'),
            b.path(key+f'-body-{i}',f'M {px-r*.8} {py+r*1.4} Q {px-r*.8} {py+r*.5} {px} {py+r*.5} Q {px+r*.8} {py+r*.5} {px+r*.8} {py+r*1.4} Z',color,None),
            b.path(key+f'-smile-{i}',f'M {px-r*.17} {py+r*.08} Q {px} {py+r*.23} {px+r*.17} {py+r*.08}',None,'#754d3b',max(.8,w/300))])
    return b.group(key,x,y,children,w,h)


def screen(b,key,mode,data,w=252,h=526):
    if mode not in SCREENS:raise ValueError('未实现的屏幕 '+str(mode))
    dark=mode=='camera';fg='#fbfbf8' if dark else INK;bg='#142d34' if dark else '#f4f7f6'
    c=[b.rect(key+'-bg',0,0,w,h,bg,radius=24),b.text(key+'-time',data.get('time','10:08'),18,16,12,fg),
       b.rect(key+'-battery-outline',w-38,19,21,10,None,radius=2,stroke=fg,lineWidth=1),b.rect(key+'-battery-bar',w-35,22,15,4,fg,radius=0)]
    def title(value):c.append(b.text(key+'-title',value,18,60,23,fg))
    if mode=='home':
        c[0]['fill']=gradient('#b6ccd5','#e9d8b8',w,h);c.extend([b.text(key+'-clock',data.get('time','10:08'),w/2,94,42,INK,align='center'),b.text(key+'-day','周三  ·  欢迎体验',w/2,149,12,MUTED,align='center')])
        colors=['#5b94a4','#b09b73','#6a9b7e','#8e91b1','#bb8e7f','#4c677a'];labels=['相册','设置','资料','信息','服务','相机']
        for i,(color,label) in enumerate(zip(colors,labels)):
            x=22+(i%3)*79;y=260+(i//3)*94;c.append(b.rect(key+f'-app-{i}',x,y,49,49,color,radius=13));c.append(b.text(key+f'-label-{i}',label,x+24.5,y+56,12,INK,align='center'))
            if label=='相机':c.extend([b.rect(key+'-camera-glyph',x+9,y+15,31,23,'#e9efee',radius=5),b.ellipse(key+'-camera-lens',x+25,y+26,13,13,'#4c677a')])
    elif mode=='camera':
        title('拍照');c.append(family_photo(b,key+'-view',10,104,w-20,h-232,data.get('subject','family')))
        for x in [w/3,w*2/3]:c.append(b.path(key+f'-grid-x-{x}',f'M {x} 104 L {x} {h-128}',None,'#ffffff55',1))
        for y in [104+(h-232)/3,104+(h-232)*2/3]:c.append(b.path(key+f'-grid-y-{y}',f'M 10 {y} L {w-10} {y}',None,'#ffffff55',1))
        c.extend([b.text(key+'-mode','人像      照片      视频',w/2,h-112,13,'#eedb9d',align='center'),b.ellipse(key+'-shutter-outer',w/2,h-59,57,57,None,stroke='#fff',lineWidth=3),b.ellipse(key+'-shutter',w/2,h-59,45,45,'#fff'),b.rect(key+'-thumbnail',24,h-80,38,38,'#6c9084',radius=6),b.ellipse(key+'-switch',w-35,h-59,25,25,None,stroke='#fff',lineWidth=2)])
    elif mode=='gallery':
        title(data.get('title','刚拍的照片'));c.append(family_photo(b,key+'-result',10,105,w-20,h-215,data.get('subject','family')))
        c.extend([b.text(key+'-result-note',data.get('note','家人的笑脸，已经拍下'),w/2,h-83,14,MUTED,align='center'),b.text(key+'-tools','分享       编辑       收藏',w/2,h-41,13,INK,align='center')])
    elif mode=='battery':
        title('电池与使用情况');level=data.get('level',24)
        if type(level) not in [int,float] or not 0<=level<=100:raise ValueError('示意电量须为0至100')
        c.extend([b.text(key+'-percent',str(level)+'%',18,111,48,GREEN if level>25 else '#b36e3b'),b.text(key+'-remaining',data.get('note','先了解，何时不够用'),20,171,13,MUTED),b.rect(key+'-charge-bg',18,206,w-36,18,'#dce5df',radius=9),b.rect(key+'-charge',18,206,(w-36)*level/100,18,GREEN if level>25 else '#c48654',radius=9),b.text(key+'-history-title','使用记录',18,255,17)])
        for i,(label,value) in enumerate(data.get('usage',[['通勤',.36],['工作',.76],['拍照',.58]])):
            y=300+i*55;c.extend([b.text(key+f'-usage-{i}',label,18,y,13),b.rect(key+f'-usage-bg-{i}',77,y+3,w-99,12,'#e0e7e2',radius=6),b.rect(key+f'-usage-fill-{i}',77,y+3,(w-99)*value,12,GREEN,radius=6)])
    elif mode=='transfer':
        title('迁移到新手机');progress=data.get('progress',0)
        if type(progress) not in [int,float] or not 0<=progress<=100:raise ValueError('迁移进度须为0至100')
        c.extend([b.ellipse(key+'-transfer-disk',w/2,153,80,80,'#e0ece7'),b.path(key+'-transfer-arrow',f'M {w/2-18} 145 L {w/2+18} 145 L {w/2+9} 136 M {w/2+18} 145 L {w/2+9} 154 M {w/2+18} 166 L {w/2-18} 166 L {w/2-9} 157 M {w/2-18} 166 L {w/2-9} 175',None,GREEN,3),b.text(key+'-progress',str(progress)+'%',w/2,217,37,GREEN,align='center'),b.rect(key+'-transfer-track',22,273,w-44,10,'#dce6df',radius=5),b.rect(key+'-transfer-progress',22,273,(w-44)*progress/100,10,GREEN,radius=5)])
        for i,(label,value) in enumerate(data.get('records',[['照片与视频','待核对'],['联系人','待核对'],['文件','待核对']])):
            c.extend([b.rect(key+f'-record-{i}',15,316+i*48,w-30,40,'#fff',radius=8),b.text(key+f'-record-name-{i}',label,26,328+i*48,13),b.text(key+f'-record-state-{i}',value,w-27,328+i*48,12,MUTED,align='right')])
        c.append(b.text(key+'-boundary',data.get('note','范围与支持方式需确认'),w/2,h-32,12,MUTED,align='center'))
    elif mode=='storage':
        title('储存与资料');c.extend([b.text(key+'-used',data.get('used','已用 96 GB'),18,115,28),b.text(key+'-capacity',data.get('capacity','共 128 GB · 示意'),18,157,12,MUTED)])
        for i,(label,color,width) in enumerate([('照片','#829c79',.39),('视频','#c9a877',.29),('应用','#7b9ca9',.18)]):
            y=220+i*67;c.extend([b.text(key+f'-storage-{i}',label,18,y,15),b.rect(key+f'-storage-bg-{i}',18,y+26,w-36,13,'#e1e6e2',radius=5),b.rect(key+f'-storage-fill-{i}',18,y+26,(w-36)*width,13,color,radius=5)])
        c.append(b.text(key+'-storage-note',data.get('note','迁移前先确认内容与范围'),18,h-68,13,MUTED))
    elif mode=='support':
        title('后续服务');c.append(b.text(key+'-service-need',data.get('need','继续围绕你的使用问题'),18,112,15,MUTED))
        for i,(label,note) in enumerate(data.get('channels',[['设置与迁移','先确认实际支持'],['拍照与使用','带着问题来答疑'],['后续联系','留下适合的方式']])):
            y=177+i*93;c.extend([b.rect(key+f'-channel-{i}',15,y,w-30,77,'#fff',radius=12),b.text(key+f'-channel-name-{i}',label,27,y+14,17),b.text(key+f'-channel-note-{i}',note,27,y+45,12,MUTED)])
    c.extend([b.rect(key+'-battery-terminal',w-16,22,2,4,fg,radius=1),
              b.path(key+'-wireless',f'M {w-62} 22 Q {w-55} 16 {w-48} 22 M {w-59} 25 Q {w-55} 21 {w-51} 25',None,fg,1.3),
              b.rect(key+'-home-bar',w/2-35,h-9,70,3,'#ccd2ce' if dark else '#7a8b86',radius=2)])
    return b.group(key,0,0,c,w,h)


def phone(recipe,scene):
    from device_models import profile, shell, front_overlay
    b=Drawing(recipe,scene);d=recipe.get('data',{});view=d.get('view','front');model=d.get('model','iphone-18-pro')
    if view not in ['front','back','side'] or model not in ['iphone-18-pro']:raise ValueError('手机视角或机身未实现')
    named=profile(model,d.get('finish','glacier-blue')) if model=='iphone-18-pro' else None
    w=named['width'] if named else 274 if model!='compact' else 252
    h=named['height'] if named else 566 if model!='compact' else 508
    sx=named['screenX'] if named else 11;sy=named['screenY'] if named else 19
    sw=named['screenWidth'] if named else w-22;sh=named['screenHeight'] if named else h-40
    edge=d.get('color','#435965');nodes=[]
    if view=='side' and named:nodes=shell(b,view,named,gradient)
    elif view=='side':
        nodes=[b.rect('side-frame',w*.45,0,23,h,gradient('#c2ced0',edge,23,0),radius=11),b.rect('side-power',w*.45+23,115,4,62,'#253f46',radius=2),b.rect('side-cameras',w*.45-8,44,11,94,'#657c82',radius=4)]
    else:
        nodes=shell(b,view,named,gradient) if named else [b.rect('shadow',8,12,w,h,'#1c35351f',radius=38),b.rect('rim',0,0,w,h,gradient('#b5c0c1',edge,w,0),radius=36),b.rect('body',4,4,w-8,h-8,'#1c272b' if view=='front' else gradient(edge,'#9caaa8',w,h),radius=33),b.rect('power',w-1,123,4,59,'#4d656e',radius=2),b.rect('volume',-3,110,4,85,'#586c74',radius=2)]
        if view=='front':
            states=d.get('screenStates',[dict(atFrame=b.a,mode=d.get('screen','home'),data=d.get('screenData',{}))])
            ats=[s.get('atFrame') for s in states]
            if not ats or ats!=sorted(set(ats)) or ats[0]!=b.a or any(type(f) is not int or not b.a<=f<b.z for f in ats):raise ValueError('屏幕状态须从素材起帧开始，使用递增的绝对整数帧')
            for i,state in enumerate(states):
                item=screen(b,'screen-'+str(i),state['mode'],state.get('data',{}),sw,sh);item.update(x=sx,y=sy,startFrame=state['atFrame'],endFrame=ats[i+1] if i+1<len(ats) else b.z);nodes.append(item)
            for i,event in enumerate(d.get('interactions',[])):
                at=event.get('atFrame');dur=event.get('durationFrames',9);target=event.get('target','shutter')
                if type(at) is not int or type(dur) is not int or not b.a<=at<at+dur<=b.z or target not in ['shutter','camera-app']:raise ValueError('手机操作须绑定实际帧及已实现目标')
                cx=sx+sw/2 if target=='shutter' else sx+22+2*79+24.5;cy=sy+sh-59 if target=='shutter' else sy+260+94+24.5
                ring=b.ellipse('touch-'+str(i),cx,cy,54,54,None,stroke='#e5c176',lineWidth=3);ring.update(startFrame=at,endFrame=at+dur,effects=[dict(type='ring-progress',startFrame=at,endFrame=at+dur,color='#e5c176',lineWidth=3)]);nodes.append(ring)
                if event.get('capture'):
                    flash=b.rect('capture-flash-'+str(i),sx+10,sy+104,sw-20,sh-232,'#ffffff',radius=0);flash.update(startFrame=at+3,endFrame=at+dur)
                    b.motion(flash,'opacity',[(at+3,.75),(at+dur,0)]);nodes.append(flash)
            if named:nodes.extend(front_overlay(b,named))
            else:nodes.extend([b.rect('speaker',w/2-35,9,70,8,'#132529',radius=4),b.ellipse('front-lens',w/2+48,13,6,6,'#7593a1')])
            if model=='foldable':nodes.append(b.path('crease',f'M 17 {h*.49} L {w-17} {h*.49}',None,'#293b3b25',1.5))
        elif not named:
            nodes.append(b.rect('camera-island',18,24,119,125,'#53666c',radius=28))
            for i,(x,y) in enumerate([(50,58),(105,62),(52,116)]):
                nodes.extend([b.ellipse(f'lens-rim-{i}',x,y,42,42,'#a5b7bb'),b.ellipse(f'lens-{i}',x,y,35,35,gradient('#0b1923','#263f56',30,30)),b.ellipse(f'lens-light-{i}',x-6,y-6,9,7,'#4d728c')])
            nodes.extend([b.ellipse('flash',104,116,16,16,'#f2e8ce'),b.text('back-caption',d.get('label','体验机'),w/2,h-67,18,'#e2e9e4',align='center')])
    root=b.group('root',recipe.get('x',0),recipe.get('y',0),nodes,w,h,scaleX=recipe.get('scale',1),scaleY=recipe.get('scale',1))
    return root,dict(kind='phone',model=model,finish=d.get('finish','glacier-blue') if named else None,view=view,deviceId=d.get('deviceId'),screenStates=d.get('screenStates'),
        reference=named['metadata'] if named else None,interface='editable teaching illustration, not an actual OS screenshot',editable='body geometry, UI text, records, states, positions')


def actor(recipe,scene):
    from character_rig import pose_angles
    b=Drawing(recipe,scene);d=recipe.get('data',{});identity=d.get('identity','C01');rig=d.get('rig')
    if d.get('performance'):
        from character_performance import compile_actor
        return compile_actor(recipe,scene)
    if identity in ['S01','S02','COACH']:
        if not d.get('headAsset'):raise ValueError('须使用该门店角色自己的原图')
        staff=identity in ['S01','S02'];w,h=(737.28,1024) if staff else (1024,1536)
        crop=[0,0,.48,1] if identity=='S01' else [780/1536,0,.48,1] if identity=='S02' else [0,0,1,1]
        image=b.node('image','original-master',assetId=d['headAsset'],x=0,y=0,width=w,height=h,crop=crop);items=[image]
        if staff:
            if not d.get('logoAsset'):raise ValueError('蓝衣店员必须绑定原版 KG 胸标')
            x=440 if identity=='S01' else 390
            items.append(b.node('image','uniform-KG',assetId=d['logoAsset'],x=x,y=320,width=48,height=48*251/321))
            image['uniformMarkNodeId']=b.r['id']+'-uniform-KG'
        elif d.get('logoAsset'):raise ValueError('Coach 保留自身 MyCoach 标识，不能加 KG')
        scale=recipe.get('scale',1)*810/h;root=b.group('root',recipe.get('x',0),recipe.get('y',0),items,w,h,scaleX=scale,scaleY=scale)
        if d.get('view')=='half':root['clip']=[0,0,w,h*.60]
        return root,dict(kind='actor',identity=identity,characterRole='store_staff' if staff else 'coach',uniformMark='KG' if staff else 'MyCoach',representation='original role art with required role-specific uniform marking')
    if identity=='M1' and not rig:
        if not d.get('headAsset'):raise ValueError('M1须绑定已有完整原图')
        if not d.get('logoAsset'):raise ValueError('黑衣店长须绑定原版KG胸标；不能直接使用无标原图')
        image=b.node('image','original-master',assetId=d['headAsset'],x=0,y=0,width=1115,height=1411)
        logo=b.node('image','uniform-KG',assetId=d['logoAsset'],x=559,y=458,width=70,height=70*251/321)
        image['uniformMarkNodeId']=b.r['id']+'-uniform-KG'
        root=b.group('root',recipe.get('x',0),recipe.get('y',0),[image,logo],1115,1411,scaleX=recipe.get('scale',1)*810/1411,scaleY=recipe.get('scale',1)*810/1411)
        if d.get('view')=='half':root['clip']=[0,0,1115,780]
        return root,dict(kind='actor',identity=identity,characterRole='store_manager',representation='original M1 illustration plus original KG at registered left chest; mesh uses same mark position',design='original identity with required brand layer')
    if d.get('contactPose'):
        pose=d['contactPose']
        if pose.get('identity')!=identity:raise ValueError('接触姿态身份不一致')
        if any(k in d for k in ['poseKeys','moodKeys','nodFrames']):raise ValueError('该接触姿态是已制作的关键姿态，不能套用旧关节或旧五官坐标')
        w,h=pose['sourceSize'];image=b.node('image','contact-master',assetId=pose['master']['assetId'],x=0,y=0,width=w,height=h)
        mount=pose['deviceMount'];device,_=phone(dict(id=recipe['id']+'-held',sceneId=scene['id'],startFrame=b.a,endFrame=b.z,x=mount['x'],y=mount['y'],data=dict(model=mount['model'],finish=mount['finish'],view=mount['view'],deviceId=d.get('deviceId'))),scene);device['matrix']=mount['matrix']
        fg=pose['foreground'];x,y,X,Y=fg['bbox'];hands=b.node('image','contact-hands',assetId=fg['assetId'],x=x,y=y,width=X-x,height=Y-y)
        scale=recipe.get('scale',1)*810/h;root=b.group('root',recipe.get('x',0),recipe.get('y',0),[image,device,hands],w,h,scaleX=scale,scaleY=scale)
        if d.get('view')=='half':root['clip']=[0,0,w,h*.60]
        return root,dict(kind='actor',identity=identity,representation=pose['method'],sourceSha256=pose['master']['sha256'],deviceId=d.get('deviceId'),deviceView=mount['view'],review=pose['designApproval'])
    if not rig or rig.get('identity')!=identity:raise ValueError('须先为本角色 stage 独立纹理绑定')
    keys=d.get('poseKeys',[dict(frame=b.a,pose=d.get('pose','rest'))]);frames=[k['frame'] for k in keys]
    if any(k.get('pose') in ['phone-use','tap-phone'] for k in keys):raise ValueError('旧持机手掌旋转方案已停用：使用角色自己的接触姿态与手部遮挡，不能把松开的手旋转成握持')
    if not frames or frames[0]!=b.a or frames!=sorted(set(frames)) or any(type(f) is not int or not b.a<=f<b.z for f in frames):raise ValueError('姿态须从起帧开始，源帧递增并位于素材内')
    values=[pose_angles(rig,k['pose']) for k in keys]
    def sprite(name,pivot=(0,0),suffix=''):
        part=rig['files'][name];x,y,X,Y=part['bbox']
        return b.node('image',name+suffix,assetId=part['assetId'],x=x-pivot[0],y=y-pivot[1],width=X-x,height=Y-y)
    def timed(n,side,prop):
        sequence=[(k['frame'],v[side][prop]) for k,v in zip(keys,values)]
        if len(sequence)==1:n['rotation']=sequence[0][1]
        else:b.motion(n,'rotation',sequence)
        return n
    def arm(side,front=False):
        S,E,W=[rig['joints'][side][k] for k in ['S','E','W']];suffix='-front' if front else '-back'
        wrist=timed(b.group(side+'-wrist'+suffix,W[0]-E[0],W[1]-E[1],[sprite(side+'-hand',W,suffix)] if front else [],100,160),side,'hand')
        elbow=timed(b.group(side+'-elbow'+suffix,E[0]-S[0],E[1]-S[1],([] if front else [sprite(side+'-elbow-cap',E,suffix),sprite(side+'-fore',E,suffix)])+[wrist],180,320),side,'fore')
        return timed(b.group(side+'-shoulder'+suffix,S[0],S[1],([] if front else [sprite(side+'-upper',S,suffix)])+[elbow],230,600),side,'upper')
    nodes=[sprite('body'),sprite('left-shoulder-cap'),sprite('right-shoulder-cap'),arm('left'),arm('right')]
    nodes.extend([arm('left',True),arm('right',True)])
    emotions=d.get('moodKeys',[dict(frame=b.a,mood=d.get('mood','neutral'))]);mframes=[k['frame'] for k in emotions]
    if not mframes or mframes[0]!=b.a or mframes!=sorted(set(mframes)) or any(type(f) is not int or not b.a<=f<b.z for f in mframes) or any('head-'+k.get('mood','') not in rig['files'] for k in emotions):raise ValueError('表情须绑定已制作纹理与实际帧')
    heads=[]
    for i,item in enumerate(emotions):
        n=sprite('head-'+item['mood'],rig['neck'],'-'+str(i));n.update(startFrame=item['frame'],endFrame=mframes[i+1] if i+1<len(mframes) else b.z);heads.append(n)
    head=b.group('head',*rig['neck'],heads,420,390,rotation=2 if d.get('pose')=='listen' else 0)
    if d.get('nodFrames'):
        a,z=d['nodFrames'];b.motion(head,'rotation',[(a,0),((a+z)//2,3),(z,0)])
    nodes.append(head);scale=recipe.get('scale',1)*810/rig['sourceSize'][1]*(.82 if identity=='C03' else 1)
    root=b.group('root',recipe.get('x',0),recipe.get('y',0),nodes,*rig['sourceSize'],scaleX=scale,scaleY=scale)
    if d.get('view')=='half':root['clip']=[40,0,940,850 if identity!='C03' else 980]
    return root,dict(kind='actor',identity=identity,representation='original source textures with coordinated shoulder/elbow/wrist chains',
        sourceSha256=rig['sourceSha256'],poseKeys=keys,moodKeys=emotions,boneLengths={side:[math.dist(rig['joints'][side]['S'],rig['joints'][side]['E']),math.dist(rig['joints'][side]['E'],rig['joints'][side]['W'])] for side in ['left','right']},
        naturalWalkReady=False,review='new motion candidate; no user motion approval inferred')


def document(recipe,scene):
    b=Drawing(recipe,scene);d=recipe.get('data',{});w=d.get('width',590);h=d.get('height',450);ticket=d.get('format')=='ticket'
    if not d.get('title') or not isinstance(d.get('rows',[]),list):raise ValueError('文书素材须提供本课标题与内容行')
    c=[b.rect('shadow',8,10,w,h,'#24463c15',radius=12),b.rect('paper',0,0,w,h,'#fffcf2',radius=12,stroke='#ccd4c6',lineWidth=2),b.rect('header',0,0,w,70,'#dfe8dc',radius=10),b.text('title',d['title'],26,20,29),b.text('subtitle',d.get('subtitle',''),28,94,19,MUTED)]
    if ticket:c.append(b.path('perforation',f'M 22 {h-72} L {w-22} {h-72}',None,'#c3bba2',2))
    row_frames=d.get('rowFrames',[b.a]*len(d.get('rows',[])))
    if len(row_frames)!=len(d.get('rows',[])) or any(type(f) is not int or not b.a<=f<b.z for f in row_frames):raise ValueError('文书各行须绑定素材内实际源帧')
    for i,row in enumerate(d.get('rows',[])):
        y=145+i*70;at=row_frames[i];group=b.group('row-'+str(i),0,y,[b.ellipse('bullet-'+str(i),38,12,8,8,GOLD),b.text('label-'+str(i),row[0],58,0,23),b.text('value-'+str(i),row[1] if len(row)>1 else '',w-28,0,21,MUTED,align='right')],w,55)
        group['startFrame']=at
        group['nonOverlappingTextIds']=[b.r['id']+'-label-'+str(i),b.r['id']+'-value-'+str(i)];group['textGap']=10
        if 'rowFrames' in d:group['effects']=[dict(type='mask-reveal',startFrame=at,endFrame=min(at+10,b.z))]
        c.append(group)
    focus=d.get('rowFocus',[])
    for i,event in enumerate(focus):
        row=event.get('row');at=event.get('atFrame');end=event.get('endFrame',focus[i+1].get('atFrame') if i+1<len(focus) else b.z)
        if type(row) is not int or not 0<=row<len(d.get('rows',[])) or type(at) is not int or type(end) is not int or not b.a<=at<end<=b.z or i and at<focus[i-1]['atFrame'] or i+1<len(focus) and end>focus[i+1]['atFrame']:raise ValueError('当前行高亮须按实际行绑定，窗口不能重叠或越界')
        border=b.rect('row-focus-'+str(i),22,145+row*70-9,w-40,52,None,stroke=GOLD,lineWidth=2,radius=8)
        border.update(startFrame=at,endFrame=end,enclosesTextIds=[b.r['id']+'-label-'+str(row),b.r['id']+'-value-'+str(row)],effects=[dict(type='mask-reveal',startFrame=at,endFrame=min(at+9,end))]);c.append(border)
    footer=b.text('footer',d.get('footer',''),28,h-47,19,MUTED);footer['startFrame']=d.get('footerFrame',b.a)
    if type(footer['startFrame']) is not int or not b.a<=footer['startFrame']<b.z:raise ValueError('文书页脚源帧越界')
    c.append(footer)
    return b.group('root',recipe.get('x',0),recipe.get('y',0),c,w,h,scaleX=recipe.get('scale',1),scaleY=recipe.get('scale',1)),dict(kind='document',format=d.get('format','sheet'),editable='title, rows, values, layout')


def parcel(recipe,scene):
    b=Drawing(recipe,scene);d=recipe.get('data',{});serial=d.get('serial','示意编码');c=[
        b.path('top','M 30 150 L 280 25 L 515 148 L 263 275 Z','#d9bf86','#827957',3),
        b.path('left','M 30 150 L 263 275 L 263 515 L 30 387 Z','#c1a36b','#827957',3),
        b.path('right','M 263 275 L 515 148 L 515 387 L 263 515 Z','#b39159','#827957',3),
        b.path('tape','M 132 99 L 365 225 L 365 295 L 319 319 L 319 248 L 85 123 Z','#e8d9ae',None),
        b.rect('label',293,330,188,105,'#fffdf5',radius=5),b.text('label-title',d.get('label','外箱信息'),306,343,20),b.text('serial',serial,306,389,19)]
    for i,bit in enumerate(hashlib.sha256(serial.encode()).digest()[:22]):c.append(b.rect('barcode-'+str(i),306+i*7,374,2+bit%3,10,'#334b48',radius=0))
    return b.group('root',recipe.get('x',0),recipe.get('y',0),c,550,540,scaleX=recipe.get('scale',1),scaleY=recipe.get('scale',1)),dict(kind='parcel',serial=serial,barcode='visual example only; supply a real code for actual scanning')


def catalog():return dict(schema='course-content-assets/1',phone=dict(models=['iphone-18-pro'],views=['front','back','side'],screens=list(SCREENS),ui='editable teaching illustration; use verified screenshots for exact OS operation training'),
    actor=dict(identities=list(IDENTITIES)+['S01','S02','COACH'],poses=['rest','welcome','listen','question'],contactPoses=['C01-phone-use-v2'],expressions=list(MOODS),registeredPerformance=dict(identities=['C01','S01'],channels=['concern','relief','gazeX','gazeY','nod','head','left','right','leftFore','fore','leftHand','hand'],method='stage-performance; own profile and actual target IDs'),scope='role-specific uniform mark required; own-identity contact pose required for holding'),
    document=dict(formats=['sheet','ticket'],editable=['title','subtitle','rows','footer']),parcel=dict(editable=['label','serial']),
    retail=__import__('retail_assets').catalog(), implementation='ordinary editable graph nodes; no separate preview renderer')


def expand(spec):
    result=copy.deepcopy(spec);graph=result.setdefault('sceneGraph',{});recipes=graph.pop('materials',[])
    if not recipes:return result
    scenes={s['id']:s for s in result['scenes']};assets={a['id'] for a in result.get('assets',[])};manifest=[];identifiers=set()
    for recipe in recipes:
        identifier=recipe.get('id');sid=recipe.get('sceneId');kind=recipe.get('kind')
        if not identifier or identifier in identifiers:raise ValueError('素材ID缺失或重复')
        identifiers.add(identifier)
        if sid not in scenes:raise ValueError('素材须绑定本课实际场景')
        if kind=='actor' and not recipe.get('data',{}).get('rig') and not recipe.get('data',{}).get('contactPose') and recipe.get('data',{}).get('headAsset') not in assets:raise ValueError('人物原图素材不存在')
        if kind=='actor' and recipe.get('data',{}).get('identity') in ['M1','S01','S02'] and recipe['data'].get('logoAsset') not in assets:raise ValueError('原版KG胸标素材不存在')
        if kind=='actor' and recipe.get('data',{}).get('contactPose'):
            if any(recipe['data']['contactPose'][k].get('assetId') not in assets for k in ['master','foreground']):raise ValueError('接触姿态或手部遮挡素材不存在')
        if kind=='actor' and recipe.get('data',{}).get('rig'):
            if any(part.get('assetId') not in assets for part in recipe['data']['rig'].get('files',{}).values()):raise ValueError('人物绑定分层素材不存在')
        from retail_assets import prop,customer,store
        factories=dict(phone=phone,actor=actor,document=document,parcel=parcel,**{'retail-prop':prop,'retail-person':customer,'store-scene':store})
        if kind not in factories:raise ValueError('未实现的素材类型 '+str(kind))
        node,description=factories[kind](recipe,scenes[sid]);node['zIndex']=recipe.get('zIndex',0);graph.setdefault('nodes',[]).append(node)
        manifest.append(dict(id=identifier,kind=kind,source=recipe,sourceSha256=hashlib.sha256(json.dumps(recipe,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),description=description,rootNodeId=node['id']))
    graph['nodes'].sort(key=lambda n:n.get('zIndex',0))
    result['contentAssets']=manifest
    return result
