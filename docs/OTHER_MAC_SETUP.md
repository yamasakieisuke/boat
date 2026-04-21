# 別Mac（自宅Mac）でのセットアップ手順

初回セットアップは会社Macで完了済み（2026-04-21）。この文書は**自宅Mac**向け、初回のみ5分程度。

## 前提

- Homebrew インストール済み
- GitHub 2FA設定済み（Passkey or Authenticator app）

## 手順

### 1. GitHub CLIをインストール

```bash
brew install gh
```

### 2. GitHubにログイン

```bash
gh auth login --web --git-protocol https --hostname github.com
```

表示された8桁コードをブラウザ（https://github.com/login/device）で入力し、Passkey等で認証。

### 3. リポジトリをクローン

```bash
mkdir -p ~/repos
cd ~/repos
gh repo clone yamasakieisuke/boat
```

### 4. 作業ディレクトリに入る

```bash
cd ~/repos/boat
```

以降、Claude Code を開くのも `~/repos/boat` で。

### 5. 動作確認

```bash
git remote -v
# → origin https://github.com/yamasakieisuke/boat (fetch/push)

git status
# → On branch main / nothing to commit, working tree clean
```

## 日常の運用

### 作業開始時

Claude Code を `~/repos/boat` で起動すると **SessionStart hook** が自動で `git pull --rebase --autostash` を実行します（何もしなくてOK）。

### 作業中

普通に編集・コミット。

### 作業終了時

Claude Code を閉じると **Stop hook** が未コミット/未push の有無をチェックし、警告表示します。

手動同期は `/sync` スラッシュコマンドで、add + commit + push を一発実行可能。

## ローカル専用ファイル

以下は各Mac個別に置く必要があります（gitに含まれない）：

- `.env` — API/WPトークン等（元のMacからUSB/1Password経由で持ち込み）
- `data/` `output/` `inbox/` `logs/` — 生成物。初回実行で自動生成

## トラブルシュート

### `git pull` でコンフリクト

別Macで未pushのまま変更していた場合に発生。
- `git status` で競合ファイル確認
- 手動解決 or Claude Codeに「コンフリクト解決して」と依頼

### 認証エラー

```bash
gh auth status
# ログインし直すなら:
gh auth refresh
```
