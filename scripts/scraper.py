#!/usr/bin/env python3
from __future__ import annotations
"""
ボートレース データスクレイパー（修正版）
boatrace.jp の実際のHTML構造に対応した出走表・各種データ取得
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
DEFAULT_RACE_FETCH_WORKERS = 4



# レース名見出しに付く距離表記（"1800m" 等）。レース名の正当性判定と除去に使う
_RACE_DISTANCE = re.compile(r"\s*\d{3,4}m\s*$")

def _is_number_text(value) -> bool:
    try:
        float(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def _normalize_exhibition_rows(rows: list[dict]) -> list[dict]:
    """
    旧形式/破損形式の展示行を現行スキーマへ寄せる。
    straight_time に展示タイムが入っている旧形式を救済する。
    """
    normalized = []
    for row in rows or []:
        waku = row.get("waku")
        try:
            waku = int(waku)
        except (TypeError, ValueError):
            continue

        ex_time = row.get("exhibition_time", "")
        if not _is_number_text(ex_time) and _is_number_text(row.get("straight_time", "")):
            ex_time = row.get("straight_time", "")

        normalized.append({
            "waku": waku,
            "exhibition_time": str(ex_time).strip(),
            "tilt": str(row.get("tilt", "")).strip(),
            "entry_course": str(row.get("entry_course", "")).strip(),
            "start_timing": str(row.get("start_timing", row.get("exhibition_st", ""))).strip(),
            "handicap_dist": str(row.get("handicap_dist", "")).strip(),
            "prev_rank": str(row.get("prev_rank", "")).strip(),
        })
    return normalized


def exhibition_has_valid_times(exhibition_rows: list[dict], min_valid_rows: int = 4) -> bool:
    """
    展示タイムが十分に取れているかを返す。
    6艇中4艇以上で数値なら、展示スコア算出に使えるとみなす。
    """
    valid = sum(1 for row in exhibition_rows or [] if _is_number_text(row.get("exhibition_time", "")))
    return valid >= min_valid_rows

def fetch(url, params=None, wait=1.5, retries=2, timeout=15):
    """共通HTTPフェッチ（過負荷防止のwait付き）

    Timeout / ConnectionError / 5xx は最大 retries 回まで線形バックオフ再試行。
    4xx や JSON エラー等は即時諦めて None 返却。
    """
    time.sleep(wait)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if 500 <= res.status_code < 600:
                raise requests.HTTPError(f"{res.status_code} server error", response=res)
            res.raise_for_status()
            res.encoding = "utf-8"
            return res.text
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_err = e
            if attempt < retries:
                backoff = 10 * (attempt + 1)
                print(f"[WARN] fetch retry {attempt+1}/{retries} in {backoff}s: {url} -> {e}")
                time.sleep(backoff)
                continue
            break
        except Exception as e:
            print(f"[ERROR] fetch failed: {url} -> {e}")
            return None
    print(f"[ERROR] fetch failed after {retries+1} attempts: {url} -> {last_err}")
    return None


def _run_parallel_race_jobs(jobs: list[tuple[int, callable]], label: str,
                            max_workers: int = DEFAULT_RACE_FETCH_WORKERS) -> list:
    """
    race_no ごとの独立ジョブを並列実行する。
    jobs: [(race_no, callable_no_args), ...]
    """
    if not jobs:
        return []
    if len(jobs) == 1:
        race_no, fn = jobs[0]
        return [(race_no, fn())]

    print(f"[INFO] {label} 並列実行: {len(jobs)}件 workers={min(max_workers, len(jobs))}")
    results: list[tuple[int, object]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as ex:
        future_map = {ex.submit(fn): race_no for race_no, fn in jobs}
        for fut in as_completed(future_map):
            race_no = future_map[fut]
            try:
                results.append((race_no, fut.result()))
            except Exception as e:
                print(f"[ERROR] {label} R{race_no:02d} 並列実行失敗: {e}")
                results.append((race_no, None))
    results.sort(key=lambda x: x[0])
    return results


def _parse_start_times_from_racelist_html(html: str) -> dict[int, str]:
    """
    racelist HTML から全12Rの発走時刻を抽出する。
    優先順:
      1. 「締切予定時刻」セクションの 12 本
      2. 近傍ノードからの再抽出
      3. 旧来の td 総取りフォールバック
    """
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    result: dict[int, str] = {}

    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for idx, line in enumerate(lines):
        if "締切予定時刻" not in line:
            continue
        joined = " ".join(lines[idx:min(idx + 3, len(lines))])
        times = re.findall(r"\b\d{1,2}:\d{2}\b", joined)
        if len(times) >= 12:
            return {i + 1: t for i, t in enumerate(times[:12])}

    marker = soup.find(string=re.compile("締切予定時刻"))
    if marker:
        nearby = []
        for node in [marker.parent, getattr(marker.parent, "next_sibling", None), getattr(marker.parent, "parent", None)]:
            if hasattr(node, "get_text"):
                nearby.append(node.get_text(" ", strip=True))
        times = []
        for chunk in nearby:
            times.extend(re.findall(r"\b\d{1,2}:\d{2}\b", chunk))
        if len(times) >= 12:
            return {i + 1: t for i, t in enumerate(times[:12])}

    times = [
        td.get_text(strip=True)
        for td in soup.find_all("td")
        if re.match(r"^\d{1,2}:\d{2}$", td.get_text(strip=True))
    ]
    for i in range(1, min(len(times), 12) + 1):
        result[i] = times[i - 1]
    return result

def _extract_nums(cell_text):
    """セルテキストから数値リストを抽出"""
    return [float(x) for x in re.findall(r"\d+\.\d+", cell_text)]

def _parse_fl_st(text):
    """F数・L数・平均STを抽出 (例: 'F1L00.14')"""
    f_count = int(re.search(r"F(\d+)", text).group(1)) if re.search(r"F(\d+)", text) else 0
    l_count = int(re.search(r"L(\d+)", text).group(1)) if re.search(r"L(\d+)", text) else 0
    avg_st  = float(re.search(r"(0\.\d+)", text).group(1)) if re.search(r"(0\.\d+)", text) else 0.18
    return f_count, l_count, avg_st

def _detect_tournament_grade(soup) -> str:
    """
    出走表HTMLからトーナメントグレード（SG/G1/G2/G3/一般/レディース）を検出する。

    検出優先順:
      1. CSS クラス属性 (is-grade_SG 等 - 最信頼)
      2. <title> / h1 / ナビゲーション テキストのキーワードマッチ
      3. フォールバック: "一般"

    Returns:
      "SG" | "G1" | "G2" | "G3" | "一般" | "レディース"
    """
    # ─ 方法1: CSS class ベース検出 ─────────────────────────────────
    # boatrace.jp は is-grade_SG, is-grade_G1, is-grade_G2, is-grade_G3 を使用
    grade_class_keywords = {
        "SG": ["grade_sg", "grade-sg", "is-sg"],
        "G1": ["grade_g1", "grade-g1", "is-g1"],
        "G2": ["grade_g2", "grade-g2", "is-g2"],
        "G3": ["grade_g3", "grade-g3", "is-g3"],
    }
    # 全要素の class 文字列を一括でスキャン（高速）
    all_classes = " ".join(
        " ".join(el.get("class", [])) for el in soup.find_all(class_=True)
    ).lower()
    for grade, patterns in grade_class_keywords.items():
        if any(p in all_classes for p in patterns):
            return grade

    # ─ 方法2: テキストキーワード検出 ─────────────────────────────
    # ページタイトル・h1・レース見出しのみを対象に検索
    # ※ .nav-item / .l-header はサイト共通ナビ（全ページに「ヴィーナスシリーズ」等の
    #    リンクが含まれる）ため除外。誤検出の原因になる。
    target_parts = []
    for sel in ["title", "h1", "h2",
                ".is-titleName", ".heading1_item", ".heading2_item",
                ".is-title1", ".is-gradeGname"]:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            if text:
                target_parts.append(text)
    search_text = " ".join(target_parts)

    SG_KWS = ["グランプリ", "クラシック", "オールスター", "グランドチャンピオン",
              "チャレンジカップ", "笹川賞", "スプリントカップ", "マスターズCUP",
              "MB大賞", "競艇王", "ボートレースクラシック", "ボートレースオールスター",
              "ボートレースグランプリ", "ボートレースグランドチャンピオン"]
    G1_KWS = ["周年記念", "地方選手権", "高松宮記念", "鳳凰賞", "ダービー", "名人戦",
              "ゴールデンカップ", "グランプリシリーズ", "選手権大会"]
    G2_KWS = ["アーリントン", "レインボーカップ", "ヤングダービー"]
    G3_KWS = ["市長杯", "知事杯", "議長杯", "城山杯", "大賞典"]
    LADIES_KWS = ["レディース", "女子選手権", "ヴィーナス", "ガールズ選手権",
                  "レディースチャンピオン", "レディースリーグ", "ヴィーナスシリーズ"]

    for kw in SG_KWS:
        if kw in search_text: return "SG"
    for kw in G1_KWS:
        if kw in search_text: return "G1"
    for kw in G2_KWS:
        if kw in search_text: return "G2"
    for kw in G3_KWS:
        if kw in search_text: return "G3"
    for kw in LADIES_KWS:
        if kw in search_text: return "レディース"

    return "一般"


def _parse_name_grade(col_element):
    """選手情報セル(col[2])から名前・級別を抽出"""
    text = col_element.get_text(separator="|", strip=True)
    parts = [p.strip() for p in text.split("|") if p.strip()]
    grade = next((p for p in parts if re.match(r"^[AB][12]$", p)), "B1")
    name_parts = [
        p for p in parts
        if not re.match(r"^[\d/歳kg]", p)
        and "歳" not in p
        and "/" not in p
        and not re.match(r"^[AB][12]$", p)
        and len(p) >= 2
    ]
    name = name_parts[0] if name_parts else "---"
    return name, grade


# ──────────────────────────────────────────
# 1. 出走表の取得（修正版）
# ──────────────────────────────────────────
def scrape_racecard(jcd: str, date: str, race_no: int) -> dict | None:
    """
    出走表を取得
    jcd     : 会場コード 2桁 (例: "22" = 福岡)
    date    : "YYYYMMDD"
    race_no : 1〜12
    """
    url = "https://www.boatrace.jp/owpc/pc/race/racelist"
    html = fetch(url, {"jcd": jcd, "hd": date, "rno": race_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        return None

    # 2番目のテーブルのtbody trが選手データを含む
    tbody_rows = tables[1].select("tbody tr")

    racers = []
    # 各選手は4行単位: [選手情報(24col), 着順(14col), ST(14col), 艇番(14col)]
    # 選手情報行はtd数==24で識別
    for row_idx, row in enumerate(tbody_rows):
        tds = row.find_all("td")
        if len(tds) != 24:
            continue

        # 枠番（全角数字→整数）
        waku_map = {"１":1,"２":2,"３":3,"４":4,"５":5,"６":6}
        waku = waku_map.get(tds[0].get_text(strip=True), 0)
        if waku == 0:
            continue

        # 登録番号（col[1]のaタグhrefから）
        reg_no = ""
        link = tds[1].find("a")
        if link:
            m = re.search(r"toban=(\d+)", link.get("href", ""))
            if m:
                reg_no = m.group(1)

        # 名前・級別（col[2]）
        name, grade = _parse_name_grade(tds[2])

        # F/L/平均ST（col[3]）
        f_count, l_count, avg_st = _parse_fl_st(tds[3].get_text(strip=True))

        # 全国成績（col[4]）: 勝率, 2連率, 3連率
        g = _extract_nums(tds[4].get_text())
        global_win  = g[0] if len(g) > 0 else 0.0
        global_2win = g[1] if len(g) > 1 else 0.0
        global_3win = g[2] if len(g) > 2 else 0.0

        # 当地成績（col[5]）: 勝率, 2連率, 3連率
        l = _extract_nums(tds[5].get_text())
        local_win  = l[0] if len(l) > 0 else 0.0
        local_2win = l[1] if len(l) > 1 else 0.0
        local_3win = l[2] if len(l) > 2 else 0.0

        # モーター（col[6]）: No, 2連率, 3連率
        mo = re.findall(r"\d+(?:\.\d+)?", tds[6].get_text())
        motor_no    = mo[0] if len(mo) > 0 else ""
        motor_2rate = float(mo[1]) if len(mo) > 1 else 0.0
        motor_3rate = float(mo[2]) if len(mo) > 2 else 0.0

        # ボート（col[7]）: No, 2連率, 3連率
        bo = re.findall(r"\d+(?:\.\d+)?", tds[7].get_text())
        boat_no    = bo[0] if len(bo) > 0 else ""
        boat_2rate = float(bo[1]) if len(bo) > 1 else 0.0

        # ── 今節成績: 直後の14td行(sub-row1)から着順, (sub-row3)から艇番コース ──
        # sub-row1: 今節の各レース着順（1〜6の数字、空欄・is-outColor=未出走）
        # sub-row3: 今節の各レース艇番（全角１〜６、コース補正用）
        # 両行の同一 index 位置が同じレースを指す
        series_ranks: list[int] = []        # 後方互換（v5.2〜）
        series_races: list[dict] = []       # v5.19 #3: [{"course": N, "rank": M}, ...]

        rank_by_idx: dict[int, int] = {}
        if row_idx + 1 < len(tbody_rows):
            sub_row = tbody_rows[row_idx + 1]
            sub_tds = sub_row.find_all("td")
            if len(sub_tds) == 14:
                for i, std in enumerate(sub_tds):
                    if "is-outColor" in std.get("class", []):
                        continue
                    val = std.get_text(strip=True)
                    if val.isdigit() and 1 <= int(val) <= 6:
                        rank_by_idx[i] = int(val)
                        series_ranks.append(int(val))

        course_by_idx: dict[int, int] = {}
        if row_idx + 3 < len(tbody_rows):
            sub_row = tbody_rows[row_idx + 3]
            sub_tds = sub_row.find_all("td")
            if len(sub_tds) == 14:
                for i, std in enumerate(sub_tds):
                    if "is-outColor" in std.get("class", []):
                        continue
                    val = std.get_text(strip=True)
                    c = waku_map.get(val, 0)
                    if c:
                        course_by_idx[i] = c

        for i in sorted(rank_by_idx.keys() & course_by_idx.keys()):
            series_races.append({"course": course_by_idx[i], "rank": rank_by_idx[i]})

        racers.append({
            "waku":         waku,
            "name":         name,
            "reg_no":       reg_no,
            "grade":        grade,
            "avg_st":       avg_st,
            "f_count":      f_count,
            "l_count":      l_count,
            "global_win":   global_win,
            "global_2win":  global_2win,
            "global_3win":  global_3win,
            "local_win":    local_win,
            "local_2win":   local_2win,
            "local_3win":   local_3win,
            "motor_no":     motor_no,
            "motor_2rate":  motor_2rate,
            "motor_3rate":  motor_3rate,
            "boat_no":        boat_no,
            "boat_2rate":     boat_2rate,
            "series_ranks":   series_ranks,   # 今節の着順リスト [1,3,2,...] (空=初日)
            "series_races":   series_races,   # v5.19 #3: [{"course":N,"rank":M},...] コース補正用
        })

    if not racers:
        print(f"[WARN] 出走表パース結果なし: {jcd} {date} {race_no}R")
        return None

    # ── レース名・種別を取得 ──────────────────────────────────────
    # boatrace.jp の出走表ページのタイトル/見出し部分から取得を試みる
    # レース名は h3.title16_titleDetail__add2020 に「レース名＋距離」の形で入る。
    #   例: "カタメン１予選\n\t\t1800m" / "ウインウイン５\n\t\t1800m" / "特別選抜戦Ａ組\n\t\t1800m"
    # 距離 (\d{3,4}m) が付いていることを正当性の合図に使う。
    #
    # ⚠️ 以前はキーワード関門 ["戦","選","杯","R"] で弾いていたため、
    #    「一般」(10,684レース) や企画レース名（ウインウイン/ランチタイム/サンライズ等）が
    #    どれにも該当せず race_name が空になっていた。実測で racecards の 24.9% が空。
    #    番組の意図（企画レースは内が強い）を読む上で、まさに欲しい行が落ちていた。
    race_name = ""
    for el in soup.select("h3.title16_titleDetail__add2020, h3"):
        text = el.get_text(strip=True)
        if _RACE_DISTANCE.search(text):
            race_name = _RACE_DISTANCE.sub("", text)
            break
    if not race_name:
        # 旧レイアウト向けフォールバック
        for sel in [".heading3_item", ".heading2_item", ".title3_item",
                    ".is-type2 .heading3", ".race_type"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if any(kw in text for kw in ["戦", "選", "杯", "予", "般"]):
                    race_name = _RACE_DISTANCE.sub("", text)
                    break
    race_name = re.sub(r"\s+", "", race_name).strip()

    # ── 大会グレードを検出して保存 ────────────────────────────────
    # SG / G1 / G2 / G3 / 一般 / レディース
    tournament_grade = _detect_tournament_grade(soup)

    result = {
        "venue_code":       jcd,
        "date":             date,
        "race_no":          race_no,
        "race_name":        race_name,
        "tournament_grade": tournament_grade,  # v5.3: 大会グレード
        "racers":           racers
    }

    save_dir = DATA_DIR / "racecards" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 出走表保存: {jcd} {race_no}R ({len(racers)}名) → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 2. オッズの取得
# ──────────────────────────────────────────
def scrape_odds(jcd: str, date: str, race_no: int) -> dict | None:
    """
    3連単オッズを取得

    boatrace.jp odds3t ページの構造（2026年現在）:
      - table[1] がオッズ本体
      - row[0] = 1着ヘッダー（6枠分）
      - row[1..20] = データ行（合計20行）
      - 18セル行 = 6列 × (2着枠, 3着枠, オッズ) 新しい2着の始まり
      - 12セル行 = 6列 × (3着枠, オッズ) 2着継続（rowspan）

    以前は td[data-combo] 属性だけで拾えたが、属性が撤去されたため
    位置ベースのパーサーに書き直した。
    """
    url = "https://www.boatrace.jp/owpc/pc/race/odds3t"
    html = fetch(url, {"jcd": jcd, "hd": date, "rno": race_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    odds_table: dict[str, float] = {}

    tables = soup.find_all("table")
    if len(tables) >= 2:
        tbl = tables[1]
        rows = tbl.find_all("tr")
        if len(rows) >= 2:
            # row[0] から 1着ヘッダーを取得（テキストが 1〜6 の td / th）
            header_cells = rows[0].find_all(["th", "td"])
            firsts: list[int] = []
            for c in header_cells:
                t = c.get_text(strip=True)
                if t.isdigit() and 1 <= int(t) <= 6 and int(t) not in firsts:
                    firsts.append(int(t))
            if len(firsts) != 6:
                firsts = [1, 2, 3, 4, 5, 6]  # フォールバック

            last_second_by_col: dict[int, int] = {}

            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                cells_text = [c.get_text(strip=True) for c in cells]

                def _try_int(s):
                    try:
                        return int(s)
                    except Exception:
                        return None

                def _try_float(s):
                    try:
                        return float(s.replace(",", ""))
                    except Exception:
                        return None

                if len(cells) == 18:
                    # 新しい 2着 の始まり: (2nd, 3rd, odds) × 6 列
                    for col in range(6):
                        idx = col * 3
                        if idx + 2 >= len(cells_text):
                            continue
                        second = _try_int(cells_text[idx])
                        third  = _try_int(cells_text[idx + 1])
                        odds_f = _try_float(cells_text[idx + 2])
                        if second is None or third is None or odds_f is None:
                            continue
                        last_second_by_col[col] = second
                        # ダッシュなし形式（旧互換: predictor が "123" で検索するため）
                        combo = f"{firsts[col]}{second}{third}"
                        odds_table[combo] = odds_f
                elif len(cells) == 12:
                    # 2着継続: (3rd, odds) × 6 列
                    for col in range(6):
                        idx = col * 2
                        if idx + 1 >= len(cells_text):
                            continue
                        third  = _try_int(cells_text[idx])
                        odds_f = _try_float(cells_text[idx + 1])
                        second = last_second_by_col.get(col)
                        if second is None or third is None or odds_f is None:
                            continue
                        combo = f"{firsts[col]}{second}{third}"
                        odds_table[combo] = odds_f

    # フォールバック: 位置ベースで取れなかったら旧ロジック（data-combo）を試す
    if not odds_table:
        for cell in soup.find_all("td", attrs={"data-combo": True}):
            combo = cell.get("data-combo", "")
            val   = cell.get_text(strip=True).replace(",", "")
            if combo and val:
                try:
                    odds_table[combo] = float(val)
                except ValueError:
                    pass

    result = {
        "venue_code": jcd,
        "date":       date,
        "race_no":    race_no,
        "odds_3t":    odds_table
    }

    save_dir = DATA_DIR / "odds" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] オッズ保存: {jcd} {race_no}R ({len(odds_table)}通り) → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 3. 展示タイム・展示ST（直前情報）の取得
# ──────────────────────────────────────────
def scrape_exhibition(jcd: str, date: str, race_no: int) -> dict | None:
    """
    展示データを全項目取得（beforeinfo ページ）
    取得フィールド:
      exhibition_time : 展示タイム（直線6m通過タイム）
      tilt            : チルト角度（-0.5〜+1.0 / マイナス=スピード重視）
      entry_course    : 展示での進入コース（1コース有利争いの指標）
      start_timing    : スタート展示でのST（前の列では前走ST）
      handicap_dist   : スタート展示の初動ハンデ距離
      prev_rank       : 前走の着順
    スタート展示（テーブル3）: course_order に別途格納
    """
    url = "https://www.boatrace.jp/owpc/pc/race/beforeinfo"
    html = fetch(url, {"jcd": jcd, "hd": date, "rno": race_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    exhibition = []
    course_order = []  # スタート展示のコース順 [{course, st}]

    tables = soup.find_all("table")

    # ── テーブル2: 展示タイム・チルト・進入コース・ST ────────────────
    # 各艇のデータは4行セット:
    #   行1: [枠番, 写真, 選手名, 体重, 展示タイム, チルト, プロペラ, 部品交換, 前走成績, 調整重量]
    #   行2: ['進入', コース番号]
    #   行3: [ハンデ距離, 'ST', STタイミング]
    #   行4: ['着順', 前走着順]
    if len(tables) >= 2:
        current = {}
        for row in tables[1].find_all("tr"):
            tds = [td.get_text(strip=True) for td in row.find_all("td")]
            if not tds:
                continue
            # 行1: 枠番が1〜6の行
            if tds[0].isdigit() and 1 <= int(tds[0]) <= 6:
                if current:
                    exhibition.append(current)
                current = {
                    "waku":             int(tds[0]),
                    "exhibition_time":  tds[4] if len(tds) > 4 else "",
                    "tilt":             tds[5] if len(tds) > 5 else "",
                    "entry_course":     "",
                    "start_timing":     "",
                    "handicap_dist":    "",
                    "prev_rank":        "",
                }
            # 行2: 進入コース
            elif tds[0] == "進入" and current:
                current["entry_course"] = tds[1] if len(tds) > 1 else ""
            # 行3: ハンデ距離・ST
            elif len(tds) == 3 and tds[1] == "ST" and current:
                current["handicap_dist"] = tds[0]
                current["start_timing"]  = tds[2]
            # 行4: 着順
            elif tds[0] == "着順" and current:
                current["prev_rank"] = tds[1] if len(tds) > 1 else ""
        if current:
            exhibition.append(current)

    # ── テーブル3: スタート展示（コース順×ST） ──────────────────────
    # 各行: "X.YY" → コースX、ST 0.YY / "XF.YY" → フライング
    if len(tables) >= 3:
        import re
        for row in tables[2].find_all("tr"):
            for td in row.find_all("td"):
                val = td.get_text(strip=True)
                m = re.match(r'^(\d)(F?)\.(\d+)$', val)
                if m:
                    course_order.append({
                        "course": int(m.group(1)),
                        "foul":   m.group(2) == "F",
                        "st":     float("0." + m.group(3)),
                    })

    # 気象情報
    weather_info = {}
    for unit in soup.select("div.weather1_bodyUnit"):
        label = unit.select_one(".weather1_bodyUnitTitle, p[class*='Title']")
        value = unit.select_one(".weather1_bodyUnitData,  p[class*='Data']")
        if label and value:
            weather_info[label.get_text(strip=True)] = value.get_text(strip=True)

    exhibition = _normalize_exhibition_rows(exhibition)
    valid_times = exhibition_has_valid_times(exhibition)

    result = {
        "venue_code":   jcd,
        "date":         date,
        "race_no":      race_no,
        "exhibition":   exhibition,
        "course_order": course_order,
        "weather":      weather_info,
    }

    if not valid_times:
        print(f"[INFO] 展示情報未公開/不完全: {jcd} {race_no}R")
        return None

    save_dir = DATA_DIR / "raw" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}_exhibition.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 展示情報保存: {jcd} {race_no}R → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 3-2. オリジナル展示（福岡公式 boatrace-fukuoka.com）
# ──────────────────────────────────────────
FUKUOKA_ORIGINAL_TENJI_URL = (
    "https://www.boatrace-fukuoka.com/modules/yosou/tenji_info.php"
    "?day={date}&race={race_no}&if=1&nowmode=1"
)


def _parse_float_or_none(text: str):
    s = (text or "").strip()
    if not s or s in {"-", "--", "-.--", "--.-", "--.--"}:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def scrape_fukuoka_original_exhibition(date: str, race_no: int) -> dict | None:
    """
    福岡公式（boatrace-fukuoka.com）のオリジナル展示タイムを取得。
    取得項目: 一周(lap_time) / まわり足(turn_time) / 直線(straight_time) / 評価(evaluation)
    rank_1 / rank_2 のCSSクラスで上位艇を識別する。

    保存: data/raw/{date}/22_R{nn}_original_exhibition.json
    福岡(jcd=22)専用。SPAなのでURL構造が他会場と異なる。
    """
    url = FUKUOKA_ORIGINAL_TENJI_URL.format(date=date, race_no=race_no)
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        print(f"[WARN] 福岡オリジナル展示 fetch失敗: R{race_no} {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return None

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        td_waku = tr.select_one("td.col1")
        if not td_waku:
            continue
        waku_text = td_waku.get_text(strip=True)
        if not waku_text.isdigit():
            continue
        waku = int(waku_text)
        if not (1 <= waku <= 6):
            continue

        td_lap = tr.select_one("td.col7")
        td_turn = tr.select_one("td.col8")
        td_straight = tr.select_one("td.col9")

        def _rank_of(td):
            if td is None:
                return None
            cls = td.get("class") or []
            if "rank_1" in cls:
                return 1
            if "rank_2" in cls:
                return 2
            return None

        td_eval = tr.select_one("td.col10")
        eval_text = td_eval.get_text(strip=True) if td_eval else ""

        rows.append({
            "waku":          waku,
            "weight":        _parse_float_or_none(
                tr.select_one("td.col3").get_text(strip=True) if tr.select_one("td.col3") else ""),
            "tilt":          _parse_float_or_none(
                tr.select_one("td.col5").get_text(strip=True) if tr.select_one("td.col5") else ""),
            "exhibition_time": _parse_float_or_none(
                tr.select_one("td.col6").get_text(strip=True) if tr.select_one("td.col6") else ""),
            "lap_time":      _parse_float_or_none(td_lap.get_text(strip=True) if td_lap else ""),
            "turn_time":     _parse_float_or_none(td_turn.get_text(strip=True) if td_turn else ""),
            "straight_time": _parse_float_or_none(td_straight.get_text(strip=True) if td_straight else ""),
            "lap_rank":      _rank_of(td_lap),
            "turn_rank":     _rank_of(td_turn),
            "straight_rank": _rank_of(td_straight),
            "evaluation":    int(eval_text) if eval_text.isdigit() else None,
        })

    if not rows:
        return None

    has_any_time = any(r["lap_time"] is not None for r in rows)
    result = {
        "venue_code": "22",
        "date":       date,
        "race_no":    race_no,
        "source":     "boatrace-fukuoka.com",
        "rows":       rows,
    }

    if not has_any_time:
        # 開催日でない／未掲載 → ファイルは作らずNone
        return None

    save_dir = DATA_DIR / "raw" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"22_R{race_no:02d}_original_exhibition.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 福岡オリジナル展示保存: R{race_no} → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 4. 気象データの取得
# ──────────────────────────────────────────
def scrape_weather(jcd: str, date: str, race_no: int) -> dict | None:
    """気象情報（風速・風向・天候・気温・水温）を取得"""
    url = "https://www.boatrace.jp/owpc/pc/race/beforeinfo"
    html = fetch(url, {"jcd": jcd, "hd": date, "rno": race_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    weather = {"venue_code": jcd, "date": date, "race_no": race_no}

    section = soup.select_one("div.weather1_body")
    if section:
        for unit in section.select("div.weather1_bodyUnit"):
            title = unit.select_one(".weather1_bodyUnitTitle")
            data  = unit.select_one(".weather1_bodyUnitData")
            if title and data:
                weather[title.get_text(strip=True)] = data.get_text(strip=True)

    save_dir = DATA_DIR / "weather" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    print(f"[OK] 気象データ保存: {jcd} {race_no}R → {out_path.name}")
    return weather


# ──────────────────────────────────────────
# 5. 選手ST統計・フライング歴の取得
# ──────────────────────────────────────────
def scrape_player_gender(reg_no: str) -> str | None:
    """
    選手の性別を取得して player JSON にキャッシュする。
    優先順:
      1. data/players/master.json["players"][reg_no]["gender"]
      2. data/players/female_players.json["reg_nos"]（フォールバック）
    いずれも見つからなければ "M" とみなす。
    Returns: "F" (女性) / "M" (男性) / None (取得失敗)
    """
    save_path = DATA_DIR / "players" / f"{reg_no}.json"
    # 既にキャッシュ済みならスキップ
    if save_path.exists():
        try:
            with open(save_path) as f:
                existing = json.load(f)
            if "gender" in existing:
                return existing["gender"]
        except Exception:
            pass

    gender: str | None = None

    # 1. master.json を優先参照
    master_path = DATA_DIR / "players" / "master.json"
    if master_path.exists():
        try:
            master = json.loads(master_path.read_text())
            info = master.get("players", {}).get(reg_no)
            if info:
                gender = info.get("gender")  # "F" or "M"
        except Exception:
            pass

    # 2. フォールバック: female_players.json
    if gender is None:
        fp_path = DATA_DIR / "players" / "female_players.json"
        if fp_path.exists():
            try:
                fp_data = json.loads(fp_path.read_text())
                female_set = set(str(x) for x in fp_data.get("reg_nos", []))
                gender = "F" if reg_no in female_set else "M"
            except Exception:
                pass

    if gender is None:
        return None

    # player JSON にマージして保存
    existing = {}
    if save_path.exists():
        try:
            with open(save_path) as f:
                existing = json.load(f)
        except Exception:
            pass
    existing["gender"] = gender
    existing["reg_no"] = reg_no
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # female_players.json も更新
    if gender == "F":
        _register_female_player(reg_no)

    return gender


def _register_female_player(reg_no: str) -> None:
    """
    female_players.json に reg_no を追加する（重複チェック付き）。
    """
    fp_path = DATA_DIR / "players" / "female_players.json"
    fp_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if fp_path.exists():
        try:
            with open(fp_path) as f:
                data = json.load(f)
        except Exception:
            pass

    reg_nos = data.get("reg_nos", [])
    if int(reg_no) not in reg_nos:
        reg_nos.append(int(reg_no))
        reg_nos.sort()
        data["reg_nos"] = reg_nos
        data["_count"] = len(reg_nos)
        data.setdefault("names", {})[reg_no] = ""  # 名前は後で補完
        with open(fp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] female_players.json 追加: {reg_no}")


def scrape_player_st_stats(reg_no: str) -> dict | None:
    """
    選手のスタートタイミング統計・フライング/出遅れ歴を取得
    """
    url = "https://www.boatrace.jp/owpc/pc/data/racersearch/season"
    html = fetch(url, {"toban": reg_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    st_stats = {"reg_no": reg_no}

    # 平均ST・STランキング
    for row in soup.select("table tbody tr"):
        th = row.find("th")
        tds = row.find_all("td")
        if th and tds:
            st_stats[f"st_{th.get_text(strip=True)}"] = tds[0].get_text(strip=True)

    # フライング・出遅れ（直近2期）
    for tbl in soup.select("div.contentsFrame1_inner table"):
        header = tbl.select_one("thead th")
        if header and ("フライング" in header.get_text() or "出遅れ" in header.get_text()):
            penalties = []
            for row in tbl.select("tbody tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    penalties.append({
                        "期":  cols[0].get_text(strip=True),
                        "F数": cols[1].get_text(strip=True),
                        "L数": cols[2].get_text(strip=True),
                    })
            st_stats["penalties"] = penalties

    # コース別ST平均
    course_st = {}
    for tbl in soup.select("table"):
        th = tbl.select_one("thead th")
        if th and "コース" in th.get_text():
            for row in tbl.select("tbody tr"):
                cols = row.find_all("td")
                if len(cols) >= 2:
                    course_st[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)
    if course_st:
        st_stats["course_st_avg"] = course_st

    # 既存データとマージして保存
    save_dir = DATA_DIR / "players"
    save_dir.mkdir(parents=True, exist_ok=True)
    existing_path = save_dir / f"{reg_no}.json"
    existing = {}
    if existing_path.exists():
        with open(existing_path) as f:
            existing = json.load(f)
    existing.update(st_stats)

    with open(existing_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"[OK] ST統計保存: {reg_no} → {existing_path.name}")
    return st_stats


# ──────────────────────────────────────────
# 6. 出走表から全選手のST統計を一括取得
# ──────────────────────────────────────────
def scrape_players_from_racecard(jcd: str, date: str, race_no: int):
    """
    出走表から登録番号を取得しST統計・性別を一括取得。
    ST統計はキャッシュがあればスキップ。性別はキャッシュ未記録の場合のみ取得。
    """
    path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
    if not path.exists():
        print(f"[WARN] 出走表未取得: {path}")
        return
    with open(path) as f:
        racecard = json.load(f)
    for racer in racecard.get("racers", []):
        reg_no = racer.get("reg_no", "")
        if not reg_no:
            continue
        cached = DATA_DIR / "players" / f"{reg_no}.json"
        if cached.exists():
            print(f"[SKIP] キャッシュあり: {reg_no}")
            # キャッシュはあるが性別未取得の場合は補完
            try:
                with open(cached) as f2:
                    pdata = json.load(f2)
                if "gender" not in pdata:
                    scrape_player_gender(reg_no)
            except Exception:
                pass
            continue
        scrape_player_st_stats(reg_no)
        # ST統計取得後に性別も取得（プロフィールページ）
        scrape_player_gender(reg_no)


# ──────────────────────────────────────────
# 7. 選手コメントの取得（福岡対応）
# ──────────────────────────────────────────
# 会場ごとのコメントページURL（今後他会場を追加）
COMMENT_SITE_URLS = {
    "07": "https://www.gamagori-kyotei.com/asp/gamagori/kyogi/kyogihtml/js/",  # JSファイルベースURL
    "21": "https://www.boatrace-ashiya.com/modules/raceinfo/?page=index_racers_comment",
    "22": "https://www.boatrace-fukuoka.com/modules/yosou/syussou.php",
    "23": "https://www.boatrace-karatsu.jp/modules/raceinfo/?page=index_racers_comment",
    "24": "https://omurakyotei.jp/yosou/comment.php",  # 全選手コメント＋モーター評価
}

# /modules/raceinfo/?page=index_racers_comment 形式の CMS を使う会場コード一覧
_MODULES_COMMENT_JCDS = {"21", "23"}

_VENUE_SUPPORT_FILE = Path(__file__).parent.parent / "data" / "venues" / "venue_site_support.json"
_VENUE_DISCOVERY_FILE = Path(__file__).parent.parent / "data" / "venues" / "venue_site_discovery.json"
_VENUE_TASKS_FILE = Path(__file__).parent.parent / "data" / "venues" / "venue_site_tasks.json"


def _load_json_file(path: Path, default):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_support_info(jcd: str) -> dict:
    support = _load_json_file(_VENUE_SUPPORT_FILE, {"venues": {}})
    return support.get("venues", {}).get(jcd, {})


def _record_site_discovery_task(jcd: str, trigger: str, support_info: dict, discovery: dict | None):
    tasks = _load_json_file(_VENUE_TASKS_FILE, {"tasks": []})
    task_id = f"{jcd}_comment_site_flow"
    tasks["tasks"] = [t for t in tasks.get("tasks", []) if t.get("id") != task_id]
    tasks["tasks"].append({
        "id": task_id,
        "jcd": jcd,
        "name": support_info.get("name", jcd),
        "site_url": support_info.get("site_url", ""),
        "status": "pending",
        "trigger": trigger,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "candidate_comment_links": (discovery or {}).get("comment_links", []),
        "candidate_review_links": (discovery or {}).get("review_links", []),
        "notes": "会場サイトの選手コメント取得ロジックを確認し、実装後 VENUE_SITE_CONFIG と scraper に組み込む。",
    })
    _save_json_file(_VENUE_TASKS_FILE, tasks)


def _discover_venue_site_links(jcd: str, support_info: dict) -> dict:
    """会場公式サイトのトップ付近からコメント候補リンクを自動抽出して保存する。"""
    site_url = support_info.get("site_url", "")
    if not site_url:
        return {}

    html = fetch(site_url, wait=0.5)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    discovery = {
        "jcd": jcd,
        "name": support_info.get("name", jcd),
        "site_url": site_url,
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comment_links": [],
        "review_links": [],
        "motor_links": [],
    }

    seen = set()
    for a in soup.find_all("a", href=True):
        text = re.sub(r"\s+", "", a.get_text(" ", strip=True))
        href = a.get("href", "").strip()
        if not href:
            continue
        full_url = requests.compat.urljoin(site_url, href)
        key = (text, full_url)
        if key in seen:
            continue
        seen.add(key)

        item = {"text": text[:80], "url": full_url}
        if any(k in text for k in ["コメント", "短評", "選手情報", "直前情報", "記者", "予想"]):
            discovery["comment_links"].append(item)
        if any(k in text for k in ["短評", "選手", "コメント"]):
            discovery["review_links"].append(item)
        if any(k in text for k in ["モーター", "エンジン", "機力", "通信簿"]):
            discovery["motor_links"].append(item)

    stored = _load_json_file(_VENUE_DISCOVERY_FILE, {"venues": {}})
    stored.setdefault("venues", {})[jcd] = discovery
    _save_json_file(_VENUE_DISCOVERY_FILE, stored)
    return discovery


def _run_venue_site_flow(jcd: str, trigger: str = "scrape_day") -> None:
    """
    新規会場を扱う時のルーチン:
      1. 公式サイト情報確認
      2. サイト内のコメント候補リンク探索
      3. 次回実装用タスクとして保存
    """
    support_info = _get_support_info(jcd)
    if not support_info:
        print(f"\n⚠️  [会場サイト] jcd={jcd} の公式サイト情報が未登録です。")
        return

    status = support_info.get("status", "unknown")
    if status == "implemented":
        return

    discovery = _discover_venue_site_links(jcd, support_info)
    _record_site_discovery_task(jcd, trigger, support_info, discovery)

    print(f"\n{'='*60}")
    print(f"🔎 [会場サイト自動調査] {support_info.get('name', jcd)}（jcd={jcd}）")
    print(f"   公式サイト : {support_info.get('site_url', '不明')}")
    print(f"   現在状態   : {status}")
    print(f"   コメント候補: {len(discovery.get('comment_links', []))}件")
    for item in discovery.get("comment_links", [])[:5]:
        print(f"    - {item.get('text', '')} -> {item.get('url', '')}")
    print(f"   保存先     : {_VENUE_TASKS_FILE.name}, {_VENUE_DISCOVERY_FILE.name}")
    print(f"{'='*60}\n")

def _check_venue_site_support(jcd: str) -> None:
    """会場固有サイトの調査状況を確認し、未調査の場合は調査を促す通知を出す。"""
    try:
        if not _VENUE_SUPPORT_FILE.exists():
            return
        support = json.loads(_VENUE_SUPPORT_FILE.read_text(encoding="utf-8"))
        info = support.get("venues", {}).get(jcd)
        if not info:
            print(f"\n⚠️  [会場サイト] jcd={jcd} の調査記録がありません。venue_site_support.json に追記してください。")
            return
        status   = info.get("status", "unknown")
        name     = info.get("name", jcd)
        site_url = info.get("site_url", "不明")
        priority = info.get("priority", "low")
        if status == "unknown":
            print(f"\n{'='*60}")
            print(f"🔍 [会場サイト未調査] {name}（jcd={jcd}）")
            print(f"   公式サイト : {site_url}")
            print(f"   優先度     : {priority}")
            print(f"   → 会場固有の補完情報（エンジン通信簿・選手短評等）がないか確認し")
            print(f"     data/venues/venue_site_support.json を更新してください。")
            print(f"{'='*60}\n")
        elif status == "investigated":
            feats = [k for k, v in info.get("features", {}).items() if v]
            print(f"\nℹ️  [会場サイト調査済み・未実装] {name}（jcd={jcd}）")
            print(f"   取得可能情報: {', '.join(feats) if feats else 'なし'}")
            print(f"   優先度={priority} / 実装検討推奨")
        elif status == "implemented":
            feats = [k for k, v in info.get("features", {}).items() if v]
            print(f"✅ [会場サイト] {name}（jcd={jcd}）: {', '.join(feats)} 取得済み")
    except Exception as e:
        print(f"[WARN] venue_site_support チェック失敗: {e}")


def _maybe_bootstrap_venue_site_flow(jcd: str, trigger: str = "scrape_day") -> None:
    """未実装会場に対して、自動調査フローを起動する。"""
    try:
        info = _get_support_info(jcd)
        if not info:
            return
        status = info.get("status", "unknown")
        if status in ("unknown", "investigated", "partial"):
            _run_venue_site_flow(jcd, trigger=trigger)
    except Exception as e:
        print(f"[WARN] 会場サイト自動調査失敗: {e}")


# 会場公式サイト設定（選手短評・エンジン通信簿・モーター成績）
VENUE_SITE_CONFIG = {
    "07": {  # 蒲郡
        "base":         "https://www.gamagori-kyotei.com",
        # コメントJSファイル: /asp/gamagori/kyogi/kyogihtml/js/comment{YYYYMMDD}07.js
        # HTMLページ(SP版): /asp/gamagori/sp/kyogi/kyogihtml/recomend/recomend{YYYYMMDD}0701.htm
        "comment_js_url": "https://www.gamagori-kyotei.com/asp/gamagori/kyogi/kyogihtml/js/comment{date}07.js",
    },
    "24": {  # 大村
        "base":          "https://omurakyotei.jp",
        "engine_report": "/yosou/motor.php",       # エンジン通信簿（モーター評価1-6点）
        "player_review": "/yosou/comment.php",     # 選手コメント（日次・足状態・モーター評価付き。?day=YYYYMMDD）
        "player_review_date_param": True,           # URLに ?day={date} を付加するフラグ
    },
    "22": {  # 福岡
        "base":          "https://www.boatrace-fukuoka.com",
        "player_review": "/modules/datafile/?page=index_tanpyou",  # 選手短評
        "motor_stats":   "/modules/datafile/?page=index_mrankdtl", # モーター成績
    },
    "23": {  # 唐津
        "base":            "https://www.boatrace-karatsu.jp",
        "comments_page":   "/modules/raceinfo/?page=index_racers_comment",
    },
    "21": {  # 芦屋（唐津と同CMS）
        "base":            "https://www.boatrace-ashiya.com",
        "comments_page":   "/modules/raceinfo/?page=index_racers_comment",
    },
    "19": {  # 下関
        "base":          "https://www.boatrace-shimonoseki.jp",
        "player_review": "/modules/raceinfo/?page=index_tenbo",    # レース展望（記事形式の選手形状テキスト）
        "player_review_type": "tenbo_article",                      # パーサー種別
    },
    "20": {  # 若松
        "base":          "https://www.wmb.jp",
        "timing_data":   "https://info.wmb.jp/pc/time.php",        # 節間タイム情報（外部サブドメイン）
    },
}


def _scrape_modules_comments_day(jcd: str, date: str) -> dict | None:
    """
    /modules/raceinfo/?page=index_racers_comment 形式の CMS サイトから
    節全体の選手コメントを取得する汎用パーサー。
    対応会場: 唐津(23), 芦屋(21), 今後同CMS の会場を追加可能。
    戻り値: {"comments_by_reg": {reg_no: {name, grade, comment_today, motor_eval_text}}} or None
    """
    cfg = VENUE_SITE_CONFIG.get(jcd, {})
    path = cfg.get("comments_page")
    if not path:
        return None

    base = cfg["base"]
    html = fetch(f"{base}{path}", wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    target_table = None
    for tbl in soup.find_all("table"):
        th_text = " ".join(th.get_text(" ", strip=True) for th in tbl.find_all("th"))
        if "選手コメント" in th_text and "登番" in th_text:
            target_table = tbl
            break
    if not target_table:
        return None

    comments_by_reg = {}
    for row in target_table.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue

        col1 = tds[0].get_text("\n", strip=True)
        m = re.search(r"(\d{4})\s*/\s*([AB][12])", col1)
        if not m:
            continue
        reg_no = m.group(1)
        grade = m.group(2)
        lines = [re.sub(r"\s+", "", x) for x in col1.splitlines() if x.strip()]
        name = ""
        for line in lines:
            if reg_no in line or grade in line:
                continue
            name = line
            break

        motor_eval_text = re.sub(r"\s+", " ", tds[1].get_text(" ", strip=True)).strip()
        comment_text = re.sub(r"\s+", " ", tds[2].get_text(" ", strip=True)).strip()

        comments_by_reg[reg_no] = {
            "player_name": name,
            "grade": grade,
            "comment_today": comment_text,
            "comment_prev": "",
            "motor_eval_text": motor_eval_text,
        }

    if not comments_by_reg:
        return None

    return {
        "venue_code": jcd,
        "date": date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comments_by_reg": comments_by_reg,
    }


def _scrape_karatsu_comments_day(date: str) -> dict | None:
    return _scrape_modules_comments_day("23", date)


def _scrape_omura_comments_day(date: str) -> dict | None:
    """
    大村公式予想サイト（omurakyotei.jp/yosou/comment.php）から
    節の全選手コメント＋モーター評価を取得する。

    テーブル構造:
      header: [選手名, コメント, モーター, 過去コメント]
      row:
        td[0]: <a href="...?toban=XXXX">選手名</a> → reg_no=XXXX
        td[1]: コメント本文（<font color="red"> 内は当日気配）
        td[2]: <p class="motorpoint">N点</p> + モーター番号
        td[3]: 過去コメントリンク（無視）

    戻り値: {"comments_by_reg": {reg_no: {name, comment_today, motor_eval_text}}} or None
    """
    cfg = VENUE_SITE_CONFIG.get("24", {})
    base = cfg.get("base", "https://omurakyotei.jp")
    path = cfg.get("player_review", "/yosou/comment.php")
    url = f"{base}{path}?day={date}"

    html = fetch(url, wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # ヘッダーに「選手名」「コメント」を含むテーブルを探す
    target_table = None
    for tbl in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in tbl.find_all("th")]
        if "選手名" in ths and "コメント" in ths:
            target_table = tbl
            break
    if not target_table:
        return None

    comments_by_reg = {}
    for row in target_table.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue

        # td[0]: 選手名 + 登録番号
        name_link = tds[0].find("a", href=True)
        if not name_link:
            continue
        href = name_link.get("href", "")
        m = re.search(r"toban=(\d+)", href)
        if not m:
            continue
        reg_no = m.group(1)
        name = re.sub(r"\s+", "", name_link.get_text(strip=True))

        # td[1]: コメント（赤字は当日気配）
        comment_td = tds[1]
        # 赤字（当日気配）があればそちらを優先、なければ通常テキスト
        red_font = comment_td.find("font", color=True)
        if red_font:
            comment_today = re.sub(r"\s+", " ", red_font.get_text(" ", strip=True)).strip()
            # 赤字以外の通常コメントも取得
            comment_prev = ""
            for child in comment_td.children:
                if child == red_font or (hasattr(child, "name") and child.name in ("font", "br")):
                    continue
                t = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                if t:
                    comment_prev = re.sub(r"\s+", " ", t).strip()
                    break
        else:
            comment_today = re.sub(r"\s+", " ", comment_td.get_text(" ", strip=True)).strip()
            comment_prev = ""

        # td[2]: モーター評価
        motor_p = tds[2].find("p", class_="motorpoint")
        motor_eval = motor_p.get_text(strip=True) if motor_p else ""
        motor_link = tds[2].find("a")
        motor_no = motor_link.get_text(strip=True) if motor_link else ""
        motor_eval_text = f"{motor_eval} {motor_no}".strip()

        comments_by_reg[reg_no] = {
            "player_name": name,
            "comment_today": comment_today,
            "comment_prev": comment_prev,
            "motor_eval_text": motor_eval_text,
        }

    if not comments_by_reg:
        return None

    return {
        "venue_code": "24",
        "date": date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comments_by_reg": comments_by_reg,
    }


def _scrape_gamagori_comments_day(date: str) -> dict | None:
    """
    蒲郡公式サイトのコメントJSファイルから節全体のコメントを取得する。
    URL: https://www.gamagori-kyotei.com/asp/gamagori/kyogi/kyogihtml/js/comment{date}07.js

    JSファイル内の funcBeforeComment（前日）と funcToDayComment（当日）を解析し、
    登録番号をキーにコメントを返す。

    戻り値: {"comments_by_reg": {reg_no: {"comment_today": str, "comment_prev": str, ...}}} or None
    """
    cfg = VENUE_SITE_CONFIG.get("07", {})
    js_url_tpl = cfg.get("comment_js_url", "")
    if not js_url_tpl:
        return None

    js_url = js_url_tpl.format(date=date)
    js = fetch(js_url, wait=0.5)
    if not js:
        return None

    def _parse_comment_func(js_text: str, func_name: str) -> dict:
        """funcXxx(argTouban) の if-elseif ブロックを解析して {reg_no: comment} を返す。"""
        result = {}
        pattern = re.compile(
            r"function\s+" + re.escape(func_name) + r"\s*\([^)]*\)\s*\{(.*?)\n\}",
            re.DOTALL,
        )
        m = pattern.search(js_text)
        if not m:
            return result
        body = m.group(1)
        entries = re.findall(
            r"strTouban\s*===\s*'(\d+)'[^}]*?strComment\s*=\s*'(.*?)'\s*;",
            body,
            re.DOTALL,
        )
        for touban, comment in entries:
            result[touban] = comment.replace("\\'", "'")
        return result

    before_comments = _parse_comment_func(js, "funcBeforeComment")
    today_comments  = _parse_comment_func(js, "funcToDayComment")

    if not today_comments and not before_comments:
        return None

    all_regs = set(before_comments) | set(today_comments)
    comments_by_reg = {
        reg_no: {
            "player_name":    "",  # racecard から補完
            "comment_today":  today_comments.get(reg_no, ""),
            "comment_prev":   before_comments.get(reg_no, ""),
            "motor_eval_text": "",
        }
        for reg_no in all_regs
    }

    return {
        "venue_code":    "07",
        "date":          date,
        "scraped_at":    datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comments_by_reg": comments_by_reg,
    }


def scrape_comments(jcd: str, date: str, race_no: int) -> dict | None:
    """
    会場公式サイトから選手コメントを取得（当日・前日）
    現対応: 蒲郡(07), 芦屋(21), 福岡(22), 唐津(23), 大村(24)
    戻り値: {waku: {player_name, comment_today, comment_prev}} or None
    """
    base_url = COMMENT_SITE_URLS.get(jcd)
    if not base_url:
        return None  # 未対応会場はスキップ（predictorで中立値を使用）

    # ── 大村(24): omurakyotei.jp の日次コメントページ ──
    if jcd == "24":
        day_comments = _scrape_omura_comments_day(date)
        if not day_comments:
            return None

        racecard_path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
        if not racecard_path.exists():
            return None

        with open(racecard_path, encoding="utf-8") as f:
            racecard = json.load(f)

        comments_by_reg = day_comments.get("comments_by_reg", {})
        comments_by_waku = {}
        for racer in racecard.get("racers", []):
            waku = racer.get("waku")
            reg_no = str(racer.get("reg_no", "")).strip()
            if not waku or not reg_no:
                continue
            comment_data = comments_by_reg.get(reg_no, {})
            comments_by_waku[int(waku)] = {
                "player_name": comment_data.get("player_name") or racer.get("name", ""),
                "comment_today": comment_data.get("comment_today", ""),
                "comment_prev": comment_data.get("comment_prev", ""),
                "motor_eval_text": comment_data.get("motor_eval_text", ""),
                "reg_no": reg_no,
            }

        if not comments_by_waku:
            return None

        result = {
            "venue_code": jcd,
            "date": date,
            "race_no": race_no,
            "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "comments": comments_by_waku,
        }
        save_dir = DATA_DIR / "comments" / date
        save_dir.mkdir(parents=True, exist_ok=True)
        out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] コメント保存: {jcd} {race_no}R → {out_path.name}")
        _append_comment_history(jcd, date, race_no, comments_by_waku)
        return result

    if jcd == "07":
        day_comments = _scrape_gamagori_comments_day(date)
        if not day_comments:
            return None

        racecard_path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
        if not racecard_path.exists():
            return None

        with open(racecard_path, encoding="utf-8") as f:
            racecard = json.load(f)

        comments_by_reg = day_comments.get("comments_by_reg", {})
        comments_by_waku = {}
        for racer in racecard.get("racers", []):
            waku   = racer.get("waku")
            reg_no = str(racer.get("reg_no", "")).strip()
            if not waku or not reg_no:
                continue

            comment_data = comments_by_reg.get(reg_no, {})
            comments_by_waku[int(waku)] = {
                "player_name":    comment_data.get("player_name") or racer.get("name", ""),
                "comment_today":  comment_data.get("comment_today", ""),
                "comment_prev":   comment_data.get("comment_prev", ""),
                "motor_eval_text": comment_data.get("motor_eval_text", ""),
                "reg_no":         reg_no,
            }

        if not comments_by_waku:
            return None

        result = {
            "venue_code": jcd,
            "date":       date,
            "race_no":    race_no,
            "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "comments":   comments_by_waku,
        }

        save_dir = DATA_DIR / "comments" / date
        save_dir.mkdir(parents=True, exist_ok=True)
        out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] コメント保存: {jcd} {race_no}R → {out_path.name}")

        _append_comment_history(jcd, date, race_no, comments_by_waku)
        return result

    # /modules/raceinfo/?page=index_racers_comment 形式の CMS 共通パーサー (唐津/芦屋 etc.)
    if jcd in _MODULES_COMMENT_JCDS:
        day_comments = _scrape_modules_comments_day(jcd, date)
        if not day_comments:
            return None

        racecard_path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
        if not racecard_path.exists():
            return None

        with open(racecard_path, encoding="utf-8") as f:
            racecard = json.load(f)

        comments_by_reg = day_comments.get("comments_by_reg", {})
        comments_by_waku = {}
        for racer in racecard.get("racers", []):
            waku = racer.get("waku")
            reg_no = str(racer.get("reg_no", "")).strip()
            if not waku or not reg_no:
                continue

            comment_data = comments_by_reg.get(reg_no, {})
            comments_by_waku[int(waku)] = {
                "player_name": comment_data.get("player_name") or racer.get("name", ""),
                "comment_today": comment_data.get("comment_today", ""),
                "comment_prev": comment_data.get("comment_prev", ""),
                "motor_eval_text": comment_data.get("motor_eval_text", ""),
                "reg_no": reg_no,
            }

        if not comments_by_waku:
            return None

        result = {
            "venue_code": jcd,
            "date": date,
            "race_no": race_no,
            "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "comments": comments_by_waku,
        }

        save_dir = DATA_DIR / "comments" / date
        save_dir.mkdir(parents=True, exist_ok=True)
        out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[OK] コメント保存: {jcd} {race_no}R → {out_path.name}")

        _append_comment_history(jcd, date, race_no, comments_by_waku)
        return result

    html = fetch(f"{base_url}?day={date}&race={race_no}&if=1&nowmode=1", wait=1.0)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # col13 = 「過去コメント」列（各選手1セル）
    comment_tds = [td for td in soup.find_all("td")
                   if "col13" in " ".join(td.get("class", []))]

    today_fmt     = f"{date[:4]}/{date[4:6]}/{date[6:8]}"
    prev_day      = (datetime.datetime.strptime(date, "%Y%m%d")
                     - datetime.timedelta(days=1)).strftime("%Y/%m/%d")

    comments_by_waku = {}
    for waku_idx, td in enumerate(comment_tds[:6], start=1):
        text = td.get_text(separator="\n", strip=True)

        # 選手名 "XX YY選手の過去コメント"
        nm = re.search(r"(.+?)選手の過去コメント", text)
        player_name = nm.group(1).strip().replace("\u3000", "").replace(" ", "") if nm else ""

        # 日付ごとコメントを抽出
        entries = re.findall(
            r"(\d{4}/\d{2}/\d{2})\s+([\s\S]+?)(?=\d{4}/\d{2}/\d{2}|$)",
            text
        )
        comment_today = ""
        comment_prev  = ""
        for dc_date, dc_text in entries:
            clean = re.sub(r"\s+", "", dc_text).strip()
            if dc_date == today_fmt:
                comment_today = clean
            elif dc_date == prev_day:
                comment_prev = clean

        comments_by_waku[waku_idx] = {
            "player_name":    player_name,
            "comment_today":  comment_today,
            "comment_prev":   comment_prev,
        }

    result = {
        "venue_code": jcd,
        "date":       date,
        "race_no":    race_no,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comments":   comments_by_waku,
    }

    # data/comments/{date}/{jcd}_R{race:02d}.json に保存
    save_dir = DATA_DIR / "comments" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] コメント保存: {jcd} {race_no}R → {out_path.name}")

    # 選手別コメント履歴に追記
    _append_comment_history(jcd, date, race_no, comments_by_waku)

    return result


def _append_comment_history(jcd: str, date: str, race_no: int,
                             comments_by_waku: dict):
    """選手ごとのコメント履歴 data/player_comments/{reg_no}.json に追記"""
    racecard_path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
    if not racecard_path.exists():
        return
    with open(racecard_path) as f:
        racecard = json.load(f)

    reg_by_waku = {str(r["waku"]): r.get("reg_no", "")
                   for r in racecard.get("racers", [])}

    hist_dir = DATA_DIR / "player_comments"
    hist_dir.mkdir(exist_ok=True)

    for waku, cdata in comments_by_waku.items():
        reg_no = reg_by_waku.get(str(waku), "")
        today_comment = cdata.get("comment_today", "")
        if not reg_no or not today_comment:
            continue

        hist_path = hist_dir / f"{reg_no}.json"
        history = []
        if hist_path.exists():
            with open(hist_path) as f:
                history = json.load(f)

        # 同日・同会場の重複は上書き
        history = [h for h in history if not (h["date"] == date and h["jcd"] == jcd)]
        history.append({
            "date":    date,
            "jcd":     jcd,
            "race_no": race_no,
            "comment": today_comment,
        })
        history.sort(key=lambda x: x["date"], reverse=True)

        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────
# 8. 公式ピットレポート取得（全会場・R7-12）
# ──────────────────────────────────────────
def scrape_pitreport(jcd: str, date: str, race_no: int) -> dict | None:
    """
    公式サイトの「ピットレポート」ページから選手コメントを取得。
    全会場対応。公式の仕様上 R7〜12 のみコメントが掲載される。
    R1〜6 を指定した場合は None を返す。

    取得フィールド（枠ごと）:
      reg_no      : 登録番号
      comment     : ピットレポートコメント（選手の足状態・調整等）
      prev_result : 前走の結果レース番号 (例: '5R', '未出走')
    """
    if race_no < 7:
        return None  # 公式仕様: R7-12のみ掲載

    url = "https://www.boatrace.jp/owpc/pc/race/pitreport"
    html = fetch(url, {"jcd": jcd, "hd": date, "rno": race_no})
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    # 「ピットレポート」列ヘッダーを持つテーブルを探す
    pit_table = None
    for tbl in tables:
        ths = [th.get_text(strip=True) for th in tbl.find_all("th")]
        if "ピットレポート" in ths:
            pit_table = tbl
            break

    if not pit_table:
        return None  # データなし（レース前など）

    comments_by_waku = {}
    for row in pit_table.find_all("tr"):
        tds = row.find_all("td")
        # データ行は5列: 枠 / 写真 / 選手情報 / コメント / 前走結果
        if len(tds) < 4:
            continue
        waku_text = tds[0].get_text(strip=True)
        if not waku_text.isdigit() or not (1 <= int(waku_text) <= 6):
            continue
        waku = int(waku_text)

        # 選手情報セル（登録番号を抽出）
        player_text = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        reg_match = re.search(r"(\d{4})", player_text)
        reg_no = reg_match.group(1) if reg_match else ""

        # コメント本文
        comment_text = tds[3].get_text(strip=True) if len(tds) > 3 else ""

        # 前走レース番号
        prev_result = tds[4].get_text(strip=True) if len(tds) > 4 else ""

        comments_by_waku[waku] = {
            "reg_no":      reg_no,
            "comment":     comment_text,
            "prev_result": prev_result,
        }

    if not comments_by_waku:
        return None

    result = {
        "venue_code": jcd,
        "date":       date,
        "race_no":    race_no,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "comments":   comments_by_waku,
    }

    # data/player_comments/{date}/{jcd}_R{race:02d}_pitreport.json に保存
    save_dir = DATA_DIR / "player_comments" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_R{race_no:02d}_pitreport.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] ピットレポート保存: {jcd} {race_no}R → {out_path.name}")

    return result


# ──────────────────────────────────────────
# 9. コメント対応管理（comment_support.json）
# ──────────────────────────────────────────

_COMMENT_SUPPORT_FILE = DATA_DIR / "venues" / "comment_support.json"


def _load_comment_support() -> dict:
    """comment_support.json を読み込む。失敗時は空辞書を返す。"""
    try:
        if _COMMENT_SUPPORT_FILE.exists():
            with open(_COMMENT_SUPPORT_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[WARN] comment_support.json 読み込み失敗: {e}")
    return {"venues": {}}


def _save_comment_support(data: dict) -> None:
    """comment_support.json を保存する。"""
    try:
        _COMMENT_SUPPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        data["updated"] = datetime.date.today().strftime("%Y-%m-%d")
        with open(_COMMENT_SUPPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] comment_support.json 保存失敗: {e}")


def _detect_comment_parser(html: str, pattern_name: str) -> bool:
    """
    取得したHTMLがパターンに対応しているかを簡易判定する。
    Returns True if the pattern matches.
    """
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    if pattern_name == "karatsu_style":
        # 全選手コメントテーブル（登番/選手コメント列あり）
        for tbl in soup.find_all("table"):
            th_text = " ".join(th.get_text(" ", strip=True) for th in tbl.find_all("th"))
            if "選手コメント" in th_text and "登番" in th_text:
                return True
        return False
    elif pattern_name == "fukuoka_style":
        # col13 クラスが6つ以上ある
        return len([td for td in soup.find_all("td") if "col13" in " ".join(td.get("class", []))]) >= 1
    elif pattern_name == "tenbo_article":
        # .tenbo_kiji_area と .player_list が存在する
        return bool(soup.find(class_="tenbo_kiji_area")) and bool(soup.find(class_="player_list"))
    elif pattern_name == "omura_style":
        # toban=XXXX 形式のリンクがある
        for a in soup.find_all("a", href=True):
            if re.search(r"toban=\d{4}", a["href"]):
                return True
        return False
    return False


def _investigate_comment_support(jcd: str, site_base: str) -> dict:
    """
    未調査会場に対して標準URLパターンを順に試し、マッチしたパーサーを返す。

    Returns: {"status": "implemented"|"none", "parser": str|None, "url": str|None, "notes": str}
    """
    today = datetime.date.today().strftime("%Y%m%d")
    support_data = _load_comment_support()
    patterns = support_data.get("investigation", {}).get("standard_patterns", [])

    print(f"\n🔍 [コメント自動調査] {jcd} ({site_base})")
    tried = []

    for pat in patterns:
        path = pat["path"]
        name = pat["name"]
        desc = pat.get("description", name)

        # 大村型は日付パラメータが必要なので付与
        url = f"{site_base}{path}" if path.startswith("/") else path
        if name == "omura_style":
            url += f"?day={today}"

        print(f"  試行: {desc} → {url}")
        html = fetch(url, wait=0.8)
        tried.append(url)

        if _detect_comment_parser(html, name):
            print(f"  ✅ マッチ: {name}")
            return {
                "status": "implemented",
                "parser": name,
                "url": url.split("?day=")[0],  # 日付パラメータは除去して保存
                "notes": f"自動調査で {desc} パターンを検出。{datetime.date.today()}",
                "last_checked": str(datetime.date.today()),
                "last_success": str(datetime.date.today()),
            }
        else:
            print(f"  ✗ 不一致")

    print(f"  → 有効なコメントページ未検出。調査済みとして none に登録。")
    return {
        "status": "none",
        "parser": None,
        "url": None,
        "notes": f"自動調査済み（{datetime.date.today()}）。試行URL: {'; '.join(tried[:3])}",
        "last_checked": str(datetime.date.today()),
        "last_success": None,
    }


def _scrape_shimonoseki_tenbo_review(date: str) -> dict | None:
    """
    下関公式サイトの「レース展望」から各選手の形状テキストを取得する。
    .tenbo_kiji_area の本文 + .player_list の登番リストを紐づけて選手短評として保存。

    戻り値: {reg_no: {name, review, scraped_from}} or None
    """
    cfg = VENUE_SITE_CONFIG.get("19", {})
    base = cfg.get("base", "")
    path = cfg.get("player_review", "")
    if not base or not path:
        return None

    url = f"{base}{path}"
    html = fetch(url, wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 本文エリア（.tenbo_kiji_area > .main_kiji）
    kiji_area = soup.find(class_="tenbo_kiji_area")
    if not kiji_area:
        print(f"[WARN] 下関レース展望: tenbo_kiji_area が見つかりません ({url})")
        return None

    main_kiji = kiji_area.find(class_="main_kiji")
    article_text = re.sub(r"\s+", " ", main_kiji.get_text(" ", strip=True)) if main_kiji else ""

    # 主な出場選手リスト（.player_list > .player_item）から登番・選手名を取得
    player_list = soup.find(class_="player_list")
    if not player_list:
        print(f"[WARN] 下関レース展望: player_list が見つかりません")
        return None

    players_in_article = []
    for item in player_list.find_all(class_="player_item"):
        # 登番は "A1 /3942（山口）" 形式の player_detail から抽出
        detail_el = item.find(class_="player_detail")
        name_el   = item.find(class_="player_name")
        if not detail_el or not name_el:
            continue

        detail_text = detail_el.get_text(" ", strip=True)
        m = re.search(r"/(\d{4})", detail_text)
        if not m:
            continue

        reg_no = m.group(1)
        name   = re.sub(r"\s+", "", name_el.get_text())
        # 支部
        branch_m = re.search(r"（(.+?)）", detail_text)
        branch = branch_m.group(1) if branch_m else ""

        players_in_article.append({"reg_no": reg_no, "name": name, "branch": branch})

    if not players_in_article:
        return None

    # 本文から各選手の言及文を抽出
    reviews = {}
    for p in players_in_article:
        name_clean = p["name"].replace("\u3000", "").replace(" ", "")
        # 選手名を含む文（句読点区切り）を抽出
        sentences = re.split(r"[。、\n]", article_text)
        mentions = [s.strip() for s in sentences if name_clean in s and len(s.strip()) > 5]
        review_text = "。".join(mentions[:3])  # 最大3文

        if review_text:
            reviews[p["reg_no"]] = {
                "name":          p["name"],
                "review":        review_text,
                "scraped_from":  "tenbo_article",
            }

    # 出場選手一覧ページからも登番を補完（レース展望に載らない選手用）
    assen_html = fetch(f"{base}/modules/raceinfo/?page=index_assen", wait=0.8)
    if assen_html:
        assen_soup = BeautifulSoup(assen_html, "html.parser")
        for tbl in assen_soup.find_all("table"):
            for row in tbl.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) < 3:
                    continue
                # 登番は最初の数値セル
                reg_m = re.match(r"^(\d{4})$", tds[0].get_text(strip=True))
                if not reg_m:
                    continue
                reg_no = reg_m.group(1)
                if reg_no not in reviews:
                    # 言及なし → 空レビューで登録（中立扱い）
                    name_raw = tds[1].get_text(strip=True) if len(tds) > 1 else ""
                    reviews[reg_no] = {
                        "name":         re.sub(r"\s+", "", name_raw),
                        "review":       "",
                        "scraped_from": "tenbo_article",
                    }

    if not reviews:
        return None

    result = {
        "venue_code": "19",
        "date":       date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "reviews":    reviews,
    }

    save_dir = DATA_DIR / "player_comments" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / "19_player_review.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 下関レース展望保存: {len(reviews)}選手 → {out_path.name}")
    return result


def _scrape_wakamatsu_timing(date: str) -> dict | None:
    """
    若松公式サブサイト info.wmb.jp/pc/time.php から節間タイム情報を取得する。
    取得フィールド: 登番, 選手名, 級別, モーター番号, 前検タイム, 今節平均ST,
                   最高上がりタイム, 最高1周タイム, 最高直線タイム, 最高展示タイム
    保存先: data/player_comments/{date}/20_timing.json

    戻り値: {reg_no: {name, motor_no, jikken_time, avg_st, ...}} or None
    """
    cfg = VENUE_SITE_CONFIG.get("20", {})
    url = cfg.get("timing_data", "")
    if not url:
        return None

    html = fetch(url, wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    tbl = soup.find("table")
    if not tbl:
        return None

    # ヘッダー列名マッピング
    headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
    COL_MAP = {
        "登番選手名":      "reg_name",
        "級別":           "grade",
        "ﾓｰﾀｰ":          "motor_no",
        "前検タイム":      "jikken_time",
        "今節平均ST":      "avg_st",
        "最高上がりタイム":"best_agari",
        "最高1周タイム":   "best_1lap",
        "最高直線タイム":  "best_chokusen",
        "最高展示タイム":  "best_tenshi",
    }
    col_indices = {}
    for i, h in enumerate(headers):
        key = COL_MAP.get(h)
        if key:
            col_indices[key] = i

    if "reg_name" not in col_indices:
        print(f"[WARN] 若松タイム: 登番列が見つかりません")
        return None

    timing = {}
    for row in tbl.find_all("tr")[1:]:  # ヘッダー行をスキップ
        tds = [td.get_text(strip=True) for td in row.find_all("td")]
        if not tds:
            continue

        reg_name_raw = tds[col_indices["reg_name"]] if "reg_name" in col_indices else ""
        # "3305小野\u3000信樹" → reg_no=3305, name=小野信樹
        m = re.match(r"(\d{4})(.+)", reg_name_raw.replace("\u3000", "　"))
        if not m:
            continue

        reg_no = m.group(1)
        name   = re.sub(r"\s+", "", m.group(2))

        def _get(key: str) -> str:
            idx = col_indices.get(key)
            return tds[idx] if idx is not None and idx < len(tds) else ""

        timing[reg_no] = {
            "name":          name,
            "grade":         _get("grade"),
            "motor_no":      _get("motor_no"),
            "jikken_time":   _get("jikken_time"),    # 前検タイム（例: "6.81"）
            "avg_st":        _get("avg_st"),          # 今節平均ST（例: "0.17"）
            "best_agari":    _get("best_agari"),
            "best_1lap":     _get("best_1lap"),
            "best_chokusen": _get("best_chokusen"),
            "best_tenshi":   _get("best_tenshi"),     # 最高展示タイム
        }

    if not timing:
        return None

    result = {
        "venue_code": "20",
        "date":       date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "timing":     timing,
    }

    save_dir = DATA_DIR / "player_comments" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / "20_timing.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 若松タイム情報保存: {len(timing)}選手 → {out_path.name}")
    return result


def run_comment_scraper(jcd: str, date: str, race_no: int | None = None) -> bool:
    """
    コメント対応フローの統一エントリーポイント。

    1. comment_support.json を参照して会場の対応状況を確認
    2. status == "unknown" → 自動調査フローを起動し、発見できれば登録・実行
    3. status == "implemented" → 登録済みパーサーでスクレイピング実行
    4. status == "timing_only" → タイムデータスクレイパーを実行
    5. status == "none" → スキップ（静かに return False）

    Args:
        jcd:      会場コード
        date:     日付 (YYYYMMDD)
        race_no:  レース番号（None の場合は日次一括処理）

    Returns:
        True if any data was successfully scraped/saved.
    """
    support_data = _load_comment_support()
    venues = support_data.get("venues", {})
    venue  = venues.get(jcd, {})
    status = venue.get("status", "unknown")
    name   = venue.get("name", f"jcd={jcd}")

    # ── unknown: 自動調査フロー ───────────────────────────────────────
    if status == "unknown":
        site_info = _get_support_info(jcd)  # venue_site_support.json から base URL 取得
        site_base = site_info.get("site_url", "")
        if not site_base:
            print(f"[SKIP] {name}({jcd}): 公式サイトURL不明。venue_site_support.json を確認してください。")
            # unknown のまま返す（再調査の余地を残す）
            return False

        print(f"\n📋 [{name}({jcd})] comment_support: 未調査 → 自動調査を開始")

        # 調査中に設定（多重起動防止）
        venues[jcd] = {**venue, "status": "investigating", "name": name}
        _save_comment_support(support_data)

        result = _investigate_comment_support(jcd, site_base.rstrip("/"))

        # 結果を反映して保存
        venues[jcd] = {
            "name":         name,
            "status":       result["status"],
            "type":         _parser_to_type(result.get("parser")),
            "parser":       result.get("parser"),
            "url":          result.get("url"),
            "notes":        result.get("notes", ""),
            "last_checked": result.get("last_checked"),
            "last_success": result.get("last_success"),
        }
        _save_comment_support(support_data)

        if result["status"] == "implemented":
            # 登録成功 → そのまま実行
            return _execute_comment_scraper(jcd, date, race_no, venues[jcd])
        return False

    # ── implemented: 登録済みスクレイパーを実行 ──────────────────────
    elif status == "implemented":
        return _execute_comment_scraper(jcd, date, race_no, venue)

    # ── timing_only: タイムデータスクレイパーを実行 ──────────────────
    elif status == "timing_only":
        return _execute_timing_scraper(jcd, date)

    # ── none / investigating: スキップ ──────────────────────────────
    else:
        return False


def _parser_to_type(parser: str | None) -> str | None:
    """パーサー名から type 文字列に変換する。"""
    if parser in ("fukuoka", "karatsu"):
        return "comments_venue"
    if parser in ("omura", "shimonoseki_tenbo", "tenbo_article"):
        return "player_review"
    return None


def _execute_comment_scraper(jcd: str, date: str, race_no: int | None, venue: dict) -> bool:
    """
    comment_support.json に登録済みのパーサーを使ってスクレイピングを実行する。
    成功時は last_success を更新する。
    """
    parser = venue.get("parser")
    ok = False

    try:
        if parser == "fukuoka":
            if race_no is not None:
                ok = scrape_comments(jcd, date, race_no) is not None
            else:
                ok = any(scrape_comments(jcd, date, r) is not None for r in range(1, 13))

        elif parser == "karatsu":
            if race_no is not None:
                ok = scrape_comments(jcd, date, race_no) is not None
            else:
                ok = any(scrape_comments(jcd, date, r) is not None for r in range(1, 13))

        elif parser == "omura":
            ok = scrape_player_review(jcd, date) is not None

        elif parser in ("shimonoseki_tenbo", "tenbo_article"):
            ok = _scrape_shimonoseki_tenbo_review(date) is not None

        elif parser == "wakamatsu_timing":
            ok = _scrape_wakamatsu_timing(date) is not None

        else:
            # 未知パーサー: scrape_comments で試みる
            print(f"[WARN] 未知パーサー '{parser}' → scrape_comments() にフォールバック")
            if race_no is not None:
                ok = scrape_comments(jcd, date, race_no) is not None

        if ok:
            # last_success を更新
            support_data = _load_comment_support()
            v = support_data.get("venues", {}).get(jcd, {})
            v["last_success"] = str(datetime.date.today())
            support_data["venues"][jcd] = v
            _save_comment_support(support_data)

    except Exception as e:
        print(f"[ERROR] run_comment_scraper({jcd}): {e}")

    return ok


def _execute_timing_scraper(jcd: str, date: str) -> bool:
    """timing_only 会場用タイムデータスクレイパーを実行する。"""
    if jcd == "20":
        ok = _scrape_wakamatsu_timing(date) is not None
        if ok:
            support_data = _load_comment_support()
            v = support_data.get("venues", {}).get(jcd, {})
            v["last_success"] = str(datetime.date.today())
            support_data["venues"][jcd] = v
            _save_comment_support(support_data)
        return ok
    return False


# ──────────────────────────────────────────
# 10. 会場公式サイト補完情報の取得
# ──────────────────────────────────────────

def scrape_engine_report(jcd: str, date: str) -> dict | None:
    """
    会場公式サイトから「エンジン通信簿」を取得。
    現対応: 大村(24)

    戻り値: {
        "motor_no": { "reg_no": str, "eval": int(1-6), "name": str },
        ...
    }
    eval は会場スタッフによる前日評価:
        6=最優秀, 5=良, 4=普通, 3=やや不良, 2=不良, 1=最不良
    """
    cfg = VENUE_SITE_CONFIG.get(jcd, {})
    path = cfg.get("engine_report")
    if not path:
        return None  # 未対応会場

    base = cfg["base"]
    html = fetch(f"{base}{path}", wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    motor_data = {}

    for tbl in soup.find_all("table"):
        for cell_td in tbl.find_all("td"):
            cell_text = cell_td.get_text(strip=True)
            # パターン: "11号機[4343]村 岡    賢(前日評価：6)"
            m = re.match(r"(\d+)号機\[(\d{4})\](.+?)\(前日評価：(\d)\)", cell_text)
            if m:
                motor_no, reg_no, name_raw, eval_str = m.groups()
                motor_data[motor_no] = {
                    "reg_no": reg_no,
                    "eval":   int(eval_str),
                    "name":   re.sub(r"\s+", "", name_raw),
                }

    if not motor_data:
        return None

    result = {
        "venue_code": jcd,
        "date":       date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motors":     motor_data,
    }

    save_dir = DATA_DIR / "motors" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_engine_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] エンジン通信簿保存: {jcd} ({len(motor_data)}機) → {out_path.name}")
    return result


def scrape_player_review(jcd: str, date: str) -> dict | None:
    """
    会場公式サイトから「選手コメント/短評」を取得。
    現対応: 大村(24) … 日次コメント+モーター評価 /yosou/comment.php?day={date}
             福岡(22) … シリーズ単位短評 /modules/datafile/?page=index_tanpyou

    戻り値: { reg_no: {"name": str, "review": str, ...}, ... }
    """
    cfg = VENUE_SITE_CONFIG.get(jcd, {})
    path = cfg.get("player_review")
    if not path:
        return None

    base = cfg["base"]
    use_date_param = cfg.get("player_review_date_param", False)
    url = f"{base}{path}?day={date}" if use_date_param else f"{base}{path}"
    html = fetch(url, wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    reviews = {}

    if use_date_param:
        # 大村方式: td[0]=選手名リンク(toban=XXXX), td[1]=コメント, td[2]=モーター評価("X点"), td[3]=モーター号機
        for tbl in soup.find_all("table"):
            for row in tbl.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) < 2:
                    continue
                a_tag = tds[0].find("a")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                m = re.search(r'toban=(\d{4})', href)
                if not m:
                    continue
                reg_no = m.group(1)
                name   = re.sub(r"\s+", "", a_tag.get_text())
                review = tds[1].get_text(strip=True)
                motor_score = tds[2].get_text(strip=True) if len(tds) > 2 else ""
                reviews[reg_no] = {"name": name, "review": review, "motor_score": motor_score}
    else:
        # 福岡方式: td[0]=登録番号(4桁), td[1]=選手名, td[2]=短評
        for tbl in soup.find_all("table"):
            for row in tbl.find_all("tr"):
                tds = [td.get_text(strip=True) for td in row.find_all("td")]
                tds = [t for t in tds if t]
                # パターン: [登録番号, 選手名, 短評テキスト]
                if len(tds) >= 3 and tds[0].isdigit() and len(tds[0]) == 4:
                    reg_no = tds[0]
                    name   = re.sub(r"\s+", "", tds[1])
                    review = tds[2].strip()
                    reviews[reg_no] = {"name": name, "review": review}

    if not reviews:
        return None

    result = {
        "venue_code": jcd,
        "date":       date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "reviews":    reviews,
    }

    save_dir = DATA_DIR / "player_comments" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_player_review.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 選手短評保存: {jcd} ({len(reviews)}選手) → {out_path.name}")
    return result


def scrape_venue_motor_stats(jcd: str, date: str) -> dict | None:
    """
    会場公式サイトから「モーター成績」を取得（節間累積）。
    現対応: 福岡(22)

    戻り値: { motor_no: {"top2_rate": float, "win_rate": float, "races": int}, ... }
    """
    cfg = VENUE_SITE_CONFIG.get(jcd, {})
    path = cfg.get("motor_stats")
    if not path:
        return None

    base = cfg["base"]
    html = fetch(f"{base}{path}", wait=0.8)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    motor_data = {}

    for tbl in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
        if "モーター番号" not in headers:
            continue
        # ヘッダーのインデックス確認
        try:
            idx_no     = headers.index("モーター番号")
            idx_2rate  = headers.index("２連対率")
            idx_win    = headers.index("勝率")
            idx_races  = headers.index("出走回数")
        except ValueError:
            continue

        for row in tbl.find_all("tr"):
            tds = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(tds) <= max(idx_no, idx_2rate, idx_win, idx_races):
                continue
            motor_no = tds[idx_no]
            if not motor_no.isdigit():
                continue
            try:
                motor_data[motor_no] = {
                    "top2_rate": float(tds[idx_2rate]),
                    "win_rate":  float(tds[idx_win]),
                    "races":     int(tds[idx_races]),
                }
            except (ValueError, IndexError):
                continue

    if not motor_data:
        return None

    result = {
        "venue_code": jcd,
        "date":       date,
        "scraped_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "motors":     motor_data,
    }

    save_dir = DATA_DIR / "motors" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_motor_stats_venue.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 会場モーター成績保存: {jcd} ({len(motor_data)}機) → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 艇国データバンク 会場別コース成績（v5.19 #A 会場特性データ取得）
# ──────────────────────────────────────────
# 見出しテキスト → カテゴリキー対応（ナイター会場のみ night_18h あり）
_COURSE_STATS_HEAD_MAP = {
    "総合":           "total",
    "SG・G1・G2":     "sg_g1_g2",
    "雨・雪":         "rain_snow",
    "向い風6m以上":   "headwind_6m",
    "追い風6m以上":   "tailwind_6m",
    "波高6cm以上":    "wave_6cm",
    "ナイター":       "night_18h",    # 「ナイター（18時以降）」含む
    "優勝戦":         "champion_race",
}


def _match_stats_category(heading_text: str) -> str | None:
    for key, cat in _COURSE_STATS_HEAD_MAP.items():
        if key in heading_text:
            return cat
    return None


def scrape_stadium_course_stats(jcd: str, save: bool = True) -> dict | None:
    """
    艇国データバンクから会場別コース成績を取得。
    7〜8カテゴリ × 6コース × 9指標（出走数/勝率/1着率/2連対率/3連対率/F/L/平均ST）
    保存先: data/venues/stats/{jcd}_course_stats.json
    """
    url = f"https://boatrace-db.net/stadium/ccourse/pid/{jcd}/"
    html = fetch(url, wait=1.0)
    if not html:
        print(f"[WARN] stadium stats fetch失敗: {jcd}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="tStadiumTcourse")
    if len(tables) < 7:
        print(f"[WARN] stadium stats テーブル数不足: {jcd} / tables={len(tables)}")
        return None

    def _num(s: str) -> float:
        s = (s or "").replace("%", "").strip()
        try:
            return float(s)
        except Exception:
            return 0.0

    def _int(s: str) -> int:
        try:
            return int((s or "").strip())
        except Exception:
            return 0

    result: dict = {"jcd": str(jcd), "source": url, "categories": {}}
    for t in tables:
        prev = t.find_previous(["h2", "h3", "h4"])
        heading = prev.get_text(strip=True) if prev else ""
        cat = _match_stats_category(heading)
        if not cat:
            continue
        rows = t.find_all("tr")[1:]  # ヘッダー除く
        courses: dict = {}
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 9:
                continue
            try:
                c_no = int(cols[0].replace("コース", "").strip())
            except Exception:
                continue
            courses[str(c_no)] = {
                "starts":    _int(cols[1]),
                "win_rate":  _num(cols[2]),    # 勝率
                "top1_pct":  _num(cols[3]),    # 1着率
                "top2_pct":  _num(cols[4]),    # 2連対率
                "top3_pct":  _num(cols[5]),    # 3連対率
                "f_count":   _int(cols[6]),
                "l_count":   _int(cols[7]),
                "avg_st":    _num(cols[8]),
            }
        result["categories"][cat] = courses

    if len(tables) > 0 and not result["categories"]:
        print(f"[WARN] stadium stats 解析失敗: {jcd}")
        return None

    if save:
        out_dir = DATA_DIR / "venues" / "stats"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{jcd}_course_stats.json"
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OK] 会場コース成績保存: {jcd} ({len(tables)}カテゴリ) → {out_path.name}")
    return result


# ──────────────────────────────────────────
# 10. 全レース発走時刻を一括取得
# ──────────────────────────────────────────
def scrape_start_times(jcd: str, date: str) -> dict[int, str]:
    """
    racelist ページから全12Rの発走時刻を取得して返す。
    戻り値: {1: "10:35", 2: "11:05", ...}
    キャッシュ: data/racecards/{date}/{jcd}_start_times.json
    """
    save_dir = DATA_DIR / "racecards" / date
    save_dir.mkdir(parents=True, exist_ok=True)
    cache_path = save_dir / f"{jcd}_start_times.json"

    # キャッシュがあれば返す
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}

    html = fetch(
        "https://www.boatrace.jp/owpc/pc/race/racelist",
        {"jcd": jcd, "hd": date, "rno": "1"},
        wait=0.5,
    )
    if not html:
        return {}

    result = _parse_start_times_from_racelist_html(html)
    if result and len(result) < 12:
        # 不足分のみ最後の既知時刻から補完
        from datetime import datetime as _dt, timedelta as _td
        last_race = max(result.keys())
        base = _dt.strptime(result[last_race], "%H:%M")
        for i in range(last_race + 1, 13):
            extra = i - last_race
            result[i] = (base + _td(minutes=30 * extra)).strftime("%H:%M")

    if result:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in result.items()}, f, ensure_ascii=False)
        print(f"[OK] 発走時刻キャッシュ保存: {jcd} {date} ({len(result)}R) → {cache_path.name}")

    return result


# ──────────────────────────────────────────
# 9. 1日分まとめて取得
# ──────────────────────────────────────────
def scrape_day(jcd: str, date: str, total_races: int = 12,
               include_exhibition: bool = False,
               include_comments: bool = True):
    """
    指定会場・日付の全レース出走表・オッズを取得
    include_exhibition=True で展示タイム・気象も取得（レース直前のみ有効）
    include_comments=True  で選手コメントも取得（run_comment_scraper() 経由）
    """
    print(f"\n=== {date} 会場:{jcd} 全{total_races}R 取得開始 ===")
    _maybe_bootstrap_venue_site_flow(jcd, trigger="scrape_day")

    # コメント/タイムデータを日次一括で先に取得
    # （player_review・timing_only 型は レース単位でなく日次なので 1回だけ実行）
    if include_comments:
        support_data = _load_comment_support()
        venue_status = support_data.get("venues", {}).get(jcd, {}).get("status", "unknown")
        venue_type   = support_data.get("venues", {}).get(jcd, {}).get("type")

        if venue_type in ("player_review", "timing_data", None) or venue_status in ("unknown", "timing_only"):
            # 日次一括処理（レースループの外）
            run_comment_scraper(jcd, date, race_no=None)
            include_comments_per_race = (venue_type == "comments_venue")
        else:
            include_comments_per_race = True
    else:
        include_comments_per_race = False

    races = list(range(1, total_races + 1))
    _run_parallel_race_jobs(
        [(r, lambda r=r: scrape_racecard(jcd, date, r)) for r in races],
        label=f"出走表 {jcd} {date}"
    )
    _run_parallel_race_jobs(
        [(r, lambda r=r: scrape_odds(jcd, date, r)) for r in races],
        label=f"オッズ {jcd} {date}"
    )
    if include_comments_per_race:
        _run_parallel_race_jobs(
            [(r, lambda r=r: run_comment_scraper(jcd, date, race_no=r)) for r in races],
            label=f"コメント {jcd} {date}"
        )
    if include_exhibition:
        _run_parallel_race_jobs(
            [(r, lambda r=r: scrape_exhibition(jcd, date, r)) for r in races],
            label=f"展示 {jcd} {date}"
        )
        _run_parallel_race_jobs(
            [(r, lambda r=r: scrape_weather(jcd, date, r)) for r in races],
            label=f"気象 {jcd} {date}"
        )
    print(f"=== {total_races}R 完了 ===\n")


if __name__ == "__main__":
    import argparse
    today = datetime.date.today().strftime("%Y%m%d")

    parser = argparse.ArgumentParser(description="ボートレース データスクレイパー")
    parser.add_argument("--mode",  default="day",
                        choices=["day","racecard","odds","exhibition","original_exhibition","weather","comments","players"],
                        help="取得モード (デフォルト: day=1日分まとめて)")
    parser.add_argument("--jcd",   default="22", help="会場コード (例: 22=福岡)")
    parser.add_argument("--date",  default=today, help="開催日 YYYYMMDD")
    parser.add_argument("--race",  type=int, default=0, help="レース番号 1〜12 (day/playersモードでは無視)")
    args = parser.parse_args()

    if args.mode in ("day", "racecard", "comments"):
        _maybe_bootstrap_venue_site_flow(args.jcd, trigger=f"scraper:{args.mode}")

    if args.mode == "day":
        scrape_day(jcd=args.jcd, date=args.date, total_races=12)
        _run_parallel_race_jobs(
            [(r, lambda r=r: scrape_players_from_racecard(args.jcd, args.date, r)) for r in range(1, 13)],
            label=f"選手詳細 {args.jcd} {args.date}"
        )
        # 会場固有データ（VENUE_SITE_CONFIG に設定がある場合のみ）
        if args.jcd in VENUE_SITE_CONFIG:
            cfg = VENUE_SITE_CONFIG[args.jcd]
            if "engine_report" in cfg:
                scrape_engine_report(args.jcd, args.date)
            if "player_review" in cfg:
                scrape_player_review(args.jcd, args.date)
        # 会場固有サイト調査状況チェック
        _check_venue_site_support(args.jcd)

    elif args.mode == "racecard":
        if args.race:
            scrape_racecard(args.jcd, args.date, args.race)
        else:
            _run_parallel_race_jobs(
                [(r, lambda r=r: scrape_racecard(args.jcd, args.date, r)) for r in range(1, 13)],
                label=f"出走表 {args.jcd} {args.date}"
            )

    elif args.mode == "odds":
        if args.race:
            scrape_odds(args.jcd, args.date, args.race)
        else:
            _run_parallel_race_jobs(
                [(r, lambda r=r: scrape_odds(args.jcd, args.date, r)) for r in range(1, 13)],
                label=f"オッズ {args.jcd} {args.date}"
            )

    elif args.mode == "exhibition":
        if args.race:
            scrape_exhibition(args.jcd, args.date, args.race)
        else:
            _run_parallel_race_jobs(
                [(r, lambda r=r: scrape_exhibition(args.jcd, args.date, r)) for r in range(1, 13)],
                label=f"展示 {args.jcd} {args.date}"
            )

    elif args.mode == "original_exhibition":
        if args.jcd != "22":
            print(f"[SKIP] original_exhibition は福岡(jcd=22)のみ対応 (指定: {args.jcd})")
        elif args.race:
            scrape_fukuoka_original_exhibition(args.date, args.race)
        else:
            _run_parallel_race_jobs(
                [(r, lambda r=r: scrape_fukuoka_original_exhibition(args.date, r)) for r in range(1, 13)],
                label=f"福岡オリジナル展示 {args.date}"
            )

    elif args.mode == "weather":
        if args.race:
            scrape_weather(args.jcd, args.date, args.race)
        else:
            _run_parallel_race_jobs(
                [(r, lambda r=r: scrape_weather(args.jcd, args.date, r)) for r in range(1, 13)],
                label=f"気象 {args.jcd} {args.date}"
            )

    elif args.mode == "comments":
        # run_comment_scraper() 経由で会場対応状況を自動判定して実行
        if args.race:
            run_comment_scraper(args.jcd, args.date, race_no=args.race)
        else:
            run_comment_scraper(args.jcd, args.date, race_no=None)

    elif args.mode == "players":
        race_no = args.race if args.race else 1
        scrape_players_from_racecard(args.jcd, args.date, race_no)
