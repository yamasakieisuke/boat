# WordPress プラグイン分割計画（フェーズC / C-1・C-2）

対象: `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`（5,628行 / 234KB）
作成: 2026-08-16　ステータス: **Step 1 完了（2026-08-25）。Step 2 以降が残り**

| Step | 状態 |
|---|---|
| Step 0 基準スナップショット | ✅ |
| **Step 1 CSS外出し** | ✅ 5,643 → 2,421行 |
| **Step 2 `<head>` / `render_nav` を `inc/` へ** | ✅ 2,420 → 2,268行 |
| **Step 3 ヘルパ・データ・ルーティングを `inc/` へ** | ✅ 2,268 → 1,713行 |
| **Step 4 `render_*` を `views/` へ** | ✅ 1,713 → **85行** |
| Step 5 `<link>` 配信化（任意） | ⬜ 本題とは無関係の最適化。必要になったら |

### 完了（2026-09-05）— 5,628行の1ファイル → 最大850行

全ステップで**本番6URLがバイト一致**することを確認しながら進めた。
新ファイルが実際に配信されているかは、`inc/*.php` を直接叩いて
200(ABSPATHガードで空) か 404 かで判定した（出力が同一なので、
「まだデプロイされていない」と「デプロイされて正常」を区別する必要があった）。

  boat-forecast-viewer.php    85行   ヘッダ・define・require・activate のみ
  inc/helpers.php            351行 / inc/data.php 191行 / inc/nav.php 115行
  inc/routing.php             69行 / inc/head.php 33行
  views/single.php           850行 / player 244 / accuracy 243 / review 205 / archive 166
  assets/css/*.css         3,239行（6ファイル）

**踏んだ罠**:
- Step 1: 関数抽出に `(/\*\*.*?\*/\n)?function ...` を使い `re.S` で
  ファイル冒頭から一致、24関数を巻き込み削除。→ **行ベースで範囲を特定する**
- Step 2: player の `<title>` だけ「PHPタグ + 後続リテラル」の複合で、
  自動抽出が文字列リテラルとして誤って取り込んだ。→ 式に組み直し
- 各ステップで**関数の集合・フック数・波括弧の均衡**を検算したことで、
  いずれもコミット前に気づけた

### Step 1 の実績（2026-08-25）

- `C-1a`: `assets/css/*.css` を追加するだけのコミット。本番で6本とも HTTP 200 かつ
  ローカルとバイト一致を確認してから次へ
- `C-1b`: `common_root_css()` を `boat_forecast_viewer_css(...$names)` に置換し、
  5つの `<style>` の中身を1行の呼び出しへ
- **検証結果: 6URL すべてページ全体がバイト一致**（PHPの警告混入も無し）。
  デプロイ遅延は実測51秒（push 17:30:31 → 反映 17:31:22）

**改行の扱いが唯一の落とし穴だった。** 分割前は `<?php echo ...(); ?>` の直後の改行を
PHP が1つ食うため、common の末尾 `}` と次のセレクタが同じ行に出ていた。ヘルパを
「各ファイルの末尾改行を落として連結し、最後に改行を1つだけ出す」形にして再現した。

**踏んだ罠**: `common_root_css` の関数全体を正規表現
`(/\*\*.*?\*/\n)?function ...` で取ろうとしたところ、`re.S` により
ファイル冒頭のコメントから一致し、**24関数を巻き込んで削除**した。コミット前に
関数集合の差分チェックで気づいて `git checkout` で復旧。行ベースの特定に切り替えた。
→ **この規模のブロック抽出に `.*?` を使わないこと。関数集合の増減を必ず検算すること。**

きっかけ: 2026-08-15、参考指標カードを削除した際に削除範囲の終端検索が
インデント違いの内側 `<?php endif; ?>` にマッチし、外側の `</div>` と
`<?php endif; ?>` が孤児化して本番が parse error（commit `f7305547`）。
5,600行の中で「どのタグがどのタグと対か」が目視で追えないことが直接の原因。

---

## C-1 構造マップ

### 全体の内訳

| 領域 | 行 | 割合 |
|---|---:|---:|
| **CSS（全部インライン）** | **3,239** | **57.6%** |
| PHP + HTML テンプレート（描画5関数） | 1,688 | 30.0% |
| PHP ヘルパ・データ取得・ルーティング | 675 | 12.0% |
| WP配線（`template_include` / `activate`） | 26 | 0.4% |

**JavaScript は 1 行も無い。** `<script>` タグ 0件、`onclick=` 等のインラインハンドラも 0件。
ドロワーメニューは `<input type="checkbox">` + CSS の `:checked ~ ...` で実装されており（`common_root_css` 内 617–644行）、JS を一切使っていない。
→ **「CSS と JS の外出し」のうち、JS は対象そのものが存在しない。CSS だけが本丸。**

### 関数一覧（行番号は現在の HEAD 基準）

| 行 | 行数 | 関数 | 役割 |
|---:|---:|---|---|
| 1–14 | 14 | (プラグインヘッダ・`ABSPATH` ガード・`define`) | エントリ |
| 15–18 | 4 | `favicon_href` | |
| 19–28 | 10 | `render_favicon` + `wp_head`/`admin_head`/`login_head` 登録 | |
| 29–57 | 29 | `venue_map` | 24会場 slug→日本語名 |
| 58–68 | 11 | `add_rewrite_rules` (+`init`) | ルーティング |
| 69–79 | 11 | `query_vars` (+filter) | ルーティング |
| 80–98 | 19 | `pre_get_posts` (+action) | ルーティング |
| 99–195 | 97 | `collect_archive_items` | アーカイブ用データ集約 |
| 196–220 | 25 | `compute_global_kpi` | |
| 221–252 | 32 | `render_sparkline` | SVG生成 |
| 253–268 | 16 | `match_filter` | |
| 269–287 | 19 | `grade_class` / `render_grade` | |
| 288–354 | 67 | `waku_colors` / `render_waku_name` / `render_waku_tds` | 枠番表示 |
| 355–363 | 9 | `load_payload` | post_meta から JSON |
| 364–483 | 120 | `render_badge` / `conf_class` / `mark_for_rank` / `render_meter` / `render_exhibition_text` / `format_decimal` / `sort_rows_by_waku` / `pick_waku_stats` | 小物 |
| **484–714** | **231** | **`common_root_css`** | **CSS（heredoc、本体227行）** |
| 715–727 | 13 | `font_links` | Google Fonts の `<link>` |
| 728–833 | 106 | `render_nav` | トップバー・ドロワー・タブバーの HTML |
| **834–3501** | **2,668** | **`render_single`** | `/race/<venue>-<date>/`。うち **CSS 1,822 / PHP+HTML 846** |
| **3502–4108** | **607** | **`render_archive`** | `/race/`。うち **CSS 445 / PHP+HTML 162** |
| **4109–4586** | **478** | **`render_review`** | `/review/`。うち **CSS 277 / PHP+HTML 201** |
| 4587–4615 | 29 | `load_accuracy_data` | `data/accuracy/*.json` 読み |
| **4616–5061** | **446** | **`render_accuracy`** | `/accuracy/`。うち **CSS 207 / PHP+HTML 239** |
| 5062–5087 | 26 | `load_player_data` | `data/players/*.json` 読み |
| **5088–5603** | **516** | **`render_player`** | `/player/`。うち **CSS 276 / PHP+HTML 240** |
| 5604–5623 | 20 | `template_include` (+filter) | WP配線 |
| 5624–5629 | 6 | `activate` + `register_activation_hook` | WP配線 |

### CSS ブロックの正確な位置

`<style>`／`</style>` タグを除いた **純粋な CSS だけ** の行範囲。

| 出所 | CSS本体の行範囲 | 行数 | セレクタ接頭辞 |
|---|---|---:|---|
| `common_root_css()` heredoc | 486–712 | 227 | `.bfv-topbar` / `.bfv-drawer-*` / `.bfv-tabbar` + トークン(`--bfv-*`) |
| `render_single` の `<style>` | 855–2673 | 1,819 | `.bfv-` |
| `render_archive` の `<style>` | 3518–3959 | 442 | `.bfva-` |
| `render_review` の `<style>` | 4176–4449 | 274 | `.bfrv-` |
| `render_accuracy` の `<style>` | 4632–4835 | 204 | `.bfac-` |
| `render_player` の `<style>` | 5106–5378 | 273 | `.bfp-` |
| | **合計** | **3,239** | |

**重要な性質（分割の安全性を決める）**

1. **5つの `<style>` ブロックの中に PHP は一切無い。** 各ブロックの2行目にある
   `<?php echo boat_forecast_viewer_common_root_css(); ?>` の1行だけが例外で、
   それ以降 `</style>` まで `<?php` / `<?=` / `?>` は 0 個（機械確認済み）。
   → **切り出しに際して PHP 構文を触る必要がまったく無い。**
2. **ページごとにセレクタ接頭辞が分かれている**（`bfv-` / `bfva-` / `bfrv-` / `bfac-` / `bfp-`）。
   ページ間のセレクタ重複は最大4件（`body` / `a` / `.bfv-shell` 相当の共通部分のみ）。
   → 5枚に分けても相互汚染が起きない。
3. **共通レイヤは既に `common_root_css()` に分離済み**（デザイントークン＋ナビ chrome）。
   ただし「トークンだけ」ではなくナビの実装CSSも入っている（525行目以降）。

### 5つのページは「テーマを使わない完結HTML」

`render_*` は各々 `<!DOCTYPE html>` から `</html>` までを自前で出力する。
`get_header()` / `get_footer()` は使っていない。`<head>` の中身は5関数とも
**`<title>` の1行を除いて完全に同一**（6行）。

> **落とし穴: `wp_head()` が一度も呼ばれていない。**
> そのため `wp_enqueue_style()` は **これらのページでは動かない**。
> CSS を外出しする際は `<link rel="stylesheet">` を直接 echo するか、
> `readfile()` でインライン展開するかの二択になる（後述）。
> 同じ理由で、`render_favicon` は `wp_head` に登録されているのに
> この5ページでは発火していなかった（ファビコンが出ていない既存バグ）。
> **これは Step 2 を待たず 2026-08-25 に単独で修正済み（`530c834d`）。**
> 各 `<head>` で `boat_forecast_viewer_render_favicon()` を直接呼んでいる。

### 同ディレクトリの他 PHP ファイル（5件・全部で43行）

すべて **WP の `template_include` から読まれる薄いテンプレートスタブ**。
自前のロジックは持たず、エントリポイントで定義された `render_*` を呼ぶだけ。

| ファイル | 行 | 中身 | 対応URL |
|---|---:|---|---|
| `single-forecast-day.php` | 14 | `load_payload()` → `render_single()` | `/race/<venue>-<date>/` |
| `archive-forecast-day.php` | 8 | `global $wp_query` → `render_archive()` | `/race/`, `/race/<venue>/` |
| `review-forecast.php` | 7 | `render_review()` | `/review/` |
| `accuracy-forecast.php` | 7 | `render_accuracy()` | `/accuracy/`, `/accuracy/<YYYY-Www>/` |
| `player-forecast.php` | 7 | `render_player()` | `/player/`, `/player/<reg_no>/` |

呼び出し経路: `boat_forecast_viewer_template_include()`（5604–5623行）が
`template_include` フィルタでこれらのパスを返す → WP がテンプレートとして include。
**つまり「分割済みファイルを増やす」パターンは既にこのプラグイン内に存在しており、実績がある。**

### その他の同梱物

- `assets/boat-favicon.svg`（4KB）— CSS を置く先として `assets/css/` を作れる
- `data/accuracy/*.json`, `data/players/*.json`（計1.5MB）— `load_accuracy_data` /
  `load_player_data` が `BOAT_FORECAST_VIEWER_DIR . '/data/...'` で読む。**デプロイ必須**
- `.gitignore` は `data/*` を無視するが `!wordpress/boat-forecast-viewer/data/**` で除外済み。
  `assets/css/` と `inc/` は無視対象外（`git check-ignore` で確認済み）

---

## C-2 分割案

### 切り方の方針: 「レイヤ別 → 画面別」の2軸

```
レイヤ第1軸 : CSS を PHP から完全に外す（構文リスクゼロ・削減効果57%）
レイヤ第2軸 : PHP を「配線 / データ / 部品 / ビュー」に分ける
画面軸      : ビューは既存の5ページ境界（single/archive/review/accuracy/player）で切る
```

画面軸を選ぶ理由は、**既にページ単位で完全に独立しているから**。
CSS接頭辞が分かれ、`<style>` が分かれ、テンプレートスタブも5枚に分かれている。
自然な破断面がそこにあるので、そこで折る。機能別（例「テーブル描画」）で
横断的に切ると、5ページの微妙な差異を統合する作業が発生してリスクが上がる。

### 目標のディレクトリ構成

```
wordpress/boat-forecast-viewer/
├── boat-forecast-viewer.php        ← エントリ。~60行。ヘッダ/define/require/フック登録のみ
├── inc/
│   ├── routing.php                 ← rewrite / query_vars / pre_get_posts / template_include   (~70)
│   ├── data.php                    ← load_payload / load_accuracy_data / load_player_data
│   │                                  / collect_archive_items / compute_global_kpi            (~180)
│   ├── helpers.php                 ← venue_map / 枠色 / バッジ / メータ / 数値整形 等          (~280)
│   ├── head.php                    ← 共通 <head> 出力 + font_links + favicon + CSS読込        (~40)
│   └── nav.php                     ← render_nav                                               (~110)
├── views/
│   ├── single.php                  ← render_single 本体（CSS抜き後 ~846行）
│   ├── archive.php                 ← ~162行
│   ├── review.php                  ← ~201行
│   ├── accuracy.php                ← ~239行
│   └── player.php                  ← ~240行
├── assets/
│   ├── boat-favicon.svg
│   └── css/
│       ├── common.css   (227)   single.css  (1819)   archive.css (442)
│       └── review.css   (274)   accuracy.css (204)   player.css  (273)
├── single-forecast-day.php  ほか4枚（現状のまま変更なし）
└── data/                    （現状のまま）
```

> ⚠️ **`src/` という名前は絶対に使わないこと。**
> `deploy-wp.yml` の `exclude` に `src/**` があり、**FTPS で本番へ配られない**。
> include 先は `inc/` と `views/` にする。

### 最終形の行数

| ファイル | 行数 |
|---|---:|
| `boat-forecast-viewer.php`（エントリ） | ~60 |
| `views/single.php`（最大のPHPファイル） | ~846 |
| その他 PHP 各ファイル | 40〜280 |
| CSS 各ファイル | 204〜1,819 |

**5,628行の単一ファイル → 最大でも 846行の PHP ファイル**。
`render_single` の中で `if`/`endif` が59対、`foreach`/`endforeach` が30対あるが、
これは 846行の中に閉じるので目視で追える範囲になる。

---

### 最優先の判断: **CSS 外出しが最優先。異論なし。**

根拠（実測）:

| 観点 | 評価 |
|---|---|
| 削減量 | **3,239行 / 5,628行 = 57.6%**。これ1つで半分以上が消える |
| PHP構文リスク | **ゼロ**。`<style>` 内に PHP が1つも無いので、切り出しは「PHP の外側にある連続行をそのまま別ファイルへ移す」だけ |
| HTML構造リスク | **ゼロ**。`if`/`endif`・`div` の対応関係にまったく触れない |
| 事故の再発防止効果 | 大。今回の事故は「テンプレート部を探すのに 1,800行の CSS をスクロールで越える」構造が土台にあった |
| ロールバック容易性 | 最高。CSS ファイルが消えても parse error にならず、最悪「見た目が崩れる」だけで済む |
| 作業の機械性 | 最高。行範囲が確定済み（上表）なので、`sed -n 'A,Bp'` 相当のコピーで済む |

**JS は対象なし**（前述のとおり0行）。よって「CSS/JS 外出し」＝実質「CSS 外出し」。

### CSS の配り方: 2段構え

php バイナリが無い＝ローカルで動作確認できない以上、**まず出力バイト列を変えない方法**で
ファイルを分け、その後に配信方式を変える。

**方式A（Step 1で採用）: `readfile()` でインライン展開**

```php
// inc/head.php
function boat_forecast_viewer_css($name) {
    $p = BOAT_FORECAST_VIEWER_DIR . '/assets/css/' . $name . '.css';
    if (is_readable($p)) { readfile($p); }
}
```
```php
    <style>
<?php boat_forecast_viewer_css('common'); ?>
<?php boat_forecast_viewer_css('single'); ?>
    </style>
```

- **生成される HTML が現行とバイト単位でほぼ同一**（改行の扱いだけ要注意）
  → 検証が「デプロイ前後の HTML を diff して差分ゼロ」で済む。これが決定的に強い
- キャッシュ効率は現状のまま（今もインラインなので**悪化しない**）
- CSS ファイル欠損時は `is_readable` で握りつぶすので白画面にならない

**方式B（Step 5・任意）: `<link rel="stylesheet">` に切替**

```php
    <link rel="stylesheet" href="<?php echo esc_url(BOAT_FORECAST_VIEWER_URL . 'assets/css/common.css?v=' . filemtime(...)); ?>">
```

- ページ間で `common.css` がブラウザキャッシュされる（5ページとも別ドキュメントなので効く）
- HTML が 3,239行ぶん軽くなる
- ただし **描画ブロッキングのリクエストが増える** / **heteml 側キャッシュとの相性**（`WP_AUTO_DEPLOY.md`
  のトラブルシュートに「ファイルは上がったが反映されない」の項がある）/ **404 時に全ページ無スタイル**
  というリスクが新規に発生する
- **これは「見通しを良くする」という本題とは無関係の最適化**。Step 1〜4 が全部安定してから、
  独立した判断として実施する

---

### WordPress プラグインとしての制約と、その満たし方

| 制約 | 内容 | 対応 |
|---|---|---|
| **エントリファイル名は変更不可** | WP は `active_plugins` オプションに `boat-forecast-viewer/boat-forecast-viewer.php` という**相対パス文字列**を保存している。リネーム・移動すると**プラグインが黙って無効化**され、全ページが 404 になる | エントリファイルのパスは絶対に変えない。中身だけ空にしていく |
| **プラグインヘッダはエントリ先頭のみ有効** | `Plugin Name:` コメントが無いと WP がプラグインとして認識しない | 1–6行目はそのまま残す |
| **`register_activation_hook(__FILE__, ...)`** | `__FILE__` はエントリファイルでないと正しいキーにならない | 5624–5628行は**エントリに残す**。`inc/` に移動してはいけない |
| **`plugin_dir_url(__FILE__)`** | 同上。`BOAT_FORECAST_VIEWER_URL` の定義はエントリに残す | 12–13行の `define` はエントリ先頭のまま |
| **フック登録のタイミング** | `add_action('init', ...)` などはプラグイン読み込み時（＝`plugins_loaded` 前）に実行される必要がある | `require_once` をエントリ冒頭（define の直後）に置けば従来と同一タイミング。**`add_action` の記述位置は各 `inc/*.php` の関数定義直後のままでよい** |
| **include パスの解決** | 相対 include は cwd 依存で壊れる | 既にある `BOAT_FORECAST_VIEWER_DIR`（= `__DIR__`）を使う。`plugin_dir_path(__FILE__)` でも同義 |
| **リライトルールの再フラッシュ** | ルーティングのコードを `inc/routing.php` に移すだけならルール自体は不変なので**フラッシュ不要** | 万一 `/review/` 等が 404 になったら、管理画面 → 設定 → パーマリンク設定 → 「変更を保存」で手動フラッシュ（プラグイン再有効化でも可） |
| **`wp_head()` が無い** | `wp_enqueue_style` が効かない（前述） | `<link>` / `readfile()` を直接出力する。**`wp_head()` を追加するのは避ける** — テーマや他プラグインの出力が混入して見た目が変わるリスクがある |
| **デプロイ除外 `src/**`** | `src/` 配下は本番へ行かない | `inc/` `views/` `assets/css/` を使う |
| **`php -l` の対象** | `deploy-wp.yml` の lint は `find wordpress -name '*.php'` なので新規 `inc/*.php` `views/*.php` も自動で対象になる | 追加設定不要 |

#### require の置き方（`views/` は遅延 require にする）

```php
// boat-forecast-viewer.php （抜粋・イメージ）
define('BOAT_FORECAST_VIEWER_DIR', __DIR__);
define('BOAT_FORECAST_VIEWER_URL', plugin_dir_url(__FILE__));

require_once __DIR__ . '/inc/helpers.php';
require_once __DIR__ . '/inc/data.php';
require_once __DIR__ . '/inc/head.php';
require_once __DIR__ . '/inc/nav.php';
require_once __DIR__ . '/inc/routing.php';

function boat_forecast_viewer_render_single($payload, $post) {
    require __DIR__ . '/views/single.php';   // ← 遅延。呼ばれた時に初めて読む
}
```

**なぜ views だけ遅延 require か（重要）**

PHP の parse error は「そのファイルを require した瞬間」に fatal になる。

- エントリ冒頭で全部 `require_once` する設計だと、`views/single.php` を壊した瞬間に
  **全ページ + `/wp-admin/` まで白画面**になる（プラグインは毎リクエストでロードされるため）。
  こうなると管理画面からプラグインを無効化することすらできず、復旧は FTP 経由しかない
- ビューを遅延 require にすれば、`views/single.php` の parse error は
  **`/race/<venue>-<date>/` だけ**を落とす。`/review/` も管理画面も生きているので、
  管理画面からプラグイン無効化 → git revert という通常の手順で戻せる

この「爆発半径の縮小」が、分割のもう一つの実利。

---

### ステップと、各ステップのリスク・検証方法

php バイナリが無い前提なので、**全ステップで「本番のHTMLを取って差分を見る」を検証の主軸**にする。
GitHub Actions の `php -l` は既に deploy の `needs:` になっているので、
parse error は本番に届かない（deploy ジョブがスキップされる）ことは担保済み。
残るリスクは「構文は通るが出力が変わる」なので、そこを HTML diff で押さえる。

#### Step 0（着手前・必須）: 基準スナップショットを取る

```bash
mkdir -p /tmp/bfv-baseline && cd /tmp/bfv-baseline
B=https://ask11.jp/web/boat
curl -sS "$B/race/"                  -o archive.html
curl -sS "$B/race/fukuoka/"          -o archive_venue.html
curl -sS "$B/review/"                -o review.html
curl -sS "$B/accuracy/"              -o accuracy.html
curl -sS "$B/player/"                -o player.html
# single は /race/ の HTML から実在する記事URLを1本拾って取る
curl -sS "$B/race/<実在するslug>/"   -o single.html
wc -c *.html
```

以後、各ステップのデプロイ完了後に同じ URL を取り直して `diff` する。
**Step 1〜4 は「出力が変わらないこと」が目標**なので、diff は空になるのが正解。

#### Step 1: CSS を6ファイルへ外出し（`readfile()` 方式）

*内容*: 上表の行範囲をそのまま `assets/css/*.css` へコピーし、
`<style>` 内を `<?php boat_forecast_viewer_css('...'); ?>` に置換。
`common_root_css()` は `readfile` に置き換える（関数名は残す＝呼び出し側を触らない）。

*これを 2 コミットに割る*:
- **1-a**: `assets/css/*.css` を**追加するだけ**（PHP は一切触らない）。
  デプロイしても出力は完全に不変。
  検証: `curl -sSI https://ask11.jp/web/boat/wp-content/plugins/boat-forecast-viewer/assets/css/single.css`
  が 200 かつ Content-Length が期待値であることを6本すべてで確認
- **1-b**: PHP 側を `readfile()` に切替。
  検証: 6URL の HTML を再取得して baseline と `diff`。空 or 改行1個の差ならOK

*リスク*: 低。
- 最悪ケース: CSS ファイルの取りこぼし → その画面だけ無スタイル（parse error にはならない）
- 1-a を先に完了させて 200 を確認済みなので、この最悪ケースはほぼ潰れている
- CSS の切り出し行を1行ずれて取ると `}` が欠けて以降のスタイルが崩れる
  → **`assets/css/*.css` の合計行数が 3,239 になることを機械的に検算**する

*削減後*: `boat-forecast-viewer.php` は **5,628 → 2,389行**

#### Step 2: `<head>` と `render_nav` を `inc/` へ

*内容*: 5関数で完全に同一の `<head>` 6行を `boat_forecast_viewer_head_open($title, $css)` に集約し、
`inc/head.php` へ。`render_nav`（728–833）を `inc/nav.php` へそのまま移動。
ここで **`render_favicon()` を head に呼び足してファビコン欠落バグも直す**（出力は増えるが意図的）。

*リスク*: 低〜中。5ページの `<head>` は「`<title>` 以外同一」を機械確認済みなので統合可能。
*検証*: HTML diff。差分は `<title>` 行と、追加した3本の favicon `<link>` のみ、が正解。

#### Step 3: ヘルパ・データ・ルーティングを `inc/` へ

*内容*: 15–483行と `load_*` 群を `inc/helpers.php` / `inc/data.php` / `inc/routing.php` へ移動。
**移動のみ。関数の中身は1文字も変えない。** `add_action` / `add_filter` は関数の直後に付いてくる。

*リスク*: 低。ただし**移動漏れ = 関数未定義 = fatal error** なので、
移動前後で「定義されている関数名の集合」が一致することを検算する:
```bash
grep -ho '^function [a-z_]*' boat-forecast-viewer.php inc/*.php views/*.php | sort > after.txt
# before.txt と diff して空なら OK
```
*検証*: HTML diff（差分ゼロが正解）。加えて `/accuracy/2026-W33/` と `/player/<reg_no>/` の
サブルートも叩いて 200 を確認（`data/` 読み込みが生きているか）。

#### Step 4: 5つの `render_*` を `views/` へ（遅延 require）

*内容*: 一度に全部やらず、**小さい順に1画面ずつ、1コミット1画面**で移す。
`accuracy`(239行) → `player`(240) → `archive`(162) → `review`(201) → `single`(846)。
`render_single` は最後。移動時に本体は書き換えない（`return` の有無だけ注意）。

*リスク*: 中（ここが一番危ない）。
- 関数の**スコープ**が変わる: `require` された側でも呼び出し元関数のローカル変数は見えるが、
  `global` を暗黙に期待している箇所があると壊れる。`render_archive($query)` は引数で受けているのでOK、
  `render_single($payload, $post)` も引数。**確認済み: 5関数とも必要なデータは引数か関数呼び出しで取得しており、暗黙のグローバル依存は無い**
- `single` は 846行なので、切り出し時の先頭/末尾1行ズレに注意（`function` 行と閉じ `}` を落とす／残す）

*検証*: 1画面ごとにデプロイ → 該当URLの HTML diff（差分ゼロ）→ 次へ。
`render_single` のコミットの前に、**`views/single.php` の `if`/`endif`・`foreach`/`endforeach` の
対応数を数えるスクリプトを回す**（php が無いのでこれが唯一のローカル事前チェック）:
```bash
python3 - <<'EOF'
import re,sys
s=open('wordpress/boat-forecast-viewer/views/single.php',encoding='utf-8').read()
for a,b in [('if\\s*\\(','endif'),('foreach\\s*\\(','endforeach'),('<\\?php','\\?>')]:
    print(a, len(re.findall(a,s)), '/', b, len(re.findall(b,s)))
EOF
```
（`if` は `{}` 形式も混ざるため厳密一致はしない。**移動の前後で数が変わらないこと**を見る。）

#### Step 5（任意・別判断）: `readfile()` → `<link>` 配信

Step 1〜4 が安定してから、独立した最適化として検討。前述のとおり本題とは無関係。

---

### 事前に整えておくと安全な足回り（任意だが推奨）

現状 `deploy-wp.yml` の `php -l` は **`push: branches:[main]`** でしか動かない。
本番は守られるが「main に壊れたコミットが載る」状態にはなる。
分割作業中は**ブランチ + PR**で進め、PR 時点で lint が回るようにしておくと手戻りが減る。

```yaml
# .github/workflows/wp-lint.yml （新規・deploy-wp.yml は触らない）
on:
  pull_request:
    paths: ['wordpress/**']
  workflow_dispatch:
```
中身は `deploy-wp.yml` の lint ジョブと同一。
（`deploy-wp.yml` に `pull_request` を足すのは NG — deploy ジョブの `if:` 条件が
`github.event_name != 'workflow_run'` なので PR でも本番デプロイが走ってしまう。）

---

### ロールバック手順

**レベル1: 通常（HTML diff で異常を検知した場合）**

```bash
git revert <bad-sha> && git push
```
→ `deploy-wp.yml` が再走し、FTPS が前の内容を再同期する。所要 1〜2分。
これが基本形。ステップを小さく刻む最大の理由は「revert 1個で確実に戻せる」状態を保つこと。

**レベル2: 画面が1つだけ落ちた（views の parse error など）**

Step 4 で views を**遅延 require** にしていれば管理画面は生きている。
- 管理画面 → プラグイン → Boat Forecast Viewer を**停止**（サイト全体が素のテーマ表示に戻る）
- 落ち着いて revert → push → デプロイ完了後に**再度有効化**
- 有効化で `boat_forecast_viewer_activate()` が走り `flush_rewrite_rules()` されるので、
  `/review/` `/accuracy/` `/player/` のルートも復活する

**レベル3: 全ページ + 管理画面が白画面（エントリファイルの parse error）**

`deploy-wp.yml` の lint がある限り理論上ここには来ないが、来た場合:
- heteml の FTP（`ftp-ask.heteml.net` / `ask_wp` / パスワードは GitHub Secrets `HETEML_FTP_PASSWORD` と同じ値）で
  `/web/boat/wp-content/plugins/boat-forecast-viewer/` に接続
- **ディレクトリ名を `boat-forecast-viewer.disabled` にリネーム** → WP がプラグインを見失って自動的に無効化状態になり、管理画面が復活する
- ローカルで revert → push → デプロイ完了を確認 → ディレクトリ名を戻す → 管理画面で再有効化
- ※ FTP クライアントが手元に無い場合、heteml のコントロールパネルのファイルマネージャでも同じ操作ができる

**共通の前提**: 作業前に必ず `git log --oneline -1 -- wordpress/` で「戻る先」を控えておく。
現時点の安全な既知良好コミットは **`d954a07a`**。

---

## 推奨する実施順（サマリ）

| # | 内容 | PHP行数 | リスク | 検証 |
|---|---|---:|---|---|
| 0 | 本番HTMLの基準スナップショット取得 | 5,628 | — | — |
| 1a | `assets/css/*.css` 6本を追加のみ | 5,628 | 極小 | CSS の 200 と Content-Length |
| 1b | `<style>` 内を `readfile()` に置換 | **2,389** | 小 | HTML diff = 空 |
| 2 | `<head>` / `nav` を `inc/` へ | ~2,250 | 小 | HTML diff = title + favicon のみ |
| 3 | helpers / data / routing を `inc/` へ | ~1,700 | 小 | 関数名集合の一致 + HTML diff = 空 |
| 4 | views を1画面ずつ `views/` へ（5コミット） | **~60** | 中 | 画面ごとに HTML diff = 空 |
| 5 | （任意）`<link>` 配信へ | ~60 | 中 | 別判断 |

Step 1 だけで **57.6% が消え、事故の温床だった「1,800行のCSSを越えないとテンプレートに辿り着けない」構造がなくなる**。
まずここまでを1セットとして実施し、効果を見てから Step 2 以降を判断するのが妥当。
