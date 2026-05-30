"""
test_fem.py — 3DトラスソルバFEMの検証

手計算で閉形解が得られる3ケースで軸力・変位を照合する:
  1) 単一軸材        — δ = PL/EA, 軸力 = P
  2) 平面2部材トラス — 対称, 各部材 T = P/√2
  3) 空間トリポッド  — 対称, 各脚 圧縮 = P·L/(3H)
research ワークフローが返す教科書ケースも tests/verification_case.json があれば検証する。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.fem import TrussModel, quick_truss  # noqa: E402

TOL = 1e-6


def approx(a, b, tol=1e-4):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_single_bar():
    E, A, L, P = 200e9, 1e-3, 2.0, 5000.0
    nodes = np.array([[0, 0, 0], [L, 0, 0]], float)
    members = np.array([[0, 1]])
    model = TrussModel(nodes, members, E, A)
    model.add_pin_support(0)
    # 節点1は x 方向のみ自由（軸力試験）。y,z を拘束。
    model.fix_dof(1, 1)
    model.fix_dof(1, 2)
    model.add_nodal_load(1, fx=P)
    r = model.solve()
    delta = r["disp"][1, 0]
    assert approx(delta, P * L / (E * A)), (delta, P * L / (E * A))
    assert approx(r["axial"][0], P), r["axial"]
    print(f"[OK] 単一軸材: δ={delta:.3e} m (理論 {P*L/(E*A):.3e}), N={r['axial'][0]:.1f} N")


def test_planar_two_bar():
    E, A, P = 200e9, 1e-3, 1000.0
    nodes = np.array([[0, 0, 0], [2, 0, 0], [1, 0, -1]], float)
    members = np.array([[0, 2], [1, 2]])
    # 平面(x-z)内の挙動に限定するため全節点の y を拘束
    model = TrussModel(nodes, members, E, A)
    model.add_pin_support(0)
    model.add_pin_support(1)
    model.fix_dof(2, 1)  # node2 の y 拘束
    model.add_nodal_load(2, fz=-P)
    r = model.solve()
    T = P / np.sqrt(2)
    assert approx(r["axial"][0], T, 1e-3), r["axial"]
    assert approx(r["axial"][1], T, 1e-3), r["axial"]
    print(f"[OK] 平面2部材: N=({r['axial'][0]:.1f}, {r['axial'][1]:.1f}) N "
          f"(理論 {T:.1f} 引張)")


def test_space_tripod():
    E, A, P, R, H = 200e9, 1e-3, 3000.0, 2.0, 3.0
    s = np.sqrt(3) / 2
    nodes = np.array([
        [R, 0, 0], [-R / 2, R * s, 0], [-R / 2, -R * s, 0], [0, 0, H]
    ], float)
    members = np.array([[3, 0], [3, 1], [3, 2]])
    model = TrussModel(nodes, members, E, A)
    for i in range(3):
        model.add_pin_support(i)
    model.add_nodal_load(3, fz=-P)
    r = model.solve()
    L = np.sqrt(R**2 + H**2)
    expected = -P * L / (3 * H)  # 圧縮（負）
    for m in range(3):
        assert approx(r["axial"][m], expected, 1e-3), (r["axial"], expected)
    print(f"[OK] 空間トリポッド: 各脚 N={r['axial'][0]:.1f} N "
          f"(理論 {expected:.1f} 圧縮), 頂点沈下={r['disp'][3,2]:.3e} m")


def test_research_case():
    """research ワークフローが出力した教科書ケース（あれば）。"""
    path = os.path.join(os.path.dirname(__file__), "verification_case.json")
    if not os.path.exists(path):
        print("[skip] verification_case.json なし（research 結果待ち）")
        return
    c = json.load(open(path))
    nodes = np.array(c["nodes"], float)
    members = np.array(c["members"], int)
    model = TrussModel(nodes, members, c["material"]["E_Pa"], c["material"]["A_m2"])
    for s in c["supports"]:
        node, fx, fy, fz = s
        if fx: model.fix_dof(node, 0)
        if fy: model.fix_dof(node, 1)
        if fz: model.fix_dof(node, 2)
    for ld in c["loads"]:
        node, Fx, Fy, Fz = ld
        model.add_nodal_load(int(node), Fx, Fy, Fz)
    r = model.solve()
    exp = np.array(c["expected"]["member_axial_forces_N"], float)
    for m in range(len(members)):
        assert approx(r["axial"][m], exp[m], 2e-2), (
            f"部材{m}: 計算 {r['axial'][m]:.1f} N ≠ 期待 {exp[m]:.1f} N")
    print(f"[OK] research検証ケース「{c.get('test_case_name','?')}」 "
          f"{len(members)}部材すべて期待値と一致")


if __name__ == "__main__":
    test_single_bar()
    test_planar_two_bar()
    test_space_tripod()
    test_research_case()
    print("\n全テスト完了")
