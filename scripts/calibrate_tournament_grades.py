#!/usr/bin/env python3
"""data/tournament_grades.json を racecards × results_csv の実測から作る。

背景:
  predictor.get_tournament_grade_mods() はこのファイルが無いと全グレードに対して
  course_mod=[1.0]*6 を返す。2026-09-05 時点でファイルは存在せず git にも
  一度も入っていなかったため、SG/G1 のイン有利増幅もレディースのイン弱体も
  **一度も効いていなかった**。

測り方:
  grade は racecards の tournament_grade、着順・進入コースは results_csv。
  (日付, 会場コード, レース番号) で結合し、完走6艇のレースだけ使う。
  各 (グレード, コース) の1着率を、そのコースの全体1着率で割った比を出す。
  これが course_mod の意味そのもの（course_score にこの比を掛ける）。

⚠️ 採否の基準（ここが重要）:
  比が1.0から離れて見えても、多くはサンプル不足のノイズ。実測では
    - SG   C6: 前半3.07 → 後半0.40
    - レディース C5: 前半0.83 → 後半1.43
  のように期間を割ると符号ごと変わるセルがある。**信頼区間が1.0を含むセルは
  1.0のまま据え置く**（--shrink、既定で有効）。全部そのまま入れると
  ノイズを予想に持ち込むことになり、中立のままより悪くなりうる。
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
from build_stats import VENUE_CODE_MAP as NAME_TO_JCD  # noqa: E402

OUT = BASE_DIR / "data" / "tournament_grades.json"
# これ未満のグレードは丸ごと中立にする。
# 500 に置いたのは、分割検定で崩れたのが SG(245R) と G2(352R) の2つで、
# 残った 一般(11,714) / G1(2,219) / G3(1,592) / レディース(533) は前後半で
# 符号も大きさも保たれたため。閾値を数字合わせで下げないこと。
MIN_RACES = 500


def wilson(k: int, n: int) -> tuple[float, float]:
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - m, c + m


def load() -> tuple[dict, dict]:
    grade = {}
    for f in glob.glob(str(BASE_DIR / "data/racecards/*/*.json")):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        key = (d.get("date"), str(d.get("venue_code")), int(d.get("race_no") or 0))
        grade[key] = (d.get("tournament_grade") or "").strip()

    races: dict = collections.defaultdict(dict)
    for p in sorted(glob.glob(str(BASE_DIR / "data/results_csv/2*.csv"))):
        with open(p, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                jcd = NAME_TO_JCD.get(r["venue_name"].strip(), "")
                if not jcd:
                    continue
                key = (r["date"], jcd, int(r["race_no"]))
                ce = (r.get("course_enter") or "").strip()
                rk = (r.get("rank") or "").strip()
                if ce.isdigit() and rk.isdigit():
                    races[key][int(ce)] = int(rk)
    return grade, races


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-shrink", action="store_true",
                    help="信頼区間が1.0を含むセルもそのまま入れる（非推奨）")
    ap.add_argument("--write", action="store_true", help="実際にファイルを書き出す")
    args = ap.parse_args()

    grade, races = load()
    keys = [k for k in grade if k in races and len(races[k]) == 6]
    if not keys:
        print("結合できるレースが無い。racecards のバックフィルが進んでいるか確認すること")
        return 1

    def tally(subset):
        n, w, gn = collections.Counter(), collections.Counter(), collections.Counter()
        for k in subset:
            g = grade[k] or "(空)"
            gn[g] += 1
            for c, rk in races[k].items():
                n[(g, c)] += 1
                if rk == 1:
                    w[(g, c)] += 1
        return n, w, gn

    keys.sort()                       # 日付順。前後半に割って安定性を見る
    n, w, gn = tally(keys)
    half = len(keys) // 2
    nA, wA, gA = tally(keys[:half])
    nB, wB, gB = tally(keys[half:])

    def half_ratio(nn, ww, gg, g, c):
        """その期間だけで測った比。母数が薄ければ None。"""
        if nn[(g, c)] < 40:
            return None
        bs = sum(ww[(x, c)] for x in gg) / max(sum(nn[(x, c)] for x in gg), 1)
        return (ww[(g, c)] / nn[(g, c)]) / bs if bs else None

    grades = sorted(gn)
    base = {c: sum(w[(g, c)] for g in grades) / max(sum(n[(g, c)] for g in grades), 1)
            for c in range(1, 7)}

    print(f"結合 {len(keys):,}レース（完走6艇のみ）")
    print("全体のコース別1着率: " + "  ".join(f"{c}:{base[c]*100:.1f}%" for c in range(1, 7)))
    print(f"\n{'グレード':<12}{'R数':>6}   " + "".join(f"{'C'+str(c):>9}" for c in range(1, 7)))

    out_grades = {}
    for g, cnt in gn.most_common():
        mods, kept = [], 0
        for c in range(1, 7):
            N, K = n[(g, c)], w[(g, c)]
            if cnt < MIN_RACES or not N or not base[c]:
                mods.append(1.0)
                continue
            ratio = (K / N) / base[c]
            lo, hi = wilson(K, N)
            significant = not (lo / base[c] <= 1.0 <= hi / base[c])

            # 第2の関門: 期間を前後半に割って符号が一致し、開きが小さいこと。
            # 信頼区間だけだと母数の薄いセルが通ってしまう。実測では
            # SG C6 が 3.07→0.40、G2 C6 が 2.186 と、区間は通るのに
            # 期間を割ると崩れるセルがあった。
            ra = half_ratio(nA, wA, gA, g, c)
            rb = half_ratio(nB, wB, gB, g, c)
            stable = (ra is not None and rb is not None
                      and (ra - 1.0) * (rb - 1.0) > 0        # 符号が一致
                      and abs(ra - rb) <= 0.25)              # 開きが小さい

            if args.no_shrink or (significant and stable):
                mods.append(round(ratio, 3))
                kept += 1
            else:
                mods.append(1.0)
        c1_n, c1_w = n[(g, 1)], w[(g, 1)]
        out_grades[g] = {
            "course_mod": mods,
            "volatility": 1.0,
            "races": cnt,
            "kept_cells": kept,
            # 表示用（predictor._generate_tournament_guide_md が読む）
            "course1_win_pct": round(c1_w / c1_n * 100, 1) if c1_n else None,
            "note": (f"実測{cnt:,}R。採用{kept}セル"
                     if kept else f"実測{cnt:,}R。有意かつ安定なセルが無く全中立"),
        }
        mark = "  ← 全セル中立" if kept == 0 else f"  ← {kept}セル採用"
        print(f"{g:<12}{cnt:>6}   " + "".join(f"{m:>9.3f}" for m in mods) + mark)

    doc = {
        "_generated_by": "scripts/calibrate_tournament_grades.py",
        "_method": ("racecards の tournament_grade と results_csv を結合し、"
                    "(グレード,コース)の1着率をそのコースの全体1着率で割った比。"
                    "採用条件は2つ: (1)信頼区間が1.0を含まない (2)期間を前後半に"
                    "割っても符号が一致し開きが0.25以内。どちらか外れたセルは1.0に"
                    "据え置く。区間だけだと母数の薄いセルが通ってしまう。"),
        "_races": len(keys),
        "_min_races_per_grade": MIN_RACES,
        "grades": out_grades,
        "ladies_tournaments": {},
    }
    if args.write:
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n書き出した: {OUT}")
    else:
        print("\n（--write を付けると書き出す。付けないので何も変えていない）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
