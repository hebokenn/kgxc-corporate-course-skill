#!/usr/bin/env python3
"""Change only KGXC course lettering on packaged approved R5/R8 backgrounds."""
from pathlib import Path
import argparse,json,math,subprocess,sys,os,hashlib
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate
activate()
A=ROOT/'assets/bookends';W,H,FPS=1280,720,24;FONT=A/'CourseTitle.otf'
TRACK=json.loads((A/'title-tracking.json').read_text())
def smooth_intro(x):
 x=max(0,min(1,x));return x*x*(3-2*x)
def smooth_outro(x):
 x=max(0,min(1,x));return x*x*x*(10+x*(-15+6*x))

def typography(title,subtitle):
    if not title or len(title)>60: raise ValueError('课程名须为 1–60 字')
    lines=[title]
    size=46
    def font(n): return ImageFont.truetype(str(FONT),n)
    while size>30 and font(size).getlength(title)>680: size-=1
    if font(size).getlength(title)>680:
        # Balanced two lines, preserving wording and punctuation.
        width=lambda i:max(font(32).getlength(title[:i]),font(32).getlength(title[i:]))
        split=min(range(1,len(title)),key=width)
        natural=[i for i in range(5,len(title)-5) if title[i] in '与及和' or title[i-1] in '：，、']
        natural=[i for i in natural if width(i)<=min(690,width(split)+96)]
        if natural:split=min(natural,key=width)
        lines=[title[:split],title[split:]]; size=32
    if any(font(size).getlength(line)>690 for line in lines): raise ValueError('课程名超出安全区，请缩短课程名')
    layer=Image.new('RGBA',(W*2,H*2)); d=ImageDraw.Draw(layer)
    ys=[420] if len(lines)==1 else [408,449]
    for text,y in zip(lines,ys): d.text((W,y*2),text,font=font(size*2),anchor='mm',fill=(69,70,72,255))
    if subtitle:
        ss=21
        while ss>14 and font(ss).getlength(subtitle)>680: ss-=1
        if font(ss).getlength(subtitle)>680: raise ValueError('副标题超出安全区')
        d.text((W,(478 if len(lines)==1 else 491)*2),subtitle,font=font(ss*2),anchor='mm',fill=(119,123,126,255))
    return layer.resize((W,H),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.22)),lines,size

def font(n):return ImageFont.truetype(str(FONT),n)

def split_title(text,size,maxwidth):
 if not text or len(text)>60:raise ValueError('课程主标题须为1–60字')
 while size>24 and font(size).getlength(text)>maxwidth:size-=1
 if font(size).getlength(text)<=maxwidth:return [text],size
 mid=min(range(1,len(text)),key=lambda k:max(font(size).getlength(text[:k]),font(size).getlength(text[k:])))
 lines=[text[:mid],text[mid:]]
 if any(font(size).getlength(x)>maxwidth for x in lines):raise ValueError('主标题超出两行安全区')
 return lines,size

def lettering(title,subtitle,closing):
 lines,size=split_title(title,76,1330)
 layer=Image.new('RGBA',(1600,900));d=ImageDraw.Draw(layer)
 ys=[585] if len(lines)==1 else [550,630]
 for t,y in zip(lines,ys):d.text((800,y),t,font=font(size),anchor='mm',fill=(65,70,76,255))
 if subtitle:
  ss=38
  while ss>23 and font(ss).getlength(subtitle)>1300:ss-=1
  if font(ss).getlength(subtitle)>1300:raise ValueError('副标题超出安全区')
  d.text((800,710 if len(lines)==1 else 743),subtitle,font=font(ss),anchor='mm',fill=(112,121,128,255))
 # Supersampling preserves fine Chinese strokes at native 720p.
 final=Image.new('RGBA',(W*2,H*2));d=ImageDraw.Draw(final)
 lastsize=44
 while lastsize>20 and font(lastsize).getlength(title)>1000:lastsize-=1
 if font(lastsize).getlength(title)>1000:raise ValueError('请缩短课程名，以保持主标题和副标题两行')
 lastlines=[title]
 d.text((W,490*2),title,font=font(lastsize*2),anchor='mm',fill=(45,52,59,255))
 if subtitle:
  ss=24
  while ss>16 and font(ss).getlength(subtitle)>960:ss-=1
  if font(ss).getlength(subtitle)>960:raise ValueError('副标题超出单行安全区')
  d.text((W,552*2),subtitle,font=font(ss*2),anchor='mm',fill=(85,95,104,255))
 return layer,final.resize((W,H),Image.Resampling.LANCZOS),lastlines

def over(bg,layer,opacity=1):
 rgb=layer[:,:,:3][:,:,::-1].astype(np.float32);a=layer[:,:,3].astype(np.float32)/255*opacity
 return bg*(1-a[:,:,None])+rgb*a[:,:,None]

def encode(kind,count,layer,final,out):
 capture=cv2.VideoCapture(str(A/(kind+'-background.mkv')))
 if not capture.isOpened():raise ValueError('不能解码批准品牌背景')
 limit=145 if kind=='intro' else 109
 command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1280x720','-r','24','-i','-','-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(out/(kind+'.mp4'))]
 encoder=subprocess.Popen(command,stdin=subprocess.PIPE);last=None
 try:
  for f in range(1,count+1):
   if f<=limit:
    ok,last=capture.read()
    if not ok:raise ValueError('批准背景帧缺失')
   im=last.copy().astype(np.float32)
   if kind=='intro':
    im=over(im,layer,smooth_intro(((f-1)/24-3.72)/.62))
   else:
    if f<=70 and TRACK[str(f)]['opacity']>.001:
     h,w=layer.shape[:2];mat=cv2.getPerspectiveTransform(np.float32([(0,0),(w,0),(w,h),(0,h)]),np.float32(TRACK[str(f)]['quad']))
     im=over(im,cv2.warpPerspective(layer,mat,(W,H),flags=cv2.INTER_CUBIC),TRACK[str(f)]['opacity'])
    opacity=smooth_outro(((f-1)/24-3.7)/.45)
    if opacity:im=over(im,final,opacity)
   image=np.clip(im,0,255).astype(np.uint8)
   if f==count:cv2.imwrite(str(out/(kind+'-poster.png')),image)
   encoder.stdin.write(image.tobytes())
  encoder.stdin.close()
  if encoder.wait():raise ValueError('品牌片段编码失败')
 finally:
  capture.release()
  if encoder.poll() is None:encoder.kill();encoder.wait()
 for mode in ['preview','1080p30']:
  command=['ffmpeg','-v','error','-y','-i',str(out/(kind+'.mp4')),'-i',str(A/(kind+'-score.wav')),'-map','0:v:0','-map','1:a:0','-af','apad','-t',str(count/24)]
  if mode=='preview':command+=['-c:v','copy']
  else:command+=['-vf','scale=1920:1080,fps=30','-c:v','libx264','-crf','16','-pix_fmt','yuv420p']
  command+=['-c:a','aac','-b:a','256k','-movflags','+faststart',str(out/(kind+'-'+mode+'.mp4'))]
  subprocess.run(command,check=True)
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(A/(kind+'-score.wav')),'-af','apad','-t',str(count/24),'-c:a','pcm_f32le',str(out/(kind+'-soundtrack.wav'))],check=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--title',required=True);p.add_argument('--subtitle',default='');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists() and any(a.out.iterdir()):raise ValueError('目标目录非空 保留已有品牌片段 请选择新目录')
 intro,lines,size=typography(a.title,a.subtitle);course,final,_=lettering(a.title,a.subtitle,'')
 intro_count=math.ceil(max(10.5,4.5+max(map(len,lines))*.25+(len(a.subtitle)*.20 if a.subtitle else 0)+1)*24)
 outro_count=math.ceil(max(7,3.7+len(a.title)*.25+.5)*24)
 a.out.mkdir(parents=True,exist_ok=True);intro.save(a.out/'intro-title-layer.png');course.save(a.out/'outro-course-layer.png');final.save(a.out/'outro-final-layer.png')
 encode('intro',intro_count,np.array(intro),None,a.out);encode('outro',outro_count,np.array(course),np.array(final),a.out)
 report=dict(brand_version='kgxc-bookends-r5-intro-r8-outro',title=a.title,subtitle=a.subtitle,resolution=[1280,720],fps=24,intro_seconds=intro_count/24,outro_seconds=outro_count/24,approval='approved background retained; current lettering and audio seam require review',source=json.loads((A/'packaging-provenance.json').read_text()),files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.out.iterdir() if p.is_file()})
 (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
