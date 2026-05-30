"""
snow_scene.py — 豪雪の雪景色シーン（ドーム＋雪原に雪が積もった色彩シーン）

粒子の点ではなく「雪の層」をメッシュで作る:
  ・ドームに積もる雪冠   = ドーム殻を法線方向に積雪厚ぶん外側へオフセットした白い層
                           （屋根形状係数 μ_b で急斜面は薄く、クラウンは厚い）
  ・周囲の雪原(草原)     = 起伏のある白い雪の地面（Displaceでドリフト）＋ドーム基部の雪だまり
  ・舞う雪               = 雰囲気づけの降雪パーティクル
  ・色・空・光           = 冬の青空ワールド＋太陽光、竹は緑、雪は白
1晩に約1m積もる豪雪地帯（福井）を想定。

実行（ヘッドレス）:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
      --python blender/snow_scene.py -- \
      --geo output/sim/dome_geo_for_blender.json --out output/sim/snow_scene.png \
      --blend output/sim/snow_scene.blend --snow-m 1.0 --culm-d 0.10
検証: Blender 4.5.3 LTS。
"""
import sys
import os
import json
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
    ap.add_argument("--out", default="output/sim/snow_scene.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--snow-m", type=float, default=1.0, help="積雪深[m]（クラウン, 最終）")
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--res", type=int, default=1500)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--falling", type=int, default=1500, help="舞う雪の粒子数")
    ap.add_argument("--animate", type=int, default=0,
                    help="アニメフレーム数(0=静止画)。徐々に積もるタイムラプス")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--hours", type=float, default=14.0, help="一晩の時間(表示用)")
    return ap.parse_args(argv)


# --- マテリアル ---
def principled(mat):
    return next(n for n in mat.node_tree.nodes
               if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_snow(name="Snow"):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.93, 0.95, 1.0, 1.0)
    b.inputs["Roughness"].default_value = 0.45
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.25      # やわらかい雪
    if "Subsurface Radius" in b.inputs:
        b.inputs["Subsurface Radius"].default_value = (0.4, 0.45, 0.6)
    return mat


def make_simple(name, rgba, rough=0.5):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    return mat


# --- ジオメトリ補助 ---
def cylinder_geo(bm, p1, p2, radius, seg=8):
    p1, p2 = Vector(p1), Vector(p2)
    vec = p2 - p1; L = vec.length
    if L < 1e-9:
        return
    q = vec.to_track_quat("Z", "Y")
    m = Matrix.Translation((p1 + p2) * 0.5) @ q.to_matrix().to_4x4()
    g = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=radius, radius2=radius, depth=L)
    bmesh.ops.transform(bm, matrix=m, verts=g["verts"])


def build_mesh_object(name, build_fn, material, smooth=True):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); build_fn(bm)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def face_normal(nodes, f):
    a, b, c = (Vector(nodes[i]) for i in f)
    n = (b - a).cross(c - a)
    if n.length < 1e-12:
        return Vector((0, 0, 1))
    n.normalize()
    cen = (a + b + c) / 3
    if n.dot(cen) < 0:                      # 外向き（原点=ドーム中心から外へ）
        n = -n
    return n


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]; members = geo["members"]; faces = geo.get("faces", [])
    node_disp = geo.get("node_disp")               # 満積雪時の節点変位[m]（FEM連成）
    defl_scale = geo.get("defl_scale", 0.0)        # 変形誇張倍率
    use_defl = (node_disp is not None) and (args.animate > 0) and (defl_scale > 0)

    def disp_of(i):                                # 誇張後の節点変位ベクトル
        if use_defl:
            d = node_disp[i]
            return Vector((d[0], d[1], d[2])) * defl_scale
        return Vector((0, 0, 0))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 60

    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys)); top = max(zs)

    mat_bamboo = make_simple("Bamboo", (0.30, 0.40, 0.12, 1.0), 0.5)
    mat_snow = make_snow("Snow")
    mat_ground_snow = make_snow("GroundSnow")
    mat_grass = make_simple("Grass", (0.20, 0.34, 0.12, 1.0), 0.8)

    # --- 竹チューブ（緑） ---
    def bamboo(bm):
        for (i, j) in members:
            cylinder_geo(bm, nodes[i], nodes[j], args.culm_d / 2.0)
    bamboo_obj = build_mesh_object("Bamboo", bamboo, mat_bamboo)

    # --- ドームに積もる雪冠（物理モデル snow_sim の積雪深で駆動・融雪なし） ---
    # snow_depth_per_face は src.snow_sim.accumulate_field の出力（鉛直積雪深[m]）。
    # 無ければ μ_b による近似にフォールバック。
    n_nodes = len(nodes)
    nsum = [Vector((0, 0, 0)) for _ in range(n_nodes)]
    for f in faces:
        fn = face_normal(nodes, f)
        for idx in f:
            nsum[idx] += fn
    node_norm = [(v.normalized() if v.length > 1e-9 else Vector((0, 0, 1))) for v in nsum]

    depth_face = geo.get("snow_depth_per_face")    # 物理モデル由来（あれば）
    # 各節点の鉛直積雪深（隣接面の平均）
    d_node = [0.0] * n_nodes
    cnt = [0] * n_nodes
    if depth_face is not None:
        for fi, f in enumerate(faces):
            for idx in f:
                d_node[idx] += depth_face[fi]; cnt[idx] += 1
        d_node = [d / c if c else 0.0 for d, c in zip(d_node, cnt)]
    else:
        for i in range(n_nodes):
            beta = math.degrees(math.acos(max(-1, min(1, node_norm[i].z))))
            mu_b = math.sqrt(max(0.0, math.cos(math.radians(1.5 * beta)))) if beta < 60 else 0.0
            d_node[i] = args.snow_m * mu_b

    # 満積雪状態の雪冠頂点 = 変形後の節点 + 法線方向の層厚（FEM連成）
    snow_verts = []
    keep_node = [False] * n_nodes
    for i in range(n_nodes):
        nrm = node_norm[i]
        beta = math.degrees(math.acos(max(-1, min(1, nrm.z))))
        t = d_node[i] * max(0.15, math.cos(math.radians(beta)))   # 法線方向の層厚
        snow_verts.append(Vector(nodes[i]) + disp_of(i) + nrm * t)
        keep_node[i] = d_node[i] > 0.05            # 積もる節点
    snow_faces = [f for f in faces if all(keep_node[i] for i in f)]
    cap_obj = cap_solid = None
    if snow_faces:
        me = bpy.data.meshes.new("SnowCap")
        me.from_pydata([tuple(v) for v in snow_verts], [], [tuple(f) for f in snow_faces])
        me.update()
        cap_obj = bpy.data.objects.new("SnowCap", me)
        bpy.context.collection.objects.link(cap_obj)
        cap_obj.data.materials.append(mat_snow)
        for p in cap_obj.data.polygons:
            p.use_smooth = True
        cap_solid = cap_obj.modifiers.new("Solidify", type="SOLIDIFY")
        cap_solid.thickness = args.snow_m * 0.25; cap_solid.offset = 1.0
        # アニメ用シェイプキー: Basis=雪なし(ドーム面), Snow=満積雪
        if args.animate > 0:
            basis = cap_obj.shape_key_add(name="Basis", from_mix=False)
            for i in range(n_nodes):
                basis.data[i].co = Vector(nodes[i])      # 雪ゼロ位置
            snow_key = cap_obj.shape_key_add(name="Snow", from_mix=False)
            for i in range(n_nodes):
                snow_key.data[i].co = snow_verts[i]      # 満積雪位置

    # --- 雪原の地面（起伏のある白い雪 ＋ ドーム基部の雪だまり） ---
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120,
                                    size=size * 6, location=(cx, cy, 0))
    ground = bpy.context.active_object; ground.name = "SnowField"
    ground.data.materials.append(mat_ground_snow)
    # 雪面の自然な起伏（Displace + Clouds）
    tex = bpy.data.textures.new("Drift", type="CLOUDS")
    tex.noise_scale = size * 0.5
    disp = ground.modifiers.new("Drift", type="DISPLACE")
    disp.texture = tex; disp.strength = args.snow_m * 0.6; disp.mid_level = 0.3
    sub = ground.modifiers.new("Sub", type="SUBSURF"); sub.levels = 1
    for p in ground.data.polygons:
        p.use_smooth = True
    # ドーム基部の雪だまり（リング状のメタっぽい盛り上がり=トーラス）
    bpy.ops.mesh.primitive_torus_add(location=(cx, cy, 0.0),
                                     major_radius=size * 0.5, minor_radius=args.snow_m * 0.5)
    drift = bpy.context.active_object; drift.name = "BaseDrift"
    drift.scale = (1, 1, 0.5); drift.data.materials.append(mat_ground_snow)
    bpy.ops.object.shade_smooth()
    # 草が少しのぞく（雪原=草原の名残）: 遠景に低い緑の円盤
    bpy.ops.mesh.primitive_circle_add(radius=size * 5.5, fill_type="NGON",
                                      location=(cx, cy, -0.05))
    bpy.context.active_object.data.materials.append(mat_grass)

    # --- 舞う雪（雰囲気） ---
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.05, location=(0, 0, -500))
    grain = bpy.context.active_object; grain.name = "Flake"
    grain.data.materials.append(mat_snow)
    bpy.ops.mesh.primitive_plane_add(size=size * 3, location=(cx, cy, top + size))
    em = bpy.context.active_object; em.name = "Sky"
    _span = args.animate if args.animate > 0 else 60
    psm = em.modifiers.new("Fall", type="PARTICLE_SYSTEM")
    ps = em.particle_systems[psm.name].settings
    ps.count = args.falling; ps.frame_start, ps.frame_end = 1, _span
    ps.lifetime = max(40, _span // 2)
    ps.physics_type = "NEWTON"; ps.normal_factor = 0.0; ps.factor_random = 0.1
    ps.mass = 0.01; ps.effector_weights.gravity = 0.15      # ゆっくり舞う
    ps.render_type = "OBJECT"; ps.instance_object = grain
    ps.particle_size = 0.6; ps.size_random = 0.5
    em.show_instancer_for_render = False

    # --- 冬の青空ワールド ---
    world = bpy.data.worlds.new("Winter"); sc.world = world; world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    try:                                            # Sky Texture（Nishita）でリアルな空
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "NISHITA"; sky.sun_elevation = math.radians(34)
        sky.sun_rotation = math.radians(40)
        nt.links.new(sky.outputs[0], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.5
    except Exception:
        bg.inputs["Color"].default_value = (0.55, 0.72, 0.92, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    # --- 太陽光（冬の斜光・やや寒色） ---
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 2.6
    sun.color = (0.95, 0.97, 1.0)
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (math.radians(60), 0, math.radians(40))
    bpy.context.collection.objects.link(so)

    # --- カメラ（雪原に佇むドームを見上げ気味に） ---
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size * 1.7, cy - size * 2.0, top * 0.8 + size * 0.2))
    cam.location = loc
    direction = Vector((cx, cy, top * 0.45)) - loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    sc.camera = cam

    # --- アニメ: 徐々に積もる（融雪なし＝単調増加）。物理モデルの積雪深に比例 ---
    animate = args.animate > 0
    if animate:
        N = args.animate
        sc.frame_start, sc.frame_end = 1, N
        full_thk = args.snow_m * 0.25
        full_disp = disp.strength

        def _lin(ad):     # アクションのキーを線形補間に
            if ad and ad.action:
                for fc in ad.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"

        # 竹ドームのたわみ（FEM連成）: 各頂点を最寄り節点の変位で移動するシェイプキー
        if use_defl:
            node_vecs = [Vector(n) for n in nodes]
            disp_vecs = [disp_of(i) for i in range(n_nodes)]
            bb = bamboo_obj.shape_key_add(name="Basis", from_mix=False)
            dk = bamboo_obj.shape_key_add(name="Sag", from_mix=False)
            for vi, v in enumerate(bamboo_obj.data.vertices):
                co = v.co
                # 最寄り節点（ブルートフォース, 節点数は少ない）
                best, bd = 0, 1e18
                for ni, nv in enumerate(node_vecs):
                    dd = (co - nv).length_squared
                    if dd < bd:
                        bd = dd; best = ni
                dk.data[vi].co = co + disp_vecs[best]
            dk.value = 0.0; dk.keyframe_insert("value", frame=1)
            dk.value = 1.0; dk.keyframe_insert("value", frame=N)
            _lin(bamboo_obj.data.shape_keys.animation_data)

        # 雪冠シェイプキー 0→1（フレーム1=雪ゼロ→Nで満積雪）
        if cap_obj is not None and cap_obj.data.shape_keys and \
                "Snow" in cap_obj.data.shape_keys.key_blocks:
            kb = cap_obj.data.shape_keys.key_blocks["Snow"]
            kb.value = 0.0; kb.keyframe_insert("value", frame=1)
            kb.value = 1.0; kb.keyframe_insert("value", frame=N)
            cap_solid.thickness = 0.0; cap_solid.keyframe_insert("thickness", frame=1)
            cap_solid.thickness = full_thk; cap_solid.keyframe_insert("thickness", frame=N)
            _lin(cap_obj.data.shape_keys.animation_data)   # シェイプキーは別アクション
        # 地面の積雪（Displace強度 0→満）
        disp.strength = 0.0; disp.keyframe_insert("strength", frame=1)
        disp.strength = full_disp; disp.keyframe_insert("strength", frame=N)
        # 基部の雪だまり（Z方向に成長）
        drift.scale = (1, 1, 0.0); drift.keyframe_insert("scale", frame=1)
        drift.scale = (1, 1, 0.5); drift.keyframe_insert("scale", frame=N)
        # 地面の色 草原(緑)→雪(白)、粗さも変化
        gb = principled(mat_ground_snow)
        for fr, col, rg in ((1, (0.22, 0.34, 0.13, 1.0), 0.8),
                            (N, (0.93, 0.95, 1.0, 1.0), 0.45)):
            gb.inputs["Base Color"].default_value = col
            gb.inputs["Base Color"].keyframe_insert("default_value", frame=fr)
            gb.inputs["Roughness"].default_value = rg
            gb.inputs["Roughness"].keyframe_insert("default_value", frame=fr)
        _lin(mat_ground_snow.node_tree.animation_data)
        for ob in (cap_obj, ground, drift):
            if ob:
                _lin(ob.animation_data)

    # --- レンダー設定（H264は幅高さとも偶数が必要） ---
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res - (args.res % 2)
    sc.render.resolution_y = int(args.res * 0.62) // 2 * 2
    try:
        sc.eevee.taa_render_samples = args.samples
    except AttributeError:
        pass

    if args.blend:
        sc.frame_set(sc.frame_start if animate else 45)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[scene] blend saved -> {args.blend}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        if animate:
            sc.render.image_settings.file_format = "FFMPEG"
            sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
            sc.render.ffmpeg.constant_rate_factor = "HIGH"; sc.render.fps = args.fps
            sc.render.filepath = os.path.abspath(args.out)
            print(f"[scene] rendering animation ({N}フレーム, 一晩{args.hours:.0f}h→1m) ...")
            bpy.ops.render.render(animation=True)
            import glob
            print(f"[scene] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(45)
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[scene] rendered -> {args.out}")


if __name__ == "__main__":
    main()
