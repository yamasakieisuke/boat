#!/usr/bin/env python3
"""「入れたのに効いていない」ロジックを予測ログから検出する。

## なぜ

このリポジトリで繰り返し起きている事故は、**壊れたのではなく黙って中立に落ちる**
タイプ。エラーも警告も出ないので、振り返りで「効いていなかった」と気づくまで
何ヶ月も走り続ける。今までに見つかったぶんだけで:

  1. data/venues/         … 会場・季節・潮汐の補正が丸ごと無効（iCloud事故で消失）
  2. tournament_grades    … git に一度も入らず、SG/G1のイン有利が常に 1.0
  3. *_combo_freq.json    … 生成されておらず会場別ブレンドが全会場 None
  4. w1_winrate.json      … 生成器そのものが無く定数 0.578 に固定
  5. data/techniques/     … git 未追跡で Actions からは存在しないのと同じ
  6. predict.yml のシャドー … 一度も実行されていなかった
  7. verify.py のログ収集 … *_pred.json しか拾わずシャドーが検証に届かない
  8. female_factor        … 天候が無いと女子選手が居ても必ず中立を返す
  9. 展開モデルの cond2   … 重みが小さく買い目の集合が3%しか変わらなかった

共通するのは「**結果のログしか残っておらず、入力が有ったのかを事後に確認できない**」
こと。preflight_data.py はファイルの存在を見るが、存在しても効いていない
（8番・9番）は捕まえられない。ここでは**出力の分散**を見る。

## 何を見るか

1. **スコア項目が定数になっていないか**
   全艇・全レースで同じ値なら、その補正はレースの差を一切生んでいない。
   中立値に張り付いている＝入力が無いか、条件が一度も成立していない。

2. **入力が揃っていたか**（pred.json の inputs ブロック）
   天候・コメント・展示・潮汐などの取得率。低いものは上流が壊れている。

3. **シャドー変種が本番と同じ買い目を出していないか**
   集合が変わらないなら、そのロジックは検証以前に出口が詰まっている。

## 使い方

    python3 scripts/audit_dead_logic.py --from 20260901 --to 20260905
    python3 scripts/audit_dead_logic.py --days 7        # 直近7日
"""
from __future__ import annotations

import argparse
import datetime
import json
import statistics
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "data" / "logs"

# 「定数でも異常ではない」項目。中立が正しい状態のもの。
EXPECTED_CONSTANT: set[str] = set()

# 分散がこれ未満なら定数とみなす
FLAT_EPS = 1e-9


def _load(date_from: str, date_to: str):
    prod: list[tuple[str, dict]] = []
    shadow: dict[str, dict[tuple, dict]] = defaultdict(dict)
    for d_dir in sorted(LOG_DIR.glob("2*")):
        if not (date_from <= d_dir.name <= date_to):
            continue
        for p in sorted(d_dir.glob("*_R*_pred*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            stem = p.stem
            key = (d_dir.name, stem.split("_")[0], d.get("race_no"))
            if stem.endswith("_pred"):
                prod.append((d_dir.name, d))
            else:
                shadow[stem.rsplit("_pred_", 1)[1]][key] = d
    return prod, shadow


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default="")
    ap.add_argument("--to", dest="date_to", default="")
    ap.add_argument("--days", type=int, default=0, help="直近N日")
    args = ap.parse_args()

    if args.days:
        today = datetime.date.today()
        args.date_from = (today - datetime.timedelta(days=args.days)).strftime("%Y%m%d")
        args.date_to = today.strftime("%Y%m%d")
    date_from = args.date_from or "20000101"
    date_to = args.date_to or "29991231"

    prod, shadow = _load(date_from, date_to)
    if not prod:
        print(f"予測ログが見つからない（{date_from}〜{date_to}）")
        return 0

    print("=" * 74)
    print(f"  効いていないロジックの検出  {date_from}〜{date_to}  {len(prod):,}レース")
    print("=" * 74)

    problems: list[str] = []

    # ── 1) スコア項目の分散 ────────────────────────────────
    vals: dict[str, list[float]] = defaultdict(list)
    for _d, log in prod:
        for r in log.get("predictions") or []:
            for k, v in (r.get("breakdown") or {}).items():
                if isinstance(v, (int, float)):
                    vals[k].append(float(v))

    print(f"\n■ スコア項目（{sum(len(v) for v in vals.values()):,}艇ぶん）")
    print(f"  {'項目':<24}{'最小':>9}{'最大':>9}{'標準偏差':>11}  判定")
    for k in sorted(vals, key=lambda x: statistics.pstdev(vals[x])):
        v = vals[k]
        sd = statistics.pstdev(v)
        flag = ""
        if sd < FLAT_EPS and k not in EXPECTED_CONSTANT:
            flag = "← 定数。レースの差を一切生んでいない"
            problems.append(f"スコア項目 {k} が定数（値 {v[0]}）")
        print(f"  {k:<24}{min(v):>9.4f}{max(v):>9.4f}{sd:>11.6f}  {flag}")

    # ── 2) 入力の取得率 ────────────────────────────────────
    inp: dict[str, list[float]] = defaultdict(list)
    n_with = 0
    for _d, log in prod:
        block = log.get("inputs")
        if not block:
            continue
        n_with += 1
        for k, v in block.items():
            inp[k].append(1.0 if v is True else (0.0 if v is False else float(bool(v))))

    print(f"\n■ 入力の取得率（inputs ブロックのある {n_with:,}レース）")
    if not n_with:
        print("  inputs が記録されていない。predictor.py が古い可能性がある")
        print("  （2026-09-05 以降のログにしか入っていない）")
    for k in sorted(inp, key=lambda x: sum(inp[x]) / len(inp[x])):
        rate = sum(inp[k]) / len(inp[k])
        flag = ""
        if rate == 0.0:
            flag = "← 一度も取れていない。これに依存する補正は全部死んでいる"
            problems.append(f"入力 {k} の取得率が 0%")
        elif rate < 0.5:
            flag = "← 取得率が低い。上流を確認"
            problems.append(f"入力 {k} の取得率が {rate*100:.0f}%")
        print(f"  {k:<20}{rate*100:>6.1f}%  {flag}")

    # ── 3) シャドー変種が出口に届いているか ────────────────
    if shadow:
        print("\n■ シャドー変種（買い目の集合が本番と変わった割合）")
        prod_by_key = {}
        for d, log in prod:
            prod_by_key[(d, log.get("jcd"), log.get("race_no"))] = log
        for var, logs in sorted(shadow.items()):
            same = diff = 0
            for key, sl in logs.items():
                pl = prod_by_key.get((key[0], sl.get("jcd"), key[2]))
                if not pl:
                    continue
                a = {b.get("combo") for b in (pl.get("bets") or [])}
                b = {x.get("combo") for x in (sl.get("bets") or [])}
                if a == b:
                    same += 1
                else:
                    diff += 1
            tot = same + diff
            if not tot:
                continue
            rate = diff / tot
            flag = ""
            if rate < 0.05:
                flag = "← 出口が詰まっている。検証しても差が出ない"
                problems.append(f"シャドー {var} の買い目が {rate*100:.1f}% しか変わらない")
            print(f"  {var:<20}{rate*100:>6.1f}%  ({diff}/{tot})  {flag}")

    print("\n" + "=" * 74)
    if problems:
        print(f"  ⚠️  {len(problems)}件")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  問題なし。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
