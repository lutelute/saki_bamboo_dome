"""
design.py — 部材の設計照査（許容応力 + 座屈）

research(ISO 22156 / 竹工学文献)に基づく照査ロジック:
  ・引張: σ = N/A ≤ 許容引張 f_t,allow
  ・圧縮: 次の小さい方で決まる耐力に対して照査（min(材料破壊, 座屈)）
      - 材料(圧壊) 許容耐力  P_crush = A · f_c,allow
      - Euler 弾性座屈 許容  P_euler = P_cr / SF_buckling,  P_cr = π²EI/(KL)²
      - 中間細長比の非保守を避け、両者を Rankine-Gordon で合成（常に保守側）:
            P_allow = P_crush · P_euler / (P_crush + P_euler)
  ・細長比 λ = K·L/r ≤ 150 を超える部材は非適合としてフラグ（要中間節点）
  ・接合部効率 η（縛り/ボルト）で部材耐力を割引（接合が支配する旨を明示）
K=1.0（ピン接合ドーム束材）を既定とする。
"""
from __future__ import annotations

import numpy as np

SLENDERNESS_LIMIT = 150.0  # 圧縮材の細長比上限（竹/木/鋼の実務目安）


def member_capacity(N: float, L: float, section, material,
                    K: float = 1.0, joint_efficiency: float = 1.0) -> dict:
    """1部材の照査。N: 軸力[N](引張+/圧縮-)。"""
    A = section.area
    I = section.I
    r = section.r_gyration
    sigma = N / A                       # 応力[Pa]（引張+）
    lam = K * L / r                     # 細長比

    if N >= 0:  # 引張（座屈しない＝細長比は情報表示のみ）
        cap_allow = A * material.allow_tension * joint_efficiency
        util = N / cap_allow
        mode = "引張"
        P_cr = np.inf
        P_crush_allow = A * material.allow_tension
        P_euler_allow = np.inf
        P_allow = cap_allow
        slender_flag = False                       # 引張材に細長比制限は不適用
    else:       # 圧縮
        Ncomp = -N
        P_cr = np.pi**2 * material.E * I / (K * L)**2          # Euler弾性座屈(極限)
        # Rankine-Gordon は「極限耐力」に対して合成し、安全率を一度だけ掛ける。
        # （許容値どうしを合成すると SF≠SF_buckling のとき実効SFが不整合になる）
        P_crush_ult = A * material.characteristic(material.f_compression_mean)
        P_euler_ult = P_cr
        P_R_ult = P_crush_ult * P_euler_ult / (P_crush_ult + P_euler_ult)
        P_allow = (material.C_mod * P_R_ult / material.SF_buckling) * joint_efficiency
        util = Ncomp / P_allow
        # 表示用の参考許容値
        P_crush_allow = A * material.allow_compression
        P_euler_allow = P_cr / material.SF_buckling
        # 支配モード: 中間域(Pe≈Pc)は両者の合成なので明示
        ratio = P_euler_ult / P_crush_ult
        if ratio < 0.5:
            mode = "座屈"
        elif ratio > 2.0:
            mode = "圧壊"
        else:
            mode = "座屈+圧壊(RG)"
        slender_flag = bool(lam > SLENDERNESS_LIMIT)  # 圧縮材のみ

    return dict(
        N=N, sigma=sigma, length=L, slenderness=lam,
        P_cr=P_cr, P_crush_allow=P_crush_allow, P_euler_allow=P_euler_allow,
        P_allow=P_allow, utilization=util, mode=mode,
        slender_flag=slender_flag,
        ok=bool(util <= 1.0 and not slender_flag),
    )


def check_dome(geo: dict, axial: np.ndarray, section, material,
               K: float = 1.0, joint_efficiency: float = 1.0) -> dict:
    """ドーム全部材を照査し、結果リストとサマリを返す。"""
    members = geo["members"]
    lengths = geo["lengths"]
    results = []
    for m in range(len(members)):
        results.append(member_capacity(
            float(axial[m]), float(lengths[m]), section, material,
            K=K, joint_efficiency=joint_efficiency))

    utils = np.array([r["utilization"] for r in results])
    slender = np.array([r["slender_flag"] for r in results])
    gov = int(np.argmax(utils))
    n_ng = int(np.sum(utils > 1.0))

    summary = dict(
        max_utilization=float(utils.max()),
        governing_member=gov,
        governing=results[gov],
        n_members=len(results),
        n_overstressed=n_ng,
        n_slender=int(slender.sum()),
        all_ok=bool(utils.max() <= 1.0 and not slender.any()),
        n_compression=int(np.sum(axial < 0)),
        n_tension=int(np.sum(axial > 0)),
    )
    return dict(members=results, summary=summary)


def max_utilization(geo: dict, axial: np.ndarray, section, material,
                    K: float = 1.0, joint_efficiency: float = 1.0) -> float:
    """全部材中の最大利用率（耐力探索の評価関数）。"""
    lengths = geo["lengths"]
    u = 0.0
    for m in range(len(geo["members"])):
        u = max(u, member_capacity(float(axial[m]), float(lengths[m]),
                                   section, material, K, joint_efficiency)["utilization"])
    return u
