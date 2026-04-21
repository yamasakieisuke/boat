#!/usr/bin/env python3
"""
scrape_stadium_data.py  —  boatrace.jp/owpc/pc/data/stadium から
全24場の公式コース勝率・季節別統計・決まり手・進入コース取得率を取得する。

出力:
  data/venues/official_course_stats.json

使い方:
  python3 scripts/scrape_stadium_data.py           # 全24場
  python3 scripts/scrape_stadium_data.py --jcd 22  # 福岡のみ

活用用途:
  - predictor.py の calc_venue_course_mod() での実測値補正
  - venue_characteristics.json の course_mod の検証・更新
"""

import json
import re
import time
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_FILE = DATA_DIR / "venues" / "official_course_stats.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

SEASON_LABELS = {
    "spring": "春季", "summer": "夏季", "autumn": "秋季", "winter": "冬季"
}


def fetch_html(jcd: str) -> str | None:
    url = f"https://www.boatrace.jp/owpc/pc/data/stadium?jcd={jcd}"
    try:
        time.sleep(1.2)
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        res.encoding = "utf-8"
        return res.text
    except Exception as e:
        print(f"[ERROR] {jcd}: {e}")
        return None


def _safe_pct(text: str) -> float | None:
    """'58.1%' → 58.1 に変換。失敗時 None"""
    try:
        return float(text.replace("%", "").strip())
    except:
        return None


def parse_stadium_page(jcd: str, html: str) -> dict:
    """
    stadium ページを解析して以下を返す:
      {
        "jcd": "22",
        "name": "福岡",
        "water_type": "汽水",        # 淡水 / 海水 / 汽水
        "tidal": true/false,          # 干満差あり
        "motor_type": "減音",
        "recent": {                   # 最近3ヶ月
          "course_win_pct":  [58.1, 16.5, ...],   # 1〜6コース
          "winning_move":    [{"nige":92.5, "makuri":...}, ...],  # 1〜6コース
          "frame_to_course": [[99.4, 0.3, ...], ...],             # 6x6マトリクス
        },
        "seasonal": {
          "spring": {"course_win_pct": [...]},
          "summer": {"course_win_pct": [...]},
          "autumn": {"course_win_pct": [...]},
          "winter": {"course_win_pct": [...]},
        }
      }
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {
        "jcd": jcd,
        "name": VENUE_NAMES.get(jcd, jcd),
        "water_type": "",
        "tidal": False,
        "motor_type": "",
    }

    # ── 施設情報 ─────────────────────────────────────────────────
    for el in soup.find_all(["dt", "th", "td"]):
        txt = el.get_text(strip=True)
        if "水質" in txt:
            nx = el.find_next_sibling()
            if nx: result["water_type"] = nx.get_text(strip=True)
        if "モーター" in txt:
            nx = el.find_next_sibling()
            if nx: result["motor_type"] = nx.get_text(strip=True)
        if "干満差" in txt:
            nx = el.find_next_sibling()
            if nx and "あり" in nx.get_text():
                result["tidal"] = True

    # 施設情報テーブルを別途検索
    for li in soup.find_all("li"):
        txt = li.get_text(strip=True)
        if "水質" in txt:
            m = re.search(r"水質[：:]\s*(\S+)", txt)
            if m: result["water_type"] = m.group(1)
        if "干満差" in txt and "あり" in txt:
            result["tidal"] = True
        if "モーター" in txt:
            m = re.search(r"モーター[：:]\s*(\S+)", txt)
            if m: result["motor_type"] = m.group(1)

    # ── テーブルを全抽出して分類 ─────────────────────────────────
    tables = soup.find_all("table")
    recent_win_pct      = None   # 最近3ヶ月 コース別1着率
    recent_winning_move = None   # 最近3ヶ月 決まり手
    frame_to_course     = None   # 枠番別コース取得率
    seasonal            = {"spring": None, "summer": None,
                           "autumn": None, "winter": None}

    # 季節キーワードマップ
    SEASON_KW = [
        ("spring", ["春季", "春", "03/", "3月"]),
        ("summer", ["夏季", "夏", "06/", "6月"]),
        ("autumn", ["秋季", "秋", "09/", "9月"]),
        ("winter", ["冬季", "冬", "12/", "12月"]),
    ]

    def _extract_6floats(table) -> list[float] | None:
        """テーブルから 1〜6コースの数値を順番に抽出"""
        vals = []
        for td in table.find_all(["td", "th"]):
            txt = td.get_text(strip=True)
            m = re.search(r"(\d+\.\d+)%?", txt)
            if m:
                vals.append(float(m.group(1)))
        return vals[:6] if len(vals) >= 6 else None

    def _extract_6x6(table) -> list[list[float]] | None:
        """6x6 の枠→コース取得率マトリクスを抽出"""
        rows_data = []
        for tr in table.find_all("tr"):
            row_vals = []
            for td in tr.find_all(["td", "th"]):
                txt = td.get_text(strip=True)
                m = re.search(r"(\d+\.\d+)%?", txt)
                if m:
                    row_vals.append(float(m.group(1)))
            if len(row_vals) == 6:
                rows_data.append(row_vals)
        return rows_data if len(rows_data) == 6 else None

    def _extract_winning_move(table) -> list[dict] | None:
        """
        決まり手テーブル: 各コースの逃げ/差し/捲り/捲り差し/抜き/恵まれ (%)
        行=コース(1-6)、列=決まり手
        """
        MOVES = ["nige", "sashi", "makuri", "makuri_sashi", "nuki", "megmare"]
        move_labels = ["逃げ", "差し", "捲り", "捲り差し", "抜き", "恵まれ"]
        courses = []
        for tr in table.find_all("tr"):
            vals = []
            for td in tr.find_all("td"):
                txt = td.get_text(strip=True)
                m = re.search(r"(\d+\.\d+)%?", txt)
                if m:
                    vals.append(float(m.group(1)))
            if len(vals) >= 4:
                d = {}
                for i, mv in enumerate(MOVES):
                    d[mv] = vals[i] if i < len(vals) else 0.0
                courses.append(d)
        return courses[:6] if len(courses) >= 4 else None

    # ページテキストで各テーブルの前後の見出しを確認して分類
    # soup.find_all の前後の h2/h3/div テキストを取得して判断
    for table in tables:
        # テーブル直前の見出しテキストを探す
        heading = ""
        for sib in table.find_all_previous(["h2", "h3", "h4", "div", "p"], limit=5):
            txt = sib.get_text(strip=True)
            if len(txt) > 2 and len(txt) < 60:
                heading = txt
                break

        is_frame_course = "枠番" in heading or "コース取得" in heading
        is_winning_move = "決まり手" in heading
        is_course_win   = "1着率" in heading or "コース" in heading

        rows_data = _extract_6x6(table)
        flat_vals = _extract_6floats(table)

        # 枠番→コース取得率（6x6）
        if is_frame_course and rows_data and frame_to_course is None:
            frame_to_course = rows_data
            continue

        # 決まり手
        if is_winning_move and recent_winning_move is None:
            wm = _extract_winning_move(table)
            if wm:
                recent_winning_move = wm
            continue

        # 季節別 or 最近3ヶ月 コース別1着率
        if flat_vals:
            matched_season = None
            for skey, kws in SEASON_KW:
                if any(kw in heading for kw in kws):
                    matched_season = skey
                    break

            if matched_season:
                if seasonal[matched_season] is None:
                    seasonal[matched_season] = {"course_win_pct": flat_vals}
            elif recent_win_pct is None and is_course_win:
                recent_win_pct = flat_vals

    # ── ページ全体から季節別1着率を正規表現でも検索（フォールバック） ──
    all_text = soup.get_text()
    season_pattern = re.compile(
        r"(春季|夏季|秋季|冬季)[^\n]*?\n"
        r".*?(\d+\.\d+)%.*?(\d+\.\d+)%.*?(\d+\.\d+)%.*?(\d+\.\d+)%.*?(\d+\.\d+)%.*?(\d+\.\d+)%",
        re.DOTALL
    )
    for m in season_pattern.finditer(all_text):
        season_jp = m.group(1)
        vals = [float(m.group(i)) for i in range(2, 8)]
        skey = {"春季": "spring", "夏季": "summer",
                "秋季": "autumn", "冬季": "winter"}.get(season_jp)
        if skey and seasonal.get(skey) is None:
            seasonal[skey] = {"course_win_pct": vals}

    # ── 最近3ヶ月の1着率: ページ内で最初の6数値セットを探す ──
    if recent_win_pct is None:
        win_pct_pattern = re.compile(
            r"(\d+\.\d+)%[^%\n]*?(\d+\.\d+)%[^%\n]*?(\d+\.\d+)%[^%\n]*?"
            r"(\d+\.\d+)%[^%\n]*?(\d+\.\d+)%[^%\n]*?(\d+\.\d+)%"
        )
        for m in win_pct_pattern.finditer(all_text):
            vals = [float(m.group(i)) for i in range(1, 7)]
            if abs(sum(vals) - 100.0) < 5.0:   # 合計が100%に近い→コース別1着率
                recent_win_pct = vals
                break

    result["recent"] = {
        "course_win_pct":   recent_win_pct  or [],
        "winning_move":     recent_winning_move or [],
        "frame_to_course":  frame_to_course or [],
    }
    result["seasonal"] = {
        k: v for k, v in seasonal.items() if v is not None
    }

    return result


def load_existing() -> dict:
    if OUT_FILE.exists():
        with open(OUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"_comment": "boatrace.jp/owpc/pc/data/stadium から自動取得した公式コース統計",
            "venues": {}}


def save(data: dict):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run(jcds: list[str]):
    existing = load_existing()
    venues   = existing.setdefault("venues", {})

    for jcd in jcds:
        name = VENUE_NAMES.get(jcd, jcd)
        print(f"[{jcd}] {name} を取得中...", end=" ", flush=True)
        html = fetch_html(jcd)
        if not html:
            print("SKIP")
            continue
        parsed = parse_stadium_page(jcd, html)
        win_pct = parsed.get("recent", {}).get("course_win_pct", [])
        seasonal_count = len(parsed.get("seasonal", {}))
        print(f"1コース{win_pct[0] if win_pct else '?'}%  季節別:{seasonal_count}季  OK")
        venues[jcd] = parsed

    existing["_updated"] = __import__("datetime").date.today().isoformat()
    save(existing)
    print(f"\n[完了] {OUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="boatrace.jp 会場統計スクレイパー")
    parser.add_argument("--jcd", help="会場コード (省略時: 全24場)")
    args = parser.parse_args()

    if args.jcd:
        jcds = [args.jcd.zfill(2)]
    else:
        jcds = [str(i).zfill(2) for i in range(1, 25)]

    run(jcds)
