"""
vinyl_cover.py — 竹ドームにビニール(被覆シート)を被せるクロスシミュレーション

竹ドームを衝突体、上空のビニールシートを布(Cloth)として落下させ、ドーム形状に
沿って垂れ下がり被さる様子をシミュレートしてレンダリング。半透明ビニール材質。

実行:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/vinyl_cover.py -- --geo output/sim/dome_snow_scene.json \
    --out output/sim/vinyl.png --blend output/sim/vinyl.blend --frames 80
検証: Blender 4.5.3 LTS。
"""
import sys
import os
import json
import argparse

import bpy
import bmesh
from mathutils import Vector, Matrix


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", required=True)
    ap.add_argument("--out", default="output/sim/vinyl.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=80)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--res", type=int, default=1400)
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_mat(name, rgba, rough=0.5):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    return mat


def make_vinyl():
    mat = bpy.data.materials.new("Vinyl"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.85, 0.9, 0.95, 1.0)
    b.inputs["Roughness"].default_value = 0.12
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.5
    if "IOR" in b.inputs:
        b.inputs["IOR"].default_value = 1.45
    b.inputs["Alpha"].default_value = 0.68
    mat.blend_method = "BLEND"
    return mat


def cylinder_geo(bm, p1, p2, radius, seg=8):
    p1, p2 = Vector(p1), Vector(p2); vec = p2 - p1; L = vec.length
    if L < 1e-9:
        return
    q = vec.to_track_quat("Z", "Y")
    m = Matrix.Translation((p1 + p2) * 0.5) @ q.to_matrix().to_4x4()
    g = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=radius, radius2=radius, depth=L)
    bmesh.ops.transform(bm, matrix=m, verts=g["verts"])


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]; members = geo["members"]; faces = geo.get("faces", [])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0, 0, -9.81)

    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys)); top = max(zs)

    mat_bamboo = make_mat("Bamboo", (0.30, 0.40, 0.12, 1.0), 0.5)
    mat_shell = make_mat("Shell", (0.2, 0.25, 0.3, 1.0), 0.6)
    mat_vinyl = make_vinyl()
    mat_ground = make_mat("Ground", (0.4, 0.42, 0.45, 1.0), 0.9)

    me = bpy.data.meshes.new("Bamboo"); bm = bmesh.new()
    for (i, j) in members:
        cylinder_geo(bm, nodes[i], nodes[j], args.culm_d / 2.0)
    bm.to_mesh(me); bm.free()
    bamboo = bpy.data.objects.new("Bamboo", me)
    bpy.context.collection.objects.link(bamboo); bamboo.data.materials.append(mat_bamboo)
    for p in bamboo.data.polygons:
        p.use_smooth = True

    shell_me = bpy.data.meshes.new("Shell")
    shell_me.from_pydata([tuple(n) for n in nodes], [], [tuple(f) for f in faces])
    shell_me.update()
    shell = bpy.data.objects.new("Shell", shell_me)
    bpy.context.collection.objects.link(shell)
    shell.data.materials.append(mat_shell)
    shell.modifiers.new("Collision", type="COLLISION")
    shell.collision.thickness_outer = 0.04
    shell.collision.damping = 0.5

    bpy.ops.mesh.primitive_grid_add(x_subdivisions=70, y_subdivisions=70,
                                    size=size * 1.45, location=(cx, cy, top + 0.6))
    vinyl = bpy.context.active_object
    vinyl.name = "Vinyl"
    vinyl.data.materials.append(mat_vinyl)
    for p in vinyl.data.polygons:
        p.use_smooth = True
    cloth = vinyl.modifiers.new("Cloth", type="CLOTH")
    cs = cloth.settings
    cs.quality = 12
    cs.mass = 0.25
    cs.tension_stiffness = 35
    cs.compression_stiffness = 35
    cs.shear_stiffness = 35
    cs.bending_stiffness = 8
    cloth.collision_settings.use_self_collision = True
    cloth.collision_settings.distance_min = 0.02
    cloth.collision_settings.collision_quality = 4
    vinyl.modifiers.new("Sub", type="SUBSURF").levels = 1

    bpy.ops.mesh.primitive_plane_add(size=size*5, location=(cx, cy, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size*1.6, cy - size*1.9, top*0.9 + size*0.3))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((cx, cy, top*0.45)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.2
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(so)
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.5, 0.6, 0.72, 1)

    print("[vinyl] baking cloth ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)

    for scr in bpy.data.screens:
        for ar in scr.areas:
            if ar.type == "VIEW_3D":
                for sp in ar.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "MATERIAL"

    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res - args.res % 2
    sc.render.resolution_y = int(args.res*0.62)//2*2

    if args.blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[vinyl] blend saved -> {args.blend}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if args.animate:
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"; sc.render.fps = 24
        sc.render.filepath = os.path.abspath(args.out)
        bpy.ops.render.render(animation=True)
        import glob
        print(f"[vinyl] done -> {glob.glob(args.out + '*.mp4')}")
    else:
        sc.render.image_settings.file_format = "PNG"
        sc.frame_set(sc.frame_end)
        sc.render.filepath = os.path.abspath(args.out)
        bpy.ops.render.render(write_still=True)
        print(f"[vinyl] rendered -> {args.out}")


if __name__ == "__main__":
    main()
