#!/usr/bin/env python3
"""
選手別ページデータ生成スクリプト

results_csv を年度別に walk して各選手の枠別累計成績を集計、
当日 racecard から出走予定を取得して {reg_no}.json を出力する。

出力:
  output/data/players/pages/{reg_no}.json
  output/data/players/pages/index.json    (本日出走予定の選手一覧)
  wordpress/boat-forecast-viewer/data/players/{reg_no}.json (WP配布用 mirror)

Usage:
  python3 scripts/build_player_pages.py             # 本日出走予定の選手のみ
  python3 scripts/build_player_pages.py --all       # master 全選手分生成
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = DATA_DIR / "results_csv"
RACECARD_DIR = DATA_DIR / "racecards"
PLAYERS_DATA_DIR = DATA_DIR / "players"
MASTER_PATH = PLAYERS_DATA_DIR / "master.json"
OUTPUT_DIR = BASE_DIR / "output" / "data" / "players" / "pages"
WP_MIRROR_DIR = BASE_DIR / "wordpress" / "boat-forecast-viewer" / "data" / "players"

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


def aggregate_results_by_player_year_waku() -> dict:
    """results_all.csv を walk して {reg_no: {year: {waku: {total, ranks: [_, n1..n6]}}}}."""
    # results_all.csv は 2026-09-05 に廃止（日別CSVの派生物が古くなっていたため）。
    # この変数は「もし残っていれば使う」程度の意味しか無く、通常は下の
    # 日別CSVスキャンに落ちる。
    csv_path = RESULTS_DIR / "results_all.csv"
    out: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"total": 0, "ranks": [0] * 7})))

    if csv_path.exists():
        sources = [csv_path]
    else:
        # フォールバック: 日次CSV を全部スキャン
        sources = sorted(RESULTS_DIR.glob("[0-9]*.csv"))

    rows_total = 0
    for src in sources:
        try:
            with src.open(encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    reg_no = (row.get("reg_no") or "").strip()
                    if not reg_no:
                        continue
                    date_str = (row.get("date") or "").strip()
                    if len(date_str) < 4:
                        continue
                    try:
                        rank = int(row.get("rank") or 0)
                        waku = int(row.get("waku") or 0)
                    except ValueError:
                        continue
                    if waku < 1 or waku > 6 or rank < 1 or rank > 6:
                        continue
                    year = date_str[:4]
                    bucket = out[reg_no][year][str(waku)]
                    bucket["total"] += 1
                    bucket["ranks"][rank] += 1
                    rows_total += 1
        except Exception as e:
            print(f"  [warn] {src.name}: {e}")
            continue
    print(f"  results 行数: {rows_total} / 選手数(年度ヒットあり): {len(out)}")
    return out


def to_yearly_summary(stats: dict) -> dict:
    """{reg_no: {year: {waku: {races, 1st_pct..6th_pct, top2_pct, top3_pct}}}} に変換。"""
    result: dict = {}
    for reg_no, year_d in stats.items():
        out: dict = {}
        for year, waku_d in year_d.items():
            yy: dict = {}
            for waku, d in waku_d.items():
                n = d["total"]
                ranks = d["ranks"]
                rec = {"races": n}
                if n > 0:
                    rec["1st_pct"] = round(ranks[1] / n * 100, 1)
                    rec["2nd_pct"] = round(ranks[2] / n * 100, 1)
                    rec["3rd_pct"] = round(ranks[3] / n * 100, 1)
                    rec["4th_pct"] = round(ranks[4] / n * 100, 1)
                    rec["5th_pct"] = round(ranks[5] / n * 100, 1)
                    rec["6th_pct"] = round(ranks[6] / n * 100, 1)
                    rec["top2_pct"] = round((ranks[1] + ranks[2]) / n * 100, 1)
                    rec["top3_pct"] = round((ranks[1] + ranks[2] + ranks[3]) / n * 100, 1)
                yy[waku] = rec
            out[year] = yy
        # 年度の合計（全枠を統合した overall）も付与
        for year, yy in out.items():
            total_n = sum(rec.get("races", 0) for rec in yy.values())
            if total_n > 0:
                rsum = [0] * 7
                for waku, rec in yy.items():
                    pass  # rec には ranks が無いので、stats から再構成
                # rebuild from stats
                ranks_year = [0] * 7
                for waku, d in year_d[year].items():
                    for i in range(1, 7):
                        ranks_year[i] += d["ranks"][i]
                yy["all"] = {
                    "races": total_n,
                    "1st_pct": round(ranks_year[1] / total_n * 100, 1),
                    "2nd_pct": round(ranks_year[2] / total_n * 100, 1),
                    "3rd_pct": round(ranks_year[3] / total_n * 100, 1),
                    "4th_pct": round(ranks_year[4] / total_n * 100, 1),
                    "5th_pct": round(ranks_year[5] / total_n * 100, 1),
                    "6th_pct": round(ranks_year[6] / total_n * 100, 1),
                    "top2_pct": round((ranks_year[1] + ranks_year[2]) / total_n * 100, 1),
                    "top3_pct": round((ranks_year[1] + ranks_year[2] + ranks_year[3]) / total_n * 100, 1),
                }
        result[reg_no] = out
    return result


def collect_today_upcoming() -> dict:
    """当日 racecard を walk して {reg_no: [{date, jcd, venue_name, race_no, waku, series_races}]}."""
    today = datetime.date.today().strftime("%Y%m%d")
    target = RACECARD_DIR / today
    if not target.exists():
        print(f"  [info] 当日 racecard ディレクトリなし: {target}")
        return {}
    out: dict = defaultdict(list)
    file_count = 0
    for path in sorted(target.glob("*.json")):
        stem = path.stem  # "01_R12" 等
        try:
            jcd, rpart = stem.split("_R")
            race_no = int(rpart)
        except Exception:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        file_count += 1
        for racer in data.get("racers", []) or []:
            reg_no = str(racer.get("reg_no") or "").strip()
            waku = racer.get("waku")
            if not reg_no or not waku:
                continue
            try:
                waku_i = int(waku)
            except (ValueError, TypeError):
                continue
            out[reg_no].append({
                "date": today,
                "jcd": jcd,
                "venue_name": VENUE_NAMES.get(jcd, jcd),
                "race_no": race_no,
                "waku": waku_i,
                "series_races": racer.get("series_races", []) or [],
                "race_name": data.get("race_name") or "",
                "grade": racer.get("grade") or "",
            })
    print(f"  当日 racecard 走査: {file_count} files / 出走選手数: {len(out)}")
    return out


def main():
    parser = argparse.ArgumentParser(description="選手別ページデータ生成")
    parser.add_argument("--all", action="store_true",
                        help="出走予定なくても master 全選手分を生成（重い）")
    args = parser.parse_args()

    print("=" * 60)
    print("  選手別ページデータ生成")
    print("=" * 60)

    # ── master 読込 ────────────────────────────────────────
    print("\n[1/4] master.json 読込")
    master_full = json.loads(MASTER_PATH.read_text(encoding="utf-8")) if MASTER_PATH.exists() else {}
    master = master_full.get("players", master_full)
    if "players" not in master_full and not isinstance(master, dict):
        master = {}
    print(f"  master 選手数: {len(master)}")

    # ── 年度別累計集計 ─────────────────────────────────────
    print("\n[2/4] results_csv 集計（年度×枠別）")
    raw_stats = aggregate_results_by_player_year_waku()
    yearly = to_yearly_summary(raw_stats)

    # ── 当日出走予定 ─────────────────────────────────────────
    print("\n[3/4] 当日出走予定取得")
    upcoming = collect_today_upcoming()

    # ── 出力 ──────────────────────────────────────────────
    print("\n[4/4] {reg_no}.json 書き出し")
    if args.all:
        target_reg_nos = set(master.keys()) | set(yearly.keys()) | set(upcoming.keys())
    else:
        target_reg_nos = set(upcoming.keys())
        # 出走予定なくても、last_modified が新しい選手は更新したい等の拡張余地あり

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WP_MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for reg_no in sorted(target_reg_nos):
        m = master.get(reg_no, {}) if isinstance(master, dict) else {}
        page = {
            "reg_no": reg_no,
            "name": m.get("name_kanji") or m.get("name") or "",
            "name_kana": m.get("name_kana", ""),
            "grade": m.get("grade", ""),
            "branch": m.get("branch", ""),
            "prefecture": m.get("prefecture", ""),
            "win_rate": m.get("win_rate"),
            "championship_count": m.get("championship_count"),
            "ability_index": m.get("ability_index"),
            "gender": m.get("gender", "M"),
            "yearly_waku_stats": yearly.get(reg_no, {}),
            "upcoming_today": upcoming.get(reg_no, []),
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        text = json.dumps(page, ensure_ascii=False, indent=2)
        (OUTPUT_DIR / f"{reg_no}.json").write_text(text, encoding="utf-8")
        (WP_MIRROR_DIR / f"{reg_no}.json").write_text(text, encoding="utf-8")
        written += 1

    # ── index.json (本日出走予定の選手一覧) ────────────────
    today_index = []
    for reg_no in sorted(upcoming.keys()):
        m = master.get(reg_no, {}) if isinstance(master, dict) else {}
        races = upcoming[reg_no]
        venues = sorted({r["venue_name"] for r in races})
        today_index.append({
            "reg_no": reg_no,
            "name": m.get("name_kanji") or m.get("name") or "",
            "name_kana": m.get("name_kana", ""),
            "grade": m.get("grade", ""),
            "branch": m.get("branch", ""),
            "venues": venues,
            "races_today": len(races),
        })
    today_index.sort(key=lambda x: (x.get("name_kana") or "", x.get("reg_no") or ""))
    idx = {
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "today_count": len(today_index),
        "today_players": today_index,
    }
    idx_text = json.dumps(idx, ensure_ascii=False, indent=2)
    (OUTPUT_DIR / "index.json").write_text(idx_text, encoding="utf-8")
    (WP_MIRROR_DIR / "index.json").write_text(idx_text, encoding="utf-8")

    print(f"\n  💾 {written} 件の選手ページを書き出し")
    print(f"  💾 出力先:    {OUTPUT_DIR}")
    print(f"  💾 WPミラー:  {WP_MIRROR_DIR}")
    print(f"  💾 index.json (本日 {len(today_index)} 名)")


if __name__ == "__main__":
    main()
