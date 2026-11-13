#!/usr/bin/env python3
"""Create local material treatments from approved role masters, preserving originals."""
from pathlib import Path
import argparse,hashlib,json

def build(skill,out):
 from PIL import Image,ImageOps,ImageFilter,ImageEnhance,ImageChops
 import numpy as np
 import cv2
 skill=Path(skill);out=Path(out);out.mkdir(parents=True,exist_ok=True);base=skill/'assets/profiles/kgxc';kg=Image.open(base/'kg-original.png').convert('RGBA');rows=[]
 sources={'M1':base/'M1-repaired.png','S01':base/'blue-cast.png','S02':base/'blue-cast.png','COACH':base/'MyCoach-reference-2D.png','C01':skill/'assets/characters/kgxc-customers-v1/C01-full-v1.png','C02':skill/'assets/characters/kgxc-customers-v1/C02-full-v1.png','C03':skill/'assets/characters/kgxc-customers-v1/C03-full-v1.png'}
 for identity,file in sources.items():
  im=Image.open(file).convert('RGBA')
  if identity=='M1':
   mark=kg.resize((70,round(70*251/321)),Image.Resampling.LANCZOS);im.alpha_composite(mark,(559,458))
  if identity=='S01':
   im=im.crop((0,0,round(im.width*.48),im.height));mark=kg.resize((48,round(48*251/321)),Image.Resampling.LANCZOS);im.alpha_composite(mark,(440,320))
  if identity=='S02':
   im=im.crop((round(im.width*780/1536),0,round(im.width*(780/1536+.48)),im.height));mark=kg.resize((48,round(48*251/321)),Image.Resampling.LANCZOS);im.alpha_composite(mark,(390,320))
  # Preserve a composed baseline with the correct original uniform mark.
  full=out/(identity+'-original.png');im.save(full);alpha=im.getchannel('A');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);rgb=white.convert('RGB');arr=np.asarray(rgb)
  styles={}
  styles['cel-paint']=rgb.filter(ImageFilter.MedianFilter(3)).quantize(colors=30).convert('RGB')
  gray=ImageOps.grayscale(rgb);edges=gray.filter(ImageFilter.FIND_EDGES).point(lambda v:255 if v<27 else 25)
  styles['ink-paper']=ImageOps.colorize(ImageOps.invert(gray).point(lambda x:255 if x>110 else 0),'#faf5e3','#334839')
  smooth=cv2.stylization(arr,sigma_s=65,sigma_r=.32);styles['watercolor']=Image.fromarray(smooth)
  styles['graphite']=ImageOps.colorize(ImageChops.multiply(gray,edges),'#282d2a','#efeadc')
  styles['newsprint']=ImageOps.colorize(gray.quantize(colors=5).convert('L'),'#242a28','#e9e4d3')
  comic=Image.fromarray(cv2.bilateralFilter(arr,9,85,85)).quantize(colors=12).convert('RGB');styles['comic-halftone']=ImageChops.multiply(comic,Image.merge('RGB',(edges,edges,edges)))
  styles['pixel-dither']=rgb.resize((max(1,im.width//12),max(1,im.height//12)),Image.Resampling.BOX).quantize(colors=18).convert('RGB').resize(im.size,Image.Resampling.NEAREST)
  styles['original']=rgb
  for surface,pic in styles.items():
   pic=pic.convert('RGBA');pic.putalpha(alpha);dest=out/(identity+'-'+surface+'.png');pic.save(dest);rows.append(dict(id=identity+'-'+surface,identity=identity,surface=surface,file=dest.name,source=file.name,sourceSha256=hashlib.sha256(file.read_bytes()).hexdigest(),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),method='local deterministic image processing of the same approved master; no new identity or generative image model',uniform='original KG' if identity in ['M1','S01','S02'] else 'original MyCoach' if identity=='COACH' else 'customer'))
 (out/'catalog.json').write_text(json.dumps(dict(schema='approved-role-surfaces/1',assets=rows),ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(count=len(rows),output=str(out))))
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--skill',type=Path,default=Path(__file__).resolve().parents[1]);a.add_argument('--out',type=Path,required=True);x=a.parse_args();build(x.skill,x.out)
