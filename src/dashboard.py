"""
dashboard.py — 複数サイズの竹ドームを一覧比較するHTMLダッシュボード

小径(直径4m)〜大径まで複数構成を解析し、各ドームの回転可能な3Dミニビュー＋
構造指標（部材数・総竹長・自重・積雪耐力・福井の設計積雪に対する合否）を
1枚の自己完結HTMLに並べる。比較グラフ（積雪耐力 vs 直径、総竹長 vs 直径）付き。
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from .analysis import analyze
from .bamboo import CulmSection, MOSO, G
from . import loads as L
from .tube3d import build_tube_mesh

_UTIL_SCALE = [[0.0, "#5fd38a"], [0.5, "#f0c14b"], [0.8, "#f0a23a"], [1.0, "#ef6a6a"]]
_BG = "#0c1016"
_FUKUI_SNOW = L.SNOW_FUKUI / 1e3  # kN/m²


def _mini_view(rep: dict, div_id: str, first: bool) -> str:
    """1ドームの軽量3Dビュー（竹チューブをD+S利用率で色分け）のHTML断片を返す。"""
    geo = rep["geo"]
    nodes, members = geo["nodes"], geo["members"]
    cr = rep["case_results"]["D+S"]
    utils = np.array([m["utilization"] for m in cr["check"]["members"]])
    crad = rep["section"].outer_d / 2.0            # 実際の竹半径

    umax = max(1.0, float(utils.max()))
    mesh = build_tube_mesh(nodes, members, utils, crad, sides=6)
    line = go.Mesh3d(x=mesh["x"], y=mesh["y"], z=mesh["z"],
                     i=mesh["i"], j=mesh["j"], k=mesh["k"],
                     intensity=mesh["intensity"], colorscale=_UTIL_SCALE,
                     cmin=0.0, cmax=umax, showscale=False,
                     flatshading=False, lighting=dict(ambient=0.6, diffuse=0.8),
                     hoverinfo="skip")
    sup = nodes[geo["supports"]]
    sm = go.Scatter3d(x=sup[:, 0], y=sup[:, 1], z=sup[:, 2], mode="markers",
                      marker=dict(size=2.5, color="#5fd38a"), hoverinfo="skip")
    # 地面(z=0)と寸法が分かるよう軸を薄く表示
    g = float(np.max(np.abs(nodes[:, :2]))) * 1.05
    ground = go.Mesh3d(x=[-g, g, g, -g], y=[-g, -g, g, g], z=[0, 0, 0, 0],
                       i=[0, 0], j=[1, 2], k=[2, 3], color="#11161f",
                       opacity=0.5, hoverinfo="skip", showscale=False)
    fig = go.Figure([ground, line, sm])
    ax = dict(backgroundcolor=_BG, color="#5a677b", gridcolor="#222a38",
              showbackground=True, showgrid=True, showticklabels=True,
              tickfont=dict(size=8), zerolinecolor="#3a4660")
    fig.update_layout(
        paper_bgcolor=_BG, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        autosize=True, height=300,          # 明示高さ。無いと既定450pxがコンテナで見切れる
        scene=dict(
            xaxis=dict(title="X[m]", **ax), yaxis=dict(title="Y[m]", **ax),
            zaxis=dict(title="Z[m]", **ax), aspectmode="data",
            camera=dict(eye=dict(x=1.75, y=1.75, z=1.05))),  # 全体が収まるよう少し引く
    )
    return pio.to_html(fig, include_plotlyjs=False,
                       full_html=False, div_id=div_id,
                       config={"displayModeBar": False, "responsive": True})


def _bar(values, labels, title, ylab, hline=None, colors=None, incl=False) -> str:
    fig = go.Figure(go.Bar(x=labels, y=values,
                           marker_color=colors or "#4ec9d4",
                           text=[f"{v:.1f}" for v in values], textposition="outside",
                           textfont=dict(color="#dfe6ef")))
    if hline is not None:
        fig.add_hline(y=hline, line=dict(color="#ef6a6a", dash="dash"),
                      annotation_text=f"福井 設計積雪 {hline:.1f}",
                      annotation_font_color="#ef6a6a")
    fig.update_layout(
        title=dict(text=title, font=dict(color="#dfe6ef", size=14)),
        paper_bgcolor=_BG, plot_bgcolor=_BG, font=dict(color="#8493a8"),
        margin=dict(l=50, r=20, t=40, b=40), height=300,
        xaxis=dict(gridcolor="#283142"), yaxis=dict(title=ylab, gridcolor="#283142"))
    return pio.to_html(fig, include_plotlyjs=incl, full_html=False,
                       config={"displayModeBar": False, "responsive": True})


# 既定の比較構成 (frequency=格子密度, radius=サイズ)。
# 疎な格子(v=1=15本, v=2=60本)から密(v=4=240本)まで、サイズも変えて並べる。
DEFAULT_CONFIGS = [
    (1, 3.0),   # 15本  最小格子（疎）
    (2, 3.0),   # 60本
    (2, 4.0),   # 60本
    (3, 3.0),   # 135本
    (3, 4.0),   # 135本
    (3, 5.0),   # 135本
    (4, 5.0),   # 240本 密
]


def build_dashboard(out_path: str = "output/dome_dashboard.html",
                    configs=None,
                    section: CulmSection = None,
                    height_ratio: float = 0.5,
                    joint_efficiency: float = 0.6) -> str:
    section = section or CulmSection(0.10, 0.010)
    configs = configs or DEFAULT_CONFIGS

    reps = []
    for freq, r in configs:
        rep = analyze(frequency=freq, radius=r, height_ratio=height_ratio,
                      section=section, joint_efficiency=joint_efficiency)
        reps.append((freq, r, rep))

    # 比較グラフ（格子密度×サイズ）。ラベルに部材数を併記。
    labels = [f"v{freq} φ{2*r:.0f}m<br>{rep['geo']['meta']['n_members']}本"
              for freq, r, rep in reps]
    caps = [rep["capacity"]["q_fail"] / 1e3 for _, _, rep in reps]
    lens = [rep["geo"]["meta"]["total_length"] for _, _, rep in reps]
    cap_colors = ["#5fd38a" if c >= _FUKUI_SNOW else "#ef6a6a" for c in caps]
    # 最初にDOMへ出るグラフが plotly.js を読み込む（これが無いと後続が描画失敗）
    chart_cap = _bar(caps, labels, "積雪耐力（崩壊積雪荷重）— 格子密度×サイズ", "kN/m²",
                     hline=_FUKUI_SNOW, colors=cap_colors, incl="cdn")
    chart_len = _bar(lens, labels, "必要な総竹長", "m", colors="#4ec9d4")

    # 各ドームのカード
    cards = []
    for idx, (freq, r, rep) in enumerate(reps):
        m = rep["geo"]["meta"]
        q = rep["quantities"]
        s = rep["case_results"]["D+S"]["check"]["summary"]
        cap = rep["capacity"]["q_fail"] / 1e3
        ok = cap >= _FUKUI_SNOW
        view = _mini_view(rep, f"view{idx}", first=(idx == 0))
        verdict = ("<span class='ok'>✓ 福井の積雪OK</span>" if ok
                   else "<span class='ng'>✗ 福井の積雪NG</span>")
        density = {1: "最小・疎", 2: "粗", 3: "標準", 4: "密"}.get(freq, "")
        card = f"""
        <div class="card">
          <h3>v{freq} φ{2*r:.0f}m ドーム　{verdict}</h3>
          <div class="view">{view}</div>
          <table>
            <tr><td>格子密度 (frequency)</td><td>v={freq}（{density}）</td></tr>
            <tr><td>直径 / 高さ</td><td>{2*r:.0f} m / {m['dome_height']:.1f} m</td></tr>
            <tr><td>部材(竹) / 節点 / 支点</td><td><b>{m['n_members']}本</b> / {m['n_nodes']} / {m['n_supports']}</td></tr>
            <tr><td>平均部材長</td><td>{m['member_len_mean']:.2f} m</td></tr>
            <tr><td>総竹長</td><td>{q['total_length_m']:.0f} m（6m材 {q['n_culms_6m']}本）</td></tr>
            <tr><td>自重 / 概算</td><td>{q['total_weight_kg']:.0f} kg / {q['est_cost_yen']/1e4:.1f}万円</td></tr>
            <tr><td>D+S 最大利用率</td><td class="{'ng' if s['max_utilization']>1 else 'ok'}">{s['max_utilization']:.2f}</td></tr>
            <tr><td><b>積雪耐力</b></td><td class="{'ok' if ok else 'ng'}"><b>{cap:.2f} kN/m²</b>（≒積雪{cap/0.30:.0f}cm）</td></tr>
          </table>
        </div>"""
        cards.append(card)

    html = _TEMPLATE.format(
        n=len(reps), sec=f"φ{section.outer_d*1e3:.0f}×t{section.wall_t*1e3:.0f}",
        eta=joint_efficiency, fukui=_FUKUI_SNOW,
        chart_cap=chart_cap, chart_len=chart_len, cards="\n".join(cards))
    with open(out_path, "w") as f:
        f.write(html)
    return out_path


_TEMPLATE = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>竹ドーム サイズ比較ダッシュボード</title>
<style>
:root{{--bg:#0c1016;--panel:#141a23;--line:#283142;--ink:#dfe6ef;--dim:#8493a8;
--ok:#5fd38a;--ng:#ef6a6a;--cyan:#4ec9d4;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:"Hiragino Sans",sans-serif;
padding:24px;line-height:1.5}}
header{{border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:20px}}
h1{{font-size:20px;font-weight:600;letter-spacing:.03em}}
header p{{color:var(--dim);font-size:13px;margin-top:6px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
@media(max-width:820px){{.charts{{grid-template-columns:1fr}}}}
.charts>div{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.card h3{{font-size:14px;font-weight:600;margin-bottom:8px;display:flex;
justify-content:space-between;align-items:center;gap:8px}}
.view{{height:300px;background:var(--bg);border-radius:8px;overflow:hidden;margin-bottom:10px}}
.view>div,.view .plot-container,.view .svg-container{{height:300px!important}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
td{{padding:3px 4px;border-bottom:1px solid #1b2330}}
td:first-child{{color:var(--dim)}}
td:last-child{{text-align:right;font-family:"IBM Plex Mono",monospace}}
.ok{{color:var(--ok)}}.ng{{color:var(--ng)}}
.legend{{color:var(--dim);font-size:12px;margin-top:18px;border-top:1px solid var(--line);padding-top:12px}}
</style></head><body>
<header>
<h1>🎍 竹ジオデシックドーム　格子密度×サイズ 比較ダッシュボード</h1>
<p>{n}構成を比較（格子密度 v=1〜4＝部材15〜240本・断面 竹{sec}・接合効率 η={eta}）。
竹は実直径のチューブで描画。色分けは D+S（自重＋積雪）の利用率＝緑(余裕)→黄→赤(許容超過)。
判定は福井市の設計積雪 {fukui:.1f} kN/m²（多雪区域・垂直積雪140cm）に対する崩壊余裕。</p>
</header>
<section class="charts">
<div>{chart_cap}</div>
<div>{chart_len}</div>
</section>
<section class="grid">
{cards}
</section>
<p class="legend">格子密度 v が小さいほど部材は少なく(疎)・1本が長くなり座屈しやすく、v が大きいほど部材は多く(密)・短く強い。
小径ほど積雪荷重も小さく安全側。大径・疎格子では断面拡大(φ125以上)・frequency増・接合補強が必要になります。
竹は実直径φ100mmのチューブで描画。各3Dビューはドラッグで回転できます。</p>
</body></html>"""
