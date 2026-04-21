# Phase 5 — 齟齬調整: 会場一覧(archive)を redesign に寄せる

## 背景
Phase 2 は実装後に redesign HTML との齟齬があったため、**見た目を redesign 側に合わせ直す**。  
前回の指示は「方針」寄りで解釈の余地が広すぎたため、この Phase 5 からは **完全なコード断片** を貼り付ける形式にする。

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 関数: `boat_forecast_viewer_render_archive`
- 影響URL: `/web/boat/race` など

## 作業手順(Claude Code 向け)

以下の **① CSS差し替え** と **② HTML差し替え** を順に行い、最後に **③ 検証**。

---

## ① CSS 完全差し替え

`boat_forecast_viewer_render_archive` 関数内の `<style>` ブロック、つまり  
`<?php echo boat_forecast_viewer_common_root_css(); ?>` の**直後の行から `</style>` の直前まで**を、下記で**全置換**する。

```css
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

.bfva-shell {
    width: min(1120px, calc(100% - 24px));
    margin: 0 auto;
    padding: 20px 0 72px;
}

/* ===== HERO (compact, single line) ===== */
.bfva-hero {
    background: var(--bfv-surface);
    color: var(--bfv-ink);
    border: 1px solid var(--bfv-line);
    border-radius: var(--bfv-radius-md);
    padding: 14px 18px;
    box-shadow: var(--bfv-shadow-xs);
    display: flex;
    align-items: baseline;
    gap: 14px;
    margin-bottom: 14px;
}
.bfva-hero h1 {
    margin: 0;
    font-size: clamp(18px, 2.8vw, 22px);
    letter-spacing: 0.02em;
    font-feature-settings: "palt";
}
.bfva-hero p {
    display: block;
    margin: 0;
    color: var(--bfv-muted);
    font-size: 12px;
    font-family: var(--bfv-font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.bfva-hero-count {
    margin-left: auto;
    font-family: var(--bfv-font-mono);
    font-size: 12px;
    color: var(--bfv-ink-sub);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ===== GRID ===== */
.bfva-grid {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

/* ===== CARD ===== */
.bfva-card {
    background: var(--bfv-surface);
    border: 1px solid var(--bfv-line);
    border-radius: var(--bfv-radius-md);
    padding: 0;
    overflow: hidden;
    box-shadow: var(--bfv-shadow-xs);
    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
    display: flex;
    flex-direction: column;
}
.bfva-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--bfv-shadow-md);
    border-color: var(--bfv-line-strong);
}

/* card header */
.bfva-card-head {
    padding: 12px 14px 10px;
    border-bottom: 1px solid var(--bfv-line);
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 0;
}
.bfva-card-head-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
}
.bfva-card h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.005em;
}
.bfva-card-slug {
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    color: var(--bfv-muted);
}
.bfva-card-link {
    color: var(--bfv-ink);
    text-decoration: none;
}
.bfva-card-link:hover { color: var(--bfv-accent); }
.bfva-card-date {
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    color: var(--bfv-ink-sub);
    white-space: nowrap;
}

/* card meta row */
.bfva-card-meta {
    padding: 8px 14px;
    border-bottom: 1px solid var(--bfv-line);
    display: flex;
    gap: 14px;
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    color: var(--bfv-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.bfva-card-meta strong {
    color: var(--bfv-ink);
    font-weight: 600;
    font-size: 13px;
    margin-right: 4px;
    text-transform: none;
}

/* history row list (replaces the chip row) */
.bfva-card-list {
    display: flex;
    flex-direction: column;
}
.bfva-card-row {
    display: grid;
    grid-template-columns: 10px 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 8px 14px;
    color: var(--bfv-ink-sub);
    text-decoration: none;
    font-family: var(--bfv-font-mono);
    font-size: 11px;
    border-bottom: 1px solid rgba(26,25,21,0.04);
}
.bfva-card-row:last-child { border-bottom: 0; }
.bfva-card-row:hover {
    background: var(--bfv-surface-sub);
    color: var(--bfv-ink);
}
.bfva-card-row-dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--bfv-line-strong);
}
.bfva-card-row.has-review .bfva-card-row-dot {
    background: var(--bfv-accent);
}
.bfva-card-row-date {
    color: inherit;
}
.bfva-card-row-tag {
    font-size: 9px;
    color: var(--bfv-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.bfva-card-row.has-review .bfva-card-row-tag {
    color: var(--bfv-accent);
}

/* card footer (cta) */
.bfva-card-foot {
    margin-top: auto;
    padding: 8px 14px;
    background: var(--bfv-surface-sub);
    border-top: 1px solid var(--bfv-line);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.bfva-card-foot-meta {
    font-family: var(--bfv-font-mono);
    font-size: 10px;
    color: var(--bfv-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.bfva-card-cta {
    font-family: var(--bfv-font-mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--bfv-accent);
    text-decoration: none;
    letter-spacing: 0.04em;
}
.bfva-card-cta::after { content: " →"; }

@media (max-width: 640px) {
    .bfva-shell { width: calc(100% - 16px); padding-top: 14px; }
    .bfva-hero { padding: 12px 14px; }
    .bfva-grid { grid-template-columns: 1fr; gap: 8px; }
}
```

---

## ② HTML 完全差し替え

`boat_forecast_viewer_render_archive` 関数内の**ループでカードを吐いている部分**(`.bfva-grid` の中)を、以下の構造に差し替える。**対応するPHP変数名は現行のものに合わせること**(`$venue['slug']` / `$venue['name']` / `$venue['latest_date']` / `$venue['latest_link']` / `$venue['count']` / `$venue['review_count']` / `$venue['items']` — 各アイテムは `$item['date']` / `$item['link']` / `$item['title']` / `$item['has_review']`)。

### ヒーロー部の置換(既存 `.bfva-hero` ブロック全体)

```php
<header class="bfva-hero">
    <h1>会場一覧</h1>
    <p>Forecast Archive</p>
    <span class="bfva-hero-count"><?php echo count($venues); ?> venues</span>
</header>
```

### カードループの置換

既存のカードを吐いている `foreach ($venues as $venue) { ... }` ループ本体を、以下に置き換え:

```php
<div class="bfva-grid">
<?php foreach ($venues as $venue): ?>
    <article class="bfva-card">
        <div class="bfva-card-head">
            <div class="bfva-card-head-left">
                <h2><a class="bfva-card-link" href="<?php echo esc_url($venue['latest_link']); ?>"><?php echo esc_html($venue['name']); ?></a></h2>
                <span class="bfva-card-slug">/<?php echo esc_html($venue['slug']); ?></span>
            </div>
            <span class="bfva-card-date"><?php echo esc_html($venue['latest_date']); ?></span>
        </div>

        <div class="bfva-card-meta">
            <span><strong><?php echo (int) $venue['count']; ?></strong>予想</span>
            <span><strong><?php echo (int) $venue['review_count']; ?></strong>振り返り</span>
        </div>

        <div class="bfva-card-list">
            <?php foreach ($venue['items'] as $item): ?>
                <a class="bfva-card-row<?php echo !empty($item['has_review']) ? ' has-review' : ''; ?>"
                   href="<?php echo esc_url($item['link']); ?>"
                   title="<?php echo esc_attr($item['title']); ?>">
                    <span class="bfva-card-row-dot" aria-hidden="true"></span>
                    <span class="bfva-card-row-date"><?php echo esc_html($item['date']); ?></span>
                    <span class="bfva-card-row-tag"><?php echo !empty($item['has_review']) ? '振返済' : '予想のみ'; ?></span>
                </a>
            <?php endforeach; ?>
        </div>

        <div class="bfva-card-foot">
            <span class="bfva-card-foot-meta"><?php echo (int) $venue['count']; ?>R記録 · <?php echo (int) $venue['review_count']; ?>R振返済</span>
            <a class="bfva-card-cta" href="<?php echo esc_url($venue['latest_link']); ?>">詳細</a>
        </div>
    </article>
<?php endforeach; ?>
</div>
```

---

## ③ 検証(実機 `/web/boat/race` で確認)

- [ ] ヒーローが1行にスリム化され「会場一覧 / Forecast Archive / N venues」で並ぶ
- [ ] カードのヘッダに「会場名 + /slug + 最新日付」の3要素が1行で出る
- [ ] meta行に「N予想 / N振り返り」がモノスペースで出る
- [ ] 日付履歴が **チップの横並び** ではなく **行リスト**で縦に並ぶ(各行: ドット + 日付 + タグ)
- [ ] 振り返り済みの行だけドットが暖色アクセント(`--bfv-accent`)に
- [ ] フッターに「NR記録 · NR振返済」+ 右に「詳細 →」
- [ ] hover で若干リフト
- [ ] モバイル幅で 1列に落ちて崩れない

## コミット
```
refactor(viewer): rework archive cards to row-list layout (Phase 5)
```

## 備考(次Phaseへの申し送り)
- Phase 6: レビュー画面(review)の月次グループ見出しと KPI カードの密度調整
- Phase 7: 予想詳細ヘッダ(single)を 6艇グリッド + サマリ行構成へ
- いずれも本指示書同様、**完全なコード断片 + before/afterの明示**で書く
