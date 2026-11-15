#!/usr/bin/env python3
"""Beat-locked 64-second KGXC release showcase. Python 3 Pillow + FFmpeg/ffprobe.
Needs validated native-action atlas export plus original stereo score.
"""
import argparse
import collections
import hashlib
import json
import math
import re
import subprocess
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont

W,H,FPS=1920,1080,30
SECONDS=64
DARK='#121b18'
PANEL='#22322a'
WHITE='#f8f6ef'
BLACK='#17221b'
WARM='#eee9dd'
GREEN='#225844'
RED='#cf262c'
PUNCH='#ff6353'
MINT='#d9f37d'
LIGHT='#e8eee3'
GREY='#5c675d'
CJK='/usr/share/fonts/opentype/noto'

# Course samples are from the public release; starts/finishes chosen after frame inspection.
# At 1s from each cut, the geometric midpoint of its source window lands on an accent.
# File stem, source-in, source-out, short action, payoff, outcome flag.
CLIPS=[
('swiss',.95,4.85,'字体层级','先看关键词', '先听需求，|再谈产品'),
('editorial',.95,5.15,'公式拆解','先看怎么算', '先对口径，|再算数字'),
('ink',.65,4.55,'知识分枝','一眼找到关系', '需求对应体验项目'),
('data',1.45,5.15,'数据聚合','让比例有来路', '从 100 条里|找出 20 条'),
('pages',.50,4.50,'翻页比较','把规则并排看', '不用在两页之间|来回找'),
('terminal',1.85,4.75,'记录筛选','看见哪些没算', '只把同口径数据|放在一起'),
('blueprint',1.05,4.45,'扫描连线','照着看核对项', '订单与商品逐项对应'),
('isometric',.65,4.15,'空间拆层','看清部件|对应证据', '外箱、标签、订单|一项不漏'),
('spotlight',.65,3.95,'聚光放大','只聚焦|核对细节', '只放大|需核对的标签'),
('presenter',.90,4.50,'人物手势','让手势|带着视线走', '说到哪一步，|就指到哪一步'),
('whiteboard',.70,4.55,'逐笔路径','顺着线路|看清先后', '知道先做什么，|再做什么'),
('papercut',.55,4.15,'纸艺展开','分阶段|交代任务', '接待前、中、后，|各看各的'),
('correction',2.50,5.90,'对比纠错','先发现，再修正', '差一位，也必须核对'),
('sorting',.95,4.45,'排序归组','乱序任务|怎样归位', '四张任务卡|归到正确位置'),
('timeline',1.30,4.65,'时间轴编排','一边看变化|一边看结果', '移过去，|再看覆盖够不够'),
('comic',.78,3.70,'分镜对话','话术放进|真实情境', '先问使用场景，|再邀约体验'),
('quiz',2.05,5.85,'选择与反馈','答错也知道|为什么', '不只亮答案，|还解释依据'),
('pixel',1.55,5.05,'任务闯关','用关卡|串起确认顺序', '逐关完成，|再到交接'),
]
ACTS=[
('01','先看懂','文字先给行动，条件不要藏。',RED),
('02','再看会','让对象、轨迹和结果接得上。',GREEN),
('03','当场判断','看到差异，才知道下一步怎么做。','#70501b'),
]

# Pedagogical groups, distinct from internal broad registry labels.
GROUPS=[
('规则与视线','先看哪行，重点在哪里', '''chars-in text-rise blur-in typewriter draw-on mask-reveal marker underline spotlight magnify scan callout focus-isolate brace-draw tooltip-point search-match redaction-reveal'''),
('流程与交接','对象怎么走，责任怎么接', '''path-follow handoff route-progress flow-token swimlane-transfer parallel-sync connector-reroute arrow-travel dash-march chain-link dependency-unlock progress-segments lane-distribute queue-enqueue queue-dequeue stack-push stack-pop'''),
('拆分与归组','结构理顺，再看前后关系', '''assemble explode paper-fold sort group-collect branch-grow split-merge grid-deal fan-spread card-flip page-turn carousel-shift accordion-open rank-reorder cluster-pack tree-collapse rotate-inspect'''),
('数据与对照','变了多少，在哪条线判断', '''compare-wipe correct-replace count-up odometer bar-grow ring-progress area-fill record-filter dot-aggregate timeline-reflow balance gauge-sweep threshold-cross venn-intersect pie-sector line-plot scatter-converge'''),
('操作演示','看清手势或输入，才能照做', '''cursor-click drag-drop swipe-pan pinch-zoom scroll-window tab-switch toggle-switch slider-adjust dropdown-expand notification-slide table-row-insert table-row-delete cell-update column-resize signature-write presenter-gesture dialogue'''),
('反馈与机制','反馈说明结果，运动说明原理', '''quiz-feedback pixel-walk evidence-attach check-draw cross-draw checklist-tick stamp-approve histogram-bin ratio-normalize waterfall-step funnel-narrow orbit-revolve pendulum-swing gear-turn spring-compress'''),
]
# All 100 canonical IDs must occur once; assertion below guards group membership against drift.

def run(cmd):
    return subprocess.check_output(cmd)

def clamp(v):
    return max(0,min(1,v))

def ease(v):
    v=clamp(v)
    return v*v*(3-2*v)

def rush(v):
    return 1-(1-clamp(v))**3

def xy(b):
    return tuple(map(round,b))

@lru_cache(None)
def ft(n,kind='bold'):
    face='NotoSerifCJK-Bold.ttc' if kind=='serif' else 'NotoSansCJK-Regular.ttc' if kind=='body' else 'NotoSansCJK-Bold.ttc'
    return ImageFont.truetype(str(Path(CJK)/face),int(n),index=2)

def txt(d,x,y,s,n,fill=BLACK,kind='bold',anchor='lt'):
    d.text((round(x),round(y)),s,font=ft(n,kind),fill=fill,anchor=anchor)

def rr(d,b,c,r=12,outline=None,width=1):
    d.rounded_rectangle(xy(b),r,fill=c,outline=outline,width=width)

def line(d,b,c,w=2):
    d.line(xy(b),fill=c,width=w)

def add_logo(dst,logo,x,y,w):
    l=logo.resize((w,round(w*logo.height/logo.width)),Image.Resampling.LANCZOS)
    dst.paste(l,(x,y),l)

def punch(d,t,x,y,w,base=RED):
    p=(t%.50)/.5
    d.rectangle((x,y,x+round(w*(.48+.52*(1-p)**3)),y+5), fill=base)

def footer(d,t,dark=False):
    fg='#acc2b3' if dark else GREY
    bg='#355044' if dark else '#d6dbd2'
    txt(d,82,1011,'酷果星创  /  企业培训课程设计与制作',21,fg,'body')
    txt(d,1838,1011,'KGXC  /  COURSE MOTION',20,fg,'bold','rt')
    d.rectangle((82,1057,1838,1061),fill=bg)
    d.rectangle((82,1057,82+round(1756*t/SECONDS),1061),fill=PUNCH if dark else RED)

def read_full(stream,n):
    buf=bytearray()
    while len(buf)<n:
        q=stream.read(n-len(buf))
        if not q: break
        buf.extend(q)
    return bytes(buf)

def sample_still(path, t, w, h):
    result=run(['ffmpeg','-nostdin','-v','error','-threads','1','-ss',str(t),'-i',str(path),
                '-frames:v','1','-vf',f'scale={w}:{h}','-threads','1','-c:v','png','-f','image2pipe','-'])
    return Image.open(BytesIO(result)).convert('RGB')

def decode_clip(path, start,end):
    # Exact 2-second cuts on bars; preserve speed direction with no overshoot when available.
    width,height=1408,792
    scale=f'setpts=(PTS-STARTPTS)*{2/(end-start):.9f},fps={FPS},scale={width}:{height}'
    cmd=['ffmpeg','-nostdin','-v','error','-threads','2','-ss',str(start),'-i',str(path),
         '-t','2.02','-an','-vf',scale,'-pix_fmt','rgb24','-threads','1','-frames:v','60',
         '-c:v','rawvideo','-f','rawvideo','pipe:1']
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as p:
        last=None
        for i in range(60):
            r=read_full(p.stdout,width*height*3)
            if len(r)==width*height*3: last=Image.frombytes('RGB',(width,height),r)
            if last is None: raise ValueError(f'Missing frame in {path}')
            yield last
        if p.wait(): raise subprocess.CalledProcessError(p.returncode,cmd)

def intro(t, logo, heroes):
    bg=Image.new('RGB',(W,H),DARK); d=ImageDraw.Draw(bg)
    rr(d,(83,68,343,157),WHITE,12); add_logo(bg,logo,110,87,204)
    txt(d,1836,85,'MOTION SHOWREEL  /  64 S',27,'#b7c8bb','bold','rt')
    txt(d,82,232,'企业培训动效',95,'#ffffff')
    txt(d,82,347,'不只让画面动起来',85,MINT)
    punch(d,t,84,481,423,PUNCH)
    txt(d,84,532,'先看懂规则。',42,'#eaf1e5')
    if t>=.50: txt(d,84,593,'再看会动作。',42,'#eaf1e5')
    if t>=1.0: txt(d,84,654,'最后能自己判断。',42,'#eaf1e5')
    txt(d,84,837,'17 支公开效果样片 + 动效库 100 项原生动作速览',29,'#b8c9bc','body')
    k=min(len(heroes)-1,int(t/.5))
    left=1010-round(30*(1-rush((t%.5)/.18)))
    top=248
    im,key=heroes[k]
    rr(d,(left-9,top-9,1836,top+470),PANEL,18)
    bg.paste(im,(left,top))
    rr(d,(left+24,top+420,left+248,top+468),MINT,7)
    txt(d,left+39,top+429,key,25,BLACK)
    for i in range(8):
        d.rectangle((left+i*100,776,left+i*100+79,781), fill=MINT if i<=k else '#486253')
    footer(d,t,True)
    return bg

def clipframe(i,t, t0,picture):
    q=t-t0
    act=i//6
    number,actname,_,color=ACTS[act]
    fn,_,_,name,benefit,outcome=CLIPS[i]
    bg=Image.new('RGB',(W,H),WHITE); d=ImageDraw.Draw(bg)
    d.rectangle((0,0,1920,134), fill=DARK)
    rr(d,(82,41,268,92),MINT if act==1 else LIGHT,8)
    txt(d,103,51,number+' / '+actname,29,BLACK)
    txt(d,302,48,ACTS[act][2],28,'#e7eee8','body')
    txt(d,1837,48,f'{i+1:02d} / 18',31,'#e7eee8','bold','rt')
    punch(d,t,83,122,1755,PUNCH if act==0 else MINT)
    bg.paste(picture,(82,165))
    rr(d,(1526,167,1838,957),'#eaece2',14)
    txt(d,1550,198,'公开样片',24,GREY)
    txt(d,1550,268,name,37,color)
    line(d,(1550,333,1814,333),color,3)
    # Main benefit lines remain stable while the original course example moves.
    for j,s in enumerate(pack(benefit,6)):
        txt(d,1550,402+j*60,s,41,BLACK)
    if q>=1:
        d.rectangle((1550,584,1814,589),fill=color)
        for j,s in enumerate(pack(outcome,9)):
            txt(d,1550,621+j*43,s,28,color,'bold')
    txt(d,1550,902,'补充样片' if fn=='pages' else '实际课程样片节选',19,GREY,'body')
    footer(d,t)
    return bg

def pack(s,n):
    # Character lengths rather than arbitrary UI cell width. Individual clauses are short.
    return s.split('|') if '|' in s else [s[i:i+n] for i in range(0,len(s),n)]

def bridge(t,logo):
    q=t-40
    bg=Image.new('RGB',(W,H),DARK); d=ImageDraw.Draw(bg)
    txt(d,83,126,'17 支原例，是结果。',68,WHITE)
    if q>=.5: txt(d,83,283,'100 项原生动作，是怎么做。',78,MINT)
    punch(d,t,83,463,790,PUNCH)
    rr(d,(85,550,1830,816),'#263a30',16)
    txt(d,132,610,'调度  /  预备动作  /  轨迹与节奏  /  落定',43,WHITE)
    txt(d,132,710,'借鉴迪士尼动画准则，不需要迪士尼素材。',30,'#b1c5b7','body')
    footer(d,t,True)
    return bg

def gallery_read(actions_root):
    manifest_path=actions_root/'manifest.json'
    m=json.loads(manifest_path.read_text())
    rows=m['actions']
    count=m['count']
    groups=[(title,ben,ids.split()) for title,ben,ids in GROUPS]
    ids=[i for _,_,part in groups for i in part]
    expected={x['id'] for x in rows}
    if m.get('status')!='complete' or count!=100 or m.get('actualRuntimeCount')!=100 or count!=len(rows):
        raise ValueError('Must supply full genuine 100-action runtime atlas export')
    if len(set(ids))!=len(ids) or set(ids)!=expected:
        raise ValueError('Gallery classification mismatch: missing '+str(sorted(expected-set(ids)))+' extra '+str(sorted(set(ids)-expected)))
    fw,fh,columns,atlas_rows=(m[k] for k in ('frameWidth','frameHeight','columns','rows'))
    info={}
    for entry in rows:
        f=actions_root/entry['path']
        if hashlib.sha256(f.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError(f'Unverified native atlas {f}')
        atlas=Image.open(f).convert('RGB')
        if atlas.size!=(fw*columns,fh*atlas_rows):
            raise ValueError(f'Bad atlas dimensions {f}')
        phases=[]
        for i in range(columns*atlas_rows):
            x,y=i%columns*fw,i//columns*fh
            phases.append(atlas.crop((x,y,x+fw,y+fh)).resize((270,152),Image.Resampling.LANCZOS))
        if len(phases)!=12 or not entry['activeRuntimeReceipts'] or entry['distinctReducedFrames']<2:
            raise ValueError(f'Unverified execution evidence {f}')
        info[entry['id']]=(entry,phases)
    return groups,info,m

def gallery(gi,t,groups,info):
    q=t-(42+3*gi)
    title,benefit,ids=groups[gi]
    bg=Image.new('RGB',(W,H),DARK); d=ImageDraw.Draw(bg)
    txt(d,82,57,'动效库  /  六组真实原生渲染速览',27,'#afc3b7','body')
    txt(d,82,107,title,64,MINT)
    txt(d,518,133,benefit,32,'#f0f6ec','body')
    txt(d,1838,81,f'{gi+1:02d} / 06   {len(ids)} 项',30,'#e7eee8','bold','rt')
    punch(d,t,83,207,1760,MINT)
    for i,key in enumerate(ids):
        entry,frames=info[key]
        c,r=i%6,i//6
        x=84+c*294
        y=238+r*236
        # Starts in a controlled stagger but each action's landing is held on the grid.
        p=clamp((q-0.10-(c%3)*.055-r*.12)/2.19)
        fi=min(11,round(11*ease(p)))
        chosen=(i//6)==min(2,int(q))
        rr(d,(x,y,x+280,y+214),'#30493a' if chosen else PANEL,12)
        bg.paste(frames[fi],(x+5,y+5))
        txt(d,x+13,y+166,f'{entry["ordinal"]:02d}',19,'#b3c7b6')
        txt(d,x+57,y+165,entry['title'],24,WHITE if chosen else '#dfeee0')
    txt(d,82,968,'汇总展示。此处以原生渲染的真实动作相位抽帧，不替代逐项验看。',21,'#a3bbac','body')
    footer(d,t,True)
    return bg

def end(t,logo):
    q=t-60
    bg=Image.new('RGB',(W,H),WHITE); d=ImageDraw.Draw(bg)
    add_logo(bg,logo,83,81,281)
    txt(d,1837,91,'KGXC  /  企业培训制课',27,GREY,'bold','rt')
    txt(d,84,245,'让规则好读。',106,BLACK,'serif')
    if q>=.5: txt(d,84,415,'让动作会说话。',106,GREEN,'serif')
    punch(d,t,90,564,649,RED)
    txt(d,89,641,'讲稿 · 分镜 · 有声小样 · 整课交付',34,BLACK)
    rr(d,(1112,294,1837,733),DARK,22)
    txt(d,1163,350,'GITHUB  /  项目主页',29,MINT)
    txt(d,1163,459,'酷果星创企业制课',50,WHITE)
    txt(d,1163,563,'hebokenn / kgxc-corporate-course-skill',26,WHITE)
    txt(d,1163,648,'查看完整动效索引、制课 Skill 与 DSH 工作台',25,'#c1d0c5','body')
    footer(d,t)
    return bg

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',type=Path,default=Path('.'))
    p.add_argument('--actions-root',type=Path,required=True)
    p.add_argument('--audio-file',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('dist'))
    p.add_argument('--preview-only',action='store_true',help='Source art and verified atlas representative stills only.')
    a=p.parse_args(); output=a.output_dir
    output.mkdir(parents=True,exist_ok=True)
    src=a.repo_root/'docs/media'
    m=json.loads((src/'capabilities-manifest.json').read_text())
    official={r['file']:r['sha256'] for r in m['samples']}
    mapped={f'sample-{r[0]}.mp4' for r in CLIPS if r[0]!='pages'}
    assert mapped==set(official) and len(mapped)==17, 'Public catalogue sample coverage changed'
    supplemental=json.loads((src/'embeds.json').read_text())['videos']
    pages=next(x for x in supplemental if x['file']=='sample-pages.mp4')
    for filename,sha in {**official,pages['file']:pages['sha256']}.items():
        if hashlib.sha256((src/filename).read_bytes()).hexdigest()!=sha:
            raise ValueError('Bad previous public source: '+filename)
    actions,info,actionManifest=gallery_read(a.actions_root)
    logo=Image.open(a.repo_root/'skills/corporate-training-motion/assets/brand/kgxc-logo.png').convert('RGBA')
    logo=logo.crop(logo.getbbox())
    hero_spec=[('correction',2.15,'发现差异'),('correction',4.8,'核对结果'),('spotlight',2.3,'聚焦细节'),
               ('isometric',2.3,'拆开看清'),('sorting',2.6,'动作归位'),('quiz',5.5,'选择反馈'),
               ('comic',3.9,'讲清对话'),('pixel',4.9,'完成交接')]
    heroes=[(sample_still(src/f'sample-{f}.mp4',t,816,459),desc) for f,t,desc in hero_spec]
    fr=intro(1.50,logo,heroes)
    fr.save(output/'kgxc-kinetic-showreel-poster.jpg',quality=92,optimize=True,subsampling=0)
    if a.preview_only:
        contact=Image.new('RGB',(1440,1080),WHITE)
        stills=[fr,clipframe(2,9.3,8,sample_still(src/'sample-ink.mp4',3.4,1408,792)),
                clipframe(15,35.4,34,sample_still(src/'sample-comic.mp4',3.4,1408,792)),bridge(41.4,logo),
                *[gallery(i,42+i*3+1.2,actions,info) for i in range(6)],end(63,logo)]
        for i,x in enumerate(stills):
            contact.paste(x.resize((480,270),Image.Resampling.LANCZOS),(i%3*480,i//3*270))
        contact.save(output/'qa-source-contact.jpg',quality=88)
        return
    if not a.audio_file: raise ValueError('A verified 64s original 120 BPM score file is required')
    duration=float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(a.audio_file)]))
    if abs(duration-64)>.04: raise ValueError(f'Audio does not match the frozen beat grid: {duration}')
    target=output/'kgxc-kinetic-showreel.mp4'
    cmd=['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
         '-i',str(a.audio_file),'-map','0:v:0','-map','1:a:0','-vf','scale=out_color_matrix=bt709',
         '-c:v','libx264','-crf','19','-preset','veryfast','-threads','4','-pix_fmt','yuv420p','-colorspace','bt709',
         '-color_primaries','bt709','-color_trc','bt709','-c:a','aac','-b:a','192k','-movflags','+faststart','-t','64',str(target)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        def write(frame):
            proc.stdin.write(frame.tobytes())
        try:
            for n in range(4*FPS): write(intro(n/FPS,logo,heroes))
            for i,(f,a0,b0,*_) in enumerate(CLIPS):
                t0=4+i*2
                for frame_no,picture in enumerate(decode_clip(src/f'sample-{f}.mp4',a0,b0)):
                    write(clipframe(i,t0+frame_no/FPS,t0,picture))
            for n in range(40*FPS,42*FPS): write(bridge(n/FPS,logo))
            for i in range(6):
                for n in range((42+i*3)*FPS,(45+i*3)*FPS):
                    write(gallery(i,n/FPS,actions,info))
            for n in range(60*FPS,64*FPS): write(end(n/FPS,logo))
        finally: proc.stdin.close()
        if proc.wait(): raise subprocess.CalledProcessError(proc.returncode,cmd)
    print(f'{target}: 64.0 s / 17 gallery samples + 1 supplemental / 100 evidenced native-action phases / {actionManifest["sourceCommit"]}')

if __name__=='__main__': main()
