"""
bamboo_vinyl_snow.py — 竹ビニールドーム(ビニール被覆あり)に雪が積もるシミュレーション

竹格子 + ビニール被覆（半透明膜）+ 雪冠 + 雪原 + 舞う雪のシーン。
ビニールはクロスではなくドーム表面を法線方向に少しオフセットした薄い膜として配置。
雪は物理モデル(snow_sim.accumulate_field)による各面の積雪深で駆動（融雪なし）。
徐々に積もるタイムラプス対応。

実行:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_vinyl_snow.py -- \
    --geo output/sim/dome_snow_scene.json \
    --out output/sim/bvs_ --blend output/sim/bvs.blend \
    --snow-m 1.0 --animate 120 --hours 14
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
    ap.add_argument("--out", default="output/sim/bvs.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--snow-m", type=float, default=1.0)
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--vinyl-offset", type=float, default=0.04,
                    help="ビニール膜のドーム面からのオフセット[m]")
    ap.add_argument("--res", type=int, default=1400)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--animate", type=int, default=0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--hours", type=float, default=14.0)
    ap.add_argument("--falling", type=int, default=4000)
    ap.add_argument("--collapse-defl", type=float, default=0.0,
                    help="後半でドームが潰れる(変形)演出の振幅[m]。0=無し")
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_mat(name, rgba, rough=0.5):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    return mat


def make_snow():
    mat = bpy.data.materials.new("Snow"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.93, 0.95, 1.0, 1.0)
    b.inputs["Roughness"].default_value = 0.45
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.25
        b.inputs["Subsurface Radius"].default_value = (0.4, 0.45, 0.6)
    return mat


def make_vinyl():
    """半透明ビニール: 透過＋ほんのり青白"""
    mat = bpy.data.materials.new("Vinyl"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.85, 0.92, 0.97, 1.0)
    b.inputs["Roughness"].default_value = 0.10
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.6
    if "IOR" in b.inputs:
        b.inputs["IOR"].default_value = 1.45
    b.inputs["Alpha"].default_value = 0.55
    mat.blend_method = "BLEND"
    mat.show_transparent_back = False
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
    if n.dot(cen) < 0:
        n = -n
    return n


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]; members = geo["members"]; faces = geo.get("faces", [])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 60
    sc.gravity = (0, 0, -9.81)

    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys)); top = max(zs)

    mat_bamboo = make_mat("Bamboo", (0.30, 0.40, 0.12, 1.0), 0.5)
    mat_vinyl = make_vinyl()
    mat_snow = make_snow()
    mat_ground_snow = make_snow()
    mat_grass = make_mat("Grass", (0.20, 0.34, 0.12, 1.0), 0.8)

    # 竹チューブ
    def bamboo_fn(bm):
        for (i, j) in members:
            cylinder_geo(bm, nodes[i], nodes[j], args.culm_d / 2.0)
    build_mesh_object("Bamboo", bamboo_fn, mat_bamboo)

    # 各節点の外向き法線（被覆と雪冠の両方で使う）
    n_nodes = len(nodes)
    nsum = [Vector((0, 0, 0)) for _ in range(n_nodes)]
    for f in faces:
        fn = face_normal(nodes, f)
        for idx in f:
            nsum[idx] += fn
    node_norm = [(v.normalized() if v.length > 1e-9 else Vector((0, 0, 1))) for v in nsum]

    # --- ビニール被覆膜（ドーム面を法線方向に offset した薄い膜） ---
    vinyl_verts = [Vector(nodes[i]) + node_norm[i] * args.vinyl_offset
                   for i in range(n_nodes)]
    vinyl_me = bpy.data.meshes.new("Vinyl")
    vinyl_me.from_pydata([tuple(v) for v in vinyl_verts], [], [tuple(f) for f in faces])
    vinyl_me.update()
    vinyl_obj = bpy.data.objects.new("Vinyl", vinyl_me)
    bpy.context.collection.objects.link(vinyl_obj)
    vinyl_obj.data.materials.append(mat_vinyl)
    for p in vinyl_obj.data.polygons:
        p.use_smooth = True
    # ソリッド化（膜に厚みを与えて二面ハイライト）
    sol = vinyl_obj.modifiers.new("Solidify", type="SOLIDIFY")
    sol.thickness = 0.008; sol.offset = 0

    # --- 雪冠（ビニールの上に積もる, 物理モデルの積雪深で駆動） ---
    depth_face = geo.get("snow_depth_per_face")
    d_node = [0.0] * n_nodes; cnt = [0] * n_nodes
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

    snow_verts = []
    keep_node = [False] * n_nodes
    for i in range(n_nodes):
        nrm = node_norm[i]
        beta = math.degrees(math.acos(max(-1, min(1, nrm.z))))
        # ビニール膜の上に乗る
        t = d_node[i] * max(0.15, math.cos(math.radians(beta))) + args.vinyl_offset
        snow_verts.append(Vector(nodes[i]) + nrm * t)
        keep_node[i] = d_node[i] > 0.05
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
        if args.animate > 0:
            basis = cap_obj.shape_key_add(name="Basis", from_mix=False)
            # ビニール面上から成長開始
            for i in range(n_nodes):
                basis.data[i].co = Vector(nodes[i]) + node_norm[i] * args.vinyl_offset
            snow_key = cap_obj.shape_key_add(name="Snow", from_mix=False)
            for i in range(n_nodes):
                snow_key.data[i].co = snow_verts[i]

    # --- 雪原（起伏のある雪の地面）＋雪だまり＋草原 ---
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120,
                                    size=size * 6, location=(cx, cy, 0))
    ground = bpy.context.active_object; ground.name = "SnowField"
    ground.data.materials.append(mat_ground_snow)
    tex = bpy.data.textures.new("Drift", type="CLOUDS"); tex.noise_scale = size * 0.5
    disp = ground.modifiers.new("Drift", type="DISPLACE")
    disp.texture = tex; disp.strength = args.snow_m * 0.6; disp.mid_level = 0.3
    sub = ground.modifiers.new("Sub", type="SUBSURF"); sub.levels = 1
    for p in ground.data.polygons:
        p.use_smooth = True
    bpy.ops.mesh.primitive_torus_add(location=(cx, cy, 0.0),
                                     major_radius=size * 0.5,
                                     minor_radius=args.snow_m * 0.5)
    drift = bpy.context.active_object; drift.name = "BaseDrift"
    drift.scale = (1, 1, 0.5); drift.data.materials.append(mat_ground_snow)
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_circle_add(radius=size * 5.5, fill_type="NGON",
                                      location=(cx, cy, -0.05))
    bpy.context.active_object.data.materials.append(mat_grass)

    # --- 舞う雪 ---
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.05,
                                          location=(0, 0, -500))
    grain = bpy.context.active_object; grain.name = "Flake"
    grain.data.materials.append(mat_snow)
    span = args.animate if args.animate > 0 else 60
    bpy.ops.mesh.primitive_plane_add(size=size * 4, location=(cx, cy, top + size * 1.2))
    em = bpy.context.active_object; em.name = "Sky"
    psm = em.modifiers.new("Fall", type="PARTICLE_SYSTEM")
    ps = em.particle_systems[psm.name].settings
    ps.count = args.falling
    # 降雪は最初から最後まで降り続ける（連続的）
    ps.frame_start, ps.frame_end = 1, span
    ps.lifetime = max(60, span)
    ps.physics_type = "NEWTON"; ps.normal_factor = 0.0; ps.factor_random = 0.3
    ps.mass = 0.02
    ps.effector_weights.gravity = 0.35       # しっかり降る
    ps.render_type = "OBJECT"; ps.instance_object = grain
    ps.particle_size = 0.8; ps.size_random = 0.6
    em.show_instancer_for_render = False
    # ランダムな初速で吹雪感
    ps.object_align_factor = (0.05, 0.05, -0.3)

    # --- 冬の空 ---
    world = bpy.data.worlds.new("Winter"); sc.world = world; world.use_nodes = True
    nt = world.node_tree; bg = nt.nodes.get("Background")
    try:
        sky = nt.nodes.new("ShaderNodeTexSky"); sky.sky_type = "NISHITA"
        sky.sun_elevation = math.radians(34); sky.sun_rotation = math.radians(40)
        nt.links.new(sky.outputs[0], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.5
    except Exception:
        bg.inputs["Color"].default_value = (0.55, 0.72, 0.92, 1.0)

    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 2.6
    sun.color = (0.95, 0.97, 1.0)
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = (math.radians(60), 0, math.radians(40))
    bpy.context.collection.objects.link(so)

    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size*1.7, cy - size*2.0, top*0.8 + size*0.2))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((cx, cy, top*0.45)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam

    # --- アニメ: 雪冠と地面と雪だまりが徐々に成長 ---
    animate = args.animate > 0
    if animate:
        N = args.animate
        sc.frame_start, sc.frame_end = 1, N
        full_thk = args.snow_m * 0.25
        full_disp = disp.strength

        def _set_interp(ad, interp="LINEAR"):
            if ad and ad.action:
                for fc in ad.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = interp
                        if interp == "BEZIER":
                            kp.handle_left_type = "AUTO_CLAMPED"
                            kp.handle_right_type = "AUTO_CLAMPED"

        # 雪冠の成長: 中間に1キーを追加して曲線的に（最初ゆっくり、後半急増）
        if cap_obj is not None and cap_obj.data.shape_keys \
                and "Snow" in cap_obj.data.shape_keys.key_blocks:
            kb = cap_obj.data.shape_keys.key_blocks["Snow"]
            mid_fr = int(N * 0.6)
            kb.value = 0.0; kb.keyframe_insert("value", frame=1)
            kb.value = 0.18; kb.keyframe_insert("value", frame=mid_fr)
            kb.value = 1.0; kb.keyframe_insert("value", frame=N)
            cap_solid.thickness = 0.0
            cap_solid.keyframe_insert("thickness", frame=1)
            cap_solid.thickness = full_thk * 0.18
            cap_solid.keyframe_insert("thickness", frame=mid_fr)
            cap_solid.thickness = full_thk
            cap_solid.keyframe_insert("thickness", frame=N)
            _set_interp(cap_obj.data.shape_keys.animation_data, "BEZIER")
        # 地面雪も曲線的
        disp.strength = 0.0; disp.keyframe_insert("strength", frame=1)
        disp.strength = full_disp * 0.2; disp.keyframe_insert("strength", frame=int(N*0.6))
        disp.strength = full_disp; disp.keyframe_insert("strength", frame=N)
        drift.scale = (1, 1, 0.0); drift.keyframe_insert("scale", frame=1)
        drift.scale = (1, 1, 0.1); drift.keyframe_insert("scale", frame=int(N*0.6))
        drift.scale = (1, 1, 0.5); drift.keyframe_insert("scale", frame=N)
        gb = principled(mat_ground_snow)
        for fr, col, rg in (
            (1, (0.22, 0.34, 0.13, 1.0), 0.8),
            (int(N*0.45), (0.55, 0.60, 0.55, 1.0), 0.6),
            (N, (0.93, 0.95, 1.0, 1.0), 0.45)):
            gb.inputs["Base Color"].default_value = col
            gb.inputs["Base Color"].keyframe_insert("default_value", frame=fr)
            gb.inputs["Roughness"].default_value = rg
            gb.inputs["Roughness"].keyframe_insert("default_value", frame=fr)
        _set_interp(mat_ground_snow.node_tree.animation_data, "BEZIER")
        for ob in (cap_obj, ground, drift):
            if ob:
                _set_interp(ob.animation_data, "BEZIER")

        # 潰れる演出: 最終付近でドーム頂部が下にたわむ
        if args.collapse_defl > 0:
            bamboo_obj = bpy.data.objects.get("Bamboo")
            vinyl_obj_ref = bpy.data.objects.get("Vinyl")
            for ob in (bamboo_obj, vinyl_obj_ref, cap_obj):
                if ob is None:
                    continue
                ob.scale = (1.0, 1.0, 1.0); ob.keyframe_insert("scale", frame=int(N*0.85))
                # 頂部が沈むイメージ: Z方向に少し圧縮
                ob.scale = (1.01, 1.01, 1.0 - args.collapse_defl/4.0)
                ob.keyframe_insert("scale", frame=N)
                _set_interp(ob.animation_data, "BEZIER")

    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res - args.res % 2
    sc.render.resolution_y = int(args.res*0.62)//2*2
    try:
        sc.eevee.taa_render_samples = args.samples
    except AttributeError:
        pass

    # ビューポートをマテリアル表示に
    for scr in bpy.data.screens:
        for ar in scr.areas:
            if ar.type == "VIEW_3D":
                for sp in ar.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "MATERIAL"

    if args.blend:
        sc.frame_set(sc.frame_start if animate else 45)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[bvs] blend saved -> {args.blend}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        if animate:
            sc.render.image_settings.file_format = "FFMPEG"
            sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
            sc.render.ffmpeg.constant_rate_factor = "HIGH"; sc.render.fps = args.fps
            sc.render.filepath = os.path.abspath(args.out)
            print(f"[bvs] rendering animation ({N}フレーム) ...")
            bpy.ops.render.render(animation=True)
            import glob
            print(f"[bvs] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(45)
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[bvs] rendered -> {args.out}")


if __name__ == "__main__":
    main()
