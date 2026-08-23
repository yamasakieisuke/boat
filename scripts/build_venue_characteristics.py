#!/usr/bin/env python3
"""data/venues/venue_characteristics.json を実測から組み立てる。

このファイルは元々手書きで、2026-08-10 の iCloud 事故で消失した。gitignore の
例外指定も無かったため git にも残っていない。`predictor.calc_venue_course_mod()` は
`if not venue: return base` で即座に抜けるため、**会場・季節・潮汐・風の補正が
全部無効化されたまま動いていた**（2026-08-16 に判明）。

手書きの推定値を復元することはできないので、代わりに
`data/results_csv/`（2026-08-16 に修復済み・約76,800レース）の実測から作る。

方針:
  race_no_tendency … 中立(1.0)のまま。効果自体は実測で大きい（late帯のコース1は
                     全国平均比 +15%超）。
                     元の無効化理由は「R9-12 は優勝戦・準優勝戦を多く含み、
                     RACE_TYPE_BONUS["finalist"] と二重計上になる」だったが、
                     **v5.27 (2026-08-23) で RACE_TYPE_BONUS からレース番号の効果を
                     割り戻したので、その理由は解消している**
                     （scripts/calibrate_race_type_bonus.py 参照）。
                     一方で v5.27 の時点ではレース番号の効果がモデルのどこにも
                     入っていない状態でもある。有効化は course_advantage の挙動を
                     大きく変えるうえバックテスト手段が無い（racecards が未完）ため、
                     種別の較正と同時に入れず、切り分けて判断する
  tidal            … venue_config.py の tidal_influence から
  seasonal         … 中立(1.0)。official_course_stats.json が優先されるため
  tidal_conditions … 中立(1.0)。潮汐ラベル別の実測を持っていないため
  wind             … 中立(1.0)。**風向に識別力が無いことが実測で確認済み**
                     （docs/race_development_research.md: 強風時の1号艇1着率は
                       北系52.1% vs 南系52.2%）。推定値を捏造せず無効化する。
                     風は「会場別×風速の連続関数」として別途入れるのが正しい

使い方:
  python3 scripts/build_venue_characteristics.py
  python3 scripts/build_venue_characteristics.py --dry-run
"""
from __future__ import annotations

import csv
import json
import argparse
import collections
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = DATA_DIR / "results_csv"
OUT_FILE = DATA_DIR / "venues" / "venue_characteristics.json"

import sys
sys.path.insert(0, str(Path(__file__).parent))
from venue_config import VENUE_CONFIG

NAME_TO_JCD = {v["name"]: k for k, v in VENUE_CONFIG.items()}

# predictor.get_race_period と同じ区切りにすること
PERIODS = {"early": range(1, 5), "middle": range(5, 9), "late": range(9, 13)}

# 実測が少ない層で極端な補正が出ないようにする
MIN_RACES_PER_CELL = 200
MOD_CLAMP = (0.85, 1.15)


def period_of(race_no: int) -> str:
    for name, rng in PERIODS.items():
        if race_no in rng:
            return name
    return "late"


def collect() -> dict:
    """(jcd, period, course) -> [1着数, 総数] を results_csv から集める。"""
    stat: dict = collections.defaultdict(lambda: [0, 0])
    for path in sorted(RESULTS_DIR.glob("2*.csv")):
        if not path.stem.isdigit():
            continue
        races: dict = {}
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                jcd = NAME_TO_JCD.get(row.get("venue_name", ""))
                if not jcd:
                    continue
                try:
                    rno = int(row["race_no"])
                    waku = int(row["waku"])
                    rank = int(row["rank"])
                except (ValueError, KeyError, TypeError):
                    continue
                if not (1 <= waku <= 6 and 1 <= rank <= 6 and 1 <= rno <= 12):
                    continue
                races.setdefault((jcd, rno), {})[waku] = rank
        for (jcd, rno), wk in races.items():
            if len(wk) < 6:       # 完走6艇そろったレースだけ使う
                continue
            p = period_of(rno)
            for waku, rank in wk.items():
                cell = stat[(jcd, p, waku)]
                cell[1] += 1
                if rank == 1:
                    cell[0] += 1
    return stat


def build_national_tendency(stat: dict) -> dict:
    """レース番号帯 × コースの補正を全24会場プールで作る。

    会場ごとに切ると (会場, 帯, コース) のセルが薄くなり、外枠の1着数が
    数十件しかないためクランプに張り付く＝ほぼノイズになる。レース番号の効果
    自体は全国プールで頑健に出る（docs/race_development_research.md でも
    R2-R4 46.9% / R11-12 69.2% と層別後も 8〜11pt 残ることを確認済み）。
    会場固有の差は official_course_stats.json と _get_venue_win_freq_mod()
    が別途担当するので、ここで二重に持たせない。
    """
    jcds = sorted({k[0] for k in stat})
    overall = {}
    for waku in range(1, 7):
        w = sum(stat[(j, p, waku)][0] for j in jcds for p in PERIODS)
        n = sum(stat[(j, p, waku)][1] for j in jcds for p in PERIODS)
        overall[waku] = (w / n) if n else 0.0

    tendency = {}
    for p in PERIODS:
        mods, ns = [], []
        for waku in range(1, 7):
            w = sum(stat[(j, p, waku)][0] for j in jcds)
            n = sum(stat[(j, p, waku)][1] for j in jcds)
            ns.append(n)
            if n < MIN_RACES_PER_CELL or not overall[waku]:
                mods.append(1.0)
                continue
            m = (w / n) / overall[waku]
            mods.append(round(min(max(m, MOD_CLAMP[0]), MOD_CLAMP[1]), 4))
        tendency[p] = {"course_mod": mods, "n": min(ns)}
    return tendency


def build(stat: dict) -> dict:
    out: dict = {}
    jcds = sorted({k[0] for k in stat})
    measured = build_national_tendency(stat)   # 参考値として _measured に残す
    neutral = {p: {"course_mod": [1.0] * 6} for p in PERIODS}
    for jcd in jcds:
        cfg = VENUE_CONFIG.get(jcd, {})
        out[jcd] = {
            "name": cfg.get("name", jcd),
            "water_type": cfg.get("water_type"),
            "tidal": bool(cfg.get("tidal_influence")),
            "tidal_influence": cfg.get("tidal_influence"),
            "race_no_tendency": neutral,
            # 以下は中立。理由は本ファイル冒頭の docstring を参照
            "seasonal": {s: {"course_mod": [1.0] * 6}
                         for s in ("spring", "summer", "autumn", "winter")},
            "tidal_conditions": {},
            "wind": {"headwind_threshold_ms": 99,   # 事実上の無効化
                     "headwind_course_mod": [1.0] * 6,
                     "tailwind_course_mod": [1.0] * 6},
            "_source": "build_venue_characteristics.py / data/results_csv 実測",
        }
    # 実測値そのものは捨てずに残す（将来 RACE_TYPE_BONUS と整理したときに使う）
    out["_measured_race_no_tendency"] = measured
    out["_default"] = {
        "name": "default",
        "tidal": False,
        "race_no_tendency": {p: {"course_mod": [1.0] * 6} for p in PERIODS},
        "seasonal": {s: {"course_mod": [1.0] * 6}
                     for s in ("spring", "summer", "autumn", "winter")},
        "tidal_conditions": {},
        "wind": {"headwind_threshold_ms": 99,
                 "headwind_course_mod": [1.0] * 6,
                 "tailwind_course_mod": [1.0] * 6},
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stat = collect()
    data = build(stat)
    venues = [k for k in data if not k.startswith("_")]
    print(f"会場数: {len(venues)}")
    t = data["_measured_race_no_tendency"]
    print("レース番号帯 × コース補正（実測・参考値。適用はしない）")
    for p in ("early", "middle", "late"):
        print(f"  {p:6s} n={t[p]['n']:6d} course_mod={t[p]['course_mod']}")
    print("\n潮汐フラグ:")
    print("  ", ", ".join(f"{data[j]['name']}" for j in sorted(venues) if data[j]['tidal']))
    if args.dry_run:
        print("\n--dry-run のため書き込みません")
        return
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n書き込み: {OUT_FILE}")


if __name__ == "__main__":
    main()
