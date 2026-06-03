"""
bamboo_simple_bend.py — 竹のしなり可視化（シンプル・確実）

物理シミュなし。キーフレームでメッシュ頂点を動かして「真っ直ぐ→弧→戻る」を
表現。確実に動くシンプルな見せ方。

#### 実行
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_simple_bend.py -- \
    --out output/sim/simple_bend_ --blend output/sim/simple_bend.blend --animate
"""
import sys, os, math, argparse
import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/sim/simple_bend.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--length", type=float, default=10.0)
    ap.add_argument("--diameter", type=float, default=0.08)
    ap.add_argument("--max-rise", type=float, default=3.0)
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


def make_ground_mat():
    mat = bpy.data.materials.new("Ground"); mat.use_nodes = True
    b = principled(mat)
    b.inputs["Base Color"].default_value = (0.20, 0.25, 0.12, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    return mat


def create_straight_bamboo(name, length, diameter, segments=30, ring_segs=8):
    """X軸方向に真っ直ぐな竹を生成（後でshape keyで弧に変形）"""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    radius = diameter / 2
    half = length / 2
    for seg in range(segments + 1):
        t = seg / segments
        x = -half + length * t
        for ring in range(ring_segs):
            ang = 2 * math.pi * ring / ring_segs
            y = math.cos(ang) * radius
            z = math.sin(ang) * radius
            bm.verts.new(Vector((x, y, z + 0.3)))   # 地面少し上
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


def add_arc_shape_key(obj, segments, ring_segs, length, max_rise, diameter):
    """直線竹に「弧」のシェイプキーを追加。値0=直線、1=弧。"""
    # Basis（直線）作成
    obj.shape_key_add(name="Basis", from_mix=False)
    # 弧のシェイプキー
    arc = obj.shape_key_add(name="Arc", from_mix=False)
    half = length / 2
    rise = max_rise
    # 弧の幾何
    R = (rise**2 + half**2) / (2 * rise)
    half_angle = math.asin(half / R)
    radius = diameter / 2
    for seg in range(segments + 1):
        t = seg / segments
        # 直線位置: x = -half + length*t
        x_straight = -half + length * t
        # 弧位置: 角度補間
        ang = -half_angle + 2 * half_angle * t
        x_arc = R * math.sin(ang)
        z_arc = rise - R + R * math.cos(ang)
        # 接線方向（円弧）
        tx = math.cos(ang)
        tz = -math.sin(ang)
        # 直線時の接線は X方向
        for ring in range(ring_segs):
            a = 2 * math.pi * ring / ring_segs
            cos_a = math.cos(a)
            sin_a = math.sin(a)
            # 弧での頂点位置: 中心 + 接線に直交する円環
            # 接線(tx,0,tz)に直交: side=(0,1,0), normal=(-tz,0,tx)
            side = Vector((0, 1, 0))
            normal = Vector((-tz, 0, tx))
            center = Vector((x_arc, 0, z_arc + 0.3))
            offset = side * cos_a * radius + normal * sin_a * radius
            target = center + offset
            arc.data[seg * ring_segs + ring].co = target


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames

    mat_bamboo = make_bamboo_mat()
    mat_ground = make_ground_mat()

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=args.length * 2, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 真っ直ぐな竹を作成
    me, segs, rsegs = create_straight_bamboo(
        "Bamboo", args.length, args.diameter, segments=30, ring_segs=8)
    bamboo = bpy.data.objects.new("Bamboo", me)
    bpy.context.collection.objects.link(bamboo)
    bamboo.data.materials.append(mat_bamboo)
    for p in bamboo.data.polygons:
        p.use_smooth = True

    # 弧シェイプキー追加
    add_arc_shape_key(bamboo, segs, rsegs, args.length, args.max_rise, args.diameter)

    # アニメ: 0→1→1→0 で直線→弧→保持→復元
    if args.animate:
        kb = bamboo.data.shape_keys.key_blocks["Arc"]
        f1, f2, f3, f4 = 1, int(args.frames * 0.35), int(args.frames * 0.7), args.frames
        kb.value = 0.0; kb.keyframe_insert("value", frame=f1)
        kb.value = 1.0; kb.keyframe_insert("value", frame=f2)
        kb.value = 1.0; kb.keyframe_insert("value", frame=f3)
        kb.value = 0.05; kb.keyframe_insert("value", frame=f4)  # 復元時のしなり残し
        # BEZIER補間
        for fc in bamboo.data.shape_keys.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    # カメラ（横から見て、しなりがよく見える）
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((args.length * 0.3, -args.length * 0.7, args.max_rise * 0.8))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((0, 0, args.max_rise * 0.5)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.5
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
        print(f"[simple] blend saved -> {args.blend}")

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
            print(f"[simple] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(int(args.frames * 0.5))
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[simple] rendered -> {args.out}")


if __name__ == "__main__":
    main()
