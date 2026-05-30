"""
loads.py — 荷重ケース（自重・積雪・風）の節点等価荷重

数値は research で裏取りした福井市の建築基準法荷重:
  積雪: 多雪区域, 垂直積雪量 d=140cm, 単位荷重 p=30 N/m²/cm
        → 積雪荷重 S = d·p·μ_b = 140·30·1.0 = 4200 N/m² (μ_b=1.0 保守側)
        屋根形状係数 μ_b = √(cos(1.5β))   (令第86条, 告示第1455号)
        ※多雪区域では積雪は長期荷重(令第86条第3項)
  風  : 基準風速 V0=32 m/s, 速度圧 q≈0.73 kN/m²(遮蔽)〜1.1(開放)
        W = q·Cf, 軽量ドームは吹上げ(負圧 Cf≈-0.8〜-1.0)が支配
出典: 建築基準法施行令 第86/87条, 平成12年建設省告示1454/1455号,
      福井県積雪荷重等指導基準, AIJ建築物荷重指針。
"""
from __future__ import annotations

import numpy as np

from .bamboo import G

# 福井市の既定荷重値 [N/m^2]
SNOW_FUKUI = 4200.0     # 積雪荷重 (d=140cm × 30 N/m²/cm, μ_b=1.0)
SNOW_FUKUI_CONSERVATIVE = 6000.0  # 垂直積雪量200cm基準を使う場合
WIND_Q_SHELTERED = 730.0   # 速度圧 q (粗度区分III, 遮蔽地)
WIND_Q_EXPOSED = 1100.0    # 速度圧 q (粗度区分II, 開放地)


# ---------------------------------------------------------------------------
# 屋根形状係数
# ---------------------------------------------------------------------------
def roof_shape_factor(beta_deg: float) -> float:
    """屋根形状係数 μ_b = √(cos(1.5β))（令第86条, 告示1455号）。

    β: 屋根勾配[deg]。β≧60°で μ_b=0。雪止めがあり滑落しない場合は μ_b=1.0。
    """
    if beta_deg >= 60.0:
        return 0.0
    return float(np.sqrt(max(0.0, np.cos(np.radians(1.5 * beta_deg)))))


# ---------------------------------------------------------------------------
# 面の幾何量
# ---------------------------------------------------------------------------
def _face_geom(nodes: np.ndarray, faces: np.ndarray):
    """各面の plan面積(xy投影)・3D面積・外向き単位法線・重心 を返す。"""
    p0 = nodes[faces[:, 0]]
    p1 = nodes[faces[:, 1]]
    p2 = nodes[faces[:, 2]]
    cross = np.cross(p1 - p0, p2 - p0)          # 法線方向(長さ=2×面積)
    area3d = 0.5 * np.linalg.norm(cross, axis=1)
    # plan面積 = xy平面への投影 = |cross_z|/2
    plan = 0.5 * np.abs(cross[:, 2])
    centroid = (p0 + p1 + p2) / 3.0
    # 外向き法線（球中心=原点から重心方向に揃える）
    n = cross / (np.linalg.norm(cross, axis=1, keepdims=True) + 1e-30)
    flip = np.sum(n * centroid, axis=1) < 0.0
    n[flip] = -n[flip]
    return plan, area3d, n, centroid


# ---------------------------------------------------------------------------
# 各荷重 → 節点力ベクトル(長さ 3N)
# ---------------------------------------------------------------------------
def dead_load(geo: dict, section, material) -> np.ndarray:
    """自重: 各部材重量を両端節点に1/2ずつ集中, 下向き(-z)。"""
    nodes, members, lengths = geo["nodes"], geo["members"], geo["lengths"]
    F = np.zeros(3 * len(nodes))
    w = section.weight_per_length(material)  # [N/m]
    for m, (i, j) in enumerate(members):
        half = 0.5 * w * lengths[m]
        F[3 * i + 2] -= half
        F[3 * j + 2] -= half
    return F


def snow_load(geo: dict, q_snow: float = SNOW_FUKUI) -> np.ndarray:
    """積雪: 鉛直下向き, 水平投影(plan)面積に比例して節点へ分配。

    雪は上向き面(外向き法線 n_z>0)にのみ積もる。半球超(height_ratio>0.5)で
    赤道下に張り出す下面(n_z<0)に abs() で雪を二重計上しないよう除外する。
    """
    nodes, faces = geo["nodes"], geo["faces"]
    F = np.zeros(3 * len(nodes))
    plan, _, n, _ = _face_geom(nodes, faces)
    for f, (a, b, c) in enumerate(faces):
        if n[f, 2] <= 0.0:           # 下向き面（張り出し裏面）には積もらない
            continue
        fz = q_snow * plan[f] / 3.0   # 各頂点へ1/3
        for node in (a, b, c):
            F[3 * node + 2] -= fz
    return F


def wind_load(geo: dict, q_wind: float = WIND_Q_SHELTERED,
              cf: float = -0.8) -> np.ndarray:
    """風: 面に垂直な圧力。cf<0=負圧(吹上げ/外向き), cf>0=正圧(内向き)。

    面力 = q·cf·A3d を外向き法線方向に作用（cf<0で外向き=吹上げ）。

    注意: 全面に一様な cf を与える「一様吸込み」理想化のため、対称性から
    水平合力・転倒モーメントは 0 になる。これは軽量ドームで支配的な
    「鉛直吹上げ（アンカー引抜き）」の包絡を見るための簡略モデルであり、
    横力(滑動)・転倒の検討には使えない。方向性風（風上正圧/風下・天端負圧）が
    必要なら cf(θ) を面ごとに与えること。
    """
    nodes, faces = geo["nodes"], geo["faces"]
    F = np.zeros(3 * len(nodes))
    _, area3d, n, _ = _face_geom(nodes, faces)
    for f, (a, b, c) in enumerate(faces):
        # 正圧(cf>0)は面を内側へ押す=-n方向, 負圧(cf<0)は外側へ吸う=+n方向
        force_vec = (-q_wind * cf * area3d[f]) * n[f] / 3.0
        for node in (a, b, c):
            F[3 * node:3 * node + 3] += force_vec
    return F


def cladding_load(geo: dict, q_clad: float) -> np.ndarray:
    """屋根材・膜などの被覆自重: 3D面積に比例, 鉛直下向き。"""
    nodes, faces = geo["nodes"], geo["faces"]
    F = np.zeros(3 * len(nodes))
    _, area3d, _, _ = _face_geom(nodes, faces)
    for f, (a, b, c) in enumerate(faces):
        fz = q_clad * area3d[f] / 3.0
        for node in (a, b, c):
            F[3 * node + 2] -= fz
    return F


# ---------------------------------------------------------------------------
# 荷重ケース
# ---------------------------------------------------------------------------
def plan_area(geo: dict) -> float:
    """ドームの水平投影（フットプリント）面積 [m^2]。

    上向き面(n_z>0)のみ集計。これで snow_load と総積雪荷重が整合し、
    半球超ドームで下面投影を二重計上しない。"""
    plan, _, n, _ = _face_geom(geo["nodes"], geo["faces"])
    return float(plan[n[:, 2] > 0.0].sum())


def surface_area(geo: dict) -> float:
    """ドームの表面積 [m^2]。"""
    _, area3d, _, _ = _face_geom(geo["nodes"], geo["faces"])
    return float(area3d.sum())


def build_load_cases(geo: dict, section, material,
                     q_snow: float = SNOW_FUKUI,
                     q_wind: float = WIND_Q_SHELTERED,
                     wind_cf: float = -0.8,
                     q_cladding: float = 0.0) -> dict:
    """代表的な荷重組合せを構築して返す（各値は長さ3Nのベクトル）。

    - D    : 自重(+被覆)
    - D+S  : 自重 + 積雪（多雪区域では長期）
    - D+W  : 自重 + 風（吹上げ）  ← 軽量ドームのアンカー検討用
    """
    D = dead_load(geo, section, material)
    if q_cladding > 0:
        D = D + cladding_load(geo, q_cladding)
    S = snow_load(geo, q_snow)
    W = wind_load(geo, q_wind, wind_cf)
    return {
        "D": D,
        "D+S": D + S,
        "D+W": D + W,
        "_components": {"D": D, "S": S, "W": W},
        "_meta": {
            "q_snow_N_m2": q_snow, "q_wind_N_m2": q_wind, "wind_cf": wind_cf,
            "q_cladding_N_m2": q_cladding,
            "plan_area_m2": plan_area(geo), "surface_area_m2": surface_area(geo),
            "total_snow_N": q_snow * plan_area(geo),
            "total_dead_N": float(-D[2::3].sum()),
        },
    }
