#!/usr/bin/env python3
"""展示タイムのコース別の構造的な偏りを実測する。

## なぜ要るか

展示タイムは**引き波の影響を受ける**。1コースは前に艇がいないぶん速く出る。
実測(478,649件)で 1コースは他コースより 0.015〜0.023秒 速い。
レース内の展示タイム幅は中央値0.120秒なので、**構造的優位がばらつきの約17%**を占める。

生タイムをレース内で正規化すると、この構造がそのまま「速い」と評価される。
実際、現行の exhibition_score は 1枠の平均が 0.6285（中立なら0.5）と偏っており、
course_advantage が既に持っているイン有利を**二重に数えている**。

補正して測り直すと、展示の効果は残るが約1.5倍に水増しされていたと分かる:
  枠1 展示1位vs6位の差  生 +25.4pt → 補正後 +16.8pt
  枠3                    生 +14.5pt → 補正後 +10.2pt

## 出力

  {"national": {"1": 0.0, "2": 0.015, ...}, "_venues": {jcd: {...}}}

national は全会場プール（安定）。_venues は診断用で、predictor は読まない。
水面ごとに引き波の出方は違うはずだが、まずは全国値で足りるかを見る。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
from build_stats import VENUE_CODE_MAP as NAME_TO_JCD  # noqa: E402

OUT = BASE_DIR / "data" / "venues" / "stats" / "exhibition_course_bias.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    nat = defaultdict(list)
    per = defaultdict(lambda: defaultdict(list))
    for p in sorted(glob.glob(str(BASE_DIR / "data/results_csv/2*.csv"))):
        if "results_all" in p:
            continue
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                c = (r.get("course_enter") or "").strip()
                t = (r.get("exhibition_time") or "").strip()
                if not c.isdigit():
                    continue
                try:
                    t = float(t)
                except ValueError:
                    continue
                if not (6.0 < t < 8.0):
                    continue
                nat[int(c)].append(t)
                jcd = NAME_TO_JCD.get(r["venue_name"].strip(), "")
                if jcd:
                    per[jcd][int(c)].append(t)

    if not nat:
        print("展示タイムが読めない")
        return 1
    base = statistics.mean(nat[1])
    national = {str(c): round(statistics.mean(nat[c]) - base, 4) for c in sorted(nat)}
    print(f"全国 {sum(len(v) for v in nat.values()):,}件")
    print(f"{'コース':<8}{'n':>10}{'平均':>9}{'1コースとの差':>14}")
    for c in sorted(nat):
        print(f"{c:<8}{len(nat[c]):>10,}{statistics.mean(nat[c]):>9.3f}"
              f"{national[str(c)]:>+13.4f}秒")

    venues = {}
    for jcd, d in sorted(per.items()):
        if min((len(v) for v in d.values()), default=0) < 500:
            continue
        b = statistics.mean(d[1])
        venues[jcd] = {str(c): round(statistics.mean(d[c]) - b, 4) for c in sorted(d)}

    doc = {
        "_generated_by": "scripts/build_exhibition_course_bias.py",
        "_meaning": ("展示タイムのコース別の構造的な偏り（1コース基準の秒差）。"
                     "引き波の有無で1コースが速く出る。生タイムのまま正規化すると"
                     "course_advantage と二重にイン有利を数えることになる。"),
        "_races": sum(len(v) for v in nat.values()),
        "national": national,
        "_venues": venues,
    }
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n書き出した: {OUT}")
    else:
        print("\n（--write で書き出す）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
