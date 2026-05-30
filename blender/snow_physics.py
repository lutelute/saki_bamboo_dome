"""
snow_physics.py — Blender 粒子物理による「雪がドームに積もる」シミュレーション＋mp4

ドーム殻(faces)を衝突面、竹(members)をチューブ表示し、上方から雪粒子を降らせて
ニュートン粒子＋Collisionで堆積させ、アニメーションを mp4 出力する。

実行（ヘッドレス）:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
      --python blender/snow_physics.py -- \
      --geo output/dome_geometry.json --out output/sim/snow_blender_ \
      --frames 120 --count 1500 --culm-d 0.10

API は Blender 4.5.3 で検証済み（research）:
  ニュートン粒子(physics_type='NEWTON', lifetime大, die_on_collision=False),
  Collision(damping/friction/stickiness=1, use_particle_kill=False),
  particle_size 小, use_size_deflect=True, integrator='VERLET', subframes 4,
  frame_set ループでベイク, EEVEE_NEXT + FFMPEG/H264, filepath は接頭辞。
"""
import sys
import os
import json
import argparse
import glob

import bpy
import bmesh
from mathutils import Vector, Matrix


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", required=True)
    ap.add_argument("--out", default="output/sim/snow_blender_")
    ap.add_argument("--blend", default="", help=".blend 保存パス（GUIで開く用）")
    ap.add_argument("--no-render", action="store_true", help="mp4レンダリングを省略")
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--count", type=int, default=1500)
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--res", type=int, default=1100)
    return ap.parse_args(argv)


def make_material(name, rgba, rough=0.5, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
    return mat


def cylinder_geo(bm, p1, p2, radius, seg=8):
    p1, p2 = Vector(p1), Vector(p2)
    vec = p2 - p1
    L = vec.length
    if L < 1e-9:
        return
    quat = vec.to_track_quat("Z", "Y")
    mat = Matrix.Translation((p1 + p2) * 0.5) @ quat.to_matrix().to_4x4()
    geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                                 radius1=radius, radius2=radius, depth=L)
    bmesh.ops.transform(bm, matrix=mat, verts=geom["verts"])


def build_mesh_object(name, build_fn, material):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new(); build_fn(bm); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def main():
    args = parse_args()
    geo = json.load(open(args.geo))
    nodes = geo["nodes"]
    members = geo["members"]
    faces = geo.get("faces", [])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, args.frames
    sc.gravity = (0.0, 0.0, -9.81)

    # 寸法
    xs = [n[0] for n in nodes]; ys = [n[1] for n in nodes]; zs = [n[2] for n in nodes]
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys))
    top = max(zs)

    mat_bamboo = make_material("Bamboo", (0.33, 0.42, 0.12, 1.0), 0.5)
    mat_shell = make_material("Shell", (0.20, 0.25, 0.32, 1.0), 0.7, alpha=0.18)
    mat_snow = make_material("Snow", (0.96, 0.97, 1.0, 1.0), 0.35)
    mat_ground = make_material("Ground", (0.06, 0.07, 0.09, 1.0), 0.9)

    # 竹チューブ
    def build_bamboo(bm):
        for (i, j) in members:
            cylinder_geo(bm, nodes[i], nodes[j], args.culm_d / 2.0)
    build_mesh_object("Bamboo", build_bamboo, mat_bamboo)

    # ドーム殻（衝突面）— faces から三角メッシュ
    shell_mesh = bpy.data.meshes.new("Shell")
    shell_mesh.from_pydata([tuple(n) for n in nodes], [],
                           [tuple(f) for f in faces])
    shell_mesh.update()
    shell = bpy.data.objects.new("Shell", shell_mesh)
    bpy.context.collection.objects.link(shell)
    shell.data.materials.append(mat_shell)
    shell.modifiers.new("Collision", type="COLLISION")
    cs = shell.collision
    cs.damping_factor = 1.0
    cs.friction_factor = 1.0
    cs.stickiness = 1.0           # 滑落を抑え堆積させる
    cs.permeability = 0.0
    cs.thickness_outer = 0.08
    cs.use_particle_kill = False

    # 雪粒子インスタンス（雪玉。見た目のサイズはこの球で決まる）
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.13,
                                          location=(0, 0, -1000))
    grain = bpy.context.active_object
    grain.name = "Grain"
    bpy.ops.object.shade_smooth()
    grain.data.materials.append(mat_snow)

    # 雪エミッタ（ドーム上方の平面）
    bpy.ops.mesh.primitive_plane_add(size=size * 1.1, location=(cx, cy, top + size * 0.5))
    emitter = bpy.context.active_object
    emitter.name = "SnowEmitter"
    psm = emitter.modifiers.new("Snow", type="PARTICLE_SYSTEM")
    ps = emitter.particle_systems[psm.name].settings
    ps.count = args.count
    ps.frame_start, ps.frame_end = 1, int(args.frames * 0.8)
    ps.lifetime = 100000
    ps.physics_type = "NEWTON"
    ps.integrator = "VERLET"
    ps.subframes = 4
    ps.timestep = 0.02
    ps.normal_factor = 0.0
    ps.factor_random = 0.05
    ps.mass = 0.05
    ps.particle_size = 0.06        # 衝突半径（小, 浮かないよう）
    ps.use_size_deflect = True
    ps.use_die_on_collision = False
    ps.use_rotations = False
    ps.emit_from = "FACE"
    ps.distribution = "RAND"
    ps.render_type = "OBJECT"
    ps.instance_object = grain      # 見た目は grain(φ26cm)で決まる
    ps.size_random = 0.4
    emitter.show_instancer_for_render = False   # エミッタ平面は描画しない

    # 地面
    bpy.ops.mesh.primitive_plane_add(size=size * 5, location=(cx, cy, 0))
    bpy.context.active_object.data.materials.append(mat_ground)

    # カメラ＋ライト
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    loc = Vector((cx + size * 1.5, cy - size * 1.8, top + size * 0.9))
    cam.location = loc
    direction = Vector((cx, cy, top * 0.5)) - loc
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    sc.camera = cam
    sun = bpy.data.lights.new("Sun", type="SUN"); sun.energy = 3.5
    sun_obj = bpy.data.objects.new("Sun", sun)
    sun_obj.rotation_euler = (0.9, 0.2, 0.5)
    bpy.context.collection.objects.link(sun_obj)
    world = bpy.data.worlds.new("W"); sc.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.04, 0.05, 0.07, 1)

    # ベイク（frame_set ループ＋point cache 凍結）
    print("[snow] baking physics ...")
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
    try:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.ptcache.bake_all(bake=True)
    except Exception as e:
        print(f"[snow] ptcache.bake_all skipped: {e}")

    # .blend 保存（GUIで開いて再生・編集できる）
    if args.blend:
        sc.frame_set(sc.frame_start)
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[snow] blend saved -> {args.blend}")

    if args.no_render:
        print("[snow] render skipped (--no-render)")
        return

    # レンダリング設定（mp4）
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = args.res
    sc.render.resolution_y = int(args.res * 0.62)
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.fps = 24
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sc.render.filepath = os.path.abspath(args.out)
    print("[snow] rendering animation ...")
    bpy.ops.render.render(animation=True)
    files = glob.glob(args.out + "*.mp4")
    print(f"[snow] done -> {files}")


if __name__ == "__main__":
    main()
