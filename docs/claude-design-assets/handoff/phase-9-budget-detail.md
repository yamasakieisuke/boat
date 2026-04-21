# Phase 9 — 予算別買い目・展示/コメント実データ表の整理

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- CSS範囲: `.bfv-budget-section`, `.bfv-budget-box`, `.bfv-budget-head`, `.bfv-budget-status`, `.bfv-budget-ok`, `.bfv-budget-ng`, `.bfv-budget-note`, `.bfv-budget-table`, `.bfv-detail-block`, `.bfv-detail-wrap`, `.bfv-detail-table`, `.sticky-name-table`, `.bfv-comment-table`, `.cmt-good`, `.cmt-bad`, `.cmt-neutral`, `.ex-best`, `.ex-good`, `.ex-slow`
- 影響URL: forecast_day single ページ(1カード内の後半ブロック)

## 前提
Phase 7・8 完了後。本Phaseは **CSSのみ** で、カード後半の「予算別買い目」「展示実データ」「コメント実データ」の3ブロックを統一リズムに揃える。

## 現状の問題
- 3ブロックともフォントサイズ・borderスタイル・配色がバラバラ
- `.bfv-budget-ok` / `.bfv-budget-ng` が原色気味で他と浮く
- 展示評価(★/▲/▼)の色指定がその場限りで、Phase 1のトークンと分離

## 変更方針

### 9a. 共通ラッパ `.bfv-detail-block`
```css
.bfv-detail-block {
  margin-top: 4px;
  padding: 14px 16px;
  border-radius: var(--bfv-radius-md);
  background: var(--bfv-surface-2);
  border: 1px solid var(--bfv-border-soft);
}
.bfv-detail-block h4 {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--bfv-ink-dim);
  font-weight: 600;
}
.bfv-detail-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--bfv-radius-sm);
  border: 1px solid var(--bfv-border-soft);
  background: var(--bfv-surface);
}
.bfv-detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.bfv-detail-table th {
  background: var(--bfv-surface-2);
  text-align: left;
  padding: 8px 10px;
  font-size: 11px;
  color: var(--bfv-ink-dim);
  font-weight: 600;
  border-bottom: 1px solid var(--bfv-border-soft);
  white-space: nowrap;
}
.bfv-detail-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--bfv-border-soft);
  font-variant-numeric: tabular-nums;
}
.bfv-detail-table tr:last-child td { border-bottom: none; }
```

### 9b. 予算別買い目
```css
.bfv-budget-section { display: grid; gap: 10px; }
.bfv-budget-section h4 {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--bfv-accent);
  font-weight: 600;
}
.bfv-budget-box {
  padding: 12px 14px;
  border-radius: var(--bfv-radius-md);
  background: var(--bfv-surface);
  border: 1px solid var(--bfv-border-soft);
}
.bfv-budget-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.bfv-budget-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.bfv-budget-ok { color: var(--bfv-ok); background: var(--bfv-ok-soft); }
.bfv-budget-ng { color: var(--bfv-warn); background: var(--bfv-warn-soft); }
.bfv-budget-note { font-size: 12px; color: var(--bfv-ink-dim); }
.bfv-budget-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.bfv-budget-table th,
.bfv-budget-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--bfv-border-soft);
  text-align: left;
  font-variant-numeric: tabular-nums;
}
.bfv-budget-table th {
  background: var(--bfv-surface-2);
  font-size: 11px;
  color: var(--bfv-ink-dim);
  font-weight: 600;
}
.bfv-budget-table tr:last-child td { border-bottom: none; }
```

### 9c. 展示実データ(評価マーク)
```css
.bfv-detail-table .ex-best { color: var(--bfv-accent); font-weight: 700; }
.bfv-detail-table .ex-good { color: var(--bfv-ok); font-weight: 600; }
.bfv-detail-table .ex-slow { color: var(--bfv-warn); font-weight: 600; }
```

### 9d. コメント実データ(判定マーク)
```css
.bfv-comment-table .cmt-good    { color: var(--bfv-ok); font-weight: 700; }
.bfv-comment-table .cmt-bad     { color: var(--bfv-warn); font-weight: 700; }
.bfv-comment-table .cmt-neutral { color: var(--bfv-ink-dim); }
.bfv-cmt-keywords {
  margin-top: 3px;
  font-size: 11px;
  color: var(--bfv-ink-dim);
}
.sticky-name-table td:first-child,
.sticky-name-table th:first-child {
  position: sticky;
  left: 0;
  background: var(--bfv-surface);
  z-index: 1;
}
.sticky-name-table th:first-child { background: var(--bfv-surface-2); }
```

## 検証
- [ ] 3ブロック(予算 / 展示 / コメント)が同じ余白リズムに揃う
- [ ] トリガミ回避バッジが小ぶりかつ色トークンで一貫
- [ ] 展示★/▲/▼、コメント▲/▼が色トークン経由で配色される
- [ ] 横スクロール時、選手名列が左固定で追従(sticky-name-table)

## コミット
```
feat(viewer): unify budget/exhibition/comment detail blocks (Phase 9)
```
