"""User-local tools configuration; contains no machine paths or credentials."""
import json
import os
from pathlib import Path


def config_dir():
    return Path(os.environ.get('COURSE_CONFIG_DIR',str(Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'corporate-training-motion'))).expanduser()


def tools():
    p=config_dir()/'tools.json'
    data=json.loads(p.read_text()) if p.is_file() else {}
    return {k:os.path.expandvars(os.path.expanduser(v)) if isinstance(v,str) else v for k,v in data.items()}


def activate():
    data=tools();parents=[]
    for key in ['python','node','ffmpeg','ffprobe']:
        value=data.get(key)
        if value and Path(value).is_absolute():parents.append(str(Path(value).parent))
    os.environ['PATH']=os.pathsep.join(dict.fromkeys(parents+os.environ.get('PATH','').split(os.pathsep)))
    if data.get('node_modules'):os.environ.setdefault('NODE_PATH',data['node_modules'])
    if data.get('browser_path'):os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',data['browser_path'])
    os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
    return data


def browser_options():
    channel=os.environ.get('COURSE_BROWSER_CHANNEL',tools().get('browser_channel','chrome'))
    if channel=='chromium':return {}
    if channel not in ['chrome','msedge']:raise ValueError('browser_channel must be chromium, chrome or msedge')
    return dict(channel=channel)
