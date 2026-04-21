from __future__ import annotations

"""
analyze_combo_freq.py  ── 会場別 出目確率テーブルを構築する

【何を計算するか】
  1. win_freq[waku]
       各枠が1着になる確率（全レース集計）
  2. cond_2nd[first][second]
       first枠が1着のとき、second枠が2着になる確率
       → "4が1着のとき5が2着に来やすいか" などを数値化
  3. cond_3rd[first][second][third]
       first-second の順で来たとき、third が3着になる確率
  4. top_combos
       3連単の出現頻度トップ20
  5. upset_1st_freq[waku]
       1〜3枠以外（外枠）が1着になる頻度（荒れ指標）

【出力】
  data/stats/{jcd}_combo_freq.json  （会場ごと）
  data/stats/_all_combo_freq.json   （全会場合計）

【使用例（predictor.py から）】
  from analyze_combo_freq import load_combo_stats
  stats = load_combo_stats("19")  # 下関
  # stats["cond_2nd"]["4"]["5"] = 0.38  → 4が1着のとき5が2着38%
"""

import csv
import json
import glob
import argparse
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR  = Path(__file__).parent.parent
CSV_DIR   = BASE_DIR / "data" / "results_csv"
STATS_DIR = BASE_DIR / "data" / "stats"

# 会場名 → 会場コードのマッピング
try:
    from venue_config import VENUE_CONFIG
    NAME_TO_JCD = {v["name"]: k for k, v in VENUE_CONFIG.items()}
except ImportError:
    NAME_TO_JCD = {}


def _month_to_season(month: str) -> str:
    """'202604' → 'spring' などに変換"""
    try:
        m = int(month[-2:])
    except Exception:
        return "unknown"
    if 3 <= m <= 5: return "spring"
    if 6 <= m <= 8: return "summer"
    if 9 <= m <= 11: return "autumn"
    return "winter"


def _race_no_to_period(race_no: int) -> str:
    if race_no <= 4:  return "early"   # 1-4R
    if race_no <= 8:  return "middle"  # 5-8R
    return "late"                       # 9-12R


def _race_type_to_stage(race_type: str) -> str:
    """
    race_type 列の文字列からレース種別（stage）を判定する。
    results_csv にはグレード情報が無いので、選手のやる気レベルが近い
    以下4分類に正規化する:

      優勝戦  — 優勝戦・ドリーム・SG決勝など、真剣度最高
      準優勝  — 準優勝戦、選抜戦、予選特選、特選、記者選抜、特別選抜
      予選    — 予選、予選特賞、予選特選、一般予選
      一般    — それ以外（通常節のランチタイム枠、企画レースなど）
    """
    if not race_type:
        return "一般"
    rt = race_type
    if "優勝戦" in rt and "準" not in rt:
        return "優勝戦"
    if "ドリーム" in rt:
        return "優勝戦"
    if "準優勝" in rt:
        return "準優勝"
    if "特選" in rt or "選抜" in rt or "特賞" in rt or "特別" in rt:
        return "準優勝"  # 準決相当の準ビッグ戦
    if "予選" in rt:
        return "予選"
    return "一般"


def _build_stats(races: list[dict]) -> dict:
    """
    races: [{"first": "1", "second": "2", "third": "3"}, ...]
    from the won3 field
    """
    total = len(races)
    if total == 0:
        return {}

    # 1着頻度
    win_cnt = Counter(r["first"] for r in races)
    win_freq = {k: round(v / total, 4) for k, v in win_cnt.items()}

    # 2着条件付き確率
    cond_2nd_cnt: dict[str, Counter] = defaultdict(Counter)
    for r in races:
        cond_2nd_cnt[r["first"]][r["second"]] += 1

    cond_2nd = {}
    for first, cnt in cond_2nd_cnt.items():
        denom = win_cnt[first]
        cond_2nd[first] = {
            sec: round(c / denom, 4)
            for sec, c in sorted(cnt.items(), key=lambda x: -x[1])
        }

    # 3着条件付き確率
    cond_3rd_cnt: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for r in races:
        cond_3rd_cnt[r["first"]][r["second"]][r["third"]] += 1

    cond_3rd = {}
    for first, sec_dict in cond_3rd_cnt.items():
        cond_3rd[first] = {}
        for second, cnt in sec_dict.items():
            denom = sum(cnt.values())
            cond_3rd[first][second] = {
                trd: round(c / denom, 4)
                for trd, c in sorted(cnt.items(), key=lambda x: -x[1])
            }

    # トップ20出目（頻度ベース）
    combo_cnt = Counter(f"{r['first']}-{r['second']}-{r['third']}" for r in races)
    top_combos = [
        {"combo": combo, "count": cnt, "freq": round(cnt / total, 4)}
        for combo, cnt in combo_cnt.most_common(20)
    ]

    # v5.15 段階3: 期待値ベース top_combos（頻度×平均払戻）
    # won3_pay は「円」単位の生払戻（100円ベース）。期待値は頻度×平均払戻で計算する。
    pay_sum: dict[str, float] = defaultdict(float)
    pay_cnt: dict[str, int] = defaultdict(int)
    for r in races:
        combo = f"{r['first']}-{r['second']}-{r['third']}"
        pay = r.get("won3_pay", 0) or 0
        try:
            pay_f = float(pay)
        except Exception:
            continue
        if pay_f <= 0:
            continue
        pay_sum[combo] += pay_f
        pay_cnt[combo] += 1

    ev_combos = []
    for combo, cnt in combo_cnt.most_common():
        if cnt < 3:  # サンプル少なすぎる出目はスキップ
            continue
        if combo not in pay_sum:
            continue
        avg_pay = pay_sum[combo] / pay_cnt[combo]
        freq = cnt / total
        # EV = freq × avg_pay / 100（100円購入あたりの期待払戻）
        ev = freq * avg_pay / 100.0
        ev_combos.append({
            "combo":    combo,
            "count":    cnt,
            "freq":     round(freq, 4),
            "avg_pay":  round(avg_pay, 0),
            "ev":       round(ev, 3),  # 1.00 超 = 回収率プラス
        })
    ev_combos.sort(key=lambda x: x["ev"], reverse=True)
    ev_top_combos = ev_combos[:20]

    # 外枠（4〜6）が1着になる割合
    outer_1st = sum(win_cnt.get(str(w), 0) for w in range(4, 7))
    upset_freq = round(outer_1st / total, 4)

    # 枠別 "まくり連れ出し" パターン
    # 外枠が1着のとき、誰が一番多く2着に来るか
    outer_companion = {}
    for w in ["4", "5", "6"]:
        if w in cond_2nd:
            best_pair = max(cond_2nd[w].items(), key=lambda x: x[1], default=None)
            if best_pair:
                outer_companion[w] = {
                    "most_likely_2nd": best_pair[0],
                    "prob": best_pair[1],
                    "breakdown": cond_2nd[w],
                }

    return {
        "total_races": total,
        "win_freq": win_freq,
        "cond_2nd": cond_2nd,
        "cond_3rd": cond_3rd,
        "top_combos": top_combos,
        "ev_top_combos": ev_top_combos,
        "upset_freq": upset_freq,
        "outer_companion": outer_companion,
    }


def _build_axis_stats(races: list[dict], key_fn, min_samples: int = 30) -> dict:
    """
    races を key_fn(race) で分類し、各パーティションの _build_stats を返す。
    サンプル数が min_samples 未満のパーティションはスキップする。
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in races:
        k = key_fn(r)
        if k:
            buckets[k].append(r)

    result = {}
    for k, rs in buckets.items():
        if len(rs) < min_samples:
            continue
        # 軽量版: top_combos と win_freq と cond_2nd のみ保持（ファイルサイズ節約）
        full = _build_stats(rs)
        result[k] = {
            "total_races":      full["total_races"],
            "win_freq":         full["win_freq"],
            "cond_2nd":         full["cond_2nd"],
            "top_combos":       full["top_combos"][:10],   # トップ10だけ保持
            "ev_top_combos":    full.get("ev_top_combos", [])[:10],
            "outer_companion":  full.get("outer_companion", {}),
        }
    return result


def build_all(min_races: int = 30) -> dict[str, dict]:
    """
    全CSVを読み込み、会場ごとの出目統計を構築して保存する。
    min_races: 会場をスキップする最小レース数
    """
    STATS_DIR.mkdir(parents=True, exist_ok=True)

    # 会場別レースリストを収集
    venue_races: dict[str, list[dict]] = defaultdict(list)

    files = sorted(glob.glob(str(CSV_DIR / "202*.csv")))
    print(f"CSVファイル数: {len(files)}")

    for filepath in files:
        with open(filepath, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        # rank==1の行だけが3連単情報を持つ
        for row in rows:
            if row.get("rank", "").strip() != "1":
                continue
            venue_name = row.get("venue_name", "").strip()
            won3 = row.get("won3", "").strip()
            if not venue_name or not won3:
                continue
            parts = won3.split("-")
            if len(parts) != 3:
                continue

            jcd = NAME_TO_JCD.get(venue_name, "")
            if not jcd:
                continue  # 会場コード不明はスキップ

            try:
                race_no = int(row.get("race_no", 0) or 0)
            except Exception:
                race_no = 0
            try:
                won3_pay = float((row.get("won3_pay", "") or "0").replace(",", ""))
            except Exception:
                won3_pay = 0.0

            venue_races[jcd].append({
                "first":     parts[0],
                "second":    parts[1],
                "third":     parts[2],
                "date":      row.get("date", ""),
                "race_no":   race_no,
                "race_type": row.get("race_type", ""),
                "won3_pay":  won3_pay,
            })

    # 統計を構築して保存
    all_stats = {}
    for jcd, races in sorted(venue_races.items()):
        if len(races) < min_races:
            print(f"  [{jcd}] スキップ ({len(races)}R < {min_races}R)")
            continue

        print(f"  [{jcd}] {len(races)}R → 統計構築中 ...", end="")
        stats = _build_stats(races)

        # v5.14: 多軸集計を追加
        stats["by_month"]  = _build_axis_stats(races, lambda r: (r.get("date","") or "")[:6], min_samples=40)
        stats["by_season"] = _build_axis_stats(races, lambda r: _month_to_season(r.get("date","")), min_samples=80)
        stats["by_period"] = _build_axis_stats(races, lambda r: _race_no_to_period(r.get("race_no", 0) or 0), min_samples=80)
        stats["by_stage"]  = _build_axis_stats(races, lambda r: _race_type_to_stage(r.get("race_type","")), min_samples=40)

        all_stats[jcd] = stats

        out_path = STATS_DIR / f"{jcd}_combo_freq.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        axes = []
        if stats["by_month"]:  axes.append(f"月{len(stats['by_month'])}")
        if stats["by_season"]: axes.append(f"季{len(stats['by_season'])}")
        if stats["by_period"]: axes.append(f"帯{len(stats['by_period'])}")
        if stats["by_stage"]:  axes.append(f"種{len(stats['by_stage'])}")
        axes_str = " ".join(axes)
        print(f" top出目: {stats['top_combos'][0]['combo']} ({stats['top_combos'][0]['freq']*100:.1f}%)  [{axes_str}]")

    # 全体
    all_races = [r for races in venue_races.values() for r in races]
    all_total_stats = _build_stats(all_races)
    with open(STATS_DIR / "_all_combo_freq.json", "w", encoding="utf-8") as f:
        json.dump(all_total_stats, f, ensure_ascii=False, indent=2)
    print(f"\n全体: {all_total_stats['total_races']}R")
    print(f"全体top出目: {all_total_stats['top_combos'][0]['combo']} ({all_total_stats['top_combos'][0]['freq']*100:.1f}%)")

    return all_stats


def load_combo_stats(jcd: str) -> dict | None:
    """
    会場コードの出目統計を読み込む。
    ファイルがなければ全体統計を返す。
    なければNone。
    """
    path = STATS_DIR / f"{jcd}_combo_freq.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # フォールバック: 全体統計
    fallback = STATS_DIR / "_all_combo_freq.json"
    if fallback.exists():
        with open(fallback, encoding="utf-8") as f:
            return json.load(f)
    return None


def get_cond_2nd_prob(stats: dict, first: str, second: str) -> float:
    """P(2nd=second | 1st=first) を返す。データなければ1/5=0.2"""
    if not stats:
        return 0.2
    return stats.get("cond_2nd", {}).get(str(first), {}).get(str(second), 0.0)


def get_cond_3rd_prob(stats: dict, first: str, second: str, third: str) -> float:
    """P(3rd=third | 1st=first, 2nd=second) を返す。データなければ1/4=0.25"""
    if not stats:
        return 0.25
    return stats.get("cond_3rd", {}).get(str(first), {}).get(str(second), {}).get(str(third), 0.0)


def get_combo_freq(stats: dict, combo: str) -> float:
    """
    combo = "1-2-3" の出現頻度（全体の何%か）を返す。
    """
    if not stats:
        return 0.0
    for item in stats.get("top_combos", []):
        if item["combo"] == combo:
            return item["freq"]
    return 0.0


def get_best_2nd(stats: dict, first: str) -> tuple[str, float]:
    """
    first枠が1着のとき、最も多く2着に来る枠と確率を返す。
    戻り値: ("枠番文字列", 確率)
    """
    if not stats:
        return ("2", 0.2)
    d = stats.get("cond_2nd", {}).get(str(first), {})
    if not d:
        return ("2", 0.2)
    best = max(d.items(), key=lambda x: x[1])
    return best


def get_best_3rd(stats: dict, first: str, second: str) -> tuple[str, float]:
    """
    first-second の順で来たとき、最も多く3着に来る枠と確率を返す。
    """
    if not stats:
        return ("3", 0.25)
    d = stats.get("cond_3rd", {}).get(str(first), {}).get(str(second), {})
    if not d:
        return ("3", 0.25)
    best = max(d.items(), key=lambda x: x[1])
    return best


def print_report(jcd: str):
    """会場の出目統計サマリーをコンソール出力"""
    from venue_config import VENUE_CONFIG
    name = VENUE_CONFIG.get(jcd, {}).get("name", jcd)
    stats = load_combo_stats(jcd)
    if not stats:
        print(f"[{jcd}] 統計なし")
        return

    print(f"\n{'='*60}")
    print(f"  📊 出目統計  {name}({jcd})  {stats['total_races']}R")
    print(f"{'='*60}")

    print("\n【1着頻度】")
    for waku in ["1","2","3","4","5","6"]:
        freq = stats["win_freq"].get(waku, 0)
        bar  = "█" * int(freq * 100)
        print(f"  {waku}枠: {freq*100:5.1f}%  {bar}")

    print(f"\n【荒れ頻度（外枠1着）】: {stats['upset_freq']*100:.1f}%")

    print("\n【外枠まくり連れ出しパターン】")
    for w, info in stats.get("outer_companion", {}).items():
        print(f"  {w}枠1着 → 2着は {info['most_likely_2nd']}枠 ({info['prob']*100:.1f}%)  "
              f"全2着分布: " + " ".join(f"{k}枠{v*100:.0f}%" for k,v in list(info['breakdown'].items())[:4]))

    print("\n【1着ごとの最多2着】")
    for first in ["1","2","3","4","5","6"]:
        d = stats.get("cond_2nd", {}).get(first, {})
        if not d: continue
        top3 = list(d.items())[:3]
        parts = " | ".join(f"{k}枠:{v*100:.1f}%" for k,v in top3)
        print(f"  {first}枠1着時: {parts}")

    print("\n【top20出目】")
    for i, item in enumerate(stats["top_combos"][:10], 1):
        print(f"  {i:2d}. {item['combo']}  {item['freq']*100:.2f}%  ({item['count']}回)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="会場別出目頻度分析")
    parser.add_argument("--build",  action="store_true", help="全会場の統計を再構築")
    parser.add_argument("--report", default="",  help="会場コード (例: 19=下関)")
    parser.add_argument("--min",    type=int, default=30, help="最小レース数 (default:30)")
    args = parser.parse_args()

    if args.build:
        build_all(min_races=args.min)
    if args.report:
        print_report(args.report)
    if not args.build and not args.report:
        parser.print_help()
