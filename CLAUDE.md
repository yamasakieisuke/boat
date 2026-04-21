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
| 実行ログ | `~/Library/Logs/claude-tasks/boat-run-pending-YYYYMMDD.log` | |

## スケジュール実行（launchd）

**重要: launchd ジョブは1台のMacでのみ有効化すること**（両方で動くとWP再送信が二重になる）。

| plist | 頻度 | 現在有効なMac |
|---|---|---|
| `com.boat.run-pending.plist` | 4分毎 | 会社Mac |
| `com.claude-code.task.boat-daily-morning-v2.plist` | 毎朝8:00 | 会社Mac |

場所: `~/Library/LaunchAgents/`（iCloud非同期、各Mac独立管理）
定義SKILL: `~/Agent/personal-life/Scheduled/boat-*/SKILL.md`（iCloud同期）
ラッパー: `~/Agent/scripts/claude-code-cron/boat_run_pending.sh`（iCloud同期）

自宅Mac側でジョブを走らせたい場合は、**先に会社Macのジョブを `launchctl unload` で停止** すること。

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

- `docs/OTHER_MAC_SETUP.md` — 別Macでの初回セットアップ手順
- `docs/CLAUDE_COWORK_HANDOVER.md` — Claude 他モデルとの協業時の引き継ぎ
- `docs/RESULTS_ACQUISITION.md` — 結果データ取得の仕組み
- `docs/wordpress_handover.md` — WP 側プラグインの引き継ぎ
- `docs/version_history.md` — v5.20 までの変更履歴
- `docs/claude-design-assets/README.md` — Claude Design 連携素材と投入手順
