"""
sim_viz.py — シミュレーション結果のアニメーション出力

  ・wind_cfd_animation_mpl : 風CFD(LBM)の渦度・速度場 mp4
  ・snow_animation_mpl     : 積雪堆積×構造たわみ mp4（3D + 利用率推移）
  ・snow_animation_plotly  : 積雪堆積の自己完結インタラクティブHTML（再生/スライダ）
  ・wind_pressure_plotly   : 方向性風圧 cp の3Dヒートマップ＋変形（静止）
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as _fm
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import plotly.graph_objects as go

# 日本語フォント
_avail = {f.name for f in _fm.fontManager.ttflist}
for _jp in ("Hiragino Sans", "Hiragino Maru Gothic Pro", "YuGothic", "Osaka"):
    if _jp in _avail:
        plt.rcParams["font.family"] = _jp
        break
plt.rcParams["axes.unicode_minus"] = False

_BG = "#0c1016"
_UTIL_SCALE = [[0.0, "#5fd38a"], [0.5, "#f0c14b"], [0.8, "#f0a23a"], [1.0, "#ef6a6a"]]
_SNOW_SCALE = [[0.0, "#1b2330"], [0.3, "#3a6b8a"], [0.7, "#9fc7de"], [1.0, "#ffffff"]]


# ---------------------------------------------------------------------------
# 風 CFD（LBM）アニメーション
# ---------------------------------------------------------------------------
def wind_cfd_animation_mpl(frames: list, solid: np.ndarray, out_path: str,
                           u_in: float = 0.06, fps: int = 20, dpi: int = 110) -> str:
    """渦度場＋速度場の2パネル mp4。frames は LBM2D.run() の出力。"""
    ny, nx = solid.shape
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.6), facecolor=_BG)
    vmax = np.nanmax([np.nanmax(np.abs(f["vort"])) for f in frames]) * 0.6
    smax = np.nanmax([np.nanmax(f["speed"]) for f in frames])

    im1 = ax1.imshow(frames[0]["vort"], origin="lower", cmap="RdBu_r",
                     vmin=-vmax, vmax=vmax, aspect="equal")
    im2 = ax2.imshow(frames[0]["speed"], origin="lower", cmap="turbo",
                     vmin=0, vmax=smax, aspect="equal")
    for ax, t in ((ax1, "渦度（Karman 渦）"), (ax2, "流速")):
        ax.set_facecolor(_BG)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(t, color="#dfe6ef", fontsize=11)
    # 障害物を重ねる
    mask_rgba = np.zeros((ny, nx, 4)); mask_rgba[solid] = [0.5, 0.42, 0.18, 1.0]
    ax1.imshow(mask_rgba, origin="lower"); ax2.imshow(mask_rgba, origin="lower")
    sup = fig.suptitle("", color="#dfe6ef", fontsize=13)

    def update(i):
        f = frames[i]
        im1.set_data(f["vort"]); im2.set_data(f["speed"])
        sup.set_text(f"竹ドーム 風CFD（格子ボルツマン法 D2Q9）  step={f['step']}  "
                     f"流入風速 U={u_in} (格子単位)")
        return im1, im2

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000/fps, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    anim.save(out_path, writer=FFMpegWriter(fps=fps, bitrate=4000), dpi=dpi)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# 積雪堆積アニメーション（matplotlib mp4）
# ---------------------------------------------------------------------------
def _segments(coords, members):
    return np.array([[coords[i], coords[j]] for i, j in members])


def snow_animation_mpl(sim: dict, out_path: str, fps: int = 6, dpi: int = 120) -> str:
    """積雪×たわみの3D ＋ 利用率推移 の2パネル mp4。"""
    nodes, members = sim["nodes"], sim["members"]
    frames = sim["frames"]
    scale = sim["defl_scale"]
    faces = sim["faces"]

    fig = plt.figure(figsize=(13, 6.4), facecolor=_BG)
    ax = fig.add_subplot(121, projection="3d", facecolor=_BG)
    axu = fig.add_subplot(122, facecolor=_BG)

    # 構造（変形 + 利用率色）
    coords0 = nodes + scale * frames[0]["disp"]
    util0 = _member_util(sim, 0)
    lc = Line3DCollection(_segments(coords0, members), cmap="turbo", linewidths=2.2)
    lc.set_array(util0); lc.set_clim(0, 1.2)
    ax.add_collection3d(lc)
    sup = nodes[sim["supports"]]
    ax.scatter(sup[:, 0], sup[:, 1], sup[:, 2], c="#5fd38a", s=28, marker="^")
    _style3d(ax, nodes)
    cb = fig.colorbar(lc, ax=ax, shrink=0.5, pad=0.02); cb.set_label("利用率", color="#8493a8")
    _style_cb(cb)

    # 利用率 vs 時間
    ts = [f["t_hr"] for f in frames]
    us = [f["max_util"] for f in frames]
    axu.plot(ts, us, color="#4ec9d4", lw=1, alpha=0.4)
    pt, = axu.plot([], [], "o-", color="#f0a23a", lw=2)
    axu.axhline(1.0, color="#ef6a6a", ls="--", lw=1)
    axu.set_xlim(0, ts[-1]); axu.set_ylim(0, max(1.3, max(us) * 1.05))
    axu.set_xlabel("経過時間 [時間]", color="#8493a8")
    axu.set_ylabel("最大利用率", color="#8493a8")
    axu.set_title("積雪による構造利用率の推移", color="#dfe6ef")
    axu.tick_params(colors="#5a677b"); axu.set_facecolor(_BG)
    for sp in axu.spines.values():
        sp.set_color("#283142")

    sup_t = fig.suptitle("", color="#dfe6ef", fontsize=13)

    def update(i):
        f = frames[i]
        coords = nodes + scale * f["disp"]
        lc.set_segments(_segments(coords, members))
        lc.set_array(_member_util(sim, i))
        pt.set_data(ts[:i + 1], us[:i + 1])
        col = "崩壊" if f["max_util"] >= 1.0 else "健全"
        sup_t.set_text(f"竹ドーム 積雪シミュレーション  t={f['t_hr']:.0f}時間"
                       f"（{f['t_hr']/24:.1f}日）  クラウン積雪{f['crown_depth_cm']:.0f}cm  "
                       f"最大利用率{f['max_util']:.2f}  [{col}]  変形×{scale:.0f}")
        return lc, pt

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000/fps, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    anim.save(out_path, writer=FFMpegWriter(fps=fps, bitrate=3500), dpi=dpi)
    plt.close(fig)
    return out_path


def _member_util(sim, frame_idx):
    """各部材の利用率（snow_sim が保存した値）。"""
    return sim["frames"][frame_idx]["member_utils"]


# ---------------------------------------------------------------------------
# 積雪堆積アニメーション（plotly 自己完結HTML）
# ---------------------------------------------------------------------------
def snow_animation_plotly(sim: dict, out_path: str) -> str:
    """雪が積もる→ドームがたわむ→崩壊 を再生/スライダで見るHTML。"""
    nodes, members, faces = sim["nodes"], sim["members"], sim["faces"]
    frames_data = sim["frames"]
    scale = sim["defl_scale"]

    # 面メッシュ（雪深で色付け）。頂点ごとに隣接面の平均積雪深。
    n_nodes = len(nodes)
    fi = faces[:, 0]; fj = faces[:, 1]; fk = faces[:, 2]

    def node_depth(depth_per_face):
        acc = np.zeros(n_nodes); cnt = np.zeros(n_nodes)
        for fidx, (a, b, c) in enumerate(faces):
            for nd in (a, b, c):
                acc[nd] += depth_per_face[fidx]; cnt[nd] += 1
        return acc / np.maximum(cnt, 1)

    dmax = max(f["depth"].max() for f in frames_data) * 100 + 1e-6

    def mesh_for(fr):
        coords = nodes + scale * fr["disp"]
        nd = node_depth(fr["depth"]) * 100
        return go.Mesh3d(x=coords[:, 0], y=coords[:, 1], z=coords[:, 2],
                         i=fi, j=fj, k=fk, intensity=nd, colorscale=_SNOW_SCALE,
                         cmin=0, cmax=dmax, opacity=1.0,
                         colorbar=dict(title="積雪深 [cm]", x=1.02),
                         flatshading=True, name="積雪面")

    def lines_for(fr):
        coords = nodes + scale * fr["disp"]
        xs, ys, zs = [], [], []
        for (i, j) in members:
            xs += [coords[i, 0], coords[j, 0], None]
            ys += [coords[i, 1], coords[j, 1], None]
            zs += [coords[i, 2], coords[j, 2], None]
        col = "#ef6a6a" if fr["max_util"] >= 1.0 else "#8a6a3a"
        return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                            line=dict(width=3, color=col), hoverinfo="skip", name="竹")

    pframes = []
    for idx, fr in enumerate(frames_data):
        pframes.append(go.Frame(data=[mesh_for(fr), lines_for(fr)], name=str(idx)))

    fig = go.Figure(data=[mesh_for(frames_data[0]), lines_for(frames_data[0])],
                    frames=pframes)

    rng = np.ptp(nodes, axis=0).max()
    cen = nodes.mean(0)
    play = dict(label="▶ 再生", method="animate",
                args=[None, {"frame": {"duration": 250, "redraw": True},
                             "fromcurrent": True}])
    pause = dict(label="⏸ 停止", method="animate",
                 args=[[None], {"frame": {"duration": 0, "redraw": False},
                                "mode": "immediate"}])
    steps = [dict(method="animate", label=f"{fr['t_hr']:.0f}h",
                  args=[[str(i)], {"frame": {"duration": 0, "redraw": True},
                                   "mode": "immediate"}])
             for i, fr in enumerate(frames_data)]
    collapse = sim["collapse_hr"]
    p = sim["params"]
    fig.update_layout(
        title=dict(text=(f"竹ドーム 積雪堆積シミュレーション（高さ場×FEM連成）<br>"
                         f"<sub>降雪{p['intensity_cm_per_hr']}cm/時・密度{p['rho_snow']:.0f}kg/m³"
                         f"・吹きだまり{p['wind_drift']:.0%}"
                         + (f"　→ t={collapse:.0f}時間で崩壊" if collapse else "")
                         + f"　変形×{scale:.0f}　雪は急斜面で滑落しクラウンに堆積</sub>"),
                   font=dict(color="#dfe6ef", size=14)),
        paper_bgcolor=_BG, font=dict(color="#dfe6ef"),
        scene=dict(xaxis=dict(title="X[m]", range=[cen[0]-rng/2, cen[0]+rng/2],
                              backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   yaxis=dict(title="Y[m]", range=[cen[1]-rng/2, cen[1]+rng/2],
                              backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   zaxis=dict(title="Z[m]", range=[0, rng],
                              backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   aspectmode="data", camera=dict(eye=dict(x=1.6, y=1.6, z=0.9))),
        updatemenus=[dict(type="buttons", showactive=False, buttons=[play, pause],
                          x=0.05, y=0.05, bgcolor="#1b2330", font=dict(color="#dfe6ef"))],
        sliders=[dict(active=0, steps=steps, x=0.15, len=0.8,
                      currentvalue=dict(prefix="経過 ", font=dict(color="#dfe6ef")),
                      bgcolor="#1b2330", font=dict(color="#8493a8"))],
        margin=dict(l=0, r=0, t=70, b=0))
    fig.write_html(out_path, include_plotlyjs=True, full_html=True, auto_play=False)
    return out_path


# ---------------------------------------------------------------------------
# 方向性風圧 cp の3D可視化
# ---------------------------------------------------------------------------
def wind_pressure_plotly(rep: dict, out_path: str, q_wind: float = 730.0,
                         wind_az_deg: float = 0.0) -> str:
    """ドーム表面の外圧係数 cp を3Dヒートマップ表示（風上=正圧, クラウン/風下=負圧）。"""
    from .wind_pressure import node_cp, directional_wind_load
    from .fem import TrussModel
    geo = rep["geo"]
    nodes, members, faces = geo["nodes"], geo["members"], geo["faces"]
    cp = node_cp(geo, wind_az_deg)

    # 風荷重でのたわみ
    model = TrussModel(nodes, members, rep["material"].E,
                       rep["section"].area * np.ones(len(members)))
    for s in geo["supports"]:
        model.add_pin_support(s)
    model.set_load_vector(directional_wind_load(geo, q_wind, wind_az_deg))
    res = model.solve()
    scale = 0.12 * 2 * geo["meta"]["base_radius"] / (res["max_disp"] + 1e-9)
    coords = nodes + scale * res["disp"]

    mesh = go.Mesh3d(x=coords[:, 0], y=coords[:, 1], z=coords[:, 2],
                     i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
                     intensity=cp, colorscale="RdBu_r", cmin=-1.0, cmax=1.0,
                     colorbar=dict(title="外圧係数 cp"), flatshading=True, opacity=0.97)
    # 風向き矢印
    rng = np.ptp(nodes, axis=0).max()
    az = np.radians(wind_az_deg)
    arr = go.Cone(x=[-rng*0.7], y=[0], z=[rng*0.5],
                  u=[np.cos(az)], v=[np.sin(az)], w=[0],
                  sizemode="absolute", sizeref=rng*0.4, anchor="tail",
                  colorscale=[[0, "#5fd38a"], [1, "#5fd38a"]], showscale=False)
    fig = go.Figure([mesh, arr])
    fig.update_layout(
        title=dict(text=(f"竹ドーム 方向性風圧 cp 分布（風向 {wind_az_deg}°）<br>"
                         f"<sub>風上=正圧(赤) / クラウン・風下=負圧/吸込み(青)　"
                         f"最大変位{res['max_disp']*1e3:.1f}mm×{scale:.0f}誇張　"
                         f"cp: Cheng&Fu/EN1991-1-4/AIJ準拠</sub>"),
                   font=dict(color="#dfe6ef", size=14)),
        paper_bgcolor=_BG, font=dict(color="#dfe6ef"),
        scene=dict(xaxis=dict(title="X[m]", backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   yaxis=dict(title="Y[m]", backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   zaxis=dict(title="Z[m]", backgroundcolor=_BG, color="#5a677b", gridcolor="#283142"),
                   aspectmode="data", camera=dict(eye=dict(x=1.7, y=1.4, z=0.8))),
        margin=dict(l=0, r=0, t=70, b=0))
    fig.write_html(out_path, include_plotlyjs=True, full_html=True)
    return out_path


# ---- スタイル補助 ----
def _style3d(ax, nodes):
    rng = np.ptp(nodes, axis=0).max() / 2
    mid = nodes.mean(0)
    ax.set_xlim(mid[0]-rng, mid[0]+rng); ax.set_ylim(mid[1]-rng, mid[1]+rng)
    ax.set_zlim(0, 2*rng)
    ax.set_box_aspect((1, 1, 1))
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.05, 0.07, 0.10, 1.0))
    ax.tick_params(colors="#5a677b", labelsize=7)
    ax.view_init(elev=16, azim=40)


def _style_cb(cb):
    cb.ax.yaxis.set_tick_params(color="#8493a8")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="#8493a8")
