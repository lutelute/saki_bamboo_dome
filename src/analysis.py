"""
analysis.py — 竹ドームの統合構造解析ドライバ

幾何生成 → 荷重 → 3DトラスFEM → 設計照査 → 積雪耐力 を一気通貫で実行し、
レポート辞書を返す。CLI(run_demo.py)・可視化・Blender出力が共通利用する。
"""
from __future__ import annotations

import numpy as np

from .geometry import geodesic_dome
from .bamboo import BambooMaterial, CulmSection, MOSO, CULM_100, G
from .fem import TrussModel
from . import loads as L
from . import design as D


def _solve_case(geo: dict, F: np.ndarray, material) -> dict:
    """支点ピン拘束で荷重ベクトル F に対して解く。"""
    model = TrussModel(geo["nodes"], geo["members"],
                       material.E, _areas(geo, material))
    for s in geo["supports"]:
        model.add_pin_support(s)
    model.set_load_vector(F)
    return model.solve()


def _areas(geo: dict, material) -> np.ndarray:
    # 断面はモデル全体で一定（CULM）。analyze() が section.area を渡す。
    return geo["_area"] * np.ones(len(geo["members"]))


def snow_capacity(geo: dict, F_dead: np.ndarray, F_snow_unit: np.ndarray,
                  section, material, K: float, joint_eff: float,
                  q_snow_unit: float) -> dict:
    """積雪倍率 λ を増やし、最大利用率=1.0 となる崩壊積雪荷重を二分法で探索。

    線形FEMなので axial(λ) = axial_D + λ·axial_S。
    """
    res_D = _solve_case(geo, F_dead, material)
    res_S = _solve_case(geo, F_snow_unit, material)
    aD, aS = res_D["axial"], res_S["axial"]

    def maxutil(lam):
        return D.max_utilization(geo, aD + lam * aS, section, material, K, joint_eff)

    # 上限を拡大して利用率>1 を跨ぐ区間を確保
    lo, hi = 0.0, 1.0
    if maxutil(0.0) >= 1.0:
        return dict(lambda_fail=0.0, q_fail=0.0, note="自重のみで既に許容超過")
    while maxutil(hi) < 1.0 and hi < 1e6:
        hi *= 2.0
    # 二分法
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if maxutil(mid) < 1.0:
            lo = mid
        else:
            hi = mid
    lam = 0.5 * (lo + hi)
    return dict(lambda_fail=float(lam), q_fail=float(lam * q_snow_unit),
                q_snow_unit=q_snow_unit)


def analyze(frequency: int = 3, radius: float = 4.0, height_ratio: float = 0.5,
            section: CulmSection = CULM_100, material: BambooMaterial = MOSO,
            q_snow: float = L.SNOW_FUKUI, q_wind: float = L.WIND_Q_SHELTERED,
            wind_cf: float = -0.8, q_cladding: float = 0.0,
            K: float = 1.0, joint_efficiency: float = 0.6,
            ground_snap: bool = True) -> dict:
    """竹ドームを構築・解析し、レポート辞書を返す。

    joint_efficiency: 接合部効率 η（縛り接合は<0.5, 良好なボルト+クランプで~1.0）。
                      research の知見に基づき既定0.6で接合支配を反映。
    """
    geo = geodesic_dome(frequency, radius, height_ratio, ground_snap)
    geo["_area"] = section.area  # _solve_case 用

    cases = L.build_load_cases(geo, section, material, q_snow, q_wind,
                               wind_cf, q_cladding)

    # 各荷重ケースを解いて照査
    case_results = {}
    for name in ("D", "D+S", "D+W"):
        res = _solve_case(geo, cases[name], material)
        chk = D.check_dome(geo, res["axial"], section, material, K, joint_efficiency)
        case_results[name] = dict(fem=res, check=chk)

    # 積雪耐力（設計積雪 q_snow に対する崩壊倍率 λ を探索）
    comp = cases["_components"]
    cap = snow_capacity(geo, comp["D"], comp["S"],
                        section, material, K, joint_efficiency, q_snow)

    # 数量・重量・概算コスト
    total_len = geo["meta"]["total_length"]
    total_weight = total_len * section.weight_per_length(material)  # [N]
    # 竹材単価の概算（φ100 孟宗竹 ~ 1本(5-6m) 2000-4000円 → ~500円/m とする）
    cost_per_m = 500.0
    est_cost = total_len * cost_per_m

    report = dict(
        geo=geo, cases=cases, case_results=case_results, capacity=cap,
        section=section, material=material,
        params=dict(frequency=frequency, radius=radius, height_ratio=height_ratio,
                    K=K, joint_efficiency=joint_efficiency,
                    q_snow=q_snow, q_wind=q_wind, wind_cf=wind_cf),
        quantities=dict(
            total_length_m=total_len,
            total_weight_N=total_weight, total_weight_kg=total_weight / G,
            n_culms_6m=int(np.ceil(total_len / 5.5)),  # 1本=有効5.5m
            est_cost_yen=est_cost,
            plan_area_m2=cases["_meta"]["plan_area_m2"],
            surface_area_m2=cases["_meta"]["surface_area_m2"],
        ),
    )
    return report


# ---------------------------------------------------------------------------
# レポート整形（テキスト）
# ---------------------------------------------------------------------------
def format_report(rep: dict) -> str:
    m = rep["geo"]["meta"]
    q = rep["quantities"]
    p = rep["params"]
    sec = rep["section"]
    mat = rep["material"]
    lines = []
    add = lines.append
    add("=" * 64)
    add("  竹ジオデシックドーム  構造解析レポート")
    add("=" * 64)
    add(f"【形状】 frequency={p['frequency']}  半径={p['radius']:.1f} m  "
        f"高さ比={p['height_ratio']:.2f}")
    add(f"         ドーム高={m['dome_height']:.2f} m  基礎半径={m['base_radius']:.2f} m  "
        f"水平投影={q['plan_area_m2']:.1f} m²  表面積={q['surface_area_m2']:.1f} m²")
    add(f"【格子】 節点={m['n_nodes']}  部材(竹)={m['n_members']}  面={m['n_faces']}  "
        f"支点={m['n_supports']}")
    add(f"         部材長 {m['member_len_min']:.2f}〜{m['member_len_max']:.2f} m "
        f"(平均{m['member_len_mean']:.2f} m)")
    add(f"【材料】 {mat.name}")
    add(f"         E={mat.E/1e9:.0f}GPa  許容圧縮={mat.allow_compression/1e6:.1f}MPa  "
        f"許容引張={mat.allow_tension/1e6:.1f}MPa  SF={mat.SF}")
    add(f"【断面】 φ{sec.outer_d*1e3:.0f}×t{sec.wall_t*1e3:.0f} mm  "
        f"A={sec.area*1e4:.1f}cm²  I={sec.I*1e8:.0f}cm⁴  r={sec.r_gyration*1e3:.0f}mm  "
        f"自重={sec.weight_per_length(mat):.1f}N/m")
    add(f"【数量】 総竹長={q['total_length_m']:.1f} m  "
        f"≈φ100孟宗竹 {q['n_culms_6m']} 本(6m材)  "
        f"自重合計={q['total_weight_kg']:.0f} kg  概算={q['est_cost_yen']/1e4:.1f} 万円")
    add("-" * 64)
    add("【荷重ケース別 照査】(接合効率 η={:.2f}, K={:.1f})".format(
        p["joint_efficiency"], p["K"]))
    for name in ("D", "D+S", "D+W"):
        cr = rep["case_results"][name]
        s = cr["check"]["summary"]
        g = s["governing"]
        verdict = "OK " if s["all_ok"] else "NG✗"
        add(f"  [{name:3s}] 最大利用率={s['max_utilization']:.2f} {verdict}  "
            f"支配部材#{s['governing_member']}({g['mode']}) "
            f"N={g['N']/1e3:+.1f}kN λ={g['slenderness']:.0f}  "
            f"圧縮{s['n_compression']}/引張{s['n_tension']}  "
            f"最大変位={cr['fem']['max_disp']*1e3:.1f}mm")
        if s["n_overstressed"] or s["n_slender"]:
            add(f"        ⚠ 許容超過 {s['n_overstressed']} 部材 / "
                f"細長比超過 {s['n_slender']} 部材")
    add("-" * 64)
    cap = rep["capacity"]
    qf = cap.get("q_fail", 0.0)
    add("【積雪耐力】")
    add(f"  崩壊積雪荷重 ≈ {qf/1e3:.2f} kN/m²  "
        f"(設計積雪 {p['q_snow']/1e3:.1f} kN/m² に対し余裕率 {qf/p['q_snow']:.2f})")
    snow_depth_fail = qf / 30.0  # 30 N/m²/cm（多雪区域）
    add(f"  ≒ 垂直積雪量 {snow_depth_fail:.0f} cm 相当 で崩壊"
        f"（福井市 設計積雪 140cm）")
    add("=" * 64)
    return "\n".join(lines)
