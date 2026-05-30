"""
viz_mpl.py — matplotlib による竹ドーム3D可視化（静止画PNG）

軸力（圧縮=シアン / 引張=アンバー）と利用率（NG=赤）で色分けした
2パネル図を出力する。配色は既存HTMLツールと統一。
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from mpl_toolkits.mplot3d.art3d import Line3DCollection

# 日本語フォント（macOS）。利用可能な候補を順に試す。
import matplotlib.font_manager as _fm
_avail = {f.name for f in _fm.fontManager.ttflist}
for _jp in ("Hiragino Sans", "Hiragino Maru Gothic Pro", "YuGothic",
            "Apple SD Gothic Neo", "Osaka"):
    if _jp in _avail:
        plt.rcParams["font.family"] = _jp
        break
plt.rcParams["axes.unicode_minus"] = False  # マイナス記号の豆腐化防止

# 配色（既存HTMLと統一）: 圧縮 cyan, 引張 amber
_CMAP_FORCE = LinearSegmentedColormap.from_list(
    "force", ["#4ec9d4", "#1b2330", "#f0a23a"])  # 圧縮 - 中立 - 引張
_CMAP_UTIL = LinearSegmentedColormap.from_list(
    "util", ["#5fd38a", "#f0c14b", "#ef6a6a"])     # OK - 注意 - NG


def _segments(nodes, members):
    return np.array([[nodes[i], nodes[j]] for i, j in members])


def plot_dome(rep: dict, case: str = "D+S", out_path: str = "output/dome.png",
              dpi: int = 130) -> str:
    """軸力図 + 利用率図の2パネルPNGを出力。"""
    geo = rep["geo"]
    nodes = geo["nodes"]
    members = geo["members"]
    cr = rep["case_results"][case]
    axial = cr["fem"]["axial"]                     # N（引張+）
    utils = np.array([m["utilization"] for m in cr["check"]["members"]])
    segs = _segments(nodes, members)

    fig = plt.figure(figsize=(15, 7.2), facecolor="#0c1016")

    # ---- パネル1: 軸力 ----
    ax1 = fig.add_subplot(121, projection="3d", facecolor="#0c1016")
    amax = np.abs(axial).max() + 1e-9
    norm = TwoSlopeNorm(vmin=-amax, vcenter=0.0, vmax=amax)
    lc1 = Line3DCollection(segs, cmap=_CMAP_FORCE, norm=norm, linewidths=2.2)
    lc1.set_array(axial)
    ax1.add_collection3d(lc1)
    _scatter_supports(ax1, geo)
    _style_axes(ax1, nodes)
    ax1.set_title(f"軸力分布 [{case}]  圧縮◀ シアン / 引張 アンバー▶",
                  color="#dfe6ef", fontsize=11)
    cb1 = fig.colorbar(lc1, ax=ax1, shrink=0.5, pad=0.02)
    cb1.set_label("軸力 N [kN]", color="#8493a8")
    cb1.formatter = matplotlib.ticker.FuncFormatter(lambda t, _: f"{t/1e3:.0f}")
    cb1.update_ticks()
    _style_cbar(cb1)

    # ---- パネル2: 利用率 ----
    ax2 = fig.add_subplot(122, projection="3d", facecolor="#0c1016")
    lc2 = Line3DCollection(segs, cmap=_CMAP_UTIL, linewidths=2.2)
    lc2.set_array(utils)
    lc2.set_clim(0.0, max(1.0, utils.max()))
    ax2.add_collection3d(lc2)
    # NG部材を強調
    ng = utils > 1.0
    if ng.any():
        lc_ng = Line3DCollection(segs[ng], colors="#ff3b3b", linewidths=4.0)
        ax2.add_collection3d(lc_ng)
    _scatter_supports(ax2, geo)
    _style_axes(ax2, nodes)
    s = cr["check"]["summary"]
    ttl = (f"利用率分布 [{case}]  最大={s['max_utilization']:.2f}  "
           f"{'NG ' + str(s['n_overstressed']) + '部材' if s['n_overstressed'] else 'OK'}")
    ax2.set_title(ttl, color="#dfe6ef", fontsize=11)
    cb2 = fig.colorbar(lc2, ax=ax2, shrink=0.5, pad=0.02)
    cb2.set_label("利用率 N/許容", color="#8493a8")
    _style_cbar(cb2)

    fig.suptitle(
        f"竹ジオデシックドーム  v={rep['params']['frequency']}  "
        f"R={rep['params']['radius']:.1f}m  "
        f"部材{geo['meta']['n_members']}本  総竹長{geo['meta']['total_length']:.0f}m",
        color="#dfe6ef", fontsize=13, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=dpi, facecolor="#0c1016", bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_geometry(rep: dict, out_path: str = "output/dome_geometry.png",
                  dpi: int = 130) -> str:
    """格子形状のみ（解析前のモデル確認用）。"""
    geo = rep["geo"]
    nodes, members = geo["nodes"], geo["members"]
    fig = plt.figure(figsize=(8, 7.5), facecolor="#0c1016")
    ax = fig.add_subplot(111, projection="3d", facecolor="#0c1016")
    lc = Line3DCollection(_segments(nodes, members), colors="#4ec9d4",
                          linewidths=1.6, alpha=0.9)
    ax.add_collection3d(lc)
    ax.scatter(nodes[:, 0], nodes[:, 1], nodes[:, 2], c="#f0a23a", s=8)
    _scatter_supports(ax, geo)
    _style_axes(ax, nodes)
    ax.set_title("格子構造（ジオデシック測地線シェル）", color="#dfe6ef")
    fig.savefig(out_path, dpi=dpi, facecolor="#0c1016", bbox_inches="tight")
    plt.close(fig)
    return out_path


# ---- スタイル補助 ----
def _scatter_supports(ax, geo):
    sup = geo["nodes"][geo["supports"]]
    ax.scatter(sup[:, 0], sup[:, 1], sup[:, 2], c="#5fd38a", s=40,
               marker="^", depthshade=False, label="支点")


def _style_axes(ax, nodes):
    rng = np.ptp(nodes, axis=0).max() / 2.0
    mid = nodes.mean(axis=0)
    ax.set_xlim(mid[0] - rng, mid[0] + rng)
    ax.set_ylim(mid[1] - rng, mid[1] + rng)
    ax.set_zlim(nodes[:, 2].min(), nodes[:, 2].min() + 2 * rng)
    ax.set_box_aspect((1, 1, 1))
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((0.05, 0.07, 0.10, 1.0))
        axis.label.set_color("#8493a8")
    ax.tick_params(colors="#5a677b", labelsize=7)
    ax.view_init(elev=18, azim=35)


def _style_cbar(cb):
    cb.ax.yaxis.set_tick_params(color="#8493a8")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="#8493a8")
