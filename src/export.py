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
                           wind_az_deg: float = 0.0, culm_outer_d: float = 0.10) -> str:
    """雪景色Blender用: 幾何＋物理モデルによる各面の積雪深(融雪なし)をJSON出力。"""
    from .snow_sim import accumulate_field
    field = accumulate_field(geo, total_snow_m, wind_drift, wind_az_deg)
    data = dict(
        nodes=geo["nodes"].tolist(),
        members=geo["members"].tolist(),
        faces=geo["faces"].tolist(),
        supports=list(geo["supports"]),
        snow_depth_per_face=field["depth_per_face"].tolist(),  # 鉛直積雪深[m]
        total_snow_m=total_snow_m, wind_drift=wind_drift, wind_az_deg=wind_az_deg,
        culm_outer_d=culm_outer_d,
    )
    import os
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
