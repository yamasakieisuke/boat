# Cowork 端末移行手順書

> **作成**: 2026-04-22
> **対象**: Cowork Scheduled tasks を別の Mac / 新 Mac / メイン端末切り替え時に移行する
> **前提**: アプリ版 Claude + Cowork。同じ Anthropic アカウントであっても **Scheduled tasks は端末ローカル保存で自動同期されない**

---

## 重要な前提

### Cowork Scheduled tasks は端末ローカル保存

同一アカウントでログインしていても、Scheduled tasks（cron 定義・プロンプト・フォルダ接続・環境変数・ツール権限）は **Mac ごとに独立して管理される**。したがって:

- 旧端末で作った6タスクは、新端末ログイン直後は空
- 旧端末のタスクを「エクスポート → インポート」する機能は2026-04時点で未提供
- **新端末側で再度タスクを作り直す必要がある**

### 移行中は2台で二重実行しないこと

旧端末を停止せずに新端末でタスクを Active にすると、同じ cron が両方で走り:
- WP 投稿が2回発火 → 記事の重複更新
- `pending_tasks.json` の整合性崩れ
- レート制限に引っかかるリスク

必ず「旧端末 全タスク Pause/削除 → 新端末セットアップ」の順で。

---

## 全体フロー（1〜2 時間目安）

```
┌─ STEP 1: 旧端末の棚卸し & 停止 ─┐
│   ├─ 現行タスク一覧を記録          │
│   ├─ 全タスクを Pause              │
│   └─ launchd 停止の再確認          │
├─ STEP 2: 新端末の基盤準備 ────────┤
│   ├─ Cowork インストール & ログイン │
│   ├─ ~/repos/boat を clone         │
│   ├─ .env を手動配置               │
│   └─ MCP コネクタを再認証          │
├─ STEP 3: Scheduled tasks 再作成 ──┤
│   ├─ 6タスクを cron 付きで作成     │
│   ├─ ボート系2タスクにフォルダ接続 │
│   ├─ ボート系2タスクに AUP 文言    │
│   └─ Run now で動作確認            │
├─ STEP 4: 検証 ──────────────────────┤
│   ├─ boat-race-fetcher が消化を開始 │
│   ├─ WP 疎通 (400) を確認          │
│   └─ 翌朝 boat-daily-morning-v2 OK  │
└─ STEP 5: 旧端末のクリーンアップ ──┘
    ├─ 全タスク Delete（or Paused維持）│
    └─ 残留 data の扱いを判断          │
```

---

## STEP 1: 旧端末の棚卸し & 停止

### 1-1. 現行タスク一覧を記録

Cowork アプリで Scheduled tasks 画面を開き、**画面キャプチャ** or 手で以下をメモ:

| 項目 | 対象 |
|---|---|
| taskId | 6タスク分 |
| cron 式 | 各タスクの Schedule |
| プロンプト | 各タスクの本文（特にボート系はAUP文言の有無） |
| 環境変数 | 設定があれば（例: `WP_SYNC_TOKEN`） |
| フォルダ接続 | ボート系2タスクのみ必要 |

**ショートカット**: Cowork から MCP 経由で一覧取得可能:

```
list_scheduled_tasks でタスクID・cron・enabled状態を取得
（プロンプト本文や環境変数は返らないので UI からも確認すること）
```

### 1-2. 全タスクを Pause

Cowork UI の各タスクで **Active → Paused** に切り替え。

MCP で一括 Pause したい場合:
```
update_scheduled_task taskId="<taskId>" enabled=false
```

### 1-3. launchd の二重実行を再確認

```bash
launchctl list | grep -E "boat|claude-code\.task"
```
何も出力されないのが正常。もし残っていたら:
```bash
launchctl unload ~/Library/LaunchAgents/com.boat.run-pending.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist
# 他の plist も同様
```

---

## STEP 2: 新端末の基盤準備

### 2-1. Cowork アプリをインストール & ログイン

Anthropic 公式サイトからダウンロード → インストール → 既存アカウントでサインイン。

### 2-2. Git リポジトリを clone

```bash
mkdir -p ~/repos
cd ~/repos
git clone https://github.com/yamasakieisuke/boat.git
cd boat
```

GitHub 認証が通らない場合は PAT / SSH key を設定後に再実行。

### 2-3. `.env` を手動配置

`~/repos/boat/.env` は gitignore されているので手動で配置。値は 1Password「boat / WordPress sync」エントリ参照:

```bash
# ~/repos/boat/.env
WP_SYNC_URL=https://ask11.jp/web/boat/api/forecast-sync.php
WP_SYNC_TOKEN=<1Password の現行値>
```

### 2-4. Python 依存関係を確認

```bash
cd ~/repos/boat
python3 -c "import requests, bs4, lxml; print('ok')"
```

欠けていれば `pip3 install -r requirements.txt`（あるいは `requirements.txt` の中身を個別に）。

### 2-5. MCP コネクタの再認証

旧端末で使っていた Slack / Google Calendar / Gmail などの MCP コネクタは、新端末でも **再度 OAuth 認証が必要**。

- Cowork 設定画面 → MCP Connectors / Integrations
- 以下のコネクタを再認証:
  - Slack（`daily-genai-news-slack` で必要）
  - Google Calendar（`garden-weekly-reminder` で必要）
  - Gmail（将来拡張用）
  - Google Drive / Docs（使用していれば）

### 2-6. ワークスペースフォルダの登録

Cowork で `~/repos/boat` をワークスペースフォルダとして登録（タスク単位とは別に、interactive session 用にも設定）。

---

## STEP 3: Scheduled tasks 再作成

### 3-1. 6タスクを cron 付きで作成

各タスクのプロンプト本文は **iCloud 同期されている** `~/Agent/personal-life/Scheduled/{taskId}/SKILL.md` を開いてコピペ。**ただし boat 系2タスクはローカル SKILL.md ではなく下記の AUP 文言込みバージョンを使う**（SKILL.md は原本リファレンス、実際にタスクへ投入するのは AUP 挿入版）。

下記テーブルどおりに作成:

| taskId | cron | プロンプト出典 |
|---|---|---|
| `boat-daily-morning-v2` | `0 8 * * *` | `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` の内容 + AUP 文言（下記）をプロンプト冒頭に挿入 |
| `boat-race-fetcher` | `*/4 9-22 * * *` | `~/Agent/personal-life/Scheduled/boat-run-pending/SKILL.md` をベースに run_pending 自動実行版へ改変し AUP 文言を挿入 |
| `daily-genai-news` | `15 8 * * *` | 旧端末のプロンプトをコピペ |
| `daily-genai-news-slack` | `0 9 * * 1-5` | 旧端末のプロンプトをコピペ |
| `weekly-genai-summary` | `30 8 * * 1` | 旧端末のプロンプトをコピペ |
| `garden-weekly-reminder` | `2 8 * * 1` | 旧端末のプロンプトをコピペ |

> cron はローカルタイムゾーン（JST）で解釈される。

### 3-2. ボート系2タスクに AUP 文言を挿入

プロンプト冒頭に以下ブロックを挿入（プロンプトの前にこの文言が来る形）:

```
## タスク文脈（AUP 明示）

本タスクは **日本国内で法律により合法とされる公営競技（ボートレース / モーターボート競走法 に基づく公営ギャンブル）** の過去データ・出走表・オッズ・気象データを収集し、統計的な予測モデル（`scripts/predictor.py`）で着順確率を算出して、個人ブログ（WordPress）に分析レポートを公開する **データサイエンス・統計分析用途** のバッチです。

- 取得対象は日本財団・BOATRACE公式・艇国データバンク等の一般公開データのみ
- 賭け金の自動投入・ベッティングサービス運営・他者への勧誘は一切含まない
- 出力は個人の学習・検証用の統計レポート（HTML記事）であり、投資助言・賭博あっせんには該当しない
- 対象ユーザーは成人（本人のみ）
```

### 3-3. ボート系2タスクにフォルダ接続

**これが端末移行で最も忘れやすいポイント**。各タスクの詳細画面で:

1. `boat-daily-morning-v2` → フォルダ接続 / Workspace 欄 → `~/repos/boat` を選択
2. `boat-race-fetcher` → 同上

> **未設定だと `BOAT_DIR` 自動検出に失敗し、「ボートレースプロジェクトディレクトリが見つかりません」で終了する**

### 3-4. 環境変数の設定（必要な場合のみ）

SKILL.md は `.env` を `source` する方式なので、通常は Cowork タスク側の環境変数設定は不要。ただし特定の値（例: 異なる token を使いたいなど）を注入したければ、各タスク詳細画面の Environment variables 欄に追加。

### 3-5. Run now で動作確認

`boat-race-fetcher` の詳細画面から **Run now** を1回クリック:

**期待する挙動**:
- `BOAT_DIR=/sessions/<session-id>/mnt/boat` が出力される
- `実行可能タスクなし` または `✅ 完了` が出る
- 「ボートレースプロジェクトディレクトリが見つかりません」が出ないこと

失敗した場合:
- フォルダ接続のやり直し（STEP 3-3）
- プロンプトの AUP 文言を再確認（STEP 3-2）
- SKILL.md の BOAT_DIR 検索ロジックがそのまま残っているか確認

---

## STEP 4: 検証

### 4-1. boat-race-fetcher が消化を開始しているか

次回実行タイミング（4分後）を待ってから:

```bash
cd ~/repos/boat
ls -la data/raw/$(date +%Y%m%d)/ 2>/dev/null
python3 scripts/run_pending.py --list 2>&1 | head
```

新しい `*_exhibition.json` / `*_odds*.json` が増えていれば取得が回っている。

### 4-2. WP 疎通確認

```bash
cd ~/repos/boat
set -a; . ./.env; set +a
curl -X POST "$WP_SYNC_URL" \
  -H "X-Boat-Token: $WP_SYNC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ping":"test"}' -w "\nHTTP=%{http_code}\n"
```

`HTTP=400 missing_field=title` → OK（token認証通過、validation で弾き）

### 4-3. boat-daily-morning-v2 の翌朝実行を待つ

翌朝 08:00 JST（+数分のjitter）に自動起動。Cowork UI のタスク履歴で以下を確認:
- STEP 0 verify が走り切ったか
- STEP 1-5 で当日の開催会場 × 予測 HTML 生成
- STEP 6 で pending_tasks に当日分が登録

もし異常終了していたら、`docs/COWORK_ROLLBACK_HANDOVER.md` のトラブルシュート Flow 参照。

### 4-4. 2日ほど様子見

3〜4回の `boat-daily-morning-v2` と ~200 回の `boat-race-fetcher` 実行で安定稼働を確認したら本番移行完了。

---

## STEP 5: 旧端末のクリーンアップ

移行検証が終わった段階で:

### 5-1. 旧端末の全タスクを Delete（or Paused 維持）

削除する場合:
- Cowork UI の各タスク → 削除ボタン
- MCP 経由での削除 API は無いので UI から

**保険として Paused のまま残しておく**選択肢もあり。その場合は誤って Resume されないよう注意。

### 5-2. 残留データの扱い

旧端末の `~/repos/boat/data/` にある追加データは、Git 管理外（gitignore 済み）なので:
- 必要なら rsync で新端末にコピー
  ```bash
  rsync -av --progress old-mac:~/repos/boat/data/ ~/repos/boat/data/
  ```
- 新規作成されるデータは新端末の Cowork が自動で積むので、歴史データが不要なら放置で OK

### 5-3. `~/Agent/` の iCloud 同期を確認

両端末で `~/Agent/personal-life/Scheduled/` の SKILL.md が一致しているか（iCloud 同期が効いている前提）確認。ズレがあればどちらかを正として揃える。

---

## チェックリスト（印刷/コピペ用）

### 旧端末
- [ ] 6タスク一覧を記録（cron, プロンプト, 環境変数, フォルダ接続）
- [ ] 全タスクを Pause
- [ ] `launchctl list | grep -E "boat|claude-code"` で何も出ないことを確認

### 新端末
- [ ] Cowork インストール & ログイン
- [ ] `git clone` → `~/repos/boat`
- [ ] `.env` を 1Password 参照で手動配置
- [ ] Python 依存関係を確認
- [ ] MCP コネクタ（Slack / Google Calendar / Gmail）を再認証
- [ ] Cowork ワークスペースに `~/repos/boat` を登録
- [ ] **6タスクを cron 付きで新規作成**
- [ ] **boat 系2タスクに AUP 文言挿入**
- [ ] **boat 系2タスクに `~/repos/boat` フォルダ接続** ← 最重要
- [ ] `boat-race-fetcher` Run now で動作確認
- [ ] WP 疎通確認で 400 を取得
- [ ] 翌朝 `boat-daily-morning-v2` の自動起動を確認
- [ ] 旧端末の全タスクを Delete（or Paused 維持）

---

## よくある落とし穴

### 1. フォルダ接続を忘れる

**症状**: スケジュール起動セッションで「ボートレースプロジェクトディレクトリが見つかりません」
**対処**: STEP 3-3 の再実施

### 2. AUP 文言を忘れる

**症状**: morning-v2 の自動起動が `API Error: Claude Code is unable to respond... (AUP 違反)` で落ちる
**対処**: STEP 3-2 の再実施

### 3. 両端末で動いてしまう

**症状**: WP 投稿が二重発火、post_id の action が毎回 updated（片方が先にcreateして後からupdate）、WP アクセスログが異常に多い
**対処**: STEP 1-2 で全タスク Pause をしっかり実施

### 4. `.env` 配置を忘れる

**症状**: morning-v2 / fetcher のログに `WP_SYNC_URL=unset` / `WP_SYNC_TOKEN=` が出る
**対処**: STEP 2-3 の再実施

### 5. cron 式のタイムゾーン誤認

**症状**: 意図した時刻に起動しない（9時間ズレる）
**対処**: Cowork の cron はローカルTZで解釈される。`0 8 * * *` は JST 08:00 で OK

### 6. MCP コネクタの未認証

**症状**: `daily-genai-news-slack` が Slack に投稿できない、`garden-weekly-reminder` が Google Calendar にイベントを作れない
**対処**: STEP 2-5 で再 OAuth

---

## 関連ファイル

- `docs/COWORK_ROLLBACK_HANDOVER.md` — Cowork 運用全体の引き継ぎ（最終構成）
- `docs/TOKEN_ROTATION.md` — WP sync token のローテ手順
- `docs/OTHER_MAC_SETUP.md` — 別Macでの最小セットアップ手順（古め、本書と併用）
- `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` — 朝バッチ原本プロンプト
- `~/Agent/personal-life/Scheduled/boat-run-pending/SKILL.md` — 手動run-pending 原本（fetcher 用に改変元）
