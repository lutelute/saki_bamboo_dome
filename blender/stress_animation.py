"""
stress_animation.py — 雪の重みで竹ドームに応力がかかる様子をアニメ化

雪が積もるほど竹部材の利用率が上がり、色が緑→黄→赤に変化。
危険な部材が一目でわかるアニメ。物理モデル(snow_sim.simulate_snow)で
時系列の応力データを生成し、Blenderの竹マテリアルを各フレームで色付け。

実行:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/stress_animation.py -- \
    --geo output/sim/dome_snow_scene.json --stress output/sim/stress_timeline.json \
    --out output/sim/stress_ --blend output/sim/stress.blend --animate 120
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
    ap.add_argument("--stress", required=True, help="時系列応力データJSON")
    ap.add_argument("--out", default="output/sim/stress.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--animate", type=int, default=120)
    ap.add_argument("--res", type=int, default=1280)
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_emit_mat(name):
    """利用率で色変化する発光マテリアル: emission color をキーフレーム化可能"""
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.2, 0.5, 0.2, 1.0)
    b.inputs["Roughness"].default_value = 0.4
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (0.2, 0.5, 0.2, 1.0)
        b.inputs["Emission Strength"].default_value = 1.5
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


def util_to_color(u):
    """利用率(0-1+) → RGBA色: 緑→黄→オレンジ→赤"""
    if u <= 0.5:
        t = u / 0.5
        return (0.2 + 0.8*t, 0.6 + 0.4*t, 0.2 - 0.2*t, 1.0)   # 緑→黄
    elif u <= 0.85:
        t = (u - 0.5) / 0.35
        return (1.0, 1.0 - 0.5*t, 0.0, 1.0)                    # 黄→オレンジ
    else:
        t = min(1.0, (u - 0.85) / 0.15)
        return (1.0, 0.5 - 0.5*t, 0.0, 1.0)                    # オレンジ→赤


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    stress = json.load(open(args.stress))
    nodes = geo["nodes"]; members = geo["members"]
    frames = stress["frames"]   # 各フレーム = {member_utils: [...], max_util: ...}
    N = args.animate

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, N

    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys)); top = max(zs)

    # 各部材を個別オブジェクトとして作成（個別マテリアル＝個別色アニメ可能）
    member_objs = []
    member_mats = []
    rad = args.culm_d / 2.0
    for m_idx, (i, j) in enumerate(members):
        bm = bmesh.new()
        cylinder_geo(bm, nodes[i], nodes[j], rad)
        me = bpy.data.meshes.new(f"M{m_idx}")
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(f"M{m_idx}", me)
        bpy.context.collection.objects.link(ob)
        mat = make_emit_mat(f"Mat{m_idx}")
        ob.data.materials.append(mat)
        for p in ob.data.polygons:
            p.use_smooth = True
        member_objs.append(ob)
        member_mats.append(mat)

    # 各フレームに対応する利用率を時系列キーフレーム化
    # フレームデータが少ない場合は補間して animateフレーム数に伸ばす
    n_data = len(frames)
    for m_idx in range(len(members)):
        mat = member_mats[m_idx]
        b = principled(mat)
        ec = b.inputs["Emission Color"]
        bc = b.inputs["Base Color"]
        for fr in range(1, N+1):
            # フレーム時間→データインデックス
            t = (fr - 1) / max(1, N - 1)
            di = min(n_data - 1, int(t * (n_data - 1)))
            u = frames[di]["member_utils"][m_idx]
            col = util_to_color(u)
            ec.default_value = col
            ec.keyframe_insert("default_value", frame=fr)
            bc.default_value = col
            bc.keyframe_insert("default_value", frame=fr)

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=size*5, location=(cx, cy, 0))
    ground = bpy.context.active_object
    gmat = bpy.data.materials.new("Ground"); gmat.use_nodes = True
    principled(gmat).inputs["Base Color"].default_value = (0.08, 0.10, 0.13, 1)
    principled(gmat).inputs["Roughness"].default_value = 0.9
    ground.data.materials.append(gmat)

    # カメラ＋ライト
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size*1.5, cy - size*1.8, top*1.0 + size*0.3))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((cx, cy, top*0.5)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 1.5
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(so)
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.02, 0.03, 0.05, 1.0)
    bg.inputs["Strength"].default_value = 0.3

    # ビューポートをマテリアル表示に
    for scr in bpy.data.screens:
        for ar in scr.areas:
            if ar.type == "VIEW_3D":
                for sp in ar.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "MATERIAL"

    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res - args.res % 2
    sc.render.resolution_y = int(args.res*0.62)//2*2
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass

    if args.blend:
        sc.frame_set(1)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[stress] blend saved -> {args.blend}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"; sc.render.fps = 24
        sc.render.filepath = os.path.abspath(args.out)
        print(f"[stress] rendering animation ({N}フレーム) ...")
        bpy.ops.render.render(animation=True)
        import glob
        print(f"[stress] done -> {glob.glob(args.out + '*.mp4')}")


if __name__ == "__main__":
    main()
