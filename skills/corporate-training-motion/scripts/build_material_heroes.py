"""Local Blender originals: four distinct constructions, not a colour-swapped scene.
Run: blender -b --python-exit-code 1 --python SCRIPT -- OUTPUT_DIRECTORY
"""
import bpy, math, json, sys, hashlib
from pathlib import Path
from mathutils import Vector
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True)



def label_anchors(style):
    from bpy_extras.object_utils import world_to_camera_view
    points={
        'brushed-metal':[('正面显示',(-1.9,0,1.65)),('金属机身',(0,.15,1.65)),('背面镜组',(1.9,.35,1.65))],
        'clay-matte':[('AirPods',(-1.35,0,1.7)),('Apple Watch',(1.6,0,1.8))],
        'lowpoly-facets':[('接待通道',(-2,-1.5,0)),('体验桌',(.95,-.25,.94)),('配件墙',(0,2,1.6))],
        'clear-acrylic':[('iPhone',(-1.9,-.8,.65)),('iPad',(0,.2,1)),('Mac',(1.8,.9,1.35))]}
    bpy.context.view_layer.update();scene=bpy.context.scene;result=[]
    for label,position in points[style]:
        point=world_to_camera_view(scene,scene.camera,Vector(position));result.append(dict(label=label,point=[point.x,1-point.y]))
    return result

if '--anchors-only' in sys.argv:
    receipt=json.loads((out/'provenance.json').read_text())
    for item in receipt['materials']:
        bpy.ops.wm.open_mainfile(filepath=str(out/item['blend']));item['labelAnchors']=label_anchors(item['surface']);item['imageSize']=[bpy.context.scene.render.resolution_x,bpy.context.scene.render.resolution_y]
    (out/'provenance.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');raise SystemExit(0)

def material(name,color,rough=.6,metal=0,trans=0,clay=False,brushed=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;ns=m.node_tree.nodes;ns.clear()
    p=ns.new('ShaderNodeBsdfPrincipled');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Transmission Weight'].default_value=trans
    output=ns.new('ShaderNodeOutputMaterial');m.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
    if clay or brushed:
        noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=75 if clay else 240;noise.inputs['Detail'].default_value=2
        bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.25 if clay else .1;bump.inputs['Distance'].default_value=.03 if clay else .009;m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    return m


def box(name,loc,size,mat,bevel=.06,facets=False):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    if bevel:
        mod=o.modifiers.new('edge geometry','BEVEL');mod.width=bevel;mod.segments=1 if facets else 6;o.modifiers.new('face normal','WEIGHTED_NORMAL')
    return o


def sphere(name,loc,scale,mat,facets=False):
    if facets:bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=loc)
    else:bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=20,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
    if not facets:
        for p in o.data.polygons:p.use_smooth=True
    return o


def cylinder(name,loc,r,depth,mat,rot=(0,0,0),facets=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8 if facets else 48,radius=r,depth=depth,location=loc,rotation=rot);o=bpy.context.object;o.name=name;o.data.materials.append(mat)
    if not facets:
        mod=o.modifiers.new('soft edge','BEVEL');mod.width=min(.035,depth*.2);mod.segments=3;o.modifiers.new('normals','WEIGHTED_NORMAL')
    return o


def phone(name,x,y,z,scale,body,dark,rim,facets=False,front=False):
    def B(n,dx,dy,dz,size,mat,bevel=.08):return box(name+'-'+n,(x+dx*scale,y+dy*scale,z+dz*scale),tuple(v*scale for v in size),mat,bevel*scale,facets)
    B('body',0,0,0,(1.25,.16,2.55),body,.16)
    if front:
        B('display',0,-.1,0,(1.12,.035,2.35),dark,.12);B('island',0,-.125,.98,(.35,.025,.10),rim,.045)
    else:
        B('wide camera platform',0,-.14,.82,(1.12,.12,.77),body,.11)
        for i,(dx,dz) in enumerate([(-.32,.98),(.10,.94),(-.32,.57)]):
            cylinder(name+'-lens-rim-'+str(i),(x+dx*scale,y-.23*scale,z+dz*scale),.175*scale,.08*scale,rim,(math.pi/2,0,0),facets)
            cylinder(name+'-lens-'+str(i),(x+dx*scale,y-.28*scale,z+dz*scale),.125*scale,.035*scale,dark,(math.pi/2,0,0),facets)


rows=json.loads((out/'provenance.json').read_text()).get('materials',[]) if (out/'provenance.json').exists() else []
rows=[x for x in rows if isinstance(x,dict)]
for style in (sys.argv[sys.argv.index('--')+2:] or ['brushed-metal','clay-matte','lowpoly-facets','clear-acrylic']):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    dark=material('display / camera glass',(.014,.035,.045),.18);ivory=material('warm white',(.88,.87,.79),.8,clay=style=='clay-matte');blue=material('blue aluminium',(.15,.35,.48),.28,.7);silver=material('brushed aluminium',(.48,.55,.59),.28,.92,brushed=True)
    if style=='brushed-metal':
        bg=(.055,.075,.095);floor=material('studio charcoal',bg,.85);box('studio',(0,0,-.07),(200,200,.1),floor,0)
        # Exterior layers only. No invented internal circuitry or specifications.
        phone('front display',-1.9,0,1.65,1,blue,dark,silver,front=True)
        box('aluminium middle layer',(0,.15,1.65),(1.24,.12,2.55),silver,.14)
        phone('rear shell',1.9,.35,1.65,1,blue,dark,silver)
        for x in [-.95,.95]:cylinder('alignment guide',(x,.3,1.62),.015,.8,silver,(0,math.pi/2,0))
        camera=(5,-10,5.2);target=(0,0,1.6);ortho=7.0;desc='separated front display, metal body plate and rear shell; exterior teaching schematic, not a teardown'
    elif style=='clay-matte':
        bg=(.64,.37,.23);floor=material('clay backdrop',bg,.95,clay=True);terra=material('terracotta',(.68,.25,.13),.95,clay=True);sand=material('sand clay',(.68,.52,.34),.95,clay=True);rubber=material('watch silicone clay',(.33,.46,.32),.95,clay=True)
        box('floor',(0,0,-.1),(200,200,.2),floor,0)
        cylinder('AirPods round plinth',(-1.35,.05,.25),1.4,.5,sand);cylinder('Watch round plinth',(1.6,.2,.43),1.15,.86,terra)
        box('AirPods charging case',(-1.35,-.08,1.15),(1.85,.76,1.10),ivory,.42);box('AirPods lid seam',(-1.35,-.476,1.35),(1.48,.008,.016),sand,.006);sphere('case status light',(-1.35,-.48,1.07),(.025,.009,.025),rubber)
        for i,x in enumerate([-1.8,-.92]):
            sphere('AirPod curved housing '+str(i),(x,-.05,2.21),(.29,.20,.21),ivory);box('AirPod short stem '+str(i),(x+.09,.01,1.96),(.14,.16,.46),ivory,.07);sphere('AirPod acoustic mesh '+str(i),(x-.08,-.22,2.22),(.105,.026,.065),dark)
        box('Watch strap',(1.6,.1,1.65),(.67,.20,2.2),rubber,.25);box('Watch rounded case',(1.6,-.03,1.72),(1.18,.34,1.30),terra,.28);box('Watch display',(1.6,-.22,1.72),(.95,.035,1.08),dark,.22);cylinder('Watch digital crown',(2.25,-.05,1.94),.13,.14,terra,(0,math.pi/2,0));cylinder('Watch dial',(1.6,-.25,1.72),.32,.015,ivory,(math.pi/2,0,0));box('Watch hour hand',(1.61,-.27,1.83),(.045,.015,.23),rubber,.014)
        camera=(5,-9,5.1);target=(0,0,1.25);ortho=6.3;desc='hand-moulded style AirPods and Apple Watch with rough clay surfaces and separate round plinths'
    elif style=='lowpoly-facets':
        bg=(.12,.22,.23);floor=material('studio',bg,.95);wall=material('store wall',(.67,.71,.66),.8);wood=material('wood floor',(.55,.37,.21),.8);trim=material('store fascia',(.12,.17,.18),.8);glass=material('store glass',(.35,.65,.66),.24,trans=.5)
        box('outside',(0,0,-.25),(200,200,.15),floor,0);box('store floor',(0,0,0),(6,4.7,.25),wood,.12,True);box('back wall',(0,2.2,1.55),(6,.15,3.2),wall,.015,True);box('side wall',(-2.9,0,1.55),(.16,4.5,3.2),wall,.015,True)
        box('front fascia',(0,-2.25,3.05),(6,.22,.42),trim,.02,True);box('left corner glass',(-2.86,-1.35,1.4),(.05,1.45,2.7),glass,.01,True)
        for x in [-1.55,.95]:
            box('display table top',(x,-.25,.94),(1.55,1.85,.16),ivory,.045,True)
            for dx in [-.61,.61]:
                for dy in [-.72,.72]:box('table leg',(x+dx,-.25+dy,.47),(.10,.10,.86),ivory,.015,True)
            for i in range(2):phone('iPhone display '+str(x)+str(i),x-.35+i*.68,-.5,1.32,.23,blue,dark,silver,True,front=i==0)
        for col in range(7):
            for row in range(4):box('accessory packaging',(-2.35+col*.73,2.03,.53+row*.48),(.42,.08,.35),ivory if row%2 else silver,.02,True)
        for z in [.27,.76,1.24,1.73,2.21]:box('wall shelf',(0,1.98,z),(5.65,.4,.06),ivory,.01,True)
        for x in [-1.5,.2,1.8]:box('ceiling strip',(x,.5,3.0),(.035,2.9,.04),ivory,.01,True)
        camera=(8,-10,8);target=(0,0,1.3);ortho=8.6;desc='entire angular retail diorama: charcoal fascia, light accessory wall, wood floor and two iPhone tables'
    else:
        bg=(.045,.11,.15);floor=material('night studio',bg,.8);box('studio',(0,0,-.1),(200,200,.2),floor,0);clear=material('clear acrylic',(.90,.98,1.0),.045,trans=1);edge=material('lit acrylic edges',(.21,.68,.75),.21,.35);gold=material('warm relationship line',(.72,.46,.17),.30,.65)
        # Flat, overlapping transparent plates use a different spatial grammar
        # from the upright metal layers. The rear grid reveals transmission.
        grid=material('transmission reference grid',(.18,.28,.30),.9)
        for j in range(-5,6):
            box('floor grid X '+str(j),(j*.6,0,.015),(.014,7,.008),grid,0);box('floor grid Y '+str(j),(0,j*.6,.016),(8,.014,.008),grid,0)
        for i,(x,y,z) in enumerate([(-1.9,-.8,.65),(0,.2,1.0),(1.8,.9,1.35)]):
            before=set(bpy.data.objects)
            box('acrylic plate '+str(i),(0,0,0),(1.80,.11,2.6),clear,.10);box('plate lower edge '+str(i),(0,-.07,-1.22),(1.58,.015,.025),edge,.008)
            if i==0:phone('iPhone silhouette',0,-.12,0,.55,edge,dark,silver,front=True)
            elif i==1:box('iPad outline',(0,-.11,0),(1.38,.06,1.03),edge,.10);box('iPad display',(0,-.15,0),(1.22,.02,.86),dark,.06)
            else:
                box('Mac display',(0,-.11,.1),(1.40,.06,.94),edge,.07);box('Mac screen',(0,-.15,.1),(1.25,.02,.79),dark,.04);box('Mac keyboard',(0,-.32,-.43),(1.43,.54,.045),silver,.03)
            pieces=set(bpy.data.objects)-before
            bpy.ops.object.empty_add(type='PLAIN_AXES',location=(x,y,z));anchor=bpy.context.object;anchor.name='acrylic panel assembly '+str(i);anchor.rotation_euler=(-math.pi/2,0,-.16+i*.16)
            for piece in pieces:piece.parent=anchor
        for i,loc in enumerate([(-.9,-.3,.28),(.95,.65,.43)]):cylinder('relationship bridge '+str(i),loc,.035,.80,gold,(0,math.pi/2,0))
        camera=(6,-9,11);target=(0,0,.6);ortho=7.8;desc='three diagonal overlapping transparent acrylic plates with distinct iPhone, iPad and Mac silhouettes; transmission visible against a reference grid'
    for loc,power,size in [((1,-4,7),900,5),((-4,-2,5),650,4),((2,4,5),1100,3)]:
        bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=camera);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=ortho
    scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.device='CPU';scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
    scene.world.use_nodes=True;ns=scene.world.node_tree.nodes;ns.clear();back=ns.new('ShaderNodeBackground');back.inputs['Color'].default_value=(*bg,1);back.inputs['Strength'].default_value=.35;world=ns.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(back.outputs['Background'],world.inputs['Surface'])
    scene.render.filepath=str(out/(style+'.png'));scene.render.image_settings.color_mode='RGBA';bpy.ops.wm.save_as_mainfile(filepath=str(out/(style+'.blend')));bpy.ops.render.render(write_still=True)
    rows=[x for x in rows if x['surface']!=style]
    rows.append(dict(surface=style,labelAnchors=label_anchors(style),imageSize=[1200,800],description=desc,file=style+'.png',sha256=hashlib.sha256((out/(style+'.png')).read_bytes()).hexdigest(),blend=style+'.blend'))
(out/'provenance.json').write_text(json.dumps(dict(method='local Blender independent geometry and procedural materials',products='Apple-family teaching illustrations; not exact CAD or teardown specifications',noGenerativeImages=True,materials=rows),ensure_ascii=False,indent=2)+'\n')
