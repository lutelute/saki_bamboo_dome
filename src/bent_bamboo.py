"""
bent_bamboo.py — 曲げ竹（active bending）による竹ドーム解析

竹の本質的な性質（しなやか・カーブ可能・復元力）を活かした構造モデル。
真っ直ぐな長い竹を曲げて配置し、復元力（プレストレス）で形状を保持する
**アクティブベンディング構造**を扱う。

#### 物理モデル
1. **曲げ応力**: σ = M·y/I = E·y/R（円弧の場合、Rは曲率半径）
2. **曲げ限界**: σ ≤ f_b,allow（許容曲げ応力 ~ 35 MPa for Moso）
3. **最小曲率半径**: R_min = E·D/(2·f_b,allow)
4. **プレストレス**: 曲げ加工時の復元モーメント = E·I/R（節点を絞めるだけで形状ロック）

#### 設計フロー
- 屋根アーチの曲率半径 R を入力
- 竹の長さ L、外径 D で許容曲げ半径 R_min を計算
- R >= R_min なら成立、そうでなければ径を細くするか別経路へ
- 真っ直ぐな竹をしならせた状態の応力を計算

参考: ICD/ITKE Pavilion (2010-2014), Lightweight Structures (Bunger et al.)
"""
from __future__ import annotations
import numpy as np

try:
    from .bamboo import BambooMaterial, CulmSection, MOSO, CULM_100
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.bamboo import BambooMaterial, CulmSection, MOSO, CULM_100


def min_bending_radius(section: CulmSection, material: BambooMaterial = MOSO,
                       safety_factor: float = 2.0) -> float:
    """竹を折らずに曲げられる最小曲率半径 [m]。

    曲げ応力 σ = E·y_max/R ≤ f_b,allow
    → R_min = E·D/(2·f_b,allow·SF)

    安全率SF=2は実務で曲げ加工の余裕として一般的。
    """
    y_max = section.outer_d / 2.0
    f_allow = material.f_bending_mean / safety_factor
    return material.E * y_max / f_allow


def bending_stress(section: CulmSection, R: float,
                   material: BambooMaterial = MOSO) -> float:
    """曲率半径 R で曲げた竹の最大繊維応力 [Pa]。"""
    y_max = section.outer_d / 2.0
    return material.E * y_max / R


def bending_utilization(section: CulmSection, R: float,
                        material: BambooMaterial = MOSO) -> float:
    """曲げ応力の利用率（許容曲げに対する比）。"""
    sigma = bending_stress(section, R, material)
    return sigma / material.f_bending_mean


def restoring_moment(section: CulmSection, R: float,
                     material: BambooMaterial = MOSO) -> float:
    """曲げた竹が直線に戻ろうとする復元モーメント [N·m]。

    M = E·I/R
    これがプレストレスとして節点に伝わり、構造を保持する力になる。
    """
    return material.E * section.I / R


def arch_geometry(span: float, rise: float) -> dict:
    """円弧アーチの幾何（径間 span, 立ち上がり rise から R, 弧長を計算）。

    Returns: dict(R, arc_length, angle_rad)
    """
    if rise <= 0 or span <= 0:
        raise ValueError("span, rise > 0")
    R = (rise**2 + (span / 2)**2) / (2 * rise)
    half_angle = np.arcsin((span / 2) / R)
    arc_length = 2 * R * half_angle
    return dict(R=float(R), arc_length=float(arc_length),
                angle_rad=float(2 * half_angle))


def can_bend_culm(culm_length: float, span: float, rise: float,
                  section: CulmSection = CULM_100,
                  material: BambooMaterial = MOSO,
                  safety_factor: float = 2.0) -> dict:
    """指定アーチに、1本の竹で曲げて被覆できるかチェック。"""
    arch = arch_geometry(span, rise)
    R = arch["R"]
    R_min = min_bending_radius(section, material, safety_factor)
    feasible_bend = R >= R_min
    feasible_length = culm_length >= arch["arc_length"]
    sigma = bending_stress(section, R, material)
    util = sigma / (material.f_bending_mean / safety_factor)
    return dict(
        arch=arch,
        R_min=R_min,
        feasible_bend=feasible_bend,
        feasible_length=feasible_length,
        feasible=feasible_bend and feasible_length,
        bending_stress_MPa=sigma / 1e6,
        bending_util=util,
        restoring_moment_Nm=restoring_moment(section, R, material),
        margin_ratio=R / R_min,
    )


def analyze_dome_bent_bamboo(dome_diameter: float, dome_height: float,
                             n_arches: int = 8,
                             culm_length: float = 12.0,
                             section: CulmSection = CULM_100,
                             material: BambooMaterial = MOSO):
    """曲げ竹アーチドームの解析（径間=直径、立ち上がり=高さの全周配置）。

    n_arches 本のアーチを放射状に配置し、頂点で交わる構造。
    各アーチは1本の長い竹（または継いで延ばした竹）を曲げて作る。

    Returns: dict with feasibility, n_culms, total_length, etc.
    """
    chk = can_bend_culm(culm_length, dome_diameter, dome_height,
                        section, material)
    arch = chk["arch"]
    # 各アーチに必要な竹の本数（弧長 / 6m材で切り上げ）
    n_culms_per_arch = int(np.ceil(arch["arc_length"] / 6.0))
    # リブ（補強リング）は周方向に節点をつなぐ。とりあえず3層と仮定。
    n_rings = 3
    ring_lengths_m = [np.pi * dome_diameter * (1 - i / n_rings) for i in range(n_rings)]
    ring_culms = sum(int(np.ceil(L / 6.0)) for L in ring_lengths_m)
    total_culms = n_arches * n_culms_per_arch + ring_culms
    total_length = n_arches * arch["arc_length"] + sum(ring_lengths_m)
    joints = n_arches * 2 + n_rings * n_arches      # 両端と各リングの交点
    return dict(
        arch=arch,
        feasible=chk["feasible"],
        chk=chk,
        n_arches=n_arches,
        n_culms_per_arch=n_culms_per_arch,
        n_rings=n_rings,
        total_culms=total_culms,
        total_length_m=total_length,
        joint_count=joints,
        # 部材長平均
        ratio_long_vs_short=(arch["arc_length"] / 1.58),  # 1.58は v=3 ドームの平均部材長
    )


def print_dome_analysis(rep: dict):
    a = rep["arch"]; c = rep["chk"]
    print(f"=== 曲げ竹アーチドーム解析 ===")
    print(f"アーチ寸法: 径間={2*a['R']*np.sin(a['angle_rad']/2):.1f}m  "
          f"曲率半径R={a['R']:.2f}m  弧長={a['arc_length']:.2f}m  "
          f"角度{np.degrees(a['angle_rad']):.0f}度")
    print(f"曲げ可能性: 最小R={c['R_min']:.2f}m  余裕率{c['margin_ratio']:.1f}x  "
          f"{'OK' if c['feasible_bend'] else 'NG'}")
    print(f"曲げ応力: σ={c['bending_stress_MPa']:.1f}MPa  利用率{c['bending_util']:.2f}  "
          f"{'OK' if c['bending_util']<=1.0 else 'NG'}")
    print(f"復元モーメント: {c['restoring_moment_Nm']:.0f} N·m（プレストレス源）")
    print(f"アーチ数: {rep['n_arches']}本  ×  竹{rep['n_culms_per_arch']}本/アーチ")
    print(f"+ リング補強: {rep['n_rings']}層 = {rep['total_culms']-rep['n_arches']*rep['n_culms_per_arch']}本")
    print(f"総計: {rep['total_culms']}本（6m材）  総長{rep['total_length_m']:.0f}m")
    print(f"接合点: {rep['joint_count']}個")
    print(f"竹1本のカバー範囲: 平均部材長 {a['arc_length']/rep['n_culms_per_arch']:.1f}m "
          f"(短材分割比較で {rep['ratio_long_vs_short']:.1f}倍長い)")


if __name__ == "__main__":
    print("=== 曲げ竹アーチドーム解析（直径8m、高さ4m）===\n")
    rep = analyze_dome_bent_bamboo(dome_diameter=8.0, dome_height=4.0,
                                   n_arches=8, culm_length=12.0)
    print_dome_analysis(rep)
    print("\n=== 比較: ジオデシック格子 v=3, φ8m の場合 ===")
    print("  部材135本（短材分割、平均長1.58m）")
    print("  接合点52個（中間節点が多い）")
    print("  竹の節を多数切断＝強度低下")
    print("\n=== 曲げ竹の利点 ===")
    print("  + 接合点が少ない（弱点減）")
    print("  + 節を切らない（強度保持）")
    print("  + プレストレスで形状ロック")
    print("  + 部材数大幅削減")
    print("  + 伝統的な竹建築の工法に近い")
