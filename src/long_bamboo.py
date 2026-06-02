"""
long_bamboo.py — 竹の特質（長尺・しなる・節間中空）を活かした構造検討

竹は8-20mに育つ長尺中空材。短く分割するほど接合点が増え、コストと弱点が増える。
本モジュールは現状のジオデシック格子の辺から、同一直線上に並ぶ辺を
「1本の長い竹」に統合できる経路を抽出し、必要な竹の本数と長さを再評価する。

#### 検討項目
1. **連続経路抽出**: 各節点で「同一方向に伸びる辺」を直線とみなしグルーピング
2. **長尺竹本数**: 統合後の必要竹本数（接合点が両端のみと仮定）
3. **接合点数**: 削減率
4. **応力評価**: 連続竹は両端ピン接合の長柱として座屈を再検討
"""
import numpy as np


def detect_long_paths(nodes: np.ndarray, members: np.ndarray,
                      angle_tol_deg: float = 15.0):
    """同一方向の連続辺を1本の長尺竹としてまとめる。

    各節点で、接続辺の方向ベクトルを比べ、方向が近いもの同士を「連続」とみなして
    パスを構築する（貪欲法）。

    Returns
    -------
    paths : list[list[int]]   各パス=節点インデックス列（順序つき）
    edge_to_path : dict       元の辺 (i,j) → パスインデックス
    """
    n = len(nodes)
    # 節点ごとの隣接辺リスト
    adj = [[] for _ in range(n)]
    for eidx, (i, j) in enumerate(members):
        adj[i].append((j, eidx))
        adj[j].append((i, eidx))

    used = set()              # 既に消費した辺 eidx
    paths = []                # 各パス = [n0, n1, n2, ...]
    cos_tol = np.cos(np.radians(angle_tol_deg))

    for start_e, (i0, j0) in enumerate(members):
        if start_e in used:
            continue
        # この辺を起点に、両方向に延長
        path = [i0, j0]
        used.add(start_e)
        # j0 方向に延ばす
        while True:
            i_prev, i_cur = path[-2], path[-1]
            v_in = nodes[i_cur] - nodes[i_prev]
            v_in /= np.linalg.norm(v_in) + 1e-9
            best = None
            best_cos = cos_tol
            for nb, e in adj[i_cur]:
                if e in used or nb == i_prev:
                    continue
                v_out = nodes[nb] - nodes[i_cur]
                v_out /= np.linalg.norm(v_out) + 1e-9
                c = float(np.dot(v_in, v_out))
                if c > best_cos:
                    best = (nb, e); best_cos = c
            if best is None:
                break
            path.append(best[0]); used.add(best[1])
        # i0 方向に延ばす
        while True:
            i_prev, i_cur = path[1], path[0]
            v_in = nodes[i_cur] - nodes[i_prev]
            v_in /= np.linalg.norm(v_in) + 1e-9
            best = None
            best_cos = cos_tol
            for nb, e in adj[i_cur]:
                if e in used or nb == i_prev:
                    continue
                v_out = nodes[nb] - nodes[i_cur]
                v_out /= np.linalg.norm(v_out) + 1e-9
                c = float(np.dot(v_in, v_out))
                if c > best_cos:
                    best = (nb, e); best_cos = c
            if best is None:
                break
            path.insert(0, best[0]); used.add(best[1])
        paths.append(path)

    edge_to_path = {}
    for pidx, path in enumerate(paths):
        for k in range(len(path) - 1):
            a, b = path[k], path[k + 1]
            edge_to_path[(min(a, b), max(a, b))] = pidx
    return paths, edge_to_path


def path_lengths(nodes: np.ndarray, paths) -> np.ndarray:
    """各パス（連続竹）の全長 [m]。"""
    return np.array([
        sum(np.linalg.norm(nodes[p[k+1]] - nodes[p[k]]) for k in range(len(p) - 1))
        for p in paths
    ])


def required_culms(lengths: np.ndarray, culm_length: float = 6.0,
                   waste_factor: float = 0.1) -> dict:
    """竹材長(culm_length, 既定6m)で必要本数を計算。

    各パスの長さを culm_length で割って切り上げ＝必要本数（継ぎ手は別途）。
    """
    n_culms_per_path = np.ceil(lengths * (1 + waste_factor) / culm_length).astype(int)
    return dict(
        per_path=n_culms_per_path,
        total=int(n_culms_per_path.sum()),
        total_length_m=float(lengths.sum() * (1 + waste_factor)),
        avg_path_length=float(lengths.mean()),
        max_path_length=float(lengths.max()),
    )


def joint_count(paths) -> dict:
    """パスの両端のみを接合点と仮定したときの総接合数（重複除去）。"""
    joints = set()
    for p in paths:
        joints.add(p[0]); joints.add(p[-1])
    # 中間節点（経路内）は「またぐだけで接合なし」
    return dict(
        joints_with_long_bamboo=len(joints),
        original_nodes=len(set().union(*[set(p) for p in paths])),
    )


def analyze_dome_long_bamboo(geo: dict, culm_length: float = 6.0,
                             angle_tol_deg: float = 15.0):
    """ドーム幾何を「長尺竹活用」の観点で分析。"""
    nodes, members = geo["nodes"], geo["members"]
    paths, e2p = detect_long_paths(nodes, members, angle_tol_deg)
    lens = path_lengths(nodes, paths)
    culms = required_culms(lens, culm_length)
    joints = joint_count(paths)

    # 短材分割（現状）との比較
    n_short_members = len(members)
    n_short_joints = len(set().union(*[{i, j} for i, j in members]))
    n_long_paths = len(paths)
    n_long_joints = joints["joints_with_long_bamboo"]

    return dict(
        paths=paths, path_lengths_m=lens,
        culms=culms,
        # 比較
        short_members=n_short_members,
        short_joints=n_short_joints,
        long_paths=n_long_paths,
        long_joints=n_long_joints,
        joint_reduction_pct=(1 - n_long_joints / n_short_joints) * 100,
        path_reduction_pct=(1 - n_long_paths / n_short_members) * 100,
        # 部材長統計
        path_len_min=float(lens.min()),
        path_len_max=float(lens.max()),
        path_len_mean=float(lens.mean()),
    )


def print_analysis(rep: dict):
    """解析結果を見やすく表示。"""
    print(f"=== 長尺竹活用解析 ===")
    print(f"現状（短材分割）: {rep['short_members']}本の短い部材、接合点{rep['short_joints']}個")
    print(f"長尺竹統合後   : {rep['long_paths']}本の連続パス、接合点{rep['long_joints']}個")
    print(f"  → 接合点 {rep['joint_reduction_pct']:.0f}% 削減")
    print(f"  → 経路 {rep['path_reduction_pct']:.0f}% 削減（1本の竹がカバーする辺数増加）")
    print(f"  → 経路長 {rep['path_len_min']:.2f}〜{rep['path_len_max']:.2f}m"
          f"（平均 {rep['path_len_mean']:.2f}m）")
    print(f"  → 6m竹材換算: {rep['culms']['total']}本必要"
          f"（短材{rep['short_members']}本と比較）")


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.geometry import geodesic_dome
    for v in (1, 2, 3, 4):
        geo = geodesic_dome(v, 4.0, 0.5)
        print(f"\n--- v={v}, R=4m ---")
        rep = analyze_dome_long_bamboo(geo, culm_length=6.0, angle_tol_deg=15)
        print_analysis(rep)
