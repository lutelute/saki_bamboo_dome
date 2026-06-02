"""
render_mpm.py — MPM雪の .ply 列を Blender で表面化してレンダリング

粒子点群を Geometry Nodes（Mesh to Points → Points to Volume → Volume to Mesh）で
連続した雪面に変換（ボクセル化が粒子の"結合"を表現）し、竹ドームと共にレンダ。
静止画(最終フレーム)とアニメ(全.ply列)の両対応。

実行:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/render_mpm.py -- \
    --geo output/sim/dome_geo_for_blender.json --ply-dir output/sim/mpm \
    --out output/sim/mpm_snow.png --voxel 0.06 --radius 0.13
検証: Blender 4.5.3 LTS。
"""
import sys
import os
import json
import glob
import math
import argparse

import bpy
import bmesh
from mathutils import Vector, Matrix


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", required=True)
    ap.add_argument("--ply-dir", required=True)
    ap.add_argument("--out", default="output/sim/mpm_snow.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--voxel", type=float, default=0.05, help="ボクセルサイズ[m]")
    ap.add_argument("--radius", type=float, default=0.20, help="粒子半径=結合距離[m]（大=滑らか）")
    ap.add_argument("--smooth", type=int, default=18, help="スムーズ反復回数（大=滑らか）")
    ap.add_argument("--animate", action="store_true", help="全.ply列をアニメ化")
    ap.add_argument("--frame", type=int, default=-1,
                    help="静止画にする.plyの番号（-1=最終）")
    ap.add_argument("--res", type=int, default=1400)
    ap.add_argument("--samples", type=int, default=64)
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_material(name, rgba, rough=0.5):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    return mat


def make_snow_material():
    """本物の雪: 透け感(サブサーフェス)＋粒状バンプ＋きらめきで豆腐感を消す。"""
    mat = bpy.data.materials.new("Snow"); mat.use_nodes = True
    nt = mat.node_tree
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.90, 0.94, 1.0, 1.0)   # わずかに青白い
    b.inputs["Roughness"].default_value = 0.42
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.32          # 雪の透け
        b.inputs["Subsurface Radius"].default_value = (0.10, 0.12, 0.18)
        if "Subsurface Scale" in b.inputs:
            b.inputs["Subsurface Scale"].default_value = 0.03
    # 細かな粒状バンプ（豆腐のツルツルを壊す）
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 42.0
    noise.inputs["Detail"].default_value = 8.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    # きらめき: 高周波ノイズの一部で粗さを下げ、雪のキラキラを出す
    spk = nt.nodes.new("ShaderNodeTexNoise"); spk.inputs["Scale"].default_value = 260.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.60
    ramp.color_ramp.elements[1].position = 0.70
    nt.links.new(spk.outputs["Fac"], ramp.inputs["Fac"])
    scl = nt.nodes.new("ShaderNodeMath"); scl.operation = "MULTIPLY"
    scl.inputs[1].default_value = 0.32
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    sub.inputs[0].default_value = 0.42
    nt.links.new(ramp.outputs["Color"], scl.inputs[0])
    nt.links.new(scl.outputs["Value"], sub.inputs[1])
    nt.links.new(sub.outputs["Value"], b.inputs["Roughness"])
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


def surfacing_nodes(obj, voxel, radius, mat):
    """Mesh to Points → Points to Volume → Volume to Mesh の Geometry Nodes を付与。"""
    mod = obj.modifiers.new("Surface", type="NODES")
    ng = bpy.data.node_groups.new("SnowSurface", "GeometryNodeTree")
    mod.node_group = ng
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = ng.nodes, ng.links
    n_in = nodes.new("NodeGroupInput"); n_in.location = (-600, 0)
    n_out = nodes.new("NodeGroupOutput"); n_out.location = (600, 0)
    m2p = nodes.new("GeometryNodeMeshToPoints"); m2p.location = (-400, 0)
    p2v = nodes.new("GeometryNodePointsToVolume"); p2v.location = (-150, 0)
    v2m = nodes.new("GeometryNodeVolumeToMesh"); v2m.location = (150, 0)
    shade = nodes.new("GeometryNodeSetShadeSmooth"); shade.location = (320, 0)
    setmat = nodes.new("GeometryNodeSetMaterial"); setmat.location = (470, 0)
    # Points to Volume 設定（ボクセルサイズ・半径）
    try:
        p2v.resolution_mode = "VOXEL_SIZE"
        p2v.inputs["Voxel Size"].default_value = voxel
    except Exception:
        pass
    for nm, val in (("Radius", radius), ("Density", 1.0)):
        if nm in p2v.inputs:
            p2v.inputs[nm].default_value = val
    if "Threshold" in v2m.inputs:
        v2m.inputs["Threshold"].default_value = 0.12
    if "Adaptivity" in v2m.inputs:
        v2m.inputs["Adaptivity"].default_value = 0.3
    setmat.inputs["Material"].default_value = mat
    links.new(n_in.outputs[0], m2p.inputs["Mesh"])
    links.new(m2p.outputs["Points"], p2v.inputs["Points"])
    links.new(p2v.outputs["Volume"], v2m.inputs["Volume"])
    links.new(v2m.outputs["Mesh"], shade.inputs["Geometry"])
    links.new(shade.outputs["Geometry"], setmat.inputs["Geometry"])
    links.new(setmat.outputs["Geometry"], n_out.inputs[0])
    return mod


def add_smooth(obj, iterations):
    """生成された雪面を頂点スムーズで滑らかにする。"""
    sm = obj.modifiers.new("Smooth", type="SMOOTH")
    sm.iterations = iterations
    sm.factor = 1.0


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]; members = geo["members"]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene

    mat_bamboo = make_material("Bamboo", (0.30, 0.40, 0.12, 1.0), 0.5)
    mat_snow = make_snow_material()
    mat_ground = make_snow_material()      # 地面も雪

    # 竹ドーム
    me = bpy.data.meshes.new("Bamboo"); bm = bmesh.new()
    for (i, j) in members:
        cylinder_geo(bm, nodes[i], nodes[j], args.culm_d / 2.0)
    bm.to_mesh(me); bm.free()
    bamboo = bpy.data.objects.new("Bamboo", me)
    bpy.context.collection.objects.link(bamboo); bamboo.data.materials.append(mat_bamboo)
    for p in bamboo.data.polygons:
        p.use_smooth = True

    # 地面
    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys)); top = max(zs)
    bpy.ops.mesh.primitive_plane_add(size=size*5, location=(cx, cy, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 雪点群 .ply を読み込み
    plys = sorted(glob.glob(os.path.join(args.ply_dir, "snow_*.ply")))
    if not plys:
        print("[mpm] .ply が見つかりません"); return
    target = plys if args.animate else [plys[args.frame]]
    sc.frame_start, sc.frame_end = 1, len(target)

    snow_objs = []
    for idx, ply in enumerate(target):
        bpy.ops.wm.ply_import(filepath=ply)
        ob = bpy.context.active_object
        ob.name = f"Snow_{idx:04d}"
        surfacing_nodes(ob, args.voxel, args.radius, mat_snow)
        add_smooth(ob, args.smooth)
        snow_objs.append(ob)
        if args.animate:                              # フレーム idx+1 のみ表示
            for fr, hidden in ((idx, True), (idx + 1, False), (idx + 2, True)):
                ob.hide_render = hidden
                ob.hide_viewport = hidden
                ob.keyframe_insert("hide_render", frame=fr)
                ob.keyframe_insert("hide_viewport", frame=fr)
            if ob.animation_data and ob.animation_data.action:
                for fc in ob.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"

    # カメラ＋ライト
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size*1.6, cy - size*1.9, top*0.8 + size*0.2))
    cam.location = loc
    direction = Vector((cx, cy, top*0.45)) - loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.0
    sun.color = (1.0, 0.97, 0.92); sun.angle = 0.06    # やわらかい影
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.95, 0.15, 0.5)
    bpy.context.collection.objects.link(so)
    # 冬の青空ワールド（Nishita sky）
    world = bpy.data.worlds.new("Winter"); sc.world = world; world.use_nodes = True
    nt = world.node_tree; bg = nt.nodes.get("Background")
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "NISHITA"; sky.sun_elevation = math.radians(32)
        sky.sun_rotation = math.radians(40)
        nt.links.new(sky.outputs[0], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.6
    except Exception:
        bg.inputs["Color"].default_value = (0.55, 0.68, 0.85, 1.0)

    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res - args.res % 2
    sc.render.resolution_y = int(args.res*0.62)//2*2
    try:
        sc.eevee.taa_render_samples = args.samples
    except AttributeError:
        pass

    if args.blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[mpm] blend saved -> {args.blend}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if args.animate:
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"; sc.render.fps = 24
        sc.render.filepath = os.path.abspath(args.out)
        bpy.ops.render.render(animation=True)
        print(f"[mpm] done -> {glob.glob(args.out + '*.mp4')}")
    else:
        sc.render.image_settings.file_format = "PNG"
        sc.frame_set(1)
        sc.render.filepath = os.path.abspath(args.out)
        bpy.ops.render.render(write_still=True)
        print(f"[mpm] rendered -> {args.out}")


if __name__ == "__main__":
    main()
