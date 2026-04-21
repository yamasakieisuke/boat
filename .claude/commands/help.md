---
description: boatリポジトリで使えるコマンド・ドキュメント・運用ルールの一覧を表示
---

以下を整形して表示してください。コマンド実行せず**一覧のみ**を提示します。

## 📁 boat リポジトリで使えるカスタムコマンド

| コマンド | 動作 |
|---|---|
| `/sync` | 変更を add + commit + push（一発） |
| `/pull` | リモートから pull（手動） |
| `/help` | このヘルプを表示 |

## 🪝 自動hook

| タイミング | 動作 |
|---|---|
| セッション開始時 | `git pull --rebase --autostash` を自動実行 |
| セッション終了時 | 未コミット/未push変更があれば警告表示 |

## 📚 リポジトリ内ドキュメント

| 用途 | パス / URL |
|---|---|
| 環境構造・運用まとめ | `CLAUDE.md`（セッション開始で自動読込） |
| 別Macセットアップ手順 | `docs/OTHER_MAC_SETUP.md` |
| WP自動デプロイ仕組み | `docs/WP_AUTO_DEPLOY.md` |
| v5.20 変更履歴 | `docs/version_history.md` |
| 結果データ取得の仕組み | `docs/RESULTS_ACQUISITION.md` |
| WPプラグイン引継ぎ | `docs/wordpress_handover.md` |
| 優先度付きTODO | `TODO.md` |
| 本体仕様 | `README.md`（47KB） |

## 🔄 サーバーデプロイ

- `wordpress/` 配下を変更して `/sync` → GitHub Actions → heteml FTPS で自動デプロイ
- デプロイ先:
  - `wordpress/boat-forecast-viewer/` → `/web/boat/wp-content/plugins/boat-forecast-viewer/`
  - `wordpress/forecast-sync.php` → `/web/boat/api/forecast-sync.php`
- 状態確認: `gh run list --repo yamasakieisuke/boat --limit 3`

## ⏰ launchd スケジュール実行（会社Mac主ホスト）

| plist | 頻度 | 内容 |
|---|---|---|
| `com.boat.run-pending.plist` | 4分毎 | 展示/オッズ積み残しタスク処理 |
| `com.claude-code.task.boat-daily-morning-v2.plist` | 毎朝8:00 | 当日朝の予測生成・WP投稿 |

**両Macで同時に有効化しないこと**（WP送信が二重になる）。

## 🌐 関連URL

- GitHub: https://github.com/yamasakieisuke/boat
- Actions: https://github.com/yamasakieisuke/boat/actions
- Secrets: https://github.com/yamasakieisuke/boat/settings/secrets/actions
- 公開ブログ: https://ask11.jp/web/boat/

## 💡 新規コードベースプロジェクトを立ち上げたいとき

boatと同じ運用を他プロジェクトに展開する手順は **`/new-codebase`** コマンド（グローバル）で参照可能。
