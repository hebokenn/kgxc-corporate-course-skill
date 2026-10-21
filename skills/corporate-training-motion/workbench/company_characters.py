"""Stage complete company-role bindings, including required uniform marks."""
from pathlib import Path
import hashlib,shutil

ROLES={
    'M1':dict(file='M1-repaired.png',role='store_manager',mark='KG'),
    'S01':dict(file='blue-cast.png',role='store_staff',mark='KG'),
    'S02':dict(file='blue-cast.png',role='store_staff',mark='KG'),
    'COACH':dict(file='MyCoach-reference-2D.png',role='coach',mark='MyCoach'),
}

UNBRANDED_MASTERS={
    '3097490102ce597f146450018988c70f014804e69919cde874f9ae4a6dce8b0a',
    '26be92c31b94be2bfd8f37a4fb456f35c677895e244aa8a4cb04fbf1949827e5',
    'ad2f1af34b4938f39f0609ff9f6341e08f4975285bc8c34e3ca9ec58867be3e3',
    'fc80229302a5de57c9aeb394d56307163ce8374c74a7479d44db3e31bffd79fa',
}
ORIGINAL_KG='fd088e5b6b5d8b35d4a73ed0ada69afbc6a56aecd9e483123add67a4257e73a9'


def validate_uniforms(doc,project):
    if not doc.get('characterPolicy',{}).get('required'):return
    from authoring import walk
    p=Path(project);assets={a['id']:hashlib.sha256((p/a['path']).read_bytes()).hexdigest() for a in doc['assets']};nodes={n['id']:n for n in walk(doc.get('sceneGraph',{}).get('nodes',[]))};parents={}
    def register(items,parent=None):
        for n in items:parents[n['id']]=parent;register(n.get('children',[]),n['id'])
    register(doc.get('sceneGraph',{}).get('nodes',[]))
    for n in nodes.values():
        if n.get('type')!='image' or assets.get(n.get('assetId')) not in UNBRANDED_MASTERS:continue
        if any(e.get('type')=='presenter-gesture' and assets.get(e.get('kgAsset'))==ORIGINAL_KG for e in n.get('effects',[])):continue
        mark=nodes.get(n.get('uniformMarkNodeId'));a=n.get('startFrame',0);z=n.get('endFrame',doc['sourceDurationFrames'])
        if not mark or mark.get('type')!='image' or assets.get(mark.get('assetId'))!=ORIGINAL_KG or parents.get(mark['id'])!=parents[n['id']] or mark.get('startFrame',0)>a or mark.get('endFrame',doc['sourceDurationFrames'])<z:
            raise ValueError('已知门店原图缺少随角色显示的原版 KG 胸标：'+n['id']+'；使用 stage-company-character 与 actor，不能直接裁切无标原图')


def stage_company(identity,project,skill_root):
    if identity not in ROLES:raise ValueError('门店角色身份无效')
    p=Path(project);p=p if (p/'workbench.json').exists() else p/'project'
    if not (p/'workbench.json').is_file():raise ValueError('先建立实际课程工作台')
    base=Path(skill_root)/'assets/profiles/kgxc';role=ROLES[identity];assets=[];data=dict(identity=identity,characterRole=role['role'])
    for kind,name in [('headAsset',role['file'])]+([('logoAsset','kg-original.png')] if role['mark']=='KG' else []):
        src=base/name;digest=hashlib.sha256(src.read_bytes()).hexdigest();dest=p/'assets/company-characters'/(digest[:10]+'-'+name);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise ValueError('已有公司角色素材被编辑，保留并使用新版本')
        if not dest.exists():shutil.copy2(src,dest)
        aid='company-'+identity+'-'+kind;assets.append(dict(id=aid,path=str(dest.relative_to(p)),label=role['role']+' '+kind));data[kind]=aid
    return dict(assets=assets,data=data,role=role['role'],mark=role['mark'])
