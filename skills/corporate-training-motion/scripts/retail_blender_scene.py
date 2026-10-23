"""Blender-owned side of render_blender_asset.py. Use the launcher, not plain Python."""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
cfg=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text());out=Path(cfg['out']);bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=cfg['model']);meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes:raise ValueError('模型没有网格')
coords=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box];lo=Vector([min(v[i] for v in coords) for i in range(3)]);hi=Vector([max(v[i] for v in coords) for i in range(3)]);center=(lo+hi)/2;span=max(hi-lo);span=max(span,.1)
bpy.ops.object.camera_add();cam=bpy.context.object;angle=math.radians(cfg['angle']);cam.location=center+Vector((math.cos(angle)*span*2.8,-math.sin(angle)*span*2.8,span*2.0));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=span*1.8;bpy.context.scene.camera=cam
for pos,energy,size in [((2,-3,5),650,4),((-3,-1,2),250,4),((0,4,3),400,3)]:
 bpy.ops.object.light_add(type='AREA',location=center+Vector(pos)*span);light=bpy.context.object;light.data.energy=energy;light.data.shape='DISK';light.data.size=size*span;light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.device='CPU';scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.filepath=str(out/'asset.png');scene.world.color=(.6,.6,.6);bpy.ops.wm.save_as_mainfile(filepath=str(out/'asset.blend'));bpy.ops.render.render(write_still=True)
