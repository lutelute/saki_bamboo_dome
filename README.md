# 竹ジオデシックドーム 設計・構造解析・3Dモデリング ツールキット

孟宗竹（Moso, *Phyllostachys edulis*）で**格子状のドーム**を作るための、
**幾何生成 → 構造計算 → 設計照査 → 3D可視化 → Blender出力**を一気通貫で行う
Python ツールキットです。福井市の積雪・風荷重（建築基準法）で実際に検証できます。

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
├── src/
│   ├── geometry.py        ジオデシックドーム生成（正二十面体細分割・球面投影・カット）
│   ├── bamboo.py          孟宗竹の材料特性・中空円形断面・許容応力（ISO 22156）
│   ├── fem.py             3D空間トラス直接剛性法ソルバ
│   ├── loads.py           自重・積雪・風（福井市・建築基準法）
│   ├── design.py          許容応力照査・Euler座屈・Rankine-Gordon・細長比
│   ├── analysis.py        統合ドライバ（解析→照査→積雪耐力→レポート）
│   ├── viz_mpl.py         matplotlib 3D（PNG）
│   ├── viz_plotly.py      plotly インタラクティブ3D（HTML）
│   └── export.py          幾何JSON / GLB・OBJ メッシュ書き出し
├── blender/
│   └── build_dome.py      Blender 4.5 ヘッドレスビルダ（bpy/bmesh）
├── tests/
│   ├── test_fem.py        FEMソルバ検証（閉形解4ケース）
│   └── verification_case.json  教科書の空間トラス検証ケース
└── output/                生成物
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
