# Phase 7 — レースカード(.bfv-card)密度整理

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- CSS範囲: `.bfv-card`, `.bfv-card-head`, `.bfv-card-sub`, `.bfv-pill`, `.bfv-bets`, `.bfv-betbox`, `.bfv-bet`, `.bfv-odds`, `.bfv-comment`, `.bfv-reason-grid`, `.bfv-reason`
- 影響URL: 個別 `forecast_day` 投稿ページ(12本のレースカード)

## 前提
Phase 1〜3 のトークン化とヒーロー縮小は反映済み。本Phaseは **CSSのみ**、HTMLは触らない。

## 現状の問題

- カード1枚の情報量が多い(買い目4種 + 理由4種 + コメント + 予算 + 展示テーブル + コメント表…)
- 買い目(.bfv-bets)が4カラム固定気味で、スマホで潰れる
- .bfv-pill が種類多すぎて視覚ノイズ(信頼度 / 荒れ / 展示反映 / オッズ反映 が同格)
- .bfv-reason-grid(理由4種)がカードの下に貼り付き、区切りが弱い

## 変更方針

### 7a. カード全体の余白とリズム
```css
.bfv-card {
  padding: 18px 20px;
  border-radius: var(--bfv-radius-lg);
  border: 1px solid var(--bfv-border);
  background: var(--bfv-surface);
  display: grid;
  gap: 14px;  /* セクション間の呼吸 */
}
.bfv-card + .bfv-card { margin-top: 14px; }
```

### 7b. カードヘッダ(.bfv-card-head)
- レース番号(h3)を巨大に `font-size: 28px; font-weight: 800; line-height: 1;`
- 発走時刻・節タイプ・潮を `.bfv-card-sub` に横並び、dim text で
- 信頼度 .bfv-pill は **他のpillより太く**:
  ```css
  .bfv-pill.is-conf-high { color: var(--bfv-ok); background: var(--bfv-ok-soft); }
  .bfv-pill.is-conf-mid  { color: var(--bfv-accent); background: var(--bfv-accent-soft); }
  .bfv-pill.is-conf-low  { color: var(--bfv-warn); background: var(--bfv-warn-soft); }
  ```
- 「展示反映 / オッズ反映」pillは **dim扱い**(color: var(--bfv-ink-dim); background: transparent; border: 1px solid var(--bfv-border);)
- 「荒れ注意」pillのみ強調保持

### 7c. 買い目ボックス(.bfv-bets / .bfv-betbox)
```css
.bfv-bets {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.bfv-betbox {
  padding: 12px 14px;
  border-radius: var(--bfv-radius-md);
  border: 1px solid var(--bfv-border);
  background: var(--bfv-surface-2);
}
.bfv-betbox.is-main {
  border-color: var(--bfv-accent);
  background: var(--bfv-accent-soft);
}
.bfv-betbox strong {
  display: block;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--bfv-ink-dim);
  margin-bottom: 6px;
  text-transform: uppercase;  /* 英字ラベルでなくても微妙に効く。日本語なら外してOK */
}
.bfv-betbox.is-main strong { color: var(--bfv-accent); }
.bfv-bet {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.bfv-odds {
  font-size: 11px;
  color: var(--bfv-ink-dim);
  font-weight: 500;
}
```

### 7d. コメント・理由グリッド
- `.bfv-comment` は淡いラベル + 本文の2段構成に:
  ```css
  .bfv-comment {
    padding: 10px 12px;
    background: var(--bfv-surface-2);
    border-left: 3px solid var(--bfv-accent);
    border-radius: var(--bfv-radius-sm);
    font-size: 13px;
    color: var(--bfv-ink);
  }
  ```
- `.bfv-reason-grid` を2カラムに統一、各 `.bfv-reason` を薄いカード化:
  ```css
  .bfv-reason-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  @media (max-width: 640px) { .bfv-reason-grid { grid-template-columns: 1fr; } }
  .bfv-reason {
    padding: 10px 12px;
    background: var(--bfv-surface-2);
    border-radius: var(--bfv-radius-sm);
    font-size: 12.5px;
    line-height: 1.55;
  }
  .bfv-reason strong {
    display: block;
    font-size: 11px;
    color: var(--bfv-ink-dim);
    margin-bottom: 3px;
  }
  ```

### 7e. 信頼度pillのクラス追加(PHP側)
viewer 側で信頼度pillに `is-conf-high/mid/low` が付くよう、`.bfv-pill` の既存render部分に `boat_forecast_viewer_conf_class(...)` を付加。該当箇所:
```php
<span class="bfv-pill <?php echo esc_attr(boat_forecast_viewer_conf_class((string) ($race['confidence_label'] ?? 'low'))); ?>">
```
→
```php
<span class="bfv-pill is-conf-<?php echo esc_attr((string) ($race['confidence_label'] ?? 'low')); ?>">
```
(既存の `bfv-conf-*` クラスと衝突しないよう `is-conf-*` に寄せる)

## 検証
- [ ] 1レースカードのpadding/gapが統一され、呼吸のあるリズム
- [ ] 信頼度pillが3段階で色分けされる(高=緑 / 中=暖色 / 低=赤)
- [ ] 「展示反映」「オッズ反映」pillが主張しない
- [ ] 買い目の本線ボックスだけアクセント色で引き立つ
- [ ] 理由グリッドがデスクトップで2カラム、モバイルで1カラム

## コミット
```
feat(viewer): refine race card rhythm and confidence pills (Phase 7)
```
