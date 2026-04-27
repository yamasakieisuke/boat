#!/usr/bin/env python3
"""
予測精度検証スクリプト v1.0
──────────────────────────────────────────────────────────────
data/logs/{date}/{jcd}_R{rno}_pred.json（予測ログ）と
data/results_csv/{date}.csv（実際の着順）を照合し、
的中率・平均スコア差などの精度指標を集計して表示する。

使い方:
  # 指定会場の全ログを検証
  python3 scripts/verify.py --jcd 22

  # 日付範囲を指定
  python3 scripts/verify.py --jcd 22 --from 20250315 --to 20260315

  # 詳細レース一覧を表示
  python3 scripts/verify.py --jcd 22 --verbose
──────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import csv
import re
import io
import contextlib
import datetime
import argparse
from pathlib import Path
from collections import defaultdict
from json import JSONDecodeError

BASE_DIR         = Path(__file__).parent.parent
DATA_DIR         = BASE_DIR / "data"
LOG_DIR          = DATA_DIR / "logs"
RESULTS_DIR      = DATA_DIR / "results_csv"
OUTPUT_DIR       = BASE_DIR / "output"
DATA_OUTPUT_DIR  = OUTPUT_DIR / "data"                     # output/data/ 配下に統合
VERIFY_DIR       = DATA_OUTPUT_DIR / "verify"              # output/data/verify/ → 詳細ファイル格納
VERIFY_HIST_FILE = LOG_DIR  / "verify_history.json"        # JSON蓄積ログ
VERIFY_MD_FILE   = DATA_OUTPUT_DIR / "verify_log.md"       # サマリ目視用MD（output/data/に移動）
VERIFY_HTML_FILE = DATA_OUTPUT_DIR / "verify_log.html"     # サマリHTML
ACCURACY_DIR     = DATA_OUTPUT_DIR / "accuracy"            # 週次精度レポート格納
WP_ACCURACY_DIR  = BASE_DIR / "wordpress" / "boat-forecast-viewer" / "data" / "accuracy"  # WP配布用ミラー

VENUE_NAMES = {
    "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川",
    "06":"浜名湖","07":"蒲郡","08":"常滑","09":"津","10":"三国",
    "11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀",
    "16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松",
    "21":"芦屋","22":"福岡","23":"唐津","24":"大村",
}


def load_json(path):
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


_RACECARD_DIR = Path(__file__).resolve().parent.parent / "data" / "racecards"


def _load_racecard_series_races(jcd: str, date: str, race_no: int, waku) -> list:
    """v5.19 #3: racecard から指定枠の series_races [{course,rank},...] を読む。"""
    if not waku:
        return []
    path = _RACECARD_DIR / date / f"{jcd}_R{int(race_no):02d}.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rc = json.load(f)
    except Exception:
        return []
    for racer in rc.get("racers", []):
        if int(racer.get("waku", 0) or 0) == int(waku):
            return racer.get("series_races", []) or []
    return []


def _series_perf_score(series_races: list) -> float | None:
    """v5.19 #3: コース補正着順 → series_raw (0〜1) を返す。None=実績なし。"""
    if not series_races:
        return None
    expected = {1: 1.85, 2: 3.0, 3: 3.3, 4: 3.5, 5: 4.2, 6: 4.5}
    perfs = [expected.get(s.get("course", 0), 3.5) - s.get("rank", 3.5) for s in series_races]
    avg_perf = sum(perfs) / len(perfs)
    return max(0.0, min(1.0, (avg_perf + 3.0) / 6.0))


def load_verify_history() -> list[dict]:
    """
    verify_history.json を読み込む。
    末尾の余分な文字などで JSON が壊れていても、先頭の有効な配列部分を救済する。
    """
    if not VERIFY_HIST_FILE.exists():
        return []

    text = VERIFY_HIST_FILE.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    try:
        data, _end = decoder.raw_decode(text)
        if isinstance(data, list):
            return data
    except JSONDecodeError:
        pass

    print(f"[WARN] verify_history.json の解析に失敗: {VERIFY_HIST_FILE}")
    return []


VENUE_NAME_TO_CODE = {
    "桐生":"01","戸田":"02","江戸川":"03","平和島":"04","多摩川":"05",
    "浜名湖":"06","蒲郡":"07","常滑":"08","津":"09","三国":"10",
    "びわこ":"11","住之江":"12","尼崎":"13","鳴門":"14","丸亀":"15",
    "児島":"16","宮島":"17","徳山":"18","下関":"19","若松":"20",
    "芦屋":"21","福岡":"22","唐津":"23","大村":"24",
}


def he(text: str) -> str:
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def pct_class(val: float) -> str:
    if val >= 50:
        return "pct-good"
    if val >= 20:
        return "pct-mid"
    return "pct-low"


def display_bet_label(label: str, combo: str = "", reason: str = "") -> str:
    clean = (label or "").strip()
    reason = reason or ""
    if clean == "本命①":
        return "◎本線"
    if clean == "本命②":
        return "○対抗"
    if clean == "出目④":
        return "△押さえ"
    if clean == "穴":
        if "1着狙い" in reason:
            return "穴狙い"
        if "2着差し" in reason:
            return "▲単穴"
        return "△押さえ"
    if combo:
        return clean or combo
    return clean


def load_results_for_date(date_str: str) -> dict:
    """
    results_csv/{date}.csv を読み込み、
    {(venue_code, race_no): {
        "racers": [{"rank","waku","name"}, ...],
        "won3": "1-2-3", "won3_pay": 950, "won3_pop": 2,
        "race_type": "予選"
    }} を返す。
    """
    csv_path = RESULTS_DIR / f"{date_str}.csv"
    if not csv_path.exists():
        return {}

    # race_meta: (jcd, race_no) -> 1着行のメタ情報
    results   = defaultdict(lambda: {"racers": [], "won3": "", "won3_pay": 0,
                                      "won3_pop": 0, "race_type": ""})
    try:
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                venue_name = row.get("venue_name", "").strip()
                jcd = VENUE_NAME_TO_CODE.get(venue_name)
                if not jcd:
                    continue
                try:
                    race_no = int(row.get("race_no", 0))
                    rank    = int(row.get("rank", 0))
                    waku    = int(row.get("waku", 0))
                    name    = row.get("name", "").replace(" ", "")
                except (ValueError, TypeError):
                    continue
                if race_no > 0 and rank > 0 and waku > 0:
                    key = (jcd, race_no)
                    results[key]["racers"].append({"rank": rank, "waku": waku, "name": name})
                    # 1着行からレースメタ情報を取得
                    if rank == 1:
                        results[key]["won3"]      = row.get("won3", "").strip()
                        results[key]["won3_pay"]  = int(row.get("won3_pay", 0) or 0)
                        results[key]["won3_pop"]  = int(row.get("won3_pop", 0) or 0)
                        results[key]["race_type"] = row.get("race_type", "").strip()
    except Exception as e:
        print(f"[WARN] CSV読み込みエラー {csv_path}: {e}")

    return dict(results)


def evaluate_prediction(pred_log: dict, actual_results: list) -> dict:
    """
    1レース分の予測ログと実際の着順を比較して評価指標を返す。

    返値:
      {
        "hit_1st":  bool  # 1着的中
        "hit_2nd":  bool  # 2着的中
        "hit_3rd":  bool  # 3着的中
        "hit_top3_all": bool  # 3連単的中（1-2-3着完全一致）
        "hit_top3_box": bool  # 3連複的中（3着以内3艇一致）
        "hit_top2_ord": bool  # 2連単的中（1-2着順序一致）
        "hit_top2_box": bool  # 2連複的中（2着以内2艇一致）
        "pred_1st_actual_rank": int  # 予測1位の実際の順位
      }
    """
    predictions = pred_log.get("predictions", [])
    actual_sorted = sorted(actual_results, key=lambda r: r["rank"])

    pred_order = [p["waku"] for p in predictions]
    actual_order = [r["waku"] for r in actual_sorted]

    if len(actual_order) < 3 or len(pred_order) < 3:
        return {}

    a1, a2, a3 = actual_order[0], actual_order[1], actual_order[2]
    p1, p2, p3 = pred_order[0], pred_order[1], pred_order[2]

    # 予測1位が実際何位だったか
    pred_1st_actual_rank = next(
        (r["rank"] for r in actual_results if r["waku"] == p1), 99
    )

    return {
        "hit_1st":           p1 == a1,
        "hit_2nd":           p2 == a2,
        "hit_3rd":           p3 == a3,
        "hit_top3_all":      (p1, p2, p3) == (a1, a2, a3),
        "hit_top3_box":      set([p1, p2, p3]) == set([a1, a2, a3]),
        "hit_top2_ord":      (p1, p2) == (a1, a2),
        "hit_top2_box":      set([p1, p2]) == set([a1, a2]),
        "pred_1st_actual_rank": pred_1st_actual_rank,
    }


def evaluate_bets(pred_log: dict, actual_won3: str) -> dict:
    """
    保存済みの買い目に対する的中状況を返す。

    v5.16 新構造: pred_log に "honmei" / "others" があれば本命/その他 で評価し、
    旧 "bets" フィールドとの互換フィールド hit_bet1/2/3 も同時に返す。
    """
    bets = pred_log.get("bets", []) or []
    combos = [b.get("combo", "") for b in bets if b.get("combo")]
    hit_index = next((i for i, combo in enumerate(combos) if combo == actual_won3), -1)

    # v5.16: 本命/その他 の的中判定（新フィールド優先）
    honmei_bets = pred_log.get("honmei", []) or []
    others_bets = pred_log.get("others", []) or []
    honmei_combos = [b.get("combo", "") for b in honmei_bets if b.get("combo")]
    others_combos = [b.get("combo", "") for b in others_bets if b.get("combo")]
    # subtype 別
    others_by_subtype: dict[str, list[str]] = {"対抗": [], "穴": [], "抑え": []}
    for b in others_bets:
        st = b.get("subtype", "")
        if st in others_by_subtype and b.get("combo"):
            others_by_subtype[st].append(b["combo"])

    hit_honmei = actual_won3 in honmei_combos
    hit_others = actual_won3 in others_combos
    hit_taikou = actual_won3 in others_by_subtype["対抗"]
    hit_oshi   = actual_won3 in others_by_subtype["抑え"]
    hit_ana    = actual_won3 in others_by_subtype["穴"]

    return {
        "bet_combos":  combos,
        "hit_bet_any": hit_index >= 0,
        "hit_bet1":    hit_index == 0,
        "hit_bet2":    hit_index == 1,
        "hit_bet3":    hit_index == 2,
        # v5.16
        "honmei_combos": honmei_combos,
        "others_combos": others_combos,
        "taikou_combos": others_by_subtype["対抗"],
        "ana_combos":    others_by_subtype["穴"],
        "oshi_combos":   others_by_subtype["抑え"],
        "hit_honmei":    hit_honmei,
        "hit_others":    hit_others,
        "hit_taikou":    hit_taikou,
        "hit_oshi":      hit_oshi,
        "hit_ana":       hit_ana,
    }


def save_verify_log(summary: dict):
    """
    検証サマリーを data/logs/verify_history.json に追記保存する。
    同じ (run_date, jcd, date_from, date_to) のレコードがあれば上書き更新。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    history = load_verify_history()

    # 同一キーがあれば上書き
    key = (summary["run_date"], summary["jcd"], summary["date_from"], summary["date_to"])
    history = [r for r in history
               if (r["run_date"], r["jcd"], r["date_from"], r["date_to"]) != key]
    history.append(summary)
    history.sort(key=lambda r: (r["run_date"], r["jcd"]))

    with open(VERIFY_HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 検証ログ保存: {VERIFY_HIST_FILE}  （累計 {len(history)} 件）")


def update_verify_md(summary: dict):
    """
    output/verify_log.md を更新する。
    1行1レース場の形式で、新しい行を先頭に追記（最新が上）。
    同じ (run_date, jcd) の行があれば上書き。

    フォーマット例:
    | 2026-03-15 | 福岡(22) | 12R | 75.0% | 16.7% | 8.3% | 9.50 |
    """
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    vname   = VENUE_NAMES.get(summary["jcd"], summary["jcd"])
    new_row = (
        f"| {summary['run_date']} "
        f"| {vname} "
        f"| {summary['date_from']}〜{summary['date_to']} "
        f"| {summary['total_races']}R "
        f"| {summary['hit_1st_pct']}% "
        f"| {summary['hit_bet_any_pct']}% "
        f"| {summary['hit_3fuku_pct']}% "
        f"| {summary['hit_3tan_pct']}% "
        f"| {summary['avg_rank']:.2f} |"
    )

    header = (
        "# 予測精度ログ\n\n"
        "| 検証日 | 会場 | 対象期間 | レース数 | 1着% | 買い目% | 3連複% | 3連単% | 平均着順 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )

    # 既存ファイルを読み込む
    existing_rows: list[str] = []
    if VERIFY_MD_FILE.exists():
        with open(VERIFY_MD_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                # ヘッダー・空行はスキップ、データ行だけ保持
                if line.startswith("| ") and "検証日" not in line and "---" not in line:
                    existing_rows.append(line)

    # 同じ (run_date, jcd) の行を除外して新行を先頭に追加
    key_prefix = f"| {summary['run_date']} | {vname} "
    existing_rows = [r for r in existing_rows if not r.startswith(key_prefix)]
    all_rows = [new_row] + existing_rows   # 最新が先頭

    with open(VERIFY_MD_FILE, "w", encoding="utf-8") as f:
        f.write(header)
        for row in all_rows:
            f.write(row + "\n")

    print(f"  📋 目視ログ更新: {VERIFY_MD_FILE}  （{len(all_rows)} 行）")


def update_verify_html() -> None:
    """verify_log.md と verify_history.json を元にサマリHTMLを生成する。"""
    rows = load_verify_history()
    rows.sort(key=lambda r: (r.get("run_date", ""), r.get("jcd", "")), reverse=True)

    venue_stats = defaultdict(lambda: {
        "total_races": 0, "hit_1st": 0, "hit_bet_any": 0, "hit_3fuku": 0, "hit_3tan": 0
    })
    month_stats = defaultdict(lambda: {
        "total_races": 0, "hit_1st": 0, "hit_bet_any": 0, "hit_3fuku": 0, "hit_3tan": 0
    })
    for row in rows:
        jcd = str(row.get("jcd", "")).zfill(2)
        ym = str(row.get("date_to", ""))[:6]
        total = int(row.get("total_races", 0) or 0)
        if total <= 0:
            continue
        for bucket in (venue_stats[jcd], month_stats[ym]):
            bucket["total_races"] += total
            bucket["hit_1st"] += int(row.get("hit_1st", 0) or 0)
            bucket["hit_bet_any"] += int(row.get("hit_bet_any", 0) or 0)
            bucket["hit_3fuku"] += int(row.get("hit_3fuku", 0) or 0)
            bucket["hit_3tan"] += int(row.get("hit_3tan", 0) or 0)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="ja"><head><meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>的中率サマリ</title>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;padding:10px;background:#fff;color:#111;}",
        "h1{font-size:18px;margin:0 0 10px;}",
        "h2{font-size:14px;margin:18px 0 8px;color:#2c4a8a;}",
        ".note{color:#666;font-size:12px;margin:0 0 10px;}",
        ".tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}",
        "table{border-collapse:collapse;min-width:100%;font-size:12px;}",
        "th{background:#2c4a8a;color:#fff;padding:6px 8px;white-space:nowrap;position:sticky;top:0;}",
        "td{border:1px solid #ddd;padding:5px 8px;white-space:nowrap;}",
        "tr:nth-child(even) td{background:#f5f7fb;}",
        ".pct-good{color:#1a7f1a;font-weight:700;}",
        ".pct-mid{color:#8a6800;font-weight:700;}",
        ".pct-low{color:#c04000;font-weight:700;}",
        "a{color:#0055cc;text-decoration:none;}a:hover{text-decoration:underline;}",
        "</style></head><body>",
        "<h1>的中率サマリ</h1>",
        '<p class="note">会場ごとの検証結果。日別詳細HTMLと、会場別・月別の集計を確認できます。</p>',
        '<h2>最新検証一覧</h2>',
        '<div class="tbl-wrap"><table>',
        "<tr><th>検証日</th><th>会場</th><th>対象期間</th><th>R数</th><th>1着%</th><th>買い目%</th><th>3連複%</th><th>3連単%</th><th>平均着順</th><th>詳細</th></tr>",
    ]

    for row in rows:
        vname = VENUE_NAMES.get(str(row.get("jcd", "")).zfill(2), str(row.get("jcd", "")))
        date_to = str(row.get("date_to", ""))
        detail_rel = f"verify/verify_detail_{vname}_{date_to}.html" if len(date_to) == 8 else ""
        detail_html = f'<a href="{he(detail_rel)}">詳細</a>' if detail_rel else '—'
        bet_pct = row.get("hit_bet_any_pct")
        bet_pct_num = None
        try:
            bet_pct_num = float(bet_pct)
            bet_pct_text = f"{bet_pct_num:.1f}%"
            bet_pct_cls = pct_class(bet_pct_num)
        except (TypeError, ValueError):
            bet_pct_text = "-"
            bet_pct_cls = "pct-low"
        parts.append(
            "<tr>"
            f"<td>{he(row.get('run_date',''))}</td>"
            f"<td>{he(vname)}</td>"
            f"<td>{he(row.get('date_from',''))}〜{he(row.get('date_to',''))}</td>"
            f"<td>{he(row.get('total_races',''))}R</td>"
            f"<td class=\"{pct_class(float(row.get('hit_1st_pct', 0)))}\">{he(row.get('hit_1st_pct',''))}%</td>"
            f"<td class=\"{bet_pct_cls}\">{he(bet_pct_text)}</td>"
            f"<td class=\"{pct_class(float(row.get('hit_3fuku_pct', 0)))}\">{he(row.get('hit_3fuku_pct',''))}%</td>"
            f"<td class=\"{pct_class(float(row.get('hit_3tan_pct', 0)))}\">{he(row.get('hit_3tan_pct',''))}%</td>"
            f"<td>{he(row.get('avg_rank',''))}</td>"
            f"<td>{detail_html}</td>"
            "</tr>"
        )

    parts.append("</table></div>")

    parts.append('<h2>会場別集計</h2><div class="tbl-wrap"><table>')
    parts.append("<tr><th>会場</th><th>R数</th><th>1着%</th><th>買い目%</th><th>3連複%</th><th>3連単%</th></tr>")
    for jcd, stat in sorted(venue_stats.items()):
        total = stat["total_races"]
        if total <= 0:
            continue
        vname = VENUE_NAMES.get(jcd, jcd)
        parts.append(
            "<tr>"
            f"<td>{he(vname)}</td>"
            f"<td>{total}R</td>"
            f"<td class=\"{pct_class(stat['hit_1st']/total*100)}\">{stat['hit_1st']/total*100:.1f}%</td>"
            f"<td class=\"{pct_class(stat['hit_bet_any']/total*100)}\">{stat['hit_bet_any']/total*100:.1f}%</td>"
            f"<td class=\"{pct_class(stat['hit_3fuku']/total*100)}\">{stat['hit_3fuku']/total*100:.1f}%</td>"
            f"<td class=\"{pct_class(stat['hit_3tan']/total*100)}\">{stat['hit_3tan']/total*100:.1f}%</td>"
            "</tr>"
        )
    parts.append("</table></div>")

    if month_stats:
        parts.append('<h2>月別集計</h2><div class="tbl-wrap"><table>')
        parts.append("<tr><th>月</th><th>R数</th><th>1着%</th><th>買い目%</th><th>3連複%</th><th>3連単%</th></tr>")
        for ym, stat in sorted(month_stats.items(), reverse=True):
            total = stat["total_races"]
            if total <= 0:
                continue
            parts.append(
                "<tr>"
                f"<td>{he(ym[:4] + '/' + ym[4:6])}</td>"
                f"<td>{total}R</td>"
                f"<td class=\"{pct_class(stat['hit_1st']/total*100)}\">{stat['hit_1st']/total*100:.1f}%</td>"
                f"<td class=\"{pct_class(stat['hit_bet_any']/total*100)}\">{stat['hit_bet_any']/total*100:.1f}%</td>"
                f"<td class=\"{pct_class(stat['hit_3fuku']/total*100)}\">{stat['hit_3fuku']/total*100:.1f}%</td>"
                f"<td class=\"{pct_class(stat['hit_3tan']/total*100)}\">{stat['hit_3tan']/total*100:.1f}%</td>"
                "</tr>"
            )
        parts.append("</table></div>")

    parts.append("</body></html>")
    VERIFY_HTML_FILE.write_text("".join(parts), encoding="utf-8")
    print(f"  📋 HTMLログ更新: {VERIFY_HTML_FILE}")


def save_verify_detail(jcd: str, date_str: str, race_details: list):
    """
    1会場1日分の詳細検証ファイルを output/data/verify/ に保存する。

    ファイル名: output/data/verify/verify_detail_{venue_name}_{date}.md

    フォーマット（1行1レース + 末尾に振り返り分析）:
      1R　予測　1-2-3　1-3-2　3-2-4　結果　1-4-3　2番人気　配当　950円　予測結果：✕
      ...
      ## 振り返り分析
      ...
    """
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    vname    = VENUE_NAMES.get(jcd, jcd)
    date_fmt = f"{date_str[:4]}/{int(date_str[4:6])}/{int(date_str[6:])}"

    fname = VERIFY_DIR / f"verify_detail_{vname}_{date_str}.md"
    html_fname = VERIFY_DIR / f"verify_detail_{vname}_{date_str}.html"

    # 集計
    sorted_details = sorted(race_details, key=lambda d: d["race_no"])
    total     = len(sorted_details)
    hit_3tan  = sum(1 for d in sorted_details if d.get("hit_3tan"))
    hit_3fuku = sum(1 for d in sorted_details if d.get("hit_3fuku"))
    hit_1st   = sum(1 for d in sorted_details
                    if d.get("combo1","").split("-")[0] == (d.get("won3","") or "").split("-")[0])

    pays_all  = [d.get("won3_pay", 0) for d in sorted_details if d.get("won3_pay")]
    pops_all  = [d.get("won3_pop", 0) for d in sorted_details if d.get("won3_pop")]
    avg_pay   = sum(pays_all) / len(pays_all) if pays_all else 0
    avg_pop   = sum(pops_all) / len(pops_all) if pops_all else 0

    # 高配当レース（10,000円超）
    big_upset = [d for d in sorted_details if d.get("won3_pay", 0) >= 10000]
    # 3複は当たっているが3単を外したレース
    hit_fuku_miss_tan = [d for d in sorted_details
                         if d.get("hit_3fuku") and not d.get("hit_3tan")]
    # 1着予測が合っているレース（combo1の先頭枠 = won3先頭枠）
    hit_1st_races = [d["race_no"] for d in sorted_details
                     if d.get("combo1","").split("-")[0] ==
                        (d.get("won3","") or "").split("-")[0]]

    bet_history = [
        ("本命", sum(1 for d in sorted_details if d.get("hit_honmei"))),
        ("対抗", sum(1 for d in sorted_details if d.get("hit_taikou"))),
        ("穴",   sum(1 for d in sorted_details if d.get("hit_ana"))),
        ("抑え", sum(1 for d in sorted_details if d.get("hit_oshi"))),
    ]

    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"# 予測詳細　{date_fmt}　{vname}\n\n")

        for det in sorted_details:
            race_no    = det["race_no"]
            won3       = det.get("won3") or "---"
            pop        = det.get("won3_pop", 0)
            pay        = det.get("won3_pay", 0)
            race_title = det.get("race_type", "")

            # v5.16: 本命/対抗/穴/抑え で表示
            honmei_str = " / ".join(det.get("honmei_combos", [])) or det.get("combo1", "---")
            # others は bet_combos から honmei を除外して分類
            others_combos = det.get("others_combos", [])
            if others_combos:
                others_str = " / ".join(others_combos)
            else:
                # 旧形式フォールバック
                c2 = det.get("combo2", "")
                c3 = det.get("combo3", "")
                others_str = " / ".join(c for c in [c2, c3] if c and c != "---")
            others_str = others_str or "—"

            if det.get("hit_bet_any", False):
                # 具体的にどのカテゴリで的中したか表示
                if det.get("hit_honmei"):
                    mark = "◎本命的中"
                elif det.get("hit_taikou"):
                    mark = "◎対抗的中"
                elif det.get("hit_ana"):
                    mark = "◎穴的中"
                elif det.get("hit_oshi"):
                    mark = "◎抑え的中"
                else:
                    mark = "◎的中"
            elif det.get("hit_3fuku", False):
                mark = "△3連複"
            else:
                mark = "✕"

            pop_str   = f"{pop}番人気" if pop else "--番人気"
            pay_str   = f"{pay:,}円"  if pay else "--円"
            title_str = f"　{race_title}" if race_title else ""

            f.write(
                f"{race_no}R{title_str}　"
                f"本命　{honmei_str}　その他　{others_str}　"
                f"結果　{won3}　{pop_str}　配当　{pay_str}　"
                f"判定：{mark}\n"
            )

        # ── 振り返り分析 ─────────────────────────────────────────
        hit_bet_any_cnt = sum(1 for d in sorted_details if d.get("hit_bet_any"))
        hit_honmei_cnt  = sum(1 for d in sorted_details if d.get("hit_honmei"))
        hit_others_cnt  = sum(1 for d in sorted_details if d.get("hit_others"))
        f.write("\n---\n\n## 振り返り分析\n\n")
        f.write(f"- **買い目的中**: {hit_bet_any_cnt}/{total}R "
                f"({hit_bet_any_cnt/total*100:.1f}%)  "
                f"本命 {hit_honmei_cnt}回 / その他 {hit_others_cnt}回\n")
        f.write(f"- **参考** 3連単(順位一致) {hit_3tan}回 / 3連複 {hit_3fuku}回\n")
        f.write(f"- **1着予測一致**: {len(hit_1st_races)}R "
                f"（{', '.join(str(r)+'R' for r in hit_1st_races) or 'なし'}）\n")
        f.write(f"- **平均配当**: {avg_pay:,.0f}円　平均人気: {avg_pop:.1f}番人気\n")

        if big_upset:
            races_str = ", ".join(
                f"{d['race_no']}R({d['won3_pay']:,}円/{d['won3_pop']}人気)"
                for d in big_upset
            )
            f.write(f"- **高配当(1万円超)**: {races_str}\n")

        if hit_fuku_miss_tan:
            r_str = ", ".join(str(d["race_no"]) + "R" for d in hit_fuku_miss_tan)
            f.write(f"- **3連複○ / 3連単✕**: {r_str}　→ 3着の順序が逆\n")

        # 傾向コメント
        f.write("\n### 傾向コメント\n\n")
        notes = []

        bet_any_pct = hit_bet_any_cnt / total * 100 if total else 0
        h1_pct      = len(hit_1st_races) / total * 100 if total else 0

        if bet_any_pct >= 40:
            notes.append(f"買い目的中率 {bet_any_pct:.1f}% — 好調。買い目の組み合わせが機能している。")
        elif bet_any_pct >= 25:
            notes.append(f"買い目的中率 {bet_any_pct:.1f}% — 標準的。本命軸の精度向上が課題。")
        else:
            notes.append(f"買い目的中率 {bet_any_pct:.1f}% — 低調。荒れたレースが多い可能性。")

        if h1_pct >= 70:
            notes.append(f"1着予測一致 {h1_pct:.1f}% — 本命軸は信頼できる水準。2・3着の精度向上が課題。")
        elif h1_pct <= 40:
            notes.append(f"1着予測一致 {h1_pct:.1f}% — 1着予測精度が低め。スコア上位選手でも荒れたレースが多い可能性。")

        if big_upset:
            avg_upset_pay = sum(d['won3_pay'] for d in big_upset) / len(big_upset)
            notes.append(
                f"高配当レースが {len(big_upset)}R — 平均{avg_upset_pay:,.0f}円。"
                f"穴枠（{', '.join(str(d['race_no'])+'R' for d in big_upset)}）は"
                "アウト枠・2コース差しが決まっている。潮汐・展示タイム差を事前確認したい。"
            )

        miss_only = [d for d in sorted_details if not d.get("hit_bet_any")]
        if len(miss_only) >= total * 0.7:
            notes.append("買い目不的中が7割超。予選序盤は荒れやすく1枠信頼度が低い可能性。次回は買い目点数の配分見直しを検討。")

        for note in notes:
            f.write(f"- {note}\n")

    print(f"  📝 詳細ファイル保存: {fname}")

    cards = [
        ("検証R", f"{total}R", ""),
        ("1着%", f"{hit_1st/total*100:.1f}%", "good" if hit_1st/total*100 >= 50 else "mid"),
        ("買い目%", f"{sum(1 for d in sorted_details if d.get('hit_bet_any'))/total*100:.1f}%", "mid"),
        ("3連複%", f"{hit_3fuku/total*100:.1f}%", "good" if hit_3fuku/total*100 >= 30 else "mid"),
        ("3連単%", f"{hit_3tan/total*100:.1f}%", "good" if hit_3tan/total*100 >= 10 else "low"),
        ("平均着順", f"{sum(1 for _ in []) if False else ''}{''}", ""),
    ]
    avg_rank = 0.0
    if sorted_details:
        pred_ranks = []
        for det in sorted_details:
            won3 = (det.get("won3") or "").split("-")
            combo1 = (det.get("combo1") or "").split("-")
            if combo1 and won3 and combo1[0]:
                if combo1[0] in won3:
                    pred_ranks.append(won3.index(combo1[0]) + 1)
                else:
                    pred_ranks.append(6)
        avg_rank = sum(pred_ranks) / len(pred_ranks) if pred_ranks else 0.0
    cards[-1] = ("平均着順", f"{avg_rank:.2f}", "good" if avg_rank <= 1.6 else "mid" if avg_rank <= 2.2 else "low")

    html = [
        "<!DOCTYPE html><html lang=\"ja\"><head><meta charset=\"UTF-8\">",
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>予測詳細 {he(vname)} {he(date_fmt)}</title>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;padding:10px;background:#fff;color:#111;}",
        "h1{font-size:18px;margin:0 0 8px;}",
        ".sub{color:#666;font-size:12px;margin-bottom:10px;}",
        ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin:8px 0 12px;}",
        ".card{border:1px solid #d8e0ef;border-radius:8px;padding:8px 10px;background:#f8fbff;}",
        ".card .k{font-size:11px;color:#666;margin-bottom:4px;}",
        ".card .v{font-size:20px;font-weight:700;}",
        ".good .v{color:#1a7f1a;}.mid .v{color:#8a6800;}.low .v{color:#c04000;}",
        ".tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}",
        "table{border-collapse:collapse;min-width:100%;font-size:12px;}",
        "th{background:#2c4a8a;color:#fff;padding:6px 8px;white-space:nowrap;}",
        "td{border:1px solid #ddd;padding:5px 8px;white-space:nowrap;}",
        "tr:nth-child(even) td{background:#f5f7fb;}",
        ".row-hit td{background:#eefaf0 !important;}",
        ".row-mid td{background:#fff8e6 !important;}",
        ".row-miss td{background:#fff1f0 !important;}",
        ".mark-hit{color:#1a7f1a;font-weight:700;}.mark-mid{color:#8a6800;font-weight:700;}.mark-miss{color:#c04000;font-weight:700;}",
        ".sec{font-size:13px;font-weight:700;color:#2c4a8a;margin:14px 0 6px;border-bottom:1px solid #d8e0ef;padding-bottom:2px;}",
        "ul{padding-left:18px;} li{margin:4px 0;}",
        "a{color:#0055cc;text-decoration:none;}a:hover{text-decoration:underline;}",
        "</style></head><body>",
        f"<h1>予測詳細 {he(date_fmt)} {he(vname)}</h1>",
        '<div class="sub"><a href="../verify_log.html">サマリへ戻る</a></div>',
        '<div class="cards">',
    ]
    for key, val, klass in cards:
        html.append(f'<div class="card {klass}"><div class="k">{he(key)}</div><div class="v">{he(val)}</div></div>')
    html.append("</div>")
    html.append('<div class="sec">レース別結果</div>')
    html.append('<div class="tbl-wrap"><table><tr><th>R</th><th>種別</th><th>本命</th><th>対抗</th><th>穴</th><th>抑え</th><th>結果</th><th>人気</th><th>配当</th><th>判定</th></tr>')
    for det in sorted_details:
        if det.get("hit_bet_any", False):
            if det.get("hit_honmei"):
                mark = "◎本命"
            elif det.get("hit_taikou"):
                mark = "◎対抗"
            elif det.get("hit_ana"):
                mark = "◎穴"
            elif det.get("hit_oshi"):
                mark = "◎抑え"
            else:
                mark = "◎的中"
        elif det.get("hit_3fuku"):
            mark = "△3連複"
        else:
            mark = "✕"
        mark_cls = "mark-hit" if mark.startswith("◎") else "mark-mid" if mark.startswith("△") else "mark-miss"
        row_cls = "row-hit" if mark.startswith("◎") else "row-mid" if mark.startswith("△") else "row-miss"
        pop_str = f"{det.get('won3_pop', '--')}番人気"
        pay_val = det.get("won3_pay", 0)
        pay_str = f"{pay_val:,}円" if pay_val else "--円"
        # v5.16: honmei_combos / subtype別 combos から4列に分解
        honmei_combos = det.get("honmei_combos", [])
        honmei_str = " / ".join(honmei_combos) if honmei_combos else det.get("combo1", "---")
        if honmei_combos:
            taikou_str = " / ".join(det.get("taikou_combos", [])) or "—"
            ana_str    = " / ".join(det.get("ana_combos", []))    or "—"
            oshi_str   = " / ".join(det.get("oshi_combos", []))   or "—"
        else:
            # 旧形式フォールバック
            taikou_str = det.get("combo2", "---")
            ana_str = "—"
            oshi_str = det.get("combo3", "---")
        html.append(
            f"<tr class=\"{row_cls}\">"
            f"<td>{det['race_no']}R</td>"
            f"<td>{he(det.get('race_type',''))}</td>"
            f"<td>{he(honmei_str)}</td>"
            f"<td>{he(taikou_str)}</td>"
            f"<td>{he(ana_str)}</td>"
            f"<td>{he(oshi_str)}</td>"
            f"<td>{he(det.get('won3','---'))}</td>"
            f"<td>{he(pop_str)}</td>"
            f"<td>{he(pay_str)}</td>"
            f"<td class=\"{mark_cls}\">{mark}</td>"
            "</tr>"
        )
    html.append("</table></div>")
    html.append('<div class="sec">買い目別命中履歴</div>')
    html.append('<div class="tbl-wrap"><table><tr><th>買い目</th><th>的中数</th><th>的中率</th><th>該当R</th></tr>')
    for label, count in bet_history:
        hit_key_map = {"本命": "hit_honmei", "対抗": "hit_taikou", "穴": "hit_ana", "抑え": "hit_oshi"}
        hit_key = hit_key_map.get(label, "")
        race_hits = [f"{d['race_no']}R" for d in sorted_details if hit_key and d.get(hit_key)]
        rate = count / total * 100 if total else 0.0
        html.append(
            "<tr>"
            f"<td>{he(label)}</td>"
            f"<td>{count}</td>"
            f"<td class=\"{pct_class(rate)}\">{rate:.1f}%</td>"
            f"<td>{he(', '.join(race_hits) if race_hits else 'なし')}</td>"
            "</tr>"
        )
    html.append("</table></div>")
    html.append('<div class="sec">振り返り分析</div><ul>')
    html.append(f"<li>買い目的中: {hit_bet_any_cnt}/{total}R ({hit_bet_any_cnt/total*100:.1f}%) 本命 {hit_honmei_cnt}回 / その他 {hit_others_cnt}回</li>")
    html.append(f"<li>参考: 3連単(順位一致) {hit_3tan}回 / 3連複 {hit_3fuku}回</li>")
    html.append(f"<li>1着予測一致: {len(hit_1st_races)}R ({he(', '.join(str(r)+'R' for r in hit_1st_races) or 'なし')})</li>")
    html.append(f"<li>平均配当: {avg_pay:,.0f}円 / 平均人気: {avg_pop:.1f}番人気</li>")
    if big_upset:
        html.append("<li>高配当(1万円超): " + he(", ".join(f"{d['race_no']}R({d['won3_pay']:,}円/{d['won3_pop']}人気)" for d in big_upset)) + "</li>")
    if hit_fuku_miss_tan:
        html.append("<li>3連複○ / 3連単✕: " + he(", ".join(str(d["race_no"]) + "R" for d in hit_fuku_miss_tan)) + "</li>")
    for note in notes:
        html.append(f"<li>{he(note)}</li>")
    html.append("</ul></body></html>")
    html_fname.write_text("".join(html), encoding="utf-8")
    print(f"  📝 詳細HTML保存: {html_fname}")


def run_verification(jcd: str, date_from: str, date_to: str,
                     verbose: bool = False, save: bool = True):
    """
    指定会場・期間の予測ログを全て検証して集計結果を表示する。
    save=True の場合、結果を verify_history.json に蓄積する。
    """
    print(f"\n{'='*72}")
    print(f"  📊 予測精度検証  会場={jcd}  {date_from}〜{date_to}")
    print(f"{'='*72}")

    # 対象ログを収集
    log_files = sorted(LOG_DIR.rglob(f"{jcd}_R*_pred.json"))

    total     = 0
    hit_1st   = 0
    hit_top3_box = 0
    hit_top3_all = 0
    hit_top2_ord = 0
    hit_top2_box = 0
    hit_bet_any = 0
    hit_bet1 = 0
    hit_bet2 = 0
    hit_bet3 = 0
    # v5.16: 本命/その他 集計
    hit_honmei = 0
    hit_others = 0
    hit_taikou = 0
    hit_oshi   = 0
    hit_ana    = 0
    rank_sum  = 0
    miss_details = []
    hit_details  = []

    cached_results: dict = {}          # date → results_dict のキャッシュ
    race_details_by_date: dict = defaultdict(list)  # date → [per-race detail]

    for log_path in log_files:
        # 日付ディレクトリから日付を取得
        date_str = log_path.parent.name
        if date_str < date_from or date_str > date_to:
            continue

        pred_log = load_json(log_path)
        if not pred_log:
            continue

        race_no = pred_log.get("race_no", 0)

        # 実績データを取得（同日は1回だけ読む）
        if date_str not in cached_results:
            cached_results[date_str] = load_results_for_date(date_str)
        race_data = cached_results[date_str].get((jcd, race_no))
        actual = race_data["racers"] if race_data else []

        if not actual:
            continue  # 実績データなし（当日など）

        ev = evaluate_prediction(pred_log, actual)
        if not ev:
            continue
        bet_ev = evaluate_bets(pred_log, race_data.get("won3", "") if race_data else "")

        total += 1
        hit_1st      += int(ev["hit_1st"])
        hit_top3_box += int(ev["hit_top3_box"])
        hit_top3_all += int(ev["hit_top3_all"])
        hit_top2_ord += int(ev["hit_top2_ord"])
        hit_top2_box += int(ev["hit_top2_box"])
        hit_bet_any  += int(bet_ev["hit_bet_any"])
        hit_bet1     += int(bet_ev["hit_bet1"])
        hit_bet2     += int(bet_ev["hit_bet2"])
        hit_bet3     += int(bet_ev["hit_bet3"])
        # v5.16
        hit_honmei   += int(bet_ev.get("hit_honmei", False))
        hit_others   += int(bet_ev.get("hit_others", False))
        hit_taikou   += int(bet_ev.get("hit_taikou", False))
        hit_oshi     += int(bet_ev.get("hit_oshi",   False))
        hit_ana      += int(bet_ev.get("hit_ana",    False))
        rank_sum     += ev["pred_1st_actual_rank"]

        preds  = pred_log.get("predictions", [])
        p_waku = [r["waku"] for r in preds]

        pred_1 = pred_log["predictions"][0] if pred_log["predictions"] else {}
        actual_top3 = sorted(actual, key=lambda r: r["rank"])[:3]
        a_wakus = [r["waku"] for r in actual_top3]
        p_wakus = p_waku[:3]

        # ── 買い目3点を予測リストから再構成 ─────────────────
        logged_bets = bet_ev["bet_combos"]
        if logged_bets:
            combo1 = logged_bets[0] if len(logged_bets) >= 1 else "---"
            combo2 = logged_bets[1] if len(logged_bets) >= 2 else "---"
            combo3 = logged_bets[2] if len(logged_bets) >= 3 else "---"
        elif len(p_waku) >= 3:
            combo1 = f"{p_waku[0]}-{p_waku[1]}-{p_waku[2]}"
            combo2 = f"{p_waku[0]}-{p_waku[2]}-{p_waku[1]}"
            combo3 = (f"{p_waku[3]}-{p_waku[0]}-{p_waku[1]}"
                      if len(p_waku) >= 4 else
                      f"{p_waku[0]}-{p_waku[1]}-{p_waku[2]}")
        else:
            combo1 = combo2 = combo3 = "---"

        # ── 詳細リストに追記 ────────────────────────────────
        race_details_by_date[date_str].append({
            "race_no":   race_no,
            "combo1":    combo1,
            "combo2":    combo2,
            "combo3":    combo3,
            "bet_combos": bet_ev["bet_combos"],
            "honmei_combos": bet_ev.get("honmei_combos", []),
            "others_combos": bet_ev.get("others_combos", []),
            "taikou_combos": bet_ev.get("taikou_combos", []),
            "ana_combos":    bet_ev.get("ana_combos", []),
            "oshi_combos":   bet_ev.get("oshi_combos", []),
            "won3":      race_data.get("won3",     "") if race_data else "",
            "won3_pay":  race_data.get("won3_pay", 0)  if race_data else 0,
            "won3_pop":  race_data.get("won3_pop", 0)  if race_data else 0,
            "race_type": race_data.get("race_type","") if race_data else "",
            "hit_3tan":  ev["hit_top3_all"],
            "hit_3fuku": ev["hit_top3_box"],
            "hit_bet_any": bet_ev["hit_bet_any"],
            "hit_bet1": bet_ev["hit_bet1"],
            "hit_bet2": bet_ev["hit_bet2"],
            "hit_bet3": bet_ev["hit_bet3"],
            # v5.16
            "hit_honmei": bet_ev.get("hit_honmei", False),
            "hit_others": bet_ev.get("hit_others", False),
            "hit_taikou": bet_ev.get("hit_taikou", False),
            "hit_oshi":   bet_ev.get("hit_oshi",   False),
            "hit_ana":    bet_ev.get("hit_ana",    False),
            # v5.19 #1: セオリーパターン発動追跡
            "triggered_patterns": pred_log.get("triggered_patterns", {}),
            "applied_patterns":   pred_log.get("applied_patterns", []),
            # v5.19 #3: 本命の今節成績（series_score 効果検証用）
            "honmei_series_ranks": ((pred_1.get("raw_metrics", {}) or {}).get("series", {}) or {}).get("ranks", []),
            # v5.19 #3 改良: コース補正用（racecard再取得後に入る）
            "honmei_series_races": _load_racecard_series_races(jcd, date_str, race_no, pred_1.get("waku")),
            # v5.20〜: 予測バージョン（ロジック改修の効果測定用）
            "version": pred_log.get("version", "pre-v5.20"),
        })

        if verbose:
            mark = "✅" if ev["hit_top3_box"] else "❌"
            print(f"  {mark} {date_str} R{race_no:2d}  "
                  f"予{p_wakus} → 実{a_wakus}  "
                  f"予1位={pred_1.get('waku','-')}枠({pred_1.get('name','?')})  "
                  f"実際{ev['pred_1st_actual_rank']}位  "
                  f"{'1着✓' if ev['hit_1st'] else ''}"
                  f"{'3複✓' if ev['hit_top3_box'] else ''}"
                  f"{'3単✓' if ev['hit_top3_all'] else ''}")

    if total == 0:
        print("  対象データなし（実績CSVが揃っていないか、日付範囲に予測ログがありません）")
        return None

    # ── 集計表示 ────────────────────────────────────────────────
    print(f"\n  検証レース数:   {total} R")
    print(f"  1着的中率:     {hit_1st}/{total}  ({hit_1st/total*100:.1f}%)")
    print(f"  ★ レース的中率: {hit_bet_any}/{total}  ({hit_bet_any/total*100:.1f}%)  ← 買い目のいずれかが3連単的中")
    print(f"     本命:      {hit_honmei}/{total}  ({hit_honmei/total*100:.1f}%)")
    print(f"     その他:    {hit_others}/{total}  ({hit_others/total*100:.1f}%)  (対抗{hit_taikou} / 抑え{hit_oshi} / 穴{hit_ana})")
    print(f"  予測1位の平均着順: {rank_sum/total:.2f}  (理想値:1.0)")
    # 補足指標（従来互換）
    print(f"  (参考) 3連複: {hit_top3_box}/{total}({hit_top3_box/total*100:.1f}%) / 3連単(順位一致): {hit_top3_all}/{total}({hit_top3_all/total*100:.1f}%)")
    print()

    # ── 月別集計 ────────────────────────────────────────────────
    monthly = defaultdict(lambda: {"total":0,"hit_1st":0,"hit_top3_box":0})
    for log_path in sorted(LOG_DIR.rglob(f"{jcd}_R*_pred.json")):
        date_str = log_path.parent.name
        if date_str < date_from or date_str > date_to:
            continue
        pred_log = load_json(log_path)
        if not pred_log:
            continue
        race_no = pred_log.get("race_no", 0)
        if date_str not in cached_results:
            cached_results[date_str] = load_results_for_date(date_str)
        race_data2 = cached_results[date_str].get((jcd, race_no))
        actual2    = race_data2["racers"] if race_data2 else []
        if not actual2:
            continue
        ev = evaluate_prediction(pred_log, actual2)
        if not ev:
            continue
        ym = date_str[:6]
        monthly[ym]["total"]        += 1
        monthly[ym]["hit_1st"]      += int(ev["hit_1st"])
        monthly[ym]["hit_top3_box"] += int(ev["hit_top3_box"])

    if len(monthly) > 1:
        print(f"  {'月':8s}  {'R数':>5}  {'1着%':>7}  {'3連複%':>8}")
        print(f"  {'─'*35}")
        for ym in sorted(monthly.keys()):
            m = monthly[ym]
            t = m["total"]
            print(f"  {ym[:4]}/{ym[4:]:>2s}    "
                  f"{t:>5d}  "
                  f"{m['hit_1st']/t*100:>6.1f}%  "
                  f"{m['hit_top3_box']/t*100:>7.1f}%")

    print(f"\n{'='*72}")

    # ── v5.19 #1: セオリーパターン別ヒット率集計 ─────────────────
    pattern_thresholds = {"2差し": 0.60, "3カド": 0.60, "4カドまくり": 0.60, "外差し": 0.55}
    pattern_stats: dict[str, dict] = {
        name: {"triggered": 0, "triggered_hit": 0, "applied": 0, "applied_hit": 0}
        for name in pattern_thresholds
    }
    all_details = [d for details in race_details_by_date.values() for d in details]
    for d in all_details:
        tp = d.get("triggered_patterns") or {}
        ap = d.get("applied_patterns") or []
        hit = bool(d.get("hit_bet_any"))
        for name, thr in pattern_thresholds.items():
            conf = tp.get(name, 0) or 0
            if conf >= thr:
                pattern_stats[name]["triggered"] += 1
                if hit:
                    pattern_stats[name]["triggered_hit"] += 1
            if name in ap:
                pattern_stats[name]["applied"] += 1
                if hit:
                    pattern_stats[name]["applied_hit"] += 1

    if any(s["triggered"] > 0 or s["applied"] > 0 for s in pattern_stats.values()):
        print("  ── セオリーパターン別（v5.19 #1）──")
        print(f"  {'パターン':<10} {'発動':>6} {'発動時的中':>12} {'適用':>6} {'適用時的中':>12}")
        for name, s in pattern_stats.items():
            tr_pct = f"{s['triggered_hit']/s['triggered']*100:.1f}%" if s["triggered"] else "-"
            ap_pct = f"{s['applied_hit']/s['applied']*100:.1f}%"     if s["applied"]   else "-"
            print(f"  {name:<10} {s['triggered']:>6} {tr_pct:>12} {s['applied']:>6} {ap_pct:>12}")
        print()

    # ── v5.19 #3: series_score 効果検証（走数帯別の本命ヒット率） ──
    # 本命(pred_1) の今節走数で層別し、series_score が的中と相関しているか確認
    # 帯: 0走（初日）/ 1-3走 / 4-6走 / 7走+
    def _series_band(n: int) -> str:
        if n <= 0:   return "0走(初日)"
        if n <= 3:   return "1-3走"
        if n <= 6:   return "4-6走"
        return "7走+"

    series_bands = ["0走(初日)", "1-3走", "4-6走", "7走+"]
    series_stats: dict[str, dict] = {
        b: {"n": 0, "honmei_hit": 0, "top2_rt_sum": 0.0, "avg_rk_sum": 0.0}
        for b in series_bands
    }
    for d in all_details:
        ranks = d.get("honmei_series_ranks") or []
        n = len(ranks)
        band = _series_band(n)
        series_stats[band]["n"] += 1
        series_stats[band]["honmei_hit"] += int(bool(d.get("hit_honmei")))
        if n > 0:
            series_stats[band]["top2_rt_sum"] += sum(1 for r in ranks if r <= 2) / n
            series_stats[band]["avg_rk_sum"]  += sum(ranks) / n

    # ── v5.20: 予測バージョン別ヒット率（ロジック改修の効果測定）──
    ver_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "hit_1st": 0, "hit_3fuku": 0, "hit_bet_any": 0, "hit_honmei": 0
    })
    for d in all_details:
        v = d.get("version") or "pre-v5.20"
        s = ver_stats[v]
        s["total"] += 1
        s["hit_1st"]     += int(bool(d.get("hit_bet1")) or 0)  # 便宜: 1着指標は別集計
        s["hit_3fuku"]   += int(bool(d.get("hit_3fuku")))
        s["hit_bet_any"] += int(bool(d.get("hit_bet_any")))
        s["hit_honmei"]  += int(bool(d.get("hit_honmei")))
    if len(ver_stats) > 0:
        print("  ── バージョン別ヒット率（v5.20〜）──")
        print(f"  {'version':<12} {'R数':>5} {'3複':>7} {'全体':>7} {'本命':>7}")
        for v, s in sorted(ver_stats.items()):
            if s["total"] == 0: continue
            print(f"  {v:<12} {s['total']:>5} "
                  f"{s['hit_3fuku']/s['total']*100:>6.1f}% "
                  f"{s['hit_bet_any']/s['total']*100:>6.1f}% "
                  f"{s['hit_honmei']/s['total']*100:>6.1f}%")
        print()

    if any(s["n"] > 0 for s in series_stats.values()):
        print("  ── series_score 効果検証（v5.19 #3）──")
        print(f"  {'走数帯':<12} {'R数':>5} {'本命的中率':>12} {'平均着順':>10} {'1-2着率':>10}")
        for b in series_bands:
            s = series_stats[b]
            if s["n"] == 0:
                continue
            hit_pct = f"{s['honmei_hit']/s['n']*100:.1f}%"
            if b == "0走(初日)":
                avg_rk_str = "-"
                top2_str   = "-"
            else:
                avg_rk_str = f"{s['avg_rk_sum']/s['n']:.2f}"
                top2_str   = f"{s['top2_rt_sum']/s['n']*100:.1f}%"
            print(f"  {b:<12} {s['n']:>5} {hit_pct:>12} {avg_rk_str:>10} {top2_str:>10}")
        print()

    # ── v5.19 #3 改良: コース補正 series_score 帯別の本命ヒット率 ──
    # 旧: 平均着順ベース / 新: 期待着順-実着順の perf ベース
    # それぞれで本命のスコアを低・中・高に分け、的中率がスコアと正相関しているか確認
    def _score_band(v: float | None) -> str:
        if v is None: return "N/A"
        if v < 0.40:  return "低(<0.40)"
        if v < 0.55:  return "中(0.40-0.55)"
        return "高(≥0.55)"

    def _old_score(ranks: list) -> float | None:
        if not ranks: return None
        n = len(ranks)
        avg_rk = sum(ranks) / n
        top2_rt = sum(1 for r in ranks if r <= 2) / n
        return (6.0 - avg_rk) / 5.0 * 0.7 + top2_rt * 0.3

    bands = ["低(<0.40)", "中(0.40-0.55)", "高(≥0.55)", "N/A"]
    old_stats = {b: {"n": 0, "hit": 0} for b in bands}
    new_stats = {b: {"n": 0, "hit": 0} for b in bands}
    new_available = 0
    for d in all_details:
        hit = bool(d.get("hit_honmei"))
        old_v = _old_score(d.get("honmei_series_ranks") or [])
        new_v = _series_perf_score(d.get("honmei_series_races") or [])
        if d.get("honmei_series_races"):
            new_available += 1
        ob = _score_band(old_v)
        nb = _score_band(new_v)
        old_stats[ob]["n"] += 1
        old_stats[ob]["hit"] += int(hit)
        new_stats[nb]["n"] += 1
        new_stats[nb]["hit"] += int(hit)

    if any(s["n"] > 0 for s in old_stats.values()):
        print(f"  ── series_score 新旧比較（v5.19 #3, 新ロジックracecard={new_available}R）──")
        print(f"  {'スコア帯':<16} {'旧R数':>7} {'旧本命的中':>12} {'新R数':>7} {'新本命的中':>12}")
        for b in bands:
            os_, ns_ = old_stats[b], new_stats[b]
            o_pct = f"{os_['hit']/os_['n']*100:.1f}%" if os_["n"] else "-"
            n_pct = f"{ns_['hit']/ns_['n']*100:.1f}%" if ns_["n"] else "-"
            print(f"  {b:<16} {os_['n']:>7} {o_pct:>12} {ns_['n']:>7} {n_pct:>12}")
        print()

    # ── サマリーを返す（保存・呼び出し元での利用のため） ─────────
    summary = {
        "run_date":      datetime.date.today().strftime("%Y-%m-%d"),
        "jcd":           jcd,
        "date_from":     date_from,
        "date_to":       date_to,
        "total_races":   total,
        "hit_1st":       hit_1st,
        "hit_2tan":      hit_top2_ord,
        "hit_2fuku":     hit_top2_box,
        "hit_3fuku":     hit_top3_box,
        "hit_3tan":      hit_top3_all,
        "hit_bet_any":   hit_bet_any,
        "hit_bet1":      hit_bet1,
        "hit_bet2":      hit_bet2,
        "hit_bet3":      hit_bet3,
        # v5.16
        "hit_honmei":    hit_honmei,
        "hit_others":    hit_others,
        "hit_taikou":    hit_taikou,
        "hit_oshi":      hit_oshi,
        "hit_ana":       hit_ana,
        "hit_honmei_pct": round(hit_honmei / total * 100, 1),
        "hit_others_pct": round(hit_others / total * 100, 1),
        "hit_taikou_pct": round(hit_taikou / total * 100, 1),
        "hit_oshi_pct":   round(hit_oshi   / total * 100, 1),
        "hit_ana_pct":    round(hit_ana    / total * 100, 1),
        "avg_rank":      round(rank_sum / total, 2),
        "hit_1st_pct":   round(hit_1st / total * 100, 1),
        "hit_2tan_pct":  round(hit_top2_ord / total * 100, 1),
        "hit_2fuku_pct": round(hit_top2_box / total * 100, 1),
        "hit_3fuku_pct": round(hit_top3_box / total * 100, 1),
        "hit_3tan_pct":  round(hit_top3_all / total * 100, 1),
        "hit_bet_any_pct": round(hit_bet_any / total * 100, 1),
        "hit_bet1_pct":  round(hit_bet1 / total * 100, 1),
        "monthly":       {
            ym: {
                "total":       m["total"],
                "hit_1st_pct": round(m["hit_1st"]      / m["total"] * 100, 1),
                "hit_3fuku_pct": round(m["hit_top3_box"] / m["total"] * 100, 1),
            }
            for ym, m in sorted(monthly.items())
        },
        # v5.19 #1: セオリーパターン別集計
        "pattern_stats": pattern_stats,
        # v5.19 #3: series_score 効果検証（走数帯別の本命ヒット率）
        "series_stats": series_stats,
        # v5.20〜: バージョン別集計
        "version_stats": dict(ver_stats),
    }
    if save:
        save_verify_log(summary)
        update_verify_md(summary)
        update_verify_html()
        # 日ごとの詳細12行ファイルを保存
        for d_str, details in sorted(race_details_by_date.items()):
            save_verify_detail(jcd, d_str, details)
    return summary


# =============================================================================
# 週次精度レポート（全24会場集計）
# =============================================================================

def _parse_iso_week(s: str) -> tuple[int, int]:
    """'2026-W17' / '2026W17' → (year, week)"""
    m = re.match(r"^(\d{4})-?W(\d{1,2})$", s.strip())
    if not m:
        raise ValueError(f"Invalid ISO week format: {s} (expected: YYYY-Www)")
    return int(m.group(1)), int(m.group(2))


def _iso_week_key(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


def _iso_week_dates(year: int, week: int) -> tuple[datetime.date, datetime.date]:
    monday = datetime.date.fromisocalendar(year, week, 1)
    sunday = datetime.date.fromisocalendar(year, week, 7)
    return monday, sunday


def _prev_iso_week(year: int, week: int) -> tuple[int, int]:
    monday = datetime.date.fromisocalendar(year, week, 1)
    prev_monday = monday - datetime.timedelta(days=7)
    py, pw, _ = prev_monday.isocalendar()
    return py, pw


def _aggregate_pattern_stats(summaries: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for s in summaries:
        for name, ps in (s.get("pattern_stats") or {}).items():
            d = out.setdefault(name, {"triggered": 0, "triggered_hit": 0,
                                      "applied": 0, "applied_hit": 0})
            for k in ("triggered", "triggered_hit", "applied", "applied_hit"):
                d[k] += ps.get(k, 0) or 0
    for d in out.values():
        d["triggered_hit_pct"] = (round(d["triggered_hit"] / d["triggered"] * 100, 1)
                                  if d["triggered"] else 0.0)
        d["applied_hit_pct"] = (round(d["applied_hit"] / d["applied"] * 100, 1)
                                if d["applied"] else 0.0)
    return out


def _aggregate_series_stats(summaries: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for s in summaries:
        for band, ss in (s.get("series_stats") or {}).items():
            d = out.setdefault(band, {"n": 0, "honmei_hit": 0,
                                      "top2_rt_sum": 0.0, "avg_rk_sum": 0.0})
            d["n"] += ss.get("n", 0) or 0
            d["honmei_hit"] += ss.get("honmei_hit", 0) or 0
            d["top2_rt_sum"] += ss.get("top2_rt_sum", 0.0) or 0.0
            d["avg_rk_sum"] += ss.get("avg_rk_sum", 0.0) or 0.0
    for d in out.values():
        n = d["n"]
        d["honmei_hit_pct"] = round(d["honmei_hit"] / n * 100, 1) if n else 0.0
        d["avg_top2_rt"] = round(d["top2_rt_sum"] / n, 2) if n else None
        d["avg_rk"] = round(d["avg_rk_sum"] / n, 2) if n else None
    return out


def _aggregate_version_stats(summaries: list[dict]) -> dict:
    """version_stats の各 venue summary の実体キー: total, hit_1st, hit_3fuku, hit_bet_any, hit_honmei
    (注: ここでの hit_1st は本命の1着的中=hit_bet1 ベースで、純粋な1着的中とは別)
    """
    raw: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for s in summaries:
        for ver, vs in (s.get("version_stats") or {}).items():
            for k, v in vs.items():
                raw[ver][k] += v or 0
    out: dict[str, dict] = {}
    metric_keys = ("hit_1st", "hit_bet_any", "hit_3fuku", "hit_honmei")
    for ver, d in raw.items():
        n = d.get("total", 0)
        rec = {"n": n, "total": n}
        for k in metric_keys:
            rec[k] = d.get(k, 0)
            rec[f"{k}_pct"] = round(d.get(k, 0) / n * 100, 1) if n else 0.0
        out[ver] = rec
    return out


def _save_accuracy_files(week_key: str, accuracy: dict) -> None:
    ACCURACY_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ACCURACY_DIR / f"{week_key}.json"
    json_text = json.dumps(accuracy, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    md_path = ACCURACY_DIR / f"{week_key}.md"
    md_path.write_text(_render_accuracy_md(accuracy), encoding="utf-8")
    print(f"  💾 週次レポート保存: {json_path}")
    print(f"  💾 週次レポート保存: {md_path}")
    # WordPress プラグインへもミラー (GitHub Actions が heteml に自動デプロイ)
    WP_ACCURACY_DIR.mkdir(parents=True, exist_ok=True)
    (WP_ACCURACY_DIR / f"{week_key}.json").write_text(json_text, encoding="utf-8")
    print(f"  💾 WPミラー保存: {WP_ACCURACY_DIR / (week_key + '.json')}")


def _update_accuracy_index() -> None:
    ACCURACY_DIR.mkdir(parents=True, exist_ok=True)
    weeks: list[dict] = []
    for p in sorted(ACCURACY_DIR.glob("*.json")):
        if p.name == "index.json":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        o = d.get("overall", {})
        weeks.append({
            "week": d.get("week"),
            "date_from": d.get("date_from"),
            "date_to": d.get("date_to"),
            "total_races": o.get("total_races"),
            "hit_1st_pct": o.get("hit_1st_pct"),
            "hit_bet_any_pct": o.get("hit_bet_any_pct"),
            "hit_3tan_pct": o.get("hit_3tan_pct"),
        })
    weeks.sort(key=lambda w: w.get("week") or "", reverse=True)
    idx = {
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "weeks": weeks,
    }
    idx_text = json.dumps(idx, ensure_ascii=False, indent=2)
    (ACCURACY_DIR / "index.json").write_text(idx_text, encoding="utf-8")
    WP_ACCURACY_DIR.mkdir(parents=True, exist_ok=True)
    (WP_ACCURACY_DIR / "index.json").write_text(idx_text, encoding="utf-8")


def _render_accuracy_md(a: dict) -> str:
    o = a["overall"]
    n = o.get("total_races", 0)
    lines = [
        f"# 週次精度レポート {a['week']}",
        "",
        f"期間: **{a['date_from']} 〜 {a['date_to']}**　／　生成: {a['generated_at']}",
        "",
        "## 全体サマリ",
        "",
        f"- 総レース数: **{n}R**　／　対象会場: {o.get('venues_with_data', 0)}",
        f"- 1着的中率:    **{o.get('hit_1st_pct', 0)}%**　({o.get('hit_1st', 0)}/{n})",
        f"- 買い目的中率: **{o.get('hit_bet_any_pct', 0)}%**　({o.get('hit_bet_any', 0)}/{n})",
        f"- 3連単的中率:  **{o.get('hit_3tan_pct', 0)}%**　({o.get('hit_3tan', 0)}/{n})",
        f"- 3連複的中率:  {o.get('hit_3fuku_pct', 0)}%　({o.get('hit_3fuku', 0)}/{n})",
        f"- 本命的中率:   {o.get('hit_honmei_pct', 0)}%　／　対抗: {o.get('hit_taikou_pct', 0)}%　／　穴: {o.get('hit_ana_pct', 0)}%　／　押さえ: {o.get('hit_oshi_pct', 0)}%",
    ]
    diff = a.get("diff_prev_week") or {}
    if diff:
        parts = []
        for k, v in diff.items():
            sign = "+" if v > 0 else ""
            parts.append(f"{k} {sign}{v}")
        lines += ["", f"**前週比**: {' / '.join(parts)}"]

    if a.get("by_venue"):
        lines += ["",
                  "## 会場別ランキング (買い目的中率順)",
                  "",
                  "| 順 | 会場 | R数 | 1着% | 買い目% | 3連単% | 平均着順 |",
                  "|---|---|---:|---:|---:|---:|---:|"]
        for i, v in enumerate(a["by_venue"], 1):
            lines.append(
                f"| {i} | {v['name']} | {v['n']} | {v['hit_1st_pct']}% | "
                f"{v['hit_bet_any_pct']}% | {v['hit_3tan_pct']}% | {v['avg_rank']} |"
            )

    if a.get("by_pattern"):
        lines += ["", "## セオリーパターン別",
                  "",
                  "| パターン | 発動R | 発動的中% | 採用R | 採用的中% |",
                  "|---|---:|---:|---:|---:|"]
        for name, p in a["by_pattern"].items():
            lines.append(
                f"| {name} | {p['triggered']} | {p['triggered_hit_pct']}% | "
                f"{p['applied']} | {p['applied_hit_pct']}% |"
            )

    if a.get("by_series_band"):
        lines += ["", "## シリーズ走数帯別 (本命的中率)",
                  "",
                  "| 走数帯 | n | 本命的中% | 平均着順 |",
                  "|---|---:|---:|---:|"]
        for band in ("0走", "1-3走", "4-6走", "7走+"):
            d = a["by_series_band"].get(band)
            if not d:
                continue
            lines.append(
                f"| {band} | {d['n']} | {d.get('honmei_hit_pct', 0)}% | "
                f"{d.get('avg_rk', '-')} |"
            )

    if a.get("by_version"):
        lines += ["", "## バージョン別",
                  "",
                  "| version | n | 本命1着% | 買い目% | 3連複% | 本命% |",
                  "|---|---:|---:|---:|---:|---:|"]
        for ver, d in sorted(a["by_version"].items()):
            lines.append(
                f"| {ver} | {d['n']} | {d.get('hit_1st_pct', 0)}% | "
                f"{d.get('hit_bet_any_pct', 0)}% | {d.get('hit_3fuku_pct', 0)}% | "
                f"{d.get('hit_honmei_pct', 0)}% |"
            )

    return "\n".join(lines) + "\n"


def _print_weekly_summary(a: dict) -> None:
    o = a["overall"]
    n = o.get("total_races", 0)
    print(f"\n{'='*72}")
    print(f"  📈 週次精度レポート  {a['week']}  {a['date_from']}〜{a['date_to']}")
    print(f"{'='*72}")
    print(f"  対象: {n}R　／　会場: {o.get('venues_with_data', 0)}")
    print(f"  1着:    {o.get('hit_1st_pct', 0)}%  ({o.get('hit_1st', 0)}/{n})")
    print(f"  買い目: {o.get('hit_bet_any_pct', 0)}%  ({o.get('hit_bet_any', 0)}/{n})")
    print(f"  3連単:  {o.get('hit_3tan_pct', 0)}%  ({o.get('hit_3tan', 0)}/{n})")
    print(f"  本命:   {o.get('hit_honmei_pct', 0)}%　対抗:{o.get('hit_taikou_pct', 0)}%　穴:{o.get('hit_ana_pct', 0)}%　押:{o.get('hit_oshi_pct', 0)}%")
    if a.get("diff_prev_week"):
        diffs = ", ".join(f"{k}={('+' if v>0 else '')}{v}" for k, v in a["diff_prev_week"].items())
        print(f"  前週比: {diffs}")
    if a.get("by_venue"):
        print(f"\n  会場 TOP5 (買い目%):")
        for v in a["by_venue"][:5]:
            print(f"    {v['name']:>5}  R={v['n']:>3}  買目={v['hit_bet_any_pct']:>5}%  1着={v['hit_1st_pct']:>5}%")


def run_weekly_report(week_iso: str | None = None,
                      refresh: bool = True,
                      save: bool = True,
                      quiet: bool = True) -> dict | None:
    """全24会場の週次精度レポートを生成。

    refresh=True (default): 各会場 run_verification を再実行して verify_history を更新
    quiet=True (default):   各会場 run_verification の冗長 stdout を抑制
    """
    if week_iso:
        year, week = _parse_iso_week(week_iso)
    else:
        today = datetime.date.today()
        year, week, _ = today.isocalendar()

    monday, sunday = _iso_week_dates(year, week)
    today = datetime.date.today()
    date_to_d = min(sunday, today)
    df = monday.strftime("%Y%m%d")
    dt = date_to_d.strftime("%Y%m%d")
    week_key = _iso_week_key(year, week)

    print(f"\n[週次レポート開始] {week_key}  {df}〜{dt}  refresh={refresh}")

    summaries: list[dict] = []
    for jcd in sorted(VENUE_NAMES.keys()):
        if refresh:
            if quiet:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    s = run_verification(jcd, df, dt, verbose=False, save=True)
            else:
                s = run_verification(jcd, df, dt, verbose=False, save=True)
        else:
            history = load_verify_history()
            s = next((r for r in reversed(history)
                      if r.get("jcd") == jcd
                      and r.get("date_from") == df
                      and r.get("date_to") == dt), None)
        if s and s.get("total_races", 0) > 0:
            summaries.append(s)
            print(f"  ✓ {VENUE_NAMES.get(jcd, jcd)}({jcd}): {s['total_races']}R / 買目={s.get('hit_bet_any_pct', 0)}%")
        else:
            print(f"  ・{VENUE_NAMES.get(jcd, jcd)}({jcd}): データなし")

    if not summaries:
        print("\n  ⚠ 対象データなし。週次レポートを生成しませんでした。")
        return None

    total = sum(s["total_races"] for s in summaries)
    sum_keys = ("hit_1st", "hit_3tan", "hit_3fuku", "hit_2tan", "hit_2fuku",
                "hit_bet_any", "hit_bet1", "hit_bet2", "hit_bet3",
                "hit_honmei", "hit_others", "hit_taikou", "hit_oshi", "hit_ana")
    overall = {
        "total_races": total,
        "venues_with_data": len(summaries),
        **{k: sum(s.get(k, 0) for s in summaries) for k in sum_keys},
    }
    if total:
        for k in sum_keys:
            overall[f"{k}_pct"] = round(overall[k] / total * 100, 1)
        rank_total = sum((s.get("avg_rank", 0.0) or 0.0) * s["total_races"]
                         for s in summaries)
        overall["avg_rank"] = round(rank_total / total, 2)

    by_venue = sorted([
        {
            "jcd": s["jcd"],
            "name": VENUE_NAMES.get(s["jcd"], s["jcd"]),
            "n": s["total_races"],
            "hit_1st_pct": s.get("hit_1st_pct", 0.0),
            "hit_bet_any_pct": s.get("hit_bet_any_pct", 0.0),
            "hit_3tan_pct": s.get("hit_3tan_pct", 0.0),
            "hit_3fuku_pct": s.get("hit_3fuku_pct", 0.0),
            "hit_honmei_pct": s.get("hit_honmei_pct", 0.0),
            "avg_rank": s.get("avg_rank", 0.0),
        }
        for s in summaries
    ], key=lambda v: -v["hit_bet_any_pct"])

    by_pattern = _aggregate_pattern_stats(summaries)
    by_series_band = _aggregate_series_stats(summaries)
    by_version = _aggregate_version_stats(summaries)

    diff_prev_week: dict = {}
    py, pw = _prev_iso_week(year, week)
    prev_path = ACCURACY_DIR / f"{_iso_week_key(py, pw)}.json"
    if prev_path.exists():
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
            po = prev.get("overall", {})
            for k in ("hit_1st_pct", "hit_bet_any_pct", "hit_3tan_pct",
                      "hit_honmei_pct"):
                if k in overall and k in po:
                    diff_prev_week[k] = round(overall[k] - po[k], 1)
        except Exception:
            pass

    accuracy = {
        "week": week_key,
        "date_from": df,
        "date_to": dt,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "by_venue": by_venue,
        "by_pattern": by_pattern,
        "by_series_band": by_series_band,
        "by_version": by_version,
        "diff_prev_week": diff_prev_week,
    }

    if save:
        _save_accuracy_files(week_key, accuracy)
        _update_accuracy_index()

    _print_weekly_summary(accuracy)
    return accuracy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="予測精度検証スクリプト")
    parser.add_argument("--jcd",     default="22",
                        help="会場コード (デフォルト: 22=福岡)")
    parser.add_argument("--from",    dest="date_from",
                        default="20250101",
                        help="集計開始日 YYYYMMDD (デフォルト: 20250101)")
    parser.add_argument("--to",      dest="date_to",
                        default=datetime.date.today().strftime("%Y%m%d"),
                        help="集計終了日 YYYYMMDD (デフォルト: 今日)")
    parser.add_argument("--verbose",  action="store_true",
                        help="レース単位の詳細を表示")
    parser.add_argument("--no-save", action="store_true",
                        help="結果をverify_history.jsonに保存しない")
    parser.add_argument("--report", choices=["weekly"],
                        help="集計モード (weekly = 全24会場の週次精度レポート生成)")
    parser.add_argument("--week",
                        help="ISO週指定 例: 2026-W17 (省略時は現在の週)")
    parser.add_argument("--no-refresh", action="store_true",
                        help="--report 時に各会場の verify を再実行しない (履歴のみ集計)")
    args = parser.parse_args()

    if args.report == "weekly":
        run_weekly_report(week_iso=args.week,
                          refresh=not args.no_refresh,
                          save=not args.no_save)
    else:
        run_verification(args.jcd, args.date_from, args.date_to,
                         verbose=args.verbose, save=not args.no_save)
