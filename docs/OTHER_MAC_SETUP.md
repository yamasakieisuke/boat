# 別Mac（自宅Mac）でのセットアップ手順

会社Macで初回セットアップ済み（2026-04-21）。本文書は**自宅Mac**で同じ作業環境を再現する手順。所要 10〜15分。

## 前提条件

- Homebrew インストール済み
- GitHub 2FA 設定済み（Passkey + Authenticator app、Recovery codes は 1Password）
- 1Password にログイン可能（`.env` の再構築に使用）

## Step 1. GitHub CLI インストール＆認証

```bash
brew install gh
gh auth login --web --git-protocol https --hostname github.com
```

ブラウザで 8桁コードを入力→Passkey/TouchID で認証→`Authorize` を承認。

```bash
gh auth setup-git  # git認証ヘルパーを設定
```

## Step 2. git の名前・メール設定

会社Macと同じ identity で揃える：

```bash
git config --global user.name "yamasakieisuke"
git config --global user.email "ask11nl@gmail.com"
```

## Step 3. リポジトリをクローン

```bash
mkdir -p ~/repos
cd ~/repos
gh repo clone yamasakieisuke/boat
cd ~/repos/boat
```

動作確認:

```bash
git remote -v   # → origin https://github.com/yamasakieisuke/boat
git status      # → On branch main / nothing to commit, working tree clean
ls .claude/     # → settings.json commands/
```

## Step 4. `.env` を再構築

`.env` は .gitignore 除外のためクローンに含まれない。自宅Macで作成する:

```bash
cat > ~/repos/boat/.env <<'EOF'
WP_SYNC_URL=<1Passwordから>
WP_SYNC_TOKEN=<1Passwordから>
EOF
chmod 600 ~/repos/boat/.env
```

※ 実際の値は 1Password の「boat / WordPress sync」項目を参照。
※ 会社Macの `~/repos/boat/.env` を cat して目視コピー → 1Password に改めて格納しておくと確実。

## Step 5. Python 依存関係

```bash
cd ~/repos/boat
python3 -m pip install -r requirements.txt
```

## Step 6. 初期データの取得（任意）

### 選択肢A: ゼロから積み上げる（推奨）

何もしない。launchd ジョブを自宅Mac側で有効化するか、手動で `scripts/morning_verify.py` 等を走らせれば `data/` 配下は徐々に蓄積される。

### 選択肢B: 会社Macから `data/` を丸ごと持ってくる

LAN 経由で rsync（247MB）:

```bash
# 会社Mac → 自宅Mac（例: 会社Mac側でファイル共有を有効にして）
rsync -av /Users/eisuke.yamasaki/repos/boat/data/ \
  <自宅Mac名>.local:/Users/eisuke.yamasaki/repos/boat/data/
```

または USB / AirDrop で `data/`・`output/` を転送。

## Step 7. launchd ジョブの扱い（重要）

**両方のMacで同時に有効化しない。**（WordPress 再送信が二重になる）

現在は **会社Mac** でジョブが稼働中。自宅Macでジョブを動かす必要がない場合は何もしない（ジョブ定義 `com.boat.run-pending.plist` は自宅Macの `~/Library/LaunchAgents/` にも古い定義があるかもしれないので、あれば unload）:

```bash
# 自宅Mac側で既存ジョブが居たら停止
ls ~/Library/LaunchAgents/ | grep -i boat
launchctl unload ~/Library/LaunchAgents/com.boat.run-pending.plist 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist 2>/dev/null
```

逆に自宅Macを主ホストにしたい場合は、会社Mac側で同じ `unload` を実行してから、自宅Macで `launchctl load` する。

## Step 8. 動作確認

```bash
cd ~/repos/boat
set -a; . ./.env; set +a

# 任意の会場で予測を1レース走らせる（例: 04/21 の芦屋=21）
python3 scripts/predictor.py --jcd 21 --date $(date +%Y%m%d) --output auto | tail -3
# 期待: 💾 出力ファイル: /Users/eisuke.yamasaki/repos/boat/output/...
```

## 日常の運用

- Claude Code を `~/repos/boat` で起動 → SessionStart hook が自動 `git pull --rebase`
- 作業終了 → `/sync` スラッシュコマンドで add+commit+push
- 自宅⇄会社の切り替わりタイミングでは「終了前に push」「開始時に pull」を守れば競合ゼロ
- Claude Code が Stop hook で未コミット/未pushを検出 → 警告表示

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `gh auth` が古いまま | `gh auth refresh` |
| `git push` で認証失敗 | `gh auth setup-git` を再実行 |
| `git pull` でコンフリクト | Claude Code に「コンフリクト解決して」と依頼 |
| launchd ジョブが動かない | `tail ~/Library/Logs/claude-tasks/boat-run-pending-*.log`、`BOAT_DIR` が `~/repos/boat` を指しているか確認 |
| `.env` が無いまま実行 | WordPress 同期がスキップされるだけで他は動く。`.env` 作成で復旧 |
