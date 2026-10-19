#!/usr/bin/env python3
"""Create a separated enterprise training course; never overwrite existing files."""
from pathlib import Path
import argparse,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
def create(destination):
 destination=Path(destination).expanduser().resolve()
 if destination.exists() and any(destination.iterdir()):raise SystemExit('目标目录非空，不覆盖：'+str(destination))
 destination.mkdir(parents=True,exist_ok=True)
 for name in ['inputs','project','delivery','packages','project/source','project/assets','project/audio','project/media','project/qa','project/work']:(destination/name).mkdir(parents=True,exist_ok=True)
 for p in (ROOT/'assets/templates').iterdir():
  if p.is_file():shutil.copy2(p,destination/'project'/('qa' if p.name in {'assessment-status.json','visual-evidence.json'} else '')/p.name)
 shutil.copytree(ROOT/'assets/profiles/kgxc',destination/'project/assets/brand/kgxc')
 p=destination/'project/project.json';d=json.loads(p.read_text());d['source_file']='../inputs/your-document.pdf';d['layout_version']=2;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 sys.path.insert(0,str(ROOT/'workbench'))
 from authoring import init_project
 init_project(destination/'project',ROOT)
 editor=destination/'project/editor';shutil.copytree(ROOT/'workbench',editor/'workbench',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 (editor/'scripts').mkdir(parents=True)
 for name in ['workbench.py','single_line_subtitles.py','check_workbench.py']:shutil.copy2(ROOT/'scripts'/name,editor/'scripts'/name)
 w={'layout_version':2,'current_version':None,'project_dir':'project','delivery_dir':'delivery','package_dir':'packages','retain_artifacts':[]}
 (destination/'workspace.json').write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n')
 (destination/'README.md').write_text('# 企业培训课程\n\ninputs/：原始资料；project/：唯一制作工程；delivery/：当前成片与字幕；packages/：当前工程包。\n\n工作台已内置，运行 `python3 project/editor/scripts/workbench.py serve .` 即可打开。当前为可编辑草稿，尚未生成声音或视频。制作时填入实际配音、场景、素材与字幕，使用统一工作台配置及导出。\n')
 print('工程已建立（仅模板）：',destination)
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('destination',type=Path);create(a.parse_args().destination)
