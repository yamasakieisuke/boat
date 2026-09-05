#!/usr/bin/env python3
"""判定基準が実際に効いているかを、蓄積した検証履歴から確かめる。

## なぜ要るか

予想エンジンには判定基準が積み上がっている（荒れ判定 / 信頼度 / 沈みリスク /
レース種別 / セオリーパターン / 買い目の並び順）。だが「入れた」ことは記録されても
**「効いていたか」を後から確かめる場所が無かった**。効かない基準が残り続けると、
次の改修もその上に積むことになる。

## 判定の考え方

ある基準が「効いている」とは、**その基準で切ったときにグループ間で成績が違う**
ということ。よって各グループの的中率・回収率を出し、次の2つを見る:

  1. 差があるか   … 最上位と最下位のグループの95%信頼区間が重ならないか
  2. 続いているか … 期間を前後半に割っても、グループの順位関係が保たれるか

**1だけでは足りない。** この repo では会場別回収率が3倍開いて見えたのに順列検定
p=0.37 だった前例（フェーズA）や、大会グレードのセルが期間を割ると符号ごと
反転した前例がある。1回の期間で差が出ることと、その差が本物であることは別。

使い方:
    python3 scripts/review_criteria.py                 # 表示のみ
    python3 scripts/review_criteria.py --html PATH     # ページも書き出す
"""
from __future__ import annotations

import argparse
import html as _html
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY = BASE_DIR / "data" / "logs" / "verify_history.json"
BREAK_EVEN = 75.0          # 3連単の払戻率
MIN_RACES = 60             # これ未満のグループは判定に使わない


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - m) * 100, (c + m) * 100


def blank() -> dict:
    return {"races": 0, "hits": 0, "points": 0, "payout": 0, "w1_won": 0}


def add(dst: dict, src: dict) -> None:
    for k in ("races", "hits", "points", "payout", "w1_won"):
        dst[k] += int(src.get(k, 0) or 0)


def collect(records: list) -> dict:
    """{基準グループ: {ラベル: 実績}} に畳む。"""
    out: dict = defaultdict(lambda: defaultdict(blank))
    for r in records:
        for group, buckets in (r.get("criteria_stats") or {}).items():
            for label, v in buckets.items():
                add(out[group][label], v)
        # 買い目の並び順は roi.by_cell に既にある（criteria_stats より前から取れる）
        for label, v in ((r.get("roi") or {}).get("by_cell") or {}).items():
            c = out["bet_cell"][label]
            c["races"] += int(v.get("points", 0) or 0)     # ここは「点数」が母数
            c["hits"] += int(v.get("hits", 0) or 0)
            c["points"] += int(v.get("points", 0) or 0)
            c["payout"] += int(v.get("payout", 0) or 0)
        for label, v in (r.get("pattern_stats") or {}).items():
            c = out["pattern"][label]
            c["races"] += int(v.get("applied", 0) or 0)
            c["hits"] += int(v.get("applied_hit", 0) or 0)
    return out


GROUP_META = {
    "is_rough":      ("荒れ判定 (is_rough)", "荒れると判定したレースは実際に当てにくいか"),
    "confidence":    ("信頼度 (confidence)", "信頼度が高いほど的中率も高いか"),
    "sink_risk":     ("1号艇の沈みリスク", "沈みリスクが高いほど1号艇は実際に沈むか"),
    "race_category": ("レース種別", "種別ごとに成績が違うか（RACE_TYPE_BONUS の前提）"),
    "bet_cell":      ("買い目の並び順", "本命#1が#4より当たるか＝並べる意味があるか"),
    "pattern":       ("セオリーパターン", "パターン適用時に的中率が上がるか"),
}


def judge(buckets: dict, halves: tuple[dict, dict]) -> tuple[str, str]:
    """(判定, 理由) を返す。"""
    usable = {k: v for k, v in buckets.items() if v["races"] >= MIN_RACES}
    if len(usable) < 2:
        return "判定不能", f"母数{MIN_RACES}以上のグループが2つ未満"
    rates = {k: v["hits"] / v["races"] for k, v in usable.items()}
    hi = max(rates, key=rates.get)
    lo = min(rates, key=rates.get)
    hlo, hhi = wilson(usable[hi]["hits"], usable[hi]["races"])
    llo, lhi = wilson(usable[lo]["hits"], usable[lo]["races"])
    separated = hlo > lhi
    A, B = halves
    ra = {k: (A[k]["hits"] / A[k]["races"]) for k in usable if A.get(k, blank())["races"] >= 25}
    rb = {k: (B[k]["hits"] / B[k]["races"]) for k in usable if B.get(k, blank())["races"] >= 25}
    both = set(ra) & set(rb)
    stable = None
    if len(both) >= 2:
        oa = sorted(both, key=lambda k: ra[k])
        ob = sorted(both, key=lambda k: rb[k])
        stable = (oa[0] == ob[0] and oa[-1] == ob[-1])
    spread = (rates[hi] - rates[lo]) * 100
    if not separated:
        return "効いていない", f"最上位{hi}と最下位{lo}の信頼区間が重なる（差{spread:.1f}pt）"
    if stable is False:
        return "疑わしい", f"差{spread:.1f}ptはあるが、前後半で順位が入れ替わる"
    if stable is None:
        return "たぶん効いている", f"差{spread:.1f}pt・区間は分離。ただし前後半に割ると母数不足で安定性は未確認"
    return "効いている", f"差{spread:.1f}pt・区間が分離し、前後半でも順序が保たれる"


def render_rows(buckets: dict) -> list[dict]:
    rows = []
    for label, v in sorted(buckets.items(), key=lambda kv: -kv[1]["races"]):
        n, k = v["races"], v["hits"]
        lo, hi = wilson(k, n)
        roi = (v["payout"] / (v["points"] * 100) * 100) if v["points"] else None
        rows.append({
            "label": label, "n": n, "hits": k,
            "hit_pct": (k / n * 100) if n else 0.0,
            "ci": (lo, hi), "roi": roi,
            "thin": n < MIN_RACES,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="", help="HTMLの書き出し先")
    ap.add_argument("--from", dest="date_from", default="", help="開始日 YYYYMMDD")
    args = ap.parse_args()

    if not HISTORY.exists():
        print(f"検証履歴が無い: {HISTORY}")
        return 1
    recs = json.loads(HISTORY.read_text(encoding="utf-8"))
    if args.date_from:
        recs = [r for r in recs if (r.get("date_from") or "") >= args.date_from]
    recs.sort(key=lambda r: (r.get("date_from") or "", r.get("jcd") or ""))
    if not recs:
        print("対象レコードが無い")
        return 1

    half = len(recs) // 2
    allb = collect(recs)
    A, B = collect(recs[:half]), collect(recs[half:])

    span = f"{recs[0].get('date_from')}〜{recs[-1].get('date_to')}"
    total_races = sum(r.get("total_races", 0) for r in recs)
    print("=" * 78)
    print(f"  判定基準の効果検証   期間 {span} / {len(recs)}会場日 / {total_races:,}レース")
    print("=" * 78)

    results = []
    for group in ("is_rough", "confidence", "sink_risk", "race_category",
                  "bet_cell", "pattern"):
        buckets = allb.get(group) or {}
        if not buckets:
            continue
        title, question = GROUP_META.get(group, (group, ""))
        verdict, reason = judge(buckets, (A.get(group, {}), B.get(group, {})))
        rows = render_rows(buckets)
        results.append({"group": group, "title": title, "question": question,
                        "verdict": verdict, "reason": reason, "rows": rows})
        print(f"\n■ {title} — {question}")
        print(f"  判定: 【{verdict}】 {reason}")
        print(f"  {'グループ':<16}{'母数':>8}{'的中率':>9}{'  95%区間':>16}{'回収率':>9}")
        for r in rows:
            roi = f"{r['roi']:.1f}%" if r["roi"] is not None else "-"
            thin = "  ※母数不足" if r["thin"] else ""
            print(f"  {r['label']:<16}{r['n']:>8,}{r['hit_pct']:>8.1f}%"
                  f"   [{r['ci'][0]:.1f},{r['ci'][1]:.1f}]{roi:>9}{thin}")

    if args.html:
        out = Path(args.html)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(results, span, len(recs), total_races), encoding="utf-8")
        print(f"\n書き出した: {out}")
    return 0


VERDICT_CLASS = {"効いている": "ok", "たぶん効いている": "maybe",
                 "疑わしい": "warn", "効いていない": "bad", "判定不能": "unknown"}


def build_html(results: list, span: str, n_days: int, total_races: int) -> str:
    e = _html.escape
    parts = [f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>判定基準の効果検証</title><style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#e2e6ef;--head:#2c4a8a;--zebra:#f6f8fc;
--ok:#1c7c3f;--maybe:#7a6a10;--warn:#a35a00;--bad:#a32020;--unknown:#666}}
@media(prefers-color-scheme:dark){{:root{{--bg:#14161a;--fg:#e8eaed;--mut:#9aa0a6;
--line:#2b2f36;--head:#3a5a9a;--zebra:#1b1e23;--ok:#4cc46e;--maybe:#d4bd4a;
--warn:#e0913c;--bad:#e46a6a;--unknown:#9aa0a6}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.7 -apple-system,sans-serif;
margin:0;padding:20px;max-width:1000px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
h2{{font-size:15px;margin:26px 0 2px}} .q{{color:var(--mut);font-size:13px;margin-bottom:8px}}
.verdict{{display:inline-block;padding:2px 10px;border-radius:4px;font-weight:700;
font-size:13px;color:#fff}}
.ok{{background:var(--ok)}}.maybe{{background:var(--maybe)}}.warn{{background:var(--warn)}}
.bad{{background:var(--bad)}}.unknown{{background:var(--unknown)}}
.reason{{color:var(--mut);font-size:13px;margin:6px 0 10px}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse;font-size:13px;min-width:100%}}
th{{background:var(--head);color:#fff;padding:6px 10px;text-align:left;white-space:nowrap}}
td{{border-bottom:1px solid var(--line);padding:5px 10px;white-space:nowrap}}
tr:nth-child(even) td{{background:var(--zebra)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.thin{{color:var(--mut)}} .note{{color:var(--mut);font-size:12px;margin-top:6px}}
footer{{margin-top:34px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);
padding-top:12px}}
</style></head><body>
<h1>判定基準の効果検証</h1>
<div class="sub">期間 {e(span)} ／ {n_days}会場日 ／ {total_races:,}レース　
生成 {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
<div class="note">判定は2段構え。<b>①最上位と最下位のグループの95%信頼区間が重ならないか</b>、
<b>②期間を前後半に割っても順位関係が保たれるか</b>。①だけでは足りない
（会場別回収率が3倍開いて見えたのに順列検定 p=0.37 だった前例がある）。
回収率の損益分岐は {BREAK_EVEN:.0f}%。母数{MIN_RACES}未満のグループは判定に使わない。</div>"""]
    for r in results:
        cls = VERDICT_CLASS.get(r["verdict"], "unknown")
        parts.append(f'<h2>{e(r["title"])}</h2><div class="q">{e(r["question"])}</div>'
                     f'<span class="verdict {cls}">{e(r["verdict"])}</span>'
                     f'<div class="reason">{e(r["reason"])}</div><div class="tw"><table>'
                     f'<tr><th>グループ</th><th class="num">母数</th><th class="num">的中</th>'
                     f'<th class="num">的中率</th><th>95%区間</th><th class="num">回収率</th></tr>')
        for row in r["rows"]:
            roi = f'{row["roi"]:.1f}%' if row["roi"] is not None else "-"
            tc = ' class="thin"' if row["thin"] else ""
            parts.append(
                f'<tr{tc}><td>{e(row["label"])}{"（母数不足）" if row["thin"] else ""}</td>'
                f'<td class="num">{row["n"]:,}</td><td class="num">{row["hits"]:,}</td>'
                f'<td class="num">{row["hit_pct"]:.1f}%</td>'
                f'<td>[{row["ci"][0]:.1f}, {row["ci"][1]:.1f}]</td>'
                f'<td class="num">{roi}</td></tr>')
        parts.append("</table></div>")
    parts.append('<footer>scripts/review_criteria.py が data/logs/verify_history.json '
                 'から生成。criteria_stats は 2026-09-05 の verify から記録が始まったため、'
                 'それ以前の会場日は荒れ判定・信頼度・沈みリスク・レース種別の行を持たない。'
                 '</footer></body></html>')
    return "\n".join(parts)


if __name__ == "__main__":
    sys.exit(main())
