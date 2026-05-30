"""
bake_mpm.py — MPM雪シミュレーションを実行し、フレーム毎の粒子位置を .ply に書き出す

実行（venv-mpm のPythonで）:
  .venv-mpm/bin/python tools/bake_mpm.py --frames 80 --particles 200000 \
      --substeps 200 --arch cpu --out output/sim/mpm

各フレームを binary .ply（実寸[m]・Z-up）で出力。Blender側(blender/render_mpm.py)で
表面化してレンダリングする。フレーム数=レンダリング枚数、substeps=各枚の内部ステップ。
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import taichi as ti                                  # noqa: E402
from src.mpm_snow import MPMSnow                      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=80)
    ap.add_argument("--substeps", type=int, default=200)
    ap.add_argument("--particles", type=int, default=200_000)
    ap.add_argument("--grid", type=int, default=128)
    ap.add_argument("--emit-per-frame", type=int, default=4000)
    ap.add_argument("--emit-until", type=float, default=0.85,
                    help="この割合のフレームまで降雪を続ける")
    ap.add_argument("--arch", default="cpu", choices=["cpu", "metal"])
    ap.add_argument("--sticky", action="store_true",
                    help="ドームを粘着衝突に（既定はスリップ=急斜面で滑落）")
    ap.add_argument("--rho", type=float, default=400.0)
    ap.add_argument("--theta-c", type=float, default=2.5e-2)
    ap.add_argument("--theta-s", type=float, default=7.5e-3)
    ap.add_argument("--xi", type=float, default=10.0)
    ap.add_argument("--out", default="output/sim/mpm")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    sim = MPMSnow(n_grid=args.grid, max_particles=args.particles, arch=args.arch,
                  rho=args.rho, theta_c=args.theta_c, theta_s=args.theta_s, xi=args.xi,
                  dome_sticky=args.sticky)
    print(f"MPM雪 bake: grid={args.grid} 最大粒子={args.particles} arch={args.arch} "
          f"dt={sim.dt} θc={args.theta_c} θs={args.theta_s} ξ={args.xi}")

    emit_until = int(args.frames * args.emit_until)
    cap = int(args.particles * 0.98)
    t0 = time.time()
    for frame in range(args.frames):
        if frame < emit_until and sim.n_active[None] < cap:
            sim.emit(args.emit_per_frame)
        for _ in range(args.substeps):
            sim.substep()
        pos = sim.positions_world().astype(np.float32)
        # binary .ply で書き出し
        w = ti.tools.PLYWriter(num_vertices=len(pos))
        w.add_vertex_pos(pos[:, 0], pos[:, 1], pos[:, 2])
        w.export_frame(frame, os.path.join(args.out, "snow.ply"))
        if frame % 10 == 0 or frame == args.frames - 1:
            el = time.time() - t0
            print(f"  frame {frame:3d}/{args.frames}  粒子{sim.n_active[None]:7d}  "
                  f"z[{pos[:,2].min():.2f},{pos[:,2].max():.2f}]m  "
                  f"{el:.0f}s ({el/(frame+1):.2f}s/frame)")
    # 最終位置も .npy で（プレビュー用）
    np.save(os.path.join(args.out, "final.npy"), sim.positions_world().astype(np.float32))
    print(f"完了 {time.time()-t0:.0f}s  → {args.out}/snow_*.ply ({args.frames}枚)")


if __name__ == "__main__":
    main()
