"""
bamboo_bend_v3.py — 竹のしなり物理 v3（弧から始める、復元力アニメ）

最初から半円弧形に配置した竹アーチを、力を加えると変形し、力を抜くと
復元する挙動を物理シミュ。竹の本質（しなり＋復元力）を可視化。

#### モデル
- 弧状に配置した竹（Cloth修飾子）
- 両端Pin、それ以外は自由に動く
- 上から重り（Snowball）を落として変形させる
- 重りを除けて復元の様子を見る

#### 実行
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_bend_v3.py -- \
    --out output/sim/bend_v3_ --blend output/sim/bend_v3.blend --frames 150 --animate
"""
import sys, os, math, argparse
import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/sim/bend_v3.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--span", type=float, default=8.0, help="径間[m]")
    ap.add_argument("--rise", type=float, default=2.5, help="アーチ高さ[m]")
    ap.add_argument("--diameter", type=float, default=0.08)
    ap.add_argument("--n-arches", type=int, default=6)
    ap.add_argument("--load-mass", type=float, default=200.0, help="重り[kg]")
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=48)
    return ap.parse_args(argv)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def make_bamboo_mat():
    mat = bpy.data.materials.new("Bamboo"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.40, 0.55, 0.15, 1.0)
    b.inputs["Roughness"].default_value = 0.35
    return mat


def make_snow_mat():
    mat = bpy.data.materials.new("Snow"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.93, 0.95, 1.0, 1.0)
    b.inputs["Roughness"].default_value = 0.5
    return mat


def make_ground_mat():
    mat = bpy.data.materials.new("Ground"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.18, 0.22, 0.12, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    return mat


def create_arch_bamboo(name, span, rise, diameter, rot_z=0.0,
                        segments=40, ring_segs=8):
    """半円弧アーチを描く竹を生成（XZ面、Y軸周りに回転）"""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    radius = diameter / 2
    # アーチの幾何: 円弧として近似（R, 中心C）
    R = (rise**2 + (span / 2)**2) / (2 * rise)
    cx = 0
    cz = rise - R
    half_angle = math.asin((span / 2) / R)
    cos_rot = math.cos(rot_z)
    sin_rot = math.sin(rot_z)
    for seg in range(segments + 1):
        t = seg / segments
        # 角度 -half_angle から +half_angle
        ang = -half_angle + 2 * half_angle * t
        cx_local = cx + R * math.sin(ang)
        cz_local = cz + R * math.cos(ang)
        # 中心位置を回転（Z軸周り）
        cx_world = cos_rot * cx_local
        cy_world = sin_rot * cx_local
        cz_world = cz_local
        # 接線方向（円弧の接線）
        tx_local = math.cos(ang)
        tz_local = -math.sin(ang)
        tx_world = cos_rot * tx_local
        ty_world = sin_rot * tx_local
        tz_world = tz_local
        tangent = Vector((tx_world, ty_world, tz_world))
        # 接線に直交する2方向（局所up=Z, 局所side=接線×Z）
        up_world = Vector((0, 0, 1))
        side = tangent.cross(up_world).normalized()
        normal = side.cross(tangent).normalized()
        center = Vector((cx_world, cy_world, cz_world))
        for ring in range(ring_segs):
            a = 2 * math.pi * ring / ring_segs
            offset = side * math.cos(a) * radius + normal * math.sin(a) * radius
            bm.verts.new(center + offset)
    bm.verts.ensure_lookup_table()
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


def setup_arch_cloth(obj, segments, ring_segs):
    vg_pin = obj.vertex_groups.new(name="Pinned")
    end1 = list(range(ring_segs))
    end2 = list(range(segments * ring_segs, (segments + 1) * ring_segs))
    vg_pin.add(end1 + end2, 1.0, "REPLACE")
    cm = obj.modifiers.new("Cloth", type="CLOTH")
    cs = cm.settings
    cs.quality = 20
    cs.mass = 0.5
    cs.tension_stiffness = 200       # 軸方向すごく堅い
    cs.compression_stiffness = 200
    cs.shear_stiffness = 100
    cs.bending_stiffness = 80        # しっかり弾力（高めの曲げ剛性）
    cs.tension_damping = 5
    cs.bending_damping = 0.5
    cs.vertex_group_mass = "Pinned"
    cm.collision_settings.use_collision = True
    cm.collision_settings.use_self_collision = False
    cm.collision_settings.distance_min = 0.02
    cm.collision_settings.collision_quality = 4
    return cm


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0, 0, -9.81)

    mat_bamboo = make_bamboo_mat()
    mat_ground = make_ground_mat()
    mat_snow = make_snow_mat()

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=args.span * 3, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 複数アーチを放射状に
    for i in range(args.n_arches):
        rot = math.pi * i / args.n_arches
        me, segs, rsegs = create_arch_bamboo(
            f"Arch_{i}", args.span, args.rise, args.diameter, rot_z=rot,
            segments=30, ring_segs=8)
        ob = bpy.data.objects.new(f"Arch_{i}", me)
        bpy.context.collection.objects.link(ob)
        ob.data.materials.append(mat_bamboo)
        for p in ob.data.polygons:
            p.use_smooth = True
        setup_arch_cloth(ob, segs, rsegs)

    # 重り球（雪荷重として上から落として変形→除く）
    if args.load_mass > 0:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.8, location=(0, 0, args.rise + 3))
        ball = bpy.context.active_object
        ball.name = "SnowLoad"
        ball.data.materials.append(mat_snow)
        for p in ball.data.polygons:
            p.use_smooth = True
        bpy.ops.rigidbody.object_add()
        ball.rigid_body.mass = args.load_mass
        ball.rigid_body.collision_shape = "SPHERE"
        if args.animate:
            # 後半でボールを離す（位置を持ち上げて消す）
            ball.location = (0, 0, args.rise + 3)
            ball.keyframe_insert("location", frame=1)
            ball.location = (0, 0, args.rise + 3)
            ball.keyframe_insert("location", frame=int(args.frames * 0.6))
            # 後半: ボールを横に逃がす
            ball.location = (args.span * 2, 0, args.rise + 5)
            ball.keyframe_insert("location", frame=args.frames)

    # アーチを衝突体としても登録
    for i in range(args.n_arches):
        ob = bpy.data.objects[f"Arch_{i}"]
        ob.modifiers.new("Collision", type="COLLISION")

    # ベイク
    print("[bend3] baking simulation ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)

    # カメラ（横から）
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((args.span * 1.2, -args.span * 1.4, args.rise * 1.0))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((0, 0, args.rise * 0.5)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(so)
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.68, 0.82, 1.0)
    bg.inputs["Strength"].default_value = 0.6

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
        sc.frame_set(1)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[bend3] blend saved -> {args.blend}")

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
            print(f"[bend3] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(args.frames // 2)
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[bend3] rendered -> {args.out}")


if __name__ == "__main__":
    main()
