#!/usr/bin/env python3
"""data/venues/stats/w1_winrate.json を results_csv の実測から作る。

## 何のための数字か

predictor.estimate_w1_winrate() は「このレースで1号艇が1着になる確率」を
推定する。その出発点が会場ごとの 1号艇(枠番1)1着率 = overall_w1_winrate で、
そこに 級別 / 自前スコア順位 / ST / 全国勝率 の4係数を掛ける。
出た値の裏返し sink_risk = 1 - estimated が荒れ判定(is_rough)と信頼度%を動かす。

## なぜ要るか

このファイルが無いと base_rate が**全会場で定数 0.578 に固定**される。
実測では会場差が 42.5%(戸田) 〜 61.3%(徳山) と 18.9pt あり、各会場3,000R超なので
信頼区間も重ならない。定数固定だと、

  - 戸田で1号艇の勝率を 1.36倍 に過大評価する（荒れ判定が効いてほしい会場で効かない）
  - 全国平均が実測54.5%なのに57.8%を使うため、**全会場で一律に荒れ判定が鈍る**

## 出力

  {"<jcd>": {"overall_w1_winrate": 0.xxx, "races": N, "ci95": [lo, hi]}, ...}

races / ci95 は predictor は読まないが、後から「この数字はどれだけ確かか」を
確認できるように残す。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
from build_stats import VENUE_CODE_MAP as NAME_TO_JCD  # noqa: E402

OUT = BASE_DIR / "data" / "venues" / "stats" / "w1_winrate.json"
MIN_RACES = 300


def wilson(k: int, n: int) -> tuple[float, float]:
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m, c + m


def collect() -> list[tuple[str, str, bool]]:
    """(日付, 会場名, 1号艇が1着か) を1レース1件で返す。"""
    out, seen = [], set()
    for p in sorted(glob.glob(str(BASE_DIR / "data/results_csv/2*.csv"))):
        if "results_all" in p:
            continue
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                key = (r["date"], r["venue_name"], r["race_no"])
                if key in seen:
                    continue
                won3 = (r.get("won3") or "").strip()
                if not won3:
                    continue
                seen.add(key)
                out.append((r["date"], r["venue_name"].strip(), won3.startswith("1-")))
    return out


def rates(rows) -> tuple[Counter, Counter]:
    n, w = Counter(), Counter()
    for _, v, hit in rows:
        n[v] += 1
        w[v] += hit
    return n, w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="実際に書き出す")
    args = ap.parse_args()

    rows = collect()
    if not rows:
        print("results_csv が読めない")
        return 1
    rows.sort()
    n, w = rates(rows)
    half = len(rows) // 2
    nA, wA = rates(rows[:half])
    nB, wB = rates(rows[half:])

    national = sum(w.values()) / sum(n.values())
    print(f"対象 {sum(n.values()):,}レース / {len(n)}会場")
    print(f"全国の1号艇1着率 {national*100:.1f}%（コード内の定数は 0.578）\n")
    print(f"{'会場':<8}{'jcd':>4}{'R数':>7}{'1着率':>9}{'  95%区間':>15}"
          f"{'前半→後半':>16}")

    out: dict = {}
    skipped = []
    for v in sorted(n, key=lambda v: -w[v] / n[v]):
        jcd = NAME_TO_JCD.get(v, "")
        if not jcd or n[v] < MIN_RACES:
            skipped.append(v)
            continue
        p = w[v] / n[v]
        lo, hi = wilson(w[v], n[v])
        ra = wA[v] / nA[v] if nA[v] >= 100 else None
        rb = wB[v] / nB[v] if nB[v] >= 100 else None
        half_str = (f"{ra*100:.1f}%→{rb*100:.1f}%" if ra and rb else "n不足")
        print(f"{v:<8}{jcd:>4}{n[v]:>7,}{p*100:>8.1f}%   [{lo*100:.1f},{hi*100:.1f}]"
              f"{half_str:>16}")
        out[jcd] = {
            "venue_name": v,
            "overall_w1_winrate": round(p, 4),
            "races": n[v],
            "ci95": [round(lo, 4), round(hi, 4)],
        }
    if skipped:
        print(f"\n除外（{MIN_RACES}R未満 or 会場コード不明）: {skipped}")

    doc = {
        "_generated_by": "scripts/build_w1_winrate.py",
        "_meaning": ("会場ごとの「枠番1号艇の1着率」。"
                     "predictor.estimate_w1_winrate() の base_rate として使われ、"
                     "級別/スコア順位/ST/全国勝率の4係数がこれに掛かる。"
                     "裏返した sink_risk が荒れ判定(is_rough)と信頼度%を動かす。"),
        "_national": round(national, 4),
        "_races": sum(n.values()),
        "_min_races": MIN_RACES,
        **out,
    }
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n書き出した: {OUT}")
    else:
        print("\n（--write を付けると書き出す。付けないので何も変えていない）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
