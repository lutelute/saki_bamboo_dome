"""
bamboo_softbody.py — 竹のしなり物理（Soft Body）

竹の本質（しなやか・カーブ可能・復元力）を Blender Soft Body で物理シミュ。
Soft Body はバネ＋ゴール（原形維持力）で動作し、棒状弾性体に向く。

#### モデル
- 真っ直ぐな細長メッシュ（X方向、中央付近を細分化）
- Soft Body修飾子: spring stiffness, bending, goal で竹の物理
- 両端をPin（goal=1.0で固定）
- 中央を Empty で持ち上げ → しなりアーチ形成 → 離す → 復元

#### 実行
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_softbody.py -- \
    --out output/sim/sb_ --blend output/sim/sb.blend --animate --frames 150
"""
import sys, os, math, argparse
import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/sim/sb.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=150)
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


def create_long_rod(name, length, diameter, segments=40, ring_segs=6):
    """細長い棒メッシュ（Soft Body用）"""
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
            bm.verts.new(Vector((x, y, z + 0.3)))
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


def setup_softbody(obj, segments, ring_segs):
    """Soft Body設定: 両端をgoal=1で固定、その他はバネで結合"""
    # 頂点グループ: 両端を「Goal」群に
    vg = obj.vertex_groups.new(name="Goal")
    end1 = list(range(ring_segs))
    end2 = list(range(segments * ring_segs, (segments + 1) * ring_segs))
    vg.add(end1 + end2, 1.0, "REPLACE")
    # 中央付近もリスト化（後でフックする頂点群）
    vg_mid = obj.vertex_groups.new(name="MidGroup")
    mid_seg = segments // 2
    mid_range = list(range(max(0, mid_seg - 1) * ring_segs,
                            min(segments + 1, mid_seg + 2) * ring_segs))
    vg_mid.add(mid_range, 1.0, "REPLACE")

    # Soft Body修飾子
    sb = obj.modifiers.new("Softbody", type="SOFT_BODY")
    s = sb.settings
    s.use_goal = True
    s.vertex_group_goal = "Goal"
    s.goal_default = 0.5            # 軽い形状維持力
    s.goal_min = 0.0
    s.goal_max = 1.0
    s.goal_spring = 0.7
    s.goal_friction = 5.0           # 揺れ抑制
    # バネ設定（穏やかな値で安定動作）
    s.use_edges = True
    s.pull = 0.9                    # 引張剛性
    s.push = 0.9                    # 圧縮剛性
    s.damping = 50                   # 減衰大（発散防止）
    s.bend = 5.0                    # 曲げ剛性
    s.use_stiff_quads = True
    s.use_self_collision = False
    s.mass = 1.0
    # 反復回数を増やして安定化
    s.step_min = 20
    s.step_max = 80
    return sb, mid_range


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0, 0, -9.81)

    mat_bamboo = make_bamboo_mat()
    mat_ground = make_ground_mat()

    bpy.ops.mesh.primitive_plane_add(size=args.length * 2, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 竹
    me, segs, rsegs = create_long_rod("Bamboo", args.length, args.diameter)
    bamboo = bpy.data.objects.new("Bamboo", me)
    bpy.context.collection.objects.link(bamboo)
    bamboo.data.materials.append(mat_bamboo)
    for p in bamboo.data.polygons:
        p.use_smooth = True

    # Soft Body
    sb, mid_verts = setup_softbody(bamboo, segs, rsegs)

    # 中央コントローラ（Empty）
    bpy.ops.object.empty_add(type="SPHERE", location=(0, 0, 0.3))
    controller = bpy.context.active_object
    controller.name = "MidController"
    controller.empty_display_size = 0.4

    # Hook で中央群を controller に接続
    hook = bamboo.modifiers.new("Hook_Mid", type="HOOK")
    hook.object = controller
    hook.vertex_indices_set(mid_verts)
    hook.strength = 1.0

    # アニメ: コントローラを上下に
    if args.animate:
        f1, f2, f3, f4 = 1, int(args.frames*0.35), int(args.frames*0.65), args.frames
        # 直線（地面付近）
        controller.location = (0, 0, 0.3)
        controller.keyframe_insert("location", frame=f1)
        # 最大アーチ
        controller.location = (0, 0, args.max_rise)
        controller.keyframe_insert("location", frame=f2)
        # 保持
        controller.keyframe_insert("location", frame=f3)
        # 復元（地面に戻す＝Hook外す代わりに移動）
        controller.location = (0, 0, 0.3)
        controller.keyframe_insert("location", frame=f4)
        for fc in controller.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    # ベイク
    print("[sb] baking soft body ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)

    # カメラ（横から、竹がよく見える位置）
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    # 真横やや上、十分離れた位置
    loc = Vector((0, -args.length * 1.5, args.max_rise * 0.5 + 1.0))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    # 中央(0,0,rise/2) を見る
    cam.rotation_quaternion = (Vector((0, 0, args.max_rise * 0.3)) - loc).to_track_quat("-Z", "Y")
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
        print(f"[sb] blend saved -> {args.blend}")

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
            print(f"[sb] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(int(args.frames * 0.4))
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[sb] rendered -> {args.out}")


if __name__ == "__main__":
    main()
