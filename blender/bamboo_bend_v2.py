"""
bamboo_bend_v2.py — 竹のしなり物理シミュレーション v2

真っ直ぐな竹の中央を引き上げて、弧を描くしなり挙動を物理アニメ化。
- 竹 = 長い細棒メッシュ（多セグメント）
- Cloth物理 + 両端Pin + 中央フック（時間で上に動かす）
- 中央が上に動くと竹がしなって弧になる
- 力を抜くと復元（元に戻る）→ 復元力の可視化

#### 実行
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/bamboo_bend_v2.py -- \
    --out output/sim/bend_v2_ --blend output/sim/bend_v2.blend --frames 120 --animate
"""
import sys, os, math, argparse
import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/sim/bend_v2.png")
    ap.add_argument("--blend", default="")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--length", type=float, default=10.0)
    ap.add_argument("--diameter", type=float, default=0.06)
    ap.add_argument("--rise", type=float, default=2.5, help="中央の最大持ち上げ高さ[m]")
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
    b.inputs["Base Color"].default_value = (0.18, 0.22, 0.12, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    return mat


def create_long_bamboo(name, length, diameter, segments=40, ring_segs=8):
    """X方向に真っ直ぐな長い竹を生成（X=-L/2 から L/2）"""
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
            bm.verts.new(Vector((x, y, z + 0.2)))    # 少し浮かす
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


def setup_cloth(obj, segments, ring_segs):
    """竹に Cloth + 両端Pin + 中央Pin (アニメで動く)"""
    # 頂点グループ: 両端Pin
    vg_pin = obj.vertex_groups.new(name="Pinned")
    end1 = list(range(ring_segs))
    end2 = list(range(segments * ring_segs, (segments + 1) * ring_segs))
    vg_pin.add(end1 + end2, 1.0, "REPLACE")
    # 中央Pin（Hook用）
    vg_mid = obj.vertex_groups.new(name="Mid")
    mid_seg = segments // 2
    mid_verts = list(range(mid_seg * ring_segs, (mid_seg + 1) * ring_segs))
    vg_mid.add(mid_verts, 1.0, "REPLACE")
    # Cloth
    cm = obj.modifiers.new("Cloth", type="CLOTH")
    cs = cm.settings
    cs.quality = 25
    cs.mass = 0.3
    cs.tension_stiffness = 80
    cs.compression_stiffness = 80
    cs.shear_stiffness = 50
    cs.bending_stiffness = 25      # 竹の曲げ剛性（しなる感じ）
    cs.tension_damping = 8
    cs.bending_damping = 0.5
    cs.vertex_group_mass = "Pinned"   # Pinned 群を固定
    return cm, mid_verts


def add_hook_to_mid(obj, mid_verts, controller):
    """中央の頂点を Empty に Hook接続。Empty を動かすと中央が引っ張られる。"""
    # Hook modifier
    hook = obj.modifiers.new("Hook_Mid", type="HOOK")
    hook.object = controller
    hook.vertex_indices_set(mid_verts)
    hook.strength = 1.0


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0, 0, -9.81)

    mat_bamboo = make_bamboo_mat()
    mat_ground = make_ground_mat()

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=args.length * 2, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # 竹を1本だけ（中央をしならせる検証）
    me, segs, rsegs = create_long_bamboo("Bamboo", args.length, args.diameter,
                                          segments=40, ring_segs=8)
    bamboo = bpy.data.objects.new("Bamboo", me)
    bpy.context.collection.objects.link(bamboo)
    bamboo.data.materials.append(mat_bamboo)
    for p in bamboo.data.polygons:
        p.use_smooth = True

    # 中央コントローラ Empty を作成
    bpy.ops.object.empty_add(type="SPHERE", location=(0, 0, 0.2))
    controller = bpy.context.active_object
    controller.name = "MidController"
    controller.empty_display_size = 0.3

    # Cloth設定（Hookより先）
    cm, mid_verts = setup_cloth(bamboo, segs, rsegs)

    # Hook追加（Clothの後で評価される）
    add_hook_to_mid(bamboo, mid_verts, controller)

    # アニメーション: コントローラが時間とともに上に上がる→竹がしなる
    if args.animate:
        # フレーム1: 中央が地面付近
        controller.location = (0, 0, 0.2)
        controller.keyframe_insert("location", frame=1)
        # フレーム frames*0.5: 中央が最大高さ（しなって弧）
        controller.location = (0, 0, args.rise)
        controller.keyframe_insert("location", frame=int(args.frames * 0.5))
        # フレーム frames*0.7: そのまま
        controller.keyframe_insert("location", frame=int(args.frames * 0.7))
        # フレーム frames: 元に戻す（復元力可視化）
        controller.location = (0, 0, 0.2)
        controller.keyframe_insert("location", frame=args.frames)
        # 補間をBEZIERに
        for fc in controller.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    # ベイク
    print("[bend2] baking cloth simulation ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)

    # カメラ
    cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d)
    bpy.context.collection.objects.link(cam)
    loc = Vector((args.length * 0.4, -args.length * 0.8, args.rise * 1.2))
    cam.location = loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (Vector((0, 0, args.rise * 0.4)) - loc).to_track_quat("-Z", "Y")
    sc.camera = cam
    # ライト
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun); so.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(so)
    # 空
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.68, 0.82, 1.0)
    bg.inputs["Strength"].default_value = 0.6

    # ビューポート マテリアル表示
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
        print(f"[bend2] blend saved -> {args.blend}")

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
            print(f"[bend2] done -> {glob.glob(args.out + '*.mp4')}")
        else:
            sc.render.image_settings.file_format = "PNG"
            sc.frame_set(args.frames // 2)
            sc.render.filepath = os.path.abspath(args.out)
            bpy.ops.render.render(write_still=True)
            print(f"[bend2] rendered -> {args.out}")


if __name__ == "__main__":
    main()
