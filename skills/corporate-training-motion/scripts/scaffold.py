#!/usr/bin/env python3
"""Create a separated enterprise training course; never overwrite existing files."""
from pathlib import Path
import argparse,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import ensure_dir,config_dir
def create(destination):
 destination=Path(destination).expanduser().resolve()
 if destination.exists() and any(destination.iterdir()):raise SystemExit('目标目录非空，不覆盖：'+str(destination))
 ensure_dir(destination)
 for name in ['inputs','project','delivery','packages','project/source','project/assets','project/audio','project/media','project/qa','project/work']:ensure_dir(destination/name)
 for p in (ROOT/'assets/templates').iterdir():
  if p.is_file():shutil.copy2(p,destination/'project'/('qa' if p.name in {'assessment-status.json','visual-evidence.json'} else '')/p.name)
 shutil.copytree(ROOT/'assets/profiles/kgxc',destination/'project/assets/brand/kgxc')
 shutil.copytree(ROOT/'assets/sfx',destination/'project/audio/sfx')
 p=destination/'project/project.json';d=json.loads(p.read_text());d['source_file']='../inputs/your-document.pdf';d['layout_version']=2
 from qwen3_tts import resolve
 voice_config=config_dir()/'voice.json';selected=resolve(json.loads(voice_config.read_text()) if voice_config.exists() else {})
 d['voice']={k:v for k,v in selected.items() if k not in ['python','model_paths','model','reference_audio','reference_text']}
 d['voice']['model']=selected['model_repository'];d['voice']['status']='selected_default_for_new_narration'
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 sys.path.insert(0,str(ROOT/'workbench'))
 from authoring import init_project
 init_project(destination/'project',ROOT)
 editor=destination/'project/editor';shutil.copytree(ROOT/'workbench',editor/'workbench',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 from render_routes import stage_libraries
 stage_libraries(ROOT,editor/'workbench/motion/lib')
 (editor/'scripts').mkdir(parents=True)
 for name in ['workbench.py','single_line_subtitles.py','check_workbench.py','workflow.py','course_tools.py']:shutil.copy2(ROOT/'scripts'/name,editor/'scripts'/name)
 from workflow import Course
 Course(destination).init()
 w={'layout_version':2,'current_version':None,'project_dir':'project','delivery_dir':'delivery','package_dir':'packages','retain_artifacts':[]}
 (destination/'workspace.json').write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n')
 launcher=destination/'打开课程工作台.command'
 launcher.write_text('#!/bin/sh\ncd -- "$(dirname -- "$0")"\nexec python3 project/editor/scripts/workflow.py resume .\n');launcher.chmod(0o755)
 (destination/'README.md').write_text('# 企业培训课程\n\n双击“打开课程工作台.command”，或运行 python3 project/editor/scripts/workflow.py resume .\n\ninputs/ 原件；project/design-plan.json 教学设计与选择；project/course-state.json 进度与确认；project/workbench.json 画面与时间轴。新课先确认教学方案和逐字稿，再选择独立课件或导演视频。视频先确认三个风格与有声画面小样，再生成整片。\n')
 print('工程已建立（仅模板）：',destination)
if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('destination',type=Path);create(a.parse_args().destination)
