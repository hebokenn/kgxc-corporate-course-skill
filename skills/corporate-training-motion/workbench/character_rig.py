"""Prepare coordinated texture rigs and local expressions from approved masters.

All RGB comes from the original portrait. Masks, source landmarks and inverse
deformation fields are explicit per identity, never borrowed from another actor.
"""
from pathlib import Path
import hashlib,json,math

PROFILES={
 'C01':dict(size=[1024,1536],neck=[512,300],mouth=[507,226,33,18],eyes=[[468,173,26,29],[544,165,25,29]],brows=[[467,133,31,13],[543,126,29,13]],
  head=[[300,0],[710,0],[710,240],[560,281],[560,322],[450,322],[440,281],[300,240]],
  body=[[431,267],[575,267],[667,334],[691,485],[685,725],[664,775],[668,1355],[780,1463],[749,1510],[537,1510],[502,1386],[451,1505],[220,1510],[215,1465],[274,1340],[315,1045],[334,755],[325,602],[334,440],[345,343]],
  left=dict(S=[345,356],E=[271,642],W=[245,807],upper=[[340,325],[418,349],[358,552],[327,662],[213,669],[210,620],[231,528],[275,420]],fore=[[218,628],[310,650],[293,732],[277,791],[268,827],[207,818],[214,740]],hand=[[213,786],[270,795],[298,837],[291,875],[270,875],[266,848],[274,893],[248,913],[211,880],[204,837]]),
  right=dict(S=[658,357],E=[735,644],W=[771,810],upper=[[646,326],[706,350],[743,436],[768,560],[778,658],[675,680],[656,564],[620,363]],fore=[[678,632],[775,628],[790,742],[795,823],[740,831],[730,781],[707,717]],hand=[[739,787],[791,795],[806,836],[799,880],[771,908],[733,896],[722,864],[728,825]])),
 'C02':dict(size=[1024,1536],neck=[515,357],mouth=[526,264,35,19],eyes=[[474,211,27,30],[559,195,27,30]],brows=[[470,162,32,13],[557,145,31,13]],
  head=[[250,0],[740,0],[740,330],[593,360],[590,390],[435,390],[428,357],[250,350]],
  body=[[449,327],[580,327],[649,386],[650,540],[623,590],[666,760],[778,1033],[725,1075],[650,1082],[628,1370],[693,1440],[651,1501],[526,1487],[512,1397],[460,1499],[282,1498],[272,1450],[331,1350],[389,1050],[272,1020],[324,855],[381,650],[385,580],[341,510],[346,380]],
  left=dict(S=[374,416],E=[321,649],W=[275,809],upper=[[374,358],[441,386],[402,545],[368,660],[284,648],[309,526],[311,496]],fore=[[288,631],[371,649],[337,742],[316,803],[300,834],[246,819],[265,732]],hand=[[248,785],[307,798],[327,838],[313,897],[287,930],[257,908],[234,866],[237,817]]),
  right=dict(S=[651,422],E=[707,649],W=[773,811],upper=[[607,360],[664,378],[718,494],[721,548],[752,636],[675,680],[641,557],[620,510]],fore=[[675,628],[753,635],[788,742],[810,809],[769,837],[735,784],[699,725]],hand=[[766,782],[812,806],[830,847],[824,888],[800,928],[770,914],[750,886],[748,835]])),
 'C03':dict(size=[1024,1536],neck=[512,442],mouth=[530,348,34,8],eyes=[[467,302,35,39],[575,278,34,38]],brows=[[457,237,37,15],[565,214,35,15]],
  head=[[200,0],[760,0],[760,395],[571,435],[568,480],[448,480],[437,430],[200,415]],
  body=[[445,409],[574,410],[652,471],[683,690],[674,875],[682,1080],[636,1170],[641,1300],[785,1425],[795,1498],[550,1514],[511,1394],[457,1505],[230,1520],[225,1460],[303,1350],[315,1160],[324,1060],[350,875],[354,699],[345,515]],
  left=dict(S=[383,549],E=[286,817],W=[239,947],upper=[[355,489],[435,536],[383,735],[356,832],[212,830],[211,763],[248,661]],fore=[[216,791],[354,817],[315,883],[281,952],[209,970],[197,900]],hand=[[209,912],[282,940],[293,983],[276,1022],[248,1032],[219,1003],[199,1023],[178,1009],[169,966],[181,928]]),
  right=dict(S=[642,548],E=[742,817],W=[796,948],upper=[[601,489],[670,478],[720,639],[794,760],[802,830],[670,857],[644,733]],fore=[[671,800],[800,790],[828,891],[818,973],[753,966],[711,888]],hand=[[751,920],[812,913],[845,955],[855,1000],[843,1033],[815,1032],[802,1008],[780,1028],[753,1015],[736,974]])),
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(identity,source,destination):
    from PIL import Image,ImageDraw
    import numpy as np
    import cv2
    if identity not in PROFILES:raise ValueError('缺少本角色自己的标定 '+identity)
    d=PROFILES[identity];source=Path(source);out=Path(destination);out.mkdir(parents=True,exist_ok=True)
    if (out/'rig.json').is_file():
        existing=json.loads((out/'rig.json').read_text())
        if existing.get('sourceSha256')!=sha(source) or any(not (out/v['path']).is_file() or sha(out/v['path'])!=v['sha256'] for v in existing.get('files',{}).values()):raise ValueError('已有绑定或原图已编辑，保留现有素材并使用新的输出目录')
        return existing
    im=Image.open(source).convert('RGBA')
    if list(im.size)!=d['size']:raise ValueError('原图尺寸变化，不能套用旧坐标')
    expected=json.loads((source.parent/(identity+'-profile.json')).read_text())['assets']['master']['sha256'] if (source.parent/(identity+'-profile.json')).exists() else None
    if expected and sha(source)!=expected:raise ValueError('原图已变更，先核对身份与标定')
    files={}
    def mask(points):
        m=Image.new('L',im.size);ImageDraw.Draw(m).polygon([tuple(p) for p in points],fill=255);return m
    def save(name,image,m):
        image=image.copy();a=np.minimum(np.asarray(image.getchannel('A')),np.asarray(m));image.putalpha(Image.fromarray(a));box=image.getbbox()
        if not box:raise ValueError('分层原图为空 '+name)
        box=(max(0,box[0]-3),max(0,box[1]-3),min(im.width,box[2]+3),min(im.height,box[3]+3));file=out/(identity+'-'+name+'.png');image.crop(box).save(file)
        files[name]=dict(path=file.name,bbox=list(box),sha256=sha(file))
    save('body',im,mask(d['body']))
    for side in ['left','right']:
        for part in ['upper','fore','hand']:save(side+'-'+part,im,mask(d[side][part]))
        for part,joint,radius in [('shoulder-cap','S',30),('elbow-cap','E',38 if identity=='C01' else 26)]:
            x,y=d[side][joint];m=Image.new('L',im.size);ImageDraw.Draw(m).ellipse((x-radius,y-radius,x+radius,y+radius),fill=255);save(side+'-'+part,im,m)
    yy,xx=np.indices((im.height,im.width),dtype=np.float32);original=np.asarray(im);headmask=mask(d['head'])
    for mood in ['neutral','smile','concern','curious','relieved','blink']:
        mx=xx.copy();my=yy.copy();cx,cy,rx,ry=d['mouth'];compression=1
        curve=-7 if mood=='concern' else 0
        def compress(cx,cy,rx,ry,ratio,bend=0):
            nonlocal my
            u=(xx-cx)/rx;weight=np.clip((1-(u/1.45)**2),0,1)**2;center=cy+bend*np.clip(1-u*u,0,1);rel=yy-center;R=ry+28
            mapped=np.interp(rel,[-R,-ry*ratio,ry*ratio,R],[-R,-ry,ry,R])+cy
            vertical=np.clip((R+8-np.abs(yy-cy))/8,0,1);my+=(mapped-yy)*weight*vertical
        # Closed lips use a bounded skin reconstruction and antialiased local
        # stroke; crushing an open mouth creates teeth fragments and scars.
        if mood in ['concern','curious']:
            for i,(bx,by,bw,bh) in enumerate(d['brows']):
                r=((xx-bx)/(bw*1.35))**2+((yy-by)/(bh*2.4))**2;weight=np.clip(1-r,0,1)**2;tilt=(.23 if mood=='concern' else .10)*(1 if i==0 else -1);my+=(xx-bx)*tilt*weight
        if mood=='blink':
            for ex,ey,ew,eh in d['eyes']:compress(ex,ey,ew,eh,.07)
        rendered=cv2.remap(original,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        bad=(original[:,:,3]>128)&(rendered[:,:,3]<250);rendered[bad]=original[bad];rendered[:,:,3]=original[:,:,3]
        if mood in ['neutral','concern','curious','blink']:
            mouth_mask=np.zeros(original.shape[:2],np.uint8);cv2.ellipse(mouth_mask,(cx,cy),(rx+2,ry+3),0,0,360,255,-1)
            rgb=cv2.inpaint(rendered[:,:,:3].copy(),mouth_mask,7,cv2.INPAINT_TELEA);rendered[:,:,:3]=rgb
            face=Image.fromarray(rendered);layer=Image.new('RGBA',(im.width*3,im.height*3));draw=ImageDraw.Draw(layer)
            bend=-6 if mood=='concern' else 4 if mood=='neutral' else 2
            points=[]
            for i in range(61):
                u=i/60;points.append((round((cx-rx*.77+u*rx*1.54)*3),round((cy+4*bend*u*(1-u))*3)))
            draw.line(points,fill=(137,74,55,245),width=5,joint='curve');face=Image.alpha_composite(face,layer.resize(im.size,Image.Resampling.LANCZOS))
            rendered=np.array(face);rendered[:,:,3]=original[:,:,3]
        save('head-'+mood,Image.fromarray(rendered),headmask)
    result=dict(schema='course-texture-rig/1',identity=identity,sourceSha256=sha(source),sourceSize=list(im.size),neck=d['neck'],
        joints={side:{k:d[side][k] for k in ['S','E','W']} for side in ['left','right']},files=files,
        method='source-preserving segmentation + coordinated FK/IK + bounded inverse local feature fields',
        scope='2D rig candidate; source design approval inherited, new motion acceptance pending',naturalWalkReady=False)
    (out/'rig.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result


def stage(identity,project,skill_root):
    p=Path(project);p=p if (p/'workbench.json').exists() else p/'project'
    source=Path(skill_root)/'assets/characters/kgxc-customers-v1'/(identity+'-full-v1.png')
    version=hashlib.sha256((sha(source)+sha(__file__)).encode()).hexdigest()[:10];folder=p/'assets/character-rigs'/(identity+'-'+version)
    rig=prepare(identity,source,folder);assets=[]
    for key,file in rig['files'].items():
        identifier='rig-'+identity+'-'+key;file['assetId']=identifier;assets.append(dict(id=identifier,path=str((folder/file['path']).relative_to(p)),label=identity+' '+key))
    return dict(assets=assets,rig=rig)


def angle(v):return math.degrees(math.atan2(-v[0],v[1]))
def inverse(S,E,W,target):
    L1=math.dist(S,E);L2=math.dist(E,W);dx=target[0]-S[0];dy=target[1]-S[1];dist=math.hypot(dx,dy)
    if dist>L1+L2 or dist<abs(L1-L2):raise ValueError('手部目标超出本角色骨长；不能拉长手臂')
    bend=math.acos(max(-1,min(1,(dist*dist-L1*L1-L2*L2)/(2*L1*L2))))*(-1 if target[0]>S[0] else 1)
    upper=math.atan2(-dx,dy)-math.atan2(L2*math.sin(bend),L1+L2*math.cos(bend))
    return math.degrees(upper),math.degrees(bend)


def pose_angles(rig,pose):
    result={};identity=rig['identity']
    if pose not in ['rest','listen','question','phone-use','tap-phone','welcome']:raise ValueError('本纹理绑定未实现该动作 '+pose)
    for side in ['left','right']:
        S,E,W=[rig['joints'][side][k] for k in ['S','E','W']];rest0=angle([E[0]-S[0],E[1]-S[1]]);rest1=angle([W[0]-E[0],W[1]-E[1]])
        up=0;fore=0;hand=0
        if pose in ['phone-use','tap-phone']:
            cx=512;level={'C01':708,'C02':745,'C03':871}[identity];tx=cx+(-59 if side=='left' else 59)
            if pose=='tap-phone' and side=='right':tx=cx+12;level-=24
            upper,bend=inverse(S,E,W,[tx,level]);up=upper-rest0;fore=upper+bend-rest1-up;hand=-(up+fore)+(-166 if side=='left' else 166)
        elif pose in ['question','welcome'] and side=='right':up=-5;fore=-25;hand=-10
        elif pose=='listen':up=2 if side=='left' else -2
        result[side]=dict(upper=up,fore=fore,hand=hand)
    return result
