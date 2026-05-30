"""
build_dome.py — 竹ドームを Blender で3Dモデル化し、ヘッドレスでレンダリング

幾何JSON(nodes/members/supports/axial)を読み、各部材を竹シリンダー、各節点を
継手スフィアとして生成。軸力で色分け（圧縮シアン/引張アンバー）も可能。
PNG出力と .blend 保存を行う。

実行（ヘッドレス）:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
      --python blender/build_dome.py -- \
      --geo output/dome_geometry.json --out output/dome_render.png \
      --blend output/dome.blend --culm-d 0.10 --color-by force

API は Blender 4.5.3 LTS で検証済み（research）:
  ・Principled BSDF は bl_idname='ShaderNodeBsdfPrincipled' で取得（表示名はローカライズされる）
  ・レンダーエンジンは 'BLENDER_EEVEE_NEXT'（4.2+）
  ・シリンダーは midpoint に置き rotation_quaternion = vec.to_track_quat('Z','Y')
  ・scene.camera にカメラ"オブジェクト"を設定し、ライトを置かないと真っ黒
"""
import sys
import os
import json
import argparse

import bpy
import bmesh
from mathutils import Vector, Matrix


# ---------------------------------------------------------------------------
# 引数（Blender の '--' 以降のみ argparse へ）
# ---------------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(description="竹ドーム Blender ビルダ")
    ap.add_argument("--geo", required=True, help="幾何JSONパス")
    ap.add_argument("--out", default="", help="レンダリングPNG出力パス")
    ap.add_argument("--blend", default="", help=".blend 保存パス")
    ap.add_argument("--culm-d", type=float, default=0.10, help="竹外径[m]")
    ap.add_argument("--node-d", type=float, default=0.14, help="継手スフィア径[m]")
    ap.add_argument("--color-by", choices=["force", "none"], default="force")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", type=int, default=1400)
    ap.add_argument("--engine", default="BLENDER_EEVEE_NEXT")
    return ap.parse_args(argv)


# ---------------------------------------------------------------------------
# マテリアル
# ---------------------------------------------------------------------------
def make_material(name, rgba, roughness=0.55, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    # 表示名はUI言語で翻訳されるため bl_idname で取得（research の落とし穴）
    bsdf = next(n for n in mat.node_tree.nodes
                if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = rgba          # RGBA(linear)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bsdf.inputs:                 # 4.x の名称
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
    return mat


# ---------------------------------------------------------------------------
# ジオメトリ構築（bmesh で高速に1メッシュへ統合）
# ---------------------------------------------------------------------------
def cylinder_geo(bm, p1, p2, radius, segments=10):
    """p1-p2 間に円柱ジオメトリを bmesh へ追加。"""
    p1, p2 = Vector(p1), Vector(p2)
    vec = p2 - p1
    length = vec.length
    if length < 1e-9:
        return
    mid = (p1 + p2) * 0.5
    quat = vec.to_track_quat("Z", "Y")          # 局所+Zを方向ベクトルへ
    mat = Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
    geom = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius, radius2=radius, depth=length)
    verts = geom["verts"]
    bmesh.ops.transform(bm, matrix=mat, verts=verts)


def sphere_geo(bm, center, radius, subdiv=2):
    geom = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)),
                        verts=geom["verts"])


def build_object(name, build_fn, material):
    """build_fn(bm) で bmesh を構築 → メッシュオブジェクト化しマテリアル付与。"""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build_fn(bm)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    # スムーズシェード
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


# ---------------------------------------------------------------------------
# シーン
# ---------------------------------------------------------------------------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                  bpy.data.lights):
        for b in list(block):
            block.remove(b)


def setup_camera_and_light(center, size):
    # カメラ
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    loc = Vector(center) + Vector((size * 1.6, -size * 1.9, size * 1.25))
    cam.location = loc
    direction = Vector(center) + Vector((0, 0, size * 0.15)) - loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    bpy.context.scene.camera = cam            # ← オブジェクトを設定（必須）

    # 太陽光
    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (0.9, 0.2, 0.6)
    bpy.context.collection.objects.link(sun)
    # 補助エリアライト。照度 ∝ energy/距離² なので energy を size² でスケールし
    # モデル寸法に依らず一定の明るさに保つ。さらに中心へ向ける。
    area_data = bpy.data.lights.new("Fill", type="AREA")
    area_data.size = size * 2
    area_data.energy = 25.0 * size * size       # 照度をスケール不変に
    area = bpy.data.objects.new("Fill", area_data)
    area.location = Vector(center) + Vector((-size, size, size * 2))
    aim = Vector(center) - area.location
    area.rotation_mode = "QUATERNION"
    area.rotation_quaternion = aim.to_track_quat("-Z", "Y")  # 構造へ向ける
    bpy.context.collection.objects.link(area)

    # ワールド背景
    world = bpy.data.worlds.new("World") if not bpy.data.worlds else bpy.data.worlds[0]
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.03, 0.04, 0.06, 1.0)
        bg.inputs["Strength"].default_value = 0.6


def setup_ground(center, size, mat):
    bpy.ops.mesh.primitive_plane_add(size=size * 6,
                                     location=(center[0], center[1], 0.0))
    ground = bpy.context.active_object
    ground.data.materials.append(mat)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]
    members = geo["members"]
    supports = set(geo.get("supports", []))
    axial = geo.get("axial", None)

    clear_scene()

    # マテリアル
    mat_bamboo = make_material("Bamboo", (0.33, 0.42, 0.12, 1.0), 0.5)
    mat_comp = make_material("Compression", (0.10, 0.62, 0.68, 1.0), 0.45)  # シアン
    mat_tens = make_material("Tension", (0.85, 0.52, 0.13, 1.0), 0.45)      # アンバー
    mat_joint = make_material("Joint", (0.12, 0.10, 0.08, 1.0), 0.7)
    mat_support = make_material("Support", (0.25, 0.70, 0.45, 1.0), 0.6)
    mat_ground = make_material("Ground", (0.06, 0.07, 0.09, 1.0), 0.9)

    crad = args.culm_d / 2.0
    nrad = args.node_d / 2.0

    # 部材: 色分け（force）の場合は圧縮/引張で別オブジェクトに分けて統合
    if args.color_by == "force" and axial is not None:
        comp_idx = [m for m in range(len(members)) if axial[m] < 0]
        tens_idx = [m for m in range(len(members)) if axial[m] >= 0]

        def build_comp(bm):
            for m in comp_idx:
                i, j = members[m]
                cylinder_geo(bm, nodes[i], nodes[j], crad)

        def build_tens(bm):
            for m in tens_idx:
                i, j = members[m]
                cylinder_geo(bm, nodes[i], nodes[j], crad)

        build_object("Members_Compression", build_comp, mat_comp)
        build_object("Members_Tension", build_tens, mat_tens)
    else:
        def build_all(bm):
            for (i, j) in members:
                cylinder_geo(bm, nodes[i], nodes[j], crad)
        build_object("Members", build_all, mat_bamboo)

    # 継手スフィア（支点とそれ以外で別マテリアル）
    def build_joints(bm):
        for k in range(len(nodes)):
            if k not in supports:
                sphere_geo(bm, nodes[k], nrad)

    def build_supports(bm):
        for k in supports:
            sphere_geo(bm, nodes[k], nrad * 1.3)

    build_object("Joints", build_joints, mat_joint)
    build_object("Supports", build_supports, mat_support)

    # シーン範囲
    import math
    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    setup_ground(center, size, mat_ground)
    setup_camera_and_light(center, size)

    # レンダー設定
    scn = bpy.context.scene
    scn.render.engine = args.engine
    scn.render.resolution_x = args.res
    scn.render.resolution_y = int(args.res * 0.62)
    scn.render.image_settings.file_format = "PNG"
    if args.engine == "CYCLES":
        scn.cycles.samples = args.samples
    else:
        try:
            scn.eevee.taa_render_samples = args.samples
        except AttributeError as e:   # API名変更を握り潰さず可視化
            print(f"[warn] taa_render_samples を設定できません: {e}")

    # .blend 保存
    if args.blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[blend] saved -> {args.blend}")

    # レンダリング
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        scn.render.filepath = os.path.abspath(args.out)
        bpy.ops.render.render(write_still=True)
        print(f"[render] saved -> {args.out}")

    n_obj = len(bpy.context.scene.objects)
    print(f"[done] {len(members)} 部材 / {len(nodes)} 節点 / {n_obj} オブジェクト")


if __name__ == "__main__":
    main()
