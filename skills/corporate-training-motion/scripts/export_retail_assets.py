#!/usr/bin/env python3
"""Export the editable retail factories to reusable transparent SVG and PNG assets."""
import argparse,html,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from retail_assets import PROPS,ROLES,POSES,MOODS,APPLE_PRODUCTS,prop,customer,store

def svg(node):
 def esc(v):return html.escape(str(v),quote=True)
 defs=[]
 def paint(v):
  if v is None:return 'none'
  if isinstance(v,dict):
   identifier='g'+hashlib.sha256((node['id']+json.dumps(v,sort_keys=True)).encode()).hexdigest()[:14]
   stops=''.join(f'<stop offset="{x*100}%" stop-color="{col}"/>' for x,col in v['stops'])
   if v.get('type')=='linear-gradient':
    x,y=v['from'];z,w=v['to'];defs.append(f'<linearGradient id="{identifier}" gradientUnits="userSpaceOnUse" x1="{x}" y1="{y}" x2="{z}" y2="{w}">{stops}</linearGradient>')
   else:
    x,y,r=v['outer'];defs.append(f'<radialGradient id="{identifier}" gradientUnits="userSpaceOnUse" cx="{x}" cy="{y}" r="{r}">{stops}</radialGradient>')
   return 'url(#'+identifier+')'
  return v
 t=node['type'];transform=f'translate({node.get("x",0)} {node.get("y",0)}) rotate({node.get("rotation",0)}) scale({node.get("scaleX",1)} {node.get("scaleY",1)})';style=f'fill="{paint(node.get("fill"))}" stroke="{paint(node.get("stroke"))}" stroke-width="{node.get("lineWidth",3)}" stroke-linecap="round" stroke-linejoin="round"';tag=''
 if t=='group':tag=''.join(svg(n) for n in node.get('children',[]))
 elif t=='rect':tag=f'<rect width="{node["width"]}" height="{node["height"]}" rx="{node.get("radius",0)}" {style}/>'
 elif t=='ellipse':tag=f'<ellipse rx="{node["width"]/2}" ry="{node["height"]/2}" {style}/>'
 elif t=='path':tag=f'<path d="{esc(node["path"])}" {style}/>'
 elif t=='text':tag=f'<text dominant-baseline="text-before-edge" font-family="sans-serif" font-size="{node.get("fontSize",18)}" text-anchor="'+{'left':'start','center':'middle','right':'end'}.get(node.get('align'),'start')+f'" fill="{paint(node.get("fill"))}">{esc(node["text"])}</text>'
 return ('<defs>'+''.join(defs)+'</defs>' if defs else '')+f'<g transform="{transform}" opacity="{node.get("opacity",1)}">{tag}</g>'

def export(out,png=False):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);scene=dict(id='asset',sourceStartFrame=0,sourceEndFrame=90);recipes=[]
 for k in PROPS:recipes.append((APPLE_PRODUCTS[k][0] if k in APPLE_PRODUCTS else k,'retail-prop',dict(object=k),prop))
 for identity in ROLES:
  for pose in POSES:
   for mood in MOODS:recipes.append((identity+'-'+pose+'-'+mood,'retail-person',dict(identity=identity,pose=pose,mood=mood),customer))
 for view in ['front','interior','isometric']:recipes.append(('store-'+view,'store-scene',dict(view=view),store))
 rows=[]
 for ident,kind,data,factory in recipes:
  r=dict(id=ident,kind=kind,sceneId='asset',data=data);node,desc=factory(r,scene);w=node['width'];h=node['height'];node['x']=20;node['y']=20;file=out/(ident+'.svg');raw=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w+40}" height="{h+40}" viewBox="0 0 {w+40} {h+40}">'+svg(node)+'</svg>'
  if file.exists() and file.read_text()!=raw:raise ValueError('保留已有不同版本，输出到新目录 '+str(file))
  file.write_text(raw);rows.append(dict(id=ident,kind=kind,svg=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),recipe=r,description=desc))
 if png:
  from runtime import activate,browser_options
  activate()
  from playwright.sync_api import sync_playwright
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,**browser_options());page=browser.new_page()
   for row in rows:
    page.goto((out/row['svg']).resolve().as_uri());page.locator('svg').screenshot(path=str(out/(row['id']+'.png')),omit_background=True);row['png']=row['id']+'.png'
   browser.close()
 (out/'catalog.json').write_text(json.dumps(dict(schema='course-retail-svg/1',count=len(rows),source='editable factories',assets=rows),ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(count=len(rows),png=png)))

if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path,required=True);a.add_argument('--png',action='store_true');x=a.parse_args();export(x.out,x.png)
