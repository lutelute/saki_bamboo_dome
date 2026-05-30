"""
bamboo.py — 竹（孟宗竹 Moso, Phyllostachys edulis）の材料特性と中空円形断面

数値は research ワークフローで裏取りした査読論文・ISO 22156 由来:
  E ≈ 16 GPa (11-20), 密度 ≈ 770 kg/m³, 引張145 / 圧縮58 / 曲げ130 MPa,
  せん断14 MPa, ポアソン比0.32, 一般的な構造竹: 外径100mm・肉厚10mm。
出典: Zhou et al. 2021 (DOI:10.1177/15589250211066802), ISO 22156:2021,
      ISO 22157:2019, IStructE/Arup Manual。

許容応力は ISO 22156 の考え方で透過的に算出する:
  特性値 f_k = f_mean * (1 - k_s * CoV)        … 5%下側分位（大標本・正規 z=1.645）
  許容応力 f_allow = C_mod * f_k / SF           … C_mod=含水/荷重継続等の修正係数
竹はばらつきが大きい(CoV≈0.2)ため、平均強度をそのまま使わないのが要点。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

G = 9.80665  # 重力加速度 [m/s^2]


# ---------------------------------------------------------------------------
# 材料
# ---------------------------------------------------------------------------
@dataclass
class BambooMaterial:
    """孟宗竹の材料特性（既定値は実測平均, 単位はSI）。"""
    name: str = "孟宗竹 (Moso, Phyllostachys edulis)"
    E: float = 16.0e9            # ヤング率 [Pa]（繊維方向, 設計用代表値）
    density: float = 770.0       # 気乾密度 [kg/m^3]
    poisson: float = 0.32
    # 平均極限強度（クリア試験片）[Pa]
    f_tension_mean: float = 145.0e6
    f_compression_mean: float = 58.0e6
    f_bending_mean: float = 130.0e6
    f_shear_mean: float = 14.0e6
    # 設計係数
    cov: float = 0.20            # 強度の変動係数（竹は大きい）
    ks: float = 1.645            # 5%下側分位係数（大標本・正規）
    SF: float = 2.5             # ASD 全体安全率（特性値に対して）
    SF_buckling: float = 2.5    # 座屈に対する安全率
    C_mod: float = 1.0          # 含水・荷重継続・温度などの修正係数(ISO22156 Ci)

    def characteristic(self, f_mean: float) -> float:
        """平均極限 → 特性値（5パーセンタイル）。"""
        return f_mean * (1.0 - self.ks * self.cov)

    def allowable(self, f_mean: float, sf: float | None = None) -> float:
        """平均極限 → 許容応力 = C_mod * f_k / SF。"""
        sf = self.SF if sf is None else sf
        return self.C_mod * self.characteristic(f_mean) / sf

    # よく使う許容応力（プロパティ）
    @property
    def allow_compression(self) -> float:
        return self.allowable(self.f_compression_mean)

    @property
    def allow_tension(self) -> float:
        return self.allowable(self.f_tension_mean)

    @property
    def allow_bending(self) -> float:
        return self.allowable(self.f_bending_mean)

    @property
    def allow_shear(self) -> float:
        return self.allowable(self.f_shear_mean)


MOSO = BambooMaterial()  # 既定材料


# ---------------------------------------------------------------------------
# 中空円形断面（竹稈）
# ---------------------------------------------------------------------------
@dataclass
class CulmSection:
    """竹稈の中空円形断面。径・肉厚は [m]。"""
    outer_d: float = 0.100   # 外径 [m]
    wall_t: float = 0.010    # 肉厚 [m]

    @property
    def inner_d(self) -> float:
        return self.outer_d - 2.0 * self.wall_t

    @property
    def area(self) -> float:
        """断面積（中実材部）A = π/4 (Do² - Di²) [m^2]。"""
        return np.pi / 4.0 * (self.outer_d**2 - self.inner_d**2)

    @property
    def I(self) -> float:
        """断面二次モーメント I = π/64 (Do⁴ - Di⁴) [m^4]。"""
        return np.pi / 64.0 * (self.outer_d**4 - self.inner_d**4)

    @property
    def r_gyration(self) -> float:
        """回転半径 r = sqrt(I/A) [m]。中空円管では (1/4)sqrt(Do²+Di²)。"""
        return np.sqrt(self.I / self.area)

    @property
    def section_modulus(self) -> float:
        """断面係数 Z = I / (Do/2) [m^3]。"""
        return self.I / (self.outer_d / 2.0)

    def weight_per_length(self, material: BambooMaterial) -> float:
        """自重線荷重 [N/m]。"""
        return material.density * self.area * G

    def summary(self, material: BambooMaterial = MOSO) -> dict:
        return dict(
            outer_d_mm=self.outer_d * 1e3, wall_t_mm=self.wall_t * 1e3,
            inner_d_mm=self.inner_d * 1e3,
            area_cm2=self.area * 1e4, I_cm4=self.I * 1e8,
            r_gyration_mm=self.r_gyration * 1e3,
            weight_per_length_N_m=self.weight_per_length(material),
        )


CULM_100 = CulmSection()  # 既定断面: φ100 × t10


if __name__ == "__main__":
    print("材料:", MOSO.name)
    print(f"  E = {MOSO.E/1e9:.1f} GPa, 密度 = {MOSO.density:.0f} kg/m^3")
    print(f"  許容圧縮 = {MOSO.allow_compression/1e6:.1f} MPa "
          f"(特性値 {MOSO.characteristic(MOSO.f_compression_mean)/1e6:.1f} MPa)")
    print(f"  許容引張 = {MOSO.allow_tension/1e6:.1f} MPa")
    print(f"  許容曲げ = {MOSO.allow_bending/1e6:.1f} MPa")
    print("断面 φ100×t10:")
    for k, v in CULM_100.summary().items():
        print(f"  {k} = {v:.3f}")
