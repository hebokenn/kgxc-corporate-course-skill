"""Meaningful extension, Apple-scope and invalid-motion regression checks."""
import copy,json,sys,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'));sys.path.insert(0,str(ROOT/'scripts'))
from retail_assets import catalog,prop,APPLE_PRODUCTS
from content_assets import phone
from render_routes import effect_errors
from visual_styles import registry,expand,register
from asset_library import register as add_asset,stage
class LibraryTests(unittest.TestCase):
 def setUp(self):self.scene=dict(id='S',sourceStartFrame=0,sourceEndFrame=90)
 def test_apple_families_have_distinct_geometry_and_reject_other_brands(self):
  for key,(alias,ref,_) in APPLE_PRODUCTS.items():
   n,d=prop(dict(id='P',data=dict(object=alias)),self.scene);self.assertTrue(n['children']);self.assertEqual(d['productFamily'],alias);self.assertTrue(ref.startswith('https://www.apple.com.cn/'))
  with self.assertRaises(ValueError):prop(dict(id='P',data=dict(object='airpods',brand='Sony')),self.scene)
  for model in ['slab','compact','foldable','pixel-phone']:
   with self.assertRaises(ValueError):phone(dict(id='P',data=dict(model=model)),self.scene)
 def test_front_film_has_no_rear_camera_cutout(self):
  n,_=prop(dict(id='film',data=dict(object='iphone-screen-film')),self.scene);self.assertNotIn('film-cutout',{x['id'] for x in n['children']})
  n,_=prop(dict(id='case',data=dict(object='iphone-18-pro-case')),self.scene);self.assertIn('case-cutout',{x['id'] for x in n['children']})
 def test_font_and_outline_are_compiled_into_actual_nodes(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,COURSE_CONFIG_DIR=d):
   style=copy.deepcopy(registry()['pen-whiteboard']);style.update(id='own-whiteboard',font='CourseSerif',outline=12);file=Path(d)/'own.json';file.write_text(json.dumps(style));register(file)
   out=expand(dict(scenes=[self.scene],sceneGraph=dict(styleScenes=[dict(id='own',style=style['id'],sceneId='S',data=dict(title='实际课程',labels=['步骤甲','步骤乙']))])))
   from authoring import walk
   nodes=list(walk(out['sceneGraph']['nodes']));self.assertTrue(any(x.get('fontFamily')=='CourseSerif' for x in nodes));self.assertTrue(any(x.get('lineWidth',0)>=12 for x in nodes))
 def test_distinct_user_ids_do_not_collide_or_overwrite(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,COURSE_CONFIG_DIR=d+'/config'):
   root=Path(d);course=root/'course';(course/'project').mkdir(parents=True);file=root/'custom.svg';file.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"><rect width="50" height="50"/></svg>')
   for k in ['custom.prop','custom-prop']:add_asset(file,k,k)
   a=stage(course,'custom.prop');b=stage(course,'custom-prop');self.assertNotEqual(a['assets'][0]['id'],b['assets'][0]['id'])
   with self.assertRaises(ValueError):add_asset(file,'wrong-brand','wrong',product=dict(brand='Samsung'))
 def test_bad_ratio_and_fake_matches_rejected(self):
  for typ,params in [('ratio-normalize',dict(values=[0,0])),('rank-reorder',dict(order=[1,1])),('scatter-converge',dict(targets=[[1,2]])),('search-match',dict(query='不存在'))]:
   n=dict(id='n',type='text' if typ=='search-match' else 'group',text='真实文字',children=[dict(id='a'),dict(id='b')],effects=[dict(type=typ,startFrame=0,endFrame=30,**params)])
   self.assertTrue(effect_errors(dict(sourceDurationFrames=90,sceneGraph=dict(nodes=[n]))))
 def test_cluster_uses_actual_object_dimensions_and_content_bounds(self):
  node=dict(id='tasks',type='group',width=1400,height=315,children=[dict(id='task-'+str(i),type='group',width=205,height=100) for i in range(8)])
  good=dict(type='cluster-pack',startFrame=0,endFrame=30,centers=[[20,20],[770,20]],columns=2,gapX=300,gapY=140)
  for effect,expected in [(good,False),({**good,'gapX':100},True),({**good,'centers':[[20,-100],[1400,20]]},True)]:
   node['effects']=[effect];errors=effect_errors(dict(sourceDurationFrames=90,sceneGraph=dict(nodes=[node])));self.assertEqual(bool(errors),expected,errors)
 def test_presenter_never_silently_becomes_generic_customer(self):
  from visual_styles import build
  with self.assertRaisesRegex(ValueError,'stage-style-assets'):
   build(dict(id='host',data={}),self.scene,registry()['retail-toon'])
 def test_store_bases_touch_the_drawn_tabletops(self):
  from retail_assets import store
  n,_=store(dict(id='shop',data=dict(view='interior')),self.scene);objects={x['id']:x for x in n['children']};count=0
  for item in objects.values():
   binding=item.get('supportBinding')
   if not binding:continue
   table=objects[binding['objectId']];base=next(v for v in item['children'] if v['id'].endswith('-base'))
   # Derive the actual visible stand base from geometry, independently of its
   # declared attachment metadata, and compare its world contact to the table.
   bx=base['x']+base['width']/2;by=base['y']+base['height'];px,py=binding['point']
   self.assertAlmostEqual(item['x']+bx*item['scaleX'],table['x']+px*table['scaleX'])
   self.assertAlmostEqual(item['y']+by*item['scaleY'],table['y']+py*table['scaleY'])
   poly=table['supportSurface'];signs=[(poly[(j+1)%4][0]-q[0])*(py-q[1])-(poly[(j+1)%4][1]-q[1])*(px-q[0]) for j,q in enumerate(poly)];self.assertTrue(all(x>=0 for x in signs) or all(x<=0 for x in signs));count+=1
  self.assertEqual(count,12)
 def test_public_cli_stages_the_approved_identity_and_material_assets(self):
  import subprocess
  cli=ROOT/'scripts/course_tools.py'
  rows=json.loads(subprocess.check_output([sys.executable,str(cli),'surface-catalog']));self.assertEqual(len(rows),24)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'project').mkdir();out=root/'stage.json'
   subprocess.run([sys.executable,str(cli),'stage-style-assets',str(root),'--style','soft-volume','--out',str(out)],check=True,capture_output=True)
   staged=json.loads(out.read_text());self.assertEqual(set(staged['data']['roleAssets']),{'M1','S01','S02','COACH','C01','C02','C03'});self.assertIn('heroAsset',staged['data'])
   for asset in staged['assets']:self.assertTrue((root/'project'/asset['path']).is_file())
 def test_photo_annotation_uses_contained_image_coordinates_and_object_order(self):
  from visual_styles import build
  style=registry()['photo-annotation']
  with self.assertRaisesRegex(ValueError,'尺寸及逐物件'):
   build(dict(id='photo',data=dict(photoAsset='photo')),self.scene,style)
  data=dict(photoAsset='photo',photoSize=[1000,1000],annotations=[dict(label='桌面',point=[.2,.8]),dict(label='门头',point=[.5,.1])])
  node=build(dict(id='photo',data=data),self.scene,style)
  labels=[x['text'] for x in node['children'] if x['id'].startswith('photo-label')]
  self.assertEqual(labels,['门头','桌面'])
  arrows=[x for x in node['children'] if x['id'].startswith('photo-callout')]
  # A square source is centred inside the 850x490 image box; its x origin
  # is 270, rather than the frame's x=90. Keep the named target with its point.
  self.assertEqual(arrows[0]['points'][-1],[515,269])
  self.assertEqual(arrows[1]['points'][-1],[368,612])
  data['annotations'][0]['point']=[1.2,.8]
  with self.assertRaisesRegex(ValueError,'当前图像范围'):
   build(dict(id='photo',data=data),self.scene,style)
if __name__=='__main__':unittest.main()
