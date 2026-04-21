# Phase 11 — 選手名+枠番の表記統一・角丸トークン化

## 対象
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php`
- 影響箇所: `boat_forecast_viewer_render_waku_name()` と、それを呼ぶ全 `<td>` / `.bfv-pick` / `.bfv-pick-meta` / `.bfv-pick-name`
- 角丸トークン: `.bfv-panel` / `.bfv-pick` / `.bfv-betbox` / `.bfv-comment` / `.bfv-reason` / `.bfv-review-card` / `.bfv-badge` / `.bfv-budget-box`

## 前提
- Phase 1 で `--bfv-radius-sm/md/lg` トークンが定義済み(sm=6〜8px / md=10〜12px / lg=14〜16px を想定)
- Phase 7〜10 で詳細ページの骨格はリデザイン済み
- 本Phaseは **PHPヘルパーの拡張 + CSSの表記統一** で、HTML構造の大改造はしない

## 変更方針

### 11a. `boat_forecast_viewer_render_waku_name()` にサイズ引数を追加

**現状(170行目あたり):**
```php
function boat_forecast_viewer_render_waku_name($waku, $name, $is_female) {
    list($bg, $fg, $border) = boat_forecast_viewer_waku_colors($waku);
    $female = !empty($is_female) ? '<span class="bfv-female">♥</span>' : '';
    return sprintf(
        '<span class="bfv-waku-name-cell"><span class="bfv-waku-chip" style="background:%s;color:%s;border-color:%s;">%s</span><span class="bfv-waku-name">%s%s</span></span>',
        ...
    );
}
```

**変更後:**
```php
function boat_forecast_viewer_render_waku_name($waku, $name, $is_female, $size = 'md') {
    list($bg, $fg, $border) = boat_forecast_viewer_waku_colors($waku);
    $female = !empty($is_female) ? '<span class="bfv-female">♥</span>' : '';
    $size = in_array($size, ['sm', 'md', 'lg'], true) ? $size : 'md';
    // 氏名の空白を半角1個に正規化(全角→半角、連続→1個、前後トリム)
    $name = preg_replace('/[\x{3000}\s]+/u', ' ', (string) $name);
    $name = trim($name);
    return sprintf(
        '<span class="bfv-waku-name-cell is-%s"><span class="bfv-waku-chip" style="background:%s;color:%s;border-color:%s;">%s</span><span class="bfv-waku-name">%s%s</span></span>',
        esc_attr($size),
        esc_attr($bg),
        esc_attr($fg),
        esc_attr($border),
        esc_html((string) $waku),
        $female,
        esc_html($name)
    );
}
```

### 11b. `.bfv-waku-chip` / `.bfv-waku-name` の CSS を3サイズ対応に

**該当: 775行目あたりの `.bfv-waku-chip` ブロックを全面書き換え。**

```css
.bfv-waku-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
}
.bfv-waku-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #ccc;
  border-radius: 999px;
  font-weight: 700;
  line-height: 1;
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  box-sizing: border-box;
}
/* サイズバリアント */
.bfv-waku-name-cell.is-sm .bfv-waku-chip { width: 16px; height: 16px; font-size: 10px; }
.bfv-waku-name-cell.is-md .bfv-waku-chip { width: 20px; height: 20px; font-size: 12px; }
.bfv-waku-name-cell.is-lg .bfv-waku-chip { width: 24px; height: 24px; font-size: 13px; }

.bfv-waku-name {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.bfv-waku-name-cell.is-sm .bfv-waku-name { font-size: 12px; }
.bfv-waku-name-cell.is-md .bfv-waku-name { font-size: 14px; }
.bfv-waku-name-cell.is-lg .bfv-waku-name { font-size: 16px; }
```

**枠番1・5のボーダーを太く**(白・黄はぱっと見弱いため):
```php
// waku_colors() 内で枠1・5のborder色を濃くすでに対応済みであれば変更不要。
// 未対応なら以下に置換:
$map = [
    1 => ['#ffffff', '#222222', '#9a9a9a'],  // 既存 #c9c9c9 → #9a9a9a
    2 => ['#111111', '#ffffff', '#111111'],
    3 => ['#d73030', '#ffffff', '#d73030'],
    4 => ['#2f6fd6', '#ffffff', '#2f6fd6'],
    5 => ['#f0d44c', '#222222', '#b8960f'],  // 既存 #d3b11f → #b8960f
    6 => ['#4aa35c', '#ffffff', '#4aa35c'],
];
```

### 11c. 呼び出し箇所でサイズを指定

#### テーブル系(小さめでOK)
- 展示実データ表(1564行目あたり): `render_waku_name($exrow['waku'], $exrow['name'], false, 'sm')`
- 実データ表(後述の foreach 内): `render_waku_name($row['waku'], $row['name'], !empty($row['is_female']), 'sm')`
- コメント実データ表: `render_waku_name($cp['waku'], $cp['name'], !empty($cp['is_female']), 'sm')`

#### Pick行(主役、大きめ)
1597行目あたりの `.bfv-pick-name` 内:
```php
<div class="bfv-pick-name">
    <?php echo boat_forecast_viewer_render_waku_name($pick['waku'] ?? '', $pick['name'] ?? '', !empty($pick['is_female']), 'lg'); ?>
</div>
```

### 11d. `.bfv-pick-meta` から「号艇」テキストを削除

**現状(1601行目あたり):**
```php
<div class="bfv-pick-meta">
    <span><?php echo esc_html((string) ($pick['waku'] ?? '')); ?>号艇</span>
    <?php if (!empty($pick['grade'])) : ?>
        <?php echo boat_forecast_viewer_render_grade($pick['grade']); ?>
    <?php endif; ?>
    ...
```

**変更後:**
```php
<div class="bfv-pick-meta">
    <?php if (!empty($pick['grade'])) : ?>
        <?php echo boat_forecast_viewer_render_grade($pick['grade']); ?>
    <?php endif; ?>
    <?php if (!empty($pick['comment_label'])) : ?>
        <span>コメント <?php echo esc_html((string) $pick['comment_label']); ?></span>
    <?php endif; ?>
    ...
```
(号艇はチップで既に見えているので削除。A1/B1等のgradeは残す)

### 11e. `.bfv-pick-name` のフォントサイズ調整
```css
.bfv-pick-name {
  font-size: 16px;   /* 既存 15px → 16px */
  font-weight: 700;
  line-height: 1.3;
}
```

### 11f. 角丸を全てトークンに統一

**Phase 1 で定義済みのトークン想定(未定義なら Phase 1 に追記):**
```css
:root {
  --bfv-radius-sm: 6px;
  --bfv-radius-md: 10px;
  --bfv-radius-lg: 14px;
}
```

**以下の border-radius ハードコード値をトークンに置換:**

| セレクタ | 現状 | 置換後 |
|---|---|---|
| `.bfv-panel` | `12px` | `var(--bfv-radius-lg)` |
| `.bfv-comment` | `12px` | `var(--bfv-radius-md)` |
| `.bfv-reason` | `12px` | `var(--bfv-radius-md)` |
| `.bfv-pick` | `12px` | `var(--bfv-radius-md)` |
| `.bfv-betbox` | 未確認(Phase 7 で `var(--bfv-radius-md)` 指定済ならOK) | `var(--bfv-radius-md)` |
| `.bfv-review` | `12px` | `var(--bfv-radius-lg)` |
| `.bfv-review-card` | `16px` | `var(--bfv-radius-md)` ← **これが唯一浮いてた箇所** |
| `.bfv-budget-box` | 未確認 | `var(--bfv-radius-md)` |
| `.bfv-detail-block` | 未確認 | `var(--bfv-radius-md)` |
| `.bfv-badge` | `999px`(pill維持) | そのまま維持 |
| `.bfv-table-wrap` | 未指定 | `var(--bfv-radius-md)` |

**grepで一括確認:**
```bash
grep -n "border-radius: [0-9]" boat-forecast-viewer.php
```
→ ヒットした各行を上記ルールで置換。`999px` と `50%`(円)は維持。

### 11g. 氏名の折り返し対策(既にCSSで nowrap + ellipsis にしたが、テーブル狭幅でも効かせる)

```css
.bfv-detail-table td { max-width: 140px; }  /* 氏名セルが長くならないように */
.bfv-detail-table .bfv-waku-name-cell { max-width: 100%; }
```
(必要な列のみ調整。全体適用はやりすぎ注意)

## 検証
- [ ] 選手表・Pick行・コメント表・展示表のすべてで、**枠チップは真円**・色は枠番慣習(1白/2黒/3赤/4青/5黄/6緑)
- [ ] 氏名の空白が**どの画面でも半角1個**
- [ ] Pick行で「3号艇」の重複表示が消える(チップ「3」のみ)
- [ ] テーブル内は sm(16px)、Pick 行は lg(24px)で視覚の主従が明確
- [ ] 角丸: ボタン/pill/ドットは円、カード・パネルは `--bfv-radius-md` か `--bfv-radius-lg` のみ(8/10/12/14/16 の中間値が混在しない)
- [ ] 枠番1・5のチップが背景と溶けず、境界線でちゃんと見える

## コミット
```
feat(viewer): unify racer/waku rendering and radius tokens (Phase 11)
```
