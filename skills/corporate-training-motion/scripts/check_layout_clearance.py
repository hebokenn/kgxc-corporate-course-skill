#!/usr/bin/env python3
"""Conservative geometry candidates for every visible glyph vs glyph/stroke/thin fill.
Does not infer beauty or solve arbitrary alpha/rounded-mask occlusion. Review candidates.
"""
import json,argparse,hashlib
from pathlib import Path
from check_actor_clearance import check_frame,segment_rect,intersects

def inspect(frame):
 findings,contacts=check_frame(frame);es=frame['elements'];texts=[e for e in es if e['kind']=='text']
 strokes=[e for e in es if e['kind'] in ['line','decoration']]
 for i,a in enumerate(texts):
  for b in texts[i+1:]:
   if intersects(a['bounds'],b['bounds']):findings.append({'kind':'text_text','a':a['id'],'b':b['id'],'detail':[a.get('text'),b.get('text')]})
  for b in strokes:
   pad=3*a.get('scene_scale',1)
   hit=segment_rect(b['points'],a['bounds'],b['width']/2+pad) if b['kind']=='line' else intersects(b['bounds'],a['bounds'],pad)
   if hit:findings.append({'kind':'text_stroke' if b['kind']=='line' else 'text_thin_fill','a':a['id'],'b':b['id'],'detail':a.get('text')})
  region=a.get('allowed_region')
  if region:
   x,y,X,Y=a['bounds'];l,t,r,b=region
   if x<l or y<t or X>r or Y>b:findings.append({'kind':'component_region','a':a['id'],'b':a.get('role','region'),'detail':a['bounds']})
 return findings,contacts

def audit(path):
 issues={};n=0;relations={'text_text':0,'text_stroke':0,'text_thin_fill':0}
 for row in Path(path).open():
  frame=json.loads(row);n+=1;es=frame['elements'];nt=sum(e['kind']=='text' for e in es);relations['text_text']+=nt*(nt-1)//2;relations['text_stroke']+=nt*sum(e['kind']=='line' for e in es);relations['text_thin_fill']+=nt*sum(e['kind']=='decoration' for e in es)
  for issue in inspect(frame)[0]:
   key=(issue['kind'],issue['a'],issue['b']);r=issues.setdefault(key,dict(issue,first=frame['time'],last=frame['time'],frames=0));r['last']=frame['time'];r['frames']+=1
 assert n,'No snapshots cannot pass'
 return {'ok':not issues,'snapshots':n,'tested_relation_counts':relations,'issues':list(issues.values()),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'limits':'conservative transformed glyph/segment/thin-fill candidates, all paint orders; no blanket layer exclusion. Not every raster/alpha/mask shape, not visual approval.'}

def self_test():
 text={'kind':'text','id':'label','text':'营业与班次','bounds':[130,922,305,955],'order':2}
 bar={'kind':'decoration','id':'actual-nav-bar','bounds':[130,940,480,947],'order':1}
 r={'time':10,'elements':[text,bar]}
 assert any(x['kind']=='text_thin_fill' for x in inspect(r)[0])
 r['elements'][1]={'kind':'line','id':'arrow','points':[100,940,500,940],'width':4,'order':0}
 assert any(x['kind']=='text_stroke' for x in inspect(r)[0])
 r['elements'][1]['points']=[100,870,500,870];assert not inspect(r)[0]
 r['elements'].append(dict(text,id='second',bounds=[200,930,350,963]));assert any(x['kind']=='text_text' for x in inspect(r)[0])
 hits=[]
 for y in [870,940,990]:
  hits.append(bool(inspect({'time':y,'elements':[text,{'kind':'line','id':'moving-line','points':[100,y,500,y],'width':4,'order':0}]})[0]))
 assert hits==[False,True,False],hits
 return {'ok':True,'checks':['thin filled nav through glyph detected','stroke behind glyph still detected','clear layout accepted','text/text detected','movement midpoint crossing detected despite clear endpoints'],'note':'actual encoded regression fixture is checked separately'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshots',nargs='?');p.add_argument('--out',type=Path);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 r=self_test() if a.self_test else audit(a.snapshots)
 if a.out:a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(json.dumps({'ok':r['ok'],'issues':len(r.get('issues',[])),'snapshots':r.get('snapshots')},ensure_ascii=False));raise SystemExit(not r['ok'])
