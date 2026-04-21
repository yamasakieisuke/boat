# Phase 10 — 詳細ページ ヒーロー & ナビ磨き込み

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- CSS範囲: `.bfv-hero`, `.bfv-kicker`, `.bfv-title`, `.bfv-sub`, `.bfv-meta`, `.bfv-badge`, `.bfv-jump`, `.bfv-note`, `.bfv-nav`(既存ナビがあれば), `.bfv-panel`, `.bfv-panel-head`, `.bfv-info-grid`, `.bfv-info-card`

## 前提
Phase 7〜9 完了後、最後に詳細ページ全体の **印象の頭とサイド情報**を整える。CSSのみ、HTMLは触らない。

## 現状の問題
- ヒーローと本体panelのコントラストが弱く、最初の一目で「今日の○○ × ○○レース」の要点がつかみにくい
- 反映フラグ(展示/オッズ)と最終更新時刻が同じ重みで並ぶ
- サイド `.bfv-panel` の「ページ情報」が開発者向けメタ感が強い(スラッグ等)

## 変更方針

### 10a. ヒーロー
```css
.bfv-hero {
  padding: 20px 24px 22px;
  border-radius: var(--bfv-radius-lg);
  background: var(--bfv-surface);
  border: 1px solid var(--bfv-border);
  display: grid;
  gap: 10px;
}
.bfv-kicker {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--bfv-accent);
  font-weight: 600;
}
.bfv-title {
  margin: 0;
  font-size: clamp(24px, 3.2vw, 34px);
  font-weight: 800;
  line-height: 1.15;
  color: var(--bfv-ink);
}
.bfv-title span {
  display: inline-block;
  margin-left: 10px;
  font-size: 0.6em;
  color: var(--bfv-ink-dim);
  font-weight: 600;
}
.bfv-sub {
  margin: 0;
  font-size: 13px;
  color: var(--bfv-ink-dim);
  max-width: 60ch;
  line-height: 1.6;
}
.bfv-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: center;
}
```

### 10b. バッジ差別化
```css
.bfv-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: var(--bfv-ink-dim);
  border: 1px solid var(--bfv-border);
  background: var(--bfv-surface-2);
}
.bfv-badge.is-on {
  color: var(--bfv-ok);
  border-color: transparent;
  background: var(--bfv-ok-soft);
}
.bfv-badge.is-on::before {
  content: "●";
  font-size: 8px;
  line-height: 1;
}
```
→ PHP側 `boat_forecast_viewer_render_badge($flag, $label)` 実装内で、`$flag` 真の場合に class に `is-on` を付加:
```php
function boat_forecast_viewer_render_badge($on, $label) {
  $class = $on ? 'bfv-badge is-on' : 'bfv-badge';
  return '<span class="' . esc_attr($class) . '">' . esc_html($label) . '</span>';
}
```
(既存実装が2値クラスを付けていなければこの形に)

### 10c. ジャンプリンク(.bfv-jump)
```css
.bfv-jump {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--bfv-accent);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 120ms ease;
}
.bfv-jump:hover { border-color: var(--bfv-accent); }
```

### 10d. 注意書き(.bfv-note)
```css
.bfv-note {
  padding: 10px 12px;
  border-radius: var(--bfv-radius-sm);
  background: var(--bfv-warn-soft);
  color: var(--bfv-warn);
  font-size: 12.5px;
  line-height: 1.5;
}
```

### 10e. サイド情報カード(.bfv-info-grid / .bfv-info-card)
```css
.bfv-panel {
  padding: 18px 20px;
  border-radius: var(--bfv-radius-lg);
  background: var(--bfv-surface);
  border: 1px solid var(--bfv-border);
  display: grid;
  gap: 12px;
}
.bfv-panel-head h2 {
  margin: 0 0 2px;
  font-size: 14px;
  font-weight: 700;
  color: var(--bfv-ink);
}
.bfv-panel-head p {
  margin: 0;
  font-size: 12px;
  color: var(--bfv-ink-dim);
}
.bfv-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.bfv-info-card {
  padding: 10px 12px;
  border-radius: var(--bfv-radius-sm);
  background: var(--bfv-surface-2);
  display: grid;
  gap: 3px;
}
.bfv-info-card strong {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--bfv-ink-dim);
  font-weight: 600;
  text-transform: uppercase;
}
.bfv-info-card span {
  font-size: 13px;
  color: var(--bfv-ink);
  font-variant-numeric: tabular-nums;
  word-break: break-all;
}
```

### 10f. `.bfv-grid` レイアウト確認
```css
.bfv-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  margin-top: 16px;
}
@media (max-width: 960px) {
  .bfv-grid { grid-template-columns: 1fr; }
}
```

## 検証
- [ ] ヒーローが明るく、会場名と日付が最優先で読める
- [ ] 展示/オッズバッジが「反映済みは緑ドット」「未反映はグレー枠」で一目瞭然
- [ ] サイド「ページ情報」が小さなステータスカード4つで整列
- [ ] 960px未満でサイドが本体下に回る(横並び→縦積み)

## コミット
```
feat(viewer): polish single-page hero & side info (Phase 10)
```
