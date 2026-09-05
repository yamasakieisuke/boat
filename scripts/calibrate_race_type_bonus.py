#!/usr/bin/env python3
"""RACE_TYPE_BONUS を results_csv から較正する。

なぜスクリプトにするか:
  この値は手で置かれた定数で、実測との対応が誰にも検証できない状態だった。
  分類を変えるたびに手で置き直すと同じことの繰り返しになるので、
  predictor.classify_race_type() をそのまま使って測り直せるようにする。

測り方:
  1. 各区分の 1号艇1着率を出す
  2. **レース番号の効果を割り戻す**。種別と番号は強く相関する（準優/優勝戦は
     必ず終盤、進入固定は序盤）ので、割り戻さないと種別が番号の代理変数になる。
     期待値は「そのレース番号の全体1着率」。
     ※ レース番号の効果自体は現状モデルに入っていない。venue_characteristics の
       race_no_tendency は全会場 1.0 で無効（実測は _measured_race_no_tendency）。
  3. 現行の加重平均 bonus を保つようにスケールする。
     type_bonus は course_advantage 全体にかかる係数で、勝率とは次元が違う。
     WEIGHTS["course_advantage"] は現行の平均 bonus を含んだ状態で調整されて
     いるはずなので、平均を動かさずに**相対の傾きだけ**直す。

使い方:
    python3 scripts/calibrate_race_type_bonus.py
    python3 scripts/calibrate_race_type_bonus.py --target-avg 1.0   # 平均を1.0に置く場合
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from predictor import classify_race_type, RACE_TYPE_BONUS  # noqa: E402

RESULTS_DIR = BASE_DIR / "data" / "results_csv"

# ── v5.26 以前の分類とボーナス（目標平均を出すためだけに残す）─────────────
# 「course_advantage にかかる係数の平均を変えない」を不変条件にするので、
# 変更前のコードが実際に掛けていた平均を再現できる必要がある。
_LEGACY_BONUS = {"fixed_entry": 1.20, "finalist": 1.12, "general": 1.00, "qualifier": 0.87}
_LEGACY_FINALIST  = re.compile(r"(優勝戦|準優勝戦|ドリーム|トライアル|マスターズ|シリーズ)")
_LEGACY_QUALIFIER = re.compile(r"(予選|敗者復活|一般|B級|選考|補充|組合せ|順位決定)")


def _legacy_classify(race_no: int, race_name: str) -> str:
    """v5.26 以前の classify_race_type()。レース番号フォールバック込み。"""
    if race_name:
        if re.search(r"進入固定", race_name):
            return "fixed_entry"
        if _LEGACY_FINALIST.search(race_name):
            return "finalist"
        if _LEGACY_QUALIFIER.search(race_name):
            return "qualifier"
    if race_no == 12:
        return "finalist"
    if race_no >= 11:
        return "general"
    return "qualifier"


def load_races() -> list[tuple[str, int, bool, str]]:
    """(新区分, レース番号, 1号艇が1着か, 旧区分) を1レース1件で返す。"""
    out: list[tuple[str, int, bool, str]] = []
    seen: set = set()
    # results_all.csv は廃止。日別CSVを読む（唯一のソース）
    import glob as _glob
    rows_iter = []
    for _p in sorted(_glob.glob(str(RESULTS_DIR / "2*.csv"))):
        if "results_all" in _p:
            continue
        with open(_p, encoding="utf-8-sig") as f:
            rows_iter.extend(list(csv.DictReader(f)))
    if True:
        for r in rows_iter:
            key = (r["date"], r["venue_name"], r["race_no"])
            if key in seen:
                continue
            won3 = (r.get("won3") or "").strip()
            if not won3:
                continue
            seen.add(key)
            rno = int(r["race_no"])
            name = (r.get("race_type") or "").strip()
            out.append((classify_race_type(rno, name), rno, won3.startswith("1-"),
                        _legacy_classify(rno, name)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-avg", type=float, default=None,
                    help="目標とする加重平均bonus。省略時は現行 RACE_TYPE_BONUS の加重平均を保つ")
    args = ap.parse_args()

    races = load_races()
    if not races:
        print("日別CSVが読めません")
        return 1

    # レース番号ごとの基準1着率（割り戻しに使う）
    rn_n, rn_w = Counter(), Counter()
    for _, rno, hit, _legacy in races:
        rn_n[rno] += 1
        rn_w[rno] += hit
    rate = {k: rn_w[k] / rn_n[k] for k in rn_n}
    base = sum(rn_w.values()) / sum(rn_n.values())

    n, w, exp = Counter(), Counter(), Counter()
    for cat, rno, hit, _legacy in races:
        n[cat] += 1
        w[cat] += hit
        exp[cat] += rate[rno]

    adjusted = {c: (w[c] / n[c]) / (exp[c] / n[c]) for c in n}

    total = sum(n.values())
    if args.target_avg is not None:
        target = args.target_avg
    else:
        # 変更前のコードが実際に掛けていた平均（旧分類・旧ボーナス・番号フォールバック込み）。
        # これを保てば course_advantage の全体の重みは動かず、相対の傾きだけが変わる。
        target = sum(_LEGACY_BONUS[lc] for _, _, _, lc in races) / total
    cur_avg_new = sum(adjusted[c] * n[c] for c in n) / total
    scale = target / cur_avg_new

    print(f"対象 {total:,}レース / 全体1号艇1着率 {base*100:.1f}%")
    print(f"目標の加重平均bonus {target:.4f}（スケール {scale:.4f}）\n")
    print(f"{'区分':<14}{'n':>8}{'1着率':>9}{'素の比':>9}{'番号調整後':>11}"
          f"{'新bonus':>10}{'現行':>8}")
    for c, cnt in n.most_common():
        raw = (w[c] / cnt) / base
        print(f"{c:<14}{cnt:>8,}{w[c]/cnt*100:>8.1f}%{raw:>9.3f}{adjusted[c]:>11.3f}"
              f"{adjusted[c]*scale:>10.3f}{RACE_TYPE_BONUS.get(c, float('nan')):>8.3f}")

    print("\nRACE_TYPE_BONUS = {")
    for c, _ in n.most_common():
        print(f'    "{c}": {adjusted[c]*scale:.3f},')
    print(f'    "unknown": {target:.3f},   # 名前が取れないとき＝情報なし（全体平均）')
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
