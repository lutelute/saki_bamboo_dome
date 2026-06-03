# 竹ジオデシックドーム 設計・構造解析・3Dモデリング ツールキット

孟宗竹（Moso, *Phyllostachys edulis*）で**格子状のドーム**を作るための、
**幾何生成 → 構造計算 → 設計照査 → 3D可視化 → Blender物理シミュレーション**を一気通貫で行う
Python ツールキットです。福井市の積雪・風荷重（建築基準法）で実際に検証できます。

---

## 🎬 全成果物アクセスガイド

### 📊 インタラクティブWebダッシュボード（ブラウザで開く）

```bash
open output/dome_dashboard.html       # 11構成の比較ダッシュボード（並び替え・サマリ統計）
open output/dome_interactive.html     # 1ドームの3Dビュー（軸力分布・回転可能）
```

| ファイル | 内容 |
|---|---|
| [`output/dome_dashboard.html`](output/dome_dashboard.html) | **格子密度×サイズ 比較ダッシュボード**: φ2m(v1=15本)〜φ12m(v4=240本)の11構成、用途タグ、並び替えボタン、サマリ統計 |
| [`output/dome_interactive.html`](output/dome_interactive.html) | 軸力分布・荷重ケース切替の3Dビュー |

### 🎥 シミュレーション動画（QuickTimeで開く）

```bash
open output/sim/collapse_simulation.mp4         # 🏆 雪で潰れる崩壊シミュ（おすすめ）
open output/sim/bamboo_vinyl_snow_v2.mp4        # 竹ビニールドーム雪積もり
open output/sim/stress_animation.mp4            # 構造応力の色変化アニメ
open output/sim/presentation.mp4                # 統合プレゼン動画
open output/sim/snow_accumulation.mp4           # 草原→雪原シンプル版
```

| 動画 | 内容 | 長さ |
|---|---|---|
| `collapse_simulation.mp4` | **健全→軋み→崩壊** の3段階崩壊（180フレーム） | 7.5秒 |
| `bamboo_vinyl_snow_v2.mp4` | 竹ビニールドームに雪が徐々に積もる | 6秒 |
| `stress_animation.mp4` | 部材が緑→黄→赤に色変化（利用率可視化） | 4秒 |
| `presentation.mp4` | 統合版（雪積もり+応力） | 10秒 |

### 🎨 Blender プロジェクト（編集可能）

```bash
open -a Blender output/sim/collapse.blend            # 崩壊シミュレーション
open -a Blender output/sim/bvs2.blend                # 竹ビニール雪積もり
open -a Blender output/sim/stress.blend              # 応力色変化
open -a Blender output/sim/mpm_snow_anim.blend       # MPM粘着雪
open -a Blender output/sim/snow_color.blend          # シンプル雪積もり
```

> **重要**: Blender でファイルを開いたら **`Z` キー → マテリアル表示** で色が出ます

### 📚 ドキュメント

#### 🔬 技術文書（アカデミック）
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md) - **技術文書**：構造モデル・荷重・FEM・崩壊機構・MPM雪物理 *（引用文献20件）*
- [`docs/COLLAPSE_PHYSICS.md`](docs/COLLAPSE_PHYSICS.md) - **崩壊機構の理論と数値モデル**：Rankine-Gordon式、塑性ヒンジ、連鎖崩壊
- [`docs/MANUAL.md`](docs/MANUAL.md) - Blender操作マニュアル（開き方・動かし方・トラブル対応）
- [`docs/PRESENTATION.md`](docs/PRESENTATION.md) - プレゼンストーリー・質問対策・数値例
- [`docs/gif/`](docs/gif/) - ハイライトGIF集（プレゼン挿入用）

### 🖼 GIF（プレゼン素材）

```bash
docs/gif/collapse_simulation.gif       # 崩壊（ハイライト）
docs/gif/bamboo_vinyl_snow_v2.gif      # 雪積もり
docs/gif/stress_animation.gif          # 応力
docs/gif/snow_accumulation.gif         # 草原→雪原
docs/gif/presentation_highlight.gif    # 15秒ハイライト
```

### 🎋 竹の本質的な性質を活かした設計検討

竹は**木材・鋼材と根本的に異なる材料**：
- **しなやか**（弾性ひずみ 5-10%、木材の5倍）
- **常温でカーブできる**（曲げ加工可能）
- **強い復元力**（プレストレス源として利用可能）
- **節間中空管**（自然の効率的な構造材）
- **長尺**（8-20mに育つ、孟宗竹は12m+も）

このプロジェクトの初期は「**短く切った直線部材を接合した剛体トラス**」モデルでしたが、これは**竹の特質を活かしていない**ことが判明。

#### 曲げ竹（active bending）モデルでの再検討

`src/bent_bamboo.py` で、長い真っ直ぐな竹を曲げて配置する**アクティブベンディング構造**を解析。

#### 重要な発見

| ドーム形状 | 曲げ可能性 |
|---|---|
| **半球**（rise/D = 0.5） | φ60mmでも不可（曲げ応力が許容の2倍以上） |
| **浅いドーム**（rise/D ≤ 0.25） | 細い竹で可能 |
| **大径＋浅い**（φ8m+, rise/D ≤ 0.20） | φ100mmまで余裕で可能 |

#### 設計指針

- 半球ドームは竹に**向かない**（鋼材・木材で作るべき）
- 竹建築の伝統的な**浅いアーチ**は理論的に正しい選択
- **大径浅型ドーム** + **細い竹を曲げて長尺活用** が竹の本質に合う
- 1本の長尺竹で**アーチ全体**をカバー（接合点最小化）

実行:
```bash
python3 src/bent_bamboo.py            # 単一ドーム解析
python3 tools/bent_bamboo_study.py    # 寸法×竹径マトリクス
```

### 📐 なぜ格子が多い方が積雪耐力が高いか（理論）

ダッシュボードでは v=1（15本）→ v=4（240本）と密にするほど積雪耐力が劇的に上がります。これは**3つの構造力学の原理**による必然的な結果です：

#### 1️⃣ Eulerの座屈式（部材長 L の2乗に反比例）

```
P_cr = π² · E · I / (KL)²
```
- 部材長 L が**半分**になると、座屈耐力 P_cr は**4倍**に
- v=1（部材長 4.21m）→ v=3（1.58m）で長さ約2.7倍短く → 座屈耐力**約7倍**
- 実装: `src/design.py` の `member_capacity()` 関数

#### 2️⃣ 荷重を分担する部材数の増加

| v | 部材数 | 1本あたり荷重 |
|---|---|---|
| 1 | 15 | 100% |
| 2 | 60 | 25% |
| 3 | 135 | 11% |
| 4 | 240 | 6% |

#### 3️⃣ 静的不静定度・三角形ラチスの剛性

- 細分化＝節点数増加→**剛体運動の自由度が減り**、変形が小さくなる
- 三角形ラチスは面内せん断剛性が高い（ピン接合でも自立）
- ジオデシック幾何＝面に近い均等分布→**応力集中が少ない**

#### 🎯 設計指針

- **小径**（φ2-4m）→ v=1-2 で十分（コスト最小）
- **中径**（φ5-8m）→ v=3 が標準
- **大径**（φ10m+）→ v=4 必須（座屈リスク）
- **豪雪地**（福井）→ さらに v を上げる or 断面拡大 or 接合補強

> 完全な理論的裏付けは「4. 工学的根拠」セクションを参照（ISO 22156、AIJ規準、Stomakhin et al. 2013）

### 🎬 プレゼン用ランチャー

```bash
# プレゼン素材を一括起動（ダッシュボード+GIFインデックス+Blender）
./tools/presentation_mode.sh setup

# 個別起動
./tools/launch_presentation.sh dashboard      # ダッシュボードのみ
./tools/launch_presentation.sh blender        # Blender崩壊シーン
./tools/launch_presentation.sh main           # メイン崩壊動画
./tools/launch_presentation.sh videos         # 全動画順次再生
./tools/launch_presentation.sh list           # 全成果物一覧

# 終了
./tools/presentation_mode.sh close
```

GIFインデックスHTML: `docs/gif/index.html` （全GIF+動画+blendへのリンク集）

### 🔧 再生成コマンド

```bash
# ダッシュボード再生成
python3 -c "import sys; sys.path.insert(0,'.'); from src.dashboard import build_dashboard; build_dashboard()"

# 崩壊シミュレーション
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python blender/bamboo_vinyl_snow.py -- \
  --geo output/sim/dome_snow_scene.json \
  --out output/sim/collapse_ --blend output/sim/collapse.blend \
  --snow-m 1.5 --animate 180 --collapse-defl 0.55 --falling 6000

# 応力アニメ（時系列データから）
python3 tools/gen_stress_timeline.py --out output/sim/stress_timeline.json
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python blender/stress_animation.py -- \
  --geo output/sim/dome_snow_scene.json \
  --stress output/sim/stress_timeline.json \
  --out output/sim/stress_ --blend output/sim/stress.blend --animate 100
```

---

```
                    ╱╲╱╲╱╲
                  ╱╲╱╲╱╲╱╲╱╲          測地線格子シェル（三角形ラチス）
                ╱╲╱╲╱╲╱╲╱╲╱╲        圧縮＝シアン / 引張＝アンバー
               ╱──╳──╳──╳──╳──╲       3DトラスFEMで軸力・座屈・積雪耐力を算定
              ▲    ▲    ▲    ▲    ▲      ▲＝支点（基礎リング）
```

---

## 1. これは何か

| やりたいこと | このツールキットでの実現 |
|---|---|
| 竹でドームを作りたい | 正二十面体を細分割した**ジオデシックドーム**を任意の半径・高さで生成 |
| 格子状の構造を作りたい | 三角形ラチス（面内せん断剛性が高くピン接合でも自立）で構成 |
| 構造計算をしたい | **3次元空間トラスFEM**で軸力・応力・変位、Euler座屈、**積雪耐力**を算定 |
| 3Dモデリングしたい | matplotlib静止画 / plotlyインタラクティブHTML / GLB・OBJメッシュ |
| Blenderを使いたい | ヘッドレスで竹シリンダーを組み、PNGレンダリング＋`.blend`保存 |
| DEMO | `python3 run_demo.py` 一発で上記すべてを実行 |

---

## 2. クイックスタート

```bash
pip install -r requirements.txt          # numpy/scipy/matplotlib/plotly/trimesh
python3 run_demo.py                       # 既定: v=3, R=4m, φ100×t10 孟宗竹

# パラメータを変える
python3 run_demo.py --frequency 4 --radius 5 --culm-d 0.125 --wall-t 0.012
python3 run_demo.py --no-blender          # Blenderレンダを省略
python3 run_demo.py --no-study            # 設計スタディを省略
```

成果物は `output/` に出力されます:

| ファイル | 内容 |
|---|---|
| `dome_force_util.png` | 軸力分布 ＋ 利用率分布（2パネル） |
| `dome_geometry_view.png` | 格子形状 |
| `dome_interactive.html` | **回転・ホバー・荷重ケース切替**できる3D（自己完結） |
| `dome_geometry.json` | Blenderビルダ用の幾何データ |
| `dome.glb` / `dome.obj` | 竹シリンダーを実体化したメッシュ（任意の3Dソフトで開ける） |
| `dome_render.png` | Blenderレンダリング画像 |
| `dome.blend` | Blenderプロジェクトファイル |

---

## 3. 構成

```
saki_bamboo_dome/
├── run_demo.py            ← ワンコマンドDEMO（解析→可視化→出力→Blender→設計スタディ）
├── run_sim.py             ← シミュレーションDEMO（積雪堆積・風CFD・風圧・Blender雪）
├── src/
│   ├── geometry.py        ジオデシックドーム生成（正二十面体細分割・球面投影・カット）
│   ├── bamboo.py          孟宗竹の材料特性・中空円形断面・許容応力（ISO 22156）
│   ├── fem.py             3D空間トラス直接剛性法ソルバ
│   ├── loads.py           自重・積雪・風（福井市・建築基準法）
│   ├── design.py          許容応力照査・Euler座屈・Rankine-Gordon・細長比
│   ├── analysis.py        統合ドライバ（解析→照査→積雪耐力→レポート）
│   ├── tube3d.py          竹を実直径の3Dチューブ(円柱)メッシュ化（plotly用）
│   ├── viz_mpl.py         matplotlib 3D（PNG）
│   ├── viz_plotly.py      plotly インタラクティブ3D（変形図・竹チューブ）
│   ├── dashboard.py       格子密度×サイズ 比較ダッシュボード（HTML）
│   ├── wind_cfd.py        風CFD: 格子ボルツマン法 D2Q9（Strouhal検証付き）
│   ├── wind_pressure.py   方向性風圧 cp(θ)（半球ドーム外圧係数）
│   ├── snow_sim.py        積雪堆積の時間発展（高さ場×FEM連成・滑落・吹きだまり）
│   ├── sim_viz.py         シミュレーションのアニメ出力（mp4 / plotly）
│   └── export.py          幾何JSON / GLB・OBJ メッシュ書き出し
├── blender/
│   ├── build_dome.py      Blender 4.5 ヘッドレスビルダ（bpy/bmesh）
│   └── snow_physics.py    Blender 粒子物理による雪の堆積＋mp4
├── tests/
│   ├── test_fem.py        FEMソルバ検証（閉形解4ケース）
│   └── verification_case.json  教科書の空間トラス検証ケース
└── output/                生成物（output/sim/ にシミュレーション動画）
```

---

## 4. 工学的根拠（裏取り済み）

数値は査読論文・ISO規格・建築基準法から取得しています。

### 4.1 竹材料（孟宗竹, `src/bamboo.py`）
| 物性 | 値 | 出典 |
|---|---|---|
| ヤング率 E | 16 GPa（11–20） | Zhou et al. 2021, DOI:10.1177/15589250211066802 |
| 気乾密度 | 770 kg/m³（600–900） | PMC11084349 |
| 引張強度∥ | 145 MPa | 同上 |
| 圧縮強度∥ | 58 MPa | 同上 |
| 曲げ強度 | 130 MPa | 同上 |
| せん断強度∥ | 14 MPa | BioResources |
| 一般的な構造竹 | 外径100mm・肉厚10mm | ISO 22157 / 実務 |

許容応力は ISO 22156:2021 の許容応力設計（ASD）に倣い透過的に算出:
```
特性値   f_k     = f_mean · (1 − k_s·CoV)      # 5パーセンタイル（CoV≈0.2, k_s=1.645）
許容応力 f_allow = C_mod · f_k / SF             # SF=2.5, C_mod=含水/荷重継続修正
```
→ 許容圧縮 ≈ **15.6 MPa**、許容引張 ≈ 38.9 MPa（research値「12–16 MPa」と整合）。

### 4.2 荷重（福井市, `src/loads.py`）
- **積雪**: 多雪区域、垂直積雪量 d=140 cm、単位荷重 p=30 N/m²/cm
  → S = d·p·μ_b = **4.2 kN/m²**（屋根形状係数 μ_b=√(cos1.5β)、浅いドームは≈1.0で保守側）。
  多雪区域では積雪は**長期荷重**（令第86条第3項）。
- **風**: 基準風速 V0=32 m/s、速度圧 q≈0.73 kN/m²（遮蔽）〜1.1（開放）。
  軽量ドームは**吹上げ（負圧 Cf≈−0.8）でシェルが引張化**しアンカーが支配。
- 出典: 建築基準法施行令 第86/87条、平成12年建設省告示1454/1455号、福井県積雪荷重等指導基準、AIJ建築物荷重指針。

### 4.3 構造解析（`src/fem.py`, `src/design.py`）
- **3D空間トラス**（両端ピン・軸力のみ）。竹の縛り/ボルト接合は曲げをほぼ伝えないため妥当な理想化。
- 要素剛性 `K_e = (EA/L)·[[T,−T],[−T,T]]`, `T = r⊗r`。軸力 `N = (EA/L)·r·(u_j−u_i)`（引張正）。
- **検証**: 単一軸材・平面2部材・空間トリポッド・教科書の直交3部材空間トラスの**4ケースで閉形解と機械精度一致**（`tests/test_fem.py`）。
- **設計照査**:
  - 引張: σ=N/A ≤ 許容引張
  - 圧縮: `min(圧壊, Euler座屈)` を **Rankine-Gordon** で保守的に合成
    `P_cr = π²EI/(KL)²`（K=1.0）、`P_allow = P_crush·P_euler/(P_crush+P_euler)`
  - 細長比 λ=KL/r ≤ 150 を超える部材は非適合フラグ
  - **接合部効率 η**（縛り接合は<0.5、良好なボルト+クランプで≈1.0）で部材耐力を割引
    → 接合が支配する旨を反映（既定 η=0.6）。出典: ISO 22156、Trujillo et al.（Ylinen座屈）ほか。
- **積雪耐力**: 線形重ね合わせ `軸力(λ)=軸力_D + λ·軸力_S` で利用率=1.0となる崩壊積雪倍率を二分法で算定。

---

## 5. Blender の使い方

`run_demo.py` が自動でヘッドレス実行しますが、手動でも実行できます:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
    --python blender/build_dome.py -- \
    --geo output/dome_geometry.json \
    --out output/dome_render.png \
    --blend output/dome.blend \
    --culm-d 0.10 --color-by force --samples 64 --res 1500
```

- `--color-by force` で**圧縮材=シアン・引張材=アンバー**に色分け（構造解析結果を3Dに反映）。
- `bmesh` で全部材を1メッシュに統合するため、高frequencyでも高速。
- 生成した `dome.blend` を Blender GUI で開けば、編集・高品質レンダリング・アニメーションが可能。
- 検証済みの Blender 4.5 API ポイント: Principled BSDF は `bl_idname` で取得（表示名はUI言語で翻訳される）、エンジンは `BLENDER_EEVEE_NEXT`、シリンダーは `vec.to_track_quat('Z','Y')` で配向、`scene.camera` にカメラ"オブジェクト"を設定。

---

## 6. 既定構成の結果例（v=3, R=4m, φ100×t10, η=0.6）

```
D    （自重）   最大利用率 0.02  OK
D+S  （積雪）   最大利用率 1.17  NG ← 福井の積雪が支配
D+W  （風）     最大利用率 0.02  OK（全部材引張＝吹上げ、アンカー要検討）
積雪耐力 ≈ 3.59 kN/m²（設計4.2に対し余裕率0.85）≒ 垂直積雪120cm相当で崩壊
```

`run_demo.py` の**設計スタディ**が、福井の積雪に耐える最小構成を自動探索します:

```
v3 φ100×t10  利用率1.17  耐力3.59kN  ✗NG
v3 φ125×t12  利用率0.67  耐力6.34kN  ✓OK ← 最小で要求充足
v4 φ100×t10  利用率0.76  耐力5.57kN  ✓OK
v4 φ150×t15  利用率0.22  耐力19.6kN  ✓OK
```

---

## 6.5 シミュレーション（`run_sim.py`）

```bash
python3 run_sim.py                 # 積雪・風CFD・風圧・Blender雪 を全実行
python3 run_sim.py --no-cfd        # CFD省略（重い）
python3 run_sim.py --no-blender    # Blender省略
```

| 種別 | 手法 | 出力 |
|---|---|---|
| **積雪堆積** | 高さ場×FEM連成。屋根形状係数 μ_b=√cos1.5β で急斜面は滑落、クラウンに堆積。風で吹きだまり（風上削剥/風下堆積）。毎ステップFEMで利用率→**崩壊時刻を検出** | `output/sim/snow_sim.html`（再生/スライダ）, `snow_sim.mp4` |
| **風CFD** | 格子ボルツマン法 **D2Q9・BGK**（自前実装, numpy）。流線・渦度・圧力場。**円柱Strouhal数 St≈0.21 で物理検証**（理論0.175） | `output/sim/wind_cfd.mp4`（渦度＋流速） |
| **方向性風圧** | 半球ドームの外圧係数 **cp(θ)**（風上+0.8〜クラウン−1.0〜風下−0.4, Cheng&Fu/EN1991-1-4/AIJ準拠）。横力・吹上げを算定 | `output/sim/wind_pressure.html`（cp 3Dヒートマップ） |
| **Blender粒子雪** | bpy ニュートン粒子＋Collisionで雪を降らせ堆積させレンダリング | `output/sim/snow_blender_*.mp4` |

積雪シミュレーション例（v3 φ100, 降雪4cm/時, 福井想定）→ **約48時間（2日）で利用率1.0に達し崩壊**、クラウン積雪は最大約196cm。出典は research 裏取り（ISO 22156, 建築基準法, Krüger et al. LBM, Cheng&Fu 2010 ほか）。

---

## 7. 制約・免責

- これは**教育・概念設計用**のツールであり、実建築の確認申請に用いる構造計算書ではありません。
- トラス（ピン接合）理想化のため、剛接合の曲げ・節点剛性・初期不整・偏心は簡略化しています。
- 竹は異方性・含水・節・個体差が大きい天然材料です。実施工では ISO 22157 に基づく**実材の試験**で
  特性値を取得し、**接合部のディテールと耐力を実証**してください（接合部が通常支配します）。
- 非対称積雪（吹きだまり）・地震・施工誤差・基礎の検討は別途必要です。

---

## 8. テスト

```bash
python3 tests/test_fem.py     # FEMソルバを閉形解4ケースで検証
python3 src/geometry.py       # frequency別の格子諸元を表示
python3 src/bamboo.py         # 材料・断面諸元を表示
```
