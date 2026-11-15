#!/usr/bin/env python3
"""Render original KGXC rules + motion promo; uses the repository's public logo and Ubuntu CJK fonts.
Ubuntu: apt-get install ffmpeg fonts-noto-cjk python3-pil
python3 docs/media/source/kgxc-motion-promo.py --repo-root . --output-dir dist
"""
import argparse
import hashlib
import math
import subprocess
import tempfile
import wave
from array import array
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS = 1920, 1080, 1.5, 30
DURATION = 36
BASE = '#f9f7f3'
MIST = '#eee9e1'
WHITE = '#fffefa'
INK = '#202522'
GREEN = '#185843'
DIM = '#555e57'
LINE = '#dddcd2'
RED = '#c01923'
SOFT_RED = '#f7e8e6'
SOFT_GREEN = '#e8efe7'
MONO = '#6a6963'
BROWN = '#76512e'
SOFT_AMBER = '#f4ebdb'
FONT = Path('/usr/share/fonts/opentype/noto')
LOGOSHA = 'e3af5f28d205ba05c96c72379430f7eef42885229301a7474436e8827dd12179'


def u(x):
    return round(x * S)


def point(xy):
    return tuple(map(u, xy))


def sat(x):
    return min(1.0, max(0.0, x))


def ease(x):
    x = sat(x)
    return x * x * (3 - 2 * x)


def out(x):
    return 1 - (1 - sat(x)) ** 3


def arrive(t, start=0, duration=.5):
    return out((t - start) / duration)


def lerp(a, b, p):
    return a + (b - a) * p


def rgb(c):
    return tuple(bytes.fromhex(c.lstrip('#')))


def color(c, d, p):
    return tuple(round(lerp(a, b, sat(p))) for a, b in zip(rgb(c), rgb(d)))


@lru_cache(None)
def font(n, mode='body'):
    if mode == 'display':
        return ImageFont.truetype(str(FONT/'NotoSerifCJK-Bold.ttc'), u(n), index=2)
    f = 'NotoSansCJK-Bold.ttc' if mode == 'bold' else 'NotoSansCJK-Regular.ttc'
    return ImageFont.truetype(str(FONT/f), u(n), index=2)


class Stage:
    def __init__(self, logo):
        self.logo = logo
        self.im = Image.new('RGB', (W, H), BASE)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, b, fill, border=None, r=0, width=1):
        self.d.rounded_rectangle(point(b), radius=u(r), fill=fill, outline=border,
                                 width=u(width)) if border or fill else None

    def line(self, xy, fill=LINE, width=1):
        self.d.line([point(p) for p in xy], fill=fill, width=max(1, u(width)), joint='curve')

    def oval(self, b, fill=None, outline=None, width=1):
        self.d.ellipse(point(b), fill=fill, outline=outline, width=max(1, u(width)))

    def text(self, x, y, s, n=24, fill=INK, mode='body', anchor='lt'):
        self.d.text((u(x), u(y)), s, font=font(n, mode), fill=fill, anchor=anchor)

    def measure(self, s, n, mode='body'):
        return self.d.textlength(s, font=font(n, mode)) / S

    def badge(self, x, y, s, fg=GREEN, bg=SOFT_GREEN, n=17):
        w = self.measure(s, n, 'bold') + 24
        self.rect((x,y,x+w,y+32),bg,r=15)
        self.text(x+12,y+7,s,n,fg,'bold')
        return w

    def logo_at(self, x, y, w):
        l = self.logo.resize((u(w),round(u(w)*self.logo.height/self.logo.width)),
                             Image.Resampling.LANCZOS)
        self.im.paste(l, point((x,y)),l)

    def card(self, b, fill=WHITE, shadow=True, r=20, border=LINE):
        x,y,x1,y1=b
        if shadow:
            self.rect((x+1,y+7,x1+1,y1+7),MIST,r=r)
        self.rect(b,fill,border,r)

    def tick(self, x,y, c=GREEN, z=1):
        self.line(((x,y+5*z),(x+5*z,y+10*z),(x+15*z,y-1*z)),c,2.5*z)

    def lock(self, x,y, c=RED):
        self.d.arc(point((x+4,y,x+16,y+14)),180,360,fill=c,width=u(2))
        self.rect((x,y+8,x+20,y+24),None,c,3,2)
        self.oval((x+9,y+15,x+11,y+17),c)

    def arrow(self, x, y, c=GREEN, z=1):
        self.line(((x,y),(x+24*z,y)),c,2*z)
        self.line(((x+17*z,y-6*z),(x+24*z,y),(x+17*z,y+6*z)),c,2*z)

    def glyph(self, x, y, key, c=GREEN, n=1):
        if key == 'photo':
            self.rect((x,y,x+22*n,y+17*n),None,c,3*n,1.5*n)
            self.oval((x+13*n,y+3*n,x+17*n,y+7*n),c)
            self.line(((x+3*n,y+13*n),(x+8*n,y+7*n),(x+13*n,y+13*n),(x+16*n,y+10*n),
                       (x+19*n,y+13*n)),c,1.3*n)
        elif key == 'contact':
            self.oval((x+6*n,y,x+15*n,y+9*n),None,c,1.5*n)
            self.d.arc(point((x+2*n,y+8*n,x+19*n,y+20*n)),183,355,fill=c,width=u(1.5*n))
        elif key == 'play':
            self.rect((x,y,x+23*n,y+17*n),None,c,3*n,1.5*n)
            self.d.polygon([point(p) for p in ((x+9*n,y+4*n),(x+9*n,y+13*n),
                                               (x+16*n,y+8.5*n))],fill=c)
        elif key == 'page':
            self.rect((x+3*n,y-2*n,x+19*n,y+19*n),None,c,3*n,1.5*n)
            self.line(((x+6*n,y+5*n),(x+16*n,y+5*n)),c,1.5*n)
            self.line(((x+6*n,y+10*n),(x+15*n,y+10*n)),c,1.5*n)
        elif key == 'branch':
            self.line(((x,y+2*n),(x+9*n,y+9*n),(x+20*n,y+9*n)),c,1.5*n)
            self.line(((x,y+16*n),(x+9*n,y+9*n)),c,1.5*n)
            for xx,yy in ((x,y+2*n),(x,y+16*n),(x+20*n,y+9*n)):
                self.oval((xx-2*n,yy-2*n,xx+2*n,yy+2*n),c)
        elif key == 'lock':
            self.lock(x,y-2*n,c)

    def header(self, index, name):
        self.logo_at(74,46,126)
        self.line(((74,94),(1206,94)))
        self.text(1206,61,f'KGXC  /  {index:02d}  {name}',16,DIM,'bold','rt')

    def foot(self,t, note='酷果星创 · 企业培训课程设计与制作'):
        self.text(74,665,note,15,DIM)
        self.text(1206,665,'KGXC  /  MOTION DESIGN',15,DIM,'bold','rt')
        self.rect((74,695,1206,698),LINE,r=1)
        self.rect((74,695,max(75,74+1132*t/DURATION),698),RED,r=1)

    def phone(self,x,y,w,h, active=False, old=False, evidence=0, evidence_glow=(0,0)):
        self.rect((x+3,y+7,x+w+3,y+h+7),MIST,r=25)
        self.rect((x,y,x+w,y+h),INK,r=25)
        self.rect((x+5,y+5,x+w-5,y+h-5),WHITE,r=21)
        self.rect((x+w*.38,y+12,x+w*.62,y+17),INK,r=3)
        self.text(x+17,y+40,('旧设备' if old else '新设备'),23,INK,'bold')
        self.line(((x+16,y+76),(x+w-16,y+76)))
        content = [('photo','常用照片'),('contact','常用联系人')]
        for i,(key,title) in enumerate(content):
            by=y+97+i*49
            done=bool(old or evidence>=i+1)
            if evidence_glow[i]>.01:
                self.rect((x+12,by-6,x+w-12,by+31),color(WHITE,'#d3e5d9',evidence_glow[i]),r=8)
            self.glyph(x+18,by+3,key,GREEN if done else DIM,.88)
            self.text(x+47,by,title,15 if w<175 else 17,GREEN if done else DIM,'bold')
            if not old and done:
                self.tick(x+w-34,by+5,GREEN,.8)
            elif not old:
                self.line(((x+w-34,by+11),(x+w-22,by+11)),LINE,2)
        if old:
            self.rect((x+16,y+h-70,x+w-16,y+h-24),SOFT_RED,r=9)
            self.lock(x+27,y+h-61)
            self.text(x+54,y+h-58,'暂不清空',18,RED,'bold')
        elif active:
            yes=evidence>=2
            self.rect((x+16,y+h-70,x+w-16,y+h-24),SOFT_GREEN if yes else MIST,r=9)
            self.text(x+28,y+h-58,'核对完成' if yes else '待现场核对',18,GREEN if yes else DIM,'bold')
        self.rect((x+w*.35,y+h-14,x+w*.65,y+h-11),LINE,r=2)


def hero(s,t):
    s.header(1,'设计方法')
    a=arrive(t,.10,.50)
    # Keep the course title visible on encoded frame 0; other elements build in.
    b=max(.88,arrive(t,.31,.70))
    c=max(.88,arrive(t,.50,.44))
    s.badge(74-13*(1-a),133,'企业培训 · 制课 Skill / DSH',GREEN,SOFT_GREEN)
    s.text(74,193+18*(1-b),'把关键动作',75,color(BASE,INK,b),'display')
    s.text(74,292+12*(1-c),'讲明白',93,color(BASE,GREEN,c),'display')
    d=arrive(t,.64,.50)
    rx=74+164*d
    s.rect((74,414,max(75,rx),419),RED,r=2)
    p=arrive(t,.77,.54)
    s.text(74,447,'从一页规则，到一段看得懂的演示',28,color(BASE,DIM,p))
    a=arrive(t,.50,.77)
    y=160+14*(1-a)
    s.card((684,y,1206,y+390),SOFT_GREEN,r=27)
    s.text(711,y+26,'01 / 01    门店操作示意',16,GREEN,'bold')
    s.oval((1056,y+64,1168,y+176),None,'#c6d8cb',1)
    s.oval((1068,y+76,1156,y+164),None,'#c6d8cb',1)
    s.phone(732,y+84,157,240,old=True)
    q=arrive(t,.86,.65)
    s.phone(999+12*(1-q),y+95,161,240,active=True,evidence=2)
    sx=895+95*ease((t-.91)/1.15)
    s.line(((903,y+204),(981,y+204)), '#b8cbbb',2)
    s.oval((sx-5,y+199,sx+5,y+209),GREEN)
    s.foot(t)


def layout(s,t,ab):
    s.header(2,'F 型扫读')
    a=arrive(t,.12,.54)
    s.text(74,125,'同一条规则，先让人找到要做的事',51,color(BASE,INK,a),'display')
    s.text(74,204,'F 型扫读的启发：把行动放前面，限制放在它旁边。',25,DIM)
    y=267+9*(1-arrive(t,.24,.46))
    s.card((74,y,598,y+322),'#f4f1eb',r=19)
    s.badge(96,y+21,'原排法',DIM,'#e9e5dc')
    s.text(96,y+72,'迁移后的处理要求',24,INK,'bold')
    dense=[
        '完成资料迁移后，请在新设备抽查常用照片、',
        '联系人等顾客关心的内容，确认正常，并由',
        '顾客确认后，再进入旧设备清空步骤。',
        '如果顾客还没有确认，旧设备先不要清空。',
    ]
    for i,v in enumerate(dense):
        s.text(96,y+120+i*31,v,20,DIM)
    s.text(96,y+276,'动作、依据和限制混在同一段。',17,DIM)
    s.arrow(619,420,GREEN,1.4)
    p=arrive(t,.50,.78)
    x=679+18*(1-p)
    s.card((x,y,1206+18*(1-p),y+322),WHITE,r=19,border='#cadacf')
    s.badge(x+23,y+21,'按决策重排',GREEN,SOFT_GREEN)
    s.text(x+23,y+73,'先抽查新设备',40,GREEN,'bold')
    s.text(x+23,y+137,'核对内容  /  常用照片、联系人',21,INK,'bold')
    q=arrive(t,1.15,.68)
    s.rect((x+23,y+186,x+503,y+232),color(WHITE,SOFT_RED,q),r=9)
    s.text(x+37,y+198,'顾客未确认 → 暂不清空旧设备',21,color(WHITE,RED,q),'bold')
    s.text(x+23,y+273,'重点前置，例外紧贴相关动作。',17,DIM)
    s.foot(ab,'规则展示示意 · 文本版式不强画 F 形')


def bezier(p, a, b, c, d):
    z=1-p
    return tuple(z*z*z*x + 3*z*z*p*y + 3*z*p*p*w+p*p*p*v for x,y,w,v in zip(a,b,c,d))


def demonstration(s,t,ab):
    s.header(3,'动作演示')
    p=arrive(t,.16,.50)
    s.text(74,123,'先确认新设备，再决定清空旧设备',50,color(BASE,INK,p),'display')
    s.text(74,198,'虚构门店演示  /  关键动作与状态变化逐项对应',24,DIM)
    p=arrive(t,.26,.60)
    dy=11*(1-p)
    s.card((74,256+dy,1206,586+dy),'#f2f3eb',r=25)
    s.phone(150,285+dy,208,272,old=True)
    e1=t>=5.90
    e2=t>=8.20
    flash=tuple(max(0,1-ease((t-at)/.92)) if t>=at else 0 for at in (5.90,8.20))
    s.phone(923,285+dy,208,272,active=True,evidence=int(e1)+int(e2),evidence_glow=flash)
    s.text(640,537,'迁移完成 ≠ 已核对',19,DIM,'bold','mt')
    # Launch path shown in order: visibly prepare, travel, then land and settle.
    a,b,c,d=(401,417+dy),(498,276+dy),(771,292+dy),(878,413+dy)
    if t>=1.14:
        pts=[bezier(i/70,a,b,c,d) for i in range(71)]
        for i in range(0,70,5):
            s.line(pts[i:i+3], '#a5b7a6',2)
        s.oval((a[0]-5,a[1]-5,a[0]+5,a[1]+5),GREEN)
        s.oval((d[0]-5,d[1]-5,d[0]+5,d[1]+5),GREEN)
    badges=((1.65,'photo','常用照片'),(2.90,'contact','常用联系人'))
    for start,key,_ in badges:
        local=t-start
        if not (-.16<=local<=3.08):
            continue
        if local<.42:
            prep=ease((local+.16)/.58)
            x,y=a[0]-19*prep,a[1]+5*prep
            opacity=arrive(local,-.16,.20)
        elif local<2.45:
            q=ease((local-.42)/2.03)
            x,y=bezier(q,(a[0]-19,a[1]+5),b,c,d)
            opacity=1
        else:
            landing=sat((local-2.45)/.63)
            x,y=d[0]+7*math.sin(landing*math.pi)*(1-landing),d[1]
            opacity=1-ease((landing-.55)/.45)
        if opacity>.01:
            s.rect((x-25,y-21,x+25,y+21),color('#f2f3eb',WHITE,opacity),
                   color('#f2f3eb','#98aa9b',opacity),11)
            s.glyph(x-11,y-9,key,color('#f2f3eb',GREEN,opacity))
    checkpoints=[
        (0,'01','先保留旧设备'),
        (1.65,'02','迁移到新设备'),
        (5.75,'03','现场抽查并确认'),
    ]
    stage=2 if t>=5.75 else 1 if t>=1.65 else 0
    for i,(start,num,label) in enumerate(checkpoints):
        x=74+i*387
        active=i==stage
        s.rect((x,606,x+358,643),SOFT_GREEN if active else '#f2eee8',r=8)
        s.text(x+12,615,num,16,GREEN if active else DIM,'bold')
        s.text(x+51,614,label,18,GREEN if active else DIM,'bold')
    if t<1.55:
        title,status,fill='动作前先停一下','旧设备保持原状',SOFT_RED
    elif t<5.75:
        title,status,fill='先移动，再核对','缓入 → 加速 → 减速落定',SOFT_GREEN
    elif t<8.20:
        title,status,fill='现场抽查新设备','逐项查看，别只看传输提示',SOFT_GREEN
    else:
        title,status,fill='核对完成后再询问','经顾客确认后，才进入清空流程',SOFT_GREEN
    s.rect((438,293,841,354),fill,r=15)
    s.text(640,305,title,19,GREEN if t>=1.55 else RED,'bold','mt')
    s.text(640,330,status,16,DIM,'body','mt')
    s.foot(ab,'虚构教学示意，不替代门店规定 · 调度 / 预备动作 / 弧线 / 落定')


def workflow(s,t,ab):
    s.header(4,'制作与交付')
    p=arrive(t,.12,.54)
    s.text(74,130,'把设计落到每一步制课',60,color(BASE,INK,p),'display')
    s.text(74,223,'规则页先看行动。动作页先看对象，再看结果。',25,DIM)
    rows=[
        ('01','讲稿','明确学员要判断什么','page',SOFT_GREEN),
        ('02','分镜','安排动作、焦点与节奏','branch',MIST),
        ('03','有声小样','核对画面和口播是否对上','play',MIST),
        ('04','整课交付','留出读图时间，再检查成片','tick',SOFT_GREEN),
    ]
    for i,(n,h,desc,key,fill) in enumerate(rows):
        k=arrive(t,.34+i*.16,.55 if i%2 else .72)
        x=74+i*288
        y=305+24*(1-k)
        s.card((x,y,x+268,y+273),WHITE,r=18)
        s.rect((x+18,y+18,x+76,y+77),fill,r=12)
        if key=='tick':
            s.tick(x+38,y+44,GREEN,1.2)
        else:
            s.glyph(x+35,y+38,key,GREEN,1.15)
        s.text(x+22,y+107,n,16,GREEN,'bold')
        s.text(x+22,y+143,h,33,color(WHITE,INK,k),'bold')
        s.text(x+22,y+206,desc,17,color(WHITE,DIM,k))
    s.foot(ab)


def close(s,t,ab):
    s.header(5,'了解项目')
    p=arrive(t,.12,.58)
    s.text(74,137,'让规则好读，',79,color(BASE,INK,p),'display')
    q=arrive(t,.28,.73)
    s.text(74,240,'让动作会说话。',79,color(BASE,GREEN,q),'display')
    s.rect((75,355,75+188*arrive(t,.40,.59),361),RED,r=2)
    s.text(74,391,'看看设计说明、动效库和现成样片。',28,DIM)
    s.badge(74,456,'制课 Skill',GREEN,SOFT_GREEN)
    s.badge(195,456,'DSH 工作台',GREEN,SOFT_GREEN)
    s.card((710,376,1206,580),SOFT_GREEN,r=22)
    s.text(738,406,'GITHUB  /  项目主页',17,GREEN,'bold')
    s.text(738,450,'酷果星创企业制课',37,INK,'bold')
    s.text(738,505,'hebokenn / kgxc-corporate-course-skill',20,GREEN,'bold')
    s.arrow(1158,415,GREEN,.9)
    s.foot(ab,'设计灵感：F 型扫读研究 · 迪士尼动画准则（非联名）')


CUTS=(0,5.4,12.2,25.2,31.0,DURATION)
SCENES=(hero,layout,demonstration,workflow,close)


def frame(logo,t):
    i=max(k for k in range(len(SCENES)) if t>=CUTS[k])
    s=Stage(logo)
    fn=SCENES[i]
    a=t-CUTS[i]
    if i==0:
        fn(s,a)
    else:
        fn(s,a,t)
    if i and a < .34:
        old=Stage(logo)
        prior=SCENES[i-1]
        b=CUTS[i]-CUTS[i-1]
        if i==1:
            prior(old,b)
        else:
            prior(old,b,CUTS[i])
        return Image.blend(old.im,s.im,ease(a/.34))
    return s.im


def tones(path):
    """Original quiet UI punctuation; no sampled or third-party audio."""
    rate=48000
    cues=[(.96,440,.54,.030),(5.80,480,.38,.020),(13.45,524,.38,.022),
          (15.50,570,.47,.028),(18.15,655,.35,.025),(20.42,726,.38,.026),(18.10,620,.31,.020),
          (25.65,510,.37,.022),(31.75,560,.58,.022),(32.08,740,.53,.023)]
    samples=array('h',[0])*int(rate*DURATION)
    for t,pitch,span,volume in cues:
        start=int(t*rate)
        for j in range(int(span*rate)):
            x=j/rate
            envelope=min(1,x/.013)*math.exp(-6*x)*(1-(x/span)**2)
            v=volume*envelope*(math.sin(math.tau*pitch*x)+.27*math.sin(math.tau*pitch*1.503*x))
            samples[start+j]+=round(32767*v)
    with wave.open(str(path),'wb') as wav:
        wav.setparams((1,2,rate,len(samples),'NONE','not compressed'))
        wav.writeframes(samples.tobytes())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,default=Path('.'))
    p.add_argument('--output-dir',type=Path,default=Path('dist'))
    p.add_argument('--preview-only',action='store_true',help='Export representative stills, not the MP4')
    p.add_argument('--contact',action='store_true',help='Also export a contact sheet, not a release attachment')
    a=p.parse_args()
    source=a.repo_root/'skills/corporate-training-motion/assets/brand/kgxc-logo.png'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==LOGOSHA, 'Expected public KGXC brand source'
    logo=Image.open(source).convert('RGBA')
    logo=logo.crop(logo.getbbox())
    a.output_dir.mkdir(parents=True,exist_ok=True)
    poster=a.output_dir/'kgxc-motion-promo-poster.jpg'
    frame(logo,2.5).save(poster,quality=94,subsampling=0,optimize=True)
    if a.contact or a.preview_only:
        ts=(0.9,2.5,6.0,9.1,13.0,15.2,16.0,17.1,18.9,20.8,24.0,27.5,33.5)
        tile=Image.new('RGB',(4*480,4*270),BASE)
        for i,t in enumerate(ts):
            f=frame(logo,t)
            tile.paste(f.resize((480,270),Image.Resampling.LANCZOS),((i%4)*480,(i//4)*270))
        tile.save(a.output_dir/'contact.jpg',quality=91,subsampling=0)
    if a.preview_only:
        return
    target=a.output_dir/'kgxc-motion-promo.mp4'
    with tempfile.TemporaryDirectory(prefix='kgxc-promo-') as d:
        audio=Path(d)/'original-ui.wav'
        tones(audio)
        command=['ffmpeg','-nostdin','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
                 '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(audio),
                 '-map','0:v:0','-map','1:a:0','-vf','scale=out_color_matrix=bt709',
                 '-c:v','libx264','-crf','18','-preset','veryfast','-threads','4',
                 '-pix_fmt','yuv420p','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709',
                 '-c:a','aac','-b:a','96k','-movflags','+faststart','-t',str(DURATION),str(target)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for i in range(DURATION*FPS):
                proc.stdin.write(frame(logo,i/FPS).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise SystemExit('ffmpeg export failed')


if __name__=='__main__':
    main()
