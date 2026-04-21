# Phase 8 — 12R早見表(.bfv-table)リデザイン

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- CSS範囲: `.bfv-table`, `.bfv-table-wrap`, `.bfv-race-link`, `.bfv-table-bets`, `.bfv-bet`, `.bfv-odds`, `.bfv-rough`
- PHP範囲: `.bfv-panel#bfv-summary` 内の `<table>`(≒ 1287行目〜)

## 前提
Phase 7 完了後、本Phaseで早見表のみを詰める。CSSのみ、HTMLは触らない。

## 現状の問題

- 7列(R / 発走 / 本線 / 対抗 / 穴 / 信頼 / 備考)で情報密度が高いが、本線/対抗/穴の中身が入れ子の `.bfv-bet` で視覚的にうるさい
- 信頼度セルが `bfv-conf-*` クラスで色違いだが、文字のみで判別しにくい
- R列リンク(.bfv-race-link)が弱く、タップ先に見えない
- 横スクロールが発生していて、モバイルでは全体俯瞰しにくい

## 変更方針

### 8a. テーブル基本レイアウト
```css
.bfv-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--bfv-radius-md);
  border: 1px solid var(--bfv-border);
  background: var(--bfv-surface);
}
.bfv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.bfv-table thead {
  background: var(--bfv-surface-2);
}
.bfv-table th {
  text-align: left;
  padding: 10px 12px;
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--bfv-ink-dim);
  font-weight: 600;
  border-bottom: 1px solid var(--bfv-border);
  white-space: nowrap;
}
.bfv-table td {
  padding: 12px;
  border-bottom: 1px solid var(--bfv-border-soft);
  vertical-align: top;
}
.bfv-table tr:last-child td { border-bottom: none; }
.bfv-table tr:hover td { background: var(--bfv-surface-2); }
```

### 8b. R列(ジャンプリンク)を前面に
```css
.bfv-race-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 32px;
  border-radius: var(--bfv-radius-sm);
  background: var(--bfv-accent-soft);
  color: var(--bfv-accent);
  font-weight: 700;
  font-size: 14px;
  text-decoration: none;
  transition: background 120ms ease;
}
.bfv-race-link:hover { background: var(--bfv-accent); color: var(--bfv-surface); }
```

### 8c. 買い目セル(.bfv-table-bets)を軽量化
表内は **小さな買い目のみ**表示し、オッズは `.bfv-odds` を一段弱く:
```css
.bfv-table-bets {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}
.bfv-table-bets .bfv-bet {
  font-size: 12px;
  font-weight: 600;
  color: var(--bfv-ink);
  background: transparent;
  padding: 0;
}
.bfv-table-bets .bfv-odds {
  font-size: 11px;
  color: var(--bfv-ink-dim);
  margin-left: 2px;
}
```

### 8d. 信頼度セル
Phase 7 と同じ `.bfv-pill is-conf-*` 風の色トークンを、セル自体には適用せず **値の右に小さなドット**で表現:
```css
.bfv-table td[data-conf] { position: relative; padding-right: 24px; font-variant-numeric: tabular-nums; font-weight: 600; }
.bfv-table td[data-conf]::after {
  content: "";
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--bfv-ink-dim);
}
.bfv-table td[data-conf="high"]::after { background: var(--bfv-ok); }
.bfv-table td[data-conf="mid"]::after  { background: var(--bfv-accent); }
.bfv-table td[data-conf="low"]::after  { background: var(--bfv-warn); }
```
そのために PHP 側の該当 `<td>` に `data-conf="..."` 属性を追加:
```php
<td data-conf="<?php echo esc_attr((string) ($race['confidence_label'] ?? 'low')); ?>">
    <?php echo esc_html((string) ($race['confidence'] ?? '')); ?>%
</td>
```
(既存の `boat_forecast_viewer_conf_class(...)` クラスは残す。data属性を追加するだけ)

### 8e. 備考(.bfv-rough)
```css
.bfv-rough {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bfv-warn-soft);
  color: var(--bfv-warn);
  font-size: 11px;
  font-weight: 600;
}
```

## 検証
- [ ] 12R分が1画面(PC幅 1200px)で横スクロール無しに収まる
- [ ] Rセルが小さなボタン状に見え、タップ先と直感的に分かる
- [ ] 買い目テキストが並列するが、表組みが視覚的に軽い
- [ ] 信頼度が小さなドット色で即判別できる
- [ ] ホバー時に行ハイライト

## コミット
```
feat(viewer): redesign 12R summary table (Phase 8)
```
