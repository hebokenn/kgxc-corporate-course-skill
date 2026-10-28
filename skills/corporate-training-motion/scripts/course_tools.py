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
    parser.add_argument('command', choices=['continuity-check','continuity-enable','reading-check','reading-enable','direction-check','stage-style-assets','surface-catalog','style-catalog','recommend-visuals','register-style','retail-catalog','inventory', 'capabilities', 'route', 'motion-catalog', 'motion-check', 'craft-check', 'compile-modules', 'asset-catalog', 'compile-assets', 'stage-character-rig', 'stage-contact-pose', 'stage-company-character', 'stage-performance', 'upgrade-renderer', 'sfx-catalog', 'sfx-plan', 'sfx-mix', 'prepare-web', 'prepare-illustration',
                                          'render-web', 'render-illustration',
                                          'diagnose-web', 'diagnose-illustration', 'beats', 'workbench'])
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--engine-root', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args, rest = parser.parse_known_args(argv)
    if args.command=='continuity-check':
        ap=argparse.ArgumentParser(description='Read-only planned pauses and real dry/encoded narration gaps; no automatic holds')
        ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--project',type=Path)
        ap.add_argument('--video',type=Path);ap.add_argument('--out',type=Path)
        ap.add_argument('--first-frame',type=int,default=0);ap.add_argument('--last-frame',type=int)
        aa=ap.parse_args(rest)
        if aa.video and not aa.project:ap.error('--video 同时需要 --project 核对旁白干声')
        from continuity_pacing import inspect,audit
        doc=json.loads(aa.spec.read_text())
        result=audit(doc,aa.project,aa.first_frame,aa.last_frame,aa.video,force=True) if aa.project else inspect(doc,force=True)
        if aa.out:
            if args.dry_run or aa.out.exists() or aa.out.resolve()==aa.spec.resolve():ap.error('保留已有工程和报告；指定新的 --out')
            aa.out.parent.mkdir(parents=True,exist_ok=True);aa.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result['status']=='fail'else 0
    if args.command=='continuity-enable':
        ap=argparse.ArgumentParser();ap.add_argument('course',type=Path);ap.add_argument('--evidence',required=True);aa=ap.parse_args(rest)
        if args.dry_run:ap.error('旧课显式启用会保存历史；先用 continuity-check 诊断')
        from continuity_pacing import enable
        print(json.dumps(enable(aa.course,aa.evidence),ensure_ascii=False,indent=2));return 0
    if args.command=='reading-check':
        ap=argparse.ArgumentParser(description='Actual stable text exposure, reading focus and retention; read-only diagnosis')
        ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path);aa=ap.parse_args(rest)
        from reading_pacing import inspect
        result=inspect(json.loads(aa.spec.read_text()),force=True)
        if aa.out:
            if args.dry_run or aa.out.exists()or aa.out.resolve()==aa.spec.resolve():ap.error('保留已有文件；检查不改工程，指定新的 --out')
            aa.out.parent.mkdir(parents=True,exist_ok=True);aa.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result['status']=='fail'else 0
    if args.command=='reading-enable':
        ap=argparse.ArgumentParser();ap.add_argument('course',type=Path);ap.add_argument('--evidence',required=True);aa=ap.parse_args(rest)
        if args.dry_run:ap.error('启用阅读契约是显式修改；使用 reading-check 先只读检查')
        from reading_pacing import enable
        print(json.dumps(enable(aa.course,aa.evidence),ensure_ascii=False,indent=2));return 0
    if args.command=='direction-check':
        ap=argparse.ArgumentParser(description='Read-only content inventory and critical-frame candidates, not creative approval')
        ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path);aa=ap.parse_args(rest)
        from direction_review import inspect
        import hashlib
        result=inspect(json.loads(aa.spec.read_text()));result['documentSha256']=hashlib.sha256(aa.spec.read_bytes()).hexdigest()
        if aa.out:
            if args.dry_run:ap.error('--dry-run 不写入检查计划')
            if aa.out.exists() or aa.out.resolve()==aa.spec.resolve():ap.error('保留已有工程或检查计划；指定新的 --out')
            aa.out.parent.mkdir(parents=True,exist_ok=True);aa.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(aa.out)
        else:print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    if args.command=='surface-catalog':
        from visual_styles import registry
        print(json.dumps([dict(id=s['id'],title=s['title'],surface=s.get('surface'),evidence=s.get('materialEvidence')) for s in registry().values()],ensure_ascii=False,indent=2));return 0
    if args.command=='stage-style-assets':
        ap=argparse.ArgumentParser();ap.add_argument('course',type=Path);ap.add_argument('--style',required=True);ap.add_argument('--out',type=Path,required=True);aa=ap.parse_args(rest)
        if aa.out.exists():ap.error('输出已存在，保留原件并指定新版本')
        from visual_styles import stage_style_assets
        result=stage_style_assets(aa.course,aa.style,ROOT);aa.out.parent.mkdir(parents=True,exist_ok=True);aa.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(aa.out);return 0
    if args.command in ['style-catalog','recommend-visuals','register-style','retail-catalog']:
        from visual_styles import catalog,register,recommend
        if args.command in ['style-catalog','retail-catalog']:
            if rest:parser.error('目录命令不接受额外参数')
            result=catalog() if args.command=='style-catalog' else __import__('retail_assets').catalog()
        else:
            ap=argparse.ArgumentParser()
            if args.command=='register-style':ap.add_argument('--file',type=Path,required=True)
            else:ap.add_argument('--intent',required=True)
            aa=ap.parse_args(rest)
            if args.command=='register-style' and args.dry_run:parser.error('先检查风格JSON；dry-run不会注册')
            result=register(aa.file) if args.command=='register-style' else recommend(aa.intent)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    if args.command=='craft-check':
        ap=argparse.ArgumentParser(description='Read-only composition signals and bound aesthetic evidence')
        ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--project',type=Path);ap.add_argument('--video',type=Path)
        aa=ap.parse_args(rest)
        if bool(aa.project)!=bool(aa.video):ap.error('核对成片须同时提供 --project 与 --video')
        from craft_quality import analyze,review
        doc=json.loads(aa.spec.read_text());result=analyze(doc)
        if aa.video:result['review']=review(aa.project,doc,aa.video)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('review',{}).get('status')=='pending' else 0
    if args.command in ['asset-catalog','compile-assets','stage-character-rig','stage-contact-pose','stage-company-character','stage-performance']:
        if args.dry_run and args.command!='asset-catalog':parser.error('本素材命令不支持 --dry-run；未执行写入。先用 asset-catalog 查看能力')
        from content_assets import catalog,expand
        if args.command=='asset-catalog':
            if rest:parser.error('asset-catalog 不接受其他参数')
            result=catalog()
        else:
            ap=argparse.ArgumentParser(description='Code-authored content assets in the actual course graph')
            if args.command=='compile-assets':ap.add_argument('--spec',type=Path,required=True)
            else:ap.add_argument('course',type=Path);ap.add_argument('--identity',choices=['C01','S01'] if args.command=='stage-performance' else ['M1','S01','S02','COACH'] if args.command=='stage-company-character' else ['C01','C02','C03'],required=True)
            ap.add_argument('--out',type=Path,required=True);aa=ap.parse_args(rest)
            if aa.out.exists():ap.error('输出已存在，保留既有文件；指定新的 --out')
            if args.command=='compile-assets':result=expand(json.loads(aa.spec.read_text()))
            elif args.command=='stage-character-rig':
                from character_rig import stage
                result=stage(aa.identity,aa.course,ROOT)
            elif args.command=='stage-performance':
                from character_performance import stage
                result=stage(aa.identity,aa.course,ROOT)
            elif args.command=='stage-contact-pose':
                from character_pose import stage_pose
                result=stage_pose(aa.identity,aa.course,ROOT)
            else:
                from company_characters import stage_company
                result=stage_company(aa.identity,aa.course,ROOT)
            aa.out.parent.mkdir(parents=True,exist_ok=True);aa.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        if args.command=='asset-catalog':print(json.dumps(result,ensure_ascii=False,indent=2))
        else:print(aa.out)
        return 0
    if args.command in ['motion-catalog','motion-check','compile-modules']:
        if args.command=='motion-catalog':
            if rest:parser.error('motion-catalog 不接受其他参数')
            from motion_catalog import inventory
            from teaching_modules import catalog
            result=inventory();result['modules']=catalog()
        else:
            motion_parser=argparse.ArgumentParser(description='Executable teaching modules and full-course motion quality')
            motion_parser.add_argument('--spec',type=Path,required=True)
            motion_parser.add_argument('--out',type=Path)
            if args.command=='motion-check':motion_parser.add_argument('--video',type=Path)
            motion_args=motion_parser.parse_args(rest)
            from teaching_modules import expand
            result=expand(json.loads(motion_args.spec.read_text()))
            if args.command=='motion-check':
                from motion_quality import preflight,audit_encoded
                doc=result;result=preflight(doc)
                if motion_args.video:result['encoded']=audit_encoded(motion_args.video,doc,0,doc['sourceDurationFrames'])
            if motion_args.out:
                if args.dry_run:parser.error('--dry-run 不写入输出')
                motion_args.out.parent.mkdir(parents=True,exist_ok=True)
                motion_args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        if args.command=='compile-modules' and motion_args.out:print(motion_args.out)
        else:print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get('status')=='fail' or result.get('encoded',{}).get('status') in ['fail','review-required'] else 0
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
            from sound import PALETTE,project_path
            sound_parser.add_argument('course',type=Path,nargs='?');sound_parser.add_argument('--palette',default=PALETTE)
            sound_args=sound_parser.parse_args(rest);result=catalog(project_path(sound_args.course) if sound_args.course else None,sound_args.palette)
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
