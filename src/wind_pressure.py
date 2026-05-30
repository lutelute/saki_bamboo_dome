"""
wind_pressure.py — 方向性風の外圧係数 cp(θ) による風圧荷重

一様吸込み(loads.wind_load)を、風向き依存の現実的な圧力分布に格上げする。
半球ドームの外圧係数（research 裏取り: Cheng&Fu 2010, EN1991-1-4, AIJ-RLB2015）:
  θ = 風上よどみ点からの角度（風向き子午線に沿う, 0=風上裾, 90=クラウン, 180=風下裾）
  区分モデル（乱流境界層中の半球, 既定）:
    θ≤35°    : cp = cp_stag·cos(90°·θ/35)         （風上, 正圧→0）
    35<θ≤88° : cp = cp_crown·(t²)                  （クラウンへ加速, 0→負圧ピーク）
    88<θ≤105°: cp = cp_crown+(cp_lee−cp_crown)·t²  （剥離へ）
    θ>105°   : cp = cp_lee                          （風下, 一定負圧）
  既定: cp_stag=+0.8, cp_crown=−1.0, cp_lee=−0.4。
面圧 = q·cp,  節点力 = −q·cp·A·n（cp>0=内向き押し, cp<0=外向き吸込み）。
"""
from __future__ import annotations

import numpy as np

try:
    from .loads import _face_geom
except ImportError:  # スクリプト直接実行時
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.loads import _face_geom

# 既定 cp パラメータ（乱流境界層中の真半球 f/d=0.5）
CP_PARAMS = dict(cp_stag=0.8, theta_zero=35.0, cp_crown=-1.0,
                 theta_min=88.0, theta_sep=105.0, cp_lee=-0.4)


def cp_hemisphere(theta_deg, p=CP_PARAMS):
    """風上よどみ点からの角度 θ[deg] における外圧係数 cp（区分モデル）。"""
    th = np.asarray(theta_deg, dtype=float)
    cp = np.empty_like(th)
    z, tmin, tsep = p["theta_zero"], p["theta_min"], p["theta_sep"]
    cs, cc, cl = p["cp_stag"], p["cp_crown"], p["cp_lee"]
    # 1) 風上付着域: cos減衰
    m1 = th <= z
    cp[m1] = cs * np.cos(np.radians(90.0 * th[m1] / z))
    # 2) クラウンへ加速: 0→cc（二次）
    m2 = (th > z) & (th <= tmin)
    t = (th[m2] - z) / (tmin - z)
    cp[m2] = cc * t * t
    # 3) クラウン→剥離: cc→cl
    m3 = (th > tmin) & (th <= tsep)
    t = (th[m3] - tmin) / (tsep - tmin)
    cp[m3] = cc + (cl - cc) * t * t
    # 4) 風下剥離域: 一定
    cp[th > tsep] = cl
    return cp


def face_cp(geo: dict, wind_az_deg: float = 0.0, p=CP_PARAMS):
    """各面の cp を返す。wind_az_deg: 風が吹いていく方位（xy面, 0=+x方向）。"""
    nodes, faces = geo["nodes"], geo["faces"]
    _, area3d, n, centroid = _face_geom(nodes, faces)
    az = np.radians(wind_az_deg)
    w = np.array([np.cos(az), np.sin(az), 0.0])    # 風が吹いていく向き
    # θ = 風上よどみ(法線=−w)からの角度: cosθ = n·(−w)
    cos_t = np.clip(-(n @ w), -1.0, 1.0)
    theta = np.degrees(np.arccos(cos_t))
    return cp_hemisphere(theta, p), area3d, n, centroid, theta


def directional_wind_load(geo: dict, q_wind: float, wind_az_deg: float = 0.0,
                          p=CP_PARAMS) -> np.ndarray:
    """方向性風の節点等価荷重ベクトル(長さ3N)。"""
    nodes, faces = geo["nodes"], geo["faces"]
    cp, area3d, n, _, _ = face_cp(geo, wind_az_deg, p)
    F = np.zeros(3 * len(nodes))
    for f, (a, b, c) in enumerate(faces):
        # 面力 = q·cp·A を内向き(−n)に作用（cp>0押し, cp<0吸込み）
        force_vec = (-q_wind * cp[f] * area3d[f]) * n[f] / 3.0
        for node in (a, b, c):
            F[3 * node:3 * node + 3] += force_vec
    return F


def node_cp(geo: dict, wind_az_deg: float = 0.0, p=CP_PARAMS) -> np.ndarray:
    """各節点の cp（隣接面の面積加重平均, 可視化用）。"""
    nodes, faces = geo["nodes"], geo["faces"]
    cp, area3d, _, _, _ = face_cp(geo, wind_az_deg, p)
    acc = np.zeros(len(nodes))
    wsum = np.zeros(len(nodes))
    for f, (a, b, c) in enumerate(faces):
        for node in (a, b, c):
            acc[node] += cp[f] * area3d[f]
            wsum[node] += area3d[f]
    return acc / np.maximum(wsum, 1e-12)


if __name__ == "__main__":
    # cp(θ) の代表値を表示
    for th in (0, 15, 35, 60, 88, 105, 140, 180):
        print(f"  θ={th:3d}° → cp={float(cp_hemisphere(th)):+.2f}")
