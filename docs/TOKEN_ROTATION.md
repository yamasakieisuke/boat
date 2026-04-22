# WP Sync Token ローテート手順

> **作成**: 2026-04-22
> **対象**: `BOAT_SYNC_TOKEN` / `WP_SYNC_TOKEN`（同一の値を指す）
> **頻度**: 年1回ペース（推奨）、または漏洩疑いがあるとき

## Token の流れ（アーキテクチャ）

```
publish_wordpress.py      →  HTTP header: X-Boat-Token
    ↓ 読み込み元
~/repos/boat/.env (WP_SYNC_TOKEN)
─────────────────────── 送信側

─────────────────────── 受信側
/web/boat/api/forecast-sync.php  ←  resolve_expected_token() で以下の順に探索
  1. getenv('BOAT_SYNC_TOKEN')                    ← PHP環境変数（通常未設定）
  2. $_SERVER['BOAT_SYNC_TOKEN']                  ← .htaccess SetEnv 経由（heteml で効かない可能性）
  3. $_ENV['BOAT_SYNC_TOKEN']                     ← フォールバック
  4. apache_getenv('BOAT_SYNC_TOKEN')             ← フォールバック
  5. BOAT_SYNC_TOKEN 定数                         ← ★ C案: forecast-config.php で define
```

**実効ソースは 5（PHP 定数）** 。`.htaccess` / `.user.ini` は互換フォールバックとして残してあるが、普段は参照されない。

---

## 3点同期の要件

ローテート時は以下 3 箇所を **同じ値** に揃える必要がある:

| # | 場所 | 役割 | 更新方法 |
|---|---|---|---|
| 1 | `~/repos/boat/.env` の `WP_SYNC_TOKEN=` | 送信側（publish_wordpress.py） | 手動編集（ローカルのみ、gitignore） |
| 2 | `wordpress/forecast-config.php` の `define('BOAT_SYNC_TOKEN', '...')` | 受信側（forecast-sync.php から include） | git push → GitHub Actions で自動デプロイ |
| 3 | Cowork タスクの環境変数 `WP_SYNC_TOKEN`（設定している場合） | スケジュール実行時の送信側 | Cowork UI で手動更新 |

> **補足**: `wordpress/.htaccess` と `wordpress/.user.ini` のダミー値は実効しないので厳密には揃えなくてよいが、誤解防止のため揃える方が親切。

---

## ローテート手順

### 1. 新 token を生成

```bash
openssl rand -base64 24 | tr -d '/+=' | head -c 28
```

出力例: `abCdEf12GhIjKl34MnOpQr56StUv`（28文字、URLセーフ）

### 2. `wordpress/forecast-config.php` を更新

```php
// forecast-config.php
<?php
if (!defined('FORECAST_SYNC_LOADER')) { exit; }
define('BOAT_SYNC_TOKEN', '新tokenをここに');
```

### 3. `wordpress/.htaccess` と `wordpress/.user.ini` も同値に揃える（誤解防止）

```apache
# .htaccess
<Files "forecast-sync.php">
    SetEnv BOAT_SYNC_TOKEN "新tokenをここに"
</Files>
```

```ini
# .user.ini
; env[BOAT_SYNC_TOKEN] = "新tokenをここに"
```

### 4. git push → GitHub Actions 自動デプロイ

```bash
git add wordpress/forecast-config.php wordpress/.htaccess wordpress/.user.ini
git commit -m "chore(wp): rotate BOAT_SYNC_TOKEN"
git push origin main
```

`.github/workflows/deploy-wp.yml` が起動、約1〜2分で heteml `/web/boat/api/` に配布完了。

### 5. ローカル `.env` を更新

```bash
# ~/repos/boat/.env
WP_SYNC_URL=https://ask11.jp/web/boat/api/forecast-sync.php
WP_SYNC_TOKEN=新tokenをここに
```

### 6. Cowork タスク環境変数を更新（設定している場合）

Cowork UI で `boat-daily-morning-v2` と `boat-race-fetcher` の環境変数 `WP_SYNC_TOKEN` を新値に更新。

> **備考**: 現在のプロンプトは `.env` を `source` する方式なので、環境変数を Cowork 側で明示設定していない場合は 5 の `.env` 更新だけで完結する。

### 7. 疎通確認

```bash
cd ~/repos/boat
set -a; . ./.env; set +a
curl -X POST "$WP_SYNC_URL" \
  -H "X-Boat-Token: $WP_SYNC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ping":"test"}' -w "\nHTTP=%{http_code}\n"
```

**期待値**: `HTTP=400 {"ok":false,"error":"missing_field","field":"title"}`
→ 400 は token 認証通過後の validation エラー（正常）。403 が返ったらどこかがズレている。

### 8. 旧 token 削除確認

- heteml 側: `forecast-config.php` を上書きしたので旧値は消失
- ローカル: `.env` を上書きしたので旧値は消失
- 1Password に「boat / WordPress sync」エントリがあれば、**旧 token を削除 or historical 扱いに**、新 token で更新

---

## トラブルシュート

### `HTTP=403 {"ok":false,"error":"invalid_token","expected_set":true}`

サーバは token を読めているが値が送信側と不一致。`.env` と `forecast-config.php` を比較して違いを修正。

### `HTTP=403 {"ok":false,"error":"invalid_token","expected_set":false}`

**サーバが token を読めていない**。ありえるケース:

1. `forecast-config.php` がまだデプロイされていない（Actions 進行中 or 失敗）
   → GitHub Actions の workflow 結果を確認。失敗してたら手動で FileZilla 上書き
2. `forecast-config.php` の include が壊れている
   → heteml 側のファイル破損確認、`forecast-sync.php` の include_once 文がある確認

### GitHub Actions が走らない

- `wordpress/**` 配下のファイルを更新していないと workflow trigger されない
- 手動起動: GitHub UI → Actions → `Deploy WordPress files to heteml` → `Run workflow`

---

## 旧方式（参考・使っていない）

過去に試したが採用しなかった方式:

| 方式 | 内容 | 不採用理由 |
|---|---|---|
| A: `.htaccess SetEnv` のみ | Apache SetEnv で env 注入 | heteml PHP で `getenv()` に反映されない |
| B: `.user.ini env[]=` | PHP-FPM で env 注入 | heteml の PHP-FPM 設定次第で効かない |
| **C: PHP定数（採用）** | `define('BOAT_SYNC_TOKEN', ...)` | 確実、heteml 環境依存なし |

---

## 関連ファイル

- `wordpress/forecast-sync.php` — 受信エンドポイント、token 検証ロジック
- `wordpress/forecast-config.php` — token 定数の供給元（**このファイルがローテート本丸**）
- `.github/workflows/deploy-wp.yml` — FTPS 自動デプロイ workflow
- `docs/COWORK_ROLLBACK_HANDOVER.md` — Cowork 運用全体の引き継ぎ
- `scripts/publish_wordpress.py` — 送信側クライアント
