# Phase 3 — 予想詳細(single)リデザイン

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 関数: `boat_forecast_viewer_render_single`
- 影響URL: 個別 `forecast_day` 投稿ページ

## 変更方針

1. ヒーローを薄く・情報密度を上げる(会場・日付・更新時刻・反映フラグを1行に)
2. 「早見表(全レース一覧テーブル)」と「レースカード(12本)」の2段構成を維持しつつ、
   - 早見表 → **グリッドチップ式**(12レース分を横スクロールせず並べる)
   - レースカード → **縦リズム統一**(枠番→選手→買い目→コメントの順序を固定)
3. 買い目ボックスを「本線/穴/3連複/3連単」のラベル＋オッズを読みやすく
4. 選手行は `--bfv-accent` で◎○▲✕を強調、枠番チップは既存の色(waku_colors)を維持
5. スマホで買い目が潰れないよう、`grid-template-columns: repeat(auto-fit, minmax(140px, 1fr))`

## 具体変更(段階的に)

**Phase 3 は CSS先行、HTMLは触らない**。既存クラス名に対するスタイルだけ書き換え、構造は温存。

### 3a. ヒーロー縮小
`.bfv-hero` の `padding: 28px;` → `padding: 18px 22px;`
背景を `var(--bfv-hero-ink)` → `var(--bfv-surface)` + `border`, `color: var(--bfv-ink)` に反転させて「詳細ヘッダは明るく」。
ただし `bfv-kicker` / `bfv-title` は黒字前提なので配色修正を合わせて行う。

### 3b. 早見表テーブル
`.bfv-table` の `min-width: 640px;` 指定を外し、
`.bfv-table td` / `.bfv-table th` の padding を `10px 12px` に軽量化。
`.bfv-race-link` を `color: var(--bfv-accent); font-weight: 700` に。

### 3c. レースカード
`.bfv-card` の `padding` を `16px` に、`radius` を `var(--bfv-radius-md)` に統一。
`.bfv-bets` を `grid-template-columns: repeat(auto-fit, minmax(140px, 1fr))`。
`.bfv-betbox.is-main` を `background: var(--bfv-accent-soft); border-color: var(--bfv-accent)` に。
`.bfv-pick-mark` の色を `var(--bfv-accent)` に。

### 3d. 枠番チップ
`boat_forecast_viewer_waku_colors()` は **変更しない**(既存色は業界慣習なので維持)。
`.bfv-waku-chip` の size を `20px` に、font-size `12px`。

## 検証
- [ ] 1レースカードに買い目4種(本線/穴/3連複/3連単)が1行〜2行で並ぶ
- [ ] ◎○▲✕マークが暖色アクセントで表示
- [ ] テーブルが横スクロール無しで収まる(モバイルでは従来どおりスクロール可)
- [ ] 既存の「◎○▲✕」カラム・レビュー埋め込みが正常動作

## コミット
```
feat(viewer): refresh single forecast page styles (Phase 3)
```
