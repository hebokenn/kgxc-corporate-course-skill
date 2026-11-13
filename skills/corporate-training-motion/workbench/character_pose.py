"""Stage contact poses without confusing identity approval with motion approval."""
from pathlib import Path
import hashlib,json,shutil


def stage_pose(identity,project,skill_root):
    if identity!='C01':raise ValueError('该角色还没有已制作的接触姿态，不能复用另一人的手')
    p=Path(project);p=p if (p/'workbench.json').exists() else p/'project'
    if not (p/'workbench.json').is_file():raise ValueError('先建立实际课程工作台')
    base=Path(skill_root)/'assets/characters/kgxc-customers-v1/poses';source=base/'C01-phone-use-v2.json';pose=json.loads(source.read_text())
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    folder=p/'assets/contact-poses'/('C01-'+sha(source)[:10]);folder.mkdir(parents=True,exist_ok=True);assets=[]
    for key in ['master','foreground']:
        item=pose[key];src=base/item['path'];dest=folder/item['path']
        if sha(src)!=item['sha256']:raise ValueError('接触姿态来源已变化')
        if dest.exists() and sha(dest)!=item['sha256']:raise ValueError('已有姿态素材被编辑；保留改动并使用新版本')
        if not dest.exists():shutil.copy2(src,dest)
        item['assetId']='pose-C01-phone-use-v2-'+key;assets.append(dict(id=item['assetId'],path=str(dest.relative_to(p)),label='C01 持机姿态修订候选 '+key))
    return dict(assets=assets,pose=pose)
