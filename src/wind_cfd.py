"""
wind_cfd.py — 2次元 格子ボルツマン法（D2Q9, BGK）による風の流れCFD

ドーム断面まわりの非圧縮流れを解き、流線・渦度・圧力場を可視化する。
OpenFOAM等の外部CFD不要の自己完結ソルバ（numpyベクトル化）。

理論（research 裏取り: Krüger et al. 2017, Succi 2001, Zou-He 1997）:
  速度 e_i, 重み w_i (cs²=1/3),
  平衡分布 feq_i = w_i ρ (1 + 3 e·u + 4.5(e·u)² − 1.5 u·u),
  BGK 衝突 f = f − (1/τ)(f − feq),  移流 streaming = np.roll,
  障害物: ハーフウェイ bounce-back,  流入: Zou-He 速度境界,  流出: 勾配ゼロ,
  動粘性 ν = cs²(τ−0.5),  Re = U·L/ν。
検証: 円柱まわりの Karman 渦列 Strouhal数 St≈0.16〜0.20 (Re=100〜200)。
"""
from __future__ import annotations

import numpy as np

# D2Q9 格子
EX = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1])
EY = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1])
W = np.array([4/9, 1/9, 1/9, 1/9, 1/9, 1/36, 1/36, 1/36, 1/36])
OPP = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6])  # 反対方向（bounce-back用）
COL_R = [1, 5, 8]   # ex>0（左流入で未知の入射方向）
COL_0 = [0, 2, 4]   # ex=0
COL_L = [3, 6, 7]   # ex<0（右流出で未知の入射方向）
CS2 = 1.0 / 3.0


def equilibrium(rho, ux, uy):
    """平衡分布 feq (9, ny, nx)。"""
    eu = 3.0 * (EX[:, None, None] * ux + EY[:, None, None] * uy)
    usq = 1.5 * (ux * ux + uy * uy)
    return W[:, None, None] * rho * (1.0 + eu + 0.5 * eu * eu - usq)


class LBM2D:
    """2D D2Q9 BGK 格子ボルツマンソルバ。"""

    def __init__(self, nx: int, ny: int, solid: np.ndarray,
                 u_in: float = 0.06, Re: float = 150.0, L: float = None):
        self.nx, self.ny = nx, ny
        self.solid = solid.astype(bool)            # (ny, nx) True=障害物
        self.u_in = u_in
        L = L if L else max(1.0, solid.sum(axis=0).max())  # 代表長さ（障害物高さ）
        self.L = L
        nu = u_in * L / Re                          # 動粘性
        self.tau = 0.5 + 3.0 * nu
        self.omega = 1.0 / self.tau
        self.Re = Re
        self.uy_in = 0.0   # 流入の縦速度（渦放出誘発の一時擾乱に使う）
        # 初期化: 一様流の平衡分布 + 渦放出を誘発する微小擾乱
        rho = np.ones((ny, nx))
        ux = np.full((ny, nx), u_in)
        uy = 1e-3 * u_in * np.sin(2 * np.pi * np.arange(ny)[:, None] / ny) \
            * np.ones((1, nx))
        ux[self.solid] = 0.0
        uy[self.solid] = 0.0
        self.f = equilibrium(rho, ux, uy)
        self.step_count = 0

    def macroscopic(self, f=None):
        f = self.f if f is None else f
        rho = f.sum(0)
        ux = (f * EX[:, None, None]).sum(0) / rho
        uy = (f * EY[:, None, None]).sum(0) / rho
        return rho, ux, uy

    def step(self):
        """Latt 方式: 流出→巨視量→流入Zou-He→衝突→bounce-back→移流。"""
        f = self.f
        # --- 流出（右端）: 左向き成分を内側からコピー（勾配ゼロ） ---
        f[COL_L, :, -1] = f[COL_L, :, -2]

        rho, ux, uy = self.macroscopic(f)

        # --- 流入（左端）: Zou-He 速度境界 ux=u_in, uy=uy_in ---
        ux[:, 0] = self.u_in
        uy[:, 0] = self.uy_in
        rho[:, 0] = (f[COL_0, :, 0].sum(0) + 2 * f[COL_L, :, 0].sum(0)) / (1.0 - self.u_in)

        feq = equilibrium(rho, ux, uy)
        # 入射方向(COL_R)を非平衡bounce-backで設定
        for i in COL_R:
            f[i, :, 0] = feq[i, :, 0] + f[OPP[i], :, 0] - feq[OPP[i], :, 0]

        # --- 衝突（BGK） ---
        fout = f - self.omega * (f - feq)

        # --- 障害物: ハーフウェイ bounce-back（衝突前 f の反対方向） ---
        for i in range(9):
            fout[i][self.solid] = f[OPP[i]][self.solid]

        # --- 移流（streaming） ---
        for i in range(9):
            f[i] = np.roll(fout[i], (EY[i], EX[i]), axis=(0, 1))

        self.f = f
        self.step_count += 1

    def run(self, n_steps: int, record_every: int = 20, warmup: int = 0):
        """n_steps 実行し、record_every ごとに (ux,uy,vort,p,speed) を記録。"""
        frames = []
        for s in range(n_steps):
            self.step()
            if s >= warmup and (s - warmup) % record_every == 0:
                frames.append(self.fields())
        return frames

    def fields(self):
        rho, ux, uy = self.macroscopic()
        ux = ux.copy(); uy = uy.copy()
        ux[self.solid] = 0.0
        uy[self.solid] = 0.0
        speed = np.sqrt(ux**2 + uy**2)
        vort = np.gradient(uy, axis=1) - np.gradient(ux, axis=0)
        vort[self.solid] = np.nan
        p = CS2 * (rho - 1.0)                      # ゲージ圧（格子単位）
        p[self.solid] = np.nan
        return dict(ux=ux, uy=uy, speed=speed, vort=vort, p=p, step=self.step_count)


# ---------------------------------------------------------------------------
# 障害物マスク
# ---------------------------------------------------------------------------
def dome_mask(nx: int, ny: int, cx: int, radius: int, ground: int = 3):
    """地面(下から groundピクセル)に載る半円ドーム＋天井壁のマスク。"""
    solid = np.zeros((ny, nx), dtype=bool)
    solid[:ground, :] = True                       # 地面
    solid[-1, :] = True                            # 天井壁（縦periodic巻込み防止）
    yy, xx = np.mgrid[0:ny, 0:nx]
    cy = ground
    dome = ((xx - cx)**2 + (yy - cy)**2 <= radius**2) & (yy >= cy)
    solid |= dome
    return solid


def cylinder_mask(nx: int, ny: int, cx: int, cy: int, radius: int):
    """検証用: 一様流中の円柱。"""
    yy, xx = np.mgrid[0:ny, 0:nx]
    return (xx - cx)**2 + (yy - cy)**2 <= radius**2


# ---------------------------------------------------------------------------
# 検証: 円柱の Strouhal 数
# ---------------------------------------------------------------------------
def verify_strouhal(Re: float = 120.0, D: int = 32, nx: int = 560, ny: int = 180,
                    n_steps: int = 30000, u_in: float = 0.07) -> dict:
    """円柱後流の uy を FFT し Strouhal 数 St=fD/U を推定。

    Williamson: St = 0.2120(1 − 21.2/Re)。Re=120 で St≈0.174。
    渦放出は流入を一時的に傾けて(uy_in)非対称性を注入して誘発する。
    """
    cx, cy = nx // 4, ny // 2
    solid = cylinder_mask(nx, ny, cx, cy, D // 2)
    sim = LBM2D(nx, ny, solid, u_in=u_in, Re=Re, L=D)
    px, py = min(cx + 4 * D, nx - 2), cy + D // 3    # 後流プローブ(4D下流・やや上)
    signal = []
    for s in range(n_steps):
        # 過渡: 最初の一定区間だけ流入を傾けて対称性を破る
        sim.uy_in = (0.06 * u_in) if s < 600 else 0.0
        sim.step()
        if s > n_steps // 2:                         # 後半のみ記録（過渡を捨てる）
            _, _, uy = sim.macroscopic()
            signal.append(uy[py, px])
    sig = np.array(signal) - np.mean(signal)
    freqs = np.fft.rfftfreq(len(sig), d=1.0)
    amp = np.abs(np.fft.rfft(sig))
    amp[0] = 0
    f_peak = freqs[np.argmax(amp)]
    St = f_peak * D / sim.u_in
    St_expected = 0.2120 * (1 - 21.2 / Re)
    return dict(Re=Re, St=float(St), St_expected=float(St_expected),
                tau=sim.tau, f_peak=float(f_peak), amp_peak=float(amp.max()),
                rel_err=float(abs(St - St_expected) / St_expected))


if __name__ == "__main__":
    print("円柱 Strouhal 検証中（数千ステップ, 1分程度）...")
    r = verify_strouhal()
    print(f"  Re={r['Re']:.0f}  τ={r['tau']:.3f}")
    print(f"  St(計算)={r['St']:.3f}  St(Williamson)={r['St_expected']:.3f}  "
          f"相対誤差={r['rel_err']*100:.1f}%")
