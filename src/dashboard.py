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

_UTIL_SCALE = [[0.0, "#5fd38a"], [0.5, "#f0c14b"], [0.8, "#f0a23a"], [1.0, "#ef6a6a"]]
_BG = "#0c1016"
_FUKUI_SNOW = L.SNOW_FUKUI / 1e3  # kN/m²


def _mini_view(rep: dict, div_id: str, first: bool) -> str:
    """1ドームの軽量3Dビュー（D+S利用率で色分け）のHTML断片を返す。"""
    geo = rep["geo"]
    nodes, members = geo["nodes"], geo["members"]
    cr = rep["case_results"]["D+S"]
    utils = np.array([m["utilization"] for m in cr["check"]["members"]])

    xs, ys, zs, cs = [], [], [], []
    for m, (i, j) in enumerate(members):
        for nd in (i, j):
            xs.append(nodes[nd, 0]); ys.append(nodes[nd, 1]); zs.append(nodes[nd, 2])
            cs.append(utils[m])
        xs.append(None); ys.append(None); zs.append(None); cs.append(utils[m])

    umax = max(1.0, float(utils.max()))
    line = go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                        line=dict(width=3.5, color=cs, colorscale=_UTIL_SCALE,
                                  cmin=0.0, cmax=umax, showscale=False),
                        hoverinfo="skip")
    sup = nodes[geo["supports"]]
    sm = go.Scatter3d(x=sup[:, 0], y=sup[:, 1], z=sup[:, 2], mode="markers",
                      marker=dict(size=2.5, color="#5fd38a"), hoverinfo="skip")
    fig = go.Figure([line, sm])
    fig.update_layout(
        paper_bgcolor=_BG, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        autosize=True, height=300,          # 明示高さ。無いと既定450pxがコンテナで見切れる
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            zaxis=dict(visible=False), aspectmode="data",
            camera=dict(eye=dict(x=1.75, y=1.75, z=1.05)),  # 全体が収まるよう少し引く
            bgcolor=_BG),
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


def build_dashboard(out_path: str = "output/dome_dashboard.html",
                    radii=(1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
                    frequency: int = 3,
                    section: CulmSection = None,
                    height_ratio: float = 0.5,
                    joint_efficiency: float = 0.6) -> str:
    section = section or CulmSection(0.10, 0.010)

    reps, cards, rows = [], [], []
    for r in radii:
        rep = analyze(frequency=frequency, radius=r, height_ratio=height_ratio,
                      section=section, joint_efficiency=joint_efficiency)
        reps.append((r, rep))

    # 比較グラフ
    labels = [f"φ{2*r:.0f}m" for r, _ in reps]
    caps = [rep["capacity"]["q_fail"] / 1e3 for _, rep in reps]
    lens = [rep["geo"]["meta"]["total_length"] for _, rep in reps]
    utils = [rep["case_results"]["D+S"]["check"]["summary"]["max_utilization"]
             for _, rep in reps]
    cap_colors = ["#5fd38a" if c >= _FUKUI_SNOW else "#ef6a6a" for c in caps]
    # 最初にDOMへ出るグラフが plotly.js を読み込む（これが無いと後続が描画失敗）
    chart_cap = _bar(caps, labels, "積雪耐力（崩壊積雪荷重） vs ドーム直径", "kN/m²",
                     hline=_FUKUI_SNOW, colors=cap_colors, incl="cdn")
    chart_len = _bar(lens, labels, "必要な総竹長 vs ドーム直径", "m", colors="#4ec9d4")

    # 各ドームのカード
    for idx, (r, rep) in enumerate(reps):
        m = rep["geo"]["meta"]
        q = rep["quantities"]
        s = rep["case_results"]["D+S"]["check"]["summary"]
        cap = rep["capacity"]["q_fail"] / 1e3
        ok = cap >= _FUKUI_SNOW
        view = _mini_view(rep, f"view{idx}", first=(idx == 0))
        verdict = ("<span class='ok'>✓ 福井の積雪OK</span>" if ok
                   else "<span class='ng'>✗ 福井の積雪NG</span>")
        card = f"""
        <div class="card">
          <h3>φ{2*r:.0f} m ドーム　{verdict}</h3>
          <div class="view">{view}</div>
          <table>
            <tr><td>直径 / 高さ</td><td>{2*r:.0f} m / {m['dome_height']:.1f} m</td></tr>
            <tr><td>水平投影 / 表面積</td><td>{q['plan_area_m2']:.0f} / {q['surface_area_m2']:.0f} m²</td></tr>
            <tr><td>部材 / 節点 / 支点</td><td>{m['n_members']} / {m['n_nodes']} / {m['n_supports']}</td></tr>
            <tr><td>総竹長</td><td>{q['total_length_m']:.0f} m（φ100×6m材 {q['n_culms_6m']}本）</td></tr>
            <tr><td>自重</td><td>{q['total_weight_kg']:.0f} kg</td></tr>
            <tr><td>概算費用</td><td>{q['est_cost_yen']/1e4:.1f} 万円</td></tr>
            <tr><td>D+S 最大利用率</td><td class="{'ng' if s['max_utilization']>1 else 'ok'}">{s['max_utilization']:.2f}</td></tr>
            <tr><td><b>積雪耐力</b></td><td class="{'ok' if ok else 'ng'}"><b>{cap:.2f} kN/m²</b>（≒積雪{cap/0.30:.0f}cm）</td></tr>
          </table>
        </div>"""
        cards.append(card)

    html = _TEMPLATE.format(
        n=len(reps), freq=frequency, sec=f"φ{section.outer_d*1e3:.0f}×t{section.wall_t*1e3:.0f}",
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
<h1>🎍 竹ジオデシックドーム　サイズ比較ダッシュボード</h1>
<p>{n}構成を比較（frequency v={freq}・断面 {sec}・接合効率 η={eta}）。
色分けは D+S（自重＋積雪）の利用率＝緑(余裕)→黄→赤(許容超過)。
判定は福井市の設計積雪 {fukui:.1f} kN/m²（多雪区域・垂直積雪140cm）に対する崩壊余裕。</p>
</header>
<section class="charts">
<div>{chart_cap}</div>
<div>{chart_len}</div>
</section>
<section class="grid">
{cards}
</section>
<p class="legend">小径ほど部材が短く積雪荷重も小さいため安全側。大径化すると総竹長・自重・部材力が増え、
福井の積雪に対しては断面拡大(φ125以上)・frequency増・接合補強が必要になります。
各3Dビューはドラッグで回転できます。</p>
</body></html>"""
