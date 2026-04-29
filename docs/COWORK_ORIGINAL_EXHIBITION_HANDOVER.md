# Cowork 引き継ぎ：福岡オリジナル展示の取得（2026-04-29 更新）

福岡(jcd=22)のオリジナル展示タイム（一周/まわり足/直線）を取得→保存→WP表示するパイプラインを追加した。**Cowork タスクの prompt 自体は改修不要**だが、最新コードが Cowork 側で参照されることが前提。

## 関連 commit

| commit | 内容 | 反映先 |
|---|---|---|
| `9eef06d` | scraper.py / publish_wordpress.py / WP PHP 出力＋docs | GitHub Actions deploy 完了（21秒） |
| `d055a1e` | run_pending.py: 福岡時にオリジナル展示も同時取得 | Python 側、Cowork側の git pull 経由で反映 |
| `(this PR)` | fetch_results.py: results CSV に1周/まわり足/直線列追加 | Python 側、Cowork側の git pull 経由で反映 |

## Cowork タスク改修要否

### `boat-race-fetcher` （4分間隔ポーリング、`scripts/run_pending.py` 実行）

**prompt 改修: 不要**

理由: `run_pending.py:run_exhibition_task()` 内部で `jcd == "22"` の判定→`scrape_fukuoka_original_exhibition()` 呼出を追加した。tasks の登録形式・prompt フローは変わらない。

**ただし前提条件**: Cowork セッション開始時に **`cd $BOAT_DIR && git pull --rebase --autostash`** で最新コードを取り込む必要がある。Cowork prompt の冒頭に既に pull が入っていれば追加対応不要。

### `boat-daily-morning-v2` （朝バッチ、出走表＋初期予測）

**prompt 改修: 不要**

理由: 朝の段階ではオリジナル展示はまだ未公開（直前情報のため）。朝バッチが取りに行く必要はなく、その後 `boat-race-fetcher` が直前タイミングで取得する。

`build_player_pages.py` 同様、福岡固有データの取得は朝バッチには組み込まない。

## fetch_results.py（事後集計用）

**prompt 改修: 不要、ただし手動再生成を推奨**

`fetch_results.py` は前日結果を取得して results CSV を生成するスクリプト。今回 `CSV_HEADER` に7列追加（lap_time / turn_time / straight_time / lap_rank / turn_rank / straight_rank / exhibition_eval）し、福岡レコードに対し `_attach_fukuoka_original_exhibition()` で JSON join を行う。

**注意**: 既存 `data/results_csv/results_all.csv` は古いヘッダのまま。次回 `fetch_results.py` が `--no-merge` なしで動くと、既存 CSV に新列付き行を append して**ヘッダ非整合**になる。対策:

```bash
# 既存 results_all.csv を退避してから --no-merge で日次CSV だけ更新
cd ~/repos/boat
mv data/results_csv/results_all.csv data/results_csv/results_all.csv.bak
python3 scripts/fetch_results.py --years 1 --no-merge
# 全期間再生成（時間かかる）
python3 scripts/fetch_results.py --years 3
```

または、新規ヘッダで `cat $(ls -1 data/results_csv/2*.csv) > results_all_v2.csv` の手動 merge でもよい。

## 動作確認方法

### 1. リアルタイム確認（本日福岡開催時）
- 1R 展示取得予定時刻（pending_tasks.json の `fetch_at` 参照、通常 1R 発走15分前）以降に:
  - `data/raw/{TODAY}/22_R01_original_exhibition.json` が生成される
  - WP single ページ `https://ask11.jp/web/boat/race/fukuoka-{TODAY}/?race=1` に「オリジナル展示（一周・まわり足・直線）」セクションが現れる
  - 一周1位艇の数値セルが背景強調＋★マーク表示

### 2. 手動取得（デバッグ・障害時）
```bash
cd ~/repos/boat
python3 scripts/scraper.py --mode original_exhibition --jcd 22 --date 20260429 --race 1
# JSON が `data/raw/20260429/22_R01_original_exhibition.json` に出る
python3 scripts/predictor.py --jcd 22 --date 20260429 --wp-publish
# WP に payload 送信 → サイト表示更新
```

### 3. ログ確認
```bash
# Cowork race-fetcher のログ（macOS launchd 退避後の場所）
tail -f ~/Library/Logs/claude-tasks/boat-run-pending-$(date +%Y%m%d).log
# scrape の成功メッセージ:
# [OK] 福岡オリジナル展示保存: R1 → 22_R01_original_exhibition.json
```

## 障害時のロールバック

### コードロールバック
```bash
cd ~/repos/boat
git revert d055a1e   # run_pending.py の福岡フック削除
git revert 9eef06d   # scraper / publish / PHP 表示の追加
git push
```

ロールバック後は WP 側にも自動デプロイが走り、「オリジナル展示」セクションは消える。

### 部分無効化（コード残しつつ取得停止）
`scripts/run_pending.py:run_exhibition_task()` の `if jcd == "22":` を `if False:` にコメントアウトすれば、scraper呼出だけ止まる。WP 側は JSON が無いので自動的にセクション非表示。

## 現状の制限

- 取得対象: **福岡(jcd=22)のみ**。江戸川/津以外の22会場で公開されているが、未実装
- 予測ロジックへの組込み: **未実装**（Phase 3 保留中、今節データ蓄積後に再開）
- BOATCAST (`boatcast.jp`) 経由の全会場一元化は将来の差替候補（`docs/original_exhibition.md` 参照）

## 関連ドキュメント

- `docs/original_exhibition.md` - 取得経路・JSONスキーマ・全会場展開の設計
- `docs/COWORK_ROLLBACK_HANDOVER.md` - launchd→Cowork 移行全体の引継ぎ
- `~/.claude/projects/.../memory/project_boat_original_exhibition.md` - 設計判断・残工程
