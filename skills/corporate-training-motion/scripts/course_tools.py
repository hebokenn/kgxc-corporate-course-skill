#!/usr/bin/env python3
"""One entry point to the course Skill's internal rendering and diagnosis tools."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate, tools
activate()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=['inventory', 'capabilities', 'route', 'upgrade-renderer', 'sfx-catalog', 'sfx-plan', 'sfx-mix', 'prepare-web', 'prepare-illustration',
                                          'render-web', 'render-illustration',
                                          'diagnose-web', 'diagnose-illustration', 'beats', 'workbench'])
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--engine-root', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args, rest = parser.parse_known_args(argv)
    web = ROOT / 'libraries/web'
    art = ROOT / 'libraries/illustration'
    paths = dict(web_renderer=web/'scripts/render.mjs', web_qa=web/'scripts/qa.py',
                 illustration_renderer=art/'scripts/engine/render.py', illustration_qa=art/'scripts/qa.py',
                 workbench=ROOT/'scripts/workbench.py', workbench_renderer=ROOT/'workbench/render_worker.py')
    if args.command == 'inventory':
        print(json.dumps({k:dict(path=str(v.relative_to(ROOT)), exists=v.is_file()) for k,v in paths.items()}, indent=2))
        return 0
    if args.command in ['capabilities','route']:
        from render_routes import capabilities,plan
        if args.command=='capabilities':
            if rest:parser.error('capabilities 不接受其他参数')
            result=capabilities()
        else:
            route_parser=argparse.ArgumentParser(description='Read-only selection of an actual course renderer')
            route_parser.add_argument('--spec',type=Path,required=True)
            route_args=route_parser.parse_args(rest)
            result=plan(json.loads(route_args.spec.read_text()))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('ready',True) else 2
    if args.command=='upgrade-renderer':
        from render_routes import upgrade
        upgrade_parser=argparse.ArgumentParser(description='Explicit renderer upgrade preserving saved edits, audio and timeline')
        upgrade_parser.add_argument('course',type=Path)
        upgrade_parser.add_argument('--spec',type=Path,required=True)
        upgrade_parser.add_argument('--base-revision',type=int,required=True)
        upgrade_args=upgrade_parser.parse_args(rest)
        print(json.dumps(upgrade(upgrade_args.course,upgrade_args.spec,upgrade_args.base_revision,args.dry_run),ensure_ascii=False,indent=2))
        return 0
    if args.command.startswith('sfx-'):
        from sound import catalog,make_plan,mix
        sound_parser=argparse.ArgumentParser(description='Natural interface action SFX for the current course')
        if args.command=='sfx-catalog':
            sound_parser.parse_args(rest);result=catalog()
        else:
            sound_parser.add_argument('course',type=Path)
            if args.command=='sfx-plan':
                sound_parser.add_argument('--events',type=Path,required=True);sound_parser.add_argument('--out');sound_parser.add_argument('--spec')
                sound_args=sound_parser.parse_args(rest)
                if args.dry_run:sound_parser.error('音效计划会复制素材；先用 sfx-catalog 查看，未执行写入')
                result=make_plan(sound_args.course,sound_args.events,sound_args.out,sound_args.spec)
            else:
                sound_parser.add_argument('--plan',type=Path,required=True);sound_parser.add_argument('--narration',required=True)
                sound_parser.add_argument('--out',required=True);sound_parser.add_argument('--bind',action='store_true')
                sound_args=sound_parser.parse_args(rest)
                if args.dry_run:sound_parser.error('音效混音须读取实际音轨；--dry-run 未执行写入')
                result=mix(sound_args.course,sound_args.plan,sound_args.narration,sound_args.out,sound_args.bind)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    if args.command.startswith('prepare-'):
        if args.destination is None or rest:
            parser.error('prepare requires --destination only')
        dest = args.destination
        if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
            parser.error('Destination is not an empty directory; not overwriting')
        if args.command == 'prepare-web':
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(web/'templates/engine.html', dest/'composition.html')
        else:
            shutil.copytree(art/'scripts/engine', dest, dirs_exist_ok=True)
        print(dest.resolve())
        return 0
    config = tools()
    python = os.environ.get('COURSE_PYTHON', config.get('python', sys.executable))
    environment = os.environ.copy()
    environment.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    if config.get('node_modules'):
        environment.setdefault('NODE_PATH', config['node_modules'])
    if args.command == 'workbench':
        cmd = [sys.executable, str(ROOT/'scripts/workbench.py'), *rest]
    elif args.command == 'render-web':
        cmd = [os.environ.get('NODE', config.get('node', 'node')), str(paths['web_renderer']), *rest]
    elif args.command == 'render-illustration':
        engine = args.engine_root or art/'scripts/engine'
        cmd = [python, str(engine/'render.py'), *rest]
        if '--fps' not in rest:
            cmd.extend(['--fps', '30'])
    else:
        script = dict(diagnose_web=paths['web_qa'], diagnose_illustration=paths['illustration_qa'],
                      beats=web/'scripts/beats.py')[args.command.replace('-', '_')]
        cmd = [python, str(script), *rest]
    if args.dry_run:
        print(json.dumps(cmd, ensure_ascii=False))
        return 0
    return subprocess.run(cmd, env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
