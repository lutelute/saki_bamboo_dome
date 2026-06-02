"""
mpm_snow.py — MPM(Material Point Method)による「粘着する雪」シミュレーション

Stomakhin et al. 2013 (Disney『アナと雪の女王』) の弾塑性スノー構成則を MLS-MPM で実装。
雪の凝着・パッキング・焼結・脆性破壊は、変形勾配 F の特異値クランプと指数硬化
 h=exp(ξ(1−J_p)) として「創発的」に表現される（明示的ボンド不要）。
Taichi で Apple Silicon (Metal/CPU) 実行。ドーム上＋地面に降雪を堆積させる。

座標: 単位立方体[0,1]³で計算し、出力時に実寸[m]・Z-upへ変換（×WORLD_SCALE）。
パラメータ(裏取り Stomakhin 2013 Table2): E=1.4e5, ν=0.2, θ_c=0.025, θ_s=0.0075, ξ=10。

実行:
  .venv-mpm/bin/python -m src.mpm_snow            # 単体プロトタイプ
  （通常は tools/bake_mpm.py から .ply 列を書き出す）
"""
import numpy as np
import taichi as ti


@ti.data_oriented
class MPMSnow:
    def __init__(self, n_grid=128, max_particles=300_000, arch="cpu",
                 dome_radius_m=4.0, dome_height_m=3.9, world_scale=10.0,
                 E=1.4e5, nu=0.2, rho=400.0,
                 theta_c=2.5e-2, theta_s=7.5e-3, xi=10.0,
                 dt=5e-5, gravity=14.0, dome_sticky=True):
        ti.init(arch=(ti.metal if arch == "metal" else ti.cpu),
                default_fp=ti.f32, random_seed=1)
        self.n_grid = n_grid
        self.dx = 1.0 / n_grid
        self.inv_dx = float(n_grid)
        self.dt = dt
        self.max_particles = max_particles
        self.world_scale = world_scale

        # 材料
        self.p_vol = (self.dx * 0.5) ** 3
        self.p_rho = rho
        self.p_mass = self.p_vol * self.p_rho
        self.mu_0 = E / (2 * (1 + nu))
        self.lambda_0 = E * nu / ((1 + nu) * (1 - 2 * nu))
        self.theta_c = theta_c
        self.theta_s = theta_s
        self.xi = xi
        self.gravity = gravity
        self.dome_sticky = dome_sticky

        # ドーム(正規化座標): 半径 R, 底 z=floor の半球を固体衝突体とする
        self.world_scale = world_scale
        self.dome_R = dome_radius_m / world_scale
        self.floor_z = 0.06                          # 地面の高さ(正規化)
        self.dome_c = ti.Vector([0.5, 0.5, self.floor_z])

        # フィールド
        self.x = ti.Vector.field(3, ti.f32, max_particles)
        self.v = ti.Vector.field(3, ti.f32, max_particles)
        self.C = ti.Matrix.field(3, 3, ti.f32, max_particles)
        self.F = ti.Matrix.field(3, 3, ti.f32, max_particles)
        self.Jp = ti.field(ti.f32, max_particles)
        self.n_active = ti.field(ti.i32, ())
        self.grid_v = ti.Vector.field(3, ti.f32, (n_grid, n_grid, n_grid))
        self.grid_m = ti.field(ti.f32, (n_grid, n_grid, n_grid))
        self.n_active[None] = 0

    # -- 降雪エミッタ: 上空の円盤から count 個を投入 --
    @ti.kernel
    def _emit(self, start: int, count: int, cx: float, cy: float,
              cz: float, radius: float, vz: float):
        for k in range(count):
            p = start + k
            r = radius * ti.sqrt(ti.random())
            a = ti.random() * 2.0 * np.pi
            self.x[p] = ti.Vector([cx + r * ti.cos(a), cy + r * ti.sin(a),
                                   cz + 0.04 * (ti.random() - 0.5)])
            self.v[p] = ti.Vector([0.0, 0.0, vz])
            self.F[p] = ti.Matrix.identity(ti.f32, 3)
            self.C[p] = ti.Matrix.zero(ti.f32, 3, 3)
            self.Jp[p] = 1.0

    def emit(self, count, vz=-2.5, height=None):
        start = self.n_active[None]
        count = min(count, self.max_particles - start)
        if count <= 0:
            return 0
        # 投入高さ＝現在の雪山頂上のすぐ上（height指定）。落下距離をほぼ0にし、
        # 「空中の板」を作らず雪面に着地→下から積もる。初期はドーム頂部直上。
        z = height if height is not None else (self.dome_c[2] + self.dome_R + 0.03)
        self._emit(start, count, 0.5, 0.5, z, self.dome_R * 1.15, vz)
        self.n_active[None] = start + count
        return count

    def pile_top_norm(self):
        """現在の雪面頂上の正規化z（99パーセンタイルで外れ値除外）。"""
        n = self.n_active[None]
        if n == 0:
            return self.dome_c[2] + self.dome_R
        zs = self.x.to_numpy()[:n, 2]
        return float(np.percentile(zs, 99))

    # -- MLS-MPM 1ステップ --
    @ti.kernel
    def substep(self):
        for I in ti.grouped(self.grid_m):
            self.grid_v[I] = ti.Vector.zero(ti.f32, 3)
            self.grid_m[I] = 0.0
        # P2G
        for p in range(self.n_active[None]):
            Xp = self.x[p] * self.inv_dx
            base = int(Xp - 0.5)
            fx = Xp - base.cast(ti.f32)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            self.F[p] = (ti.Matrix.identity(ti.f32, 3) + self.dt * self.C[p]) @ self.F[p]
            h = ti.exp(self.xi * (1.0 - self.Jp[p]))           # 硬化(焼結)
            mu = self.mu_0 * h
            la = self.lambda_0 * h
            U, sig, V = ti.svd(self.F[p])
            J = 1.0
            for d in ti.static(range(3)):
                s = sig[d, d]
                s = ti.min(ti.max(s, 1 - self.theta_c), 1 + self.theta_s)  # 塑性クランプ=凝着/破壊
                self.Jp[p] *= sig[d, d] / s
                sig[d, d] = s
                J *= s
            self.F[p] = U @ sig @ V.transpose()
            stress = (2 * mu * (self.F[p] - U @ V.transpose()) @ self.F[p].transpose()
                      + ti.Matrix.identity(ti.f32, 3) * la * J * (J - 1))
            stress = (-self.dt * self.p_vol * 4 * self.inv_dx * self.inv_dx) * stress
            affine = stress + self.p_mass * self.C[p]
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                offs = ti.Vector([i, j, k])
                dpos = (offs.cast(ti.f32) - fx) * self.dx
                wt = w[i][0] * w[j][1] * w[k][2]
                self.grid_v[base + offs] += wt * (self.p_mass * self.v[p] + affine @ dpos)
                self.grid_m[base + offs] += wt * self.p_mass
        # グリッド演算 + 衝突
        for I in ti.grouped(self.grid_m):
            if self.grid_m[I] > 0:
                self.grid_v[I] = self.grid_v[I] / self.grid_m[I]
                self.grid_v[I][2] -= self.dt * self.gravity          # 重力(-z)
                pos = I.cast(ti.f32) * self.dx
                # 地面（滑り＋摩擦）
                if pos[2] < self.floor_z and self.grid_v[I][2] < 0:
                    self.grid_v[I][2] = 0.0
                    self.grid_v[I][0] *= 0.7
                    self.grid_v[I][1] *= 0.7
                # ドーム（固体半球: 内部に入る速度を除去）
                d = pos - self.dome_c
                dn = d.norm()
                if pos[2] >= self.dome_c[2] and dn < self.dome_R and dn > 1e-6:
                    if ti.static(self.dome_sticky):
                        self.grid_v[I] = ti.Vector.zero(ti.f32, 3)   # 粘着
                    else:
                        n = d / dn
                        self.grid_v[I] -= ti.min(0.0, self.grid_v[I].dot(n)) * n
                # 箱境界
                for ax in ti.static(range(3)):
                    if I[ax] < 3 and self.grid_v[I][ax] < 0:
                        self.grid_v[I][ax] = 0.0
                    if I[ax] > self.n_grid - 3 and self.grid_v[I][ax] > 0:
                        self.grid_v[I][ax] = 0.0
        # G2P
        for p in range(self.n_active[None]):
            Xp = self.x[p] * self.inv_dx
            base = int(Xp - 0.5)
            fx = Xp - base.cast(ti.f32)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            nv = ti.Vector.zero(ti.f32, 3)
            nC = ti.Matrix.zero(ti.f32, 3, 3)
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                offs = ti.Vector([i, j, k])
                dpos = offs.cast(ti.f32) - fx
                wt = w[i][0] * w[j][1] * w[k][2]
                g = self.grid_v[base + offs]
                nv += wt * g
                nC += 4 * self.inv_dx * wt * g.outer_product(dpos)
            self.v[p] = nv
            self.C[p] = nC
            self.x[p] += self.dt * nv

    # -- 位置を実寸[m]・Z-upで取得（Blender用） --
    def positions_world(self, settled_only=False, vmax=1.2):
        n = self.n_active[None]
        xs = self.x.to_numpy()[:n]
        if settled_only and n > 0:
            vs = self.v.to_numpy()[:n]
            speed = np.sqrt((vs ** 2).sum(1))
            xs = xs[speed < vmax]                 # 着地・静止した雪だけ（空中の板を除外）
        out = np.empty((len(xs), 3), dtype=np.float32)
        out[:, 0] = (xs[:, 0] - 0.5) * self.world_scale
        out[:, 1] = (xs[:, 1] - 0.5) * self.world_scale
        out[:, 2] = (xs[:, 2] - self.floor_z) * self.world_scale
        return out


if __name__ == "__main__":
    # 軽量プロトタイプ: CPUで少数粒子・短時間
    import time
    sim = MPMSnow(n_grid=96, max_particles=80_000, arch="cpu")
    print(f"dome_R(norm)={sim.dome_R:.3f}, dt={sim.dt}, mu_0={sim.mu_0:.0f}, λ_0={sim.lambda_0:.0f}")
    t0 = time.time()
    for frame in range(40):
        if frame % 2 == 0 and sim.n_active[None] < 60000:
            sim.emit(4000)
        for _ in range(250):
            sim.substep()
        pos = sim.positions_world()
        if len(pos):
            print(f"  frame {frame:2d}: 粒子{sim.n_active[None]:6d}  "
                  f"z[min={pos[:,2].min():.2f} mean={pos[:,2].mean():.2f} max={pos[:,2].max():.2f}]m  "
                  f"({time.time()-t0:.1f}s)")
    print(f"完了 {time.time()-t0:.1f}s")
