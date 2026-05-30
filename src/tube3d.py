"""
tube3d.py — 竹部材を実直径の3Dチューブ(円柱)メッシュとして生成

plotly の Mesh3d 用に、節点・部材・竹半径からチューブの頂点・三角面・
頂点強度(色付け用スカラ)を作る。面トポロジ(i,j,k)は座標に依らず一定なので、
荷重ケースごとに x,y,z と intensity だけ差し替えれば変形アニメに使える。
細い線ではなく実際の竹の太さ(φ100mm等)で表示できる。
"""
from __future__ import annotations

import numpy as np


def _perp_basis(d: np.ndarray):
    """方向ベクトル d に直交する単位ベクトル2本 (u, v)。"""
    a = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(d, a)
    u /= np.linalg.norm(u) + 1e-12
    v = np.cross(d, u)
    return u, v


def build_tube_mesh(coords: np.ndarray, members: np.ndarray, values: np.ndarray,
                    radius: float, sides: int = 8):
    """竹部材をチューブ化した Mesh3d 用データを返す。

    coords : (N,3) 節点座標（変形後でも可）
    members: (M,2) 部材
    values : (M,)  各部材のスカラ値（軸力・利用率など, 色付け用）
    radius : 竹の半径 [m]（外径/2）
    戻り値 : dict(x,y,z,i,j,k,intensity)
    """
    coords = np.asarray(coords, float)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    cos_a, sin_a = np.cos(ang), np.sin(ang)

    X, Y, Z, I, J, K, INT = [], [], [], [], [], [], []
    vbase = 0
    for m, (a, b) in enumerate(members):
        p1, p2 = coords[a], coords[b]
        d = p2 - p1
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        d = d / L
        u, vv = _perp_basis(d)
        ring = radius * (cos_a[:, None] * u[None, :] + sin_a[:, None] * vv[None, :])
        r1 = p1[None, :] + ring        # (sides,3)
        r2 = p2[None, :] + ring
        verts = np.vstack([r1, r2])    # (2*sides,3)
        X.extend(verts[:, 0]); Y.extend(verts[:, 1]); Z.extend(verts[:, 2])
        INT.extend([values[m]] * (2 * sides))
        # 側面の三角形（リング1[k],リング1[k+1],リング2[k],リング2[k+1]）
        for k in range(sides):
            k2 = (k + 1) % sides
            a1, b1 = vbase + k, vbase + k2
            a2, b2 = vbase + sides + k, vbase + sides + k2
            I.append(a1); J.append(b1); K.append(a2)
            I.append(b1); J.append(b2); K.append(a2)
        vbase += 2 * sides

    return dict(x=np.array(X), y=np.array(Y), z=np.array(Z),
                i=np.array(I), j=np.array(J), k=np.array(K),
                intensity=np.array(INT))


def tube_coords_intensity(coords, members, values, radius, sides=8):
    """変形ケース差し替え用: x,y,z,intensity のみ（面トポロジは共通なので不要）。"""
    mesh = build_tube_mesh(coords, members, values, radius, sides)
    return mesh["x"], mesh["y"], mesh["z"], mesh["intensity"]
