"""Verified desktop delivery and a small playback receipt after engineering cleanup."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import urllib.request
import uuid

from runtime import config_dir
from workflow import read,atomic,now

ROOT_ITEMS={'project','inputs','delivery','packages','versions','README.md','workspace.json','打开课程工作台.command','.DS_Store'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_visible(path):
    """A staging name/source metadata must not hide a delivered Finder item."""
    target=Path(path);hidden=getattr(stat,'UF_HIDDEN',0)
    if hasattr(os,'chflags') and hidden:
        flags=target.stat().st_flags
        if flags&hidden:os.chflags(target,flags&~hidden)


def receipt_file(course_id):
    if not re.fullmatch('[a-f0-9]{32}',course_id):raise ValueError('课程标识无效')
    return config_dir()/'deliveries'/ (course_id+'.json')


def completed(path):
    target=str(Path(path).resolve());target=read(config_dir()/'course-relocations.json',{}).get(target,{}).get('course_path',target)
    for file in (config_dir()/'deliveries').glob('*.json'):
        value=read(file,{})
        if value.get('course_path')==target and all(Path(f['path']).is_file() for f in value.get('files',[])):
            return dict(ok=True,course_path=value['course_path'],delivery_only=True,delivery=value,
                        workflow=dict(course_id=value['course_id'],title=value['title'],revision=value['revision'],stage='complete',
                                      gates=[dict(id='final',status='delivered')],jobs=[],next_action='成品已保存；'+('过程文件此前已清理' if value.get('cleanup_status')=='complete' else '过程文件保留，清理须另行选择确认')+'，仍可在当前会话播放与下载'))


def open_saved_folder(course_path):
    """Open only the verified saved folder from this course's delivery receipt."""
    result=completed(course_path)
    if not result:raise ValueError('本课尚无可核对的保存记录，请先保存成品')
    receipt=result['delivery'];folder=Path(receipt['delivery_root'])
    if folder.is_symlink() or not folder.is_dir():raise ValueError('保存文件夹已移动或缺失，请先核对实际位置')
    for file in receipt['files']:
        path=Path(file['path'])
        if path.is_symlink() or path.parent.resolve()!=folder.resolve() or not path.is_file() or digest(path)!=file['sha256']:
            raise ValueError('本课保存文件已改变或缺失，请先重新核对成品')
    make_visible(folder)
    for file in receipt['files']:make_visible(file['path'])
    if sys.platform!='darwin':raise ValueError('当前原生文件夹打开功能仅验证 macOS')
    try:subprocess.run(['open',str(folder.resolve())],check=True,capture_output=True)
    except subprocess.CalledProcessError as error:raise ValueError('文件夹未能打开，成品文件仍保存在所示位置') from error
    return dict(ok=True,folder=str(folder.resolve()),verified=True)


def copy_verified(source,target):
    if target.is_symlink():raise ValueError('交付目标不能是符号链接')
    expected=digest(source)
    if target.is_file() and digest(target)==expected:
        make_visible(target);return expected
    if target.exists():raise ValueError('目标已有不同内容，请先核对：'+target.name)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name('.'+target.name+'.pending-'+uuid.uuid4().hex)
    try:
        shutil.copy2(source,temporary)
        if digest(temporary)!=expected:raise ValueError('交付字节校验失败：'+target.name)
        temporary.replace(target)
        make_visible(target)
    finally:
        if temporary.exists():temporary.unlink()
    return expected


def deliver(course,workspace,desktop=None):
    workspace=Path(workspace).resolve();root=course.root.resolve()
    if root.parent!=workspace/'courses' or course.root.is_symlink():raise ValueError('只保存当前会话 courses 内的本课成品')
    with course.locked():
        status=course.status()
        if status['stage']!='complete' or not any(g['id']=='final' and g['status']=='delivered' for g in status['gates']):raise ValueError('当前完整视频尚未完成制作端校验与登记')
        if any(j.get('status') in ['queued','rendering','encoding','packaging'] for j in status.get('jobs',[])):raise ValueError('制作任务尚未结束，暂不保存或处理工程')
        files=[course.relative(name) for name in status['artifacts'].get('final',[])]
        videos=[p for p in files if p.suffix.lower()=='.mp4' and p.is_file()]
        if len(videos)!=1:raise ValueError('当前交付应只有一个已登记完整视频')
        video=videos[0];subtitles=next((p for p in files if p.suffix.lower()=='.srt' and p.is_file()),video.with_suffix('.srt'))
        cover_record=read(course.project/'qa/cover-review.json',{});cover=course.relative(cover_record.get('coverPath','')) if cover_record.get('coverPath') else None
        if not subtitles.is_file() or not cover or not cover.is_file() or digest(cover)!=cover_record.get('coverSha256'):raise ValueError('缺少与当前成品对应的字幕或已核对封面')
        final_title=read(course.project/'workbench.json',{}).get('title') or status['title']
        title=re.sub(r'[/\\\x00-\x1f]','-',final_title).strip(' .')[:120] or '课程'
        parent=(Path(desktop) if desktop is not None else Path.home()/'Desktop/ai 制课').resolve();folder=parent/title
        previous=read(receipt_file(status['course_id']),{})
        if previous.get('course_path')==str(root) and previous.get('revision')==status['revision'] and previous.get('cleanup_status')!='complete':
            expected=[digest(file) for file in [video,subtitles,cover]]
            if [file.get('sha256') for file in previous.get('files',[])]==expected and all(Path(file['path']).is_file() and digest(file['path'])==file['sha256'] for file in previous['files']):
                make_visible(folder)
                for file in previous['files']:make_visible(file['path'])
                return completed(root)
        if folder.exists() and any(folder.iterdir()):folder=parent/(title+'-'+status['course_id'][:8])
        if folder.exists() and any(folder.iterdir()):folder=parent/(title+'-'+status['course_id'][:8]+'-r'+str(status['revision']))
        if folder.exists() and any(folder.iterdir()):raise ValueError('本课目标文件夹已有文件，请先核对')
        originals=[]
        for source in status['plan'].get('sources',[]):
            path=course.relative(source['location'])
            if not path.is_file():raise ValueError('原始资料已缺失，工程保留，请先核对')
        staging=parent/('.kgxc-delivery-'+status['course_id']+'-'+uuid.uuid4().hex[:8]);outputs=[]
        try:
            staging.mkdir(parents=True)
            for source,name in [(video,title+'.mp4'),(subtitles,title+'.srt'),(cover,title+'-封面'+cover.suffix.lower())]:
                target=staging/name;sha=copy_verified(source,target);outputs.append(dict(name=name,path=str(folder/name),sha256=sha,bytes=target.stat().st_size))
            if folder.is_dir():folder.rmdir()  # The earlier check permits only an empty destination.
            staging.replace(folder)
            make_visible(folder)
            for output in outputs:make_visible(output['path'])
        finally:
            if staging.is_dir():shutil.rmtree(staging)
        export=read(video.with_suffix('.json'),{});chapters=export.get('playback',{}).get('chapters',[]) if export.get('video_sha256')==digest(video) else []
        policy=read(course.project/'retention-policy.json',{})
        decision=dict(choice='keep',at=now(),evidence=policy.get('evidence'),actor=policy.get('actor','user')) if policy.get('mode')=='keep' and policy.get('evidence') else None
        value=dict(schema='course-delivery-receipt/1',at=now(),course_path=str(root),course_id=status['course_id'],title=title,revision=status['revision'],
                   delivery_root=str(folder),files=outputs,originals=originals,chapters=chapters,review_context=read(course.project/'workbench-review-context.json',{}).get('scope','course-review'),cleanup_status='retained',cleanup_decision=decision)
        receipt=receipt_file(status['course_id']);atomic(receipt,value)
        # Saving verified deliverables never authorizes removal of source work.
        # Retention is the default, including unattended and delegated production.
    return completed(root)


def _retention_context(course,workspace):
    root=course.root.resolve();workspace=Path(workspace).resolve()
    if root.parent!=workspace/'courses' or course.root.is_symlink():raise ValueError('只处理当前会话内本课的过程文件')
    status=course.status();receipt=read(receipt_file(status['course_id']),{})
    if receipt.get('course_path')!=str(root):raise ValueError('请先保存并校验本课桌面成品')
    if status['stage']!='complete' or not any(g['id']=='final' and g['status']=='delivered' for g in status['gates']):raise ValueError('当前完整视频尚未完成校验，保留工程')
    if any(j.get('status') in ['queued','rendering','encoding','packaging'] for j in status.get('jobs',[])):raise ValueError('制作任务尚未结束，保留工程')
    for file in receipt['files']:
        if not Path(file['path']).is_file() or digest(file['path'])!=file['sha256']:raise ValueError('桌面成品已改变或缺失，保留工程，请重新核对')
    return root,workspace,status,receipt


def _inventory(root):
    unknown=[p.name for p in root.iterdir() if p.name not in ROOT_ITEMS]
    if unknown:raise ValueError('工程顶层还有未识别文件，保留并核对：'+'、'.join(unknown))
    rows=[];groups={key:dict(label=label,files=0,bytes=0) for key,label in [('drafts','逐字稿、教学设计与分镜'),('samples','小样、审阅版与旧版本'),('audio','配音与声音过程文件'),('cache','渲染缓存与临时导出'),('other','其余课程工程与输入副本')]}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError('工程含链接文件，保留并核对')
        if not path.is_file():continue
        rel=str(path.relative_to(root));info=path.stat();rows.append([rel,info.st_size,info.st_mtime_ns,info.st_ino])
        key='drafts' if any(x in rel for x in ['transcript','design-plan','director-plan','storyboard','script-editor','studio-content']) else 'samples' if rel.startswith('versions/') or any(x in rel.lower() for x in ['pilot','preview','history','sample']) else 'audio' if rel.startswith('project/audio/') else 'cache' if rel.startswith('project/work/') else 'other'
        groups[key]['files']+=1;groups[key]['bytes']+=info.st_size
    signature=hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()
    return dict(inventory_sha256=signature,file_count=len(rows),bytes=sum(row[1] for row in rows),groups=list(groups.values()))


def cleanup_preview(course,workspace):
    """Show an exact, short-lived inventory. This operation never removes work."""
    with course.locked():
        root,_,status,receipt=_retention_context(course,workspace)
        value=dict(schema='course-cleanup-request/1',request_id=uuid.uuid4().hex,course_id=status['course_id'],course_path=str(root),title=receipt['title'],revision=status['revision'],expires_at=time.time()+1800,**_inventory(root))
        atomic(config_dir()/'cleanup-requests'/(status['course_id']+'.json'),value)
    return dict(ok=True,preview=value)


def retention(course,workspace,choice,request_id=None):
    """Keep/defer are non-destructive; deletion requires the presented request."""
    if choice not in ['keep','later','delete-process-files']:raise ValueError('请选择保留、稍后提醒，或明确清理过程文件')
    with course.locked():
        root,workspace,status,receipt=_retention_context(course,workspace)
        if choice in ['keep','later']:
            receipt.update(cleanup_status='retained' if choice=='keep' else 'deferred',cleanup_decision=dict(choice=choice,at=now(),actor='user-choice'))
            atomic(receipt_file(status['course_id']),receipt)
            return completed(root)
        request=read(config_dir()/'cleanup-requests'/(status['course_id']+'.json'),{})
        if not request_id or request.get('request_id')!=request_id or request.get('course_path')!=str(root) or request.get('expires_at',0)<time.time():raise ValueError('清理需要当前范围弹窗中的明确确认；关闭、预选和制作授权均不算确认')
        if request.get('revision')!=status['revision'] or request.get('inventory_sha256')!=_inventory(root)['inventory_sha256']:raise ValueError('过程文件或课程版本已变化，请重新查看清理范围；当前没有删除文件')
        originals=[];retained=workspace/'docs/training-production/retained-originals'
        for source in status['plan'].get('sources',[]):
            path=course.relative(source['location'])
            if not path.is_file():raise ValueError('原始资料已缺失，保留工程')
            sha=digest(path);target=retained/(sha[:16]+'-'+path.name);copy_verified(path,target);originals.append(dict(path=str(target),sha256=sha))
        service=read(course.project/'work/workbench-service.json',{});identity={}
        if service.get('url'):
            try:
                with urllib.request.urlopen(service['url']+'/api/identity',timeout=4) as response:identity=json.load(response)
            except OSError:pass
        receipt.update(cleanup_status='pending',originals=originals,cleanup_decision=dict(choice=choice,at=now(),actor='user-choice',request_id=request_id,inventory_sha256=request['inventory_sha256'],files=request['file_count'],bytes=request['bytes']))
        atomic(receipt_file(status['course_id']),receipt)
        if identity.get('course_id')==status['course_id'] and identity.get('course_root')==str(root) and identity.get('pid')==service.get('pid'):os.kill(identity['pid'],signal.SIGTERM)
        for name in ['project','inputs','delivery','packages','versions']:
            path=root/name
            if path.is_dir():shutil.rmtree(path)
        for path in list(root.iterdir()):
            if path.name in ROOT_ITEMS and path.is_file():path.unlink()
        root.rmdir();receipt['cleanup_status']='complete';atomic(receipt_file(status['course_id']),receipt)
        request['used_at']=now();atomic(config_dir()/'cleanup-requests'/(status['course_id']+'.json'),request)
    return completed(root)
