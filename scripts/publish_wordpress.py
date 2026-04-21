#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_FILE = BASE_DIR / "config.json"
FEMALE_PLAYERS_FILE = DATA_DIR / "players" / "female_players.json"
VERIFY_HISTORY_FILE = DATA_DIR / "logs" / "verify_history.json"
VERIFY_DETAIL_DIR = OUTPUT_DIR / "data" / "verify"
RESULTS_DIR = DATA_DIR / "results_csv"

VENUE_SLUGS = {
    "01": "kiryu",
    "02": "toda",
    "03": "edogawa",
    "04": "heiwajima",
    "05": "tamagawa",
    "06": "hamanako",
    "07": "gamagori",
    "08": "tokoname",
    "09": "tsu",
    "10": "mikuni",
    "11": "biwako",
    "12": "suminoe",
    "13": "amagasaki",
    "14": "naruto",
    "15": "marugame",
    "16": "kojima",
    "17": "miyajima",
    "18": "tokuyama",
    "19": "shimonoseki",
    "20": "wakamatsu",
    "21": "ashiya",
    "22": "fukuoka",
    "23": "karatsu",
    "24": "omura",
}

FEMALE_REG_NOS: set[str] = set()


def _init_female_players() -> None:
    global FEMALE_REG_NOS
    if not FEMALE_PLAYERS_FILE.exists():
        FEMALE_REG_NOS = set()
        return
    try:
        data = json.loads(FEMALE_PLAYERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        FEMALE_REG_NOS = set()
        return
    reg_nos = data.get("reg_nos", []) if isinstance(data, dict) else []
    FEMALE_REG_NOS = {str(x) for x in reg_nos}


def is_female_reg(reg_no: str) -> bool:
    return str(reg_no or "") in FEMALE_REG_NOS


_init_female_players()


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_start_times(jcd: str, date: str) -> dict[str, str]:
    path = DATA_DIR / "racecards" / date / f"{jcd}_start_times.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_racecard(jcd: str, date: str, race_no: int) -> dict:
    path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_prediction(jcd: str, date: str, race_no: int) -> dict:
    path = DATA_DIR / "logs" / date / f"{jcd}_R{race_no:02d}_pred.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_results_for_date(date_str: str) -> dict[tuple[str, int], dict]:
    path = RESULTS_DIR / f"{date_str}.csv"
    if not path.exists():
        return {}
    import csv

    results = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key_date = row.get("\ufeffdate", row.get("date", "")).strip()
            jcd = ""
            venue_name = row.get("venue_name", "").strip()
            for code, name in load_config()["venues"].items():
                if name == venue_name:
                    jcd = code
                    break
            if key_date != date_str or not jcd:
                continue
            race_no = int(row.get("race_no", 0) or 0)
            key = (jcd, race_no)
            results.setdefault(key, {
                "racers": [],
                "won3": row.get("won3", "").strip(),
                "won3_pay": int(row.get("won3_pay", 0) or 0),
                "won3_pop": int(row.get("won3_pop", 0) or 0),
                "race_type": row.get("race_type", "").strip(),
            })
            rank = int(row.get("rank", 0) or 0)
            waku = int(row.get("waku", 0) or 0)
            if rank and waku:
                results[key]["racers"].append({"rank": rank, "waku": waku})
    return results


def load_verify_history() -> list[dict]:
    if not VERIFY_HISTORY_FILE.exists():
        return []
    try:
        return json.loads(VERIFY_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def clean_review_line(text: str) -> str:
    line = str(text or "").strip()
    line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def strip_html(text: str) -> str:
    raw = re.sub(r"<[^>]+>", "", str(text or ""))
    return clean_review_line(html.unescape(raw))


def load_verify_detail_tables(venue_name: str, date: str) -> dict:
    path = VERIFY_DETAIL_DIR / f"verify_detail_{venue_name}_{date}.html"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    tables = re.findall(r"<table>(.*?)</table>", text, flags=re.S)
    if len(tables) < 2:
        return {}

    def parse_rows(table_html: str) -> list[list[str]]:
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S):
            cols = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S)
            rows.append([strip_html(col) for col in cols])
        return rows

    race_rows = parse_rows(tables[0])
    bet_rows = parse_rows(tables[1])
    if len(race_rows) < 2 or len(bet_rows) < 2:
        return {}

    return {
        "race_table": {
            "headers": race_rows[0],
            "rows": race_rows[1:],
        },
        "bet_history_table": {
            "headers": bet_rows[0],
            "rows": bet_rows[1:],
        },
    }


def evaluate_prediction_order(pred_log: dict, actual_results: list[dict]) -> dict:
    predictions = pred_log.get("predictions", [])
    actual_sorted = sorted(actual_results, key=lambda r: r["rank"])
    pred_order = [int(p["waku"]) for p in predictions if p.get("waku")]
    actual_order = [int(r["waku"]) for r in actual_sorted if r.get("waku")]
    if len(actual_order) < 3 or len(pred_order) < 3:
        return {}
    p1, p2, p3 = pred_order[:3]
    a1, a2, a3 = actual_order[:3]
    return {
        "hit_top3_all": (p1, p2, p3) == (a1, a2, a3),
        "hit_top3_box": set([p1, p2, p3]) == set([a1, a2, a3]),
    }


def build_review_tables_from_logs(jcd: str, date: str) -> dict:
    """v5.18: honmei/others 構造に対応したレース別結果テーブルを構築する。"""
    results = load_results_for_date(date)
    race_rows = []
    bet_history = {"本命": [], "対抗": [], "穴": [], "抑え": []}

    for race_no in range(1, 13):
        try:
            pred_log = load_prediction(jcd, date, race_no)
        except FileNotFoundError:
            continue
        race_data = results.get((jcd, race_no))
        if not race_data:
            continue

        actual_won3 = race_data.get("won3", "")

        # v5.16 構造を優先、旧形式フォールバック
        honmei_combos = []
        others_by_sub: dict[str, list[str]] = {"対抗": [], "穴": [], "抑え": []}
        all_combos: list[tuple[str, str]] = []  # (category, combo)

        if "honmei" in pred_log or "others" in pred_log:
            for b in pred_log.get("honmei", []) or []:
                c = b.get("combo", "")
                if c:
                    honmei_combos.append(c)
                    all_combos.append(("本命", c))
            for b in pred_log.get("others", []) or []:
                c = b.get("combo", "")
                sub = b.get("subtype", "")
                if c and sub in others_by_sub:
                    others_by_sub[sub].append(c)
                    all_combos.append((sub, c))
        else:
            # 旧形式フォールバック
            for bet in pred_log.get("bets", []) or []:
                label = str(bet.get("label", ""))
                combo = str(bet.get("combo", ""))
                if not combo:
                    continue
                if label in ("本命①", "本命②"):
                    honmei_combos.append(combo)
                    all_combos.append(("本命", combo))
                elif label == "穴":
                    others_by_sub["穴"].append(combo)
                    all_combos.append(("穴", combo))
                elif label == "出目④":
                    others_by_sub["抑え"].append(combo)
                    all_combos.append(("抑え", combo))

        # 的中判定
        hit_category = ""
        hit_combo = ""
        for cat, combo in all_combos:
            if combo == actual_won3 and not hit_category:
                hit_category = cat
                hit_combo = combo
                break

        if hit_category:
            bet_history.setdefault(hit_category, []).append(f"{race_no}R")

        ev = evaluate_prediction_order(pred_log, race_data.get("racers", []))
        if hit_category:
            verdict = f"買い目的中（{hit_category} {hit_combo}）"
        elif ev.get("hit_top3_all"):
            verdict = "予測3連単一致"
        elif ev.get("hit_top3_box"):
            verdict = "3連複のみ"
        else:
            verdict = "不的中"

        race_rows.append([
            f"{race_no}R",
            normalize_race_name(race_data.get("race_type", "")),
            " / ".join(honmei_combos) or "—",
            " / ".join(others_by_sub["対抗"]) or "—",
            " / ".join(others_by_sub["穴"]) or "—",
            " / ".join(others_by_sub["抑え"]) or "—",
            actual_won3 or "—",
            f"{race_data.get('won3_pop', 0)}番人気" if race_data.get("won3_pop") else "—",
            f"{race_data.get('won3_pay', 0):,}円" if race_data.get("won3_pay") else "—",
            verdict,
        ])

    history_rows = []
    total = len(race_rows)
    for label in ["本命", "対抗", "穴", "抑え"]:
        hits = bet_history.get(label, [])
        rate = (len(hits) / total * 100.0) if total else 0.0
        history_rows.append([
            label,
            str(len(hits)),
            f"{rate:.1f}%",
            ", ".join(hits) if hits else "なし",
        ])

    return {
        "race_table": {
            "headers": ["R", "種別", "本命", "対抗", "穴", "抑え", "結果", "人気", "配当", "買い目判定"],
            "rows": race_rows,
        },
        "bet_history_table": {
            "headers": ["買い目", "的中数", "的中率", "該当R"],
            "rows": history_rows,
        },
    }


def load_verify_detail_lines(venue_name: str, date: str) -> dict:
    path = VERIFY_DETAIL_DIR / f"verify_detail_{venue_name}_{date}.md"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}

    race_lines: list[str] = []
    summary_lines: list[str] = []
    trend_lines: list[str] = []
    section = "races"

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            continue
        if line == "---":
            continue
        if line.startswith("## 振り返り分析"):
            section = "summary"
            continue
        if line.startswith("### 傾向コメント"):
            section = "trend"
            continue

        if section == "races":
            race_lines.append(clean_review_line(line))
        elif section == "summary" and line.startswith("- "):
            summary_lines.append(clean_review_line(line[2:]))
        elif section == "trend" and line.startswith("- "):
            trend_lines.append(clean_review_line(line[2:]))

    return {
        "race_lines": race_lines,
        "summary_lines": summary_lines,
        "trend_lines": trend_lines,
        "detail_file": f"verify_detail_{venue_name}_{date}.html",
    }


def classify_confidence(value: str) -> tuple[int, str]:
    raw = str(value or "").strip()
    if raw.endswith("%"):
        pct = int(raw.rstrip("%"))
    elif set(raw) <= {"★", "☆"} and "★" in raw:
        star_count = raw.count("★")
        pct_map = {
            5: 90,
            4: 80,
            3: 70,
            2: 55,
            1: 40,
        }
        pct = pct_map.get(star_count, 0)
    else:
        m = re.search(r"(\d+)", raw)
        pct = int(m.group(1)) if m else 0
    if pct >= 80:
        label = "high"
    elif pct >= 60:
        label = "mid"
    else:
        label = "low"
    return pct, label


def normalize_race_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"\s*1800m$", "", text, flags=re.IGNORECASE).strip()
    return text


def pick_bet(pred: dict, label: str) -> tuple[str, str]:
    for bet in pred.get("bets", []):
        if bet.get("label") == label:
            return bet.get("combo", ""), bet.get("reason", "")
    return "", ""


def pick_bets(pred: dict, label: str) -> list[dict]:
    """
    旧ラベルベースのピッカー（v5.16 以前の pred.json 互換用）。

    v5.16 では pred.json に `honmei` / `others` が直接入っているので
    pick_bets_v2() を使うのが望ましい。このヘルパーは後方互換のため残置。
    """
    rows = []
    for bet in pred.get("bets", []):
        if bet.get("label") == label:
            rows.append({
                "combo": bet.get("combo", ""),
                "reason": bet.get("reason", ""),
            })
    return rows


def pick_bets_v2(pred: dict) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    v5.16 構造の pred.json から (main_bets, sub_bets, longshot_bets, cover_bets) を返す。

    - main_bets  : honmei 配列 (最大4点)
    - sub_bets   : others の subtype="対抗"
    - longshot_bets: others の subtype="穴"
    - cover_bets : others の subtype="抑え"

    pred.json に `honmei` / `others` が無い旧形式なら pick_bets(label) で組み立て直す。
    """
    if "honmei" in pred or "others" in pred:
        main_bets = [
            {"combo": b.get("combo", ""), "reason": b.get("reason", "")}
            for b in pred.get("honmei", []) or []
        ]
        others = pred.get("others", []) or []
        sub_bets      = [{"combo": b.get("combo",""), "reason": b.get("reason","")} for b in others if b.get("subtype") == "対抗"]
        longshot_bets = [{"combo": b.get("combo",""), "reason": b.get("reason","")} for b in others if b.get("subtype") == "穴"]
        cover_bets    = [{"combo": b.get("combo",""), "reason": b.get("reason","")} for b in others if b.get("subtype") == "抑え"]
        return main_bets, sub_bets, longshot_bets, cover_bets

    # 旧形式フォールバック
    return (
        pick_bets(pred, "本命①"),
        pick_bets(pred, "本命②"),
        pick_bets(pred, "穴"),
        pick_bets(pred, "出目④"),
    )


def build_top_picks(pred: dict) -> list[dict]:
    picks = []
    marks = ["◎", "○", "▲", "✕", "", ""]
    for idx, racer in enumerate(pred.get("predictions", [])[:6]):
        raw_comment = (racer.get("raw_metrics") or {}).get("comment", {}) or {}
        raw_ex = (racer.get("raw_metrics") or {}).get("exhibition", {}) or {}
        reg_no = str(racer.get("reg_no", "") or "")
        picks.append({
            "mark": marks[idx] if idx < len(marks) else "",
            "rank": racer.get("rank"),
            "waku": racer.get("waku"),
            "name": racer.get("name", ""),
            "reg_no": reg_no,
            "is_female": is_female_reg(reg_no),
            "grade": racer.get("grade", ""),
            "score": round(float(racer.get("score", 0.0)), 4),
            "comment_source": raw_comment.get("source", ""),
            "comment_text": raw_comment.get("text", ""),
            "comment_label": raw_comment.get("final_label", ""),
            # v5.18: コメント実データ用拡張フィールド
            "comment_raw_score": raw_comment.get("raw_score", ""),
            "comment_history_bonus": raw_comment.get("history_bonus", ""),
            "comment_matched_keywords": raw_comment.get("matched_keywords", []),
            "exhibition_time": raw_ex.get("time", ""),
        })
    return picks


def build_detailed_predictions(pred: dict) -> list[dict]:
    rows = []
    for racer in pred.get("predictions", []):
        row = dict(racer)
        reg_no = str(row.get("reg_no", "") or "")
        row["is_female"] = is_female_reg(reg_no)
        rows.append(row)
    return rows


def _build_review_extras(jcd: str, date: str) -> dict:
    """avg_pay / avg_pop / big_upsets をレース結果CSVから算出する（v5.18）。"""
    results = load_results_for_date(date)
    pays = []
    pops = []
    upsets = []
    for race_no in range(1, 13):
        race_data = results.get((jcd, race_no))
        if not race_data:
            continue
        pay = race_data.get("won3_pay", 0) or 0
        pop = race_data.get("won3_pop", 0) or 0
        if pay > 0:
            pays.append(pay)
        if pop > 0:
            pops.append(pop)
        if pay >= 10000:
            upsets.append({
                "race_no": race_no,
                "payout": pay,
                "popularity": pop,
                "won3": race_data.get("won3", ""),
            })
    return {
        "avg_pay": round(sum(pays) / len(pays)) if pays else 0,
        "avg_pop": round(sum(pops) / len(pops) * 10) / 10 if pops else 0,
        "big_upsets": upsets,
    }


def _build_exhibition_section(pred: dict) -> dict:
    """展示実データセクション用の構造体を構築する（v5.18）。"""
    rows = []
    for racer in pred.get("predictions", []):
        raw_ex = (racer.get("raw_metrics") or {}).get("exhibition", {}) or {}
        time_val = raw_ex.get("time", "")
        if not str(time_val).strip():
            continue
        rows.append({
            "waku": racer.get("waku"),
            "name": racer.get("name", ""),
            "time": time_val,
            "tilt": raw_ex.get("tilt", ""),
            "entry_course": raw_ex.get("entry_course") or raw_ex.get("actual_course", ""),
            "start_timing": raw_ex.get("start_timing", ""),
            "prev_rank": raw_ex.get("prev_rank", ""),
        })
    if not rows:
        return {}
    # 展示タイム順にソート
    rows.sort(key=lambda r: float(r["time"]) if r["time"] else 99.0)
    # 評価ラベルを付与
    fastest = float(rows[0]["time"]) if rows and rows[0]["time"] else 99.0
    for r in rows:
        t = float(r["time"]) if r["time"] else 99.0
        diff = t - fastest
        if diff == 0:
            r["rating"] = "★最速"
        elif diff <= 0.03:
            r["rating"] = "▲好調"
        elif diff >= 0.10:
            r["rating"] = "▼遅"
        else:
            r["rating"] = ""
    return {
        "rows": rows,
        "course_order": pred.get("course_order", []),
    }


def build_review_summary(jcd: str, date: str) -> dict:
    venue_name = load_config()["venues"][jcd]
    detail = load_verify_detail_lines(venue_name, date)
    detail_tables = build_review_tables_from_logs(jcd, date) or load_verify_detail_tables(venue_name, date)
    for row in reversed(load_verify_history()):
        if str(row.get("jcd", "")).zfill(2) != jcd:
            continue
        if row.get("date_from") != date or row.get("date_to") != date:
            continue
        # v5.18: 平均配当/人気/高配当レースをCSVから算出
        extras = _build_review_extras(jcd, date)

        review = {
            "date": date,
            "run_date": row.get("run_date", ""),
            "total_races": row.get("total_races", 0),
            # v5.16: 主指標 = レース的中率（買い目のいずれかが3連単的中）
            "hit_1st_pct": row.get("hit_1st_pct", 0),
            "hit_bet_any_pct": row.get("hit_bet_any_pct", 0),
            "hit_honmei_pct": row.get("hit_honmei_pct", 0),
            "hit_others_pct": row.get("hit_others_pct", 0),
            "hit_taikou_pct": row.get("hit_taikou_pct", 0),
            "hit_oshi_pct": row.get("hit_oshi_pct", 0),
            "hit_ana_pct": row.get("hit_ana_pct", 0),
            # 参考指標
            "hit_3fuku_pct": row.get("hit_3fuku_pct", 0),
            "hit_3tan_pct": row.get("hit_3tan_pct", 0),
            "avg_rank": row.get("avg_rank", 0),
            # v5.18: 追加指標
            "hit_2tan_pct": row.get("hit_2tan_pct", 0),
            "hit_2fuku_pct": row.get("hit_2fuku_pct", 0),
            "avg_pay": extras.get("avg_pay", 0),
            "avg_pop": extras.get("avg_pop", 0),
            "big_upsets": extras.get("big_upsets", []),
        }
        if detail:
            review.update(detail)
        else:
            review["detail_file"] = f"verify_detail_{venue_name}_{date}.html"
        if detail_tables:
            review.update(detail_tables)
        return review
    return {}


def build_race_payload(jcd: str, date: str, race_no: int, start_times: dict[str, str]) -> dict:
    pred = load_prediction(jcd, date, race_no)
    racecard = load_racecard(jcd, date, race_no)
    confidence, confidence_label = classify_confidence(pred.get("confidence", "0%"))
    # v5.16: pred.json の honmei/others を優先的に読む（旧形式もフォールバック対応）
    main_bets, sub_bets, longshot_bets, cover_bets = pick_bets_v2(pred)
    main_bet = main_bets[0]["combo"] if main_bets else ""
    sub_bet = sub_bets[0]["combo"] if sub_bets else ""
    longshot_bet = longshot_bets[0]["combo"] if longshot_bets else ""
    cover_bet = cover_bets[0]["combo"] if cover_bets else ""
    main_reason = main_bets[0]["reason"] if main_bets else ""
    sub_reason = sub_bets[0]["reason"] if sub_bets else ""
    longshot_reason = longshot_bets[0]["reason"] if longshot_bets else ""
    cover_reason = cover_bets[0]["reason"] if cover_bets else ""
    has_exhibition = any(
        str((p.get("raw_metrics") or {}).get("exhibition", {}).get("time", "")).strip()
        for p in pred.get("predictions", [])
    )
    # オッズファイルの有無を確認
    odds_path = DATA_DIR / "odds" / date / f"{jcd}_R{race_no:02d}.json"
    has_odds = False
    odds_data: dict = {}
    if odds_path.exists():
        try:
            odds_data = json.loads(odds_path.read_text(encoding="utf-8"))
            has_odds = bool(odds_data.get("odds_3t"))
        except Exception:
            pass

    # 各買い目にオッズ値を付加
    def _attach_odds(bets_list: list[dict]) -> list[dict]:
        if not has_odds:
            return bets_list
        odds_3t = odds_data.get("odds_3t", {})
        for b in bets_list:
            combo = b.get("combo", "")
            key = combo.replace("-", "")
            o = odds_3t.get(key)
            if o is not None:
                b["odds"] = o
        return bets_list

    # v5.18: 展示実データ用の構造体を構築
    exhibition_section = _build_exhibition_section(pred)

    # v5.18: 予算別買い目をログから読み取り
    budget_plans = pred.get("budget_plans", []) or []

    return {
        "race_no": race_no,
        "start_time": start_times.get(str(race_no), ""),
        "race_type": normalize_race_name(racecard.get("race_name", "")),
        "confidence": confidence,
        "confidence_label": confidence_label,
        "is_rough": bool(pred.get("is_rough", False)),
        "main_bet": main_bet,
        "main_bets": _attach_odds(main_bets),
        "sub_bet": sub_bet,
        "sub_bets": _attach_odds(sub_bets),
        "longshot_bet": longshot_bet,
        "longshot_bets": _attach_odds(longshot_bets),
        "cover_bet": cover_bet,
        "cover_bets": _attach_odds(cover_bets),
        "comment": main_reason,
        "bet_reasons": {
            "main": main_reason,
            "sub": sub_reason,
            "longshot": longshot_reason,
            "cover": cover_reason,
        },
        "top_picks": build_top_picks(pred),
        "detailed_predictions": build_detailed_predictions(pred),
        "tide_status": pred.get("tide_status", ""),
        "has_exhibition": has_exhibition,
        "has_odds": has_odds,
        # v5.18: WP連携拡張
        "exhibition_section": exhibition_section,
        "budget_plans": budget_plans,
    }


def infer_stage(has_exhibition: bool, has_odds: bool) -> str:
    if has_exhibition and has_odds:
        return "after_odds"
    if has_exhibition:
        return "after_exhibition"
    return "morning"


def build_status_note(stage: str) -> str:
    notes = {
        "morning": "朝時点の初期予測です",
        "after_exhibition": "展示反映済みです",
        "after_odds": "展示・オッズ反映済みです",
        "final": "最終更新版です",
    }
    return notes.get(stage, "予想を更新しました")


def build_day_payload(jcd: str, date: str) -> dict:
    config = load_config()
    venue_name = config["venues"][jcd]
    venue_slug = VENUE_SLUGS[jcd]
    start_times = load_start_times(jcd, date)
    races = [build_race_payload(jcd, date, race_no, start_times) for race_no in range(1, 13)]
    has_exhibition = any(r["has_exhibition"] for r in races)
    has_odds = any(r["has_odds"] for r in races)
    stage = infer_stage(has_exhibition, has_odds)
    display_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    headline = f"{venue_name} {date[:4]}/{date[4:6]}/{date[6:8]} ボートレース予想"
    updated_at = max(load_prediction(jcd, date, race_no).get("predicted_at", "") for race_no in range(1, 13))
    payload = {
        "date": display_date,
        "venue_code": jcd,
        "venue_slug": venue_slug,
        "venue_name": venue_name,
        "headline": headline,
        "updated_at": updated_at.replace("T", " ")[:16],
        "publish_stage": stage,
        "has_exhibition": has_exhibition,
        "has_odds": has_odds,
        "review_summary": build_review_summary(jcd, date),
        "races": races,
    }
    return payload


def build_post_body(payload: dict) -> str:
    exh = "反映済み" if payload["has_exhibition"] else "未反映"
    odds = "反映済み" if payload["has_odds"] else "未反映"
    return (
        f"<p>{payload['venue_name']} {payload['date']} の予想ページです。</p>\n"
        f"<p>最終更新: {payload['updated_at']}</p>\n"
        f"<p>展示: {exh} / オッズ: {odds}</p>\n"
        f"<p>このページはレース進行に合わせて随時更新します。</p>"
    )


def build_request_payload(jcd: str, date: str) -> dict:
    day = build_day_payload(jcd, date)
    compact_date = date
    slug = f"{day['venue_slug']}-{compact_date}"
    stage = day["publish_stage"]
    return {
        "title": day["headline"],
        "slug": slug,
        "status": "publish",
        "content": build_post_body(day),
        "acf": {
            "venue_code": day["venue_code"],
            "venue_slug": day["venue_slug"],
            "venue_name": day["venue_name"],
            "race_date": day["date"],
            "updated_at": day["updated_at"],
            "publish_stage": stage,
            "has_exhibition": day["has_exhibition"],
            "has_odds": day["has_odds"],
            "status_note": build_status_note(stage),
            "forecast_payload": json.dumps(day, ensure_ascii=False),
        },
    }


def write_payload_file(jcd: str, date: str, payload: dict) -> Path:
    out_dir = OUTPUT_DIR / "wordpress" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{jcd}_payload.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def publish_payload(payload: dict, url: str, token: str, timeout: float) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Boat-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="WordPress forecast_day 投稿ペイロード生成・送信")
    parser.add_argument("--jcd", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--publish", action="store_true", help="WordPress へPOST送信する")
    parser.add_argument("--sync-url", default=os.getenv("WP_SYNC_URL", ""))
    parser.add_argument("--token", default=os.getenv("WP_SYNC_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("WP_SYNC_TIMEOUT", "10")))
    args = parser.parse_args()

    payload = build_request_payload(args.jcd, args.date)
    out_path = write_payload_file(args.jcd, args.date, payload)
    print(f"payload: {out_path}")

    if not args.publish:
        return 0

    if not args.sync_url or not args.token:
        print("sync-url and token are required when --publish is used", file=sys.stderr)
        return 2

    try:
        response = publish_payload(payload, args.sync_url, args.token, args.timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"publish failed: {e}", file=sys.stderr)
        return 1

    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
