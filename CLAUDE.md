# boat リポジトリ — セッション開始時読み込みファイル

Claude Code は本ディレクトリで起動するとこのファイルを自動読み込みする。
他Macから初めて触る場合はまず `docs/OTHER_MAC_SETUP.md` を参照。

---

## プロジェクト概要

ボートレース予想エンジン **v5.20**（2026-04-18 稼働）。
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
| ペンディング | `~/repos/boat/data/pending_tasks.json` | 展示/オッズ取得予定 |
| 実行ログ | Cowork UI 各タスクのセッション履歴 | 旧 launchd 時代のログは `~/Library/Logs/claude-tasks/` に残存 |

## スケジュール実行（Cowork Scheduled tasks）

**2026-04-22 以降は Cowork 側で定期実行。** launchd は全ジョブ `launchctl unload` で停止済み（plist ファイルは残置）。

| taskId | cron | 頻度 | フォルダ接続 |
|---|---|---|---|
| `boat-daily-morning-v2` | `0 8 * * *` | 毎朝 08:00 | ✅ `~/repos/boat` 必須 |
| `boat-race-fetcher` | `*/4 9-22 * * *` | 9-22時の4分毎 | ✅ `~/repos/boat` 必須 |

### Cowork 運用の重要ポイント

1. **タスク単位でフォルダ接続**が必要。Cowork のスケジュール起動は interactive session とは別の isolated sandbox で走るため、各タスク詳細画面で `~/repos/boat` を明示接続する。未接続だと `BOAT_DIR` 検出失敗で即終了
2. **AUP 文言の挿入**: プロンプト冒頭に公営ギャンブル用途明示を残しておく（Claude の応答拒否予防）
3. **launchd 二重起動禁止**: `launchctl list | grep -E "boat|claude-code\.task"` で何も出ないのが正常
4. 端末非依存のため、どの Mac で Cowork を起動していても実行される（逆に新規 Mac でも上記フォルダ接続は個別に必要）

### 関連ファイル

- 定義 SKILL（Cowork プロンプトの原本）: `~/Agent/personal-life/Scheduled/boat-*/SKILL.md`（iCloud 同期）
- launchd plist（停止中・ロールフォワード用）: `~/Library/LaunchAgents/com.claude-code.task.*.plist` / `com.boat.*.plist`
- 運用引き継ぎ: [docs/COWORK_ROLLBACK_HANDOVER.md](docs/COWORK_ROLLBACK_HANDOVER.md)

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
- `docs/TOKEN_ROTATION.md` — **WP sync token ローテート手順（3点同期）**
- `docs/OTHER_MAC_SETUP.md` — 別Macでの初回セットアップ手順
- `docs/CLAUDE_COWORK_HANDOVER.md` — Claude 他モデルとの協業時の引き継ぎ
- `docs/RESULTS_ACQUISITION.md` — 結果データ取得の仕組み
- `docs/wordpress_handover.md` — WP 側プラグインの引き継ぎ
- `docs/version_history.md` — v5.20 までの変更履歴
- `docs/WP_AUTO_DEPLOY.md` — `wordpress/**` push での GitHub Actions 自動FTPSデプロイ
- `docs/claude-design-assets/README.md` — Claude Design 連携素材と投入手順
