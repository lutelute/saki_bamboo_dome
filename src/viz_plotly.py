"""
viz_plotly.py — plotly によるインタラクティブ3D（自己完結HTML）

竹部材を「実際の竹直径(φ100mm等)を持つ3Dチューブ」で描画。回転・ズーム可能で、
荷重ケース(D / D+S / D+W)をボタンで切替でき、各ケースで実際にたわんだ変形形状を
（誇張倍率つきで）表示する。元形状を薄く重ね、XYZ軸(単位m)・地面も表示。
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .tube3d import build_tube_mesh

_FORCE_SCALE = [[0.0, "#4ec9d4"], [0.5, "#283142"], [1.0, "#f0a23a"]]  # 圧縮-中立-引張
_UTIL_SCALE = [[0.0, "#5fd38a"], [0.5, "#f0c14b"], [0.8, "#f0a23a"], [1.0, "#ef6a6a"]]
_LIGHT = dict(ambient=0.55, diffuse=0.8, specular=0.2, roughness=0.5, fresnel=0.1)


def _ref_lines(nodes, members):
    xs, ys, zs = [], [], []
    for (i, j) in members:
        xs += [nodes[i, 0], nodes[j, 0], None]
        ys += [nodes[i, 1], nodes[j, 1], None]
        zs += [nodes[i, 2], nodes[j, 2], None]
    return xs, ys, zs


def build_interactive(rep: dict, out_path: str = "output/dome_interactive.html") -> str:
    geo = rep["geo"]
    nodes, members = geo["nodes"], geo["members"]
    cr = rep["case_results"]
    cases = ["D", "D+S", "D+W"]
    case_label = {"D": "自重のみ", "D+S": "自重＋積雪", "D+W": "自重＋風(吹上げ)"}
    crad = rep["section"].outer_d / 2.0            # 実際の竹半径[m]
    sides = 8

    dome_size = 2.0 * geo["meta"]["base_radius"]
    target = 0.12 * dome_size

    # 各ケース: 変形座標・チューブ頂点(x,y,z)・強度・誇張倍率
    info = {}
    base_ijk = None
    for c in cases:
        disp = cr[c]["fem"]["disp"]
        axial = cr[c]["fem"]["axial"]
        util = np.array([m["utilization"] for m in cr[c]["check"]["members"]])
        max_disp = float(np.linalg.norm(disp, axis=1).max())
        scale = (target / max_disp) if max_disp > 1e-9 else 0.0
        deformed = nodes + scale * disp
        mesh = build_tube_mesh(deformed, members, axial, crad, sides)
        if base_ijk is None:
            base_ijk = (mesh["i"], mesh["j"], mesh["k"])
        util_mesh = build_tube_mesh(deformed, members, util, crad, sides)["intensity"]
        info[c] = dict(mesh=mesh, util_int=util_mesh, scale=scale, max_disp=max_disp)

    amax = float(np.abs(np.concatenate([cr[c]["fem"]["axial"] for c in cases])).max())
    init = "D+S"
    mi = info[init]["mesh"]

    # 元形状（薄い参照ワイヤ）
    ux, uy, uz = _ref_lines(nodes, members)
    ref = go.Scatter3d(x=ux, y=uy, z=uz, mode="lines",
                       line=dict(width=1.2, color="#3a4660"),
                       name="元形状(変形なし)", hoverinfo="skip")

    # 竹チューブ（Mesh3d）
    tubes = go.Mesh3d(
        x=mi["x"], y=mi["y"], z=mi["z"], i=mi["i"], j=mi["j"], k=mi["k"],
        intensity=mi["intensity"], colorscale=_FORCE_SCALE, cmin=-amax, cmax=amax,
        colorbar=dict(title="軸力 [N]", x=1.02), flatshading=False, lighting=_LIGHT,
        name="竹部材", hoverinfo="skip")

    # 支点
    sup = nodes[geo["supports"]]
    sup_tr = go.Scatter3d(x=sup[:, 0], y=sup[:, 1], z=sup[:, 2], mode="markers",
                          marker=dict(size=4, color="#5fd38a", symbol="diamond"),
                          name="支点（基礎）", hoverinfo="name")

    # 地面
    g = dome_size * 0.62
    cx, cy = nodes[:, 0].mean(), nodes[:, 1].mean()
    ground = go.Mesh3d(x=[cx - g, cx + g, cx + g, cx - g], y=[cy - g, cy - g, cy + g, cy + g],
                       z=[0, 0, 0, 0], i=[0, 0], j=[1, 2], k=[2, 3],
                       color="#11161f", opacity=0.5, hoverinfo="skip", showscale=False)

    fig = go.Figure([ground, ref, tubes, sup_tr])
    MAIN = 2

    p = rep["params"]

    def title_for(c):
        d = info[c]
        s = cr[c]["check"]["summary"]
        return (f"竹ドーム 変形図　【{c}：{case_label[c]}】　v={p['frequency']} "
                f"R={p['radius']:.1f}m　竹φ{rep['section'].outer_d*1e3:.0f}mm<br>"
                f"<sub>最大変位 {d['max_disp']*1e3:.1f} mm を ×{d['scale']:.0f} に誇張　"
                f"｜最大利用率 {s['max_utilization']:.2f}　｜薄い灰色＝変形前　"
                f"｜ドラッグで回転</sub>")

    def force_button(c):
        m = info[c]["mesh"]
        return dict(label=f"{c}（{case_label[c]}）", method="update",
                    args=[{"x": [m["x"]], "y": [m["y"]], "z": [m["z"]],
                           "intensity": [m["intensity"]], "colorscale": [_FORCE_SCALE],
                           "cmin": -amax, "cmax": amax,
                           "colorbar.title.text": "軸力 [N]"},
                          {"title.text": title_for(c)}, [MAIN]])

    mS = info["D+S"]["mesh"]
    umax = max(1.0, float(info["D+S"]["util_int"].max()))
    util_button = dict(label="D+S 利用率", method="update",
                       args=[{"x": [mS["x"]], "y": [mS["y"]], "z": [mS["z"]],
                              "intensity": [info["D+S"]["util_int"]],
                              "colorscale": [_UTIL_SCALE], "cmin": 0.0, "cmax": umax,
                              "colorbar.title.text": "利用率"},
                             {"title.text": title_for("D+S")}, [MAIN]])

    buttons = [force_button("D+S"), force_button("D"), force_button("D+W"), util_button]

    axc = dict(backgroundcolor="#0c1016", color="#8493a8", gridcolor="#283142",
               zerolinecolor="#3a4660", showbackground=True, showgrid=True)
    fig.update_layout(
        title=dict(text=title_for(init), font=dict(color="#dfe6ef", size=15)),
        paper_bgcolor="#0c1016", font=dict(color="#dfe6ef"),
        legend=dict(bgcolor="rgba(20,26,35,0.6)", font=dict(size=11), x=0, y=0.98),
        scene=dict(xaxis=dict(title="X [m]", **axc), yaxis=dict(title="Y [m]", **axc),
                   zaxis=dict(title="Z 高さ [m]", **axc), aspectmode="data",
                   camera=dict(eye=dict(x=1.6, y=1.6, z=0.85))),
        updatemenus=[dict(buttons=buttons, direction="right", x=0.5, y=1.0,
                          xanchor="center", yanchor="bottom", bgcolor="#1b2330",
                          font=dict(color="#dfe6ef"), bordercolor="#283142",
                          active=0, pad=dict(t=4, b=4))],
        margin=dict(l=0, r=0, t=110, b=0))
    fig.write_html(out_path, include_plotlyjs=True, full_html=True)
    return out_path
