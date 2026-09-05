#!/usr/bin/env python3
"""Boatrace Open API から出走表を取り込む（スクレイピングの代替）。

## なぜ

scrape_racecard は1レースずつ boatrace.jp を叩くため 12.9秒/件かかる。
このAPIは**1日1リクエストで全24会場・全レース**が返る（約1.4MB）。
残り5,890件のバックフィルが、数十リクエストで終わる。

## 出典と注意

  https://boatraceopenapi.github.io/api/v1/{YYYY}/{YYYYMMDD}.json

**有志の非公式プロジェクト**（MIT / 正確性の保証なし）。同 organization の
results / programs / previews は既に Deprecated で、現役は api のみ。
**2026-01-01 以降しか無い**ので、それ以前はスクレイピングが要る。

依存先としては公式サイトより不安定なので、
  - 取り込んだ値は既存のスクレイプ結果と突き合わせて検証してから使う
  - 取得済みファイルは上書きしない（--overwrite で明示）
という方針にする。実際 20260320 の1レースで全12項目が一致することを確認済み
（名前の全角スペースの差のみ）。

## 取り込まないもの

series_ranks / series_races（節間成績）は API に無い。scrape_racecard は
これを持つので、**API 由来のファイルには空配列が入る**。predictor の
series_score はその分だけ効かなくなる。バックテスト用途では許容し、
当日の予想は従来どおりスクレイプを使う。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
RACECARDS = BASE_DIR / "data" / "racecards"
API = "https://boatraceopenapi.github.io/api/v1/{y}/{d}.json"
UA = {"User-Agent": "boat-import/1.0 (personal backtest data; contact: ask11nl@gmail.com)"}
GRADE_FALLBACK = "B1"


def to_racecard(date: str, jcd: str, rno: int, race: dict) -> dict:
    racers = []
    for k in sorted(race.get("racers", {}), key=lambda x: int(x)):
        a = race["racers"][k]
        racers.append({
            "waku": int(a.get("entry_number") or k),
            "name": (a.get("name") or "").strip(),
            "reg_no": str(a.get("number") or ""),
            "grade": a.get("rank_number_source") or GRADE_FALLBACK,
            "avg_st": a.get("average_start_timing"),
            "f_count": a.get("flying_count") or 0,
            "l_count": a.get("late_count") or 0,
            "global_win": a.get("national_win_rate"),
            "global_2win": a.get("national_top_2_percent"),
            "global_3win": a.get("national_top_3_percent"),
            "local_win": a.get("local_win_rate"),
            "local_2win": a.get("local_top_2_percent"),
            "local_3win": a.get("local_top_3_percent"),
            "motor_no": str(a.get("motor_number") or ""),
            "motor_2rate": a.get("motor_top_2_percent"),
            "motor_3rate": a.get("motor_top_3_percent"),
            "boat_no": str(a.get("boat_number") or ""),
            "boat_2rate": a.get("boat_top_2_percent"),
            # API に無い。scrape_racecard 由来のファイルとの違いを明示する
            "series_ranks": [],
            "series_races": [],
        })
    return {
        "venue_code": jcd,
        "date": date,
        "race_no": rno,
        "race_name": (race.get("subtitle") or "").strip(),
        "tournament_grade": race.get("grade_number_source") or "",
        "racers": racers,
        "_source": "boatraceopenapi/api v1",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--overwrite", action="store_true",
                    help="既存ファイルも上書きする（既定は取得済みを尊重）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import datetime
    d0 = datetime.datetime.strptime(args.date_from, "%Y%m%d").date()
    d1 = datetime.datetime.strptime(args.date_to, "%Y%m%d").date()
    if d0 < datetime.date(2026, 1, 1):
        print("[WARN] このAPIは 2026-01-01 以降のみ。それ以前はスクレイピングが要る")

    wrote = skipped = missing = 0
    d = d0
    while d <= d1:
        ds = d.strftime("%Y%m%d")
        url = API.format(y=ds[:4], d=ds)
        try:
            r = requests.get(url, timeout=40, headers=UA)
        except Exception as e:
            print(f"  {ds}: 取得失敗 {e}")
            d += datetime.timedelta(days=1)
            continue
        if r.status_code != 200:
            print(f"  {ds}: HTTP {r.status_code}（開催なし or 未提供）")
            missing += 1
            d += datetime.timedelta(days=1)
            time.sleep(args.sleep)
            continue
        stadiums = (r.json().get("programs") or {}).get("stadiums") or {}
        w = s = 0
        for jcd_raw, st in stadiums.items():
            jcd = f"{int(jcd_raw):02d}"
            for rno_raw, race in (st.get("races") or {}).items():
                rno = int(rno_raw)
                p = RACECARDS / ds / f"{jcd}_R{rno:02d}.json"
                if p.exists() and not args.overwrite:
                    s += 1
                    continue
                if not args.dry_run:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(to_racecard(ds, jcd, rno, race),
                                            ensure_ascii=False, indent=2), encoding="utf-8")
                w += 1
        wrote += w
        skipped += s
        print(f"  {ds}: {len(stadiums)}会場 / 新規{w} スキップ{s}")
        d += datetime.timedelta(days=1)
        time.sleep(args.sleep)

    print(f"\n{'DRY-RUN ' if args.dry_run else ''}完了: 新規 {wrote:,} / 既存スキップ {skipped:,} "
          f"/ 未提供 {missing}日")
    return 0


if __name__ == "__main__":
    sys.exit(main())
