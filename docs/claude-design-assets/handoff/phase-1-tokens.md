# Phase 1 — 共通デザイントークン(完了分の記録)

> ステータス: ✅ 適用済み。本ドキュメントは履歴のため残します。

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`

## 変更内容

### 1. 新関数の追加 — `boat_forecast_viewer_render_nav()` の直前に配置

```php
/**
 * Phase 1: Common design tokens.
 */
function boat_forecast_viewer_common_root_css() {
    return <<<'CSS'
    :root {
        --bfv-bg:          #f0eee9;
        --bfv-surface:     #ffffff;
        --bfv-surface-sub: #f6f4ef;
        --bfv-ink:         #1a1915;
        --bfv-ink-sub:     #5a5750;
        --bfv-muted:       #8a8680;
        --bfv-line:        rgba(26,25,21,0.10);
        --bfv-line-strong: rgba(26,25,21,0.18);
        --bfv-accent:      #b5542a;
        --bfv-accent-soft: #f6e6db;
        --bfv-good:        #1e7b65;
        --bfv-good-soft:   #e6f6f2;
        --bfv-warn:        #b22323;
        --bfv-warn-soft:   #fdf3f3;
        --bfv-hero-ink:    #1a1915;
        --bfv-radius-sm:   8px;
        --bfv-radius-md:   12px;
        --bfv-radius-lg:   16px;
        --bfv-shadow-xs:   0 1px 0 rgba(26,25,21,0.04);
        --bfv-shadow-sm:   0 1px 2px rgba(26,25,21,0.06), 0 1px 1px rgba(26,25,21,0.04);
        --bfv-shadow-md:   0 4px 12px rgba(26,25,21,0.06), 0 1px 2px rgba(26,25,21,0.04);
        --bfv-font-sans:   "IBM Plex Sans JP","Noto Sans JP","Hiragino Sans","Hiragino Kaku Gothic ProN","Helvetica Neue",Arial,Meiryo,sans-serif;
        --bfv-font-mono:   "IBM Plex Mono","JetBrains Mono",SFMono-Regular,Consolas,Menlo,monospace;
    }
CSS;
}
```

### 2. 3つの `<style>` 冒頭にトークンを注入

`render_single` / `render_archive` / `render_review` の `<style>` 直後に下記1行を追加。

```php
<?php echo boat_forecast_viewer_common_root_css(); ?>
```

### 3. body の置換(3画面共通)

before:
```css
background: #f5f8fa;
color: #08131a;
font-family: "Helvetica Neue", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Arial, "Noto Sans JP", Meiryo, sans-serif;
```

after:
```css
background: var(--bfv-bg);
color: var(--bfv-ink);
font-family: var(--bfv-font-sans);
```

### 4. archive ヒーローの色を暖色インクに

before: `background: #0d4f70;`
after: `background: var(--bfv-hero-ink);`

## 検証
- /race/, /race/mikuni/, 単体 forecast_day 投稿, /review/ の4画面で文字が欠けないこと
- 和文フォントが IBM Plex Sans JP になっていること(ネット環境次第でフォールバック)
- レイアウト崩れがないこと

## コミット
```
feat(viewer): introduce common design tokens (Phase 1)
```
