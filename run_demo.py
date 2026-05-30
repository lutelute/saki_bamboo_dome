#!/usr/bin/env python3
"""
run_demo.py — 竹ジオデシックドーム 統合DEMO（ワンコマンド）

  1. 幾何生成（測地線格子シェル）
  2. 3DトラスFEM 構造解析（自重・積雪・風）
  3. 設計照査（許容応力・座屈・積雪耐力）＋ レポート出力
  4. 可視化（matplotlib PNG / plotly インタラクティブHTML）
  5. エクスポート（Blender用JSON / GLB・OBJメッシュ）
  6. Blender ヘッドレスレンダリング（インストールされていれば）
  7. 設計スタディ（福井の積雪に耐える構成を自動探索）

使い方:
    python3 run_demo.py                       # 既定（v=3, R=4m, φ100竹）
    python3 run_demo.py --frequency 4 --radius 5
    python3 run_demo.py --no-blender          # Blenderレンダ省略
    python3 run_demo.py --no-study            # 設計スタディ省略
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.bamboo import BambooMaterial, CulmSection, MOSO
from src.analysis import analyze, format_report
from src import loads as L
from src.viz_mpl import plot_dome, plot_geometry
from src.viz_plotly import build_interactive
from src.dashboard import build_dashboard
from src.export import export_geometry_json, export_mesh

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
OUT = "output"


def banner(t):
    print("\n" + "─" * 64 + f"\n▶ {t}\n" + "─" * 64)


def run_blender(geo_json, png, blend, culm_d):
    if not os.path.exists(BLENDER):
        print("  Blender 未検出 → レンダリングをスキップ "
              "（output/dome_geometry.json から手動で実行可）")
        return False
    cmd = [BLENDER, "--background", "--factory-startup",
           "--python", "blender/build_dome.py", "--",
           "--geo", geo_json, "--out", png, "--blend", blend,
           "--culm-d", str(culm_d), "--color-by", "force",
           "--samples", "48", "--res", "1500"]
    print("  $ " + " ".join(cmd[:2]) + " ... --python blender/build_dome.py -- ...")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print("  Blender タイムアウト（300s）")
        return False
    for line in r.stdout.splitlines():
        if any(k in line for k in ("[blend]", "[render]", "[done]", "Error", "Traceback")):
            print("   " + line)
    if r.returncode != 0:
        print("  Blender 失敗（stderr 末尾）:")
        print("   " + "\n   ".join(r.stderr.splitlines()[-8:]))
        return False
    print(f"  Blender 完了 ({time.time()-t0:.0f}s)")
    return os.path.exists(png)


def design_study(args):
    """福井の設計積雪(4.2 kN/m²)に対し利用率≦1となる構成を探索。"""
    banner("設計スタディ：福井の積雪に耐える構成の探索")
    q_target = L.SNOW_FUKUI
    print(f"  目標：設計積雪 {q_target/1e3:.1f} kN/m²（福井市・多雪区域）で D+S 利用率 ≤ 1.0\n")
    print(f"  {'構成':<28}{'最大利用率':>10}{'積雪耐力':>12}{'総竹長':>9}{'判定':>6}")
    print("  " + "-" * 67)
    candidates = [
        ("v3 φ100×t10 η0.6", 3, CulmSection(0.10, 0.010), 0.6),
        ("v3 φ125×t12 η0.6", 3, CulmSection(0.125, 0.012), 0.6),
        ("v4 φ100×t10 η0.6", 4, CulmSection(0.10, 0.010), 0.6),
        ("v4 φ125×t12 η0.7", 4, CulmSection(0.125, 0.012), 0.7),
        ("v4 φ150×t15 η0.8", 4, CulmSection(0.150, 0.015), 0.8),
    ]
    best = None
    for label, freq, sec, eta in candidates:
        rep = analyze(frequency=freq, radius=args.radius,
                      height_ratio=args.height, section=sec,
                      joint_efficiency=eta)
        s = rep["case_results"]["D+S"]["check"]["summary"]
        qf = rep["capacity"]["q_fail"]
        ok = s["max_utilization"] <= 1.0
        mark = "✓OK" if ok else "✗NG"
        print(f"  {label:<28}{s['max_utilization']:>10.2f}"
              f"{qf/1e3:>9.2f}kN  {rep['geo']['meta']['total_length']:>6.0f}m  {mark:>6}")
        if ok and best is None:
            best = (label, rep)
    print()
    if best:
        print(f"  ⇒ 最小で要求を満たす構成: 【{best[0]}】 "
              f"(積雪耐力 {best[1]['capacity']['q_fail']/1e3:.2f} kN/m²)")
    else:
        print("  ⇒ 候補内に適合構成なし。断面拡大・継手補強・節点追加を検討。")
    return best


def main():
    ap = argparse.ArgumentParser(description="竹ドーム統合DEMO")
    ap.add_argument("--frequency", type=int, default=3)
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--height", type=float, default=0.5, help="高さ/直径 比")
    ap.add_argument("--culm-d", type=float, default=0.10, help="竹外径[m]")
    ap.add_argument("--wall-t", type=float, default=0.010, help="竹肉厚[m]")
    ap.add_argument("--joint-eff", type=float, default=0.6, help="接合効率η")
    ap.add_argument("--no-blender", action="store_true")
    ap.add_argument("--no-study", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    section = CulmSection(args.culm_d, args.wall_t)

    banner("1–3. 構造解析")
    rep = analyze(frequency=args.frequency, radius=args.radius,
                  height_ratio=args.height, section=section,
                  joint_efficiency=args.joint_eff)
    print(format_report(rep))

    banner("4. 可視化（matplotlib / plotly）")
    p1 = plot_dome(rep, "D+S", f"{OUT}/dome_force_util.png")
    p2 = plot_geometry(rep, f"{OUT}/dome_geometry_view.png")
    p3 = build_interactive(rep, f"{OUT}/dome_interactive.html")
    p4 = build_dashboard(f"{OUT}/dome_dashboard.html",
                         radii=(1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
                         frequency=args.frequency, section=section,
                         height_ratio=args.height, joint_efficiency=args.joint_eff)
    for p in (p1, p2, p3, p4):
        print(f"  生成: {p}")

    banner("5. エクスポート（JSON / メッシュ）")
    gj = export_geometry_json(rep, f"{OUT}/dome_geometry.json", "D+S")
    print(f"  生成: {gj}")
    try:
        gm = export_mesh(rep, f"{OUT}/dome.glb")
        export_mesh(rep, f"{OUT}/dome.obj")
        print(f"  生成: {gm} / {OUT}/dome.obj")
    except Exception as e:
        print(f"  メッシュ書き出しスキップ: {e}")

    if not args.no_blender:
        banner("6. Blender ヘッドレスレンダリング")
        run_blender(os.path.abspath(gj), os.path.abspath(f"{OUT}/dome_render.png"),
                    os.path.abspath(f"{OUT}/dome.blend"), args.culm_d)

    if not args.no_study:
        design_study(args)

    banner("完了")
    print(f"  すべての成果物は {OUT}/ に出力されました。")
    print(f"  インタラクティブ3D: open {OUT}/dome_interactive.html")
    if os.path.exists(f"{OUT}/dome_render.png"):
        print(f"  Blenderレンダ:      open {OUT}/dome_render.png")


if __name__ == "__main__":
    main()
