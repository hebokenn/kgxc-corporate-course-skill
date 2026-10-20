#!/usr/bin/env python3
"""Install the Skill and an isolated media runtime; never write credentials."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NAME='corporate-training-motion'


def read(path,default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.pending');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(folder):
    manifest=read(folder/'package-manifest.json');actual={str(p.relative_to(folder)):digest(p) for p in folder.rglob('*') if p.is_file() and p.name!='package-manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    if not manifest or actual!=manifest['files']:raise ValueError('Skill 文件清单或哈希不匹配 请重新下载完整发布包')
    if any(p.is_symlink() for p in folder.rglob('*')):raise ValueError('发布包不能包含符号链接')
    return manifest


def install_skill(source,destination,data_root,replace=False):
    manifest=verify(source)
    skill_name=source.name
    if destination.is_symlink():raise ValueError('目标是已有符号链接 请明确选择另一个 --dest 不覆盖链接')
    if destination.exists():
        try:old=verify(destination)
        except (ValueError,KeyError):
            if not replace:raise ValueError('已有 Skill 含本地修改或来源未知 保留原件 使用 --replace-skill 才会备份后替换')
        else:
            if old==manifest:return 'already_current'
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+NAME+'-',dir=destination.parent));backup=None
    try:
        shutil.copytree(source,stage,dirs_exist_ok=True);verify(stage)
        if destination.exists():
            backup=data_root/'backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')/skill_name;backup.parent.mkdir(parents=True,exist_ok=True)
            destination.rename(backup)
        stage.rename(destination)
    except Exception:
        if backup and not destination.exists():backup.rename(destination)
        raise
    finally:
        if stage.exists():shutil.rmtree(stage)
    return 'installed'


def run(command):
    print('+ '+shlex.join([str(x) for x in command]),flush=True)
    subprocess.run([str(x) for x in command],check=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})


def prepare_runtime(data_root,uv):
    if platform.system()!='Darwin' or platform.machine()!='arm64':raise ValueError('完整安装目前仅验证 macOS Apple 芯片 请用 --skill-only 仅复制 Skill 其他平台未验证')
    missing=[x for x in ['ffmpeg','ffprobe','node','npm'] if not shutil.which(x)]
    if missing:
        brew=shutil.which('brew')
        if not brew:raise ValueError('缺少 '+', '.join(missing)+'；请先安装 Homebrew https://brew.sh/ 再重跑安装命令')
        formula=[]
        if any(x in missing for x in ['ffmpeg','ffprobe']):formula.append('ffmpeg')
        if any(x in missing for x in ['node','npm']):formula.append('node')
        run([brew,'install',*formula])
    node_version=subprocess.check_output([shutil.which('node'),'--version'],text=True).strip()
    if int(node_version.lstrip('v').split('.')[0])<20:raise ValueError('Node.js 版本低于上游声明的20 请更新 Node 后重跑安装 https://nodejs.org/')
    runtime=data_root/'runtime';venv=runtime/'venv';runtime.mkdir(parents=True,exist_ok=True)
    os.environ['UV_PYTHON_INSTALL_DIR']=str(runtime/'python')
    os.environ['UV_PYTHON_BIN_DIR']=str(runtime/'python/bin')
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(runtime/'browsers')
    if not (venv/'bin/python').exists():run([uv,'venv','--managed-python','--python','3.12.13',venv])
    python=venv/'bin/python'
    run([uv,'pip','install','--python',python,'-r',ROOT/'requirements.lock'])
    run([python,'-m','playwright','install','chromium'])
    node_root=runtime/'node';node_root.mkdir(exist_ok=True)
    for name in ['package.json','package-lock.json']:shutil.copy2(ROOT/'config'/name,node_root/name)
    run([shutil.which('npm'),'ci','--prefix',node_root,'--no-audit','--no-fund','--ignore-scripts'])
    return dict(python=str(python),node=shutil.which('node'),node_modules=str(node_root/'node_modules'),ffmpeg=shutil.which('ffmpeg'),ffprobe=shutil.which('ffprobe'),browser_channel='chromium',browser_path=str(runtime/'browsers'))


def prepare_voice(data_root,config_root,skill,uv):
    venv=data_root/'voice/venv'
    if not (venv/'bin/python').exists():run([uv,'venv','--managed-python','--python','3.12.13',venv])
    run([uv,'pip','install','--python',venv/'bin/python','-r',ROOT/'requirements-voice.lock'])
    run([venv/'bin/python',ROOT/'scripts/prepare_voice.py','--root',ROOT,'--data',data_root,'--config',config_root/'voice.json','--skill',skill])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skill-only',action='store_true');p.add_argument('--skip-voice',action='store_true');p.add_argument('--replace-skill',action='store_true');p.add_argument('--uninstall',action='store_true')
    p.add_argument('--dest',type=Path)
    p.add_argument('--agent',choices=['codex','workbuddy','both'],default='both')
    p.add_argument('--data-dir',type=Path,default=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'kgxc-course')
    p.add_argument('--config-dir',type=Path,default=Path(os.environ.get('COURSE_CONFIG_DIR',str(Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/NAME))))
    p.add_argument('--bin-dir',type=Path,default=Path.home()/'.local/bin');p.add_argument('--uv',default=shutil.which('uv'))
    a=p.parse_args();data=a.data_dir.expanduser().absolute();cfg=a.config_dir.expanduser().absolute();bindir=a.bin_dir.expanduser().absolute();receipt_path=data/'install-receipt.json'
    roots=([a.dest.expanduser().absolute().parent] if a.dest else
           [Path.home()/name/'skills' for name in (['.agents','.workbuddy'] if a.agent=='both' else ['.workbuddy' if a.agent=='workbuddy' else '.agents'])])
    dest=(a.dest.expanduser().absolute() if a.dest else roots[0]/NAME)
    receipt=read(receipt_path,{})
    if a.uninstall:
        if receipt.get('skill_path')!=str(dest) or receipt.get('managed_by')!='kgxc-course':raise ValueError('此目标没有本安装器的记录 不自动删除')
        archive=data/'uninstalled'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');archive.mkdir(parents=True)
        installed=receipt.get('skills') or [dict(name=NAME,path=str(dest))]
        for index,item in enumerate(installed):
            target=Path(item['path'])
            if target.is_symlink():raise ValueError('已安装目标变为符号链接，保留原件')
            if target.exists():target.rename(archive/(item['name'] if index==0 else str(index)+'-'+item['name']))
        launcher=Path(receipt.get('launcher',str(bindir/'kgxc-course')))
        if launcher.is_file() and launcher.read_text().startswith('#!/bin/sh\n# kgxc-course managed launcher'):launcher.rename(archive/'kgxc-course')
        receipt_path.rename(archive/'install-receipt.json');print('已卸载 Skill 和启动器 原件保留于 '+str(archive)+'；课程 配置 运行环境未移除');return 0
    # Verify both sources before changing any installed module.
    for name in [NAME,'elearning-course-design']:verify(ROOT/'skills'/name)
    statuses=[]
    for folder in roots:
        for name in [NAME,'elearning-course-design']:
            target=dest if a.dest and name==NAME else folder/name
            status=install_skill(ROOT/'skills'/name,target,data,a.replace_skill)
            statuses.append(dict(name=name,path=str(target),status=status))
    status=statuses[0]['status']
    receipt.update(managed_by='kgxc-course',skill_path=str(dest),skills=statuses,agent=a.agent,version=(ROOT/'VERSION').read_text().strip(),source_repository=read(ROOT/'release.json')['repository'],config_dir=str(cfg))
    write(receipt_path,receipt)
    if not a.skill_only:
        if not a.uv:raise ValueError('找不到 uv 请运行仓库 install.sh 或先按 https://docs.astral.sh/uv/getting-started/installation/ 安装')
        new=prepare_runtime(data,a.uv);existing=read(cfg/'tools.json',{})
        # Existing machine/user choices are never overwritten.
        merged={**new,**existing};merged['managed_by']=existing.get('managed_by','kgxc-course');write(cfg/'tools.json',merged)
    bindir.mkdir(parents=True,exist_ok=True);launcher=bindir/'kgxc-course'
    if launcher.exists() and not launcher.read_text().startswith('#!/bin/sh\n# kgxc-course managed launcher'):raise ValueError('启动器同名文件已存在 已保留 请使用 --bin-dir 选择另一目录')
    command=dest/'scripts/kgxc_course.py';python=read(cfg/'tools.json',{}).get('python',sys.executable)
    launcher.write_text('#!/bin/sh\n# kgxc-course managed launcher\nexport COURSE_CONFIG_DIR='+shlex.quote(str(cfg))+'\nexec '+shlex.quote(str(python))+' '+shlex.quote(str(command))+' "$@"\n');launcher.chmod(0o755)
    receipt['launcher']=str(launcher);receipt['skill_status']=status;write(receipt_path,receipt)
    print('\n两个课程模块已安装：'+', '.join(str(folder) for folder in roots)+'\n快捷入口：'+str(launcher)+'\n在 Codex 或 WorkBuddy 新对话中调用 corporate-training-motion；先确认教学方案与逐字稿，再选择独立课件或导演视频分支。')
    if a.skill_only:print('已更新技能并保留已有媒体与配音配置；新机器仍需完整安装。可运行 kgxc-course doctor 检查。');return 0
    if not a.skip_voice:
        prepare_voice(data,cfg,dest,a.uv)
        configuration=read(cfg/'tools.json',{});configuration['voice_proof']=str(data/'voice/setup-proof.json');write(cfg/'tools.json',configuration)
    return subprocess.call([str(launcher),'doctor',*(['--media-only'] if a.skip_voice else [])])


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.CalledProcessError) as e:print('安装未全部完成：'+str(e),file=sys.stderr);raise SystemExit(2)
