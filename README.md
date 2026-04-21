# ボートレース予想エンジン v5.17

## 概要

過去1年分の競走成績データ（全国・当地）と当日の出走表・展示データを組み合わせ、
各選手にスコアを付けて着順を予測するシステムです。
出力は **HTML レポート** を基本とし、1レースごとに
「実データ → コメント/展示 → 予算別買い目 → システム計算ロジック」
の順で確認できます。
WordPress 連携は追加機能として分離しており、ローカルHTML出力は従来どおり維持します。

---

## ドキュメント一覧

| ドキュメント | 内容 |
|---|---|
| **[TODO.md](./TODO.md)** | プロジェクト全体の残タスク（コメント未対応会場 10件の個別実装ロジック等） |
| **[docs/wordpress_handover.md](./docs/wordpress_handover.md)** | WordPress 連携の設計・受信口・プラグイン・運用手順 |
| **[docs/RESULTS_ACQUISITION.md](./docs/RESULTS_ACQUISITION.md)** | 結果取得の運用フロー（fetch_results_official.py / morning_verify.py） |
| **[docs/CLAUDE_COWORK_HANDOVER.md](./docs/CLAUDE_COWORK_HANDOVER.md)** | ClaudeCowork 向けの改修引き継ぎ |
| **[output/data/tournament_guide.md](./output/data/tournament_guide.md)** | 大会グレード別補正テーブル・傾向解説（predictor 実行時に自動生成） |
| **[output/data/verify_log.md](./output/data/verify_log.md)** | 検証ログ一覧（日次自動更新） |
| **[output/data/comment_term_candidates.md](./output/data/comment_term_candidates.md)** | コメントキーワード辞書の候補語一覧 |
| **[output/pending_tasks.md](./output/pending_tasks.md)** | 積み残しタスク一覧（run_pending.py 実行時に自動更新） |

### データ管理ファイル

| ファイル | 内容 |
|---|---|
| `data/venues/comment_support.json` | 会場別コメント取得対応状況 |
| `data/venues/venue_site_tasks.json` | 会場別コメント実装タスク管理（pending/done） |
| `data/stats/{jcd}_combo_freq.json` | 会場別出目統計（頻度・条件付き確率・EV・多軸） |
| `data/logs/verify_history.json` | 検証結果累積ログ |

### スケジュール関連

| 定義 | 内容 |
|---|---|
| `Scheduled/boat-daily-morning-v2/SKILL.md` | 毎朝 8:00 JST の自動処理スキル定義（macOS cron 経由） |
| `Scheduled/boat-run-pending/SKILL.md` | 展示/オッズポーリングの手動実行手順（自動実行は bash cron） |
| `scripts/claude-code-cron/boat_run_pending.sh` | 4分間隔 cron ジョブ（`*/4 9-22 * * *`） |

---

## WordPress 同期

### 方針

- 既存のローカルHTML出力は変更しない
- WordPress 側は `forecast_day` カスタム投稿タイプに対して開催日単位で同期する
- 同期は独自受信口 `forecast-sync.php` 経由で行う
- REST API + Application Password は環境依存の認証問題があったため、現時点では採用しない

### ローカル側のファイル

- 同期送信スクリプト: [scripts/publish_wordpress.py](/Users/eisuke.yamasaki/Library/Mobile%20Documents/com~apple~CloudDocs/Agent/personal-life/boat/scripts/publish_wordpress.py)
- サーバーへ配置する受信口雛形: [wordpress/forecast-sync.php](/Users/eisuke.yamasaki/Library/Mobile%20Documents/com~apple~CloudDocs/Agent/personal-life/boat/wordpress/forecast-sync.php)
- サーバーへ配置する表示プラグイン: [wordpress/boat-forecast-viewer](/Users/eisuke.yamasaki/Library/Mobile%20Documents/com~apple~CloudDocs/Agent/personal-life/boat/wordpress/boat-forecast-viewer)

### payload 出力

WordPress 向けの送信JSONはローカルにも保存される。

保存先:
- `output/wordpress/YYYYMMDD/<jcd>_payload.json`

例:
- `output/wordpress/20260405/22_payload.json`

### 手動送信

```bash
python3 scripts/publish_wordpress.py \
  --jcd 22 \
  --date 20260405 \
  --publish \
  --sync-url https://ask11.jp/web/boat/api/forecast-sync.php \
  --token 'your-shared-token'
```

### predictor 実行後に同期

```bash
python3 scripts/predictor.py \
  --jcd 22 \
  --date 20260405 \
  --wp-publish \
  --wp-sync-url https://ask11.jp/web/boat/api/forecast-sync.php \
  --wp-sync-token 'your-shared-token'
```

環境変数でも指定できる。

```bash
export WP_SYNC_URL='https://ask11.jp/web/boat/api/forecast-sync.php'
export WP_SYNC_TOKEN='your-shared-token'
python3 scripts/predictor.py --jcd 22 --date 20260405 --wp-publish
```

### WordPress 表示プラグイン

`forecast_day` の単体ページと `/race/` 一覧を、`forecast_payload` から専用レイアウトで描画する。

配置先:
- `wp-content/plugins/boat-forecast-viewer/`

配置ファイル:
- `boat-forecast-viewer.php`
- `single-forecast-day.php`
- `archive-forecast-day.php`

有効化後:
- 単体ページ `single forecast_day`
- アーカイブ `/race/`
をテーマではなくプラグイン側テンプレートで描画する。

---

## バージョン履歴

| バージョン | 主な変更 |
|---|---|
| **v5.17** | オッズ修正・WP強化・コメント対応拡充: (1) scraper odds キー形式を `"123"` に統一（predictor 互換修正）/ (2) `publish_wordpress` の `has_odds` ハードコード撤去 → 動的判定＋各買い目に `odds` 値付与 / (3) WP プラグインに買い目横オッズ表示（`.bfv-odds`）追加 / (4) `predictor.py --wp-publish` で `write_payload_file` を呼び出し追加（ローカル payload 常時最新化）/ (5) 大村(24) コメント取得 `_scrape_omura_comments_day` 新設（モーター評価1-7点＋選手コメント）/ (6) 芦屋(21) コメント取得対応（唐津と同CMS 汎用パーサー `_scrape_modules_comments_day`）/ (7) 蒲郡(07) を管理JSON上 done に更新 / (8) `_parse_motor_eval_points` でモーター評価点をコメントスコアにボーナス反映（7点+0.25〜1点-0.30）/ (9) verify 表示を「レース的中率」主指標に簡素化 / (10) WP 振り返りテンプレートを 4 カード構成（1着的中・レース的中・本命・その他）に刷新 / (11) README ドキュメントリンク集約 |
| **v5.16** | 買い目表示を**2セクション構成**にリファクタ: **本命（最大4点）**と**その他（最大4点 抑え／対抗／穴）**に分離。`_normalize_bets()` ヘルパー新設。その他行には subtype バッジ（対抗/抑え/穴）を色付きで表示。`_save_prediction_log` に `honmei` / `others` 新フィールド追加、`verify.evaluate_bets()` が新構造を読み取って `hit_honmei` / `hit_others` / `hit_taikou` / `hit_oshi` / `hit_ana` を算出、サマリ表示と verify_history.json に記録。オッズパーサーの boatrace.jp 構造変化対応（`td[data-combo]` 撤去 → 位置ベース解析）も同時修正 |
| **v5.15** | 出目ロジック段階3（期待値ベース評価）: `analyze_combo_freq.py` で `won3_pay` から 3連単の **期待値 EV = 頻度 × 平均払戻 / 100** を計算し、`ev_top_combos` フィールドとして各軸（overall / by_month / by_stage / by_period / by_season）に保存。predictor 側に `_collect_axis_ev_combos()` を追加し、`count ≥ 10 & EV ≥ 1.30` でフィルタした高回収率出目を「出目④」枠に最大2点追加。「当たっても低配当でトリガミ」の回避を目指す |
| **v5.14** | 出目ロジック段階2（多軸集計）: `analyze_combo_freq.py` に `_build_axis_stats()` を追加し、**月別 / 季節別 / レース帯別（early 1-4R / middle 5-8R / late 9-12R）/ レース種別別（予選/準優勝/優勝戦/一般）** の4軸で top_combos / win_freq / cond_2nd を細分化。predictor に `_collect_axis_top_combos()` を追加し、月 0.35 / 種別 0.30 / レース帯 0.20 / 季節 0.15 の重みでマージして本命①に動的反映。当該レースの軸を自動選択して買い目に流し込む |
| **v5.13** | 出目ロジック大幅強化（段階1）: **(1-A)** 会場 `top_combos` 実測トップ出目を本命①フォーメーションに強制組み込み（freq≥3%の1着固定出目を最大2点追加）/ **(1-B)** `cond_2nd` / `cond_3rd` の重みを ×0.18/0.15 → ×0.35/0.28、`_combo_model_score` の条件付き確率項を ×0.30/0.22 → ×0.55/0.42 に強化 / **(1-C)** 会場実測 `win_freq` を `course_advantage` に 25% ブレンド / **(1-D)** 穴ロジック `upset_score` 閾値 0.35 → 0.28、`outer_companion` 高確率連れ出し(≥40%)の保険強化 / **(1-E)** セオリー決まり手パターン検出 `_detect_race_patterns()` 新設。2差し・3カドまくり・4カドまくり差し・外差しの4パターンを `avg_st` / 展示ST / score順位 / 級別 / 風 から動的に confidence 計算し、conf ≥ 0.55〜0.60 で本命②に強制反映。1-2-3 一辺倒からの脱却 |
| **v5.12** | 展示/オッズ取得スケジューリングを純 bash cron に一本化：(1) `data/next_run.json` と `write_schedule_request` を廃止 / (2) `scripts/claude-code-cron/boat_run_pending.sh` を新設し `*/4 9-22 * * *` で `run_pending.py --quiet` をポーリング / (3) オッズ `fetch_at` を 発走-10分 → **発走-15分** に延長 / (4) `--quiet` 早期 return で実行可能タスク0件時の無出力化 / (5) `boat-run-pending` SKILL を手動実行用に縮小 |
| **v5.11** | `scripts/morning_verify.py` 拡張：(1) 前日以前の pending_tasks を一括クリーンアップ / (2) verify 成功後に WordPress へ review_summary 入り payload を自動再送信（`WP_SYNC_URL` / `WP_SYNC_TOKEN` 必須） |
| **v5.10** | 選手マスターDB（`data/players/master.json`）新設 / br-racers.jp(1,623名)+ladies-info.jp(278名)から生成 / 性別判定を master.json 優先に変更 / `_load_player_name()` 追加 / `scripts/build_player_master.py` 追加（定期更新用） |
| **v5.9** | 会場別コメント取得対応状況を `data/venues/comment_support.json` で一元管理 / 未整備会場は予測時に自動調査・実装フロー / 下関・若松のコメント/タイムデータ取得対応 / 女性選手マーカーを ♥（赤）に変更 / `female_players.json` を正源にした性別判定 (`scrape_player_gender`) |
| **v5.8** | 予想順位記号を `★ / ◎ / ○ / ▲ / △` に再定義 / 信頼度表示を `%` 連続値へ変更 / コメント辞書と未判定抽出を改善 |
| **v5.7** | 会場別出力フォルダ + `index.html` 自動生成 / スマホ向け固定列を `枠・名前` 1列に統合 / verify 履歴JSONの破損耐性追加 / コメント用語候補抽出 `extract_comment_terms.py` を追加 |
| v5.6 | HTML出力を「実データ先行」へ再構成 / raw_metrics とコメント判定根拠を表示 / 予算別買い目を `500円=本命寄せ` `1000円=保険込み` に分離 / 唐津(23)会場コメント対応 |
| **v5.5** | 公式ピットレポート統合（全会場R7-12）/ エンジン通信簿・選手短評（大村・福岡）/ engine_bonus列追加 / 進入コース空欄対応 |
| v5.4 | 公式会場統計データ統合（boatrace.jp/data/stadium）/ 全国平均比コース補正 / scrape_stadium_data.py 追加 |
| v5.3 | 大会グレード補正（SG/G1/G2/G3/一般/レディース）/ 全員女性レース自動検出 / tournament_guide.md 出力 |
| v5.2 | 出目統計ブレンド / ボート2連率・今節成績スコア追加 / 進入コース補正 / _RACE_TYPE バグ修正 |
| v5.1 | 出力改善（早見表・信頼度・買い目先頭）/ 大会種別補正 / 先行まくり傾向・オッズEV |
| v5.0 | 女性レーサー係数追加・1枠過剰支配の是正・3連単買い目出力に統一・検証ログ蓄積 |
| v4.1 | コメントスコア追加・展示/枠実績係数調整 |
| v4.0 | 実績勝率・実績ST・モーター実績・枠実績スコア導入 |
| v3.0 | 潮汐データ（気象庁）・風補正対応 |

---

## スコアリング指標と係数

総合スコアは以下の **12指標** を重み付き合算して算出します（合計 = 1.00）。

### 1. 全国勝率　`global_win_rate`　係数 **0.15**

選手の全国1着率。出走表の当季値と過去1年の実績値を **実績60% ＋ 当季40%** でブレンド。
全国的な実力の底力を示す指標。

### 2. 当地勝率　`local_win_rate`　係数 **0.15**

その会場での1着率。同じく **実績60% ＋ 当季40%** でブレンド。
会場特有のクセへの対応力を反映。

### 3. モーター2連率　`motor_2rate`　係数 **0.11**

配艇されたモーターの2連率。出走表の当季値と当地実績を **実績50% ＋ 当季50%** でブレンド。
モーター性能による加速・乗り心地の差を表す。過去レース数が5未満の場合は当季値のみ使用。

### 4. コース補正　`course_advantage`　係数 **0.15**

出走枠ごとの有利不利を会場特性データから多段補正。
v4以前は係数0.22で1枠が全レース1位になりやすかったため、v5.0で0.15に引き下げ。
v5.3では**大会グレード補正**が追加され、1コース勝率の実態に合わせてグレード別に補正する。

| 補正要素 | 内容 |
|---|---|
| 枠ベーススコア | 1枠=1.00、2枠=0.55、3枠=0.45、4枠=0.40、5枠=0.30、6枠=0.25 |
| **季節補正 (v5.4)** | boatrace.jp 公式の季節別コース1着率 ÷ 全国平均 で補正係数を算出し優先適用（フォールバック: venue_characteristics.json 手動推定値） |
| レース帯補正 | 序盤(1〜4R)・中盤(5〜8R)・終盤(9〜12R)の傾向を乗算 |
| **大会グレード補正 (v5.3)** | SG×1.10 / G1×1.07 / G2×1.04 / G3×1.02 / 一般×1.00 / レディース×0.87（1コース補正） |
| **大会種別補正 (v5.1)** | 優勝/準優勝戦×1.12・一般×1.00・予選×0.87 |
| **先行/まくり傾向補正 (v5.1)** | 外枠配置のまくり型はペナルティ軽減（×0.88〜1.12）、先行型は内枠でボーナス |
| **進入コース補正 (v5.2)** | 展示の実際の進入コースがある場合、前づけ−3%・外押し−5% |
| 潮汐補正 | 満潮・干潮・上げ・下げで枠ごとの不利を乗算（潮汐会場のみ） |
| 風補正 | 4m/s 以上の向かい風・追い風時に各枠スコアを補正 |

> **レディース戦の例：1コース補正 ×0.87、6コース補正 ×1.11** → 外枠が相対的に大幅有利になる

> **詳細は `output/data/tournament_guide.md` を参照**（predictor.py 実行時に自動生成）

### 4b. ボート2連率　`boat_2rate`　係数 **0.04** ← NEW v5.2

配艇されたボート（艇）の今節2連率。モーター同様エンジン性能の指標だが、
ボート固有の特性（浮力バランス・波きり性能等）を反映。
全国平均約35%を基準に 0〜1 に正規化して寄与量を計算。

### 5. 級別ボーナス　`grade_bonus`　係数 **0.04**

| 級 | スコア |
|---|---|
| A1 | 1.00 |
| A2 | 0.75 |
| B1 | 0.50 |
| B2 | 0.25 |

### 6. STスコア　`st_score`　係数 **0.16**

平均スタートタイムを 0.10秒→満点・0.25秒→0点 の線形変換でスコア化。
優先度：実績ST（build_stats集計）＞ 出走表記載ST ＞ プロフィールST ＞ デフォルト0.18秒。

フライング（F）・出遅れ（L）ペナルティを減算：

| ペナルティ | 減点 |
|---|---|
| F 1本 | −0.15 |
| F 2本目以降（追加） | −0.10/本 |
| L 1本 | −0.05 |
| 上限 | −0.50 |

### 7. 展示スコア　`exhibition_score`　係数 **0.09**

当日の展示（スタート練習）データを使用。レース前に取得した場合のみ有効（未取得時は中立値0.5）。

- **展示タイム（60%）**：6艇中の相対位置を 1.0〜0.0 に正規化（直線スピード）
- **前走ST（30%）**：展示前走スタートタイミングをSTスコア式でスコア化
- **チルト（10%）**：チルト角度（マイナス＝スピード重視セッティング）を相対スコア化

#### 取得フィールド（scraper.py `scrape_exhibition`）

| フィールド | 内容 | 備考 |
|---|---|---|
| `exhibition_time` | 展示タイム（秒） | 直線6m通過タイム。速いほど高スコア |
| `tilt` | チルト角度 | -0.5=スピード重視、0.0=標準、+1.0=ターン重視 |
| `entry_course` | 展示での進入コース | 実際に入ったコース（内枠争いの指標） |
| `start_timing` | 前走スタートタイミング | ".11"=0.11秒。0.10未満が理想 |
| `handicap_dist` | スタートハンデ距離 | 0=フライングライン、1=1M、2=2Mハンデ |
| `prev_rank` | 前走着順 | 直前レースの結果 |
| `course_order`（別オブジェクト） | スタート展示コース順×ST | `[{course, foul, st}]` |

> **進入コースは予測精度向上の重要指標**：外枠選手が1コースに入ればコース補正より有利になるが、現バージョンのスコアリングは枠番ベースで計算。出力の展示データ表を参照して手動補正を推奨。

### 8a. 今節成績スコア　`series_score`　係数 **0.04** ← NEW v5.2

今節（同じ大会期間）でこれまで何着を取ったかを着順リストからスコア化。
平均着順 70% + 1-2着率 30% で合算。初日（データなし）は中立値 0.5。
レース数が少ない場合は信頼度（races/7）を乗じてベースライン 0.5 に向かってブレンド。

### 8b. 枠実績スコア　`hist_waku_score`　係数 **0.04**

当地でその枠に入ったときの過去1着率（0〜100%）を 33.3% 基準で正規化（0〜1.0）。
当地データが3レース未満の場合は全国データで代替。
どちらも不足の場合は中立値 0.5 を使用。

### 9. コメントスコア　`comment_score`　係数 **0.04**

会場公式サイトから取得した選手コメント（足の状態）をキーワード解析でスコア化。
直近3件のコメント履歴から継続的な好不調トレンドも加味する。
未取得時は中立値 0.5。

- 現行辞書は [predictor.py](/Users/eisuke.yamasaki/Library/Mobile%20Documents/com~apple~CloudDocs/Agent/Claude/personal-life/boat/scripts/predictor.py) の `COMMENT_KEYWORDS`
- 候補語抽出は `scripts/extract_comment_terms.py` で実行し、`output/data/comment_term_candidates.{json,md}` に保存
- `Janome` が入っていれば形態素解析を使用、未導入時は日本語句の n-gram 抽出で代替

### 10. 女性レーサー係数　`female_factor`　係数 **0.04** ← NEW v5.0

男女混合戦における女性選手の荒天時ハンデを補正する指標。

| 条件 | スコア | 効果 |
|---|---|---|
| 男性選手 | 0.50 | ニュートラル（変化なし） |
| 女性・穏やか（風<2m/s・波<10cm） | 0.50 | ニュートラル（精密さが活きる） |
| 女性・中程度（風2〜4m/s または波10〜14cm） | 0.35 | 軽微なペナルティ |
| 女性・強風（風≥4m/s または波≥15cm） | 0.20 | ペナルティ大（−0.012 相当） |

女性選手は出力に 🚺 マーカーで表示される。
登録リストは `data/players/female_players.json` で管理し、スクレーパーで随時更新する。

---

## v5.1 追加機能

### 現地向け出力改善（A2）

出力ファイルの冒頭に **全レース早見表** が追加され、ファイルを開いた瞬間に全レースの買い目が一覧できる。

```
########################################################################
#  下関(19)  2026/03/16  全12R 早見表
########################################################################
   R    本線        対抗         単穴    信頼   種別    備考
  ────────────────────────────────────────────────────────────────────
   1R   1-2-6    1-6-2    4-1-2   96%   予選
   7R   3-1-4    1-3-4    3-4-2   58%   予選      ⚡荒れ
  12R   1-3-4    1-3-2    1-4-2   91%   🏆決勝
########################################################################
```

各レース詳細では **信頼度（%）と買い目が先頭** に表示される。
信頼度は `1位-2位` 差と `1位-3位` 差をベースに `55%〜90%` へ再スケーリングし、
さらに `展示未取得` `コメント根拠が薄い` `上位拮抗` の条件で減点する。

順位記号は以下の順で付与する。
- `★` … ダントツ評価（1位で、2位との差が大きい）
- `◎` … 1番評価
- `○` … 2番評価
- `▲` … 3番評価
- `△` … 4番評価

### 大会種別補正（B）

365日CSVデータ分析に基づき、レース種別に応じた補正を `course_advantage` に適用：

| 種別 | 補正倍率 | 3連単平均払戻 | 1枠1着率 |
|---|---|---|---|
| 🏆 優勝戦・準優勝戦 | ×1.12（1枠有利強化） | ¥14,000 | 11.95% |
| 一般戦 | ×1.00（標準） | ¥18,300 | — |
| 予選・通常戦 | ×0.87（荒れ補正） | ¥19,700 | 7.22% |

### オッズ期待値モデル（A1①）

オッズデータ取得済みの場合、各買い目に **EV（期待値）** が表示される：
```
◎本線:  1-2-6  12.3倍  EV:1.45  💰高EV   （スコア順）
○対抗:  1-6-2  28.1倍  EV:0.72  ⚡低EV   （入替）
```
EV ≥ 1.20 → `💰高EV`（スコア高い割に人気薄 = 買い目推奨）
EV < 0.80 → `⚡低EV`（オッズが低すぎる）

---

## v5.3 追加機能

### 大会グレード補正（tournament_grade）

`data/tournament_grades.json` を静的データとして管理し、大会のグレードに応じて `course_advantage` を補正する。

#### グレード検出の優先順

1. **CSS クラス属性** (`is-grade_SG` 等) — boatrace.jp の公式クラスを直接チェック
2. **テキストキーワード** — ページタイトル・h1・ナビゲーション部分をキーワードマッチ
3. **フォールバック** — 検出できない場合は「一般」として処理

検出結果は racecard JSON の `tournament_grade` フィールドに保存される。

#### グレード別1コース補正係数

| グレード | 1コース | 2〜6コース | 1コース平均勝率 | 荒れ指数 |
|:---:|:---:|:---:|:---:|:---:|
| SG | ×1.10 | ×0.97 | 57.5% | 0.90 |
| G1 | ×1.07 | ×0.98 | 56.0% | 0.92 |
| G2 | ×1.04 | ×0.99 | 54.0% | 0.96 |
| G3 | ×1.02 | ×0.99〜1.00 | 53.0% | 0.98 |
| 一般 | ×1.00 | ×1.00 | 52.0% | 1.00 |
| レディース | ×0.87 | ×1.04〜1.11 | 46.5% | 1.15 |

### 全員女性レース検出（is_all_female_race）

`scraper.py` がグレード「レディース」を検出できなかった場合でも、`predictor.py` 内で全選手の性別チェックを行い、全員女性であれば「レディース」補正を自動適用する。

- 判定基準: `player_stats["gender"]` = "F" または `female_players.json` に登録
- 対象: 通常節中の全員女性レース（稀に発生）
- 適用時は `[INFO] 全員女性レースを検出 → グレード補正: レディース` をログ出力

### tournament_guide.md 自動生成

`predictor.py` 実行のたびに `output/data/tournament_guide.md` を自動更新。
グレード別の1コース勝率・荒れ指数・コース補正係数・傾向説明を一覧で確認できる。

---

## データ優先順位（ブレンドロジック）

```
勝率    = 実績(1年) × 0.60  +  当季(出走表) × 0.40
モーター = 実績(当地) × 0.50  +  当季(出走表) × 0.50   ※実績5R以上の場合
ST      = 実績ST > 出走表ST > プロフィールST > 0.18秒
```

---

## 出力の読み方

```
順  枠  名前    級   スコア  全勝  当地  モータ  コース   ST   展示  枠実績  コメ  性別
1◎ [1] 選手名  A1  0.5800  0.023 0.023  0.050   0.165  0.110  0.045  0.060  0.024
4△ [6] 女性選手 B2  0.2500  0.003 0.004  0.018   0.037  0.096  0.045  0.000  0.020 🚺
```

各数値は「その指標の重みをかけた後の寄与量」です。合計がスコアになります。
1位がダントツのときだけ `★`、通常の1位は `◎` を付けます。

### 3連単買い目セクション

```
🎯 【3連単 買い目】
  ◎本線:  1-3-4   （スコア順）
  ○対抗:  1-4-3   （2-3着接近(差0.007) 入替）
  穴狙い: 2-1-3   （⚡2枠1着(差0.014)）
```

買い目の自動選択ロジック：

- `◎本線`: もっとも素直な本命筋
- `○対抗`: 本線の入替・次点筋
- `▲単穴`: 一発までは薄いが、2着差しや相手違いで拾う筋
- `△押さえ`: 統計差し込み・3着押さえ
- `穴狙い`: 1着まで食い込む波乱筋

| 本命② の条件 | パターン |
|---|---|
| 2・3着スコア差 < 0.015 | 2-3着入替 |
| 1・2着スコア差 < 0.020 | 1-2着逆転 |
| それ以外 | 3着に4位差し込み |

穴は4位選手のスコア差・風速条件に応じて 1着大穴 または 3着差し込み を選択。

### 予算別買い目セクション（オッズ取得済みの場合のみ）

HTML では買い目候補とは別に、予算制約つきの配分案を表示する。

| 予算 | 方針 | 仕様 |
|---|---|---|
| 500円 | 本命寄せ | 本命①を必須、最大2点。回収重視で点数を絞る |
| 1000円 | 保険込み | 本命①を必須、最大3点。本命②や穴まで含めて取りこぼしを減らす |

配分表には以下を表示する：
- 配分額
- オッズ
- 的中時収支
- 最悪収支
- 期待収支
- トリガミ回避可否

### HTMLレイアウト（v5.6）

各レース詳細は以下の順で表示する。

1. `🧭 実データ`
2. `💬 コメント実データ`
3. `🏁 展示実データ`
4. `💴 予算別買い目`
5. `🎯 システム選択の買い目`
6. `⚙️ システム計算ロジック`
7. `📊 枠別着順実績`

「何を見て判断したか」を先に表示し、その後で「どう計算したか」を確認する構成。

### 実データセクション（v5.6）

`🧭 実データ` では、各指標を以下の3段で表示する。

- 実データ
- 採用値
- 寄与

コメント欄はさらに以下を表示する。

- 出典
- 判定（`▲ / ▼ / ―` と raw score）
- 一致キーワード
- 本文

### 展示データ実数表（取得済みの場合のみ表示）

展示データが取得済みの場合、コメントブロックの直後に6艇分の実数表を出力する。

```
🏁 展示データ（速い順）
────────────────────────────────────────────────────────────────────
枠   選手         展示T    チルト  進入   前走ST  前走着  評価
────────────────────────────────────────────────────────────────────
[3] 石本　　裕武     6.65   -0.5  1コース     .17    １  ★最速
[1] 吉田　　拡郎     6.69   -0.5  5コース     .11    ６
[2] 吉川　　元浩     6.70   -0.5  6コース     .13    ４
[5] 和田　　兼輔     6.71    0.0  2コース     .24    ５
[6] 森高　　一真     6.75   -0.5  2コース     .21    ３
[4] 中島　　孝平     6.79   -0.5  2コース     .12    ３  ▼遅
────────────────────────────────────────────────────────────────────
スタート展示: 1(0.05)  2(0.09)  3(0.14)  4(0.23)  5[F](0.04)  6(0.04)
────────────────────────────────────────────────────────────────────
```

- **展示T評価**: ★最速 / ▲好調（最速+0.03以内） / ▼遅（最速+0.10以上）
- **チルト**: マイナス＝スピード重視セッティング（直線有利）
- **進入コース**: 外枠選手が内コースに入る＝コース優位を奪取（重要サイン）
- **前走ST**: 理想は 0.10〜0.15 / 0.24以上は遅い
- **スタート展示 [F]**: フライング（展示時の早起きは本番リスク）
- 展示未取得時は `🏁 展示データ: 未取得（発走前に自動取得予定）` を表示

### 選手コメントセクション（出力ルール）

**コメントブロックは取得状況にかかわらず全レースで常に出力する。**

```
💬 コメント実データ
────────────────────────────────────────────────────────────────────
[1] 田中　宏樹    ―  中堅上位くらい。十分に納得できる。         キーワード一致なし / raw 0.50
[2] 佐藤　駿介    ▼  スカッていた。伸びも売り切れ気味。           スカっ(-0.12) / 売り切れ(-0.15) / raw 0.23
[6] 鐘ヶ江 真司   ▲  スリットから出て行くし、伸びはいい。         スリットから出(+0.12) / 伸びはいい(+0.14) / raw 0.76
```

| 記号 | 意味 | 条件 |
|---|---|---|
| ▲ | 好調（スコア補正プラス） | comment_score > 0.55 |
| ― | 普通（中立） | 0.45 ≤ score ≤ 0.55 |
| ▼ | 不調（スコア補正マイナス） | comment_score < 0.45 |

コメントが取得できていない会場・レースでは以下を表示する：

```
⚠️  コメント未取得（この会場は公式コメントサイト未対応、またはデータ取得前）
```

**コメント取得対応会場（`COMMENT_SITE_URLS` / 公式会場コメント）：**

| 会場 | コード | URL |
|---|---|---|
| 福岡 | 22 | boatrace-fukuoka.com |
| 唐津 | 23 | boatrace-karatsu.jp |

加えて、以下は補助コメント系として使用する：

| 会場 | コード | 取得内容 |
|---|---|---|
| 大村 | 24 | 選手短評（シリーズ単位） |
| 全会場 | — | boatrace.jp 公式ピットレポート（R7-12） |

コメントはキーワード辞書（`COMMENT_KEYWORDS`）でスコア化する。辞書は `predictor.py` 内で管理し、データ蓄積に応じて随時拡充する。

---

## 予測精度の限界

- **展示データなし**の場合、`exhibition_score` は全員中立（0.5 × 0.09 = 0.045 均等）
- **当地レース数が少ない**選手は全国ベースに後退するため局所特性が反映されにくい
- **当日の体調・スタート気配**は数値に現れない
- **女性選手リスト**は `female_players.json` の登録状況に依存する（未登録の場合は男性扱い）

---

## ファイル構成

```
boat/
├── scripts/
│   ├── scraper.py          # boatrace.jp スクレイピング（出走表・展示・オッズ）
│   ├── build_player_master.py  # 選手マスターDB構築（br-racers.jp + ladies-info.jp）
│   ├── fetch_results.py    # mbrace.or.jp からLZH形式の競走成績を取得
│   ├── fetch_tide.py       # 気象庁から潮汐データを取得
│   ├── build_stats.py      # CSV → 選手/モーターJSON統計を生成
│   ├── predictor.py        # 予想エンジン本体 v5.7
│   ├── verify.py           # 予測精度検証・蓄積スクリプト
│   ├── extract_comment_terms.py  # コメント用語候補抽出（Janome対応/フォールバックあり）
│   ├── gen_venue_guide.py  # 会場特性ガイド生成（output/data/venue_guide.txt）
│   ├── scrape_stadium_data.py  # boatrace.jp/data/stadium から全24場の公式コース統計取得 (v5.4)
│   └── run_pending.py      # 積み残しタスク管理（展示・オッズ自動取得）
├── data/
│   ├── racecards/          # 出走表JSON（日付/会場_Rxx.json）
│   ├── players/            # 選手統計JSON（登録番号.json）
│   │   ├── master.json          # 選手マスターDB（全1,623名・性別・名前・支部・勝率）
│   │   ├── female_players.json  # 女性選手登録番号リスト（master.jsonから自動生成）
│   │   ├── br_racers_raw.json   # br-racers.jp スクレイプ原本（build_player_master.py が生成）
│   │   └── ladies_raw.json      # ladies-info.jp スクレイプ原本（同上）
│   ├── motors/             # モーター統計JSON（会場_モーター番号.json）
│   ├── results_csv/        # 過去成績CSV（YYYYMMDD.csv）
│   ├── results_raw/        # LZHから展開したテキスト原本
│   ├── odds/               # 3連単オッズJSON（日付/会場_Rxx.json）
│   ├── tides/              # 潮汐データJSON（日付/会場_tide.json）
│   ├── logs/
│   │   ├── {日付}/              # 予測ログJSON（会場_Rxx_pred.json, bets/raw_metrics含む）
│   │   └── verify_history.json  # 検証結果蓄積ログ（末尾破損時も verify.py が救済読込）
│   ├── comments/           # 会場公式コメントJSON（日付/会場_Rxx.json）
│   ├── player_comments/    # 選手コメント履歴 / ピットレポート / 選手短評
│   ├── pending_tasks.json  # 積み残しタスクキュー
│   ├── stats/              # 会場別出目頻度統計 ({jcd}_combo_freq.json)
│   ├── tournament_grades.json           # 大会グレード別補正テーブル (v5.3)
│   └── venues/
│       ├── venue_characteristics.json   # 24会場の特性データ（手動推定値）
│       ├── official_course_stats.json   # 全24場公式コース統計（scrape_stadium_data.py 取得, v5.4）
│       ├── venue_site_support.json      # 会場固有サイトの調査・実装状況
│       ├── venue_site_discovery.json    # 自動調査で見つけた候補リンク
│       └── venue_site_tasks.json        # 未実装会場の実装タスクメモ
└── output/
    ├── index.html             # 全会場横断の出力インデックス
    ├── {会場名}/
    │   ├── index.html         # その会場の出力一覧
    │   ├── YYYYMMDD.html      # 予測結果HTML（全R早見表＋実データ/買い目/計算ロジック）
    │   └── YYYYMMDD.md        # 旧Markdown出力（過去分アーカイブ）
    ├── pending_tasks.md        # 積み残しタスク一覧（目視用）
    └── data/                   # 目視確認用データ集約フォルダ
        ├── comment_term_candidates.json  # コメント用語候補（構造化）
        ├── comment_term_candidates.md    # コメント用語候補（目視用）
        ├── venue_guide.txt           # 全24場の水面特性・枠補正ガイド
        ├── tournament_guide.md       # 大会グレード別傾向ガイド (v5.3, 自動生成)
        ├── verify_log.md             # 的中率サマリ（1行1会場・最新先頭）
        └── verify/                   # 詳細検証ファイル置き場
            └── verify_detail_{会場名}_{日付}.md   # 1日1会場の全R予測vs結果＋振り返り分析
```

---

## 実行方法

```bash
# 今日の全レース予測（output/ に自動保存）
python3 scripts/predictor.py

# 自動保存先:
# output/{会場名}/YYYYMMDD.html
# output/index.html と output/{会場名}/index.html も自動更新

# 日付・会場・レース番号を指定
python3 scripts/predictor.py --jcd 22 --date 20260315 --race 9

# ファイル保存なし（ターミナルのみ）
python3 scripts/predictor.py --output none

# データ取得（当日朝に実行）
python3 scripts/scraper.py --jcd 22 --date 20260315

# 潮汐データ取得（対応会場のみ）
python3 scripts/fetch_tide.py --jcd 22 --date 20260315

# 積み残しタスク管理（展示・オッズを発走15分前に自動取得）
python3 scripts/run_pending.py --add-exhibition 22 20260315 09:00   # 展示タスク登録
python3 scripts/run_pending.py --add-odds       22 20260315 09:00   # オッズタスク登録
python3 scripts/run_pending.py                                       # タスク実行（定期的に呼ぶ）
python3 scripts/run_pending.py --list                                # タスク一覧確認

# 公式会場コース統計更新（全24場、約30秒、月1回程度推奨）(v5.4)
python3 scripts/scrape_stadium_data.py            # 全24場
python3 scripts/scrape_stadium_data.py --jcd 22   # 福岡のみ

# 統計再ビルド（新たなCSVを追加した後に実行）
python3 scripts/build_stats.py --jcd 22

# 結果取得（レース終了後）
python3 scripts/fetch_results.py --date 20260315

# 精度検証・蓄積（結果取得後に実行）
# → output/data/verify_log.md（サマリ）と verify_detail_{会場}_{日付}.md（詳細）を自動生成
python3 scripts/verify.py --jcd 22 --verbose

# 検証結果を保存せずに表示のみ
python3 scripts/verify.py --jcd 22 --no-save

# コメント用語候補を抽出
python3 scripts/extract_comment_terms.py
python3 scripts/extract_comment_terms.py --min-count 3

# 会場特性ガイド生成（全24場）
python3 scripts/gen_venue_guide.py
# 特定会場のみ
python3 scripts/gen_venue_guide.py --jcd 22
```

---

## 会場固有サイト対応フロー（新規会場で予測する際）

### 管理ファイル

`data/venues/venue_site_support.json` で全24場の調査・実装状況を管理。

| status | 意味 |
|---|---|
| `implemented` | スクレイパー実装済み・predictor 組み込み済み |
| `investigated` | サイト確認済み・補完情報あり・未実装 |
| `partial` | 一部取得可能またはパース困難 |
| `none` | 調査済みだが有益情報なし |
| `unknown` | 未調査 |

### 自動通知と自動調査

`scraper.py --mode day` や `predictor.py` 実行時に会場の調査状況を自動表示し、未実装会場では候補リンクを保存する：
- `unknown` → 🔍 調査促進メッセージ（サイトURL付き）
- `investigated` → ℹ️ 取得可能情報と実装推奨通知
- `implemented` → ✅ 実装済み機能確認

保存先:
- `data/venues/venue_site_discovery.json`
- `data/venues/venue_site_tasks.json`

### 新規会場の調査手順

```
1. scraper.py --mode day を実行 → 🔍 通知が出たら調査開始
2. venue_site_support.json の site_url にアクセスして以下を確認:
   - エンジン通信簿（モーター評価スコア）
   - 選手短評（シリーズ単位コメント）
   - モーター成績（2連単率・勝率）
   - その他公式 boatrace.jp にない情報
3. 有益情報があれば scraper.py に取得関数を追加
   - VENUE_SITE_CONFIG にパスを追加
   - scrape_engine_report / scrape_player_review に準じた関数を実装
   - scraper.py --mode day の自動実行ブロックに組み込み
4. predictor.py で取得データをスコアに反映
5. venue_site_support.json の status を更新（investigated → implemented）
```

### 実装済み会場

| jcd | 会場 | 取得情報 |
|---|---|---|
| 22 | 福岡 | 選手短評・モーター成績 |
| 23 | 唐津 | 全選手コメント（日次）を racecard の reg_no と紐づけて各Rへ保存 |
| 24 | 大村 | エンジン通信簿（1-6評価・engine_bonus）・選手コメント（日次・足状態・モーター評価点） |

### 調査優先度 high の未実装会場

| jcd | 会場 | サイト | 情報 |
|---|---|---|---|
| 07 | 蒲郡 | https://www.gamagori-kyotei.com/ | 高橋アナのモーター太鼓判（エンジン評価相当） |
| 14 | 鳴門 | https://www.n14.jp/ | 未調査 |

---

## 選手マスターDB 更新フロー

```
【定期更新（前期→後期切替時など、半年に1回程度）】
python3 scripts/build_player_master.py --br-only
# → data/players/br_racers_raw.json を更新（Pythonのみ・所要1分以内）

【ladies-info.jp の更新は Claude Cowork で実行】
# Chromeでhttps://www.ladies-info.jp/list/ を開き
# 全ページを自動クリックで収集 → data/players/ladies_raw.json を更新
# → python3 scripts/build_player_master.py --merge-only で master.json 再生成

【マスター内容】
data/players/master.json
  _meta: { total: 1623, female: 278, male: 1345, updated: ... }
  players:
    "4500": { name_kanji, name_kana, grade, branch, prefecture, win_rate, gender: "M" }
    "5406": { ..., gender: "F" }
    ...

【性別判定の優先順（predictor.py / scraper.py）】
  1. master.json["players"][reg_no]["gender"]
  2. female_players.json["reg_nos"]（フォールバック）
```

---

## 推奨デイリーフロー

```
【前日まで】
  fetch_results.py → build_stats.py  （定期実行済みが理想）

【当日朝】
  scraper.py --jcd XX --date YYYYMMDD   出走表 + 気象 + コメント取得
                                          ※ 大村(24)・福岡(22)・唐津(23)は会場固有コメント補完あり
  fetch_tide.py --jcd XX --date YYYYMMDD  潮汐取得（対応会場のみ）
  predictor.py --jcd XX --date YYYYMMDD  初回予測生成

  run_pending.py --add-exhibition XX YYYYMMDD HH:MM  展示タスク登録（R1発走時刻を指定）
  run_pending.py --add-odds       XX YYYYMMDD HH:MM  オッズタスク登録
  ↑ 登録と同時に data/next_run.json を書き出し、
    boat-run-pending が自動で最初の fetch_at に one-time スケジュール

【レース中（自動）】
  boat-run-pending スケジュールタスクが発走10分前に自動起動
  → 展示・オッズ取得成功  : 次レースの fetch_at で再スケジュール
  → 取得失敗（未公開）    : 5分後に1回だけリトライ予約
  → リトライも失敗        : タスク削除（終了）
  ※ 無駄な実行はゼロ（必要な時刻にだけ起動）

【当日夜〜翌朝】
  fetch_results.py --date YYYYMMDD   結果CSV取得
  verify.py --jcd XX                 的中率照合
                                      → output/data/verify_log.md（サマリ 1行1会場）
                                      → output/data/verify_detail_{会場}_{日付}.md（全R詳細）
```

### タスクのタイミング制御

`run_pending.py` が管理するタスクには 2 つの時刻フィールドがある：

| フィールド | 意味 | 展示・オッズの設定値 |
|---|---|---|
| `fetch_at` | この時刻より前はスキップ | 発走 **10分前** |
| `deadline` | この時刻を過ぎたら自動削除 | 発走時刻 |
| `retry_count` | 0=初回取得済み、1=1回リトライ後（以降は削除） | exhibition/odds のみ |

**イベント駆動スケジューリング（5分ポーリング廃止）:**

```
run_pending.py 実行後 → data/next_run.json を出力
  → boat-run-pending が読み取り、自身の fireAt を更新して再スケジュール
  → ファイルを削除（次の実行まで存在しない）
```

boat-run-pending は `enabled=false`（cronは無効）のまま、fireAt による one-time 起動のみで動作する。

---

## output/data/ ファイル詳細

### verify_log.md（的中率サマリ）

1行1会場の最新先頭形式。`verify.py` 実行のたびに自動更新。
`verify_history.json` の末尾に余分な `]` などが混入していても、`verify.py` は有効な先頭配列部分を読んで保存を継続する。

```
| 検証日     | 会場      | 対象期間          | レース数 | 1着% | 買い目% | 3連複% | 3連単% | 平均着順 |
| 2026-03-15 | 福岡(22)  | 20260315〜20260315 | 12R      | 72.7%| 18.2%  | 9.1%   | 0.0%   | 10.27    |
```

### output/data/verify/verify_detail_{会場名}_{日付}.md（全R詳細＋振り返り分析）

1日1会場ごとに自動生成。予測3点 vs 実際の結果を1行1Rで確認でき、末尾に振り返り分析を追加。

```
# 予測詳細　2026/3/15　福岡

1R　カタメン１一　予測　1-3-4　1-4-3　2-1-3　結果　1-4-5　8番人気　配当　2,350円　予測結果：✕
2R　一般戦　      予測　1-2-5　1-5-2　4-1-2　結果　1-5-2　9番人気　配当　1,790円　予測結果：△
...

---

## 振り返り分析

- **集計**: 12R  3連単 1回  3連複 3回  （3連単 8.3% / 3連複 25.0%）
- **1着予測一致**: 9R （1R, 2R, 4R, ...）
- **平均配当**: 3,200円　平均人気: 8.5番人気
- **高配当(1万円超)**: 3R(12,180円/36人気)
- **3連複○ / 3連単✕**: 2R, 6R　→ 3着の順序が逆

### 傾向コメント

- 1着予測一致 75.0% — 本命軸は信頼できる水準。2・3着の精度向上が課題。
- 高配当レースが 1R — 穴枠はアウト枠・2コース差しが決まっている。潮汐・展示タイム差を事前確認したい。
```

- 予測3点：ログ保存された実際の `bets` をそのまま検証に使用
- 予測結果：○ = 3連単的中 / △ = 3連複的中 / ✕ = 外れ
- 振り返り：1着的中率・買い目的中率・平均配当・高配当レースの傾向・改善コメント自動生成

### comment_term_candidates.md / .json（コメント辞書候補）

会場コメントと選手コメント履歴から、辞書未登録の頻出語を抽出した一覧。

- `positive`: 既存辞書でポジティブ文脈に偏る候補
- `negative`: 既存辞書でネガティブ文脈に偏る候補
- `neutral`: 文脈が割れており、辞書反映前に目視確認したい候補
- `score_hint`: `(positive - negative) / total` の簡易指標

### venue_guide.txt（会場特性ガイド）

`gen_venue_guide.py` で生成。24会場すべての水面特性・枠補正を一覧で確認できる。

```
■ 福岡(22)  海水　潮汐あり  1コース基礎勝率: 56%
  概要: 博多湾に面した海水面。潮の干満差が大きく満潮時はインが流れやすい。
  【季節別 枠補正】
  春(3〜5月): 1=1.00  2=1.00  3=1.01  4=1.01  5=1.00  6=0.99  ← 標準
  ...
```

---

## 今後やりたいこと

1. 風補正の精緻化
イン向き追い風・向かい風・横風を会場別に分けて、`course_advantage` への補正を明文化する。

2. 信頼度 `%` の再スケーリング
現在は `1位-2位` のスコア差が中心なので、`1位-3位` 差や展示差、人気差も含めて過剰に `100%` が出ないように調整する。

3. コメント辞書の継続改善
会場別の言い回し差、ピットレポート特有表現、否定形や改善表現を継続的に辞書へ反映する。

4. コメント評価ルールの固定化
調整作業そのものは `0`、足の状態や感触だけを評価するルールを維持し、README 内の仕様としても明文化する。

5. verify HTML の強化
的中/外れの色分け、会場別・月別集計、買い目別の命中履歴などを見やすく追加する。

6. 予算別買い目の設定化
`500円=本命寄せ`、`1000円=保険込み` の固定ルールを、設定ファイルやCLIで変更できるようにする。

7. 会場コメント対応の横展開
唐津以外の会場でも、公式サイトの選手コメント取得ロジックを順次実装する。

---

*予想エンジン v5.8 / 2026-03-22*
