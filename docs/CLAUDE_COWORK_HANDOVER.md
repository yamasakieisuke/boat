# Claude Cowork 引き継ぎメモ

この文書は、`boat` プロジェクトで直近に入れた改修を、ClaudeCowork 側が短時間で把握できるようにまとめたものです。

## 対象期間

2026-03-22 〜 2026-03-23 に実施した改修を主対象としています（v5.9 まで反映済み）。

## まず見るファイル

- `scripts/predictor.py`
- `scripts/verify.py`
- `scripts/scraper.py`
- `scripts/fetch_results.py`
- `scripts/fetch_results_official.py`
- `scripts/extract_comment_terms.py`
- `README.md`

## 主な改修内容

### 1. 予測 HTML の構成を見直し

予測詳細の出力順を、`データ → 最後に予想` に変更しました。

現行の並び:

1. 実データ
2. コメント実データ
3. 展示実データ
4. 枠別着順実績（当地・全国）
5. システム計算ロジック
6. 予算別買い目
7. システム選択の買い目

狙いは、先に「何を見ているか」を見せ、その後で「どう計算したか」を追えるようにすることです。

### 2. HTML のスマホ視認性を改善

- テーブルの固定列を `枠・名前` の 1 列に統合
- 横スクロール中も選手名が見切れないように調整
- 枠色チップを `枠・名前` セルに反映
- 会場コードは出力表示から削除
- 級別表示は `A1/A2=赤`, `B1/B2=青`

出力フォルダ構成も整理済みです。

- 予測 HTML: `output/{会場名}/YYYYMMDD.html`
- 旧 `.md` も会場別フォルダに移動済み
- `output/index.html` と `output/{会場名}/index.html` を自動生成

### 3. 買い目ラベルを実運用向けに変更

内部の買い目ロジックは維持しつつ、表示ラベルを以下に変更しました。

- `本命①` → `◎本線`
- `本命②` → `○対抗`
- 3番手候補 → `▲単穴 / △押さえ / 穴狙い`

早見表の列見出しも `本線 / 対抗 / 単穴` に統一しています。

### 4. 信頼度の定義を変更

旧来の `★1-3` ではなく `%` 表示に変更しました。

現行仕様:

- `1位-2位` 差
- `1位-3位` 差

をベースに `55%〜90%` へ再スケーリングし、以下で減点します。

- 展示未取得
- コメント根拠が薄い
- 上位拮抗

順位記号は以下です。

- `★` ダントツ評価
- `◎` 1番評価
- `○` 2番評価
- `▲` 3番評価
- `△` 4番評価

### 5. 予算別買い目を追加

オッズ取得済みレースでは、予算制約つきの買い方案を HTML に表示します。

- `500円`: 本命寄せ
- `1000円`: 保険込み

現行は 100 円単位で配分し、可能な範囲でトリガミを避ける方向です。

### 6. コメント判定を全面的に整理

`scripts/predictor.py` の `COMMENT_KEYWORDS` と関連ロジックを見直しました。

実施内容:

- 重複一致による二重加点・二重減点を防止
  - 例: `少し弱い` と `弱い` が同時に効かないように修正
- 未判定候補の抽出スクリプト `scripts/extract_comment_terms.py` を追加
- 調整作業そのものは `0` 扱い
  - `ペラを叩く`, `回転を上げる調整` などは評価しない
- 状態評価だけを加点減点
  - `足はいい`, `直らない`, `回っていない`, `差がある` などを辞書化
- `ケツを振る` 系の文言を整理
  - `ケツを振る` は弱ネガティブ
  - `ケツを振らない` は中立
  - `ケツを振るのはなくなった` は弱ポジティブ

未判定候補の出力先:

- `output/data/comment_term_candidates.md`
- `output/data/comment_term_candidates.json`

### 7. 唐津の会場公式コメントを実装

唐津の `全選手コメント` を日次取得できるようにしています。

主な変更:

- `scripts/scraper.py` に唐津コメント取得ロジックを追加
- `scripts/venue_config.py` の唐津 `has_comments=True`
- `data/venues/venue_site_support.json` の唐津を `implemented` に更新

会場サイト自動調査フローも追加済みです。

- 未実装会場では、公式サイト候補とコメント導線候補を JSON に保存
- 保存先:
  - `data/venues/venue_site_discovery.json`
  - `data/venues/venue_site_tasks.json`

### 8. verify を HTML 中心で見られるように変更

`scripts/verify.py` を強化し、以下を HTML で確認できるようにしました。

- 的中/外れの色分け
- 買い目別の命中履歴
- 会場別集計
- 月別集計

出力先:

- `output/data/verify_log.html`
- `output/data/verify/verify_detail_{会場名}_{日付}.html`

`output/index.html` から verify HTML へリンク済みです。

### 9. 発走時刻取得ロジックを修正

旧実装は `racelist` 内の時刻文字列を総取りしていたため不安定でした。

現行は `締切予定時刻` 行から 1R-12R を抽出する共通ロジックに変更しています。

関連ファイル:

- `scripts/scraper.py`
- `scripts/run_pending.py`

### 10. 結果 CSV の補完が必要なケースを確認

2026-03-22 の大村では、公式 LZH 日次成績に `24KBGN` はあるものの「この場の全レース終了後に登録されます。」の状態で、結果未反映でした。

そのため、当日は `boatrace.jp` のレース結果ページから大村 1R-12R を補完し、verify を実施しています。

補完先:

- `data/results_csv/20260322.csv`

この補完経路は `scripts/fetch_results_official.py` として切り出したうえで、`scripts/fetch_results.py` からも自動で呼ばれるようにしました。
運用手順は `docs/RESULTS_ACQUISITION.md` を参照してください。

## 現在の出力・検証で見るべき場所

### 予測

- `output/index.html`
- `output/大村/20260322.html`
- `output/唐津/20260322.html`

### 検証

- `output/data/verify_log.html`
- `output/data/verify/verify_detail_大村_20260322.html`
- `output/data/verify/verify_detail_唐津_20260322.html`

### 11. 会場別コメント取得対応管理システムを追加（v5.9）

`data/venues/comment_support.json` を作成し、24 会場のコメント取得対応状況を一元管理しています。

実装済み: 下関(19)＝shimonoseki_tenbo、若松(20)＝wakamatsu_timing、福岡(22)＝fukuoka、唐津(23)＝karatsu、大村(24)＝omura

`run_comment_scraper()` がメインエントリポイント。`scrape_day()` からはこれを呼ぶようになっています。未調査会場(`unknown`)は自動調査フローで 4 種の URL パターンを試し、結果を JSON に書き戻します。

### 12. 女性選手マーカーを公式に合わせて変更（v5.9）

`predictor.py` の女性選手表示を `🚺` から `♥`（赤、#e00020）に変更しました。レディースバッジも同色に統一しています。

`scrape_player_gender()` は `female_players.json` を正源として性別を判定する実装に変更（boatrace.jp の profile ページに性別フィールドがないため）。`female_players.json` は 57 → 75 名に更新済みです（2026-03-23 追加 18 名）。

### 13. _waku_label の prefix HTML エスケープを修正（v5.9）

`_waku_label(waku, name, prefix)` の prefix 引数が `_he()` でエスケープされていたため、HTML span が文字列化されていました。`prefix` は信頼済み HTML として直接展開するよう修正しました。

## 未解決・次に着手しやすい項目

1. `fetch_results.py` のフォールバック対象を「LZH 欠損会場」以外にも広げるか検討
2. 風補正を会場別・風向別に再定義
3. コメント辞書の継続追加
4. 予算別買い目を設定ファイル化
5. 残りの未調査会場（桐生/戸田/江戸川等）のコメント対応を自動調査で順次整備
6. `female_players.json` に女性選手が出走するたびに自動追記されるか運用確認

## 運用上の注意

- `data/pending_tasks.json` は現在空
- verify の古い履歴には `bets` が無いものがあるため、一部は簡易再構成評価
- README は `v5.9` に更新済みだが、詳細な引き継ぎはこの文書を正とする
