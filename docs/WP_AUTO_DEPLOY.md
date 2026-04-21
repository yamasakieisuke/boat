# WordPress 自動デプロイ (GitHub Actions → heteml FTPS)

`wordpress/` 配下のファイルが `main` ブランチに push されると、GitHub Actions が自動で heteml サーバーへ FTPS アップロードする仕組み。

## 仕組み

1. `main` に push、`wordpress/**` に変更あり
2. `.github/workflows/deploy-wp.yml` が起動（GitHubの無料枠で実行）
3. heteml の FTPS サーバー (`ftp-ask.heteml.net:21`) に接続
4. 変更差分のみを転送
   - `wordpress/boat-forecast-viewer/` → `/web/boat/wp-content/plugins/boat-forecast-viewer/`
   - `wordpress/forecast-sync.php` → `/web/boat/api/forecast-sync.php`

## 初回セットアップ（一度だけ）

### 1. FTPパスワードをGitHub Secretsに登録

ブラウザで https://github.com/yamasakieisuke/boat/settings/secrets/actions を開く。

- **New repository secret** をクリック
- Name: `HETEML_FTP_PASSWORD`
- Secret: heteml の ask_wp ユーザーの FTP パスワード
- **Add secret** をクリック

※ 一度登録すると値は閲覧不可（更新・削除のみ可能）。ログにも出ないよう自動マスク。

### 2. 動作確認

ローカルで `wordpress/` 配下の任意のファイルを1バイト変更して commit & push:

```bash
cd ~/repos/boat
echo "" >> wordpress/boat-forecast-viewer/boat-forecast-viewer.php
git add -A && git commit -m "Test auto-deploy" && git push
```

ブラウザで https://github.com/yamasakieisuke/boat/actions を開く。

- `Deploy WordPress files to heteml` ワークフローが実行中/成功になっているか確認
- ログで「Uploaded: boat-forecast-viewer.php」等が出ていればOK
- サーバー側のファイル更新時刻が変わっているか確認

## 日常運用

変更手順は変わらない:

1. ローカルで `wordpress/` 配下を編集
2. `/sync` コマンド（or `git add/commit/push`）
3. **FTPアップは不要** — Actionsが自動でやる
4. 失敗時は GitHub Actions のログに詳細あり

## 手動トリガー

ファイル変更なしでもデプロイしたい場合:
1. https://github.com/yamasakieisuke/boat/actions
2. 左側 `Deploy WordPress files to heteml` を選択
3. `Run workflow` ボタン → main ブランチを選択 → 実行

## トラブルシュート

| 症状 | 対処 |
|---|---|
| 認証エラー (`530 Login incorrect`) | Secrets の `HETEML_FTP_PASSWORD` を更新 |
| 接続タイムアウト | heteml 側 FTP制限の可能性。`protocol: ftp`（平文）に一時変更してテスト |
| ファイルは上がったが反映されない | heteml のキャッシュ or WP側のキャッシュプラグイン。サーバー側で削除 |
| `forecast-sync.php` の場所が違う | `.github/workflows/deploy-wp.yml` の `server-dir` を調整 |

## セキュリティ注意

- パスワードは GitHub Secrets のみに保管。**コード内に書かない**
- FTP (平文) より FTPS (TLS暗号) を使用中
- より堅牢にしたい場合は SFTP (SSH) 化を検討 — heteml の SFTP 対応確認要
- リポジトリが public になるとワークフロー実行が制限される。**必ず private を維持**
