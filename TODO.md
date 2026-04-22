# ボートレース予想システム TODO

プロジェクト全体の残タスクを集約する。個別の細かいタスクは `data/venues/venue_site_tasks.json` 等に構造化されているので、本ファイルは「何をゴールにしているか」をトップダウンで記す。

*最終更新: 2026-04-22*

**v5.19 進捗**: #1（セオリーパターン発動記録）実装完了。次回の予測実行から pred.json に `triggered_patterns` / `applied_patterns` が記録され、verify でパターン別ヒット率が表示される。

**#3 方針変更（2026-04-17）**: 当初「Phase 1〜3 の段階導入」として書いていたが、実際は v5.2 で series_score が既にスコア反映済みであることが判明。Phase 1/2/3 を統合し「既組込指標の効果検証」タスクに再定義。

**v5.20 リリース（2026-04-18）**: 当日の改修を全て v5.20 として確定。
- WEIGHTS再配分（寄与度分析）/ series_races（コース→着順）/ 予算別買い目4段階刷新（本命オッズ連動・波乱判定）/ 全24会場特性データ取得 / morning会場 5→8 / WPテンプレ改修
- バージョン管理開始: `PREDICTOR_VERSION = "v5.20"`、pred.json に version タグ、verify で `version_stats` 集計、`docs/version_history.md` 新設
- 要FTPアップ: `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 次: 1週間データ蓄積して pre-v5.20 と比較検証、会場特性データの predictor 組込み（v5.21 候補）

**運用基盤切り戻し（2026-04-22）**: launchd → Cowork Scheduled tasks に完全移行。6タスク全てが cron 有効化済み、ボート系2タスクには AUP 文言挿入＋`~/repos/boat` フォルダ接続を実施。詳細は `docs/COWORK_ROLLBACK_HANDOVER.md` 。

---

## 優先度サマリ

| P | タスク | ゴール | 備考 |
|---|---|---|---|
| ✅ **P0** | [#6 daily-morning-v2 朝バッチ失敗検証](#6-daily-morning-v2-朝バッチ失敗検証) | ~~原因特定・復旧~~ | **解決済み（2026-04-22）**: Cowork Scheduled tasks に移行、launchd は unload 済み |
| ✅ **P0** | [#7 WP同期 403 検証](#7-wp-sync-403-検証) | ~~トークン/URL 確認・復旧~~ | **解決済み（2026-04-22）**: C案（PHP定数方式）採用、新token rotate 完了 |
| ✅ **P1** | [#1 セオリーパターン発動記録](#1-セオリーパターン発動ヒット率の-verify-記録) | ~~verify にパターンフラグ追加~~ | **v5.19 実装完了（2026-04-17）** |
| **P1** | [#2 v5.16 新指標チューニング](#2-v516-新指標の-verify-蓄積チューニング) | EV閾値 / パターンconf / 本命配分の最適化 | #1と並行で蓄積 → 1〜2週後に調整 |
| **P2** | [#3 series_score 効果検証](#3-series_score-今節成績スコアの効果検証) | verify で既存指標と独立に効いているか可視化 | v5.2 で既に組込済 |
| **P4** | [#4 コメント未対応会場（ピンポイント）](#4-コメント未対応会場の個別取得ロジック実装) | morning 出現頻度TOP3のみ対応 | 全10会場は沼。絞る方針に変更 |
| **P5** | [#5 boat_run_pending.sh エラーハンドリング](#5-boat_run_pendingsh-のエラーハンドリング) | ログ肥大化対策 / 再試行 | Cowork 運用になり launchd 側 wrapper は未使用 |

---

## 1. セオリーパターン発動ヒット率の verify 記録 ✅ 実装済み（v5.19 / 2026-04-17）

現在4種（2差し / 3カド / 4カドまくり差し / 外差し）のパターンのヒット率を追跡する拡張。

### 実装内容
- `predictor.py`: 予測時に `_detect_race_patterns` を呼び、pred.json に以下を追加
  - `triggered_patterns`: `{"2差し": 0.78, "3カド": 0.0, ...}`（全パターンの conf 値）
  - `applied_patterns`: `["2差し", "外差し"]`（bets に実際に影響したパターン、reason文字列から逆引き）
- `verify.py`:
  - race_detail に `triggered_patterns` / `applied_patterns` を記録
  - サマリー出力にパターン別セクション追加（発動回数 / 発動時的中率 / 適用回数 / 適用時的中率）
  - `summary["pattern_stats"]` として verify_history.json にも保存

### 次回以降の運用
- 1〜2週間データが貯まったら #2 のチューニングで閾値見直し材料として使う
- 効果の低いパターンを廃止 or 閾値調整

---

## 2. v5.16 新指標の verify 蓄積・チューニング

2026-04-12 以降の pred.json から `honmei` / `others` 新構造が蓄積される。1〜2週間分のデータが貯まったら以下をチューニング:

- **EV 閾値**: 現行 1.30 → 実績ベースで最適値を探る
- **セオリーパターン conf 閾値**: 現行 0.60 → 発動頻度と的中率のバランス（#1 の記録が前提）
- **本命 4点 / その他 4点 の配分**: 本命を3に減らしてその他を増やす方が良いか等

### 初期測定結果（2日間 84R）

| 指標 | v5.12以前 | v5.16〜17 |
|---|---|---|
| レース的中率 | 19.4% | **38.1%** |
| 本命ヒット | 5.8% | **15.5%** |

---

## 3. series_score（今節成績スコア）の効果検証

v5.2 で既に実装済み。scraper が `series_ranks` を取得し、predictor の `series_score` が予想スコアに加算されている（平均着順70% + 1-2着率30%、走数n でtrustブレンド）。したがって残るのは「この指標が実際に効いているか / 既存指標（exhibition_timing, motor_2rate）と独立した情報量を持つか」の検証。

### 検証ゴール
- verify で series_score の本命採用実績と的中/不的中の相関を可視化
- 既存指標（展示タイム / モーター2連率 / 通年勝率）との相関をチェックし、独立した情報量があるか確認
- 結果次第で:
  - 独立性が高い → 現状維持 or WEIGHTS["series_score"] 上方修正
  - 既存指標と重複 → ウェイト縮小 or 廃止

### 実装ステップ
1. pred.json の `series.ranks` から `races / win_rate / top2_rate` を verify 側で算出
2. verify_history に `series_stats` セクションを追加（走数帯別の本命ヒット率、初日=0走 / 2-3走 / 4-6走 / 7走+ など）
3. 他指標との相関は目視で十分（精密な相関行列までは不要）

### 備考
- v5.2 時点でスコア反映済みなのは把握漏れだった（Phase 1 観測→Phase 3 投入の段階導入を設計していた）
- 既に組込済みの指標の事後検証なので、データ蓄積は待たずに直近の verify_history で即実施可

### 初期検証結果（2026-04-17 / 福岡204R）

verify に `series_stats` 走数帯別集計を実装して計測:

| 走数帯 | R数 | 本命的中率 | 平均着順 | 1-2着率 |
|---|---|---|---|---|
| 0走(初日) | 36 | 5.6% | - | - |
| 1-3走 | 56 | 5.4% | 3.76 | 27.4% |
| 4-6走 | 60 | **10.0%** | 3.63 | 31.0% |
| 7走+ | 52 | **1.9%** | 3.34 | 36.0% |

**示唆**: 7走+帯で今節1-2着率36%（最高）なのに本命ヒット率は1.9%と急落。今節の重みを強くかけるほど裏目に出ている可能性。ただし n=52 は結論出すには少ないので様子見。

**アクション（保留）**: データが倍増（n=100+）しても同じ傾向なら以下を検討:
- **D案（有力）**: `WEIGHTS["series_score"] = 0` にして計算から外し、pred.json / 画面には `series.ranks` を参考情報として残す。今節成績は人間が最後に参照する材料に留める（既存の global_win / local_win / motor_2rate で十分カバー出来ている可能性）。ウェイトの 0.04 は他指標に再分配
- B案: `trust = min(0.5, n/7.0)` で trust 上限を 0.5 に制限（走数多くても半分しか効かせない）
- A案: `WEIGHTS["series_score"]` を 30〜50% 減

---

## 4. コメント未対応会場の個別取得ロジック実装

**方針変更（2026-04-17）**: 全10会場対応は労力大・効果不明のため、morning 定期タスクの選定履歴から **出現頻度の高い会場 TOP3 のみピンポイント対応** に方針転換。残りは `comment_score` 中立値 0.5 で運用継続。

各会場の公式サイト構造が異なるため、1会場ずつパーサーを書いて `scripts/scraper.py` の `COMMENT_SITE_URLS` と `scrape_comments()` に組み込む。現在の対応状況は `data/venues/comment_support.json` と `data/venues/venue_site_tasks.json` で管理。

### 実装済み — 5会場

| JCD | 会場 | 種別 | 備考 |
|---|---|---|---|
| 07 | 蒲郡 | JS comment ファイル | `_scrape_gamagori_comments_day` / 2026-04-11 動作確認済み |
| 21 | 芦屋 | modules CMS（唐津と同型） | `_scrape_modules_comments_day` / 開催時に自動取得 |
| 22 | 福岡 | HTML パーサー | `boatrace-fukuoka.com/modules/yosou/syussou.php` |
| 23 | 唐津 | modules CMS | `_scrape_modules_comments_day` / `boatrace-karatsu.jp` |
| 24 | 大村 | omurakyotei.jp comment.php | `_scrape_omura_comments_day` / モーター評価1-7点込み / 2026-04-12 動作確認済み |

### 未対応（pending）— 10会場

詳細な候補リンク情報は `data/venues/venue_site_tasks.json` の各タスク内 `candidate_comment_links` に保持されている。

| JCD | 会場 | 公式サイト | 調査状況 |
|---|---|---|---|
| 02 | 戸田 | https://www.boatrace-toda.jp/ | 候補リンクなし、要再調査 |
| 08 | 常滑 | https://www.boatrace-tokoname.jp/ | PDF / javascript:void → 別アプローチ必要 |
| 10 | 三国 | https://www.boatrace-mikuni.jp/ | PDF / 外部予想サイト → 別アプローチ必要 |
| 12 | 住之江 | https://www.boatrace-suminoe.jp/ | 独自 HTML（asp/suminoe/kyogi） |
| 13 | 尼崎 | https://www.boatrace-amagasaki.jp/ | PDF / ニッカン外部リンク |
| 15 | 丸亀 | https://www.marugameboat.jp/ | PDF のみ（404 for modules） |
| 16 | 児島 | https://www.kojimaboat.jp/ | 優勝戦コメントのみ |
| 17 | 宮島 | https://www.boatrace-miyajima.com/ | 動画 / 予想紙 PDF |
| 19 | 下関 | https://www.boatrace-shimonoseki.jp/ | player_review（レース展望）は対応済み。コメントは PDF |
| 20 | 若松 | https://www.wmb.jp/ | timing_data 対応済み。コメントは PDF |

> **調査結果（2026-04-12）**: `/modules/raceinfo/?page=index_racers_comment` パターンが使えるのは唐津・芦屋のみ。残り10会場はいずれも modules CMS 非対応で、PDF / JavaScript 動的生成 / 独自 HTML の個別パーサーが必要。

### 実装手順（1会場あたり）

1. `candidate_comment_links` の各URLを開き、選手コメントが載っているページを特定する
2. HTML構造を調査し、`scrape_comments(jcd, date, race_no)` のパーサー分岐を追加する
   - `COMMENT_SITE_URLS[jcd]` を登録
   - パーサー関数を定義し、`{"player_comments": [{"name": ..., "text": ...}, ...]}` を返す構造に正規化
3. `data/venues/comment_support.json` の該当エントリを `status: "implemented"` に更新し、`parser` / `url` / `last_success` を書き込む
4. `data/venues/venue_site_tasks.json` の該当タスクを `status: "done"` にして `completed_at` と `notes` を記録
5. `scripts/extract_comment_terms.py` で抽出した候補語を `predictor.py` の `COMMENT_KEYWORDS` に反映する（必要に応じ）
6. ドライランとして直近の開催日で `python3 scripts/scraper.py`（該当関数）を走らせ、コメント取得件数を確認

### ゴール（方針変更後）

- morning 選定履歴から出現頻度 TOP3 の未対応会場を特定し、その3会場のみ実装
- それ以外は `comment_score` 中立値 0.5 で運用継続
- 全24会場対応は長期目標として据え置き（優先度は低）

---

## 5. boat_run_pending.sh のエラーハンドリング

- 展示取得失敗時のログ肥大化対策（失敗ログの行数制限 or ローテーション）
- predictor 非ゼロ終了時のリカバリ（再試行 or 通知）

---

## 6. daily-morning-v2 朝バッチ失敗検証 ✅ 解決済み（2026-04-22）

**経緯**: 2026-04-21 08:00 実行で launchd 側 exit 1。ログ 295 byte でスタートアップのみ記録、Claude Code 本体が起動直後に落ちた症状。

**決着**: launchd での運用をやめ、Cowork Scheduled tasks に切り戻し。同時に AUP refusal 対策（プロンプト冒頭に公営ギャンブル用途明示）を実施。

- `boat-daily-morning-v2`（cron: `0 8 * * *`）に AUP 文言挿入＋`~/repos/boat` フォルダ接続完了
- launchd 側は `launchctl unload` で停止、plist ファイルはロールフォワード用に残置
- 2026-04-22 の手動実行で STEP 0-6 全工程の動作確認済み（8会場分の予測HTML生成、WP投稿、pending登録）

詳細は `docs/COWORK_ROLLBACK_HANDOVER.md` の「最終構成」セクション参照。

---

## 7. WP sync 403 検証 ✅ 解決済み（2026-04-22）

**経緯**: 2026-04-21 の run-pending ログに 403 が 68 回（最終的に 84 回）記録。heteml 側 `BOAT_SYNC_TOKEN` 環境変数が消失していた（`/web/boat/api/` に `.htaccess` も `.user.ini` も無し）。

**決着**: **C案（PHP定数方式）**を採用。

- `wordpress/forecast-config.php` で `define('BOAT_SYNC_TOKEN', ...)` を供給（`FORECAST_SYNC_LOADER` ガード付き）
- `wordpress/forecast-sync.php` の `resolve_expected_token()` で最優先ソースに定数を据える多段フォールバック構成
- `wordpress/.htaccess` / `wordpress/.user.ini` は互換フォールバック・診断用に残置
- 新 token を `openssl rand` で生成（28 chars）、3点同期完了（`.env` / `forecast-config.php` / Cowork タスク環境変数）
- 疎通確認: `curl -X POST $WP_SYNC_URL ... '{"ping":"test"}'` で `HTTP=400 missing_field=title` を確認（token認証通過、validationで正常弾き）
- 本日 4/22 × 8 会場は `action=created`、4/21 verify 振り返り × 8 会場は `action=updated` で WP 反映済み

今後のローテ手順は `docs/TOKEN_ROTATION.md` に整備。

---

## 参照

- 現行仕様: [README.md](./README.md)
- 構造化タスク: `data/venues/venue_site_tasks.json`
- 対応状況: `data/venues/comment_support.json`
- 候補語辞書: `output/data/comment_term_candidates.{json,md}`
