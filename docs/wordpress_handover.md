# WordPress連携 引き継ぎメモ

## 目的
ボートレース予想システムの既存ローカルHTML出力は維持したまま、追加機能として WordPress に開催日単位の予想ページを公開する。

公開先:
- `https://ask11.jp/web/boat/`

想定URL形式:
- `/race/fukuoka-20260405/`

運用方針:
- 投稿は常に `publish`
- 下書き運用はしない
- 同一開催日は同一URLの投稿を更新し続ける
- 検索流入は避ける方針
- ローカルHTML出力は既存のまま残す

## 既存ボート側の状況

### 既存のローカル予測出力
既存システムでは Python で HTML を生成している。

主な対象:
- `boat/scripts/predictor.py`
- 出力例:
  - `/Users/eisuke.yamasaki/Library/Mobile Documents/com~apple~CloudDocs/Agent/personal-life/boat/output/福岡/20260405.html`

方針として、これは変更しない。
WordPress 連携は追加機能として分離する。

## WordPress 側で完了済みの作業

### 1. WordPress インストール
サイトURL:
- `https://ask11.jp/web/boat/`

### 2. パーマリンク設定
管理画面で `%postname%` 系へ変更済み。

結果:
- `https://ask11.jp/web/boat/%postname%/` 形式

### 3. `race` スラッグ競合確認
インストール直後のため、`race` 固定ページ等との競合なし。

### 4. Custom Post Type UI 導入
プラグイン:
- `Custom Post Type UI`

用途:
- `forecast_day` カスタム投稿タイプ作成

### 5. `forecast_day` 投稿タイプ作成済み
設定概要:
- 投稿タイプスラッグ: `forecast_day`
- 複数形ラベル: `Forecast Days`
- 単数形ラベル: `Forecast Day`

重要設定:
- 公開: `True`
- 一般公開クエリー可: `True`
- UIを表示: `True`
- REST API で表示: `True`
- アーカイブあり: `True`
- アーカイブURLスラッグ: `race`
- 階層: `False`
- リライト: `True`
- カスタムリライトスラッグ: `race`
- クエリー変数: `True`

結果:
- `Forecast Days` メニューが管理画面に表示
- テスト投稿URLが期待どおり生成される

### 6. テスト投稿作成済み
投稿URL:
- `https://ask11.jp/web/boat/race/fukuoka-20260405`

テスト投稿の基本情報:
- 投稿ID: `6`
- スラッグ: `fukuoka-20260405`
- ステータス: `publish`

## ACF 側で完了済みの作業

### 1. Advanced Custom Fields 導入
プラグイン:
- `Advanced Custom Fields`

### 2. フィールドグループ作成済み
フィールドグループは `forecast_day` 投稿タイプに紐付け済み。

ロケーション条件:
- 投稿タイプ
- 等しい
- `Forecast Day`

### 3. ACF フィールド定義
作成済みフィールド:
- `venue_code`
- `venue_slug`
- `venue_name`
- `race_date`
- `updated_at`
- `publish_stage`
- `has_exhibition`
- `has_odds`
- `status_note`
- `forecast_payload`

注意:
- 一時 `venue_slug` の name が `venue_slug_venue_slug` になっていたが、修正済み
- 現在は `venue_slug`

### 4. `publish_stage` の選択肢
設定済み:
- `morning`
- `after_exhibition`
- `after_odds`
- `final`

### 5. ACF 表示確認
`Forecast Days` 投稿編集画面で、ACF フィールドがメタボックスとして表示されることを確認済み。

### 6. ACF 保存確認
テスト値を入力し、保存後に再表示されることを確認済み。

保存確認済みの例:
- `venue_code = 22`
- `venue_slug = fukuoka`
- `venue_name = 福岡`
- `race_date = 2026-04-05`
- `updated_at = 2026-04-05 12:00`
- `publish_stage = morning`
- `has_exhibition = false`
- `has_odds = false`
- `status_note = テスト投稿`
- `forecast_payload = {"test": true}`

### 7. ACF グループ設定
フィールドグループ設定の `REST API で表示` は ON に設定済み。

## API 設計方針として確定していること

### 投稿単位
- 1投稿 = 1会場 × 1日

例:
- `福岡 2026/04/05 ボートレース予想`

### URL ルール
- `/race/fukuoka-20260405/`

### 投稿ステータス
- 常に `publish`

### 運用フロー
同一開催日投稿を更新し続ける。

例:
- 朝予測: `publish_stage = morning`
- 展示反映後: `after_exhibition`
- オッズ反映後: `after_odds`
- 最終更新: `final`

### 本文方針
本文は巨大HTMLを入れない。
最低限の案内文のみを想定。

本文の想定用途:
- 開催名
- 更新時刻
- 展示/オッズ反映状況
- 「随時更新します」のような補足

### 本体データ
`forecast_payload` を ACF の JSON文字列1本で保持する方針。

## `forecast_payload` 設計

### トップレベル必須項目
- `date`
- `venue_code`
- `venue_slug`
- `venue_name`
- `headline`
- `updated_at`
- `publish_stage`
- `has_exhibition`
- `has_odds`
- `races`

### 各レース必須項目
- `race_no`
- `start_time`
- `race_type`
- `confidence`
- `confidence_label`
- `is_rough`
- `main_bet`
- `sub_bet`
- `longshot_bet`
- `cover_bet`
- `comment`
- `has_exhibition`
- `has_odds`

### 最小JSONイメージ
```json
{
  "date": "2026-04-05",
  "venue_code": "22",
  "venue_slug": "fukuoka",
  "venue_name": "福岡",
  "headline": "福岡 2026/04/05 ボートレース予想",
  "updated_at": "2026-04-05 12:00",
  "publish_stage": "morning",
  "has_exhibition": false,
  "has_odds": false,
  "races": [
    {
      "race_no": 1,
      "start_time": "12:33",
      "race_type": "予選",
      "confidence": 78,
      "confidence_label": "mid",
      "is_rough": false,
      "main_bet": "1-2-4",
      "sub_bet": "1-2-3",
      "longshot_bet": "1-5-2",
      "cover_bet": "1-4-3",
      "comment": "1着1固定 / 相手抜け保険あり",
      "has_exhibition": false,
      "has_odds": false
    }
  ]
}
```

## REST API 調査結果

### 1. 投稿一覧取得
URL:
- `https://ask11.jp/web/boat/wp-json/wp/v2/forecast_day`
- `https://ask11.jp/web/boat/wp-json/wp/v2/forecast_day?slug=fukuoka-20260405`

結果:
- 投稿取得可能
- スラッグ検索でテスト投稿を 1件取得可能

取得例の主要部分:
- `id: 6`
- `slug: fukuoka-20260405`
- `status: publish`
- `link: https://ask11.jp/web/boat/race/fukuoka-20260405`

ただし一覧取得では:
- `acf: []`

### 2. 個別投稿取得
URL:
- `https://ask11.jp/web/boat/wp-json/wp/v2/forecast_day/6`

結果:
- `acf` に値が入って返る

取得例の主要部分:
```json
"acf": {
  "venue_code": "22",
  "venue_slug": "fukuoka",
  "venue_name": "福岡",
  "race_date": "2026-04-05",
  "updated_at": "2026-04-05 12:00",
  "publish_stage": "morning",
  "has_exhibition": false,
  "has_odds": false,
  "status_note": "テスト投稿",
  "forecast_payload": "{\"test\": true}"
}
```

### 3. この結果から確定した実装方針
- 既存投稿検索は `slug` 検索で行う
- 実データ確認/更新は個別投稿エンドポイントを使う
- ACF 更新は `acf` キーで送る前提で設計可能

想定API:
- 検索:
  - `GET /wp-json/wp/v2/forecast_day?slug=fukuoka-20260405`
- 個別取得:
  - `GET /wp-json/wp/v2/forecast_day/6`
- 新規作成:
  - `POST /wp-json/wp/v2/forecast_day`
- 更新:
  - `POST /wp-json/wp/v2/forecast_day/6`

## 投稿APIで送る想定データ

### 投稿本体
- `title`
- `slug`
- `status`
- `content`

### ACF
- `venue_code`
- `venue_slug`
- `venue_name`
- `race_date`
- `updated_at`
- `publish_stage`
- `has_exhibition`
- `has_odds`
- `status_note`
- `forecast_payload`

### 例
```json
{
  "title": "福岡 2026/04/05 ボートレース予想",
  "slug": "fukuoka-20260405",
  "status": "publish",
  "content": "<p>福岡 2026/04/05 の予想ページです。</p>",
  "acf": {
    "venue_code": "22",
    "venue_slug": "fukuoka",
    "venue_name": "福岡",
    "race_date": "2026-04-05",
    "updated_at": "2026-04-05 12:00",
    "publish_stage": "morning",
    "has_exhibition": false,
    "has_odds": false,
    "status_note": "朝時点の初期予測です",
    "forecast_payload": "{\"test\": true}"
  }
}
```

## 認証まわり ✅ 解決済み（2026-04-06）

### 結論
WP REST API の Application Password / Basic 認証は**不採用**。
代わりに `forecast-sync.php` へ `X-Boat-Token` ヘッダーで POST する独自エンドポイント方式を採用し、疎通確認済み。

### 採用した認証方式
- エンドポイント: `https://ask11.jp/web/boat/api/forecast-sync.php`
- 認証ヘッダー: `X-Boat-Token: <shared_secret>`
- サーバー側では `BOAT_SYNC_TOKEN` 環境変数と `hash_equals()` で検証

### 認証情報の保管場所
`boat/.env` に保存済み：
```
WP_SYNC_URL=https://ask11.jp/web/boat/api/forecast-sync.php
WP_SYNC_TOKEN=（.envファイルを参照）
```

### 疎通テスト結果（2026-04-06）
全5会場で `{"ok": true, "action": "updated"}` を確認：
- 福岡(22): post_id=87, https://ask11.jp/web/boat/race/fukuoka-20260406
- 蒲郡(07): post_id=83, https://ask11.jp/web/boat/race/gamagori-20260406
- 三国(10): post_id=85, https://ask11.jp/web/boat/race/mikuni-20260406
- 住之江(12): post_id=86, https://ask11.jp/web/boat/race/suminoe-20260406
- 常滑(08): post_id=84, https://ask11.jp/web/boat/race/tokoname-20260406

### 毎朝タスクへの組み込み
`boat-daily-morning-v2` の STEP 5.5 に追加済み（2026-04-06）。
各会場の predictor.py 実行後に publish_wordpress.py を呼び出す。

---

## 過去の認証トラブル履歴（参考）

WP REST API での試行は以下の理由で断念：
- `X-WP-Nonce` 方式 → `403 rest_cookie_invalid_nonce`
- Application Password (Basic認証) → `401 rest_cannot_edit`（`Authorization` ヘッダーがサーバー層でブロックされていた可能性が高い）

## 認証検証で使った代表コード

### 投稿更新試行コード
```js
const username = 'YOUR_LOGIN_USERNAME';
const appPassword = 'YOUR_NEW_APP_PASSWORD';
const basic = btoa(`${username}:${appPassword}`);

fetch('https://ask11.jp/web/boat/wp-json/wp/v2/forecast_day/6', {
  method: 'POST',
  headers: {
    'Authorization': `Basic ${basic}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    status: 'publish',
    acf: {
      updated_at: '2026-04-05 13:00',
      status_note: 'API更新テスト',
      forecast_payload: '{"test": true, "updated_by": "browser"}'
    }
  })
}).then(async r => {
  const text = await r.text();
  console.log(r.status, text);
});
```

結果:
- `401`

### 認証切り分け用に次回試すべきコード
```js
const username = 'YOUR_LOGIN_USERNAME';
const appPassword = 'YOUR_NEW_APP_PASSWORD';
const basic = btoa(`${username}:${appPassword}`);

fetch('https://ask11.jp/web/boat/wp-json/wp/v2/users/me?context=edit', {
  headers: {
    'Authorization': `Basic ${basic}`
  }
}).then(async r => {
  const text = await r.text();
  console.log(r.status, text);
});
```

判定:
- `200` なら認証成功
- `401/403` なら Application Password / Authorization ヘッダー経路の問題

## 次回最優先TODO

### 1. 認証切り分け
最優先は WordPress 側の API 認証が通るかの確認。

やること:
- Application Password を再発行
- `/wp-json/wp/v2/users/me?context=edit` に Basic 認証でアクセス
- ステータス確認

### 2. 401 の原因切り分け
もし `401` 継続なら、次を疑う:
- `Authorization` ヘッダーがサーバーで落ちている
- Application Password 認証がサーバー/環境で通らない
- `.htaccess` や Apache 側の設定不足

### 3. 認証成功後にやること
認証が通ったら:
- `forecast_day/6` への更新テスト
- `acf.updated_at`
- `acf.status_note`
- `acf.forecast_payload`
の更新確認

### 4. その後の実装
認証が通れば、Python 側で以下を実装予定:
- `publish_wordpress.py`
- `slug` で既存投稿検索
- あれば更新 / なければ新規作成
- `status=publish`
- `forecast_payload` 生成と送信

## 実装時の前提設計まとめ

### 既存ローカル処理は維持
既存:
- `boat/scripts/predictor.py`
- ローカルHTML出力

追加:
- WordPress payload 生成
- WordPress 投稿/更新

### 投稿ルール
- 1開催日1投稿
- 同じスラッグなら更新
- 常に公開
- URL固定

### 検索流入
- 検索は避ける方針
- 必要なら後で `noindex` や sitemap 除外を検討

### 表示方針
- PC: 比較しやすい一覧
- スマホ: 1Rカード中心
- ただし今は表示テンプレート未着手
- 先に API 疎通が必要

## 重要メモ
- テスト投稿IDは `6`
- `forecast_day` の個別GETでは `acf` が見える
- 一覧GETでは `acf` が空でも問題ない
- 最大の未解決事項は「Basic認証で更新APIが 401 になる」点
- ここが解消しない限り Python 実装を進めても詰まる可能性が高い

## 追加調査: `.htaccess` / 認証ヘッダー経路

### `web/boat/.htaccess`
`boat` 側の `.htaccess` は以下のように `HTTP_AUTHORIZATION` 引き継ぎ行を含んでいる。

```apache
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /web/boat/
RewriteRule ^index\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /web/boat/index.php [L]
</IfModule>
# END WordPress
```

### 親階層の `.htaccess`
親階層にも同様の引き継ぎ設定あり。

```apache
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /
RewriteRule ^index\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
```

### 追加で試した設定
以下も試したが改善なし。

```apache
SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1
```

また、以下の `RewriteCond %{HTTP:Authorization}` 版も検討したが、既存設定と近く優先度は低いと判断。

```apache
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTP:Authorization} ^(.*)
RewriteRule .* - [E=HTTP_AUTHORIZATION:%1]
</IfModule>
```

## 追加調査: `auth-check.php`

### 背景
Basic 認証ヘッダーが PHP まで届いているかを確認するため、WordPress 配下に一時確認用ファイルを設置した。

想定配置:
- `https://ask11.jp/web/boat/auth-check.php`

### 設置した内容
```php
<?php
header('Content-Type: application/json; charset=utf-8');

echo json_encode([
    'php_auth_user' => $_SERVER['PHP_AUTH_USER'] ?? null,
    'php_auth_pw' => isset($_SERVER['PHP_AUTH_PW']) ? 'set' : null,
    'http_authorization' => $_SERVER['HTTP_AUTHORIZATION'] ?? null,
    'authorization' => $_SERVER['Authorization'] ?? null,
    'request_uri' => $_SERVER['REQUEST_URI'] ?? null,
], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
```

### ブラウザ `fetch` テスト結果
共有した `Authorization: Basic ...` 付きの `fetch()` を実行しても、返り値は以下。

```json
{
  "php_auth_user": null,
  "php_auth_pw": null,
  "http_authorization": null,
  "authorization": null,
  "request_uri": "/web/boat/auth-check.php"
}
```

### この結果からの結論
- `Authorization` ヘッダーが PHP まで届いていない
- WordPress の投稿権限以前に、認証ヘッダー経路の問題がある
- `.htaccess` 単体の微修正では解決しない可能性が高い

## 追加調査: ディレクトリ構成

### FTPで判明した構成
`boat` 用の WordPress は、別の WordPress 配下に入れ子になっている。

概念的には:
- ルートに親 WordPress
- その配下 `web/`
- さらに `web/boat/` に今回の WordPress

この構成のため、
- 親 `.htaccess`
- `web/` 階層
- `web/boat/`
の影響を受けうる。

ただし、親 `.htaccess` にも `HTTP_AUTHORIZATION` 引き継ぎが入っており、それでも `auth-check.php` でヘッダーが見えないため、`.htaccess` 深掘りの優先度は下がった。

## 方針転換

### 旧方針
- WordPress REST API
- Application Password
- Basic 認証

### 旧方針の問題
- `forecast_day` の GET は動く
- しかし更新APIは `401`
- `auth-check.php` では `Authorization` ヘッダー自体が PHP に届いていない

### 新方針
REST API + Application Password は一旦見切り、WordPress 内部で更新処理を行う独自受信エンドポイント方式へ切り替える。

## 新方針: 独自受信エンドポイント方式

### 目的
- Basic Auth / Application Password に依存しない
- heteml 環境の認証経路問題を回避する
- WordPress 内部関数で `forecast_day` 投稿を作成/更新する

### 想定配置
- `web/boat/api/forecast-sync.php`

### 想定URL
- `https://ask11.jp/web/boat/api/forecast-sync.php`

### 現状
- 受信口はサーバーへ配置済み
- トークン認証で POST 更新成功確認済み
- `fukuoka-20260405` は `updated`
- `fukuoka-20260403` は `created`

### 認証方式
共有シークレット方式にする。

ヘッダー:
- `X-Boat-Token: <shared_secret>`

判定:
- 一致で処理続行
- 不一致は `403`

### HTTPメソッド
- `POST` のみ許可

### 受信JSON
```json
{
  "title": "福岡 2026/04/05 ボートレース予想",
  "slug": "fukuoka-20260405",
  "status": "publish",
  "content": "<p>福岡 2026/04/05 の予想ページです。</p>",
  "acf": {
    "venue_code": "22",
    "venue_slug": "fukuoka",
    "venue_name": "福岡",
    "race_date": "2026-04-05",
    "updated_at": "2026-04-05 12:00",
    "publish_stage": "morning",
    "has_exhibition": false,
    "has_odds": false,
    "status_note": "朝時点の初期予測です",
    "forecast_payload": "{\"test\": true}"
  }
}
```

### 必須項目
トップレベル:
- `title`
- `slug`
- `status`
- `content`
- `acf`

`acf` 内:
- `venue_code`
- `venue_slug`
- `venue_name`
- `race_date`
- `updated_at`
- `publish_stage`
- `has_exhibition`
- `has_odds`
- `status_note`
- `forecast_payload`

### WordPress 側処理の流れ
1. `X-Boat-Token` を検証
2. JSON を読む
3. 必須項目を検証
4. `wp-load.php` を読み込む
5. `slug` で `forecast_day` を検索
6. 見つかれば更新、なければ新規作成
7. ACF / post meta を更新
8. JSON レスポンスを返す

### 投稿特定方法
スラッグで統一:
- `fukuoka-20260405`

### 投稿更新ルール
- 投稿タイプ: `forecast_day`
- 投稿状態: 常に `publish`
- 同一スラッグなら更新
- URLは固定で維持

### レスポンス仕様
成功時:
```json
{
  "ok": true,
  "action": "updated",
  "post_id": 6,
  "slug": "fukuoka-20260405",
  "link": "https://ask11.jp/web/boat/race/fukuoka-20260405"
}
```

失敗時:
```json
{
  "ok": false,
  "error": "invalid_token"
}
```

### 想定HTTPステータス
- `200`: 成功
- `400`: 必須項目不足 / JSON不正
- `403`: トークン不一致
- `405`: POST以外
- `500`: WordPress更新失敗

## Python 側の新方針

### 想定スクリプト
- `boat/scripts/publish_wordpress.py`

### 役割
- 予測結果を WordPress 向け JSON に変換
- `forecast-sync.php` に POST
- 失敗してもローカルHTML出力は止めない

### 実装状況
- `publish_wordpress.py` 実装済み
- `predictor.py` に `--wp-publish` / `--wp-sync-url` / `--wp-sync-token` / `--wp-timeout` を追加済み
- `predictor.py --wp-publish` から WordPress 同期成功確認済み

### 送信先
- `https://ask11.jp/web/boat/api/forecast-sync.php`

### 認証
ヘッダー:
- `X-Boat-Token: <shared_secret>`

### タイトル生成規則
- `{venue_name} {YYYY/MM/DD} ボートレース予想`

例:
- `福岡 2026/04/05 ボートレース予想`

### スラッグ生成規則
- `{venue_slug}-{YYYYMMDD}`

例:
- `fukuoka-20260405`

### 本文生成規則
本文は最小限。

例:
```html
<p>福岡 2026/04/05 の予想ページです。</p>
<p>最終更新: 2026-04-05 12:00</p>
<p>展示: 未反映 / オッズ: 未反映</p>
<p>このページはレース進行に合わせて随時更新します。</p>
```

### `publish_stage` の運用
- `morning`
- `after_exhibition`
- `after_odds`
- `final`

### `status_note` の運用
- `morning`: `朝時点の初期予測です`
- `after_exhibition`: `展示反映済みです`
- `after_odds`: `展示・オッズ反映済みです`
- `final`: `最終更新版です`

### `forecast_payload`
開催日単位で JSON を作り、`json.dumps(..., ensure_ascii=False)` で文字列化して `acf.forecast_payload` に入れる。

## 表示レイヤー方針

### 課題
標準テーマ Twenty Twenty-Five のままだと、投稿の作成・更新は成功しても `forecast_payload` を描画しないため、意図したページ表示にならない。

### 対応方針
テーマ改修ではなく、プラグインで `forecast_day` 表示を差し替える。

### 追加したローカルファイル
- `boat/wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- `boat/wordpress/boat-forecast-viewer/single-forecast-day.php`
- `boat/wordpress/boat-forecast-viewer/archive-forecast-day.php`

### 役割
- `single forecast_day` を専用レスポンシブUIで描画
- `forecast_day` アーカイブ `/race/` をカード一覧で描画
- 表示データは `forecast_payload`（post meta）から取得

### サーバー配置先
- `wp-content/plugins/boat-forecast-viewer/`

### 有効化後の期待動作
- `https://ask11.jp/web/boat/race/fukuoka-20260405`
- `https://ask11.jp/web/boat/race/fukuoka-20260403`
- `https://ask11.jp/web/boat/race/`
が専用ビューで表示される

## TODO 更新

### 旧TODO
- Application Password を再発行
- `users/me` 認証確認
- `forecast_day/6` の更新再試行

### 新TODO
1. `boat-forecast-viewer` をサーバーへ配置して有効化する
2. 単体ページ `/race/fukuoka-20260405` と `/race/fukuoka-20260403` の見え方を確認する
3. アーカイブ `/race/` の表示確認をする
4. 必要に応じて race payload に追加項目（race_type, notes, odds state）を足す
5. 運用フローで `predictor.py --wp-publish` をどこから呼ぶか確定する

### 補足
- REST API + Application Password の調査結果は残す
- ただし今後の主経路は独自受信エンドポイント方式

---

# 2026-04-05 追加引き継ぎ

## 到達点

WordPress 連携は、単なる投稿作成ではなく以下まで実装済み。

- 予想投稿の新規作成・更新
- 専用の公開ビュー
- 会場別の一覧導線
- 当日ページと検証済みページの振り返り表示
- 過去の予測データの一括投稿

現在の主経路は以下。

- 同期受信口:
  - `https://ask11.jp/web/boat/api/forecast-sync.php`
- 同期トークン:
  - `zsCTc6ReMHAb6BAryfj2`
- ローカル同期スクリプト:
  - `boat/scripts/publish_wordpress.py`
- 表示プラグイン本体:
  - `boat/wordpress/boat-forecast-viewer/boat-forecast-viewer.php`

## 投稿・同期の実績

### 更新成功確認
- `fukuoka-20260405`
  - WordPress 投稿 `id=6`
  - 独自受信口経由で更新成功

### 新規作成成功確認
- `fukuoka-20260403`
  - WordPress 投稿 `id=24`
  - `created` で新規作成成功

### 4/5 福岡の振り返り反映
以下を実行済み。

- `fetch_results.py --date 20260405`
- `verify.py --jcd 22 --from 20260405 --to 20260405 --verbose`
- `publish_wordpress.py --jcd 22 --date 20260405 --publish ...`

結果:
- 11R 検証
- 1着率 `45.5%`
- 買い目率 `63.6%`
- 3連複率 `36.4%`
- 3連単率 `18.2%`

ローカル生成物:
- `boat/data/results_csv/20260405.csv`
- `boat/output/data/verify/verify_detail_福岡_20260405.md`
- `boat/output/data/verify/verify_detail_福岡_20260405.html`
- `boat/output/wordpress/20260405/22_payload.json`

WordPress 反映先:
- `https://ask11.jp/web/boat/race/fukuoka-20260405`

## 一括投稿の状況

12R そろった履歴 59 件を WordPress へ投入済み。

- 既存は `updated`
- 未作成は `created`

例:
- `shimonoseki-20260315`
- `fukuoka-20260315`
- `omura-20260321`
- `karatsu-20260322`
- `fukuoka-20260402`
- `fukuoka-20260403`
- `fukuoka-20260404`
- `fukuoka-20260405`

途中で古い `confidence=★★★` 形式に当たり、`publish_wordpress.py` 側で互換対応済み。

## `publish_wordpress.py` の追加実装

### 予測 payload の拡張
各レースについて WordPress 側へ以下を載せるようにした。

- `main_bets`
- `sub_bets`
- `longshot_bets`
- `cover_bets`
- `bet_reasons`
- `top_picks`
- `detailed_predictions`
- `tide_status`
- `comment`

### `top_picks`
- 6艇分まで保持
- `is_female` を含む
- `mark` は以下
  - 1位 `◎`
  - 2位 `○`
  - 3位 `▲`
  - 4位 `✕`
  - 5位以降は空白

### 女子判定
- `boat/data/players/female_players.json` を使用
- WordPress 表示では `♥` を付与

### 振り返り構造化
`review_summary` に以下を持つ。

- `summary_lines`
- `trend_lines`
- `race_table`
- `bet_history_table`

`race_table` / `bet_history_table` は `verify_detail.html` の見た目をそのまま使うのではなく、

- 保存済み予測ログ
- 保存済み買い目
- `results_csv`

から再構築するように変更済み。

これにより、表示している買い目と判定ロジックが一致する。

例:
- `買い目的中（本命① 1-2-4）`
- `買い目的中（穴 3-1-4）`
- `予測3連単一致`
- `不的中`

以前あった「表示上は外れて見えるのに ◎」という誤解は解消済み。

## `boat-forecast-viewer.php` の追加実装

### 単体ページ
`forecast_day` 単体ページに以下を表示する。

- ヒーロー
- 12R 早見表
- ページ情報カード
- 各レース詳細カード
- `実データ`
- `枠別着順実績`
- `システム計算ロジック`
- `結果振り返り`

### 一覧ページ階層
URL 構成:

- `/race/`
  - 会場ハブ
- `/race/fukuoka/`
  - 会場別開催日一覧
- `/race/fukuoka-20260405/`
  - 開催日詳細

個別記事URLは維持。

### 一覧導線
- `/race/` は会場カード表示
- `/race/fukuoka/` は福岡の開催日一覧
- 振り返りがある場合:
  - `振り返りを見る`
  - `#review` への直リンク

### 表示改善済み事項
- 枠色チップ追加
- 女子 `♥`
- A/B 級別色分け
  - `A1/A2` 赤
  - `B1/B2` 青
- `△` は `✕`
- `注` は無印
- 5位以降は空白
- `順` 列は数字なし、記号のみ
- 詳細表は順位順ではなく枠番順に並べ、印だけ付ける方式へ変更
- `score` と各寄与値は小数第2位表示

### 早見表
- 各 `R` から詳細カードへのページ内リンクあり
- `href="#race-{R}"`
- 各レースカード側に `id="race-{R}"`

### 振り返り導線
- 単体ページ上部に `振り返りへ`
- 振り返りセクションは `id="review"`
- 一覧から review 付き日付へ直接飛べる

## 現在の表示に関する未解決事項

### 1. 振り返り表のスマホ横スクロール
最重要の未解決課題。

状況:
- 他の詳細表は比較的安定
- `結果振り返り` の表だけスマホで横スクロールしづらい/効かない

対応履歴:
- `width: max-content`
- sticky 列2本
- `touch-action: pan-x`
- `overscroll-behavior-x: contain`

などを試したが、依然として不安定。

最新方針:
- 振り返り表を「他の詳細表と同じ構成」に寄せる
- `bfv-review-table` を `width:100% + min-width`
- sticky 列を廃止
- 通常の横スクロールだけに寄せる

この修正はローカルファイルには適用済みだが、**サーバー側の最新版反映確認が必要**。

### 2. 冒頭コメントのスマホ表示
ヒーロー直下の説明文がスマホで大きすぎる問題に対して、以下をローカルで修正済み。

- `bfv-sub` のフォントサイズをモバイル時だけ縮小
- 行高を増加
- `bfv-title` もモバイル時に少し縮小

こちらもサーバー反映確認が必要。

## 最新ローカル修正（未反映の可能性あり）

以下は最後にローカルの `boat-forecast-viewer.php` に入れた変更で、**最新版を FTP で再アップロードしないと live へは反映されない**。

### 反映待ちの変更
- `◎ ○ ▲ ✕` を丸背景なしの直接表示
- 無印は空白
- スマホ時のセクション幅ズレ抑制
- ヒーロー文言の日本語化
- `ページ情報` の圧縮カード化
- スマホ時の早見表簡略表示
- 早見表から各レース詳細へのリンク
- 詳細表の `順` 列を記号のみへ変更
- `score` / 寄与値の小数第2位化
- 振り返り表を通常横スクロールへ寄せる再調整
- ヒーロー説明文のスマホ縮小

### 要アップロードファイル
- ローカル:
  - `boat/wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- サーバー:
  - `wp-content/plugins/boat-forecast-viewer/boat-forecast-viewer.php`

## 実表示確認で分かっていること

### 確認済み live URL
- `https://ask11.jp/web/boat/race/`
- `https://ask11.jp/web/boat/race/fukuoka/`
- `https://ask11.jp/web/boat/race/fukuoka-20260404`
- `https://ask11.jp/web/boat/race/fukuoka-20260405`

### 表示済み内容
- 12R 早見表
- レースカード
- 実データ
- 枠別着順実績
- システム計算ロジック
- 4/4, 4/5 の振り返り
- 買い目別命中履歴

## 次回の最優先 TODO

1. 最新 `boat-forecast-viewer.php` をサーバーへ再アップロード
2. スマホで以下を再確認
   - `https://ask11.jp/web/boat/race/fukuoka-20260405`
   - 振り返り表が横スクロールできるか
   - 冒頭コメントが全文見えるか
3. 必要なら振り返り表だけをさらに簡略化
   - 列数削減
   - モバイル専用レイアウト
4. 次の見た目改善候補
   - `買い目判定` を色付きタグ化
   - `score` を数値だけでなくバー強調
   - 本線/対抗/穴/押さえボックス高さの調整

## 再開時のメモ

次回は「サーバーへ最新版プラグインを上書きした前提」で進めるのが最短。

まず確認するべきファイル:
- `boat/wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- `boat/scripts/publish_wordpress.py`

まず確認するべき live URL:
- `https://ask11.jp/web/boat/race/fukuoka-20260405`
- `https://ask11.jp/web/boat/race/fukuoka/`
- `https://ask11.jp/web/boat/race/`

---

# 2026-04-06 追加引き継ぎ

## ファビコン対応

WordPress デフォルトのファビコンではなく、ボート系の SVG ファビコンをプラグイン側で差し込む実装を追加済み。

### ローカル追加ファイル
- `boat/wordpress/boat-forecast-viewer/assets/boat-favicon.svg`

### 変更ファイル
- `boat/wordpress/boat-forecast-viewer/boat-forecast-viewer.php`

### 仕様
- 公開ページ
- 管理画面
- ログイン画面

の `head` に同じ favicon を差し込む。

### サーバー反映時に必要なもの
- `wp-content/plugins/boat-forecast-viewer/boat-forecast-viewer.php`
- `wp-content/plugins/boat-forecast-viewer/assets/boat-favicon.svg`

## サブドメイン移行トラブル

### 対象
- サブドメイン: `https://boat.ask11.jp/`
- 既存運用URL: `http://ask11.jp/web/boat`

### heteml 設定確認結果
公開フォルダは正しい。

- `boat.ask11.jp` → `/web/boat`

したがって、ドキュメントルートのズレは主因ではない。

### 問題の発生
WordPress 管理画面の一般設定で以下を `boat.ask11.jp` に変更したところ、サイトが `500 Internal Server Error` になった。

変更前に確認できた一般設定:
- `WordPress アドレス(URL)` = `http://ask11.jp/web/boat`
- `サイトアドレス(URL)` = `http://ask11.jp/web/boat`

### 見立て
原因候補として強かったのは以下。

1. 一般設定だけを `boat.ask11.jp` に変えてしまい、WordPress 側の URL 設定と `.htaccess` / 実ファイル構成が揃っていなかった
2. `/web/boat/.htaccess` が `ask11.jp/web/boat` 前提の rewrite のままだった可能性
3. `wp-config.php` に URL 強制定義がない状態で DB 設定だけ変わり、不整合になった

なお、`500` は DNS 浸透の問題ではないという判断でよい。

### 復旧方法
FTP で `/web/boat/wp-config.php` を編集し、WordPress URL を強制上書きして復旧した。

追加した定義:

```php
define('WP_HOME', 'http://ask11.jp/web/boat');
define('WP_SITEURL', 'http://ask11.jp/web/boat');
```

これにより、DB 上の `boat.ask11.jp` 設定より `wp-config.php` の値が優先され、`http://ask11.jp/web/boat/wp-admin/` に再度入れるようになった。

### 現在の状態
- 管理画面復旧済み
- 既存運用 URL は `ask11.jp/web/boat`
- `boat.ask11.jp` への移行は未完了

### サブドメイン移行の教訓
次回 `boat.ask11.jp` へ移行する場合は、一般設定だけを単独で変更しないこと。

必要なのは最低でも以下の整合。

1. `heteml` の公開フォルダ
   - `/web/boat`
2. `/web/boat/.htaccess`
   - サブドメイン直下前提の rewrite
3. `wp-config.php`
   - `WP_HOME`
   - `WP_SITEURL`
4. 管理画面の一般設定

### 想定される `.htaccess` の差分
`ask11.jp/web/boat` 運用と `boat.ask11.jp` 運用では `RewriteBase` などが変わる可能性が高い。

サブドメイン直下なら通常は以下寄り。

```apache
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /
RewriteRule ^index\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
```

ただし、実移行は未実施なので、次回は現在の `/web/boat/.htaccess` を見ながら慎重に合わせ込むこと。

### 次回サブドメイン移行時の推奨手順
1. まず `wp-config.php` に現在値の `WP_HOME / WP_SITEURL` を書いて安定化
2. `/web/boat/.htaccess` をサブドメイン用に調整
3. その後に一般設定の URL を `https://boat.ask11.jp` へ変更
4. `https://boat.ask11.jp/wp-admin/` へ入り直す
5. 問題があればすぐ `wp-config.php` を旧値へ戻す

### 重要メモ
現在復旧のために `wp-config.php` へ旧 URL の定義を入れている。
したがって、将来 `boat.ask11.jp` へ移行する際は、この定義をそのままにして一般設定だけを変えても意味がない。

移行時には `wp-config.php` の定義自体も `https://boat.ask11.jp` に合わせる必要がある。

---

## UI拡張対応ログ（2026-04-08）

### 変更対象ファイル
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`（メイン）
- `wordpress/boat-forecast-viewer/review-forecast.php`（新規作成）

### 追加・変更内容

#### 1. グローバルナビ（全ページ共通）

`boat_forecast_viewer_render_nav($active)` ヘルパー関数を追加。

表示リンク:
- 🏁 予想一覧 → `/race/`
- 📊 振り返り → `/review/`

`render_single`・`render_archive`・`render_review` の `<div class="bfv-shell">` 直後で呼び出す。

現在地に応じて `bfv-gnav-active` クラスが付与される。

#### 2. 早見表から各レースへのアンカーリンク

既存の早見表テーブルの各行 `?R` リンクは `href="#race-N"` 形式で実装済み（変更なし）。

早見表パネルに `id="bfv-summary"` を追加した（`render_single` の `.bfv-panel` 要素）。

#### 3. 各レースカードから早見表への戻りボタン

各 `.bfv-card`（`<article>`）の末尾に `.bfv-card-foot` を追加。

```html
<div class="bfv-card-foot">
    <a class="bfv-back-btn" href="#bfv-summary">↑ 早見表へ戻る</a>
</div>
```

#### 4. 振り返りサマリページ（`/review/`）

**新規URL:** `https://ask11.jp/web/boat/review/`

**rewriteルール:**
```php
add_rewrite_rule('^review/?$', 'index.php?bfv_review=1', 'top');
```

**query var:** `bfv_review`

**テンプレート:** `review-forecast.php` → `boat_forecast_viewer_render_review()` を呼び出す。

**render_review の機能:**
- `forecast_day` 全投稿から `review_summary` があるものを抽出
- ヒーローセクションに累計統計（開催数・累計レース数・累計的中数・通算的中率）を表示
- 各開催の的中率・要約行（最大3行）・詳細リンクをカードで一覧表示

#### 5. WordPress パーマリンクの再保存が必要

`/review/` の rewrite ルールを反映させるため、FTPアップロード後に一度：
- WordPress管理画面 → 設定 → パーマリンク → 「変更を保存」をクリック（flush_rewrite_rules の実行）

### 次回引き継ぎ事項

- `/review/` の見た目は今後調整可能（CSS は `render_review` 内にインライン記述）
- 振り返り統計の集計キー名（`total_races` / `hit_races` / `avg_rank`）は `review_summary` の JSON 構造に依存。Python 側（`predictor.py` や `verify.py`）のキー定義と要整合
- グローバルナビにリンクを追加する場合は `boat_forecast_viewer_render_nav()` 関数を編集するだけでよい
