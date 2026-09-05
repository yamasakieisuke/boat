#!/usr/bin/env python3
"""福岡オリジナル展示（一周/まわり足/直線）が着順の情報を持つかを測る。

## この検証で答える問い

「予想に組み込む価値があるか」の前に「**そもそも着順と関係があるか**」を見る。
関係が無ければ組み込む意味は無いし、あっても**既に持っている情報（枠番・標準展示）
で説明がつくなら上乗せは無い**。増分を見るのがこのスクリプトの主眼。

## なぜ予想エンジンを回さないのか

オリジナル展示は展示航走の結果＝レース前に確定するので、着順との関係を測るのに
未来の情報は要らない。エンジンを回す（＝バックテスト）には
  - その時点の選手・モーター統計（今のファイルは全期間ぶんなので look-ahead になる）
  - その時点のオッズ（20260818 より前は保有していない）
が要る。**先に安いほうで信号の有無を確かめる。**

## 測り方

1. レース内で各艇の一周/まわり足/直線を順位化する（速い=1位）
2. 順位ごとの1着率・2連対率・3連対率を出す
3. **枠番で層別する**。福岡でも1号艇が57.9%勝つので、層別しないと
   「1号艇が展示も速い」だけを見てしまう
4. 標準展示タイムの順位と比べ、**それを上回る情報があるか**を見る

使い方:
    python3 scripts/analyze_fukuoka_tenji.py
    python3 scripts/analyze_fukuoka_tenji.py --from 20250608
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
COLS = ("lap_time", "turn_time", "straight_time", "exhibition_time")
LABEL = {"lap_time": "一周", "turn_time": "まわり足",
         "straight_time": "直線", "exhibition_time": "標準展示"}


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - m) * 100, (c + m) * 100


def load(date_from: str) -> list[list[dict]]:
    """福岡のレースを [ {waku, rank, 各タイム}, ... ] の単位で返す。"""
    races: dict = defaultdict(list)
    for p in sorted(glob.glob(str(BASE_DIR / "data/results_csv/2*.csv"))):
        if "results_all" in p:
            continue
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["venue_name"].strip() != "福岡" or r["date"] < date_from:
                    continue
                row = {"waku": r.get("waku", ""), "rank": r.get("rank", "")}
                for c in COLS:
                    v = (r.get(c) or "").strip()
                    try:
                        row[c] = float(v)
                    except ValueError:
                        row[c] = None
                races[(r["date"], r["race_no"])].append(row)
    # オリジナル展示が全艇そろっているレースだけ使う
    out = []
    for rows in races.values():
        if len(rows) != 6:
            continue
        if all(x["lap_time"] is not None for x in rows):
            out.append(rows)
    return out


def ranks_of(rows: list[dict], col: str) -> dict:
    """レース内順位（速い=1）。同値は同順位。"""
    vals = [(x[col], x["waku"]) for x in rows if x[col] is not None]
    vals.sort()
    out, prev, r = {}, None, 0
    for i, (v, w) in enumerate(vals, 1):
        if v != prev:
            r = i
            prev = v
        out[w] = r
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default="20250608")
    args = ap.parse_args()

    races = load(args.date_from)
    if not races:
        print("オリジナル展示が入ったレースがまだ無い。"
              "scripts/backfill_fukuoka_tenji.py の完了を待つこと")
        return 1
    print(f"対象 {len(races):,}レース（福岡・{args.date_from}以降・"
          f"オリジナル展示が全艇そろったもの）\n")

    # ── 1) 単純な順位別の成績 ─────────────────────────────
    for col in COLS:
        n, w1, w2, w3 = Counter(), Counter(), Counter(), Counter()
        for rows in races:
            rk = ranks_of(rows, col)
            for x in rows:
                r = rk.get(x["waku"])
                fr = x["rank"]
                if r is None or not str(fr).isdigit():
                    continue
                fr = int(fr)
                n[r] += 1
                w1[r] += fr == 1
                w2[r] += fr <= 2
                w3[r] += fr <= 3
        print(f"■ {LABEL[col]} の順位別")
        print(f"  {'順位':<5}{'n':>7}{'1着率':>9}{'  95%区間':>15}{'2連対':>8}{'3連対':>8}")
        for r in sorted(n):
            lo, hi = wilson(w1[r], n[r])
            print(f"  {r:<5}{n[r]:>7,}{w1[r]/n[r]*100:>8.1f}%   [{lo:.1f},{hi:.1f}]"
                  f"{w2[r]/n[r]*100:>7.1f}%{w3[r]/n[r]*100:>7.1f}%")
        print()

    # ── 2) 枠番で層別（ここが本番）───────────────────────
    print("■ 枠番で層別した1着率（枠の強さを取り除いた上での効き）")
    print("  同じ枠の中で、展示の順位が上位/下位のときに1着率がどう変わるか\n")
    for col in ("lap_time", "turn_time", "straight_time", "exhibition_time"):
        print(f"  ── {LABEL[col]} ──")
        print(f"    {'枠':<4}{'展示上位(1-2位)':>18}{'展示下位(5-6位)':>18}{'差':>9}")
        for waku in range(1, 7):
            hi_n = hi_w = lo_n = lo_w = 0
            for rows in races:
                rk = ranks_of(rows, col)
                for x in rows:
                    if str(x["waku"]) != str(waku) or not str(x["rank"]).isdigit():
                        continue
                    r = rk.get(x["waku"])
                    if r is None:
                        continue
                    win = int(x["rank"]) == 1
                    if r <= 2:
                        hi_n += 1; hi_w += win
                    elif r >= 5:
                        lo_n += 1; lo_w += win
            if hi_n < 30 or lo_n < 30:
                print(f"    {waku:<4}{'母数不足':>18}")
                continue
            a, b = hi_w / hi_n * 100, lo_w / lo_n * 100
            print(f"    {waku:<4}{f'{a:.1f}% (n={hi_n})':>18}"
                  f"{f'{b:.1f}% (n={lo_n})':>18}{a-b:>+8.1f}pt")
        print()

    print("読み方: 差が大きく、かつ標準展示より大きければ「標準展示に無い情報を"
          "持っている」ことになる。差が小さい、または標準展示と同程度なら、"
          "予想に足しても上乗せは期待できない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
