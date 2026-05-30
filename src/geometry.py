"""
geometry.py — ジオデシックドーム（測地線格子シェル）の幾何生成

正二十面体（icosahedron）を frequency v で細分割し、球面に投影、
水平面でカットして「格子状のドーム」を生成する。

出力は構造解析・可視化・Blender 出力で共通利用する素直なデータ構造:
    nodes:    (N, 3) ndarray  — 節点座標 [m]
    members:  (M, 2) int ndarray — 部材（=竹）両端の節点インデックス
    supports: list[int]        — 支点（基礎リング）となる節点インデックス

「格子状の構造」= 三角形格子のラチスシェル。三角形分割は面内せん断剛性が高く、
ピン接合（竹の縛り接合の理想化）でも形状を保持できるためドームに適する。
"""
from __future__ import annotations

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0  # 黄金比


# ---------------------------------------------------------------------------
# 正二十面体
# ---------------------------------------------------------------------------
def icosahedron() -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """単位球に内接する正二十面体の頂点(12)と三角形面(20)を返す。"""
    verts = []
    for a in (-1.0, 1.0):
        for b in (-PHI, PHI):
            verts.append((0.0, a, b))
            verts.append((a, b, 0.0))
            verts.append((b, 0.0, a))
    verts = np.array(verts, dtype=float)
    # 重複除去（上の生成は重複を含まないが安全側で）
    verts = _unique_rows(verts)[0]
    verts /= np.linalg.norm(verts, axis=1, keepdims=True)  # 単位球に正規化

    # 面: 最近接の頂点同士で辺長が等しい三角形を抽出する代わりに、
    # 既知の辺長（正二十面体の辺長 = 2/PHI/... ）で隣接判定する。
    # 単位球上の正二十面体の辺長は 1.0515... (= 2/sqrt(PHI*sqrt(5)))。
    edge_len = np.linalg.norm(verts[0] - verts[_nearest(verts, 0)])
    faces = _faces_from_adjacency(verts, edge_len)
    return verts, faces


def _nearest(verts: np.ndarray, i: int) -> int:
    d = np.linalg.norm(verts - verts[i], axis=1)
    d[i] = np.inf
    return int(np.argmin(d))


def _faces_from_adjacency(verts: np.ndarray, edge_len: float) -> list[tuple[int, int, int]]:
    """辺長で隣接行列を作り、三角形（3頂点が相互に隣接）を列挙。"""
    n = len(verts)
    tol = edge_len * 0.05
    adj = np.zeros((n, n), dtype=bool)
    for i in range(n):
        d = np.linalg.norm(verts - verts[i], axis=1)
        adj[i] = np.abs(d - edge_len) < tol
    faces = []
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j]:
                continue
            for k in range(j + 1, n):
                if adj[i, k] and adj[j, k]:
                    faces.append((i, j, k))
    return faces


# ---------------------------------------------------------------------------
# 細分割 + 球面投影
# ---------------------------------------------------------------------------
def geodesic_sphere(frequency: int = 2, radius: float = 1.0
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """frequency v のジオデシック球の節点・辺・三角形面を生成。

    各正二十面体の面を v×v の三角格子に細分割し、各細分頂点を球面へ投影する。
    戻り値: (nodes, members, faces)
    """
    if frequency < 1:
        raise ValueError("frequency は 1 以上")
    base_v, faces = icosahedron()
    v = frequency

    coords = []          # 細分頂点（重複あり）
    edges = set()        # (a, b) ソート済みインデックス対
    faces_list = []      # (a, b, c) 三角形面（荷重の負担面積計算用）
    index_cache: dict[tuple, int] = {}

    def add_point(p: np.ndarray) -> int:
        p = p / np.linalg.norm(p)  # 球面に投影
        key = tuple(np.round(p, 7))
        idx = index_cache.get(key)
        if idx is None:
            idx = len(coords)
            index_cache[key] = idx
            coords.append(p)
        return idx

    for (ia, ib, ic) in faces:
        A, B, C = base_v[ia], base_v[ib], base_v[ic]
        # 重心座標格子: grid[i][j], i+j <= v
        grid = {}
        for i in range(v + 1):
            for j in range(v + 1 - i):
                k = v - i - j
                p = (k * A + i * B + j * C) / v
                grid[(i, j)] = add_point(p)
        # 小三角形の辺を追加
        for i in range(v):
            for j in range(v - i):
                a = grid[(i, j)]
                b = grid[(i + 1, j)]
                c = grid[(i, j + 1)]
                _add_edge(edges, a, b)
                _add_edge(edges, a, c)
                _add_edge(edges, b, c)
                faces_list.append((a, b, c))      # 上向き三角形
                # 上向き三角形と対になる下向き三角形
                if i + j < v - 1:
                    d = grid[(i + 1, j + 1)]
                    _add_edge(edges, b, d)
                    _add_edge(edges, c, d)
                    faces_list.append((b, d, c))  # 下向き三角形

    nodes = np.array(coords) * radius
    members = np.array(sorted(edges), dtype=int)
    faces = np.array(faces_list, dtype=int)
    return nodes, members, faces


def _add_edge(edges: set, a: int, b: int) -> None:
    if a != b:
        edges.add((a, b) if a < b else (b, a))


# ---------------------------------------------------------------------------
# ドーム化（カット）
# ---------------------------------------------------------------------------
def geodesic_dome(frequency: int = 3, radius: float = 4.0,
                  height_ratio: float = 0.5, ground_snap: bool = True,
                  ) -> dict:
    """ジオデシックドームを生成する。

    Parameters
    ----------
    frequency    : 細分割頻度 v（1,2,3,4...）。大きいほど部材が増え滑らか。
    radius       : 球半径 [m]
    height_ratio : ドーム高さ / 直径。0.5=半球, <0.5=浅いキャップ, >0.5=半球超。
    ground_snap  : True なら基礎リング節点を共通の地面高さに揃える（平らな基礎）。

    Returns
    -------
    dict(nodes, members, supports, meta)
    """
    nodes, members, faces = geodesic_sphere(frequency, radius)

    z_top = radius
    z_cut = z_top - height_ratio * 2.0 * radius  # 残す下限 z
    keep = nodes[:, 2] >= z_cut - 1e-9

    # 残す節点のみで再番号付け
    old2new = -np.ones(len(nodes), dtype=int)
    old2new[keep] = np.arange(keep.sum())
    new_nodes = nodes[keep].copy()

    new_members = []
    for a, b in members:
        if keep[a] and keep[b]:
            new_members.append((old2new[a], old2new[b]))
    new_members = np.array(new_members, dtype=int)

    new_faces = []
    for a, b, c in faces:
        if keep[a] and keep[b] and keep[c]:
            new_faces.append((old2new[a], old2new[b], old2new[c]))
    new_faces = np.array(new_faces, dtype=int)

    # 基礎リング = 「最下層の1リングのみ」を選ぶ。
    # 固定帯(0.04R)だと非半球カット時に上のリングまで巻き込み内部節点を
    # 誤って支点化・変位させてしまうため、実際の層間隔に応じた許容差を使う。
    z = new_nodes[:, 2]
    z_min = float(z.min())
    layers = np.sort(np.unique(np.round(z, 6)))
    if len(layers) > 1:
        gap = layers[1] - layers[0]
        tol = min(0.49 * gap, 0.04 * radius)  # 次の層に届かない範囲に制限
    else:
        tol = 1e-6 * radius
    supports = np.where(z <= z_min + tol)[0].tolist()

    if ground_snap:
        new_nodes[supports, 2] = z_min  # 最下リングのみ平らな基礎高さへ

    lengths = _member_lengths(new_nodes, new_members)
    meta = dict(
        frequency=frequency, radius=radius, height_ratio=height_ratio,
        n_nodes=len(new_nodes), n_members=len(new_members),
        n_faces=len(new_faces), n_supports=len(supports),
        dome_height=float(new_nodes[:, 2].max() - new_nodes[:, 2].min()),
        base_radius=float(np.max(np.linalg.norm(new_nodes[supports, :2], axis=1))),
        total_length=float(lengths.sum()),
        member_len_min=float(lengths.min()), member_len_max=float(lengths.max()),
        member_len_mean=float(lengths.mean()),
    )
    return dict(nodes=new_nodes, members=new_members, faces=new_faces,
                supports=supports, lengths=lengths, meta=meta)


def _member_lengths(nodes: np.ndarray, members: np.ndarray) -> np.ndarray:
    d = nodes[members[:, 0]] - nodes[members[:, 1]]
    return np.linalg.norm(d, axis=1)


# ---------------------------------------------------------------------------
# 補助
# ---------------------------------------------------------------------------
def _unique_rows(a: np.ndarray, tol: int = 6):
    """行の重複除去（丸めキー）。戻り値: (unique, inverse_index)。"""
    keyed = np.round(a, tol)
    seen: dict[tuple, int] = {}
    inv = np.empty(len(a), dtype=int)
    out = []
    for i, row in enumerate(keyed):
        key = tuple(row)
        if key not in seen:
            seen[key] = len(out)
            out.append(a[i])
        inv[i] = seen[key]
    return np.array(out), inv


if __name__ == "__main__":
    for v in (1, 2, 3, 4):
        d = geodesic_dome(frequency=v, radius=4.0, height_ratio=0.5)
        m = d["meta"]
        print(f"v={v}: 節点{m['n_nodes']:4d}  部材{m['n_members']:4d}  "
              f"支点{m['n_supports']:3d}  総竹長{m['total_length']:7.1f} m  "
              f"高さ{m['dome_height']:.2f} m  基礎半径{m['base_radius']:.2f} m")
