# 竹ジオデシックドームの崩壊機構：理論と数値モデル

**作成**: 2026-06-03
**対象**: 静的弾塑性解析、ジオデシックドーム、雪荷重崩壊

---

## 概要

本文書は竹ジオデシックドームの**崩壊（structural collapse）**を構成する物理機構を整理し、本ツールキットでの数値モデル化方針を記述する。崩壊は単一現象でなく、**材料破壊・部材座屈・接合破壊**の複合事象であり、それぞれの数式的取り扱いと、本実装での扱いを示す。

---

## 1. 崩壊の構成機構

竹トラスドームの崩壊機構は以下に分類される：

| 機構 | 物理現象 | 数学的定式化 | 本実装での扱い |
|---|---|---|---|
| (A) 材料圧壊 | 圧縮応力が降伏応力を超える | $\sigma = N/A > f_c$ | ◯ Rankine-Gordon式に統合 |
| (B) Euler座屈 | 細長部材の弾性不安定 | $P > \pi^2 EI/(KL)^2$ | ◯ Rankine-Gordon式に統合 |
| (C) 引張破断 | 引張応力が引張強度を超える | $\sigma = N/A > f_t$ | ◯ 単純応力照査 |
| (D) 接合破壊 | 縛り・ボルトの抜出・割裂 | 経験的接合効率 $\eta$ | △ 効率係数のみ（詳細解析なし） |
| (E) 連鎖崩壊 | 1部材の破壊で他部材が過荷重 | 動的・非線形 | × 初期崩壊判定までで停止 |
| (F) スナップスルー | アーチの飛び移り座屈 | 非線形大変形 | × 適用範囲外 |

---

## 2. 部材破壊機構の数式

### 2.1 弾性応答（前提）

各部材の変形 $\delta$ と軸力 $N$ の関係：

$$
N = \frac{EA}{L} \delta = k_e \delta
$$

$k_e = EA/L$ が要素剛性、$L$ は無応力長。本ツールキットでは**微小変形理論**を仮定。

### 2.2 圧縮限界（Rankine-Gordon合成）

Rankine-Gordon式 [1, 2] は材料破壊と弾性座屈の合成式：

$$
\frac{1}{P_{\text{collapse}}} = \frac{1}{P_y} + \frac{1}{P_E}
$$

ここで：
- $P_y = A f_y$ : 降伏荷重（=材料圧壊）
- $P_E = \pi^2 E I / (KL)^2$ : Euler座屈荷重

これを部材1本の崩壊耐力として用い、安全率で割って許容値とする：

$$
P_{\text{allow}} = \frac{P_{\text{collapse}}}{\text{SF}_{\text{buck}}}
$$

#### 2.2.1 細長比に応じた支配モード

無次元化変数 $\alpha = P_y / P_E$ を定義すると：

$$
\frac{P_{\text{collapse}}}{P_y} = \frac{1}{1 + \alpha}
$$

| 細長比 $\lambda$ | $\alpha = (Lf_y / r_g^2 E) (\lambda^2 / \pi^2)$ | 支配モード |
|---|---|---|
| $\lambda < 50$ | $\alpha \ll 1$ | 材料圧壊 |
| $50 < \lambda < 100$ | $\alpha \approx 1$ | **混合域** |
| $\lambda > 100$ | $\alpha \gg 1$ | Euler座屈 |

竹（$E = 16$ GPa, $f_y = 58$ MPa, $r_g \approx 32$ mm）の部材長 $L = 1.5$ m では $\lambda \approx 47$、**材料圧壊と座屈の混合域**。

#### 2.2.2 接合効率 $\eta$

縛り接合・ボルト接合の竹建築では、接合部が部材本体より弱い [3, 4]。これを耐力係数 $\eta \in [0.3, 0.9]$ で表現：

$$
P_{\text{allow, joint}} = \eta \cdot P_{\text{allow}}
$$

実測例（INBAR/Janssen [3]）:
- 縛り接合（rope lashing）: $\eta = 0.3 - 0.5$
- 穴あけボルト: $\eta = 0.5 - 0.7$
- 金属クランプ: $\eta = 0.7 - 0.9$

### 2.3 引張限界

引張は接合効率に強く依存：

$$
N_{\text{tens, allow}} = \eta \cdot A \cdot f_{t,\text{allow}}
$$

---

## 3. 全体崩壊機構

### 3.1 利用率（demand-to-capacity比）

各部材 $e$ について：

$$
u_e = \frac{|N_e|}{P_{e,\text{allow}}}
$$

引張なら $P_e = N_{\text{tens, allow}}$、圧縮なら Rankine-Gordon式の $P_{\text{allow, joint}}$。

### 3.2 全体崩壊条件

**初期崩壊基準**（first-yield approach）：

$$
\text{Failure} \iff \max_{e} u_e \geq 1
$$

これは**保守的**（実構造はこれ以降も耐荷力余力を持つ）。

### 3.3 弾塑性崩壊（リミット解析）

塑性ヒンジが順次形成され、メカニズムが完成するときに**真の崩壊**：

$$
\text{Plastic collapse} \iff \text{Determinacy degree} \leq 0
$$

ジオデシックドームでは部材数 $m$、節点数 $n$、拘束自由度 $r$ について：

$$
\text{Determinacy} = m + r - 3n
$$

$\nu = 3$ の半球: $m = 135$, $n = 52$, $r = 36$（12節点 × 3方向） → 静的不定度 = $135 + 36 - 156 = 15$。即ち**15回の塑性化に耐える余力**を持つ。本実装は初期崩壊までで停止するため、安全側の評価。

---

## 4. 雪荷重による崩壊：時間発展

### 4.1 準静的仮定

雪は時間スケール（時間〜日）に対し非常にゆっくり堆積するため、各時刻で**静的釣合い**が成立すると仮定：

$$
\mathbf{K} \mathbf{u}(t) = \mathbf{F}(t)
$$

### 4.2 線形性

材料が弾性域にある限り、$\mathbf{F}$ と $\mathbf{u}, \mathbf{N}$ は線形：

$$
\mathbf{N}(t) = \mathbf{N}_D + \frac{S(t)}{S_{\text{ref}}} \mathbf{N}_S
$$

$\mathbf{N}_S$ は基準積雪荷重 $S_{\text{ref}}$ に対する応答。

### 4.3 崩壊時刻の二分探索

$S(t)$ が時間に単調増加するとき、崩壊時刻 $t^*$ は：

$$
t^* = \min\{t : u_{\max}(t) \geq 1\}
$$

積雪堆積モデル：

$$
S(t) = \rho_{\text{snow}} g \int_0^t I(\tau) \mu_b \chi_{\text{up}} d\tau
$$

降雪強度 $I(\tau)$ が一定なら線形に増加。

---

## 5. 崩壊後の挙動（適用範囲外、可視化のみ）

### 5.1 連鎖崩壊（progressive collapse）

実際の崩壊は以下の動的過程：

1. 1部材が降伏・座屈
2. 失われた剛性が他部材に再配分
3. 過荷重部材が次々に崩壊
4. 全体機構変位

これを正確に解くには**Time-history dynamic analysis** + 接続要素剛性低下のモデルが必要 [5]。本実装は**初期崩壊までで停止**。

### 5.2 可視化の運動学

`output/sim/collapse_simulation.mp4` の崩壊表現：

| フェーズ | 物理的意味 | 視覚化 |
|---|---|---|
| 1. 弾性期 ($t < 0.70 T$) | $u_{\max} < 0.85$、たわみ微小 | 微小変形を$\alpha = 50$倍に誇張 |
| 2. 軋み期 ($0.70 T < t < 0.85 T$) | 一部部材が0.85〜1.0、初期降伏 | Z方向に均等圧縮（kinematic） |
| 3. 崩落期 ($0.85 T < t < T$) | 連鎖崩壊・大変形 | Z方向圧縮 + XY方向膨張 |

各フェーズの遷移は**Bezier補間**で滑らかに：

$$
s(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3
$$

> **重要な明示**: 崩落期の運動は**動的有限要素解析の結果ではなく**、教育・概念伝達目的のキネマティクス。実構造の崩壊様態は遥かに複雑。

---

## 6. 不確実性とロバストネス

### 6.1 材料変動性

竹は変動係数 $\text{CoV} = 0.20$ と大きい [6, 7]：

$$
f_{k,5\%} = f_{\text{mean}}(1 - 1.645 \times 0.20) = 0.671 f_{\text{mean}}
$$

特性値は平均の67%。設計時はこれを基準。

### 6.2 接合の不確実性

接合効率 $\eta$ は$\pm 0.2$程度の不確実性を持つ。崩壊予測の感度：

$$
\frac{\partial S_{\text{fail}}}{\partial \eta} \approx \frac{S_{\text{fail}}}{\eta}
$$

$\eta = 0.6 \pm 0.2$ で崩壊積雪荷重は $\pm 33\%$ の不確実性。

### 6.3 推奨実務手順

1. **現地竹材の引張・圧縮試験**で $f_k$ を決定
2. **接合部の実モデル試験**で $\eta$ を測定
3. 安全率 $\text{SF} = 2.5$ で照査
4. **モニタリング**で初期座屈の徴候を検出

---

## 7. ケーススタディ：福井市・$\phi$8m ドーム

### 7.1 入力

- $\nu = 3$、半球、$D_o = 100$ mm、$t = 10$ mm
- 接合効率 $\eta = 0.6$（縛り接合）
- 福井市の冬期降雪パターン（過去10年平均）

### 7.2 結果

| 指標 | 値 |
|---|---|
| 崩壊積雪荷重 $S_{\text{fail}}$ | 3.59 kN/m² |
| 設計積雪荷重 $S_{\text{design}}$ | 4.2 kN/m² |
| 余裕率 $S_{\text{fail}}/S_{\text{design}}$ | 0.85（不足） |
| 崩壊時刻（降雪 0.1 kN/m²/h） | 約36時間 |
| 支配部材 | 上部リング、利用率1.17 |
| 崩壊モード | Rankine-Gordon混合 |

### 7.3 結論

設計上は補強が必要。以下のいずれかで対応：

1. **断面拡大**: $\phi$125 × t12 → $S_{\text{fail}} = 6.34$ kN/m²、安全
2. **格子細分化**: $\nu = 4$ → $S_{\text{fail}} = 5.57$ kN/m²、安全（135本→240本に増加）
3. **接合補強**: $\eta = 0.7$ → 限界に近いが安全側

最も経済的なのは（1）の断面拡大。

---

## 8. 引用文献

[1] Rankine, W. J. M. (1858). *A Manual of Applied Mechanics*. Charles Griffin and Co.

[2] Gordon, A. R. (1957). *Strength of Materials* (3rd ed.). Pitman.

[3] Janssen, J. J. A. (2000). *Designing and Building with Bamboo*. INBAR Technical Report No. 20.

[4] Trujillo, D. J. A., Jangra, S., & Gibson, J. M. (2017). Flexural properties as a basis for bamboo strength grading. *Proceedings of the Institution of Civil Engineers - Structures and Buildings*, 170(4), 284-294.

[5] Bažant, Z. P., & Cedolin, L. (2010). *Stability of Structures: Elastic, Inelastic, Fracture and Damage Theories*. World Scientific.

[6] Zhou, Q., Tian, J., Liu, P., & Zhang, H. (2021). Test and prediction of mechanical properties of Moso bamboo. *Advances in Mechanical Engineering*, 13(12).

[7] ISO 22156:2021. *Bamboo structures — Bamboo culms — Structural design*. ISO Geneva.

[8] Stomakhin, A., Schroeder, C., Chai, L., Teran, J., & Selle, A. (2013). A material point method for snow simulation. *ACM Trans. Graphics*, 32(4), 102.

[9] Bao, K., Yu, Y., & Mizoguchi, A. (2014). Numerical simulation of snowpack mechanical properties using DEM. *Cold Regions Science and Technology*, 105, 27-37.

[10] AISC (2016). *Steel Construction Manual* (15th ed.). Chapter E.

---

## 付録：本実装の仮定の明示的リスト

1. 微小変形（線形理論）
2. 弾性域（塑性ヒンジ形成・大変形は不考慮）
3. 静的・準静的荷重
4. 材料特性は均質・等方（実は強い異方性）
5. 接合は両端ピン（モーメント伝達なし）
6. 接合効率 $\eta$ で一括して品質ばらつきを表現
7. 安全率 SF = 2.5 を全部材一律
8. 初期崩壊で停止（連鎖崩壊は適用範囲外）
9. 福井市の典型条件を仮定

これらの仮定が成立しない場合（地震動、長期クリープ、大変形、接合劣化）は**追加解析が必要**。
