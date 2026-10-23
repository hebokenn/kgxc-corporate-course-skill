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
if __name__=='__main__':unittest.main()
