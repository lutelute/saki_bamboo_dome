"""
bamboo_bend_sim.py — 竹のしなり物理シミュレーション

長い竹を曲げてアーチを作り、復元力（プレストレス）で形状を保持する様子を
物理シミュレートする。

#### モデル
- 竹 = 細長い円柱メッシュ（多セグメント分割）
- Cloth物理: bending stiffness で曲げ剛性、structural stiffness で伸縮剛性
- 両端を Hook制約で位置固定 → 中央が自然に弧を描く
- 荷重（雪・風）を上から加えてしなり方を観察
- 真っ直ぐな状態と曲げた状態を比較

#### 実行
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_bend_sim.py -- \
    --out output/sim/bamboo_bend.png --blend output/sim/bamboo_bend.blend \
    --frames 100 --animate
"""
import sys, os, math, argparse
import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/sim/bamboo_bend.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--length", type=float, default=12.0, help="竹の長さ[m]")
    ap.add_argument("--diameter", type=float, default=0.08, help="竹の外径[m]")
    ap.add_argument("--span", type=float, default=8.0, help="アーチの径間[m]")
    ap.add_argument("--n-arches", type=int, default=6, help="アーチ本数")
    ap.add_argument("--snow-load", type=float, default=0.0,
                    help="頂部にかける荷重[N]（雪荷重シミュレート）")
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=64)
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_bamboo_mat():
    mat = bpy.data.materials.new("Bamboo"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.32, 0.45, 0.14, 1.0)
    b.inputs["Roughness"].default_value = 0.4
    return mat


def make_ground_mat():
    mat = bpy.data.materials.new("Ground"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.15, 0.20, 0.12, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    return mat


def create_bamboo_segment(name, p1, p2, radius, segments=20, ring_segs=8):
    """細長い円柱を多セグメントで生成（Cloth物理で曲がる）。"""
    p1, p2 = Vector(p1), Vector(p2)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    direction = (p2 - p1).normalized()
    length = (p2 - p1).length
    # 各セグメント環
    for seg in range(segments + 1):
        t = seg / segments
        center = p1 + (p2 - p1) * t
        # 円環を作る
        up = Vector((0, 0, 1)) if abs(direction.z) < 0.95 else Vector((1, 0, 0))
        side = direction.cross(up).normalized()
        local_up = direction.cross(side).normalized()
        for ring in range(ring_segs):
            ang = 2 * math.pi * ring / ring_segs
            offset = side * math.cos(ang) * radius + local_up * math.sin(ang) * radius
            bm.verts.new(center + offset)
    bm.verts.ensure_lookup_table()
    # 面を貼る
    for seg in range(segments):
        for ring in range(ring_segs):
            v0 = bm.verts[seg * ring_segs + ring]
            v1 = bm.verts[seg * ring_segs + (ring + 1) % ring_segs]
            v2 = bm.verts[(seg + 1) * ring_segs + (ring + 1) % ring_segs]
            v3 = bm.verts[(seg + 1) * ring_segs + ring]
            bm.faces.new([v0, v1, v2, v3])
    bm.normal_update()
    bm.to_mesh(me); bm.free()
    return me, segments, ring_segs


def setup_bamboo_cloth(obj, segments, ring_segs, end1, end2, snow_load_obj=None):
    """竹に Cloth物理を設定し、両端の節点を固定する。"""
    # 頂点グループ: 両端を pin する
    vg = obj.vertex_groups.new(name="Pinned")
    end1_verts = list(range(ring_segs))                  # 最初の環
    end2_verts = list(range(segments * ring_segs, (segments + 1) * ring_segs))  # 最後の環
    vg.add(end1_verts + end2_verts, 1.0, "REPLACE")
    # Cloth修飾子
    cm = obj.modifiers.new("Cloth", type="CLOTH")
    cs = cm.settings
    cs.quality = 20
    cs.mass = 0.3                       # 軽い
    cs.tension_stiffness = 80           # 伸縮はしにくい（軸方向に堅い）
    cs.compression_stiffness = 80
    cs.shear_stiffness = 50
    cs.bending_stiffness = 30           # 曲げ剛性（竹のしなり）
    cs.tension_damping = 10
    cs.bending_damping = 0.8
    cs.use_pressure = False
    cs.vertex_group_mass = "Pinned"     # pin 設定
    # 重力など
    cm.collision_settings.use_self_collision = False
    return cm


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0, 0, -9.81)

    mat_bamboo = make_bamboo_mat()
    mat_ground = make_ground_mat()

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=args.span * 3, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 複数アーチを放射状に配置（竹ドーム）
    bamboo_objects = []
    half_span = args.span / 2
    radius = args.diameter / 2
    for i in range(args.n_arches):
        angle = 2 * math.pi * i / args.n_arches
        p1 = Vector((half_span * math.cos(angle), half_span * math.sin(angle), 0.1))
        # 反対側
        p2 = Vector((-half_span * math.cos(angle), -half_span * math.sin(angle), 0.1))
        # 真っ直ぐな状態で生成
        me, segs, rsegs = create_bamboo_segment(
            f"Bamboo_{i}", p1, p2, radius, segments=30, ring_segs=8)
        ob = bpy.data.objects.new(f"Bamboo_{i}", me)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat_bamboo)
        for p in ob.data.polygons:
            p.use_smooth = True
        setup_bamboo_cloth(ob, segs, rsegs, p1, p2)
        bamboo_objects.append(ob)

    # 雪荷重シミュ用の球（中央に置く）
    if args.snow_load > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.5, location=(0, 0, args.span * 0.5))
        snow_ball = bpy.context.active_object
        snow_ball.name = "SnowLoad"
        snow_ball.data.materials.append(make_bamboo_mat())  # 白くしたいなら別マテリアル
        # rigid body設定
        bpy.ops.rigidbody.object_add()
        snow_ball.rigid_body.mass = args.snow_load / 9.81

    # ベイク（重力で竹がしなる）
    print("[bend] baking cloth simulation ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)

    # カメラ＋ライト
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((args.span * 1.5, -args.span * 1.5, args.span * 0.8))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((0, 0, args.span * 0.3)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(so)
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.5, 0.62, 0.75, 1.0)
    bg.inputs["Strength"].default_value = 0.6

    # ビューポートをマテリアル表示
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
        sc.eevee.taa_render_samples = args.samples
    except AttributeError:
        pass

    if args.blend:
        sc.frame_set(sc.frame_start if args.animate else sc.frame_end)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[bend] blend saved -> {args.blend}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        if args.animate:
            sc.render.image_settings.file_format = "FFMPEG"
            sc.render.ffmpeg.format = "MPEG4"
            sc.render.ffmpeg.codec = "H264"
            sc.render.ffmpeg.constant_rate_factor = "HIGH"
            sc.render.fps = 24
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(animation=True)
            import glob
            print(f"[bend] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(sc.frame_end)
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[bend] rendered -> {args.out}")


if __name__ == "__main__":
    main()
