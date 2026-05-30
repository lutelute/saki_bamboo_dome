#!/usr/bin/env python3
"""
run_sim.py — 竹ドーム シミュレーション統合実行

  1. 積雪堆積シミュレーション（高さ場×FEM連成）→ mp4 ＋ インタラクティブHTML
  2. 風CFD（格子ボルツマン法 D2Q9）→ 渦度・流速 mp4
  3. 方向性風圧 cp(θ) 3Dヒートマップ → HTML
  4. Blender 粒子雪シミュレーション → mp4（インストールされていれば）

使い方:
    python3 run_sim.py                    # 全部
    python3 run_sim.py --no-blender       # Blender省略
    python3 run_sim.py --no-cfd           # CFD省略（重いので）
    python3 run_sim.py --frequency 3 --radius 4
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.geometry import geodesic_dome
from src.bamboo import CulmSection, MOSO
from src.analysis import analyze
from src.snow_sim import simulate_snow, summary as snow_summary
from src.sim_viz import (wind_cfd_animation_mpl, snow_animation_mpl,
                         snow_animation_plotly, wind_pressure_plotly)
from src.export import export_geometry_json

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
OUT = "output/sim"


def banner(t):
    print("\n" + "─" * 64 + f"\n▶ {t}\n" + "─" * 64)


def run_snow(args, section):
    banner("1. 積雪堆積シミュレーション（高さ場 × FEM連成）")
    geo = geodesic_dome(args.frequency, args.radius, 0.5)
    geo["_area"] = section.area
    sim = simulate_snow(geo, section, MOSO, joint_efficiency=args.joint_eff,
                        intensity_cm_per_hr=args.snowfall, dt_hr=3.0,
                        max_hr=200.0, rho_snow=300.0, wind_drift=0.35)
    print(snow_summary(sim))
    p1 = snow_animation_plotly(sim, f"{OUT}/snow_sim.html")
    print(f"  生成: {p1}")
    try:
        p2 = snow_animation_mpl(sim, f"{OUT}/snow_sim.mp4")
        print(f"  生成: {p2}")
    except Exception as e:
        print(f"  mp4スキップ: {e}")
    return sim


def run_wind(args, rep):
    banner("3. 方向性風圧 cp(θ) 3Dヒートマップ")
    p = wind_pressure_plotly(rep, f"{OUT}/wind_pressure.html", q_wind=730.0, wind_az_deg=0.0)
    print(f"  生成: {p}")


def run_cfd(args):
    banner("2. 風CFD（格子ボルツマン法 D2Q9）")
    from src.wind_cfd import LBM2D, dome_mask
    nx, ny = 320, 140
    R = 40
    solid = dome_mask(nx, ny, cx=95, radius=R, ground=3)
    sim = LBM2D(nx, ny, solid, u_in=0.07, Re=180, L=2 * R)
    print(f"  格子 {nx}×{ny}, τ={sim.tau:.3f}, Re={sim.Re}  計算中...")
    t0 = time.time()
    # 渦放出を誘発する一時擾乱
    frames = []
    n_steps, warmup, rec = 9000, 2500, 90
    for s in range(n_steps):
        sim.uy_in = (0.05 * sim.u_in) if s < 500 else 0.0
        sim.step()
        if s >= warmup and (s - warmup) % rec == 0:
            frames.append(sim.fields())
    print(f"  {n_steps}ステップ {time.time()-t0:.0f}s, {len(frames)}フレーム")
    p = wind_cfd_animation_mpl(frames, solid, f"{OUT}/wind_cfd.mp4", u_in=sim.u_in)
    print(f"  生成: {p}")


def run_blender_snow(args, rep):
    banner("4. Blender 粒子雪シミュレーション")
    if not os.path.exists(BLENDER):
        print("  Blender 未検出 → スキップ")
        return
    gj = export_geometry_json(rep, f"{OUT}/dome_geo_for_blender.json", "D+S")
    cmd = [BLENDER, "--background", "--factory-startup",
           "--python", "blender/snow_physics.py", "--",
           "--geo", os.path.abspath(gj), "--out", os.path.abspath(f"{OUT}/snow_blender_"),
           "--frames", "100", "--count", "1400", "--culm-d", str(args.culm_d)]
    print("  Blender 粒子物理を実行中（数分）...")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print("  タイムアウト（600s）"); return
    for line in r.stdout.splitlines():
        if any(k in line for k in ("[snow]", "Error", "Traceback")):
            print("   " + line)
    if r.returncode != 0:
        print("  失敗（stderr末尾）:\n   " + "\n   ".join(r.stderr.splitlines()[-6:]))
    else:
        print(f"  Blender 完了 ({time.time()-t0:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frequency", type=int, default=3)
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--culm-d", type=float, default=0.10)
    ap.add_argument("--wall-t", type=float, default=0.010)
    ap.add_argument("--joint-eff", type=float, default=0.6)
    ap.add_argument("--snowfall", type=float, default=4.0, help="降雪強度 cm/時")
    ap.add_argument("--no-blender", action="store_true")
    ap.add_argument("--no-cfd", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    section = CulmSection(args.culm_d, args.wall_t)
    rep = analyze(frequency=args.frequency, radius=args.radius, section=section,
                  joint_efficiency=args.joint_eff)

    run_snow(args, section)
    if not args.no_cfd:
        run_cfd(args)
    run_wind(args, rep)
    if not args.no_blender:
        run_blender_snow(args, rep)

    banner("完了")
    print(f"  成果物は {OUT}/ に出力されました。")
    print(f"  積雪アニメ:   open {OUT}/snow_sim.html / {OUT}/snow_sim.mp4")
    print(f"  風CFD:        open {OUT}/wind_cfd.mp4")
    print(f"  風圧cp分布:   open {OUT}/wind_pressure.html")


if __name__ == "__main__":
    main()
