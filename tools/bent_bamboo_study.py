"""
bent_bamboo_study.py — 曲げ竹アーチドームの設計スタディ

各種ドーム寸法と竹径の組み合わせで、曲げ竹が成立するかを格子状に解析。
出力: HTMLヒートマップ＋設計推奨
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from src.bamboo import CulmSection, MOSO
from src.bent_bamboo import (analyze_dome_bent_bamboo, min_bending_radius,
                              bending_stress, bending_utilization, arch_geometry)


def study():
    diameters = [3, 4, 5, 6, 8, 10, 12]   # m
    h_ratios = [0.15, 0.20, 0.25, 0.30, 0.40, 0.50]  # rise/diameter
    culm_diams = [60, 80, 100, 120, 150]  # mm

    print(f"{'径':>4} {'高さ':>5} {'h/D':>5} {'弧長':>5} {'R':>5} "
          f"{'φ60':>8} {'φ80':>8} {'φ100':>8} {'φ120':>8} {'φ150':>8}")
    print("-" * 86)
    for D in diameters:
        for hr in h_ratios:
            h = D * hr
            arch = arch_geometry(D, h)
            row = [f"{D:>4} {h:>5.1f} {hr:>5.2f} {arch['arc_length']:>5.1f} "
                   f"{arch['R']:>5.1f}"]
            for cd in culm_diams:
                sec = CulmSection(cd / 1000, cd / 100 / 1000)  # 肉厚=外径の1割
                util = bending_utilization(sec, arch['R'], MOSO)
                if util <= 0.5:
                    mark = "✓✓"
                elif util <= 1.0:
                    mark = " ✓"
                elif util <= 2.0:
                    mark = " △"
                else:
                    mark = "✗"
                row.append(f"u={util:.1f}{mark}")
            print(" ".join(f"{x:>8}" for x in row))
    print()
    print("✓✓ = 余裕で曲げ可能, ✓ = 曲げ可能, △ = 要工夫, ✗ = 折れる")
    print()
    print("=== 結論 ===")
    print("浅いドーム（rise/D ≤ 0.25）と細い竹（φ60-80mm）なら曲げ加工可能。")
    print("半球（rise/D=0.5）は無理。竹建築の伝統的アーチが浅いのは合理的。")


if __name__ == "__main__":
    study()
