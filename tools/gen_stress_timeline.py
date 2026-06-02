"""
gen_stress_timeline.py — 時系列の各部材利用率データJSONを生成

snow_sim.simulate_snow を呼んで、雪が徐々に積もる過程の各部材の利用率を
JSONに保存。Blender(stress_animation.py)で時系列色付けに使う。

実行:
  python3 tools/gen_stress_timeline.py \
    --intensity 8 --dt 1.5 --max-hr 100 \
    --out output/sim/stress_timeline.json
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.geometry import geodesic_dome
from src.bamboo import CulmSection, MOSO
from src.snow_sim import simulate_snow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frequency", type=int, default=3)
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--height-ratio", type=float, default=0.5)
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--wall-t", type=float, default=0.010)
    ap.add_argument("--joint-eff", type=float, default=0.6)
    ap.add_argument("--intensity", type=float, default=8.0, help="降雪強度 cm/時")
    ap.add_argument("--dt", type=float, default=1.5, help="時間刻み[時間]")
    ap.add_argument("--max-hr", type=float, default=120.0)
    ap.add_argument("--rho-snow", type=float, default=300.0)
    ap.add_argument("--wind-drift", type=float, default=0.35)
    ap.add_argument("--out", default="output/sim/stress_timeline.json")
    args = ap.parse_args()

    section = CulmSection(args.culm_d, args.wall_t)
    geo = geodesic_dome(args.frequency, args.radius, args.height_ratio)
    geo["_area"] = section.area
    sim = simulate_snow(geo, section, MOSO, joint_efficiency=args.joint_eff,
                        intensity_cm_per_hr=args.intensity, dt_hr=args.dt,
                        max_hr=args.max_hr, rho_snow=args.rho_snow,
                        wind_drift=args.wind_drift)

    print(f"フレーム数: {len(sim['frames'])}")
    if sim["collapse_hr"]:
        print(f"⚠ 崩壊検出: t={sim['collapse_hr']:.0f}時間")

    data = dict(
        n_frames=len(sim["frames"]),
        n_members=len(geo["members"]),
        collapse_hr=sim["collapse_hr"],
        frames=[dict(
            t_hr=float(f["t_hr"]),
            max_util=float(f["max_util"]),
            crown_depth_cm=float(f["crown_depth_cm"]),
            mean_depth_cm=float(f["mean_depth_cm"]),
            member_utils=f["member_utils"].tolist(),
        ) for f in sim["frames"]],
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(data, f)
    print(f"生成: {args.out}")
    print(f"最終 t={sim['frames'][-1]['t_hr']:.0f}h "
          f"クラウン{sim['frames'][-1]['crown_depth_cm']:.0f}cm "
          f"最大利用率{sim['frames'][-1]['max_util']:.2f}")


if __name__ == "__main__":
    main()
