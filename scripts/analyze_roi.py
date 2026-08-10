#!/usr/bin/env python3
"""生き残った output/wordpress/*/*_payload.json（予想）× data/results_csv（結果）で
的中率と回収率を再集計する。verify.py が計測していない ROI を出すのが主目的。"""
from __future__ import annotations
import csv, json, glob, collections, statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RES = BASE / "data" / "results_csv"

# ---- 結果CSVを (date, venue_name, race_no) -> {won3, pay, pop} に畳む
results: dict[tuple, dict] = {}
for p in sorted(RES.glob("*.csv")):
    with open(p, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["date"], row["venue_name"], str(int(row["race_no"] or 0)))
            if key in results:
                continue
            won3 = (row.get("won3") or "").strip()
            if not won3 or won3.count("-") != 2:
                continue
            def num(x):
                try: return int(str(x).replace(",", "") or 0)
                except ValueError: return 0
            results[key] = {
                "won3": won3,
                "pay": num(row.get("won3_pay")),
                "pop": num(row.get("won3_pop")),
                "trio": (row.get("trio") or "").strip(),
                "trio_pay": num(row.get("trio_pay")),
                "won2": (row.get("won2") or "").strip(),
                "won2_pay": num(row.get("won2_pay")),
            }

TIERS = [("main", "main_bets", "本命"), ("sub", "sub_bets", "その他"),
         ("cover", "cover_bets", "抑え"), ("longshot", "longshot_bets", "穴")]

rows = []
missing = 0
for f in sorted(glob.glob(str(BASE / "output/wordpress/*/*_payload.json"))):
    d = json.load(open(f))
    fp = json.loads(d["acf"]["forecast_payload"])
    date = fp["date"].replace("-", "")
    venue = fp["venue_name"]
    for r in fp.get("races", []):
        key = (date, venue, str(int(r.get("race_no") or 0)))
        act = results.get(key)
        if not act:
            missing += 1
            continue
        combos = {}
        for tier, field, _ in TIERS:
            combos[tier] = [b.get("combo") for b in (r.get(field) or []) if b.get("combo")]
        allc = [c for t in combos.values() for c in t]
        rows.append({
            "date": date, "venue": venue, "race_no": key[2],
            "conf": r.get("confidence"), "is_rough": bool(r.get("is_rough")),
            "won3": act["won3"], "pay": act["pay"], "pop": act["pop"],
            "combos": combos, "n_bets": len(allc),
            "hit_any": act["won3"] in allc,
            "hit_tier": {t: (act["won3"] in combos[t]) for t, _, _ in TIERS},
            "head_hit": bool(allc) and allc[0].split("-")[0] == act["won3"].split("-")[0],
            "ret": act["pay"] if act["won3"] in allc else 0,
        })

def agg(sub, label):
    n = len(sub)
    if not n:
        return None
    bets = sum(x["n_bets"] for x in sub)
    ret = sum(x["ret"] for x in sub)
    hits = sum(1 for x in sub if x["hit_any"])
    pays = [x["pay"] for x in sub if x["hit_any"]]
    return {
        "label": label, "races": n, "bets": bets,
        "hit_pct": round(hits / n * 100, 1),
        "head_pct": round(sum(1 for x in sub if x["head_hit"]) / n * 100, 1),
        "roi": round(ret / (bets * 100) * 100, 1) if bets else 0.0,
        "stake": bets * 100, "ret": ret,
        "med_pay": int(statistics.median(pays)) if pays else 0,
        "max_pay": max(pays) if pays else 0,
        "bets_per_race": round(bets / n, 1),
        **{f"hit_{t}": round(sum(1 for x in sub if x["hit_tier"][t]) / n * 100, 1)
           for t, _, _ in TIERS},
    }

def tier_roi(sub, tier):
    bets = sum(len(x["combos"][tier]) for x in sub)
    ret = sum(x["pay"] for x in sub if x["hit_tier"][tier])
    return (round(ret / (bets * 100) * 100, 1) if bets else 0.0, bets)

print(f"# 対象レース {len(rows)}R / 結果欠損 {missing}R / 期間 "
      f"{min(r['date'] for r in rows)}〜{max(r['date'] for r in rows)}")
o = agg(rows, "全体")
print("\n## 全体")
for k, v in o.items():
    print(f"  {k}: {v}")

print("\n## 買い目タイプ別 ROI（100円/点）")
for t, _, jp in TIERS:
    roi, bets = tier_roi(rows, t)
    hit = round(sum(1 for x in rows if x["hit_tier"][t]) / len(rows) * 100, 1)
    print(f"  {jp:4s} 点数{bets:6d}  的中率{hit:5.1f}%  回収率{roi:6.1f}%")

print("\n## 月別")
for m in sorted({r["date"][:6] for r in rows}):
    a = agg([r for r in rows if r["date"][:6] == m], m)
    print(f"  {m} R{a['races']:5d} 的中{a['hit_pct']:5.1f}% 頭{a['head_pct']:5.1f}% 回収{a['roi']:6.1f}%")

print("\n## 会場別（レース数順 上位15）")
by_v = collections.Counter(r["venue"] for r in rows)
for v, _ in by_v.most_common(15):
    a = agg([r for r in rows if r["venue"] == v], v)
    print(f"  {v:5s} R{a['races']:5d} 的中{a['hit_pct']:5.1f}% 頭{a['head_pct']:5.1f}% "
          f"回収{a['roi']:6.1f}% 中央配当{a['med_pay']:6d}")

print("\n## confidence 帯別")
bands = [(0, 50), (50, 60), (60, 70), (70, 80), (80, 101)]
for lo, hi in bands:
    sub = [r for r in rows if r["conf"] is not None and lo <= r["conf"] < hi]
    a = agg(sub, f"{lo}-{hi}")
    if a:
        print(f"  conf {lo:3d}-{hi:3d} R{a['races']:5d} 的中{a['hit_pct']:5.1f}% "
              f"回収{a['roi']:6.1f}% 点数/R{a['bets_per_race']:4.1f}")

print("\n## 波乱判定(is_rough)別")
for flag in (False, True):
    a = agg([r for r in rows if r["is_rough"] == flag], str(flag))
    if a:
        print(f"  is_rough={flag!s:5s} R{a['races']:5d} 的中{a['hit_pct']:5.1f}% "
              f"回収{a['roi']:6.1f}% 中央配当{a['med_pay']:6d}")

print("\n## 的中レースの人気分布")
pops = sorted(r["pop"] for r in rows if r["hit_any"] and r["pop"])
allpops = sorted(r["pop"] for r in rows if r["pop"])
print(f"  的中時 中央人気 {statistics.median(pops):.0f} / 全レース中央人気 {statistics.median(allpops):.0f}")
for lo, hi in [(1, 3), (4, 10), (11, 30), (31, 121)]:
    sub = [r for r in rows if r["pop"] and lo <= r["pop"] <= hi]
    if sub:
        a = agg(sub, "")
        print(f"  実績{lo:3d}-{hi:3d}番人気 R{a['races']:5d} 的中{a['hit_pct']:5.1f}% 回収{a['roi']:6.1f}%")
