"""
snow_sim.py — 積雪堆積の時間発展シミュレーション（高さ場 × FEM連成）

各面の積雪深を時間積分し、斜面での滑落（屋根形状係数 μ_b=√cos1.5β）と
風による吹きだまり（風上削剥・風下堆積）を反映。毎ステップ FEM で構造応答を
計算し、利用率が1.0に達する「崩壊時刻」を検出する。

裏取り(research): 新雪密度~100, 沈降後~300 kg/m³, 安息角~40°(乾)/20°(湿),
  滑落臨界~40-60°, μ_b=√cos(1.5β) (β>60°で0=完全滑落),
  堆積 dh = 強度·dt·cos(面傾斜), 風: 風上削剥/風下堆積(ASCE/EN非対称積雪)。
ドームではクラウン(β小)に積もり急斜面(β大)で滑落する現実的パターンになる。
"""
from __future__ import annotations

import numpy as np

from .bamboo import G
from .fem import TrussModel
from .loads import _face_geom
from . import design as D


def accumulate_field(geo: dict, total_snow_m: float = 1.0,
                     wind_drift: float = 0.35, wind_az_deg: float = 0.0) -> dict:
    """積雪堆積の物理モデルによる各面の積雪深（融雪なし, 可視化用）。

    総降雪(水平面換算) total_snow_m に対し、屋根形状係数 μ_b=√cos(1.5β) で
    傾斜面は滑落して薄く、風で風上削剥/風下堆積する。FEM連成は行わない。
    戻り値: dict(depth_per_face[m,鉛直], beta_deg, mu_b, total_snow_m)
    """
    nodes, faces = geo["nodes"], geo["faces"]
    plan, area3d, n, centroid = _face_geom(nodes, faces)
    nz = np.clip(n[:, 2], -1.0, 1.0)
    beta = np.degrees(np.arccos(nz))
    mu_b = np.where(beta < 60.0,
                    np.sqrt(np.clip(np.cos(np.radians(1.5 * beta)), 0, 1)), 0.0)
    upward = nz > 0.05
    az = np.radians(wind_az_deg)
    wdir = np.array([np.cos(az), np.sin(az), 0.0])
    nh = n.copy(); nh[:, 2] = 0
    lee = nh @ wdir
    drift = 1.0 + wind_drift * np.tanh(2.0 * lee)
    depth = total_snow_m * mu_b * drift * upward          # 鉛直積雪深[m]（融雪なし）
    return dict(depth_per_face=depth, beta_deg=beta, mu_b=mu_b,
                total_snow_m=total_snow_m)


def _build_model(geo, section, material):
    model = TrussModel(geo["nodes"], geo["members"], material.E,
                       section.area * np.ones(len(geo["members"])))
    for s in geo["supports"]:
        model.add_pin_support(s)
    return model


def simulate_snow(geo: dict, section, material, K: float = 1.0,
                  joint_efficiency: float = 0.6,
                  intensity_cm_per_hr: float = 4.0, dt_hr: float = 3.0,
                  max_hr: float = 160.0, rho_snow: float = 300.0,
                  wind_drift: float = 0.35, wind_az_deg: float = 0.0,
                  defl_scale_target: float = 0.12) -> dict:
    """積雪堆積を時間発展で計算し、各時刻のフレームを返す。

    intensity_cm_per_hr : 降雪強度（新雪 cm/時, 水平面換算）
    rho_snow            : 沈降後の積雪密度 [kg/m³]
    wind_drift          : 吹きだまり強度(0=対称, 0.35=風下に+35%/風上−35%)
    """
    nodes, faces = geo["nodes"], geo["faces"]
    plan, area3d, n, centroid = _face_geom(nodes, faces)
    nz = np.clip(n[:, 2], -1.0, 1.0)
    beta = np.degrees(np.arccos(nz))               # 面傾斜[deg]（0=水平）
    mu_b = np.where(beta < 60.0,
                    np.sqrt(np.clip(np.cos(np.radians(1.5 * beta)), 0, 1)), 0.0)
    upward = nz > 0.05

    # 風による堆積係数（風下=多, 風上=少）
    az = np.radians(wind_az_deg)
    wdir = np.array([np.cos(az), np.sin(az), 0.0])  # 風が吹いていく向き
    # 面の風上/風下: 法線水平成分と風向の内積（+なら風下向き面）
    nhoriz = n.copy(); nhoriz[:, 2] = 0
    lee = np.array([v @ wdir for v in nhoriz])      # >0:風下, <0:風上
    drift_factor = 1.0 + wind_drift * np.tanh(2.0 * lee)

    model = _build_model(geo, section, material)
    dome_size = 2.0 * geo["meta"]["base_radius"]

    depth = np.zeros(len(faces))                    # 各面の鉛直積雪深[m]
    intensity_m = intensity_cm_per_hr / 100.0       # m/時（水平面）
    n_steps = int(max_hr / dt_hr)

    frames = []
    collapse_hr = None
    for k in range(n_steps + 1):
        t_hr = k * dt_hr
        if k > 0:
            # 堆積: 斜面ほど積もりにくい(μ_b)＋風で偏る。β>60°は積もらない
            depth += intensity_m * dt_hr * mu_b * drift_factor * upward

        # 積雪荷重ベクトル（各面 鉛直下向き = ρ·g·depth·plan）
        F = np.zeros(3 * len(nodes))
        qface = rho_snow * G * depth                # [N/m²]（鉛直深×密度×g）
        for fidx, (a, b, c) in enumerate(faces):
            fz = qface[fidx] * plan[fidx] / 3.0
            for nd in (a, b, c):
                F[3 * nd + 2] -= fz
        # 自重も足す
        for m, (i, j) in enumerate(geo["members"]):
            half = 0.5 * section.weight_per_length(material) * geo["lengths"][m]
            F[3 * i + 2] -= half
            F[3 * j + 2] -= half

        model.set_load_vector(F)
        try:
            res = model.solve()
        except Exception:
            break
        chk = D.check_dome(geo, res["axial"], section, material, K, joint_efficiency)
        max_util = chk["summary"]["max_utilization"]
        member_utils = np.array([mm["utilization"] for mm in chk["members"]])

        # 平均積雪深・総雪荷重
        total_snow_N = float((qface * plan).sum())
        mean_depth_cm = float(depth[upward].mean() * 100) if upward.any() else 0.0
        crown_depth_cm = float(depth[np.argmax(centroid[:, 2])] * 100)

        frames.append(dict(
            t_hr=t_hr, depth=depth.copy(), max_util=max_util,
            disp=res["disp"].copy(), axial=res["axial"].copy(),
            member_utils=member_utils, total_snow_N=total_snow_N,
            mean_depth_cm=mean_depth_cm, crown_depth_cm=crown_depth_cm,
            snow_load_kN_m2=float(rho_snow * G * depth.max() / 1e3)))

        if collapse_hr is None and max_util >= 1.0:
            collapse_hr = t_hr
            # 崩壊後2フレームで打ち切り
        if collapse_hr is not None and t_hr >= collapse_hr + 2 * dt_hr:
            break

    # 変形誇張倍率（全フレーム共通, 最大変位基準）
    max_disp = max((np.linalg.norm(f["disp"], axis=1).max() for f in frames), default=1e-6)
    defl_scale = (defl_scale_target * dome_size / max_disp) if max_disp > 1e-9 else 0.0

    return dict(frames=frames, faces=faces, nodes=nodes, members=geo["members"],
                supports=geo["supports"], beta=beta, mu_b=mu_b,
                defl_scale=defl_scale, collapse_hr=collapse_hr,
                params=dict(intensity_cm_per_hr=intensity_cm_per_hr, dt_hr=dt_hr,
                            rho_snow=rho_snow, wind_drift=wind_drift,
                            wind_az_deg=wind_az_deg))


def summary(sim: dict) -> str:
    f0, fl = sim["frames"][0], sim["frames"][-1]
    c = sim["collapse_hr"]
    lines = [
        f"積雪シミュレーション: {len(sim['frames'])}フレーム, "
        f"降雪{sim['params']['intensity_cm_per_hr']}cm/時, "
        f"密度{sim['params']['rho_snow']:.0f}kg/m³, 吹きだまり{sim['params']['wind_drift']:.0%}",
        f"  最終 t={fl['t_hr']:.0f}時間: 平均積雪{fl['mean_depth_cm']:.0f}cm "
        f"クラウン{fl['crown_depth_cm']:.0f}cm 最大利用率{fl['max_util']:.2f}",
    ]
    if c is not None:
        lines.append(f"  ⚠ 崩壊: t={c:.0f}時間（約{c/24:.1f}日）で利用率1.0到達")
    else:
        lines.append(f"  崩壊せず（{fl['t_hr']:.0f}時間で最大利用率{fl['max_util']:.2f}）")
    return "\n".join(lines)
