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
import json                                           # noqa: E402
import taichi as ti                                  # noqa: E402
from src.mpm_snow import MPMSnow                      # noqa: E402
from src.geometry import geodesic_dome                # noqa: E402
from src.bamboo import CULM_100, MOSO, G              # noqa: E402
from src.fem import TrussModel                        # noqa: E402
from src import design as Dz                          # noqa: E402
from src.loads import _face_geom                      # noqa: E402


class DomeCoupling:
    """MPM堆積雪の高さ→各節点積雪深→荷重→FEM→利用率→崩壊判定。"""

    def __init__(self, frequency=3, radius=4.0, section=CULM_100, material=MOSO,
                 joint_eff=0.6, rho_snow=300.0, p_vol_world=5.96e-5, snow_scale=1.0):
        self.geo = geodesic_dome(frequency, radius, 0.5)
        self.section, self.material, self.joint_eff = section, material, joint_eff
        self.rho_snow = rho_snow
        # 1粒子が代表する積雪体積[m³]（材料体積×サンプリング係数）
        self.vol_per_particle = p_vol_world * snow_scale
        nodes, faces = self.geo["nodes"], self.geo["faces"]
        plan, _, n, _ = _face_geom(nodes, faces)
        self.trib = np.zeros(len(nodes))            # 各節点の負担plan面積
        for fi, (a, b, c) in enumerate(faces):
            if n[fi, 2] > 0:
                for nd in (a, b, c):
                    self.trib[nd] += plan[fi] / 3.0
        self.trib = np.maximum(self.trib, 1e-3)
        self.upper_idx = np.where(nodes[:, 2] > 0.12 * radius)[0]   # 上部ドーム節点
        self.upper_xyz = nodes[self.upper_idx]
        self.band = 0.9 * self.geo["meta"]["member_len_mean"]       # 表面近傍帯[m]
        self.model = TrussModel(nodes, self.geo["members"], material.E,
                                section.area * np.ones(len(self.geo["members"])))
        for s in self.geo["supports"]:
            self.model.add_pin_support(s)
        self.Fdead = np.zeros(3 * len(nodes))       # 自重
        for m, (i, j) in enumerate(self.geo["members"]):
            half = 0.5 * section.weight_per_length(material) * self.geo["lengths"][m]
            self.Fdead[3 * i + 2] -= half
            self.Fdead[3 * j + 2] -= half

    def evaluate(self, pos):
        """粒子を最寄り上部節点へ割当→材料体積から局所積雪深→荷重→FEM→利用率。"""
        nodes = self.geo["nodes"]
        # 各粒子→最寄り上部節点(3D)。帯内(ドーム表面に乗った雪)のみ計上。
        K = len(self.upper_idx)
        d2 = ((pos[:, None, :] - self.upper_xyz[None, :, :]) ** 2).sum(2)  # (N,K)
        nearest = np.argmin(d2, axis=1)
        mind = np.sqrt(d2[np.arange(len(pos)), nearest])
        on_dome = mind < self.band
        counts = np.bincount(nearest[on_dome], minlength=K)
        depth = np.zeros(len(nodes))
        F = self.Fdead.copy()
        for kk, ni in enumerate(self.upper_idx):
            if counts[kk] > 0:
                depth[ni] = counts[kk] * self.vol_per_particle / self.trib[ni]
                F[3 * ni + 2] -= self.rho_snow * G * depth[ni] * self.trib[ni]
        self.model.set_load_vector(F)
        try:
            res = self.model.solve()
        except Exception:
            return dict(max_util=99.0, crown_depth=float(depth.max()), ok=False)
        u = Dz.max_utilization(self.geo, res["axial"], self.section,
                               self.material, 1.0, self.joint_eff)
        return dict(max_util=float(u), crown_depth=float(depth.max()), ok=(u <= 1.0))


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
    ap.add_argument("--rho-snow-load", type=float, default=300.0,
                    help="崩壊判定用の積雪密度[kg/m³]（荷重換算）")
    ap.add_argument("--snow-scale", type=float, default=6.0,
                    help="1粒子が代表する積雪体積の倍率（粗いサンプリングの補正）")
    ap.add_argument("--out", default="output/sim/mpm")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    sim = MPMSnow(n_grid=args.grid, max_particles=args.particles, arch=args.arch,
                  rho=args.rho, theta_c=args.theta_c, theta_s=args.theta_s, xi=args.xi,
                  dome_sticky=args.sticky)
    print(f"MPM雪 bake: grid={args.grid} 最大粒子={args.particles} arch={args.arch} "
          f"dt={sim.dt} θc={args.theta_c} θs={args.theta_s} ξ={args.xi}")

    p_vol_world = sim.p_vol * sim.world_scale ** 3
    coupling = DomeCoupling(rho_snow=args.rho_snow_load, p_vol_world=p_vol_world,
                            snow_scale=args.snow_scale)
    print(f"  崩壊判定: FEM連成（積雪密度{args.rho_snow_load:.0f}kg/m³, "
          f"1粒子={p_vol_world*args.snow_scale*1e3:.2f}L相当）")

    emit_until = int(args.frames * args.emit_until)
    cap = int(args.particles * 0.98)
    t0 = time.time()
    timeline = []
    collapse_frame = None
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
        # 崩壊判定（FEM連成）
        ev = coupling.evaluate(pos)
        if collapse_frame is None and ev["max_util"] >= 1.0:
            collapse_frame = frame
        timeline.append(dict(frame=frame, n=int(sim.n_active[None]),
                             max_util=ev["max_util"], crown_depth_cm=ev["crown_depth"] * 100))
        if frame % 10 == 0 or frame == args.frames - 1 or frame == collapse_frame:
            el = time.time() - t0
            mark = " ⚠崩壊" if frame == collapse_frame else ""
            print(f"  frame {frame:3d}/{args.frames}  粒子{sim.n_active[None]:7d}  "
                  f"クラウン積雪{ev['crown_depth']*100:5.0f}cm  利用率{ev['max_util']:.2f}{mark}  "
                  f"{el:.0f}s")
    np.save(os.path.join(args.out, "final.npy"), sim.positions_world().astype(np.float32))
    json.dump(dict(timeline=timeline, collapse_frame=collapse_frame,
                   n_frames=args.frames),
              open(os.path.join(args.out, "collapse.json"), "w"))
    if collapse_frame is not None:
        print(f"⚠ 崩壊検出: frame {collapse_frame}/{args.frames} "
              f"（クラウン積雪{timeline[collapse_frame]['crown_depth_cm']:.0f}cmで利用率1.0到達）")
    else:
        print(f"崩壊せず（最終利用率{timeline[-1]['max_util']:.2f}）")
    print(f"完了 {time.time()-t0:.0f}s  → {args.out}/snow_*.ply ({args.frames}枚) + collapse.json")


if __name__ == "__main__":
    main()
