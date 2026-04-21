# Phase 6 — レビュー(review)画面のリズム再構成

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 関数: `boat_forecast_viewer_render_review`
- 影響URL: `/web/boat/review`

## 背景と方針
現状はヒーロー(黒)+当月セクション+過去月の `<details>` 折りたたみで情報は網羅されている。
redesign に寄せるポイントは:
1. **KPI 数値をモノスペース大文字で数字を主役に** — 見出しは小さく
2. **月セクション見出しをミニマルにし、「2026年4月 当月 84件 買い目的中37.5%」を水平の情報バーに**
3. **各 `bfrv-row` を従来のカード型ではなく、左揃えのメタ行リストに** — 会場名大+日付小、メトリックチップ行、要約行、右端に「詳細」リンク
4. 背景色は `var(--bfv-bg)`、カードは `var(--bfv-surface)`、アクセントは `var(--bfv-accent)`

## 作業手順

### ① CSS 完全差し替え

`boat_forecast_viewer_render_review` の `<style>` 内、
`<?php echo boat_forecast_viewer_common_root_css(); ?>` 直後〜`</style>` 直前までを**全置換**:

```css
*, *::before, *::after { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bfv-bg);
    color: var(--bfv-ink);
    font-family: var(--bfv-font-sans);
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
a { color: inherit; }
.bfrv-shell {
    width: min(1120px, calc(100% - 24px));
    margin: 0 auto;
    padding: 20px 0 72px;
}

/* ==== HERO ==== */
.bfrv-hero {
    background: var(--bfv-hero-ink);
    color: #fff;
    border-radius: var(--bfv-radius-md);
    padding: 24px 26px 22px;
    box-shadow: var(--bfv-shadow-sm);
    margin-bottom: 18px;
}
.bfrv-kicker {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(255,255,255,.10);
    color: rgba(255,255,255,.82);
    margin-bottom: 12px;
}
.bfrv-hero h1 {
    margin: 0 0 6px;
    font-size: clamp(24px, 4.2vw, 34px);
    letter-spacing: 0.02em;
    font-feature-settings: "palt";
}
.bfrv-hero p {
    margin: 0;
    color: rgba(255,255,255,.70);
    font-size: 13px;
}

.bfrv-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 18px;
}
.bfrv-stat {
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(255,255,255,.10);
    border-radius: var(--bfv-radius-md);
    padding: 12px 14px;
    text-align: left;
    min-width: 0;
}
.bfrv-stat strong {
    display: block;
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(255,255,255,.55);
    margin-bottom: 6px;
}
.bfrv-stat span {
    font-family: var(--bfv-font-mono);
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    color: #fff;
}
@media (max-width: 640px) {
    .bfrv-stats { grid-template-columns: repeat(2, 1fr); }
    .bfrv-stat span { font-size: 22px; }
}

/* ==== NAV (既存の .bfv-gnav がここに出力される) ==== */
.bfv-gnav {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
    margin-bottom: 14px;
    padding: 6px 10px;
    background: var(--bfv-surface);
    border: 1px solid var(--bfv-line);
    border-radius: 999px;
}
.bfv-gnav-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    color: var(--bfv-ink);
    text-decoration: none;
    transition: background .15s, color .15s;
}
.bfv-gnav-link:hover { background: var(--bfv-surface-sub); }
.bfv-gnav-active { background: var(--bfv-ink) !important; color: #fff !important; }

/* ==== MONTH GROUPS ==== */
.bfrv-month-section { margin-top: 22px; }
.bfrv-month-header,
details.bfrv-month-details > summary {
    display: flex;
    align-items: baseline;
    gap: 14px;
    font-size: 14px;
    font-weight: 700;
    color: var(--bfv-ink);
    padding: 10px 2px;
    background: transparent;
    border-radius: 0;
    border-bottom: 1px solid var(--bfv-line);
    margin-bottom: 10px;
    user-select: none;
}
.bfrv-month-header > span:first-child,
details.bfrv-month-details > summary > span:first-child {
    font-size: 18px;
    letter-spacing: 0.02em;
}
.bfrv-month-header .bfrv-month-badge {
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--bfv-accent);
    color: #fff;
}
.bfrv-month-header .bfrv-month-stat,
details.bfrv-month-details .bfrv-month-stat {
    margin-left: auto;
    font-family: var(--bfv-font-mono);
    font-size: 11px;
    color: var(--bfv-muted);
    letter-spacing: 0.04em;
}

details.bfrv-month-details { margin-top: 28px; }
details.bfrv-month-details > summary {
    cursor: pointer;
    list-style: none;
}
details.bfrv-month-details > summary::-webkit-details-marker { display: none; }
details.bfrv-month-details > summary::before {
    content: "▶";
    font-size: 9px;
    color: var(--bfv-muted);
    transition: transform .2s;
    margin-right: 4px;
}
details.bfrv-month-details[open] > summary::before { transform: rotate(90deg); }
details.bfrv-month-details .bfrv-list { margin-top: 10px; }

/* ==== ROW LIST ==== */
.bfrv-list { display: grid; gap: 8px; }
.bfrv-row {
    background: var(--bfv-surface);
    border: 1px solid var(--bfv-line);
    border-radius: var(--bfv-radius-md);
    padding: 14px 16px;
    box-shadow: var(--bfv-shadow-xs);
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    align-items: center;
    transition: border-color .15s, box-shadow .15s;
}
.bfrv-row:hover {
    border-color: var(--bfv-line-strong);
    box-shadow: var(--bfv-shadow-sm);
}
.bfrv-row-title {
    margin: 0 0 6px;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.01em;
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
}
.bfrv-row-title > span {
    font-family: var(--bfv-font-mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--bfv-muted);
}
.bfrv-row-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 12px;
    color: var(--bfv-ink-sub);
}
.bfrv-pill {
    display: inline-flex;
    align-items: center;
    padding: 3px 9px;
    border-radius: 999px;
    font-family: var(--bfv-font-mono);
    font-size: 11px;
    font-weight: 600;
    background: var(--bfv-surface-sub);
    color: var(--bfv-ink-sub);
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
}
.bfrv-pill.is-good { background: var(--bfv-good-soft); color: var(--bfv-good); }
.bfrv-pill.is-mid  { background: #fcf5e3; color: #8a6420; }
.bfrv-pill.is-low  { background: var(--bfv-warn-soft); color: var(--bfv-warn); }

.bfrv-summary-lines {
    margin: 10px 0 0;
    padding-left: 16px;
    font-size: 12px;
    color: var(--bfv-muted);
    list-style: disc;
}
.bfrv-summary-lines li { margin-top: 2px; }

.bfrv-link-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 7px 14px;
    border-radius: 999px;
    background: transparent;
    border: 1px solid var(--bfv-line-strong);
    color: var(--bfv-ink);
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
    transition: background .15s, color .15s, border-color .15s;
}
.bfrv-link-btn:hover {
    background: var(--bfv-accent);
    color: #fff;
    border-color: var(--bfv-accent);
}

.bfrv-empty {
    text-align: center;
    padding: 56px 20px;
    color: var(--bfv-muted);
    font-size: 14px;
    background: var(--bfv-surface);
    border: 1px dashed var(--bfv-line-strong);
    border-radius: var(--bfv-radius-md);
}

@media (max-width: 640px) {
    .bfrv-row { grid-template-columns: 1fr; }
    .bfrv-link-btn { justify-self: start; }
}
```

### ② HTMLの2箇所だけ微調整

#### ②-a ヒーローの kicker を短く

before(`<span class="bfrv-kicker">📊 Review</span>`)を、
after:

```php
<span class="bfrv-kicker">Review · 振り返り</span>
```

絵文字を落として英+和文並記でトーンをクール寄りに。

#### ② -b `<section class="bfrv-hero">` 内の `<p>` のインラインスタイルを削除

before:
```php
<p style="margin:0;color:rgba(255,255,255,.8);font-size:14px;">振り返りデータがある開催をまとめています。</p>
```
after:
```php
<p>振り返りデータがある開催をまとめています。</p>
```

(CSSで色・サイズを定義したので inline style は不要)

### ③ 検証

- [ ] ヒーロー内KPIが4枚の**モノスペース大数字**で並ぶ(font-size 28px相当)
- [ ] 「当月」見出しが borderBottom + バッジ + 右寄せ月次統計の1行に
- [ ] 各レース行が白カードで左右レイアウト(情報左、ボタン右)
- [ ] `bfrv-pill` がモノスペース + soft色
- [ ] 「詳細を見る」が枠線ボタン → hover で暖色fill
- [ ] `<details>` の折りたたみが引き続き動作

## コミット
```
feat(viewer): restyle review page with mono KPIs and compact row list (Phase 6)
```
