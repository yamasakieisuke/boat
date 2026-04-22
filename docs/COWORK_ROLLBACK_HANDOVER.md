# Cowork 運用引き継ぎ（旧: ロールバック計画）

> **初版**: 2026-04-22 午前（ロールバック計画として作成）
> **最終更新**: 2026-04-22 午後（完了状態に改訂、完全復活を記録）
> **対象読者**: 運用者（山崎さん） / Cowork 側で編集するときの Claude / 将来セッションの Claude Code

## この文書の位置づけ

2026-04-13〜04-22 の期間、boat 定期バッチを launchd（ローカル Mac）で動かしていたが不安定だったため、**Cowork Scheduled tasks に戻した**。本ドキュメントは移行の経緯と最終構成を記録し、将来の差し戻し・新規 Mac 追加・トラブルシュートの起点にする。

---

## 経緯（タイムライン）

| フェーズ | 実行基盤 | 結果 |
|---|---|---|
| 〜 2026-04-13 | Cowork Scheduled tasks (6タスク) | ✅ 安定 |
| 2026-04-13 〜 04-21 | launchd + `~/.local/bin/claude-task-runner.sh` | ⚠️ 4/19まで正常、4/20-22で不安定（AUP refusal、exit 1、Mac sleep） |
| **2026-04-22 以降** | **Cowork Scheduled tasks (6タスク) 再有効化** | ✅ **稼働中** |

### launchd 側で発生した問題（移行の動機）

1. 2026-04-20 08:00 の morning-v2 → `API Error: Claude Code is unable to respond... (AUP 違反)` で応答拒否
2. 2026-04-21 08:00 の morning-v2 → ログ 295 byte の startup のみ、exit 1
3. 2026-04-22 08:00 の morning-v2 → 発火形跡なし（Mac sleep 疑い）
4. 2026-04-21 の run-pending → WP sync 403 が 84 回連発

---

## 最終構成（2026-04-22 稼働中）

### Cowork Scheduled tasks（6タスクすべて enabled）

| taskId | cron | 頻度 | フォルダ接続 |
|---|---|---|---|
| `boat-daily-morning-v2` | `0 8 * * *` | 毎朝 08:00 | ✅ `~/repos/boat`（必須） |
| `boat-race-fetcher` | `*/4 9-22 * * *` | 9:00-22:59 の4分毎 | ✅ `~/repos/boat`（必須） |
| `daily-genai-news` | `15 8 * * *` | 毎朝 08:15 | 不要（MCPコネクタ） |
| `daily-genai-news-slack` | `0 9 * * 1-5` | 平日 09:00 | 不要（MCPコネクタ） |
| `weekly-genai-summary` | `30 8 * * 1` | 月曜 08:30 | 不要（MCPコネクタ） |
| `garden-weekly-reminder` | `2 8 * * 1` | 月曜 08:02 | 不要（MCPコネクタ） |

> cron は local timezone（JST）で解釈される。jitter（決定論的遅延）で数分ズレて起動する。

### ボート系タスクの3つのクリティカル要件

**1. AUP 文言のプロンプト挿入（ボート系2タスクのみ）**

公営ギャンブル用途の明示で Claude の応答拒否を予防。プロンプト冒頭に以下を挿入済み:

```
## タスク文脈（AUP 明示）

本タスクは 日本国内で法律により合法とされる公営競技（ボートレース / モーターボート競走法に基づく公営ギャンブル）
の過去データ・出走表・オッズ・気象データを収集し、統計的な予測モデル（scripts/predictor.py）で着順確率を算出
して、個人ブログ（WordPress）に分析レポートを公開するデータサイエンス・統計分析用途のバッチです。

- 取得対象は日本財団・BOATRACE公式・艇国データバンク等の一般公開データのみ
- 賭け金の自動投入・ベッティングサービス運営・他者への勧誘は一切含まない
- 出力は個人の学習・検証用の統計レポート（HTML記事）であり、投資助言・賭博あっせんには該当しない
- 対象ユーザーは成人（本人のみ）
```

**2. タスク単位のフォルダ接続（ボート系2タスクのみ）**

Cowork のスケジュール起動は **interactive session とは別の isolated sandbox** で走るため、タスク設定画面で `~/repos/boat` を接続する必要がある。

- 設定場所: Cowork → 各タスク詳細画面 → フォルダ接続 / Workspace
- 未設定だと `BOAT_DIR` 検出に失敗し「ボートレースプロジェクトディレクトリが見つかりません」で終了する
- **新規 Mac 追加・タスク複製・Cowork再インストール時は毎回再設定が必要**

**3. launchd ジョブは全台で Unload**

二重実行防止のため、launchd 側は完全停止しておく（plist ファイルは残してOK）:

```bash
launchctl unload ~/Library/LaunchAgents/com.boat.run-pending.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-genai-news.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-genai-news-slack.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-investment-news.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-investment-news-slack.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.weekly-genai-summary.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.garden-weekly-reminder.plist

# 確認（何も出なければ OK）
launchctl list | grep -E "boat|claude-code\.task"
```

---

## WP sync 403 の決着（2026-04-22）

### 原因
- heteml サーバ側 `BOAT_SYNC_TOKEN` が消失（`/web/boat/api/` に `.htaccess` も `.user.ini` も無かった）
- 全 POST が `{"ok":false,"error":"invalid_token"}` で 403

### 採用構成: C案（PHP定数方式）

`.htaccess SetEnv` は heteml の PHP 実行環境で `getenv()` に反映されない可能性があり不確実。PHP 定数で定義する方式を採用:

- **`wordpress/forecast-config.php`** — `define('BOAT_SYNC_TOKEN', ...)` を供給（`FORECAST_SYNC_LOADER` ガード付き）
- **`wordpress/forecast-sync.php`** — 先頭で `include_once` し、`resolve_expected_token()` の最優先ソースに定数を据える
- **`wordpress/.htaccess`** — 互換フォールバック・診断用として残置（`<Files "forecast-sync.php"> SetEnv BOAT_SYNC_TOKEN ...`）
- **`wordpress/.user.ini`** — 互換フォールバックとして残置

デプロイは既存の `.github/workflows/deploy-wp.yml`（`wordpress/**` push で FTPS 自動配布）。疎通は `HTTP=400 missing_field=title` で確認（token認証通過、validationで正常弾き）。

### 新 token（2026-04-22 rotate 済み）
- 値: `dslGr00chvVut1fzLEEOnyoBnjAU`（28 chars）
- 3点同期完了: `.env` / `forecast-config.php` / Cowork タスク環境変数

> **トークンローテート時の手順は [docs/TOKEN_ROTATION.md](./TOKEN_ROTATION.md) を参照**

---

## 新規 Mac で Cowork 運用を始めるときの手順

1. **Cowork アプリをインストール**してサインイン
2. **`~/repos/boat`** を git clone（GitHub Actions deploy があるので private repo アクセス権が必要）
3. **`.env`** を手動で配置（値は 1Password「boat / WordPress sync」参照）
4. **Cowork タスク一覧**で 6 タスクを確認。初回同期時に自動で現れるはず
5. **ボート系2タスクに `~/repos/boat` フォルダを接続**（最重要、設定画面から）
6. **launchd が稼働してないことを確認**（`launchctl list | grep -E "boat|claude-code\.task"` で何も出ないのが正常）
7. `boat-race-fetcher` で `Run now` を1回実行して動作確認（「実行可能タスクなし」等が返れば成功）

---

## トラブルシュート Flow

### 症状: `boat-race-fetcher` のログに「ボートレースプロジェクトディレクトリが見つかりません」
→ **フォルダ接続が外れている**。タスク詳細画面で `~/repos/boat` を再接続

### 症状: morning-v2 が AUP 違反で応答拒否
→ プロンプト冒頭の AUP 文言が消えていないか確認。消えていれば SKILL.md からコピペで挿入

### 症状: WP sync が 403 invalid_token
→ 3点同期ズレ。[docs/TOKEN_ROTATION.md](./TOKEN_ROTATION.md) の手順で再同期、または `curl -X POST $WP_SYNC_URL -H "X-Boat-Token: $WP_SYNC_TOKEN" -d '{"ping":"test"}'` で疎通確認

### 症状: Cowork スケジュールが全く起動しない
→ Cowork アプリ自体が起動しているか、ネットワーク接続、サインイン状態を確認

---

## ロールフォワード（launchd に戻したい場合）

1. Cowork 各タスクを **Pause**（UIトグル or `update_scheduled_task enabled=false`）
2. launchd plist を load し直し:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist
   launchctl load ~/Library/LaunchAgents/com.boat.run-pending.plist
   # 他も同様
   ```
3. SKILL.md 側に Cowork prompt で加えた修正を反映
4. AUP refusal 対策の追加検討

---

## 関連ファイル・パス

| 項目 | 場所 |
|---|---|
| SKILL.md（boat-daily-morning-v2） | `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` |
| SKILL.md（boat-race-fetcher の元） | `~/Agent/personal-life/Scheduled/boat-run-pending/SKILL.md` |
| launchd plist（停止中） | `~/Library/LaunchAgents/com.claude-code.task.*.plist` / `com.boat.*.plist` |
| 純bash cron ラッパー（使っていない） | `~/Agent/scripts/claude-code-cron/boat_run_pending.sh` |
| WP 受信口（heteml deployed） | `/web/boat/api/forecast-sync.php` |
| WP 受信口（source） | `~/repos/boat/wordpress/forecast-sync.php` |
| WP token定数（source） | `~/repos/boat/wordpress/forecast-config.php` |
| 送信スクリプト | `~/repos/boat/scripts/publish_wordpress.py` |
| `.env`（gitignore） | `~/repos/boat/.env` |
| GitHub Actions deploy | `.github/workflows/deploy-wp.yml`（`wordpress/**` push で自動FTPS） |
| トークンローテ手順 | `docs/TOKEN_ROTATION.md` |

---

## 2026-04-22 に完了した作業ログ（サマリ）

- [x] Cowork Scheduled tasks 6件を `Paused` → cron付き `enabled`
- [x] ボート系2タスクに AUP 文言挿入
- [x] ボート系2タスクに `~/repos/boat` フォルダ接続
- [x] launchd 8ジョブ を `launchctl unload`
- [x] WP sync 403 → C案（PHP定数）で決着
- [x] 新 token 生成 `dslGr00chvVut1fzLEEOnyoBnjAU` に rotate、3点同期
- [x] 本日 4/22 × 8 会場の予測 HTML 生成 & WP 投稿（新規 post_id 160-167）
- [x] 4/21 verify 振り返り × 8 会場 再送信（WP 上書き更新）
- [x] 192 件の pending_tasks を登録、以降は boat-race-fetcher が4分毎に消化
- [x] TODO.md の P0 #6 / #7 を解決済みにマーク（別途更新）
