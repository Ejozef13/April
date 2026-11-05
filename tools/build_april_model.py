"""Original editable procedural terrier. Run: blender -b --python tools/build_april_model.py"""
import math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, roughness=.65):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    result.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color, 1)
    result.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = roughness
    return result

white = material('Warm white coat', (.93,.90,.82))
brown = material('Terrier tan', (.39,.19,.075))
ear = material('Folded ear brown', (.23,.095,.035))
black = material('Eyes and nose', (.012,.017,.016), .22)
purple = material('Purple collar', (.22,.065,.30))
pink = material('Tongue', (.72,.23,.27))
silver = material('Tag', (.67,.71,.68), .3)

def sphere(name, location, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=location)
    obj=bpy.context.object; obj.name=name; obj.scale=scale
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:polygon.use_smooth=True
    if parent:
        obj.parent=parent
    return obj

# Sideways standing body; face points +Y. Model is intentionally stylized.
sphere('Body', (0,0,1.02), (.43,.80,.43), white)
sphere('Chest', (0,.49,1.10), (.36,.40,.52), white)
sphere('BackPatch', (.02,-.40,1.36), (.30,.30,.09), brown)
for x in [-.27,.27]:
    for y in [-.53,.47]:
        sphere('Leg', (x,y,.55), (.13,.16,.42), white)
        sphere('Paw', (x,y+.055,.19), (.17,.23,.12), white)

head=bpy.data.objects.new('HeadPivot',None)
bpy.context.collection.objects.link(head)
head.location=(0,.58,1.47)
sphere('Head', (0,.09,.27), (.36,.34,.38), brown, head)
sphere('WhiteMuzzle', (0,.36,.10), (.27,.28,.19), white, head)
sphere('Nose', (0,.57,.16), (.14,.085,.09), black, head)
sphere('Chin', (0,.39,-.005), (.21,.18,.07), white, head)
for x in [-.18,.18]:
    sphere('Eye', (x,.365,.35), (.072,.04,.08), black, head)
    sphere('EyeHighlight', (x-.017,.40,.376), (.018,.012,.02), white, head)
    folded=sphere('EarFold', (x*1.8,.12,.30), (.115,.15,.24), ear, head)
    folded.rotation_euler[1]=-.30 if x<0 else .30
    # Folded triangular ears have actual volume, rather than pointed cones.
    vertices=[(x*1.4,-.01,.51),(x*2.25,.12,.40),(x*1.7,.23,.06),
              (x*1.4,-.07,.48),(x*2.25,.06,.38),(x*1.7,.17,.06)]
    mesh=bpy.data.meshes.new('FoldedEar')
    mesh.from_pydata(vertices,[],[(0,1,2),(3,5,4),(0,3,4,1),(1,4,5,2),(2,5,3,0)])
    mesh.materials.append(ear)
    obj=bpy.data.objects.new('Ear',mesh);bpy.context.collection.objects.link(obj);obj.parent=head
    bevel=obj.modifiers.new('Soft edges','BEVEL');bevel.width=.045;bevel.segments=3
    obj.modifiers.new('Normals','WEIGHTED_NORMAL')
tongue=sphere('Tongue', (0,.49,-.045), (.09,.085,.035), pink, head)

bpy.ops.mesh.primitive_torus_add(major_radius=.285,minor_radius=.045,major_segments=32,minor_segments=10,
                               location=(0,.57,1.36))
bpy.context.object.name='Collar';bpy.context.object.data.materials.append(purple)
sphere('CollarTag', (0,.86,1.29), (.065,.025,.075), silver)

tail=bpy.data.objects.new('TailPivot',None);bpy.context.collection.objects.link(tail)
tail.location=(0,-.72,1.14)
sphere('TailBrown', (0,-.12,.17), (.085,.105,.25), brown, tail)
sphere('TailWhiteTip', (0,-.16,.40), (.07,.085,.14), white, tail)

# Own source scene includes camera/light for later editing and export.
bpy.ops.object.camera_add(location=(3,4,2.4))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,1.1))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=3.4
bpy.context.scene.camera=camera
for location, energy, size in [((2,3,5),450,4),((-3,1,3),250,3)]:
    bpy.ops.object.light_add(type='AREA',location=location)
    bpy.context.object.data.energy=energy;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=size
    bpy.context.object.rotation_euler=(Vector((0,0,1))-bpy.context.object.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=False
scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.render.film_transparent=True
scene.world.color=(.3,.3,.3)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'tools/april-prototype.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'april/web/assets/april-prototype.glb'),export_format='GLB',
                         export_cameras=False,export_lights=False)
scene.render.filepath='/tmp/april-3d-prototype.png'
bpy.ops.render.render(write_still=True)
