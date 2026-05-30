"""
viz_plotly.py — plotly によるインタラクティブ3D（自己完結HTML）

回転・ズーム・ホバー可能な3Dビューを出力。
荷重ケース(D / D+S / D+W の軸力, D+S利用率)をボタンで切替できる。
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

_FORCE_SCALE = [[0.0, "#4ec9d4"], [0.5, "#283142"], [1.0, "#f0a23a"]]  # 圧縮-中立-引張
_UTIL_SCALE = [[0.0, "#5fd38a"], [0.5, "#f0c14b"], [0.8, "#f0a23a"], [1.0, "#ef6a6a"]]


def _line_arrays(nodes, members, values):
    """各部材を [端i, 端j, None] で連結し、色配列も対応させる。"""
    xs, ys, zs, cs, texts = [], [], [], [], []
    for m, (i, j) in enumerate(members):
        for node in (i, j):
            xs.append(nodes[node, 0]); ys.append(nodes[node, 1]); zs.append(nodes[node, 2])
            cs.append(values[m])
            texts.append(f"部材#{m}  端{node}")
        xs.append(None); ys.append(None); zs.append(None); cs.append(values[m]); texts.append("")
    return xs, ys, zs, cs, texts


def build_interactive(rep: dict, out_path: str = "output/dome_interactive.html") -> str:
    geo = rep["geo"]
    nodes, members = geo["nodes"], geo["members"]
    cr = rep["case_results"]

    # 各ケースの軸力・利用率
    forceD = cr["D"]["fem"]["axial"]
    forceS = cr["D+S"]["fem"]["axial"]
    forceW = cr["D+W"]["fem"]["axial"]
    utilS = np.array([m["utilization"] for m in cr["D+S"]["check"]["members"]])

    # ホバーテキスト（D+S基準で部材情報）
    chkS = cr["D+S"]["check"]["members"]
    hover = []
    for m, (i, j) in enumerate(members):
        h = (f"部材#{m}<br>軸力(D+S)={forceS[m]/1e3:+.1f} kN<br>"
             f"利用率={utilS[m]:.2f} ({chkS[m]['mode']})<br>"
             f"長さ={geo['lengths'][m]:.2f} m  細長比λ={chkS[m]['slenderness']:.0f}")
        hover.append(h)

    amax = float(np.abs(np.concatenate([forceD, forceS, forceW])).max())

    # 初期表示: D+S 軸力
    xs, ys, zs, cs, _ = _line_arrays(nodes, members, forceS)
    # ホバーは部材ごとに2頂点へ展開
    htext = []
    for m in range(len(members)):
        htext += [hover[m], hover[m], ""]

    line_trace = go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(width=5, color=cs, colorscale=_FORCE_SCALE, cmin=-amax, cmax=amax,
                  colorbar=dict(title="軸力 [N]", x=1.02)),
        text=htext, hoverinfo="text", name="竹部材",
    )

    # 節点・支点
    sup = set(geo["supports"])
    others = [k for k in range(len(nodes)) if k not in sup]
    node_trace = go.Scatter3d(
        x=nodes[others, 0], y=nodes[others, 1], z=nodes[others, 2],
        mode="markers", marker=dict(size=2.5, color="#8493a8"),
        name="節点", hoverinfo="skip")
    sup_arr = nodes[geo["supports"]]
    sup_trace = go.Scatter3d(
        x=sup_arr[:, 0], y=sup_arr[:, 1], z=sup_arr[:, 2],
        mode="markers", marker=dict(size=5, color="#5fd38a", symbol="diamond"),
        name="支点（基礎）", hoverinfo="name")

    fig = go.Figure([line_trace, node_trace, sup_trace])

    # ケース切替ボタン（line.color / colorscale / cmin/cmax を restyle）
    def color_arr(vals):
        c = []
        for v in vals:
            c += [v, v, v]
        return c

    btn = lambda label, vals, scale, cmin, cmax, title: dict(
        label=label, method="restyle",
        args=[{"line.color": [color_arr(vals)], "line.colorscale": [scale],
               "line.cmin": cmin, "line.cmax": cmax,
               "line.colorbar.title.text": title}, [0]])

    umax = max(1.0, float(utilS.max()))
    buttons = [
        btn("軸力 D+S（積雪）", forceS, _FORCE_SCALE, -amax, amax, "軸力 [N]"),
        btn("軸力 D（自重）", forceD, _FORCE_SCALE, -amax, amax, "軸力 [N]"),
        btn("軸力 D+W（風）", forceW, _FORCE_SCALE, -amax, amax, "軸力 [N]"),
        btn("利用率 D+S", utilS, _UTIL_SCALE, 0.0, umax, "利用率"),
    ]

    p = rep["params"]
    s = cr["D+S"]["check"]["summary"]
    fig.update_layout(
        title=dict(text=(
            f"竹ジオデシックドーム インタラクティブ3D　"
            f"v={p['frequency']} R={p['radius']:.1f}m 部材{len(members)}本<br>"
            f"<sub>D+S最大利用率 {s['max_utilization']:.2f}　"
            f"積雪耐力 {rep['capacity']['q_fail']/1e3:.2f} kN/m²　"
            f"（ドラッグで回転・ホバーで部材情報）</sub>"),
            font=dict(color="#dfe6ef", size=15)),
        paper_bgcolor="#0c1016", font=dict(color="#dfe6ef"),
        scene=dict(
            xaxis=dict(title="X [m]", backgroundcolor="#0c1016", color="#5a677b",
                       gridcolor="#283142"),
            yaxis=dict(title="Y [m]", backgroundcolor="#0c1016", color="#5a677b",
                       gridcolor="#283142"),
            zaxis=dict(title="Z [m]", backgroundcolor="#0c1016", color="#5a677b",
                       gridcolor="#283142"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=1.5, z=0.9)),
        ),
        updatemenus=[dict(
            buttons=buttons, direction="right", x=0.5, y=1.02,
            xanchor="center", bgcolor="#1b2330", font=dict(color="#dfe6ef"),
            bordercolor="#283142", active=0)],
        margin=dict(l=0, r=0, t=80, b=0),
    )
    fig.write_html(out_path, include_plotlyjs=True, full_html=True)
    return out_path
