# 予測ロジック バージョン履歴

`PREDICTOR_VERSION`（`scripts/predictor.py`）の変更履歴と、バージョン別の的中率記録。

## バージョン繰り上げ基準

- **必ず繰上**: WEIGHTS 変更 / 主要スコアリングロジック変更 / 買い目生成方式変更
- **繰上しない**: 表示変更 / 運用ロジック（スケジューラ・通知等） / WPテンプレCSS

---

## v5.23 （2026-05-17〜）

### 主要変更

1. **会場別 1着waku別 連動テーブル導入** (`data/venues/stats/top1_followers.json`)
   - 構造: `{jcd: {by_winner: {w1: {n, w2_dist, w3_dist, top_combos[5]}}}}`
   - 24会場 × 6パターン（1着waku別） × TOP5 2-3着組合せ
   - サンプル数 n≥8 のみ採用（ノイズ排除）

2. **`get_top1_followers(jcd, w1, min_n)` 追加**
   - 会場別・1着艇別の最頻 2-3着連動を返すローダー

3. **`_suggest_3rentan` に follower bets 追加**
   - score上位3艇のうち non-1 を対象（1号艇1着は既存ロジックで網羅）
   - 各候補について TOP3 連動を確認し、頻度≥8%・未登場のものを「対抗」へ最大2件追加
   - 理由文字列: `"会場連動(w1=X, 頻度Y%, n=Z)"`

### 効果例（戸田 20260517 R1）

```
旧対抗: 3-1-4, 3-2-4, 3-1-5, 1-4-5 (信頼度由来のみ)
新対抗: + 3-1-2 (戸田3まくり→1残し→2 17.6%)
         + 3-6-4 (戸田3まくり→外連発 17.6%)
         + 4-1-6 (戸田4まくり→1残し→6差し 20.0%)
         + 4-2-3 (戸田4まくり→2-3続き 10.0%)
```

### 背景

- v5.20era 4718R 分析で「1逃げ→4差し(1-4)」が10.7%、「3まくり→1残し(3-1)」が5.1%、「4まくり→3着(4-x-3)」が会場依存で頻発（戸田4-1-6 で20%）と判明
- 会場特性が決まり手の連動を強く規定する（江戸川は外連発、戸田は3カド頻発、福岡は4-5-6縦目あり）
- 一般的セオリーパターン（既存 `_detect_race_patterns`）と独立に、純粋な統計頻度ベースで補強

### 自動再生成

- `build_stats.py` の `build_top1_followers()` が `data/results_csv/*.csv` 全件から再生成
- main で `--no-global` 指定がなければ build_player_stats / build_motor_stats と一緒に走る

---

## v5.22 （2026-05-17〜）

### 主要変更

1. **1号艇沈みリスクスコア導入** (`estimate_w1_winrate`)
   - 入力: scored（6艇）, jcd
   - 計算: `base_rate(会場別) × grade_mult × score_rank_mult × st_mult × gw_mult`
   - 出力: `estimated`（推定1着率）, `sink_risk` (=1-estimated), 補正係数, 説明文
   - **base_rate**: `data/venues/stats/w1_winrate.json` から（24会場、43.8%〜71.3%）
   - **grade_mult**: A1=1.25 / A2=1.10 / B1=0.70 / B2=0.65
   - **score_rank_mult**: 1位=1.0 / 2位=0.70 / 3位=0.55 / 4位+=0.60-0.65
   - **st_mult**: 1号艇ST-他艇最速ST が -0.005以下=1.35 / 0以下=1.15 / +0.005以下=1.00 / +0.020以下=0.85 / それ以上=0.75
   - **gw_mult**: 全国勝率 15+=1.10 / 10+=1.00 / 5+=0.85 / それ以下=0.70

2. **信頼度判定の沈みリスク補正** (`_calc_confidence`)
   - sink_risk ≥ 0.65 → 信頼度 -10pt
   - sink_risk ≥ 0.55 → 信頼度 -5pt, `is_rough=True` を強制
   - sink_risk ≤ 0.15 → 信頼度 +3pt（1号艇本命確信）
   - sink_risk ≤ 0.20 のみ `is_dominant` 判定許可

3. **pred.json 拡張**
   - `w1_estimate` フィールド追加（推定1着率, sink_risk, 補正係数, 理由）
   - verify でバージョン別に推定精度を検証可能

### 背景・効果

- v5.20 verify 2440R 分析より、1号艇=B1×戸田/桐生/三国は実測 30.3〜32.8% （全体57.8%）
- 既存ロジックは1号艇 score1位を強制本命にしがちで、これらの沈みケースで本命外し
- v5.22 では`sink_risk` を一次指標として is_rough を補強、対抗（3-x 等）の買い目を促す

### 検証例 (戸田 20260517 R1)

```
w1_estimate: {
  "base_rate": 0.438,
  "grade_mult": 0.70 (B1),
  "score_rank_mult": 1.0,
  "st_mult": 0.75 (ST不利+0.023),
  "gw_mult": 0.70 (勝率4.4),
  "estimated": 0.161, "sink_risk": 0.839
}
confidence: 55%, is_rough: True
```

---

## v5.21 （2026-05-17〜）

### 主要変更

1. **展示タイム履歴フォールバック**（live exhibition が取れない時用）
   - `data/players/{reg}.json` に `hist_exhibition` を追加（`build_stats.py compute_exhibition_stats`）
     - `overall_avg`: 全期間平均展示タイム
     - `by_venue`: 会場別平均（22 jcd 分まで）
     - `recent_avg` / `recent_deviation`: 直近20走の会場平均との偏差（form 指標）
   - `calc_exhibition_score` が live無し時に `recent_deviation` で フォールバック計算
     - 0.5 - deviation × 10 を [0, 1] にクリップ
     - 例: dev=-0.05 → 1.0、dev=+0.05 → 0.0

2. **K公式結果ファイルパーサ拡張**（`fetch_results_official.py`）
   - boatrace.jp 公式 raceresult ページから `exhibition_time` / `course_enter` / `st_timing` を抽出
   - beforeinfo ページから 展示タイム / チルト を併せて取得
   - 既存空欄 CSV は別途夜間バッチで埋め直す予定

### 背景

- v5.20 verify (2440R) で 1号艇1着率 57.8% に対し、score1位でない1号艇は 40.4%、ST≥0.18 の1号艇は 42.6%、B級1号艇×戸田/桐生/三国は 30〜33% と分布に大差
- 当日展示が取れない会場ではこれら指標が score に反映されにくく、本命を1枠に固定する傾向
- hist_exhibition.recent_deviation を form 指標として導入し、live無し時の差別化を確保

---

## v5.20 （2026-04-18〜）

### 主要変更

1. **WEIGHTS 再配分**（541R 寄与度分析ベース）
   - 強化: `course_advantage` 0.15→0.20 / `hist_waku_score` 0.04→0.09 / `global_win_rate` 0.14→0.16 / `grade_bonus` 0.04→0.05
   - 縮小: `local_win_rate` 0.15→0.12 / `motor_2rate` 0.11→0.08 / `boat_2rate` 0.04→0.02 / `series_score` 0.04→0.02 / `female_factor` 0.03→0.02 / `st_score` 0.16→0.15 / `exhibition_score` 0.07→0.06

2. **今節成績 コース→着順ペア表示**
   - `series_races: [{course, rank}, ...]` を scraper で取得
   - predictor HTML / WP テンプレで `4→3 6→5 3→2 ...` 形式表示

3. **予算別買い目ロジック刷新**
   - 予算帯 4段階: 500 / 1000 / 2000 / 3000
   - strategy × 配分方式（`inverse_odds` / `ev_weighted` / `equal`）を予算帯別に選択
   - 本命①オッズ連動: <10倍で1点絞り / ≥10倍で2点分散
   - 本命①最低オッズ>30倍で「波乱」モード（`min_selected` 拡大 + 均等配分）
   - 本命①内は**オッズ昇順ソート**、最安を筆頭 & 必須で含む

4. **会場特性データ取得（全24会場）**
   - 艇国データバンクから条件別コース成績（総合 / SG・G1・G2 / 雨雪 / 向風 / 追風 / 波高 / ナイター / 優勝戦）
   - 保存: `data/venues/stats/{jcd}_course_stats.json`
   - 予測への反映は v5.21 以降で順次

5. **morning 会場選定 上限拡大** 5会場 → 8会場

6. **WP テンプレ改修**
   - グローバルナビ固定 / スマホ版選手名列縮小 / コメント実データ文字サイズ縮小

### 累計成績（記録開始 2026-04-18）

| 日付範囲 | R数 | 3連複 | 全体 | 本命 |
|---|---|---|---|---|
| （蓄積中） | - | - | - | - |

---

## pre-v5.20 （2026-04-17 以前）

### 参考成績（全会場合算 1216R）

| 指標 | 値 |
|---|---|
| 1着的中 | 56.2% |
| 3連複 | 21.5% |
| 3連単 | 7.7% |
| 全体的中 | 25.1% |
| 本命 | 4.6% |
| 穴 | 0.25% |

---

## 運用メモ

- バージョンタグは `pred.json` の `"version"` フィールドに記録
- `verify.py` 実行時に `summary["version_stats"]` として集計されて `verify_history.json` に残る
- バージョン切り替えで成績が下がった場合は、旧 `WEIGHTS` / ロジックを本ファイルから復元可能
