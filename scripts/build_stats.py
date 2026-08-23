#!/usr/bin/env python3
"""
build_stats.py  —  過去CSV → 選手・モーター統計JSONを生成

生成するデータ:
  data/players/{reg_no}.json へ以下をマージ:
    hist_global_waku_stats  : 全国・枠別着順割合（1〜6着%）
    hist_local_waku_stats   : 当地・枠別着順割合（福岡のみ）
    hist_global_win_rate    : 全国1着率（実績）
    hist_local_win_rate     : 当地1着率（実績）
    hist_avg_st             : 全CSVから集計した平均ST
    hist_exhibition         : 展示タイム集計 {overall_avg, count, by_venue, recent_avg, recent_deviation}
    hist_motor_stats        : {motor_no: {win_rate, 2rate, races}}

  data/motors/{motor_no}.json:
    motor_no, venue_code, races, win_rate, top2_rate, top3_rate, last_date

使い方:
  python scripts/build_stats.py            # 全会場
  python scripts/build_stats.py --jcd 22  # 福岡のみローカル統計を更新
"""

import csv
import json
import argparse
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_DIR  = DATA_DIR / "results_csv"

VENUE_CODE_MAP = {
    "桐生":"01","戸田":"02","江戸川":"03","平和島":"04","多摩川":"05",
    "浜名湖":"06","蒲郡":"07","常滑":"08","津":"09","三国":"10",
    "びわこ":"11","住之江":"12","尼崎":"13","鳴門":"14","丸亀":"15",
    "児島":"16","宮島":"17","徳山":"18","下関":"19","若松":"20",
    "芦屋":"21","福岡":"22","唐津":"23","大村":"24",
}

def load_all_csvs(venue_filter: str = "") -> list[dict]:
    """全CSVを読み込む。venue_filter が指定されれば会場名で絞り込む"""
    records = []
    for p in sorted(CSV_DIR.glob("????????.csv")):
        try:
            with open(p, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if venue_filter and venue_filter not in row.get("venue_name",""):
                        continue
                    records.append(row)
        except Exception as e:
            print(f"[WARN] {p.name}: {e}")
    return records

def safe_int(v, default=0):
    try:
        return int(v) if v and v.strip() else default
    except:
        return default

def safe_float(v, default=0.0):
    try:
        return float(v) if v and v.strip() else default
    except:
        return default

def compute_waku_stats(rows_for_player: list[dict]) -> dict:
    """
    枠別 着順分布を計算する
    戻り値例:
      {
        "1": {"races":10, "1st%":60.0, "2nd%":20.0, "3rd%":10.0, "4th+%":10.0},
        "2": {...},
        ...
      }
    """
    by_waku = defaultdict(lambda: defaultdict(int))
    for row in rows_for_player:
        waku = row.get("waku","").strip()
        rank = row.get("rank","").strip()
        if not waku.isdigit() or not rank.isdigit():
            continue
        w = int(waku)
        r = int(rank)
        if 1 <= w <= 6 and 1 <= r <= 6:
            by_waku[w]["total"] += 1
            by_waku[w][r]       += 1

    result = {}
    for w in range(1, 7):
        s = by_waku[w]
        total = s.get("total", 0)
        if total == 0:
            continue
        result[str(w)] = {
            "races":    total,
            "1st_pct":  round(s.get(1,0)/total*100, 1),
            "2nd_pct":  round(s.get(2,0)/total*100, 1),
            "3rd_pct":  round(s.get(3,0)/total*100, 1),
            "4th_pct":  round(s.get(4,0)/total*100, 1),
            "5th_pct":  round(s.get(5,0)/total*100, 1),
            "6th_pct":  round(s.get(6,0)/total*100, 1),
            "top2_pct": round((s.get(1,0)+s.get(2,0))/total*100, 1),
            "top3_pct": round((s.get(1,0)+s.get(2,0)+s.get(3,0))/total*100, 1),
        }
    return result

# 非完走艇の着順コード（D-9 で拾えるようにした行）。
# F/L/S は「出走した」ので分母に数える。K0/K1（欠場）は出走していないので除外する。
ABSENT_RANK_CODES = {"K0", "K1"}


def started_rows(rows: list[dict]) -> list[dict]:
    """出走した行だけを返す（欠場を除く）。勝率の分母に使う。"""
    return [r for r in rows if (r.get("rank") or "").strip() not in ABSENT_RANK_CODES]


def compute_st_stats(rows_for_player: list[dict]) -> dict:
    """平均STを集計（course_enter 別）"""
    sts = []
    course_sts = defaultdict(list)
    for row in rows_for_player:
        st = row.get("st_timing","").strip()
        ce = row.get("course_enter","").strip()
        if re.match(r"^[0-9.]+$", st):
            val = float(st)
            if 0.0 <= val <= 0.5:
                sts.append(val)
                if ce.isdigit():
                    course_sts[int(ce)].append(val)
    result = {}
    if sts:
        result["avg_st"]    = round(sum(sts)/len(sts), 3)
        result["st_count"]  = len(sts)
    if course_sts:
        result["course_st"] = {
            str(k): round(sum(v)/len(v), 3)
            for k, v in sorted(course_sts.items())
        }
    return result


def compute_exhibition_stats(rows_for_player: list[dict], recent_n: int = 20) -> dict:
    """
    展示タイム（exhibition_time）の集計。
      overall_avg : 全期間・全会場の平均
      count       : 有効サンプル数
      by_venue    : {jcd: {avg, count}}
      recent_avg  : 直近 recent_n 走の平均
      recent_deviation : 直近走の「会場平均からの偏差」平均（負=会場平均より速い）
    """
    samples = []  # [(date, jcd, val)]
    for row in rows_for_player:
        et = row.get("exhibition_time","").strip()
        if not re.match(r"^\d+\.\d+$", et):
            continue
        try:
            val = float(et)
        except ValueError:
            continue
        if not (5.5 <= val <= 8.5):
            continue
        jcd = VENUE_CODE_MAP.get(row.get("venue_name","").strip(), "")
        date = row.get("date","").strip()
        samples.append((date, jcd, val))

    if not samples:
        return {}

    samples.sort(key=lambda x: x[0])
    vals = [v for _,_,v in samples]
    by_venue: dict[str, list[float]] = defaultdict(list)
    for _, j, v in samples:
        if j:
            by_venue[j].append(v)

    result = {
        "overall_avg": round(sum(vals)/len(vals), 2),
        "count": len(vals),
        "by_venue": {
            j: {"avg": round(sum(v)/len(v), 2), "count": len(v)}
            for j, v in by_venue.items()
        },
    }

    recent = samples[-recent_n:]
    if recent:
        rvals = [v for _,_,v in recent]
        result["recent_avg"] = round(sum(rvals)/len(rvals), 2)
        result["recent_count"] = len(rvals)
        deviations = []
        for _, j, v in recent:
            base = sum(by_venue[j]) / len(by_venue[j]) if j and by_venue.get(j) else None
            if base is not None:
                deviations.append(v - base)
        if deviations:
            result["recent_deviation"] = round(sum(deviations)/len(deviations), 3)

    return result

def build_player_stats(all_rows: list[dict], local_rows: list[dict], local_jcd: str):
    """全選手の統計をplayers/フォルダに保存（既存データへマージ）"""
    # reg_no でグルーピング
    by_reg_all   = defaultdict(list)
    by_reg_local = defaultdict(list)

    for row in all_rows:
        reg = row.get("reg_no","").strip()
        if reg:
            by_reg_all[reg].append(row)

    for row in local_rows:
        reg = row.get("reg_no","").strip()
        if reg:
            by_reg_local[reg].append(row)

    all_regs = set(by_reg_all.keys()) | set(by_reg_local.keys())
    print(f"選手数: 全国={len(by_reg_all)}  当地={len(by_reg_local)}  合計={len(all_regs)}")

    save_dir = DATA_DIR / "players"
    save_dir.mkdir(parents=True, exist_ok=True)

    for reg in sorted(all_regs):
        # 既存JSONを読み込み
        existing_path = save_dir / f"{reg}.json"
        existing = {}
        if existing_path.exists():
            with open(existing_path, encoding="utf-8") as f:
                existing = json.load(f)

        g_rows = by_reg_all.get(reg, [])
        l_rows = by_reg_local.get(reg, [])

        # 全国統計
        if g_rows:
            existing["hist_global_waku_stats"] = compute_waku_stats(g_rows)
            g_started = started_rows(g_rows)
            existing["hist_global_win_rate"]   = round(
                sum(1 for r in g_started if r.get("rank","").strip() == "1")
                / max(len(g_started), 1) * 100, 2
            )
            st_info = compute_st_stats(g_rows)
            if st_info:
                existing["hist_avg_st"] = st_info
            ex_info = compute_exhibition_stats(g_rows)
            if ex_info:
                existing["hist_exhibition"] = ex_info

        # 当地統計
        if l_rows:
            existing["hist_local_waku_stats"]  = compute_waku_stats(l_rows)
            l_started = started_rows(l_rows)
            existing["hist_local_win_rate"]    = round(
                sum(1 for r in l_started if r.get("rank","").strip() == "1")
                / max(len(l_started), 1) * 100, 2
            )

        with open(existing_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"選手統計を {save_dir} に保存しました")

def build_top1_followers(all_rows: list[dict]) -> None:
    """
    v5.23: 会場別 1着waku別 の2-3着連動テーブルを生成。
    出力: data/venues/stats/top1_followers.json
    """
    from collections import Counter
    by_race: dict = defaultdict(dict)
    for r in all_rows:
        try:
            rank = int(r.get("rank", "") or 0)
            waku = int(r.get("waku", "") or 0)
        except ValueError:
            continue
        if rank not in (1, 2, 3) or waku not in range(1, 7):
            continue
        jcd = VENUE_CODE_MAP.get(r.get("venue_name", "").strip(), "")
        if not jcd:
            continue
        key = (r.get("date", ""), jcd, r.get("race_no", ""))
        by_race[key][rank] = waku

    agg: dict = defaultdict(lambda: {"n": 0, "w2": Counter(), "w3": Counter(), "combo": Counter()})
    for (_, jcd, _), ranks in by_race.items():
        if 1 in ranks and 2 in ranks and 3 in ranks:
            w1, w2, w3 = ranks[1], ranks[2], ranks[3]
            a = agg[(jcd, w1)]
            a["n"] += 1
            a["w2"][w2] += 1
            a["w3"][w3] += 1
            a["combo"][(w2, w3)] += 1

    out: dict = {}
    jcd_names = {v: k for k, v in VENUE_CODE_MAP.items()}
    for (jcd, w1), data in agg.items():
        n = data["n"]
        if n < 5:
            continue
        venue_dict = out.setdefault(jcd, {"name": jcd_names.get(jcd, ""), "by_winner": {}})
        venue_dict["by_winner"][str(w1)] = {
            "n": n,
            "w2_dist": {str(w): round(c / n, 3) for w, c in data["w2"].most_common()},
            "w3_dist": {str(w): round(c / n, 3) for w, c in data["w3"].most_common()},
            "top_combos": [
                {"combo": f"{w1}-{w2}-{w3}", "count": c, "pct": round(c / n, 3)}
                for (w2, w3), c in data["combo"].most_common(5)
            ],
        }

    stats_dir = DATA_DIR / "venues" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    out_path = stats_dir / "top1_followers.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"連動テーブル: {len(out)}会場 → {out_path}")


def build_motor_stats(local_rows: list[dict], jcd: str):
    """モーター統計を motors/ フォルダに保存"""
    by_motor = defaultdict(list)
    for row in local_rows:
        mo = row.get("motor_no","").strip()
        if mo:
            by_motor[mo].append(row)

    save_dir = DATA_DIR / "motors"
    save_dir.mkdir(parents=True, exist_ok=True)

    for motor_no, rows in by_motor.items():
        rows  = started_rows(rows)   # 欠場は出走に数えない
        total = len(rows)
        if total == 0:
            continue
        win   = sum(1 for r in rows if r.get("rank","").strip() == "1")
        top2  = sum(1 for r in rows if r.get("rank","").strip() in ("1","2"))
        top3  = sum(1 for r in rows if r.get("rank","").strip() in ("1","2","3"))
        dates = sorted(r.get("date","") for r in rows if r.get("date"))
        data = {
            "motor_no":   motor_no,
            "venue_code": jcd,
            "races":      total,
            "win_rate":   round(win /total*100, 1),
            "top2_rate":  round(top2/total*100, 1),
            "top3_rate":  round(top3/total*100, 1),
            "first_date": dates[0]  if dates else "",
            "last_date":  dates[-1] if dates else "",
        }
        out = save_dir / f"{jcd}_{motor_no}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"モーター統計 {len(by_motor)}件を {save_dir} に保存しました")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jcd", default="22", help="当地会場コード（デフォルト=22 福岡）")
    ap.add_argument("--no-global", action="store_true", help="全国統計をスキップ（高速化）")
    args = ap.parse_args()

    venue_name = {v: k for k, v in VENUE_CODE_MAP.items()}.get(args.jcd, "")
    print(f"=== 統計ビルド: 当地会場={args.jcd}({venue_name}) ===\n")

    print("当地CSVを読み込み中...")
    local_rows = load_all_csvs(venue_filter=venue_name)
    print(f"  当地レコード数: {len(local_rows)}")

    if not args.no_global and not args.jcd:
        print("全国CSVを読み込み中...")
        all_rows = load_all_csvs()
        print(f"  全国レコード数: {len(all_rows)}")
    elif not args.no_global:
        print("全国CSVを読み込み中（全会場）...")
        all_rows = load_all_csvs()
        print(f"  全国レコード数: {len(all_rows)}")
    else:
        all_rows = local_rows

    print("\n選手統計を構築中...")
    build_player_stats(all_rows, local_rows, args.jcd)

    print("\nモーター統計を構築中...")
    build_motor_stats(local_rows, args.jcd)

    if not args.no_global:
        print("\n会場別連動テーブルを構築中（v5.23）...")
        build_top1_followers(all_rows)

    print("\n=== 完了 ===")

if __name__ == "__main__":
    main()
