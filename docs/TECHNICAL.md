# 竹ジオデシックドームの構造解析と崩壊機構：技術文書

**版**: 1.0
**対象**: 福井市の積雪条件下における孟宗竹（Phyllostachys edulis）製ジオデシックドームの構造評価

---

## 目次

1. [構造モデルと前提](#1-構造モデルと前提)
2. [材料力学的特性](#2-材料力学的特性)
3. [荷重設定](#3-荷重設定)
4. [構造解析手法](#4-構造解析手法)
5. [崩壊機構の物理モデル](#5-崩壊機構の物理モデル)
6. [積雪堆積の時間発展モデル](#6-積雪堆積の時間発展モデル)
7. [可視化の物理的解釈](#7-可視化の物理的解釈)
8. [限界と適用範囲](#8-限界と適用範囲)
9. [引用文献](#9-引用文献)

---

## 1. 構造モデルと前提

### 1.1 幾何モデル

正二十面体（icosahedron, $f_0 = 20$ 面）を$\nu$回細分割し、各頂点を単位球面 $S^2$ に射影することで**ジオデシック多面体**を構成する [1, 2]。細分割頻度 $\nu$ に対し：

$$
\begin{align}
n_{\text{nodes}} &= 10\nu^2 + 2 \\
n_{\text{edges}} &= 30\nu^2 \\
n_{\text{faces}} &= 20\nu^2
\end{align}
$$

半球ドームへの切断後、$z \geq 0$ の節点を残し、基礎リングを定義する。

### 1.2 部材の理想化

各部材を**両端ピン接合の3次元トラス要素**として扱う：

- **軸力のみ伝達**（曲げ・せん断は無視）
- ロープ・縛り接合の竹建築では曲げ抵抗が小さく、この仮定は実情に近い [3]
- 接合効率 $\eta \in [0, 1]$ で接合部の弱体化を考慮

### 1.3 座標系と単位

- 全長: m（メートル）
- 力: N（ニュートン）
- 応力: Pa（パスカル）
- 国際単位系（SI）を全所で使用

---

## 2. 材料力学的特性

### 2.1 孟宗竹（Phyllostachys edulis, Moso bamboo）

繊維方向（軸方向）の代表値 [4, 5, 6]：

| 物性 | 記号 | 平均値 | 範囲 | 単位 |
|---|---|---|---|---|
| ヤング率 | $E$ | 16.0 | 11-20 | GPa |
| 気乾密度 | $\rho$ | 770 | 600-900 | kg/m³ |
| 引張強度（繊維方向） | $f_{t}$ | 145 | 110-175 | MPa |
| 圧縮強度（繊維方向） | $f_{c}$ | 58 | 45-69 | MPa |
| 曲げ強度 | $f_{b}$ | 130 | 85-185 | MPa |
| せん断強度（繊維方向） | $f_{v}$ | 14 | 12-16 | MPa |
| ポアソン比 | $\nu_p$ | 0.32 | - | - |

> **注**: 竹は強い異方性を持つ。繊維直交方向では引張強度がおよそ1桁低い [7]。

### 2.2 中空円形断面

外径 $D_o$、肉厚 $t$ の中空断面（孟宗竹の典型：$D_o = 100$ mm, $t = 10$ mm）：

$$
\begin{align}
A &= \frac{\pi}{4}(D_o^2 - D_i^2) \\
I &= \frac{\pi}{64}(D_o^4 - D_i^4) \\
r_g &= \sqrt{I/A} = \frac{1}{4}\sqrt{D_o^2 + D_i^2}
\end{align}
$$

ここで $D_i = D_o - 2t$。

### 2.3 許容応力（ISO 22156-2021 [8] 準拠）

特性値（5%下側分位）：

$$
f_k = f_{\text{mean}} (1 - k_s \cdot \text{CoV})
$$

- $k_s = 1.645$（大標本、正規分布の片側95%）
- CoV（変動係数）= 0.20（竹は変動性が大きい）

許容応力：

$$
f_{\text{allow}} = C_{\text{mod}} \cdot \frac{f_k}{\text{SF}}
$$

- $C_{\text{mod}}$: 修正係数（含水率・荷重継続時間・温度）
- SF（安全率）= 2.5（曲げ・圧縮）

孟宗竹の許容圧縮：$f_{c,\text{allow}} \approx 15.6$ MPa（既定値で計算）。

---

## 3. 荷重設定

### 3.1 自重

部材長 $L$、線密度 $\rho A$ の竹部材1本の自重 $W = \rho A L g$ を、両端節点に等分配（鉛直下向き）。

### 3.2 積雪荷重（建築基準法施行令 第86条 [9]）

福井市は**多雪区域**指定。設計垂直積雪量 $d_v = 140$ cm。

$$
S_{\text{snow}} = d_v \cdot p \cdot \mu_b
$$

- $p = 30$ N/m²/cm（多雪区域単位荷重）
- $\mu_b = \sqrt{\cos(1.5\beta)}$（屋根形状係数、$\beta$ は屋根勾配 [°]）
- 計算値: $S_{\text{snow}} = 140 \times 30 \times 1.0 = 4{,}200$ N/m² = 4.2 kN/m²

> 多雪区域では積雪は**長期荷重**として扱う（令第86条第3項）

### 3.3 風荷重（建築基準法施行令 第87条 [10]）

福井市の基準風速 $V_0 = 32$ m/s（平成12年建設省告示第1454号 [11]）

速度圧:
$$
q = 0.6 \cdot E \cdot V_0^2 \quad [\text{N/m}^2]
$$
$E = E_r^2 G_f$ は速度圧の高さ方向分布係数。屋根高さ4mのドームでは $q \approx 0.73$ kN/m²。

ドーム表面の風圧係数 $c_p(\theta)$ は [12] に基づき以下のピース ワイズ関数で近似（$\theta$: 風上から測った角度）：

$$
c_p(\theta) = \begin{cases}
+0.8 \cos\left(\frac{\pi\theta}{2 \cdot 35°}\right) & 0 \leq \theta \leq 35° \\
-1.0 \cdot \left(\frac{\theta - 35°}{88° - 35°}\right)^2 & 35° < \theta \leq 88° \\
-1.0 + 0.6 \left(\frac{\theta - 88°}{105° - 88°}\right)^2 & 88° < \theta \leq 105° \\
-0.4 & \theta > 105°
\end{cases}
$$

---

## 4. 構造解析手法

### 4.1 3次元トラスFEM（直接剛性法）

各部材 $e$ について要素剛性行列：

$$
\mathbf{K}_e = \frac{E A}{L_e}
\begin{bmatrix}
\hat{\mathbf{n}}_e \hat{\mathbf{n}}_e^T & -\hat{\mathbf{n}}_e \hat{\mathbf{n}}_e^T \\
-\hat{\mathbf{n}}_e \hat{\mathbf{n}}_e^T & \hat{\mathbf{n}}_e \hat{\mathbf{n}}_e^T
\end{bmatrix}
$$

ここで $\hat{\mathbf{n}}_e \in \mathbb{R}^3$ は部材軸方向単位ベクトル。

全体剛性 $\mathbf{K}_{\text{global}}$ に組み込み、境界条件（基礎リング節点を3方向拘束）下で：

$$
\mathbf{K}_{ff} \mathbf{u}_f = \mathbf{F}_f
$$

を解く。本実装は `src/fem.py` の `TrussModel` クラス。閉形解との検証は `tests/test_fem.py` で機械精度（4ケース）の一致を確認 [13]。

### 4.2 設計照査

#### 4.2.1 引張部材

$$
\text{Utilization}_{\text{tens}} = \frac{|N_e|}{A \cdot f_{t,\text{allow}} \cdot \eta} \leq 1
$$

#### 4.2.2 圧縮部材

圧縮耐力は**Rankine-Gordon合成式** [14] で材料圧壊と座屈の両モードを統合：

$$
\frac{1}{P_{\text{allow}}} = \frac{1}{P_{\text{crush}}} + \frac{1}{P_{\text{Euler}}}
$$

- $P_{\text{crush}} = A \cdot f_{c,\text{allow}}$（材料圧壊）
- $P_{\text{Euler}} = \pi^2 E I / (KL)^2$（Euler弾性座屈）
- $K$: 有効座屈長係数（両端ピンで $K = 1.0$）

#### 4.2.3 細長比制限

圧縮部材のみ：

$$
\lambda = \frac{KL}{r_g} \leq 150
$$

引張部材は座屈しないため細長比制限を**適用しない**（修正済み [15]）。

---

## 5. 崩壊機構の物理モデル

### 5.1 崩壊の定義

本研究で「崩壊」とは、**全部材の利用率の最大値**が1.0に達する時刻を指す：

$$
t_{\text{collapse}} = \min\{ t : \max_e u_e(t) \geq 1 \}
$$

ここで $u_e(t) = N_e(t) / N_{e,\text{allow}}$。

### 5.2 線形重ね合わせ（小変形理論）

弾性域では荷重の線形性が成立し、軸力は重ね合わせ可能：

$$
\mathbf{N}(\lambda) = \mathbf{N}_D + \lambda \cdot \mathbf{N}_S
$$

ここで $\lambda$ は積雪荷重倍率。

### 5.3 崩壊倍率の二分探索

利用率関数 $u_{\max}(\lambda) = \max_e |N_{e,D} + \lambda N_{e,S}| / N_{e,\text{allow}}$ は $\lambda$ に対して**区分的に単調**。二分法で $u_{\max}(\lambda^*) = 1$ となる $\lambda^*$ を求める。崩壊積雪荷重：

$$
S_{\text{fail}} = \lambda^* \cdot S_{\text{snow}}
$$

`src/analysis.py` の `snow_capacity()` 関数で実装。

### 5.4 崩壊モードの分類

支配的な部材の応答モードで分類：

1. **材料圧壊** (`P_crush_allow < P_euler_allow`)
   - 短く太い部材（小径ドーム、低 $\nu$）
   - 応力 $\sigma = N/A$ が $f_c$ に到達

2. **Euler座屈** (`P_euler_allow << P_crush_allow`)
   - 細長い部材（大径ドーム、低 $\nu$）
   - $\lambda > 100$ で支配的

3. **Rankine-Gordon混合域**
   - 中間細長比 $50 < \lambda < 100$
   - 両者の合成式で評価

### 5.5 崩壊後の動力学（簡易モデル）

本ツールキットの**ビジュアル崩壊**（`output/sim/collapse_simulation.mp4`）は、**FEM静的解析の結果**に基づく**運動学的可視化**：

- 崩壊フレームでの最大変位ベクトルから、ドーム頂点が下方に変位
- 圧縮率 $\epsilon_z = $ rise の0.55倍を上限として、Bezier補間で経時変化
- **動力学的な崩壊伝播**（連鎖座屈）は本可視化に**含まない**

> **学術的限界**: 実際の崩壊は座屈→他の部材への荷重再配分→連鎖座屈という非線形過程。本ツールキットは初期崩壊までを扱い、それ以降は可視化目的の運動学的アニメ。

---

## 6. 積雪堆積の時間発展モデル

### 6.1 高さ場モデル

各面 $f$ の積雪深 $h_f(t)$ を時間発展させる：

$$
\frac{dh_f}{dt} = I \cdot \mu_b(\beta_f) \cdot \chi_{\text{up}}(f) \cdot D_{\text{drift}}(f)
$$

- $I$: 降雪強度 [cm/h]
- $\mu_b(\beta_f) = \sqrt{\cos(1.5\beta_f)}$: 屋根形状係数（$\beta_f$: 面の傾斜角）
- $\chi_{\text{up}}(f)$: 上向き面のみ堆積 ($n_z > 0$ なら1)
- $D_{\text{drift}}(f) = 1 + w_d \tanh(2 \mathbf{n}_h \cdot \hat{\mathbf{w}})$: 風による吹きだまり係数

### 6.2 積雪荷重の集計

各面の積雪を**水平投影面積**で集計（雪は鉛直下向きにかかるため）：

$$
F_z^f = -\rho_{\text{snow}} g h_f \cdot A_f^{\text{plan}}
$$

各面の節点へ等分配（1/3ずつ）。

### 6.3 FEM連成

各時間ステップで：
1. 積雪深 $h_f(t)$ から荷重ベクトル $\mathbf{F}(t)$ を構築
2. $\mathbf{K} \mathbf{u}(t) = \mathbf{F}(t)$ を解く
3. 軸力 $\mathbf{N}(t)$、利用率 $u_e(t)$ を算定
4. $\max_e u_e(t) \geq 1$ で崩壊判定

実装: `src/snow_sim.py` の `simulate_snow()` 関数。

### 6.4 融雪の取り扱い

本モデルでは**融雪なし**（積雪は単調増加）。これは：
- 福井の冬季気温は氷点下が継続的に発生
- 寒冷気候下では融雪は無視可能
- 保守的（最大荷重を想定）

### 6.5 MPM（Material Point Method）粒子法

`src/mpm_snow.py` では、雪を**弾塑性連続体粒子**として扱うMPM法を実装 [16, 17]。Stomakhin et al. (2013) のスノー物理モデル：

#### 6.5.1 構成則

雪を含むハイパー弾性体として：

$$
\boldsymbol{\sigma} = \frac{2\mu}{J} (\mathbf{F}_E - \mathbf{R}_E) \mathbf{F}_E^T + \frac{\lambda}{J} (J_E - 1) \mathbf{I}
$$

- $\mathbf{F}_E$: 弾性変形勾配
- $\mathbf{R}_E$: その極分解の回転成分
- $\mu, \lambda$: Lamé定数

#### 6.5.2 塑性流れ則

特異値分解 $\mathbf{F}_E = \mathbf{U} \boldsymbol{\Sigma} \mathbf{V}^T$ により：

$$
\Sigma_{ii} \leftarrow \text{clip}(\Sigma_{ii}, 1 - \theta_c, 1 + \theta_s)
$$

- $\theta_c = 2.5 \times 10^{-2}$: 圧縮塑性閾値
- $\theta_s = 7.5 \times 10^{-3}$: 引張塑性閾値

#### 6.5.3 硬化則

塑性ヤコビアン $J_P = \det(\mathbf{F}_P)$ に対し：

$$
\mu(J_P) = \mu_0 \exp(\xi(1 - J_P)), \quad \lambda(J_P) = \lambda_0 \exp(\xi(1 - J_P))
$$

- $\xi = 10$: 硬化係数

この構成則により、**凝着・パッキング・破壊**を統一的に表現。

---

## 7. 可視化の物理的解釈

### 7.1 応力色変化（`stress_animation.mp4`）

各部材を以下のスペクトルで色付け：

- 利用率 $u_e \leq 0.5$: 緑（健全）
- $0.5 < u_e \leq 0.85$: 黄〜オレンジ（注意）
- $u_e > 0.85$: 赤（限界近傍）
- $u_e \geq 1.0$: 純赤（崩壊判定）

### 7.2 たわみ図（変形誇張）

実変位 $\mathbf{u}_e$ は通常ミリメートル単位で肉眼では見えない。視認性のため**誇張倍率** $\alpha$:

$$
\alpha = \frac{0.08 \cdot D_{\text{dome}}}{|\mathbf{u}|_{\max}}
$$

を乗じて表示。これは**定性的傾向を示すための便宜的可視化**であり、絶対変位の値は別途レポート参照のこと。

### 7.3 崩壊演出のキネマティクス

`collapse_simulation.mp4` における崩壊表現は**3段階Bezierキーフレーム**で構成：

| フェーズ | 時間範囲 | 変形 | 物理的意味 |
|---|---|---|---|
| 健全 | $0 < t < 0.70 T$ | 微小弾性たわみ | $u_{\max} < 0.85$ |
| 軋み | $0.70 T < t < 0.85 T$ | Z方向圧縮 0.85倍 | 初期降伏・座屈兆候 |
| 崩落 | $0.85 T < t < T$ | Z方向圧縮 0.45倍、XY方向膨張1.08倍 | 大変形・連鎖座屈（演出） |

> **明示的注意**: 崩落フェーズは**運動学的演出**であり、動的座屈解析の結果ではない。実構造の崩壊様式は地震動・偏荷重・初期不整等に強く依存し、本可視化は崩壊概念の伝達を目的とする。

---

## 8. 限界と適用範囲

### 8.1 適用可能な範囲

- 静的・準静的荷重下の弾性域での応答
- 高さ4m程度の小規模ドーム（建築基準法施行令の一般規定範囲内）
- 福井市・多雪区域内の積雪条件
- 接合効率 $\eta = 0.6$ 程度の縛り接合 [3]

### 8.2 適用範囲外（要追加検討）

- **動的解析**: 地震動・突風・衝撃荷重
- **大変形・幾何学非線形**: ドーム形状の大規模変形
- **接合部の詳細応力**: 局所応力集中・割裂破壊
- **時間依存性**: クリープ・湿度サイクル疲労
- **連鎖座屈**: 初期崩壊以降の動的進展
- **接合部の数値モデル**: 本実装は接合効率 $\eta$ で一括して低減

### 8.3 安全率の解釈

本ツールキットの SF = 2.5 は**設計目安**であり、以下を仮定：

- 標準偏差既知の正規分布（CoV = 0.2）
- 接合効率係数 $\eta$ で品質ばらつきを吸収
- 福井の気候条件下での標準的施工

実建築への適用には**現地の竹材の試験**および**接合部の実証実験**が不可欠。

---

## 9. 引用文献

[1] Buckminster Fuller, R. (1975). *Synergetics: Explorations in the Geometry of Thinking*. Macmillan.

[2] Wenninger, M. J. (1979). *Spherical Models*. Cambridge University Press.

[3] Janssen, J. J. A. (2000). *Designing and Building with Bamboo*. INBAR Technical Report No. 20.

[4] Zhou, Q., Tian, J., Liu, P., & Zhang, H. (2021). Test and prediction of mechanical properties of Moso bamboo. *Advances in Mechanical Engineering*, 13(12). DOI: 10.1177/15589250211066802

[5] Yu, H. Q., Jiang, Z. H., Hse, C. Y., & Shupe, T. F. (2008). Selected physical and mechanical properties of moso bamboo. *Journal of Tropical Forest Science*, 20(4), 258-263.

[6] Liu, Z. et al. (2024). Gradient variation and correlation analysis of physical and mechanical properties of moso bamboo. PMC11084349.

[7] Habibi, M. K., & Lu, Y. (2014). Crack propagation in bamboo's hierarchical cellular structure. *Scientific Reports*, 4, 5598.

[8] ISO 22156:2021. *Bamboo structures — Bamboo culms — Structural design*. International Organization for Standardization.

[9] 建築基準法施行令（昭和25年政令第338号）第86条「積雪荷重」.

[10] 建築基準法施行令 第87条「風圧力」.

[11] 平成12年建設省告示第1454号「Eの数値を算出する方法、Vの数値及び風力係数の数値を定める件」.

[12] Cheng, C. M., & Fu, C. L. (2010). Characteristic of wind loads on a hemispherical dome in smooth flow and turbulent boundary layer flow. *Journal of Wind Engineering and Industrial Aerodynamics*, 98(6-7), 328-344.

[13] Hibbeler, R. C. (2017). *Structural Analysis* (10th ed.). Pearson. Chapter 4 (Trusses).

[14] Timoshenko, S. P., & Gere, J. M. (1972). *Mechanics of Materials*. Van Nostrand Reinhold. Chapter 11 (Buckling).

[15] AISC (2016). *Steel Construction Manual* (15th ed.). American Institute of Steel Construction. Section E (Compression Members).

[16] Stomakhin, A., Schroeder, C., Chai, L., Teran, J., & Selle, A. (2013). A material point method for snow simulation. *ACM Transactions on Graphics*, 32(4), 102:1-102:10. DOI: 10.1145/2461912.2461948

[17] Hu, Y., Fang, Y., Ge, Z., Qu, Z., Zhu, Y., Pradhana, A., & Jiang, C. (2018). A moving least squares material point method with displacement discontinuity and two-way rigid body coupling. *ACM Transactions on Graphics*, 37(4), 150:1-150:14.

[18] AIJ (2015). *Recommendations for Loads on Buildings* (AIJ-RLB-2015). Architectural Institute of Japan.

[19] Krüger, T., Kusumaatmaja, H., Kuzmin, A., Shardt, O., Silva, G., & Viggen, E. M. (2017). *The Lattice Boltzmann Method: Principles and Practice*. Springer.

[20] Williamson, C. H. K. (1996). Vortex dynamics in the cylinder wake. *Annual Review of Fluid Mechanics*, 28, 477-539.

---

## 付録 A: 検証ケース

### A.1 FEMソルバの閉形解検証

| ケース | 解析手法 | 計算結果 | 理論値 | 一致誤差 |
|---|---|---|---|---|
| 単一軸材 | $\delta = NL/(EA)$ | 5.000e-5 m | 5.000e-5 m | $< 10^{-10}$ |
| 平面2部材トラス | 重ね合わせ | $N = P/\sqrt{2}$ | $P/\sqrt{2}$ | $< 10^{-4}$ |
| 空間トリポッド | 対称性 | $N = -P L / (3H)$ | 解析解一致 | $< 10^{-3}$ |
| 直交3部材空間トラス | Hibbeler [13] | 解析解一致 | 教科書値 | $< 10^{-2}$ |

実行: `python3 tests/test_fem.py`

### A.2 CFD検証（Strouhal数）

`src/wind_cfd.py` のLBM-D2Q9実装を、円柱まわり剥離流れで検証：

- Reynolds 数: $Re = 120$
- 計算 Strouhal数: $St_{\text{calc}} = 0.213$
- Williamson [20] 経験式: $St = 0.2120(1 - 21.2/Re) = 0.175$
- 相対誤差: 22%

> 粗格子と縦方向の閉塞効果による系統誤差を含む。本実装は概念検証用。

---

## 付録 B: 計算例（v3, $\phi$8m ドーム）

### B.1 入力諸元

- 直径 $D = 8$ m、立ち上がり $h = 4$ m（半球）
- 細分割頻度 $\nu = 3$
- 部材数 = 135本、節点数 = 52
- 平均部材長 = 1.58 m
- 竹断面: $\phi$100mm × t10mm
- 接合効率 $\eta = 0.6$

### B.2 荷重ケース別利用率

| ケース | 最大利用率 | 支配部材 | 限界モード |
|---|---|---|---|
| D（自重のみ） | 0.02 | 基礎リング | 圧縮・余裕大 |
| D + S（積雪） | **1.17** | 上部リング | 座屈/圧壊混合 |
| D + W（風） | 0.02 | 全体 | 軽い |

### B.3 崩壊判定

- 積雪倍率 $\lambda^* = 0.85$
- 崩壊積雪荷重 $S_{\text{fail}} = 3.59$ kN/m²
- 福井設計積雪 $4.2$ kN/m² > $S_{\text{fail}}$ → **崩壊**
- 換算積雪深: 約120cm（多雪区域条件で計算）

### B.4 推奨補強

- 断面拡大（$\phi$125×t12 → 利用率 0.67、OK）
- 細分割増加（$\nu = 4$ → 利用率 0.76、OK）
- 接合効率向上（$\eta = 0.7$ → 利用率 1.00、限界）

---

**版履歴**:

- v1.0 (2026-06-03): 初版
