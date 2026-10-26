#!/usr/bin/env python3
"""Colleague-friendly entry point for the internal KGXC course Skill."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate, tools, config_dir, browser_options
activate()


def doctor(media_only=False):
    result=[]
    def item(name,ok,detail,required=True):result.append(dict(name=name,status='ok' if ok else 'missing' if required else 'manual',required=required,detail=detail))
    item('Skill',(ROOT/'SKILL.md').is_file(),str(ROOT))
    item('platform',platform.system()=='Darwin' and platform.machine()=='arm64',platform.platform()+'；完整流程仅验证 macOS arm64')
    item('Python',sys.version_info[:2]>=(3,12),platform.python_version()+'；安装器使用已验证 3.12.13')
    for name in ['ffmpeg','ffprobe','node']:
        value=shutil.which(name);item(name,bool(value),value or '重跑完整安装 或先准备 Homebrew https://brew.sh/')
    for name in ['playwright','numpy','Pillow','scipy','fonttools','opencv-python-headless']:
        try:item(name,True,importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:item(name,False,'重跑完整安装命令')
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,**browser_options());page=b.new_page();page.set_content('<canvas width="16" height="16"></canvas>');b.close()
        item('browser',True,str(browser_options() or 'Playwright Chromium'))
    except Exception as e:item('browser',False,str(e).splitlines()[0]+'；重跑完整安装')
    node=shutil.which('node')
    if node:
        test=subprocess.run([node,'-e',"require('playwright-core'); console.log('ok')"],capture_output=True,text=True)
        item('Node Playwright',test.returncode==0,'playwright-core 可加载' if test.returncode==0 else 'Node 环境缺依赖 重跑完整安装')
    blender=shutil.which('blender') or ('/Applications/Blender.app/Contents/MacOS/Blender' if Path('/Applications/Blender.app/Contents/MacOS/Blender').exists() else None)
    item('Blender',bool(blender),blender or '请安装 Blender https://www.blender.org/download/ 用于三维源工程编辑',False)
    voice={}
    voice_path=config_dir()/'voice.json';proof_path=Path(tools().get('voice_proof',str(config_dir()/'voice-setup-proof-missing.json')));voice_ok=False
    if voice_path.is_file() and proof_path.is_file():
        voice=json.loads(voice_path.read_text());proof=json.loads(proof_path.read_text())
        candidate={**json.loads((proof_path.parent/'install-voice-config.json').read_text()),**voice}
        fingerprint=hashlib.sha256((json.dumps(candidate,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
        audio=proof_path.parent/'setup-test.wav'
        voice_ok=proof.get('status')=='pass' and proof.get('configuration_sha256')==fingerprint and audio.is_file() and proof.get('audio_sha256')==hashlib.sha256(audio.read_bytes()).hexdigest() and Path(voice.get('model','')).is_dir() and Path(voice.get('python','')).is_file()
    from qwen3_tts import CATALOG
    voice_label=voice.get('profile',voice.get('voice_id',CATALOG['default'])) if voice_path.is_file() else CATALOG['default']
    item('Qwen3-TTS / '+voice_label,voice_ok,voice_label+' 短句生成已验证' if voice_ok else '配音尚未完成自动部署 请重跑完整安装 官方项目 https://github.com/QwenLM/Qwen3-TTS',False)
    report=dict(skill='corporate-training-motion',version='5.3.0',media_ready=all(x['status']=='ok' for x in result if x['required']),voice_ready=voice_ok,checks=result)
    report['full_ready']=report['media_ready'] and voice_ok
    for x in result:print(f'[{x["status"]}] {x["name"]}: {x["detail"]}')
    print('\n编辑导出环境：'+('就绪' if report['media_ready'] else '尚未就绪')+'；'+voice_label+' 配音：'+('就绪' if voice_ok else '尚未就绪'))
    config_dir().mkdir(parents=True,exist_ok=True);(config_dir()/'last-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return 0 if (report['media_ready'] if media_only else report['full_ready']) else 2


def main():
    workflow_commands={'start','resume','status','design','decide','checkpoint','package','review','script','director','branch','style'}
    if len(sys.argv)>1 and sys.argv[1] in workflow_commands:
        return subprocess.call([sys.executable,str(ROOT/'scripts/workflow.py'),*sys.argv[1:]])
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=sorted(workflow_commands|{'doctor','new','demo','serve','export','bookends','check'}));args,rest=p.parse_known_args()
    if args.command=='doctor':return doctor(media_only='--media-only' in rest)
    if args.command in workflow_commands:
        return subprocess.call([sys.executable,str(ROOT/'scripts/workflow.py'),args.command,*rest])
    script={'new':'scaffold.py','demo':'example_course.py','serve':'workbench.py','export':'workbench.py','bookends':'bookends.py','check':'check_workbench.py'}[args.command]
    prefix=[args.command] if args.command in ['serve','export'] else []
    return subprocess.call([sys.executable,str(ROOT/'scripts'/script),*prefix,*rest])


if __name__=='__main__':raise SystemExit(main())
