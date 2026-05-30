"""
fem.py — 3次元空間トラス（ピン接合）の直接剛性法ソルバ

竹ドームの部材を「両端ピン・軸力のみ負担」とする理想化（=空間トラス）で解く。
竹の縛り/ボルト接合は曲げをほとんど伝えないため、トラス理想化は安全側で妥当。
（接合部の不確実性は安全率で吸収する。design.py を参照）

要素剛性（軸材, グローバル6自由度）:
    方向余弦 r = (dx,dy,dz)/L,  T = r ⊗ r (3x3)
    K_e = (EA/L) * [[ T, -T],
                    [-T,  T]]
部材軸力（引張正）:
    N = (EA/L) * r · (u_j - u_i)

検証は tests/test_fem.py（教科書の閉形解と一致を確認）。
"""
from __future__ import annotations

import numpy as np


class TrussModel:
    """3次元空間トラスモデル。"""

    def __init__(self, nodes: np.ndarray, members: np.ndarray,
                 E, A):
        self.nodes = np.asarray(nodes, dtype=float)
        self.members = np.asarray(members, dtype=int)
        n_m = len(self.members)
        # E, A はスカラ or 部材ごと配列
        self.E = np.full(n_m, float(E)) if np.isscalar(E) else np.asarray(E, float)
        self.A = np.full(n_m, float(A)) if np.isscalar(A) else np.asarray(A, float)
        self.n_nodes = len(self.nodes)
        self.n_dof = 3 * self.n_nodes

        d = self.nodes[self.members[:, 1]] - self.nodes[self.members[:, 0]]
        self.lengths = np.linalg.norm(d, axis=1)
        if np.any(self.lengths < 1e-12):
            raise ValueError("長さ0の部材があります")
        self.dircos = d / self.lengths[:, None]  # (M,3)

        self.fixed_dof: set[int] = set()
        self.loads = np.zeros(self.n_dof)

    # -- 境界条件・荷重 ----------------------------------------------------
    def add_pin_support(self, node: int) -> None:
        """節点の並進3自由度を拘束（ピン支点）。"""
        for k in range(3):
            self.fixed_dof.add(3 * node + k)

    def fix_dof(self, node: int, dof: int) -> None:
        self.fixed_dof.add(3 * node + dof)

    def add_nodal_load(self, node: int, fx=0.0, fy=0.0, fz=0.0) -> None:
        self.loads[3 * node + 0] += fx
        self.loads[3 * node + 1] += fy
        self.loads[3 * node + 2] += fz

    def set_load_vector(self, F: np.ndarray) -> None:
        """全自由度の荷重ベクトル（長さ 3N）を直接設定。"""
        self.loads = np.asarray(F, float).copy()

    # -- 解析 --------------------------------------------------------------
    def assemble(self) -> np.ndarray:
        """全体剛性行列 K (3N x 3N) を組み立てる。"""
        K = np.zeros((self.n_dof, self.n_dof))
        for m, (i, j) in enumerate(self.members):
            r = self.dircos[m]
            k = self.E[m] * self.A[m] / self.lengths[m]
            T = np.outer(r, r) * k
            dofs = [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
            Ke = np.block([[T, -T], [-T, T]])
            for a in range(6):
                for b in range(6):
                    K[dofs[a], dofs[b]] += Ke[a, b]
        return K

    def solve(self) -> dict:
        """変位・反力・部材軸力を解く。"""
        K = self.assemble()
        free = np.array([d for d in range(self.n_dof) if d not in self.fixed_dof])
        if len(free) == 0:
            raise ValueError("自由自由度がありません")

        Kff = K[np.ix_(free, free)]
        Ff = self.loads[free]

        # 特異（機構）検出
        cond = np.linalg.cond(Kff)
        if not np.isfinite(cond) or cond > 1e12:
            raise np.linalg.LinAlgError(
                f"剛性行列が特異（機構/不安定）です。cond={cond:.2e}。"
                "支点・部材配置を確認してください。")

        uf = np.linalg.solve(Kff, Ff)
        u = np.zeros(self.n_dof)
        u[free] = uf

        reactions = K @ u - self.loads  # 拘束自由度に反力が出る
        disp = u.reshape(self.n_nodes, 3)

        # 部材軸力（引張正）と応力
        axial = np.zeros(len(self.members))
        for m, (i, j) in enumerate(self.members):
            r = self.dircos[m]
            du = disp[j] - disp[i]
            axial[m] = self.E[m] * self.A[m] / self.lengths[m] * (r @ du)
        stress = axial / self.A  # Pa（引張正）

        return dict(
            disp=disp, u=u, reactions=reactions.reshape(self.n_nodes, 3),
            axial=axial, stress=stress, cond=float(cond),
            max_disp=float(np.linalg.norm(disp, axis=1).max()),
            max_tension=float(axial.max()), max_compression=float(axial.min()),
        )


def quick_truss(nodes, members, supports, nodal_loads, E, A) -> dict:
    """簡易ヘルパ: supports=[node,...], nodal_loads={node:(fx,fy,fz)}。"""
    model = TrussModel(nodes, members, E, A)
    for s in supports:
        model.add_pin_support(s)
    for node, (fx, fy, fz) in nodal_loads.items():
        model.add_nodal_load(node, fx, fy, fz)
    return model.solve()
