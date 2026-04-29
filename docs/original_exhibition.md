# オリジナル展示タイム取得

22/24会場が「一周・まわり足・直線」のオリジナル展示タイムを公開しているが、公式 boatrace.jp には掲載されない。各会場が独自に計測・公開している。

現状は **福岡(jcd=22)のみ実装済み**。将来的に BOATCAST (boatcast.jp) で全会場一元化されたら差し替える設計。

## 福岡 公式サイトからの取得（現行実装）

- ベースURL: `https://www.boatrace-fukuoka.com/modules/yosou/tenji_info.php?day={YYYYMMDD}&race={1-12}&if=1&nowmode=1`
- 関数: `scripts/scraper.py:scrape_fukuoka_original_exhibition(date, race_no)`
- CLI: `python3 scripts/scraper.py --mode original_exhibition --jcd 22 --date YYYYMMDD --race N`
- 出力: `data/raw/{date}/22_R{nn}_original_exhibition.json`

### HTML構造（参照）

```html
<table>
  <tr>
    <th>艇番</th><th>体重</th><th>調整体重</th><th>チルト</th>
    <th>展示タイム</th>
    <th colspan="3">オリジナル展示データ</th>
    <th>展示評価</th>
  </tr>
  <tr><th class="col7">一周</th><th class="col8">まわり足</th><th class="col9">直線</th></tr>
  <tr>
    <td class="col1 imp-num1 tei">1</td>
    <td class="col3 weight">52.0</td>
    <td class="col5">0.0</td>
    <td class="col6">7.20</td>
    <td class="col7 rank_1">37.96</td>  <!-- 一周1位 -->
    <td class="col8">6.04</td>
    <td class="col9">8.27</td>
    <td class="col10 col_last">3</td>
  </tr>
</table>
```

`rank_1` / `rank_2` のCSSクラスで上位艇が明示される。

## 出力JSONスキーマ

```json
{
  "venue_code": "22",
  "date": "20250413",
  "race_no": 1,
  "source": "boatrace-fukuoka.com",
  "rows": [
    {
      "waku": 1,
      "weight": 52.0,
      "tilt": 0.0,
      "exhibition_time": 7.20,
      "lap_time": 37.96,
      "turn_time": 6.04,
      "straight_time": 8.27,
      "lap_rank": 1,
      "turn_rank": null,
      "straight_rank": null,
      "evaluation": 3
    }
  ]
}
```

## バッチ組込み

`scripts/run_race_day.py:fetch_exhibition_and_predict()` で `jcd == "22"` のときのみ展示取得後に呼び出し。Cowork `boat-race-fetcher` (4分間隔) が福岡開催日に自動実行する。SKILL.md側の改修は不要（呼び出し方は変わらない）。

## WP表示

- `scripts/publish_wordpress.py:_build_original_exhibition_section()` がJSONを読み出し payload に `original_exhibition_section` を追加
- `wordpress/boat-forecast-viewer/boat-forecast-viewer.php` の出走表ページに「オリジナル展示」セクション表示。`rank_1` の艇は背景色＋★マークで強調

## 全会場展開・BOATCAST差し替えの方針

### 22会場対応（必要になった時点で実装）

非対応: 江戸川(03)、津(09)。
部分対応: 徳山(18)直線なし／若松(20)まわり足なし／桐生(01)半周のみ。

各会場ごとに公式サイトドメイン・URL構造・HTMLセレクタが異なるため、`scrape_{slug}_original_exhibition()` を会場別に追加する形になる。共通ロジック（rank抽出・JSON保存）は `_save_original_exhibition_json()` ヘルパに切り出すと再利用しやすい。

### BOATCASTへの差し替え

2025年7月から `boatcast.jp` で全場一元化された「オリジナル展示データ」機能が稼働。レース別URL構造が確定したら以下のリファクタが推奨:

```python
ORIGINAL_EXH_PROVIDERS = {
    "boatcast": scrape_boatcast_original_exhibition,  # 新設・全場対応
    "fukuoka_official": scrape_fukuoka_original_exhibition,  # 既存・福岡のみ
}

def scrape_original_exhibition(jcd, date, race_no, provider="boatcast"):
    fn = ORIGINAL_EXH_PROVIDERS[provider]
    return fn(jcd, date, race_no) if provider == "boatcast" else fn(date, race_no)
```

`config.json` に `original_exhibition_provider: "boatcast"` を入れて切替可能にする。福岡のみ実装段階では明示的に `provider="fukuoka_official"`、BOATCAST移行後は全場一元の `"boatcast"` に変更。

JSONスキーマは現行の `rows[]` 構造のまま使えるよう、BOATCASTスクレイパーも同形式で出力する想定。

## 予想ロジックへの組み込み（未実装、Phase 2）

`predictor.py` への組込みは別タスク。設計案は次の通り:

- 新WEIGHTS: `original_exhibition_score: 0.04`（`exhibition_score` 0.06→0.04, `boat_2rate` 0.02→0 で合計1.00維持）
- タイム重み: 一周50% / まわり足30% / 直線20%（福岡book 1着率 43.5/31.8/20.9 比準拠）
- 会場別信頼度係数 `venue_characteristics.json#{jcd}.exhibition_reliability` で動的調整（福岡=1.0、自動計測会場=0.7-1.0、手動=0.5、桐生=0.3、江戸川/津=0.0）
- データ蓄積1〜3ヶ月後にWEIGHTS実測チューニング

詳細は `memory/project_boat_*` 系の会話履歴を参照。
