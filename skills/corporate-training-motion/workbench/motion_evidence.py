"""Executable object predicates and isolated final-encoded pixels. No aesthetic score."""
import copy,hashlib,json,subprocess
from pathlib import Path

OPS={'eq','approx','lt','gt','absent'}


def property_value(obj,path):
 for key in path.split('.'):
  if not key:continue
  obj=obj.get(key)if isinstance(obj,dict)else None
 return obj


def predicate(check,states):
 obj=states.get(check['objectId']);actual=property_value(obj,check.get('property',''));op=check['op'];expected=check.get('expected');passed=False
 if op=='absent':passed=obj is None
 elif op=='eq':passed=actual==expected
 elif op in ['approx','lt','gt']and type(actual)in[int,float]and type(expected)in[int,float]:
  passed=abs(actual-expected)<=check.get('tolerance',.01)if op=='approx'else actual<expected if op=='lt'else actual>expected
 return dict(check=check,actual=actual,passed=passed)


def inspect(doc,nodes):
 errors=[]
 if not doc.get('motionPolicy',{}).get('stateProofRequired'):return errors
 scenes={s['id']:s for s in doc['scenes']}
 for beat in doc.get('motionPlan',{}).get('beats',[]):
  scene=scenes.get(beat.get('sceneId'));kind=beat.get('kind','action')
  if not scene:continue
  if kind in ['observe','read','think']:
   ids=beat.get('objectIds',[])
   if not ids or any(i not in nodes or nodes[i].get('role')in ['decoration','navigation','title']for i in ids):errors.append('读图停留须绑定本段实际对象 '+beat['id'])
   if beat['startFrame']==scene['sourceStartFrame']and beat['endFrame']==scene['sourceEndFrame']and scene.get('presentation',{}).get('mode')not in ['reference','navigation','brand']:errors.append('整场observe不能代替本段演示 '+beat['id'])
   continue
  checks=beat.get('stateChecks',[]);frames=beat.get('evidenceFrames',[])
  if len(frames)!=3 or len(set(frames))!=3 or any(type(f)is not int or not scene['sourceStartFrame']<=f<scene['sourceEndFrame']for f in frames)or frames!=sorted(frames):errors.append('动作须提供起态过程结果的三个实际源帧 '+beat['id'])
  if not checks:errors.append('动作须有可执行对象状态断言 '+beat['id'])
  for q in checks:
   if q.get('sourceFrame')not in frames or q.get('objectId')not in beat.get('objectIds',[])or q.get('op')not in OPS or not isinstance(q.get('property'),str):errors.append('状态断言未绑定本动作的对象及证据帧 '+beat['id'])
   if q.get('property','').startswith(('camera','renderTransform','worldMatrix')):errors.append('镜头坐标不能代替对象状态 '+beat['id'])
 return errors


def requests(doc,first,last):
 from timeline import source_frame
 by_source={}
 for display in range(first,last):by_source.setdefault(source_frame(display,doc.get('holds',[]),doc.get('cuts',[])),display)
 result=[]
 for beat in doc.get('motionPlan',{}).get('beats',[]):
  if beat.get('kind','action')!='action':continue
  frames=beat.get('evidenceFrames',[])
  if not any(f in by_source for f in frames):continue
  # Partial exports do not invent missing before/after proof.
  if not all(f in by_source for f in frames):raise ValueError('导出范围须覆盖动作的完整验证帧 '+beat['id'])
  result.append(dict(id=beat['id'],objects=beat['objectIds'],stateChecks=beat['stateChecks'],frames=[dict(source=f,display=by_source[f],encoded=by_source[f]-first)for f in frames]))
 return result


def verify(video,requests,captures,out):
 import numpy as np
 from PIL import Image
 out=Path(out);out.mkdir(parents=True,exist_ok=True);indices=sorted({f['encoded']for r in requests for f in r['frames']})
 if not indices:return dict(status='pass',events=[],scope='no retained action events; static-reference approval remains separate')
 expression='+'.join('eq(n\\,%d)'%i for i in indices);folder=out/'encoded';folder.mkdir(exist_ok=True)
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf','select='+expression,'-fps_mode','vfr',str(folder/'%06d.png')],check=True)
 files=sorted(folder.glob('*.png'));assert len(files)==len(indices);encoded=dict(zip(indices,files));events=[];failures=[]
 for r in requests:
  phases=[];states=[];masks=[];pictures=[];checks=[]
  for i,f in enumerate(r['frames']):
   captured=captures[(r['id'],f['source'])];states.append(captured['states']);checks.extend(predicate(q,captured['states'])for q in r['stateChecks']if q['sourceFrame']==f['source'])
   base=np.asarray(Image.open(captured['base']).convert('RGB'));hidden=np.asarray(Image.open(captured['hidden']).convert('RGB'));pic=np.asarray(Image.open(encoded[f['encoded']]).convert('RGB'));mask=np.abs(base.astype('int16')-hidden.astype('int16')).max(2)>10;masks.append(mask);pictures.append(pic)
   phases.append(dict(**f,visiblePixels=int(mask.sum()),path=str(encoded[f['encoded']].relative_to(out)),sha256=hashlib.sha256(encoded[f['encoded']].read_bytes()).hexdigest()))
  union=masks[0]|masks[1]|masks[2];changed=[]
  for i in [1,2]:
   delta=np.abs(pictures[i].astype('int16')-pictures[i-1].astype('int16'));changed.append(int((delta.max(2)[union]>12).sum()))
  def rendered_state(value):
   if isinstance(value,dict):return{k:rendered_state(v)for k,v in value.items()if k not in ['gazeTarget','scope','identity','sourceSize','role','visibility']}
   return value
  own=[{k:rendered_state(states[i].get(k))for k in r['objects']}for i in range(3)];state_changed=len({json.dumps(v,sort_keys=True)for v in own})>1
  passed=bool(checks)and all(q['passed']for q in checks)and state_changed and union.any()and max(changed,default=0)>12
  events.append(dict(id=r['id'],status='pass'if passed else'fail',checks=checks,objectStateChanged=state_changed,encodedTargetChangedPixels=changed,phases=phases))
  if not passed:failures.append('对象状态或实际编码像素未证明该动作 '+r['id'])
 result=dict(schema='course-object-state-proof/1',status='pass'if not failures else'fail',events=events,failures=failures,scope='authored state predicates and isolated current encoded object pixels; semantic fit, craft and user acceptance separate',userFinalAcceptance=False);(out/'proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
