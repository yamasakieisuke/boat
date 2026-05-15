# boat リポジトリ — セッション開始時読み込みファイル

Claude Code は本ディレクトリで起動するとこのファイルを自動読み込みする。
他Macから初めて触る場合はまず `docs/OTHER_MAC_SETUP.md` を参照。

---

## プロジェクト概要

ボートレース予想エンジン **v5.23**（2026-05-15 朝バッチ単一コマンド化）。
- 公営競技（ボートレース）の公開データを統計分析し、個人ブログ(WordPress)に予測レポートを公開するデータサイエンス用途のバッチ
- 本格詳細は `README.md`（47KB）、優先度タスクは `TODO.md`、バージョン履歴は `docs/version_history.md`

## 環境構造

| 種類 | パス | 備考 |
|---|---|---|
| コード本体 | `~/repos/boat/` | git管理、iCloud外 |
| GitHub | `https://github.com/yamasakieisuke/boat` | private |
| .env | `~/repos/boat/.env` | `WP_SYNC_URL` / `WP_SYNC_TOKEN`。**gitignore済** |
| 蓄積データ | `~/repos/boat/data/` | racecard/player/tide等、**gitignore済** |
| 出力HTML | `~/repos/boat/output/` | 会場別、**gitignore済** |
| ペンディング | `~/repos/boat/data/fetch_requests.json` | 展示/オッズ取得依頼（v5.22〜） |
| 実行ログ | Cowork UI 各タスクのセッション履歴 / GitHub Actions | 旧 launchd 時代のログは `~/Library/Logs/claude-tasks/` に残存 |

## スケジュール実行（現行構成 2026-05-15〜）

### 朝バッチ: GitHub Actions に移行済み

**2026-05-15 に Cowork sandbox から boatrace.jp への TCP 接続がブロックされる問題が判明し、朝バッチを GitHub Actions に移行。**

| 実行基盤 | タスク | cron (UTC) | 備考 |
|---|---|---|---|
| **GitHub Actions** | `morning-batch.yml` | `0 23 * * *`（08:00 JST） | boatrace.jp に直接接続可 |
| Cowork（停止中） | `boat-daily-morning-v2` | — | ネットワーク制限により無効化 |
| Cowork（有効） | `boat-race-fetcher` | `*/4 9-22 * * *` | 9-22時の4分毎 |

**GitHub Actions の手動実行**: リポジトリ → Actions → Boat Morning Batch → Run workflow
- `skip_verify`: 前日 verify スキップ
- `jcd`: 特定会場のみ（例: 22）
- `date`: 日付指定 YYYYMMDD

**必要な GitHub Secrets**（Settings → Secrets → Actions）:
- `WP_SYNC_URL` / `WP_SYNC_TOKEN`（`.env` と同じ値）

### Cowork sandbox のネットワーク制限（既知の問題）

- スケジュールタスクの isolated sandbox は boatrace.jp（184.26.219.91）への **TCP 接続がブロック**される
- インタラクティブセッションからは到達可能だが 1リクエスト約 10秒と低速（サンドボックスの地理的距離）
- Pro プランのため Admin → Capabilities でのネットワーク設定変更不可
- **回避策**: `mcp__workspace__web_fetch`（MCP経由）は Anthropic インフラ経由なので制限を受けない

### `boat-race-fetcher` (Cowork) の重要ポイント

1. **タスク単位でフォルダ接続**が必要。各タスク詳細画面で `~/repos/boat` を明示接続
2. **AUP 文言の挿入**: プロンプト冒頭に公営ギャンブル用途明示を残しておく（Claude の応答拒否予防）
3. **launchd 二重起動禁止**: `launchctl list | grep -E "boat|claude-code\.task"` で何も出ないのが正常

### 関連ファイル

- 朝バッチ workflow: `.github/workflows/morning-batch.yml`
- 定義 SKILL（Cowork プロンプトの原本）: `~/Documents/Claude/Scheduled/boat-*/SKILL.md`（iCloud 同期）
- launchd plist（停止中・ロールフォワード用）: `~/Library/LaunchAgents/com.claude-code.task.*.plist` / `com.boat.*.plist`
- 運用引き継ぎ: [docs/COWORK_ROLLBACK_HANDOVER.md](docs/COWORK_ROLLBACK_HANDOVER.md)

### v5.22〜 の主要変更

- **pending 登録廃止**: `pending_tasks.json` → `fetch_requests.json` の依頼ベースに変更
- **朝バッチ単一コマンド化 (v5.23)**: `scripts/run_morning.py` が STEP 0〜5 を統合実行

## 作業開始時/終了時の運用

- **セッション開始時**: `SessionStart` hook が `git pull --rebase --autostash` を自動実行
- **セッション終了時**: `Stop` hook が未コミット/未push 変更を警告表示
- **手動同期**: `/sync` スラッシュコマンドで add + commit + push 一発
- **手動pull**: `/pull` スラッシュコマンド

## コード品質の前提

- `predictor.py` 全体で `BASE_DIR = Path(__file__).parent.parent` を使用。ハードコードパス禁止
- `PREDICTOR_VERSION` は `scripts/predictor.py` 冒頭で管理
- WordPress 再送信は `.env` の `WP_SYNC_URL` / `WP_SYNC_TOKEN` 両方が必須

## 関連文書

- `docs/COWORK_ROLLBACK_HANDOVER.md` — **Cowork運用引き継ぎ（2026-04-22 移行記録・現行構成）**
- `docs/COWORK_DEVICE_MIGRATION.md` — **別端末への Cowork Scheduled tasks 移行手順**
- `docs/TOKEN_ROTATION.md` — **WP sync token ローテート手順（3点同期）**
- `docs/OTHER_MAC_SETUP.md` — 別Macでのリポジトリ初回セットアップ手順
- `docs/CLAUDE_COWORK_HANDOVER.md` — Claude 他モデルとの協業時の引き継ぎ
- `docs/RESULTS_ACQUISITION.md` — 結果データ取得の仕組み
- `docs/wordpress_handover.md` — WP 側プラグインの引き継ぎ
- `docs/version_history.md` — v5.20 までの変更履歴
- `docs/WP_AUTO_DEPLOY.md` — `wordpress/**` push での GitHub Actions 自動FTPSデプロイ
- `.github/workflows/morning-batch.yml` — 朝バッチ GitHub Actions ワークフロー（2026-05-15〜）
- `docs/claude-design-assets/README.md` — Claude Design 連携素材と投入手順
