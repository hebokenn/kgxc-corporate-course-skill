#!/usr/bin/env python3
"""Check exported screen-space actor/name groups and strokes; not pixel-perfect occlusion QA.
JSONL: one frame {time,elements,contacts,chapter,config}. Bounds=[left,top,right,bottom].
Contacts must name exact actor/token IDs and a bounded grip zone; heads/names never exempt.
"""
import argparse,json,math
from pathlib import Path

def intersects(a,b,pad=0):return a[0]<b[2]+pad and a[2]>b[0]-pad and a[1]<b[3]+pad and a[3]>b[1]-pad

def gap(a,b):return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))

def union(a,b):return [min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]

def segment_rect(points,rect,pad=0):
 x,y,X,Y=points;lo,hi=0.,1.;r=[rect[0]-pad,rect[1]-pad,rect[2]+pad,rect[3]+pad]
 for start,delta,mn,mx in [(x,X-x,r[0],r[2]),(y,Y-y,r[1],r[3])]:
  if abs(delta)<1e-10:
   if start<mn or start>mx:return False
  else:
   a,b=sorted(((mn-start)/delta,(mx-start)/delta));lo=max(lo,a);hi=min(hi,b)
   if lo>hi:return False
 return True

def check_frame(frame):
 es=frame['elements'];cfg=frame.get('config',{});u=cfg.get('unit',12);findings=[];allowed=[]
 actors=[e for e in es if e['kind']=='actor'];texts=[e for e in es if e['kind']=='text'];lines=[e for e in es if e['kind']=='line'];keys=[e for e in es if e['kind']=='key'];images=[e for e in es if e['kind']=='image'];contacts=frame.get('contacts',[])
 def add(kind,a,b,detail):findings.append({'kind':kind,'a':a['id'],'b':b['id'],'detail':detail})
 groups={a['id']:dict(a,group_bounds=a['bounds'][:]) for a in actors}
 for t in texts:
  if t.get('owner') in groups:groups[t['owner']]['group_bounds']=union(groups[t['owner']]['group_bounds'],t['bounds'])
 for a in actors:
  scale=a.get('scene_scale',1);label_gap=cfg.get('nameGap',u)*scale
  for t in texts:
   if t.get('owner')==a['id']:
    if gap(a['bounds'],t['bounds'])<label_gap-.05:add('own_name_clearance',a,t,'actor/name gap below scaled unit')
   elif intersects(a['bounds'],t['bounds'],label_gap-.05):add('text_actor_clearance',t,a,'foreign text approaches or overlaps actor')
  for line in lines:
   # Later strokes can occlude actors. Calendar separators must exclude the whole group regardless of layer order.
   r=groups[a['id']]['group_bounds'] if line.get('tag')=='calendar-divider' else a['bounds']
   if line.get('tag')=='calendar-divider' or line['order']>a['order']:
    if segment_rect(line['points'],r,line['width']/2+u*scale-.05):
     if line.get('tag')=='floor' and segment_rect(line['points'],a['foot_zone'],line['width']/2):allowed.append({'a':a['id'],'b':line['id'],'reason':'feet on declared floor','zone':a['foot_zone']})
     else:add('separator_actor' if line.get('tag')=='calendar-divider' else 'stroke_actor',line,a,'stroke enters protected actor/name region')
  for k in keys:
   if intersects(k['bounds'],a['head']):add('key_head',k,a,'head is never a permitted contact zone');continue
   for part in k.get('parts') or [{'bounds':k['bounds']}]:
    kb=part['bounds']
    if not intersects(kb,a['bounds']):continue
    intersection=[max(kb[0],a['bounds'][0]),max(kb[1],a['bounds'][1]),min(kb[2],a['bounds'][2]),min(kb[3],a['bounds'][3])]
    valid=next((c for c in contacts if c['actor']==a['id'] and c['token']==k['id'] and c.get('reason') and c.get('time_range',[float('inf'),-float('inf')])[0]<=frame['time']<=c.get('time_range',[float('inf'),-float('inf')])[1] and c['zone'][0]<=intersection[0] and c['zone'][1]<=intersection[1] and c['zone'][2]>=intersection[2] and c['zone'][3]>=intersection[3]),None)
    if valid:
     if valid not in allowed:allowed.append(valid)
    else:add('undeclared_key_contact',k,a,'actual token part enters actor outside bounded grip exception')
   for t in texts:
    if t.get('owner')==a['id'] and intersects(k['bounds'],t['bounds']):add('key_name',k,t,'names are never permitted contact zones')
  for im in images:
   if intersects(a['head'],im['bounds'],u/2*scale):add('image_head_clearance',im,a,'logo/image near face')
 chapter=frame.get('chapter',{})
 if chapter.get('id') not in {None,'cover'} and not any(t.get('text')==chapter.get('title') for t in texts):findings.append({'kind':'chapter_not_drawn','a':chapter.get('id'),'b':'rendered-text','detail':'declared title absent from actual draw calls'})
 for i,a in enumerate(actors):
  for b in actors[i+1:]:
   compact=a.get('variant')=='compact' and b.get('variant')=='compact';required=(cfg.get('compactGap',.75*u) if compact else cfg.get('groupGap',2*u))*min(a.get('scene_scale',1),b.get('scene_scale',1))
   if gap(groups[a['id']]['group_bounds'],groups[b['id']]['group_bounds'])<required-.05:add('actor_group_clearance',a,b,f'whole-group gap below {required:.2f}px')
 for t in texts:
  if not t.get('owner'):continue
  for line in lines:
   if segment_rect(line['points'],t['bounds'],line['width']/2+u/2*t.get('scene_scale',1)-.05):add('stroke_name',line,t,'stroke enters name padding regardless of paint order')
 return findings,allowed

def check_file(path):
 issues={};frames=0;contacts=0;elements=0;chapters={};config=None
 with Path(path).open() as f:
  for row in f:
   a=json.loads(row);frames+=1;elements+=len(a['elements']);config=a.get('config');c=a.get('chapter');
   if c:chapters.setdefault(c['id'],set()).add(c['title'])
   found,ok=check_frame(a);contacts+=len(ok)
   for item in found:
    key=(item['kind'],item['a'],item['b']);r=issues.setdefault(key,dict(item,first=a['time'],last=a['time'],frames=0));r['last']=a['time'];r['frames']+=1
 if not frames or not elements:raise ValueError('Empty geometry cannot pass')
 return {'snapshot_sha256':__import__('hashlib').sha256(Path(path).read_bytes()).hexdigest(),'ok':not issues,'frames':frames,'elements':elements,'issues':list(issues.values()),'bounded_contact_frame_count':contacts,'config':config,'chapters':{k:sorted(v) for k,v in chapters.items()},'limits':'transformed primitive/glyph bounds and stroke geometry; conservative candidates, not exhaustive raster/alpha occlusion or aesthetic certification'}

def self_test():
 import copy
 actor={'kind':'actor','id':'employee','bounds':[100,100,200,350],'head':[120,100,180,160],'foot_zone':[110,330,190,355],'order':1,'scene_scale':1}
 key={'kind':'key','id':'duty-key','bounds':[90,250,150,290],'order':2}
 contact={'actor':'employee','token':'duty-key','zone':[80,230,220,310],'reason':'actual palm/key contact','time_range':[9,11]}
 frame={'time':10,'elements':[actor,key],'contacts':[contact]}
 assert not check_frame(frame)[0] and check_frame(frame)[1]
 face=copy.deepcopy(frame);face['elements'][1]['bounds']=[130,110,150,140];face['contacts'][0]['zone']=[0,0,500,500]
 assert any(x['kind']=='key_head' for x in check_frame(face)[0])
 name=copy.deepcopy(frame);name['elements'].append({'kind':'text','id':'name','owner':'employee','bounds':[115,365,185,395]});name['elements'][1]['bounds']=[120,370,190,390];name['contacts'][0]['zone']=[0,0,500,500]
 assert any(x['kind']=='key_name' for x in check_frame(name)[0])
 outside=copy.deepcopy(frame);outside['time']=12
 assert any(x['kind']=='undeclared_key_contact' for x in check_frame(outside)[0])
 pair=copy.deepcopy(frame);pair['contacts'][0]['actor']='another-person'
 assert any(x['kind']=='undeclared_key_contact' for x in check_frame(pair)[0])
 stroke={'time':10,'elements':[actor,{'kind':'line','id':'divider','points':[0,130,300,130],'width':2,'order':3,'tag':'calendar-divider'}]}
 assert any(x['kind']=='separator_actor' for x in check_frame(stroke)[0])
 assert not segment_rect([140,0,0,-140],[0,0,100,100],13)
 return {'ok':True,'checks':['bounded hand/key accepted','head never exempt','name never exempt','time range enforced','exact pair enforced','divider crossing detected','segment geometry avoids diagonal AABB false positive']}

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('snapshots',type=Path,nargs='?');ap.add_argument('--out',type=Path);ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
 if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));raise SystemExit(0)
 if args.snapshots is None:ap.error('snapshots or --self-test required')
 report=check_file(args.snapshots);s=json.dumps(report,ensure_ascii=False,indent=2)
 if args.out:args.out.write_text(s)
 print(json.dumps({'ok':report['ok'],'frames':report['frames'],'issue_count':len(report['issues'])},ensure_ascii=False));raise SystemExit(not report['ok'])
