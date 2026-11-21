import bpy, math, json
from mathutils import Vector
from pathlib import Path

# 30-second, silent, stylized 3D stick-fighter short.
W,H,FPS,DURATION = 720,1280,24,30
OUT = Path("output")
OUT.mkdir(exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def material(name, color, metallic=0.0, roughness=0.38):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(*color,1)
    bs.inputs["Metallic"].default_value=metallic
    bs.inputs["Roughness"].default_value=roughness
    return m

red=material("Hero - ruby red", (0.82,0.025,0.035), 0.18)
blue=material("Rival - electric blue", (0.025,0.12,0.78), 0.18)
jointmat=material("Joint dark graphite",(0.035,0.045,0.065),0.25)
floor_mat=material("Matte studio floor",(0.78,0.82,0.9),0.0,0.8)
white=material("Studio background",(0.94,0.96,1.0),0.0,0.9)

def smooth(obj):
    if obj.type=="MESH":
        for p in obj.data.polygons: p.use_smooth=True

def sphere(name, loc, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=radius, location=loc)
    o=bpy.context.object; o.name=name; o.data.materials.append(mat); smooth(o)
    return o

def cylinder(name, radius, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=1, location=(0,0,0))
    o=bpy.context.object; o.name=name; o.data.materials.append(mat); smooth(o)
    bevel=o.modifiers.new("Soft rounded edges","BEVEL"); bevel.width=radius*0.32; bevel.segments=3
    o.modifiers.new("Weighted corner normals","WEIGHTED_NORMAL")
    return o

def segment(obj, a, b, frame):
    av,bv=Vector(a),Vector(b); d=bv-av
    obj.location=(av+bv)*0.5
    obj.rotation_mode="QUATERNION"; obj.rotation_quaternion=d.to_track_quat("Z","Y")
    obj.dimensions=(obj.dimensions.x,obj.dimensions.y,d.length)
    obj.keyframe_insert(data_path="location",frame=frame)
    obj.keyframe_insert(data_path="rotation_quaternion",frame=frame)
    obj.keyframe_insert(data_path="scale",frame=frame)

def make_fighter(label, mat, x, facing):
    c={}
    c["head"]=sphere(label+" head",(x,0,3.02),0.34,mat)
    c["torso"]=cylinder(label+" torso",0.16,mat)
    c["upper_arm_l"]=cylinder(label+" upper arm L",0.085,mat)
    c["lower_arm_l"]=cylinder(label+" forearm L",0.075,mat)
    c["upper_arm_r"]=cylinder(label+" upper arm R",0.085,mat)
    c["lower_arm_r"]=cylinder(label+" forearm R",0.075,mat)
    c["thigh_l"]=cylinder(label+" thigh L",0.105,mat)
    c["shin_l"]=cylinder(label+" shin L",0.085,mat)
    c["thigh_r"]=cylinder(label+" thigh R",0.105,mat)
    c["shin_r"]=cylinder(label+" shin R",0.085,mat)
    c["hand_l"]=sphere(label+" glove L",(x,0,1),0.11,mat)
    c["hand_r"]=sphere(label+" glove R",(x,0,1),0.11,mat)
    c["foot_l"]=sphere(label+" foot L",(x,0,0.1),0.13,mat)
    c["foot_r"]=sphere(label+" foot R",(x,0,0.1),0.13,mat)
    c["facing"]=facing; c["x"]=x
    return c

def pose(c, frame, rootx, action="guard", jump=0):
    f=c["facing"]; x=rootx; y=0
    # World-space joints. Slight 3D depth offsets make the figures feel dimensional.
    head=(x,0,3.04+jump)
    shoulder=(x,0,2.36+jump)
    hip=(x,0,1.35+jump)
    if action=="punch":
        arm1=(x-f*0.22,-0.03,2.25+jump); elbow1=(x+f*0.26,-0.05,2.23+jump); hand1=(x+f*0.78,-0.10,2.20+jump)
        arm2=(x-f*0.22,0.08,2.28+jump); elbow2=(x-f*0.43,0.10,2.04+jump); hand2=(x-f*0.48,0.12,1.88+jump)
        knee1=(x-f*0.28,0,0.72+jump); ankle1=(x-f*0.38,0,0.12+jump)
        knee2=(x+f*0.22,0,0.78+jump); ankle2=(x+f*0.30,0,0.12+jump)
    elif action=="kick":
        arm1=(x-f*0.22,0,2.28+jump); elbow1=(x-f*0.52,0,2.50+jump); hand1=(x-f*0.66,0,2.66+jump)
        arm2=(x+f*0.22,0,2.28+jump); elbow2=(x+f*0.50,0,2.18+jump); hand2=(x+f*0.58,0,2.35+jump)
        knee1=(x-f*0.22,0,0.78+jump); ankle1=(x-f*0.38,0,0.12+jump)
        knee2=(x+f*0.30,0,1.45+jump); ankle2=(x+f*1.12,-0.06,1.85+jump)
    elif action=="jump":
        shoulder=(x,0,2.48+jump); hip=(x,0,1.48+jump)
        arm1=(x-f*0.22,0,2.40+jump); elbow1=(x-f*0.48,0,2.78+jump); hand1=(x-f*0.72,0,3.02+jump)
        arm2=(x+f*0.22,0,2.40+jump); elbow2=(x+f*0.48,0,2.78+jump); hand2=(x+f*0.72,0,3.02+jump)
        knee1=(x-f*0.42,0,1.08+jump); ankle1=(x-f*0.72,0,0.72+jump)
        knee2=(x+f*0.42,0,1.08+jump); ankle2=(x+f*0.72,0,0.72+jump)
    elif action=="down":
        head=(x+f*0.55,0,1.12); shoulder=(x,0,0.90); hip=(x-f*0.35,0,0.65)
        arm1=(x+f*0.12,0,0.85); elbow1=(x+f*0.48,0,0.58); hand1=(x+f*0.78,0,0.52)
        arm2=(x-f*0.12,0,0.82); elbow2=(x-f*0.40,0,0.45); hand2=(x-f*0.65,0,0.40)
        knee1=(x-f*0.65,0,0.55); ankle1=(x-f*1.00,0,0.18)
        knee2=(x+f*0.12,0,0.52); ankle2=(x+f*0.55,0,0.18)
    else:
        arm1=(x-f*0.22,0,2.28+jump); elbow1=(x-f*0.48,0,2.12+jump); hand1=(x-f*0.40,0,1.90+jump)
        arm2=(x+f*0.22,0,2.28+jump); elbow2=(x+f*0.48,0,2.12+jump); hand2=(x+f*0.40,0,1.90+jump)
        knee1=(x-f*0.28,0,0.72+jump); ankle1=(x-f*0.34,0,0.12+jump)
        knee2=(x+f*0.28,0,0.72+jump); ankle2=(x+f*0.34,0,0.12+jump)
    # torso/head
    c["head"].location=head; c["head"].keyframe_insert("location",frame=frame)
    segment(c["torso"],shoulder,hip,frame)
    # Arms
    for side,sh,el,ha in [("l",arm1,elbow1,hand1),("r",arm2,elbow2,hand2)]:
        segment(c["upper_arm_"+side],sh,el,frame); segment(c["lower_arm_"+side],el,ha,frame)
        glove=c["hand_"+side]; glove.location=ha; glove.keyframe_insert("location",frame=frame)
    # Legs
    for side,hi,kn,an in [("l",hip,knee1,ankle1),("r",hip,knee2,ankle2)]:
        segment(c["thigh_"+side],hi,kn,frame); segment(c["shin_"+side],kn,an,frame)
        foot=c["foot_"+side]; foot.location=an; foot.keyframe_insert("location",frame=frame)

def scene_setup():
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-0.08))
    floor=bpy.context.object; floor.name="Studio floor"; floor.data.materials.append(floor_mat)
    bpy.ops.object.camera_add(location=(0,-15,4.1))
    cam=bpy.context.object; cam.name="Camera"; cam.data.type="ORTHO"; cam.data.ortho_scale=9.6
    cam.rotation_euler=(math.radians(78),0,0)
    # Aim camera toward center stage
    direction=Vector((0,0,1.7))-cam.location
    cam.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    bpy.context.scene.camera=cam
    for loc,energy,size in [((-4,-6,8),1800,7),((4,-2,6),1200,5),((0,4,7),1500,4)]:
        bpy.ops.object.light_add(type="AREA",location=loc)
        light=bpy.context.object; light.data.energy=energy; light.data.shape="DISK"; light.data.size=size
        light.rotation_euler=(Vector((0,0,1.5))-light.location).to_track_quat("-Z","Y").to_euler()
    world=bpy.context.scene.world; world.color=(0.8,0.8,0.8)
    world.use_nodes=True; world.node_tree.nodes["Background"].inputs[0].default_value=(0.78,0.83,0.92,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=0.45

scene_setup()
hero=make_fighter("Ruby Fighter",red,-2.0,1)
rival=make_fighter("Blue Fighter",blue,2.0,-1)

# 7 key poses, interpolated smoothly across a complete fight.
beats=[
 (1,-2.0,2.0,"guard","guard",0,0),
 (4,-1.65,1.75,"punch","guard",0,0),
 (8,-1.8,1.9,"guard","down",0,0),
 (12,-1.5,1.55,"kick","guard",0,0),
 (16,-1.4,1.4,"jump","jump",0.75,0.65),
 (21,-1.5,1.6,"guard","down",0,0),
 (26,-1.8,1.8,"guard","down",0,0),
 (30,-1.8,1.8,"guard","down",0,0)
]
for sec,hx,bx,hp,bp,hj,bj in beats:
    frame=int(sec*FPS)
    pose(hero,frame,hx,hp,hj)
    pose(rival,frame,bx,bp,bj)
# Add anticipation and final impact beats for more lively motion.
for c in (hero,rival):
    for obj in c.values():
        if hasattr(obj,"animation_data") and obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation="BEZIER"

scene=bpy.context.scene
scene.frame_start=1; scene.frame_end=FPS*DURATION
scene.render.engine="BLENDER_EEVEE_NEXT" if hasattr(bpy.types,"BLENDER_EEVEE_NEXT") else "BLENDER_EEVEE"
scene.render.resolution_x=W; scene.render.resolution_y=H; scene.render.resolution_percentage=100
scene.render.fps=FPS
scene.render.image_settings.file_format="FFMPEG"
scene.render.ffmpeg.format="MPEG4"; scene.render.ffmpeg.codec="H264"
scene.render.ffmpeg.constant_rate_factor="MEDIUM"; scene.render.ffmpeg.ffmpeg_preset="GOOD"
scene.render.filepath=str(OUT/"ai_story_short.mp4")
scene.view_settings.view_transform="Standard"
scene.render.image_settings.color_mode="RGB"
scene.render.film_transparent=False
scene.camera.data.lens=50
scene.world.color=(0.8,0.8,0.8)
scene.render.use_file_extension=True
scene.frame_set(1)
print("Rendering original 3D Stickman Fight animation...")
bpy.ops.render.render(animation=True)
video=OUT/"ai_story_short.mp4"
if not video.exists() or video.stat().st_size<10000:
    raise RuntimeError("3D video render did not produce a valid MP4")
print(f"SUCCESS: Created silent 3D fight video: {video} ({video.stat().st_size} bytes)")
