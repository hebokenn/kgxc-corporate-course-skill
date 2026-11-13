#!/usr/bin/env python3
"""Render a local GLB fixture to transparent PNG and retain an editable .blend.

Run with ordinary Python; it locates Blender or accepts --blender. No image API.
"""
import argparse,json,shutil,subprocess,sys
from pathlib import Path

def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--model',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--blender');a.add_argument('--azimuth',type=float,default=35);a.add_argument('--category',choices=['fixture','apple-product'],default='fixture');a.add_argument('--apple-reference');x=a.parse_args()
 if x.category=='apple-product' and (not x.apple_reference or not x.apple_reference.startswith(('https://www.apple.com/','https://www.apple.com.cn/','https://support.apple.com/'))):raise ValueError('Apple产品三维模型须绑定实际官方参考，其他品牌不导入')
 if x.model.suffix.lower() not in ['.glb','.gltf']:raise ValueError('支持本地GLB/GLTF')
 if x.out.exists():raise ValueError('输出目录已存在，保留已有素材，指定新的版本目录')
 exe=x.blender or shutil.which('blender');mac=Path('/Applications/Blender.app/Contents/MacOS/Blender')
 if not exe and mac.exists():exe=str(mac)
 if not exe:raise ValueError('未发现本地Blender；保留模型，使用已打包SVG/PNG或配置 --blender')
 x.out.mkdir(parents=True);config=dict(model=str(x.model.resolve()),out=str(x.out.resolve()),angle=x.azimuth,category=x.category,reference=x.apple_reference);(x.out/'request.json').write_text(json.dumps(config,indent=2))
 script=Path(__file__).with_name('retail_blender_scene.py');subprocess.run([exe,'--background','--factory-startup','--python',str(script),'--',str((x.out/'request.json').resolve())],check=True)
 for name in ['asset.png','asset.blend']:
  if not (x.out/name).is_file() or not (x.out/name).stat().st_size:raise ValueError('Blender缺少实际输出 '+name)
 print(json.dumps(dict(png=str(x.out/'asset.png'),editable=str(x.out/'asset.blend'),method='local Blender; no generative image model')))
if __name__=='__main__':main()
