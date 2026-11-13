#!/usr/bin/env python3
"""Preserve and register user-local assets; stage them into a course by immutable hash."""
import argparse,hashlib,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from runtime import config_dir

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def root():return config_dir()/'asset-library'
def read():
 p=root()/'catalog.json';return json.loads(p.read_text()) if p.exists() else dict(schema='course-user-assets/1',assets=[])
def save(d):
 root().mkdir(parents=True,exist_ok=True);(root()/'catalog.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def register(file,identifier,title,license='user-provided-private',tags=(),source=None,product=None):
 if product:
  if product.get('brand') not in ['Apple','Apple-compatible-unbranded']:raise ValueError('产品只允许 Apple 或无其他品牌的 Apple 适配配件')
  if product.get('brand')=='Apple-compatible-unbranded' and not product.get('compatibleWith'):raise ValueError('适配配件须说明对应的 Apple 设备')
 if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{1,100}',identifier):raise ValueError('素材ID须为字母数字、点、下划线、连字符')
 file=Path(file).resolve()
 if file.suffix.lower() not in ['.svg','.png','.jpg','.jpeg','.webp']:raise ValueError('支持SVG、PNG、JPEG、WebP')
 raw=digest(file);dest=root()/'files'/(identifier+'-'+raw[:12]+file.suffix.lower());dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists():shutil.copy2(file,dest)
 d=read();old=next((x for x in d['assets'] if x['id']==identifier),None)
 if old and old['sha256']!=raw:raise ValueError('同ID已有其他版本，请使用新ID保留旧素材')
 item=dict(id=identifier,title=title,path=str(dest.relative_to(root())),sha256=raw,license=license,tags=list(tags),source=source or dict(file=str(file)),visibility='private-local' if license.startswith('user-') else 'licensed-source',product=product)
 if old is None:d['assets'].append(item);save(d)
 return item

def import_photo(file,identifier,title):
 from PIL import Image,ImageOps,ImageFilter,ImageChops
 file=Path(file);src=register(file,identifier+'-original',title+' 原始实拍',tags=['store','photo','original'])
 im=ImageOps.exif_transpose(Image.open(file)).convert('RGB');im.thumbnail((1920,1080))
 base=im.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.SMOOTH_MORE)
 poster=base.quantize(colors=28,method=Image.Quantize.MEDIANCUT).convert('RGB')
 edges=base.convert('L').filter(ImageFilter.FIND_EDGES).point(lambda p:0 if p>30 else 255).filter(ImageFilter.MaxFilter(3))
 ink=ImageChops.multiply(poster,Image.merge('RGB',(edges,edges,edges)))
 work=root()/'derived';work.mkdir(parents=True,exist_ok=True);out=[]
 for suffix,pic in [('flat',poster),('ink',ink)]:
  p=work/(identifier+'-'+suffix+'.png');pic.save(p)
  out.append(register(p,identifier+'-'+suffix,title+(' 平涂卡通化' if suffix=='flat' else '线稿卡通化'),tags=['store','cartoon','photo-derived'],source=dict(originalAssetId=src['id'],originalSha256=src['sha256'],method='Pillow local median/smooth, quantization, optional edge ink; no generative model')))
 return [src,*out]

def catalog():
 d=read();icons=ROOT/'assets/open-source/lucide/icons'
 return dict(schema='course-asset-library/1',privateAssets=d['assets'],bundledIcons=[dict(id='lucide:'+p.stem,path=str(p.relative_to(ROOT)),license='ISC') for p in sorted(icons.glob('*.svg'))],bundledRetail=[dict(id='retail:'+x['id'],kind=x['kind'],description=x['description']) for x in json.loads((ROOT/'assets/retail-v1/catalog.json').read_text())['assets']] if (ROOT/'assets/retail-v1/catalog.json').exists() else [],bundledFixtures=[dict(id='kenney:'+p.stem,license='CC0',category='fixture') for p in sorted((ROOT/'assets/open-source/kenney-furniture/sprites').glob('*.png'))],extension='register new SVG/PNG with source, license, stable ID; keep user references in local library, stage only selected files into the course')

def stage(course,identifier):
 p=Path(course).resolve();p=p if (p/'workbench.json').exists() else p/'project'
 if not p.is_dir():raise ValueError('课程project目录不存在')
 if identifier.startswith('retail:') or identifier.startswith('kenney:'):
  prefix,name=identifier.split(':',1)
  if not re.fullmatch('[a-zA-Z0-9-]+',name):raise ValueError('无效库素材ID')
  source=ROOT/('assets/retail-v1' if prefix=='retail' else 'assets/open-source/kenney-furniture/sprites')/(name+('.svg' if prefix=='retail' else '.png'));item=dict(id=identifier,title=name,sha256=digest(source),license='original-code' if prefix=='retail' else 'CC0',category='fixture' if prefix=='kenney' else 'retail-factory',source='retail-v1' if prefix=='retail' else 'Kenney Furniture Kit 2.0')
 elif identifier.startswith('lucide:'):
  name=identifier.split(':',1)[1]
  if not re.fullmatch('[a-z0-9-]+',name):raise ValueError('无效图标ID')
  source=ROOT/'assets/open-source/lucide/icons'/(name+'.svg');item=dict(id=identifier,title=name,sha256=digest(source),license='ISC',source='lucide-icons/lucide v0.468.0')
 else:
  item=next((x for x in read()['assets'] if x['id']==identifier),None)
  if not item:raise ValueError('素材尚未注册 '+identifier)
  source=root()/item['path']
 if digest(source)!=item['sha256']:raise ValueError('素材哈希已变化，保留原件并注册新版本')
 aid=re.sub('[^a-zA-Z0-9-]','-',identifier)+'-'+hashlib.sha256(identifier.encode()).hexdigest()[:8];dest=p/'assets/library'/(aid+'-'+item['sha256'][:12]+source.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists() and digest(dest)!=item['sha256']:raise ValueError('课程素材已被编辑，不覆盖')
 if not dest.exists():shutil.copy2(source,dest)
 notices=p/'assets/library/attribution.json';ledger=json.loads(notices.read_text()) if notices.exists() else []
 record={k:v for k,v in item.items() if k!='path'}
 if record not in ledger:ledger.append(record);notices.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
 if identifier.startswith('lucide:'):shutil.copy2(ROOT/'assets/open-source/lucide/LICENSE',p/'assets/library/LUCIDE-LICENSE')
 if identifier.startswith('kenney:'):shutil.copy2(ROOT/'assets/open-source/kenney-furniture/LICENSE.txt',p/'assets/library/KENNEY-LICENSE.txt')
 return dict(assets=[dict(id=aid,path=str(dest.relative_to(p)))],node=dict(id=aid+'-image',type='image',assetId=aid,x=100,y=200,width=800,height=450,role='subject'),source=record)

def main():
 a=argparse.ArgumentParser(description=__doc__);sub=a.add_subparsers(dest='command',required=True)
 sub.add_parser('catalog')
 for command in ['register','import-photo']:
  p=sub.add_parser(command);p.add_argument('--file',type=Path,required=True);p.add_argument('--id',required=True);p.add_argument('--title',required=True)
  if command=='register':p.add_argument('--license',default='user-provided-private');p.add_argument('--tags',default='');p.add_argument('--category',choices=['reference','product'],default='reference');p.add_argument('--brand');p.add_argument('--compatible-with');p.add_argument('--product-family')
 p=sub.add_parser('stage');p.add_argument('course',type=Path);p.add_argument('--id',required=True);p.add_argument('--out',type=Path,required=True)
 x=a.parse_args()
 if x.command=='catalog':r=catalog()
 elif x.command=='import-photo':r=import_photo(x.file,x.id,x.title)
 elif x.command=='register':r=register(x.file,x.id,x.title,x.license,x.tags.split(','),product=dict(brand=x.brand,family=x.product_family,compatibleWith=x.compatible_with) if x.category=='product' else None)
 else:
  if x.out.exists():raise ValueError('输出已存在，请指定新文件')
  r=stage(x.course,x.id);x.out.parent.mkdir(parents=True,exist_ok=True);x.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
