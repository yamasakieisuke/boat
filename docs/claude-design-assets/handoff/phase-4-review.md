# Phase 4 — レビュー(review)リデザイン

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 関数: `boat_forecast_viewer_render_review`
- 影響URL: `/review/`

## 変更方針

1. ヒーローは既存の暗色維持(データビズ的なコントラストを保つ)
2. 主要KPI(的中率/回収率/参照数)を **4枚のサマリカード**で。数値はモノスペースで大きく
3. レース別テーブルは読みやすさ最優先:偶数行のゼブラを薄く、ヘッダ sticky
4. 判定バッジ(`verdict-hit` 等)はアクセシブルな色 + アイコン不要(文字だけで)
5. モバイルで **サマリカード→テーブル** の縦積みへ自然に落ちる

## 具体変更(CSSのみ)

### 4a. KPIカード
```css
.bfrv-review-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 14px;
}
.bfrv-review-card {
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.10);
    border-radius: var(--bfv-radius-md);
    padding: 14px 16px;
}
.bfrv-review-card.is-primary {
    background: rgba(255,255,255,.16);
    border-color: rgba(255,255,255,.22);
}
.bfrv-review-value {
    font-family: var(--bfv-font-mono);
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
}
@media (max-width: 640px) {
    .bfrv-review-grid { grid-template-columns: repeat(2, 1fr); }
}
```

### 4b. テーブル
```css
.bfrv-review-table th {
    position: sticky;
    top: 0;
    background: rgba(255,255,255,.14);
    z-index: 2;
}
.bfrv-review-table tr:nth-child(even) td {
    background: rgba(255,255,255,.04);
}
```

### 4c. 判定バッジ
```css
.verdict-hit { color: #6ddca6; }
.verdict-order { color: #8fb8ff; }
.verdict-box { color: #e7c478; }
.verdict-miss { color: rgba(255,255,255,.35); }
```

## 検証
- [ ] KPI数値がモノスペースで綺麗に揃う
- [ ] テーブルヘッダがスクロールでも固定
- [ ] 判定色がダーク背景上で読める(コントラスト AA)
- [ ] モバイルで 2×2 に落ちる

## コミット
```
feat(viewer): refresh review dashboard styles (Phase 4)
```
