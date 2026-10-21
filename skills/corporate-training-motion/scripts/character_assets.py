#!/usr/bin/env python3
"""Create/edit character briefs and stage verified assets without inventing approval."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from runtime import activate
activate()


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(profile):
    from PIL import Image
    path=Path(profile).resolve();d=json.loads(path.read_text());errors=[]
    if d.get('schema')!='course-character/1':errors.append('未知角色格式')
    for role,a in d.get('assets',{}).items():
        f=(path.parent/a.get('path','')).resolve()
        if not f.is_relative_to(path.parent) or not f.is_file():errors.append('缺少/越界素材 '+role);continue
        if sha(f)!=a.get('sha256'):errors.append('素材已变化，不能沿用旧确认 '+role)
        if role=='master':
            im=Image.open(f)
            if 'A' not in im.getbands() or im.getchannel('A').getextrema()[0]!=0 or im.getchannel('A').getextrema()[1]<250:errors.append('全身原图需要真实透明与清楚实体')
            if min(im.size)<500:errors.append('全身原图分辨率不足')
    if 'master' not in d.get('assets',{}):errors.append('尚无独立全身原图；设计板不能作为生产原图')
    for name,view in d.get('views',{}).items():
        crop=view.get('crop',[])
        if len(crop)!=4 or any(type(x) not in [int,float] for x in crop) or min(crop)<0 or crop[2]<=0 or crop[3]<=0 or crop[0]+crop[2]>1 or crop[1]+crop[3]>1:errors.append('取景范围无效 '+name)
    approval=d.get('approval') or {};design=d.get('assets',{}).get('design',{})
    design_ok=approval.get('stage')=='design' and bool(approval.get('evidence')) and any(a.get('sha256')==design.get('sha256') for a in approval.get('approvedFiles',[]))
    return dict(ok=not errors,errors=errors,designApproved=design_ok,naturalJointAnimationReady=bool(d.get('performance',{}).get('naturalJointAnimationReady')),scope='asset integrity and approval binding; anatomy and motion require actual visual review')


def prepare(destination,identifier,role,outfit):
    dest=Path(destination)
    if dest.exists() and any(dest.iterdir()):raise ValueError('目录非空，不覆盖已有角色')
    dest.mkdir(parents=True,exist_ok=True)
    brief=dict(schema='course-character-brief/1',id=identifier,role=role,outfit=outfit,
        referenceImages=[],identity=['face','hair','skin','body-proportions','outfit','shoes'],
        views=['full-front','full-three-quarter','half-from-same-source'],
        expressions=['neutral','smile','listen','concern','relieved'],actions=['idle','listen','phone-use'],status='needs-design')
    (dest/'brief.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2)+'\n')
    (dest/'prompts.md').write_text('角色设计：参考已确认角色的画风，依据 brief.json 创建设计板，包含全身、半身、表情与实际需要的姿态。先查看引用图，再使用宿主图像生成工具。\n\n独立原图：引用已确认设计板，只输出同一角色完整全身、真实透明背景，不加文字/其他姿态。\n\n局部修改：只改本次指定项目；锁定脸型、发型、身体比例、未指定服装、鞋子、原始透明轮廓。另存新版本，保存提示词、输入/输出哈希与影响范围。\n\n动作：先做当前角色自己的绑定与小样；不能复用其他角色关节坐标，不能切四肢旋转拉伸。\n')
    return dict(path=str(dest),status='brief-created',generation='use host built-in image generation; no paid/cloud call made by this script')


def stage(profile,project,view='full',action='static-full'):
    path=Path(profile).resolve();d=json.loads(path.read_text());result=check(path)
    if not result['ok'] or not result['designApproved']:raise ValueError('角色素材或具体设计确认未通过：'+str(result))
    if action not in d.get('performance',{}).get('validated',[]):raise ValueError('该角色尚未验证动作 '+action+'；先补姿态/绑定和代表性样片')
    if view not in d.get('views',{}):raise ValueError('未知取景 '+view)
    p=Path(project).resolve();p=p if (p/'workbench.json').exists() else p/'project';dest=p/'assets/characters'/d['id'];dest.mkdir(parents=True,exist_ok=True)
    master=path.parent/d['assets']['master']['path'];target=dest/master.name
    if target.exists() and sha(target)!=sha(master):raise ValueError('工程已有不同角色素材，不覆盖用户版本')
    shutil.copy2(master,target);shutil.copy2(path,dest/'profile.json')
    # Keep the evidence needed by the copied profile independently readable.
    design=path.parent/d['assets']['design']['path'];shutil.copy2(design,dest/design.name)
    return dict(asset=dict(id='character-'+d['id'],path=str(target.relative_to(p))),
        node=dict(id=d['id']+'-'+view,type='image',assetId='character-'+d['id'],x=200,y=300,
                  width=320 if view=='full' else 620,height=540 if view=='full' else 550,crop=d['views'][view]['crop']),
        provenance=dict(characterId=d['id'],designSha256=d['assets']['design']['sha256'],masterSha256=sha(master),action=action),
        review='new scene integration and any natural performance still need actual review')


def main():
    a=argparse.ArgumentParser(description=__doc__);sub=a.add_subparsers(dest='command',required=True)
    b=sub.add_parser('prepare');b.add_argument('destination',type=Path);b.add_argument('--id',required=True);b.add_argument('--role',default='customer');b.add_argument('--outfit',required=True)
    b=sub.add_parser('check');b.add_argument('profile',type=Path)
    b=sub.add_parser('stage');b.add_argument('profile',type=Path);b.add_argument('course',type=Path);b.add_argument('--view',choices=['full','half'],default='full');b.add_argument('--action',default='static-full')
    args=a.parse_args()
    try:
        if args.command=='prepare':result=prepare(args.destination,args.id,args.role,args.outfit)
        elif args.command=='check':result=check(args.profile)
        else:result=stage(args.profile,args.course,args.view,args.action)
    except (ValueError,OSError) as exc:a.exit(2,str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get('ok',True) else 2


if __name__=='__main__':raise SystemExit(main())
