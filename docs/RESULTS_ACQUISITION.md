# 結果取得ロジック

この文書は、`boat` プロジェクトで `results_csv/{date}.csv` をどう埋めるかを、他の作業エージェントが短時間で追えるように整理したものです。

## 全体方針

結果取得は 2 段構成ですが、通常運用では `fetch_results.py` から補完まで自動で流れます。

1. 標準経路: `scripts/fetch_results.py`
2. 補完経路: `scripts/fetch_results_official.py`

verify は最終的に `data/results_csv/{date}.csv` を読むため、LZH と公式結果ページのどちらから取得しても、最終 CSV が揃えば動きます。

## 標準経路 `scripts/fetch_results.py`

### 役割

公式 LZH 日次成績を取得し、固定長テキストを日別 CSV に変換します。

### 入力元

- `https://www1.mbrace.or.jp/od2/K/{ym}/k{ymd6}.lzh`

### 出力先

- 生テキスト: `data/results_raw/K{yymmdd}.txt`
- 日別 CSV: `data/results_csv/{date}.csv`
- 全期間追記: `data/results_csv/results_all.csv`

### 強み

- 過去日分の一括取得に向く
- 既存の統計生成や verify と自然につながる

### 現在の自動フォールバック

LZH テキスト内に

- `24KBGN`
- `データは、この場の全レース終了後に登録されます。`
- `24KEND`

のような会場プレースホルダが見つかった場合、`fetch_results.py` は自動で `fetch_results_official.py` 相当の処理を呼び、公式結果ページから当該会場を補完します。

### 弱み

- 日によっては LZH が存在しても一部会場が未反映
- 当日や翌日早朝は日次ファイル自体が未公開のことがある

## 補完経路 `scripts/fetch_results_official.py`

### 役割

`boatrace.jp` の公式結果ページから、指定会場・指定日の成績を直接取得し、`results_csv/{date}.csv` に差し込みます。

### 入力元

- 結果一覧:
  - `https://www.boatrace.jp/owpc/pc/race/resultlist?hd={date}&jcd={jcd}`
- レース結果:
  - `https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd={date}`

### 出力先

- `data/results_csv/{date}.csv`

### 使いどころ

- LZH に会場欠損がある日
- 当日分の verify を先に作りたい日

### 使い方

```bash
python3 scripts/fetch_results_official.py --date 20260322 --jcd 24 --replace
```

`--replace` を付けると、同日・同会場の既存行を置換して保存します。

## 実運用フロー

1. `python3 scripts/fetch_results.py --date YYYYMMDD`
2. `results_csv/{date}.csv` に対象会場があるか確認
3. 自動補完で埋まらなかった会場だけ `python3 scripts/fetch_results_official.py --date YYYYMMDD --jcd XX --replace`
4. `python3 scripts/verify.py --jcd XX --from YYYYMMDD --to YYYYMMDD`

## 確認例

```bash
python3 - <<'PY'
import csv
from collections import Counter
with open('personal-life/boat/data/results_csv/20260321.csv', encoding='utf-8-sig') as f:
    print(Counter(r['venue_name'] for r in csv.DictReader(f)))
PY
```

## 直近の実例

### 2026-03-22 大村

- LZH 日次成績には `24KBGN` があるが、本文は `データは、この場の全レース終了後に登録されます。`
- そのため、公式結果ページから大村 1R-12R を補完
- 補完後に verify 実行

### 2026-03-23 下関・若松・福岡

- `fetch_results.py --date 20260323` では `休場/データなし`
- 公式 `resultlist` には到達できるが、レース結果リンク未公開のため、現時点では補完不可

## 注意点

- verify には `results_csv/{date}.csv` と `data/logs/{date}/{jcd}_R*_pred.json` の両方が必要
- 予測 HTML があっても、予測ログが無いと verify は作れない
- `resultlist` が開いても `raceresult` リンクが無ければ、公式ページ側もまだ未公開

## 関連ファイル

- `scripts/fetch_results.py`
- `scripts/fetch_results_official.py`
- `scripts/verify.py`
- `docs/CLAUDE_COWORK_HANDOVER.md`
