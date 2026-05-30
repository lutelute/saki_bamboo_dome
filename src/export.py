"""
export.py — 幾何データの書き出し

  ・export_geometry_json : Blender ビルダ用の JSON（nodes/members/supports/axial）
  ・export_mesh          : trimesh で竹シリンダーを実体化し OBJ/STL/GLB 出力
                           （Blender が無くても任意の3Dビューアで開ける）
"""
from __future__ import annotations

import json
import numpy as np


def export_geometry_json(rep: dict, path: str = "output/dome_geometry.json",
                         case: str = "D+S") -> str:
    geo = rep["geo"]
    axial = rep["case_results"][case]["fem"]["axial"]
    data = dict(
        nodes=geo["nodes"].tolist(),
        members=geo["members"].tolist(),
        faces=geo["faces"].tolist(),
        supports=list(geo["supports"]),
        axial=axial.tolist(),
        case=case,
        culm_outer_d=rep["section"].outer_d,
        meta=geo["meta"],
    )
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return path


def export_snow_scene_json(geo: dict, path: str = "output/sim/dome_snow_scene.json",
                           total_snow_m: float = 1.0, wind_drift: float = 0.35,
                           wind_az_deg: float = 0.0, culm_outer_d: float = 0.10,
                           section=None, material=None, rho_snow: float = 300.0,
                           defl_exagg_ratio: float = 0.08) -> str:
    """雪景色Blender用JSON: 幾何＋物理モデルの各面積雪深(融雪なし)＋
    満積雪時のFEM変形(節点変位)＋推奨誇張倍率 を出力。

    Blender側で雪の成長に同期してドームをたわませ、雪冠も追従させる（FEM連成）。
    """
    import os
    import numpy as np
    from .snow_sim import accumulate_field
    from .fem import TrussModel
    from .loads import _face_geom
    from .bamboo import CULM_100, MOSO, G

    section = section or CULM_100
    material = material or MOSO
    field = accumulate_field(geo, total_snow_m, wind_drift, wind_az_deg)
    depth = field["depth_per_face"]
    nodes, members, faces = geo["nodes"], geo["members"], geo["faces"]
    plan, _, _, _ = _face_geom(nodes, faces)

    # 満積雪荷重 + 自重 → FEM変形
    F = np.zeros(3 * len(nodes))
    qface = rho_snow * G * depth                       # [N/m²]
    for fidx, (a, b, c) in enumerate(faces):
        fz = qface[fidx] * plan[fidx] / 3.0
        for nd in (a, b, c):
            F[3 * nd + 2] -= fz
    for m, (i, j) in enumerate(members):
        half = 0.5 * section.weight_per_length(material) * geo["lengths"][m]
        F[3 * i + 2] -= half; F[3 * j + 2] -= half
    model = TrussModel(nodes, members, material.E,
                       section.area * np.ones(len(members)))
    for s in geo["supports"]:
        model.add_pin_support(s)
    model.set_load_vector(F)
    try:
        res = model.solve()
        disp = res["disp"]
        max_disp = float(np.linalg.norm(disp, axis=1).max())
    except Exception:
        disp = np.zeros((len(nodes), 3)); max_disp = 1e-9

    dome_size = 2.0 * geo["meta"]["base_radius"]
    defl_scale = (defl_exagg_ratio * dome_size / max_disp) if max_disp > 1e-9 else 0.0

    data = dict(
        nodes=nodes.tolist(), members=members.tolist(), faces=faces.tolist(),
        supports=list(geo["supports"]),
        snow_depth_per_face=depth.tolist(),            # 鉛直積雪深[m]
        node_disp=disp.tolist(),                       # 満積雪時の節点変位[m]
        defl_scale=defl_scale,                         # 推奨誇張倍率
        max_disp_mm=max_disp * 1e3,
        total_snow_m=total_snow_m, wind_drift=wind_drift, wind_az_deg=wind_az_deg,
        culm_outer_d=culm_outer_d,
    )
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def export_mesh(rep: dict, path: str = "output/dome.glb",
                culm_radius: float | None = None) -> str:
    """竹シリンダーを実体メッシュ化して書き出し（拡張子で形式自動判定）。"""
    import trimesh

    geo = rep["geo"]
    nodes = geo["nodes"]
    members = geo["members"]
    r = culm_radius if culm_radius else rep["section"].outer_d / 2.0

    meshes = []
    for (i, j) in members:
        seg = np.array([nodes[i], nodes[j]])
        cyl = trimesh.creation.cylinder(radius=r, segment=seg, sections=10)
        meshes.append(cyl)
    # 継手スフィア
    nr = r * 1.4
    for k in range(len(nodes)):
        sph = trimesh.creation.icosphere(subdivisions=1, radius=nr)
        sph.apply_translation(nodes[k])
        meshes.append(sph)

    combined = trimesh.util.concatenate(meshes)
    combined.export(path)
    return path
