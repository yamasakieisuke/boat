# Phase 2 — 予想一覧(archive)リデザイン

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 関数: `boat_forecast_viewer_render_archive`(`<style>` ブロックは `<style>` 直後〜`</style>` まで)
- 影響URL: `/race/` および `/race/{venue}/`

## 変更方針

**ねらい:** 24場をひと目で比較できる「会場ダッシュボード」に寄せる。

1. ヒーローを薄く(スリム化)し、上にリストをすぐ出す
2. カードを **3〜4列グリッド** に。場名は大きく、最新予想の日付 + レビュー有無 + 枠運メタを副次的に
3. 各カード内に **直近4レースのチップリスト**(日付のみ)を横並び → クリックで該当日のページへ
4. 枠運/強調色は `--bfv-accent`(暖色ブリック)で統一
5. **既存クラス名 `bfva-*` は完全維持**。新規は接尾辞 `-v2` を付与せず、同名CSSのルールだけ差し替える

## 具体変更

### 1. `<style>` 内の既存ブロックを全面差し替え

`<?php echo boat_forecast_viewer_common_root_css(); ?>` の直後から `</style>` までを、以下で上書き。

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
    width: min(1120px, calc(100% - 28px));
    margin: 0 auto;
    padding: 28px 0 72px;
}

.bfva-hero {
    background: var(--bfv-surface);
    color: var(--bfv-ink);
    border: 1px solid var(--bfv-line);
    border-radius: var(--bfv-radius-md);
    padding: 20px 24px;
    box-shadow: var(--bfv-shadow-xs);
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}
.bfva-hero h1 {
    margin: 0;
    font-size: clamp(22px, 3.6vw, 30px);
    letter-spacing: 0.04em;
    font-feature-settings: "palt";
}
.bfva-hero p {
    display: block;
    margin: 0;
    color: var(--bfv-muted);
    font-size: 13px;
}

.bfva-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    margin-top: 18px;
}

.bfva-card {
    background: var(--bfv-surface);
    border: 1px solid var(--bfv-line);
    border-radius: var(--bfv-radius-md);
    padding: 16px 16px 14px;
    box-shadow: var(--bfv-shadow-xs);
    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.bfva-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--bfv-shadow-md);
    border-color: var(--bfv-line-strong);
}
.bfva-card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 0;
}
.bfva-card h2 {
    margin: 0;
    font-size: 22px;
    letter-spacing: 0.02em;
    font-feature-settings: "palt";
}
.bfva-card-link {
    color: var(--bfv-ink);
    text-decoration: none;
    font-weight: 700;
}
.bfva-card-link:hover { color: var(--bfv-accent); }

.bfva-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    font-size: 12px;
    color: var(--bfv-muted);
}
.bfva-card-meta strong {
    color: var(--bfv-ink);
    font-weight: 600;
}
.bfva-card-date {
    font-family: var(--bfv-font-mono);
    font-size: 12px;
    color: var(--bfv-ink-sub);
}

.bfva-card-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 2px;
}
.bfva-card-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border-radius: 999px;
    background: var(--bfv-surface-sub);
    border: 1px solid var(--bfv-line);
    font-family: var(--bfv-font-mono);
    font-size: 11px;
    color: var(--bfv-ink-sub);
    text-decoration: none;
    white-space: nowrap;
}
.bfva-card-chip:hover {
    background: var(--bfv-accent-soft);
    border-color: var(--bfv-accent);
    color: var(--bfv-accent);
}
.bfva-card-chip.has-review::after {
    content: "●";
    color: var(--bfv-accent);
    font-size: 8px;
}

.bfva-card-cta {
    margin-top: auto;
    align-self: flex-end;
    font-size: 12px;
    font-weight: 700;
    color: var(--bfv-accent);
    text-decoration: none;
}
.bfva-card-cta::after { content: " →"; }

@media (max-width: 640px) {
    .bfva-shell { width: calc(100% - 16px); padding-top: 16px; }
    .bfva-hero { padding: 16px 18px; }
    .bfva-grid { grid-template-columns: 1fr; gap: 10px; }
}
```

### 2. HTMLマークアップの調整

現行の会場カード `foreach` ループ内で、**クラス名は維持しつつ** 追加要素を挿入するイメージ。以下の構造に寄せる:

```php
<article class="bfva-card">
  <div class="bfva-card-head">
    <h2><a class="bfva-card-link" href="<?php echo esc_url($venue['latest_link']); ?>"><?php echo esc_html($venue['name']); ?></a></h2>
    <span class="bfva-card-date"><?php echo esc_html($venue['latest_date']); ?></span>
  </div>
  <div class="bfva-card-meta">
    <span>予想 <strong><?php echo (int) $venue['count']; ?></strong></span>
    <span>振り返り <strong><?php echo (int) $venue['review_count']; ?></strong></span>
  </div>
  <div class="bfva-card-list">
    <?php foreach ($venue['items'] as $item): ?>
      <a class="bfva-card-chip<?php echo $item['has_review'] ? ' has-review' : ''; ?>"
         href="<?php echo esc_url($item['link']); ?>"
         title="<?php echo esc_attr($item['title']); ?>"><?php echo esc_html($item['date']); ?></a>
    <?php endforeach; ?>
  </div>
  <a class="bfva-card-cta" href="<?php echo esc_url($venue['latest_link']); ?>">すべて見る</a>
</article>
```

> **Claude Code へのお願い**: 既存マークアップが若干異なる場合は、**同じ要素を同じクラス名で出すことを優先**し、追加要素(`bfva-card-date` / `bfva-card-meta` / `bfva-card-chip` / `bfva-card-cta`)だけ新規導入してください。

## 検証
- [ ] `/race/` が3〜4列グリッドで表示される
- [ ] 1列に落ちた場合(スマホ)でもカードが崩れない
- [ ] `has-review` チップに小さなブリック色のドットが出る
- [ ] hover で若干リフト
- [ ] フォントが IBM Plex Sans JP → Noto Sans JP にフォールバックしても崩れない

## コミット
```
feat(viewer): redesign archive page to dashboard-style card grid (Phase 2)
```
