"""Registered, editable source-texture performance; unknown art needs its own profile."""
import copy,hashlib,json,math,shutil
from pathlib import Path

CHANNELS={'nod':(0,1),'head':(-6,6),'left':(-14,14),'right':(-14,14),'leftFore':(-80,80),'fore':(-80,80),'leftHand':(-15,15),'hand':(-15,15),'gazeX':(-1,1),'gazeY':(-1,1),'concern':(0,1),'relief':(0,1),'blink':(0,1)}


def profiles():return json.loads((Path(__file__).with_name('performance-profiles.json')).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(v):return type(v)in[int,float]and math.isfinite(v)


def errors(node,doc):
 d=node.get('performance',{});p=d.get('profile',{});out=[];a=node.get('startFrame',0);z=node.get('endFrame',doc['sourceDurationFrames'])
 if node.get('type')!='image':out.append('人物演出须绑定原图 image '+node['id'])
 if not p.get('identity')or not isinstance(p.get('sourceSha256'),str)or len(p.get('sourceSha256',''))!=64:out.append('人物缺少原图哈希与本角色标定 '+node['id'])
 size=p.get('size',[])
 if len(size)!=2 or not all(finite(v)and v>0 for v in size):out.append('人物标定尺寸无效 '+node['id'])
 for key in ['neck','head','body','left','right','face']:
  if not p.get(key):out.append('人物自己的标定缺项 '+key+' '+node['id'])
 keys=d.get('keys',[]);frames=[k.get('frame')for k in keys]
 if not keys or frames[0]!=a or any(type(f)is not int or not a<=f<z for f in frames)or frames!=sorted(set(frames)):out.append('人物关键帧须从素材起帧开始并在素材内递增 '+node['id'])
 for key in keys:
  for name,value in key.get('values',{}).items():
   if name not in CHANNELS or not finite(value)or not CHANNELS[name][0]<=value<=CHANNELS[name][1]:out.append('超出已验证的人物通道/幅度 '+name+' '+node['id'])
   if name in ['right','fore','hand']and 'right'not in p.get('supportedAnimatedSides',['left','right'])and value!=0:out.append('该角色此侧手臂未验证 '+node['id'])
 for blink in d.get('blinks',[]):
  if len(blink)!=3 or any(type(f)is not int or not a<=f<z for f in blink)or not blink[0]<blink[1]<blink[2]:out.append('眨眼须有本人物独立的开始闭合回开帧 '+node['id'])
 if not d.get('targets'):out.append('人物视线须说明所看的具体对象 '+node['id'])
 target_frames=[v.get('frame')for v in d.get('targets',[])]
 if any(type(v)is not int or not a<=v<z for v in target_frames)or target_frames!=sorted(set(target_frames)):out.append('视线目标帧无效 '+node['id'])
 ids=set()
 def walk(items):
  for n in items:ids.add(n['id']);walk(n.get('children',[]))
 walk(doc.get('sceneGraph',{}).get('nodes',[]))
 for target in d.get('targets',[]):
  if target.get('id')not in ids:out.append('视线目标未绑定实际对象 '+str(target.get('id')))
 return out


def validate_assets(doc,project):
 assets={a['id']:a for a in doc['assets']}
 def walk(items):
  for n in items:
   if n.get('performance'):
    p=n['performance']['profile'];src=Path(project)/assets[n['assetId']]['path']
    if sha(src)!=p['sourceSha256']:raise ValueError('人物原图已换，须重新核对本角色标定：'+n['id'])
   walk(n.get('children',[]))
 walk(doc.get('sceneGraph',{}).get('nodes',[]))


def compile_actor(recipe,scene):
 from content_assets import Drawing
 b=Drawing(recipe,scene);data=recipe['data'];spec=copy.deepcopy(data['performance']);profile=spec.get('profile',{})
 if profile.get('identity')!=data.get('identity'):raise ValueError('不能套用其他角色的人物标定')
 w,h=profile['size'];scale=recipe.get('scale',1)*810/h
 image=b.node('image','performance',assetId=data['headAsset'],x=0,y=0,width=w,height=h,performance=spec);items=[image]
 if data['identity']in['M1','S01','S02']:
  if not data.get('logoAsset'):raise ValueError('门店人物必须绑定原版KG')
  mark=profile.get('uniformMark')
  if not mark:raise ValueError('该人物尚未标定胸标')
  image['uniformMarkNodeId']=recipe['id']+'-uniform-KG';items.append(b.node('image','uniform-KG',assetId=data['logoAsset'],x=mark[0],y=mark[1],width=mark[2],height=mark[2]*251/321))
 root=b.group('root',recipe.get('x',0),recipe.get('y',0),items,w,h,scaleX=scale,scaleY=scale)
 if data.get('clip'):root['clip']=data['clip']
 return root,dict(kind='actor',identity=data['identity'],sourceSha256=profile['sourceSha256'],representation='registered source-texture facial and joint performance',naturalWalkReady=False,phonemeLipSyncReady=False,review='actual current scene review required; no inferred user acceptance')


def stage(identity,project,skill_root):
 p=Path(project);p=p if(p/'workbench.json').is_file()else p/'project';root=Path(skill_root);known=profiles()
 if identity not in known:raise ValueError('尚未为此角色标定演出；须制作其自己的 profile')
 if not(p/'workbench.json').is_file():raise ValueError('先建立实际工作台')
 profile=known[identity];assets=[]
 if identity=='C01':
  src=root/'assets/characters/kgxc-customers-v1/C01-full-v1.png';dst=p/'assets/character-performance'/(sha(src)[:12]+'-'+src.name);dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists()and sha(dst)!=sha(src):raise ValueError('保留已编辑人物素材，使用新目录')
  if not dst.exists():shutil.copy2(src,dst)
  aid='performance-C01-master';assets=[dict(id=aid,path=str(dst.relative_to(p)),label='C01 registered original')];data=dict(identity=identity,headAsset=aid)
 else:
  from company_characters import stage_company
  company=stage_company(identity,p,root);assets=company['assets'];data=company['data'];src=p/next(a['path']for a in assets if a['id']==data['headAsset']);profile['uniformMark']=[440,320,48]
 profile['sourceSha256']=sha(src)
 data['performance']=dict(profile=profile,keys=[],blinks=[],targets=[])
 return dict(assets=assets,data=data,scope='add scene-specific keys and actual target IDs before compiling; same managed preview/export runtime')
